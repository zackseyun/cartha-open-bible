#!/usr/bin/env python3
"""supplement_from_vulgate_org.py — fill remaining Latin gaps from a PD digital text.

Policy:
  - keep existing OCR-derived / fragment-derived verse text when present
  - fill only missing verses, empty verses, or verses containing obvious
    unresolved placeholders (`[⋯ ...]`, `...`) from the public-domain
    Latin text at vulgate.org

This is an editorial completion step, not a scan-grounded transcription
step, so it must remain transparent in the output headers.
"""
from __future__ import annotations

import html
import pathlib
import re
import urllib.request


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"

VERSE_RE = re.compile(r"(?m)^(\d+)\s(.*)$")
HTML_VERSE_RE = re.compile(
    r'<SUP class="Vulgate">(\d+)</SUP></td>\s*<td><span class="Latin">(.*?)</span>',
    re.S,
)
TAG_RE = re.compile(r"<[^>]+>")
CROP_RE = re.compile(r"\[⋯[^\]]*\]")
ELLIPSIS_RE = re.compile(r"\.\s*\.\s*\.")


def fetch_vulgate_chapter(chapter: int) -> dict[int, str]:
    url = f"https://vulgate.org/ot/4esdras_{chapter}.htm"
    raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", "ignore")
    verses: dict[int, str] = {}
    for m in HTML_VERSE_RE.finditer(raw):
        verse = int(m.group(1))
        latin_html = m.group(2)
        latin = TAG_RE.sub("", latin_html)
        latin = html.unescape(latin)
        latin = re.sub(r"\s+", " ", latin).strip()
        verses[verse] = latin
    if not verses:
        raise ValueError(f"no verses parsed from {url}")
    return verses


def parse_existing(path: pathlib.Path) -> tuple[list[str], dict[int, str]]:
    text = path.read_text(encoding="utf-8")
    comments = [ln for ln in text.splitlines() if ln.startswith("#")]
    verses = {int(m.group(1)): m.group(2).strip() for m in VERSE_RE.finditer(text)}
    return comments, verses


def needs_supplement(text: str) -> bool:
    return (not text.strip()) or bool(CROP_RE.search(text)) or bool(ELLIPSIS_RE.search(text))


def rewrite_chapter(chapter: int) -> tuple[pathlib.Path, list[int], list[int]]:
    path = TRANSCRIBED_DIR / f"ch{chapter:02d}.txt"
    existing_comments, existing = parse_existing(path)
    reference = fetch_vulgate_chapter(chapter)

    supplemented_missing: list[int] = []
    supplemented_placeholder: list[int] = []
    merged: dict[int, str] = {}

    for verse in sorted(reference):
        if verse not in existing:
            merged[verse] = reference[verse]
            supplemented_missing.append(verse)
        elif needs_supplement(existing[verse]):
            merged[verse] = reference[verse]
            supplemented_placeholder.append(verse)
        else:
            merged[verse] = existing[verse]

    header = [
        f"# 2 Esdras chapter {chapter} Latin transcription",
        "# Primary source: OCR-derived / fragment-derived working text where available",
        f"# Supplemental source for missing or placeholder verses: public-domain digital Latin text at https://vulgate.org/ot/4esdras_{chapter}.htm",
    ]
    if supplemented_missing:
        header.append("# Missing verses supplemented from PD digital text: " + ", ".join(map(str, supplemented_missing)))
    if supplemented_placeholder:
        header.append("# Placeholder/crop/ellipsis verses replaced from PD digital text: " + ", ".join(map(str, supplemented_placeholder)))
    header.append("")

    lines = header + [f"{v} {merged[v]}" for v in sorted(merged)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, supplemented_missing, supplemented_placeholder


def main() -> int:
    results = []
    for chapter in range(1, 17):
        path, missing, placeholders = rewrite_chapter(chapter)
        results.append((chapter, path, missing, placeholders))
        print(
            f"chapter {chapter:02d}: supplemented missing={len(missing)} "
            f"placeholder={len(placeholders)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
