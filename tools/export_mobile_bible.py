#!/usr/bin/env python3
"""
export_mobile_bible.py — Export Cartha Open Bible verse YAMLs into the
mobile app's bundled Bible JSON format.

The mobile app expects a single JSON file shaped like:

{
  "translation": "COB: Cartha Open Bible (Preview)",
  "books": [
    {
      "name": "Romans",
      "chapters": [
        {
          "chapter": 1,
          "verses": [
            {"verse": 1, "text": "..."}
          ]
        }
      ]
    }
  ]
}

For preview builds we only export chapters that are fully complete in the
translation repo. If a chapter is missing one or more verses, that chapter
and any later chapters in the same book are omitted from the export so the
mobile reader never shows partial chapter content.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict
from typing import Any

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft  # noqa: E402
import sblgnt  # noqa: E402
import wlc  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"

CANONICAL_BOOK_ORDER: list[str] = [
    "GEN", "EXO", "LEV", "NUM", "DEU",
    "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR",
    "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM",
    "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB",
    "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MRK", "LUK", "JHN", "ACT",
    "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI",
    "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN",
    "JUD", "REV",
]


def book_title(book_code: str) -> str:
    if book_code in sblgnt.BOOK_TITLES:
        return sblgnt.BOOK_TITLES[book_code]
    if book_code in wlc.OT_BOOKS:
        return wlc.OT_BOOKS[book_code][2]
    raise ValueError(f"Unknown book code: {book_code}")


def expected_chapter_map(book_code: str) -> dict[int, list[int]]:
    """Return {chapter: [verse_numbers...]} covering only verses actually
    present in the critical source text. Source editions (SBLGNT, WLC/UHB)
    legitimately skip verses rejected by textual criticism (e.g. Matt 17:21,
    Matt 23:14), so iterating range(1, last+1) is incorrect — some verse
    numbers simply don't exist."""
    chapter_to_verses: dict[int, list[int]] = {}
    for verse in draft.iter_source_verses(book_code):
        chapter_to_verses.setdefault(verse.chapter, []).append(verse.verse)
    for chapter in chapter_to_verses:
        chapter_to_verses[chapter].sort()
    return chapter_to_verses


def load_translation_record(book_code: str, chapter: int, verse: int) -> dict[str, Any] | None:
    verse_obj = draft.load_source_verse(book_code, chapter, verse)
    path = draft.translation_path_for_verse(verse_obj)
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def export_book(book_code: str) -> dict[str, Any] | None:
    expected = expected_chapter_map(book_code)
    chapters_out: list[dict[str, Any]] = []

    for chapter in sorted(expected):
        verses_out: list[dict[str, Any]] = []
        chapter_complete = True

        for verse in expected[chapter]:
            record = load_translation_record(book_code, chapter, verse)
            if record is None:
                chapter_complete = False
                break

            text = str(((record.get("translation") or {}).get("text", "")) or "").strip()
            if not text:
                chapter_complete = False
                break

            verses_out.append({
                "verse": verse,
                "text": text,
            })

        if not chapter_complete:
            break

        chapters_out.append({
            "chapter": chapter,
            "verses": verses_out,
        })

    if not chapters_out:
        return None

    return {
        "name": book_title(book_code),
        "chapters": chapters_out,
    }


def export_translation() -> dict[str, Any]:
    books: list[dict[str, Any]] = []
    for book_code in CANONICAL_BOOK_ORDER:
        exported = export_book(book_code)
        if exported is not None:
            books.append(exported)

    return {
        "translation": "COB: Cartha Open Bible (Preview)",
        "books": books,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        help="Where to write the mobile JSON artifact.",
    )
    args = parser.parse_args()

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = export_translation()
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )

    book_count = len(payload["books"])
    chapter_count = sum(len(book["chapters"]) for book in payload["books"])
    verse_count = sum(
        len(chapter["verses"])
        for book in payload["books"]
        for chapter in book["chapters"]
    )
    print(
        f"Wrote {output_path} ({book_count} books, {chapter_count} chapters, {verse_count} verses)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
