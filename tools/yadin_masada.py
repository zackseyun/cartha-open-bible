"""yadin_masada.py — LOCAL-ONLY Zone 2 consult reader for Yadin 1965.

Yigael Yadin, *The Ben Sira Scroll from Masada* (Jerusalem: IES, 1965)
is the editio princeps of the Masada Ben Sira scroll (Sir 39:27-44:17).
It is copyrighted (Yadin d. 1984). Per REFERENCE_SOURCES.md, this work
is Zone 2 (consulted-only) — translators may read it for reference,
but its text must never appear in COB output or be committed to this
repository.

This module reads the LOCAL extraction at
  ~/cartha-reference-local/yadin_1965/
(populated by /tmp/extract_yadin.py). If the extraction directory does
not exist (e.g. on a clean checkout, or a teammate without a local
reference library), the module silently reports unavailable and the
translator prompt omits the Zone 2 Yadin entry — exactly the intended
behavior.

WHAT THIS MODULE DOES:
  - Reads per-page JSON extractions and builds a (chapter, verse) -> page index
  - Exposes lookup(chapter, verse) -> dict with Hebrew, page-in-Yadin, notes

WHAT IT DOES NOT DO:
  - Copy any extraction into the repository
  - Provide Yadin's English translation to the translator prompt (per
    Zone 2: do not track his English word-for-word). Only Hebrew and
    scholarly apparatus flow through.
  - Operate if the local extraction is missing.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Optional

# Local-only: explicitly OUTSIDE the repo working tree
LOCAL_ROOT = pathlib.Path.home() / "cartha-reference-local" / "yadin_1965"
PAGES_DIR = LOCAL_ROOT / "pages"

# Sirach chapter/verse range covered by the Masada scroll
MASADA_COVERAGE = (39, 27, 44, 17)  # (start_ch, start_vs, end_ch, end_vs)

_INDEX_CACHE: Optional[dict[tuple[int, int], dict]] = None


def is_available() -> bool:
    """True iff the local extraction directory exists with at least
    some per-page JSON files.
    """
    if not PAGES_DIR.exists():
        return False
    return any(PAGES_DIR.glob("*.json"))


_VERSE_REF_RE = re.compile(
    r"(?:Sir|Sirach|Ben\s*Sira|Ecclus)\.?\s*(\d+)\s*[:.]\s*(\d+)(?:\s*[-–]\s*(?:(\d+)\s*[:.]\s*)?(\d+))?",
    re.IGNORECASE,
)


def _parse_verse_range(s: str) -> list[tuple[int, int]]:
    """Parse 'Sir 39:27-40:3' or '39:27-30' etc. into a list of (ch, vs) tuples it covers.

    Returns [] if the string can't be parsed. Caps expansion to avoid
    explosions on malformed data.
    """
    if not s:
        return []
    m = _VERSE_REF_RE.search(s)
    if not m:
        m2 = re.match(r"^\s*(\d+)[:.](\d+)(?:\s*[-–]\s*(?:(\d+)[:.])?(\d+))?\s*$", s)
        if not m2:
            return []
        start_ch = int(m2.group(1))
        start_vs = int(m2.group(2))
        end_ch = int(m2.group(3)) if m2.group(3) else start_ch
        end_vs = int(m2.group(4)) if m2.group(4) else start_vs
    else:
        start_ch = int(m.group(1))
        start_vs = int(m.group(2))
        end_ch = int(m.group(3)) if m.group(3) else start_ch
        end_vs = int(m.group(4)) if m.group(4) else start_vs

    out: list[tuple[int, int]] = []
    if end_ch < start_ch:
        return [(start_ch, start_vs)]
    if end_ch == start_ch:
        for v in range(start_vs, end_vs + 1):
            out.append((start_ch, v))
            if len(out) > 200:
                break
    else:
        # Rough expansion — we don't know exact verses-per-chapter here,
        # so record the anchors only. The translator prompt still finds
        # the page this way, which is what matters.
        out.append((start_ch, start_vs))
        out.append((end_ch, end_vs))
    return out


def _build_index() -> dict[tuple[int, int], dict]:
    """Walk the per-page JSON files and build (ch,vs) -> page-info."""
    idx: dict[tuple[int, int], dict] = {}
    for jf in sorted(PAGES_DIR.glob("*.json")):
        try:
            data = json.loads(jf.read_text())
        except Exception:
            continue
        page_num = int(jf.stem)
        vr = data.get("verse_range")
        if not vr:
            continue
        for ch, vs in _parse_verse_range(vr):
            # Keep the first page that attests this verse; additional
            # pages covering the same verse are noted as `also_on`.
            if (ch, vs) not in idx:
                idx[(ch, vs)] = {
                    "page_in_yadin": page_num,
                    "hebrew_text": data.get("hebrew_text", ""),
                    "scholarly_notes": data.get("scholarly_notes", ""),
                    "confidence": data.get("confidence", ""),
                    "also_on": [],
                }
            else:
                idx[(ch, vs)]["also_on"].append(page_num)
    return idx


def _ensure_index() -> dict[tuple[int, int], dict]:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        if not is_available():
            _INDEX_CACHE = {}
        else:
            _INDEX_CACHE = _build_index()
    return _INDEX_CACHE


def in_coverage(chapter: int, verse: int) -> bool:
    sc, sv, ec, ev = MASADA_COVERAGE
    if (chapter, verse) < (sc, sv):
        return False
    if (chapter, verse) > (ec, ev):
        return False
    return True


def lookup(chapter: int, verse: int) -> Optional[dict]:
    """Return Zone 2 consult info for a Sirach verse, or None if
    unavailable (either outside coverage or extraction not on disk).

    Does NOT include Yadin's English translation — Zone 2 policy
    prohibits tracking his English in our output.
    """
    if not is_available():
        return None
    if not in_coverage(chapter, verse):
        return None
    idx = _ensure_index()
    entry = idx.get((chapter, verse))
    if not entry:
        return {
            "kind": "zone_2_consult",
            "source": "Yadin 1965, The Ben Sira Scroll from Masada",
            "book_code": "SIR",
            "chapter": chapter,
            "verse": verse,
            "available": False,
            "note": (
                "This verse is within the Masada scroll coverage range "
                "(Sir 39:27-44:17) but was not successfully indexed from "
                "the local extraction. The translator may consult the "
                "PDF directly. Not all pages expose a verse_range field."
            ),
            "local_path_hint": str(LOCAL_ROOT),
            "policy": "REFERENCE_SOURCES.md Zone 2 -- consult only, fact-level citation, do not reproduce",
        }
    return {
        "kind": "zone_2_consult",
        "source": "Yadin 1965, The Ben Sira Scroll from Masada (editio princeps)",
        "book_code": "SIR",
        "chapter": chapter,
        "verse": verse,
        "available": True,
        "hebrew_text_masada": entry["hebrew_text"],
        "scholarly_notes": entry["scholarly_notes"],
        "page_in_yadin": entry["page_in_yadin"],
        "also_on_pages": entry["also_on"],
        "extraction_confidence": entry["confidence"],
        "guidance": (
            "Masada scroll is older than the Cairo Geniza MSS. Compare "
            "the Masada Hebrew above against the Kahana/Schechter Zone 1 "
            "Hebrew for this verse. Where they disagree, Masada typically "
            "wins on textual-critical grounds. Footnote fact-level "
            "(e.g. 'Masada reads X where MS B reads Y'). Do NOT reproduce "
            "Yadin's English translation -- we have deliberately excluded "
            "it from this context block to protect our CC-BY output."
        ),
        "policy": "REFERENCE_SOURCES.md Zone 2 -- consult only, no reproduction, no derivative English",
    }


def summary() -> dict:
    if not is_available():
        return {
            "available": False,
            "local_root": str(LOCAL_ROOT),
            "note": "Yadin extraction not present on this machine. Zone 2 consult silently omitted from translator prompts.",
        }
    idx = _ensure_index()
    pages = sorted({v["page_in_yadin"] for v in idx.values()})
    chapters = sorted({k[0] for k in idx})
    return {
        "available": True,
        "indexed_verses": len(idx),
        "chapters_indexed": chapters,
        "unique_pages": len(pages),
        "coverage_range": f"Sir {MASADA_COVERAGE[0]}:{MASADA_COVERAGE[1]}-{MASADA_COVERAGE[2]}:{MASADA_COVERAGE[3]}",
    }


if __name__ == "__main__":
    import pprint
    print("=== Yadin Masada summary ===")
    pprint.pp(summary())
    if is_available():
        print("\n=== Sample lookups ===")
        for ref in [("SIR", 39, 27), ("SIR", 40, 1), ("SIR", 42, 15), ("SIR", 44, 17), ("SIR", 1, 1)]:
            _, ch, vs = ref
            hit = lookup(ch, vs)
            print(f"\nSIR {ch}:{vs}")
            if hit is None:
                print("  (outside Masada coverage or extraction missing)")
            elif not hit.get("available"):
                print(f"  page_index_gap: {hit['note'][:80]}")
            else:
                heb = hit.get("hebrew_text_masada", "")
                print(f"  page: {hit['page_in_yadin']}  confidence: {hit['extraction_confidence']}")
                print(f"  hebrew (first 80 chars): {heb[:80]}{'...' if len(heb) > 80 else ''}")
