#!/usr/bin/env python3
"""build_translation_prompt.py — assemble a chapter-drafting prompt for 2 Baruch.

This prompt builder sits on top of the new Ceriani chapter buckets. It is designed
for the current translation-ready stage where:

- the Ceriani primary witness is fully OCR'd and bridged
- chapter buckets are now control-backed and chapter-ready
- targeted Kmosko control pages exist across the major weak zones
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CONTROL_PLAN = REPO_ROOT / 'sources' / '2baruch' / 'CONTROL_WITNESSES.md'
SPOTCHECK_QUEUE = REPO_ROOT / 'sources' / '2baruch' / 'raw_ocr' / 'ceriani1871' / 'SPOTCHECK_QUEUE.md'
TRANSLATION_DIR = REPO_ROOT / 'translation' / 'extra_canonical' / '2_baruch'
spec = importlib.util.spec_from_file_location('baruch_multi_witness', REPO_ROOT / 'tools' / '2baruch' / 'multi_witness.py')
multi_witness = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(multi_witness)


def build_prompt(chapter: int) -> str:
    bundle = multi_witness.chapter_bundle(chapter)
    bucket = bundle['primary']
    yaml_path = TRANSLATION_DIR / f'{chapter:03d}.yaml'
    control_blocks = [
        (block['page'], block['label'], block['text'])
        for block in bundle['secondary']['kmosko1907']
        if block.get('usable')
    ]

    parts = [
        f'# 2 Baruch chapter draft prompt — chapter {chapter}',
        '',
        'You are drafting a translation-ready English rendering of one chapter of 2 Baruch.',
        'Primary rule: **Ceriani 1871 Syriac remains the base text.**',
        'Secondary rule: Kmosko control pages, Charles 1896, and Violet 1924 help with boundary / ambiguity decisions but do not replace the primary Syriac witness.',
        '',
        '## Current substrate status',
        '- The chapter bucket below is **chapter-ready**, but some edge pages still carry medium-confidence boundary judgments.',
        '- If a boundary looks doubtful, note that in the draft comments / footnotes rather than silently forcing a false precision.',
        '',
        f'## Source bucket for 2 Baruch {chapter}',
        f'- reference: {bundle["reference"]}',
        f'- source PDF pages: {bucket["source_pdf_pages"]}',
        f'- source printed pages: {bucket["source_printed_pages"]}',
        f'- translation YAML target: {yaml_path.relative_to(REPO_ROOT)}',
        '',
        '## Primary Syriac source text',
        bucket['text'],
        '',
    ]

    if control_blocks:
        parts.extend([
            '## Available targeted Kmosko control pages',
            'Use these only as control witnesses / clarification aids.',
            '',
        ])
        for page, label, text in control_blocks:
            parts.extend([
                f'### Kmosko page {page} — {label}',
                text[:3000],
                '',
            ])
    else:
        parts.extend([
            '## Available targeted Kmosko control pages',
            'No targeted Kmosko page is currently attached to this chapter zone yet.',
            '',
        ])

    parts.extend([
        '## Additional notes',
        CONTROL_PLAN.read_text(encoding='utf-8')[:4000],
        '',
        '## Spot-check guidance',
        SPOTCHECK_QUEUE.read_text(encoding='utf-8')[:2500],
        '',
        '## Output expectation',
        textwrap.dedent(f'''\
        Update `{yaml_path.relative_to(REPO_ROOT)}` with:
        - source text retained as-is unless the bucket itself is rebuilt
        - translation.text filled with the English draft
        - philosophy: optimal-equivalence
        - footnotes only where the source situation really requires them
        ''').strip(),
        '',
        'Prefer honesty over false exactness. Where a medium-confidence boundary still matters, say so plainly.',
    ])
    return '\n'.join(parts).strip() + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chapter', type=int, required=True)
    args = ap.parse_args()
    print(build_prompt(args.chapter))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
