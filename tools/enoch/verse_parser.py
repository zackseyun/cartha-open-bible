#!/usr/bin/env python3
"""verse_parser.py — recover verse rows from Charles 1906 1 Enoch OCR.

The chapter-level OCR files under ``sources/enoch/ethiopic/transcribed/charles_1906/``
are not clean one-chapter isolates. Because adjacent Enoch chapters often share a
single printed page, a chapter file can contain:

- the *tail* of the previous chapter,
- the current chapter (usually with verse 1 unnumbered and later verses marked
  with Arabic numerals like ``2.``, ``3.``), and
- the *opening* of the next chapter introduced by a Roman chapter header
  (``II.``, ``XI.``, ``C.``, etc.).

This parser makes that usable for drafting by:

1. locating the requested chapter's Roman numeral header when present,
2. cutting off any spillover at the next chapter header,
3. preserving leading unnumbered verse 1 material, and
4. splitting the remainder on explicit Arabic verse markers.

It currently targets the Charles 1906 Ethiopic witness because that is the most
translation-ready OCR layer. Dillmann 1851 remains available as a chapter-level
secondary witness, but its verse alignment is not yet implemented here.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import asdict, dataclass
from typing import Iterable


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHARLES_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed" / "charles_1906"

_HEADING_PREFIXES = (
    "መጽሐፈ",
    "ምዕራፍ",
)
_SUPERSCRIPT_TRANSLATION = str.maketrans("", "", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_MULTI_SPACE_RE = re.compile(r"\s+")
_EXPLICIT_VERSE_RE = re.compile(r"(?<![0-9])(?P<verse>\d{1,3})\.\s*")


@dataclass(frozen=True)
class EnochVerseRow:
    chapter: int
    verse: int
    text: str
    marker_raw: str
    chapter_file: str


def roman_numeral(n: int) -> str:
    if not (1 <= n <= 399):
        raise ValueError(f"Roman numeral conversion only supports 1..399; got {n}")
    table = (
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    out: list[str] = []
    remaining = n
    for value, symbol in table:
        while remaining >= value:
            out.append(symbol)
            remaining -= value
    return "".join(out)


def chapter_path(chapter: int) -> pathlib.Path:
    return CHARLES_ROOT / f"ch{chapter:02d}.txt"


def _header_pattern(chapter: int) -> re.Pattern[str]:
    roman = re.escape(roman_numeral(chapter))
    return re.compile(rf"(?<![A-Z]){roman}\.(?![A-Z])")


def _normalize_text(raw: str) -> str:
    lines: list[str] = []
    for line in raw.translate(_SUPERSCRIPT_TRANSLATION).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in _HEADING_PREFIXES):
            continue
        lines.append(stripped)
    return _MULTI_SPACE_RE.sub(" ", " ".join(lines)).strip()


def extract_chapter_segment(chapter: int, raw_text: str) -> tuple[str, list[str]]:
    """Return the cleaned text span that belongs to ``chapter``.

    The OCR often contains adjacent chapter spillover. We slice from the current
    chapter's Roman header (when present) up to the next chapter's Roman header.
    Chapter 1 typically starts immediately without an ``I.`` header, so it uses
    the file start as its left boundary.
    """
    cleaned = _normalize_text(raw_text)
    warnings: list[str] = []

    start = 0
    if chapter > 1:
        current_match = _header_pattern(chapter).search(cleaned)
        if current_match is None:
            warnings.append(
                f"Could not locate Roman chapter header {roman_numeral(chapter)}. in chapter file; using full cleaned file."
            )
        else:
            start = current_match.end()

    end = len(cleaned)
    next_chapter = chapter + 1
    if next_chapter <= 108:
        next_match = _header_pattern(next_chapter).search(cleaned, pos=start)
        if next_match is not None:
            end = next_match.start()

    segment = cleaned[start:end].strip()
    if not segment:
        warnings.append("Resolved chapter segment is empty after spillover trimming.")
    return segment, warnings


def parse_chapter(chapter: int) -> tuple[list[EnochVerseRow], list[str]]:
    path = chapter_path(chapter)
    if not path.exists():
        raise FileNotFoundError(f"Missing Charles 1906 chapter file: {path}")

    segment, warnings = extract_chapter_segment(chapter, path.read_text(encoding="utf-8"))
    matches = list(_EXPLICIT_VERSE_RE.finditer(segment))

    rows: list[EnochVerseRow] = []
    if not matches:
        if segment:
            rows.append(
                EnochVerseRow(
                    chapter=chapter,
                    verse=1,
                    text=segment,
                    marker_raw="",
                    chapter_file=str(path.relative_to(REPO_ROOT)),
                )
            )
        else:
            warnings.append("No explicit verse markers and no recoverable text found.")
        return rows, warnings

    leading = segment[: matches[0].start()].strip()
    if leading:
        rows.append(
            EnochVerseRow(
                chapter=chapter,
                verse=1,
                text=leading,
                marker_raw="",
                chapter_file=str(path.relative_to(REPO_ROOT)),
            )
        )

    for idx, match in enumerate(matches):
        verse_num = int(match.group("verse"))
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(segment)
        text = segment[match.end() : next_start].strip()
        if not text:
            warnings.append(f"Verse marker {verse_num}. recovered with empty body text; skipped.")
            continue
        rows.append(
            EnochVerseRow(
                chapter=chapter,
                verse=verse_num,
                text=text,
                marker_raw=match.group(0).strip(),
                chapter_file=str(path.relative_to(REPO_ROOT)),
            )
        )

    verse_numbers = [row.verse for row in rows]
    if verse_numbers and verse_numbers[0] != 1:
        warnings.append(
            f"First recovered verse is {verse_numbers[0]}, not 1. The chapter likely still needs manual alignment review."
        )
    if len(verse_numbers) != len(set(verse_numbers)):
        warnings.append("Duplicate verse numbers recovered in chapter segment.")

    return rows, warnings


def load_verse(chapter: int, verse: int) -> tuple[EnochVerseRow | None, list[str]]:
    rows, warnings = parse_chapter(chapter)
    for row in rows:
        if row.verse == verse:
            return row, warnings
    warnings.append(f"Verse {chapter}:{verse} was not recovered from the Charles 1906 OCR segment.")
    return None, warnings


def recovered_verse_numbers(chapter: int) -> list[int]:
    return [row.verse for row in parse_chapter(chapter)[0]]


def build_jsonable(chapter: int) -> dict[str, object]:
    rows, warnings = parse_chapter(chapter)
    return {
        "chapter": chapter,
        "verse_count": len(rows),
        "verses": [asdict(row) for row in rows],
        "warnings": warnings,
    }


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse a Charles 1906 Enoch chapter into verse rows.")
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--json", action="store_true", help="Emit structured JSON instead of a human summary.")
    args = ap.parse_args(list(argv) if argv is not None else None)

    payload = build_jsonable(args.chapter)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"1 Enoch chapter {args.chapter}: recovered {payload['verse_count']} verses")
    warnings = payload["warnings"]
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    verses = payload["verses"]
    for verse in verses[:10]:
        preview = str(verse["text"])[:120]
        print(f"{verse['verse']}: {preview}")
    if len(verses) > 10:
        print(f"... {len(verses) - 10} more verses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
