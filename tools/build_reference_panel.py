#!/usr/bin/env python3
"""build_reference_panel.py — vendor public-domain English translations
into per-book JSON for the Claude reviewer's reference panel.

Sources (all vendored from /tmp/cob_refs/<corpus>/<corpus>_vpl.txt — see
`fetch_corpora()` for download URLs):

  - BSB        Berean Standard Bible       (CC0 / Public Domain)   bereanbible.com
  - WEB        World English Bible         (Public Domain)         ebible.org
  - Brenton    Brenton's LXX               (Public Domain, 1851)   ebible.org
  - KJV        King James Version (2006)   (Public Domain in US)   ebible.org

Output: sources/references/<book_slug>.json with per-verse renderings.
Schema is compatible with the existing prayer_of_manasseh.json /
sirach_24.json (one chapter per file there) but allows multi-chapter
books to be expressed as { "verses": { "<chap>:<verse>": {...} } }.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Iterable

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REFS_DIR = REPO_ROOT / "sources" / "references"
CORPUS_ROOT = pathlib.Path("/tmp/cob_refs")

# Map COB book slugs to USFM-style codes used in ebible VPL files.
# A book slug may need multiple codes per panel (e.g. Psalm 151 is "PSX" in
# WEB but "PSA 151:N" in Brenton).
PANEL_CODES: dict[str, dict[str, str]] = {
    "psalms": {
        "bsb": "PSA",
        "web": "PSA",
        "brenton": "PSA",
        "kjv": "PSA",
    },
    "ezekiel": {
        "bsb": "EZE",
        "web": "EZE",
        "brenton": "EZE",
        "kjv": "EZE",
    },
    "psalm_151": {
        # Most Bibles do not carry Ps 151; only WEB-with-Apocrypha and
        # Brenton's LXX include it. WEB labels it PSX, Brenton inlines it
        # as PSA 151:N.
        "web": "PSX",
        "brenton": "PSA",
    },
}

# COB chapter/verse → panel chapter/verse override. None = use COB ch/v as-is.
# `psalm_151` is one chapter in Brenton numbered as 151 but in COB is chapter 1.
def panel_chapter(book_slug: str, panel: str, cob_chapter: int) -> int:
    if book_slug == "psalm_151" and panel == "brenton":
        return 151  # Brenton numbers it inline in PSA
    return cob_chapter


def fetch_corpora() -> None:
    """Download VPL archives if missing. Idempotent. Run by hand once."""
    import subprocess
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    targets = {
        "engbsb":      "https://ebible.org/Scriptures/engbsb_vpl.zip",
        "eng-web":     "https://ebible.org/Scriptures/eng-web_vpl.zip",
        "eng-Brenton": "https://ebible.org/Scriptures/eng-Brenton_vpl.zip",
        "eng-kjv2006": "https://ebible.org/Scriptures/eng-kjv2006_vpl.zip",
    }
    for name, url in targets.items():
        zpath = CORPUS_ROOT / f"{name}.zip"
        outdir = CORPUS_ROOT / name
        if (outdir / f"{name}_vpl.txt").exists():
            continue
        if not zpath.exists():
            subprocess.check_call([
                "curl", "-sL",
                "-A", "Mozilla/5.0 cartha-open-bible-research",
                "-o", str(zpath), url,
            ])
        subprocess.check_call([
            "unzip", "-qoj", str(zpath), "*.txt",
            "-d", str(outdir),
        ])


def load_vpl(path: pathlib.Path) -> dict[tuple[str, int, int], str]:
    """Parse a VPL file into {(usfm_book, chap, verse): text}."""
    out: dict[tuple[str, int, int], str] = {}
    pat = re.compile(r"^(\S+)\s+(\d+):(\d+)\s+(.+)$")
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = pat.match(line)
            if not m:
                continue
            book, ch, v, text = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            out[(book, ch, v)] = text.strip()
    return out


PANEL_FILES = {
    "bsb":     CORPUS_ROOT / "engbsb"      / "engbsb_vpl.txt",
    "web":     CORPUS_ROOT / "eng-web"     / "eng-web_vpl.txt",
    "brenton": CORPUS_ROOT / "eng-Brenton" / "eng-Brenton_vpl.txt",
    "kjv":     CORPUS_ROOT / "eng-kjv2006" / "eng-kjv2006_vpl.txt",
}


def panel_lookup(panels: dict, book_slug: str, cob_chapter: int, cob_verse: int) -> dict[str, str]:
    """Return {panel_name: rendering, ...} for one COB verse, including
    superscription handling: when COB verse=0 (Psalm superscription),
    return verse 1 from each panel since they bake the superscription
    into v1.
    """
    out: dict[str, str] = {}
    code_map = PANEL_CODES.get(book_slug, {})
    for panel_name, usfm in code_map.items():
        ch = panel_chapter(book_slug, panel_name, cob_chapter)
        # COB superscriptions are verse 0; published Bibles bake them
        # into verse 1. Pull verse 1 with a "(includes superscription)"
        # disclaimer.
        v_lookup = 1 if cob_verse == 0 else cob_verse
        text = panels[panel_name].get((usfm, ch, v_lookup))
        if text:
            if cob_verse == 0:
                out[panel_name] = f"[v1, includes superscription] {text}"
            else:
                out[panel_name] = text
    return out


PANEL_CITATIONS = {
    "bsb":     "Berean Standard Bible (Public Domain / CC0). bereanbible.com.",
    "web":     "World English Bible (Public Domain). ebible.org/web/.",
    "brenton": "Brenton's translation of the Septuagint (1844/1851; Public Domain). ebible.org/eng-Brenton/.",
    "kjv":     "King James Version, ebible.org 2006 transcription (Public Domain in US).",
}


def build_book_json(book_slug: str, verse_pairs: Iterable[tuple[int, int]],
                    panels: dict) -> dict:
    sources = {p: PANEL_CITATIONS[p] for p in PANEL_CODES.get(book_slug, {})}
    verses: dict[str, dict[str, str]] = {}
    for ch, v in sorted(set(verse_pairs)):
        renderings = panel_lookup(panels, book_slug, ch, v)
        if not renderings:
            continue
        verses[f"{ch}:{v}"] = renderings
    return {
        "book": book_slug,
        "source_language": "Hebrew" if book_slug != "psalm_151" else "Greek",
        "license": "All vendored renderings are public domain or CC0.",
        "sources": sources,
        "verses": verses,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worklist", default="/tmp/uncovered.jsonl")
    ap.add_argument("--books", nargs="*",
                    default=["psalms", "ezekiel", "psalm_151"],
                    help="COB book slugs to vendor refs for")
    ap.add_argument("--fetch", action="store_true",
                    help="Download VPL corpora first if missing")
    args = ap.parse_args()

    if args.fetch:
        fetch_corpora()

    panels = {name: load_vpl(p) for name, p in PANEL_FILES.items() if p.exists()}
    missing = [n for n in PANEL_FILES if n not in panels]
    if missing:
        print(f"Missing corpora: {missing}. Run with --fetch.", file=sys.stderr)
        return 1

    # Build {book_slug: [(ch, v), ...]} from worklist
    book_verses: dict[str, list[tuple[int, int]]] = {}
    with open(args.worklist) as f:
        for line in f:
            e = json.loads(line)
            slug = e["review_book_slug"]
            if slug not in args.books:
                continue
            book_verses.setdefault(slug, []).append((e["chapter"], e["verse"]))

    REFS_DIR.mkdir(parents=True, exist_ok=True)
    for slug in args.books:
        if slug not in book_verses:
            print(f"  {slug}: no verses in worklist (skipped)")
            continue
        data = build_book_json(slug, book_verses[slug], panels)
        out = REFS_DIR / f"{slug}.json"
        out.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  {slug}: {len(data['verses'])} verses with refs → {out.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
