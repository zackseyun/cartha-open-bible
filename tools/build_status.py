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

# Canonical Protestant ordering + chapter counts. These are the
# denominator for coverage percentages. Verse counts vary with the
# critical text (SBLGNT's shorter Mark, for example), so we only claim
# chapters as a stable canonical unit. Verse totals shown in the UI are
# raw drafted counts, not a fraction.
NT_BOOKS: list[tuple[str, str, int]] = [
    ("Matthew", "MAT", 28), ("Mark", "MRK", 16), ("Luke", "LUK", 24),
    ("John", "JHN", 21), ("Acts", "ACT", 28), ("Romans", "ROM", 16),
    ("1 Corinthians", "1CO", 16), ("2 Corinthians", "2CO", 13),
    ("Galatians", "GAL", 6), ("Ephesians", "EPH", 6),
    ("Philippians", "PHP", 4), ("Colossians", "COL", 4),
    ("1 Thessalonians", "1TH", 5), ("2 Thessalonians", "2TH", 3),
    ("1 Timothy", "1TI", 6), ("2 Timothy", "2TI", 4),
    ("Titus", "TIT", 3), ("Philemon", "PHM", 1),
    ("Hebrews", "HEB", 13), ("James", "JAS", 5),
    ("1 Peter", "1PE", 5), ("2 Peter", "2PE", 3),
    ("1 John", "1JN", 5), ("2 John", "2JN", 1), ("3 John", "3JN", 1),
    ("Jude", "JUD", 1), ("Revelation", "REV", 22),
]

OT_BOOKS: list[tuple[str, str, int]] = [
    ("Genesis", "GEN", 50), ("Exodus", "EXO", 40),
    ("Leviticus", "LEV", 27), ("Numbers", "NUM", 36),
    ("Deuteronomy", "DEU", 34), ("Joshua", "JOS", 24),
    ("Judges", "JDG", 21), ("Ruth", "RUT", 4),
    ("1 Samuel", "1SA", 31), ("2 Samuel", "2SA", 24),
    ("1 Kings", "1KI", 22), ("2 Kings", "2KI", 25),
    ("1 Chronicles", "1CH", 29), ("2 Chronicles", "2CH", 36),
    ("Ezra", "EZR", 10), ("Nehemiah", "NEH", 13),
    ("Esther", "EST", 10), ("Job", "JOB", 42),
    ("Psalms", "PSA", 150), ("Proverbs", "PRO", 31),
    ("Ecclesiastes", "ECC", 12), ("Song of Solomon", "SNG", 8),
    ("Isaiah", "ISA", 66), ("Jeremiah", "JER", 52),
    ("Lamentations", "LAM", 5), ("Ezekiel", "EZK", 48),
    ("Daniel", "DAN", 12), ("Hosea", "HOS", 14),
    ("Joel", "JOL", 3), ("Amos", "AMO", 9),
    ("Obadiah", "OBA", 1), ("Jonah", "JON", 4),
    ("Micah", "MIC", 7), ("Nahum", "NAM", 3),
    ("Habakkuk", "HAB", 3), ("Zephaniah", "ZEP", 3),
    ("Haggai", "HAG", 2), ("Zechariah", "ZEC", 14),
    ("Malachi", "MAL", 4),
]


def book_slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def count_book(testament: str, book: str, chapter_count: int) -> dict[str, int]:
    """Count chapters + verses drafted for a single book."""
    slug = book_slug(book)
    book_dir = TRANSLATION_ROOT / testament / slug
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


def build_books(testament: str, catalog: list[tuple[str, str, int]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, code, chapters_total in catalog:
        counts = count_book(testament, name, chapters_total)
        rows.append({
            "book": name,
            "code": code,
            "testament": testament,
            "slug": book_slug(name),
            "chapters_total": chapters_total,
            **counts,
        })
    return rows


def testament_totals(books: list[dict[str, Any]]) -> dict[str, int]:
    books_drafted = sum(1 for b in books if b["chapters_drafted"] > 0)
    chapters_drafted = sum(b["chapters_drafted"] for b in books)
    chapters_total = sum(b["chapters_total"] for b in books)
    verses_drafted = sum(b["verses_drafted"] for b in books)
    return {
        "books_drafted": books_drafted,
        "books_total": len(books),
        "chapters_drafted": chapters_drafted,
        "chapters_total": chapters_total,
        "verses_drafted": verses_drafted,
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
    all_books = nt + ot

    nt_totals = testament_totals(nt)
    ot_totals = testament_totals(ot)
    totals = {
        "books_drafted": nt_totals["books_drafted"] + ot_totals["books_drafted"],
        "books_total": nt_totals["books_total"] + ot_totals["books_total"],
        "chapters_drafted": nt_totals["chapters_drafted"] + ot_totals["chapters_drafted"],
        "chapters_total": nt_totals["chapters_total"] + ot_totals["chapters_total"],
        "verses_drafted": nt_totals["verses_drafted"] + ot_totals["verses_drafted"],
        "nt": nt_totals,
        "ot": ot_totals,
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
