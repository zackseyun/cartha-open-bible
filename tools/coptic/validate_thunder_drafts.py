#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import yaml
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENT = REPO_ROOT / 'sources/nag_hammadi/texts/thunder_perfect_mind/alignment.json'
TRANSLATION_ROOT = REPO_ROOT / 'translation/extra_canonical/thunder_perfect_mind'
REQUIRED = {'id','reference','unit','book','source','translation','lexical_decisions','parallelism_check','voice_check','alignment_risk_note','ai_draft','revision_risk_note'}

def expected_ids() -> list[str]:
    return [b['segment_id'] for b in json.loads(ALIGNMENT.read_text(encoding='utf-8'))['blocks']]

def validate_one(segment_id: str) -> list[str]:
    path = TRANSLATION_ROOT / f'{segment_id}.yaml'
    if not path.exists():
        return [f'{segment_id}: missing file']
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    errs=[]
    missing = sorted(REQUIRED - set(data))
    if missing: errs.append(f"{segment_id}: missing top-level keys: {', '.join(missing)}")
    if not str((data.get('translation') or {}).get('text','')).strip(): errs.append(f'{segment_id}: translation.text empty')
    if not isinstance(data.get('lexical_decisions'), list) or not data.get('lexical_decisions'): errs.append(f'{segment_id}: lexical_decisions missing/empty')
    for field in ('parallelism_check','voice_check','alignment_risk_note','revision_risk_note'):
        if not str(data.get(field,'')).strip(): errs.append(f'{segment_id}: {field} empty')
    source = data.get('source') or {}
    if not str(source.get('approx_ocr_excerpt','')).strip(): errs.append(f'{segment_id}: source.approx_ocr_excerpt empty')
    return errs

def main() -> int:
    errs=[]
    for sid in expected_ids(): errs.extend(validate_one(sid))
    if errs:
        print('\n'.join(errs)); print(f'\nFAILED: {len(errs)} issue(s).'); return 1
    print(f'OK: validated {len(expected_ids())} Thunder draft files.'); return 0
if __name__ == '__main__':
    raise SystemExit(main())
