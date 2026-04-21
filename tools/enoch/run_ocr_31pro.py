#!/usr/bin/env python3
"""run_ocr_31pro.py — Phase 11b Enoch OCR runner pinned to Gemini 3.1 Pro.

Why this lives next to `run_ocr.py` instead of replacing it:

  `tools/ethiopic/ocr_geez.py` is the SHARED Geʿez OCR driver used by
  both Enoch (this phase) and Jubilees (Phase 12). Its production
  default is intentionally conservative; bumping it to a preview model
  is a separate decision that affects more than this phase.

  This runner sidesteps that by calling `bakeoff_geez_ocr.call_gemini`
  directly with `model="gemini-3.1-pro-preview"` — the engine that
  won the 2026-04-22 three-engine bake-off (80.15% vs scan-truth on
  Charles 1906 ch 1 vv 1-5, vs 65.33% for the 2.5 Pro baseline and
  46.48% for Azure GPT-5.4). Full bake-off artefacts:
  `sources/enoch/ethiopic/reports/ocr_bakeoff_2026-04-22/`.

The output layout matches existing `run_ocr.py`:
  sources/enoch/ethiopic/transcribed/<edition>/pages/p<NNNN>.txt
  sources/enoch/ethiopic/transcribed/<edition>/pages/p<NNNN>.json
  sources/enoch/ethiopic/transcribed/<edition>/ch<NN>.txt
  sources/enoch/ethiopic/transcribed/<edition>/ch<NN>.json

so downstream tools (`validate_vs_scan_truth.py`,
`validate_vs_betamasaheft.py`, `multi_witness.py`) keep working
without modification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import pathlib
import sys
import time
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import bakeoff_geez_ocr  # type: ignore

PAGE_MAP = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "page_map.json"
OUT_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed"
DEFAULT_MODEL = "gemini-3.1-pro-preview"

GEEZ_PROMPT = bakeoff_geez_ocr.GEEZ_PROMPT


def load_map() -> dict[str, Any]:
    return json.loads(PAGE_MAP.read_text(encoding="utf-8"))


def transcribe_page(
    pdf_path: pathlib.Path,
    page_number: int,
    *,
    book_hint: str,
    chapter_hint: str,
    opening_hint: str,
    model: str,
    dpi: int,
) -> tuple[str, dict[str, Any]]:
    started = time.time()
    image = bakeoff_geez_ocr.render_page_png(pdf_path, page_number, dpi=dpi)
    image_sha = hashlib.sha256(image).hexdigest()
    prompt = GEEZ_PROMPT.format(
        book_hint=book_hint,
        chapter_hint=chapter_hint or "this page",
        opening_hint=opening_hint or "(no opening hint)",
    )
    result = bakeoff_geez_ocr.call_gemini(image, prompt, model=model)
    text = (result.text or "").strip()
    text = text + ("\n" if text and not text.endswith("\n") else "")
    meta = {
        "page_number": page_number,
        "model": result.model_id,
        "engine": result.engine,
        "finish_reason": result.finish_reason,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "tokens_thinking": result.tokens_thinking,
        "duration_seconds": round(time.time() - started, 2),
        "image_sha256": image_sha,
        "render_dpi": dpi,
        "transcribed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": result.error or None,
    }
    return text, meta


def run_chapter(
    edition: str,
    chapter: int,
    *,
    force: bool,
    model: str,
    dpi: int,
) -> dict[str, Any]:
    mapping = load_map()["editions"][edition]
    chapter_key = f"{chapter:03d}"
    if chapter_key not in mapping["chapters"]:
        raise SystemExit(
            f"page_map.json has no entry for {edition} chapter {chapter}. "
            f"Add it (pages, chapter_hint, opening_hint) before re-running."
        )
    chapter_meta = mapping["chapters"][chapter_key]
    pdf_path = REPO_ROOT / mapping["pdf"]
    pages: list[int] = chapter_meta["pages"]
    if not pages:
        raise SystemExit(f"page_map.json {edition} ch{chapter} has empty page list")

    edition_dir = OUT_ROOT / edition
    page_dir = edition_dir / "pages"
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
            print(f"  [skip] {edition} {stem} (already on disk)")
        else:
            print(f"  [ocr ] {edition} {stem} via {model} \u2026", flush=True)
            text, meta = transcribe_page(
                pdf_path,
                page,
                book_hint=f"1 Enoch {edition}",
                chapter_hint=chapter_meta.get("chapter_hint", ""),
                opening_hint=chapter_meta.get("opening_hint", "") if idx == 0 else "",
                model=model,
                dpi=dpi,
            )
            txt_path.write_text(text, encoding="utf-8")
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(
                f"         finish={meta['finish_reason']} chars={len(text.strip())} "
                f"tokens_out={meta['tokens_out']} dur={meta['duration_seconds']}s "
                f"err={meta['error'] or '-'}"
            )

        cleaned = text.strip()
        if previous_text:
            ratio = difflib.SequenceMatcher(a=previous_text, b=cleaned).ratio()
            meta["similarity_to_previous_page"] = round(ratio, 6)
            meta["suspect_duplicate"] = ratio >= 0.65
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
        "model": model,
        "page_meta": page_metas,
    }
    (edition_dir / f"ch{chapter:02d}.json").write_text(
        json.dumps(chapter_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return chapter_summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition", required=True, choices=["dillmann_1851", "charles_1906"])
    ap.add_argument("--chapter", required=True, type=int)
    ap.add_argument("--force", action="store_true", help="Re-OCR pages even if cached on disk")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model id (default: {DEFAULT_MODEL})")
    ap.add_argument("--dpi", type=int, default=400)
    args = ap.parse_args()

    print(f"Phase 11b OCR \u2014 {args.edition} chapter {args.chapter} via {args.model}")
    summary = run_chapter(
        args.edition,
        args.chapter,
        force=args.force,
        model=args.model,
        dpi=args.dpi,
    )
    print(json.dumps(
        {k: v for k, v in summary.items() if k != "page_meta"},
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
