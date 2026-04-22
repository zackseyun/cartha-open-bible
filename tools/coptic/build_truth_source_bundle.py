#!/usr/bin/env python3
"""Build a section-level source bundle for Gospel of Truth.

This converts the newly OCRed Codex I.3 facsimile pages into a translation-ready
bundle keyed to the existing 16-section segment map. It uses the Mattison/Zinner
public-domain English rendering only to recover section boundaries and approximate
codex-page coverage, while keeping the OCRed Coptic pages as the actual primary
source layer.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from common import REPO_ROOT, load_consult_registry, load_manifest, load_segments, write_json
from segment_extractors import TRUTH_HEADINGS

TEXT_ID = 'gospel_of_truth'
RAW_TEXT = REPO_ROOT / 'sources/nag_hammadi/raw/gospel_of_truth/mattison_zinner_coptic.txt'
SEGMENT_INDEX = REPO_ROOT / 'sources/nag_hammadi/segment_index/gospel_of_truth.csv'
OCR_ROOT = REPO_ROOT / 'sources/nag_hammadi/ocr/output/gospel_of_truth/nhc_i_3_facsimile_primary'
FRAG_JOB = REPO_ROOT / 'sources/nag_hammadi/ocr/jobs/gospel_of_truth.nhc_xii_2_fragments.json'
OUT_JSON = REPO_ROOT / 'sources/nag_hammadi/texts/gospel_of_truth/source_bundle.json'
OUT_MD = REPO_ROOT / 'sources/nag_hammadi/texts/gospel_of_truth/source_bundle.md'
PAGE_RE = re.compile(r'(?<!\d)(1[6-9]|2\d|3\d|4[0-3])(?!\d)')
NOTES_SENTINEL = 'Notes on Translation'


def parse_truth_sections(raw_text: str) -> list[dict[str, Any]]:
    lines = raw_text.splitlines()
    positions: list[tuple[str, int]] = []
    for heading in TRUTH_HEADINGS:
        try:
            idx = lines.index(heading)
        except ValueError as exc:
            raise RuntimeError(f'Could not find Gospel of Truth heading: {heading}') from exc
        positions.append((heading, idx))

    try:
        notes_idx = lines.index(NOTES_SENTINEL)
    except ValueError as exc:
        raise RuntimeError('Could not find Notes on Translation sentinel in Gospel of Truth raw text') from exc

    out: list[dict[str, Any]] = []
    for i, (heading, start_idx) in enumerate(positions, start=1):
        end_idx = positions[i][1] if i < len(positions) else notes_idx
        block_lines = lines[start_idx + 1:end_idx]
        excerpt = '\n'.join(line for line in block_lines if line.strip()).strip()
        pages = [int(m.group(1)) for m in PAGE_RE.finditer(excerpt)]
        pages = sorted(dict.fromkeys(pages))
        out.append({
            'segment_id': f'{i:03d}',
            'heading': heading,
            'consult_excerpt': excerpt,
            'consult_codex_pages': pages,
        })
    return out


def load_ocr_pages() -> dict[int, dict[str, Any]]:
    pages: dict[int, dict[str, Any]] = {}
    for txt_path in sorted(OCR_ROOT.glob('nhc_i3_page_*.txt')):
        page_num = int(txt_path.stem.split('_')[-1])
        meta_path = txt_path.with_suffix('.json')
        meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
        pages[page_num] = {
            'page_num': page_num,
            'text_path': str(txt_path.relative_to(REPO_ROOT)),
            'meta_path': str(meta_path.relative_to(REPO_ROOT)) if meta_path.exists() else None,
            'text': txt_path.read_text(encoding='utf-8').strip(),
            'meta': meta,
        }
    return pages


def load_overlap_fragments() -> dict[str, list[dict[str, Any]]]:
    if not FRAG_JOB.exists():
        return {}
    job = json.loads(FRAG_JOB.read_text(encoding='utf-8'))
    out: dict[str, list[dict[str, Any]]] = {}
    for fragment in job.get('fragments', []):
        fragment_path = REPO_ROOT / fragment['text_path']
        entry = {
            'fragment_id': fragment['fragment_id'],
            'nhc_xii_page': fragment.get('nhc_xii_page'),
            'text_path': fragment['text_path'],
            'text': fragment_path.read_text(encoding='utf-8').strip() if fragment_path.exists() else '',
            'approximate_i3_alignment': fragment.get('approximate_i3_alignment'),
            'alignment_confidence': fragment.get('alignment_confidence'),
        }
        for seg in fragment.get('coverage_segments', []):
            out.setdefault(seg, []).append(entry)
    return out


def build_bundle() -> dict[str, Any]:
    manifest = load_manifest(TEXT_ID)
    consult_registry = load_consult_registry()
    raw_sections = {row['segment_id']: row for row in parse_truth_sections(RAW_TEXT.read_text(encoding='utf-8'))}
    segment_rows = load_segments(manifest)
    ocr_pages = load_ocr_pages()
    overlap = load_overlap_fragments()

    sections: list[dict[str, Any]] = []
    for row in segment_rows:
        sid = row['segment_id']
        raw = raw_sections.get(sid)
        if raw is None:
            raise RuntimeError(f'Missing raw section parse for segment {sid}')
        pages = [ocr_pages[p] for p in raw['consult_codex_pages'] if p in ocr_pages]
        warnings: list[str] = []
        if not pages:
            warnings.append('No OCRed Codex I.3 pages were mapped into this section.')
        for page in pages:
            finish_reason = str(page['meta'].get('finish_reason', ''))
            if 'MAX_TOKENS' in finish_reason:
                warnings.append(f"Boundary caveat on page {page['page_num']}: finish_reason={finish_reason}")
        for fragment in overlap.get(sid, []):
            if fragment['alignment_confidence'] != 'approximate':
                warnings.append(f"Fragment {fragment['fragment_id']} alignment confidence: {fragment['alignment_confidence']}")
        sections.append({
            'segment_id': sid,
            'label': row['label'],
            'heading': row['heading'],
            'consult_excerpt': raw['consult_excerpt'],
            'consult_codex_pages': raw['consult_codex_pages'],
            'primary_page_texts': pages,
            'overlap_fragments': overlap.get(sid, []),
            'warnings': warnings,
        })

    return {
        'generated_at': __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'text_id': TEXT_ID,
        'title': manifest['title'],
        'segment_unit': manifest['segment_unit'],
        'primary_witness_id': 'nhc_i_3_facsimile_primary',
        'overlap_witness_id': 'nhc_xii_2_fragments',
        'consult_sources': [consult_registry[cid] for cid in manifest.get('consult_sources', []) if cid in consult_registry],
        'sections': sections,
    }


def write_markdown(bundle: dict[str, Any]) -> None:
    lines = [
        '# Gospel of Truth — source bundle',
        '',
        f"Sections: {len(bundle['sections'])}",
        '',
    ]
    for section in bundle['sections']:
        page_label = ', '.join(str(p) for p in section['consult_codex_pages']) or '—'
        overlap_label = ', '.join(f["fragment_id"] for f in section['overlap_fragments']) or '—'
        lines.append(f"- `{section['segment_id']}` — {section['label']} | codex pages: {page_label} | overlap: {overlap_label}")
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    bundle = build_bundle()
    write_json(OUT_JSON, bundle)
    write_markdown(bundle)
    print(OUT_JSON.relative_to(REPO_ROOT))
    print(OUT_MD.relative_to(REPO_ROOT))
    print(f"sections={len(bundle['sections'])}")


if __name__ == '__main__':
    main()
