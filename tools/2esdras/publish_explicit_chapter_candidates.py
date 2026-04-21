#!/usr/bin/env python3
"""publish_explicit_chapter_candidates.py — promote explicit chapter candidates.

This script converts a chapter candidate file like:

  sources/2esdras/latin/intermediate/bensly1895_chapter_candidates/ch12.txt

into a loader-ready chapter file under:

  sources/2esdras/latin/transcribed/ch12.txt

It is intentionally conservative:
  - it only publishes **explicitly numbered** verses found in the OCR
  - it records any missing numbers as comments
  - it does not invent verses that are not visibly marked
"""
from __future__ import annotations

import argparse
import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CANDIDATE_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "intermediate" / "bensly1895_chapter_candidates"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"

PAGE_RE = re.compile(r"^=== PAGE \d{2,4} ===$")
MARKER_RE = re.compile(r"(?<![A-Za-z])(\d{1,3})(?![A-Za-z])")
ROMAN_HEAD_RE = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI)\.\s*")


def normalize_candidate_text(path: pathlib.Path) -> str:
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    lines = [ln.rstrip() for ln in raw_lines if not ln.startswith("#") and not PAGE_RE.fullmatch(ln.strip())]

    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        while line.endswith("-") and i + 1 < len(lines):
            i += 1
            line = line[:-1] + lines[i].lstrip()
        merged.append(line)
        i += 1
    return " ".join(merged).strip()


def extract_explicit_verses(text: str) -> tuple[dict[int, str], list[int], int | None]:
    markers = list(MARKER_RE.finditer(text))
    seq: list[tuple[int, int, int]] = []
    last = 0
    for m in markers:
        n = int(m.group(1))
        if 1 <= n <= 200 and n >= last:
            if not seq or n != seq[-1][0]:
                seq.append((n, m.start(), m.end()))
                last = n

    if not seq:
        return {}, [], None

    verses: dict[int, str] = {}
    first_explicit = seq[0][0]
    prefix = text[:seq[0][1]].strip()
    prefix = ROMAN_HEAD_RE.sub("", prefix, count=1).strip()

    for idx, (n, start, end) in enumerate(seq):
        next_start = seq[idx + 1][1] if idx + 1 < len(seq) else len(text)
        seg = text[end:next_start].strip()
        if idx == 0 and n == 1 and prefix:
            seg = (prefix + " " + seg).strip()
        if idx == 0 and n == 1:
            seg = ROMAN_HEAD_RE.sub("", seg, count=1).strip()
        verses[n] = seg

    missing: list[int] = []
    if seq:
        for v in range(seq[0][0], seq[-1][0] + 1):
            if v not in verses:
                missing.append(v)
    return verses, missing, first_explicit


def write_chapter(chapter: int, verses: dict[int, str], missing: list[int], first_explicit: int | None, *, force: bool) -> pathlib.Path:
    TRANSCRIBED_DIR.mkdir(parents=True, exist_ok=True)
    out = TRANSCRIBED_DIR / f"ch{chapter:02d}.txt"
    if out.exists() and not force:
        raise FileExistsError(f"{out} already exists; pass --force to overwrite")

    header = [
        f"# 2 Esdras chapter {chapter} explicit-marker transcription",
        "# Source: Bensly 1895 chapter candidate",
        "# Method: auto-published from explicitly numbered OCR markers only",
    ]
    if first_explicit and first_explicit > 1:
        header.append(f"# Missing opening coverage before first explicit marker: verses 1-{first_explicit - 1}")
    if missing:
        header.append("# Missing explicit markers inside covered range: " + ", ".join(str(v) for v in missing))
    header.append("")

    lines = header + [f"{v} {verses[v]}" for v in sorted(verses)]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chapters", required=True, help="Comma-separated chapter list, e.g. '12' or '2,12'")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    chapters = [int(part.strip()) for part in args.chapters.split(",") if part.strip()]
    for chapter in chapters:
        path = CANDIDATE_DIR / f"ch{chapter:02d}.txt"
        text = normalize_candidate_text(path)
        verses, missing, first_explicit = extract_explicit_verses(text)
        out = write_chapter(chapter, verses, missing, first_explicit, force=args.force)
        print(f"wrote {out}")
        print(f"  verses: {len(verses)} | first explicit: {first_explicit} | missing inside range: {missing or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
