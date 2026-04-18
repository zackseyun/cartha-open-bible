#!/usr/bin/env python3
"""chapter_worker.py — Claim and draft chapter jobs from the queue."""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402
import draft  # noqa: E402
import run_phase  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def chapter_verses(book_code: str, chapter: int):
    return [verse for verse in draft.iter_source_verses(book_code) if verse.chapter == chapter]


def clean_worktree(repo_root: pathlib.Path) -> None:
    subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "clean", "-fd"], cwd=repo_root, check=True, capture_output=True, text=True)


def run_job(job: dict[str, Any], *, backend: str, model: str, temperature: float, prompt_id: str) -> str:
    book_code = str(job["book_code"])
    chapter = int(job["chapter"])
    clean_worktree(REPO_ROOT)

    paths: list[pathlib.Path] = []
    records: list[dict[str, Any]] = []
    for verse in chapter_verses(book_code, chapter):
        output_path = draft.translation_path_for_verse(verse)
        if output_path.exists():
            continue
        result = draft.retry_draft_verse(
            verse,
            backend=backend,
            model=model,
            temperature=temperature,
            prompt_id=prompt_id,
        )
        paths.append(result.output_path)
        records.append(result.record)
        print(f"Wrote {result.output_path.relative_to(REPO_ROOT)}", flush=True)

    if not paths:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
        return head

    run_phase.commit_paths(paths, run_phase.chapter_commit_message(book_code, chapter, records))
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coord-root", default=str(REPO_ROOT), help="Queue coordination repo root")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--phase", action="append", dest="phases")
    parser.add_argument("--book", action="append", dest="books")
    parser.add_argument("--backend", default=draft.BACKEND_AZURE, choices=[draft.BACKEND_AZURE, draft.BACKEND_OPENROUTER, draft.BACKEND_OPENAI, draft.BACKEND_CODEX])
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--temperature", type=float, default=draft.DEFAULT_TEMPERATURE)
    parser.add_argument("--prompt-id", default=draft.DEFAULT_PROMPT_ID)
    parser.add_argument("--max-jobs", type=int, default=1)
    parser.add_argument("--stop-when-empty", action="store_true")
    args = parser.parse_args()

    coord_root = pathlib.Path(args.coord_root).resolve()
    db_path = chapter_queue.db_path_from(coord_root)
    chapter_queue.init_queue(db_path=db_path, phases=args.phases, repo_root=coord_root)

    completed = 0
    while completed < args.max_jobs:
        job = chapter_queue.claim_next_job(
            db_path=db_path,
            worker_id=args.worker_id,
            worktree_path=str(REPO_ROOT),
            phases=args.phases,
            books=args.books,
        )
        if not job:
            print("No pending job.", flush=True)
            return 0 if args.stop_when_empty else 1

        print(f"Claimed {job['phase']} {job['book_code']} {job['chapter']}", flush=True)
        try:
            commit_sha = run_job(job, backend=args.backend, model=args.model, temperature=args.temperature, prompt_id=args.prompt_id)
            chapter_queue.mark_completed(db_path=db_path, job_id=int(job['id']), commit_sha=commit_sha)
            print(f"Completed {job['book_code']} {job['chapter']} @ {commit_sha}", flush=True)
            completed += 1
        except Exception as exc:
            chapter_queue.mark_failed(db_path=db_path, job_id=int(job['id']), error_text=str(exc))
            print(f"FAILED {job['book_code']} {job['chapter']}: {exc}", file=sys.stderr, flush=True)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
