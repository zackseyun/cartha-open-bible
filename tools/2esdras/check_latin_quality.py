#!/usr/bin/env python3
"""check_latin_quality.py — quality report for 2 Esdras Latin transcribed files."""
from __future__ import annotations

import json
import pathlib
import re


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "2esdras" / "latin" / "transcribed"
JSON_PATH = TRANSCRIBED_DIR / "QUALITY_CHECK.json"
MD_PATH = TRANSCRIBED_DIR / "QUALITY_CHECK.md"

VERSE_LINE_RE = re.compile(r"(?m)^(\d+)\s(.*)$")
BLEED_RE = re.compile(r"[A-Za-zÀ-ÿ]\d+|\d+[A-Za-zÀ-ÿ]")
HYPHEN_BREAK_RE = re.compile(r"[A-Za-zÀ-ÿ]-\s+[A-Za-zÀ-ÿ]")
CROP_RE = re.compile(r"\[⋯[^\]]*\]")
ELLIPSIS_RE = re.compile(r"\.\s*\.\s*\.")
OPENING_MISSING_RE = re.compile(r"^# Missing opening coverage before first explicit marker: verses (.+)$")
INTERNAL_MISSING_RE = re.compile(r"^# Missing explicit markers inside covered range: (.+)$")


def parse_missing(raw: str) -> list[int]:
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


def chapter_metrics(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header_lines = [ln for ln in text.splitlines() if ln.startswith("#")]
    verse_lines = [(int(m.group(1)), m.group(2)) for m in VERSE_LINE_RE.finditer(text)]

    opening_missing: list[int] = []
    internal_missing: list[int] = []
    for line in header_lines:
        m = OPENING_MISSING_RE.match(line)
        if m:
            opening_missing = parse_missing(m.group(1))
            continue
        m = INTERNAL_MISSING_RE.match(line)
        if m:
            internal_missing = parse_missing(m.group(1))

    return {
        "chapter": int(path.stem[2:]),
        "path": str(path.relative_to(REPO_ROOT)),
        "verse_count": len(verse_lines),
        "empty_verses": [v for v, t in verse_lines if not t.strip()],
        "crop_markers": len(CROP_RE.findall(text)),
        "ellipsis_markers": len(ELLIPSIS_RE.findall(text)),
        "digit_bleed_artifacts": len(BLEED_RE.findall(text)),
        "hyphen_break_artifacts": len(HYPHEN_BREAK_RE.findall(text)),
        "opening_missing": opening_missing,
        "internal_missing": internal_missing,
    }


def main() -> int:
    records = [chapter_metrics(path) for path in sorted(TRANSCRIBED_DIR.glob("ch*.txt"))]
    payload = {"pipeline": "2esdras_latin_quality_check", "chapters": records}
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# 2 Esdras Latin quality check",
        "",
        "| Chapter | Verses | Missing opening | Missing inside | Empty verses | Crop markers | Ellipsis markers | Digit bleed | Hyphen breaks |",
        "|---|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for rec in records:
        lines.append(
            f"| {rec['chapter']} | {rec['verse_count']} | "
            f"{', '.join(map(str, rec['opening_missing'])) or '—'} | "
            f"{', '.join(map(str, rec['internal_missing'])) or '—'} | "
            f"{', '.join(map(str, rec['empty_verses'])) or '—'} | "
            f"{rec['crop_markers']} | {rec['ellipsis_markers']} | {rec['digit_bleed_artifacts']} | {rec['hyphen_break_artifacts']} |"
        )
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {JSON_PATH}")
    print(f"wrote {MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
