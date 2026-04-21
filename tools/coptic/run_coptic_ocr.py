#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import pathlib
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import requests

from common import OCR_JOBS_ROOT, REPO_ROOT, load_json, rel, utc_now, write_json

DEFAULT_MODEL = 'gemini-3-pro-preview'
AI_STUDIO_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'
USER_AGENT = 'Mozilla/5.0 (compatible; Phase-E-Coptic-OCR/1.0)'
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff'}


@dataclass
class OcrResult:
    unit_id: str
    text: str
    finish_reason: str
    tokens_in: int
    tokens_out: int
    tokens_thinking: int
    error: str = ''


def job_path(text_id: str, witness_id: str) -> pathlib.Path:
    return OCR_JOBS_ROOT / f'{text_id}.{witness_id}.json'


def resolve_job(text_id: str, witness_id: str) -> dict[str, Any]:
    path = job_path(text_id, witness_id)
    if not path.exists():
        raise SystemExit(f'OCR job not found: {rel(path)}')
    payload = load_json(path)
    input_path = payload.get('registered_input_path')
    if not input_path:
        raise SystemExit(f'Job has no registered_input_path yet: {rel(path)}')
    payload['_job_path'] = path
    payload['_input_path'] = (REPO_ROOT / input_path).resolve() if not pathlib.Path(input_path).is_absolute() else pathlib.Path(input_path)
    return payload


def render_pdf_page_png(pdf_path: pathlib.Path, page_num: int, dpi: int = 400) -> bytes:
    with tempfile.TemporaryDirectory(prefix='coptic_ocr_') as tmpdir:
        out_prefix = pathlib.Path(tmpdir) / f'page_{page_num}'
        cmd = [
            'pdftocairo', '-png', '-r', str(dpi), '-f', str(page_num), '-l', str(page_num),
            '-singlefile', str(pdf_path), str(out_prefix)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return pathlib.Path(f'{out_prefix}.png').read_bytes()


def pdf_page_count(pdf_path: pathlib.Path) -> int:
    cmd = ['pdfinfo', str(pdf_path)]
    out = subprocess.check_output(cmd, text=True)
    for line in out.splitlines():
        if line.startswith('Pages:'):
            return int(line.split(':', 1)[1].strip())
    raise RuntimeError(f'Could not determine page count for {pdf_path}')


def image_units(input_path: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    files = [p for p in sorted(input_path.iterdir()) if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    return [(f.stem, f) for f in files]


def build_prompt(*, text_id: str, witness_id: str, notes: str = '') -> str:
    base = [
        f'This is a source witness for {text_id.replace("_", " ")}.',
        f'The witness id is {witness_id}.',
        'Transcribe the Coptic text exactly using Coptic Unicode.',
        'Preserve line breaks when they are visually meaningful.',
        'Do not normalize spelling, punctuation, or damaged text.',
        'If the page also contains English, notes, or editorial apparatus, ignore those unless they are required to understand the Coptic line order.',
        'Output only the Coptic transcription, with no explanation or commentary.',
    ]
    if notes:
        base.insert(2, f'Witness note: {notes}')
    if 'grondin' in witness_id:
        base.append('This source is an interlinear page-by-page PDF; transcribe only the Coptic layer, not the English glosses.')
    if 'truth' in text_id:
        base.append('These may be fragment images; preserve fragment ordering as seen on the image and do not invent missing text.')
    return ' '.join(base)


def resolve_gemini_api_key() -> str:
    raw = os.environ.get('GEMINI_API_KEY', '').strip()
    if not raw:
        raise RuntimeError('GEMINI_API_KEY not set')
    if raw.startswith('{'):
        payload = json.loads(raw)
        if payload.get('api_key'):
            return str(payload['api_key'])
        keys = payload.get('api_keys') or []
        if keys:
            return str(keys[0])
    return raw


def call_gemini(image_bytes: bytes, *, prompt: str, model: str, thinking_budget: int = 512, max_output_tokens: int = 20000) -> OcrResult:
    api_key = resolve_gemini_api_key()
    b64 = base64.b64encode(image_bytes).decode('ascii')
    url = f'{AI_STUDIO_BASE}/{model}:generateContent?key={api_key}'
    body = {
        'contents': [{'parts': [
            {'text': prompt},
            {'inline_data': {'mime_type': 'image/png', 'data': b64}},
        ]}],
        'generationConfig': {
            'max_output_tokens': max_output_tokens,
            'thinkingConfig': {'thinkingBudget': thinking_budget},
        },
    }
    for attempt in range(6):
        try:
            r = requests.post(url, json=body, headers={'Content-Type': 'application/json', 'User-Agent': USER_AGENT}, timeout=300)
            if r.status_code in {429, 500, 503, 504} and attempt < 5:
                time.sleep(5 + attempt * 4)
                continue
            r.raise_for_status()
            resp = r.json()
            cand = resp['candidates'][0]
            usage = resp.get('usageMetadata', {})
            parts = cand.get('content', {}).get('parts') or []
            text = parts[0].get('text', '').strip() if parts else ''
            return OcrResult(
                unit_id='',
                text=text,
                finish_reason=cand.get('finishReason', '?'),
                tokens_in=usage.get('promptTokenCount', 0),
                tokens_out=usage.get('candidatesTokenCount', 0),
                tokens_thinking=usage.get('thoughtsTokenCount', 0),
                error='' if text else 'empty response text',
            )
        except requests.RequestException as exc:
            if attempt < 5:
                time.sleep(5 + attempt * 4)
                continue
            return OcrResult('', '', 'error', 0, 0, 0, error=str(exc))
    return OcrResult('', '', 'error', 0, 0, 0, error='retries exhausted')


def write_result(out_dir: pathlib.Path, unit_id: str, result: OcrResult, meta: dict[str, Any], *, model: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f'{unit_id}.txt'
    json_path = out_dir / f'{unit_id}.json'
    txt_path.write_text(result.text + ('\n' if result.text and not result.text.endswith('\n') else ''), encoding='utf-8')
    payload = {
        'unit_id': unit_id,
        'generated_at': utc_now(),
        'finish_reason': result.finish_reason,
        'tokens_in': result.tokens_in,
        'tokens_out': result.tokens_out,
        'tokens_thinking': result.tokens_thinking,
        'error': result.error or None,
        'model': model,
        'source_meta': meta,
    }
    write_json(json_path, payload)


def run_pdf(job: dict[str, Any], pages: list[int], *, model: str) -> None:
    pdf_path = job['_input_path']
    out_dir = REPO_ROOT / job['output_dir']
    prompt = build_prompt(text_id=job['text_id'], witness_id=job['witness_id'], notes=job.get('notes', ''))
    for page_num in pages:
        image_bytes = render_pdf_page_png(pdf_path, page_num)
        result = call_gemini(image_bytes, prompt=prompt, model=model)
        unit_id = f'p{page_num:04d}'
        result.unit_id = unit_id
        write_result(out_dir, unit_id, result, {
            'type': 'pdf_page',
            'page': page_num,
            'source_path': job['registered_input_path'],
            'remote_source_url': job.get('remote_source_url'),
            'remote_source_urls': job.get('remote_source_urls'),
        }, model=model)
        print(f'[ocr] {job["witness_id"]} {unit_id} finish={result.finish_reason} out={result.tokens_out} err={result.error or "-"}')


def run_image_dir(job: dict[str, Any], limit: int | None, *, model: str) -> None:
    input_dir = job['_input_path']
    out_dir = REPO_ROOT / job['output_dir']
    prompt = build_prompt(text_id=job['text_id'], witness_id=job['witness_id'], notes=job.get('notes', ''))
    units = image_units(input_dir)
    if limit is not None:
        units = units[:limit]
    for unit_id, path in units:
        image_bytes = path.read_bytes()
        result = call_gemini(image_bytes, prompt=prompt, model=model)
        result.unit_id = unit_id
        write_result(out_dir, unit_id, result, {
            'type': 'image_file',
            'source_path': rel(path),
            'registered_input_path': job['registered_input_path'],
            'remote_source_url': job.get('remote_source_url'),
            'remote_source_urls': job.get('remote_source_urls'),
        }, model=model)
        print(f'[ocr] {job["witness_id"]} {unit_id} finish={result.finish_reason} out={result.tokens_out} err={result.error or "-"}')


def parse_page_spec(spec: str) -> list[int]:
    pages: set[int] = set()
    for part in spec.split(','):
        token = part.strip()
        if not token:
            continue
        if '-' in token:
            a, b = token.split('-', 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(token))
    return sorted(pages)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run Gemini-based OCR for queued Coptic witness jobs.')
    parser.add_argument('--text', required=True, help='Text id')
    parser.add_argument('--witness', required=True, help='Witness id')
    parser.add_argument('--pages', help='PDF page spec like 1,3-5')
    parser.add_argument('--limit', type=int, help='Limit number of image files from a directory witness')
    parser.add_argument('--model', default=os.environ.get('GEMINI_MODEL', DEFAULT_MODEL), help='Gemini model code to use for OCR')
    args = parser.parse_args()

    job = resolve_job(args.text, args.witness)
    input_path = job['_input_path']
    if input_path.is_file() and input_path.suffix.lower() == '.pdf':
        if args.pages:
            pages = parse_page_spec(args.pages)
        else:
            pages = [1]
        run_pdf(job, pages, model=args.model)
        return
    if input_path.is_dir():
        run_image_dir(job, args.limit, model=args.model)
        return
    if input_path.is_file() and input_path.suffix.lower() in IMAGE_EXTS:
        run_image_dir({**job, '_input_path': input_path.parent}, limit=1, model=args.model)
        return
    raise SystemExit(f'Unsupported registered input path: {input_path}')


if __name__ == '__main__':
    main()
