#!/usr/bin/env python3
"""run_ocr.py — resumable Ethiopic OCR orchestrator for 1 Enoch.

Pilot target: chapter 1 across Dillmann 1851 and Charles 1906.
The same interface is meant to scale once the page map grows.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import pathlib
import sys
import time
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import ocr_geez  # type: ignore
import verse_parser  # type: ignore
import mask_superscripts  # type: ignore

PAGE_MAP = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "page_map.json"
OUT_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed"


def load_map() -> dict[str, Any]:
    return json.loads(PAGE_MAP.read_text(encoding="utf-8"))


def transcribe_page(pdf_path: pathlib.Path, page_number: int, *, book_hint: str, chapter_hint: str, opening_hint: str, preprocess: str = 'none') -> tuple[str, dict[str, Any]]:
    started = time.time()
    if preprocess == 'mask_superscripts':
        masked = mask_superscripts.mask_page(pdf_path, page_number)
        buf = __import__('io').BytesIO()
        masked['image'].save(buf, format='PNG')
        image = buf.getvalue()
    else:
        image = ocr_geez.render_page_png(pdf_path, page_number, dpi=400)
    result = ocr_geez.call_gemini_pro_geez(
        image,
        book_hint=book_hint,
        chapter_hint=chapter_hint,
        opening_hint=opening_hint,
        thinking_budget=512,
        max_output_tokens=20000,
    )
    result.page_number = page_number
    meta = {
        "page_number": page_number,
        "finish_reason": result.finish_reason,
        "confidence": result.confidence,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "tokens_thinking": result.tokens_thinking,
        "error": result.error,
        "duration_seconds": round(time.time() - started, 2),
        "preprocess": preprocess,
    }
    return result.geez_text, meta


def run_chapter(edition: str, chapter: int, *, force: bool = False, split_verses: bool = False, preprocess: str = 'none') -> dict[str, Any]:
    mapping = load_map()["editions"][edition]
    chapter_key = f"{chapter:03d}"
    chapter_meta = mapping["chapters"][chapter_key]
    pdf_path = REPO_ROOT / mapping["pdf"]
    pages: list[int] = chapter_meta["pages"]

    edition_dir = OUT_ROOT / edition
    page_dir = edition_dir / "pages"
    chapter_dir = edition_dir / f"ch{chapter:02d}"
    edition_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    page_texts: list[str] = []
    page_metas: list[dict[str, Any]] = []
    previous_text = ""
    for idx, page in enumerate(pages):
        stem = f"p{page:04d}"
        txt_path = page_dir / f"{stem}.txt"
        meta_path = page_dir / f"{stem}.json"
        if txt_path.exists() and meta_path.exists() and not force:
            text = txt_path.read_text(encoding="utf-8")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            text, meta = transcribe_page(
                pdf_path,
                page,
                book_hint=f"1 Enoch {edition}",
                chapter_hint=chapter_meta.get("chapter_hint", ""),
                opening_hint=chapter_meta.get("opening_hint", "") if idx == 0 else "",
                preprocess=preprocess,
            )
            txt_path.write_text(text + ("\n" if text and not text.endswith("\n") else ""), encoding="utf-8")
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cleaned = text.strip()
        if previous_text:
            meta["similarity_to_previous_page"] = round(difflib.SequenceMatcher(a=previous_text, b=cleaned).ratio(), 6)
            meta["suspect_duplicate"] = meta["similarity_to_previous_page"] >= 0.65
        else:
            meta["similarity_to_previous_page"] = None
            meta["suspect_duplicate"] = False
        previous_text = cleaned
        page_texts.append(cleaned)
        page_metas.append(meta)

    chapter_text = "\n\n".join(t for t in page_texts if t.strip()).strip() + "\n"
    chapter_txt_path = edition_dir / f"ch{chapter:02d}.txt"
    chapter_txt_path.write_text(chapter_text, encoding="utf-8")
    chapter_summary = {
        "edition": edition,
        "chapter": chapter,
        "pages": pages,
        "page_count": len(pages),
        "chars": len(chapter_text.strip()),
        "page_meta": page_metas,
        "preprocess": preprocess,
    }
    (edition_dir / f"ch{chapter:02d}.json").write_text(json.dumps(chapter_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if split_verses:
        manifest = verse_parser.write_verses(chapter_txt_path, chapter_dir)
        chapter_summary["verse_parse"] = {"verse_count": manifest["verse_count"]}
        (edition_dir / f"ch{chapter:02d}.json").write_text(json.dumps(chapter_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return chapter_summary


def promote_primary_chapter(chapter: int, *, primary_edition: str = "charles_1906") -> pathlib.Path:
    src = OUT_ROOT / primary_edition / f"ch{chapter:02d}.txt"
    dst = OUT_ROOT / f"ch{chapter:02d}.txt"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", required=True, choices=["dillmann_1851", "charles_1906"])
    ap.add_argument("--chapter", required=True, type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--split-verses", action="store_true")
    ap.add_argument("--promote-primary", action="store_true")
    ap.add_argument("--preprocess", choices=["none", "mask_superscripts"], default="none")
    args = ap.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY not set")

    summary = run_chapter(args.edition, args.chapter, force=args.force, split_verses=args.split_verses, preprocess=args.preprocess)
    if args.promote_primary:
        promote_primary_chapter(args.chapter)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
