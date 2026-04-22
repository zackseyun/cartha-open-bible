#!/usr/bin/env python3
"""run_parallel_ocr.py — fan out Ge'ez OCR across multiple Gemini API keys.

This wraps `tools/ethiopic/ocr_geez.py` with multiple worker subprocesses.
Each worker gets a single raw API key in `GEMINI_API_KEY` and a disjoint page
chunk, so large OCR jobs can finish much faster than the single-process path.

Typical usage with a secret JSON that contains `api_keys: [...]`:

    export GEMINI_API_KEY="$(aws secretsmanager get-secret-value \
      --secret-id /cartha/openclaw/gemini_api_key \
      --query SecretString --output text)"

    python3 tools/ethiopic/run_parallel_ocr.py \
      sources/jubilees/scans/charles_1895_ethiopic.pdf \
      37-210 \
      --out-dir sources/jubilees/ethiopic/transcribed/charles_1895/body \
      --book-hint "Charles 1895 Ethiopic Book of Jubilees" \
      --resume \
      --workers-per-key 2

The runner is resumable: it skips pages already present when `--resume` is set.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import ocr_geez  # type: ignore


@dataclass
class WorkerPlan:
    worker_id: int
    api_key_index: int
    pages: list[int]
    log_path: pathlib.Path


@dataclass
class WorkerResult:
    worker_id: int
    api_key_index: int
    page_count: int
    exit_code: int
    duration_seconds: float
    log_path: pathlib.Path


def pages_to_spec(pages: list[int]) -> str:
    if not pages:
        return ""
    ranges: list[str] = []
    start = prev = pages[0]
    for page in pages[1:]:
        if page == prev + 1:
            prev = page
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = page
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(ranges)


def chunk_evenly(pages: list[int], chunk_count: int) -> list[list[int]]:
    chunk_count = max(1, min(chunk_count, len(pages)))
    base, extra = divmod(len(pages), chunk_count)
    out: list[list[int]] = []
    cursor = 0
    for i in range(chunk_count):
        size = base + (1 if i < extra else 0)
        out.append(pages[cursor: cursor + size])
        cursor += size
    return [chunk for chunk in out if chunk]


def pending_pages(
    pages: list[int],
    *,
    out_dir: pathlib.Path,
    pdf_path: pathlib.Path,
    resume: bool,
) -> list[int]:
    if not resume:
        return pages
    todo: list[int] = []
    for page in pages:
        txt_path, meta_path = ocr_geez.output_paths(out_dir, pdf_path, page)
        if ocr_geez.prior_output_is_successful(txt_path, meta_path):
            continue
        todo.append(page)
    return todo


def build_worker_plans(
    *,
    pages: list[int],
    api_keys: list[str],
    workers_per_key: int,
    logs_dir: pathlib.Path,
) -> list[WorkerPlan]:
    worker_count = len(api_keys) * max(1, workers_per_key)
    chunks = chunk_evenly(pages, worker_count)
    plans: list[WorkerPlan] = []
    for i, chunk in enumerate(chunks, start=1):
        api_key_index = (i - 1) % len(api_keys)
        plans.append(
            WorkerPlan(
                worker_id=i,
                api_key_index=api_key_index,
                pages=chunk,
                log_path=logs_dir / f"worker_{i:02d}.log",
            )
        )
    return plans


def launch_worker(
    plan: WorkerPlan,
    *,
    args: argparse.Namespace,
    api_keys: list[str],
    ocr_script: pathlib.Path,
) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        str(ocr_script),
        str(args.pdf_path),
        pages_to_spec(plan.pages),
        "--out-dir",
        str(args.out_dir),
        "--book-hint",
        args.book_hint,
        "--dpi",
        str(args.dpi),
        "--thinking-budget",
        str(args.thinking_budget),
        "--max-output-tokens",
        str(args.max_output_tokens),
        "--sleep-seconds",
        str(args.sleep_seconds),
    ]
    if args.chapter_hint:
        cmd.extend(["--chapter-hint", args.chapter_hint])
    if args.opening_hint:
        cmd.extend(["--opening-hint", args.opening_hint])
    if args.hints_json:
        cmd.extend(["--hints-json", str(args.hints_json)])
    if args.resume:
        cmd.append("--resume")

    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_keys[plan.api_key_index]
    log_fh = plan.log_path.open("wb")
    return subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, env=env)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf_path", type=pathlib.Path)
    ap.add_argument("pages", help="Page spec like '37-210' or '37,40-44'")
    ap.add_argument("--out-dir", type=pathlib.Path, required=True)
    ap.add_argument("--book-hint", default="a classical Ethiopic book")
    ap.add_argument("--chapter-hint", default="")
    ap.add_argument("--opening-hint", default="")
    ap.add_argument("--hints-json", type=pathlib.Path)
    ap.add_argument("--dpi", type=int, default=400)
    ap.add_argument("--thinking-budget", type=int, default=512)
    ap.add_argument("--max-output-tokens", type=int, default=20000)
    ap.add_argument("--sleep-seconds", type=float, default=0.0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument(
        "--workers-per-key",
        type=int,
        default=1,
        help="How many worker subprocesses to launch per resolved API key",
    )
    ap.add_argument(
        "--api-key-env-var",
        default="GEMINI_API_KEY",
        help="Environment variable to resolve. Its JSON may contain api_keys[].",
    )
    ap.add_argument(
        "--api-key-indices",
        default="all",
        help="1-based indices into the resolved key list, e.g. '1' or '1,3'. Default: all",
    )
    ap.add_argument(
        "--logs-dir",
        type=pathlib.Path,
        help="Directory for worker logs (default: <out-dir>/_parallel_logs)",
    )
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def select_api_keys(api_keys: list[str], spec: str) -> list[str]:
    if spec == "all":
        return api_keys
    picks: list[str] = []
    seen: set[int] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        idx = int(token)
        zero_based = idx - 1
        if zero_based < 0 or zero_based >= len(api_keys):
            raise SystemExit(f"--api-key-indices {idx} out of range; resolved {len(api_keys)} keys")
        if zero_based in seen:
            continue
        picks.append(api_keys[zero_based])
        seen.add(zero_based)
    if not picks:
        raise SystemExit("No API keys selected")
    return picks


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf_path.resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    args.pdf_path = pdf_path
    args.out_dir = args.out_dir.resolve()
    logs_dir = (args.logs_dir or (args.out_dir / "_parallel_logs")).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    ocr_script = REPO_ROOT / "tools" / "ethiopic" / "ocr_geez.py"

    raw_env = os.environ.get(args.api_key_env_var, "").strip()
    if not raw_env:
        raise SystemExit(f"{args.api_key_env_var} not set")
    os.environ["GEMINI_API_KEY"] = raw_env
    api_keys = select_api_keys(ocr_geez.resolve_gemini_api_keys(), args.api_key_indices)
    if not api_keys:
        raise SystemExit("No Gemini API keys resolved")

    all_pages = ocr_geez.parse_page_spec(args.pages)
    todo = pending_pages(all_pages, out_dir=args.out_dir, pdf_path=pdf_path, resume=args.resume)

    print(f"[parallel-ocr] pdf={pdf_path}")
    print(f"[parallel-ocr] requested={len(all_pages)} pages, pending={len(todo)}, resume={args.resume}")
    print(f"[parallel-ocr] resolved_keys={len(api_keys)} via ${args.api_key_env_var}")
    print(f"[parallel-ocr] workers_per_key={args.workers_per_key}")
    print(f"[parallel-ocr] out_dir={args.out_dir}")
    print(f"[parallel-ocr] logs_dir={logs_dir}")
    if not todo:
        print("[parallel-ocr] nothing to do ✓")
        return 0

    plans = build_worker_plans(
        pages=todo,
        api_keys=api_keys,
        workers_per_key=args.workers_per_key,
        logs_dir=logs_dir,
    )
    for plan in plans:
        print(
            f"  worker {plan.worker_id:02d}: key#{plan.api_key_index + 1} "
            f"pages={pages_to_spec(plan.pages)} log={plan.log_path}"
        )
    if args.dry_run:
        return 0

    procs: list[tuple[WorkerPlan, subprocess.Popen[bytes], float]] = []
    for plan in plans:
        started = time.time()
        proc = launch_worker(plan, args=args, api_keys=api_keys, ocr_script=ocr_script)
        procs.append((plan, proc, started))

    failures = 0
    for plan, proc, started in procs:
        exit_code = proc.wait()
        duration = round(time.time() - started, 2)
        result = WorkerResult(
            worker_id=plan.worker_id,
            api_key_index=plan.api_key_index,
            page_count=len(plan.pages),
            exit_code=exit_code,
            duration_seconds=duration,
            log_path=plan.log_path,
        )
        status = "OK" if exit_code == 0 else "FAIL"
        print(
            f"[parallel-ocr] worker {result.worker_id:02d} key#{result.api_key_index + 1}: "
            f"{status} pages={result.page_count} dur={result.duration_seconds}s "
            f"log={result.log_path}"
        )
        if exit_code != 0:
            failures += 1

    remaining = pending_pages(all_pages, out_dir=args.out_dir, pdf_path=pdf_path, resume=True)
    complete = len(all_pages) - len(remaining)
    print(f"[parallel-ocr] complete={complete}/{len(all_pages)} remaining={len(remaining)}")
    if failures:
        print("[parallel-ocr] some workers failed — inspect logs and rerun with --resume")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
