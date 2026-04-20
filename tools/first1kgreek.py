"""first1kgreek.py — Parser for First1KGreek TEI-XML Swete LXX.

Cross-check source for the Phase 8 deuterocanonical corpus. Parses
tlg0527.tlgXXX.1st1K-grc1.xml files into (chapter, verse, greek_text)
tuples we can diff against our OCR-derived parse.

License: CC-BY-SA 4.0 (First1KGreek / OpenGreekAndLatin project,
distributed via Harvard College Library). Attribution preserved in
every derived artifact.

Source files live under `sources/lxx/swete/first1kgreek/`.
"""
from __future__ import annotations

import pathlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterator
import xml.etree.ElementTree as ET

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIRST1K_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "first1kgreek"
TEI_NS = "{http://www.tei-c.org/ns/1.0}"

# Map our book codes → First1KGreek tlg IDs (for Swete LXX edition).
# For books that have multiple First1KGreek works (e.g. OG + Theodotion
# versions of Daniel additions), we list the preferred tlg for B-text
# comparison first.
BOOK_TO_TLG: dict[str, str] = {
    "1ES": "tlg017",       # Esdras i (deuterocanonical 1 Esdras)
    "ADE": "tlg019",       # Esther (with Greek additions)
    "JDT": "tlg020",       # Judith
    "TOB": "tlg021",       # Tobit
    "1MA": "tlg023",
    "2MA": "tlg024",
    "3MA": "tlg025",
    "4MA": "tlg026",
    "WIS": "tlg033",       # Wisdom of Solomon
    "SIR": "tlg034",       # Sirach / Ecclesiasticus
    "BAR": "tlg050",
    "LJE": "tlg052",       # Letter of Jeremiah
    # Greek Daniel additions (handled specially as multi-work)
    "ADA": "tlg056",       # Daniel OG (primary); Theo version is tlg057
}

# For ADA we may also want alternates (Susanna, Bel, Theodotion)
ADA_ALTERNATE_TLGS = ("tlg054", "tlg055", "tlg056", "tlg057", "tlg058", "tlg059")


@dataclass
class First1KVerse:
    book_code: str
    chapter: str   # Chapter identifier as stored (usually int-string;
                   # Esther uses "A", "B", "1", "2" etc — keep string)
    verse: str     # Same — verse may be "1a" / "1" / other
    greek_text: str
    source_tlg: str

    @property
    def chapter_int(self) -> int | None:
        try:
            return int(self.chapter)
        except ValueError:
            return None

    @property
    def verse_int(self) -> int | None:
        # Strip letter suffixes like "1a" → 1
        m = re.match(r"^(\d+)", self.verse)
        return int(m.group(1)) if m else None


# -- Text cleaning --------------------------------------------------------

def _strip_notes(element: ET.Element) -> str:
    """Extract text from a verse element, dropping <note> children and
    <pb/> page breaks but keeping paragraph text."""
    parts: list[str] = []

    def walk(e: ET.Element) -> None:
        tag = e.tag.replace(TEI_NS, "")
        if tag == "note":
            return  # skip both marginal markers and apparatus footnotes
        if tag == "pb":
            return  # page break
        if e.text:
            parts.append(e.text)
        for child in e:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    text = "".join(parts)
    # Collapse whitespace / newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _xml_path_for(tlg: str) -> pathlib.Path:
    return FIRST1K_DIR / f"tlg0527.{tlg}.1st1K-grc1.xml"


def iter_verses(book_code: str) -> Iterator[First1KVerse]:
    """Yield every verse in First1KGreek's Swete edition for a book."""
    tlg = BOOK_TO_TLG.get(book_code)
    if not tlg:
        raise KeyError(f"No First1KGreek mapping for book code {book_code!r}")

    path = _xml_path_for(tlg)
    if not path.exists():
        raise FileNotFoundError(path)
    tree = ET.parse(path)
    root = tree.getroot()

    # Walk: <body><div type="edition"><div type="textpart" subtype="chapter">…
    body = root.find(f".//{TEI_NS}body")
    if body is None:
        return

    edition_div = body.find(f"{TEI_NS}div")
    if edition_div is None:
        return

    def iter_chapter_divs(parent: ET.Element) -> Iterator[ET.Element]:
        """Chapters might be nested one level deep (just textpart[subtype=chapter])
        or two levels (for ADE with Esther's unusual structure)."""
        for child in parent:
            if child.tag != f"{TEI_NS}div":
                continue
            subtype = child.attrib.get("subtype", "")
            if subtype == "chapter":
                yield child
            else:
                # recurse one level for nested structures
                for grand in child:
                    if grand.tag == f"{TEI_NS}div" and grand.attrib.get("subtype") == "chapter":
                        yield grand

    chapter_divs = list(iter_chapter_divs(edition_div))
    if chapter_divs:
        # Normal multi-chapter book
        for chap_div in chapter_divs:
            chap_n = chap_div.attrib.get("n", "")
            for verse_div in chap_div.findall(f"{TEI_NS}div"):
                if verse_div.attrib.get("subtype") != "verse":
                    continue
                verse_n = verse_div.attrib.get("n", "")
                text = _strip_notes(verse_div)
                if not text:
                    continue
                yield First1KVerse(
                    book_code=book_code,
                    chapter=chap_n,
                    verse=verse_n,
                    greek_text=text,
                    source_tlg=tlg,
                )
    else:
        # Single-chapter book: verses live directly under edition_div
        # (e.g. Letter of Jeremiah = tlg052, one chapter).
        for verse_div in edition_div.findall(f"{TEI_NS}div"):
            if verse_div.attrib.get("subtype") != "verse":
                continue
            verse_n = verse_div.attrib.get("n", "")
            text = _strip_notes(verse_div)
            if not text:
                continue
            yield First1KVerse(
                book_code=book_code,
                chapter="1",
                verse=verse_n,
                greek_text=text,
                source_tlg=tlg,
            )


def load_verse(book_code: str, chapter: int, verse: int) -> First1KVerse | None:
    for v in iter_verses(book_code):
        if v.chapter_int == chapter and v.verse_int == verse:
            return v
    return None


def normalize_greek(s: str) -> str:
    """Normalize Greek text for loose comparison.

    Strips accents/breathings/diacritics, final-sigma variants, punctuation.
    Case-folds. Useful for seeing whether two spellings of a verse are
    `essentially the same` without being pedantic about diacritics.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    # Drop accents
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = s.lower()
    # Normalize final sigma
    s = s.replace("ς", "σ")
    # Latin-B vs Greek-Β in First1KGreek: normalize both to Greek β
    s = s.replace("b", "β").replace("B", "β")
    # Drop punctuation / non-letter
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def similarity(a: str, b: str) -> float:
    """Crude word-overlap similarity for two Greek strings (0..1)."""
    na = normalize_greek(a)
    nb = normalize_greek(b)
    if not na or not nb:
        return 0.0
    wa = set(na.split())
    wb = set(nb.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


if __name__ == "__main__":
    # Smoke test: count verses per book
    import sys
    for book in BOOK_TO_TLG:
        try:
            verses = list(iter_verses(book))
            chapters = {}
            for v in verses:
                chapters.setdefault(v.chapter, 0)
                chapters[v.chapter] += 1
            print(f"{book}: {len(verses)}v across {len(chapters)} chapters")
            for c in sorted(chapters.keys(), key=lambda x: (x.isdigit(), int(x) if x.isdigit() else 0, x))[:5]:
                print(f"  ch {c}: {chapters[c]}")
        except Exception as e:
            print(f"{book}: ERROR {e}", file=sys.stderr)
