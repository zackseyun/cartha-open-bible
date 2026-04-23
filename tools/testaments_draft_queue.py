#!/usr/bin/env python3
"""testaments_draft_queue.py — queue/ledger for Testament chapter drafting."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import pathlib
import sqlite3
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import testaments_twelve_patriarchs as t12p  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "state"
DEFAULT_DB_PATH = STATE_DIR / "testaments_draft_queue.sqlite3"
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "testaments_twelve_patriarchs"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            testament_slug TEXT NOT NULL,
            testament_order INTEGER NOT NULL,
            chapter INTEGER NOT NULL,
            chapter_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            worker_id TEXT,
            started_at TEXT,
            finished_at TEXT,
            available_at TEXT,
            output_path TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(testament_slug, chapter)
        );
        CREATE INDEX IF NOT EXISTS idx_testaments_jobs_status ON jobs(status, testament_order, chapter);
        """
    )
    conn.commit()


def chapter_output_path(testament_slug: str, chapter: int) -> pathlib.Path:
    return TRANSLATION_ROOT / testament_slug / f"{chapter:03d}.yaml"


def iter_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for meta in t12p.TESTAMENTS:
        chapters = t12p.available_normalized_chapters(meta.slug)
        for chapter in chapters:
            jobs.append(
                {
                    "testament_slug": meta.slug,
                    "testament_order": meta.order,
                    "chapter": chapter,
                    "chapter_count": meta.chapter_count,
                }
            )
    return jobs


def init_queue(db_path: pathlib.Path | None = None) -> dict[str, int]:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        created = 0
        updated = 0
        now = utc_now()
        for job in iter_jobs():
            output_path = chapter_output_path(job["testament_slug"], job["chapter"])
            status = STATUS_COMPLETED if output_path.exists() else STATUS_PENDING
            row = conn.execute(
                "SELECT id, status FROM jobs WHERE testament_slug=? AND chapter=?",
                (job["testament_slug"], job["chapter"]),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        testament_slug, testament_order, chapter, chapter_count,
                        status, available_at, output_path, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job["testament_slug"], job["testament_order"], job["chapter"], job["chapter_count"],
                        status, now, str(output_path), now, now,
                    ),
                )
                created += 1
            else:
                if row["status"] != status:
                    conn.execute(
                        "UPDATE jobs SET status=?, output_path=?, updated_at=? WHERE id=?",
                        (status, str(output_path), now, row["id"]),
                    )
                    updated += 1
        conn.commit()
        summary_rows = conn.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
        return {row["status"]: row["c"] for row in summary_rows} | {"created": created, "updated": updated}


def claim_next_job(worker_id: str, db_path: pathlib.Path | None = None) -> dict[str, Any] | None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        now = utc_now()
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status=?
              AND (available_at IS NULL OR available_at <= ?)
            ORDER BY testament_order, chapter
            LIMIT 1
            """,
            (STATUS_PENDING, now),
        ).fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute(
            """
            UPDATE jobs
            SET status=?, worker_id=?, attempts=attempts+1, started_at=?, updated_at=?
            WHERE id=?
            """,
            (STATUS_RUNNING, worker_id, now, now, row["id"]),
        )
        conn.commit()
        claimed = conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        return dict(claimed)


def mark_completed(job_id: int, db_path: pathlib.Path | None = None) -> None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        now = utc_now()
        conn.execute(
            "UPDATE jobs SET status=?, finished_at=?, updated_at=? WHERE id=?",
            (STATUS_COMPLETED, now, now, job_id),
        )
        conn.commit()


def requeue(job_id: int, error_text: str, *, delay_seconds: int = 60, db_path: pathlib.Path | None = None) -> None:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        available_at = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delay_seconds)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        now = utc_now()
        conn.execute(
            """
            UPDATE jobs
            SET status=?, worker_id=NULL, started_at=NULL, available_at=?, last_error=?, updated_at=?
            WHERE id=?
            """,
            (STATUS_PENDING, available_at, error_text[:4000], now, job_id),
        )
        conn.commit()


def summary(db_path: pathlib.Path | None = None) -> dict[str, Any]:
    with contextlib.closing(connect(db_path)) as conn:
        ensure_schema(conn)
        rows = conn.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
        by_status = {row["status"]: row["c"] for row in rows}
        pending = conn.execute(
            "SELECT testament_slug, chapter, attempts, available_at FROM jobs WHERE status=? ORDER BY testament_order, chapter LIMIT 20",
            (STATUS_PENDING,),
        ).fetchall()
        running = conn.execute(
            "SELECT testament_slug, chapter, worker_id, started_at, attempts FROM jobs WHERE status=? ORDER BY testament_order, chapter",
            (STATUS_RUNNING,),
        ).fetchall()
        return {
            "status_counts": by_status,
            "pending_head": [dict(row) for row in pending],
            "running": [dict(row) for row in running],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    claim = sub.add_parser("claim")
    claim.add_argument("--worker-id", required=True)
    done = sub.add_parser("done")
    done.add_argument("--job-id", required=True, type=int)
    retry = sub.add_parser("retry")
    retry.add_argument("--job-id", required=True, type=int)
    retry.add_argument("--error", required=True)
    retry.add_argument("--delay-seconds", type=int, default=60)
    sub.add_parser("summary")
    args = parser.parse_args()

    if args.cmd == "init":
        print(json.dumps(init_queue(), ensure_ascii=False, indent=2))
    elif args.cmd == "claim":
        print(json.dumps(claim_next_job(args.worker_id), ensure_ascii=False, indent=2))
    elif args.cmd == "done":
        mark_completed(args.job_id)
    elif args.cmd == "retry":
        requeue(args.job_id, args.error, delay_seconds=args.delay_seconds)
    elif args.cmd == "summary":
        print(json.dumps(summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
