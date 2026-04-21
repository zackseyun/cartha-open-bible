#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import OCR_JOBS_ROOT, OCR_OUTPUT_ROOT, STAGING_ROOT, ensure_dir, load_json, load_manifest, rel, resolve_text_ids, utc_now, write_json

OCR_FORMATS = {'pdf_ocr', 'image_ocr'}


def job_path(text_id: str, witness_id: str) -> Path:
    return OCR_JOBS_ROOT / f'{text_id}.{witness_id}.json'


def build_job(text_id: str, witness: dict[str, str]) -> dict:
    output_dir = ensure_dir(OCR_OUTPUT_ROOT / text_id / witness['witness_id'])
    return {
        'job_id': f"{text_id}.{witness['witness_id']}",
        'text_id': text_id,
        'witness_id': witness['witness_id'],
        'status': 'pending_input',
        'engine': 'gemini-2.5-pro',
        'source_format': witness['format'],
        'registered_input_path': None,
        'staging_hint': rel(ensure_dir(STAGING_ROOT / text_id)),
        'output_dir': rel(output_dir),
        'created_at': utc_now(),
        'instructions': [
            'Transcribe Coptic exactly before any normalization.',
            'Preserve line breaks and page boundaries when visible.',
            'Mark uncertain or damaged letters explicitly instead of guessing.',
            'Do not silently harmonize spelling or punctuation.',
            'Emit plaintext plus a short uncertainty note if the witness is hard to read.',
        ],
        'notes': witness.get('notes'),
    }


def prepare_jobs(text_ids: list[str]) -> list[Path]:
    created = []
    ensure_dir(OCR_JOBS_ROOT)
    for text_id in text_ids:
        manifest = load_manifest(text_id)
        for witness in manifest.get('primary_witnesses', []):
            if witness.get('format') not in OCR_FORMATS:
                continue
            path = job_path(text_id, witness['witness_id'])
            if not path.exists():
                write_json(path, build_job(text_id, witness))
                created.append(path)
    return created


def register_input(text_id: str, witness_id: str, input_path: Path) -> Path:
    path = job_path(text_id, witness_id)
    if not path.exists():
        raise SystemExit(f'No OCR job scaffold exists yet for {text_id}/{witness_id}. Run prepare first.')
    payload = load_json(path)
    payload['registered_input_path'] = str(input_path.resolve())
    payload['status'] = 'queued'
    payload['updated_at'] = utc_now()
    write_json(path, payload)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description='Scaffold and update OCR jobs for Coptic witnesses.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    prepare = subparsers.add_parser('prepare', help='Create pending OCR jobs from manifests.')
    prepare.add_argument('--text', action='append', dest='texts', help='Text id to prepare. Repeatable.')
    prepare.add_argument('--all', action='store_true', help='Prepare all configured texts.')

    register = subparsers.add_parser('register', help='Register a local input file for an OCR job.')
    register.add_argument('--text', required=True, help='Text id.')
    register.add_argument('--witness', required=True, help='Witness id.')
    register.add_argument('--input', required=True, help='Absolute or relative path to the local PDF/image.')

    args = parser.parse_args()

    if args.command == 'prepare':
        text_ids = resolve_text_ids(args.texts, args.all)
        created = prepare_jobs(text_ids)
        if created:
            for path in created:
                print(f'[created] {rel(path)}')
        else:
            print('No new OCR jobs were needed.')
        return

    if args.command == 'register':
        input_path = Path(args.input).expanduser()
        if not input_path.exists():
            raise SystemExit(f'Input path does not exist: {input_path}')
        path = register_input(args.text, args.witness, input_path)
        print(f'[queued] {rel(path)}')


if __name__ == '__main__':
    main()
