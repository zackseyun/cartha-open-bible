"""hebrew_parallels.py — Hebrew/Aramaic originals for LXX deuterocanon.

For three of our deuterocanonical books there is recovered original-
language material that predates the Greek. When translating these,
the Hebrew/Aramaic witness must be consulted alongside the Greek:

  - **SIR (Sirach / Ben Sira)**: composed in Hebrew ~180 BC. ~2/3 of
    the Hebrew has been recovered (Cairo Geniza, Masada, Qumran).
    This module exposes Sefaria's CC0 Kahana-edition Hebrew text
    (sources/lxx/hebrew_parallels/sefaria_ben_sira.json). The more
    direct scholarly editions live in sources/hebrew_sirach/ and are
    processed separately by the Sirach-specific pipeline.

  - **TOB (Tobit)**: composed in Aramaic (and/or Hebrew) ~200 BC.
    Qumran 4Q196-200 fragments are the actual ancient evidence but
    sit behind DJD XIX copyright. This module exposes Neubauer's
    1878 Public-Domain Hebrew back-translation from Sefaria
    (sefaria_tobit.json) for translation reference only.

  - **1ES (1 Esdras)**: this is a Greek composition that reworks MT
    2 Chronicles 34-36 + Ezra 1-10 + Nehemiah 7:73b-8:13. This module
    maps 1 Esdras verses to their MT Hebrew parallel in our WLC
    corpus (sources/ot/wlc/). 1 Esdras 3:1-5:6 ('Three Youths') has
    NO Hebrew parallel and is Greek-only.

Usage:

    from hebrew_parallels import lookup
    hit = lookup('SIR', 1, 1)
    # -> {'kind': 'direct_hebrew', 'hebrew': '...', 'english_ref': '...', 'license': 'CC0'}

    hit = lookup('1ES', 3, 1)
    # -> {'kind': 'no_parallel', 'note': 'Three Youths — Greek only'}

    hit = lookup('1ES', 1, 1)
    # -> {'kind': 'mt_parallel', 'mt_ref': '2 Chronicles 35:1',
    #     'hebrew': '...', 'license': 'PD (WLC)'}
"""
from __future__ import annotations

import json
import pathlib
import re
from dataclasses import dataclass
from typing import Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PARALLELS_DIR = REPO_ROOT / "sources" / "lxx" / "hebrew_parallels"
WLC_DIR = REPO_ROOT / "sources" / "ot" / "wlc"

SEFARIA_BEN_SIRA = PARALLELS_DIR / "sefaria_ben_sira.json"
SEFARIA_TOBIT = PARALLELS_DIR / "sefaria_tobit.json"
ESDRAS_ALIGNMENT = PARALLELS_DIR / "1esdras_mt_alignment.json"


# ---- caches -----------------------------------------------------------------

_SIR_CACHE: Optional[dict] = None
_TOB_CACHE: Optional[dict] = None
_ESD_CACHE: Optional[dict] = None


def _load_sir() -> dict:
    global _SIR_CACHE
    if _SIR_CACHE is None:
        _SIR_CACHE = json.loads(SEFARIA_BEN_SIRA.read_text())
    return _SIR_CACHE


def _load_tob() -> dict:
    global _TOB_CACHE
    if _TOB_CACHE is None:
        _TOB_CACHE = json.loads(SEFARIA_TOBIT.read_text())
    return _TOB_CACHE


def _load_esdras_alignment() -> dict:
    global _ESD_CACHE
    if _ESD_CACHE is None:
        _ESD_CACHE = json.loads(ESDRAS_ALIGNMENT.read_text())
    return _ESD_CACHE


# ---- direct-Hebrew lookups (SIR, TOB) ---------------------------------------

def _lookup_sir(chapter: int, verse: int) -> Optional[dict]:
    data = _load_sir()
    ch = data["chapters"].get(str(chapter))
    if not ch:
        return None
    for v in ch["verses"]:
        if v["verse"] == verse and v.get("hebrew"):
            return {
                "kind": "direct_hebrew",
                "book_code": "SIR",
                "chapter": chapter,
                "verse": verse,
                "hebrew": v["hebrew"],
                "english_witness": v.get("english", ""),
                "source": "Sefaria: Ben Sira, David Kahana ed. (Wikisource)",
                "license": ch.get("license", "CC0"),
                "note": (
                    "Kahana's edition is a composite of the Cairo Geniza "
                    "Hebrew manuscripts. Where the Hebrew is missing or "
                    "uncertain, consult the fuller scholarly editions "
                    "referenced in sources/hebrew_sirach/README.md."
                ),
            }
    return None


def _lookup_tob(chapter: int, verse: int) -> Optional[dict]:
    data = _load_tob()
    ch = data["chapters"].get(str(chapter))
    if not ch:
        return None
    for v in ch["verses"]:
        if v["verse"] == verse and v.get("hebrew"):
            return {
                "kind": "indirect_hebrew",
                "book_code": "TOB",
                "chapter": chapter,
                "verse": verse,
                "hebrew": v["hebrew"],
                "english_witness": v.get("english", ""),
                "source": "Sefaria: Neubauer 1878 Hebrew back-translation",
                "license": ch.get("license", "Public Domain"),
                "note": (
                    "NOT an ancient Hebrew witness. Neubauer's 1878 Hebrew "
                    "is a back-translation from an Aramaic Munich MS. The "
                    "actual ancient evidence is Qumran 4Q196-200 (Aramaic), "
                    "published in DJD XIX (not redistributable). Use for "
                    "translation reference only; do not treat as Vorlage."
                ),
            }
    return None


# ---- 1 Esdras -> MT mapping -------------------------------------------------

# WLC book code (from our sources/ot/wlc/) -> filename base
WLC_BOOK_FILES: dict[str, str] = {
    "2 Chronicles": "2Chr",
    "Ezra": "Ezra",
    "Nehemiah": "Neh",
}

_REF_RANGE_RE = re.compile(r"^([0-9]+):([0-9]+)(?:-([0-9]+)(?::([0-9]+))?)?$")


def _parse_esdras_range(ref: str) -> tuple[int, int, int, int]:
    """Parse 'N:M' or 'N:M-P:Q' or 'N:M-Q' -> (start_ch, start_vs, end_ch, end_vs)."""
    m = _REF_RANGE_RE.match(ref)
    if not m:
        raise ValueError(f"Cannot parse Esdras ref: {ref}")
    ch1 = int(m.group(1))
    vs1 = int(m.group(2))
    end_ch_str = m.group(3)
    end_vs_str = m.group(4)
    if end_vs_str is not None:
        ch2 = int(end_ch_str)
        vs2 = int(end_vs_str)
    elif end_ch_str is not None:
        ch2 = ch1
        vs2 = int(end_ch_str)
    else:
        ch2 = ch1
        vs2 = vs1
    return ch1, vs1, ch2, vs2


def _parse_mt_ref(ref: str) -> Optional[tuple[str, int, int, int, int]]:
    """Parse e.g. '2 Chronicles 35:1-19' or 'Nehemiah 7:73b-8:13a'.

    Returns (book_name, start_ch, start_vs, end_ch, end_vs) or None.
    Letter suffixes on verse numbers (e.g. '73b') are stripped.
    """
    # Strip known letter suffixes from verse tokens
    cleaned = re.sub(r"(\d+)[a-z]", r"\1", ref)
    # Expect "Book N:M[-P[:Q]]"
    m = re.match(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+)(?::(\d+))?)?$", cleaned)
    if not m:
        return None
    book = m.group(1).strip()
    ch1, vs1 = int(m.group(2)), int(m.group(3))
    if m.group(5) is not None:
        ch2, vs2 = int(m.group(4)), int(m.group(5))
    elif m.group(4) is not None:
        ch2, vs2 = ch1, int(m.group(4))
    else:
        ch2, vs2 = ch1, vs1
    return book, ch1, vs1, ch2, vs2


def _fraction_into_range(v: int, start: int, end: int) -> float:
    if end <= start:
        return 0.0
    return (v - start) / (end - start)


def _interp_verse(v: int, s1: int, s2: int, t1: int, t2: int) -> int:
    """Map v in [s1..s2] linearly to corresponding point in [t1..t2], clamped."""
    if s2 <= s1:
        return t1
    frac = (v - s1) / (s2 - s1)
    approx = round(t1 + frac * (t2 - t1))
    return max(t1, min(t2, approx))


@dataclass
class _EsdMap:
    esdras_start: tuple[int, int]
    esdras_end: tuple[int, int]
    mt_book: Optional[str]
    mt_start: Optional[tuple[int, int]]
    mt_end: Optional[tuple[int, int]]
    content: str


def _build_esdras_map() -> list[_EsdMap]:
    data = _load_esdras_alignment()
    out: list[_EsdMap] = []
    for row in data["alignment"]:
        ch1, vs1, ch2, vs2 = _parse_esdras_range(row["esdras_ref"])
        mt_ref = row.get("mt_ref")
        if mt_ref is None:
            out.append(_EsdMap(
                esdras_start=(ch1, vs1), esdras_end=(ch2, vs2),
                mt_book=None, mt_start=None, mt_end=None,
                content=row["content"]))
            continue
        parsed = _parse_mt_ref(mt_ref)
        if parsed is None:
            out.append(_EsdMap(
                esdras_start=(ch1, vs1), esdras_end=(ch2, vs2),
                mt_book=None, mt_start=None, mt_end=None,
                content=row["content"]))
            continue
        book, mc1, mv1, mc2, mv2 = parsed
        out.append(_EsdMap(
            esdras_start=(ch1, vs1), esdras_end=(ch2, vs2),
            mt_book=book, mt_start=(mc1, mv1), mt_end=(mc2, mv2),
            content=row["content"]))
    return out


_ESD_MAP: Optional[list[_EsdMap]] = None


def _esdras_map() -> list[_EsdMap]:
    global _ESD_MAP
    if _ESD_MAP is None:
        _ESD_MAP = _build_esdras_map()
    return _ESD_MAP


def _in_range(ch: int, vs: int, start: tuple[int, int], end: tuple[int, int]) -> bool:
    if (ch, vs) < start:
        return False
    if (ch, vs) > end:
        return False
    return True


# ---- WLC Hebrew text lookup -------------------------------------------------

_WLC_CACHE: dict[str, dict[tuple[int, int], str]] = {}


def _load_wlc_book(book_name: str) -> dict[tuple[int, int], str]:
    if book_name in _WLC_CACHE:
        return _WLC_CACHE[book_name]
    fname = WLC_BOOK_FILES.get(book_name)
    if not fname:
        _WLC_CACHE[book_name] = {}
        return {}
    path = WLC_DIR / f"{fname}.xml"
    verses: dict[tuple[int, int], str] = {}
    if not path.exists():
        _WLC_CACHE[book_name] = verses
        return verses
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        root = tree.getroot()
        # WLC OSIS format: <verse osisID="Ezra.1.1">...</verse>
        for v in root.iter():
            tag = v.tag.rsplit("}", 1)[-1]
            if tag != "verse":
                continue
            osis = v.get("osisID") or v.get("sID") or ""
            m = re.match(r"^[^.]+\.(\d+)\.(\d+)$", osis)
            if not m:
                continue
            ch = int(m.group(1))
            vs = int(m.group(2))
            text = "".join(v.itertext()).strip()
            if text:
                verses[(ch, vs)] = text
    except Exception:
        pass
    _WLC_CACHE[book_name] = verses
    return verses


def _lookup_wlc(book_name: str, ch: int, vs: int) -> Optional[str]:
    verses = _load_wlc_book(book_name)
    return verses.get((ch, vs))


def _wlc_verse_sequence(book_name: str, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Return the ordered list of (ch, vs) that actually exist in WLC
    between start and end inclusive. Used to map 1ES linearly across
    chapter boundaries without inventing non-existent verses.
    """
    verses = _load_wlc_book(book_name)
    if not verses:
        return []
    keys = sorted(verses.keys())
    return [k for k in keys if start <= k <= end]


# ---- 1 Esdras lookup --------------------------------------------------------

def _lookup_1es(chapter: int, verse: int) -> dict:
    mapping = _esdras_map()
    for row in mapping:
        if not _in_range(chapter, verse, row.esdras_start, row.esdras_end):
            continue
        if row.mt_book is None:
            return {
                "kind": "no_parallel",
                "book_code": "1ES",
                "chapter": chapter,
                "verse": verse,
                "note": f"No Hebrew parallel ({row.content}). Greek-only material -- translate from Swete.",
            }
        # Map 1ES position -> MT position using the real WLC verse list
        # in the MT range. This avoids inventing verses when the MT
        # range crosses a chapter boundary.
        s1c, s1v = row.esdras_start
        s2c, s2v = row.esdras_end
        t1c, t1v = row.mt_start
        t2c, t2v = row.mt_end
        mt_seq = _wlc_verse_sequence(row.mt_book, (t1c, t1v), (t2c, t2v))
        # Estimate the 1ES verse index in its range via flat counting,
        # clamping inside the range. We use flat = ch*10000 + vs so
        # a sensible linearization even if 1ES spans a boundary.
        def flat(c, v): return c * 10000 + v
        fs = flat(s1c, s1v)
        fe = flat(s2c, s2v)
        fv = max(fs, min(fe, flat(chapter, verse)))
        if mt_seq:
            if fe <= fs:
                idx = 0
            else:
                frac = (fv - fs) / (fe - fs)
                idx = round(frac * (len(mt_seq) - 1))
                idx = max(0, min(len(mt_seq) - 1, idx))
            approx_ch, approx_vs = mt_seq[idx]
            hebrew = _load_wlc_book(row.mt_book).get((approx_ch, approx_vs))
        else:
            approx_ch, approx_vs = t1c, t1v
            hebrew = None
        return {
            "kind": "mt_parallel",
            "book_code": "1ES",
            "chapter": chapter,
            "verse": verse,
            "mt_book": row.mt_book,
            "mt_chapter_approx": approx_ch,
            "mt_verse_approx": approx_vs,
            "mt_range": f"{row.mt_book} {t1c}:{t1v}-{t2c}:{t2v}",
            "hebrew": hebrew,
            "content": row.content,
            "source": "WLC (Westminster Leningrad Codex, Public Domain)",
            "license": "Public Domain",
            "note": (
                "MT parallel is APPROXIMATE -- 1 Esdras sometimes expands, "
                "conflates, or reorders the Hebrew. Use the MT hebrew as a "
                "sanity check on proper names and phrasing; the Greek remains "
                "the primary source text."
            ),
        }
    return {
        "kind": "unmapped",
        "book_code": "1ES",
        "chapter": chapter,
        "verse": verse,
        "note": f"Verse {chapter}:{verse} falls outside the known 1ES->MT alignment. Treat as Greek-only.",
    }


# ---- public API -------------------------------------------------------------

def lookup(book_code: str, chapter: int, verse: int) -> Optional[dict]:
    """Return Hebrew/Aramaic parallel information for a given LXX verse.

    Returns dict with "kind" in:
      - "direct_hebrew":  this verse has an original Hebrew witness (SIR)
      - "indirect_hebrew": this verse has a back-translation only (TOB)
      - "mt_parallel":     this verse corresponds to a MT passage (1ES)
      - "no_parallel":     the verse has no Hebrew parallel (3 Youths in 1ES)
      - "unmapped":        the lookup fell outside the known alignment
    Or None if the book_code is not one of SIR/TOB/1ES.
    """
    if book_code == "SIR":
        hit = _lookup_sir(chapter, verse)
        if hit:
            return hit
        return {
            "kind": "direct_hebrew_missing",
            "book_code": "SIR",
            "chapter": chapter,
            "verse": verse,
            "note": (
                "This verse is not present in the Sefaria Ben Sira (Kahana) "
                "text. Either the Hebrew is lost (common in chapters 17, "
                "22-24, 26-29, 36) or our lookup missed it. Consult "
                "sources/hebrew_sirach/ for the fuller scholarly editions."
            ),
        }
    if book_code == "TOB":
        hit = _lookup_tob(chapter, verse)
        if hit:
            return hit
        return {
            "kind": "indirect_hebrew_missing",
            "book_code": "TOB",
            "chapter": chapter,
            "verse": verse,
            "note": "No Hebrew back-translation available for this verse in the Neubauer text.",
        }
    if book_code == "1ES":
        return _lookup_1es(chapter, verse)
    return None


def is_available() -> bool:
    return SEFARIA_BEN_SIRA.exists() and SEFARIA_TOBIT.exists() and ESDRAS_ALIGNMENT.exists()


def summary() -> dict:
    """Quick counts for sanity-checking."""
    out = {}
    if SEFARIA_BEN_SIRA.exists():
        d = _load_sir()
        out["SIR"] = {
            "chapters": len(d["chapters"]),
            "verses_total": sum(len(c["verses"]) for c in d["chapters"].values()),
            "verses_with_hebrew": sum(c["hebrew_count"] for c in d["chapters"].values()),
        }
    if SEFARIA_TOBIT.exists():
        d = _load_tob()
        out["TOB"] = {
            "chapters": len(d["chapters"]),
            "verses_total": sum(len(c["verses"]) for c in d["chapters"].values()),
            "verses_with_hebrew": sum(c["hebrew_count"] for c in d["chapters"].values()),
        }
    if ESDRAS_ALIGNMENT.exists():
        d = _load_esdras_alignment()
        out["1ES"] = {
            "alignment_rows": len(d["alignment"]),
            "with_mt_parallel": sum(1 for r in d["alignment"] if r.get("mt_ref")),
            "greek_only": sum(1 for r in d["alignment"] if not r.get("mt_ref")),
        }
    return out


if __name__ == "__main__":
    import pprint
    if not is_available():
        print("Not all parallel sources available. Expected:")
        for p in [SEFARIA_BEN_SIRA, SEFARIA_TOBIT, ESDRAS_ALIGNMENT]:
            print(f"  {'OK ' if p.exists() else 'MISSING '} {p}")
        raise SystemExit(1)
    print("=== Summary ===")
    pprint.pp(summary())
    print("\n=== Sample lookups ===")
    for ref in [("SIR", 1, 1), ("SIR", 17, 1), ("SIR", 39, 27),
                ("TOB", 1, 1), ("TOB", 13, 1),
                ("1ES", 1, 1), ("1ES", 3, 1), ("1ES", 5, 7),
                ("1ES", 9, 40)]:
        book, ch, vs = ref
        hit = lookup(book, ch, vs)
        print(f"\n{book} {ch}:{vs}")
        if hit:
            print(f"  kind: {hit['kind']}")
            if hit.get("hebrew"):
                heb = hit["hebrew"]
                print(f"  hebrew: {heb[:80]}{'...' if len(heb) > 80 else ''}")
            if hit.get("mt_range"):
                print(f"  mt_range: {hit['mt_range']}  approx -> {hit.get('mt_book')} {hit.get('mt_chapter_approx')}:{hit.get('mt_verse_approx')}")
            if hit.get("note"):
                print(f"  note: {hit['note'][:100]}")
