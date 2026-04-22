#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from common import OCR_JOBS_ROOT, REPO_ROOT, load_json, rel, utc_now, write_json

DEFAULT_MODEL = 'gemini-3.1-pro-preview'
AI_STUDIO_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'
DEFAULT_VERTEX_SECRET_ID = '/cartha/vertex/gemini-sa'
DEFAULT_VERTEX_LOCATION = 'global'
DEFAULT_BACKEND = os.environ.get('GEMINI_BACKEND', 'vertex')
USER_AGENT = 'Mozilla/5.0 (compatible; Phase-E-Coptic-OCR/1.1)'
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff', '.jp2', '.j2k'}
_VERTEX_CACHE: dict[str, object] = {'token': '', 'expiry': 0.0, 'project': '', 'secret_id': ''}


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
    payload['_input_path'] = (
        (REPO_ROOT / input_path).resolve()
        if not pathlib.Path(input_path).is_absolute()
        else pathlib.Path(input_path)
    )
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


def output_paths(out_dir: pathlib.Path, unit_id: str) -> tuple[pathlib.Path, pathlib.Path]:
    return out_dir / f'{unit_id}.txt', out_dir / f'{unit_id}.json'


def prior_output_is_successful(txt_path: pathlib.Path, meta_path: pathlib.Path) -> bool:
    if not (txt_path.exists() and meta_path.exists()):
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception:
        return False
    if meta.get('error'):
        return False
    if str(meta.get('finish_reason', '')).lower() == 'error':
        return False
    try:
        return bool(txt_path.read_text(encoding='utf-8').strip())
    except Exception:
        return False


def image_units(input_path: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    if input_path.is_file() and input_path.suffix.lower() in IMAGE_EXTS:
        return [(input_path.stem, input_path)]
    if not input_path.is_dir():
        return []
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
    if 'thunder' in text_id:
        base.append('This may be poetic lineation. Preserve visible line breaks and refrain from smoothing repeated “I am” structures.')
    return ' '.join(base)


def parse_pages_spec(spec: str) -> list[int]:
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


def parse_units_spec(spec: str) -> list[str]:
    return [token.strip() for token in spec.split(',') if token.strip()]


def parse_crop_box(spec: str | None) -> tuple[float, float, float, float] | None:
    if not spec:
        return None
    vals = [float(part.strip()) for part in spec.split(',') if part.strip()]
    if len(vals) != 4:
        raise ValueError('--crop-box must be x1,y1,x2,y2')
    x1, y1, x2, y2 = vals
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        raise ValueError('--crop-box values must be fractional bounds within 0..1')
    return x1, y1, x2, y2


def mime_suffix(mime_type: str) -> str:
    guessed = mimetypes.guess_extension(mime_type)
    if guessed:
        return guessed
    return '.png'


def image_dimensions(path: pathlib.Path) -> tuple[int, int]:
    out = subprocess.check_output(['magick', 'identify', '-format', '%w %h', str(path)], text=True)
    w_s, h_s = out.strip().split()
    return int(w_s), int(h_s)


def crop_image_bytes(input_path: pathlib.Path, crop_box: tuple[float, float, float, float] | None, *, band_index: int, band_count: int) -> bytes:
    width, height = image_dimensions(input_path)
    x1_f, y1_f, x2_f, y2_f = crop_box or (0.0, 0.0, 1.0, 1.0)
    crop_x = int(round(width * x1_f))
    crop_y = int(round(height * y1_f))
    crop_w = int(round(width * (x2_f - x1_f)))
    crop_h_total = int(round(height * (y2_f - y1_f)))
    band_h = crop_h_total // band_count
    band_y = crop_y + band_h * band_index
    if band_index == band_count - 1:
        band_h = crop_y + crop_h_total - band_y
    geometry = f'{crop_w}x{band_h}+{crop_x}+{band_y}'
    return subprocess.check_output(['magick', str(input_path), '-crop', geometry, '+repage', 'png:-'])


def prepare_regions(image_bytes: bytes, mime_type: str, crop_box: tuple[float, float, float, float] | None, band_count: int) -> list[bytes]:
    band_count = max(1, band_count)
    if crop_box is None and band_count == 1:
        return [image_bytes]
    with tempfile.TemporaryDirectory(prefix='coptic_regions_') as tmpdir:
        tmp_path = pathlib.Path(tmpdir) / f'input{mime_suffix(mime_type)}'
        tmp_path.write_bytes(image_bytes)
        return [crop_image_bytes(tmp_path, crop_box, band_index=i, band_count=band_count) for i in range(band_count)]


def assemble_region_ocr(
    image_bytes: bytes,
    *,
    prompt: str,
    source_mime_type: str,
    crop_box: tuple[float, float, float, float] | None,
    band_count: int,
    backend: str,
    model: str,
    thinking_budget: int,
    max_output_tokens: int,
) -> tuple[OcrResult, dict[str, Any]]:
    region_bytes = prepare_regions(image_bytes, source_mime_type, crop_box, band_count)
    parts: list[str] = []
    finish_reasons: list[str] = []
    errors: list[str] = []
    tokens_in = tokens_out = tokens_thinking = 0
    backend_meta: dict[str, Any] = {}
    for idx, region in enumerate(region_bytes, start=1):
        region_prompt = prompt
        if len(region_bytes) > 1:
            region_prompt += f' This is region {idx}/{len(region_bytes)} from a single page, top-to-bottom in reading order. Only transcribe what is visibly present in this crop.'
        result, backend_meta = call_gemini(
            region,
            prompt=region_prompt,
            mime_type='image/png',
            backend=backend,
            model=model,
            thinking_budget=thinking_budget,
            max_output_tokens=max_output_tokens,
        )
        if result.text:
            parts.append(result.text.strip())
        finish_reasons.append(result.finish_reason)
        if result.error and result.error != 'empty response text':
            errors.append(result.error)
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        tokens_thinking += result.tokens_thinking
    finish_reason = 'STOP' if all(reason == 'STOP' for reason in finish_reasons) else '+'.join(finish_reasons)
    combined_text = '\n\n'.join(part for part in parts if part)
    return OcrResult('', combined_text, finish_reason, tokens_in, tokens_out, tokens_thinking, error='; '.join(errors)), backend_meta


def _read_secret(secret_id: str) -> str:
    return subprocess.check_output(
        [
            'aws', 'secretsmanager', 'get-secret-value',
            '--secret-id', secret_id,
            '--region', 'us-west-2',
            '--query', 'SecretString',
            '--output', 'text',
        ],
        text=True,
    ).strip()


def resolve_gemini_api_keys() -> list[str]:
    raw = os.environ.get('GEMINI_API_KEY', '').strip()
    if not raw:
        raise RuntimeError('GEMINI_API_KEY not set')
    if raw.startswith('{'):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                keys_out: list[str] = []
                if isinstance(obj.get('api_key'), str) and obj['api_key'].strip():
                    keys_out.append(obj['api_key'].strip())
                keys = obj.get('api_keys')
                if isinstance(keys, list):
                    for item in keys:
                        if isinstance(item, str) and item.strip() and item.strip() not in keys_out:
                            keys_out.append(item.strip())
                if keys_out:
                    return keys_out
        except Exception:
            pass
    return [raw]


def resolve_gemini_api_key() -> str:
    return resolve_gemini_api_keys()[0]


def resolve_vertex_service_account_info() -> tuple[dict[str, object], str]:
    secret_id = os.environ.get('VERTEX_SECRET_ID', DEFAULT_VERTEX_SECRET_ID)
    raw = os.environ.get('VERTEX_SA_JSON', '').strip()
    if not raw and os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '').strip():
        cred_path = pathlib.Path(os.environ['GOOGLE_APPLICATION_CREDENTIALS']).expanduser()
        if cred_path.exists():
            raw = cred_path.read_text(encoding='utf-8')
            secret_id = f'file:{cred_path}'
    if not raw:
        raw = _read_secret(secret_id)
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not obj.get('project_id'):
        raise RuntimeError('Vertex service-account secret is not a valid service-account JSON object')
    return obj, secret_id


def vertex_access_token() -> tuple[str, str, str]:
    secret_id = os.environ.get('VERTEX_SECRET_ID', DEFAULT_VERTEX_SECRET_ID)
    now = time.time()
    cached_token = str(_VERTEX_CACHE.get('token') or '')
    cached_project = str(_VERTEX_CACHE.get('project') or '')
    cached_secret_id = str(_VERTEX_CACHE.get('secret_id') or '')
    cached_expiry = float(_VERTEX_CACHE.get('expiry') or 0.0)
    if cached_token and cached_project and cached_secret_id == secret_id and cached_expiry > now + 300:
        return cached_token, cached_project, cached_secret_id

    from google.oauth2 import service_account  # type: ignore
    from google.auth.transport.requests import Request  # type: ignore

    info, resolved_secret_id = resolve_vertex_service_account_info()
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=['https://www.googleapis.com/auth/cloud-platform'],
    )
    creds.refresh(Request())
    token = str(creds.token or '')
    expiry = creds.expiry.timestamp() if getattr(creds, 'expiry', None) else (now + 3000)
    _VERTEX_CACHE['token'] = token
    _VERTEX_CACHE['expiry'] = float(expiry)
    _VERTEX_CACHE['project'] = str(info['project_id'])
    _VERTEX_CACHE['secret_id'] = resolved_secret_id
    return token, str(info['project_id']), resolved_secret_id


def guess_mime_type(path: pathlib.Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or 'image/png'


def call_gemini(
    image_bytes: bytes,
    *,
    prompt: str,
    mime_type: str,
    backend: str,
    model: str,
    thinking_budget: int = 512,
    max_output_tokens: int = 20000,
) -> tuple[OcrResult, dict[str, Any]]:
    body = {
        'contents': [{
            'role': 'user',
            'parts': [
                {'text': prompt},
                {'inline_data': {'mime_type': mime_type, 'data': base64.b64encode(image_bytes).decode('ascii')}},
            ],
        }],
        'generationConfig': {
            'max_output_tokens': max_output_tokens,
            'thinkingConfig': {'thinkingBudget': thinking_budget},
            'temperature': 0.0,
        },
    }

    backend_meta: dict[str, Any] = {'backend': backend, 'model': model}
    if backend == 'vertex':
        token, project_id, secret_id = vertex_access_token()
        location = os.environ.get('VERTEX_LOCATION', DEFAULT_VERTEX_LOCATION)
        api_host = 'aiplatform.googleapis.com' if location == 'global' else f'{location}-aiplatform.googleapis.com'
        url = (
            f'https://{api_host}/v1/projects/{project_id}/locations/{location}/'
            f'publishers/google/models/{model}:generateContent'
        )
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        backend_meta.update({'vertex_project_id': project_id, 'vertex_location': location, 'vertex_secret_id': secret_id})
    elif backend == 'studio':
        api_key = resolve_gemini_api_key()
        url = f'{AI_STUDIO_BASE}/{model}:generateContent?key={api_key}'
        headers = {'Content-Type': 'application/json'}
        backend_meta.update({'gemini_key_prefix': api_key[:8]})
    else:
        raise RuntimeError(f'Unsupported Gemini backend: {backend!r}')

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode('utf-8'),
        headers=headers,
        method='POST',
    )

    last_error = 'retries exhausted'
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                resp = json.loads(response.read().decode('utf-8'))
            cand = resp['candidates'][0]
            usage = resp.get('usageMetadata', {})
            parts = cand.get('content', {}).get('parts') or []
            text = ''.join(part.get('text', '') for part in parts if isinstance(part, dict)).strip()
            err = '' if text else 'empty response text'
            return OcrResult(
                unit_id='',
                text=text,
                finish_reason=cand.get('finishReason', '?'),
                tokens_in=usage.get('promptTokenCount', 0),
                tokens_out=usage.get('candidatesTokenCount', 0),
                tokens_thinking=usage.get('thoughtsTokenCount', 0),
                error=err,
            ), backend_meta
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            last_error = f'HTTP {exc.code}: {detail[:300]}'
            if exc.code in {401, 429, 500, 503, 504} and attempt < 5:
                if exc.code == 401 and backend == 'vertex':
                    _VERTEX_CACHE['expiry'] = 0.0
                time.sleep(5 + attempt * 4)
                continue
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            if attempt < 5:
                time.sleep(5 + attempt * 4)
                continue
            break

    return OcrResult('', '', 'error', 0, 0, 0, error=last_error), backend_meta


def write_result(out_dir: pathlib.Path, unit_id: str, result: OcrResult, meta: dict[str, Any], *, model: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path, json_path = output_paths(out_dir, unit_id)
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


def selected_image_units(
    input_path: pathlib.Path,
    *,
    units_spec: list[str] | None,
    limit: int | None,
    out_dir: pathlib.Path,
    resume: bool,
) -> list[tuple[str, pathlib.Path]]:
    units = image_units(input_path)
    if units_spec:
        wanted = set(units_spec)
        units = [unit for unit in units if unit[0] in wanted]
    if resume:
        filtered: list[tuple[str, pathlib.Path]] = []
        for unit_id, path in units:
            txt_path, meta_path = output_paths(out_dir, unit_id)
            if prior_output_is_successful(txt_path, meta_path):
                continue
            filtered.append((unit_id, path))
        units = filtered
    if limit is not None:
        units = units[:limit]
    return units


def selected_pdf_pages(
    pdf_path: pathlib.Path,
    *,
    pages_spec: list[int] | None,
    out_dir: pathlib.Path,
    resume: bool,
) -> list[int]:
    pages = pages_spec or [1]
    if resume:
        filtered: list[int] = []
        for page_num in pages:
            unit_id = f'p{page_num:04d}'
            txt_path, meta_path = output_paths(out_dir, unit_id)
            if prior_output_is_successful(txt_path, meta_path):
                continue
            filtered.append(page_num)
        pages = filtered
    return pages


def run_pdf(
    job: dict[str, Any],
    pages: list[int],
    *,
    backend: str,
    model: str,
    thinking_budget: int,
    max_output_tokens: int,
    crop_box: tuple[float, float, float, float] | None,
    band_count: int,
    sleep_seconds: float,
) -> None:
    pdf_path = job['_input_path']
    out_dir = REPO_ROOT / job['output_dir']
    prompt = build_prompt(text_id=job['text_id'], witness_id=job['witness_id'], notes=job.get('notes', ''))
    for idx, page_num in enumerate(pages, start=1):
        image_bytes = render_pdf_page_png(pdf_path, page_num)
        result, backend_meta = assemble_region_ocr(
            image_bytes,
            prompt=prompt,
            source_mime_type='image/png',
            crop_box=crop_box,
            band_count=band_count,
            backend=backend,
            model=model,
            thinking_budget=thinking_budget,
            max_output_tokens=max_output_tokens,
        )
        unit_id = f'p{page_num:04d}'
        result.unit_id = unit_id
        write_result(out_dir, unit_id, result, {
            'type': 'pdf_page',
            'page': page_num,
            'source_path': job['registered_input_path'],
            'remote_source_url': job.get('remote_source_url'),
            'remote_source_urls': job.get('remote_source_urls'),
            'crop_box': crop_box,
            'band_count': band_count,
            **backend_meta,
        }, model=model)
        print(f'[ocr] {job["witness_id"]} {unit_id} finish={result.finish_reason} out={result.tokens_out} err={result.error or "-"}')
        if sleep_seconds > 0 and idx < len(pages):
            time.sleep(sleep_seconds)


def run_image_dir(
    job: dict[str, Any],
    units: list[tuple[str, pathlib.Path]],
    *,
    backend: str,
    model: str,
    thinking_budget: int,
    max_output_tokens: int,
    crop_box: tuple[float, float, float, float] | None,
    band_count: int,
    sleep_seconds: float,
) -> None:
    out_dir = REPO_ROOT / job['output_dir']
    prompt = build_prompt(text_id=job['text_id'], witness_id=job['witness_id'], notes=job.get('notes', ''))
    for idx, (unit_id, path) in enumerate(units, start=1):
        image_bytes = path.read_bytes()
        result, backend_meta = assemble_region_ocr(
            image_bytes,
            prompt=prompt,
            source_mime_type=guess_mime_type(path),
            crop_box=crop_box,
            band_count=band_count,
            backend=backend,
            model=model,
            thinking_budget=thinking_budget,
            max_output_tokens=max_output_tokens,
        )
        result.unit_id = unit_id
        write_result(out_dir, unit_id, result, {
            'type': 'image_file',
            'source_path': rel(path),
            'registered_input_path': job['registered_input_path'],
            'remote_source_url': job.get('remote_source_url'),
            'remote_source_urls': job.get('remote_source_urls'),
            'mime_type': guess_mime_type(path),
            'crop_box': crop_box,
            'band_count': band_count,
            **backend_meta,
        }, model=model)
        print(f'[ocr] {job["witness_id"]} {unit_id} finish={result.finish_reason} out={result.tokens_out} err={result.error or "-"}')
        if sleep_seconds > 0 and idx < len(units):
            time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run Gemini-based OCR for queued Coptic witness jobs.')
    parser.add_argument('--text', required=True, help='Text id')
    parser.add_argument('--witness', required=True, help='Witness id')
    parser.add_argument('--pages', help='PDF page spec like 1,3-5')
    parser.add_argument('--units', help='Comma-separated image-unit ids for directory witnesses')
    parser.add_argument('--limit', type=int, help='Limit number of image files from a directory witness')
    parser.add_argument('--backend', choices=['studio', 'vertex'], default=DEFAULT_BACKEND)
    parser.add_argument('--model', default=os.environ.get('GEMINI_MODEL', DEFAULT_MODEL), help='Gemini model code to use for OCR')
    parser.add_argument('--thinking-budget', type=int, default=512)
    parser.add_argument('--max-output-tokens', type=int, default=20000)
    parser.add_argument('--crop-box', help='Fractional crop box x1,y1,x2,y2 (for example 0.15,0.04,0.86,0.96)')
    parser.add_argument('--band-count', type=int, default=1, help='Split each page/image into this many horizontal regions before OCR')
    parser.add_argument('--sleep-seconds', type=float, default=0.0)
    parser.add_argument('--resume', action='store_true', help='Skip already-successful output units')
    args = parser.parse_args()

    job = resolve_job(args.text, args.witness)
    input_path = job['_input_path']
    out_dir = REPO_ROOT / job['output_dir']
    crop_box = parse_crop_box(args.crop_box)

    if input_path.is_file() and input_path.suffix.lower() == '.pdf':
        pages = selected_pdf_pages(
            input_path,
            pages_spec=parse_pages_spec(args.pages) if args.pages else None,
            out_dir=out_dir,
            resume=args.resume,
        )
        if not pages:
            print('[ocr] no pending PDF pages')
            return
        run_pdf(
            job,
            pages,
            backend=args.backend,
            model=args.model,
            thinking_budget=args.thinking_budget,
            max_output_tokens=args.max_output_tokens,
            crop_box=crop_box,
            band_count=args.band_count,
            sleep_seconds=args.sleep_seconds,
        )
        return

    units = selected_image_units(
        input_path,
        units_spec=parse_units_spec(args.units) if args.units else None,
        limit=args.limit,
        out_dir=out_dir,
        resume=args.resume,
    )
    if not units:
        print('[ocr] no pending image units')
        return
    run_image_dir(
        job,
        units,
        backend=args.backend,
        model=args.model,
        thinking_budget=args.thinking_budget,
        max_output_tokens=args.max_output_tokens,
        crop_box=crop_box,
        band_count=args.band_count,
        sleep_seconds=args.sleep_seconds,
    )


if __name__ == '__main__':
    main()
