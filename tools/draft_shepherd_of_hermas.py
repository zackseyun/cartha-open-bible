#!/usr/bin/env python3
"""draft_shepherd_of_hermas.py — draft one or more Hermas units into YAML."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from dotenv import load_dotenv
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / 'translation' / 'extra_canonical' / 'shepherd_of_hermas'
TOOLS_ROOT = REPO_ROOT / 'tools'

sys.path.insert(0, str(TOOLS_ROOT))
import draft as canonical_draft  # noqa: E402
import build_shepherd_of_hermas_prompt as hermas_prompt  # noqa: E402
import shepherd_of_hermas as hermas  # noqa: E402

DEFAULT_MODEL_ID = os.environ.get('CARTHA_MODEL_ID', 'gpt-5.4')
DEFAULT_TEMPERATURE = float(os.environ.get('CARTHA_TEMPERATURE', '0.2'))
DEFAULT_MAX_COMPLETION_TOKENS = int(os.environ.get('CARTHA_MAX_COMPLETION_TOKENS', '12000'))
DEFAULT_CODEX_REASONING_EFFORT = os.environ.get('CARTHA_CODEX_REASONING_EFFORT', 'medium')
DEFAULT_OPENROUTER_MODEL_ID = os.environ.get('CARTHA_OPENROUTER_MODEL', 'openai/gpt-5.4')
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get('AZURE_OPENAI_DEPLOYMENT_ID', 'gpt-5-4-deployment')
DEFAULT_AZURE_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
DEFAULT_PROMPT_ID = os.environ.get('CARTHA_PROMPT_ID', 'hermas_unit_draft_v1')

BACKEND_OPENAI = 'openai-sdk'
BACKEND_OPENROUTER = 'openrouter-sdk'
BACKEND_AZURE = 'azure-openai'
BACKEND_CODEX = 'codex-cli'
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

TOOL_NAME = 'submit_hermas_unit_draft'
TOOL_REASON_VALUES = {
    'alternative_reading',
    'lexical_alternative',
    'textual_variant',
    'cultural_note',
    'cross_reference',
}

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE UNIT OF THE SHEPHERD OF HERMAS. Your job is to produce the highest-quality English rendering you can while exposing the major lexical and theological decisions so the result remains fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the supplied project excerpts.

You will submit your draft by calling the `submit_hermas_unit_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the unit plainly demands one or the other.

Never:
- Paraphrase beyond what the Greek witness warrants.
- Flatten allegories, repentance language, church-order language, or visionary imagery into generic modern prose.
- Import New Testament wording just because the unit echoes familiar Christian vocabulary.
- Omit major lexical or theological decisions from the structured output just to make the prose read cleaner.
- Copy from copyrighted modern Hermas translations.
- Fabricate lexicon entry numbers. If you do not know the exact lexicon entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    'type': 'function',
    'function': {
        'name': TOOL_NAME,
        'description': 'Submit a draft English translation for one Hermas unit, including major lexical and theological decisions.',
        'strict': True,
        'parameters': {
            'type': 'object',
            'required': ['english_text', 'translation_philosophy', 'lexical_decisions'],
            'properties': {
                'english_text': {'type': 'string'},
                'translation_philosophy': {'type': 'string', 'enum': ['formal', 'dynamic', 'optimal-equivalence']},
                'lexical_decisions': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['source_word', 'chosen', 'rationale'],
                        'properties': {
                            'source_word': {'type': 'string'},
                            'chosen': {'type': 'string'},
                            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
                            'lexicon': {'type': 'string'},
                            'entry': {'type': 'string'},
                            'rationale': {'type': 'string'},
                        },
                        'additionalProperties': False,
                    },
                },
                'theological_decisions': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['issue', 'chosen_reading', 'rationale'],
                        'properties': {
                            'issue': {'type': 'string'},
                            'chosen_reading': {'type': 'string'},
                            'alternative_readings': {'type': 'array', 'items': {'type': 'string'}},
                            'rationale': {'type': 'string'},
                            'doctrine_reference': {'type': 'string'},
                        },
                        'additionalProperties': False,
                    },
                },
                'footnotes': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'required': ['marker', 'text', 'reason'],
                        'properties': {
                            'marker': {'type': 'string'},
                            'text': {'type': 'string'},
                            'reason': {'type': 'string', 'enum': sorted(TOOL_REASON_VALUES)},
                        },
                        'additionalProperties': False,
                    },
                },
            },
            'additionalProperties': False,
        },
    },
}


@dataclass
class DraftResult:
    unit: hermas.NormalizedUnit
    record: dict[str, Any]
    output_path: pathlib.Path
    prompt_sha256: str
    model_version: str


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def prune_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: prune_nulls(inner) for key, inner in value.items() if inner is not None}
    if isinstance(value, list):
        return [prune_nulls(item) for item in value if item is not None]
    return value


def codex_login_available() -> bool:
    return canonical_draft.codex_login_available()


def default_backend() -> str:
    configured = os.environ.get('CARTHA_DRAFTER_BACKEND')
    if configured:
        return configured
    if codex_login_available():
        return BACKEND_CODEX
    return BACKEND_OPENAI


DEFAULT_BACKEND = default_backend()


def output_path_for_unit(unit: hermas.NormalizedUnit) -> pathlib.Path:
    return TRANSLATION_ROOT / f'{unit.sequence:03d}.yaml'


def validate_tool_input(tool_input: dict[str, Any]) -> None:
    errors: list[str] = []
    english_text = str(tool_input.get('english_text', '') or '')
    philosophy = str(tool_input.get('translation_philosophy', '') or '')
    lexical_decisions = tool_input.get('lexical_decisions')
    theological_decisions = tool_input.get('theological_decisions')
    footnotes = tool_input.get('footnotes')
    if not english_text.strip():
        errors.append('english_text must be non-empty')
    if philosophy not in {'formal', 'dynamic', 'optimal-equivalence'}:
        errors.append('translation_philosophy must be formal/dynamic/optimal-equivalence')
    if not isinstance(lexical_decisions, list) or not lexical_decisions:
        errors.append('lexical_decisions must be a non-empty array')
    if theological_decisions is not None and not isinstance(theological_decisions, list):
        errors.append('theological_decisions must be an array when present')
    if footnotes is not None and not isinstance(footnotes, list):
        errors.append('footnotes must be an array when present')
    if isinstance(lexical_decisions, list):
        for index, decision in enumerate(lexical_decisions):
            if not isinstance(decision, dict):
                errors.append(f'lexical_decisions[{index}] must be an object')
                continue
            for field in ('source_word', 'chosen', 'rationale'):
                if not str(decision.get(field, '') or '').strip():
                    errors.append(f'lexical_decisions[{index}].{field} must be non-empty')
    if isinstance(footnotes, list):
        for index, note in enumerate(footnotes):
            if not isinstance(note, dict):
                errors.append(f'footnotes[{index}] must be an object')
                continue
            for field in ('marker', 'text', 'reason'):
                if not str(note.get(field, '') or '').strip():
                    errors.append(f'footnotes[{index}].{field} must be non-empty')
            if note.get('reason') not in TOOL_REASON_VALUES:
                errors.append(f'footnotes[{index}].reason must be one of {sorted(TOOL_REASON_VALUES)}')
    if errors:
        raise ValueError('; '.join(errors))


def _strictify_for_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_strictify_for_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    schema = dict(schema)
    if 'properties' in schema and isinstance(schema['properties'], dict):
        coerced: dict[str, Any] = {}
        for key, subschema in schema['properties'].items():
            subschema = _strictify_for_schema(subschema)
            type_value = subschema.get('type')
            if isinstance(type_value, str):
                type_values = [type_value]
            elif isinstance(type_value, list):
                type_values = list(type_value)
            else:
                type_values = []
            if 'null' not in type_values and key not in schema.get('required', []):
                if type_values:
                    type_values.append('null')
                    subschema['type'] = type_values
                else:
                    subschema['type'] = ['null']
            coerced[key] = subschema
        schema['properties'] = coerced
        schema['required'] = list(coerced.keys())
        schema['additionalProperties'] = False
    if 'array' in (schema.get('type') if isinstance(schema.get('type'), list) else [schema.get('type')]) and 'items' in schema:
        schema['items'] = _strictify_for_schema(schema['items'])
    return schema


def codex_output_schema() -> dict[str, Any]:
    return _strictify_for_schema(SUBMIT_TOOL['function']['parameters'])


def openrouter_submit_tool() -> dict[str, Any]:
    tool = json.loads(json.dumps(SUBMIT_TOOL))
    tool['function']['parameters'] = codex_output_schema()
    return tool


def _call_openai_compatible(*, api_key: str, base_url: str | None, extra_headers: dict[str, str] | None, tools: list[dict[str, Any]], system: str, user: str, model: str, temperature: float) -> tuple[dict[str, Any], str, str]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError('openai package not installed. Run: pip install -r tools/requirements.txt') from exc
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        temperature=temperature,
        max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS,
        parallel_tool_calls=False,
        tool_choice={'type': 'function', 'function': {'name': TOOL_NAME}},
        tools=tools,
        extra_headers=extra_headers,
    )
    message = response.choices[0].message
    tool_calls = message.tool_calls or []
    if len(tool_calls) != 1:
        raise RuntimeError(f'Model must return exactly one tool call; got {len(tool_calls)}')
    tool_call = tool_calls[0]
    if tool_call.type != 'function' or tool_call.function.name != TOOL_NAME:
        raise RuntimeError(f'Model called unexpected tool: {tool_call.function.name!r}')
    raw_arguments = tool_call.function.arguments or '{}'
    parsed_arguments = json.loads(raw_arguments)
    return prune_nulls(parsed_arguments), response.model, raw_arguments


def call_openai(*, system: str, user: str, model: str, temperature: float) -> tuple[dict[str, Any], str, str]:
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY not set')
    return _call_openai_compatible(api_key=api_key, base_url=None, extra_headers=None, tools=[SUBMIT_TOOL], system=system, user=user, model=model, temperature=temperature)


def call_openrouter(*, system: str, user: str, model: str, temperature: float) -> tuple[dict[str, Any], str, str]:
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENROUTER_API_KEY not set')
    return _call_openai_compatible(api_key=api_key, base_url=OPENROUTER_BASE_URL, extra_headers={'HTTP-Referer': 'https://cartha.com', 'X-Title': 'Cartha Open Bible Translation'}, tools=[openrouter_submit_tool()], system=system, user=user, model=model, temperature=temperature)


def call_azure_openai(*, system: str, user: str, model: str, temperature: float) -> tuple[dict[str, Any], str, str]:
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '').rstrip('/')
    api_key = os.environ.get('AZURE_OPENAI_API_KEY', '')
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT_ID', DEFAULT_AZURE_DEPLOYMENT_ID)
    api_version = os.environ.get('AZURE_OPENAI_API_VERSION', DEFAULT_AZURE_API_VERSION)
    if not endpoint:
        raise RuntimeError('AZURE_OPENAI_ENDPOINT not set')
    if not api_key:
        raise RuntimeError('AZURE_OPENAI_API_KEY not set')
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'temperature': temperature,
        'max_completion_tokens': DEFAULT_MAX_COMPLETION_TOKENS,
        'parallel_tool_calls': False,
        'tool_choice': {'type': 'function', 'function': {'name': TOOL_NAME}},
        'tools': [openrouter_submit_tool()],
    }
    request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'api-key': api_key, 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=180) as response:
        parsed_response = json.loads(response.read().decode('utf-8'))
    choices = parsed_response.get('choices') or []
    message = choices[0].get('message') or {}
    tool_call = (message.get('tool_calls') or [None])[0]
    function = (tool_call or {}).get('function') or {}
    raw_arguments = function.get('arguments') or '{}'
    return prune_nulls(json.loads(raw_arguments)), str(parsed_response.get('model') or model), raw_arguments


def call_codex_cli(*, system: str, user: str, model: str) -> tuple[dict[str, Any], str, str]:
    if not codex_login_available():
        raise RuntimeError('codex-cli backend requested but Codex is not logged in. Run `codex login` first.')
    schema = codex_output_schema()
    with tempfile.TemporaryDirectory(prefix='cartha-hermas-codex-') as temp_dir_name:
        temp_dir = pathlib.Path(temp_dir_name)
        schema_path = temp_dir / 'schema.json'
        instructions_path = temp_dir / 'system.txt'
        output_path = temp_dir / 'output.json'
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')
        instructions_path.write_text(system, encoding='utf-8')
        proc = subprocess.run([
            'codex','exec','-m',model,'--ephemeral','--sandbox','read-only','--output-schema',str(schema_path),'-o',str(output_path),'-c',f'model_instructions_file="{instructions_path}"','-c',f'model_reasoning_effort="{DEFAULT_CODEX_REASONING_EFFORT}"','--color','never','-'
        ], cwd=REPO_ROOT, input=user, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip() or 'unknown codex exec failure'
            raise RuntimeError(f'codex exec failed: {detail}')
        if not output_path.exists():
            raise RuntimeError('codex exec completed but did not produce an output file')
        raw_arguments = output_path.read_text(encoding='utf-8')
        return prune_nulls(json.loads(raw_arguments)), model, raw_arguments


def call_model(*, backend: str, system: str, user: str, model: str, temperature: float) -> tuple[dict[str, Any], str, str, float | None]:
    if backend == BACKEND_OPENAI:
        tool_input, model_version, raw = call_openai(system=system, user=user, model=model, temperature=temperature)
        return tool_input, model_version, raw, temperature
    if backend == BACKEND_OPENROUTER:
        tool_input, model_version, raw = call_openrouter(system=system, user=user, model=model, temperature=temperature)
        return tool_input, model_version, raw, temperature
    if backend == BACKEND_AZURE:
        tool_input, model_version, raw = call_azure_openai(system=system, user=user, model=model, temperature=temperature)
        return tool_input, model_version, raw, temperature
    if backend == BACKEND_CODEX:
        tool_input, model_version, raw = call_codex_cli(system=system, user=user, model=model)
        return tool_input, model_version, raw, None
    raise RuntimeError(f'Unknown backend: {backend}')


def build_record(unit: hermas.NormalizedUnit, bundle: hermas_prompt.PromptBundle, tool_input: dict[str, Any], *, model_id: str, model_version: str, prompt_id: str, prompt_sha256: str, temperature: float | None, output_hash: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        'id': f'HERM.{unit.unit_id}',
        'reference': f'Shepherd of Hermas — {unit.label}',
        'unit': 'section',
        'book': 'Shepherd of Hermas',
        'source': {
            'edition': bundle.source_payload['edition'],
            'text': bundle.source_payload['text'],
            'language': bundle.source_payload['language'],
            'pages': bundle.source_payload['source_pages'],
            'unit_id': bundle.source_payload['unit_id'],
            'label': bundle.source_payload['label'],
            'sequence': bundle.source_payload['sequence'],
        },
        'translation': {
            'text': str(tool_input['english_text']).strip(),
            'philosophy': tool_input['translation_philosophy'],
        },
        'lexical_decisions': tool_input.get('lexical_decisions', []),
        'ai_draft': {
            'model_id': model_id,
            'model_version': model_version,
            'prompt_id': prompt_id,
            'prompt_sha256': prompt_sha256,
            'timestamp': utc_timestamp(),
            'output_hash': output_hash,
            'zone1_sources_at_draft': bundle.zone1_sources_at_draft,
            'zone2_consults_known': bundle.zone2_consults_known,
        },
        'status': 'draft',
    }
    if bundle.source_warnings:
        record['source']['warnings'] = bundle.source_warnings
    footnotes = tool_input.get('footnotes')
    if footnotes:
        record['translation']['footnotes'] = footnotes
    theological_decisions = tool_input.get('theological_decisions')
    if theological_decisions:
        record['theological_decisions'] = theological_decisions
    if temperature is not None:
        record['ai_draft']['temperature'] = temperature
    return prune_nulls(record)


def write_unit_yaml(record: dict[str, Any], unit: hermas.NormalizedUnit) -> pathlib.Path:
    out_path = output_path_for_unit(unit)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False), encoding='utf-8')
    return out_path


def draft_unit(unit: hermas.NormalizedUnit, *, backend: str = DEFAULT_BACKEND, model: str = DEFAULT_MODEL_ID, temperature: float = DEFAULT_TEMPERATURE, prompt_id: str = DEFAULT_PROMPT_ID, dry_run: bool = False, overwrite: bool = False) -> DraftResult:
    output_path = output_path_for_unit(unit)
    if output_path.exists() and not overwrite and not dry_run:
        raise FileExistsError(f'{output_path} already exists (pass --overwrite to replace)')
    bundle = hermas_prompt.build_shepherd_of_hermas_prompt(unit_id=unit.unit_id)
    prompt_sha256 = sha256_hex(bundle.prompt)
    if dry_run:
        print(bundle.prompt)
        return DraftResult(unit=unit, record={}, output_path=output_path, prompt_sha256=prompt_sha256, model_version=model)
    tool_input, model_version, raw_arguments, applied_temperature = call_model(backend=backend, system=SYSTEM_PROMPT, user=bundle.prompt, model=model, temperature=temperature)
    validate_tool_input(tool_input)
    output_hash = sha256_hex(canonical_json(tool_input))
    record = build_record(unit, bundle, tool_input, model_id=model, model_version=model_version, prompt_id=prompt_id, prompt_sha256=prompt_sha256, temperature=applied_temperature, output_hash=output_hash)
    output_path = write_unit_yaml(record, unit)
    return DraftResult(unit=unit, record=record, output_path=output_path, prompt_sha256=prompt_sha256, model_version=model_version)


def parse_int_spec(spec: str) -> list[int]:
    values: set[int] = set()
    for part in spec.split(','):
        token = part.strip()
        if not token:
            continue
        if '-' in token:
            start_text, end_text = token.split('-', 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f'descending range not allowed: {token}')
            values.update(range(start, end + 1))
        else:
            values.add(int(token))
    return sorted(values)


def iter_units(args: argparse.Namespace) -> list[hermas.NormalizedUnit]:
    summary = hermas.load_unit_map()
    all_units = [hermas.load_normalized_unit(sequence=i) for i in range(1, len(summary.get('units', [])) + 1)]
    resolved = [u for u in all_units if u is not None]
    if args.unit_id:
        unit = hermas.load_normalized_unit(args.unit_id)
        return [unit] if unit else []
    if args.sequence is not None:
        unit = hermas.load_normalized_unit(sequence=args.sequence)
        return [unit] if unit else []
    if args.sequences:
        wanted = set(parse_int_spec(args.sequences))
        return [u for u in resolved if u.sequence in wanted]
    if args.all_units:
        return resolved
    raise ValueError('Provide --unit-id, --sequence, --sequences, or --all-units')


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--unit-id', help='Hermas unit id such as V.3.i, M.4.ii, S.8.ii')
    ap.add_argument('--sequence', type=int, help='1-based Hermas unit sequence')
    ap.add_argument('--sequences', help='Comma/range sequence list, e.g. 1-5,8,12')
    ap.add_argument('--all-units', action='store_true')
    ap.add_argument('--backend', default=DEFAULT_BACKEND, choices=[BACKEND_CODEX, BACKEND_OPENAI, BACKEND_OPENROUTER, BACKEND_AZURE])
    ap.add_argument('--model', default=DEFAULT_MODEL_ID)
    ap.add_argument('--temperature', type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument('--prompt-id', default=DEFAULT_PROMPT_ID)
    ap.add_argument('--skip-existing', action='store_true')
    ap.add_argument('--overwrite', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    units = iter_units(args)
    if not units:
        raise SystemExit('No Hermas units matched the requested selection.')

    drafted = 0
    skipped = 0
    for unit in units:
        out = output_path_for_unit(unit)
        if args.skip_existing and out.exists() and not args.overwrite and not args.dry_run:
            skipped += 1
            print(f'skip {unit.sequence:03d} {unit.unit_id} ({out.relative_to(REPO_ROOT)})')
            continue
        result = draft_unit(unit, backend=args.backend, model=args.model, temperature=args.temperature, prompt_id=args.prompt_id, dry_run=args.dry_run, overwrite=args.overwrite)
        if not args.dry_run:
            drafted += 1
            print(f'wrote {result.output_path.relative_to(REPO_ROOT)}  <- {unit.unit_id}')
    print(f'done: {drafted} drafted, {skipped} skipped, {len(units)} selected')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
