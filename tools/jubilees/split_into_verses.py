#!/usr/bin/env python3
"""split_into_verses.py — derive per-verse Jubilees YAMLs from chapter YAMLs.

Also normalizes chapter translation text when it was accidentally stored as a
stringified Python/JSON list of verse strings.
"""
from __future__ import annotations

import ast
import pathlib
import re
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BOOK_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "jubilees"
BOOK_CODE = "JUB"
BOOK_NAME = "Jubilees"
VERSE_RE = re.compile(r"(?m)^\s*(\d+)\.\s+")


def normalize_chapter_text(text: str) -> str:
    raw = text.strip()
    if raw.startswith("[") and raw.endswith("]"):
        try:
            data = ast.literal_eval(raw)
            if isinstance(data, list) and all(isinstance(x, str) for x in data):
                return "\n".join(x.strip() for x in data if x.strip())
        except Exception:
            pass
    return raw


def parse_verses(text: str) -> dict[int, str]:
    text = normalize_chapter_text(text)
    matches = list(VERSE_RE.finditer(text))
    out: dict[int, str] = {}
    for i, m in enumerate(matches):
        verse = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[verse] = text[start:end].strip()
    return out


def marker_matches(marker: Any, chapter: int, verse: int) -> bool:
    s = str(marker)
    return s == str(verse) or s == f"{chapter}:{verse}"


def split_chapter(path: pathlib.Path) -> int:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    chapter = int(path.stem)

    source_rows = {
        int(row["verse"]): row
        for row in (doc.get("source", {}).get("rows") or [])
        if isinstance(row, dict) and int(row.get("verse", 0)) >= 1
    }
    translation_text = normalize_chapter_text(str((doc.get("translation") or {}).get("text", "") or ""))
    translation_verses = parse_verses(translation_text)
    if not translation_verses:
        raise ValueError(f"{path}: no verse markers found in translation text")

    # Normalize chapter YAML text too so the flat file stops carrying serialized lists.
    doc["translation"]["text"] = translation_text
    path.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    out_dir = BOOK_ROOT / f"{chapter:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    footnotes = (doc.get("translation") or {}).get("footnotes", []) or []
    written = 0
    for verse_num in sorted(translation_verses):
        source_row = source_rows.get(verse_num, {})
        verse_footnotes = [fn for fn in footnotes if marker_matches(fn.get("marker"), chapter, verse_num)]
        record: dict[str, Any] = {
            "id": f"{BOOK_CODE}.{chapter}.{verse_num}",
            "reference": f"{BOOK_NAME} {chapter}:{verse_num}",
            "unit": "verse",
            "book": BOOK_NAME,
            "source": {
                "edition": doc["source"].get("edition"),
                "language": doc["source"].get("language"),
                "text": source_row.get("geez", ""),
                "pages": doc["source"].get("pages", []),
                "validation_modes": doc["source"].get("validation_modes", []),
            },
            "translation": {
                "text": translation_verses[verse_num],
                "philosophy": (doc.get("translation") or {}).get("philosophy"),
            },
            "note": (
                f"Derived mechanically from the chapter-level reviewed draft at "
                f"translation/extra_canonical/jubilees/{chapter:03d}.yaml "
                f"by tools/jubilees/split_into_verses.py. The chapter-level YAML remains "
                f"the authoritative draft/review record; these verse YAMLs exist for reader surfaces "
                f"and per-verse linking."
            ),
            "ai_draft_provenance": doc.get("ai_draft", {}),
            "ai_draft_chapter_review_passes": doc.get("review_passes", []),
        }
        if verse_footnotes:
            record["translation"]["footnotes"] = verse_footnotes
        out_path = out_dir / f"{verse_num:03d}.yaml"
        out_path.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
        written += 1
    return written


def main() -> int:
    total = 0
    for path in sorted(BOOK_ROOT.glob("[0-9][0-9][0-9].yaml")):
        written = split_chapter(path)
        total += written
        print(f"wrote {path.stem}: {written} verses ({total} cumulative)", flush=True)
    print(f"total verses written: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
