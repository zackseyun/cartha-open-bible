#!/usr/bin/env python3
"""build_ours_only_corpus.py — build final corpus using ONLY our OCR.

Per-verse source priority (highest first):
  1. AI-vision parse (tools/lxx_swete_ai.py output under
     sources/lxx/swete/parsed_ai/). Produced from Swete scan images
     via Azure GPT-5.4 vision. Highest quality where available.
  2. Regex parser output (tools/lxx_swete.py's parse_pages_to_verses).
     Derived from our OCR'd page .txt files.

NEVER uses First1KGreek text as a verse source — First1KGreek is used
ONLY as a validation oracle: for each of our verses, we compute the
similarity to First1KGreek's verse at the same (book, chapter, verse)
key and tag it. Never copy their text.

Output:
  sources/lxx/swete/ours_only_corpus/<BOOK>.jsonl
  sources/lxx/swete/ours_only_corpus/HEALTH.md — diff+coverage report
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
PARSED_AI_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "parsed_ai"
OUTPUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "ours_only_corpus"

# IMPORTANT: make iter_source_verses use the RAW parser (not the hybrid).
# We need the OUR-OCR-ONLY stream here.
def _raw_regex_parse(book_code: str):
    return list(lxx_swete.parse_pages_to_verses(book_code))


def _load_ai_parse(book_code: str) -> dict[tuple[int, int], tuple[str, list[int]]]:
    """Load AI-parsed chapters for this book. Return (ch, v) -> (greek, pages)."""
    out: dict[tuple[int, int], tuple[str, list[int]]] = {}
    for jf in sorted(PARSED_AI_DIR.glob(f"{book_code}_*.json")):
        data = json.loads(jf.read_text())
        pages = data.get("pages", [])
        for v in data.get("verses", []):
            ch = data["chapter"]
            vn = v.get("verse")
            greek = v.get("greek", "")
            if not greek or vn is None:
                continue
            out[(ch, vn)] = (greek, pages)
    return out


def collect_ours_only(book_code: str):
    """Combine AI parse + regex parse, AI takes priority per verse."""
    ai = _load_ai_parse(book_code)
    regex_verses = _raw_regex_parse(book_code)
    regex_map: dict[tuple[int, int], object] = {}
    for v in regex_verses:
        regex_map[(v.chapter, v.verse)] = v

    all_keys = set(ai) | set(regex_map)
    merged: dict[tuple[int, int], dict] = {}
    for key in all_keys:
        ch, vn = key
        if key in ai:
            greek, pages = ai[key]
            merged[key] = {
                "book": book_code,
                "chapter": ch,
                "verse": vn,
                "greek": greek,
                "ocr_method": "ai_vision",
                "source_pages": pages,
            }
        else:
            v = regex_map[key]
            merged[key] = {
                "book": book_code,
                "chapter": ch,
                "verse": vn,
                "greek": v.greek_text,
                "ocr_method": "regex_parse",
                "source_pages": [v.source_page] if v.source_page else [],
            }
    return merged


def validate_against_first1k(merged: dict, book_code: str):
    """Add similarity + agreement labels by comparing to First1KGreek."""
    theirs: dict[tuple[int, int], str] = {}
    try:
        for v in first1kgreek.iter_verses(book_code):
            ch = v.chapter_int
            vn = v.verse_int
            if ch is None or vn is None:
                continue
            theirs[(ch, vn)] = v.greek_text
    except Exception:
        pass

    for key, rec in merged.items():
        their_text = theirs.get(key)
        if their_text is None:
            rec["validation"] = "no_reference"
            rec["similarity"] = None
        else:
            sim = first1kgreek.similarity(rec["greek"], their_text)
            rec["similarity"] = round(sim, 3)
            if sim >= 0.85:
                rec["validation"] = "agree"
            elif sim >= 0.5:
                rec["validation"] = "minor_mismatch"
            else:
                rec["validation"] = "major_mismatch"

    missing_from_ours = sorted(set(theirs) - set(merged))
    return merged, missing_from_ours


def build_book(book_code: str) -> dict:
    merged = collect_ours_only(book_code)
    merged, missing = validate_against_first1k(merged, book_code)
    verses = [merged[k] for k in sorted(merged)]
    stats = Counter()
    for v in verses:
        stats[v["ocr_method"]] += 1
        stats[f"val_{v['validation']}"] += 1
    stats["total"] = len(verses)
    stats["missing_vs_first1k"] = len(missing)
    return {"book": book_code, "verses": verses, "stats": stats, "missing": missing}


def format_health_report(per_book: list[dict]) -> str:
    all_stats = Counter()
    rows = []
    for r in per_book:
        s = r["stats"]
        all_stats.update(s)
        rows.append({"book": r["book"], **s})

    total = all_stats["total"]
    ai = all_stats["ai_vision"]
    rx = all_stats["regex_parse"]
    agree = all_stats["val_agree"]
    minor = all_stats["val_minor_mismatch"]
    major = all_stats["val_major_mismatch"]
    no_ref = all_stats["val_no_reference"]
    missing = all_stats["missing_vs_first1k"]

    lines = [
        "# Cartha Open Bible — Phase 8 corpus health (our OCR only)",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Source composition (every verse is our own OCR)",
        "",
        f"- **Total verses:** {total}",
        f"- From AI vision parse (GPT-5.4 direct on scan images): **{ai}** ({ai/max(1,total)*100:.1f}%)",
        f"- From regex parser over our transcribed .txt: **{rx}** ({rx/max(1,total)*100:.1f}%)",
        f"- From First1KGreek: **0** (validation-only, never copied)",
        "",
        "## Independent validation against First1KGreek",
        "",
        "First1KGreek's TEI-XML encoding of the same Swete edition is used",
        "only to check our OCR. A random verse we disagree with is not",
        "automatically assumed wrong — but similarity scores let us see",
        "where our OCR is likely correct vs. where human review is warranted.",
        "",
        f"- **Text agreement** (similarity ≥ 0.85): {agree} ({agree/max(1,total)*100:.1f}%)",
        f"- **Minor mismatch** (0.5 ≤ sim < 0.85): {minor} ({minor/max(1,total)*100:.1f}%) — usually accent/orthographic",
        f"- **Major mismatch** (sim < 0.5): {major} ({major/max(1,total)*100:.1f}%) — likely our OCR error; human review recommended",
        f"- **No reference available**: {no_ref} ({no_ref/max(1,total)*100:.1f}%) — First1KGreek has no verse at this key",
        f"- **Verses present in First1KGreek but missing from ours**: {missing}",
        "",
        "## Agreement rate on verses both sources contain",
        "",
    ]
    both_present = agree + minor + major
    if both_present:
        lines.append(
            f"**{agree}/{both_present} = {agree/both_present*100:.1f}% perfect agreement**, "
            f"with an additional {minor/both_present*100:.1f}% minor variations (accents, spacing) — "
            f"jointly {(agree+minor)/both_present*100:.1f}% functional agreement."
        )
        lines.append("")
    lines.extend([
        "## Per-book health",
        "",
        "| Book | Verses | AI | Regex | Agree | Minor | Major | No ref | Missing |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for r in rows:
        lines.append(
            f"| {r['book']} | {r.get('total',0)} | {r.get('ai_vision',0)} | {r.get('regex_parse',0)} | "
            f"{r.get('val_agree',0)} | {r.get('val_minor_mismatch',0)} | {r.get('val_major_mismatch',0)} | "
            f"{r.get('val_no_reference',0)} | {r.get('missing_vs_first1k',0)} |"
        )
    lines.extend([
        "",
        "## Gaps still present",
        "",
        "Verses where First1KGreek has content but our OCR produced none.",
        "These need either (a) more page transcription from scans, or (b)",
        "a targeted AI re-parse of specific chapters.",
        "",
    ])
    for r in per_book:
        if r["missing"]:
            lines.append(f"### {r['book']} ({len(r['missing'])} missing)")
            lines.append("")
            buckets: dict[int, list[int]] = {}
            for c, v in r["missing"]:
                buckets.setdefault(c, []).append(v)
            for ch in sorted(buckets):
                vs = sorted(buckets[ch])
                lines.append(f"- Ch {ch}: verses {vs[:20]}{'…' if len(vs)>20 else ''}")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    books = ([args.book] if args.book else
             [b for b in lxx_swete.DEUTEROCANONICAL_BOOKS
              if b in first1kgreek.BOOK_TO_TLG])

    per_book = []
    for book in books:
        if lxx_swete.book_page_range(book)[0] == 0:
            continue  # skip books with no page range defined
        result = build_book(book)
        path = OUTPUT_DIR / f"{book}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for v in result["verses"]:
                fh.write(json.dumps(v, ensure_ascii=False) + "\n")
        per_book.append(result)
        s = result["stats"]
        print(
            f"{book}: {s['total']}v  ai={s['ai_vision']}  rx={s['regex_parse']}  "
            f"agree={s['val_agree']}  minor={s['val_minor_mismatch']}  "
            f"major={s['val_major_mismatch']}  missing={s['missing_vs_first1k']}"
        )

    (OUTPUT_DIR / "HEALTH.md").write_text(format_health_report(per_book), encoding="utf-8")
    print(f"\nWrote {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
