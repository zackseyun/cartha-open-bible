#!/usr/bin/env python3
"""chapter_queue.py — Queue and ledger for chapter-based Bible drafting."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft  # noqa: E402
import run_phase  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "state"
DEFAULT_DB_PATH = STATE_DIR / "chapter_queue.sqlite3"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def db_path_from(root: pathlib.Path | None = None) -> pathlib.Path:
    base = root or REPO_ROOT
    return base / "state" / "chapter_queue.sqlite3"


def connect(db_path: pathlib.Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
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
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase TEXT NOT NULL,
            phase_order INTEGER NOT NULL,
            testament TEXT NOT NULL,
            book_code TEXT NOT NULL,
            book_slug TEXT NOT NULL,
            book_order INTEGER NOT NULL,
            chapter INTEGER NOT NULL,
            verse_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT,
            worktree_path TEXT,
            commit_sha TEXT,
            merge_commit_sha TEXT,
            last_error TEXT,
            claimed_at TEXT,
            completed_at TEXT,
            merged_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(phase, book_code, chapter)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_status_order ON jobs(status, phase_order, book_order, chapter);
        CREATE INDEX IF NOT EXISTS idx_jobs_phase_order ON jobs(phase, book_order, chapter);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def chapter_verse_counts(book_code: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    for verse in draft.iter_source_verses(book_code):
        counts.setdefault(verse.chapter, 0)
        counts[verse.chapter] += 1
    return counts


def existing_chapter_complete(testament: str, book_code: str, chapter: int, verse_count: int, repo_root: pathlib.Path) -> bool:
    slug = draft.book_slug_for_code(book_code)
    chapter_dir = repo_root / "translation" / testament / slug / f"{chapter:03d}"
    if not chapter_dir.exists():
        return False
    return len(list(chapter_dir.glob("*.yaml"))) >= verse_count


def all_phase_jobs(phases: list[str] | None = None) -> list[dict[str, Any]]:
    selected = phases or list(run_phase.PHASES.keys())
    jobs: list[dict[str, Any]] = []
    for phase_order, phase_name in enumerate(selected):
        phase = run_phase.PHASES[phase_name]
        for book_order, book_code in enumerate(phase["books"]):
            slug = draft.book_slug_for_code(book_code)
            for chapter, verse_count in chapter_verse_counts(book_code).items():
                jobs.append(
                    {
                        "phase": phase_name,
                        "phase_order": phase_order,
                        "testament": phase["testament"],
                        "book_code": book_code,
                        "book_slug": slug,
                        "book_order": book_order,
                        "chapter": chapter,
                        "verse_count": verse_count,
                    }
                )
    return jobs


def append_event(conn: sqlite3.Connection, job_id: int | None, event_type: str, payload: dict[str, Any] | None = None) -> None:
    conn.execute(
        "INSERT INTO events (job_id, ts, event_type, payload_json) VALUES (?, ?, ?, ?)",
        (job_id, utc_now(), event_type, json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)),
    )


def init_queue(*, db_path: pathlib.Path, phases: list[str] | None = None, repo_root: pathlib.Path = REPO_ROOT, reset_failed: bool = False) -> dict[str, int]:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        created = 0
        updated = 0
        for job in all_phase_jobs(phases):
            now = utc_now()
            complete = existing_chapter_complete(job["testament"], job["book_code"], job["chapter"], job["verse_count"], repo_root)
            status = STATUS_COMPLETED if complete else STATUS_PENDING
            row = conn.execute(
                "SELECT id, status FROM jobs WHERE phase=? AND book_code=? AND chapter=?",
                (job["phase"], job["book_code"], job["chapter"]),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        phase, phase_order, testament, book_code, book_slug, book_order,
                        chapter, verse_count, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job["phase"], job["phase_order"], job["testament"], job["book_code"],
                        job["book_slug"], job["book_order"], job["chapter"], job["verse_count"],
                        status, now, now,
                    ),
                )
                created += 1
            else:
                should_reset = reset_failed and row["status"] == STATUS_FAILED
                if should_reset or (complete and row["status"] != STATUS_COMPLETED):
                    conn.execute(
                        "UPDATE jobs SET status=?, updated_at=?, completed_at=COALESCE(completed_at, ?) WHERE id=?",
                        (status, now, now if complete else None, row["id"]),
                    )
                    updated += 1
        conn.commit()
        summary = conn.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
        return {row["status"]: row["c"] for row in summary} | {"created": created, "updated": updated}


def claim_next_job(*, db_path: pathlib.Path, worker_id: str, worktree_path: str | None = None, phases: list[str] | None = None, books: list[str] | None = None) -> dict[str, Any] | None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        query = "SELECT * FROM jobs WHERE status=?"
        params: list[Any] = [STATUS_PENDING]
        if phases:
            query += " AND phase IN ({})".format(",".join("?" for _ in phases))
            params.extend(phases)
        if books:
            query += " AND book_code IN ({})".format(",".join("?" for _ in books))
            params.extend(books)
        query += " ORDER BY phase_order, book_order, chapter LIMIT 1"
        row = conn.execute(query, params).fetchone()
        if row is None:
            conn.commit()
            return None
        now = utc_now()
        conn.execute(
            """
            UPDATE jobs
            SET status=?, worker_id=?, worktree_path=?, attempts=attempts+1, claimed_at=?, updated_at=?
            WHERE id=?
            """,
            (STATUS_RUNNING, worker_id, worktree_path, now, now, row["id"]),
        )
        append_event(conn, row["id"], "claim", {"worker_id": worker_id, "worktree_path": worktree_path})
        conn.commit()
        claimed = conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        return dict(claimed)


def mark_completed(*, db_path: pathlib.Path, job_id: int, commit_sha: str) -> None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        now = utc_now()
        conn.execute(
            "UPDATE jobs SET status=?, commit_sha=?, completed_at=?, updated_at=? WHERE id=?",
            (STATUS_COMPLETED, commit_sha, now, now, job_id),
        )
        append_event(conn, job_id, "complete", {"commit_sha": commit_sha})
        conn.commit()


def mark_failed(*, db_path: pathlib.Path, job_id: int, error_text: str) -> None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        now = utc_now()
        conn.execute(
            "UPDATE jobs SET status=?, last_error=?, updated_at=? WHERE id=?",
            (STATUS_FAILED, error_text[:4000], now, job_id),
        )
        append_event(conn, job_id, "fail", {"error": error_text[:2000]})
        conn.commit()


def mark_merged(*, db_path: pathlib.Path, job_id: int, merge_commit_sha: str) -> None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        now = utc_now()
        conn.execute(
            "UPDATE jobs SET merge_commit_sha=?, merged_at=?, updated_at=? WHERE id=?",
            (merge_commit_sha, now, now, job_id),
        )
        append_event(conn, job_id, "merge", {"merge_commit_sha": merge_commit_sha})
        conn.commit()


def list_ready_to_merge(*, db_path: pathlib.Path, phases: list[str] | None = None) -> list[dict[str, Any]]:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        query = "SELECT * FROM jobs WHERE status=? AND commit_sha IS NOT NULL AND merged_at IS NULL"
        params: list[Any] = [STATUS_COMPLETED]
        if phases:
            query += " AND phase IN ({})".format(",".join("?" for _ in phases))
            params.extend(phases)
        query += " ORDER BY phase_order, book_order, chapter"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def summary_rows(*, db_path: pathlib.Path) -> list[dict[str, Any]]:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        rows = conn.execute(
            "SELECT phase, status, COUNT(*) AS count FROM jobs GROUP BY phase, status ORDER BY phase_order, status"
        ).fetchall()
        return [dict(r) for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite path (default: state/chapter_queue.sqlite3)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--phase", action="append", choices=sorted(run_phase.PHASES), dest="phases")
    p_init.add_argument("--reset-failed", action="store_true")

    p_claim = sub.add_parser("claim")
    p_claim.add_argument("--worker-id", required=True)
    p_claim.add_argument("--worktree-path")
    p_claim.add_argument("--phase", action="append", dest="phases")
    p_claim.add_argument("--book", action="append", dest="books")

    p_complete = sub.add_parser("complete")
    p_complete.add_argument("job_id", type=int)
    p_complete.add_argument("--commit-sha", required=True)

    p_fail = sub.add_parser("fail")
    p_fail.add_argument("job_id", type=int)
    p_fail.add_argument("--error", required=True)

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("job_id", type=int)
    p_merge.add_argument("--merge-commit-sha", required=True)

    sub.add_parser("summary")
    sub.add_parser("ready")

    args = parser.parse_args()
    db_path = pathlib.Path(args.db)

    if args.cmd == "init":
        result = init_queue(db_path=db_path, phases=args.phases, reset_failed=args.reset_failed)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.cmd == "claim":
        job = claim_next_job(db_path=db_path, worker_id=args.worker_id, worktree_path=args.worktree_path, phases=args.phases, books=args.books)
        print(json.dumps(job, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.cmd == "complete":
        mark_completed(db_path=db_path, job_id=args.job_id, commit_sha=args.commit_sha)
        return 0
    if args.cmd == "fail":
        mark_failed(db_path=db_path, job_id=args.job_id, error_text=args.error)
        return 0
    if args.cmd == "merge":
        mark_merged(db_path=db_path, job_id=args.job_id, merge_commit_sha=args.merge_commit_sha)
        return 0
    if args.cmd == "summary":
        print(json.dumps(summary_rows(db_path=db_path), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "ready":
        print(json.dumps(list_ready_to_merge(db_path=db_path), indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
