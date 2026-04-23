"""psalm151_hebrew.py — local-only consult reader for Psalm 151 Hebrew.

Psalm 151 survives in a Hebrew form in 11QPs^a / 11Q5 col. XXVIII.
The publicly viewable Leon Levy / IAA images are valuable for scholarly
consultation, but their website terms do not permit us to vendor the
images or a direct derivative transcription into this repository.

To keep COB's repo clean while still allowing a drafter to consult the
Hebrew counterpart, this module reads a **local-only** structured cache
outside the repo at:

  ~/cartha-reference-local/psalm151_hebrew/psalm151_kahana_1937.json

That local file is populated by `tools/fetch_psalm_151_hebrew.py`, which
pulls the 10-verse Hebrew Psalm 151 text from Sefaria's public API
(Avraham Kahana 1937 version) for personal scholarly consultation.

The Greek LXX Psalm 151 in COB remains the operative Zone 1 source. This
module only provides Zone 2 consult material that can be surfaced in the
translation prompt.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional


LOCAL_ROOT = pathlib.Path.home() / "cartha-reference-local" / "psalm151_hebrew"
LOCAL_JSON = LOCAL_ROOT / "psalm151_kahana_1937.json"

# Greek Psalm 151 (7 verses) is a shorter composition than the 10-verse
# Hebrew form surfaced by Sefaria. This map aligns each COB Greek verse to
# the Hebrew verse(s) that most closely correspond.
GREEK_TO_HEBREW_MAP: dict[int, list[int]] = {
    1: [2, 3],
    2: [4],
    3: [5],
    4: [6, 7],
    5: [8],
    6: [9],
    7: [10],
}

MAPPING_NOTES: dict[int, str] = {
    1: "Greek v.1 condenses Hebrew vv.2–3; Hebrew v.1 is a superscription with no direct Greek verse equivalent.",
    4: "Greek v.4 compresses the anointing sequence preserved across Hebrew vv.6–7.",
}


def is_available() -> bool:
    return LOCAL_JSON.exists()


def _load() -> dict:
    return json.loads(LOCAL_JSON.read_text(encoding="utf-8"))


def lookup(greek_verse: int) -> Optional[dict]:
    if not is_available():
        return None
    if greek_verse not in GREEK_TO_HEBREW_MAP:
        return None

    data = _load()
    verses = {int(v["verse"]): v for v in data.get("verses", [])}
    hebrew_verses = GREEK_TO_HEBREW_MAP[greek_verse]
    chosen = [verses[v] for v in hebrew_verses if v in verses]
    if not chosen:
        return None

    return {
        "kind": "zone_2_consult",
        "source": "Psalm 151 Hebrew (11QPsᵃ counterpart) via local Kahana 1937 cache",
        "book_code": "PS151",
        "chapter": 1,
        "verse": greek_verse,
        "available": True,
        "hebrew_verses": [v["verse"] for v in chosen],
        "hebrew_text": " ".join(v["hebrew"] for v in chosen if v.get("hebrew")),
        "english_gloss": " ".join(v["english"] for v in chosen if v.get("english")),
        "source_title": data.get("versionTitle", ""),
        "source_version_url": data.get("versionSource", ""),
        "mapping_note": MAPPING_NOTES.get(
            greek_verse,
            "Greek Psalm 151 is shorter than the Hebrew 10-verse form; this mapping is approximate and consultative."
        ),
        "guidance": (
            "Use the Hebrew only as a consult witness for idiom and expansion/contraction awareness. "
            "The operative COB source remains the Greek Psalm 151 text from Swete."
        ),
        "policy": (
            "Zone 2 consult only; local reference data must stay outside the repo. "
            "Do not reproduce Kahana's Hebrew as vendored repository source text."
        ),
    }


def summary() -> dict:
    if not is_available():
        return {"available": False, "local_json": str(LOCAL_JSON)}
    data = _load()
    return {
        "available": True,
        "local_json": str(LOCAL_JSON),
        "verse_count": len(data.get("verses", [])),
        "mapped_greek_verses": len(GREEK_TO_HEBREW_MAP),
        "source_title": data.get("versionTitle", ""),
    }


if __name__ == "__main__":
    import pprint
    pprint.pp(summary())
    for verse in range(1, 8):
        print(f"\nPS151 Greek v{verse}")
        pprint.pp(lookup(verse))
