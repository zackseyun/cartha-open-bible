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
import lxx_swete  # noqa: E402


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

# Deuterocanonical export. Walks `translation/deuterocanon/<slug>/`
# directly so the draft output path and mobile export stay on the same
# internal contract.
APOCRYPHA_ROOT = TRANSLATION_ROOT / "deuterocanon"

APOCRYPHA_BOOK_ORDER: list[str] = [
    "TOB", "JDT", "ESG", "WIS", "SIR", "BAR", "LJE", "PAZ", "SUS", "BEL",
    "1MA", "2MA", "3MA", "4MA", "1ES", "MAN", "PS151",
]

APOCRYPHA_BOOK_TITLES: dict[str, str] = {
    "TOB": "Tobit",
    "JDT": "Judith",
    "ADE": "Greek Esther",
    "ESG": "Additions to Esther",
    "WIS": "Wisdom of Solomon",
    "SIR": "Sirach",
    "BAR": "Baruch",
    "LJE": "Letter of Jeremiah",
    "PAZ": "Prayer of Azariah and Song of the Three",
    "SUS": "Susanna",
    "BEL": "Bel and the Dragon",
    "ADA": "Greek Additions to Daniel",
    "1MA": "1 Maccabees",
    "2MA": "2 Maccabees",
    "3MA": "3 Maccabees",
    "4MA": "4 Maccabees",
    "1ES": "1 Esdras",
    "MAN": "Prayer of Manasseh",
    "PS151": "Psalm 151",
}

APOCRYPHA_BOOK_SLUGS: dict[str, str] = {
    code: meta[4]
    for code, meta in lxx_swete.DEUTEROCANONICAL_BOOKS.items()
}


# Extra-canonical export. Walks `translation/extra_canonical/<slug>/`
# directly. Unlike deuterocanon (verse-level YAMLs), most
# extra-canonical texts are drafted as chapter-level YAMLs -- each
# chapter YAML carries a single continuous translation block that
# matches how these texts are historically read and rendered.
# For those, we emit the whole chapter as a single synthetic "verse"
# so the mobile reader gets one continuous-prose chapter unit.
EXTRA_CANONICAL_ROOT = TRANSLATION_ROOT / "extra_canonical"

EXTRA_CANONICAL_BOOK_ORDER: list[str] = [
    "DID",     # Didache
    "1CLEM",   # 1 Clement
]

EXTRA_CANONICAL_BOOK_TITLES: dict[str, str] = {
    "DID":   "Didache",
    "1CLEM": "1 Clement",
}

EXTRA_CANONICAL_BOOK_SLUGS: dict[str, str] = {
    "DID":   "didache",
    "1CLEM": "1_clement",
}

# Extra-canonical books that only have chapter-level YAMLs (single
# text block per chapter) rather than per-verse YAMLs.
#
# Didache and 1 Clement started here, but their chapter-level drafts
# have since been split into per-verse YAMLs at
# translation/extra_canonical/<slug>/<NNN>/<VVV>.yaml (via
# tools/split_extra_canonical_into_verses.py — 116 Didache verses and
# 460 1 Clement verses at the scholarly-standard divisions). They are
# now treated as verse-level books.
#
# Left in place so future books drafted as pure chapter-level prose
# can be added here for single-synthetic-verse emission without
# invoking the verse splitter.
EXTRA_CANONICAL_CHAPTER_LEVEL: set[str] = set()


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
    """Walk `translation/deuterocanon/<slug>/<NNN>/<VVV>.yaml` directly.
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


def export_extra_canonical_book(book_code: str) -> dict[str, Any] | None:
    """Walk `translation/extra_canonical/<slug>/<NNN>.yaml` for
    chapter-level books (Didache, 1 Clement, etc.), or the nested
    chapter/verse layout for any future verse-level extra-canonical
    books. Chapter-level YAMLs emit each chapter as a single synthetic
    verse-1 block — these texts aren't verse-subdivided in standard
    reading editions, so this matches the reader expectation.

    A missing or empty chapter file is skipped; the export is
    complete-chapters-only (same policy as canonical and apocrypha
    exports).
    """
    slug = EXTRA_CANONICAL_BOOK_SLUGS.get(book_code)
    if slug is None:
        return None
    book_dir = EXTRA_CANONICAL_ROOT / slug
    if not book_dir.exists():
        return None

    chapters_out: list[dict[str, Any]] = []

    if book_code in EXTRA_CANONICAL_CHAPTER_LEVEL:
        # Chapter-level YAMLs: translation/extra_canonical/<slug>/NNN.yaml
        for chapter_file in sorted(book_dir.glob("*.yaml")):
            try:
                chapter_num = int(chapter_file.stem)
            except ValueError:
                continue
            record = yaml.safe_load(chapter_file.read_text(encoding="utf-8")) or {}
            text = str(((record.get("translation") or {}).get("text", "")) or "").strip()
            if not text:
                continue
            # Emit as a single synthetic verse-1 block so the reader gets
            # the whole chapter as a continuous prose unit.
            chapters_out.append({
                "chapter": chapter_num,
                "verses": [
                    {"verse": 1, "text": text},
                ],
            })
    else:
        # Verse-level nested layout: translation/extra_canonical/<slug>/<NNN>/<VVV>.yaml
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

        for chapter in sorted(by_chapter):
            verses = by_chapter[chapter]
            verse_nums = sorted(verses)
            if not verse_nums:
                continue
            # Extra-canonical scholarly editions legitimately skip
            # verse numbers in some chapters (e.g. 1 Clement 16's Isaiah
            # 53 quotation, where the Greek source per Funk 1901 simply
            # doesn't carry markers for verses 3 and 9). Unlike the
            # canonical NT/OT where textual criticism is the only reason
            # for gaps, here gaps reflect the source editions' own
            # numbering conventions. We emit what we have and preserve
            # the verse numbers so the reader sees the scholarly numbering
            # even when it skips.
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
        "name": EXTRA_CANONICAL_BOOK_TITLES[book_code],
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
    # Extra-canonical (Apostolic Fathers etc.) after deuterocanon.
    # Labeled in the reader as a separate "Extra-canonical writings"
    # section by the frontend. First-pass translations only; subject
    # to further review.
    for book_code in EXTRA_CANONICAL_BOOK_ORDER:
        exported = export_extra_canonical_book(book_code)
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
