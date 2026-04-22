#!/usr/bin/env python3
"""build_translation_prompt.py — assemble a 1 Enoch verse translation prompt.

This is the first drafter-facing prompt builder for the Enoch pipeline. It turns
our Charles 1906 Ge'ez OCR into a verse-level prompt payload suitable for later
AI drafting. The prompt is intentionally conservative:

- Zone 1 primary: Charles 1906 Ethiopic OCR (verse-aligned via verse_parser)
- Zone 1 secondary: Dillmann 1851 exists in-repo at chapter level but is not yet
  verse-aligned here, so this builder surfaces that as a warning rather than
  pretending the secondary witness is ready.
- Zone 2 consult: registry from tools/enoch/multi_witness.py
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
BOOK_CONTEXT_PATH = REPO_ROOT / "tools" / "prompts" / "book_contexts" / "enoch.md"
PAGE_MAP_PATH = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "page_map.json"
DILLMANN_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed" / "dillmann_1851"

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import verse_parser  # noqa: E402
from multi_witness import CONSULT_REGISTRY, EnochVerseWitnessSet, EnochWitnessReading  # noqa: E402


@dataclass
class EnochPromptBundle:
    chapter: int
    verse: int
    reference: str
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    source_warnings: list[str]
    witness_set: dict[str, Any]


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


def _chapter_pages(chapter: int, edition: str = "charles_1906") -> list[int]:
    page_map = json.loads(PAGE_MAP_PATH.read_text(encoding="utf-8"))
    chapter_meta = page_map["editions"][edition]["chapters"][f"{chapter:03d}"]
    return list(chapter_meta.get("pages", []))


def _section_name(chapter: int) -> str:
    if 1 <= chapter <= 36:
        return "Book of the Watchers"
    if 37 <= chapter <= 71:
        return "Book of Parables / Similitudes"
    if 72 <= chapter <= 82:
        return "Astronomical Book / Book of the Luminaries"
    if 83 <= chapter <= 90:
        return "Dream Visions / Animal Apocalypse"
    if 91 <= chapter <= 108:
        return "Epistle of Enoch"
    raise ValueError(f"1 Enoch has 108 chapters; got {chapter}")


def _load_charles_witness(chapter: int, verse: int) -> tuple[EnochWitnessReading | None, list[str]]:
    row, warnings = verse_parser.load_verse(chapter, verse)
    if row is None:
        return None, warnings
    return (
        EnochWitnessReading(
            language="geez",
            witness="charles_1906",
            text=row.text,
            source_edition="Charles 1906 Ethiopic Enoch",
            confidence="medium",
            note=f"Recovered from {row.chapter_file} via tools/enoch/verse_parser.py",
        ),
        warnings,
    )


def _dillmann_available(chapter: int) -> bool:
    return (DILLMANN_ROOT / f"ch{chapter:02d}.txt").exists()


def _zone2_registry() -> list[dict[str, Any]]:
    return [dict(entry) for entry in CONSULT_REGISTRY]


ENOCH_GUARDRAILS = """\
- Translate from the Ge'ez witness provided here; do not silently replace it with a later English tradition.
- Preserve apocalyptic imagery, angelic speech, and repeated judgment formulas rather than smoothing them away.
- Do not import New Testament phrasing just because Jude or later Christian texts echo the passage.
- In the Parables (chs. 37-71), be especially transparent about uncertainty because the section is effectively Ge'ez-only for this workflow.
- Keep major terms like righteous/chosen/holy ones/Watchers/Son of Man locally grounded in the passage before harmonizing them across the corpus.
- When the sense is uncertain, prefer a careful English rendering plus footnote over overconfident paraphrase.
"""


def build_enoch_prompt(chapter: int, verse: int) -> EnochPromptBundle:
    if not (1 <= chapter <= 108):
        raise ValueError(f"1 Enoch has 108 chapters; {chapter} out of range")
    if verse < 1:
        raise ValueError("Verse must be >= 1")

    warnings: list[str] = []
    charles, parse_warnings = _load_charles_witness(chapter, verse)
    warnings.extend(parse_warnings)
    if charles is None:
        raise ValueError(f"Could not recover 1 Enoch {chapter}:{verse} from the Charles 1906 OCR layer.")

    if _dillmann_available(chapter):
        warnings.append(
            f"Dillmann 1851 chapter OCR exists for chapter {chapter}, but verse-aligned extraction is not yet implemented in this prompt builder."
        )
    else:
        warnings.append(f"No Dillmann 1851 chapter OCR file found for chapter {chapter}.")

    pages = _chapter_pages(chapter, edition="charles_1906")
    witness_set = EnochVerseWitnessSet(chapter=chapter, verse=verse, geez_charles=charles)
    reference = f"1 Enoch {chapter}:{verse}"
    zone1_sources_at_draft = [_snapshot_label("Charles 1906 Ethiopic Enoch (Gemini OCR + verse parser)")]
    if _dillmann_available(chapter):
        zone1_sources_at_draft.append(_snapshot_label("Dillmann 1851 Ethiopic Enoch (chapter OCR only)"))
    zone2_consults_known = [entry["name"] for entry in _zone2_registry()]

    source_payload = {
        "edition": "charles-1906-enoch",
        "language": "Geez",
        "text": charles.text,
        "pages": pages,
        "confidence": charles.confidence,
        "validation": "verse_parser_ok",
        "note": charles.note,
        "section": _section_name(chapter),
    }

    prompt = f"""Reference: {reference}
Section: {_section_name(chapter)}

Book context:
{book_context()}

Source witness (Zone 1 primary — Charles 1906 Ge'ez OCR):
{charles.text}

Source metadata:
- Witness: Charles 1906 Ethiopic Enoch
- Pages: {pages}
- Recovery method: verse_parser on chapter OCR
- Confidence: {charles.confidence}

Additional witness state:
- Dillmann 1851 chapter OCR exists: {'yes' if _dillmann_available(chapter) else 'no'}
- Greek fragment coverage for this section: {'possible/partial' if chapter <= 36 or chapter >= 72 else 'none or effectively none'}

Translation guardrails:
{ENOCH_GUARDRAILS}

Doctrinal/translation philosophy excerpts:
{doctrine_excerpt()}

Project philosophy excerpt:
{philosophy_excerpt()}

Zone 2 consult registry (reference only; do not copy wording):
{json.dumps(_zone2_registry(), ensure_ascii=False, indent=2)}

Task:
Translate ONLY this verse into clear, auditable English for the Cartha Open Bible.
Return a faithful translation anchored in the Ge'ez text above, plus transparent lexical/theological decisions and any footnotes needed for uncertainty or textual difficulty.
Do not copy from modern copyrighted English Enoch translations.
""".strip()

    return EnochPromptBundle(
        chapter=chapter,
        verse=verse,
        reference=reference,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1_sources_at_draft,
        zone2_consults_known=zone2_consults_known,
        source_warnings=warnings,
        witness_set={
            "chapter": witness_set.chapter,
            "verse": witness_set.verse,
            "section": witness_set.section(),
            "available_witnesses": [asdict(w) for w in witness_set.available_witnesses()],
        },
    )


def _to_jsonable(bundle: EnochPromptBundle) -> dict[str, Any]:
    return {
        "chapter": bundle.chapter,
        "verse": bundle.verse,
        "reference": bundle.reference,
        "prompt": bundle.prompt,
        "source_payload": bundle.source_payload,
        "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
        "zone2_consults_known": bundle.zone2_consults_known,
        "source_warnings": bundle.source_warnings,
        "witness_set": bundle.witness_set,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a verse-level translation prompt for 1 Enoch.")
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--verse", type=int, required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    bundle = build_enoch_prompt(args.chapter, args.verse)
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
