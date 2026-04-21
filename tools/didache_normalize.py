#!/usr/bin/env python3
"""didache_normalize.py — normalize Didache raw OCR into chapter files."""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "sources" / "didache" / "transcribed" / "raw"
OUT_DIR = REPO_ROOT / "sources" / "didache" / "transcribed"

BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:RUNNING HEAD|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)
LEADING_NUMBERS_RE = re.compile(r"^(?:\d+\s*)+")
CHAPTER_RE = re.compile(r"^Κεφ\.\s*([^\s]+)\s*(.*)$")

GREEK_NUMERAL_MAP = {
    "α": 1,
    "β": 2,
    "γ": 3,
    "δ": 4,
    "ε": 5,
    "ς": 6,
    "ϛ": 6,
    "ζ": 7,
    "η": 8,
    "θ": 9,
    "ι": 10,
    "ια": 11,
    "ιβ": 12,
    "ιγ": 13,
    "ιδ": 14,
    "ιε": 15,
    "ις": 16,
    "ιϛ": 16,
}


@dataclass
class ChapterBuffer:
    chapter: int
    source_pages: set[int]
    lines: list[str]


def raw_page_paths() -> list[pathlib.Path]:
    return sorted(RAW_DIR.glob("didache_hb1884_p*.txt"))


def extract_body(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = BODY_RE.search(text)
    return m.group(1).strip() if m else ""


def page_num_from_path(path: pathlib.Path) -> int:
    m = re.search(r"_p(\d{4})\.txt$", path.name)
    if not m:
        raise ValueError(f"unexpected raw page filename: {path.name}")
    return int(m.group(1))


def clean_body_lines(body: str) -> list[str]:
    out: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = LEADING_NUMBERS_RE.sub("", line).strip()
        if not line:
            continue
        out.append(line)
    return out


def normalize_greek_numeral_token(token: str) -> str:
    token = token.replace("Ϛ", "ϛ").replace("Σ", "ς")
    token = (
        token.replace(".", "")
        .replace("'", "")
        .replace("’", "")
        .replace("΄", "")
        .replace("᾽", "")
        .replace("ʹ", "")
        .replace("ʼ", "")
        .replace("ʹ", "")
    )
    token = unicodedata.normalize("NFD", token)
    token = "".join(ch for ch in token if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", token)


def normalize_join(lines: list[str]) -> str:
    if not lines:
        return ""
    out = lines[0].strip()
    for line in lines[1:]:
        nxt = line.strip()
        if not nxt:
            continue
        if out.endswith("-"):
            out = out[:-1] + nxt
        else:
            out += " " + nxt
    return re.sub(r"\s+", " ", out).strip()


def build_chapters() -> dict[int, ChapterBuffer]:
    chapters: dict[int, ChapterBuffer] = {}
    current: ChapterBuffer | None = None

    for path in raw_page_paths():
        scan_page = page_num_from_path(path)
        for line in clean_body_lines(extract_body(path)):
            m = CHAPTER_RE.match(line)
            if m:
                numeral = normalize_greek_numeral_token(m.group(1))
                chapter = GREEK_NUMERAL_MAP.get(numeral)
                if chapter is None:
                    raise ValueError(f"unknown Didache chapter numeral {numeral!r} in {path.name}: {line!r}")
                current = chapters.setdefault(chapter, ChapterBuffer(chapter=chapter, source_pages=set(), lines=[]))
                current.source_pages.add(scan_page)
                rest = m.group(2).strip()
                if rest:
                    current.lines.append(rest)
                continue

            if current is None:
                # Skip the title block before chapter 1.
                continue

            current.source_pages.add(scan_page)
            current.lines.append(line)

    return chapters


def write_outputs(chapters: dict[int, ChapterBuffer]) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chapter_map: dict[str, dict[str, object]] = {}

    for chapter in sorted(chapters):
        buf = chapters[chapter]
        text = normalize_join(buf.lines)
        out_path = OUT_DIR / f"ch{chapter:02d}.txt"
        out_path.write_text(
            "\n".join(
                [
                    f"# Didache chapter {chapter}",
                    f"# source_pages: {','.join(str(p) for p in sorted(buf.source_pages))}",
                    text,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        chapter_map[f"{chapter:02d}"] = {
            "chapter": chapter,
            "source_pages": sorted(buf.source_pages),
            "chars": len(text),
            "path": str(out_path.relative_to(REPO_ROOT)),
        }

    payload = {
        "book": "Didache",
        "source": "Hitchcock & Brown 1884 raw OCR normalization",
        "chapter_count": len(chapter_map),
        "chapters": chapter_map,
    }
    (OUT_DIR / "chapter_map.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    payload = write_outputs(build_chapters())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
