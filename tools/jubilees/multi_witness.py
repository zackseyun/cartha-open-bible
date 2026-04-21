"""multi_witness.py — Jubilees per-verse witness aggregator (scaffold).

Witness layers:

  Zone 1 (our own OCR, CC-BY 4.0 output):
    - Geʿez: Charles 1895 critical edition (primary)
    - Geʿez: Dillmann-Rönsch 1874 (secondary, cross-check)
    - Latin: Rönsch 1874 fragments (chs 13-49)

  Zone 2 (consult, not reproduced):
    - VanderKam-Milik DJD XIII (Qumran Hebrew 4Q216-228)
    - VanderKam 1989 CSCO critical Ethiopic
    - Segal 2007 commentary
    - Wintermute OTP 1985 English

No Beta maṣāḥǝft-style digital Ge'ez oracle exists for Jubilees
specifically — our cross-check relies on the two PD editions
(Charles + Dillmann/Rönsch) as mutual validation.

SCAFFOLD — Phase 12 work.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SOURCES_ROOT = REPO_ROOT / "sources" / "jubilees"


@dataclass
class JubileesWitnessReading:
    language: str       # "geez" | "latin" | "hebrew"
    witness: str        # "charles_1895" | "dillmann_ronsch_1874" | "ronsch_1874" | "vanderkam_qumran" (Zone 2)
    text: str           # transcribed text in native script
    source_edition: str
    confidence: str
    note: str = ""


@dataclass
class JubileesVerseWitnessSet:
    chapter: int
    verse: int
    geez_charles: Optional[JubileesWitnessReading] = None
    geez_dillmann_ronsch: Optional[JubileesWitnessReading] = None
    latin_ronsch: Optional[JubileesWitnessReading] = None

    def available_witnesses(self) -> list[JubileesWitnessReading]:
        return [w for w in [self.geez_charles, self.geez_dillmann_ronsch,
                            self.latin_ronsch] if w is not None]


CONSULT_REGISTRY: list[dict] = [
    {
        "name": "VanderKam & Milik, Qumran Cave 4 VIII: Parabiblical Texts Part 1 (DJD XIII)",
        "year": 1994,
        "coverage_chapters": "1-50 scattered via 4Q216-228",
        "role": "The actual Hebrew Jubilees fragments from Qumran. Consult for pre-Christian Hebrew witness to specific verses. Footnote fact-level; do NOT reproduce VanderKam's reconstructions.",
    },
    {
        "name": "VanderKam, The Book of Jubilees (CSCO 510-511, Scriptores Aethiopici 87-88)",
        "year": 1989,
        "coverage_chapters": "1-50",
        "role": "Modern critical Ethiopic edition + English translation. Consult where Charles 1895 reading is unclear; VanderKam used more manuscripts.",
    },
    {
        "name": "Segal, The Book of Jubilees: Rewritten Bible, Redaction, Ideology and Theology",
        "year": 2007,
        "coverage_chapters": "1-50",
        "role": "Modern critical commentary focused on composition and ideology.",
    },
    {
        "name": "Wintermute, 'Jubilees' in OTP vol. 2 (Charlesworth, ed.)",
        "year": 1985,
        "coverage_chapters": "1-50",
        "role": "Standard Pseudepigrapha-series English translation. Reference for interpretive context only.",
    },
]


def consult_sources() -> list[dict]:
    return list(CONSULT_REGISTRY)


def is_available() -> bool:
    geez_dir = SOURCES_ROOT / "ethiopic" / "transcribed"
    return geez_dir.exists() and any(geez_dir.glob("*.txt"))


def load_verse(chapter: int, verse: int) -> Optional[JubileesVerseWitnessSet]:
    if not is_available():
        return None
    # TODO(phase12b): implement per-witness loaders
    return None


def summary() -> dict:
    return {
        "pipeline": "jubilees_multi_witness",
        "status": "scaffold",
        "geez_ocr_complete": is_available(),
        "latin_ronsch_transcribed": (SOURCES_ROOT / "latin" / "transcribed").exists() and
                                     any((SOURCES_ROOT / "latin" / "transcribed").iterdir()) if (SOURCES_ROOT / "latin" / "transcribed").exists() else False,
        "zone_2_consult_count": len(CONSULT_REGISTRY),
    }


if __name__ == "__main__":
    import pprint
    print("=== Jubilees multi-witness scaffold ===")
    pprint.pp(summary())
    print("\n=== Zone 2 consult registry ===")
    for c in consult_sources():
        print(f"  - {c['name']} ({c['year']})")
        print(f"      role: {c['role'][:100]}")
