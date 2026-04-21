#!/usr/bin/env python3
"""publish_ch07_fragment.py — publish VII 36–105 into transcribed/ch07.txt.

This promotes the verse-indexed Bensly 1875 Missing Fragment working
file into the canonical loader path used by `latin_bensly.py`.

The resulting `ch07.txt` is intentionally **partial**:
  - verses 36–105 are present
  - verses 1–35 and 106+ remain absent until further cleanup

That is still useful because it activates real loader coverage for the
most text-critical block of chapter VII right now.
"""
from __future__ import annotations

import pathlib


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SRC = (
    REPO_ROOT
    / "sources"
    / "2esdras"
    / "latin"
    / "intermediate"
    / "bensly1875_fragment_verses"
    / "ch07_036_105.txt"
)
OUT_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"
OUT = OUT_DIR / "ch07.txt"


def main() -> int:
    body = SRC.read_text(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    header = (
        "# 2 Esdras chapter 7 partial transcription\n"
        "# Published from Bensly 1875 Missing Fragment working file\n"
        "# Coverage: verses 36-105 only\n"
        "# Verses 1-35 and 106+ remain to be filled from later cleanup\n\n"
    )
    OUT.write_text(header + body, encoding="utf-8")
    print(f"wrote partial transcription to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
