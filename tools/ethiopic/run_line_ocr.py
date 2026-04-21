#!/usr/bin/env python3
"""run_line_ocr.py — OCR automatically detected Ethiopic body lines page-by-page."""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import os
import pathlib
import sys
import urllib.request
from typing import Any

from PIL import Image

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'tools' / 'ethiopic'))
import ocr_geez  # type: ignore
import detect_line_regions  # type: ignore

OUTPUT_ROOT = REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'transcribed' / 'line_ocr'


def _gemini_line(image_bytes: bytes, *, page: int, line_id: str) -> dict[str, Any]:
    api_key = ocr_geez.resolve_gemini_api_key()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}'
    prompt = (
        f'This is one Ethiopic main-text line from Charles 1906 1 Enoch page {page}, line region {line_id}. '
        'Transcribe ONLY the visible Ethiopic text on this line. '
        'Keep the printed verse number if visible. '
        'Ignore superscript footnote numbers and symbols. '
        'Do not invent off-line continuation text. '
        'Output clean Ethiopic Unicode only.'
    )
    body = {
        'contents': [{'parts': [
            {'text': prompt},
            {'inline_data': {'mime_type': 'image/png', 'data': base64.b64encode(image_bytes).decode()}},
        ]}],
        'generationConfig': {
            'thinkingConfig': {'thinkingBudget': 512},
            'maxOutputTokens': 1000,
        },
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.loads(r.read())
    cand = resp['candidates'][0]
    parts = cand.get('content', {}).get('parts') or []
    return {
        'text': parts[0].get('text', '').strip() if parts else '',
        'finish_reason': cand.get('finishReason', ''),
        'usage': resp.get('usageMetadata', {}),
    }


def run_page(pdf_path: pathlib.Path, page_num: int, *, force: bool = False) -> dict[str, Any]:
    page_png = ocr_geez.render_page_png(pdf_path, page_num, dpi=400)
    img = Image.open(io.BytesIO(page_png))
    detection = detect_line_regions.detect_lines(img)
    page_dir = OUTPUT_ROOT / pdf_path.stem / f'p{page_num:04d}'
    lines_dir = page_dir / 'lines'
    page_dir.mkdir(parents=True, exist_ok=True)
    lines_dir.mkdir(parents=True, exist_ok=True)

    merged_parts: list[str] = []
    reports: list[dict[str, Any]] = []
    for line in detection['lines']:
        line_id = line['id']
        txt_path = lines_dir / f'{line_id}.txt'
        meta_path = lines_dir / f'{line_id}.json'
        if txt_path.exists() and meta_path.exists() and not force:
            text = txt_path.read_text(encoding='utf-8').strip()
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        else:
            x1, y1, x2, y2 = line['box_px']
            crop = img.crop((x1, y1, x2, y2))
            buf = io.BytesIO(); crop.save(buf, format='PNG')
            result = _gemini_line(buf.getvalue(), page=page_num, line_id=line_id)
            text = result['text']
            meta = {
                'line_id': line_id,
                'page': page_num,
                'box_px': line['box_px'],
                'box_pct': line['box_pct'],
                'finish_reason': result['finish_reason'],
                'usage': result['usage'],
                'chars': len(text),
                'generated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            }
            txt_path.write_text(text + ('\n' if text and not text.endswith('\n') else ''), encoding='utf-8')
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        merged_parts.append(text)
        reports.append(meta)

    merged_text = '\n'.join(part for part in merged_parts if part.strip()).strip() + '\n'
    (page_dir / 'merged.txt').write_text(merged_text, encoding='utf-8')
    (page_dir / 'merged.json').write_text(json.dumps({'pdf': str(pdf_path), 'page': page_num, 'detection': detection, 'lines': reports}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'page': page_num, 'line_count': len(reports), 'chars': len(merged_text.strip()), 'merged_txt': str(page_dir / 'merged.txt')}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('page', type=int)
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    summary = run_page(pathlib.Path(args.pdf), args.page, force=args.force)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
