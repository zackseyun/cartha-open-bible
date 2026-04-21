"""verse_parser.py — parse Jubilees OCR into verse records.

Charles 1895 Ethiopic Book of Jubilees prints verse numerals in the
**right margin** of the page, placed at the line where each verse
STARTS. Our Gemini 3.1 Pro OCR captures this layout by putting the
Ge'ez numeral at the end of the line where the verse begins.

Example OCR line sequence (Jubilees 1:1-2 opening):

    ወኮነ፡ በቀዳማይ፡ ዓመት፡ በፀአቶሙ፡ ለደቂቀ፡ እስራኤል፡ ...    ፩
    አመ፡ ዐሡሩ፡ ወስዱሱ፡ ለውእቱ፡ ወርኅ፡ ... እንዘ፡ ይብል፡
    ዕረግ፡ ኀቤየ፡ ውስተ፡ ደብር፡ ... ዘሕግ፡ ወዘትእዛዝ፡
    ዘመጠነ፡ ጸሐፍኩ፡ ታስብዎሙ። ወዐርገ፡ ሙሴ፡ ውስተ፡ ደብረ፡ ...  ፪

- ፩ at end of line 1 means "verse 1 starts somewhere on line 1"
- ፪ at end of line 4 means "verse 2 starts somewhere on line 4"
- Text for verse 1 is line 1 FROM the apparent verse start through
  to the verse-2 marker position on line 4.

The parser runs in two stages:

1. **Extract verse markers** — find Ge'ez numerals at end of lines
   (possibly preceded by whitespace). Record (line_index,
   verse_number) pairs.

2. **Slice verse bodies** — for consecutive markers (N, M):
   the body of verse N is everything from just after marker N-1
   (exclusive) through marker M's line start. For the first verse
   on a page, the body starts at the beginning of the marked line
   (verse numerals in Charles 1895 are ALWAYS at the end of the
   line where the verse starts, never mid-line).

   For the last marked verse on a page, the body runs through the
   end of the page's text.

This is distinct from the `tools/ethiopic/verse_parser.py` pattern
used for Charles 1906 Enoch, which has verse numerals inline BEFORE
the verse body. Charles 1895 Jubilees uses the OPPOSITE convention
(numerals after, marginal).

Apparatus markers captured by the OCR — superscript digits (¹²³⁴⁵...)
referencing apparatus footnotes and `*` / `'` variant-scope delimiters
— are stripped from the body text before verse-indexing, since they
are not part of the main text.

Prologue handling: The first "verse" of Jubilees 1 is actually a
prologue paragraph with no verse number. If the OCR page contains
text before the first marker, we emit that as verse 0 ("prologue")
to preserve it without misattributing it to verse 1 (which was the
2.5 Pro failure mode).
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, asdict
from typing import Iterator

# Ge'ez numerals 1-999. The 4-digit range would be overkill for verse numbers.
# Compound forms like ፲ወ፮ (16) = "10 + 6" are handled by the parser.
_ETH_DIGIT_MAP = {
    "፩": 1, "፪": 2, "፫": 3, "፬": 4, "፭": 5, "፮": 6, "፯": 7, "፰": 8, "፱": 9,
    "፲": 10, "፳": 20, "፴": 30, "፵": 40, "፶": 50, "፷": 60, "፸": 70, "፹": 80,
    "፺": 90, "፻": 100,
}
_ETH_DIGIT_CHARS = "".join(_ETH_DIGIT_MAP.keys())

# Match a Ge'ez numeral at the END of a line (possibly with trailing whitespace).
# The numeral may be compound, e.g. ፲ወ፮ (sixteen), with `ወ` ("and") joining digits.
_VERSE_MARKER_RE = re.compile(
    rf"(^|\s)(?P<marker>[{_ETH_DIGIT_CHARS}](?:[ወ፡]*[{_ETH_DIGIT_CHARS}])*)\s*$"
)

# Superscript footnote markers (Unicode superscripts ² ³ ... and regular digits
# used as superscripts in the OCR, plus the `*` and `'` variant delimiters)
_APPARATUS_RE = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁰-⁹]+|(?<=\w)[*'](?=\w|\s)")


@dataclass
class JubileesVerseRow:
    verse: int          # 0 = prologue, 1+ = verse number
    marker_raw: str     # the Ge'ez numeral as it appeared in the OCR
    text: str           # Ge'ez body text (apparatus markers stripped)
    source_page: int    # PDF page this verse started on


def parse_geez_numeral(marker: str) -> int:
    """Parse a compound Ge'ez numeral like ፲ወ፮ → 16, or ፳ → 20, or ፩ → 1.

    Charles 1895 uses the `ወ` ("and") joiner between decades and units
    for 2-digit numbers, e.g. `፲ወ፮` = 16, `፳ወ፭` = 25. We also handle
    the variant where the joiner is just the word-separator `፡`.
    """
    cleaned = marker.replace("ወ", "").replace("፡", "")
    total = 0
    for ch in cleaned:
        v = _ETH_DIGIT_MAP.get(ch)
        if v is None:
            raise ValueError(f"Not a Ge'ez numeral character: {ch!r} in {marker!r}")
        total += v
    return total


def strip_apparatus(text: str) -> str:
    """Remove superscript apparatus-footnote markers and variant-scope markers."""
    text = _APPARATUS_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_markers_per_line(lines: list[str]) -> list[tuple[int, str]]:
    """Return [(line_idx, marker_raw)] for every line ending in a Ge'ez numeral.

    Skips lines where the trailing numeral is actually a compound expression
    embedded mid-text (we require the marker to be at the real end of the
    line with only whitespace after it).
    """
    out = []
    for idx, line in enumerate(lines):
        stripped = line.rstrip()
        m = _VERSE_MARKER_RE.search(stripped)
        if m:
            out.append((idx, m.group("marker")))
    return out


def parse_page(ocr_text: str, source_page: int) -> list[JubileesVerseRow]:
    """Parse a single page of Jubilees OCR into verse rows.

    Handles the Charles 1895 right-marginal verse-numeral convention.
    Emits verse 0 for any pre-marker text (prologue or continuation).
    """
    # Normalize: drop running head, blank leading lines, etc.
    text = ocr_text.strip()
    if not text:
        return []

    # Split on explicit blank-line paragraphs so the prologue/title is
    # clearly delineated. Charles 1895 p37 structure:
    #   line 1: መጽሐፈ፡ ኩፋሌ፡
    #   (blank)
    #   lines 3-6: prologue (unnumbered)
    #   (blank)
    #   lines 7+: verse body (with marginal numerals)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    # If first paragraph is just a title (<= ~30 chars + no verse markers), skip it.
    def is_title_line(para: str) -> bool:
        if len(para) > 40:
            return False
        lines = para.splitlines()
        return len(lines) == 1 and not any(
            _VERSE_MARKER_RE.search(ln.rstrip()) for ln in lines
        )

    title_detected = bool(paragraphs) and is_title_line(paragraphs[0])
    body_paragraphs = paragraphs[1:] if title_detected else paragraphs

    # Flatten body paragraphs to a line list, but remember paragraph boundaries
    # so we can distinguish prologue from numbered verses.
    result: list[JubileesVerseRow] = []
    prologue_emitted = False

    for para_idx, para in enumerate(body_paragraphs):
        lines = para.splitlines()
        markers = find_markers_per_line(lines)

        if not markers:
            # No verse markers in this paragraph — it's prologue or
            # continuation of the previous verse.
            body = strip_apparatus("\n".join(lines))
            if not body:
                continue
            if not prologue_emitted:
                result.append(JubileesVerseRow(
                    verse=0,
                    marker_raw="",
                    text=body,
                    source_page=source_page,
                ))
                prologue_emitted = True
            else:
                # Append to the last verse's text as continuation
                if result:
                    result[-1].text = (result[-1].text + " " + body).strip()
            continue

        # Paragraph has verse markers. Split into verse bodies.
        # Pre-marker text (if any) before the first marker line is a
        # tail of the previous verse or a prologue fragment.
        first_marker_line_idx = markers[0][0]
        if first_marker_line_idx > 0:
            pre_text = strip_apparatus("\n".join(lines[:first_marker_line_idx]))
            if pre_text:
                if result and result[-1].verse >= 1:
                    result[-1].text = (result[-1].text + " " + pre_text).strip()
                elif not prologue_emitted:
                    result.append(JubileesVerseRow(
                        verse=0,
                        marker_raw="",
                        text=pre_text,
                        source_page=source_page,
                    ))
                    prologue_emitted = True

        # Walk marker pairs. Charles 1895 verse-marker convention:
        # numeral at end of line L means "verse N starts on line L."
        # Next marker's line = start of next verse (EXCLUSIVE of current body).
        for i, (line_idx, marker_raw) in enumerate(markers):
            try:
                v_num = parse_geez_numeral(marker_raw)
            except ValueError:
                continue
            # EXCLUSIVE upper bound: next marker's line is start of next verse.
            next_line_idx = markers[i + 1][0] if i + 1 < len(markers) else len(lines)
            body_lines = list(lines[line_idx:next_line_idx])
            if not body_lines:
                continue
            # Strip the trailing marker off the FIRST line.
            body_lines[0] = _VERSE_MARKER_RE.sub("", body_lines[0].rstrip()).rstrip()
            body = strip_apparatus("\n".join(body_lines))
            if not body:
                continue
            result.append(JubileesVerseRow(
                verse=v_num,
                marker_raw=marker_raw,
                text=body,
                source_page=source_page,
            ))

    # Mid-line transition fix-up: marker N signals verse N starts on the
    # line whose END carries numeral N. The SAME line also contains the
    # end of verse N-1 (up to the next ።). So verse N's OCR body often
    # includes a leading tail that actually belongs to verse N-1.
    # If verse N's text has a ። in its first ~half, move the segment up
    # through that ። back to verse N-1.
    for i in range(1, len(result)):
        prev = result[i - 1]
        curr = result[i]
        if curr.verse < 1:
            continue
        if "።" not in curr.text:
            continue
        first_term = curr.text.index("።")
        # Accept mid-line transitions up through the halfway point of the
        # current verse text (raising from 40% to 50% catches cases where
        # the pre-fixup verse is already short because the previous
        # iteration moved content forward).
        cutoff = max(30, int(len(curr.text) * 0.5))
        if first_term > cutoff:
            continue
        # Require actual remainder after the ።; otherwise the ። is the
        # current verse's OWN end, not a mid-line transition.
        if first_term >= len(curr.text) - 1:
            continue
        tail = curr.text[: first_term + 1].strip()
        remainder = curr.text[first_term + 1:].strip()
        if tail and (prev.verse == 0 or tail not in prev.text):
            if prev.verse >= 1:
                prev.text = (prev.text + " " + tail).strip()
            curr.text = remainder

    return result


def parse_chapter_pages(
    page_texts: list[tuple[int, str]],
) -> list[JubileesVerseRow]:
    """Parse a chapter's worth of OCR pages in order.

    page_texts: [(pdf_page_number, ocr_text), ...]

    Returns a merged list of verse rows. Verses that span page
    boundaries get their text concatenated automatically because we
    fold pre-marker continuation text into the previous verse.
    """
    merged: list[JubileesVerseRow] = []
    for page_num, ocr in page_texts:
        page_rows = parse_page(ocr, source_page=page_num)
        # If this page begins with a pre-marker continuation (verse 0
        # when we already have verses from the previous page), fold it
        # into the previous verse rather than emit as a new prologue.
        if page_rows and page_rows[0].verse == 0 and merged:
            tail = page_rows.pop(0).text
            merged[-1].text = (merged[-1].text + " " + tail).strip()
        merged.extend(page_rows)
    return merged


def main() -> int:
    import argparse, json
    ap = argparse.ArgumentParser(
        description="Parse Charles 1895 Jubilees OCR into verse rows."
    )
    ap.add_argument("input_path", help="Path to single-page OCR .txt file")
    ap.add_argument("--page", type=int, required=True, help="PDF page number of the input")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of tab-separated")
    args = ap.parse_args()
    text = pathlib.Path(args.input_path).read_text(encoding="utf-8")
    rows = parse_page(text, source_page=args.page)
    if args.json:
        print(json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r.verse}\t{r.marker_raw}\t{r.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
