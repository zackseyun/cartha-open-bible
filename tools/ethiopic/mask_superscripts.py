#!/usr/bin/env python3
"""mask_superscripts.py — remove tiny superscript note markers from Ethiopic body text.

This is a heuristic preprocessor for pages like Charles 1906 where body text is
polluted by many small superscript apparatus markers.
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
from skimage.measure import label, regionprops

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / 'tools' / 'ethiopic'))
import ocr_geez  # type: ignore
import detect_line_regions  # type: ignore


def mask_page(pdf_path: pathlib.Path, page_num: int) -> dict[str, Any]:
    page_png = ocr_geez.render_page_png(pdf_path, page_num, dpi=400)
    img = Image.open(io.BytesIO(page_png)).convert('L')
    arr = np.array(img)
    thr = threshold_otsu(arr)
    dark = arr < thr
    det = detect_line_regions.detect_lines(img)
    body_limit = det['rule_band'][0] if det['rule_band'] else int(img.height * 0.58)
    body = dark[:body_limit, :]

    labels = label(body)
    mask = np.zeros_like(body, dtype=bool)
    removed = []
    for reg in regionprops(labels):
        minr, minc, maxr, maxc = reg.bbox
        h = maxr - minr
        w = maxc - minc
        area = reg.area
        # likely superscript markers: tiny, detached, above the line bodies
        if area <= 250 and h <= 22 and w <= 28 and minr >= 120:
            removed.append({'bbox': [minc, minr, maxc, maxr], 'area': int(area), 'w': int(w), 'h': int(h)})
            mask[minr:maxr, minc:maxc] = True

    masked_arr = arr.copy()
    masked_arr[:body_limit, :][mask] = 255
    masked = Image.fromarray(masked_arr)

    return {
        'image': masked,
        'threshold': int(thr),
        'body_limit': int(body_limit),
        'removed_count': len(removed),
        'removed': removed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('page', type=int)
    ap.add_argument('--out-dir', default=str(REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'masked_superscripts'))
    args = ap.parse_args()

    pdf_path = pathlib.Path(args.pdf)
    out_dir = pathlib.Path(args.out_dir) / pdf_path.stem / f'p{args.page:04d}'
    out_dir.mkdir(parents=True, exist_ok=True)
    result = mask_page(pdf_path, args.page)
    img_path = out_dir / 'masked.png'
    meta_path = out_dir / 'meta.json'
    result['image'].save(img_path)
    meta_path.write_text(json.dumps({k: v for k, v in result.items() if k != 'image'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'masked_image': str(img_path), 'meta': str(meta_path), 'removed_count': result['removed_count'], 'body_limit': result['body_limit']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
