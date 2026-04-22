#!/usr/bin/env python3
"""Build a page/chapter source bundle for Thunder, Perfect Mind.

Unlike Gospel of Truth, Thunder still lacks a trustworthy automatic mapping from the
new facsimile OCR pages to the existing 123 line-block segment scaffold. This bundle
therefore packages the OCRed codex pages and the consult-only chapter/block skeleton
side by side, so the next alignment/drafting step can be explicit instead of guessed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import REPO_ROOT, load_manifest, load_segments, write_json

TEXT_ID = 'thunder_perfect_mind'
RAW_JSON = REPO_ROOT / 'sources/nag_hammadi/raw/thunder_perfect_mind/othergospels_thunder_primary.json'
OCR_ROOT = REPO_ROOT / 'sources/nag_hammadi/ocr/output/thunder_perfect_mind/nhc_vi_2_facsimile_primary'
OUT_JSON = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/source_bundle.json'
OUT_MD = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/source_bundle.md'


def load_ocr_pages() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for txt_path in sorted(OCR_ROOT.glob('nhc_vi2_page_*.txt')):
        page_num = int(txt_path.stem.split('_')[-1])
        meta_path = txt_path.with_suffix('.json')
        meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
        entry = {
            'page_num': page_num,
            'text_path': str(txt_path.relative_to(REPO_ROOT)),
            'meta_path': str(meta_path.relative_to(REPO_ROOT)) if meta_path.exists() else None,
            'text': txt_path.read_text(encoding='utf-8').strip(),
            'meta': meta,
        }
        out.append(entry)
    return out


def build_bundle() -> dict[str, Any]:
    manifest = load_manifest(TEXT_ID)
    consult = json.loads(RAW_JSON.read_text(encoding='utf-8'))
    pages = load_ocr_pages()
    chapters: list[dict[str, Any]] = []
    counter = 1
    for chapter_index, chapter in enumerate(consult.get('chapters', []), start=1):
        blocks = []
        for block_index, body in enumerate(chapter.get('body', []), start=1):
            blocks.append({
                'segment_id': f'{counter:03d}',
                'chapter_index': chapter_index,
                'block_index': block_index,
                'english_consult_text': body,
            })
            counter += 1
        chapters.append({
            'chapter_index': chapter_index,
            'title': chapter.get('title') or f'Chapter {chapter_index}',
            'block_count': len(blocks),
            'blocks': blocks,
        })
    warnings = []
    for page in pages:
        finish = str(page.get('meta', {}).get('finish_reason', ''))
        if finish and finish != 'STOP':
            warnings.append(f"Page {page['page_num']} OCR caveat: {finish}")
    return {
        'generated_at': __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'text_id': TEXT_ID,
        'title': manifest['title'],
        'segment_unit': manifest['segment_unit'],
        'primary_witness_id': 'nhc_vi_2_facsimile_primary',
        'consult_witness_id': 'othergospels_thunder_primary',
        'page_count': len(pages),
        'chapter_count': len(chapters),
        'pages': pages,
        'consult_chapters': chapters,
        'warnings': warnings,
        'alignment_status': 'page_and_consult_layers_ready; precise page-to-line-block alignment still pending',
    }


def write_markdown(bundle: dict[str, Any]) -> None:
    lines = [
        '# Thunder, Perfect Mind — source bundle',
        '',
        f"Pages: {bundle['page_count']}",
        f"Consult chapters: {bundle['chapter_count']}",
        '',
        f"Alignment status: {bundle['alignment_status']}",
        '',
        '## OCR pages',
        '',
    ]
    for page in bundle['pages']:
        finish = page.get('meta', {}).get('finish_reason', '—')
        lines.append(f"- page {page['page_num']} — finish `{finish}`")
    lines.extend(['', '## Consult chapters', ''])
    for chapter in bundle['consult_chapters']:
        lines.append(f"- chapter {chapter['chapter_index']}: {chapter['title']} ({chapter['block_count']} blocks)")
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    bundle = build_bundle()
    write_json(OUT_JSON, bundle)
    write_markdown(bundle)
    print(OUT_JSON.relative_to(REPO_ROOT))
    print(OUT_MD.relative_to(REPO_ROOT))
    print(f"pages={bundle['page_count']} chapters={bundle['chapter_count']}")


if __name__ == '__main__':
    main()
