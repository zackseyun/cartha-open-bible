#!/usr/bin/env python3
"""export_extra_canonical_chapter_books.py — export chapter-based extra-canonical books.

This is a publishing/export companion for Group A chapter-based works
such as Didache and 1 Clement. It intentionally does *not* force them
into verse-shaped mobile JSON; instead it exports chapter-level JSON
artifacts suitable for apps, websites, and downstream publishing.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical"

BOOKS: dict[str, dict[str, str]] = {
    "didache": {
        "id": "DID",
        "name": "Didache",
        "slug": "didache",
    },
    "1_clement": {
        "id": "1CLEM",
        "name": "1 Clement",
        "slug": "1_clement",
    },
}


def load_book(slug: str) -> dict[str, Any] | None:
    meta = BOOKS[slug]
    book_dir = TRANSLATION_ROOT / slug
    if not book_dir.exists():
        return None

    chapters_out: list[dict[str, Any]] = []
    for path in sorted(book_dir.glob("*.yaml")):
        try:
            chapter_num = int(path.stem)
        except ValueError:
            continue
        record = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        text = str(((record.get("translation") or {}).get("text", "")) or "").strip()
        if not text:
            continue
        chapters_out.append(
            {
                "chapter": chapter_num,
                "reference": record.get("reference", f"{meta['name']} {chapter_num}"),
                "text": text,
                "philosophy": ((record.get("translation") or {}).get("philosophy", "")),
                "source_pages": ((record.get("source") or {}).get("pages", [])),
                "footnotes": ((record.get("translation") or {}).get("footnotes", [])),
            }
        )

    if not chapters_out:
        return None

    return {
        "id": meta["id"],
        "name": meta["name"],
        "slug": meta["slug"],
        "unit": "chapter",
        "chapters": chapters_out,
    }


def build_payload(slugs: list[str]) -> dict[str, Any]:
    books: list[dict[str, Any]] = []
    for slug in slugs:
        loaded = load_book(slug)
        if loaded is not None:
            books.append(loaded)
    return {
        "translation": "COB: Cartha Open Bible (Preview)",
        "collection": "extra_canonical",
        "books": books,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--books",
        default="didache,1_clement",
        help="Comma-separated slugs from: " + ", ".join(sorted(BOOKS)),
    )
    parser.add_argument("--output", required=True, help="Where to write the JSON artifact")
    args = parser.parse_args()

    slugs = [s.strip() for s in args.books.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in BOOKS]
    if unknown:
        raise SystemExit(f"Unknown extra-canonical book slug(s): {unknown}")

    payload = build_payload(slugs)
    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
