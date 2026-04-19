"""lxx_swete.py — Source reader for Swete LXX deuterocanonical books.

Mirrors the shape of sblgnt.py (NT from MorphGNT) and wlc.py (OT from
WLC) for the Phase 8 deuterocanonical corpus. The working source is the
page-level UTF-8 polytonic Greek produced by `tools/transcribe_source.py`
in `sources/lxx/swete/transcribed/vol{N}_p{PAGE:04d}.txt`, with
provenance sidecars alongside each page.

Exposes:

- `DEUTEROCANONICAL_BOOKS` — book code → metadata (title, Swete vol +
  scan-page range + book slug on disk).
- `book_page_range(book_code)` → (vol, first_scan_page, last_scan_page).
- `iter_transcribed_pages(book_code)` — yields (scan_page, body_text)
  tuples for each transcribed page belonging to the book, BODY section
  only (RUNNING HEAD + APPARATUS stripped).
- `iter_source_verses(book_code)` — yields SwtVerse instances suitable
  for feeding into draft.py. **Currently raises NotImplementedError**:
  building the Greek-chapter/verse parser is the next iteration. The
  ingredients are ready: every page we need is on disk as clean UTF-8
  polytonic Greek with inline chapter Roman numerals and Arabic verse
  digits; the parser has to walk them into a Verse stream.

Page ranges are derived from the discovery probe run 2026-04-18 and
recorded in `sources/lxx/swete/transcribed/page_index.json`. Keep the
two in sync — the JSON is the human-readable source-of-truth; this
module's BOOK dictionary is the programmatic handle.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
from typing import Iterator

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"

# (vol, first_scan_page, last_scan_page, title, directory_slug)
# The "directory_slug" is what the draft output directory under
# translation/deuterocanon/ will be named.
DEUTEROCANONICAL_BOOKS: dict[str, tuple[int, int, int, str, str]] = {
    "TOB":   (2, 843, 862, "Tobit",                            "tobit"),
    "JDT":   (2, 795, 840, "Judith",                           "judith"),
    "ADE":   (2, 785, 795, "Greek Esther",                     "greek_esther"),
    "WIS":   (2, 626, 665, "Wisdom of Solomon",                "wisdom_of_solomon"),
    "SIR":   (2, 668, 783, "Sirach",                           "sirach"),
    "BAR":   (3, 379, 398, "Baruch",                           "baruch"),
    "LJE":   (3, 895, 915, "Letter of Jeremiah",               "letter_of_jeremiah"),
    # Greek Daniel additions ship as a bundle. Pr Azariah + Song of Three
    # are embedded in Daniel 3 (pages 555-565 within Daniel Theodotion).
    # Susanna (pp. 598-608 OG) and Bel (pp. 610-615) are separately paged.
    "ADA":   (3, 555, 615, "Greek Additions to Daniel",        "greek_daniel"),
    "1ES":   (2, 148, 192, "1 Esdras",                         "1_esdras"),
    "1MA":   (3, 615, 680, "1 Maccabees",                      "1_maccabees"),
    "2MA":   (3, 680, 740, "2 Maccabees",                      "2_maccabees"),
    "3MA":   (3, 740, 752, "3 Maccabees",                      "3_maccabees"),
    "4MA":   (3, 752, 790, "4 Maccabees",                      "4_maccabees"),
    # Prayer of Manasseh + Psalm 151 are very small (a few verses each)
    # and live in the Odes appendix. Scan pages TBD — probe before
    # enqueueing drafts.
    "MAN":   (0, 0, 0, "Prayer of Manasseh",                   "prayer_of_manasseh"),
    "PS151": (0, 0, 0, "Psalm 151",                            "psalm_151"),
}


@dataclass
class SwtVerse:
    """A single verse loaded from the Swete transcription."""
    book_code: str
    chapter: int
    verse: int
    greek_text: str = ""
    source_page: int | None = None  # scan page the verse was parsed from
    translation: str = "lxx-swete-1909"

    @property
    def reference(self) -> str:
        title = DEUTEROCANONICAL_BOOKS[self.book_code][3]
        return f"{title} {self.chapter}:{self.verse}"

    @property
    def book_slug(self) -> str:
        return DEUTEROCANONICAL_BOOKS[self.book_code][4]

    @property
    def canonical_id(self) -> str:
        return f"{self.book_code}.{self.chapter}.{self.verse}"


def book_page_range(book_code: str) -> tuple[int, int, int]:
    """Return (volume, first_scan_page, last_scan_page) for a book."""
    if book_code not in DEUTEROCANONICAL_BOOKS:
        raise KeyError(f"Unknown deuterocanonical book: {book_code!r}")
    vol, first, last, _, _ = DEUTEROCANONICAL_BOOKS[book_code]
    if vol == 0:
        raise KeyError(f"{book_code!r} page range not yet discovered — probe Swete for it first")
    return vol, first, last


def transcribed_page_path(vol: int, scan_page: int) -> pathlib.Path:
    return TRANSCRIBED_DIR / f"vol{vol}_p{scan_page:04d}.txt"


_BODY_RE = re.compile(r"\[BODY\]\s*\n(.*?)(?=\n\[(?:APPARATUS|MARGINALIA|RUNNING HEAD|PLATE|BLANK)\]|\Z)", re.DOTALL)


def extract_body(page_text: str) -> str:
    """Return the concatenated BODY section(s) of a transcribed page.

    Swete pages occasionally contain multiple [BODY] blocks (e.g. Tobit,
    where the B and S recensions are printed in parallel columns and the
    transcriber emits them as two [BODY] sections). We concatenate them
    in order preserving their separation with a blank line.
    """
    bodies = [m.group(1).strip() for m in _BODY_RE.finditer(page_text)]
    return "\n\n".join(bodies).strip()


def iter_transcribed_pages(book_code: str) -> Iterator[tuple[int, str]]:
    """Yield (scan_page, body_text) for every transcribed page of a book."""
    vol, first, last = book_page_range(book_code)
    for pg in range(first, last + 1):
        path = transcribed_page_path(vol, pg)
        if not path.exists():
            continue
        body = extract_body(path.read_text(encoding="utf-8", errors="replace"))
        if body:
            yield pg, body


def iter_source_verses(book_code: str) -> Iterator[SwtVerse]:
    """Yield SwtVerse instances for the whole book.

    Not yet implemented — the parser that walks the transcribed Greek
    into chapter/verse structure needs its own iteration. Once the
    parser is in place, chapter_queue will be able to enumerate phase8
    jobs automatically, and draft.py will be able to consume this in
    the same shape it consumes sblgnt.iter_verses for NT books.
    """
    raise NotImplementedError(
        f"iter_source_verses({book_code!r}) — Greek verse parser not yet "
        "implemented. See tools/lxx_swete.py and DEUTEROCANONICAL.md "
        "Phase C. Transcribed Greek is available via iter_transcribed_pages()."
    )
