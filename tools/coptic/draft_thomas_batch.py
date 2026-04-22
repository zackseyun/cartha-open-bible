#!/usr/bin/env python3
"""draft_thomas_batch.py — batch draft Gospel of Thomas saying files.

Wraps `draft_thomas.py` so the Track 2 Thomas pass can be resumed safely:

- defaults to the CopticScriptorium saying order (incipit → 114 sayings → subtitle)
- can skip already-written YAMLs
- can continue past failures and summarize them at the end
- supports bounded runs for checkpointing / rate-limit recovery
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional convenience only
    def load_dotenv() -> bool:
        return False

import build_thomas_saying_prompt as bp
import draft_thomas as dt


def all_saying_ids() -> list[str]:
    return [row["saying_id"] for row in bp._load_sayings()]


def parse_saying_list(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    items = [item.strip() for item in raw.split(",")]
    return [item for item in items if item]


def is_normal_numeric_saying(saying_id: str) -> bool:
    return saying_id.isdigit() and saying_id != "000"


def select_sayings(
    *,
    include_specials: bool,
    sayings: list[str] | None,
    start: str | None,
    end: str | None,
    limit: int | None,
) -> list[str]:
    ordered = all_saying_ids()
    available = set(ordered)

    if sayings is not None:
        unknown = [sid for sid in sayings if sid not in available]
        if unknown:
            raise SystemExit(f"Unknown saying ids: {', '.join(unknown)}")
        result = sayings
    else:
        result = ordered
        if not include_specials:
            result = [sid for sid in result if is_normal_numeric_saying(sid)]
        if start:
            if start not in available:
                raise SystemExit(f"Unknown --start saying id: {start}")
            result = result[result.index(start) :]
        if end:
            if end not in available:
                raise SystemExit(f"Unknown --end saying id: {end}")
            result = result[: result.index(end) + 1]

    if limit is not None:
        result = result[:limit]
    return result


def existing_output(saying_id: str) -> pathlib.Path:
    return dt.output_path_for_saying(saying_id)


def format_failures(failures: Iterable[tuple[str, str]]) -> str:
    lines = []
    for sid, err in failures:
        lines.append(f"- {sid}: {err}")
    return "\n".join(lines)


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=dt.DEFAULT_MODEL_ID)
    ap.add_argument("--temperature", type=float, default=dt.DEFAULT_TEMPERATURE)
    ap.add_argument(
        "--max-completion-tokens",
        type=int,
        default=dt.DEFAULT_MAX_COMPLETION_TOKENS,
    )
    ap.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=dt.DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
    ap.add_argument(
        "--sayings",
        help="Comma-separated explicit saying ids (example: 001,002,042,subtitle).",
    )
    ap.add_argument("--start", help="Start saying id in canonical order.")
    ap.add_argument("--end", help="End saying id in canonical order.")
    ap.add_argument(
        "--include-specials",
        action="store_true",
        help="Include incipit (000) and subtitle when range-selecting. Default: normal sayings only.",
    )
    ap.add_argument("--limit", type=int, help="Maximum number of sayings to draft.")
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip YAMLs that already exist on disk.",
    )
    ap.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep going if one saying fails.",
    )
    ap.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional pause between drafts.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected saying ids and exit without drafting.",
    )
    args = ap.parse_args()

    selected = select_sayings(
        include_specials=args.include_specials,
        sayings=parse_saying_list(args.sayings),
        start=args.start,
        end=args.end,
        limit=args.limit,
    )
    if not selected:
        print("No sayings selected.", file=sys.stderr)
        return 0

    if args.skip_existing:
        selected = [sid for sid in selected if not existing_output(sid).exists()]

    if not selected:
        print("Nothing to do — all selected sayings already exist.", file=sys.stderr)
        return 0

    if args.dry_run:
        print("\n".join(selected))
        return 0

    if not dt.azure_endpoint():
        print("ERROR: AZURE_OPENAI_ENDPOINT not set.", file=sys.stderr)
        return 2
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        print("ERROR: AZURE_OPENAI_API_KEY not set.", file=sys.stderr)
        return 2

    failures: list[tuple[str, str]] = []
    successes = 0
    total = len(selected)
    for index, saying_id in enumerate(selected, start=1):
        print(f"[{index}/{total}] drafting {saying_id}...", flush=True)
        try:
            result = dt.draft_saying(
                saying_id,
                model=args.model,
                temperature=args.temperature,
                max_completion_tokens=args.max_completion_tokens,
                request_timeout_seconds=args.request_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - batch runner wants exact failure text
            msg = str(exc)
            failures.append((saying_id, msg))
            print(f"  FAIL {saying_id}: {msg}", file=sys.stderr, flush=True)
            if not args.continue_on_error:
                break
        else:
            successes += 1
            print(
                f"  OK   {saying_id} -> {result.output_path.relative_to(dt.REPO_ROOT)}",
                flush=True,
            )
        if args.sleep_seconds > 0 and index < total:
            time.sleep(args.sleep_seconds)

    print(
        f"\nCompleted Thomas batch: {successes} succeeded, {len(failures)} failed.",
        flush=True,
    )
    if failures:
        print(format_failures(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
