#!/usr/bin/env python3
"""build_missing_fragment_verses.py — verse-index the 1875 Missing Fragment.

Builds a cleaned, verse-numbered working file for the Bensly 1875
Missing Fragment (4 Ezra / 2 Esdras VII 36–105). Most verses come from
the BODY-only extraction; verses 87–88 are rescued from the raw OCR
pages where the source text was classified as APPARATUS rather than
BODY.
"""
from __future__ import annotations

import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
INTERMEDIATE = REPO_ROOT / "sources" / "2esdras" / "latin" / "intermediate"
BODY_COMBINED = INTERMEDIATE / "bensly1875_body_main_text.txt"
RAW_DIR = REPO_ROOT / "sources" / "2esdras" / "raw_ocr" / "bensly1875"
OUT_DIR = INTERMEDIATE / "bensly1875_fragment_verses"
OUT_PATH = OUT_DIR / "ch07_036_105.txt"

PAGE_MARK_RE = re.compile(r"(?m)^=== PAGE (\d{2,4}) ===$")
VERSE_RE = re.compile(r"(?<![A-Za-z])(\d{2,3})(?![A-Za-z])")
LEADING_VERSE_RE = re.compile(r"^\s*\d{2,3}\s*[\])\.]?\s*")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def body_page_map() -> dict[int, str]:
    raw = BODY_COMBINED.read_text(encoding="utf-8")
    pieces = PAGE_MARK_RE.split(raw)
    out: dict[int, str] = {}
    # split structure: preamble, page, body, page, body ...
    for i in range(1, len(pieces), 2):
        page = int(pieces[i])
        body = pieces[i + 1].strip()
        out[page] = body
    return out


def extract_raw_apparatus_lead(page: int) -> str:
    path = RAW_DIR / f"bensly1875_p{page:04d}.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[APPARATUS]":
            capture = True
            continue
        if capture and stripped:
            return stripped
    raise ValueError(f"no apparatus lead line found in {path}")


def strip_leading_verse_number(text: str) -> str:
    return LEADING_VERSE_RE.sub("", text).strip()


def build_verse_map() -> dict[int, str]:
    page_map = body_page_map()

    verses: dict[int, str] = {}
    carried = ""
    for page in sorted(page_map):
        page_text = normalize_spaces(page_map[page])
        if page == 83 and "106" in page_text:
            page_text = page_text.split("106", 1)[0].rstrip()
        if carried:
            page_text = carried + " " + page_text
            carried = ""

        starts = list(VERSE_RE.finditer(page_text))
        if not starts:
            continue

        # keep any preface attached to the first verse on the page
        for idx, match in enumerate(starts):
            verse = int(match.group(1))
            start = match.start()
            end = starts[idx + 1].start() if idx + 1 < len(starts) else len(page_text)
            segment = strip_leading_verse_number(page_text[start:end].strip())
            verses[verse] = segment

        # if page begins with continuation before first visible verse number,
        # append it to the previous verse when possible
        first_start = starts[0].start()
        if first_start > 0 and verses:
            prev = max(v for v in verses if v < int(starts[0].group(1)))
            verses[prev] = normalize_spaces(verses[prev] + " " + page_text[:first_start])

    # Rescue verses 87–88 from the raw OCR pages that came through as apparatus-only.
    for verse, page in [(87, 75), (88, 76)]:
        lead = extract_raw_apparatus_lead(page)
        verses[verse] = normalize_spaces(strip_leading_verse_number(lead))

    # Trim spurious trailing material after verse 105 from page 83.
    if 105 in verses and "106" in verses[105]:
        verses[105] = normalize_spaces(verses[105].split("106", 1)[0])

    return verses


def main() -> int:
    verses = build_verse_map()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    expected = list(range(36, 106))
    missing = [v for v in expected if v not in verses]

    lines = [
        "# 2 Esdras / 4 Ezra VII 36–105",
        "# Bensly 1875 Missing Fragment verse-indexed working file",
        "# Source pages: 65–83",
        "# Note: verses 87–88 rescued from apparatus-only OCR pages 75–76",
        "",
    ]
    for verse in expected:
        if verse in verses:
            lines.append(f"{verse} {verses[verse]}")
        else:
            lines.append(f"# MISSING {verse}")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote verse-indexed fragment to {OUT_PATH}")
    if missing:
        print(f"missing verses: {missing}")
        return 1
    print("all verses 36–105 present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
