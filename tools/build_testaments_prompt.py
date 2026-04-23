#!/usr/bin/env python3
"""build_testaments_prompt.py — assemble a Testament chapter draft prompt."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import testaments_twelve_patriarchs as t12p


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
BOOK_CONTEXT_PATH = REPO_ROOT / "tools" / "prompts" / "book_contexts" / "testaments_twelve_patriarchs.md"


@dataclass
class PromptBundle:
    chapter: t12p.TestamentChapter
    reference: str
    chapter_id: str
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    source_warnings: list[str]


ZONE2_CONSULTS = [
    "Modern critical scholarship on the Testaments of the Twelve Patriarchs (consult only)",
    "Jewish Pseudepigrapha commentary / textual criticism (consult only)",
    "Modern English translations for interpretive context only, never for phrasing",
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


def _load_excerpt(path: pathlib.Path, keep_sections: set[str] | None = None) -> str:
    if not path.exists():
        return f"({path.name} not found)"
    if keep_sections is None:
        return path.read_text(encoding="utf-8").strip()
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


def book_context() -> str:
    return _load_excerpt(BOOK_CONTEXT_PATH)


def build_testaments_prompt(testament_slug: str, chapter_num: int) -> PromptBundle:
    chapter = t12p.load_chapter(testament_slug, chapter_num)
    if chapter is None:
        raise LookupError(f"{testament_slug} chapter {chapter_num} not found in normalized source layer")

    display_name = t12p.testament_display_name(testament_slug)
    code = t12p.testament_code(testament_slug)
    reference = f"{display_name} {chapter_num}"
    chapter_id = f"T12P.{code}.{chapter_num:02d}"

    source_payload = {
        "edition": chapter.source_edition,
        "language": "Greek",
        "testament": display_name,
        "testament_slug": testament_slug,
        "text": chapter.text,
        "chapter": chapter.chapter,
        "source_pages": chapter.source_pages,
        "normalization_note": (
            "This chapter comes from the normalized Charles 1908 Greek OCR layer "
            "for the Testaments of the Twelve Patriarchs."
        ),
    }
    zone1_sources = [
        _snapshot_label("Charles 1908 Greek Versions (normalized Testament OCR)"),
    ]
    source_warnings: list[str] = []
    if not chapter.source_pages:
        source_warnings.append("Source page list missing in normalized chapter metadata.")
    if testament_slug == "joseph":
        source_warnings.append(
            "Joseph normalization includes manual fallback transcription for two previously failed raw OCR pages (261 and 264)."
        )

    prompt = f"""# Chapter

Reference: {reference}
ID: {chapter_id}
Source pages: {chapter.source_pages}

# Book context

{book_context()}

# Zone 1 primary source

{json.dumps(source_payload, ensure_ascii=False, indent=2)}

# Zone 2 consult registry

{json.dumps(ZONE2_CONSULTS, ensure_ascii=False, indent=2)}

# Source integrity notes

{json.dumps(source_warnings or ['No known source-integrity warnings for this chapter.'], ensure_ascii=False, indent=2)}

# Derivative-work guardrails

- The English output must remain anchored in the Greek chapter text above.
- Do NOT reproduce wording from copyrighted modern English Testament translations.
- Preserve the voice of the specific patriarch speaking in this testament.
- Where the Greek reflects textual complexity or probable later expansion, translate honestly and use notes rather than harmonizing.

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# Task

Produce the highest-quality draft English translation you can for **{reference}**.

Requirements:
- Translate the whole chapter as a coherent literary unit.
- Preserve direct address, moral exhortation, and rhetorical parallelism.
- Do not flatten vice/virtue catalogues into generic modern prose.
- Keep lexical/theological reasoning explicit enough for later audit and revision.
"""

    return PromptBundle(
        chapter=chapter,
        reference=reference,
        chapter_id=chapter_id,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1_sources,
        zone2_consults_known=ZONE2_CONSULTS,
        source_warnings=source_warnings,
    )


def _to_jsonable(bundle: PromptBundle) -> dict[str, Any]:
    return {
        "reference": bundle.reference,
        "id": bundle.chapter_id,
        "prompt": bundle.prompt,
        "source": bundle.source_payload,
        "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
        "zone2_consults_known": bundle.zone2_consults_known,
        "source_warnings": bundle.source_warnings,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testament", required=True, choices=sorted(t12p.TESTAMENT_BY_SLUG))
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--json", action="store_true", help="Print JSON payload instead of raw prompt")
    args = parser.parse_args()

    bundle = build_testaments_prompt(args.testament, args.chapter)
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
