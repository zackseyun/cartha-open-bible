#!/usr/bin/env python3
"""multi_witness.py — minimal chapter-level witness bundle for 2 Baruch.

Current scope:
- Ceriani 1871 chapter buckets (primary Syriac base)
- targeted Kmosko 1907 control pages (secondary Syriac / Latin witness)

This is intentionally modest. It gives the translator prompt builder a single place to
ask, "what primary text and what control material do I have for chapter N right now?"
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CHAPTER_BUCKETS = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'chapter_buckets.json'
KMOSKO_DIR = REPO_ROOT / 'sources' / '2baruch' / 'raw_ocr' / 'kmosko1907'

KMOSKO_CONTROL_ZONES = [
    {'pages': [545, 548], 'chapter_start': 1, 'chapter_end': 6, 'label': 'opening apocalypse', 'kind': 'direct_witness'},
    {'pages': [552], 'chapter_start': 9, 'chapter_end': 11, 'label': 'temple-judgment / sanctuary-key transition', 'kind': 'direct_witness'},
    {'pages': [554, 555], 'chapter_start': 13, 'chapter_end': 15, 'label': 'chapter XIII / early apocalypse checkpoint', 'kind': 'direct_witness'},
    {'pages': [560], 'chapter_start': 20, 'chapter_end': 21, 'label': 'Cedron prayer transition', 'kind': 'direct_witness'},
    {'pages': [565], 'chapter_start': 24, 'chapter_end': 25, 'label': 'earlier-middle apocalypse', 'kind': 'direct_witness'},
    {'pages': [568], 'chapter_start': 29, 'chapter_end': 29, 'label': 'messianic banquet opening', 'kind': 'direct_witness'},
    {'pages': [570], 'chapter_start': 31, 'chapter_end': 33, 'label': 'chapter XXXII control', 'kind': 'direct_witness'},
    {'pages': [573, 574, 575, 576], 'chapter_start': 37, 'chapter_end': 42, 'label': 'forest / cedar vision block', 'kind': 'direct_witness'},
    {'pages': [578, 580, 582], 'chapter_start': 47, 'chapter_end': 50, 'label': 'prayer and response transition', 'kind': 'direct_witness'},
    {'pages': [586], 'chapter_start': 51, 'chapter_end': 51, 'label': 'chapter LI resurrection control', 'kind': 'direct_witness'},
    {'pages': [588], 'chapter_start': 52, 'chapter_end': 52, 'label': 'chapter LII judgment control', 'kind': 'direct_witness'},
    {'pages': [590, 595], 'chapter_start': 53, 'chapter_end': 59, 'label': 'cloud vision control', 'kind': 'direct_witness'},
    {'pages': [598, 600], 'chapter_start': 60, 'chapter_end': 63, 'label': 'late-middle bright waters checkpoint', 'kind': 'direct_witness'},
    {'pages': [604, 606], 'chapter_start': 67, 'chapter_end': 70, 'label': 'late-apocalypse dark waters checkpoint', 'kind': 'direct_witness'},
    {'pages': [608, 609, 610], 'chapter_start': 72, 'chapter_end': 75, 'label': 'messiah and final-age control', 'kind': 'direct_witness'},
    {'pages': [611, 613, 614], 'chapter_start': 76, 'chapter_end': 79, 'label': 'apocalypse/epistle edge', 'kind': 'direct_witness'},
    {'pages': [621, 624, 625], 'chapter_start': 78, 'chapter_end': 82, 'label': 'epistle direct control pages', 'kind': 'direct_witness'},
    {'pages': [615, 617, 620], 'chapter_start': 83, 'chapter_end': 84, 'label': 'epistle orientation / apparatus', 'kind': 'orientation_only'},
]


def load_buckets() -> dict[str, Any]:
    return json.loads(CHAPTER_BUCKETS.read_text(encoding='utf-8'))


def kmosko_pages_for_chapter(chapter: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for zone in KMOSKO_CONTROL_ZONES:
        if zone['chapter_start'] <= chapter <= zone['chapter_end']:
            for page in zone['pages']:
                txt_path = KMOSKO_DIR / f'kmosko1907_p{page:04d}.txt'
                meta_path = KMOSKO_DIR / f'kmosko1907_p{page:04d}.meta.json'
                text = txt_path.read_text(encoding='utf-8').strip() if txt_path.exists() else None
                out.append({
                    'page': page,
                    'label': zone['label'],
                    'text_path': str(txt_path.relative_to(REPO_ROOT)) if txt_path.exists() else None,
                    'meta_path': str(meta_path.relative_to(REPO_ROOT)) if meta_path.exists() else None,
                    'kind': zone.get('kind', 'direct_witness'),
                    'usable': bool(text and len(text) >= 100 and zone.get('kind', 'direct_witness') == 'direct_witness'),
                    'text': text,
                })
    return out


def chapter_bundle(chapter: int) -> dict[str, Any]:
    buckets = load_buckets()
    key = f'{chapter:02d}'
    bucket = buckets[key]
    return {
        'chapter': chapter,
        'reference': bucket['reference'],
        'primary': {
            'witness': 'ceriani1871',
            'source_pdf_pages': bucket['source_pdf_pages'],
            'source_printed_pages': bucket['source_printed_pages'],
            'text': bucket['source_text'],
            'method': bucket['chapter_bucket_method'],
            'overlap_expected': bucket['overlap_expected'],
        },
        'secondary': {
            'kmosko1907': kmosko_pages_for_chapter(chapter),
        },
    }


def main() -> int:
    import argparse, pprint
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chapter', type=int, required=True)
    args = ap.parse_args()
    pprint.pp(chapter_bundle(args.chapter))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
