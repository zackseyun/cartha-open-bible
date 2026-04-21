#!/usr/bin/env python3
"""build_ch07_hybrid.py — assemble a chapter VII hybrid working file.

The result is not yet a final `latin/transcribed/ch07.txt`. Instead it
creates a cleanup-focused hybrid:

  - chapter VII pre-fragment block from the Bensly 1895 main volume
  - verse-indexed Missing Fragment (VII 36–105) from Bensly 1875
  - chapter VII post-fragment block from the Bensly 1895 main volume

This gives the cleanup pass one authoritative working file centered on
the most text-critical section of the book.
"""
from __future__ import annotations

import pathlib


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
INTERMEDIATE = REPO_ROOT / "sources" / "2esdras" / "latin" / "intermediate"
CH07_CANDIDATE = INTERMEDIATE / "bensly1895_chapter_candidates" / "ch07.txt"
FRAGMENT_VERSES = INTERMEDIATE / "bensly1875_fragment_verses" / "ch07_036_105.txt"
OUT_PATH = INTERMEDIATE / "bensly_ch07_hybrid_working.txt"


def strip_comment_header(text: str) -> str:
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).strip()


def main() -> int:
    ch7 = strip_comment_header(CH07_CANDIDATE.read_text(encoding="utf-8"))
    fragment = FRAGMENT_VERSES.read_text(encoding="utf-8").strip()

    start_fragment = ch7.find("\n36 ")
    start_post = ch7.find("\n106 ")
    if start_fragment == -1 or start_post == -1:
        raise SystemExit("could not locate verse 36 / 106 boundaries in ch07 candidate")

    pre = ch7[:start_fragment].strip()
    post = ch7[start_post:].strip()

    out = [
        "# 2 Esdras chapter VII hybrid working file",
        "# pre-fragment: Bensly 1895 main volume",
        "# fragment (36–105): Bensly 1875 Missing Fragment, verse-indexed",
        "# post-fragment: Bensly 1895 main volume",
        "",
        "## PRE-FRAGMENT (1895 main volume)",
        pre,
        "",
        "## FRAGMENT VII 36–105 (1875 Missing Fragment)",
        fragment,
        "",
        "## POST-FRAGMENT (1895 main volume)",
        post,
        "",
    ]
    OUT_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote hybrid working file to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
