"""multi_witness.py — 2 Esdras per-verse witness aggregator (scaffold).

For any verse in 2 Esdras, return the reading from each available
textual witness. The translator prompt will receive this structured
block and use it for textual-critical grounding.

Scope:
  - Latin (primary):         Bensly 1895 critical edition
  - Syriac:                  Violet 1910 columns + Ceriani 1868
  - Ethiopic:                Violet 1910 columns + Dillmann 1894
  - Arabic (2 recensions):   Violet 1910
  - Armenian:                Violet 1910
  - Georgian:                Violet 1910
  - Coptic (partial):        optional, not yet vendored

This is a SCAFFOLD. The actual transcription pipelines are not built
yet. The interface below is the target shape that Phase 10 drafting
will consume.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

import latin_bensly

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SOURCES_ROOT = REPO_ROOT / "sources" / "2esdras"


@dataclass
class WitnessReading:
    witness: str           # "latin" | "syriac" | "ethiopic" | "arabic_a" | "arabic_b" | "armenian" | "georgian"
    text: str              # transcribed text in the witness's native script
    source_edition: str    # e.g. "Bensly 1895", "Violet 1910"
    confidence: str        # "high" | "medium" | "low" per our standard rubric
    note: str = ""         # free-form annotation (damage, lacuna, variant, etc.)


@dataclass
class VerseWitnessSet:
    chapter: int
    verse: int
    latin: Optional[WitnessReading]
    syriac: Optional[WitnessReading] = None
    ethiopic: Optional[WitnessReading] = None
    arabic_a: Optional[WitnessReading] = None
    arabic_b: Optional[WitnessReading] = None
    armenian: Optional[WitnessReading] = None
    georgian: Optional[WitnessReading] = None
    coptic: Optional[WitnessReading] = None

    def all_witnesses(self) -> list[WitnessReading]:
        out = []
        for w in [self.latin, self.syriac, self.ethiopic, self.arabic_a,
                  self.arabic_b, self.armenian, self.georgian, self.coptic]:
            if w is not None:
                out.append(w)
        return out

    def witness_count(self) -> int:
        return len(self.all_witnesses())


# ---- Zone 2 consult registry (copyrighted; reference only, no text copied) ----

CONSULT_REGISTRY: list[dict] = [
    {
        "name": "Weber-Gryson, Biblia Sacra Vulgata 5th ed.",
        "year": 2007,
        "role": "Modern critical Latin. Apparatus informs adjudication where Bensly 1895 reading is uncertain. Do not reproduce text.",
    },
    {
        "name": "Metzger, 'The Fourth Book of Ezra' in OT Pseudepigrapha vol. 1",
        "year": 1983,
        "role": "English translation with introduction. Consult for interpretive context. Do NOT track English phrasing -- we produce our own.",
    },
    {
        "name": "Stone, Fourth Ezra: A Commentary (Hermeneia)",
        "year": 1990,
        "role": "Verse-by-verse scholarly commentary. Consult for cruxes.",
    },
    {
        "name": "Bidawid, The Syriac Apocalypse of Ezra (Peshitta Institute)",
        "year": 1973,
        "role": "Modern critical Syriac edition. Consult where Violet 1910 Syriac is unclear. Do not reproduce.",
    },
    {
        "name": "Longenecker, 2 Esdras (Sheffield Guides to Apocrypha)",
        "year": 1995,
        "role": "Modern accessible commentary.",
    },
]


def consult_sources() -> list[dict]:
    """Return the Zone 2 scholarly reference list for 2 Esdras.

    Per REFERENCE_SOURCES.md: these may be consulted but their text
    must not appear in COB output.
    """
    return list(CONSULT_REGISTRY)


def is_available() -> bool:
    """True iff per-witness transcribed text files are present on disk."""
    return latin_bensly.is_available()


def load_verse(chapter: int, verse: int) -> Optional[VerseWitnessSet]:
    """Return the full multi-witness reading for a verse, or None if
    the transcription pipeline hasn't produced the chapter yet.

    This function is a SCAFFOLD -- returns None until the OCR and
    per-witness transcription is complete. The interface is frozen
    so Phase 10 drafting code can be written against it now.
    """
    latin = latin_bensly.load_verse(chapter, verse)
    if latin is None:
        return None
    # TODO(phase8c): load daughter witnesses from their transcribed/
    # subdirectories once OCR + normalization completes.
    return VerseWitnessSet(
        chapter=chapter,
        verse=verse,
        latin=WitnessReading(
            witness="latin",
            text=latin.text,
            source_edition=latin.source_edition,
            confidence="high",
            note="Primary Latin witness loaded from chapter-indexed cleaned transcription.",
        ),
    )


def summary() -> dict:
    """Diagnostic summary of what's currently loadable."""
    out = {
        "pipeline": "2esdras_multi_witness",
        "status": "latin_ready_scaffold",
        "latin_transcribed": latin_bensly.is_available(),
        "latin_chapters_available": latin_bensly.available_chapters(),
        "syriac_transcribed": (SOURCES_ROOT / "syriac" / "transcribed").exists()
            and any((SOURCES_ROOT / "syriac" / "transcribed").iterdir()),
        "ethiopic_transcribed": (SOURCES_ROOT / "ethiopic" / "transcribed").exists()
            and any((SOURCES_ROOT / "ethiopic" / "transcribed").iterdir()),
        "zone_2_consult_count": len(CONSULT_REGISTRY),
    }
    return out


if __name__ == "__main__":
    import pprint
    print("=== 2 Esdras multi-witness scaffold ===")
    pprint.pp(summary())
    print("\n=== Zone 2 consult registry ===")
    for c in consult_sources():
        print(f"  - {c['name']} ({c['year']})")
        print(f"      {c['role']}")
