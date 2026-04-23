#!/usr/bin/env python3
"""testaments_draft_worker.py — long-running worker for Testament drafting."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft_testament  # noqa: E402
import testaments_draft_queue as queue  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def fetch_azure_env() -> None:
    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
        return
    raw = subprocess.check_output(
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            "cartha-azure-openai-key",
            "--region",
            "us-west-2",
            "--query",
            "SecretString",
            "--output",
            "text",
        ],
        text=True,
    )
    secret = json.loads(raw)
    os.environ["AZURE_OPENAI_API_KEY"] = secret["api_key"]
    os.environ["AZURE_OPENAI_ENDPOINT"] = secret.get("endpoint") or "https://eastus2.api.cognitive.microsoft.com"
    os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")


def is_retryable_error(message: str) -> bool:
    lower = message.lower()
    return any(
        token in lower
        for token in (
            "rate limit",
            "resource has been exhausted",
            "429",
            "timeout",
            "timed out",
            "temporary",
            "connection reset",
            "502",
            "503",
            "504",
            "invalid json",
            "tool call",
            "must return exactly one tool call",
            "were not valid json",
        )
    )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--sleep-seconds", type=int, default=15)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-jobs", type=int, default=0, help="0 = unlimited")
    args = parser.parse_args()

    fetch_azure_env()
    os.environ["AZURE_OPENAI_DEPLOYMENT_ID"] = args.deployment

    completed = 0

    while True:
        job = queue.claim_next_job(args.worker_id)
        if job is None:
            time.sleep(args.sleep_seconds)
            summary = queue.summary()
            pending = summary["status_counts"].get(queue.STATUS_PENDING, 0)
            running = summary["status_counts"].get(queue.STATUS_RUNNING, 0)
            if pending == 0 and running == 0:
                print(f"[{args.worker_id}] queue drained; exiting")
                return 0
            continue

        testament_slug = str(job["testament_slug"])
        chapter = int(job["chapter"])
        try:
            result = draft_testament.draft_chapter(
                testament_slug=testament_slug,
                chapter=chapter,
                model="gpt-5.4",
                temperature=args.temperature,
                dry_run=False,
            )
            if result is None:
                raise RuntimeError("draft_chapter returned None unexpectedly")
            queue.mark_completed(int(job["id"]))
            completed += 1
            print(f"[{args.worker_id}] completed {testament_slug} {chapter} -> {result.output_path}")
            if args.max_jobs and completed >= args.max_jobs:
                print(f"[{args.worker_id}] reached max jobs ({args.max_jobs}); exiting")
                return 0
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            delay = 90 if is_retryable_error(msg) else 300
            queue.requeue(int(job["id"]), msg, delay_seconds=delay)
            print(f"[{args.worker_id}] requeued {testament_slug} {chapter}: {msg}")
            time.sleep(min(delay, 30))


if __name__ == "__main__":
    raise SystemExit(main())
