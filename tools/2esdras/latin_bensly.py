#!/usr/bin/env python3
"""latin_bensly.py — loader for chapter-indexed 2 Esdras Latin text.

This module defines the canonical on-disk format for the cleaned Latin
text derived from Bensly 1895 / 1875 OCR work:

    sources/2esdras/latin/transcribed/ch01.txt
    sources/2esdras/latin/transcribed/ch02.txt
    ...

Expected chapter-file format:

  - one verse begins with `<verse_number><space><text>` or
    `<verse_number><TAB><text>`
  - blank lines are ignored
  - lines beginning with `#` are comments
  - non-empty lines that do not begin a new verse are treated as
    continuations of the previous verse and appended with a space

Example:

    1 Et factum est ...
    2 Respondit mihi ...
      continuation of verse 2
    # editorial note
    3 Dixi autem ...

The actual transcription pass will populate these files later. This
loader lets the rest of the 2 Esdras pipeline target a stable format
now.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"
VERSE_LINE_RE = re.compile(r"^\s*(\d+)(?:\t+|\s+)(.+?)\s*$")


@dataclass(frozen=True)
class LatinVerse:
    chapter: int
    verse: int
    text: str
    source_edition: str = "Bensly 1895 / 1875 (cleaned Latin)"


def chapter_path(chapter: int) -> pathlib.Path:
    return TRANSCRIBED_DIR / f"ch{chapter:02d}.txt"


def available_chapters() -> list[int]:
    out: list[int] = []
    if not TRANSCRIBED_DIR.exists():
        return out
    for path in sorted(TRANSCRIBED_DIR.glob("ch*.txt")):
        m = re.fullmatch(r"ch(\d{2})\.txt", path.name)
        if m:
            out.append(int(m.group(1)))
    return out


def is_available() -> bool:
    return bool(available_chapters())


def load_chapter(chapter: int) -> dict[int, LatinVerse]:
    path = chapter_path(chapter)
    if not path.exists():
        raise FileNotFoundError(path)

    verses: dict[int, LatinVerse] = {}
    current_verse: int | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue

        m = VERSE_LINE_RE.match(line)
        if m:
            current_verse = int(m.group(1))
            verses[current_verse] = LatinVerse(
                chapter=chapter,
                verse=current_verse,
                text=m.group(2).strip(),
            )
            continue

        if current_verse is None:
            raise ValueError(
                f"{path}: encountered continuation text before first verse: {line!r}"
            )

        prev = verses[current_verse]
        verses[current_verse] = LatinVerse(
            chapter=prev.chapter,
            verse=prev.verse,
            text=(prev.text + " " + line.strip()).strip(),
            source_edition=prev.source_edition,
        )

    return verses


def load_verse(chapter: int, verse: int) -> LatinVerse | None:
    path = chapter_path(chapter)
    if not path.exists():
        return None
    return load_chapter(chapter).get(verse)


def summary() -> dict:
    chapters = available_chapters()
    return {
        "pipeline": "2esdras_latin_bensly",
        "status": "ready_for_transcribed_input",
        "transcribed_dir": str(TRANSCRIBED_DIR),
        "chapter_count": len(chapters),
        "chapters": chapters,
    }


if __name__ == "__main__":
    import argparse
    import pprint

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chapter", type=int)
    p.add_argument("--verse", type=int)
    args = p.parse_args()

    if args.chapter and args.verse:
        pprint.pp(load_verse(args.chapter, args.verse))
    elif args.chapter:
        pprint.pp(load_chapter(args.chapter))
    else:
        pprint.pp(summary())
