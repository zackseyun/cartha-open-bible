#!/usr/bin/env python3
"""syriac_primary.py — loader for the bridged 2 Baruch Ceriani Syriac corpus.

This is intentionally page-first for now. The repo currently contains a sparse
Ceriani calibration set, not a continuous chapter-aligned transcription. So the
stable loader surface is:

- iter_pages() / load_page(pdf_page)
- page-index summary

Later chapter/verse mapping can be layered on top of this without changing where
clean primary-witness text is loaded from.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSCRIBED_ROOT = REPO_ROOT / "sources" / "2baruch" / "syriac" / "transcribed" / "ceriani1871"
INDEX_PATH = TRANSCRIBED_ROOT / "page_index.json"
PAGES_DIR = TRANSCRIBED_ROOT / "pages"


@dataclass(frozen=True)
class SyriacPrimaryPage:
    pdf_page: int
    printed_page: int | None
    text: str
    running_head_raw: str
    source_edition: str = "Ceriani 1871 primary Syriac edition (bridged OCR corpus)"


def _load_index() -> dict:
    if not INDEX_PATH.exists():
        return {
            "book": "2 Baruch",
            "witness": "ceriani1871",
            "page_count": 0,
            "pages": {},
        }
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def available_pages() -> list[int]:
    payload = _load_index()
    return sorted(int(key) for key in (payload.get("pages") or {}).keys())


def is_available() -> bool:
    return bool(available_pages())


def page_path(pdf_page: int) -> pathlib.Path:
    return PAGES_DIR / f"p{pdf_page:04d}.txt"


def load_page(pdf_page: int) -> SyriacPrimaryPage | None:
    payload = _load_index()
    meta = (payload.get("pages") or {}).get(f"{pdf_page:04d}")
    path = page_path(pdf_page)
    if meta is None or not path.exists():
        return None

    running_head_raw = str(meta.get("running_head_raw") or "")
    printed_page = meta.get("source_printed_page")
    body_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if line.strip():
            body_lines.append(line.rstrip())

    return SyriacPrimaryPage(
        pdf_page=pdf_page,
        printed_page=int(printed_page) if isinstance(printed_page, int) else None,
        text="\n".join(body_lines).strip(),
        running_head_raw=running_head_raw,
    )


def iter_pages() -> list[SyriacPrimaryPage]:
    return [page for pdf_page in available_pages() if (page := load_page(pdf_page)) is not None]


def summary() -> dict:
    payload = _load_index()
    return {
        "pipeline": "2baruch_syriac_primary",
        "status": "page_corpus_available" if is_available() else "pending",
        "page_count": len(available_pages()),
        "pages": available_pages(),
        "index_path": str(INDEX_PATH),
        "source": payload.get("source"),
        "validation": payload.get("validation"),
    }


if __name__ == "__main__":
    import argparse
    import pprint

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--page", type=int)
    args = p.parse_args()

    if args.page is not None:
        pprint.pp(load_page(args.page))
    else:
        pprint.pp(summary())
