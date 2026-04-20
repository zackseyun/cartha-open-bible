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

# Deuterocanonical / Apocrypha export. Walks `translation/apocrypha/<slug>/`
# directly instead of going through `draft.iter_source_verses(...)` because
# these books have no SBLGNT or WLC entry — their source is the LXX (and
# in a few cases Latin / Syriac witnesses). The canonical export still
# needs the source files for completeness checks; Apocrypha instead uses
# whatever verse YAMLs are published and requires a contiguous 1..N
# sequence per chapter.
#
# Book codes, titles, and directory slugs are kept in sync with the
# cartha.website and cartha.ai.mobile canonical book lists. If you add
# a new Apocryphal book here, also extend:
#   - cartha.ai.mobile/lib/screens/bible/bible_catalog.dart (canonicalBibleBooks)
#   - cartha.website/src/app/(main)/cartha-open-bible/bibleData.js (CANONICAL_BOOKS + APOCRYPHA_NORMALIZED)
# so the frontends partition and render the new book correctly.
APOCRYPHA_ROOT = TRANSLATION_ROOT / "apocrypha"

APOCRYPHA_BOOK_ORDER: list[str] = [
    "TOB", "JDT", "ESG", "WIS", "SIR", "BAR", "LJE", "PAZ", "SUS", "BEL",
    "1MA", "2MA", "3MA", "4MA", "1ES", "2ES", "MAN", "PS2",
]

APOCRYPHA_BOOK_TITLES: dict[str, str] = {
    "TOB": "Tobit",
    "JDT": "Judith",
    "ESG": "Additions to Esther",
    "WIS": "Wisdom of Solomon",
    "SIR": "Sirach",
    "BAR": "Baruch",
    "LJE": "Letter of Jeremiah",
    "PAZ": "Prayer of Azariah",
    "SUS": "Susanna",
    "BEL": "Bel and the Dragon",
    "1MA": "1 Maccabees",
    "2MA": "2 Maccabees",
    "3MA": "3 Maccabees",
    "4MA": "4 Maccabees",
    "1ES": "1 Esdras",
    "2ES": "2 Esdras",
    "MAN": "Prayer of Manasseh",
    "PS2": "Psalm 151",
}

APOCRYPHA_BOOK_SLUGS: dict[str, str] = {
    "TOB": "tobit",
    "JDT": "judith",
    "ESG": "additions_to_esther",
    "WIS": "wisdom_of_solomon",
    "SIR": "sirach",
    "BAR": "baruch",
    "LJE": "letter_of_jeremiah",
    "PAZ": "prayer_of_azariah",
    "SUS": "susanna",
    "BEL": "bel_and_the_dragon",
    "1MA": "1_maccabees",
    "2MA": "2_maccabees",
    "3MA": "3_maccabees",
    "4MA": "4_maccabees",
    "1ES": "1_esdras",
    "2ES": "2_esdras",
    "MAN": "prayer_of_manasseh",
    "PS2": "psalm_151",
}


def book_title(book_code: str) -> str:
    if book_code in sblgnt.BOOK_TITLES:
        return sblgnt.BOOK_TITLES[book_code]
    if book_code in wlc.OT_BOOKS:
        return wlc.OT_BOOKS[book_code][2]
    if book_code in APOCRYPHA_BOOK_TITLES:
        return APOCRYPHA_BOOK_TITLES[book_code]
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
    """Include every chapter that is fully drafted. Skip chapters with
    gaps rather than failing fast — a later complete chapter should not
    be withheld just because an earlier one is still being drafted.
    This matches the CDN publisher Lambda's behaviour."""
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
            continue

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


def export_apocrypha_book(book_code: str) -> dict[str, Any] | None:
    """Walk `translation/apocrypha/<slug>/<NNN>/<VVV>.yaml` directly.
    Apocrypha books have no SBLGNT/WLC source to validate completeness
    against, so `expected_chapter_map` can't be used. Instead we include
    each chapter whose published verse YAMLs form a contiguous 1..N
    sequence — any gap mid-chapter disqualifies that chapter, but later
    chapters with gaps are still skipped individually (a gap in chapter
    2 doesn't withhold chapter 3). This mirrors the canonical export's
    policy that partial chapters never ship to the reader."""
    slug = APOCRYPHA_BOOK_SLUGS.get(book_code)
    if slug is None:
        return None
    book_dir = APOCRYPHA_ROOT / slug
    if not book_dir.exists():
        return None

    by_chapter: dict[int, dict[int, str]] = defaultdict(dict)
    for chapter_dir in sorted(book_dir.iterdir()):
        if not chapter_dir.is_dir():
            continue
        try:
            chapter_num = int(chapter_dir.name)
        except ValueError:
            continue
        for verse_file in sorted(chapter_dir.glob("*.yaml")):
            try:
                verse_num = int(verse_file.stem)
            except ValueError:
                continue
            record = yaml.safe_load(verse_file.read_text(encoding="utf-8")) or {}
            text = str(((record.get("translation") or {}).get("text", "")) or "").strip()
            if not text:
                continue
            by_chapter[chapter_num][verse_num] = text

    chapters_out: list[dict[str, Any]] = []
    for chapter in sorted(by_chapter):
        verses = by_chapter[chapter]
        verse_nums = sorted(verses)
        if not verse_nums:
            continue
        # Contiguous 1..N required — a missing verse mid-chapter leaves
        # the reader staring at a misnumbered body.
        expected = list(range(1, verse_nums[-1] + 1))
        if verse_nums != expected:
            continue
        chapters_out.append({
            "chapter": chapter,
            "verses": [
                {"verse": verse_num, "text": verses[verse_num]}
                for verse_num in verse_nums
            ],
        })

    if not chapters_out:
        return None

    return {
        "name": APOCRYPHA_BOOK_TITLES[book_code],
        "chapters": chapters_out,
    }


def export_translation() -> dict[str, Any]:
    books: list[dict[str, Any]] = []
    for book_code in CANONICAL_BOOK_ORDER:
        exported = export_book(book_code)
        if exported is not None:
            books.append(exported)
    # Apocrypha appended after the 66-book canon so every consumer's
    # OT/NT ordering assumption stays intact. Frontends partition these
    # into a dedicated Apocrypha section by book name, so position
    # in this list is purely a sort key.
    for book_code in APOCRYPHA_BOOK_ORDER:
        exported = export_apocrypha_book(book_code)
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
