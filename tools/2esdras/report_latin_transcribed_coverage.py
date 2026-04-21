#!/usr/bin/env python3
"""report_latin_transcribed_coverage.py — summarize 2 Esdras Latin coverage.

Reads the canonical loader-path files under:

  sources/2esdras/latin/transcribed/chNN.txt

and emits:

  - sources/2esdras/latin/transcribed/COVERAGE.json
  - sources/2esdras/latin/transcribed/COVERAGE.md

This gives the cleanup pass an honest, machine-readable view of what is
already loader-live and what still needs manual work.
"""
from __future__ import annotations

import json
import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"
JSON_PATH = TRANSCRIBED_DIR / "COVERAGE.json"
MD_PATH = TRANSCRIBED_DIR / "COVERAGE.md"

VERSE_LINE_RE = re.compile(r"(?m)^(\d+)\s")
OPENING_MISSING_RE = re.compile(r"^# Missing opening coverage before first explicit marker: verses (.+)$")
INTERNAL_MISSING_RE = re.compile(r"^# Missing explicit markers inside covered range: (.+)$")


def parse_missing_list(raw: str) -> list[int]:
    out: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(token))
    return out


def chapter_record(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header_lines = [ln for ln in text.splitlines() if ln.startswith("#")]
    verses = [int(m.group(1)) for m in VERSE_LINE_RE.finditer(text)]
    opening_missing: list[int] = []
    internal_missing: list[int] = []

    for line in header_lines:
        m = OPENING_MISSING_RE.match(line)
        if m:
            opening_missing = parse_missing_list(m.group(1))
            continue
        m = INTERNAL_MISSING_RE.match(line)
        if m:
            internal_missing = parse_missing_list(m.group(1))
            continue

    return {
        "chapter": int(path.stem[2:]),
        "path": str(path.relative_to(REPO_ROOT)),
        "verses_present": verses,
        "verse_count": len(verses),
        "first_present": verses[0] if verses else None,
        "last_present": verses[-1] if verses else None,
        "opening_missing": opening_missing,
        "internal_missing": internal_missing,
        "notes": header_lines,
    }


def build_records() -> list[dict]:
    records: list[dict] = []
    for path in sorted(TRANSCRIBED_DIR.glob("ch*.txt")):
        records.append(chapter_record(path))
    return records


def write_json(records: list[dict]) -> None:
    payload = {
        "pipeline": "2esdras_latin_transcribed_coverage",
        "chapter_count": len(records),
        "chapters": records,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(records: list[dict]) -> None:
    lines = [
        "# 2 Esdras Latin transcribed coverage",
        "",
        "Auto-generated from `sources/2esdras/latin/transcribed/chNN.txt`.",
        "",
        "| Chapter | Present verses | First | Last | Missing opening | Missing inside range |",
        "|---|---:|---:|---:|---|---|",
    ]
    for rec in records:
        opening = ", ".join(str(v) for v in rec["opening_missing"]) or "—"
        internal = ", ".join(str(v) for v in rec["internal_missing"]) or "—"
        lines.append(
            f"| {rec['chapter']} | {rec['verse_count']} | {rec['first_present'] or '—'} | "
            f"{rec['last_present'] or '—'} | {opening} | {internal} |"
        )

    lines.extend(["", "## Files", ""])
    for rec in records:
        lines.append(f"- Chapter {rec['chapter']}: `{rec['path']}`")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    TRANSCRIBED_DIR.mkdir(parents=True, exist_ok=True)
    records = build_records()
    write_json(records)
    write_md(records)
    print(f"wrote {JSON_PATH}")
    print(f"wrote {MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
