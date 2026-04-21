#!/usr/bin/env python3
"""first_clement.py — helper around the initial 1 Clement OCR layer."""
from __future__ import annotations

import json
import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "sources" / "1_clement" / "transcribed" / "raw"
BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:RUNNING HEAD|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)


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


def summary() -> dict:
    pages = available_raw_pages()
    return {
        "book": "1 Clement",
        "source": "Funk 1901 raw OCR",
        "available_raw_pages": pages,
        "greek_primary_pages": greek_primary_pages(),
        "page_classification": {str(p): classify_page(p) for p in pages},
    }


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=2))
