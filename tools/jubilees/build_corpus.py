#!/usr/bin/env python3
"""build_corpus.py — assemble a Jubilees Ge'ez verse corpus from OCR pages.

Reads the Charles 1895 page map plus OCR `.txt` files, runs the Jubilees
verse parser chapter by chapter, and writes one JSONL record per verse.

Default output:
  sources/jubilees/ethiopic/corpus/JUBILEES.jsonl

This is the translation-ready Zone 1 base corpus for later drafter work.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JUBILEES_ROOT = REPO_ROOT / "sources" / "jubilees"
DEFAULT_PAGE_MAP = JUBILEES_ROOT / "page_map.json"
BODY_DIR = JUBILEES_ROOT / "ethiopic" / "transcribed" / "charles_1895" / "body"
PILOT_CH1_DIR = JUBILEES_ROOT / "ethiopic" / "transcribed" / "charles_1895" / "pilot_ch01_3p1_run1"
LEGACY_PILOT_CH1_DIR = JUBILEES_ROOT / "ethiopic" / "transcribed" / "charles_1895" / "pilot_ch01"
DEFAULT_OUT = JUBILEES_ROOT / "ethiopic" / "corpus" / "JUBILEES.jsonl"

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import verse_parser  # noqa: E402


SOURCE_EDITION = "Charles 1895 Ethiopic critical edition (Gemini 3.1 Pro OCR)"


def display_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def parse_chapter_spec(spec: str, available: set[int]) -> list[int]:
    if spec == "all":
        return sorted(available)
    out: set[int] = set()
    for part in spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(token))
    return sorted(c for c in out if c in available)


def load_page_map(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def chapter_pages(page_map: dict[str, Any], chapter: int) -> list[int]:
    section = page_map["editions"]["charles_1895"]["chapters"]
    key = f"{chapter:03d}"
    if key not in section:
        raise KeyError(f"page_map has no Charles 1895 entry for chapter {chapter}")
    return [int(p) for p in section[key]["pages"]]


def candidate_source_dirs(chapter: int) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    if BODY_DIR.exists():
        out.append(BODY_DIR)
    if chapter == 1 and PILOT_CH1_DIR.exists():
        out.append(PILOT_CH1_DIR)
    if chapter == 1 and LEGACY_PILOT_CH1_DIR.exists():
        out.append(LEGACY_PILOT_CH1_DIR)
    if not out:
        raise FileNotFoundError(
            f"No OCR source dir found for chapter {chapter}. Looked at {BODY_DIR}, {PILOT_CH1_DIR}, and {LEGACY_PILOT_CH1_DIR}."
        )
    return out


def load_page_texts(chapter: int, pages: list[int], *, allow_missing_pages: bool) -> tuple[list[tuple[int, str]], list[int], list[str]]:
    page_texts: list[tuple[int, str]] = []
    missing: list[int] = []
    labels_used: list[str] = []
    candidates = candidate_source_dirs(chapter)
    for page in pages:
        chosen = False
        for candidate_dir in candidates:
            candidate_label = (
                "body" if candidate_dir == BODY_DIR
                else "pilot_ch01_3p1_run1" if candidate_dir == PILOT_CH1_DIR
                else "pilot_ch01_legacy" if candidate_dir == LEGACY_PILOT_CH1_DIR
                else candidate_dir.name
            )
            path = candidate_dir / f"charles_1895_ethiopic_p{page:04d}.txt"
            if not path.exists():
                continue
            page_texts.append((page, path.read_text(encoding="utf-8")))
            if candidate_label not in labels_used:
                labels_used.append(candidate_label)
            chosen = True
            break
        if not chosen:
            missing.append(page)
    if missing and not allow_missing_pages:
        raise FileNotFoundError(
            f"Chapter {chapter} missing OCR pages in configured source dirs: {missing}"
        )
    if not page_texts:
        raise FileNotFoundError(f"Chapter {chapter} has no OCR page text in configured source dirs")
    return page_texts, missing, labels_used


def build_records(
    *,
    page_map: dict[str, Any],
    chapters: list[int],
    allow_missing_pages: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for chapter in chapters:
        pages = chapter_pages(page_map, chapter)
        page_texts, missing, labels_used = load_page_texts(chapter, pages, allow_missing_pages=allow_missing_pages)
        rows = verse_parser.parse_chapter_pages(page_texts)
        if missing:
            warnings.append(f"ch{chapter:02d}: missing OCR pages {missing}")
        if len(labels_used) > 1:
            warnings.append(f"ch{chapter:02d}: mixed OCR source dirs {labels_used}")
        for row in rows:
            record = {
                "book": "JUB",
                "book_title": "Jubilees",
                "chapter": chapter,
                "verse": row.verse,
                "geez": row.text,
                "source_page_start": row.source_page,
                "chapter_source_pages": pages,
                "source_edition": SOURCE_EDITION,
                "witness": "charles_1895",
                "ocr_source_dirs": labels_used,
                "validation": "jubilees_verse_parser",
            }
            if row.verse == 0:
                record["kind"] = "prologue"
            if missing:
                record["warnings"] = [f"chapter missing OCR pages: {missing}"]
            records.append(record)
    return records, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page-map", type=pathlib.Path, default=DEFAULT_PAGE_MAP)
    ap.add_argument("--chapters", default="all")
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--allow-missing-pages", action="store_true")
    args = ap.parse_args()

    page_map = load_page_map(args.page_map)
    available = {int(k) for k in page_map["editions"]["charles_1895"]["chapters"].keys()}
    chapters = parse_chapter_spec(args.chapters, available)
    if not chapters:
        raise SystemExit("No chapters resolved from the supplied spec/page map")

    records, warnings = build_records(
        page_map=page_map,
        chapters=chapters,
        allow_missing_pages=args.allow_missing_pages,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    verse_count = sum(1 for r in records if r["verse"] >= 1)
    prologue_count = sum(1 for r in records if r["verse"] == 0)
    print(f"wrote {display_path(args.out)}")
    print(f"chapters: {chapters[0]}-{chapters[-1]} ({len(chapters)} total)")
    print(f"records: {len(records)}  verses: {verse_count}  prologues: {prologue_count}")
    if warnings:
        print(f"warnings ({len(warnings)}):")
        for warning in warnings[:20]:
            print(f"  - {warning}")
        if len(warnings) > 20:
            print(f"  … and {len(warnings) - 20} more")
    else:
        print("warnings: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
