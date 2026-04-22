#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import yaml
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE = REPO_ROOT / 'sources/nag_hammadi/texts/gospel_of_truth/source_bundle.json'
TRANSLATION_ROOT = REPO_ROOT / 'translation/extra_canonical/gospel_of_truth'
REQUIRED = {'id','reference','unit','book','source','translation','lexical_decisions','technical_vocabulary_note','textual_note','ai_draft'}

def expected_ids() -> list[str]:
    return [s['segment_id'] for s in json.loads(BUNDLE.read_text(encoding='utf-8'))['sections']]

def validate_one(section_id: str) -> list[str]:
    path = TRANSLATION_ROOT / f'{section_id}.yaml'
    if not path.exists():
        return [f'{section_id}: missing file']
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    errs=[]
    missing = sorted(REQUIRED - set(data))
    if missing: errs.append(f"{section_id}: missing top-level keys: {', '.join(missing)}")
    if not str((data.get('translation') or {}).get('text','')).strip(): errs.append(f'{section_id}: translation.text empty')
    if not isinstance(data.get('lexical_decisions'), list) or not data.get('lexical_decisions'): errs.append(f'{section_id}: lexical_decisions missing/empty')
    if not str(data.get('technical_vocabulary_note','')).strip(): errs.append(f'{section_id}: technical_vocabulary_note empty')
    if not str(data.get('textual_note','')).strip(): errs.append(f'{section_id}: textual_note empty')
    source = data.get('source') or {}
    if not source.get('primary_page_texts'): errs.append(f'{section_id}: source.primary_page_texts missing/empty')
    return errs

def main() -> int:
    errs=[]
    for sid in expected_ids(): errs.extend(validate_one(sid))
    if errs:
        print('\n'.join(errs)); print(f'\nFAILED: {len(errs)} issue(s).'); return 1
    print(f'OK: validated {len(expected_ids())} Gospel of Truth draft files.'); return 0
if __name__ == '__main__':
    raise SystemExit(main())
