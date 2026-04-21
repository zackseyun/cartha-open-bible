#!/usr/bin/env python3
"""extract_bensly_body.py — strip BODY sections from Bensly raw OCR.

Input:
  sources/2esdras/raw_ocr/bensly1895/bensly1895_pNNNN.txt
  sources/2esdras/raw_ocr/bensly1875/bensly1875_pNNNN.txt

Output:
  sources/2esdras/latin/intermediate/bensly1895_body_pages/pNNNN.txt
  sources/2esdras/latin/intermediate/bensly1895_body_main_text.txt
  sources/2esdras/latin/intermediate/bensly1875_body_pages/pNNNN.txt
  sources/2esdras/latin/intermediate/bensly1875_body_main_text.txt

This is the bridge between:
  1. page-level OCR dumps with apparatus and headers, and
  2. the later cleaned chapter files consumed by latin_bensly.py

It does *not* attempt final verse segmentation. It simply extracts the
main body text page by page and concatenates it into one cleaner Latin
working text for the human / script cleanup pass.
"""
from __future__ import annotations

import argparse
import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LATIN_INTERMEDIATE = REPO_ROOT / "sources" / "2esdras" / "latin" / "intermediate"
SOURCE_CONFIG = {
    "bensly1895": {
        "raw_dir": REPO_ROOT / "sources" / "2esdras" / "raw_ocr" / "bensly1895",
        "out_dir": LATIN_INTERMEDIATE / "bensly1895_body_pages",
        "combined_path": LATIN_INTERMEDIATE / "bensly1895_body_main_text.txt",
        "page_re": re.compile(r"bensly1895_p(\d{4})\.txt$"),
    },
    "bensly1875": {
        "raw_dir": REPO_ROOT / "sources" / "2esdras" / "raw_ocr" / "bensly1875",
        "out_dir": LATIN_INTERMEDIATE / "bensly1875_body_pages",
        "combined_path": LATIN_INTERMEDIATE / "bensly1875_body_main_text.txt",
        "page_re": re.compile(r"bensly1875_p(\d{4})\.txt$"),
    },
}


def extract_body(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_body = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[BODY]":
            in_body = True
            continue
        if stripped.startswith("[") and stripped.endswith("]") and stripped != "[BODY]":
            if in_body:
                break
        if in_body:
            out.append(line.rstrip())
    return "\n".join(out).strip()


def iter_raw_pages(raw_dir: pathlib.Path, page_re: re.Pattern[str]) -> list[tuple[int, pathlib.Path]]:
    items: list[tuple[int, pathlib.Path]] = []
    if not raw_dir.exists():
        return items
    for path in sorted(raw_dir.glob("*.txt")):
        m = page_re.fullmatch(path.name)
        if not m:
            continue
        items.append((int(m.group(1)), path))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="bensly1895",
        choices=sorted(SOURCE_CONFIG),
        help="Which Bensly OCR source to process (default: bensly1895)",
    )
    args = parser.parse_args()

    cfg = SOURCE_CONFIG[args.source]
    raw_dir = cfg["raw_dir"]
    out_dir = cfg["out_dir"]
    combined_path = cfg["combined_path"]
    page_re = cfg["page_re"]

    pages = iter_raw_pages(raw_dir, page_re)
    if not pages:
        print(f"no raw OCR pages found in {raw_dir}")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    combined_path.parent.mkdir(parents=True, exist_ok=True)

    combined_chunks: list[str] = []
    count = 0
    for page_num, path in pages:
        body = extract_body(path.read_text(encoding="utf-8"))
        if not body:
            print(f"warning: no [BODY] section found in {path.name}")
            continue
        out_path = out_dir / f"p{page_num:04d}.txt"
        out_path.write_text(body + "\n", encoding="utf-8")
        combined_chunks.append(f"=== PAGE {page_num} ===\n{body}")
        count += 1

    combined_path.write_text("\n\n".join(combined_chunks) + "\n", encoding="utf-8")
    print(f"wrote {count} page body files to {out_dir}")
    print(f"wrote combined body text to {combined_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
