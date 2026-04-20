"""rahlfs.py — Rahlfs-Hanhart LXX text parser (NC-licensed, consultation only).

Reads Eliran Wong's LXX-Rahlfs-1935 digitization (cloned to /tmp by the
fetch helper) and exposes verses keyed by (book_code, chapter, verse).

License of source: CC-BY-NC-SA 4.0 (Eliran Wong repo, based on CCAT).
Our use: **research consultation only**. We pass verse text as a
reference input to the scan-grounded adjudicator, never redistribute it.
Our corpus output is independent OCR of Swete (public domain), not
derivative of this Rahlfs digitization.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Iterator

RAHLFS_DIR = pathlib.Path("/tmp/rahlfs-ref/12-Marvel.Bible")
VERSIFICATION_DIR = pathlib.Path("/tmp/rahlfs-ref/08_versification/ccat")

# Map Rahlfs book abbreviations (used in E-verse.csv) → our book codes
RAHLFS_TO_OUR: dict[str, str] = {
    "1Esdr": "1ES",
    "Tob": "TOB",      # we'll prefer S-text (GII = Sinaiticus) when both exist
    "TobBA": "TOB",    # Tobit B/A text (Vaticanus/Alexandrinus recension)
    "TobS": "TOB_S",   # Tobit S-text (Sinaiticus recension)
    "Jdt": "JDT",
    "AddEsth": "ADE",
    "Esth": "ADE",     # may or may not include Greek additions
    "1Mac": "1MA",
    "2Mac": "2MA",
    "3Mac": "3MA",
    "4Mac": "4MA",
    "Wis": "WIS",
    "Sir": "SIR",
    "Bar": "BAR",
    "EpJer": "LJE",
    "SusTh": "ADA",    # Susanna (Theodotion)
    "Sus": "ADA",      # Susanna (Old Greek)
    "BelTh": "ADA",    # Bel and the Dragon (Theodotion)
    "Bel": "ADA",      # Bel and the Dragon (OG)
    "DanTh": "ADA",    # Daniel Theodotion (includes Pr Azariah + Song of Three)
    "Dan": "ADA",      # Daniel OG
    "OdesSol": "ADA",  # Odes (includes Pr Azariah)
    "PrAzar": "ADA",   # Prayer of Azariah
    "SgThree": "ADA",  # Song of the Three Youths
}


@dataclass
class RahlfsVerse:
    book_code: str
    chapter: int
    verse: int
    greek_text: str
    source_book_label: str   # e.g. "TobS" or "Jdt"


def _load_word_text() -> dict[int, str]:
    """Return word_id -> accented Greek word (stripped of markup)."""
    path = RAHLFS_DIR / "01-text_accented.csv"
    out: dict[int, str] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            try:
                wid = int(parts[0])
            except ValueError:
                continue
            # Strip XML-like tags (<grk ...>word</grk>) to get the plain word
            raw = parts[1]
            m = re.search(r">([^<]+)<", raw)
            word = m.group(1) if m else raw.strip()
            out[wid] = word
    return out


def _load_verse_map() -> list[tuple[int, int, str, int, int]]:
    """Return list of (word_id_start, word_id_end, book_label, chapter, verse).

    E-verse.csv format: col1 = start_word_id for this verse. The next
    row's start - 1 determines this verse's end. Col2 is a metadata
    field (possibly an alignment index) that we ignore.

    Also handles single-chapter books where the ref is "Book V"
    without an explicit chapter number (e.g. EpJer).
    """
    path = VERSIFICATION_DIR / "E-verse.csv"
    out: list[tuple[int, int, str, int, int]] = []
    if not path.exists():
        return out
    # Accept either "Book CH:V" or "Book V" (single-chapter book).
    ref_re_chv = re.compile(r"「([^\s]+)\s+(\d+):(\d+)」")
    ref_re_v = re.compile(r"「([^\s]+)\s+(\d+)」")

    # First pass: collect (start_wid, book, chapter, verse) per row.
    rows: list[tuple[int, str, int, int]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            try:
                start = int(parts[0])
            except ValueError:
                continue
            m = ref_re_chv.search(parts[2])
            if m:
                book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
            else:
                m = ref_re_v.search(parts[2])
                if not m:
                    continue
                book = m.group(1)
                # Single-chapter book: treat as chapter 1, verse = number
                ch = 1
                vs = int(m.group(2))
            rows.append((start, book, ch, vs))

    # Second pass: derive end word-id from next row's start - 1.
    for i, (start, book, ch, vs) in enumerate(rows):
        if i + 1 < len(rows):
            next_start = rows[i + 1][0]
            end = next_start - 1
        else:
            end = start  # last verse: just include its start word
        # Guard against inconsistent data
        if end < start:
            end = start
        out.append((start, end, book, ch, vs))
    return out


_WORD_CACHE: dict[int, str] | None = None
_VERSE_MAP_CACHE: list[tuple[int, int, str, int, int]] | None = None


def _ensure_loaded():
    global _WORD_CACHE, _VERSE_MAP_CACHE
    if _WORD_CACHE is None:
        _WORD_CACHE = _load_word_text()
    if _VERSE_MAP_CACHE is None:
        _VERSE_MAP_CACHE = _load_verse_map()


def is_available() -> bool:
    return (RAHLFS_DIR / "01-text_accented.csv").exists() and (VERSIFICATION_DIR / "E-verse.csv").exists()


def iter_verses(book_code: str) -> Iterator[RahlfsVerse]:
    """Yield all Rahlfs verses for a given our-book-code.

    For Tobit, prefers the S-text (GII = Sinaiticus) if available,
    since that's what modern critical editions use. Falls back to the
    B/A text (TobBA) if only that's present.
    """
    _ensure_loaded()
    assert _WORD_CACHE is not None and _VERSE_MAP_CACHE is not None

    # Find which Rahlfs book labels map to this code
    our_labels = [lbl for lbl, code in RAHLFS_TO_OUR.items() if code == book_code]
    if not our_labels:
        return

    # Collect verses from matching books
    verses: list[tuple[str, int, int, str]] = []
    for start, end, lbl, ch, vs in _VERSE_MAP_CACHE:
        if lbl not in our_labels:
            continue
        # Concatenate words [start..end]
        words: list[str] = []
        for wid in range(start, end + 1):
            w = _WORD_CACHE.get(wid)
            if w:
                words.append(w)
        if not words:
            continue
        greek = " ".join(words)
        verses.append((lbl, ch, vs, greek))

    # For Tobit specifically, prefer TobS over TobBA when both exist for
    # the same (chapter, verse) — modern practice
    if book_code == "TOB":
        by_key: dict[tuple[int, int], tuple[str, str]] = {}
        for lbl, ch, vs, greek in verses:
            key = (ch, vs)
            # S-text wins when both available
            if key not in by_key or lbl == "TobS":
                by_key[key] = (lbl, greek)
        for (ch, vs), (lbl, greek) in sorted(by_key.items()):
            yield RahlfsVerse(book_code=book_code, chapter=ch, verse=vs,
                              greek_text=greek, source_book_label=lbl)
        return

    for lbl, ch, vs, greek in sorted(verses, key=lambda v: (v[1], v[2])):
        yield RahlfsVerse(book_code=book_code, chapter=ch, verse=vs,
                          greek_text=greek, source_book_label=lbl)


def load_verse(book_code: str, chapter: int, verse: int) -> RahlfsVerse | None:
    for v in iter_verses(book_code):
        if v.chapter == chapter and v.verse == verse:
            return v
    return None


if __name__ == "__main__":
    import sys
    if not is_available():
        print("Rahlfs source not found. Clone:")
        print("  git clone --depth 1 https://github.com/eliranwong/LXX-Rahlfs-1935 /tmp/rahlfs-ref")
        sys.exit(1)
    for book in ["LJE", "TOB", "JDT", "WIS", "SIR", "1MA", "2MA", "3MA", "4MA", "BAR", "1ES", "ADE", "ADA"]:
        vs = list(iter_verses(book))
        chapters = {}
        for v in vs:
            chapters.setdefault(v.chapter, 0)
            chapters[v.chapter] += 1
        print(f"{book}: {len(vs)}v across {len(chapters)} chapters")
