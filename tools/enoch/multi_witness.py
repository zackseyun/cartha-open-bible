"""multi_witness.py — 1 Enoch per-verse witness aggregator (scaffold).

For any verse in 1 Enoch, return the reading from each available
textual witness. The translator prompt will receive this structured
block and use it for textual-critical grounding.

Witness layers (ordered by language authority):

  Zone 1 (our own OCR, CC-BY 4.0 output):
    - Ge'ez: Charles 1906 critical edition (primary)
    - Ge'ez: Dillmann 1851 (secondary, cross-check)
    - Greek: Bouriant 1892 (Codex Panopolitanus, chs 1-32)
    - Greek: Flemming 1901 (Syncellus + Chester Beatty chs 97-107)

  Zone 1 validation oracle (not vendored, cross-check only):
    - Ge'ez: Beta maṣāḥǝft LIT1340EnochE.xml (Jerabek 1995 / CC-BY-SA
      wrapper / NC inner — kept local only)

  Zone 2 (consult, not reproduced):
    - Milik 1976 DJD XXXVI — Qumran 4Q201-212 Aramaic reconstructions
    - Nickelsburg 2001 Hermeneia
    - Nickelsburg & VanderKam 2012 Hermeneia
    - Knibb 1978 modern critical Ethiopic
    - Black 1985, OTP Isaac 1983

This is a SCAFFOLD. Actual OCR/transcription is Phase 11b; actual
translation is Phase 11c. The interface below is the target shape
that Phase 11c will consume.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SOURCES_ROOT = REPO_ROOT / "sources" / "enoch"
BETAMASAHEFT_LOCAL = pathlib.Path.home() / "cartha-reference-local" / "enoch_betamasaheft"


@dataclass
class EnochWitnessReading:
    language: str       # "geez" | "greek" | "aramaic"
    witness: str        # e.g. "charles_1906" | "dillmann_1851" | "panopolitanus" | "syncellus" | "chester_beatty" | "betamasaheft"
    text: str           # transcribed text in native script
    source_edition: str
    confidence: str     # "high" | "medium" | "low"
    note: str = ""


@dataclass
class EnochVerseWitnessSet:
    chapter: int
    verse: int

    # Ge'ez witnesses (Zone 1 our-OCR + validation oracle)
    geez_charles: Optional[EnochWitnessReading] = None
    geez_dillmann: Optional[EnochWitnessReading] = None
    geez_betamasaheft_oracle: Optional[EnochWitnessReading] = None  # reference only, not for output derivation

    # Greek witnesses (Zone 1 our-OCR)
    greek_panopolitanus: Optional[EnochWitnessReading] = None  # chs 1-32
    greek_syncellus: Optional[EnochWitnessReading] = None      # scattered
    greek_chester_beatty: Optional[EnochWitnessReading] = None # chs 97-107

    def available_witnesses(self) -> list[EnochWitnessReading]:
        out = []
        for w in [self.geez_charles, self.geez_dillmann, self.geez_betamasaheft_oracle,
                  self.greek_panopolitanus, self.greek_syncellus, self.greek_chester_beatty]:
            if w is not None:
                out.append(w)
        return out

    def has_greek(self) -> bool:
        return any([self.greek_panopolitanus, self.greek_syncellus, self.greek_chester_beatty])

    def section(self) -> str:
        """The compositional section this verse belongs to."""
        ch = self.chapter
        if 1 <= ch <= 36:
            return "Book of the Watchers"
        if 37 <= ch <= 71:
            return "Book of Parables / Similitudes"
        if 72 <= ch <= 82:
            return "Astronomical Book / Book of the Luminaries"
        if 83 <= ch <= 90:
            return "Book of Dreams / Animal Apocalypse"
        if 91 <= ch <= 108:
            return "Epistle of Enoch"
        return "unknown"


# ---- Zone 2 consult registry (copyrighted; reference only, no text copied) ----

CONSULT_REGISTRY: list[dict] = [
    {
        "name": "Milik, The Books of Enoch: Aramaic Fragments of Qumrân Cave 4 (DJD XXXVI)",
        "year": 1976,
        "coverage_chapters": "1-36, 72-108 (partial, depending on fragment)",
        "role": "Qumran Aramaic 4Q201-212 reconstructions. Consult for pre-Christian Aramaic witness to chapters outside the Parables. Footnote fact-level ('4Q204 attests the Greek reading here'); do NOT reproduce Milik's reconstructed Aramaic.",
    },
    {
        "name": "Nickelsburg, 1 Enoch 1: A Commentary (Hermeneia)",
        "year": 2001,
        "coverage_chapters": "1-36, 81-108",
        "role": "Gold-standard modern commentary. Consult for interpretive cruxes and textual-critical decisions. Do NOT track English phrasing — we produce our own.",
    },
    {
        "name": "Nickelsburg & VanderKam, 1 Enoch 2: A Commentary (Hermeneia)",
        "year": 2012,
        "coverage_chapters": "37-71 (the Parables)",
        "role": "The specialist commentary on the Similitudes, which we cannot cross-check against Qumran or Greek. Especially important for this section.",
    },
    {
        "name": "Knibb, The Ethiopic Book of Enoch (2 vols, Oxford)",
        "year": 1978,
        "coverage_chapters": "1-108",
        "role": "Modern critical Ge'ez edition with English translation and apparatus. Consult where Charles 1906 reading is unclear; Knibb's apparatus may preserve variant readings. Do not reproduce.",
    },
    {
        "name": "Black, The Book of Enoch or 1 Enoch: A New English Edition (Brill)",
        "year": 1985,
        "coverage_chapters": "1-108",
        "role": "Modern English translation with commentary. Consult for interpretive context.",
    },
    {
        "name": "Isaac, '1 (Ethiopic Apocalypse of) Enoch' in OTP vol. 1 (Charlesworth, ed.)",
        "year": 1983,
        "coverage_chapters": "1-108",
        "role": "Standard Pseudepigrapha-series English translation. Reference only.",
    },
]


def consult_sources() -> list[dict]:
    """Return Zone 2 scholarly references for Enoch.

    Per REFERENCE_SOURCES.md: these may be consulted during translation;
    their text must not appear in COB output.
    """
    return list(CONSULT_REGISTRY)


def oracle_available() -> bool:
    """True iff the Beta maṣāḥǝft Ge'ez XML is present in the local
    reference workspace (outside the repo). Used for cross-validating
    our own OCR of Charles 1906 + Dillmann 1851.
    """
    return (BETAMASAHEFT_LOCAL / "LIT1340EnochE.xml").exists()


def is_available() -> bool:
    """True iff our own transcriptions are produced and loadable."""
    geez_dir = SOURCES_ROOT / "ethiopic" / "transcribed"
    return geez_dir.exists() and any(geez_dir.glob("*.txt"))


def load_verse(chapter: int, verse: int) -> Optional[EnochVerseWitnessSet]:
    """Return the full multi-witness reading for a verse, or None if
    the transcription pipeline hasn't produced the chapter yet.

    SCAFFOLD — returns None until Phase 11b transcription completes.
    """
    if not is_available():
        return None
    # TODO(phase11b): implement per-witness loaders from transcribed/ files
    return None


def summary() -> dict:
    """Diagnostic summary of what's loadable."""
    out = {
        "pipeline": "enoch_multi_witness",
        "status": "scaffold",
        "geez_ocr_complete": is_available(),
        "betamasaheft_oracle_available_locally": oracle_available(),
        "greek_ocr_complete": (SOURCES_ROOT / "greek" / "transcribed").exists() and
                              any((SOURCES_ROOT / "greek" / "transcribed").iterdir()) if (SOURCES_ROOT / "greek" / "transcribed").exists() else False,
        "zone_2_consult_count": len(CONSULT_REGISTRY),
    }
    return out


if __name__ == "__main__":
    import pprint
    print("=== 1 Enoch multi-witness scaffold ===")
    pprint.pp(summary())
    print("\n=== Zone 2 consult registry ===")
    for c in consult_sources():
        print(f"  - {c['name']} ({c['year']})")
        print(f"      coverage: {c['coverage_chapters']}")
        print(f"      role: {c['role'][:100]}")
