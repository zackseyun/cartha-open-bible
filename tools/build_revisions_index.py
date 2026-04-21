#!/usr/bin/env python3
"""build_revisions_index.py — walk every verse YAML and emit a
structured revisions index that the cartha.website frontend can fetch.

Output: `revisions.json` at repo root, served via GitHub raw CDN just
like `status.json`. Schema v1:

{
  "generated_at": "...",
  "commit_sha": "...",         # HEAD at generation time
  "schema_version": 1,
  "totals": {
    "verses_with_revisions": N,
    "total_revisions": M,       # can be > verses if one verse revised twice
    "by_category": {...},
    "by_tier": {...},
    "by_adjudicator": {...},
    "by_reviewer_model": {...}
  },
  "by_book": {
    "<slug>": {
      "display": "Genesis",
      "testament": "ot",
      "verse_count": N,
      "revision_count": M
    }
  },
  "revisions": [
    {
      "id": "GEN.3.4",
      "testament": "ot",
      "book_slug": "genesis",
      "book_display": "Genesis",
      "chapter": 3,
      "verse": 4,
      "timestamp": "2026-04-20T08:29:57Z",
      "adjudicator": "claude-opus-4-7",
      "reviewer_model": "gemini-2.5-pro",
      "category": "mistranslation",
      "tier": 2,
      "from": "You will not surely die.",
      "to": "You will surely not die.",
      "rationale": "Hebrew לֹא מוֹת...",
      "source_review": "state/reviews/gemini/..."
    },
    ...
  ]
}
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
OUT_PATH = REPO_ROOT / "revisions.json"
SCHEMA_VERSION = 1

# 3-letter codes (SBL / Paratext style) keyed by slug — drives the
# canonical_id prefix (GEN, EXO, ...) and provides display names.
BOOK_META: dict[str, tuple[str, str, str]] = {
    # testament, slug, display name, sbl_code
    "ot": {
        "genesis": ("Genesis", "GEN"), "exodus": ("Exodus", "EXO"),
        "leviticus": ("Leviticus", "LEV"), "numbers": ("Numbers", "NUM"),
        "deuteronomy": ("Deuteronomy", "DEU"), "joshua": ("Joshua", "JOS"),
        "judges": ("Judges", "JDG"), "ruth": ("Ruth", "RUT"),
        "1_samuel": ("1 Samuel", "1SA"), "2_samuel": ("2 Samuel", "2SA"),
        "1_kings": ("1 Kings", "1KI"), "2_kings": ("2 Kings", "2KI"),
        "1_chronicles": ("1 Chronicles", "1CH"),
        "2_chronicles": ("2 Chronicles", "2CH"),
        "ezra": ("Ezra", "EZR"), "nehemiah": ("Nehemiah", "NEH"),
        "esther": ("Esther", "EST"), "job": ("Job", "JOB"),
        "psalms": ("Psalms", "PSA"), "proverbs": ("Proverbs", "PRO"),
        "ecclesiastes": ("Ecclesiastes", "ECC"),
        "song_of_songs": ("Song of Songs", "SNG"),
        "isaiah": ("Isaiah", "ISA"), "jeremiah": ("Jeremiah", "JER"),
        "lamentations": ("Lamentations", "LAM"),
        "ezekiel": ("Ezekiel", "EZK"), "daniel": ("Daniel", "DAN"),
        "hosea": ("Hosea", "HOS"), "joel": ("Joel", "JOL"),
        "amos": ("Amos", "AMO"), "obadiah": ("Obadiah", "OBA"),
        "jonah": ("Jonah", "JON"), "micah": ("Micah", "MIC"),
        "nahum": ("Nahum", "NAM"), "habakkuk": ("Habakkuk", "HAB"),
        "zephaniah": ("Zephaniah", "ZEP"), "haggai": ("Haggai", "HAG"),
        "zechariah": ("Zechariah", "ZEC"), "malachi": ("Malachi", "MAL"),
    },
    "nt": {
        "matthew": ("Matthew", "MAT"), "mark": ("Mark", "MRK"),
        "luke": ("Luke", "LUK"), "john": ("John", "JHN"),
        "acts": ("Acts", "ACT"), "romans": ("Romans", "ROM"),
        "1_corinthians": ("1 Corinthians", "1CO"),
        "2_corinthians": ("2 Corinthians", "2CO"),
        "galatians": ("Galatians", "GAL"),
        "ephesians": ("Ephesians", "EPH"),
        "philippians": ("Philippians", "PHP"),
        "colossians": ("Colossians", "COL"),
        "1_thessalonians": ("1 Thessalonians", "1TH"),
        "2_thessalonians": ("2 Thessalonians", "2TH"),
        "1_timothy": ("1 Timothy", "1TI"),
        "2_timothy": ("2 Timothy", "2TI"),
        "titus": ("Titus", "TIT"), "philemon": ("Philemon", "PHM"),
        "hebrews": ("Hebrews", "HEB"), "james": ("James", "JAS"),
        "1_peter": ("1 Peter", "1PE"), "2_peter": ("2 Peter", "2PE"),
        "1_john": ("1 John", "1JN"), "2_john": ("2 John", "2JN"),
        "3_john": ("3 John", "3JN"), "jude": ("Jude", "JUD"),
        "revelation": ("Revelation", "REV"),
    },
}


def head_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return ""


def display_name_for(book_slug: str, testament: str) -> tuple[str, str]:
    t = BOOK_META.get(testament, {}).get(book_slug)
    if t:
        return t
    return book_slug.replace("_", " ").title(), book_slug.upper()[:3]


def walk_verses() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not TRANSLATION_ROOT.exists():
        return out
    for testament_dir in TRANSLATION_ROOT.iterdir():
        if not testament_dir.is_dir():
            continue
        testament = testament_dir.name
        for book_dir in testament_dir.iterdir():
            if not book_dir.is_dir():
                continue
            book_slug = book_dir.name
            display, sbl_code = display_name_for(book_slug, testament)
            for chapter_dir in book_dir.iterdir():
                if not chapter_dir.is_dir():
                    continue
                try:
                    chapter_num = int(chapter_dir.name)
                except ValueError:
                    continue
                for yaml_path in chapter_dir.glob("*.yaml"):
                    try:
                        verse_num = int(yaml_path.stem)
                    except ValueError:
                        continue
                    try:
                        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    revs = data.get("revisions") or []
                    if not revs:
                        continue
                    for rev in revs:
                        if not isinstance(rev, dict):
                            continue
                        out.append({
                            "id": f"{sbl_code}.{chapter_num}.{verse_num}",
                            "testament": testament,
                            "book_slug": book_slug,
                            "book_display": display,
                            "chapter": chapter_num,
                            "verse": verse_num,
                            "timestamp": rev.get("timestamp"),
                            "adjudicator": rev.get("adjudicator"),
                            "reviewer_model": rev.get("reviewer_model"),
                            "category": rev.get("category"),
                            "tier": rev.get("tier"),
                            "from": rev.get("from"),
                            "to": rev.get("to"),
                            "rationale": rev.get("rationale"),
                            "source_review": rev.get("source_review"),
                        })
    return out


def build_index() -> dict[str, Any]:
    revisions = walk_verses()
    # Sort newest first
    revisions.sort(key=lambda r: r.get("timestamp") or "", reverse=True)

    by_category: Counter = Counter()
    by_tier: Counter = Counter()
    by_adjudicator: Counter = Counter()
    by_reviewer: Counter = Counter()
    by_book_slug: dict[str, dict[str, Any]] = {}
    verse_ids: set[str] = set()

    for rev in revisions:
        by_category[rev.get("category") or "other"] += 1
        tier = rev.get("tier")
        if tier is not None:
            by_tier[str(tier)] += 1
        by_adjudicator[rev.get("adjudicator") or "unknown"] += 1
        by_reviewer[rev.get("reviewer_model") or "unknown"] += 1
        slug = rev["book_slug"]
        info = by_book_slug.setdefault(slug, {
            "display": rev["book_display"],
            "testament": rev["testament"],
            "verse_count": 0,  # distinct verses
            "revision_count": 0,
            "distinct_verses": set(),
        })
        info["revision_count"] += 1
        info["distinct_verses"].add(rev["id"])
        verse_ids.add(rev["id"])

    # Finalize book metadata
    by_book: dict[str, Any] = {}
    for slug, info in by_book_slug.items():
        by_book[slug] = {
            "display": info["display"],
            "testament": info["testament"],
            "verse_count": len(info["distinct_verses"]),
            "revision_count": info["revision_count"],
        }

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit_sha": head_commit_sha(),
        "schema_version": SCHEMA_VERSION,
        "totals": {
            "verses_with_revisions": len(verse_ids),
            "total_revisions": len(revisions),
            "by_category": dict(by_category),
            "by_tier": dict(by_tier),
            "by_adjudicator": dict(by_adjudicator),
            "by_reviewer_model": dict(by_reviewer),
        },
        "by_book": by_book,
        "revisions": revisions,
    }


def main() -> int:
    index = build_index()
    OUT_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    t = index["totals"]
    print(f"Wrote {OUT_PATH}")
    print(f"  {t['total_revisions']} revisions across {t['verses_with_revisions']} verses")
    print(f"  by_category: {t['by_category']}")
    print(f"  by_tier: {t['by_tier']}")
    print(f"  by_adjudicator: {t['by_adjudicator']}")
    print(f"  books touched: {len(index['by_book'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
