#!/usr/bin/env python3
"""segment_bensly_chapters.py — split Bensly body text into chapter candidates.

This takes the BODY-only working text produced by
`extract_bensly_body.py` and slices it into one file per chapter under:

  sources/2esdras/latin/intermediate/bensly1895_chapter_candidates/

These are **candidates**, not the final cleaned `latin/transcribed/`
files. They are meant to accelerate the cleanup pass by giving us a
stable chapter-by-chapter substrate with known page spans.
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
COMBINED_PATH = (
    REPO_ROOT
    / "sources"
    / "2esdras"
    / "latin"
    / "intermediate"
    / "bensly1895_body_main_text.txt"
)
OUT_DIR = (
    REPO_ROOT
    / "sources"
    / "2esdras"
    / "latin"
    / "intermediate"
    / "bensly1895_chapter_candidates"
)
MANIFEST_PATH = OUT_DIR / "manifest.json"

PAGE_MARK_RE = re.compile(r"(?m)^=== PAGE (\d{2,4}) ===$")


@dataclass(frozen=True)
class ChapterAnchor:
    chapter: int
    needle: str
    note: str


CHAPTER_ANCHORS: list[ChapterAnchor] = [
    ChapterAnchor(1, "\nI. ", "explicit chapter heading"),
    ChapterAnchor(2, "\nII. ", "explicit chapter heading"),
    ChapterAnchor(
        3,
        "=== PAGE 103 ===\nQuoniam uidi desertionem Sion",
        "page-start override; chapter III heading is absent in OCR body text",
    ),
    ChapterAnchor(4, "\nIV. ", "explicit chapter heading"),
    ChapterAnchor(5, "\nV. ", "explicit chapter heading"),
    ChapterAnchor(6, "\n1 VI. ", "chapter heading carries verse 1 inline"),
    ChapterAnchor(7, "\nVII. ", "explicit chapter heading"),
    ChapterAnchor(8, "\nVIII. ", "explicit chapter heading"),
    ChapterAnchor(9, "\nIX. ", "explicit chapter heading"),
    ChapterAnchor(10, "\nX. ", "explicit chapter heading"),
    ChapterAnchor(11, "\nXI. ", "explicit chapter heading"),
    ChapterAnchor(12, "\n1 XII. ", "chapter heading carries verse 1 inline"),
    ChapterAnchor(13, "\nXIII. ", "explicit chapter heading"),
    ChapterAnchor(14, "\nXIV. ", "explicit chapter heading"),
    ChapterAnchor(15, "\n1 XV. ", "chapter heading carries verse 1 inline"),
    ChapterAnchor(16, "\nXVI. ", "explicit chapter heading"),
]


def load_combined_text() -> str:
    return COMBINED_PATH.read_text(encoding="utf-8")


def find_page_markers(text: str) -> list[tuple[int, int]]:
    return [(m.start(), int(m.group(1))) for m in PAGE_MARK_RE.finditer(text)]


def nearest_page_at_or_before(page_markers: list[tuple[int, int]], pos: int) -> int:
    page = page_markers[0][1]
    for marker_pos, marker_page in page_markers:
        if marker_pos > pos:
            break
        page = marker_page
    return page


def build_segments(text: str) -> list[dict]:
    page_markers = find_page_markers(text)
    if not page_markers:
        raise ValueError("no page markers found in combined body text")

    starts: list[tuple[ChapterAnchor, int]] = []
    for anchor in CHAPTER_ANCHORS:
        idx = text.find(anchor.needle)
        if idx == -1:
            raise ValueError(f"chapter {anchor.chapter}: anchor not found: {anchor.needle!r}")
        starts.append((anchor, idx))

    starts.sort(key=lambda item: item[1])
    segments: list[dict] = []
    for i, (anchor, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
        raw = text[start:end].strip()
        start_page = nearest_page_at_or_before(page_markers, start)
        end_page = nearest_page_at_or_before(page_markers, max(start, end - 1))
        segments.append(
            {
                "chapter": anchor.chapter,
                "start_pos": start,
                "end_pos": end,
                "start_page": start_page,
                "end_page": end_page,
                "anchor_note": anchor.note,
                "text": raw,
            }
        )
    return segments


def write_outputs(segments: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    for seg in segments:
        chapter = seg["chapter"]
        out_path = OUT_DIR / f"ch{chapter:02d}.txt"
        header = (
            f"# 2 Esdras Bensly 1895 chapter candidate\n"
            f"# chapter: {chapter}\n"
            f"# source_pages: {seg['start_page']}-{seg['end_page']}\n"
            f"# note: {seg['anchor_note']}\n\n"
        )
        out_path.write_text(header + seg["text"].strip() + "\n", encoding="utf-8")
        manifest.append(
            {
                "chapter": chapter,
                "path": str(out_path.relative_to(REPO_ROOT)),
                "source_pages": [seg["start_page"], seg["end_page"]],
                "anchor_note": seg["anchor_note"],
            }
        )

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    text = load_combined_text()
    segments = build_segments(text)
    write_outputs(segments)
    print(f"wrote {len(segments)} chapter candidate files to {OUT_DIR}")
    print(f"wrote manifest to {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
