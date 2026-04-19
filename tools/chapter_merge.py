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


def git(coord_root: pathlib.Path, *args: str, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=coord_root,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def head_sha(coord_root: pathlib.Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=coord_root, text=True).strip()


def cherry_pick_head(coord_root: pathlib.Path) -> str | None:
    proc = git(coord_root, "rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD", check=False, capture_output=True)
    sha = (proc.stdout or "").strip()
    return sha or None


def clean_stuck_cherry_pick(coord_root: pathlib.Path) -> None:
    current = cherry_pick_head(coord_root)
    if not current:
        return
    status = git(coord_root, "status", "--porcelain", capture_output=True).stdout.strip()
    if status:
        git(coord_root, "cherry-pick", "--abort", check=False)
        return
    git(coord_root, "cherry-pick", "--skip", check=False)


def commit_already_present(coord_root: pathlib.Path, commit_sha: str) -> bool:
    # Reachable from HEAD (main) specifically. `git branch --contains` without
    # filtering returns True if *any* branch — including codex/* worktree
    # branches — contains the sha, which falsely marks uncherry-picked drafts
    # as already-applied and corrupts the merged_at flag.
    proc = git(coord_root, "merge-base", "--is-ancestor", commit_sha, "HEAD",
               check=False, capture_output=True)
    return proc.returncode == 0


def cherry_pick_or_skip(coord_root: pathlib.Path, commit_sha: str) -> tuple[bool, str]:
    clean_stuck_cherry_pick(coord_root)
    if commit_already_present(coord_root, commit_sha):
        return False, head_sha(coord_root)

    before = head_sha(coord_root)
    proc = git(coord_root, "cherry-pick", commit_sha, check=False, capture_output=True)
    if proc.returncode == 0:
        return True, head_sha(coord_root)

    combined = "\n".join(part for part in [(proc.stdout or "").strip(), (proc.stderr or "").strip()] if part)
    lowered = combined.lower()

    if "nothing to commit" in lowered or "previous cherry-pick is now empty" in lowered:
        git(coord_root, "cherry-pick", "--skip", check=False)
        return False, head_sha(coord_root)

    if "is a merge but no -m option was given" in lowered:
        git(coord_root, "cherry-pick", "--abort", check=False)
        raise RuntimeError(f"Refusing merge commit cherry-pick {commit_sha}: {combined}")

    if "could not apply" in lowered or "after resolving the conflicts" in lowered:
        git(coord_root, "cherry-pick", "--abort", check=False)
        raise RuntimeError(f"Cherry-pick conflict for {commit_sha}: {combined}")

    if "index.lock" in lowered:
        raise RuntimeError(f"Git index lock blocked merge lane for {commit_sha}: {combined}")

    if head_sha(coord_root) != before:
        clean_stuck_cherry_pick(coord_root)
        return True, head_sha(coord_root)

    raise RuntimeError(f"Cherry-pick failed for {commit_sha}: {combined}")


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
        did_merge, merge_sha = cherry_pick_or_skip(coord_root, commit_sha)
        chapter_queue.mark_merged(db_path=db_path, job_id=int(job["id"]), merge_commit_sha=merge_sha)
        if did_merge:
            print(f"Merged {job['book_code']} {job['chapter']} -> {merge_sha}")
            merged += 1
        else:
            print(f"Marked merged without cherry-pick {job['book_code']} {job['chapter']} -> {merge_sha}")

    if merged and args.push:
        git(coord_root, "push", "origin", "main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
