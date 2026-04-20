"""swete_amicarelli.py — second independent encoding of Swete LXX.

Source: Eliran Wong's LXX-Swete-1930 GitHub repo, which republishes
Pasquale Amicarelli's BibleWorks module transcription of Swete's
1909-1930 edition. GPL v3-licensed.

This is a THIRD independent transcription of the same Swete edition
(alongside our OCR and First1KGreek's TEI encoding). Used as an
additional reference in the scan-grounded adjudicator — never copied
into our corpus output.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Iterator

SOURCE_DIR = pathlib.Path("/tmp/lxx-swete-eliran")

# Map Amicarelli/Eliran book abbreviations → our book codes.
# Versification uses 3-letter prefixes like "Gen.", "1Ma.", "Wis." etc.
BOOK_MAP: dict[str, str] = {
    "1Es": "1ES",
    "Tob": "TOB",
    "Tbs": "TOB_S",       # Tobit Sinaiticus (S-text) — separate in Swete
    "Jdt": "JDT",
    "Est": "ADE",
    "Wis": "WIS",
    "Sir": "SIR",
    "Bar": "BAR",
    "Epj": "LJE",         # Epistula Jeremiae
    "Sus": "ADA",         # Susanna OG
    "Sut": "ADA",         # Susanna Theodotion variant
    "Bel": "ADA",         # Bel OG
    "Bet": "ADA",         # Bel Theodotion variant
    "Dan": "ADA",         # Daniel OG
    "Dat": "ADA",         # Daniel Theodotion
    "1Ma": "1MA",
    "2Ma": "2MA",
    "3Ma": "3MA",
    "4Ma": "4MA",
}


@dataclass
class AmicarelliVerse:
    book_code: str
    chapter: int
    verse: int
    greek_text: str
    source_label: str


def is_available() -> bool:
    return (SOURCE_DIR / "00-Swete_versification.csv").exists() and \
           (SOURCE_DIR / "01-Swete_word_with_punctuations.csv").exists()


_WORD_CACHE: dict[int, str] | None = None
_VERSE_CACHE: list[tuple[int, str, int, int]] | None = None   # (start_wid, book_label, ch, vs)


def _load_words() -> dict[int, str]:
    out: dict[int, str] = {}
    path = SOURCE_DIR / "01-Swete_word_with_punctuations.csv"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            try:
                wid = int(parts[0])
            except ValueError:
                continue
            out[wid] = parts[1]
    return out


_REF_RE = re.compile(r"^([A-Za-z0-9]+)\.(\d+):(\d+)$")


def _load_verses() -> list[tuple[int, str, int, int]]:
    out: list[tuple[int, str, int, int]] = []
    path = SOURCE_DIR / "00-Swete_versification.csv"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            try:
                start = int(parts[0])
            except ValueError:
                continue
            m = _REF_RE.match(parts[1])
            if not m:
                continue
            book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
            out.append((start, book, ch, vs))
    return out


def _ensure_loaded():
    global _WORD_CACHE, _VERSE_CACHE
    if _WORD_CACHE is None:
        _WORD_CACHE = _load_words()
    if _VERSE_CACHE is None:
        _VERSE_CACHE = _load_verses()


def iter_verses(book_code: str) -> Iterator[AmicarelliVerse]:
    _ensure_loaded()
    assert _WORD_CACHE is not None and _VERSE_CACHE is not None

    # Which amicarelli labels map to this book_code?
    labels = {lbl for lbl, code in BOOK_MAP.items() if code == book_code}
    if not labels:
        return

    # Walk the verse map; emit verses whose book label matches.
    rows = _VERSE_CACHE
    for i, (start, lbl, ch, vs) in enumerate(rows):
        if lbl not in labels:
            continue
        if i + 1 < len(rows):
            end = rows[i + 1][0] - 1
        else:
            end = start
        if end < start:
            end = start
        words = []
        for wid in range(start, end + 1):
            w = _WORD_CACHE.get(wid)
            if w:
                words.append(w)
        if not words:
            continue
        greek = " ".join(words).strip()
        # Collapse double spaces, normalize whitespace around punctuation
        greek = re.sub(r"\s+([·,.;])", r"\1", greek)
        greek = re.sub(r"\s+", " ", greek)
        yield AmicarelliVerse(
            book_code=book_code,
            chapter=ch,
            verse=vs,
            greek_text=greek,
            source_label=lbl,
        )


def load_verse(book_code: str, chapter: int, verse: int) -> AmicarelliVerse | None:
    for v in iter_verses(book_code):
        if v.chapter == chapter and v.verse == verse:
            return v
    return None


if __name__ == "__main__":
    if not is_available():
        print("Swete-Amicarelli source not found at /tmp/lxx-swete-eliran")
        raise SystemExit(1)
    for book in ["LJE", "TOB", "JDT", "WIS", "SIR", "1MA", "2MA", "3MA", "4MA",
                 "BAR", "1ES", "ADE", "ADA"]:
        vs = list(iter_verses(book))
        chapters = set(v.chapter for v in vs)
        print(f"{book}: {len(vs)}v across {len(chapters)} chapters")
