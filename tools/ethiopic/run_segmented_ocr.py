#!/usr/bin/env python3
"""run_segmented_ocr.py — region-segmented Ethiopic OCR rescue runner.

Use this for hard pages where full-page OCR is unstable. A JSON config
specifies one page plus one or more normalized crop boxes. Each segment
is OCR'd independently and then merged in order.
"""
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

OUTPUT_ROOT = REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'transcribed' / 'segmented'


def _gemini_plaintext(image_bytes: bytes, prompt: str, *, thinking_budget: int = 512, max_output_tokens: int = 3000) -> dict[str, Any]:
    api_key = ocr_geez.resolve_gemini_api_key()
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}'
    body = {
        'contents': [{'parts': [
            {'text': prompt},
            {'inline_data': {'mime_type': 'image/png', 'data': base64.b64encode(image_bytes).decode()}}
        ]}],
        'generationConfig': {
            'temperature': 0.0,
            'thinkingConfig': {'thinkingBudget': thinking_budget},
            'maxOutputTokens': max_output_tokens,
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


def crop_from_pct(page: Image.Image, box_pct: list[float]) -> Image.Image:
    w, h = page.size
    x1 = int(box_pct[0] * w)
    y1 = int(box_pct[1] * h)
    x2 = int(box_pct[2] * w)
    y2 = int(box_pct[3] * h)
    return page.crop((x1, y1, x2, y2))


def segment_prompt(*, page: int, segment_id: str, expected_verses: str) -> str:
    return (
        f'This is a cropped Ethiopic main-text region from Charles 1906 1 Enoch page {page}. '
        f'The crop should contain verses {expected_verses}. '
        'Transcribe ONLY the Ethiopic main text visible in this crop. '
        'Keep printed verse numbers if visible. '
        'Ignore superscript footnote numbers and symbols. '
        'Ignore the English apparatus. '
        'Do not invent continuation text outside the crop. '
        'Output clean Ethiopic Unicode only.'
    )


def load_config(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def run_config(config_path: pathlib.Path, *, force: bool = False) -> dict[str, Any]:
    cfg = load_config(config_path)
    pdf_path = REPO_ROOT / cfg['pdf']
    page_num = int(cfg['page'])
    strategy = cfg['strategy']

    page_png = ocr_geez.render_page_png(pdf_path, page_num, dpi=400)
    page_img = Image.open(io.BytesIO(page_png))

    out_dir = OUTPUT_ROOT / pdf_path.stem / f'p{page_num:04d}' / strategy
    segments_dir = out_dir / 'segments'
    segments_dir.mkdir(parents=True, exist_ok=True)

    merged_parts: list[str] = []
    segment_reports: list[dict[str, Any]] = []

    for seg in cfg['segments']:
        seg_id = seg['id']
        txt_path = segments_dir / f'{seg_id}.txt'
        meta_path = segments_dir / f'{seg_id}.json'
        if txt_path.exists() and meta_path.exists() and not force:
            text = txt_path.read_text(encoding='utf-8')
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        else:
            crop = crop_from_pct(page_img, seg['box_pct'])
            buf = io.BytesIO()
            crop.save(buf, format='PNG')
            result = _gemini_plaintext(
                buf.getvalue(),
                segment_prompt(page=page_num, segment_id=seg_id, expected_verses=seg.get('expected_verses', 'unknown')),
            )
            text = result['text']
            meta = {
                'segment_id': seg_id,
                'page': page_num,
                'strategy': strategy,
                'box_pct': seg['box_pct'],
                'expected_verses': seg.get('expected_verses', ''),
                'finish_reason': result['finish_reason'],
                'usage': result['usage'],
                'chars': len(text),
                'generated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            }
            txt_path.write_text(text + ('\n' if text and not text.endswith('\n') else ''), encoding='utf-8')
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        merged_parts.append(text.strip())
        segment_reports.append(meta)

    merged_text = '\n'.join(part for part in merged_parts if part).strip() + '\n'
    merged_txt = out_dir / 'merged.txt'
    merged_json = out_dir / 'merged.json'
    merged_txt.write_text(merged_text, encoding='utf-8')
    merged_json.write_text(json.dumps({
        'config': str(config_path),
        'page': page_num,
        'strategy': strategy,
        'segment_count': len(segment_reports),
        'chars': len(merged_text.strip()),
        'segments': segment_reports,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    return {
        'merged_txt': str(merged_txt),
        'merged_json': str(merged_json),
        'chars': len(merged_text.strip()),
        'segment_count': len(segment_reports),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('config')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    summary = run_config(pathlib.Path(args.config), force=args.force)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
