#!/usr/bin/env python3
from __future__ import annotations

import argparse, os, pathlib, sys, time
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool: return False
import draft_truth as dt
import json

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BUNDLE = REPO_ROOT / 'sources/nag_hammadi/texts/gospel_of_truth/source_bundle.json'

def all_sections() -> list[str]:
    data=json.loads(BUNDLE.read_text(encoding='utf-8'))
    return [s['segment_id'] for s in data['sections']]

def parse_list(raw: str | None) -> list[str] | None:
    return [x.strip() for x in raw.split(',') if x.strip()] if raw else None

def main() -> int:
    load_dotenv()
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sections')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--skip-existing', action='store_true')
    ap.add_argument('--continue-on-error', action='store_true')
    ap.add_argument('--sleep-seconds', type=float, default=0.0)
    ap.add_argument('--model', default=dt.DEFAULT_MODEL_ID)
    ap.add_argument('--temperature', type=float, default=dt.DEFAULT_TEMPERATURE)
    ap.add_argument('--max-completion-tokens', type=int, default=dt.DEFAULT_MAX_COMPLETION_TOKENS)
    ap.add_argument('--request-timeout-seconds', type=int, default=dt.DEFAULT_REQUEST_TIMEOUT_SECONDS)
    ap.add_argument('--dry-run', action='store_true')
    args=ap.parse_args()
    selected = parse_list(args.sections) or all_sections()
    if args.start:
        selected = selected[selected.index(args.start):]
    if args.end:
        selected = selected[:selected.index(args.end)+1]
    if args.limit is not None:
        selected = selected[:args.limit]
    if args.skip_existing:
        selected = [sid for sid in selected if not dt.output_path_for_section(sid).exists()]
    if args.dry_run:
        print('\n'.join(selected)); return 0
    failures=[]; ok=0
    for i,sid in enumerate(selected, start=1):
        print(f'[{i}/{len(selected)}] drafting {sid}...', flush=True)
        try:
            res=dt.draft_section(sid, model=args.model, temperature=args.temperature, max_completion_tokens=args.max_completion_tokens, request_timeout_seconds=args.request_timeout_seconds)
            ok += 1
            print(f'  OK   {sid} -> {res.output_path.relative_to(dt.REPO_ROOT)}', flush=True)
        except Exception as exc:
            failures.append((sid, str(exc)))
            print(f'  FAIL {sid}: {exc}', file=sys.stderr, flush=True)
            if not args.continue_on_error:
                break
        if args.sleep_seconds and i < len(selected):
            time.sleep(args.sleep_seconds)
    print(f'\nCompleted Truth batch: {ok} succeeded, {len(failures)} failed.')
    if failures:
        for sid, err in failures:
            print(f'- {sid}: {err}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
