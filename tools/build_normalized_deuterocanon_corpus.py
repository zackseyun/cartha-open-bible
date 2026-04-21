#!/usr/bin/env python3
"""build_normalized_deuterocanon_corpus.py

Create translation-ready overrides for deuterocanonical books whose raw
scan-adjudicated verse stream still contains known numbering contamination.

The raw source of truth remains:
  sources/lxx/swete/final_corpus_adjudicated/

This script writes only the cleaned override files needed by the
translation layer under:
  sources/lxx/swete/final_corpus_normalized/

Current normalizations:
- WIS: drop duplicated chapter 20 and the Sirach spill into WIS 19:23-30
- BAR: trim chapter 1 back to 1:1-22 and chapter 5 back to 5:1-9
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated"
OUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_normalized"


def load_book(book: str) -> list[dict]:
    path = SRC_DIR / f"{book}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_book(book: str, records: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{book}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def normalize_wis(records: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    dropped: list[str] = []
    for rec in records:
        ch = int(rec["chapter"])
        vs = int(rec["verse"])
        ref = f"WIS {ch}:{vs}"
        if ch == 20:
            dropped.append(f"{ref} — duplicate of canonical Wisdom 19 from the raw parser stream")
            continue
        if ch == 19 and vs >= 23:
            dropped.append(f"{ref} — adjacent Sirach contamination beyond canonical Wisdom 19:22")
            continue
        rec = dict(rec)
        rec["normalization"] = {
            "rule": "wisdom_trim_to_canonical_19",
            "note": "Translation-ready override derived from final_corpus_adjudicated; dropped duplicate chapter 20 and spillover beyond Wisdom 19:22.",
        }
        kept.append(rec)
    return kept, dropped


def normalize_bar(records: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    dropped: list[str] = []
    for rec in records:
        ch = int(rec["chapter"])
        vs = int(rec["verse"])
        ref = f"BAR {ch}:{vs}"
        keep = False
        if ch == 1 and vs <= 22:
            keep = True
        elif ch == 2 and vs <= 35:
            keep = True
        elif ch == 3 and vs <= 38:
            keep = True
        elif ch == 4 and vs <= 37:
            keep = True
        elif ch == 5 and vs <= 9:
            keep = True

        if not keep:
            reason = "removed by canonical Baruch chapter/verse boundaries"
            if ch == 1 and vs >= 23:
                reason = "raw chapter-1 tail is actually Baruch 3:23-38"
            elif ch == 5 and vs >= 10:
                reason = "raw chapter-5 tail spills into Lamentations material"
            dropped.append(f"{ref} — {reason}")
            continue

        rec = dict(rec)
        rec["normalization"] = {
            "rule": "baruch_trim_to_canonical_5",
            "note": "Translation-ready override derived from final_corpus_adjudicated; kept canonical Baruch 1:1-5:9 only, with Letter of Jeremiah handled separately as LJE.",
        }
        kept.append(rec)
    return kept, dropped


def chapter_counts(records: list[dict]) -> dict[int, int]:
    counts: Counter[int] = Counter()
    for rec in records:
        counts[int(rec["chapter"])] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    summary_lines = [
        "# Normalized deuterocanonical corpus overrides",
        "",
        "These files are translation-ready overrides derived from `final_corpus_adjudicated/`.",
        "The raw adjudicated corpus remains untouched for audit. The translation layer prefers these overrides when present.",
        "",
    ]

    jobs = {
        "WIS": normalize_wis,
        "BAR": normalize_bar,
    }

    for book, fn in jobs.items():
        raw = load_book(book)
        normalized, dropped = fn(raw)
        write_book(book, normalized)
        summary_lines.append(f"## {book}")
        summary_lines.append("")
        summary_lines.append(f"- Raw verses: **{len(raw)}**")
        summary_lines.append(f"- Normalized verses: **{len(normalized)}**")
        summary_lines.append(f"- Dropped contaminated / duplicate refs: **{len(dropped)}**")
        summary_lines.append(f"- Chapter counts after normalization: `{chapter_counts(normalized)}`")
        summary_lines.append("")
        for line in dropped:
            summary_lines.append(f"  - {line}")
        summary_lines.append("")

    (OUT_DIR / "SUMMARY.md").write_text("\n".join(summary_lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote normalized overrides to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
