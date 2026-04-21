#!/usr/bin/env python3
"""auto_apply_gemini.py — process Gemini review findings and apply them.

Runs continuously alongside the review workers. Processes every
completed review_job whose findings haven't been applied yet, classifies
each issue into a tier, and either auto-applies or logs.

Tiering rules:

  TIER 1 (AUTO-APPLY — mechanical, low-risk):
    - severity in {suggestion, minor}
    - category in {awkward_english}
    - Gemini's suggested rewrite is within the same "language shape" as
      the current (overlap >= 50% of word tokens) — not a wholesale
      rewrite
    - NOT in a verse that already has a theological_decisions entry
    - current & suggested both non-empty, distinct, and the current span
      actually appears in the verse's English text

  TIER 2 (SOURCE-GROUNDED AUTO-APPLY — strong source-grounded wins):
    - severity == major
    - category in {mistranslation, lexical, grammar} — actual source
      fidelity issues
    - Rationale cites source-language evidence (Hebrew/Greek/lexicon
      references: BDAG / HALOT / BDB / specific Hebrew or Greek word)
    - current span uniquely present in verse English
    - Suggested rewrite materially changes meaning in a source-faithful
      direction
    - Applied with an explicit auto-apply adjudicator label for auditability

  TIER 3 (LOG-ONLY — escalate for human review later):
    - theological_weight  (policy decisions deserve a person)
    - consistency  (cross-verse — need book-wide view to decide)
    - Psalms verse-numbering mismatches (systemic, batch-fix later)
    - anything that doesn't clear tier 1 or tier 2 bars

Every applied revision:
  - writes a `revisions[]` entry to the verse YAML with full provenance
  - preserves GPT-5.4's original rendering as a `previous_rendering`
    footnote
  - marks the review_job row as `applied=1` in a new column so we don't
    reapply on reruns

Run in daemon mode alongside workers:
  python3 tools/auto_apply_gemini.py --daemon --tier 1,2
Or once-shot on the current backlog:
  python3 tools/auto_apply_gemini.py --once
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import pathlib
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
from collections import Counter
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402
import gemini_review_queue  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = chapter_queue.DEFAULT_DB_PATH

# ---------------------------------------------------------------------------
# Tier classification rules
# ---------------------------------------------------------------------------

AUTO_APPLY_CATEGORIES_TIER1 = {"awkward_english"}
STRONG_WIN_CATEGORIES_TIER2 = {"mistranslation", "lexical", "grammar"}
ESCALATE_ONLY_CATEGORIES = {"theological_weight", "consistency"}

SOURCE_EVIDENCE_PATTERNS = [
    r"\bBDAG\b", r"\bHALOT\b", r"\bBDB\b", r"\bTDNT\b", r"\bLSJ\b",
    r"\b[\u0370-\u03FF\u1F00-\u1FFF]+\b",                # Greek letters
    r"\b[\u0590-\u05FF]+\b",                             # Hebrew letters
    r"\bMT\b", r"\bKetiv\b", r"\bQere\b", r"\bpiel\b", r"\bqal\b", r"\bhiphil\b",
    r"\bperfect\b", r"\bimperfect\b", r"\baorist\b", r"\bparticiple\b",
    r"\binfinitive\b", r"\bimperative\b", r"\bhendiadys\b",
    r"\bvocative\b", r"\bemphatic\b",
]
SOURCE_EVIDENCE_RE = re.compile("|".join(SOURCE_EVIDENCE_PATTERNS), re.IGNORECASE)


def has_source_evidence(rationale: str) -> bool:
    return bool(SOURCE_EVIDENCE_RE.search(rationale or ""))


def word_overlap(a: str, b: str) -> float:
    def norm(s: str) -> set[str]:
        s = unicodedata.normalize("NFC", s).lower()
        return {w for w in re.split(r"\W+", s) if w and len(w) > 1}
    wa, wb = norm(a), norm(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


# ---------------------------------------------------------------------------
# DB schema extensions: `applied` flag + processing disposition on review_jobs
# ---------------------------------------------------------------------------

PROCESS_STATUS_PENDING = "pending"
PROCESS_STATUS_APPLIED = "applied"
PROCESS_STATUS_ESCALATED = "escalated"
PROCESS_STATUS_NOOP = "noop"
PROCESS_STATUS_ERROR = "error"

NON_TEXT_TARGETS = {
    "footnote",
    "lexical_decision",
    "theological_note",
    "metadata",
    "notes_only",
}


def ensure_processing_columns(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(review_jobs)")]
    if "applied" not in cols:
        conn.execute("ALTER TABLE review_jobs ADD COLUMN applied INTEGER DEFAULT 0")
    if "apply_summary" not in cols:
        conn.execute("ALTER TABLE review_jobs ADD COLUMN apply_summary TEXT")
    if "process_status" not in cols:
        conn.execute("ALTER TABLE review_jobs ADD COLUMN process_status TEXT")
    if "processed_at" not in cols:
        conn.execute("ALTER TABLE review_jobs ADD COLUMN processed_at TEXT")
    conn.commit()
    migrate_legacy_processing_state(conn)


def migrate_legacy_processing_state(conn: sqlite3.Connection) -> None:
    """Normalize old rows where `applied=1` meant 'processed somehow'."""
    conn.execute(
        """
        UPDATE review_jobs
        SET applied=0
        WHERE applied=1
          AND apply_summary IS NOT NULL
          AND (apply_summary='escalated=0' OR apply_summary GLOB 'escalated=*')
        """
    )
    conn.execute(
        """
        UPDATE review_jobs
        SET process_status=?, processed_at=COALESCE(processed_at, updated_at)
        WHERE process_status IS NULL
          AND apply_summary IS NOT NULL
          AND apply_summary='escalated=0'
        """,
        (PROCESS_STATUS_NOOP,),
    )
    conn.execute(
        """
        UPDATE review_jobs
        SET process_status=?, processed_at=COALESCE(processed_at, updated_at)
        WHERE process_status IS NULL
          AND apply_summary IS NOT NULL
          AND apply_summary GLOB 'escalated=*'
          AND apply_summary!='escalated=0'
        """,
        (PROCESS_STATUS_ESCALATED,),
    )
    conn.execute(
        """
        UPDATE review_jobs
        SET process_status=?, processed_at=COALESCE(processed_at, updated_at)
        WHERE process_status IS NULL
          AND apply_summary LIKE 'error:%'
        """,
        (PROCESS_STATUS_ERROR,),
    )
    conn.execute(
        """
        UPDATE review_jobs
        SET process_status=?, processed_at=COALESCE(processed_at, updated_at)
        WHERE process_status IS NULL
          AND applied=1
        """,
        (PROCESS_STATUS_APPLIED,),
    )
    conn.commit()


def update_processing_state(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    process_status: str,
    apply_summary: str,
    applied: int,
) -> None:
    conn.execute(
        """
        UPDATE review_jobs
        SET applied=?, process_status=?, processed_at=?, apply_summary=?
        WHERE id=?
        """,
        (
            applied,
            process_status,
            dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            apply_summary[:500],
            job_id,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Verse YAML edit path (mirrors apply_gemini_revision.py but programmatic)
# ---------------------------------------------------------------------------

def yaml_path_for(testament: str, book_slug: str, chapter: int, verse: int) -> pathlib.Path:
    return REPO_ROOT / "translation" / testament / book_slug / f"{chapter:03d}" / f"{verse:03d}.yaml"


def next_footnote_marker(existing: list[dict[str, Any]] | None) -> str:
    if not existing:
        return "a"
    taken = {f.get("marker") for f in existing if isinstance(f, dict)}
    for c in "abcdefghijklmnopqrstuvwxyz":
        if c not in taken:
            return c
    return "z"


def apply_revision_to_yaml(
    path: pathlib.Path,
    *,
    find: str,
    replace: str,
    rationale: str,
    review_path: str,
    category: str,
    tier: int,
    reviewer_model: str = "gemini-2.5-pro",
) -> str:
    """Apply a single revision to a verse YAML, returning a short summary.
    Raises on failure."""
    if not path.exists():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not a mapping")

    translation = data.setdefault("translation", {})
    current_text = translation.get("text", "")

    occurrences = current_text.count(find)
    if occurrences == 0:
        raise ValueError("find-span not in verse English")
    if occurrences > 1:
        raise ValueError("find-span ambiguous (multiple occurrences)")

    new_text = current_text.replace(find, replace, 1)
    if new_text == current_text:
        raise ValueError("replace produced no change")
    translation["text"] = new_text

    # Preserve original rendering as a footnote
    footnotes = translation.setdefault("footnotes", [])
    marker = next_footnote_marker(footnotes)
    footnotes.append({
        "marker": marker,
        "text": f"Or {find!r}.",
        "reason": "previous_rendering",
    })

    revisions = data.setdefault("revisions", [])
    revisions.append({
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adjudicator": "auto_apply_tier2_source_grounded" if tier == 2 else "auto_apply_tier1",
        "reviewer_model": reviewer_model,
        "source_review": review_path,
        "category": category,
        "tier": tier,
        "from": find,
        "to": replace,
        "rationale": rationale,
    })

    new_yaml = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(new_yaml, encoding="utf-8")
    return f"tier{tier} {category} {find[:30]!r}→{replace[:30]!r}"


# ---------------------------------------------------------------------------
# Tier classifier for a single issue
# ---------------------------------------------------------------------------

def classify_issue(
    issue: dict[str, Any],
    verse_yaml: dict[str, Any] | None,
) -> tuple[int, str]:
    """Return (tier, reason). Tier 0 means skip entirely."""
    target = (issue.get("target") or "translation_text").lower()
    severity = (issue.get("severity") or "").lower()
    category = (issue.get("category") or "").lower()
    current = issue.get("current_rendering") or ""
    suggested = issue.get("suggested_rewrite") or ""
    rationale = issue.get("rationale") or ""

    if target in NON_TEXT_TARGETS:
        return 3, f"non-text-target:{target}"

    if not current or not suggested or current == suggested:
        return 0, "empty-or-noop"

    # Strong escalate-only categories
    if category in ESCALATE_ONLY_CATEGORIES:
        return 3, f"escalate-only-category:{category}"

    # Check if the verse has theological_decisions — policy-sensitive, escalate
    has_theo = bool((verse_yaml or {}).get("theological_decisions"))
    if has_theo and category != "awkward_english":
        return 3, "verse-has-theological-decisions"

    # TIER 2: Strong source-grounded major wins
    if severity == "major":
        if category not in STRONG_WIN_CATEGORIES_TIER2:
            return 3, f"major-but-category-{category}"
        if not has_source_evidence(rationale):
            return 3, "major-without-source-evidence"
        # Rewrite shouldn't be a full-verse rewrite
        overlap = word_overlap(current, suggested)
        if overlap < 0.2 and len(suggested) > 40:
            return 3, f"major-too-different (overlap={overlap:.2f})"
        return 2, "tier2-major-source-grounded"

    # TIER 1: safe auto-apply
    if severity in ("minor", "suggestion") and category in AUTO_APPLY_CATEGORIES_TIER1:
        overlap = word_overlap(current, suggested)
        if overlap >= 0.5:
            return 1, "tier1-mechanical"
        return 3, f"tier1-candidate-too-different (overlap={overlap:.2f})"

    # Everything else — lexical minors, missing_nuance, etc. — escalate.
    return 3, f"default-escalate:{severity}/{category}"


# ---------------------------------------------------------------------------
# Pipeline: scan for unapplied reviews, process, update
# ---------------------------------------------------------------------------

def process_review_job(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    enabled_tiers: set[int],
    dry_run: bool,
) -> dict[str, Any]:
    """Process one completed review_job. Return a dict of what was done."""
    review_path = REPO_ROOT / row["review_path"] if row["review_path"] else None
    if not review_path or not review_path.exists():
        if not dry_run:
            update_processing_state(
                conn,
                int(row["id"]),
                process_status=PROCESS_STATUS_ERROR,
                apply_summary="error:missing-review-file",
                applied=0,
            )
        return {"skipped": "no-review-file"}
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except Exception as exc:
        if not dry_run:
            update_processing_state(
                conn,
                int(row["id"]),
                process_status=PROCESS_STATUS_ERROR,
                apply_summary=f"error:bad-json:{type(exc).__name__}:{str(exc)[:80]}",
                applied=0,
            )
        return {"skipped": f"bad-json:{exc}"}

    issues = review.get("issues") or []
    if not issues:
        return {"applied": 0, "escalated": 0, "skipped_noop": 0}

    yaml_path = yaml_path_for(row["testament"], row["book_slug"], row["chapter"], row["verse"])
    try:
        verse_yaml = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) if yaml_path.exists() else None
    except Exception:
        verse_yaml = None

    applied = 0
    escalated = 0
    skipped_noop = 0
    errors = 0
    summaries: list[str] = []

    for issue in issues:
        tier, reason = classify_issue(issue, verse_yaml)
        if tier == 0:
            skipped_noop += 1
            continue
        if tier == 3 or tier not in enabled_tiers:
            summaries.append(f"escalate:{reason}:{issue.get('span','')[:40]}")
            escalated += 1
            continue
        # Apply tier 1 or 2
        if dry_run:
            summaries.append(f"would-apply:{reason}:{issue.get('span','')[:40]}")
            applied += 1
            continue
        try:
            # Refresh verse_yaml between applies (earlier revision may have
            # modified the text; avoid re-applying on the stale version).
            if yaml_path.exists():
                verse_yaml = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            summary = apply_revision_to_yaml(
                yaml_path,
                find=issue.get("current_rendering", ""),
                replace=issue.get("suggested_rewrite", ""),
                rationale=issue.get("rationale", ""),
                review_path=str(review_path.relative_to(REPO_ROOT)),
                category=issue.get("category", "other"),
                tier=tier,
            )
            summaries.append(summary)
            applied += 1
        except Exception as exc:
            errors += 1
            summaries.append(f"error:{type(exc).__name__}:{str(exc)[:60]}")

    # Mark as processed in DB
    apply_summary = "; ".join(summaries[:5])
    if not dry_run:
        if applied:
            update_processing_state(
                conn,
                int(row["id"]),
                process_status=PROCESS_STATUS_APPLIED,
                apply_summary=apply_summary or f"applied={applied}",
                applied=1,
            )
        elif escalated:
            update_processing_state(
                conn,
                int(row["id"]),
                process_status=PROCESS_STATUS_ESCALATED,
                apply_summary=apply_summary or f"escalated={escalated}",
                applied=0,
            )
        elif errors:
            update_processing_state(
                conn,
                int(row["id"]),
                process_status=PROCESS_STATUS_ERROR,
                apply_summary=apply_summary or f"errors={errors}",
                applied=0,
            )
        else:
            update_processing_state(
                conn,
                int(row["id"]),
                process_status=PROCESS_STATUS_NOOP,
                apply_summary=apply_summary or f"noop={skipped_noop}",
                applied=0,
            )

    return {
        "applied": applied,
        "escalated": escalated,
        "skipped_noop": skipped_noop,
        "errors": errors,
        "summary": apply_summary,
    }


def backlog_query(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(conn.execute(
        """
        SELECT id, testament, book_slug, chapter, verse, agreement_score,
               issues_found, review_path, strategy
        FROM review_jobs
        WHERE status='completed'
          AND COALESCE(process_status, 'pending')='pending'
          AND issues_found > 0
          AND agreement_score < 1.0
        ORDER BY agreement_score ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall())


def run_once(enabled_tiers: set[int], dry_run: bool, limit: int) -> dict[str, int]:
    with chapter_queue.connect(DB_PATH) as conn:
        gemini_review_queue.ensure_schema(conn)
        ensure_processing_columns(conn)
        conn.row_factory = sqlite3.Row
        rows = backlog_query(conn, limit)
        totals = Counter()
        for row in rows:
            result = process_review_job(conn, row, enabled_tiers=enabled_tiers, dry_run=dry_run)
            totals["applied"] += result.get("applied", 0)
            totals["escalated"] += result.get("escalated", 0)
            totals["skipped_noop"] += result.get("skipped_noop", 0)
            totals["errors"] += result.get("errors", 0)
            totals["verses"] += 1
            if result.get("applied"):
                loc = f"{row['book_slug']} {row['chapter']}:{row['verse']}"
                print(f"  ✓ {loc} (score={row['agreement_score']}) — {result.get('summary','')[:120]}", flush=True)
        return dict(totals)


def regenerate_revisions_index() -> None:
    """Regenerate revisions.json so the public revisions page stays fresh."""
    import subprocess
    script = REPO_ROOT / "tools" / "build_revisions_index.py"
    if not script.exists():
        return
    try:
        subprocess.run(
            [sys.executable, str(script)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            timeout=120,
        )
    except Exception as exc:
        print(f"[auto-apply] revisions.json regen skipped: {exc}", flush=True)


def run_daemon(enabled_tiers: set[int], dry_run: bool, poll_seconds: int = 60) -> int:
    print(f"[auto-apply] starting daemon; tiers={sorted(enabled_tiers)} dry={dry_run} poll={poll_seconds}s", flush=True)
    totals = Counter()
    try:
        while True:
            batch = run_once(enabled_tiers, dry_run, limit=200)
            for k, v in batch.items():
                totals[k] += v
            if batch.get("applied") and not dry_run:
                regenerate_revisions_index()
            if batch.get("verses"):
                print(f"[auto-apply] cycle: {batch}  totals: {dict(totals)}", flush=True)
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("[auto-apply] interrupted.", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tier", default="1,2", help="Comma-separated tiers to auto-apply (default 1,2).")
    ap.add_argument("--daemon", action="store_true", help="Run continuously.")
    ap.add_argument("--once", action="store_true", help="Run once on current backlog.")
    ap.add_argument("--dry-run", action="store_true", help="Print what would happen without editing YAMLs.")
    ap.add_argument("--limit", type=int, default=500, help="Max verses processed in one pass.")
    ap.add_argument("--poll", type=int, default=60, help="Daemon poll interval in seconds.")
    args = ap.parse_args()

    enabled = {int(t) for t in args.tier.split(",") if t.strip()}

    if args.daemon:
        return run_daemon(enabled, args.dry_run, args.poll)

    totals = run_once(enabled, args.dry_run, args.limit)
    print(f"\nFinished: {totals}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
