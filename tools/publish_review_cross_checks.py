#!/usr/bin/env python3
"""Publish compact cross-check summaries into verse YAMLs.

The review flywheel writes detailed local records under ``state/reviews/**``.
Those files are intentionally gitignored, but the public verse-provenance page
fetches ``translation/**/<chapter>/<verse>.yaml`` directly from GitHub and only
shows a cross-check section when the YAML itself has a top-level
``cross_check`` block.

This bridge keeps the raw review payloads local while publishing the small,
auditable agreement summary that readers need:

    python3 tools/publish_review_cross_checks.py --dry-run
    python3 tools/publish_review_cross_checks.py

The script edits only a top-level ``cross_check:`` block, preserving the rest
of each YAML file byte-for-byte.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - local operator error
    print("PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
REVIEWS_ROOT = REPO_ROOT / "state" / "reviews"
TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z0-9_]+:")


@dataclass(frozen=True)
class ReviewRecord:
    path: pathlib.Path
    testament: str
    book_slug: str
    chapter: int
    verse: int
    reviewer_model: str
    strategy: str
    reviewed_at: str
    agreement_score: float
    verdict: str
    issues_found: int

    @property
    def yaml_path(self) -> pathlib.Path:
        nested = (
            TRANSLATION_ROOT
            / self.testament
            / self.book_slug
            / f"{self.chapter:03d}"
            / f"{self.verse:03d}.yaml"
        )
        if nested.exists() or self.testament != "extra_canonical":
            return nested

        # Several extra-canonical writings are published as flat
        # chapter/saying/section files (for example
        # translation/extra_canonical/gospel_of_thomas/088.yaml). Their
        # review jobs use chapter=1 + verse=<section>, so fall back to the
        # public flat record when the nested verse path does not exist.
        flat = (
            TRANSLATION_ROOT
            / self.testament
            / self.book_slug
            / f"{self.verse:03d}.yaml"
        )
        if flat.exists():
            return flat

        # Testaments of the Twelve Patriarchs uses an extra-deep layout:
        #   extra_canonical/testaments_twelve_patriarchs/<patriarch>/<chap>/<verse>.yaml
        # Reviews are keyed on the patriarch slug (e.g. 'asher'), not on
        # the parent collection, so resolve by walking the parent.
        t12p_nested = (
            TRANSLATION_ROOT
            / "extra_canonical"
            / "testaments_twelve_patriarchs"
            / self.book_slug
            / f"{self.chapter:03d}"
            / f"{self.verse:03d}.yaml"
        )
        if t12p_nested.exists():
            return t12p_nested

        return nested

    @property
    def rel_review_path(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()


def parse_review_record(path: pathlib.Path) -> ReviewRecord | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None

    try:
        testament = str(data["testament"])
        book_slug = str(data["book_slug"])
        chapter = int(data["chapter"])
        verse = int(data["verse"])
        agreement_score = float(data["agreement_score"])
    except Exception:
        return None

    issues = data.get("issues") or []
    issues_found = len(issues) if isinstance(issues, list) else 0

    return ReviewRecord(
        path=path,
        testament=testament,
        book_slug=book_slug,
        chapter=chapter,
        verse=verse,
        reviewer_model=str(data.get("reviewer_model") or "unknown"),
        strategy=str(data.get("strategy") or "unknown"),
        reviewed_at=str(data.get("reviewed_at") or ""),
        agreement_score=agreement_score,
        verdict=str(data.get("verdict") or "unknown"),
        issues_found=issues_found,
    )


def iter_review_records() -> list[ReviewRecord]:
    if not REVIEWS_ROOT.exists():
        return []
    out: list[ReviewRecord] = []
    for path in REVIEWS_ROOT.rglob("*.json"):
        record = parse_review_record(path)
        if record is not None:
            out.append(record)
    return out


def score_status(score: float) -> str:
    if score >= 0.90:
        return "high_agreement"
    if score >= 0.75:
        return "moderate_agreement"
    return "needs_review"


def selected_record(records: list[ReviewRecord]) -> ReviewRecord:
    """Pick the current public summary record.

    Review passes are append-only. The newest pass best represents the current
    post-revision state; ties prefer newer Gemini generations so old 2.5 passes
    do not mask a later 3.x pass.
    """

    def model_rank(model: str) -> int:
        m = model.lower()
        if "3.1" in m or "3-pro" in m:
            return 3
        if "2.5" in m:
            return 2
        return 1

    return max(
        records,
        key=lambda r: (
            r.reviewed_at,
            model_rank(r.reviewer_model),
            r.strategy,
            r.rel_review_path,
        ),
    )


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def latest_revision_timestamp(yaml_path: pathlib.Path) -> str | None:
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    candidates: list[str] = []
    revision_pass = data.get("revision_pass")
    if (
        isinstance(revision_pass, dict)
        and revision_pass.get("unchanged") is False
        and revision_pass.get("timestamp")
    ):
        candidates.append(str(revision_pass["timestamp"]))

    for revision in data.get("revisions") or []:
        if isinstance(revision, dict) and revision.get("timestamp"):
            candidates.append(str(revision["timestamp"]))

    parsed = [(parse_timestamp(value), value) for value in candidates]
    parsed = [(stamp, value) for stamp, value in parsed if stamp is not None]
    if not parsed:
        return None
    return max(parsed, key=lambda item: item[0])[1]


def summarize(records: list[ReviewRecord], latest_revision_at: str | None = None) -> dict[str, Any]:
    selected = selected_record(records)
    scores = [r.agreement_score for r in records]
    verdict_counts = Counter(r.verdict for r in records)
    models = sorted({r.reviewer_model for r in records})
    strategies = sorted({r.strategy for r in records})
    issue_records = [r for r in records if r.issues_found > 0]
    passes_with_issues = len(issue_records)
    issue_count = sum(r.issues_found for r in issue_records)

    latest_revision_stamp = parse_timestamp(latest_revision_at)
    open_issue_records = issue_records
    superseded_issue_passes = 0
    if latest_revision_stamp:
        open_issue_records = [
            r
            for r in issue_records
            if (parse_timestamp(r.reviewed_at) or dt.datetime.min.replace(tzinfo=dt.timezone.utc))
            >= latest_revision_stamp
        ]
        superseded_issue_passes = passes_with_issues - len(open_issue_records)

    open_issue_count = sum(r.issues_found for r in open_issue_records)
    superseded_issue_count = issue_count - open_issue_count

    summary = {
        "status": score_status(selected.agreement_score),
        # `agreement` is what the current website component reads; keep
        # `agreement_score` too because that is the repo schema/history term.
        "agreement": round(selected.agreement_score, 4),
        "agreement_score": round(selected.agreement_score, 4),
        "agreement_min": round(min(scores), 4),
        "agreement_max": round(max(scores), 4),
        "verdict": selected.verdict,
        "reviewed_at": selected.reviewed_at,
        "reviewer_model": selected.reviewer_model,
        "strategy": selected.strategy,
        "pass_count": len(records),
        "passes_with_issues": passes_with_issues,
        "issue_count": issue_count,
        "models": models,
        "strategies": strategies,
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "source_review": selected.rel_review_path,
    }
    if latest_revision_at:
        summary["latest_revision_at"] = latest_revision_at
        summary["open_passes_with_issues"] = len(open_issue_records)
        summary["open_issue_count"] = open_issue_count
        summary["superseded_issue_passes"] = superseded_issue_passes
        summary["superseded_issue_count"] = superseded_issue_count
        if passes_with_issues and superseded_issue_passes == passes_with_issues:
            summary["review_state"] = "needs_recheck_after_revision"
            summary["needs_recheck_after_revision"] = True
    return summary


def render_cross_check_block(summary: dict[str, Any]) -> str:
    block = yaml.safe_dump(
        {"cross_check": summary},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
    return "\n" + block.rstrip() + "\n"


def replace_top_level_cross_check(original: str, rendered_block: str) -> str:
    lines = original.splitlines(keepends=True)
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("cross_check:"):
            start = idx
            break

    if start is None:
        base = original.rstrip() + "\n"
        return base + rendered_block

    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and TOP_LEVEL_KEY_RE.match(line):
            break
        end += 1

    return "".join(lines[:start]).rstrip() + "\n" + rendered_block + "".join(lines[end:])


def publish(dry_run: bool) -> dict[str, Any]:
    records = iter_review_records()
    grouped: dict[pathlib.Path, list[ReviewRecord]] = defaultdict(list)
    missing_yaml: list[ReviewRecord] = []

    for record in records:
        yaml_path = record.yaml_path
        if not yaml_path.exists():
            missing_yaml.append(record)
            continue
        grouped[yaml_path].append(record)

    changed = 0
    already_current = 0
    for yaml_path, verse_records in sorted(grouped.items()):
        summary = summarize(
            verse_records,
            latest_revision_at=latest_revision_timestamp(yaml_path),
        )
        rendered = render_cross_check_block(summary)
        original = yaml_path.read_text(encoding="utf-8")
        updated = replace_top_level_cross_check(original, rendered)
        if updated == original:
            already_current += 1
            continue
        changed += 1
        if not dry_run:
            yaml_path.write_text(updated, encoding="utf-8")

    return {
        "review_records_with_scores": len(records),
        "verse_yaml_targets": len(grouped),
        "changed": changed,
        "already_current": already_current,
        "missing_yaml_records": len(missing_yaml),
        "missing_yaml_verse_targets": len({r.yaml_path for r in missing_yaml}),
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without editing YAMLs.")
    args = parser.parse_args()

    summary = publish(dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
