#!/usr/bin/env python3
"""run_ai_gap_parse.py — run Azure GPT-5.4 vision parser on every gap chapter.

A gap chapter is any (book, chapter) with at least one verse currently
sourced from First1KGreek in the final corpus. Re-parses them from the
Swete scan images via tools/lxx_swete_ai.py so the final corpus can be
100% our own OCR.

Usage:
  python3 tools/run_ai_gap_parse.py
  python3 tools/run_ai_gap_parse.py --book TOB
  python3 tools/run_ai_gap_parse.py --concurrency 8
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402
import lxx_swete_ai  # noqa: E402


REPO_ROOT = lxx_swete.REPO_ROOT
FINAL_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus"
PARSED_AI_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "parsed_ai"


def enumerate_gaps(only_book: str | None = None) -> list[tuple[str, int]]:
    gaps: dict[str, set[int]] = {}
    for jf in sorted(FINAL_DIR.glob("*.jsonl")):
        book = jf.stem
        if only_book and book != only_book:
            continue
        for line in jf.read_text().split("\n"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["source"] != "ours":
                gaps.setdefault(book, set()).add(r["chapter"])
    out: list[tuple[str, int]] = []
    for b, chs in sorted(gaps.items()):
        for c in sorted(chs):
            out.append((b, c))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", help="Only process this book")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--force", action="store_true", help="Re-parse even if cached")
    ap.add_argument("--max-tokens", type=int, default=12000)
    args = ap.parse_args()

    gaps = enumerate_gaps(args.book)
    print(f"Found {len(gaps)} gap chapters to re-parse with AI vision")

    PARSED_AI_DIR.mkdir(parents=True, exist_ok=True)

    def worker(book: str, ch: int):
        out = PARSED_AI_DIR / f"{book}_{ch:03d}.json"
        if out.exists() and not args.force:
            return book, ch, None, "cached"
        try:
            data = lxx_swete_ai.parse_chapter(book, ch, max_tokens=args.max_tokens)
            lxx_swete_ai.save_chapter(data)
            return book, ch, None, f"{len(data['verses'])}v in {data['duration_seconds']}s"
        except Exception as exc:
            return book, ch, f"{type(exc).__name__}: {str(exc)[:150]}", None

    n_ok = n_fail = n_cached = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(worker, b, c) for b, c in gaps]
        for fut in as_completed(futures):
            b, c, err, info = fut.result()
            if err:
                n_fail += 1
                print(f"  FAIL {b} ch{c}: {err}", flush=True)
            elif info == "cached":
                n_cached += 1
                # quiet
            else:
                n_ok += 1
                print(f"  OK   {b} ch{c}: {info}", flush=True)

    print(f"\nProcessed {len(gaps)}: ok={n_ok}  failed={n_fail}  cached={n_cached}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
