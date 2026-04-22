"""build_truth_section_prompt.py — assemble one Gospel of Truth section prompt."""
from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SOURCE_BUNDLE = REPO_ROOT / 'sources/nag_hammadi/texts/gospel_of_truth/source_bundle.json'
DOCTRINE_PATH = REPO_ROOT / 'DOCTRINE.md'
PHILOSOPHY_PATH = REPO_ROOT / 'PHILOSOPHY.md'

ZONE1_SOURCES = [
    'Nag Hammadi Codex I.3 facsimile OCR (Vertex Gemini 3.1 Pro) primary Coptic witness',
    'Nag Hammadi Codex XII.2 overlap fragments (OCR) for sections 004-007',
]
ZONE2_CONSULTS = [
    'Attridge & MacRae NHS 22-23 — consult only',
    'Thomassen — consult only',
    'Meyer 2007 — consult only',
    'Mattison/Zinner OGV — public-domain English consult only',
]


@dataclass
class PromptBundle:
    section_id: str
    section_label: str
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    has_overlap_fragments: bool


def _load_bundle() -> dict[str, Any]:
    return json.loads(SOURCE_BUNDLE.read_text(encoding='utf-8'))


def _load_excerpt(path: pathlib.Path, keep_sections: set[str]) -> str:
    if not path.exists():
        return f'({path.name} not found)'
    lines = path.read_text(encoding='utf-8').splitlines()
    keeping = False
    out: list[str] = []
    for line in lines:
        if line.startswith('## '):
            keeping = line.strip() in keep_sections
        if keeping:
            out.append(line)
    return '\n'.join(out).strip() or f'({path.name} excerpt empty)'


def doctrine_excerpt() -> str:
    return _load_excerpt(DOCTRINE_PATH, {'## Translation philosophy', '## Contested terms'})


def philosophy_excerpt() -> str:
    return _load_excerpt(PHILOSOPHY_PATH, {'## What we are translating', '## What "transparent" actually means here'})


def format_pages(section: dict[str, Any]) -> str:
    out: list[str] = []
    for page in section.get('primary_page_texts', []):
        out.append(f"### Codex I page {page['page_num']}")
        out.append('```coptic')
        out.append(page['text'] or '(empty)')
        out.append('```')
        finish = page.get('meta', {}).get('finish_reason')
        if finish and finish != 'STOP':
            out.append(f'- OCR finish note: `{finish}`')
        out.append('')
    return '\n'.join(out).strip() or '_No primary page texts mapped._'


def format_overlap(section: dict[str, Any]) -> str:
    frags = section.get('overlap_fragments') or []
    if not frags:
        return '_No overlap fragments for this section._'
    out: list[str] = []
    for frag in frags:
        out.append(f"### {frag['fragment_id']} (NHC XII p. {frag.get('nhc_xii_page')})")
        if frag.get('approximate_i3_alignment'):
            out.append(f"- Alignment: {frag['approximate_i3_alignment']}")
        out.append('```coptic')
        out.append(frag.get('text') or '(empty)')
        out.append('```')
        out.append('')
    return '\n'.join(out).strip()


def build_truth_section_prompt(section_id: str) -> PromptBundle:
    bundle = _load_bundle()
    by_id = {row['segment_id']: row for row in bundle['sections']}
    if section_id not in by_id:
        raise SystemExit(f'Unknown Gospel of Truth section id: {section_id}')
    section = by_id[section_id]
    source_payload = {
        'edition': 'Nag Hammadi Codex I.3 facsimile OCR (Vertex Gemini 3.1 Pro)',
        'language': 'Coptic',
        'section_id': section_id,
        'section_label': section['label'],
        'codex_pages': section.get('consult_codex_pages', []),
        'primary_page_texts': section.get('primary_page_texts', []),
        'overlap_fragments': section.get('overlap_fragments', []),
        'warnings': section.get('warnings', []),
        'consult_excerpt': section.get('consult_excerpt', ''),
    }
    parts = [
        '## Task',
        f"Draft a faithful English translation of Gospel of Truth — **{section['label']}** (section `{section_id}`) from the Coptic primary pages below.",
        '',
        'You must submit your result by calling the `submit_truth_section_draft` function exactly once.',
        '',
        '## Primary Coptic facsimile OCR pages',
        '',
        format_pages(section),
        '',
        '## XII.2 overlap fragments',
        '',
        format_overlap(section),
        '',
        '## Consult-only English comprehension excerpt',
        '',
        'Use this only as a comprehension and section-boundary aid; do not copy its wording.',
        '',
        '```text',
        section.get('consult_excerpt', '').strip() or '(empty)',
        '```',
        '',
        '## Warnings',
        '',
    ]
    if section.get('warnings'):
        for warning in section['warnings']:
            parts.append(f'- {warning}')
    else:
        parts.append('- No special warnings recorded for this section.')
    parts.extend([
        '',
        '## Translation stance',
        '',
        '- Translate the poetic theology without flattening its technical vocabulary.',
        '- Prefer retaining key Valentinian conceptual terms when natural English would erase the theology.',
        '- If an overlap witness can repair a damaged place, note the repair explicitly.',
        '- Do not naturalize difficult metaphors merely to make the prose sound smoother.',
        '- Translate from the facsimile OCR page texts, not from the English consult excerpt.',
        '',
        '## DOCTRINE.md excerpt',
        '',
        doctrine_excerpt(),
        '',
        '## PHILOSOPHY.md excerpt',
        '',
        philosophy_excerpt(),
        '',
        '## Consult-only references',
        '',
    ])
    for item in bundle.get('consult_sources', []):
        parts.append(f"- **{item['label']}** — {item['notes']}")
    parts.extend([
        '',
        '## Required output',
        '',
        '- translation draft',
        '- technical-vocabulary note',
        '- textual note',
        '- overlap-repair note (if applicable)',
        '- revision risk note',
        '',
    ])
    return PromptBundle(
        section_id=section_id,
        section_label=section['label'],
        prompt='\n'.join(parts),
        source_payload=source_payload,
        zone1_sources_at_draft=ZONE1_SOURCES,
        zone2_consults_known=ZONE2_CONSULTS,
        has_overlap_fragments=bool(section.get('overlap_fragments')),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--section', required=True, help='Truth section id like 001..016')
    args = ap.parse_args()
    bundle = build_truth_section_prompt(args.section)
    print(bundle.prompt)


if __name__ == '__main__':
    main()
