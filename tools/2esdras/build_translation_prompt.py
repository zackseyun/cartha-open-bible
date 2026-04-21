#!/usr/bin/env python3
"""build_translation_prompt.py — assemble a 2 Esdras chapter prompt.

Per-chapter prompt builder for 2 Esdras (4 Ezra). Parallel to
tools/build_first_clement_prompt.py but specialized for:

  - Latin primary source (Bensly 1895 + 1875 Missing Fragment)
  - Compositional-layer labeling (5 Ezra / 4 Ezra / 6 Ezra)
  - Multi-witness context for chs 3-14 via multi_witness.py
  - Reader-facing section-header and headnote guidance per 2ESDRAS.md
  - Special handling for 7:28 (messianic death) and 7:36 (Bensly's
    recovered fragment)

The output is consumed by tools/2esdras/draft.py which calls the
Azure OpenAI vision-free text model with function-calling to emit
structured per-chapter YAML.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import latin_bensly
import multi_witness


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
TWO_ESDRAS_DOC = REPO_ROOT / "2ESDRAS.md"


# ---- Compositional layer labels per 2ESDRAS.md ----

LAYER_FIVE_EZRA = {
    "name": "5 Ezra",
    "chapters": [1, 2],
    "note": (
        "Christian addition preserved only in Latin, c. 2nd-3rd century AD. "
        "Distinct in origin from the Jewish apocalypse of chs 3-14. "
        "Recasts Ezra as a prophet rejected by Israel with God turning to "
        "the Gentiles. No daughter-language witnesses -- Latin is the "
        "only witness."
    ),
}

LAYER_FOUR_EZRA = {
    "name": "4 Ezra",
    "chapters": list(range(3, 15)),
    "note": (
        "The original Jewish apocalypse, c. 100 AD, composed in Hebrew or "
        "Aramaic after the fall of the Second Temple under Rome. The Semitic "
        "original is lost; the book survives through Latin + Syriac + "
        "Ethiopic + Arabic + Armenian + Georgian translations of a lost "
        "Greek intermediary. Seven visions of the seer Ezra answered by the "
        "angel Uriel."
    ),
}

LAYER_SIX_EZRA = {
    "name": "6 Ezra",
    "chapters": [15, 16],
    "note": (
        "Christian addition preserved only in Latin, c. 3rd century AD. "
        "Prophetic oracles against the nations, appended to the Latin "
        "tradition of 4 Ezra. Distinct in authorship and register from the "
        "core apocalypse. Latin is the only witness."
    ),
}


def chapter_layer(chapter: int) -> dict:
    for layer in (LAYER_FIVE_EZRA, LAYER_FOUR_EZRA, LAYER_SIX_EZRA):
        if chapter in layer["chapters"]:
            return layer
    raise LookupError(f"2 Esdras has no chapter {chapter}")


# ---- Reader-facing labels per 2ESDRAS.md ----

BOOK_HEADNOTE = (
    "**2 Esdras (Appendix)**. Also called 4 Ezra or the Ezra Apocalypse. "
    "Not canonical in modern Catholic, Orthodox, or Protestant Bibles. "
    "Canonical in the Ethiopian Orthodox tradition. Preserved in the "
    "appendix of the Latin Vulgate. Included in the Apocrypha of the 1611 "
    "King James Bible. The book is a composite: chs 3-14 are a Jewish "
    "apocalypse from c. 100 AD (Semitic original lost, surviving via "
    "Latin/Syriac/Ethiopic/Arabic/Armenian/Georgian), while chs 1-2 and "
    "15-16 are later Christian additions preserved only in Latin. This "
    "translation is based on Bensly's 1895 critical Latin edition (Cambridge "
    "Texts and Studies III.2), with the Bensly 1875 recovered fragment "
    "restoring 7:36-105."
)

SECTION_HEADER_BY_CHAPTER: dict[int, str] = {
    1: LAYER_FIVE_EZRA["note"],
    3: LAYER_FOUR_EZRA["note"],
    15: LAYER_SIX_EZRA["note"],
}

# ---- Special inline footnotes to surface at draft time ----

SPECIAL_FOOTNOTES = [
    {
        "anchor": "7:28",
        "marker_hint": "messianic_death",
        "text": (
            "The Latin reads filius meus Christus: 'my son the Messiah.' "
            "The passage describes the Messiah reigning with the righteous "
            "for 400 years and then dying, followed by seven days of "
            "primeval silence and then resurrection. Among the most "
            "striking Jewish messianic passages from roughly the era of "
            "the New Testament. The Syriac and Ethiopic witnesses preserve "
            "similar readings, though later Latin manuscripts sometimes "
            "adjusted the numeral."
        ),
    },
    {
        "anchor": "7:36",
        "marker_hint": "recovered_fragment",
        "text": (
            "Verses 7:36-105 are Bensly's 'Missing Fragment.' Cut from most "
            "medieval Latin manuscripts -- almost certainly because this "
            "section teaches that intercession for the damned is refused, "
            "which later Christian piety found difficult -- and therefore "
            "absent from the Vulgate and from the KJV 1611, where verse "
            "7:35 was followed directly by what older editions numbered as "
            "verse 7:36 some seventy verses later. Robert Bensly recovered "
            "the fragment from a Spanish manuscript in 1875 and it is now "
            "restored in all modern critical editions."
        ),
    },
]


@dataclass
class PromptBundle:
    chapter: int
    layer_name: str
    latin_text: str  # verse-numbered Latin, one verse per line
    verse_count: int
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    source_warnings: list[str]
    reader_facing: dict[str, Any]


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


def _render_latin_text(chapter: int) -> tuple[str, int]:
    verses = latin_bensly.load_chapter(chapter)
    if not verses:
        raise LookupError(f"2 Esdras chapter {chapter} has no Latin verses in the transcribed layer")
    ordered = sorted(verses.items())
    lines = [f"{num} {v.text}" for num, v in ordered]
    return "\n".join(lines), len(ordered)


def _witness_note_for_chapter(chapter: int, layer_name: str) -> str:
    """Describe multi-witness coverage available for this chapter."""
    if layer_name in ("5 Ezra", "6 Ezra"):
        return (
            "Latin is the only extant witness for this chapter (Christian "
            "addition, Latin only). No Syriac/Ethiopic/Arabic/Armenian/"
            "Georgian apparatus applies."
        )
    ws = multi_witness.load_verse(chapter, 1)
    if ws is None:
        return (
            "Multi-witness transcribed layer not yet populated for this "
            "chapter. Latin primary is used; the Violet 1910 parallel-column "
            "daughter witnesses (Syriac, Ethiopic, Arabic, Armenian, "
            "Georgian) are planned as cross-reference overlay per 2ESDRAS.md "
            "but are not present on disk at draft time."
        )
    daughters = [w.witness for w in ws.all_witnesses() if w.witness != "latin"]
    if not daughters:
        return (
            "Multi-witness scaffold is live for this chapter but no "
            "daughter-language readings are transcribed yet; Latin primary "
            "is used."
        )
    return (
        f"Multi-witness layer populated with: {', '.join(sorted(set(daughters)))}. "
        f"Use daughter-language readings as cross-check for Latin."
    )


def _special_footnotes_for_chapter(chapter: int) -> list[dict]:
    if chapter != 7:
        return []
    return SPECIAL_FOOTNOTES


def _section_header_for_chapter(chapter: int) -> str | None:
    return SECTION_HEADER_BY_CHAPTER.get(chapter)


def build_2esdras_prompt(chapter: int) -> PromptBundle:
    layer = chapter_layer(chapter)
    latin_text, verse_count = _render_latin_text(chapter)
    witness_note = _witness_note_for_chapter(chapter, layer["name"])
    special_footnotes = _special_footnotes_for_chapter(chapter)
    section_header = _section_header_for_chapter(chapter)

    source_warnings: list[str] = []
    if verse_count < 5:
        source_warnings.append(
            f"Chapter {chapter} currently has only {verse_count} verses in the Latin transcribed layer; verify completeness before drafting."
        )

    source_payload = {
        "edition": "Bensly 1895 (Texts and Studies III.2) + Bensly 1875 Missing Fragment, cleaned Latin",
        "language": "Latin",
        "text": latin_text,
        "chapter": chapter,
        "verse_count": verse_count,
        "compositional_layer": layer["name"],
        "compositional_note": layer["note"],
        "witness_situation": witness_note,
        "normalization_note": "Verse-numbered cleaned Latin loaded from sources/2esdras/latin/transcribed/. Chapter 7 includes 7:36-105 restored from Bensly 1875.",
    }
    zone1_sources = [
        _snapshot_label("Bensly 1895, Fourth Book of Ezra (Texts and Studies III.2)"),
        _snapshot_label("Bensly 1875, Missing Fragment of the Latin Translation"),
        _snapshot_label("Violet 1910, Die Esra-Apokalypse (GCS 18) — parallel witness apparatus"),
    ]
    zone2_consults = [
        f"{c['name']} ({c['year']}) — {c['role']}"
        for c in multi_witness.consult_sources()
    ]

    reader_facing = {
        "chapter": chapter,
        "compositional_layer": layer["name"],
        "is_first_chapter_of_book": chapter == 1,
        "book_headnote": BOOK_HEADNOTE if chapter == 1 else None,
        "section_header": section_header,
        "special_footnotes": special_footnotes,
    }

    prompt = f"""# Chapter

Reference: 2 Esdras {chapter}
ID: 2ES.{chapter:02d}
Compositional layer: {layer["name"]}

# Compositional-layer context

{layer["note"]}

# Zone 1 primary source (Latin)

{json.dumps(source_payload, ensure_ascii=False, indent=2)}

# Zone 2 consult registry

{json.dumps(zone2_consults, ensure_ascii=False, indent=2)}

# Source integrity notes

{json.dumps(source_warnings or ['No known source-integrity warnings for this chapter.'], ensure_ascii=False, indent=2)}

# Reader-facing obligations

The publishing pipeline will render specific labels alongside this
chapter. Your draft must respect these as structural decisions, not
smooth them away.

{json.dumps(reader_facing, ensure_ascii=False, indent=2)}

Guidance on reader-facing labeling:

- If `book_headnote` is non-null, it will render as the BOOK's intro
  above chapter 1. Do NOT copy it into the English body text. Your
  English body must START at verse 1 of the chapter itself.
- If `section_header` is non-null, it will render as a SECTION break
  above verse 1 of this chapter. Do NOT copy it into the English
  body. Treat it as structural metadata.
- For any entry in `special_footnotes`, emit a corresponding
  `footnotes[]` item with `marker` corresponding to the anchor verse
  (e.g. "7:28") and the footnote text preserved faithfully.

# Derivative-work guardrails

- The English output must remain anchored in the Latin chapter text above.
- Do NOT reproduce wording from copyrighted modern English 2 Esdras or 4 Ezra translations (Metzger, Stone, NRSV, etc.). Use those only as fact-level interpretive context.
- Do NOT smooth away the book's theological hard edges: Ezra's protests, Uriel's refusals, the narrow-way passages (7:45-61, 7:102-115, 8:38-41, 9:13-22) must land with the force the Latin gives them.
- Preserve the seven-vision structure for chs 3-14.

# Translation register obligations

- Translate `Altissimus` as "the Most High" (do not flatten to "God").
- Maintain the *cor malignum* / "evil heart" thread across 3:21-22, 4:30, 7:48 so the doctrine is visible to readers.
- Preserve Ezra's emotional register -- grief, protest, complaint, lament -- rather than smoothing into polite devotional English.
- `filius meus Christus` at 7:28 renders as "my son the Messiah" (not "my son Christ"), consistent with project policy to translate Christ as title Messiah where title sense is active.
- Uriel's voice should read as measured and authoritative; Ezra's as raw and questioning.
- For prophetic oracles in chs 15-16 (6 Ezra), keep the declamatory prophetic cadence rather than collapsing into modern prose.

# Witness-apparatus obligations

{witness_note}

Where Latin has demonstrable cruxes and the daughter-language witnesses (when available) diverge meaningfully, surface that in `theological_decisions[]` or `footnotes[]` rather than choosing silently.

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# Task

Produce the highest-quality draft English translation you can for **2 Esdras chapter {chapter}** (compositional layer: {layer["name"]}).

Requirements:
- Translate the whole chapter as a coherent literary unit.
- Preserve prophetic/apocalyptic cadence; do not flatten into generic prose.
- Keep lexical and theological reasoning explicit enough for later audit and revision.
- Render the `special_footnotes` as `footnotes[]` items on your tool call (markers "7:28" and "7:36" for chapter 7).
- Submit exactly one call to the submit_2esdras_draft function.
"""

    return PromptBundle(
        chapter=chapter,
        layer_name=layer["name"],
        latin_text=latin_text,
        verse_count=verse_count,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1_sources,
        zone2_consults_known=zone2_consults,
        source_warnings=source_warnings,
        reader_facing=reader_facing,
    )


def _to_jsonable(bundle: PromptBundle) -> dict[str, Any]:
    return {
        "reference": f"2 Esdras {bundle.chapter}",
        "id": f"2ES.{bundle.chapter:02d}",
        "compositional_layer": bundle.layer_name,
        "verse_count": bundle.verse_count,
        "prompt": bundle.prompt,
        "source": bundle.source_payload,
        "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
        "zone2_consults_known": bundle.zone2_consults_known,
        "source_warnings": bundle.source_warnings,
        "reader_facing": bundle.reader_facing,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    bundle = build_2esdras_prompt(args.chapter)
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
