#!/usr/bin/env python3
"""first_clement.py — helper around the initial 1 Clement OCR layer."""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "sources" / "1_clement" / "transcribed" / "raw"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "1_clement" / "transcribed"
BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:RUNNING HEAD|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)
CHAPTER_MAP_PATH = TRANSCRIBED_DIR / "chapter_map.json"


@dataclass(frozen=True)
class FirstClementChapter:
    chapter: int
    text: str
    source_pages: list[int]
    source_edition: str = "Funk 1901 (normalized OCR)"


def raw_page_path(page: int) -> pathlib.Path:
    return RAW_DIR / f"1c_funk1901_p{page:04d}.txt"


def available_raw_pages() -> list[int]:
    out: list[int] = []
    for path in sorted(RAW_DIR.glob("1c_funk1901_p*.txt")):
        m = re.search(r"_p(\d{4})\.txt$", path.name)
        if m:
            out.append(int(m.group(1)))
    return out


def extract_body(page_text: str) -> str:
    m = BODY_RE.search(page_text)
    return m.group(1).strip() if m else ""


def load_page(page: int) -> str | None:
    path = raw_page_path(page)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def classify_page(page: int) -> str:
    text = load_page(page)
    if text is None:
        return "missing"
    body = extract_body(text)
    if "ΚΛΗΜΕΝΤΟΣ ΠΡΟΣ ΚΟΡΙΝΘΙΟΥΣ" in body or "I CLEMENTIS" in text:
        return "greek_primary"
    if "CLEMENTIS AD CORINTHIOS" in body or "AD COR. I" in text:
        return "latin_facing"
    if "Epistula Barnabae" in body:
        return "transition"
    return "other"


def greek_primary_pages() -> list[int]:
    return [p for p in available_raw_pages() if classify_page(p) == "greek_primary"]


def chapter_path(chapter: int) -> pathlib.Path:
    return TRANSCRIBED_DIR / f"ch{chapter:02d}.txt"


def available_chapters() -> list[int]:
    out: list[int] = []
    for path in sorted(TRANSCRIBED_DIR.glob("ch*.txt")):
        try:
            out.append(int(path.stem[2:]))
        except ValueError:
            continue
    return out


def load_chapter(chapter: int) -> FirstClementChapter | None:
    path = chapter_path(chapter)
    if not path.exists():
        return None
    source_pages: list[int] = []
    body_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# source_pages:"):
            source_pages = [int(x) for x in line.split(":", 1)[1].strip().split(",") if x.strip()]
        elif line.startswith("#"):
            continue
        elif line.strip():
            body_lines.append(line.strip())
    return FirstClementChapter(chapter=chapter, text=" ".join(body_lines).strip(), source_pages=source_pages)


def summary() -> dict:
    pages = available_raw_pages()
    payload = {
        "book": "1 Clement",
        "source": "Funk 1901 raw OCR",
        "available_raw_pages": pages,
        "greek_primary_pages": greek_primary_pages(),
        "page_classification": {str(p): classify_page(p) for p in pages},
    }
    if CHAPTER_MAP_PATH.exists():
        payload["normalized"] = json.loads(CHAPTER_MAP_PATH.read_text(encoding="utf-8"))
    else:
        payload["normalized"] = {
            "chapter_count_present": len(available_chapters()),
            "chapters": available_chapters(),
            "chapter_map_present": False,
        }
    return payload


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=2))
