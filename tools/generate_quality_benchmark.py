#!/usr/bin/env python3
"""generate_quality_benchmark.py — write QUALITY_BENCHMARK.md

Produces a time-series view of corpus quality across the Phase 8
pipeline stages so we can defend the final numbers and show the
trajectory of improvement.

Stages tracked (if outputs exist on disk):
  1. Raw OCR (regex parser over our transcribed .txt)
  2. Azure-review pass (applied corrections from Azure GPT-5.4 review)
  3. Gemini cross-review (applied after 2-model merge)
  4. AI-vision re-parse (chapter-level GPT-5.4 scan-image parse)
  5. Scan-grounded adjudication (final, Azure looks at scan + candidates)

For each stage, reports: verse count, coverage vs First1KGreek,
agreement rate, functional agreement, major mismatch count, gaps.

Output: sources/lxx/swete/QUALITY_BENCHMARK.md
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402
import first1kgreek  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
OUT_PATH = REPO_ROOT / "sources" / "lxx" / "swete" / "QUALITY_BENCHMARK.md"


def measure_jsonl(path: pathlib.Path) -> dict:
    """Return stats about a JSONL corpus vs First1KGreek."""
    if not path.exists():
        return {}
    book = path.stem
    ours: dict[tuple[int, int], str] = {}
    for line in path.read_text().split("\n"):
        if not line.strip():
            continue
        r = json.loads(line)
        ours[(r["chapter"], r["verse"])] = r["greek"]

    theirs: dict[tuple[int, int], str] = {}
    try:
        for v in first1kgreek.iter_verses(book):
            ch = v.chapter_int
            vn = v.verse_int
            if ch is None or vn is None:
                continue
            theirs[(ch, vn)] = v.greek_text
    except Exception:
        pass

    agree = minor = major = missing_ours = missing_first = 0
    for key in set(ours) | set(theirs):
        ot = ours.get(key)
        tt = theirs.get(key)
        if ot is None:
            missing_ours += 1
        elif tt is None:
            missing_first += 1
        else:
            sim = first1kgreek.similarity(ot, tt)
            if sim >= 0.85:
                agree += 1
            elif sim >= 0.5:
                minor += 1
            else:
                major += 1
    both_present = agree + minor + major
    return {
        "book": book,
        "total_ours": len(ours),
        "total_first1k": len(theirs),
        "agree": agree,
        "minor": minor,
        "major": major,
        "missing_in_ours": missing_ours,
        "missing_in_first1k": missing_first,
        "both_present": both_present,
        "agree_rate": agree / both_present if both_present else 0,
        "functional_rate": (agree + minor) / both_present if both_present else 0,
    }


def measure_stage(stage_name: str, corpus_dir: pathlib.Path) -> dict:
    """Measure all books in a corpus directory."""
    if not corpus_dir.exists():
        return {"stage": stage_name, "per_book": [], "totals": {}}
    per_book = []
    for jf in sorted(corpus_dir.glob("*.jsonl")):
        m = measure_jsonl(jf)
        if m:
            per_book.append(m)
    totals = {
        "total_ours": sum(b["total_ours"] for b in per_book),
        "total_first1k": sum(b["total_first1k"] for b in per_book),
        "agree": sum(b["agree"] for b in per_book),
        "minor": sum(b["minor"] for b in per_book),
        "major": sum(b["major"] for b in per_book),
        "missing_in_ours": sum(b["missing_in_ours"] for b in per_book),
        "both_present": sum(b["both_present"] for b in per_book),
    }
    totals["agree_rate"] = totals["agree"] / totals["both_present"] if totals["both_present"] else 0
    totals["functional_rate"] = (totals["agree"] + totals["minor"]) / totals["both_present"] if totals["both_present"] else 0
    return {"stage": stage_name, "per_book": per_book, "totals": totals}


def format_benchmark(stages: list[dict]) -> str:
    import datetime as dt
    lines = [
        "# Cartha Open Bible — Phase 8 corpus quality benchmark",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Pipeline stages",
        "",
        "Our Phase 8 corpus went through multiple quality passes. This",
        "table shows the trajectory — where we started, and where each",
        "automated pass landed us — measured against First1KGreek's",
        "independent scholarly encoding of the same Swete edition as a",
        "validation oracle (NOT as a source of our text).",
        "",
        "| Stage | Verses | Coverage | Agree | Agree+Minor | Major | Missing |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for st in stages:
        if not st["totals"]:
            continue
        t = st["totals"]
        coverage = t["total_ours"] / t["total_first1k"] * 100 if t["total_first1k"] else 0
        lines.append(
            f"| {st['stage']} | {t['total_ours']} | {coverage:.1f}% | "
            f"{t['agree_rate']*100:.1f}% | {t['functional_rate']*100:.1f}% | "
            f"{t['major']} | {t['missing_in_ours']} |"
        )

    # Per-book detail for the final stage
    if stages and stages[-1].get("per_book"):
        lines.extend([
            "",
            f"## Final stage — per-book detail ({stages[-1]['stage']})",
            "",
            "| Book | Ours | First1K | Agree | Functional | Major | Missing |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for b in stages[-1]["per_book"]:
            lines.append(
                f"| {b['book']} | {b['total_ours']} | {b['total_first1k']} "
                f"| {b['agree_rate']*100:.1f}% | {b['functional_rate']*100:.1f}% "
                f"| {b['major']} | {b['missing_in_ours']} |"
            )

    lines.extend([
        "",
        "## Legend",
        "",
        "- **Verses**: total verses in our corpus",
        "- **Coverage**: our verses / First1KGreek verses (how much of their",
        "  complete-encoding corpus we cover)",
        "- **Agree**: % of verses both sources have where our text is ≥85% word-overlap similar",
        "  to First1KGreek (perfect agreement after accent normalization)",
        "- **Agree+Minor**: % where our text is ≥50% similar (functional",
        "  agreement — orthographic variations)",
        "- **Major**: count of verses where our text < 50% similar (real",
        "  textual differences — could be OCR error OR legitimate",
        "  Swete-vs-eclectic text-tradition difference)",
        "- **Missing**: verses First1KGreek has but our corpus lacks",
        "",
        "## Interpretation",
        "",
        "Agreement does NOT mean First1KGreek is ground truth. They are",
        "also machine-assisted transcription of Swete. Disagreements can",
        "mean:",
        "  - Our OCR error (their reading is right → we should fix)",
        "  - Their encoding error (our reading is right → theirs is wrong)",
        "  - Legitimate textual-tradition difference (both valid, our",
        "    choice is explicit)",
        "",
        "The adjudicator pass (final stage) uses Azure GPT-5.4 vision to",
        "look at the actual Swete scan and decide per-verse what the",
        "printed page ACTUALLY says. That's the ground-truth layer on",
        "top of both transcriptions.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    stages = [
        measure_stage("4. AI-vision re-parse (our-OCR-only)",
                      REPO_ROOT / "sources" / "lxx" / "swete" / "ours_only_corpus"),
        measure_stage("5. Scan-adjudicated (final)",
                      REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated"),
    ]
    OUT_PATH.write_text(format_benchmark(stages), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    for st in stages:
        if st["totals"]:
            t = st["totals"]
            print(f"  {st['stage']}: {t['total_ours']}v  agree={t['agree_rate']*100:.1f}%  "
                  f"func={t['functional_rate']*100:.1f}%  major={t['major']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
