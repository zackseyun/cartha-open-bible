#!/usr/bin/env python3
"""chapter_merge.py — Cherry-pick completed chapter jobs onto main in queue order."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coord-root", default=str(REPO_ROOT))
    parser.add_argument("--phase", action="append", dest="phases")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    coord_root = pathlib.Path(args.coord_root).resolve()
    db_path = chapter_queue.db_path_from(coord_root)
    ready = chapter_queue.list_ready_to_merge(db_path=db_path, phases=args.phases)
    if not ready:
        print("No completed jobs ready to merge.")
        return 0

    merged = 0
    for job in ready[: args.limit]:
        commit_sha = job.get("commit_sha")
        if not commit_sha:
            continue
        subprocess.run(["git", "cherry-pick", commit_sha], cwd=coord_root, check=True)
        merge_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=coord_root, text=True).strip()
        chapter_queue.mark_merged(db_path=db_path, job_id=int(job["id"]), merge_commit_sha=merge_sha)
        print(f"Merged {job['book_code']} {job['chapter']} -> {merge_sha}")
        merged += 1

    if merged and args.push:
        subprocess.run(["git", "push", "origin", "main"], cwd=coord_root, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
