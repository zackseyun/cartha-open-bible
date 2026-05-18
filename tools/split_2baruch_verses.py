#!/usr/bin/env python3
"""split_2baruch_verses.py

Replace the synthetic single-verse mirror files in 2_baruch/ with proper
per-verse YAML files, one file per verse number found in the chapter text.

The chapter-level flat YAMLs (2_baruch/NNN.yaml) and their current
single-verse mirrors (2_baruch/NNN/001.yaml) have inline verse numbers like:
    1 verse one text
    2 verse two text
This script splits them into 2_baruch/NNN/001.yaml, 002.yaml, etc.

The *mirror* file (NNN/001.yaml) is used as source because revision passes
may have already improved its wording relative to the flat NNN.yaml.

Usage:
  python3 tools/split_2baruch_verses.py --dry-run
  python3 tools/split_2baruch_verses.py
  python3 tools/split_2baruch_verses.py --chapter 1   # single chapter
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from copy import deepcopy

from ruamel.yaml import YAML

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EC_ROOT = REPO_ROOT / "translation" / "extra_canonical"

# Books that may need verse splitting.  Add entries here as new books are drafted.
BOOK_CONFIGS: dict[str, tuple[str, str, int]] = {
    "2_baruch":  ("2 Baruch",  "2BA",   87),
    "1_clement": ("1 Clement", "1CLEM", 65),
}

# Legacy single-book defaults (kept for backwards compat with --chapter flag)
BOOK_DIR = EC_ROOT / "2_baruch"
BOOK_NAME = "2 Baruch"
BOOK_CODE = "2BA"

_VERSE_BOUNDARY = re.compile(r"(?:^|\n+)(\d+)\.?\s+", re.MULTILINE)

_JSON_ENGLISH = re.compile(
    r'"english_text"\s*:\s*"(.*?)(?:"\s*,\s*"(?:translation_philosophy|lexical|notes|'
    r'source|theological))',
    re.DOTALL,
)


def _extract_from_corrupt_json(text: str) -> str | None:
    """Extract english_text from a truncated submit_2baruch_chapter_draft JSON blob."""
    m = _JSON_ENGLISH.search(text)
    if not m:
        return None
    raw = m.group(1)
    # Unescape JSON string escapes
    raw = raw.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
    return raw.strip()


def split_text(text: str, chapter: int = 0) -> list[tuple[int, str]]:
    """Return list of (verse_num, verse_text) by splitting on inline verse numbers."""
    # Handle corrupted JSON drafts first
    if "submit_2baruch_chapter_draft" in text or '"english_text"' in text:
        extracted = _extract_from_corrupt_json(text)
        if extracted:
            text = extracted
    text = text.strip()

    # Strip leading chapter-number header (e.g. "54 The Prayer of Baruch…")
    # — the drafter sometimes emits the chapter number as a label, not a verse number.
    if chapter:
        leading = re.match(rf"^{chapter}\.?\s+", text)
        if leading:
            text = text[leading.end():].strip()

    matches = list(_VERSE_BOUNDARY.finditer(text))
    if not matches:
        return [(1, text)]

    # If text starts before the first verse-number marker, that's verse 1.
    verse_dict: dict[int, str] = {}
    if matches[0].start() > 0:
        verse_dict[1] = text[: matches[0].start()].strip()

    # Build a dict so duplicate verse numbers are resolved with "last wins".
    # Some chapters have duplicate drafts; the final occurrence is authoritative.
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        verse_dict[int(m.group(1))] = text[start:end].strip()

    return sorted(verse_dict.items())


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n+", text.strip()) if part.strip()]


def _split_with_flat_numbered_fallback(
    text: str,
    chapter: int,
    book_dir: pathlib.Path,
) -> list[tuple[int, str]]:
    """Split a mirror text, falling back to the flat chapter's numbering.

    A few reader-facing mirror files were later revised after the inline verse
    numerals were removed. If the mirror is now plain paragraphs, but the flat
    chapter YAML still carries the standard numbered divisions and the paragraph
    count matches that numbered split, keep the revised mirror wording and attach
    those paragraphs to the flat chapter's verse numbers.
    """
    verses = split_text(text, chapter=chapter)
    if len(verses) != 1:
        return verses

    flat_path = book_dir / f"{chapter:03d}.yaml"
    if not flat_path.exists():
        return verses

    yaml_safe = YAML(typ="safe")
    try:
        flat_record = yaml_safe.load(flat_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return verses

    flat_text = ((flat_record.get("translation") or {}).get("text") or "").strip()
    flat_verses = split_text(flat_text, chapter=chapter)
    mirror_paragraphs = _paragraphs(text)

    if len(flat_verses) > 1 and len(flat_verses) == len(mirror_paragraphs):
        return [
            (verse_num, mirror_paragraphs[i])
            for i, (verse_num, _flat_text) in enumerate(flat_verses)
        ]

    return verses


def build_verse_record(
    chapter: int,
    verse_num: int,
    verse_text: str,
    source_record: dict,
    is_first: bool,
    book_name: str,
    book_code: str,
) -> dict:
    src = deepcopy(source_record.get("source") or {})
    src["verse"] = verse_num
    src.pop("verse_count", None)
    if not is_first:
        src.pop("text", None)
        src.pop("note", None)

    rec: dict = {
        "id": f"{book_code}.{chapter}.{verse_num}",
        "reference": f"{book_name} {chapter}:{verse_num}",
        "unit": "verse",
        "book": book_name,
        "source": src,
        "translation": {
            "text": verse_text,
            "philosophy": (source_record.get("translation") or {}).get("philosophy"),
        },
        "status": source_record.get("status", "ai_draft"),
    }

    if is_first:
        for key in ("lexical_decisions", "theological_decisions", "footnotes",
                    "ai_draft", "ai_draft_provenance", "revision_pass", "revisions"):
            if key in source_record:
                rec[key] = source_record[key]

    return rec


def process_chapter(
    ch: int, dry_run: bool, yaml_rt: YAML,
    book_dir: pathlib.Path | None = None,
    book_name: str = BOOK_NAME,
    book_code: str = BOOK_CODE,
) -> int:
    """Return number of verse files written (0 if chapter already split or skipped)."""
    if book_dir is None:
        book_dir = BOOK_DIR
    chapter_dir = book_dir / f"{ch:03d}"
    mirror_path = chapter_dir / "001.yaml"
    if not mirror_path.exists():
        return 0

    raw = mirror_path.read_text(encoding="utf-8")
    record = yaml_rt.load(raw)
    if not isinstance(record, dict):
        return 0

    text = (record.get("translation") or {}).get("text") or ""

    # Skip chapters that have already been split into multiple verses, but do
    # not trust the absence of the old synthetic-note alone. Later revision
    # passes can overwrite 001.yaml with a full numbered chapter while leaving
    # 002.yaml+ in place; in that case the reader duplicates the chapter head.
    note = str(record.get("note") or "")
    existing_verse_files = [f for f in chapter_dir.glob("*.yaml")]
    verses = _split_with_flat_numbered_fallback(text.strip(), chapter=ch, book_dir=book_dir)
    if (
        "Synthetic single-verse mirror" not in note
        and len(existing_verse_files) > 1
        and len(verses) <= 1
    ):
        return 0

    if dry_run:
        print(f"  ch{ch:03d}: {len(verses)} verses → " +
              ", ".join(f"v{v}" for v, _ in verses))
        return len(verses)

    # Write per-verse files
    written_paths = set()
    for i, (vnum, vtext) in enumerate(verses):
        rec = build_verse_record(ch, vnum, vtext, record, is_first=(i == 0),
                                 book_name=book_name, book_code=book_code)
        out_path = chapter_dir / f"{vnum:03d}.yaml"
        with out_path.open("w", encoding="utf-8") as fh:
            yaml_rt.dump(rec, fh)
        written_paths.add(out_path)

    # If the split didn't produce a 001.yaml (e.g. chapter starts at v7),
    # remove the stale synthetic mirror.
    old_mirror = chapter_dir / "001.yaml"
    if old_mirror not in written_paths and old_mirror.exists():
        old_mirror.unlink()

    return len(verses)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chapter", type=int, default=None)
    args = ap.parse_args()

    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.width = 4096

    total_split = already_done = 0

    if args.chapter:
        # Legacy: single-chapter mode defaults to 2 Baruch
        n = process_chapter(args.chapter, dry_run=args.dry_run, yaml_rt=yaml_rt)
        total_split += int(n > 1)
        already_done += int(n == 1)
    else:
        for slug, (bname, bcode, max_ch) in BOOK_CONFIGS.items():
            bdir = EC_ROOT / slug
            print(f"\n{bname} ({slug}):")
            for ch in range(1, max_ch + 1):
                n = process_chapter(ch, dry_run=args.dry_run, yaml_rt=yaml_rt,
                                    book_dir=bdir, book_name=bname, book_code=bcode)
                if n > 1:
                    total_split += 1
                elif n == 1:
                    already_done += 1

    label = "would split" if args.dry_run else "split"
    print(f"\n{label}: {total_split} chapters (multi-verse); {already_done} single-verse (cleaned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
