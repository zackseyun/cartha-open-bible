#!/usr/bin/env python3
"""fetch_first_clement_supplements.py — fetch missing 1 Clement chapters.

This is a narrow recovery helper for the current Funk 1901 OCR gap at
chapter 42 (and the partial chapter 43). It pulls the Greek text from a
public digital repository so the normalization layer can proceed while a
future direct-source recovery pass remains possible.
"""
from __future__ import annotations

import html
import pathlib
import re
import urllib.request


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "sources" / "1_clement" / "transcribed" / "supplemental"

CHAPTER_URLS = {
    42: "https://greekdoc.com/DOCUMENTS/early/1clem42.html",
    43: "https://greekdoc.com/DOCUMENTS/early/1clem43.html",
}


def extract_text_from_html(raw_html: str) -> str:
    rows = re.findall(r"<tr><td>(.*?)</td><td>", raw_html, flags=re.S | re.I)
    pieces: list[str] = []
    for row in rows:
        row = re.sub(r"<span class=\"num\".*?</span>&nbsp;", "", row, flags=re.S)
        row = re.sub(r"<a [^>]*>", "", row)
        row = row.replace("</a>", "")
        row = re.sub(r"<[^>]+>", "", row)
        row = html.unescape(row)
        row = re.sub(r"\s+", " ", row).strip()
        if row:
            pieces.append(row)
    return " ".join(pieces).strip()


def fetch_chapter(chapter: int) -> str:
    url = CHAPTER_URLS[chapter]
    raw_html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "ignore")
    text = extract_text_from_html(raw_html)
    if not text:
        raise RuntimeError(f"failed to extract text for 1 Clement {chapter} from {url}")
    return text


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for chapter in sorted(CHAPTER_URLS):
        text = fetch_chapter(chapter)
        out = OUT_DIR / f"ch{chapter:02d}.txt"
        out.write_text(
            "\n".join(
                [
                    f"# 1 Clement chapter {chapter}",
                    "# supplemental_source: greekdoc.com public digital Greek text",
                    text,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
