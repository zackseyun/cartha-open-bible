#!/usr/bin/env python3
"""build_corpus.py — bridge 2 Baruch raw OCR into a stable Syriac corpus layer.

Current scope: Ceriani 1871 primary Syriac witness pages that already live under
`sources/2baruch/raw_ocr/ceriani1871/`.

This script turns the region-assembled OCR pages into a committed intermediate
corpus layer that later chapter/verse alignment can build on:

- cleaned page-level Syriac transcriptions in logical reading order
- per-page JSON sidecars with provenance + column metadata
- a page index JSON
- a JSONL working corpus

Why page-level first instead of chapter-level immediately?

Because the OCR work now committed is only a sparse calibration set (5 pages), not a
full continuous sweep. The right bridge is therefore *OCR -> stable page corpus*, not
pretending we already have a fully chapter-aligned Syriac text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO_ROOT / "sources" / "2baruch" / "raw_ocr" / "ceriani1871"
TRANSCRIBED_ROOT = REPO_ROOT / "sources" / "2baruch" / "syriac" / "transcribed" / "ceriani1871"
PAGES_OUT_DIR = TRANSCRIBED_ROOT / "pages"
INDEX_PATH = TRANSCRIBED_ROOT / "page_index.json"
CORPUS_OUT = REPO_ROOT / "sources" / "2baruch" / "syriac" / "corpus" / "CERIANI_WORKING.jsonl"

SECTION_HEADER_RE = re.compile(r"^\[(RUNNING HEAD|SYRIAC COLUMN 1|SYRIAC COLUMN 2|LATIN APPARATUS|MARGINALIA|BLANK)\]\s*$")
TXT_NAME_RE = re.compile(r"ceriani1871_p(\d{4})\.txt$")
PRINTED_PAGE_RE = re.compile(r"(\d{2,3})")
MULTISPACE_RE = re.compile(r"\s+")

SOURCE_EDITION = "Ceriani 1871 primary Syriac edition (raw OCR bridged into working corpus)"
VALIDATION_LABEL = "2baruch_ceriani_ocr_bridge_v1"


@dataclass(frozen=True)
class CerianiPage:
    pdf_page: int
    running_head_raw: str
    printed_page: int | None
    physical_left_lines: list[str]
    physical_right_lines: list[str]
    reading_order_lines: list[str]
    apparatus_lines: list[str]
    raw_ocr_path: str
    raw_meta_path: str | None
    raw_ocr_sha256: str
    provenance_url: str | None
    model: str | None


def display_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def raw_page_paths() -> list[pathlib.Path]:
    return sorted(RAW_DIR.glob("ceriani1871_p*.txt"))


def pdf_page_from_path(path: pathlib.Path) -> int:
    m = TXT_NAME_RE.search(path.name)
    if not m:
        raise ValueError(f"unexpected Ceriani OCR filename: {path.name}")
    return int(m.group(1))


def normalize_block(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "[BLANK]":
            continue
        lines.append(line)
    return lines


def join_lines(lines: Iterable[str]) -> str:
    return "\n".join(line.rstrip() for line in lines if str(line).strip())


def join_lines_inline(lines: Iterable[str]) -> str:
    return MULTISPACE_RE.sub(" ", " ".join(line.strip() for line in lines if str(line).strip())).strip()


def parse_structured_sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---2BARUCH-CERIANI-PAGE---":
        raise ValueError("raw OCR page does not start with ---2BARUCH-CERIANI-PAGE---")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in lines[1:]:
        line = raw_line.rstrip("\n")
        if line.strip() == "---END-PAGE---":
            break
        m = SECTION_HEADER_RE.match(line.strip())
        if m:
            current = m.group(1)
            sections.setdefault(current, [])
            continue
        if current is None:
            continue
        sections.setdefault(current, []).append(line)
    return {name: "\n".join(body).strip() for name, body in sections.items()}


def printed_page_from_running_head(running_head_raw: str) -> int | None:
    m = PRINTED_PAGE_RE.search(running_head_raw or "")
    return int(m.group(1)) if m else None


def load_meta(path: pathlib.Path) -> dict[str, Any] | None:
    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def parse_raw_page(path: pathlib.Path) -> CerianiPage:
    raw_text = path.read_text(encoding="utf-8")
    sections = parse_structured_sections(raw_text)
    meta = load_meta(path)

    running_head_raw = sections.get("RUNNING HEAD", "").strip()
    physical_left_lines = normalize_block(sections.get("SYRIAC COLUMN 1", ""))
    physical_right_lines = normalize_block(sections.get("SYRIAC COLUMN 2", ""))
    apparatus_lines = normalize_block(sections.get("LATIN APPARATUS", ""))

    # Ceriani's Syriac pages are right-to-left; the physical right column is read first.
    reading_order_lines = [*physical_right_lines, *physical_left_lines]

    return CerianiPage(
        pdf_page=pdf_page_from_path(path),
        running_head_raw=running_head_raw,
        printed_page=printed_page_from_running_head(running_head_raw),
        physical_left_lines=physical_left_lines,
        physical_right_lines=physical_right_lines,
        reading_order_lines=reading_order_lines,
        apparatus_lines=apparatus_lines,
        raw_ocr_path=display_path(path),
        raw_meta_path=display_path(path.with_suffix(".meta.json")) if path.with_suffix(".meta.json").exists() else None,
        raw_ocr_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        provenance_url=(meta or {}).get("provenance_url"),
        model=(meta or {}).get("model"),
    )


def build_record(page: CerianiPage) -> dict[str, Any]:
    reading_text = join_lines(page.reading_order_lines)
    return {
        "book": "2BAR",
        "book_title": "2 Baruch",
        "kind": "page",
        "witness": "ceriani1871",
        "source_edition": SOURCE_EDITION,
        "source_pdf_page": page.pdf_page,
        "source_printed_page": page.printed_page,
        "running_head_raw": page.running_head_raw,
        "reading_order": "physical_right_then_left",
        "syriac": reading_text,
        "syriac_inline": join_lines_inline(page.reading_order_lines),
        "syriac_lines": page.reading_order_lines,
        "physical_right_lines": page.physical_right_lines,
        "physical_left_lines": page.physical_left_lines,
        "latin_apparatus": join_lines(page.apparatus_lines),
        "latin_apparatus_lines": page.apparatus_lines,
        "raw_ocr_path": page.raw_ocr_path,
        "raw_meta_path": page.raw_meta_path,
        "raw_ocr_sha256": page.raw_ocr_sha256,
        "provenance_url": page.provenance_url,
        "model": page.model,
        "validation": VALIDATION_LABEL,
    }


def write_page_text(page: CerianiPage) -> pathlib.Path:
    out_path = PAGES_OUT_DIR / f"p{page.pdf_page:04d}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            [
                f"# 2 Baruch Ceriani 1871 page {page.pdf_page}",
                f"# printed_page: {page.printed_page if page.printed_page is not None else 'unknown'}",
                "# reading_order: physical_right_then_left",
                f"# running_head: {page.running_head_raw or '[BLANK]'}",
                f"# raw_ocr_path: {page.raw_ocr_path}",
                (f"# provenance_url: {page.provenance_url}" if page.provenance_url else "# provenance_url: unknown"),
                join_lines(page.reading_order_lines),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out_path


def write_page_json(page: CerianiPage) -> pathlib.Path:
    out_path = PAGES_OUT_DIR / f"p{page.pdf_page:04d}.json"
    payload = build_record(page)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def write_index(pages: list[CerianiPage]) -> dict[str, Any]:
    payload = {
        "book": "2 Baruch",
        "witness": "ceriani1871",
        "source": SOURCE_EDITION,
        "validation": VALIDATION_LABEL,
        "page_count": len(pages),
        "pages": {
            f"{page.pdf_page:04d}": {
                "source_pdf_page": page.pdf_page,
                "source_printed_page": page.printed_page,
                "running_head_raw": page.running_head_raw,
                "reading_order": "physical_right_then_left",
                "syriac_line_count": len(page.reading_order_lines),
                "apparatus_line_count": len(page.apparatus_lines),
                "text_path": display_path(PAGES_OUT_DIR / f"p{page.pdf_page:04d}.txt"),
                "json_path": display_path(PAGES_OUT_DIR / f"p{page.pdf_page:04d}.json"),
                "raw_ocr_path": page.raw_ocr_path,
                "raw_meta_path": page.raw_meta_path,
                "model": page.model,
            }
            for page in pages
        },
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def write_corpus(records: list[dict[str, Any]], out_path: pathlib.Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=CORPUS_OUT)
    args = ap.parse_args()

    pages = [parse_raw_page(path) for path in raw_page_paths()]
    if not pages:
        raise SystemExit(f"No Ceriani OCR pages found in {display_path(RAW_DIR)}")

    for page in pages:
        write_page_text(page)
        write_page_json(page)

    records = [build_record(page) for page in pages]
    write_corpus(records, args.out)
    index = write_index(pages)

    printed_pages_known = [page.printed_page for page in pages if page.printed_page is not None]
    print(f"wrote {display_path(args.out)}")
    print(f"pages bridged: {len(pages)}")
    print(f"pdf pages: {', '.join(str(page.pdf_page) for page in pages)}")
    if printed_pages_known:
        print(f"printed pages recovered: {', '.join(str(n) for n in printed_pages_known)}")
    else:
        print("printed pages recovered: none")
    print(f"page index: {display_path(INDEX_PATH)}")
    print(f"page text dir: {display_path(PAGES_OUT_DIR)}")
    print(f"index entries: {index['page_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
