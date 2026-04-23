#!/usr/bin/env python3
"""gemini_review_queue.py — queue Gemini Pro translation-review jobs.

Parallel to chapter_queue.py (which queues DRAFTING jobs for the primary
drafter). This table queues REVIEW jobs: each row is one verse (or one
chapter) to be cross-checked by Gemini 2.5 Pro.

Design:
  - Jobs live in a new table `review_jobs` inside the same SQLite DB as
    chapter_queue, so the dashboard server can surface both in one
    view.
  - Three job-submission strategies:
      1. high_scrutiny — every verse of Gen, Psalms, Matt, Mark, Luke,
         John, Romans (the most-read books).
      2. weighted_vocab — verses whose `lexical_decisions` mention one
         of the theologically-weighted Greek/Hebrew lemmas (δικαιοσύνη,
         λόγος, πνεῦμα, ἀγάπη, חֶסֶד, …). Translation choice matters
         most here.
      3. random_sample — reproducible ~5% random sample across the
         full committed corpus (seed-pinned).

Usage:
  # Initial submission
  python3 tools/gemini_review_queue.py submit --strategy high_scrutiny
  python3 tools/gemini_review_queue.py submit --strategy weighted_vocab
  python3 tools/gemini_review_queue.py submit --strategy random_sample

  # Check queue summary
  python3 tools/gemini_review_queue.py status

  # Clear a strategy (or all)
  python3 tools/gemini_review_queue.py clear --strategy weighted_vocab
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import pathlib
import random
import re
import sqlite3
import sys
from collections import Counter
from typing import Any, Iterable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = chapter_queue.DEFAULT_DB_PATH
TRANSLATION_ROOT = REPO_ROOT / "translation"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

STRATEGY_HIGH_SCRUTINY = "high_scrutiny"
STRATEGY_WEIGHTED_VOCAB = "weighted_vocab"
STRATEGY_RANDOM_SAMPLE = "random_sample"
STRATEGY_LOW_AGREEMENT_RECHECK = "low_agreement_recheck"  # v2 prompt + context
STRATEGY_ENHANCED_REVIEW = "enhanced_review"               # v2 prompt + context

# Phase 10 — v3 author-intent review on deutero/extra books that didn't
# pass through Phase 9. One strategy per language tradition so supervisor
# logs and status dashboards can distinguish them.
STRATEGY_PHASE10_GREEK_APOCRYPHA = "phase10_greek_apocrypha"
STRATEGY_PHASE10_ETHIOPIC_PSEUDEPIGRAPHA = "phase10_ethiopic_pseudepigrapha"
STRATEGY_PHASE10_COPTIC_GNOSTIC = "phase10_coptic_gnostic"
STRATEGY_PHASE10_SYRIAC_APOCALYPSE = "phase10_syriac_apocalypse"
STRATEGY_PHASE10_T12P = "phase10_t12p"

# Books drawn in the "high-scrutiny" strategy. Book slugs match the
# `translation/<testament>/<slug>/` directory structure.
HIGH_SCRUTINY_BOOKS: list[tuple[str, str]] = [
    ("ot", "genesis"),
    ("ot", "psalms"),
    ("nt", "matthew"),
    ("nt", "mark"),
    ("nt", "luke"),
    ("nt", "john"),
    ("nt", "romans"),
]

# Lemmas whose translation choice is theologically weighted. A verse is
# selected for this strategy if its `lexical_decisions[*].source_word`
# matches one of these (Greek or Hebrew).
WEIGHTED_LEMMAS_GREEK = [
    "δικαιοσύνη", "δίκαιος", "δικαιόω",
    "λόγος",
    "πνεῦμα",
    "ἀγάπη", "ἀγαπάω",
    "πίστις", "πιστεύω",
    "χάρις",
    "ἁμαρτία", "ἁμαρτάνω",
    "σωτηρία", "σῴζω",
    "ἅγιος", "ἁγιάζω",
    "ἀλήθεια",
    "Χριστός",
    "υἱός",
    "βασιλεία",
    "ζωή",
    "ἔλεος",
    "θεός", "Κύριος",
    "σάρξ",
    "μετανοέω", "μετάνοια",
    "εἰρήνη",
]
WEIGHTED_LEMMAS_HEBREW = [
    "חֶסֶד", "אֱמֶת", "צֶדֶק", "מִשְׁפָּט",
    "יְהוָה", "אֱלֹהִים",
    "רוּחַ", "נֶפֶשׁ",
    "תּוֹרָה",
    "שָׁלוֹם",
    "בְּרִית",
    "קֹדֶשׁ",
    "אַהֲבָה", "אָהַב",
    "אֱמוּנָה",
    "חַטָּאת", "חָטָא",
    "יְשׁוּעָה", "יָשַׁע",
    "תְּפִלָּה",
    "מָשִׁיחַ",
    "חָכְמָה",
]
WEIGHTED_LEMMAS = WEIGHTED_LEMMAS_GREEK + WEIGHTED_LEMMAS_HEBREW

RANDOM_SAMPLE_SEED = 20260420
RANDOM_SAMPLE_FRACTION = 0.05


def utc_now() -> str:
    return chapter_queue.utc_now()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS review_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT NOT NULL,
            testament TEXT NOT NULL,
            book_slug TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT,
            review_path TEXT,
            agreement_score REAL,
            issues_found INTEGER,
            last_error TEXT,
            claimed_at TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(strategy, testament, book_slug, chapter, verse, model)
        );
        CREATE INDEX IF NOT EXISTS idx_review_status ON review_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_review_strategy ON review_jobs(strategy, status);
        CREATE INDEX IF NOT EXISTS idx_review_location ON review_jobs(testament, book_slug, chapter, verse);
        """
    )
    conn.commit()


def iter_verse_yamls(testament: str, book_slug: str) -> Iterable[pathlib.Path]:
    """Yield every verse YAML under translation/<testament>/<slug>/*/*.yaml"""
    book_dir = TRANSLATION_ROOT / testament / book_slug
    if not book_dir.exists():
        return
    for chap_dir in sorted(book_dir.iterdir()):
        if not chap_dir.is_dir():
            continue
        for yaml_path in sorted(chap_dir.glob("*.yaml")):
            yield yaml_path


def parse_verse_id(yaml_path: pathlib.Path) -> tuple[int, int] | None:
    try:
        chapter = int(yaml_path.parent.name)
        verse = int(yaml_path.stem)
        return chapter, verse
    except ValueError:
        return None


def yaml_mentions_any_lemma(yaml_path: pathlib.Path, lemmas: Iterable[str]) -> bool:
    """Quick text-grep check: does any target lemma appear in the YAML?

    Works without a YAML parser — lexical_decisions entries contain the
    `source_word` verbatim, which is enough to match. Fast.
    """
    try:
        text = yaml_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for lemma in lemmas:
        if lemma in text:
            return True
    return False


def insert_job(
    conn: sqlite3.Connection,
    *,
    strategy: str,
    testament: str,
    book_slug: str,
    chapter: int,
    verse: int,
    model: str,
) -> bool:
    now = utc_now()
    try:
        conn.execute(
            """
            INSERT INTO review_jobs
                (strategy, testament, book_slug, chapter, verse, model,
                 status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy, testament, book_slug, chapter, verse, model,
                STATUS_PENDING, now, now,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False  # already queued


def submit_high_scrutiny(conn: sqlite3.Connection, model: str) -> dict[str, int]:
    added = Counter()
    for testament, book_slug in HIGH_SCRUTINY_BOOKS:
        for yaml_path in iter_verse_yamls(testament, book_slug):
            parsed = parse_verse_id(yaml_path)
            if not parsed:
                continue
            chapter, verse = parsed
            if insert_job(
                conn,
                strategy=STRATEGY_HIGH_SCRUTINY,
                testament=testament,
                book_slug=book_slug,
                chapter=chapter,
                verse=verse,
                model=model,
            ):
                added[book_slug] += 1
    conn.commit()
    return dict(added)


def submit_weighted_vocab(conn: sqlite3.Connection, model: str) -> dict[str, int]:
    added = Counter()
    # Scan every verse YAML across both testaments for any weighted lemma.
    for testament in ("nt", "ot"):
        testament_root = TRANSLATION_ROOT / testament
        if not testament_root.exists():
            continue
        for book_dir in sorted(testament_root.iterdir()):
            if not book_dir.is_dir():
                continue
            book_slug = book_dir.name
            for yaml_path in iter_verse_yamls(testament, book_slug):
                parsed = parse_verse_id(yaml_path)
                if not parsed:
                    continue
                if not yaml_mentions_any_lemma(yaml_path, WEIGHTED_LEMMAS):
                    continue
                chapter, verse = parsed
                if insert_job(
                    conn,
                    strategy=STRATEGY_WEIGHTED_VOCAB,
                    testament=testament,
                    book_slug=book_slug,
                    chapter=chapter,
                    verse=verse,
                    model=model,
                ):
                    added[book_slug] += 1
    conn.commit()
    return dict(added)


def submit_low_agreement_recheck(
    conn: sqlite3.Connection, model: str, threshold: float = 0.9
) -> dict[str, int]:
    """Re-review every Pass-1 verse that scored below `threshold` using the
    v2 enhanced prompt (chapter context + project doctrine).
    """
    added = Counter()
    rows = conn.execute(
        """
        SELECT testament, book_slug, chapter, verse
        FROM review_jobs
        WHERE status='completed'
          AND agreement_score IS NOT NULL
          AND agreement_score < ?
        """,
        (threshold,),
    ).fetchall()
    for r in rows:
        if insert_job(
            conn,
            strategy=STRATEGY_LOW_AGREEMENT_RECHECK,
            testament=r["testament"],
            book_slug=r["book_slug"],
            chapter=r["chapter"],
            verse=r["verse"],
            model=model,
        ):
            added[r["book_slug"]] += 1
    conn.commit()
    return dict(added)


def submit_enhanced_review_for_books(
    conn: sqlite3.Connection, model: str, books: list[tuple[str, str]]
) -> dict[str, int]:
    """Submit v2 enhanced review for every verse in the given (testament,
    book_slug) pairs. Use for targeted deep-review of key books."""
    added = Counter()
    for testament, book_slug in books:
        for yaml_path in iter_verse_yamls(testament, book_slug):
            parsed = parse_verse_id(yaml_path)
            if not parsed:
                continue
            chapter, verse = parsed
            if insert_job(
                conn,
                strategy=STRATEGY_ENHANCED_REVIEW,
                testament=testament,
                book_slug=book_slug,
                chapter=chapter,
                verse=verse,
                model=model,
            ):
                added[book_slug] += 1
    conn.commit()
    return dict(added)


def submit_phase10(
    conn: sqlite3.Connection,
    model: str,
    strategy: str,
    books: list[tuple[str, str]],
) -> dict[str, int]:
    """Submit v3 author-intent review jobs for Phase 10 books.

    Handles both chapter/verse layouts and flat (section-style) layouts:
    for a flat book (e.g. gospel_of_truth), the filename stem is used as
    'verse' with chapter=1.
    """
    added: Counter[str] = Counter()
    for testament, book_slug in books:
        book_dir = TRANSLATION_ROOT / testament / book_slug
        if not book_dir.exists():
            continue
        # Detect layout: flat if root-level .yaml files exist AND no chapter
        # subdirectories exist. Mixed directories (T12P: chapter YAMLs +
        # verse subdirs after splitting) use the nested iter_verse_yamls path.
        children = list(book_dir.iterdir())
        has_yaml_files = any(p.suffix == ".yaml" for p in children)
        has_subdirs = any(p.is_dir() for p in children)
        flat = has_yaml_files and not has_subdirs
        if flat:
            for yaml_path in sorted(book_dir.glob("*.yaml")):
                try:
                    verse = int(yaml_path.stem)
                except ValueError:
                    continue
                if insert_job(
                    conn,
                    strategy=strategy,
                    testament=testament,
                    book_slug=book_slug,
                    chapter=1,
                    verse=verse,
                    model=model,
                ):
                    added[book_slug] += 1
        else:
            for yaml_path in iter_verse_yamls(testament, book_slug):
                parsed = parse_verse_id(yaml_path)
                if not parsed:
                    continue
                chapter, verse = parsed
                if insert_job(
                    conn,
                    strategy=strategy,
                    testament=testament,
                    book_slug=book_slug,
                    chapter=chapter,
                    verse=verse,
                    model=model,
                ):
                    added[book_slug] += 1
    conn.commit()
    return dict(added)


def submit_random_sample(conn: sqlite3.Connection, model: str) -> dict[str, int]:
    rng = random.Random(RANDOM_SAMPLE_SEED)
    all_verses: list[tuple[str, str, int, int]] = []
    for testament in ("nt", "ot"):
        testament_root = TRANSLATION_ROOT / testament
        if not testament_root.exists():
            continue
        for book_dir in sorted(testament_root.iterdir()):
            if not book_dir.is_dir():
                continue
            book_slug = book_dir.name
            for yaml_path in iter_verse_yamls(testament, book_slug):
                parsed = parse_verse_id(yaml_path)
                if not parsed:
                    continue
                chapter, verse = parsed
                all_verses.append((testament, book_slug, chapter, verse))
    sample_size = int(len(all_verses) * RANDOM_SAMPLE_FRACTION)
    sample = rng.sample(all_verses, sample_size)
    added = Counter()
    for testament, book_slug, chapter, verse in sample:
        if insert_job(
            conn,
            strategy=STRATEGY_RANDOM_SAMPLE,
            testament=testament,
            book_slug=book_slug,
            chapter=chapter,
            verse=verse,
            model=model,
        ):
            added[book_slug] += 1
    conn.commit()
    return dict(added)


def show_status(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT strategy, status, COUNT(*) AS n
        FROM review_jobs
        GROUP BY strategy, status
        ORDER BY strategy, status
        """
    ).fetchall()
    if not rows:
        print("No review jobs queued yet.")
        return
    current = None
    total = 0
    by_strategy_total: dict[str, int] = {}
    for row in rows:
        strat = row["strategy"]
        if strat != current:
            current = strat
            print(f"\n  {strat}:")
        print(f"    {row['status']:12s} {row['n']}")
        total += row["n"]
        by_strategy_total[strat] = by_strategy_total.get(strat, 0) + row["n"]
    print(f"\n  Totals: {total} jobs across {len(by_strategy_total)} strategies")


def clear_jobs(conn: sqlite3.Connection, strategy: str | None) -> int:
    if strategy:
        cur = conn.execute("DELETE FROM review_jobs WHERE strategy=?", (strategy,))
    else:
        cur = conn.execute("DELETE FROM review_jobs")
    conn.commit()
    return cur.rowcount


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_submit = sub.add_parser("submit", help="Submit review jobs for a strategy.")
    p_submit.add_argument(
        "--strategy",
        required=True,
        choices=[
            STRATEGY_HIGH_SCRUTINY,
            STRATEGY_WEIGHTED_VOCAB,
            STRATEGY_RANDOM_SAMPLE,
            STRATEGY_LOW_AGREEMENT_RECHECK,
            STRATEGY_ENHANCED_REVIEW,
            STRATEGY_PHASE10_GREEK_APOCRYPHA,
            STRATEGY_PHASE10_ETHIOPIC_PSEUDEPIGRAPHA,
            STRATEGY_PHASE10_COPTIC_GNOSTIC,
            STRATEGY_PHASE10_SYRIAC_APOCALYPSE,
            STRATEGY_PHASE10_T12P,
        ],
    )
    p_submit.add_argument("--model", default="gemini-3.1-pro-preview")
    p_submit.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="For low_agreement_recheck: rereview every verse below this Pass-1 score.",
    )
    p_submit.add_argument(
        "--books",
        help="For enhanced_review: comma-separated testament:slug list, e.g. 'nt:matthew,ot:genesis'",
    )

    sub.add_parser("status", help="Show review-queue summary.")

    p_clear = sub.add_parser("clear", help="Delete review jobs (by strategy or all).")
    p_clear.add_argument("--strategy")

    p_requeue = sub.add_parser("requeue", help="Reset failed jobs back to pending.")
    p_requeue.add_argument("--strategy")

    args = ap.parse_args()

    with contextlib.closing(connect()) as conn:
        ensure_schema(conn)
        if args.cmd == "submit":
            if args.strategy == STRATEGY_HIGH_SCRUTINY:
                added = submit_high_scrutiny(conn, args.model)
            elif args.strategy == STRATEGY_WEIGHTED_VOCAB:
                added = submit_weighted_vocab(conn, args.model)
            elif args.strategy == STRATEGY_RANDOM_SAMPLE:
                added = submit_random_sample(conn, args.model)
            elif args.strategy == STRATEGY_LOW_AGREEMENT_RECHECK:
                added = submit_low_agreement_recheck(conn, args.model, args.threshold)
            elif args.strategy == STRATEGY_ENHANCED_REVIEW:
                if not args.books:
                    raise SystemExit("--books required for enhanced_review, e.g. 'nt:matthew,ot:genesis'")
                book_list: list[tuple[str, str]] = []
                for tok in args.books.split(","):
                    t, s = tok.split(":")
                    book_list.append((t.strip(), s.strip()))
                added = submit_enhanced_review_for_books(conn, args.model, book_list)
            elif args.strategy in (
                STRATEGY_PHASE10_GREEK_APOCRYPHA,
                STRATEGY_PHASE10_ETHIOPIC_PSEUDEPIGRAPHA,
                STRATEGY_PHASE10_COPTIC_GNOSTIC,
                STRATEGY_PHASE10_SYRIAC_APOCALYPSE,
                STRATEGY_PHASE10_T12P,
            ):
                if not args.books:
                    raise SystemExit(f"--books required for {args.strategy}, e.g. 'deuterocanon:prayer_of_manasseh'")
                book_list = []
                for tok in args.books.split(","):
                    t, s = tok.split(":")
                    book_list.append((t.strip(), s.strip()))
                added = submit_phase10(conn, args.model, args.strategy, book_list)
            else:
                raise AssertionError(args.strategy)
            total = sum(added.values())
            print(f"Submitted {total} new review jobs for strategy {args.strategy!r} (model={args.model}):")
            for slug, n in sorted(added.items(), key=lambda kv: -kv[1]):
                print(f"  {slug:<25s} {n}")
            if not added:
                print("  (all verses already queued for this strategy)")
        elif args.cmd == "status":
            show_status(conn)
        elif args.cmd == "clear":
            n = clear_jobs(conn, args.strategy)
            print(f"Deleted {n} review job(s).")
        elif args.cmd == "requeue":
            now = utc_now()
            query = "UPDATE review_jobs SET status=?, last_error=NULL, attempts=0, claimed_at=NULL, updated_at=? WHERE status=?"
            params = [STATUS_PENDING, now, STATUS_FAILED]
            if args.strategy:
                query += " AND strategy=?"
                params.append(args.strategy)
            cur = conn.execute(query, params)
            conn.commit()
            print(f"Requeued {cur.rowcount} failed job(s) back to pending.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
