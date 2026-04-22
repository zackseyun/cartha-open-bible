#!/usr/bin/env python3
"""Build an explicit heuristic alignment layer for Thunder, Perfect Mind.

This does **not** claim a philologically final mapping. Instead it turns the existing
primary facsimile OCR pages + consult block skeleton into a transparent page/block
alignment artifact with confidence labels, so downstream work can improve it rather
than guessing implicitly.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from common import REPO_ROOT, write_json

BUNDLE_PATH = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/source_bundle.json'
OUT_JSON = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/alignment.json'
OUT_MD = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/alignment.md'
META_RE = re.compile(r'^(Codex\s+[IVXLC]+|\d{4,}|[IVXLC]+)$', re.I)


def normalize_ocr_lines(text: str) -> tuple[list[str], list[str]]:
    raw = [ln.strip() for ln in text.splitlines() if ln.strip()]
    cleaned: list[str] = []
    dropped: list[str] = []
    seen_counts: dict[str, int] = {}
    for line in raw:
        if META_RE.match(line):
            dropped.append(line)
            continue
        count = seen_counts.get(line, 0)
        seen_counts[line] = count + 1
        if len(line) >= 12 and count >= 2:
            dropped.append(line)
            continue
        cleaned.append(line)
    return cleaned, dropped


def consult_line_count(block_text: str) -> int:
    return max(1, len([ln for ln in block_text.splitlines() if ln.strip()]))


def page_for_offset(offset: int, pages: list[dict[str, Any]]) -> tuple[int, int]:
    cursor = 0
    for page in pages:
        next_cursor = cursor + page['usable_line_count']
        if offset < next_cursor:
            return page['page_num'], offset - cursor
        cursor = next_cursor
    last = pages[-1]
    return last['page_num'], max(0, last['usable_line_count'] - 1)


def build_alignment() -> dict[str, Any]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding='utf-8'))
    pages: list[dict[str, Any]] = []
    total_ocr_lines = 0
    for page in bundle['pages']:
        usable, dropped = normalize_ocr_lines(page['text'])
        entry = {
            'page_num': page['page_num'],
            'text_path': page['text_path'],
            'meta_path': page['meta_path'],
            'finish_reason': page.get('meta', {}).get('finish_reason'),
            'usable_lines': usable,
            'usable_line_count': len(usable),
            'dropped_lines': dropped,
            'dropped_line_count': len(dropped),
        }
        pages.append(entry)
        total_ocr_lines += len(usable)

    consult_blocks: list[dict[str, Any]] = []
    for chapter in bundle['consult_chapters']:
        for block in chapter['blocks']:
            consult_blocks.append({
                **block,
                'chapter_title': chapter['title'],
                'consult_line_count': consult_line_count(block['english_consult_text']),
            })

    total_consult_lines = sum(block['consult_line_count'] for block in consult_blocks)
    cumulative_consult = 0
    blocks_out: list[dict[str, Any]] = []
    for block in consult_blocks:
        start_ratio = cumulative_consult / total_consult_lines if total_consult_lines else 0.0
        cumulative_consult += block['consult_line_count']
        end_ratio = cumulative_consult / total_consult_lines if total_consult_lines else 1.0
        start_offset = min(total_ocr_lines - 1, math.floor(start_ratio * total_ocr_lines)) if total_ocr_lines else 0
        end_offset = min(total_ocr_lines - 1, max(start_offset, math.ceil(end_ratio * total_ocr_lines) - 1)) if total_ocr_lines else 0
        start_page, start_line = page_for_offset(start_offset, pages)
        end_page, end_line = page_for_offset(end_offset, pages)

        excerpt_lines: list[str] = []
        for page in pages:
            if page['page_num'] < start_page or page['page_num'] > end_page:
                continue
            lo = 0
            hi = page['usable_line_count'] - 1
            if page['page_num'] == start_page:
                lo = max(0, start_line - 1)
            if page['page_num'] == end_page:
                hi = min(hi, end_line + 1)
            excerpt_lines.extend(page['usable_lines'][lo:hi + 1])

        confidence = 'medium'
        warnings: list[str] = []
        if start_page != end_page:
            confidence = 'low'
            warnings.append('Block spans multiple OCR pages under heuristic line-ratio mapping.')
        if end_page == 21 or start_page == 21:
            confidence = 'low'
            warnings.append('Mapped through page 21, the Thunder edge page with one MAX_TOKENS OCR region.')
        blocks_out.append({
            'segment_id': block['segment_id'],
            'chapter_index': block['chapter_index'],
            'block_index': block['block_index'],
            'chapter_title': block['chapter_title'],
            'english_consult_text': block['english_consult_text'],
            'consult_line_count': block['consult_line_count'],
            'approx_page_start': start_page,
            'approx_page_end': end_page,
            'approx_page_line_start': start_line,
            'approx_page_line_end': end_line,
            'approx_ocr_excerpt': '\n'.join(excerpt_lines).strip(),
            'confidence': confidence,
            'warnings': warnings,
            'alignment_basis': 'heuristic_line_ratio_over_cleaned_page_lines',
        })

    return {
        'generated_at': __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'text_id': bundle['text_id'],
        'title': bundle['title'],
        'alignment_status': 'heuristic_page_to_lineblock_alignment',
        'page_count': len(pages),
        'segment_count': len(blocks_out),
        'total_usable_ocr_lines': total_ocr_lines,
        'total_consult_lines': total_consult_lines,
        'pages': pages,
        'blocks': blocks_out,
    }


def write_markdown(data: dict[str, Any]) -> None:
    lines = [
        '# Thunder, Perfect Mind — alignment layer',
        '',
        f"Status: {data['alignment_status']}",
        f"Pages: {data['page_count']}",
        f"Segments: {data['segment_count']}",
        '',
        '## Page summary',
        '',
    ]
    for page in data['pages']:
        lines.append(f"- page {page['page_num']} — usable OCR lines `{page['usable_line_count']}`, dropped `{page['dropped_line_count']}`, finish `{page['finish_reason']}`")
    lines.extend(['', '## Block summary', ''])
    for block in data['blocks'][:25]:
        span = f"{block['approx_page_start']}" if block['approx_page_start'] == block['approx_page_end'] else f"{block['approx_page_start']}-{block['approx_page_end']}"
        lines.append(f"- `{block['segment_id']}` — {block['chapter_title']} {block['block_index']} | page {span} | confidence `{block['confidence']}`")
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    data = build_alignment()
    write_json(OUT_JSON, data)
    write_markdown(data)
    print(OUT_JSON.relative_to(REPO_ROOT))
    print(OUT_MD.relative_to(REPO_ROOT))
    print(f"segments={data['segment_count']}")


if __name__ == '__main__':
    main()
