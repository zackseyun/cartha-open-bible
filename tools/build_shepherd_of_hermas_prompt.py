#!/usr/bin/env python3
"""build_shepherd_of_hermas_prompt.py — assemble a Shepherd of Hermas unit prompt."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import shepherd_of_hermas as hermas

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCTRINE_PATH = REPO_ROOT / 'DOCTRINE.md'
PHILOSOPHY_PATH = REPO_ROOT / 'PHILOSOPHY.md'
BOOK_CONTEXT_PATH = REPO_ROOT / 'tools' / 'prompts' / 'book_contexts' / 'shepherd_of_hermas.md'


@dataclass
class PromptBundle:
    unit: hermas.NormalizedUnit
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    source_warnings: list[str]


ZONE2_CONSULTS = [
    'Holmes / Lake / Lightfoot Apostolic Fathers editions and notes (consult only)',
    'Modern Hermas commentary and translation literature (consult only)',
    'Secondary Latin / Ethiopic witness discussion for fact-level context only',
]


def _git_head_short() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return 'unknown'


def _snapshot_label(label: str) -> str:
    return f'{label} @{_git_head_short()}'


def _load_excerpt(path: pathlib.Path, keep_sections: set[str] | None = None) -> str:
    if not path.exists():
        return f'({path.name} not found)'
    if keep_sections is None:
        return path.read_text(encoding='utf-8').strip()
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


def book_context() -> str:
    return _load_excerpt(BOOK_CONTEXT_PATH)


def _source_warnings(unit: hermas.NormalizedUnit) -> list[str]:
    warnings: list[str] = []
    unit_map = hermas.load_unit_map()
    for row in unit_map.get('units', []):
        if row.get('unit_id') == unit.unit_id:
            for note in row.get('notes', []) or []:
                warnings.append(str(note))
            break
    for source_file in unit.source_files:
        meta_path = REPO_ROOT / 'sources' / 'shepherd_of_hermas' / 'transcribed' / 'raw' / source_file.replace('.txt', '.meta.json')
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('backend') == 'manual-repair':
            warnings.append(f'Raw page {meta.get("page")} includes a manual repair: {meta.get("repair_note", "manual repair recorded in page metadata")}.')
    if unit.unit_id in set(hermas.suspicious_units()):
        warnings.append('This normalized unit still matches heuristic OCR-suspicion patterns and should be spot-checked before final publication.')
    return warnings


def build_shepherd_of_hermas_prompt(*, unit_id: str | None = None, sequence: int | None = None) -> PromptBundle:
    unit = hermas.load_normalized_unit(unit_id, sequence=sequence)
    if unit is None:
        target = unit_id if unit_id is not None else f'sequence {sequence}'
        raise LookupError(f'Shepherd of Hermas unit {target} not found in normalized source layer')

    source_payload = {
        'edition': unit.source_edition,
        'language': 'Greek',
        'text': unit.text,
        'unit_id': unit.unit_id,
        'label': unit.label,
        'sequence': unit.sequence,
        'part': unit.part_name,
        'heading': unit.heading,
        'source_pages': unit.source_pages,
        'source_files': unit.source_files,
        'normalization_note': 'This unit comes from the normalized Lightfoot 1891 Hermas OCR layer.',
    }
    warnings = _source_warnings(unit)
    zone1 = [
        _snapshot_label('Lightfoot 1891 Hermas (normalized OCR)'),
        _snapshot_label('Manual repair metadata where noted'),
    ]

    prompt = f"""# Unit

Reference: Shepherd of Hermas — {unit.label}
ID: HERM.{unit.unit_id}
Sequence: {unit.sequence}
Source pages: {unit.source_pages}

# Book context

{book_context()}

# Zone 1 primary source

{json.dumps(source_payload, ensure_ascii=False, indent=2)}

# Zone 2 consult registry

{json.dumps(ZONE2_CONSULTS, ensure_ascii=False, indent=2)}

# Source integrity notes

{json.dumps(warnings or ['No known source-integrity warnings for this unit.'], ensure_ascii=False, indent=2)}

# Derivative-work guardrails

- The English output must remain anchored in the Greek unit text above.
- Do NOT reproduce wording from copyrighted modern Hermas translations.
- Use later scholarship only as fact-level context, not as source phrasing.
- Preserve allegorical, paraenetic, and visionary texture instead of flattening it.

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# Task

Produce the highest-quality draft English translation you can for **Shepherd of Hermas {unit.label}**.

Requirements:
- Translate the whole unit as a coherent literary section.
- Preserve symbolic and ecclesial language carefully.
- Do not collapse repeated exhortation into smoother but thinner English.
- Keep lexical/theological reasoning explicit enough for later audit and revision.
"""

    return PromptBundle(
        unit=unit,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1,
        zone2_consults_known=ZONE2_CONSULTS,
        source_warnings=warnings,
    )


def _to_jsonable(bundle: PromptBundle) -> dict[str, Any]:
    return {
        'reference': f'Shepherd of Hermas — {bundle.unit.label}',
        'id': f'HERM.{bundle.unit.unit_id}',
        'prompt': bundle.prompt,
        'source': bundle.source_payload,
        'zone1_sources_at_draft': bundle.zone1_sources_at_draft,
        'zone2_consults_known': bundle.zone2_consults_known,
        'source_warnings': bundle.source_warnings,
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit-id', help='Hermas unit id such as V.3.i, M.4.ii, S.8.ii')
    parser.add_argument('--sequence', type=int, help='1-based sequence in unit_map order')
    parser.add_argument('--json', action='store_true', help='Print JSON payload instead of raw prompt')
    args = parser.parse_args()
    if not args.unit_id and not args.sequence:
        parser.error('Provide --unit-id or --sequence')
    bundle = build_shepherd_of_hermas_prompt(unit_id=args.unit_id, sequence=args.sequence)
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
