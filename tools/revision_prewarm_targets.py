#!/usr/bin/env python3
"""revision_prewarm_targets.py — list books that need forced summary refresh.

A book should have its cached summaries regenerated when a revision-style commit
lands on `main` and touches that book's translation files. First-pass draft
commits do not trigger refreshes.

Usage:
  python3 tools/revision_prewarm_targets.py --range <before>..<after>

Output:
  One canonical summary-cache book label per line (e.g. `1 ENOCH`).
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REVISION_PREFIXES = ("revise", "polish", "normalize", "rename", "consistency")

sys.path.insert(0, str(REPO_ROOT / "tools"))
from gemini_summary_prewarm import slug_to_label  # noqa: E402


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True)


def commit_subject(sha: str) -> str:
    return git("show", "-s", "--format=%s", sha).strip()


def is_revision_commit(subject: str) -> bool:
    lower = subject.lower().strip()
    return any(lower.startswith(prefix) for prefix in REVISION_PREFIXES)


def books_touched_by_commit(sha: str) -> set[str]:
    out: set[str] = set()
    paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", sha, "--", "translation/").splitlines()
    for raw in paths:
        path = pathlib.PurePosixPath(raw.strip())
        parts = path.parts
        if len(parts) < 3 or parts[0] != "translation":
            continue
        testament = parts[1]
        slug = parts[2]
        if testament not in {"nt", "ot", "deuterocanon", "extra_canonical"}:
            continue
        out.add(slug_to_label(slug))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", required=True, help="Git revision range, e.g. abc123..def456")
    args = ap.parse_args()

    shas = [line.strip() for line in git("rev-list", "--reverse", args.range).splitlines() if line.strip()]
    books: set[str] = set()
    for sha in shas:
        subject = commit_subject(sha)
        if not is_revision_commit(subject):
            continue
        books |= books_touched_by_commit(sha)

    for book in sorted(books):
        print(book)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
