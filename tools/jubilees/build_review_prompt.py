#!/usr/bin/env python3
"""build_review_prompt.py — assemble one Jubilees chapter review prompt."""
from __future__ import annotations

import functools
import json
import pathlib
import re
import subprocess
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
JUBILEES_ROOT = REPO_ROOT / "sources" / "jubilees"
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "jubilees"
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
REVISION_PATH = REPO_ROOT / "REVISION_METHODOLOGY.md"
CHARLES_1902_PDF = JUBILEES_ROOT / "scans" / "charles_1902_english.pdf"

from multi_witness import CONSULT_REGISTRY  # noqa: E402


def _load_excerpt(path: pathlib.Path, keep_sections: set[str]) -> str:
    if not path.exists():
        return f"({path.name} not found)"
    lines = path.read_text(encoding="utf-8").splitlines()
    keeping = False
    out: list[str] = []
    for line in lines:
        if line.startswith("## "):
            keeping = line.strip() in keep_sections
        if keeping:
            out.append(line)
    return "\n".join(out).strip() or f"({path.name} excerpt empty)"


def doctrine_excerpt() -> str:
    return _load_excerpt(
        DOCTRINE_PATH,
        {"## Translation philosophy", "## Contested terms"},
    )


def philosophy_excerpt() -> str:
    return _load_excerpt(
        PHILOSOPHY_PATH,
        {"## What we are translating", '## What "transparent" actually means here'},
    )


def revision_excerpt() -> str:
    return _load_excerpt(
        REVISION_PATH,
        {"## What triggers a revision", "## What does NOT trigger a revision"},
    )


def chapter_yaml_path(chapter: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{chapter:03d}.yaml"


def load_chapter_record(chapter: int) -> dict[str, Any]:
    import yaml

    path = chapter_yaml_path(chapter)
    if not path.exists():
        raise FileNotFoundError(f"Jubilees draft chapter YAML missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


ROMAN_MAP = {
    "I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000,
}


def roman_to_int(token: str) -> int:
    total = 0
    prev = 0
    for ch in reversed(token):
        val = ROMAN_MAP[ch]
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total


@functools.lru_cache(maxsize=1)
def charles_1902_text() -> str:
    if not CHARLES_1902_PDF.exists():
        return ""
    return subprocess.check_output(["pdftotext", str(CHARLES_1902_PDF), "-"], text=True, errors="ignore")


def charles_1902_chapter_text(chapter: int) -> str:
    text = charles_1902_text()
    if not text:
        return "(Charles 1902 English PDF unavailable)"
    lines = text.splitlines()
    blocks: list[str] = []
    current_heading = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        if current_heading is None:
            current_lines = []
            return
        roman_hits = re.findall(r"\b([IVXLCDM]+)\b", current_heading)
        chapters = {roman_to_int(tok) for tok in roman_hits if tok}
        if chapter in chapters:
            block = current_heading + "\n" + "\n".join(current_lines)
            blocks.append(block.strip())
        current_heading = None
        current_lines = []

    for line in lines:
        stripped = line.strip()
        if re.match(r"^CHAPTERS?\b", stripped):
            flush()
            current_heading = stripped
            continue
        if current_heading is not None:
            current_lines.append(line)
    flush()
    if not blocks:
        return f"(No Charles 1902 English block found for chapter {chapter})"
    return "\n\n".join(blocks)


def build_prompt(chapter: int) -> tuple[str, dict[str, Any]]:
    record = load_chapter_record(chapter)
    source = record["source"]
    translation = record["translation"]
    charles_1902 = charles_1902_chapter_text(chapter)
    prior_reviews = record.get("review_passes", [])

    prompt = f"""# Chapter review target

Reference: Jubilees {chapter}
YAML path: translation/extra_canonical/jubilees/{chapter:03d}.yaml

# Current source payload

{json.dumps(source, ensure_ascii=False, indent=2)}

# Current draft English

{translation.get('text', '')}

# Current lexical decisions

{json.dumps(record.get('lexical_decisions', []), ensure_ascii=False, indent=2)}

# Current theological decisions

{json.dumps(record.get('theological_decisions', []), ensure_ascii=False, indent=2)}

# Current footnotes

{json.dumps(translation.get('footnotes', []), ensure_ascii=False, indent=2)}

# Prior review passes

{json.dumps(prior_reviews, ensure_ascii=False, indent=2)}

# Charles 1902 English reference (semantic cross-check only; do not copy wording)

{charles_1902}

# Zone 2 consult registry (do not reproduce wording)

{json.dumps(CONSULT_REGISTRY, ensure_ascii=False, indent=2)}

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# REVISION_METHODOLOGY.md excerpt

{revision_excerpt()}

# Jubilees-specific review reminders

- The Ge'ez chapter source rows above are primary.
- Preserve Jubilees's calendrical vocabulary carefully.
- Preserve the Sinai-revelation / angelic dictation framing.
- Do NOT harmonize away deliberate divergences from Genesis/Exodus.
- Revise only where the English becomes materially better or more faithful.
- If the current draft is already strong in a place, leave it alone.
- Use Charles 1902 only as a semantic / chapter-boundary cross-check, not as a wording source.
- Zone 2 works are consult-only; do not reproduce their wording.

# Task

Review and revise this full Jubilees chapter draft.

Return ONLY a JSON object with keys:
- `english_text`
- `translation_philosophy`
- `lexical_decisions`
- optional `theological_decisions`
- optional `footnotes`
- `review_summary`
- `issues_found`

Requirements:
- Preserve verse numbering in `english_text` using `N. ...` per verse.
- Keep the chapter complete.
- Make real improvements where warranted.
- Do not invent source material.
"""
    return prompt, record


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, required=True)
    args = ap.parse_args()
    prompt, _ = build_prompt(args.chapter)
    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
