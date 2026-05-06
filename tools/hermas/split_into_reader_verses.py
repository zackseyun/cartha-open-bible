#!/usr/bin/env python3
"""Derive reader verse YAMLs for Shepherd of Hermas.

Hermas is drafted as 63 section-level YAML files:

    translation/extra_canonical/shepherd_of_hermas/NNN.yaml

That flat layout is the authoritative translation/review record, but the
website/mobile reader consumes a chapter ``verses`` array. Without nested
reader records, the CDN publisher emits every Hermas section as a single
synthetic verse, which makes long sections render as one huge row.

This script creates deterministic, reader-facing paragraph segments at:

    translation/extra_canonical/shepherd_of_hermas/NNN/VVV.yaml

The flat source files stay in place. The CDN publisher already prefers nested
per-verse files over flat records for the same book, so these derived files are
the non-destructive way to improve the reader while preserving provenance.
"""
from __future__ import annotations

import argparse
import pathlib
import re
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HERMAS_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "shepherd_of_hermas"

# Footnote markers in the chapter drafts were generated inline as [1], [a],
# etc. The website strips markers only when matching footnote metadata ships in
# the CDN payload, but several Hermas drafts have orphaned markers with no
# matching footnote object. Strip marker-looking tokens from the derived reader
# prose while keeping bracketed supplied words such as [God], [all], [rods].
INLINE_MARKER_RE = re.compile(r"[ \t]?\[\[?([A-Za-z0-9]{1,8})\]\]?")


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n+", text or "") if p.strip()]


def strip_inline_note_markers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.isdigit() or re.fullmatch(r"[A-Za-z]", token):
            return ""
        return match.group(0)

    cleaned = INLINE_MARKER_RE.sub(repl, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s+([’'])", r"\1", cleaned)
    return cleaned.strip()


def derived_record(parent: dict[str, Any], chapter: int, verse: int, text: str) -> dict[str, Any]:
    source = parent.get("source") or {}
    translation = parent.get("translation") or {}
    parent_id = str(parent.get("id") or f"HERM.{chapter}")
    parent_ref = str(parent.get("reference") or f"Shepherd of Hermas {chapter}")

    return {
        "id": f"{parent_id}.{verse}",
        "reference": f"Shepherd of Hermas {chapter}:{verse}",
        "unit": "verse",
        "book": "Shepherd of Hermas",
        "source": {
            "edition": source.get("edition"),
            "language": source.get("language") or "Greek",
            "pages": source.get("pages") or [],
            "unit_id": source.get("unit_id"),
            "label": source.get("label"),
            "sequence": source.get("sequence"),
            "parent_id": parent_id,
            "parent_reference": parent_ref,
            "reader_segment": verse,
            "reader_split": "paragraph",
        },
        "translation": {
            "text": text,
            "philosophy": translation.get("philosophy"),
        },
        "note": (
            "Derived from the section-level Shepherd of Hermas draft at "
            f"translation/extra_canonical/shepherd_of_hermas/{chapter:03d}.yaml "
            "by tools/hermas/split_into_reader_verses.py. The flat YAML remains "
            "the authoritative translation/review record; these nested files exist "
            "for clean mobile/web reader segmentation."
        ),
        "ai_draft_provenance": parent.get("ai_draft") or {},
    }


def split_file(path: pathlib.Path, *, dry_run: bool = False) -> tuple[int, int]:
    chapter = int(path.stem)
    parent = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    text = str(((parent.get("translation") or {}).get("text") or "")).strip()
    paragraphs = [strip_inline_note_markers(p) for p in split_paragraphs(text)]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return chapter, 0

    chapter_dir = path.parent / f"{chapter:03d}"
    if not dry_run:
        chapter_dir.mkdir(exist_ok=True)
        for stale in chapter_dir.glob("*.yaml"):
            stale.unlink()
        for idx, paragraph in enumerate(paragraphs, start=1):
            out_path = chapter_dir / f"{idx:03d}.yaml"
            out_path.write_text(
                yaml.safe_dump(
                    derived_record(parent, chapter, idx, paragraph),
                    allow_unicode=True,
                    sort_keys=False,
                    width=100,
                ),
                encoding="utf-8",
            )
    return chapter, len(paragraphs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = sorted(
        p for p in HERMAS_ROOT.glob("*.yaml")
        if p.is_file() and p.stem.isdigit()
    )
    total = 0
    for path in files:
        chapter, count = split_file(path, dry_run=args.dry_run)
        print(f"Hermas {chapter:03d}: {count} reader verses")
        total += count
    print(f"Shepherd of Hermas: {len(files)} sections, {total} reader verses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
