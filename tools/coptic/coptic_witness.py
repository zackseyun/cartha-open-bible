#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import OCR_JOBS_ROOT, RAW_ROOT, WITNESSES_ROOT, ensure_dir, load_consult_registry, load_json, load_manifest, load_segments, rel, resolve_text_ids, utc_now, write_json


def witness_files(text_id: str, witness_id: str) -> dict[str, object] | None:
    base = RAW_ROOT / text_id / witness_id
    html_path = base.with_suffix('.html')
    text_path = base.with_suffix('.txt')
    meta_path = base.with_suffix('.meta.json')
    if not any(path.exists() for path in [html_path, text_path, meta_path]):
        return None

    payload: dict[str, object] = {}
    if html_path.exists():
        payload['html_path'] = rel(html_path)
    if text_path.exists():
        payload['text_path'] = rel(text_path)
        payload['preview'] = text_path.read_text(encoding='utf-8')[:1200].strip()
    if meta_path.exists():
        payload['meta_path'] = rel(meta_path)
        payload['meta'] = load_json(meta_path)
    return payload


def ocr_job_files(text_id: str, witness_id: str) -> dict | None:
    path = OCR_JOBS_ROOT / f'{text_id}.{witness_id}.json'
    if not path.exists():
        return None
    payload = load_json(path)
    payload['job_path'] = rel(path)
    return payload


def build_bundle(text_id: str) -> Path:
    manifest = load_manifest(text_id)
    consult_registry = load_consult_registry()
    segments = load_segments(manifest)

    witnesses = []
    next_actions = []

    for witness in manifest.get('primary_witnesses', []):
        entry = {
            'witness_id': witness['witness_id'],
            'role': witness['role'],
            'provider': witness['provider'],
            'format': witness['format'],
            'status': witness.get('status', 'planned'),
            'notes': witness.get('notes'),
            'url': witness.get('url'),
        }
        files = witness_files(text_id, witness['witness_id'])
        if files:
            entry['status'] = 'fetched'
            entry['files'] = files
        job = ocr_job_files(text_id, witness['witness_id'])
        if job:
            entry['ocr_job'] = job
            if entry['status'] != 'fetched':
                entry['status'] = job.get('status', entry['status'])
        if witness['format'] == 'html_page' and not files:
            next_actions.append(f"Fetch HTML witness for {witness['witness_id']}")
        if witness['format'] in {'pdf_ocr', 'image_ocr'} and not job:
            next_actions.append(f"Prepare OCR job for {witness['witness_id']}")
        if witness['format'] in {'pdf_ocr', 'image_ocr'} and job and not job.get('registered_input_path'):
            next_actions.append(f"Register OCR input for {witness['witness_id']}")
        witnesses.append(entry)

    bundle = {
        'generated_at': utc_now(),
        'text_id': text_id,
        'title': manifest['title'],
        'phase': manifest['phase'],
        'goal': manifest['goal'],
        'segment_unit': manifest['segment_unit'],
        'segment_count': len(segments),
        'segments': segments,
        'accuracy_profile': manifest['accuracy_profile'],
        'cross_reference_strategy': manifest.get('cross_reference_strategy'),
        'guardrails': manifest.get('guardrails', []),
        'witnesses': witnesses,
        'consult_sources': [consult_registry[source_id] for source_id in manifest.get('consult_sources', []) if source_id in consult_registry],
        'next_actions': next_actions,
    }

    target_dir = ensure_dir(WITNESSES_ROOT / text_id)
    json_path = target_dir / 'bundle.json'
    md_path = target_dir / 'bundle.md'
    write_json(json_path, bundle)

    lines = [
        f'# {manifest["title"]} witness bundle',
        '',
        f'- Phase: {manifest["phase"]}',
        f'- Segment unit: {manifest["segment_unit"]}',
        f'- Seeded segments: {len(segments)}',
        '',
        '## Witness status',
        '',
    ]
    for witness in witnesses:
        lines.append(f"- **{witness['witness_id']}** — {witness['status']} ({witness['role']})")
    lines.extend(['', '## Guardrails', ''])
    for rule in bundle['guardrails']:
        lines.append(f'- {rule}')
    lines.extend(['', '## Next actions', ''])
    if next_actions:
        for action in next_actions:
            lines.append(f'- {action}')
    else:
        lines.append('- No immediate blockers recorded in the scaffold.')
    md_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return json_path


def main() -> None:
    parser = argparse.ArgumentParser(description='Build per-text Nag Hammadi witness bundles.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    build = subparsers.add_parser('build', help='Build witness bundles.')
    build.add_argument('--text', action='append', dest='texts', help='Text id to build. Repeatable.')
    build.add_argument('--all', action='store_true', help='Build all configured texts.')

    args = parser.parse_args()
    text_ids = resolve_text_ids(args.texts, args.all)
    for text_id in text_ids:
        path = build_bundle(text_id)
        print(f'[built] {rel(path)}')


if __name__ == '__main__':
    main()
