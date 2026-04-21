#!/usr/bin/env python3
"""detect_line_regions.py — detect Ethiopic body lines above an apparatus block.

Current target: printed Charles/Dillmann Ethiopic pages with a clear main-text
body and an optional lower critical apparatus separated by a rule or large gap.
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from skimage.filters import threshold_otsu

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'tools' / 'ethiopic'))
import ocr_geez  # type: ignore


def _bands_from_mask(mask: np.ndarray, min_row_density: float) -> list[tuple[int, int, float]]:
    row_density = mask.mean(axis=1)
    rows = np.where(row_density > min_row_density)[0]
    if len(rows) == 0:
        return []
    bands: list[tuple[int, int, float]] = []
    start = prev = int(rows[0])
    for r in rows[1:]:
        r = int(r)
        if r == prev + 1:
            prev = r
            continue
        bands.append((start, prev, float(row_density[start:prev+1].mean())))
        start = prev = r
    bands.append((start, prev, float(row_density[start:prev+1].mean())))
    return bands


def _find_rule_band(bands: list[tuple[int, int, float]], page_height: int) -> tuple[int, int] | None:
    candidates: list[tuple[int, int]] = []
    for y1, y2, mean_density in bands:
        h = y2 - y1 + 1
        if y1 < int(page_height * 0.35):
            continue
        if h <= 4 and mean_density >= 0.10:
            candidates.append((y1, y2))
    return candidates[0] if candidates else None


def detect_lines(page_img: Image.Image) -> dict[str, Any]:
    gray = page_img.convert('L')
    arr = np.array(gray)
    thr = threshold_otsu(arr)
    dark = arr < thr
    bands = _bands_from_mask(dark, min_row_density=0.02)
    rule = _find_rule_band(bands, page_img.height)
    body_limit = rule[0] if rule else int(page_img.height * 0.58)

    line_boxes: list[dict[str, Any]] = []
    line_idx = 1
    for y1, y2, mean_density in bands:
        h = y2 - y1 + 1
        if y2 >= body_limit:
            continue
        # skip tiny header dust and centered page number noise
        if h < 18:
            continue
        row_slice = dark[y1:y2+1, :]
        col_density = row_slice.mean(axis=0)
        cols = np.where(col_density > 0.01)[0]
        if len(cols) == 0:
            continue
        x1 = max(0, int(cols[0]) - 18)
        x2 = min(page_img.width, int(cols[-1]) + 18)
        # skip very narrow centered title/header fragments
        if (x2 - x1) < int(page_img.width * 0.25):
            continue
        line_boxes.append({
            'id': f'line_{line_idx:02d}',
            'box_px': [x1, y1, x2, y2],
            'box_pct': [round(x1 / page_img.width, 6), round(y1 / page_img.height, 6), round(x2 / page_img.width, 6), round(y2 / page_img.height, 6)],
            'height_px': h,
            'mean_density': round(mean_density, 6),
        })
        line_idx += 1

    return {
        'threshold': int(thr),
        'body_limit_y': body_limit,
        'rule_band': list(rule) if rule else None,
        'line_count': len(line_boxes),
        'lines': line_boxes,
    }


def write_outputs(pdf_path: pathlib.Path, page_num: int, out_dir: pathlib.Path) -> dict[str, Any]:
    page_png = ocr_geez.render_page_png(pdf_path, page_num, dpi=400)
    img = Image.open(io.BytesIO(page_png))
    detection = detect_lines(img)
    out_dir.mkdir(parents=True, exist_ok=True)

    overlay = img.convert('RGB')
    draw = ImageDraw.Draw(overlay)
    if detection['rule_band']:
        ry1, ry2 = detection['rule_band']
        draw.rectangle((0, ry1, img.width - 1, ry2), outline=(255, 0, 0), width=2)
    for item in detection['lines']:
        x1, y1, x2, y2 = item['box_px']
        draw.rectangle((x1, y1, x2, y2), outline=(0, 180, 0), width=2)
        draw.text((x1, max(0, y1 - 18)), item['id'], fill=(0, 120, 0))

    base = f'{pdf_path.stem}_p{page_num:04d}'
    (out_dir / f'{base}.json').write_text(json.dumps({
        'pdf': str(pdf_path),
        'page': page_num,
        **detection,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    overlay.save(out_dir / f'{base}.overlay.png')
    return {'base': base, **detection}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('page', type=int)
    ap.add_argument('--out-dir', default=str(REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'line_regions'))
    args = ap.parse_args()
    summary = write_outputs(pathlib.Path(args.pdf), args.page, pathlib.Path(args.out_dir))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
