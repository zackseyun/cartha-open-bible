#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import yaml
from truth_reader_structure import READER_SECTIONS
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLE = REPO_ROOT / 'sources/nag_hammadi/texts/gospel_of_truth/source_bundle.json'
TRANSLATION_ROOT = REPO_ROOT / 'translation/extra_canonical/gospel_of_truth'
REQUIRED = {'id','reference','unit','book','source','translation','lexical_decisions','technical_vocabulary_note','textual_note','ai_draft'}
READER_NAVIGATION_NOTE_FRAGMENT = 'editorial reader-navigation aids only'

def expected_sections() -> dict[str, str]:
    return {
        s['segment_id']: s['label']
        for s in json.loads(BUNDLE.read_text(encoding='utf-8'))['sections']
    }

def expected_ids() -> list[str]:
    return list(expected_sections())

def validate_one(section_id: str) -> list[str]:
    path = TRANSLATION_ROOT / f'{section_id}.yaml'
    if not path.exists():
        return [f'{section_id}: missing file']
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    errs=[]
    missing = sorted(REQUIRED - set(data))
    if missing: errs.append(f"{section_id}: missing top-level keys: {', '.join(missing)}")
    if not str((data.get('translation') or {}).get('text','')).strip(): errs.append(f'{section_id}: translation.text empty')
    text_paragraphs = [
        line.strip()
        for line in str((data.get('translation') or {}).get('text','')).splitlines()
        if line.strip()
    ]
    reader_sections = ((data.get('reader_navigation') or {}).get('reader_sections') or data.get('reader_sections') or [])
    if not isinstance(reader_sections, list) or not reader_sections:
        errs.append(f'{section_id}: reader_navigation.reader_sections missing/empty')
    else:
        covered = []
        for index, section in enumerate(reader_sections, start=1):
            if not isinstance(section, dict):
                errs.append(f'{section_id}: reader section {index} is not a mapping')
                continue
            if not str(section.get('title', '')).strip():
                errs.append(f'{section_id}: reader section {index} missing title')
            try:
                start = int(section.get('paragraph_start'))
                end = int(section.get('paragraph_end'))
            except (TypeError, ValueError):
                errs.append(f'{section_id}: reader section {index} has invalid paragraph range')
                continue
            if start < 1 or end < start or end > len(text_paragraphs):
                errs.append(f'{section_id}: reader section {index} paragraph range {start}-{end} outside 1..{len(text_paragraphs)}')
                continue
            covered.extend(range(start, end + 1))
        if sorted(covered) != list(range(1, len(text_paragraphs) + 1)):
            errs.append(f'{section_id}: reader section ranges do not cover every translation paragraph exactly once')
    if not isinstance(data.get('lexical_decisions'), list) or not data.get('lexical_decisions'): errs.append(f'{section_id}: lexical_decisions missing/empty')
    if not str(data.get('technical_vocabulary_note','')).strip(): errs.append(f'{section_id}: technical_vocabulary_note empty')
    if not str(data.get('textual_note','')).strip(): errs.append(f'{section_id}: textual_note empty')
    source = data.get('source') or {}
    if not source.get('primary_page_texts'): errs.append(f'{section_id}: source.primary_page_texts missing/empty')
    expected_heading = expected_sections()[section_id]
    nav = data.get('reader_navigation')
    if not isinstance(nav, dict):
        errs.append(f'{section_id}: reader_navigation missing/object expected')
    else:
        if nav.get('division_kind') != 'editorial_section':
            errs.append(f'{section_id}: reader_navigation.division_kind must be editorial_section')
        if nav.get('order') != int(section_id):
            errs.append(f'{section_id}: reader_navigation.order must be {int(section_id)}')
        if nav.get('heading') != expected_heading:
            errs.append(f'{section_id}: reader_navigation.heading must be {expected_heading!r}')
        if nav.get('authoritative_division') is not False:
            errs.append(f'{section_id}: reader_navigation.authoritative_division must be false')
        if READER_NAVIGATION_NOTE_FRAGMENT not in str(nav.get('note', '')):
            errs.append(f'{section_id}: reader_navigation.note must identify the heading as editorial navigation')
        if nav.get('reader_sections') != READER_SECTIONS.get(section_id):
            errs.append(f'{section_id}: reader_navigation.reader_sections must match the transparent Gospel of Truth structure')
    return errs

def main() -> int:
    errs=[]
    for sid in expected_ids(): errs.extend(validate_one(sid))
    if errs:
        print('\n'.join(errs)); print(f'\nFAILED: {len(errs)} issue(s).'); return 1
    print(f'OK: validated {len(expected_ids())} Gospel of Truth draft files.'); return 0
if __name__ == '__main__':
    raise SystemExit(main())
