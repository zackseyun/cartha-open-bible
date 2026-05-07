#!/usr/bin/env python3
"""find_uncovered_verses.py — emit a JSONL worklist of verses with no
published cross-check block.

Replaces the discovery half of submit_vertex_gap_closure.py and fixes the
nested-layout bug: T12P lives at
  translation/extra_canonical/testaments_twelve_patriarchs/<patriarch>/<chap>/<verse>.yaml
i.e. one extra directory level vs every other book. The original walker
treated <patriarch> as a chapter and never found its verses.

Gate (matches the user-facing definition of "needs review"):
  A verse is uncovered when its YAML has no top-level `cross_check:` block
  with content. revision_pass / revisions / Azure / Gemini activity is
  irrelevant — what readers see on the public site is the cross_check
  block, and that is what we are filling in.

  Verses whose state/reviews/claude record already exists (i.e. previously
  reviewed by Claude this pipeline) are also treated as covered to avoid
  duplicate work between batches.

Usage:
    python3 tools/find_uncovered_verses.py                 # print summary + write /tmp/uncovered.jsonl
    python3 tools/find_uncovered_verses.py --out worklist.jsonl
    python3 tools/find_uncovered_verses.py --book shepherd_of_hermas
    python3 tools/find_uncovered_verses.py --t12p-only

Each JSONL row:
  {"testament": "...", "book_slug": "...", "sub_book": "...|null",
   "chapter": N, "verse": N, "yaml_path": "translation/...",
   "review_yaml_path": "...", "ref_id": "BOOK.CH.V"}
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
REVIEWS_ROOT = REPO_ROOT / "state" / "reviews"

TESTAMENTS = ("ot", "nt", "deuterocanon", "extra_canonical")
CLAUDE_REVIEWS_ROOT = REPO_ROOT / "state" / "reviews" / "claude"

# Books known to use a deeper layout: testament/book/<sub_book>/<chap>/<verse>.yaml
# Each verse YAML is still per-verse; the sub_book level is a sibling-book within
# a collection (e.g. each patriarch within Testaments of the Twelve Patriarchs).
NESTED_BOOKS = {
    ("extra_canonical", "testaments_twelve_patriarchs"),
}


def collect_claude_review_coverage() -> set[tuple[str, str, int, int]]:
    """{(testament, review_book_slug, chap, verse)} for verses that already
    have a Claude review JSON under state/reviews/claude/**. Used to skip
    re-reviewing across batches."""
    out: set[tuple[str, str, int, int]] = set()
    if not CLAUDE_REVIEWS_ROOT.exists():
        return out
    for jf in CLAUDE_REVIEWS_ROOT.rglob("*.json"):
        parts = jf.parts
        if len(parts) < 5:
            continue
        try:
            verse = int(parts[-1].split(".")[0])
            chap = int(parts[-2])
            slug = parts[-3]
            testament = parts[-4]
            if testament not in TESTAMENTS:
                continue
            out.add((testament, slug, chap, verse))
        except (ValueError, IndexError):
            continue
    return out


def has_published_cross_check(yaml_data: dict) -> bool:
    cc = yaml_data.get("cross_check")
    if not cc:
        return False
    # Treat a cross_check key whose value is None or empty dict as missing
    # (some legacy YAMLs have a bare `cross_check:` placeholder).
    if isinstance(cc, dict) and not cc:
        return False
    return True


def iter_verse_yamls() -> list[dict]:
    """Yield {testament, book_slug, sub_book, chapter, verse, yaml_path,
    review_book_slug, ref_id} for every per-verse YAML under translation/."""
    out: list[dict] = []
    for testament_dir in sorted(TRANSLATION_ROOT.iterdir()):
        if not testament_dir.is_dir() or testament_dir.name not in TESTAMENTS:
            continue
        testament = testament_dir.name
        for book_dir in sorted(testament_dir.iterdir()):
            if not book_dir.is_dir():
                continue
            book_slug = book_dir.name
            nested = (testament, book_slug) in NESTED_BOOKS

            if nested:
                # testament/book/<sub_book>/<chap>/<verse>.yaml
                for sub_dir in sorted(book_dir.iterdir()):
                    if not sub_dir.is_dir():
                        continue
                    sub_book = sub_dir.name
                    for chap_dir in sorted(sub_dir.iterdir()):
                        if not chap_dir.is_dir() or not chap_dir.name.isdigit():
                            continue
                        chap = int(chap_dir.name)
                        for yp in sorted(chap_dir.glob("*.yaml")):
                            if not yp.stem.isdigit():
                                continue
                            verse = int(yp.stem)
                            out.append({
                                "testament": testament,
                                "book_slug": book_slug,
                                "sub_book": sub_book,
                                "chapter": chap,
                                "verse": verse,
                                "yaml_path": str(yp.relative_to(REPO_ROOT)),
                                # Reviews key on sub_book to match existing
                                # publish_review_cross_checks layout.
                                "review_book_slug": sub_book,
                            })
            else:
                # testament/book/<chap>/<verse>.yaml
                for chap_dir in sorted(book_dir.iterdir()):
                    if not chap_dir.is_dir() or not chap_dir.name.isdigit():
                        continue
                    chap = int(chap_dir.name)
                    for yp in sorted(chap_dir.glob("*.yaml")):
                        if not yp.stem.isdigit():
                            continue
                        verse = int(yp.stem)
                        out.append({
                            "testament": testament,
                            "book_slug": book_slug,
                            "sub_book": None,
                            "chapter": chap,
                            "verse": verse,
                            "yaml_path": str(yp.relative_to(REPO_ROOT)),
                            "review_book_slug": book_slug,
                        })
    return out


def find_uncovered(
    book_filter: str | None = None,
    t12p_only: bool = False,
) -> list[dict]:
    claude_coverage = collect_claude_review_coverage()
    uncovered: list[dict] = []
    for entry in iter_verse_yamls():
        if t12p_only and entry["book_slug"] != "testaments_twelve_patriarchs":
            continue
        if book_filter:
            if entry["book_slug"] != book_filter and entry.get("sub_book") != book_filter:
                continue

        # Skip if a Claude review JSON already exists (avoid duplicate work).
        ckey = (entry["testament"], entry["review_book_slug"],
                entry["chapter"], entry["verse"])
        if ckey in claude_coverage:
            continue

        try:
            data = yaml.safe_load(
                (REPO_ROOT / entry["yaml_path"]).read_text(encoding="utf-8")
            )
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # Public gate: does the YAML carry a published cross_check block?
        if has_published_cross_check(data):
            continue

        ref_id = data.get("id") or f"{entry['review_book_slug'].upper()}.{entry['chapter']}.{entry['verse']}"
        entry["ref_id"] = str(ref_id)
        uncovered.append(entry)
    return uncovered


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="/tmp/uncovered.jsonl",
                    help="Output JSONL worklist path")
    ap.add_argument("--book", default=None,
                    help="Restrict to a single book_slug or sub_book name")
    ap.add_argument("--t12p-only", action="store_true",
                    help="Only emit T12P verses (testaments_twelve_patriarchs)")
    args = ap.parse_args()

    uncovered = find_uncovered(book_filter=args.book, t12p_only=args.t12p_only)

    # Summary by (book_slug, sub_book)
    counter: collections.Counter = collections.Counter()
    for e in uncovered:
        key = (e["book_slug"], e["sub_book"] or "—")
        counter[key] += 1

    total = len(uncovered)
    print(f"Uncovered verses: {total}")
    for (book, sub), n in counter.most_common():
        if sub == "—":
            print(f"  {book:36s}  {n}")
        else:
            print(f"  {book}/{sub:24s}  {n}")

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for e in uncovered:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"\nWorklist written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
