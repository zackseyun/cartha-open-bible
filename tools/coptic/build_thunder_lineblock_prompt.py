"""build_thunder_lineblock_prompt.py — assemble one Thunder line-block prompt from the alignment layer."""
from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ALIGNMENT = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/alignment.json'
DOCTRINE_PATH = REPO_ROOT / 'DOCTRINE.md'
PHILOSOPHY_PATH = REPO_ROOT / 'PHILOSOPHY.md'
ZONE1_SOURCES = [
    'Nag Hammadi Codex VI.2 facsimile OCR (Vertex Gemini 3.1 Pro) primary Coptic witness',
]
ZONE2_CONSULTS = [
    'Parrott NHS 11 — consult only',
    'MacRae — consult only',
    'Poirier 1995 — consult only',
    'OtherGospels / Zinner consult text — English comprehension only',
]


@dataclass
class PromptBundle:
    segment_id: str
    label: str
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    alignment_confidence: str


def _load_alignment() -> dict[str, Any]:
    return json.loads(ALIGNMENT.read_text(encoding='utf-8'))


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


def build_thunder_lineblock_prompt(segment_id: str) -> PromptBundle:
    data = _load_alignment()
    by_id = {row['segment_id']: row for row in data['blocks']}
    if segment_id not in by_id:
        raise SystemExit(f'Unknown Thunder segment id: {segment_id}')
    block = by_id[segment_id]
    label = f"{block['chapter_title']} — {block['block_index']}"
    source_payload = {
        'edition': 'Nag Hammadi Codex VI.2 facsimile OCR (Vertex Gemini 3.1 Pro)',
        'language': 'Coptic',
        'segment_id': segment_id,
        'chapter_title': block['chapter_title'],
        'block_index': block['block_index'],
        'approx_page_start': block['approx_page_start'],
        'approx_page_end': block['approx_page_end'],
        'approx_page_line_start': block['approx_page_line_start'],
        'approx_page_line_end': block['approx_page_line_end'],
        'approx_ocr_excerpt': block['approx_ocr_excerpt'],
        'consult_text': block['english_consult_text'],
        'alignment_basis': block['alignment_basis'],
        'alignment_confidence': block['confidence'],
        'warnings': block.get('warnings', []),
    }
    lines = [
        '## Task',
        f"Draft a faithful English translation of Thunder, Perfect Mind — **{label}** (segment `{segment_id}`) from the mapped Coptic OCR excerpt below.",
        '',
        'This prompt is built from an explicit alignment layer. Use the Coptic OCR excerpt as the source text and the English consult text only as a comprehension / alignment aid.',
        '',
        '## Approximate Coptic OCR excerpt',
        '',
        f"- Mapped page span: {block['approx_page_start']} → {block['approx_page_end']}",
        f"- Alignment confidence: {block['confidence']}",
        f"- Alignment basis: {block['alignment_basis']}",
        '',
        '```coptic',
        block.get('approx_ocr_excerpt', '').strip() or '(empty)',
        '```',
        '',
        '## Consult-only English block',
        '',
        'Use this only to help orient the line-block mapping; do not reuse its phrasing.',
        '',
        '```text',
        block.get('english_consult_text', '').strip() or '(empty)',
        '```',
        '',
        '## Warnings',
        '',
    ]
    if block.get('warnings'):
        for warning in block['warnings']:
            lines.append(f'- {warning}')
    else:
        lines.append('- No additional alignment warnings recorded.')
    lines.extend([
        '',
        '## Translation stance',
        '',
        '- Preserve the poem’s paradoxes, cadence, and voice.',
        '- Every contradictory pair should remain contradictory in English.',
        '- Do not smooth away recurring “I am” structures.',
        '- If a line becomes elegant but loses the antithetical force of the original, reject that rendering.',
        '- Where the alignment confidence is only medium/low, record uncertainty honestly instead of forcing false precision.',
        '',
        '## DOCTRINE.md excerpt',
        '',
        doctrine_excerpt(),
        '',
        '## PHILOSOPHY.md excerpt',
        '',
        philosophy_excerpt(),
        '',
        '## Required output',
        '',
        '- translation draft',
        '- parallelism check',
        '- voice check',
        '- alignment-risk note',
        '- revision risk note',
        '',
    ])
    return PromptBundle(
        segment_id=segment_id,
        label=label,
        prompt='\n'.join(lines),
        source_payload=source_payload,
        zone1_sources_at_draft=ZONE1_SOURCES,
        zone2_consults_known=ZONE2_CONSULTS,
        alignment_confidence=block['confidence'],
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--segment', required=True)
    args = ap.parse_args()
    bundle = build_thunder_lineblock_prompt(args.segment)
    print(bundle.prompt)


if __name__ == '__main__':
    main()
