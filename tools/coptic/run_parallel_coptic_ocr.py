#!/usr/bin/env python3
"""run_parallel_coptic_ocr.py — fan out Coptic OCR across multiple Gemini credentials.

Supports both:
- AI Studio API keys
- Vertex AI service-account secrets

Unlike the Ge'ez runner, this one can split either PDF page jobs or image-directory
jobs (such as Nag Hammadi facsimile page folders) into disjoint worker batches.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Iterable

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'tools' / 'coptic'))
import run_coptic_ocr as ocr  # type: ignore

DEFAULT_VERTEX_SECRET_IDS = os.environ.get(
    'VERTEX_SECRET_IDS',
    '/cartha/vertex/gemini-sa,/cartha/vertex/gemini-sa-2',
)


@dataclass
class WorkerPlan:
    worker_id: int
    credential_index: int
    units: list[str]
    log_path: pathlib.Path


@dataclass
class WorkerResult:
    worker_id: int
    credential_index: int
    unit_count: int
    exit_code: int
    duration_seconds: float
    log_path: pathlib.Path


def chunk_evenly(items: list[str], chunk_count: int) -> list[list[str]]:
    chunk_count = max(1, min(chunk_count, len(items)))
    base, extra = divmod(len(items), chunk_count)
    out: list[list[str]] = []
    cursor = 0
    for i in range(chunk_count):
        size = base + (1 if i < extra else 0)
        out.append(items[cursor: cursor + size])
        cursor += size
    return [chunk for chunk in out if chunk]


def pages_to_spec(pages: Iterable[str]) -> str:
    nums = [int(p) for p in pages]
    if not nums:
        return ''
    nums = sorted(nums)
    ranges: list[str] = []
    start = prev = nums[0]
    for page in nums[1:]:
        if page == prev + 1:
            prev = page
            continue
        ranges.append(f'{start}-{prev}' if start != prev else str(start))
        start = prev = page
    ranges.append(f'{start}-{prev}' if start != prev else str(start))
    return ','.join(ranges)


def build_worker_plans(
    *,
    units: list[str],
    credentials: list[str],
    workers_per_key: int,
    logs_dir: pathlib.Path,
) -> list[WorkerPlan]:
    worker_count = len(credentials) * max(1, workers_per_key)
    chunks = chunk_evenly(units, worker_count)
    plans: list[WorkerPlan] = []
    for i, chunk in enumerate(chunks, start=1):
        credential_index = (i - 1) % len(credentials)
        plans.append(
            WorkerPlan(
                worker_id=i,
                credential_index=credential_index,
                units=chunk,
                log_path=logs_dir / f'worker_{i:02d}.log',
            )
        )
    return plans


def launch_worker(
    plan: WorkerPlan,
    *,
    args: argparse.Namespace,
    credentials: list[str],
    ocr_script: pathlib.Path,
    unit_mode: str,
) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        str(ocr_script),
        '--text', args.text,
        '--witness', args.witness,
        '--backend', args.backend,
        '--model', args.model,
        '--thinking-budget', str(args.thinking_budget),
        '--max-output-tokens', str(args.max_output_tokens),
        '--sleep-seconds', str(args.sleep_seconds),
        '--band-count', str(args.band_count),
        '--resume',
    ]
    if args.crop_box:
        cmd.extend(['--crop-box', args.crop_box])
    if unit_mode == 'pdf':
        cmd.extend(['--pages', pages_to_spec(plan.units)])
    elif unit_mode == 'image':
        cmd.extend(['--units', ','.join(plan.units)])
    else:
        raise SystemExit(f'Unsupported unit mode: {unit_mode}')

    env = os.environ.copy()
    if args.backend == 'studio':
        env['GEMINI_API_KEY'] = credentials[plan.credential_index]
    elif args.backend == 'vertex':
        env['VERTEX_SECRET_ID'] = credentials[plan.credential_index]
    else:
        raise SystemExit(f'Unsupported backend: {args.backend}')

    log_fh = plan.log_path.open('wb')
    return subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, env=env)


def select_api_keys(raw_env: str, spec: str) -> list[str]:
    os.environ['GEMINI_API_KEY'] = raw_env
    api_keys = ocr.resolve_gemini_api_keys()
    if spec == 'all':
        return api_keys
    picks: list[str] = []
    seen: set[int] = set()
    for token in spec.split(','):
        token = token.strip()
        if not token:
            continue
        idx = int(token) - 1
        if idx < 0 or idx >= len(api_keys):
            raise SystemExit(f'--api-key-indices {idx + 1} out of range; resolved {len(api_keys)} keys')
        if idx in seen:
            continue
        picks.append(api_keys[idx])
        seen.add(idx)
    if not picks:
        raise SystemExit('No API keys selected')
    return picks




def update_job_status(job: dict, *, status: str, args: argparse.Namespace, unit_mode: str, total_units: int, remaining_units: int) -> None:
    job_path = pathlib.Path(job['_job_path'])
    payload = json.loads(job_path.read_text(encoding='utf-8'))
    payload['status'] = status
    payload['updated_at'] = ocr.utc_now()
    payload['engine'] = args.model
    payload['backend'] = args.backend
    payload['unit_mode'] = unit_mode
    payload['total_units'] = total_units
    payload['remaining_units'] = remaining_units
    payload['crop_box'] = args.crop_box or None
    payload['band_count'] = args.band_count
    payload['workers_per_key'] = args.workers_per_key
    payload['credential_count'] = len([token.strip() for token in (args.vertex_secret_ids.split(',') if args.backend == 'vertex' else [os.environ.get(args.api_key_env_var, '')]) if token.strip()])
    if status == 'completed':
        payload['completed_at'] = ocr.utc_now()
    ocr.write_json(job_path, payload)

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--text', required=True)
    ap.add_argument('--witness', required=True)
    ap.add_argument('--pages', help='Optional page spec override for PDF jobs')
    ap.add_argument('--units', help='Optional unit-id subset for image-directory jobs')
    ap.add_argument('--backend', choices=['studio', 'vertex'], default=ocr.DEFAULT_BACKEND)
    ap.add_argument('--model', default=ocr.DEFAULT_MODEL)
    ap.add_argument('--thinking-budget', type=int, default=512)
    ap.add_argument('--max-output-tokens', type=int, default=20000)
    ap.add_argument('--crop-box', help='Fractional crop box x1,y1,x2,y2 to pass through to workers')
    ap.add_argument('--band-count', type=int, default=1)
    ap.add_argument('--sleep-seconds', type=float, default=0.0)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--workers-per-key', type=int, default=2)
    ap.add_argument('--api-key-env-var', default='GEMINI_API_KEY')
    ap.add_argument('--api-key-indices', default='all')
    ap.add_argument('--vertex-secret-ids', default=DEFAULT_VERTEX_SECRET_IDS)
    ap.add_argument('--logs-dir', type=pathlib.Path)
    ap.add_argument('--dry-run', action='store_true')
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    job = ocr.resolve_job(args.text, args.witness)
    input_path = pathlib.Path(job['_input_path'])
    out_dir = (ocr.REPO_ROOT / job['output_dir']).resolve()
    logs_dir = (args.logs_dir or (out_dir / '_parallel_logs')).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    ocr_script = REPO_ROOT / 'tools' / 'coptic' / 'run_coptic_ocr.py'

    update_job_status(job, status='running', args=args, unit_mode='pdf' if input_path.is_file() and input_path.suffix.lower() == '.pdf' else 'image', total_units=0, remaining_units=0)

    if input_path.is_file() and input_path.suffix.lower() == '.pdf':
        all_units = [str(p) for p in (ocr.parse_pages_spec(args.pages) if args.pages else range(1, ocr.pdf_page_count(input_path) + 1))]
        if args.resume:
            todo = []
            for page in all_units:
                unit_id = f'p{int(page):04d}'
                txt_path, meta_path = ocr.output_paths(out_dir, unit_id)
                if ocr.prior_output_is_successful(txt_path, meta_path):
                    continue
                todo.append(page)
        else:
            todo = all_units
        unit_mode = 'pdf'
    else:
        wanted_units = ocr.parse_units_spec(args.units) if args.units else None
        all_units = [unit_id for unit_id, _ in ocr.image_units(input_path) if wanted_units is None or unit_id in set(wanted_units)]
        if args.resume:
            todo = []
            for unit_id in all_units:
                txt_path, meta_path = ocr.output_paths(out_dir, unit_id)
                if ocr.prior_output_is_successful(txt_path, meta_path):
                    continue
                todo.append(unit_id)
        else:
            todo = all_units
        unit_mode = 'image'

    if args.backend == 'studio':
        raw_env = os.environ.get(args.api_key_env_var, '').strip()
        if not raw_env:
            raise SystemExit(f'{args.api_key_env_var} not set')
        credentials = select_api_keys(raw_env, args.api_key_indices)
        credential_label = f'${args.api_key_env_var}'
    else:
        credentials = [token.strip() for token in args.vertex_secret_ids.split(',') if token.strip()]
        if not credentials:
            raise SystemExit('No Vertex secret ids resolved')
        credential_label = 'VERTEX_SECRET_IDS'

    print(f'[parallel-coptic-ocr] text={args.text} witness={args.witness}')
    print(f'[parallel-coptic-ocr] input={input_path}')
    print(f'[parallel-coptic-ocr] unit_mode={unit_mode} requested={len(all_units)} pending={len(todo)} resume={args.resume}')
    print(f'[parallel-coptic-ocr] backend={args.backend} model={args.model}')
    print(f'[parallel-coptic-ocr] resolved_credentials={len(credentials)} via {credential_label}')
    print(f'[parallel-coptic-ocr] workers_per_key={args.workers_per_key}')
    print(f'[parallel-coptic-ocr] out_dir={out_dir}')
    print(f'[parallel-coptic-ocr] logs_dir={logs_dir}')
    if not todo:
        print('[parallel-coptic-ocr] nothing to do ✓')
        return 0

    plans = build_worker_plans(
        units=todo,
        credentials=credentials,
        workers_per_key=args.workers_per_key,
        logs_dir=logs_dir,
    )
    for plan in plans:
        rendered = pages_to_spec(plan.units) if unit_mode == 'pdf' else ','.join(plan.units)
        print(f'  worker {plan.worker_id:02d}: credential#{plan.credential_index + 1} units={rendered} log={plan.log_path}')
    if args.dry_run:
        return 0

    procs: list[tuple[WorkerPlan, subprocess.Popen[bytes], float]] = []
    for plan in plans:
        started = time.time()
        proc = launch_worker(plan, args=args, credentials=credentials, ocr_script=ocr_script, unit_mode=unit_mode)
        procs.append((plan, proc, started))

    failures = 0
    for plan, proc, started in procs:
        exit_code = proc.wait()
        duration = round(time.time() - started, 2)
        result = WorkerResult(
            worker_id=plan.worker_id,
            credential_index=plan.credential_index,
            unit_count=len(plan.units),
            exit_code=exit_code,
            duration_seconds=duration,
            log_path=plan.log_path,
        )
        status = 'OK' if exit_code == 0 else 'FAIL'
        print(
            f'[parallel-coptic-ocr] worker {result.worker_id:02d} credential#{result.credential_index + 1}: '
            f'{status} units={result.unit_count} dur={result.duration_seconds}s log={result.log_path}'
        )
        if exit_code != 0:
            failures += 1

    remaining = []
    if unit_mode == 'pdf':
        for page in all_units:
            unit_id = f'p{int(page):04d}'
            txt_path, meta_path = ocr.output_paths(out_dir, unit_id)
            if not ocr.prior_output_is_successful(txt_path, meta_path):
                remaining.append(page)
    else:
        for unit_id in all_units:
            txt_path, meta_path = ocr.output_paths(out_dir, unit_id)
            if not ocr.prior_output_is_successful(txt_path, meta_path):
                remaining.append(unit_id)

    print(f'[parallel-coptic-ocr] complete={len(all_units) - len(remaining)}/{len(all_units)} remaining={len(remaining)}')
    final_status = 'completed' if not failures else 'partial_failure'
    update_job_status(job, status=final_status, args=args, unit_mode=unit_mode, total_units=len(all_units), remaining_units=len(remaining))
    if failures:
        print('[parallel-coptic-ocr] some workers failed — inspect logs and rerun with --resume')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
