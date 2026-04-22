#!/usr/bin/env python3
"""normalize_working_corpus.py — deduplicate the Jubilees working corpus.

When multiple rows exist for the same chapter+verse, keep the best candidate:

1. targeted refinement
2. Vertex chapter split
3. deterministic parser

Tie-breaker: longer Ge'ez text wins.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_IN = REPO_ROOT / "sources" / "jubilees" / "ethiopic" / "corpus" / "JUBILEES.vertex.jsonl"

PRIORITY = {
    "vertex_targeted_refinement": 3,
    "vertex_chapter_split": 2,
    "jubilees_verse_parser": 1,
}


def score(row: dict[str, Any]) -> tuple[int, int]:
    return (PRIORITY.get(str(row.get("validation") or ""), 0), len(str(row.get("geez") or "")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-path", type=pathlib.Path, default=DEFAULT_IN)
    ap.add_argument("--out-path", type=pathlib.Path)
    args = ap.parse_args()

    rows = [json.loads(line) for line in args.in_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen: dict[tuple[int, int], dict[str, Any]] = {}
    prior_count = len(rows)
    for row in rows:
        key = (int(row["chapter"]), int(row["verse"]))
        cur = chosen.get(key)
        if cur is None or score(row) > score(cur):
            chosen[key] = row

    normalized = [chosen[key] for key in sorted(chosen.keys())]
    out_path = args.out_path or args.in_path
    out_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in normalized),
        encoding="utf-8",
    )

    print(f"in={args.in_path}")
    print(f"out={out_path}")
    print(f"before={prior_count} after={len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
