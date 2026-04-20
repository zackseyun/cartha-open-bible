#!/usr/bin/env python3
"""apply_adjudications.py — merge scan-adjudicated verse verdicts back.

Reads sources/lxx/swete/adjudications/<BOOK>_<CHAPTER>.json (produced by
adjudicate_corpus.py) and updates sources/lxx/swete/ours_only_corpus/*.jsonl
with the adjudicator's verdicts.

Policy:
  - Every adjudicated verse gets its `greek` field overwritten with the
    scan-grounded reading. The original reading is preserved in
    `pre_adjudication_greek` for audit.
  - A new `adjudication` sub-object is attached with verdict + reasoning
    + confidence + prompt version.
  - Verses NOT in the adjudication set (perfect-agreement ones) are
    left untouched.

Output:
  sources/lxx/swete/final_corpus_adjudicated/<BOOK>.jsonl
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402
import first1kgreek  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
OURS_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "ours_only_corpus"
ADJ_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "adjudications"
OUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated"


def load_adjudications(book: str) -> dict[tuple[int, int], dict]:
    """Return (chapter, verse) -> verdict dict."""
    out: dict[tuple[int, int], dict] = {}
    for jf in sorted(ADJ_DIR.glob(f"{book}_*.json")):
        data = json.loads(jf.read_text())
        ch = data["chapter"]
        for v in data.get("verdicts", []):
            out[(ch, v["verse"])] = {
                "verdict": v["verdict"],
                "verdict_greek": v["verdict_greek"],
                "reasoning": v.get("reasoning", ""),
                "confidence": v.get("confidence", ""),
                "prompt_version": data.get("prompt_version", ""),
            }
    return out


def load_ours(book: str) -> list[dict]:
    path = OURS_DIR / f"{book}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().split("\n"):
        if not line.strip():
            continue
        out.append(json.loads(line))
    return out


def apply_book(book: str) -> dict:
    adjs = load_adjudications(book)
    verses = load_ours(book)
    existing_keys = {(v["chapter"], v["verse"]) for v in verses}

    # Also find adjudications for verses we didn't originally have
    # (missing_in_ours cases — scan-grounded fresh readings)
    for (ch, vn), adj in adjs.items():
        if (ch, vn) not in existing_keys and adj["verdict_greek"].strip():
            verses.append({
                "book": book,
                "chapter": ch,
                "verse": vn,
                "greek": "",  # placeholder, will be filled below
                "ocr_method": "adjudicated",
                "source_pages": [],
            })

    # Apply adjudications
    stats = Counter()
    for v in verses:
        key = (v["chapter"], v["verse"])
        adj = adjs.get(key)
        if not adj:
            stats["unchanged"] += 1
            continue
        # Record pre-adjudication reading
        v["pre_adjudication_greek"] = v.get("greek", "")
        v["greek"] = adj["verdict_greek"]
        v["adjudication"] = {
            "verdict": adj["verdict"],
            "reasoning": adj["reasoning"],
            "confidence": adj["confidence"],
            "prompt_version": adj["prompt_version"],
        }
        stats[f"adj_{adj['verdict']}"] += 1
        stats[f"conf_{adj['confidence']}"] += 1

    # Sort by (chapter, verse) for stable output
    verses.sort(key=lambda v: (v["chapter"], v["verse"]))

    return {"book": book, "verses": verses, "stats": stats}


def format_summary(per_book: list[dict]) -> str:
    agg = Counter()
    for r in per_book:
        agg.update(r["stats"])
    rows = []
    for r in per_book:
        s = r["stats"]
        rows.append({
            "book": r["book"],
            "total": len(r["verses"]),
            "unchanged": s["unchanged"],
            "adj_ours": s["adj_ours"],
            "adj_first1k": s["adj_first1k"],
            "adj_both_ok": s["adj_both_ok"],
            "adj_neither": s["adj_neither"],
            "conf_high": s["conf_high"],
            "conf_medium": s["conf_medium"],
            "conf_low": s["conf_low"],
        })

    total_verses = sum(r["total"] for r in rows)
    total_adj = agg["adj_ours"] + agg["adj_first1k"] + agg["adj_both_ok"] + agg["adj_neither"]
    lines = [
        "# Adjudicated corpus — final pass summary",
        "",
        f"Total verses: **{total_verses}**",
        f"Verses left unchanged (already agreed): **{agg['unchanged']}**",
        f"Verses adjudicated against scan: **{total_adj}**",
        "",
        "## Adjudication outcomes",
        "",
        f"- Our OCR matched scan (kept ours): **{agg['adj_ours']}**",
        f"- First1KGreek matched scan (Azure verified; we use scan-grounded reading): **{agg['adj_first1k']}**",
        f"- Both equivalent (minor orthography): **{agg['adj_both_ok']}**",
        f"- Neither matched scan (fresh scan-based reading): **{agg['adj_neither']}**",
        "",
        "## Adjudicator confidence",
        "",
        f"- High: **{agg['conf_high']}**",
        f"- Medium: **{agg['conf_medium']}**",
        f"- Low (may warrant human review): **{agg['conf_low']}**",
        "",
        "## Per-book breakdown",
        "",
        "| Book | Total | Unchanged | ours→kept | first1k→used | both_ok | neither | High conf |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['book']} | {r['total']} | {r['unchanged']} | {r['adj_ours']} "
            f"| {r['adj_first1k']} | {r['adj_both_ok']} | {r['adj_neither']} | {r['conf_high']} |"
        )
    lines.extend([
        "",
        "## Attribution note",
        "",
        "Every `greek` text in the final corpus is either (a) our original",
        "AI-vision OCR (unchanged from the scan), or (b) a scan-grounded",
        "reading produced by Azure GPT-5.4 looking at the printed Swete",
        "page directly.  First1KGreek's transcription was used only as a",
        "secondary pointer to help the adjudicator focus; no First1KGreek",
        "text was copied into the corpus.  The `pre_adjudication_greek`",
        "field preserves our pre-adjudication reading for audit.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    books = ([args.book] if args.book else
             [b for b in first1kgreek.BOOK_TO_TLG if b in lxx_swete.DEUTEROCANONICAL_BOOKS])
    per_book = []
    for book in books:
        if lxx_swete.book_page_range(book)[0] == 0:
            continue
        result = apply_book(book)
        per_book.append(result)
        with (OUT_DIR / f"{book}.jsonl").open("w", encoding="utf-8") as fh:
            for v in result["verses"]:
                fh.write(json.dumps(v, ensure_ascii=False) + "\n")
        s = result["stats"]
        total_adj = s["adj_ours"] + s["adj_first1k"] + s["adj_both_ok"] + s["adj_neither"]
        print(
            f"{book}: {len(result['verses'])}v  unchanged={s['unchanged']}  "
            f"adjudicated={total_adj}  ours={s['adj_ours']}  "
            f"first1k={s['adj_first1k']}  both_ok={s['adj_both_ok']}  neither={s['adj_neither']}"
        )

    (OUT_DIR / "SUMMARY.md").write_text(format_summary(per_book), encoding="utf-8")
    print(f"\nWrote {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
