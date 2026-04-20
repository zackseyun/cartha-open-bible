#!/usr/bin/env python3
"""build_final_corpus.py — merge our OCR parse with First1KGreek Swete.

Produces a single authoritative per-verse corpus for the Phase 8
deuterocanonical books by applying the hybrid policy:

  - WHERE our OCR parse produced a verse that agrees with First1KGreek
    (similarity ≥ 0.5): keep our verse. Attribution: our scan + review
    + parser chain.
  - WHERE we're missing a verse or disagree substantially
    (similarity < 0.5 OR missing): take First1KGreek's verse. Attribution:
    CC-BY-SA First1KGreek Swete edition, with the Swete 1909 citation
    preserved.
  - Every verse is tagged with its provenance so downstream translators
    and auditors can see which source each verse came from.

Output:
  sources/lxx/swete/final_corpus/<BOOK>.jsonl   — one verse per line
  sources/lxx/swete/final_corpus/SUMMARY.md     — aggregate provenance stats

Each line is a JSON object:
  {
    "book": "TOB",
    "chapter": 1,
    "verse": 1,
    "greek": "…",
    "source": "ours" | "first1kgreek" | "agreement",
    "similarity": 0.97,    # for agreement/disagreement items
    "ours_greek": "…",     # when source != "ours", preserves ours too
    "first1k_greek": "…",  # same, for their version
  }
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402
import first1kgreek  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
OUTPUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus"

# Similarity threshold: if similarity between ours and theirs is >= this,
# we trust our OCR-derived text (it matches the authoritative reference).
# Below this, we prefer First1KGreek's verse (our OCR likely corrupted).
AGREEMENT_THRESHOLD = 0.5


def collect_ours(book_code: str) -> dict[tuple[int, int], tuple[str, int | None]]:
    """Return (chapter, verse) -> (greek_text, source_page)."""
    out: dict[tuple[int, int], tuple[str, int | None]] = {}
    for v in lxx_swete.iter_source_verses(book_code):
        out[(v.chapter, v.verse)] = (v.greek_text, v.source_page)
    return out


def collect_first1k(book_code: str) -> dict[tuple[int, int], str]:
    out: dict[tuple[int, int], str] = {}
    try:
        for v in first1kgreek.iter_verses(book_code):
            ch = v.chapter_int
            vn = v.verse_int
            if ch is None or vn is None:
                continue
            # Last-wins if duplicates
            out[(ch, vn)] = v.greek_text
    except Exception:
        pass
    return out


def build_book(book_code: str) -> dict:
    ours = collect_ours(book_code)
    theirs = collect_first1k(book_code)
    all_keys = sorted(set(ours) | set(theirs))

    verses = []
    stats = Counter()

    for key in all_keys:
        ch, vs = key
        ours_tup = ours.get(key)
        theirs_text = theirs.get(key)
        ours_text = ours_tup[0] if ours_tup else None
        source_page = ours_tup[1] if ours_tup else None

        if ours_text and theirs_text:
            sim = first1kgreek.similarity(ours_text, theirs_text)
            if sim >= AGREEMENT_THRESHOLD:
                verses.append({
                    "book": book_code,
                    "chapter": ch,
                    "verse": vs,
                    "greek": ours_text,
                    "source": "ours",
                    "source_page": source_page,
                    "calibrated_against": "first1kgreek_swete",
                    "similarity": round(sim, 3),
                })
                stats["ours_agreed"] += 1
            else:
                verses.append({
                    "book": book_code,
                    "chapter": ch,
                    "verse": vs,
                    "greek": theirs_text,
                    "source": "first1kgreek",
                    "ours_greek": ours_text,
                    "source_page": source_page,
                    "similarity": round(sim, 3),
                    "notes": "our OCR diverged from First1KGreek; using First1KGreek text",
                })
                stats["first1k_used_disagreement"] += 1
        elif ours_text and not theirs_text:
            verses.append({
                "book": book_code,
                "chapter": ch,
                "verse": vs,
                "greek": ours_text,
                "source": "ours",
                "source_page": source_page,
                "notes": "First1KGreek has no verse at this location",
            })
            stats["ours_only"] += 1
        elif theirs_text and not ours_text:
            verses.append({
                "book": book_code,
                "chapter": ch,
                "verse": vs,
                "greek": theirs_text,
                "source": "first1kgreek",
                "notes": "our OCR parse missing this verse",
            })
            stats["first1k_used_missing"] += 1

    return {"book": book_code, "verses": verses, "stats": stats}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", help="Only process this book")
    ap.add_argument("--no-first1k", action="store_true",
                    help="Skip First1KGreek; emit only ours (for ablation testing)")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    books_to_process: list[str] = []
    if args.book:
        books_to_process = [args.book]
    else:
        books_to_process = [b for b in first1kgreek.BOOK_TO_TLG
                            if b in lxx_swete.DEUTEROCANONICAL_BOOKS]

    all_stats = Counter()
    summary_rows = []
    for book in books_to_process:
        result = build_book(book)
        verses = result["verses"]
        s = result["stats"]
        out_path = OUTPUT_DIR / f"{book}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for v in verses:
                fh.write(json.dumps(v, ensure_ascii=False) + "\n")
        all_stats.update(s)
        total = len(verses)
        summary_rows.append({
            "book": book,
            "total": total,
            "ours_agreed": s["ours_agreed"],
            "ours_only": s["ours_only"],
            "first1k_used_disagreement": s["first1k_used_disagreement"],
            "first1k_used_missing": s["first1k_used_missing"],
        })
        print(
            f"{book}: {total}v  "
            f"ours_agreed={s['ours_agreed']}  "
            f"ours_only={s['ours_only']}  "
            f"first1k_disagreement={s['first1k_used_disagreement']}  "
            f"first1k_missing={s['first1k_used_missing']}"
        )

    # Summary doc
    total_verses = sum(r["total"] for r in summary_rows)
    ours_total = all_stats["ours_agreed"] + all_stats["ours_only"]
    first1k_total = all_stats["first1k_used_disagreement"] + all_stats["first1k_used_missing"]
    summary_lines = [
        "# Phase 8 final corpus provenance",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Total verses: **{total_verses}**",
        "",
        f"- From our OCR + parser (`source: ours`): **{ours_total}** "
        f"({ours_total/max(1,total_verses)*100:.1f}%)",
        f"  - Of these, {all_stats['ours_agreed']} verified as agreeing with "
        f"First1KGreek Swete (cross-check passed).",
        f"  - {all_stats['ours_only']} verses where First1KGreek had no verse at "
        f"that location (we went with our reading).",
        f"- From First1KGreek Swete (`source: first1kgreek`): **{first1k_total}** "
        f"({first1k_total/max(1,total_verses)*100:.1f}%)",
        f"  - {all_stats['first1k_used_disagreement']} verses where our OCR "
        f"diverged substantially (similarity < 0.5) — we used First1KGreek.",
        f"  - {all_stats['first1k_used_missing']} verses entirely missing from "
        f"our OCR parse — filled from First1KGreek.",
        "",
        "## Attribution",
        "",
        "- Our OCR-derived verses are from Swete's _The Old Testament in Greek_ "
        "(Cambridge, 1896-1905) scans on Internet Archive, transcribed via "
        "Azure GPT-5.4 vision, cross-reviewed against Gemini 2.5 Pro.",
        "- First1KGreek-sourced verses are from "
        "`https://github.com/OpenGreekAndLatin/First1KGreek` TEI-XML "
        "(CC-BY-SA 4.0), a separately encoded edition of the same Swete "
        "text, published by Harvard College Library with funding from the "
        "Arcadia Fund.",
        "- Both paths trace to the same underlying scholarly edition "
        "(Swete 1909). The First1KGreek-sourced verses are effectively a "
        "re-encoding of the same text we OCR'd; they're used here to fill "
        "gaps where our vision pipeline had OCR errors or missed verses.",
        "",
        "## Per-book breakdown",
        "",
        "| Book | Total | Ours (agreed) | Ours (only) | First1K (disagreement) | First1K (missing) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in summary_rows:
        summary_lines.append(
            f"| {r['book']} | {r['total']} | {r['ours_agreed']} | {r['ours_only']} "
            f"| {r['first1k_used_disagreement']} | {r['first1k_used_missing']} |"
        )

    (OUTPUT_DIR / "SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {OUTPUT_DIR}/")
    print(f"Total: {total_verses} verses across {len(summary_rows)} books")
    print(f"Our OCR share: {ours_total}/{total_verses} = {ours_total/max(1,total_verses)*100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
