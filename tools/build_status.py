#!/usr/bin/env python3
"""Emit ``status.json`` — the public trust-layer dashboard data.

Walks ``translation/`` to count chapters and verses drafted per book,
pulls recent ``revise:`` / ``polish:`` commits from git log, and pins
the result to the current HEAD SHA. The output is committed at the
repo root so the Cartha Open Bible website can fetch it from
``raw.githubusercontent.com/.../main/status.json`` with no backend.

This is intentionally fast and cache-free: no YAML parsing, no schema
validation. Every signal is derived from directory structure + git log
so the script stays under ~1s on a cold run. Deeper per-verse signals
(footnote counts, cross-check agreement) are deferred until we have a
reason for them and a way to update them on a cadence.

Run from the repo root::

    python3 tools/build_status.py
    git add status.json && git commit -m "status: regenerate snapshot"
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
STATUS_PATH = REPO_ROOT / "status.json"

# Canonical Protestant ordering with chapter *and* verse counts per
# book. Chapter counts are stable across major critical editions.
# Verse counts are the Protestant reference numbers (Masoretic Text for
# OT, NA28/UBS5 for NT) and are the denominator the public /progress
# page reports against. Drafted verse counts (the numerator) are derived
# from the filesystem — the gap between drafted and these targets is
# what "N% of the canon" means on the dashboard.
NT_BOOKS: list[tuple[str, str, int, int]] = [
    ("Matthew", "MAT", 28, 1071), ("Mark", "MRK", 16, 678),
    ("Luke", "LUK", 24, 1151), ("John", "JHN", 21, 879),
    ("Acts", "ACT", 28, 1007), ("Romans", "ROM", 16, 433),
    ("1 Corinthians", "1CO", 16, 437), ("2 Corinthians", "2CO", 13, 257),
    ("Galatians", "GAL", 6, 149), ("Ephesians", "EPH", 6, 155),
    ("Philippians", "PHP", 4, 104), ("Colossians", "COL", 4, 95),
    ("1 Thessalonians", "1TH", 5, 89), ("2 Thessalonians", "2TH", 3, 47),
    ("1 Timothy", "1TI", 6, 113), ("2 Timothy", "2TI", 4, 83),
    ("Titus", "TIT", 3, 46), ("Philemon", "PHM", 1, 25),
    ("Hebrews", "HEB", 13, 303), ("James", "JAS", 5, 108),
    ("1 Peter", "1PE", 5, 105), ("2 Peter", "2PE", 3, 61),
    ("1 John", "1JN", 5, 105), ("2 John", "2JN", 1, 13),
    ("3 John", "3JN", 1, 14), ("Jude", "JUD", 1, 25),
    ("Revelation", "REV", 22, 404),
]

OT_BOOKS: list[tuple[str, str, int, int]] = [
    ("Genesis", "GEN", 50, 1533), ("Exodus", "EXO", 40, 1213),
    ("Leviticus", "LEV", 27, 859), ("Numbers", "NUM", 36, 1288),
    ("Deuteronomy", "DEU", 34, 959), ("Joshua", "JOS", 24, 658),
    ("Judges", "JDG", 21, 618), ("Ruth", "RUT", 4, 85),
    ("1 Samuel", "1SA", 31, 810), ("2 Samuel", "2SA", 24, 695),
    ("1 Kings", "1KI", 22, 816), ("2 Kings", "2KI", 25, 719),
    ("1 Chronicles", "1CH", 29, 942), ("2 Chronicles", "2CH", 36, 822),
    ("Ezra", "EZR", 10, 280), ("Nehemiah", "NEH", 13, 406),
    ("Esther", "EST", 10, 167), ("Job", "JOB", 42, 1070),
    ("Psalms", "PSA", 150, 2461), ("Proverbs", "PRO", 31, 915),
    ("Ecclesiastes", "ECC", 12, 222), ("Song of Solomon", "SNG", 8, 117),
    ("Isaiah", "ISA", 66, 1292), ("Jeremiah", "JER", 52, 1364),
    ("Lamentations", "LAM", 5, 154), ("Ezekiel", "EZK", 48, 1273),
    ("Daniel", "DAN", 12, 357), ("Hosea", "HOS", 14, 197),
    ("Joel", "JOL", 3, 73), ("Amos", "AMO", 9, 146),
    ("Obadiah", "OBA", 1, 21), ("Jonah", "JON", 4, 48),
    ("Micah", "MIC", 7, 105), ("Nahum", "NAM", 3, 47),
    ("Habakkuk", "HAB", 3, 56), ("Zephaniah", "ZEP", 3, 53),
    ("Haggai", "HAG", 2, 38), ("Zechariah", "ZEC", 14, 211),
    ("Malachi", "MAL", 4, 55),
]

# Deuterocanonical (Apocrypha) targets. Verse totals are the standard
# LXX / NRSV reference counts so the progress page has a meaningful
# denominator even before we drill into per-chapter verse parity.
# Slugs must match the directories under ``translation/deuterocanon/``
# (see ``lxx_swete.DEUTEROCANONICAL_BOOKS``).
# Extra-canonical (Apostolic Fathers + pseudepigrapha + Nag Hammadi)
# target books. Chapter-level layout: translation/extra_canonical/
# <slug>/<NNN>.yaml — one YAML per chapter, continuous-prose
# translation block. Verse totals here are "number of chapters" for
# consistency with the mobile export (each chapter ships as a single
# synthetic verse).
EXTRA_CANONICAL_BOOKS: list[tuple[str, str, int, int, str]] = [
    # Verse totals reflect the actual per-verse split produced by
    # tools/split_extra_canonical_into_verses.py at the scholarly-
    # standard divisions (Lightfoot / Funk / Niederwimmer).
    ("Didache", "DID", 16, 100, "didache"),
    ("1 Clement", "1CLEM", 65, 395, "1_clement"),
    ("2 Esdras", "2ES", 16, 942, "2_esdras"),
]

# Books in EXTRA_CANONICAL_BOOKS that are presented as an Appendix
# rather than as peers of the Apostolic Fathers. Per 2ESDRAS.md these
# are tracked in their own Appendix track in the reading interface and
# do not count toward the Apocrypha completion metric. The frontend
# reads the ``appendix`` flag on each book row to render the tag.
APPENDIX_SLUGS: frozenset[str] = frozenset({"2_esdras"})


DEUTEROCANON_BOOKS: list[tuple[str, str, int, int, str]] = [
    ("Tobit", "TOB", 14, 244, "tobit"),
    ("Judith", "JDT", 16, 339, "judith"),
    ("Additions to Esther", "ESG", 6, 107, "additions_to_esther"),
    ("Wisdom of Solomon", "WIS", 19, 436, "wisdom_of_solomon"),
    ("Sirach", "SIR", 51, 1467, "sirach"),
    ("Baruch", "BAR", 5, 213, "baruch"),
    ("Letter of Jeremiah", "LJE", 1, 72, "letter_of_jeremiah"),
    ("Prayer of Azariah and Song of the Three", "PAZ", 1, 68, "prayer_of_azariah"),
    ("Susanna", "SUS", 1, 64, "susanna"),
    ("Bel and the Dragon", "BEL", 1, 42, "bel_and_the_dragon"),
    ("1 Maccabees", "1MA", 16, 924, "1_maccabees"),
    ("2 Maccabees", "2MA", 15, 555, "2_maccabees"),
    ("3 Maccabees", "3MA", 7, 228, "3_maccabees"),
    ("4 Maccabees", "4MA", 18, 482, "4_maccabees"),
    ("1 Esdras", "1ES", 9, 439, "1_esdras"),
    ("Prayer of Manasseh", "MAN", 1, 15, "prayer_of_manasseh"),
    ("Psalm 151", "PS151", 1, 7, "psalm_151"),
    ("Psalms of Solomon", "PSS", 18, 330, "psalms_of_solomon"),
]


def book_slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def count_book(
    testament: str,
    book: str,
    chapter_count: int,
    slug: str | None = None,
) -> dict[str, int]:
    """Count chapters + verses drafted for a single book.

    OT / NT directory names are derivable from the book title, but the
    deuterocanonical catalog carries its own slug (e.g. ``1_maccabees``
    isn't a lower+underscore transform of the title since the display
    form is ``1 Maccabees``). Callers pass ``slug`` explicitly when the
    on-disk directory name diverges from ``book_slug(book)``.
    """
    resolved_slug = slug or book_slug(book)
    book_dir = TRANSLATION_ROOT / testament / resolved_slug
    if not book_dir.is_dir():
        return {"chapters_drafted": 0, "verses_drafted": 0}
    chapter_dirs = [p for p in book_dir.iterdir() if p.is_dir() and p.name.isdigit()]
    verses = sum(
        1
        for ch in chapter_dirs
        for f in ch.iterdir()
        if f.is_file() and f.suffix == ".yaml"
    )
    return {"chapters_drafted": len(chapter_dirs), "verses_drafted": verses}


def recent_translation_commits(limit: int = 40) -> list[dict[str, str]]:
    """Last ``limit`` commits that touched ``translation/`` — revisions
    and drafts both land here and are surfaced as activity."""
    raw = subprocess.check_output(
        [
            "git", "log",
            f"-{limit}",
            "--date=iso-strict",
            "--pretty=format:%H\t%h\t%ad\t%s",
            "--",
            "translation/",
        ],
        cwd=REPO_ROOT, text=True,
    )
    out: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        full, short, date, subject = parts
        # The revision-pass commits and mechanical normalizations all
        # start with lowercase verbs. Tag them so the UI can show just
        # the revision subset when the reader flips a filter.
        lower_subject = subject.lower()
        is_revision = any(
            lower_subject.startswith(prefix)
            for prefix in ("revise", "polish", "normalize", "rename", "consistency")
        )
        out.append({
            "sha": full,
            "short": short,
            "date": date,
            "subject": subject,
            "is_revision": is_revision,
        })
    return out


def build_books(testament: str, catalog: list[tuple[str, str, int, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, code, chapters_total, verses_total in catalog:
        counts = count_book(testament, name, chapters_total)
        rows.append({
            "book": name,
            "code": code,
            "testament": testament,
            "slug": book_slug(name),
            "chapters_total": chapters_total,
            "verses_total": verses_total,
            **counts,
        })
    return rows


def build_deuterocanon_books(
    catalog: list[tuple[str, str, int, int, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, code, chapters_total, verses_total, slug in catalog:
        counts = count_book("deuterocanon", name, chapters_total, slug=slug)
        rows.append({
            "book": name,
            "code": code,
            "testament": "deuterocanon",
            "slug": slug,
            "chapters_total": chapters_total,
            "verses_total": verses_total,
            **counts,
        })
    return rows


def count_extra_canonical_book(slug: str) -> dict[str, int]:
    """Counts chapters + verses for extra-canonical books.

    Supports both layouts:
      - Flat chapter-level: translation/extra_canonical/<slug>/<NNN>.yaml
        (drafter output; authoritative record).
      - Nested verse-level: translation/extra_canonical/<slug>/<NNN>/<VVV>.yaml
        (produced by tools/split_extra_canonical_into_verses.py;
        drives mobile/CDN reader surfaces and per-verse bookmarks).

    A chapter counts as drafted if EITHER layout has it. Verse count
    is the verse-level files when they exist; falls back to
    chapter-level files (treated as 1-synthetic-verse) if no nested
    directories are present for a given book.
    """
    book_dir = TRANSLATION_ROOT / "extra_canonical" / slug
    if not book_dir.is_dir():
        return {"chapters_drafted": 0, "verses_drafted": 0}

    chapters = set()
    verses_drafted = 0
    has_verse_level = False

    # Nested verse-level layout
    for entry in book_dir.iterdir():
        if entry.is_dir() and entry.name.isdigit():
            has_verse_level = True
            chapters.add(int(entry.name))
            for vf in entry.iterdir():
                if vf.is_file() and vf.suffix == ".yaml" and vf.stem.isdigit():
                    verses_drafted += 1

    # Flat chapter-level layout (count chapters either way; verses only
    # if the verse-level layout is absent)
    flat_chapter_files = [
        p for p in book_dir.iterdir()
        if p.is_file() and p.suffix == ".yaml" and p.stem.isdigit()
    ]
    for p in flat_chapter_files:
        chapters.add(int(p.stem))
    if not has_verse_level:
        verses_drafted = len(flat_chapter_files)

    return {
        "chapters_drafted": len(chapters),
        "verses_drafted": verses_drafted,
    }


def build_extra_canonical_books(
    catalog: list[tuple[str, str, int, int, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, code, chapters_total, verses_total, slug in catalog:
        counts = count_extra_canonical_book(slug)
        row = {
            "book": name,
            "code": code,
            "testament": "extra_canonical",
            "slug": slug,
            "chapters_total": chapters_total,
            "verses_total": verses_total,
            **counts,
        }
        if slug in APPENDIX_SLUGS:
            row["appendix"] = True
        rows.append(row)
    return rows


def testament_totals(books: list[dict[str, Any]]) -> dict[str, int]:
    books_drafted = sum(1 for b in books if b["chapters_drafted"] > 0)
    chapters_drafted = sum(b["chapters_drafted"] for b in books)
    chapters_total = sum(b["chapters_total"] for b in books)
    verses_drafted = sum(b["verses_drafted"] for b in books)
    verses_total = sum(b["verses_total"] for b in books)
    return {
        "books_drafted": books_drafted,
        "books_total": len(books),
        "chapters_drafted": chapters_drafted,
        "chapters_total": chapters_total,
        "verses_drafted": verses_drafted,
        "verses_total": verses_total,
    }


def git_head() -> tuple[str, str]:
    full = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    short = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    return full, short


def main() -> int:
    nt = build_books("nt", NT_BOOKS)
    ot = build_books("ot", OT_BOOKS)
    deuterocanon = build_deuterocanon_books(DEUTEROCANON_BOOKS)
    extra_canonical = build_extra_canonical_books(EXTRA_CANONICAL_BOOKS)
    all_books = nt + ot + deuterocanon + extra_canonical

    nt_totals = testament_totals(nt)
    ot_totals = testament_totals(ot)
    dc_totals = testament_totals(deuterocanon)
    ec_totals = testament_totals(extra_canonical)
    # Top-line ``books_total`` / ``verses_total`` stay pinned to the
    # 66-book Protestant canon so the "% of the canon" hint on the
    # progress page keeps its original meaning. Deuterocanonical and
    # extra-canonical progress are reported as their own sibling
    # blocks so readers can see them without the main percentage
    # jumping around as those books land.
    totals = {
        "books_drafted": nt_totals["books_drafted"] + ot_totals["books_drafted"],
        "books_total": nt_totals["books_total"] + ot_totals["books_total"],
        "chapters_drafted": nt_totals["chapters_drafted"] + ot_totals["chapters_drafted"],
        "chapters_total": nt_totals["chapters_total"] + ot_totals["chapters_total"],
        "verses_drafted": nt_totals["verses_drafted"] + ot_totals["verses_drafted"],
        "verses_total": nt_totals["verses_total"] + ot_totals["verses_total"],
        "nt": nt_totals,
        "ot": ot_totals,
        "deuterocanon": dc_totals,
        "extra_canonical": ec_totals,
    }

    full_sha, short_sha = git_head()

    payload = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "commit_sha": full_sha,
        "commit_short": short_sha,
        "repo": "zackseyun/cartha-open-bible",
        "totals": totals,
        "books": all_books,
        "recent_commits": recent_translation_commits(40),
    }

    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {STATUS_PATH.relative_to(REPO_ROOT)}")
    print(
        f"  {totals['books_drafted']}/{totals['books_total']} books · "
        f"{totals['chapters_drafted']}/{totals['chapters_total']} chapters · "
        f"{totals['verses_drafted']} verses drafted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
