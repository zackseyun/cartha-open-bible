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
    "1ES":   (2, 146, 178, "1 Esdras",                         "1_esdras"),
    "WIS":   (2, 621, 665, "Wisdom of Solomon",                "wisdom_of_solomon"),
    "SIR":   (2, 666, 771, "Sirach",                           "sirach"),
    "ADE":   (2, 772, 797, "Greek Esther",                     "greek_esther"),
    "JDT":   (2, 798, 831, "Judith",                           "judith"),
    "TOB":   (2, 832, 862, "Tobit",                            "tobit"),
    "BAR":   (3, 379, 397, "Baruch",                           "baruch"),
    # Greek Daniel additions: Swete prints OG and Theodotion Daniel in
    # parallel pages. Pr Azariah + Song of Three are embedded in Daniel 3
    # (pages within Daniel); Susanna and Bel are separately paged.
    "ADA":   (3, 542, 615, "Greek Additions to Daniel",        "greek_daniel"),
    "1MA":   (3, 617, 684, "1 Maccabees",                      "1_maccabees"),
    "2MA":   (3, 685, 733, "2 Maccabees",                      "2_maccabees"),
    "3MA":   (3, 734, 752, "3 Maccabees",                      "3_maccabees"),
    "4MA":   (3, 752, 789, "4 Maccabees",                      "4_maccabees"),
    "LJE":   (3, 401, 407, "Letter of Jeremiah",               "letter_of_jeremiah"),
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
    source_pages: list[int] = field(default_factory=list)
    source_confidence: str | None = None
    source_validation: str | None = None
    source_warnings: list[str] = field(default_factory=list)
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


# Stop at any section tag, INCLUDING another [BODY] tag (Tobit pages
# occasionally print B-text and S-text blocks each with their own [BODY]
# header, and the second one must start a new match, not be body content).
_BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:BODY|APPARATUS|MARGINALIA|RUNNING HEAD|PLATE|BLANK)\]|\Z)",
    re.DOTALL,
)


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

# Strip parenthesized line-number markers like "(25)", "(7)", "(60)",
# "(1,2)" (compound indicators Swete uses on pages that split a verse
# across two printed lines), and "(1-2)" ranges.
_PAREN_LINENO_RE = re.compile(r"\(\s*\d+(?:\s*[,\-–]\s*\d+)*\s*\)\s*")
# Strip a lone `Β` siglum ("B text marker") at the start or end of a line
# (Swete's printed marginal marker for B-text lines in parallel recensions
# like Tobit). Keep any real Greek word that happens to start with Β.
_LEADING_B_SIGLUM_RE = re.compile(r"(?m)^Β(?=\s+[^\sΒ])")
_TRAILING_B_SIGLUM_RE = re.compile(r"(?m)\s+Β\s*$")
# Rejoin a trailing soft hyphen at end of line with the first token of the
# next line. Swete commonly breaks words with a hyphen-minus.
_HYPHEN_LINEBREAK_RE = re.compile(r"([Α-Ωα-ωἀ-ῼ])[-‐]\s*\n\s*")
# A verse-marker candidate: a run of one or more Arabic digits followed by a
# space and a Greek letter. We deliberately don't allow the digit to be
# preceded by another digit (rules out things like manuscript "87" etc).
_VERSE_MARKER_RE = re.compile(
    r"(?<![0-9])(?P<num>\d+)\s+(?P<word>[Α-Ωα-ωἀ-ῼ][^\s]*)"
)

# Explicit inline chapter marker: Roman numeral (Latin I-M or Greek Ι/Χ)
# followed by verse `1` and an uppercase-starting Greek word. Example:
#   "Ι 1 ΒΙΒΛΟΣ"     (Tobit 1:1 start)
#   "II 1 Καὶ"       (chapter II start)
_INLINE_CHAPTER_EXPLICIT_RE = re.compile(
    r"(?:(?<=\s)|^)"
    r"(?P<roman>[IVXLCDMΙΧ]{1,6})"
    r"\s+1\s+"
    r"(?P<word>[Α-Ω][^\s]*)"
)

# Implicit inline chapter marker: Roman numeral followed DIRECTLY by an
# uppercase Greek word (no explicit "1"). Swete uses this for some
# chapters; the implicit verse 1 is followed shortly by a "2 " verse
# marker. Example: "I Καὶ λυπηθεὶς ... 2 Δίκαιος".
_INLINE_CHAPTER_IMPLICIT_RE = re.compile(
    r"(?:(?<=\s)|^)"
    r"(?P<roman>[IVXLCDMΙΧ]{1,6})"
    r"\s+(?P<word>[Α-Ω][^\s]{2,})"
)

# Kept for backward compatibility with any external callers that import
# the original name.
_INLINE_CHAPTER_RE = _INLINE_CHAPTER_EXPLICIT_RE
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
# Fallback: any Roman numeral in the running head when no accompanying
# Arabic verse number is present (e.g. "II II ΤΩΒΕΙΤ" or "III I ΕΣΔΡΑΣ Α").
_RUNNING_HEAD_ROMAN_ONLY_RE = re.compile(
    r"(?:^|\s)([IVXLCDMΙΧ]{1,6})(?=\s|$)",
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
    """Best-effort parse of the chapter number from a page's running head.

    Tries two patterns in order:
      1. Roman numeral + Arabic verse (e.g. "II 7" — chapter II verse 7).
      2. Bare Roman numeral anywhere in head (e.g. "II II ΤΩΒΕΙΤ" where the
         book title got interleaved with the running chapter number).
    """
    m = re.search(r"\[RUNNING HEAD\]\s*\n(.*?)\n\[BODY\]", page_text, re.DOTALL)
    if not m:
        return None
    head = m.group(1)
    rm = _RUNNING_HEAD_CHAPTER_RE.search(head)
    if rm:
        v = roman_to_int(rm.group(1))
        if v:
            return v
    # Fallback: find the highest Roman numeral anywhere in the head.
    # Running heads often have the chapter number appearing once as a
    # bare Roman (in the "verse" position the Roman took over from the
    # usual "Roman + Arabic" pair).
    #
    # NOTE: No Apocryphal book has more than ~51 chapters (Sirach); cap
    # at 30 to reject spurious matches where single Latin letters C or D
    # get read as Roman 100 / 500 (Greek Esther's chapter-letter labels
    # A, B, C, D, E, F are the canonical case).
    best = 0
    for rm2 in _RUNNING_HEAD_ROMAN_ONLY_RE.finditer(head):
        roman = rm2.group(1)
        # Reject bare single-letter C or D (chapter letters in Greek Esther).
        if roman in ("C", "D"):
            continue
        v = roman_to_int(roman)
        if v and 1 <= v <= 30:
            best = max(best, v)
    return best or None


def clean_body_for_parsing(body: str) -> str:
    """Strip noise and rejoin hyphenated words. Returns single-line text.

    Order of operations matters: line-start dedup must run while the text
    is still multi-line, BEFORE the hyphen rejoin collapses everything.
    """
    # 1. Drop parenthesized line numbers (always noise)
    text = _PAREN_LINENO_RE.sub("", body)
    # 2. Drop lone Β sigla at start or end of lines (Swete's B-text
    #    recension marker — not part of the actual Greek text).
    text = _LEADING_B_SIGLUM_RE.sub("", text)
    text = _TRAILING_B_SIGLUM_RE.sub("", text)
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
    """Return [(scan_page, running_head_chapter, cleaned_body), ...].

    For Tobit, strip the S-text (Sinaiticus) recension block and keep
    only the B-text (Vaticanus) — the primary translation base.
    """
    vol, first, last = book_page_range(book_code)
    out: list[tuple[int, int | None, str]] = []
    for scan_page, body in iter_transcribed_pages(book_code):
        page_path = transcribed_page_path(vol, scan_page)
        raw = page_path.read_text(encoding="utf-8")
        rh_chap = parse_running_head_chapter(raw)
        if book_code == "TOB":
            body = split_tobit_b_text(body)
        cleaned = clean_body_for_parsing(body)
        out.append((scan_page, rh_chap, cleaned))
    return out


# --- Tobit dual-recension splitter --------------------------------------

# Distinctive markers of the S-text (Codex Sinaiticus) recension of Tobit.
# Swete prints S-text as a second block on Tobit pages, separated from the
# B-text block by a blank line. S-text uses the "Τωβειθ/Τωβιθ" spellings
# (θ-final) where B-text uses "Τωβείτ" (τ-final), and references the
# Sinaiticus manuscript with the Hebrew ALEF character א (U+05D0).
_TOBIT_S_TEXT_SIGNALS = ("Τωβειθ", "Τωβιθ", "\u05D0", "ℵ")


def split_tobit_b_text(body: str) -> str:
    """Drop Tobit's S-text (Sinaiticus) block and return only B-text.

    Swete consistently prints B-text ABOVE S-text on Tobit pages with a
    blank line between. Discriminators, in order of specificity:

      1. **Content signals** (Τωβειθ, Hebrew ALEF א, ℵ) — distinctive
         Sinaiticus spellings/sigla. Drop any block that has them.
      2. **Verse-number restart** — if block B's first verse marker is
         substantially lower than block A's last verse marker, block B
         is an S-text restart (same content, different recension).
      3. **B-text continuation across blocks** — if block B's first
         verse marker continues smoothly from block A's last, the two
         are both B-text (just a paragraph break). Keep both.
    """
    blocks = re.split(r"\n\s*\n+", body)
    if len(blocks) == 1:
        return body

    # Pass 1: content signals
    kept: list[str] = []
    for b in blocks:
        if not any(sig in b for sig in _TOBIT_S_TEXT_SIGNALS):
            kept.append(b)
    # If content filter dropped any blocks, we trust it.
    if len(kept) < len(blocks) and kept:
        return "\n\n".join(kept)

    # Pass 2: verse-number-restart detection on consecutive block pairs.
    # Walk blocks in order; stop when we detect an S-text restart UNLESS
    # the new block opens with an explicit chapter-start marker (Roman
    # numeral), which indicates a within-page chapter transition
    # (legitimate B-text continuation in a new chapter).
    def first_verse(block: str) -> int | None:
        m = _VERSE_MARKER_RE.search(block[:200])
        return int(m.group("num")) if m else None

    def last_verse(block: str) -> int | None:
        matches = list(_VERSE_MARKER_RE.finditer(block))
        return int(matches[-1].group("num")) if matches else None

    def opens_with_chapter_marker(block: str) -> bool:
        # Matches patterns like "IV 1 Ἐν", "IV (1,2) 1 Ἐν", "V Ἀλλʼ",
        # or bare "I " followed by capital Greek word (implicit verse 1).
        stripped = block.lstrip()
        # Strip Β siglum if present
        if stripped.startswith("Β ") or stripped.startswith("Β\n"):
            stripped = stripped[2:]
        stripped = stripped.lstrip()
        pat = re.compile(r"^[IVXLCDMΙΧ]{1,6}\s+(?:\(\d+(?:,\s*\d+)?\)\s*)?(?:\d+\s+)?[Α-Ω]")
        return bool(pat.match(stripped))

    b_text_blocks = [blocks[0]]
    for b in blocks[1:]:
        prev_last = last_verse(b_text_blocks[-1])
        this_first = first_verse(b)
        # If block opens with an explicit chapter marker, it's new-chapter
        # B-text. Keep it.
        if opens_with_chapter_marker(b):
            b_text_blocks.append(b)
            continue
        if prev_last is None or this_first is None:
            # Can't determine; conservatively drop.
            break
        # If this block's first verse is materially lower than the prev's
        # last verse, it's an S-text restart. Drop.
        if this_first < prev_last - 3:
            break
        # Otherwise, B-text continuation. Keep.
        b_text_blocks.append(b)

    return "\n\n".join(b_text_blocks)


def _scan_chapter_boundaries(
    book_code: str, pages: list[tuple[int, int | None, str]]
) -> list[tuple[int, int, int, bool]]:
    """Pre-scan: determine chapter boundary positions by combining
    running-head chapter deltas with text-level pattern detection.

    Returns a sorted list of (scan_page, position_in_cleaned_body,
    chapter_number, implicit_verse_1) tuples.

    Strategy:
      1. Walk pages forward. Track the last seen running-head chapter.
      2. When a page's rh_chap > last seen, one or more chapter
         transitions happen on this page. For each new chapter, try to
         locate its start position via:
           a. Explicit marker `Ι 1 Word` for the new chapter's Roman
              numeral (anywhere on this page).
           b. Implicit marker `<ROMAN> Word` preceded by a verse-reset
              or at the text-start.
           c. Fallback: position of the first small verse-reset (1..3).
      3. If we can't locate, record the page-start position as best guess.
    """
    max_chap = BOOK_CHAPTER_COUNT.get(book_code, 999)
    boundaries: list[tuple[int, int, int, bool]] = []

    def find_explicit(cleaned: str, chapter: int, after_pos: int = 0) -> int | None:
        # Roman numeral string for chapter
        roman_candidates = _int_to_roman_variants(chapter)
        for roman in roman_candidates:
            pat = re.compile(
                r"(?:(?<=\s)|^)"
                + re.escape(roman)
                + r"\s+1\s+[Α-Ω][^\s]*"
            )
            m = pat.search(cleaned, pos=after_pos)
            if m:
                return m.start()
        return None

    def find_implicit(cleaned: str, chapter: int, after_pos: int = 0) -> int | None:
        """Find a bare-Roman chapter-start marker (implicit verse 1)."""
        roman_candidates = _int_to_roman_variants(chapter)
        for roman in roman_candidates:
            pat = re.compile(
                r"(?:(?<=\s)|^)"
                + re.escape(roman)
                + r"\s+[Α-Ω][^\s]{2,}"
            )
            for m in pat.finditer(cleaned, pos=after_pos):
                # Require a nearby "2 Greek" verse marker within 400 chars
                # (since implicit verse 1 is followed by explicit verse 2).
                nearby = cleaned[m.end(): m.end() + 400]
                if re.search(r"(?<!\d)\b2\s+[Α-Ωα-ωἀ-ῼ]", nearby):
                    return m.start()
        return None

    def find_verse_reset(cleaned: str, after_pos: int = 0) -> int | None:
        """Find the first verse-reset (marker with num ≤ 3) that follows
        a marker with num ≥ 10 earlier on the page."""
        markers = list(_VERSE_MARKER_RE.finditer(cleaned, pos=after_pos))
        if not markers:
            return None
        for i in range(1, len(markers)):
            prev = int(markers[i - 1].group("num"))
            cur = int(markers[i].group("num"))
            if prev >= 10 and cur <= 3:
                return markers[i].start()
        return None

    # Strategy: walk running-head deltas. For each transition rh=N → rh=M,
    # record M-N chapter boundaries. Each boundary gets its POSITION from
    # (a) explicit marker if it exists anywhere in prev+current pages, or
    # (b) verse-reset on prev or current page.

    def all_verse_resets(cleaned: str) -> list[int]:
        """Return positions in `cleaned` where a verse-reset happens
        (marker with num ≤ 3 after a marker with num ≥ 10)."""
        markers = list(_VERSE_MARKER_RE.finditer(cleaned))
        positions = []
        for i in range(1, len(markers)):
            prev = int(markers[i - 1].group("num"))
            cur = int(markers[i].group("num"))
            if prev >= 10 and cur <= 3:
                positions.append(markers[i].start())
        return positions

    page_list = pages
    last_rh: int | None = None
    last_page_idx: int | None = None

    # --- Chapter-1 seeding ---
    # Many Apocryphal books in Swete have a title-only first page, so no
    # running head ever shows chapter 1. Seed chapter 1 at position 0 of
    # the first page with content, so the walk starts there.
    first_content_page = None
    for idx, (sp, rh, cl) in enumerate(page_list):
        if cl:
            first_content_page = (idx, sp, rh, cl)
            break
    if first_content_page is not None:
        _idx, _sp, _rh, _cl = first_content_page
        # Try explicit/implicit marker for chapter 1 first
        pos = find_explicit(_cl, 1) or find_implicit(_cl, 1)
        if pos is None:
            # No marker — seed at position 0
            pos = 0
        boundaries.append((_sp, pos, 1, pos > 0))  # implicit if seeded

    for idx, (scan_page, rh_chap, cleaned) in enumerate(page_list):
        if rh_chap is None:
            continue

        if last_rh is None:
            last_rh = rh_chap
            last_page_idx = idx
            continue

        delta = rh_chap - last_rh
        if delta > 0:
            # We have `delta` chapter transitions straddling prev+current.
            # Include ALL intermediate pages (those with rh=None which my
            # scanner skipped) in the search, because the transition might
            # actually happen on one of those unlabeled pages.
            prev_pages: list[tuple[int, str]] = []
            if last_page_idx is not None:
                for j in range(last_page_idx, idx):
                    pj, rj, cj = page_list[j]
                    prev_pages.append((pj, cj))

            candidates: list[tuple[int, int, int | None, bool]] = []

            # Explicit markers on all candidate pages (prev + current)
            all_search_pages: list[tuple[int, str]] = prev_pages + [(scan_page, cleaned)]
            for new_ch in range(last_rh + 1, rh_chap + 1):
                if new_ch > max_chap:
                    break
                for pg, cl in all_search_pages:
                    pos = find_explicit(cl, new_ch)
                    if pos is not None:
                        candidates.append((pg, pos, new_ch, False))
            # Verse-resets on all candidate pages
            for pg, cl in all_search_pages:
                for pos in all_verse_resets(cl):
                    candidates.append((pg, pos, None, True))

            # Sort candidates by (page, position) — forward order
            candidates.sort(key=lambda c: (c[0], c[1]))

            # Assign the first `delta` candidates to chapters last_rh+1..rh_chap.
            # If a candidate has an explicit chapter hint, use it.
            needed = list(range(last_rh + 1, min(rh_chap + 1, max_chap + 1)))
            used_positions: set[tuple[int, int]] = set()
            for pg, pos, hint, implicit in candidates:
                if (pg, pos) in used_positions:
                    continue
                if not needed:
                    break
                if hint is not None:
                    # Explicit marker: assign this chapter specifically
                    if hint in needed:
                        boundaries.append((pg, pos, hint, implicit))
                        needed.remove(hint)
                        used_positions.add((pg, pos))
                else:
                    # Implicit: take the lowest needed chapter
                    ch = needed.pop(0)
                    boundaries.append((pg, pos, ch, implicit))
                    used_positions.add((pg, pos))

        last_rh = rh_chap
        last_page_idx = idx

    # De-dup and sort
    unique = sorted(set(boundaries), key=lambda b: (b[0], b[1]))
    return unique


def _int_to_roman_variants(n: int) -> list[str]:
    """Return Swete's variant Roman-numeral spellings for `n`.

    Swete uses both Latin letters (I, V, X, L) and occasional Greek
    transliterations (Ι for I, Χ for X, especially in running heads).
    Returns a list ordered by likelihood.
    """
    if n <= 0 or n > 99:
        return []
    # Standard Latin Roman
    digits_latin = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"),  (90,  "XC"), (50,  "L"), (40,  "XL"),
        (10,  "X"),  (9,   "IX"), (5,   "V"), (4,   "IV"),
        (1,   "I"),
    ]
    roman = ""
    m = n
    for val, sym in digits_latin:
        while m >= val:
            roman += sym
            m -= val
    variants = [roman]
    # Greek-letter variant (Ι instead of I, Χ instead of X)
    greek = roman.replace("I", "Ι").replace("X", "Χ")
    if greek != roman:
        variants.append(greek)
    return variants


def parse_pages_to_verses(
    book_code: str,
    *,
    debug: bool = False,
) -> Iterator[SwtVerse]:
    """Walk a book's transcribed pages and yield (chapter, verse, text).

    Two-phase design:

    Phase 1 — pre-scan: find all explicit inline chapter markers
      (`Ι 1 ΒΙΒΛΟΣ`-style). These are authoritative chapter-boundary
      positions.

    Phase 2 — walk: for each verse marker, determine its chapter by
      looking up the most recent boundary position. If no boundary has
      been seen yet (before chapter 1's explicit marker), fall back to
      the running-head chapter or chapter 1.

    Defenses inside the walk:
      - Ignore verse markers with numbers equal to or lower than the
        current verse (suspected line-number leaks).
      - Ignore huge forward jumps (>30) — almost always line-number
        leaks from Swete's marginal typography.
    """
    pages = _collect_pages(book_code)
    if not pages:
        return

    max_chap = BOOK_CHAPTER_COUNT.get(book_code, 999)
    boundaries = _scan_chapter_boundaries(book_code, pages)

    # Build a lookup: (scan_page, position) → (chapter, implicit_v1).
    boundaries_by_page: dict[int, list[tuple[int, int, bool]]] = {}
    for pg, pos, ch, implicit in boundaries:
        boundaries_by_page.setdefault(pg, []).append((pos, ch, implicit))

    # Initial chapter: if the first boundary is on the first page, use it.
    # Otherwise prefer running head of first page.
    first_rh = pages[0][1]
    if boundaries and boundaries[0][0] == pages[0][0]:
        current_chapter: int = boundaries[0][2]
    elif first_rh:
        current_chapter = first_rh
    else:
        current_chapter = 1

    current_verse: int | None = None
    current_text: list[str] = []
    current_source_page: int | None = None

    def emit() -> SwtVerse | None:
        if current_verse is None or not current_text:
            return None
        txt = " ".join(current_text).strip()
        # Rejoin hyphens that were left across page-block boundaries
        # (e.g. "πορευ- θεὶς" → "πορευθεὶς").
        txt = re.sub(r"([Α-Ωα-ωἀ-ῼ])[-‐]\s+([Α-Ωα-ωἀ-ῼ])", r"\1\2", txt)
        # Collapse whitespace before punctuation
        txt = re.sub(r"\s+([·,.;])", r"\1", txt)
        # Normalize multiple spaces
        txt = re.sub(r"\s+", " ", txt)
        return SwtVerse(
            book_code=book_code,
            chapter=current_chapter,
            verse=current_verse,
            greek_text=txt,
            source_page=current_source_page,
        )

    for scan_page, rh_chap, cleaned in pages:
        if not cleaned:
            continue
        page_boundaries = boundaries_by_page.get(scan_page, [])
        consumed_boundaries: set[int] = set()  # positions already fired

        # Handle implicit-verse-1 boundaries BEFORE verse-marker walk: for
        # each implicit boundary on this page, emit a verse-1 immediately
        # at that position (then verse-marker walk picks up "2", "3", …).
        # We do this inline during the walk below by checking boundaries
        # that have NO verse marker near them.

        cursor = 0
        for m in _VERSE_MARKER_RE.finditer(cleaned):
            verse_num = int(m.group("num"))

            # Check for a chapter boundary crossed between cursor and
            # this marker position.
            crossed_boundary: int | None = None
            crossed_implicit = False
            crossed_pos: int | None = None
            for pos, ch, implicit in page_boundaries:
                if pos in consumed_boundaries:
                    continue
                if cursor <= pos <= m.start():
                    crossed_boundary = ch
                    crossed_implicit = implicit
                    crossed_pos = pos

            tail = cleaned[cursor:m.start()].strip()

            if crossed_boundary is not None and crossed_boundary > current_chapter:
                # Chapter transition. Two cases:
                #  (a) Explicit marker (e.g. "IV 1 Καὶ"): the next verse
                #      marker IS the new chapter's verse 1.
                #  (b) Implicit marker (e.g. "I Καὶ ... 2 Δίκαιος"): there
                #      is no explicit "1" — everything between the boundary
                #      and the next marker IS verse 1.
                if crossed_implicit and crossed_pos is not None:
                    pre_bound = cleaned[cursor:crossed_pos].strip()
                    post_bound = cleaned[crossed_pos:m.start()].strip()
                    # Finish previous verse with text up to the boundary
                    if current_verse is not None and pre_bound:
                        current_text.append(pre_bound)
                    v = emit()
                    if v:
                        yield v
                    # Emit the implicit verse 1 immediately
                    current_chapter = crossed_boundary
                    current_verse = 1
                    current_source_page = scan_page
                    current_text = [post_bound] if post_bound else []
                    if verse_num > 1:
                        v1 = emit()
                        if v1:
                            yield v1
                        current_verse = verse_num
                        current_text = []
                    if crossed_pos is not None:
                        consumed_boundaries.add(crossed_pos)
                    cursor = m.start() + len(m.group("num")) + 1
                    continue
                # Explicit chapter marker — emit previous, start fresh
                if current_verse is not None and tail:
                    current_text.append(tail)
                v = emit()
                if v:
                    yield v
                current_chapter = crossed_boundary
                current_verse = verse_num
                current_source_page = scan_page
                current_text = []
                # If the explicit marker's verse is > 1, there's still an
                # implicit verse 1 before it (e.g. chapter start via
                # "IV" without explicit "1"). Emit verse 1 with just the
                # pre-marker tail (if any).
                if verse_num > 1 and crossed_pos is not None:
                    pre_marker = cleaned[crossed_pos:m.start()].strip()
                    # Strip the Roman numeral itself
                    pre_marker = re.sub(r"^[IVXLCDMΙΧ]+\s+", "", pre_marker)
                    if pre_marker:
                        current_verse = 1
                        current_text = [pre_marker]
                        v1 = emit()
                        if v1:
                            yield v1
                        current_verse = verse_num
                        current_text = []
                if crossed_pos is not None:
                    consumed_boundaries.add(crossed_pos)
                cursor = m.start() + len(m.group("num")) + 1
                continue

            if current_verse is not None and tail:
                current_text.append(tail)
            cursor = m.start() + len(m.group("num")) + 1

            if current_verse is None:
                # First verse of the book
                current_verse = verse_num
                current_source_page = scan_page
                current_text = []
                if debug:
                    print(f"[init] ch={current_chapter} v={verse_num} (p{scan_page})")
                continue

            is_reset = verse_num < current_verse
            is_small_reset = is_reset and verse_num <= 3
            big_jump = verse_num > current_verse + 30
            expected_max_chap = rh_chap if rh_chap else current_chapter

            # Chapter advance via verse-reset fallback (only when no
            # explicit inline chapter marker has fired yet for this
            # chapter, and the reset is small AND we're behind the
            # running-head chapter).
            if (
                is_small_reset
                and current_chapter < max_chap
                and current_chapter < expected_max_chap
            ):
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
                # Line-number leak — drop this marker, keep the tail text
                # with the current verse (already appended above).
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

    v = emit()
    if v:
        yield v


FINAL_CORPUS_DIR = (
    REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated"
)
NORMALIZED_CORPUS_DIR = (
    REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_normalized"
)


def _load_final_corpus(book_code: str) -> list[SwtVerse] | None:
    """Load the book's verses from the hybrid final corpus (JSONL) if
    available. Returns None if the book isn't in the final corpus."""
    import json as _json
    path = NORMALIZED_CORPUS_DIR / f"{book_code}.jsonl"
    translation_label = "swete-1909-normalized"
    if not path.exists():
        path = FINAL_CORPUS_DIR / f"{book_code}.jsonl"
        translation_label = "swete-1909-adjudicated"
    if not path.exists():
        return None
    out: list[SwtVerse] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = _json.loads(line)
            out.append(
                SwtVerse(
                    book_code=rec["book"],
                    chapter=int(rec["chapter"]),
                    verse=int(rec["verse"]),
                    greek_text=rec["greek"],
                    source_page=(
                        rec.get("source_page")
                        or (rec.get("source_pages") or [None])[0]
                    ),
                    source_pages=list(rec.get("source_pages") or []),
                    source_confidence=(
                        (rec.get("adjudication") or {}).get("confidence")
                        or ("high" if rec.get("validation") == "agree" else None)
                    ),
                    source_validation=rec.get("validation"),
                    source_warnings=_source_warnings_for_record(rec),
                    translation=translation_label,
                )
            )
    return out


def _source_warnings_for_record(rec: dict) -> list[str]:
    warnings: list[str] = []
    book = str(rec.get("book") or "")
    chapter = int(rec.get("chapter") or 0)
    verse = int(rec.get("verse") or 0)
    if book == "BAR" and chapter == 5 and verse >= 10:
        warnings.append(
            "Known numbering contamination: BAR 5:10-66 currently spills into Lamentations material and should not be drafted until normalized."
        )

    if book == "WIS" and chapter == 19 and verse >= 28:
        warnings.append(
            "Known numbering contamination: WIS 19:28-30 currently reflects adjacent Sirach material and should not be drafted until normalized."
        )

    return warnings


def iter_source_verses(book_code: str) -> Iterator[SwtVerse]:
    """Yield SwtVerse instances for the whole book, in chapter/verse order.

    Uses the hybrid final corpus (our OCR + First1KGreek calibration)
    when available; falls back to the raw OCR parser otherwise.

    Consumed by chapter_queue and chapter_worker, mirroring the
    sblgnt/wlc readers.
    """
    final = _load_final_corpus(book_code)
    if final is not None:
        for v in final:
            yield v
        return
    yield from parse_pages_to_verses(book_code)


def load_verse(book_code: str, chapter: int, verse: int) -> SwtVerse:
    for v in iter_source_verses(book_code):
        if v.chapter == chapter and v.verse == verse:
            return v
    raise LookupError(f"No verse {book_code} {chapter}:{verse} found in Swete")
