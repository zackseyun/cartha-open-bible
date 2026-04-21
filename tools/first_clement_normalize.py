#!/usr/bin/env python3
"""first_clement_normalize.py — normalize the current 1 Clement OCR layer.

This is a first pass over the Funk 1901 raw OCR pages. It:

- uses the Greek-primary page set from `tools/first_clement.py`
- strips line-number noise and non-body sections
- segments by chapter headings
- applies a handful of page-local heading overrides where OCR dropped
  or distorted numerals
- records any still-missing chapters in `chapter_map.json`
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass, field

import first_clement


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "sources" / "1_clement" / "transcribed" / "raw"
OUT_DIR = REPO_ROOT / "sources" / "1_clement" / "transcribed"
SUPPLEMENT_DIR = OUT_DIR / "supplemental"

BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:RUNNING HEAD|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)
LEADING_NUMBERS_RE = re.compile(r"^(?:\d+\s*)+")
HEADING_RE = re.compile(r"^([IVXLCDMΧΛΙ]+)\.\s*(.*)$")

EXCLUDE_PAGES = {345}  # 2 Clement starts here; keep 1 Clement bounded.

# OCR on a few pages distorted chapter numerals. We pin the intended
# sequence explicitly rather than pretending the raw token is reliable.
PAGE_HEADING_OVERRIDES: dict[int, list[int]] = {
    275: [10],
    301: [31, 32],
    303: [33, 34],
    305: [35],
    313: [40, 41],
    327: [52, 53],
    337: [60],
}

# Some pages begin mid-flow before the next visible chapter marker.
# Where we know from surrounding evidence which chapter that material
# belongs to, we pin it here.
PREHEADING_CHAPTER_OVERRIDES: dict[int, int] = {
    293: 22,
    315: 43,
}


@dataclass
class ChapterBuffer:
    chapter: int
    source_pages: set[int] = field(default_factory=set)
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def greek_pages() -> list[int]:
    return [p for p in first_clement.greek_primary_pages() if p not in EXCLUDE_PAGES]


def page_path(page: int) -> pathlib.Path:
    return RAW_DIR / f"1c_funk1901_p{page:04d}.txt"


def extract_body(path: pathlib.Path) -> str:
    m = BODY_RE.search(path.read_text(encoding="utf-8"))
    return m.group(1).strip() if m else ""


def clean_lines(body: str) -> list[str]:
    out: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = LEADING_NUMBERS_RE.sub("", line).strip()
        if not line:
            continue
        out.append(line)
    return out


def normalize_heading_token(token: str) -> str:
    return token.replace("Χ", "X").replace("Λ", "L").replace("Ι", "I")


ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(token: str) -> int:
    token = normalize_heading_token(token)
    total = 0
    prev = 0
    for ch in reversed(token):
        val = ROMAN_MAP[ch]
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


def join_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    out = lines[0].strip()
    for line in lines[1:]:
        nxt = line.strip()
        if not nxt:
            continue
        if out.endswith("-"):
            out = out[:-1] + nxt
        else:
            out += " " + nxt
    return re.sub(r"\s+", " ", out).strip()


def build_chapters() -> tuple[dict[int, ChapterBuffer], list[int]]:
    chapters: dict[int, ChapterBuffer] = {}
    current_chapter: int | None = None
    detected_heading_count: dict[int, int] = {}

    for page in greek_pages():
        lines = clean_lines(extract_body(page_path(page)))
        page_heading_index = 0
        page_override_list = PAGE_HEADING_OVERRIDES.get(page, [])
        preheading_buffer: list[str] = []

        def ensure(ch: int) -> ChapterBuffer:
            return chapters.setdefault(ch, ChapterBuffer(chapter=ch))

        for line in lines:
            m = HEADING_RE.match(line)
            if m:
                if preheading_buffer:
                    target = PREHEADING_CHAPTER_OVERRIDES.get(page, current_chapter)
                    if target is not None:
                        buf = ensure(target)
                        buf.source_pages.add(page)
                        buf.lines.extend(preheading_buffer)
                    preheading_buffer = []

                chapter = (
                    page_override_list[page_heading_index]
                    if page_heading_index < len(page_override_list)
                    else roman_to_int(m.group(1))
                )
                page_heading_index += 1
                detected_heading_count[page] = page_heading_index
                current_chapter = chapter
                buf = ensure(chapter)
                buf.source_pages.add(page)
                rest = m.group(2).strip()
                if rest:
                    buf.lines.append(rest)
                continue

            if current_chapter is None:
                continue

            if page in PREHEADING_CHAPTER_OVERRIDES and page_heading_index == 0:
                preheading_buffer.append(line)
            else:
                buf = ensure(current_chapter)
                buf.source_pages.add(page)
                buf.lines.append(line)

        if preheading_buffer:
            target = PREHEADING_CHAPTER_OVERRIDES.get(page, current_chapter)
            if target is not None:
                buf = ensure(target)
                buf.source_pages.add(page)
                buf.lines.extend(preheading_buffer)

    missing = [n for n in range(1, 66) if n not in chapters]
    if 22 in chapters:
        chapters[22].notes.append("Recovered from pre-heading body text on page 293 (heading omitted in OCR).")
    if 43 in chapters:
        chapters[43].notes.append("Recovered from pre-heading body text on page 315 (heading omitted in OCR).")
    return chapters, missing


def write_outputs(chapters: dict[int, ChapterBuffer], missing: list[int]) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chapter_map: dict[str, dict[str, object]] = {}

    for chapter in sorted(chapters):
        buf = chapters[chapter]
        text = join_lines(buf.lines)
        out_path = OUT_DIR / f"ch{chapter:02d}.txt"
        lines = [
            f"# 1 Clement chapter {chapter}",
            f"# source_pages: {','.join(str(p) for p in sorted(buf.source_pages))}",
        ]
        for note in buf.notes:
            lines.append(f"# note: {note}")
        lines.extend([text, ""])
        out_path.write_text("\n".join(lines), encoding="utf-8")
        chapter_map[f"{chapter:02d}"] = {
            "chapter": chapter,
            "source_pages": sorted(buf.source_pages),
            "chars": len(text),
            "path": str(out_path.relative_to(REPO_ROOT)),
            "notes": buf.notes,
        }

    payload = {
        "book": "1 Clement",
        "source": "Funk 1901 raw OCR normalization",
        "chapter_count_present": len(chapter_map),
        "missing_chapters": missing,
        "chapters": chapter_map,
    }

    # Overlay any explicit chapter supplements last.
    for sup in sorted(SUPPLEMENT_DIR.glob("ch*.txt")):
        m = re.fullmatch(r"ch(\d{2})\.txt", sup.name)
        if not m:
            continue
        chapter = int(m.group(1))
        lines = sup.read_text(encoding="utf-8").splitlines()
        body = " ".join(line.strip() for line in lines if line.strip() and not line.startswith("#"))
        out_path = OUT_DIR / f"ch{chapter:02d}.txt"
        out_path.write_text(sup.read_text(encoding="utf-8"), encoding="utf-8")
        notes = [f"Supplemented from {sup.relative_to(REPO_ROOT)} pending direct source-layer recovery."]
        chapter_map[f"{chapter:02d}"] = {
            "chapter": chapter,
            "source_pages": [],
            "chars": len(body),
            "path": str(out_path.relative_to(REPO_ROOT)),
            "notes": notes,
        }
        if chapter in missing:
            missing.remove(chapter)

    payload["chapter_count_present"] = len(chapter_map)
    (OUT_DIR / "chapter_map.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    chapters, missing = build_chapters()
    payload = write_outputs(chapters, missing)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
