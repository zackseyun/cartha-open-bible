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
  for feeding into draft.py. This is the NT/OT-compatible entry point.
- `parse_pages_to_verses(...)` — the underlying parser. Uses the
  running head of each page as the authoritative chapter signal and
  `_VERSE_MARKER_RE` for verse detection, with defenses against
  Swete's marginal line-number leaks.

## Parser limitations (V1)

The transcribed Swete corpus has some hard cases that V1 handles
imperfectly; document and translate around them rather than trust the
parser blindly:

1. **Tobit dual-recension pages** (TOB): Swete prints B-text (Codex
   Vaticanus) and S-text (Codex Sinaiticus) in parallel on the same
   page. The parser concatenates both into a single verse payload.
   Downstream consumers should split them before translating.
2. **Chapter boundaries on non-leading verse numbers**: Some chapters
   in 1 Esdras start at verses other than 1 due to Swete's printed
   line breaks, which makes reset-detection unreliable. Missing
   chapters and off-by-one verse starts should be expected; the
   `BOOK_CHAPTER_COUNT` ceiling prevents phantom chapters past the
   last real one.
3. **Pages outside the transcribed range**: Wisdom 1–3 and 1 Esdras
   1:1–22 are on pages not in the Phase 8 transcribed scope. Those
   verses will simply be missing from `iter_source_verses` output.
   Expand the page range and run the transcription pipeline to fill.

For production translation, spot-check the first verse of each
chapter against a known-good reference edition before drafting.

Page ranges are derived from the discovery probe run 2026-04-19 via
running-head analysis; see `sources/lxx/swete/transcribed/page_index.json`.
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
# translation/deuterocanon/ will be named. Ranges below are derived from
# Swete running-head probes 2026-04-19; adjust per-book as boundaries are
# confirmed in further passes.
DEUTEROCANONICAL_BOOKS: dict[str, tuple[int, int, int, str, str]] = {
    "1ES":   (2, 148, 178, "1 Esdras",                         "1_esdras"),
    "WIS":   (2, 626, 665, "Wisdom of Solomon",                "wisdom_of_solomon"),
    "SIR":   (2, 666, 771, "Sirach",                           "sirach"),
    "ADE":   (2, 772, 797, "Greek Esther",                     "greek_esther"),
    "JDT":   (2, 798, 831, "Judith",                           "judith"),
    "TOB":   (2, 832, 862, "Tobit",                            "tobit"),
    "BAR":   (3, 379, 397, "Baruch",                           "baruch"),
    # Greek Daniel additions: Swete prints OG and Theodotion Daniel in
    # parallel pages. Pr Azariah + Song of Three are embedded in Daniel 3
    # (pages within Daniel); Susanna and Bel are separately paged.
    "ADA":   (3, 542, 615, "Greek Additions to Daniel",        "greek_daniel"),
    "1MA":   (3, 617, 680, "1 Maccabees",                      "1_maccabees"),
    "2MA":   (3, 681, 733, "2 Maccabees",                      "2_maccabees"),
    "3MA":   (3, 734, 752, "3 Maccabees",                      "3_maccabees"),
    "4MA":   (3, 752, 789, "4 Maccabees",                      "4_maccabees"),
    "LJE":   (3, 895, 904, "Letter of Jeremiah",               "letter_of_jeremiah"),
    # Prayer of Manasseh + Psalm 151 are very small (a few verses each)
    # and live in the Odes appendix. Scan pages TBD — probe before
    # enqueueing drafts.
    "MAN":   (0, 0, 0, "Prayer of Manasseh",                   "prayer_of_manasseh"),
    "PS151": (0, 0, 0, "Psalm 151",                            "psalm_151"),
}

# Known chapter counts per book — used as a hard ceiling when parsing to
# catch line-number leaks that would otherwise fire spurious chapter
# boundaries past the last real chapter. Sources: Brenton LXX + Rahlfs.
BOOK_CHAPTER_COUNT: dict[str, int] = {
    "1ES": 9,
    "TOB": 14,
    "JDT": 16,
    "ADE": 10,     # includes Greek additions A-F as chapters 10-16 or
                   # inline; Swete uses Roman chapter numbers
    "WIS": 19,
    "SIR": 51,
    "BAR": 5,
    "LJE": 1,      # single chapter (70 verses)
    "ADA": 1,      # Pr Azariah/Song of Three/Susanna/Bel — numbered as
                   # one continuous block in many editions
    "1MA": 16,
    "2MA": 15,
    "3MA": 7,
    "4MA": 18,
    "MAN": 1,
    "PS151": 1,
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


# --- parser --------------------------------------------------------------

# Strip parenthesized line-number markers like "(25)", "(7)", "(60)".
_PAREN_LINENO_RE = re.compile(r"\(\s*\d+\s*\)\s*")
# Strip a leading lone `Β` siglum ("B text marker") at the very start of a
# line; it appears in Tobit and a few other books that print parallel
# recensions. Keep any real Greek word that happens to start with Β.
_LEADING_B_SIGLUM_RE = re.compile(r"(?m)^Β(?=\s+[^\sΒ])")
# Rejoin a trailing soft hyphen at end of line with the first token of the
# next line. Swete commonly breaks words with a hyphen-minus.
_HYPHEN_LINEBREAK_RE = re.compile(r"([Α-Ωα-ωἀ-ῼ])[-‐]\s*\n\s*")
# A verse-marker candidate: a run of one or more Arabic digits followed by a
# space and a Greek letter. We deliberately don't allow the digit to be
# preceded by another digit (rules out things like manuscript "87" etc).
_VERSE_MARKER_RE = re.compile(
    r"(?<![0-9])(?P<num>\d+)\s+(?P<word>[Α-Ωα-ωἀ-ῼ][^\s]*)"
)

# Inline chapter marker: Roman numeral (Latin I-M or Greek Ι/Χ) followed by
# verse `1` and an uppercase-starting Greek word. Example matches:
#   "Ι 1 ΒΙΒΛΟΣ"     (Tobit 1:1 start)
#   "II 1 Καὶ"       (chapter II start)
#   "ΙΧ 1 Τότε"     (chapter IX start)
# Anchored only at start-of-body or after whitespace.
_INLINE_CHAPTER_RE = re.compile(
    r"(?:(?<=\s)|^)"
    r"(?P<roman>[IVXLCDMΙΧ]{1,6})"
    r"\s+(?P<verse>1)\s+"
    r"(?P<word>[Α-Ω][^\s]*)"
)
# A line-number leak at the very start of a line: digit followed by space,
# where the same digit also appears as a real verse marker inline later on
# the same line.
_LINE_START_DIGIT_RE = re.compile(r"^(\d+)\s+(.*)$", re.MULTILINE)

# Roman-numeral parse table, including Swete's occasional Greek-letter
# transliterations like ΙΧ for IX.
_ROMAN_MAP = {
    "I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000,
    "Ι": 1, "Χ": 10,  # Greek iota/chi used in running heads
}

_RUNNING_HEAD_CHAPTER_RE = re.compile(
    r"(?:^|\s)([IVXLCDMΙΧ]+)\s+\d+\s*(?:$|\s)",
)


def roman_to_int(roman: str) -> int:
    r = roman.upper().replace("Ι", "I").replace("Χ", "X")
    total = 0
    prev = 0
    for c in reversed(r):
        v = _ROMAN_MAP.get(c, 0)
        if v == 0:
            return 0  # not a valid Roman numeral
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def parse_running_head_chapter(page_text: str) -> int | None:
    """Best-effort parse of the chapter number from a page's running head."""
    # Running head is between `[RUNNING HEAD]` and `[BODY]`.
    m = re.search(r"\[RUNNING HEAD\]\s*\n(.*?)\n\[BODY\]", page_text, re.DOTALL)
    if not m:
        return None
    head = m.group(1)
    rm = _RUNNING_HEAD_CHAPTER_RE.search(head)
    if not rm:
        return None
    return roman_to_int(rm.group(1)) or None


def clean_body_for_parsing(body: str) -> str:
    """Strip noise and rejoin hyphenated words. Returns single-line text.

    Order of operations matters: line-start dedup must run while the text
    is still multi-line, BEFORE the hyphen rejoin collapses everything.
    """
    # 1. Drop parenthesized line numbers (always noise)
    text = _PAREN_LINENO_RE.sub("", body)
    # 2. Drop leading B-text sigla at line start
    text = _LEADING_B_SIGLUM_RE.sub("", text)
    # 3. Remove line-start digit leaks that duplicate an inline verse marker
    #    (e.g. "26 τίου τῷ κυρίῳ. 26 καὶ ..." — first "26" is a line number).
    def dedupe_line(m: re.Match) -> str:
        digit, rest = m.group(1), m.group(2)
        inline = re.search(rf"(?<![0-9]){re.escape(digit)}\s+[Α-Ωα-ωἀ-ῼ]", rest)
        if inline:
            return rest
        return m.group(0)

    text = _LINE_START_DIGIT_RE.sub(dedupe_line, text)
    # 4. Rejoin hyphen-linebreaks — only NOW, after line-based dedup.
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1", text)
    # 5. Collapse whitespace (multiple spaces, newlines → single space)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _collect_pages(book_code: str) -> list[tuple[int, int | None, str]]:
    """Return [(scan_page, running_head_chapter, cleaned_body), ...]."""
    vol, first, last = book_page_range(book_code)
    out: list[tuple[int, int | None, str]] = []
    for scan_page, body in iter_transcribed_pages(book_code):
        page_path = transcribed_page_path(vol, scan_page)
        raw = page_path.read_text(encoding="utf-8")
        rh_chap = parse_running_head_chapter(raw)
        cleaned = clean_body_for_parsing(body)
        out.append((scan_page, rh_chap, cleaned))
    return out


def parse_pages_to_verses(
    book_code: str,
    *,
    debug: bool = False,
) -> Iterator[SwtVerse]:
    """Walk a book's transcribed pages and yield (chapter, verse, text).

    Chapter assignment is running-head-primary:
      - Each page's running head tells us the chapter whose content ends
        on that page (if the page straddles a chapter boundary, it's the
        later chapter).
      - On pages that span a chapter transition, the transition point is
        the first verse-number reset (a small number after a big one).

    Verse markers are detected by `_VERSE_MARKER_RE` after
    `clean_body_for_parsing` has rejoined hyphens and dropped most
    line-number noise. Remaining defenses inside the walk:

      - Ignore verse markers with numbers equal to or lower than the
        current verse (suspected line-number leaks) UNLESS the drop is
        to a small number and we're near a chapter boundary.
      - Cap chapters at `BOOK_CHAPTER_COUNT[book_code]`.
    """
    pages = _collect_pages(book_code)
    if not pages:
        return

    max_chap = BOOK_CHAPTER_COUNT.get(book_code, 999)

    # Initial chapter: prefer running head of first page.
    first_rh = pages[0][1]
    current_chapter: int = first_rh if first_rh else 1
    current_verse: int | None = None
    current_text: list[str] = []
    current_source_page: int | None = None

    def emit() -> SwtVerse | None:
        if current_verse is None or not current_text:
            return None
        txt = " ".join(current_text).strip()
        txt = re.sub(r"\s+([·,.;])", r"\1", txt)
        return SwtVerse(
            book_code=book_code,
            chapter=current_chapter,
            verse=current_verse,
            greek_text=txt,
            source_page=current_source_page,
        )

    for i, (scan_page, rh_chap, cleaned) in enumerate(pages):
        if not cleaned:
            continue

        # Running-head gives the last chapter that appears on this page.
        # If rh_chap > current_chapter, we expect a chapter transition
        # somewhere on this page.
        expected_max_chap = rh_chap if rh_chap else current_chapter

        # Pre-scan: find explicit inline chapter markers like "Ι 1 ΒΙΒΛΟΣ"
        # at the start of a chapter in Swete's body. These are deterministic
        # chapter-boundary signals when present.
        inline_chapter_starts: dict[int, int] = {}  # char pos → roman value
        for cm in _INLINE_CHAPTER_RE.finditer(cleaned):
            val = roman_to_int(cm.group("roman"))
            if val and val <= max_chap:
                inline_chapter_starts[cm.start()] = val

        cursor = 0
        for m in _VERSE_MARKER_RE.finditer(cleaned):
            verse_num = int(m.group("num"))
            tail = cleaned[cursor:m.start()].strip()
            if current_verse is not None and tail:
                current_text.append(tail)
            cursor = m.start() + len(m.group("num")) + 1

            # Did an inline chapter marker just occur before this verse?
            # (Scan for an inline chapter marker between previous cursor
            # and this marker's position.)
            forced_chap: int | None = None
            for pos, ch_val in inline_chapter_starts.items():
                if pos <= m.start() and pos >= cursor - 3:
                    # Within a small window right before this marker
                    forced_chap = ch_val
                    break

            if forced_chap is not None and forced_chap > current_chapter:
                v = emit()
                if v:
                    yield v
                current_chapter = forced_chap
                current_verse = verse_num
                current_source_page = scan_page
                current_text = []
                continue

            # Classify this marker:
            if current_verse is None:
                # First verse of the book
                current_verse = verse_num
                current_source_page = scan_page
                current_text = []
                continue

            is_small = verse_num <= 3
            is_reset = verse_num < current_verse
            big_jump = verse_num > current_verse + 30

            # Chapter advance condition: small reset AND we're behind the
            # running-head chapter for this page (or next), AND we haven't
            # hit max chapters yet.
            should_advance = (
                is_small
                and is_reset
                and current_chapter < max_chap
                and current_chapter < expected_max_chap
            )

            if should_advance:
                v = emit()
                if v:
                    yield v
                current_chapter += 1
                if rh_chap and current_chapter < rh_chap:
                    current_chapter = rh_chap
                current_verse = verse_num
                current_source_page = scan_page
                current_text = []
                continue

            if is_reset or verse_num == current_verse or big_jump:
                # Line-number leak — skip this marker; the already-appended
                # `tail` text stays with the current verse.
                continue

            # Normal forward-progression marker
            v = emit()
            if v:
                yield v
            current_verse = verse_num
            current_source_page = scan_page
            current_text = []

        # Tail of page — belongs to current verse
        tail = cleaned[cursor:].strip()
        if current_verse is not None and tail:
            current_text.append(tail)

        # If the page's running head says chapter X+1 but we exited the
        # page still in chapter X with a high verse number, we missed the
        # chapter transition (rare, but happens when reset marker was
        # itself a leak). Don't force-advance here — prefer missing a
        # chapter boundary over inserting a wrong one. Caller can clean up.

    v = emit()
    if v:
        yield v


def iter_source_verses(book_code: str) -> Iterator[SwtVerse]:
    """Yield SwtVerse instances for the whole book, in chapter/verse order.

    This is the entry point consumed by chapter_queue and chapter_worker,
    mirroring the sblgnt/wlc readers. The underlying parser walks the
    transcribed Swete pages, handles Swete-specific layout features
    (hyphenated line breaks, parenthesized marginal line numbers, B-text
    sigla), and emits one `SwtVerse` per (chapter, verse).
    """
    return parse_pages_to_verses(book_code)


def load_verse(book_code: str, chapter: int, verse: int) -> SwtVerse:
    for v in iter_source_verses(book_code):
        if v.chapter == chapter and v.verse == verse:
            return v
    raise LookupError(f"No verse {book_code} {chapter}:{verse} found in Swete")
