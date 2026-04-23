#!/usr/bin/env python3
"""phase10_generate_comparison.py — compare pilot output to baseline review rows.

Reads a Phase 10 stacked-pilot directory (created by
`tools/phase10_stacked_pilot.py`), resolves the requested baseline
strategy from `state/chapter_queue.sqlite3`, loads the immutable
baseline review JSON files, and emits a side-by-side Markdown report.

Usage:
  python3 tools/phase10_generate_comparison.py \
      --pilot /tmp/cob-pilot/sirach_24 \
      --baseline v31 \
      --out /tmp/cob-pilot/sirach_24_comparison.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "state" / "chapter_queue.sqlite3"


def load_pilot(pilot_dir: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary_path = pilot_dir / "pilot_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    verses_dir = pilot_dir / "verses"
    if not verses_dir.exists():
        raise FileNotFoundError(verses_dir)
    records: list[dict[str, Any]] = []
    for path in sorted(verses_dir.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return summary, records


def connect_db(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_v3_strategy(
    conn: sqlite3.Connection,
    *,
    testament: str,
    book_slug: str,
    chapter: int,
) -> str:
    rows = conn.execute(
        """
        SELECT strategy, review_path, COUNT(*) AS n
        FROM review_jobs
        WHERE testament=? AND book_slug=? AND chapter=? AND status='completed'
        GROUP BY strategy, review_path
        ORDER BY strategy
        """,
        (testament, book_slug, chapter),
    ).fetchall()
    candidates: list[tuple[int, str]] = []
    for row in rows:
        review_path = REPO_ROOT / row["review_path"]
        if not review_path.exists():
            continue
        try:
            payload = json.loads(review_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        prompt_version = str(payload.get("prompt_version") or "")
        if "v3_author_intent" in prompt_version:
            candidates.append((int(row["n"]), str(row["strategy"])))
    if not candidates:
        raise RuntimeError(f"Could not resolve a v3 author-intent strategy for {book_slug} {chapter}")
    candidates.sort(reverse=True)
    return candidates[0][1]


def resolve_baseline_strategy(
    conn: sqlite3.Connection,
    *,
    baseline: str,
    testament: str,
    book_slug: str,
    chapter: int,
) -> str:
    if baseline == "v31":
        return "v31_full_coverage"
    if baseline in {"v3", "v3_author_intent"}:
        return resolve_v3_strategy(conn, testament=testament, book_slug=book_slug, chapter=chapter)
    return baseline


def load_baseline_reviews(
    conn: sqlite3.Connection,
    *,
    strategy: str,
    testament: str,
    book_slug: str,
    chapter: int,
) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT verse, review_path, agreement_score, issues_found, process_status
        FROM review_jobs
        WHERE testament=? AND book_slug=? AND chapter=? AND strategy=? AND status='completed'
        ORDER BY verse
        """,
        (testament, book_slug, chapter, strategy),
    ).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        review_path = REPO_ROOT / row["review_path"]
        payload: dict[str, Any] = {
            "review_path": row["review_path"],
            "agreement_score": row["agreement_score"],
            "issues_found": row["issues_found"],
            "process_status": row["process_status"],
        }
        if review_path.exists():
            try:
                payload["review"] = json.loads(review_path.read_text(encoding="utf-8"))
            except Exception:
                payload["review"] = {"notes": "Unable to parse baseline review JSON."}
        out[int(row["verse"])] = payload
    return out


def quote_cell(text: str | None) -> str:
    if not text:
        return "N/A"
    return text.replace("|", "\\|").replace("\n", " ")


def baseline_summary_text(item: dict[str, Any] | None) -> str:
    if not item:
        return "No baseline row found."
    review = item.get("review") or {}
    issues = review.get("issues") or []
    if not issues:
        score = review.get("agreement_score", item.get("agreement_score"))
        return f"No issues flagged (agreement_score={score})."
    pieces = []
    for issue in issues:
        category = issue.get("category") or "issue"
        severity = issue.get("severity") or "?"
        span = issue.get("span") or issue.get("current_rendering") or ""
        rewrite = issue.get("suggested_rewrite") or ""
        detail = f"{category}/{severity}: {span}"
        if rewrite:
            detail += f" → {rewrite}"
        pieces.append(detail)
    return "; ".join(pieces)


def stacked_flags(record: dict[str, Any]) -> bool:
    if record.get("status") != "completed":
        return False
    review = record.get("stacked_review") or {}
    verdict = review.get("verdict")
    if verdict in {"modify", "reject"}:
        return True
    return bool(review.get("key_issues") or review.get("proposed_rewrite"))


def baseline_flags(item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    review = item.get("review") or {}
    return bool(review.get("issues") or [])


def verse_heading(reference: str) -> str:
    return reference or "Verse"


def render_report(
    *,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
    baseline_strategy: str,
    baseline_alias: str,
    baseline_reviews: dict[int, dict[str, Any]],
) -> str:
    verdict_counts = {"retain": 0, "modify": 0, "reject": 0}
    blind_counts = {"high": 0, "medium": 0, "low": 0}
    same_flagged_verse = 0
    stacked_only = 0
    baseline_only = 0

    for record in records:
        if record.get("status") != "completed":
            continue
        review = record.get("stacked_review") or {}
        verdict = str(review.get("verdict") or "")
        blind = str(review.get("agreement_with_blind_draft") or "")
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1
        if blind in blind_counts:
            blind_counts[blind] += 1
        s_flag = stacked_flags(record)
        b_flag = baseline_flags(baseline_reviews.get(int(record["verse"])))
        if s_flag and b_flag:
            same_flagged_verse += 1
        elif s_flag and not b_flag:
            stacked_only += 1
        elif b_flag and not s_flag:
            baseline_only += 1

    lines: list[str] = []
    book_slug = summary["book_slug"]
    chapter = int(summary["chapter"])
    lines.append(f"# Phase 10 stacked-review comparison — {book_slug} {chapter}")
    lines.append("")
    lines.append(f"- Pilot directory: `{summary.get('book_slug', book_slug)}` chapter {chapter}")
    lines.append(f"- Baseline alias: `{baseline_alias}`")
    lines.append(f"- Resolved baseline strategy: `{baseline_strategy}`")
    lines.append(f"- Pilot model: `{summary.get('model')}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Verdicts: {verdict_counts['retain']} retain, {verdict_counts['modify']} modify, {verdict_counts['reject']} reject"
    )
    lines.append(
        "- Agreement with baseline (same verse flagged): "
        f"{same_flagged_verse}; stacked-only flagged verses: {stacked_only}; baseline-only flagged verses: {baseline_only}"
    )
    lines.append(
        "- Agreement with blind draft: "
        f"{blind_counts['high']} high, {blind_counts['medium']} medium, {blind_counts['low']} low"
    )
    lines.append(
        "- Net assessment: preliminary signal only — human review still needed to judge whether the stacked-only verses are real wins."
    )
    lines.append("")
    lines.append("## Per-verse comparison")
    lines.append("")

    for record in records:
        ref = verse_heading(str(record.get("reference") or "Verse"))
        lines.append(f"### {ref}")
        lines.append("")
        if record.get("status") != "completed":
            lines.append(f"**Pilot status:** error — {record.get('error')}")
            lines.append("")
            continue

        source_text = quote_cell((record.get("source") or {}).get("text"))
        existing_text = quote_cell((record.get("existing_draft") or {}).get("text"))
        blind_text = quote_cell((record.get("blind_draft") or {}).get("english_text"))
        stacked_review = record.get("stacked_review") or {}
        baseline_item = baseline_reviews.get(int(record["verse"]))
        lines.append(f"**Source (Greek):** {source_text}")
        lines.append("")
        lines.append("| Version | Text |")
        lines.append("|---|---|")
        lines.append(f"| Existing Cartha | {existing_text} |")
        lines.append(f"| Blind draft (Call 1) | {blind_text} |")
        lines.append(f"| Call 2 verdict | {quote_cell(str(stacked_review.get('verdict') or 'N/A'))} |")
        lines.append(f"| {baseline_alias} baseline finding | {quote_cell(baseline_summary_text(baseline_item))} |")
        lines.append(
            f"| Stacked proposed rewrite | {quote_cell(stacked_review.get('proposed_rewrite') or 'N/A')} |"
        )
        lines.append("")

        issues = stacked_review.get("key_issues") or []
        if issues:
            lines.append("**Key issues:**")
            for issue in issues:
                lines.append(f"- {issue}")
        else:
            lines.append("**Key issues:** None")
        lines.append("")

        divergences = stacked_review.get("reference_divergences") or []
        if divergences:
            lines.append("**Reference divergences:**")
            lines.append("")
            lines.append("| Source | Rendering | Alignment | Notes |")
            lines.append("|---|---|---|---|")
            for item in divergences:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            quote_cell(item.get("source")),
                            quote_cell(item.get("rendering")),
                            quote_cell(item.get("alignment")),
                            quote_cell(item.get("notes")),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("**Reference divergences:** None")
        lines.append("")
        lines.append(
            f"**Commentary alignment:** {quote_cell(stacked_review.get('commentary_alignment') or 'N/A')}"
        )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", required=True, type=pathlib.Path)
    parser.add_argument("--baseline", required=True, help="Baseline alias or concrete strategy name")
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--db", type=pathlib.Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args(argv)

    summary, records = load_pilot(args.pilot)
    conn = connect_db(args.db)
    try:
        baseline_strategy = resolve_baseline_strategy(
            conn,
            baseline=args.baseline,
            testament=str(summary["testament"]),
            book_slug=str(summary["book_slug"]),
            chapter=int(summary["chapter"]),
        )
        baseline_reviews = load_baseline_reviews(
            conn,
            strategy=baseline_strategy,
            testament=str(summary["testament"]),
            book_slug=str(summary["book_slug"]),
            chapter=int(summary["chapter"]),
        )
    finally:
        conn.close()

    report = render_report(
        summary=summary,
        records=records,
        baseline_strategy=baseline_strategy,
        baseline_alias=args.baseline,
        baseline_reviews=baseline_reviews,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
