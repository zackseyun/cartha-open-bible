#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common import REPO_ROOT, ensure_dir, rel, resolve_text_ids
from segment_extractors import load_extracted_segments

FIELDNAMES = [
    'segment_id',
    'label',
    'status',
    'heading',
    'start_ref',
    'end_ref',
    'chapter_index',
    'block_index',
    'notes',
]


def output_path(text_id: str) -> Path:
    return REPO_ROOT / 'sources' / 'nag_hammadi' / 'segment_index' / f'{text_id}.csv'


def write_segments(text_id: str) -> Path:
    segments = load_extracted_segments(text_id)
    path = output_path(text_id)
    ensure_dir(path.parent)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for segment in segments:
            row = {field: segment.get(field, '') for field in FIELDNAMES}
            writer.writerow(row)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description='Build Phase E segment indexes from fetched Nag Hammadi witnesses.')
    parser.add_argument('--text', action='append', dest='texts', help='Text id to segment. Repeatable.')
    parser.add_argument('--all', action='store_true', help='Segment all configured texts.')
    args = parser.parse_args()

    text_ids = resolve_text_ids(args.texts, args.all)
    for text_id in text_ids:
        path = write_segments(text_id)
        print(f'[built] {rel(path)}')


if __name__ == '__main__':
    main()
