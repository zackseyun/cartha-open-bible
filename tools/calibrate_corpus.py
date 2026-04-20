#!/usr/bin/env python3
"""calibrate_corpus.py — diff our Swete parse against First1KGreek Swete.

Strategy:
  - Our corpus (lxx_swete.iter_source_verses) is the PRIMARY source.
  - First1KGreek is a CROSS-CHECK. Both transcribe the same Swete edition.
  - This tool compares our parsed (chapter, verse) corpus against theirs
    and emits a report of disagreements per book.

Output:
  - Per-book diff reports in sources/lxx/swete/calibration/<BOOK>.md
  - Aggregate summary in sources/lxx/swete/calibration/SUMMARY.md
  - A machine-readable gap list for apply_calibration.py to consume:
    sources/lxx/swete/calibration/gaps.json

Gap categories:
  - missing_in_ours: First1KGreek has this verse, our parse doesn't
  - missing_in_first1k: ours has it, First1KGreek doesn't (rare; usually
    OK to trust ours in this case)
  - text_mismatch_major: both have the verse, but text similarity < 0.5
    (likely our OCR corrupted or misaligned)
  - text_mismatch_minor: similarity 0.5..0.85 (minor spelling differences;
    usually orthographic variants — investigation not urgent)
  - text_agreement: similarity >= 0.85

Usage:
  python3 tools/calibrate_corpus.py                # full run, all books
  python3 tools/calibrate_corpus.py --book TOB
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402
import first1kgreek  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
OUTPUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "calibration"


def collect_ours(book_code: str) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    for v in lxx_swete.iter_source_verses(book_code):
        out[(v.chapter, v.verse)] = v.greek_text
    return out


def collect_first1k(book_code: str) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    try:
        for v in first1kgreek.iter_verses(book_code):
            ch = v.chapter_int
            vn = v.verse_int
            if ch is None or vn is None:
                continue
            out[(ch, vn)] = v.greek_text
    except Exception:
        pass
    return out


def diff_book(book_code: str) -> dict[str, Any]:
    ours = collect_ours(book_code)
    theirs = collect_first1k(book_code)

    gaps: list[dict[str, Any]] = []
    agreements = 0
    minor_mismatches = 0

    all_keys = sorted(set(ours) | set(theirs))
    for key in all_keys:
        ours_text = ours.get(key)
        theirs_text = theirs.get(key)
        if ours_text is None and theirs_text is not None:
            gaps.append({
                "book": book_code,
                "chapter": key[0],
                "verse": key[1],
                "category": "missing_in_ours",
                "ours": None,
                "theirs": theirs_text,
                "similarity": 0.0,
            })
        elif theirs_text is None and ours_text is not None:
            gaps.append({
                "book": book_code,
                "chapter": key[0],
                "verse": key[1],
                "category": "missing_in_first1k",
                "ours": ours_text,
                "theirs": None,
                "similarity": 0.0,
            })
        else:
            sim = first1kgreek.similarity(ours_text, theirs_text)
            if sim >= 0.85:
                agreements += 1
            elif sim >= 0.5:
                minor_mismatches += 1
                gaps.append({
                    "book": book_code,
                    "chapter": key[0],
                    "verse": key[1],
                    "category": "text_mismatch_minor",
                    "ours": ours_text,
                    "theirs": theirs_text,
                    "similarity": round(sim, 3),
                })
            else:
                gaps.append({
                    "book": book_code,
                    "chapter": key[0],
                    "verse": key[1],
                    "category": "text_mismatch_major",
                    "ours": ours_text,
                    "theirs": theirs_text,
                    "similarity": round(sim, 3),
                })

    stats = {
        "book": book_code,
        "our_verses": len(ours),
        "their_verses": len(theirs),
        "agreements": agreements,
        "minor_mismatches": minor_mismatches,
        "missing_in_ours": sum(1 for g in gaps if g["category"] == "missing_in_ours"),
        "missing_in_first1k": sum(1 for g in gaps if g["category"] == "missing_in_first1k"),
        "major_mismatches": sum(1 for g in gaps if g["category"] == "text_mismatch_major"),
    }
    return {"stats": stats, "gaps": gaps}


def format_book_report(book_code: str, result: dict[str, Any]) -> str:
    s = result["stats"]
    gaps = result["gaps"]
    lines = [
        f"# {book_code} calibration vs First1KGreek",
        "",
        f"- Our verses:        {s['our_verses']}",
        f"- Their verses:      {s['their_verses']}",
        f"- Text agreement:    {s['agreements']}",
        f"- Minor mismatches:  {s['minor_mismatches']}",
        f"- Major mismatches:  {s['major_mismatches']}",
        f"- Missing in ours:   {s['missing_in_ours']}",
        f"- Missing in theirs: {s['missing_in_first1k']}",
        "",
    ]
    if gaps:
        lines.append("## Gaps")
        lines.append("")
        by_cat: dict[str, list[dict[str, Any]]] = {}
        for g in gaps:
            by_cat.setdefault(g["category"], []).append(g)
        for cat in ["missing_in_ours", "text_mismatch_major", "text_mismatch_minor", "missing_in_first1k"]:
            items = by_cat.get(cat, [])
            if not items:
                continue
            lines.append(f"### {cat} ({len(items)})")
            lines.append("")
            for g in items[:30]:
                c, v, sim = g["chapter"], g["verse"], g["similarity"]
                lines.append(f"- **{book_code} {c}:{v}** (sim={sim})")
                if g["ours"]:
                    lines.append(f"  - ours:   `{g['ours'][:100]}`")
                if g["theirs"]:
                    lines.append(f"  - theirs: `{g['theirs'][:100]}`")
            if len(items) > 30:
                lines.append(f"- … +{len(items) - 30} more")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    books = [args.book] if args.book else list(first1kgreek.BOOK_TO_TLG.keys())

    summary_stats: list[dict[str, Any]] = []
    all_gaps: list[dict[str, Any]] = []
    for book in books:
        if book not in lxx_swete.DEUTEROCANONICAL_BOOKS:
            continue
        result = diff_book(book)
        summary_stats.append(result["stats"])
        all_gaps.extend(result["gaps"])
        (OUTPUT_DIR / f"{book}.md").write_text(
            format_book_report(book, result), encoding="utf-8"
        )
        s = result["stats"]
        print(
            f"{book}: ours={s['our_verses']}  theirs={s['their_verses']}  "
            f"agree={s['agreements']}  minor={s['minor_mismatches']}  "
            f"major={s['major_mismatches']}  miss_ours={s['missing_in_ours']}  "
            f"miss_theirs={s['missing_in_first1k']}"
        )

    # Aggregate summary
    totals = Counter()
    for s in summary_stats:
        for k in ("our_verses", "their_verses", "agreements", "minor_mismatches",
                  "major_mismatches", "missing_in_ours", "missing_in_first1k"):
            totals[k] += s.get(k, 0)
    summary_lines = [
        "# Corpus calibration summary (ours vs First1KGreek Swete)",
        "",
        f"Books compared: {len(summary_stats)}",
        f"Our total verses:           {totals['our_verses']}",
        f"Their total verses:         {totals['their_verses']}",
        f"Text agreement:             {totals['agreements']}",
        f"Minor mismatches (< 0.85):  {totals['minor_mismatches']}",
        f"Major mismatches (< 0.5):   {totals['major_mismatches']}",
        f"Missing in ours:            {totals['missing_in_ours']}",
        f"Missing in theirs:          {totals['missing_in_first1k']}",
        "",
        "## Per-book breakdown",
        "",
        "| Book | Ours | Theirs | Agree | Minor | Major | MissOurs | MissTheirs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in summary_stats:
        summary_lines.append(
            f"| {s['book']} | {s['our_verses']} | {s['their_verses']} | "
            f"{s['agreements']} | {s['minor_mismatches']} | "
            f"{s['major_mismatches']} | {s['missing_in_ours']} | {s['missing_in_first1k']} |"
        )
    (OUTPUT_DIR / "SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    # Gaps JSON
    (OUTPUT_DIR / "gaps.json").write_text(
        json.dumps(all_gaps, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nReports in {OUTPUT_DIR}")
    print(f"Agreement rate: {totals['agreements']} / "
          f"{totals['our_verses']} = {totals['agreements']/max(1,totals['our_verses'])*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
