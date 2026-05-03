#!/usr/bin/env python3
"""dillmann_verse_parser.py — recover verse rows from Dillmann 1851 1 Enoch OCR.

Dillmann 1851 (Lipsiae, Vogel) was OCR'd at the chapter-file level. Each
``ch{N:02d}.txt`` file contains one or more sections delimited by
``ክፍል ፡ {ethiopic-numeral}`` headers. Within each section, verse 1 is the
unmarked leading text; subsequent verses are introduced by a standalone
Ethiopic numeral token (e.g. ``፪``, ``፲፩``).

This parser is a companion to ``verse_parser.py`` (Charles 1906) and exposes
the same ``EnochVerseRow`` dataclass and ``load_verse`` / ``parse_chapter``
interface so that ``multi_witness.py`` can call both identically.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import asdict, dataclass
from typing import Iterable

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DILLMANN_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed" / "dillmann_1851"

# ── Ethiopic numeral helpers ──────────────────────────────────────────────────

# Unicode ranges (see dillmann_verse_parser.py header comment for codepoints)
_ETH_ONES  = "፩፪፫፬፭፮፯፰፱"   # 1-9  (U+1369–U+1371)
_ETH_TENS  = "፲፳፴፵፶፷፸፹፺"   # 10-90 step 10 (U+1372–U+137A)
_ETH_HUND  = "፻"             # 100 (U+137B)
_ETH_NUMERAL_PAT = re.compile(rf"[{_ETH_ONES}{_ETH_TENS}{_ETH_HUND}]+")

# Numbers like ፬፻ (400) or ፭፻ (500) appear in verse text and must NOT be
# treated as verse markers. We exclude any numeral immediately followed by ፻.
_INLINE_NUMBER_RE = re.compile(rf"[{_ETH_ONES}{_ETH_TENS}]+{_ETH_HUND}")


def _eth_to_int(s: str) -> int:
    """Convert a Ge'ez numeral string to an integer (handles composites like ፲፩=11)."""
    ones_val = {c: i + 1 for i, c in enumerate(_ETH_ONES)}
    tens_val = {c: (i + 1) * 10 for i, c in enumerate(_ETH_TENS)}
    result = 0
    for ch in s:
        if ch in ones_val:
            result += ones_val[ch]
        elif ch in tens_val:
            result += tens_val[ch]
        elif ch == _ETH_HUND:
            # ፻ multiplies the preceding digit group; simple heuristic: add 100
            result += 100
    return result if result > 0 else 0


# ── Dataclass (mirrors verse_parser.EnochVerseRow) ────────────────────────────

@dataclass(frozen=True)
class EnochVerseRow:
    chapter: int
    verse: int
    text: str
    marker_raw: str
    chapter_file: str


# ── File resolution ───────────────────────────────────────────────────────────

def chapter_path(chapter: int) -> pathlib.Path:
    return DILLMANN_ROOT / f"ch{chapter:02d}.txt"


# ── Section extraction ────────────────────────────────────────────────────────

def _eth_numeral_for(n: int) -> str:
    """Return the Ge'ez numeral string for integer n (1–108)."""
    if n <= 0 or n > 108:
        raise ValueError(f"Chapter out of range: {n}")
    ones = _ETH_ONES
    tens = _ETH_TENS
    if n <= 9:
        return ones[n - 1]
    if n % 10 == 0 and n <= 90:
        return tens[n // 10 - 1]
    if n <= 99:
        return tens[n // 10 - 1] + ones[n % 10 - 1]
    if n == 100:
        return _ETH_HUND
    if n <= 108:
        return _ETH_HUND + ones[n - 101]
    raise ValueError(f"Cannot convert {n} to Ge'ez numeral")


def _section_header_re(chapter: int) -> re.Pattern[str]:
    """Regex matching the ክፍል header for the given chapter number."""
    eth = re.escape(_eth_numeral_for(chapter))
    return re.compile(rf"ክፍል\s*[፡:]\s*{eth}(?!\s*[፩-፻])")


def extract_section(chapter: int, raw_text: str) -> tuple[str, list[str]]:
    """Return the text span belonging to ``chapter``'s ክፍል section.

    Slices from this chapter's ክፍል header to the next one (or EOF).
    Chapter 1 is handled specially: ``ክፍል ፡ ፩`` may not exist in file ch01.txt
    for some editions — fall back to the text before the first ክፍል ፪ marker.
    """
    warnings: list[str] = []
    text = raw_text

    current_re = _section_header_re(chapter)
    current_match = current_re.search(text)

    if current_match is None:
        if chapter == 1:
            # ch01 may not have an explicit ፩ header — use text up to ክፍል ፪
            next_re = _section_header_re(2)
            next_match = next_re.search(text)
            if next_match:
                segment = text[: next_match.start()].strip()
            else:
                segment = text.strip()
            if not segment:
                warnings.append("Chapter 1: could not isolate section from file.")
            return segment, warnings
        warnings.append(
            f"Could not locate ክፍል header for chapter {chapter}; using full file text."
        )
        return text.strip(), warnings

    start = current_match.end()

    # Find the next ክፍል marker after our section start
    next_section_re = re.compile(r"ክፍል\s*[፡:]\s*[፩-፻]+")
    next_match = next_section_re.search(text, pos=start)
    end = next_match.start() if next_match else len(text)

    segment = text[start:end].strip()
    if not segment:
        warnings.append(f"Chapter {chapter}: resolved section is empty.")
    return segment, warnings


# ── Verse parsing ─────────────────────────────────────────────────────────────

# A verse marker is a standalone Ethiopic numeral token:
#   - preceded by whitespace (or start of string)
#   - NOT immediately followed by ፻ (which would make it a multiplied number)
_VERSE_MARKER_RE = re.compile(
    rf"(?<!\S)([{_ETH_ONES}{_ETH_TENS}]+)(?!\s*[{_ETH_HUND}])(?=\s)"
)


def _join_lines(text: str) -> str:
    """Collapse line breaks into spaces; normalise runs of whitespace."""
    joined = re.sub(r"\s+", " ", text.replace("\n", " "))
    return joined.strip()


def parse_chapter(chapter: int) -> tuple[list[EnochVerseRow], list[str]]:
    path = chapter_path(chapter)
    if not path.exists():
        raise FileNotFoundError(f"Missing Dillmann 1851 chapter file: {path}")

    raw = path.read_text(encoding="utf-8")
    section, warnings = extract_section(chapter, raw)
    text = _join_lines(section)

    matches = list(_VERSE_MARKER_RE.finditer(text))

    rows: list[EnochVerseRow] = []
    rel_path = str(path.relative_to(REPO_ROOT))

    if not matches:
        # Single-verse chapter or no explicit markers
        if text:
            rows.append(EnochVerseRow(
                chapter=chapter, verse=1, text=text,
                marker_raw="", chapter_file=rel_path,
            ))
        else:
            warnings.append("No verse markers and no text in section.")
        return rows, warnings

    leading = text[: matches[0].start()].strip()
    first_explicit_verse = _eth_to_int(matches[0].group(1))

    # If first explicit marker is verse 1, merge leading preamble into it
    # rather than emitting two verse-1 rows.
    prepend = ""
    if leading:
        if first_explicit_verse == 1:
            prepend = leading + " "
        else:
            rows.append(EnochVerseRow(
                chapter=chapter, verse=1, text=leading,
                marker_raw="", chapter_file=rel_path,
            ))

    for idx, match in enumerate(matches):
        verse_num = _eth_to_int(match.group(1))
        if verse_num == 0:
            warnings.append(f"Could not parse verse numeral: {match.group(0)!r}")
            continue
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[match.end(): next_start].strip()
        if verse_num == 1 and prepend:
            body = prepend + body
        if not body:
            warnings.append(f"Verse {verse_num}: marker present but body is empty; skipped.")
            continue
        rows.append(EnochVerseRow(
            chapter=chapter, verse=verse_num, text=body,
            marker_raw=match.group(0).strip(), chapter_file=rel_path,
        ))

    nums = [r.verse for r in rows]
    if nums and nums[0] != 1:
        warnings.append(f"First recovered verse is {nums[0]}, not 1 — may need manual review.")
    if len(nums) != len(set(nums)):
        warnings.append("Duplicate verse numbers in section.")

    return rows, warnings


def load_verse(chapter: int, verse: int) -> tuple[EnochVerseRow | None, list[str]]:
    rows, warnings = parse_chapter(chapter)
    for row in rows:
        if row.verse == verse:
            return row, warnings
    warnings.append(f"Verse {chapter}:{verse} not found in Dillmann 1851 OCR.")
    return None, warnings


def recovered_verse_numbers(chapter: int) -> list[int]:
    return [r.verse for r in parse_chapter(chapter)[0]]


def build_jsonable(chapter: int) -> dict:
    rows, warnings = parse_chapter(chapter)
    return {
        "chapter": chapter,
        "verse_count": len(rows),
        "verses": [asdict(r) for r in rows],
        "warnings": warnings,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse a Dillmann 1851 Enoch chapter into verse rows.")
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    payload = build_jsonable(args.chapter)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"1 Enoch {args.chapter} (Dillmann 1851): {payload['verse_count']} verses")
    for w in payload["warnings"]:
        print(f"  WARN: {w}")
    for v in payload["verses"][:10]:
        print(f"  {v['verse']}: {str(v['text'])[:120]}")
    if len(payload["verses"]) > 10:
        print(f"  … {len(payload['verses']) - 10} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
