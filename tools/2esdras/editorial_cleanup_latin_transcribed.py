#!/usr/bin/env python3
"""editorial_cleanup_latin_transcribed.py — conservative cleanup pass.

This applies only fixes that are editorially low-risk:

- remove verse-number bleed inside words, e.g.
    para14 tum   -> paratum
    monumen17 tis -> monumentis
    inter45 rogaui -> interrogaui

It does **not** invent missing verses or fill omitted text.
"""
from __future__ import annotations

import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"

BLEED_RE = re.compile(r"([A-Za-zÀ-ÿ])\d+\s*([A-Za-zÀ-ÿ])")
HYPHEN_BREAK_RE = re.compile(r"([A-Za-zÀ-ÿ])-\s+([A-Za-zÀ-ÿ])")

TARGETED_REPLACEMENTS = {
    "orfa num": "orfanum",
    "flagel lorum": "flagellorum",
}


def clean_text(text: str) -> tuple[str, int]:
    total = 0
    while True:
        text, count = BLEED_RE.subn(r"\1\2", text)
        total += count
        if count == 0:
            break
    while True:
        text, count = HYPHEN_BREAK_RE.subn(r"\1\2", text)
        total += count
        if count == 0:
            break
    for old, new in TARGETED_REPLACEMENTS.items():
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            total += count
    return text, total


def main() -> int:
    changed = 0
    total_fixes = 0
    for path in sorted(TRANSCRIBED_DIR.glob("ch*.txt")):
        original = path.read_text(encoding="utf-8")
        cleaned, fixes = clean_text(original)
        if fixes:
            path.write_text(cleaned, encoding="utf-8")
            changed += 1
            total_fixes += fixes
            print(f"{path.name}: fixed {fixes} verse-number bleed artifact(s)")
    print(f"changed files: {changed}, total fixes: {total_fixes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
