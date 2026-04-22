#!/usr/bin/env python3
"""adjudicate_escalated_gemini.py — Gemini 3.1 Pro second-opinion pass
on Gemini-escalated tier-3 findings.

Same-family variant of adjudicate_escalated.py. Chosen when the
author-intent criterion benefits from Gemini's alignment on
theologically loaded passages more than from cross-family coverage.

Reads review_jobs rows where process_status='escalated', replays each
issue through a fresh Gemini 3.1 Pro call with the tier-3 adjudicator
prompt, and either applies or rejects based on the verdict.

Prompt: tools/prompts/tier3_adjudicator_gemini.md
Applied adjudications record both the original review and the
adjudication in the verse YAML revisions[] chain.

Usage:
  python tools/adjudicate_escalated_gemini.py --strategy phase10_% --limit 50
  python tools/adjudicate_escalated_gemini.py --strategy phase10_% --daemon
  python tools/adjudicate_escalated_gemini.py --dry-run

Environment:
  GEMINI_API_KEY (auto-fetched from AWS Secrets Manager
  /cartha/openclaw/gemini_api_key in us-west-2 if not set)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402
import auto_apply_gemini as aa  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = chapter_queue.DEFAULT_DB_PATH
PROMPT_PATH = REPO_ROOT / "tools" / "prompts" / "tier3_adjudicator_gemini.md"
BOOK_CONTEXTS_DIR = REPO_ROOT / "tools" / "prompts" / "book_contexts"

ADJUDICATOR_LABEL = "gemini_3_1_pro_tier3_adjudicator"
GEMINI_MODEL = os.environ.get("CARTHA_TIER3_MODEL", "gemini-3.1-pro-preview")
AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


# ---------------------------------------------------------------------------
# Gemini 3.1 Pro call
# ---------------------------------------------------------------------------


def _fetch_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    import subprocess
    try:
        r = subprocess.run(
            [
                "aws", "secretsmanager", "get-secret-value",
                "--secret-id", "/cartha/openclaw/gemini_api_key",
                "--region", "us-west-2",
                "--query", "SecretString", "--output", "text",
            ],
            capture_output=True, text=True, check=True, timeout=15,
        )
        raw = r.stdout.strip()
        try:
            return json.loads(raw).get("api_key", raw)
        except json.JSONDecodeError:
            return raw
    except Exception:
        return ""


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_book_context(book_slug: str) -> str:
    p = BOOK_CONTEXTS_DIR / f"{book_slug}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _load_verse_source(testament: str, book_slug: str, chapter: int, verse: int) -> dict[str, Any]:
    """Return (source_text, english_text, full_yaml_as_string)."""
    base = REPO_ROOT / "translation" / testament / book_slug
    path = base / f"{chapter:03d}" / f"{verse:03d}.yaml"
    if not path.exists() and chapter == 1:
        path = base / f"{verse:03d}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    source_block = data.get("source") or {}
    source_text = source_block.get("text") or source_block.get("body") or ""
    english = (data.get("translation") or {}).get("text") or ""
    return {
        "yaml_path": path,
        "yaml_data": data,
        "source_text": source_text,
        "english_text": english,
        "raw_yaml": raw,
    }


_ADJUDICATOR_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["verdict", "confidence", "reasoning"],
    "properties": {
        "verdict": {"type": "string", "enum": ["apply", "reject", "modify"]},
        "confidence": {"type": "number"},
        "suggested_rewrite": {"type": "string"},
        "reasoning": {"type": "string"},
    },
}


def call_gemini_adjudicator(
    *,
    system_prompt: str,
    book_context: str,
    verse_ref: str,
    source_text: str,
    current_english: str,
    issue: dict[str, Any],
    timeout: int = 120,
    max_retries: int = 4,
) -> dict[str, Any]:
    """Call Gemini 3.1 Pro with the adjudicator prompt and return parsed JSON."""
    api_key = _fetch_gemini_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not available (env or AWS Secrets Manager)")

    user_payload = {
        "verse_reference": verse_ref,
        "source_text": source_text,
        "current_english": current_english,
        "issue_category": issue.get("category"),
        "issue_severity": issue.get("severity"),
        "issue_target": issue.get("target"),
        "span": issue.get("span"),
        "current_rendering": issue.get("current_rendering"),
        "proposed_rewrite": issue.get("suggested_rewrite"),
        "reviewer_rationale": issue.get("rationale"),
        "reviewer_confidence": issue.get("confidence"),
    }

    full_system = system_prompt
    if book_context:
        full_system = full_system + "\n\n---\n\n# Book Context\n\n" + book_context

    url = f"{AI_STUDIO_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"
    user_text = (
        "Adjudicate this finding and return JSON matching the schema.\n\n"
        + json.dumps(user_payload, ensure_ascii=False, indent=2)
    )
    body = {
        "systemInstruction": {"parts": [{"text": full_system}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseSchema": _ADJUDICATOR_RESPONSE_SCHEMA,
        },
    }
    headers = {"Content-Type": "application/json"}

    backoff = [10, 30, 90, 240]
    last_err: Exception | None = None
    for attempt in range(max_retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
            candidates = resp_body.get("candidates") or []
            if not candidates:
                raise RuntimeError(f"Gemini no candidates; promptFeedback={resp_body.get('promptFeedback')}")
            parts = (candidates[0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if not text:
                raise RuntimeError("empty adjudicator response")
            return json.loads(text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            last_err = RuntimeError(f"Gemini HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
                continue
            raise last_err
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = RuntimeError(f"{type(exc).__name__}: {exc}")
            if attempt < max_retries - 1:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
                continue
            raise last_err
    raise last_err  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Applying a Gemini-adjudicator-approved change
# ---------------------------------------------------------------------------


def apply_gemini_approved_change(
    *,
    yaml_path: pathlib.Path,
    find: str,
    replace: str,
    rationale: str,
    review_path: str,
    category: str,
    adjudicator_confidence: float,
) -> str:
    """Like auto_apply_gemini.apply_revision_to_yaml, but labels the
    adjudicator as the Gemini 3.1 Pro tier-3 pass and notes the original
    Gemini review as the source_review with its rationale."""
    if not yaml_path.exists():
        raise FileNotFoundError(yaml_path)
    raw = yaml_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{yaml_path}: not a mapping")

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

    footnotes = translation.setdefault("footnotes", [])
    marker = aa.next_footnote_marker(footnotes)
    footnotes.append({
        "marker": marker,
        "text": f"Or {find!r}.",
        "reason": "previous_rendering",
    })

    revisions = data.setdefault("revisions", [])
    revisions.append({
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adjudicator": ADJUDICATOR_LABEL,
        "adjudicator_confidence": round(float(adjudicator_confidence), 2),
        "reviewer_model": "gemini-3.1-pro-preview",
        "source_review": review_path,
        "category": category,
        "tier": 3,
        "from": find,
        "to": replace,
        "rationale": rationale,
    })
    yaml_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    return f"gemini-tier3-applied {category} {find[:30]!r}→{replace[:30]!r}"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def process_one_row(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    system_prompt: str,
    dry_run: bool,
) -> dict[str, int]:
    counts = {
        "issues": 0,
        "applied": 0,
        "rejected": 0,
        "modified_applied": 0,
        "errors": 0,
        "skipped_no_find": 0,
    }
    review_path_rel = row["review_path"]
    if not review_path_rel:
        return counts
    review_path = REPO_ROOT / review_path_rel
    if not review_path.exists():
        return counts
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except Exception:
        counts["errors"] += 1
        return counts

    issues = review.get("issues") or []
    if not issues:
        return counts

    testament = row["testament"]
    book_slug = row["book_slug"]
    chapter = int(row["chapter"])
    verse = int(row["verse"])
    book_context = _load_book_context(book_slug)
    try:
        vs = _load_verse_source(testament, book_slug, chapter, verse)
    except FileNotFoundError:
        counts["errors"] += 1
        return counts

    verse_ref = f"{book_slug} {chapter}:{verse}"
    summaries = []
    for issue in issues:
        # Skip issues that auto-apply would have refused outright (no find-span
        # or non-text target)
        target = issue.get("target") or "translation_text"
        if target in aa.NON_TEXT_TARGETS:
            summaries.append(f"skip:non-text:{issue.get('category')}")
            continue
        current_rendering = issue.get("current_rendering") or ""
        suggested = issue.get("suggested_rewrite") or ""
        if not current_rendering or not suggested or current_rendering == suggested:
            counts["skipped_no_find"] += 1
            continue

        counts["issues"] += 1
        try:
            verdict = call_gemini_adjudicator(
                system_prompt=system_prompt,
                book_context=book_context,
                verse_ref=verse_ref,
                source_text=vs["source_text"],
                current_english=vs["english_text"],
                issue=issue,
            )
        except Exception as exc:
            counts["errors"] += 1
            summaries.append(f"adj-error:{type(exc).__name__}:{str(exc)[:60]}")
            continue

        action = (verdict.get("verdict") or "").lower()
        conf = verdict.get("confidence") or 0.0
        reasoning = verdict.get("reasoning") or ""
        if action == "apply":
            if dry_run:
                summaries.append(f"would-apply:{issue.get('category')}:{current_rendering[:30]!r}→{suggested[:30]!r}")
                counts["applied"] += 1
                continue
            try:
                summary = apply_gemini_approved_change(
                    yaml_path=vs["yaml_path"],
                    find=current_rendering,
                    replace=suggested,
                    rationale=f"{issue.get('rationale','')[:500]} | Adjudicator: {reasoning[:200]}",
                    review_path=review_path_rel,
                    category=issue.get("category", "other"),
                    adjudicator_confidence=conf,
                )
                summaries.append(summary)
                counts["applied"] += 1
            except ValueError as exc:
                counts["skipped_no_find"] += 1
                summaries.append(f"skip-apply:{str(exc)[:40]}")
            except Exception as exc:
                counts["errors"] += 1
                summaries.append(f"apply-error:{type(exc).__name__}")
        elif action == "modify":
            modified = verdict.get("suggested_rewrite") or suggested
            if dry_run:
                summaries.append(f"would-modify:{modified[:40]!r}")
                counts["modified_applied"] += 1
                continue
            try:
                summary = apply_gemini_approved_change(
                    yaml_path=vs["yaml_path"],
                    find=current_rendering,
                    replace=modified,
                    rationale=f"Adjudicator-modified: {reasoning[:500]}",
                    review_path=review_path_rel,
                    category=issue.get("category", "other"),
                    adjudicator_confidence=conf,
                )
                summaries.append(summary)
                counts["modified_applied"] += 1
            except ValueError:
                counts["skipped_no_find"] += 1
            except Exception:
                counts["errors"] += 1
        else:
            counts["rejected"] += 1
            summaries.append(f"adj-reject:{(reasoning[:60])!r}")

    # Record adjudicated state
    if not dry_run:
        apply_summary = "; ".join(summaries[:5])[:500]
        if counts["applied"] + counts["modified_applied"] > 0:
            new_status = "gemini_tier3_applied"
        else:
            new_status = "gemini_tier3_rejected"
        conn.execute(
            """
            UPDATE review_jobs
            SET process_status=?, processed_at=?, apply_summary=?
            WHERE id=?
            """,
            (
                new_status,
                dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                apply_summary,
                int(row["id"]),
            ),
        )
        conn.commit()

    return counts


def claim_next_escalated(
    conn: sqlite3.Connection,
    strategy_glob: str,
    worker_id: str,
) -> dict[str, Any] | None:
    """Atomically pick the next escalated row and mark it 'adjudicating'
    so parallel adjudicators don't collide. Returns the row or None."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT id, strategy, testament, book_slug, chapter, verse, review_path "
        "FROM review_jobs "
        "WHERE process_status='escalated' AND strategy LIKE ? "
        "ORDER BY id ASC LIMIT 1",
        (strategy_glob,),
    ).fetchone()
    if row is None:
        conn.commit()
        return None
    conn.execute(
        "UPDATE review_jobs SET process_status='adjudicating', worker_id=?, processed_at=? WHERE id=?",
        (worker_id, now, row["id"]),
    )
    conn.commit()
    return dict(zip([c for c in row.keys()], row))


def run_batch(
    conn: sqlite3.Connection,
    strategy_glob: str,
    limit: int | None,
    dry_run: bool,
    worker_id: str = "adj-0",
) -> dict[str, int]:
    system_prompt = _load_system_prompt()
    totals = {"issues": 0, "applied": 0, "rejected": 0, "modified_applied": 0, "errors": 0, "skipped_no_find": 0, "rows": 0}
    while True:
        if dry_run:
            # dry-run uses the original non-claim path so read-only preview is clean
            cur = conn.cursor()
            q = ("SELECT id, strategy, testament, book_slug, chapter, verse, review_path "
                 "FROM review_jobs WHERE process_status='escalated' AND strategy LIKE ? "
                 "ORDER BY id ASC")
            params: list[Any] = [strategy_glob]
            if limit:
                q += " LIMIT ?"; params.append(limit)
            cur.execute(q, params)
            rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
            for row in rows:
                totals["rows"] += 1
                counts = process_one_row(conn, row, system_prompt, dry_run)
                for k, v in counts.items(): totals[k] = totals.get(k, 0) + v
            return totals

        row = claim_next_escalated(conn, strategy_glob, worker_id)
        if row is None:
            return totals
        totals["rows"] += 1
        counts = process_one_row(conn, row, system_prompt, dry_run)
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v
        if totals["rows"] % 20 == 0:
            print(f"  [{worker_id}] [{totals['rows']}] applied={totals['applied']} rejected={totals['rejected']} modified={totals['modified_applied']} err={totals['errors']}", flush=True)
        if limit and totals["rows"] >= limit:
            return totals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strategy", default="phase9_%", help="Strategy glob pattern (SQL LIKE)")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to process in this run")
    ap.add_argument("--dry-run", action="store_true", help="Print verdicts without applying")
    ap.add_argument("--daemon", action="store_true", help="Loop, processing new escalated rows as they arrive")
    ap.add_argument("--worker-id", default="adj-0", help="Unique worker id when running multiple adjudicators")
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB_PATH), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        while True:
            print(f"[{args.worker_id}] run starting; strategy like {args.strategy!r} dry={args.dry_run} limit={args.limit}", flush=True)
            t0 = time.time()
            totals = run_batch(conn, args.strategy, args.limit, args.dry_run, worker_id=args.worker_id)
            dur = round(time.time() - t0, 1)
            print(f"[adjudicator] done in {dur}s: {totals}", flush=True)
            if not args.daemon:
                break
            time.sleep(60)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
