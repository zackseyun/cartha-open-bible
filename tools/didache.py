#!/usr/bin/env python3
"""didache.py — loader for normalized Didache chapter files."""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "didache" / "transcribed"
CHAPTER_MAP_PATH = TRANSCRIBED_DIR / "chapter_map.json"


@dataclass(frozen=True)
class DidacheChapter:
    chapter: int
    text: str
    source_pages: list[int]
    source_edition: str = "Hitchcock & Brown 1884 (normalized OCR)"


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


def is_available() -> bool:
    return bool(available_chapters())


def load_chapter(chapter: int) -> DidacheChapter | None:
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
    return DidacheChapter(chapter=chapter, text=" ".join(body_lines).strip(), source_pages=source_pages)


def summary() -> dict:
    payload = {
        "book": "Didache",
        "chapter_count": len(available_chapters()),
        "chapters": available_chapters(),
        "chapter_map_present": CHAPTER_MAP_PATH.exists(),
    }
    if CHAPTER_MAP_PATH.exists():
        payload["chapter_map"] = json.loads(CHAPTER_MAP_PATH.read_text(encoding="utf-8"))
    return payload


if __name__ == "__main__":
    print(json.dumps(summary(), ensure_ascii=False, indent=2))
