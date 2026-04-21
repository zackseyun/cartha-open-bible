#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import PROMPTS_ROOT, WITNESSES_ROOT, ensure_dir, load_json, rel, resolve_text_ids
from segment_extractors import load_extracted_segments

PROFILE_INTROS = {
    'thomas': [
        'Translate from the Coptic witness first.',
        'If a Greek overlap witness exists for this unit, compare it and record meaningful divergences instead of silently collapsing them.',
        'When a Synoptic parallel exists, use it as context only; keep Thomas sounding like Thomas unless the source evidence justifies a closer echo.',
        'Flag any place where the Coptic and Greek appear to point in different directions.',
    ],
    'truth': [
        'Translate the poetic theology without flattening its technical vocabulary.',
        'Prefer retaining key Valentinian conceptual terms when natural English would erase the theology.',
        'If an overlap witness can repair a damaged place, note the repair explicitly.',
        'Do not naturalize difficult metaphors merely to make the prose sound smoother.',
    ],
    'thunder': [
        'Preserve the poem\'s paradoxes, cadence, and voice.',
        'Every contradictory pair should remain contradictory in English.',
        'Do not smooth away the recurring "I am" structures.',
        'If a line becomes elegant but loses the antithetical force of the original, reject that rendering.',
    ],
}

PROFILE_OUTPUTS = {
    'thomas': ['translation draft', 'textual note', 'Greek-overlap decision note (if applicable)', 'revision risk note'],
    'truth': ['translation draft', 'technical-vocabulary note', 'damage/repair note (if applicable)', 'revision risk note'],
    'thunder': ['translation draft', 'parallelism check', 'voice check', 'revision risk note'],
}

PROFILE_CROSSCHECKS = {
    'thomas': [
        'Check the Gebhardt-Klein cross-check witness once OCR is available.',
        'Use Greek fragment overlap where it exists and record the decision, not just the result.',
        'When NT parallels are wired in later, compare without harmonizing away Thomasine distinctives.',
    ],
    'truth': [
        'Check XII.2 overlap once OCR is registered and transcribed.',
        'Track any place where theological vocabulary could be flattened by an overly smooth English rendering.',
    ],
    'thunder': [
        'Verify that every paradoxical pairing is still visibly paradoxical in English.',
        'Check whether line cadence or repeated “I am” force has been softened in revision.',
    ],
}


def fetched_witness_paths(bundle: dict) -> list[str]:
    paths: list[str] = []
    for witness in bundle['witnesses']:
        files = witness.get('files') or {}
        for key in ['text_path', 'json_path', 'html_path']:
            value = files.get(key)
            if value and value not in paths:
                paths.append(value)
    return paths


def build_overview(text_id: str) -> str:
    bundle = load_json(WITNESSES_ROOT / text_id / 'bundle.json')
    title = bundle['title']
    profile = bundle['accuracy_profile']
    lines = [
        f'# {title} — Phase E overview prompt',
        '',
        f'You are preparing an accuracy-first English translation workflow for **{title}**.',
        f'Goal: {bundle["goal"]}',
        '',
        '## Witness posture',
        '',
    ]
    for witness in bundle['witnesses']:
        source = witness.get('url') or witness.get('files', {}).get('text_path') or 'local source pending'
        lines.append(f"- **{witness['witness_id']}** ({witness['role']}) — {witness['status']}; source: {source}")
    lines.extend(['', '## Guardrails', ''])
    for rule in bundle['guardrails']:
        lines.append(f'- {rule}')
    lines.extend(['', '## Translation stance', ''])
    for rule in PROFILE_INTROS[profile]:
        lines.append(f'- {rule}')
    lines.extend(['', '## Consult-only references', ''])
    for consult in bundle['consult_sources']:
        lines.append(f"- **{consult['label']}** — {consult['notes']}")
    lines.extend(['', '## Required output for each unit', ''])
    for item in PROFILE_OUTPUTS[profile]:
        lines.append(f'- {item}')
    lines.extend(['', '## Current scaffold status', ''])
    if bundle['next_actions']:
        for action in bundle['next_actions']:
            lines.append(f'- {action}')
    else:
        lines.append('- No immediate scaffold gaps recorded.')
    return '\n'.join(lines) + '\n'


def build_segment_prompt(bundle: dict, segment: dict[str, str]) -> str:
    title = bundle['title']
    profile = bundle['accuracy_profile']
    excerpt = (segment.get('excerpt') or '').strip()
    lines = [
        f'# {title} — {segment["label"]}',
        '',
        f'- Segment id: `{segment["segment_id"]}`',
        f'- Segment unit: {bundle["segment_unit"]}',
        f'- Heading: {segment.get("heading") or segment["label"]}',
        f'- Reference span: {segment.get("start_ref", "")} → {segment.get("end_ref", "")}',
        '',
        '## Available witness files',
        '',
    ]
    for path in fetched_witness_paths(bundle):
        lines.append(f'- `{path}`')
    lines.extend(['', '## Primary witness excerpt', ''])
    if excerpt:
        lines.extend(['```text', excerpt, '```'])
    else:
        lines.append('_Excerpt not yet available in the scaffold._')
    lines.extend(['', '## Translation stance', ''])
    for rule in PROFILE_INTROS[profile]:
        lines.append(f'- {rule}')
    lines.extend(['', '## Segment-specific checks', ''])
    for rule in bundle['guardrails']:
        lines.append(f'- {rule}')
    for rule in PROFILE_CROSSCHECKS[profile]:
        lines.append(f'- {rule}')
    lines.extend(['', '## Consult-only references', ''])
    for consult in bundle['consult_sources']:
        lines.append(f"- **{consult['label']}** — {consult['notes']}")
    lines.extend(['', '## Required output', ''])
    for item in PROFILE_OUTPUTS[profile]:
        lines.append(f'- {item}')
    return '\n'.join(lines) + '\n'


def build_segment_prompts(text_id: str, bundle: dict) -> int:
    extracted = {segment['segment_id']: segment for segment in load_extracted_segments(text_id)}
    segment_dir = ensure_dir(PROMPTS_ROOT / text_id / 'segments')
    index_lines = [
        f'# {bundle["title"]} — segment prompts',
        '',
        f'Total segments: {len(bundle["segments"])}',
        '',
    ]
    count = 0
    for segment in bundle['segments']:
        merged = {**segment, **extracted.get(segment['segment_id'], {})}
        output_path = segment_dir / f"{segment['segment_id']}.md"
        output_path.write_text(build_segment_prompt(bundle, merged), encoding='utf-8')
        index_lines.append(f"- `{segment['segment_id']}` — {segment['label']}")
        count += 1
    (segment_dir / 'index.md').write_text('\n'.join(index_lines) + '\n', encoding='utf-8')
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate Nag Hammadi translation prompts from witness bundles.')
    parser.add_argument('--text', action='append', dest='texts', help='Text id to generate. Repeatable.')
    parser.add_argument('--all', action='store_true', help='Generate prompts for all configured texts.')
    args = parser.parse_args()

    text_ids = resolve_text_ids(args.texts, args.all)
    for text_id in text_ids:
        bundle = load_json(WITNESSES_ROOT / text_id / 'bundle.json')
        output_dir = ensure_dir(PROMPTS_ROOT / text_id)
        overview_path = output_dir / 'overview.md'
        overview_path.write_text(build_overview(text_id), encoding='utf-8')
        segment_count = build_segment_prompts(text_id, bundle)
        print(f'[built] {rel(overview_path)}')
        print(f'[built] {rel(output_dir / "segments" / "index.md")} ({segment_count} segments)')


if __name__ == '__main__':
    main()
