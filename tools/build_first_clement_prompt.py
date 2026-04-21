#!/usr/bin/env python3
"""build_first_clement_prompt.py — assemble a 1 Clement chapter prompt."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import first_clement


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"


@dataclass
class PromptBundle:
    chapter: first_clement.FirstClementChapter
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    source_warnings: list[str]


ZONE2_CONSULTS = [
    "Later Apostolic Fathers critical editions / commentaries (consult only)",
    "Modern English 1 Clement translations for interpretive context only",
]


def _git_head_short() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _snapshot_label(label: str) -> str:
    return f"{label} @{_git_head_short()}"


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


def build_first_clement_prompt(chapter_num: int) -> PromptBundle:
    chapter = first_clement.load_chapter(chapter_num)
    if chapter is None:
        raise LookupError(f"1 Clement chapter {chapter_num} not found in normalized source layer")

    chapter_map = json.loads(first_clement.CHAPTER_MAP_PATH.read_text(encoding="utf-8"))
    missing = chapter_map.get("missing_chapters", [])
    source_warnings: list[str] = []
    if chapter_num in missing:
        source_warnings.append("This chapter is still marked missing in the normalized source layer.")
    if chapter_num in {22, 43}:
        source_warnings.append(
            "This chapter was reconstructed from pre-heading body flow where the raw OCR missed the chapter marker; review before final drafting."
        )

    source_payload = {
        "edition": chapter.source_edition,
        "language": "Greek",
        "text": chapter.text,
        "chapter": chapter.chapter,
        "source_pages": chapter.source_pages,
        "normalization_note": "This chapter comes from the normalized Funk 1901 OCR layer.",
    }
    zone1_sources = [
        _snapshot_label("Funk 1901 (normalized 1 Clement OCR)"),
        _snapshot_label("Lightfoot 1889 (vendored secondary PD source)"),
    ]

    prompt = f"""# Chapter

Reference: 1 Clement {chapter.chapter}
ID: 1CLEM.{chapter.chapter:02d}
Source pages: {chapter.source_pages}

# Zone 1 primary source

{json.dumps(source_payload, ensure_ascii=False, indent=2)}

# Zone 2 consult registry

{json.dumps(ZONE2_CONSULTS, ensure_ascii=False, indent=2)}

# Source integrity notes

{json.dumps(source_warnings or ['No known source-integrity warnings for this chapter.'], ensure_ascii=False, indent=2)}

# Derivative-work guardrails

- The English output must remain anchored in the Greek chapter text above.
- Do NOT reproduce wording from copyrighted modern English 1 Clement translations.
- Use later scholarship only as fact-level context, not as source phrasing.
- Preserve the rhetorical and paraenetic force of the Greek.

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# Task

Produce the highest-quality draft English translation you can for **1 Clement chapter {chapter.chapter}**.

Requirements:
- Translate the whole chapter as a coherent literary unit.
- Preserve scriptural cadence, paraenesis, and ecclesial language.
- Keep lexical/theological reasoning explicit enough for later audit and revision.
"""

    return PromptBundle(
        chapter=chapter,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1_sources,
        zone2_consults_known=ZONE2_CONSULTS,
        source_warnings=source_warnings,
    )


def _to_jsonable(bundle: PromptBundle) -> dict[str, Any]:
    return {
        "reference": f"1 Clement {bundle.chapter.chapter}",
        "id": f"1CLEM.{bundle.chapter.chapter:02d}",
        "prompt": bundle.prompt,
        "source": bundle.source_payload,
        "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
        "zone2_consults_known": bundle.zone2_consults_known,
        "source_warnings": bundle.source_warnings,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    bundle = build_first_clement_prompt(args.chapter)
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
