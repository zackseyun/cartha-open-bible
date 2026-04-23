#!/usr/bin/env python3
"""draft.py — draft one or more 2 Baruch chapters into YAML.

This is the first actual drafting runner for 2 Baruch. It consumes:
- `tools/2baruch/build_translation_prompt.py`
- `tools/2baruch/multi_witness.py`

and writes chapter YAMLs under:

    translation/extra_canonical/2_baruch/001.yaml
"""
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
from typing import Any

from dotenv import load_dotenv
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSLATION_ROOT = REPO_ROOT / 'translation' / 'extra_canonical' / '2_baruch'
TOOLS_ROOT = REPO_ROOT / 'tools'

sys.path.insert(0, str(TOOLS_ROOT))
import draft as canonical_draft  # noqa: E402

import importlib.util as _importlib_util  # noqa: E402
_BARUCH_TOOLS_DIR = pathlib.Path(__file__).parent

def _load_local_module(name: str, filename: str):
    spec = _importlib_util.spec_from_file_location(name, _BARUCH_TOOLS_DIR / filename)
    module = _importlib_util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

baruch_prompt = _load_local_module('baruch_build_translation_prompt', 'build_translation_prompt.py')
baruch_witness = _load_local_module('baruch_multi_witness', 'multi_witness.py')

DEFAULT_MODEL_ID = os.environ.get('CARTHA_MODEL_ID', 'gpt-5.4')
DEFAULT_TEMPERATURE = float(os.environ.get('CARTHA_TEMPERATURE', '0.2'))
DEFAULT_MAX_COMPLETION_TOKENS = int(os.environ.get('CARTHA_MAX_COMPLETION_TOKENS', '14000'))
DEFAULT_CODEX_REASONING_EFFORT = os.environ.get('CARTHA_CODEX_REASONING_EFFORT', 'medium')
DEFAULT_OPENROUTER_MODEL_ID = os.environ.get('CARTHA_OPENROUTER_MODEL', 'openai/gpt-5.4')
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get('AZURE_OPENAI_DEPLOYMENT_ID', 'gpt-5-4-deployment')
DEFAULT_AZURE_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
DEFAULT_PROMPT_ID = os.environ.get('CARTHA_PROMPT_ID', '2baruch_chapter_draft_v1')

BACKEND_OPENAI = 'openai-sdk'
BACKEND_OPENROUTER = 'openrouter-sdk'
BACKEND_AZURE = 'azure-openai'
BACKEND_CODEX = 'codex-cli'
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'

TOOL_NAME = 'submit_2baruch_chapter_draft'
TOOL_REASON_VALUES = {
    'alternative_reading',
    'lexical_alternative',
    'textual_variant',
    'cultural_note',
    'cross_reference',
}

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE CHAPTER OF 2 BARUCH (the Syriac Apocalypse of Baruch). Your job is to produce the highest-quality English rendering you can while exposing the major lexical and theological decisions so the result remains fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the supplied project excerpts.

You will submit your draft by calling the `submit_2baruch_chapter_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the chapter plainly demands one or the other.

Never:
- Paraphrase beyond what the Syriac primary witness warrants.
- Flatten apocalyptic imagery, lament, or judgment rhetoric into generic modern prose.
- Import 4 Ezra wording or familiar biblical phrasing just because the themes overlap.
- Pretend a medium-confidence chapter edge is certain when the prompt warns otherwise.
- Omit major lexical or theological decisions from the structured output just to make the prose read cleaner.
- Copy from copyrighted modern 2 Baruch translations.
- Fabricate lexicon entry numbers. If you do not know the exact lexicon entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    'type': 'function',
    'function': {
        'name': TOOL_NAME,
        'description': 'Submit a draft English translation for one 2 Baruch chapter, including major lexical and theological decisions.',
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
    chapter: int
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


def output_path_for_chapter(chapter: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f'{chapter:03d}.yaml'


def existing_translation_text(chapter: int) -> str:
    path = output_path_for_chapter(chapter)
    if not path.exists():
        return ''
    try:
        payload = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except Exception:
        return ''
    return str(((payload.get('translation') or {}).get('text')) or '').strip()


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
    return _call_openai_compatible(api_key=api_key, base_url=OPENROUTER_BASE_URL, extra_headers={'HTTP-Referer': 'https://cartha.com', 'X-Title': 'Cartha Open Bible'}, tools=[openrouter_submit_tool()], system=system, user=user, model=model, temperature=temperature)


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
    payload: dict[str, Any] = {
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
        'max_completion_tokens': DEFAULT_MAX_COMPLETION_TOKENS,
        'parallel_tool_calls': False,
        'tool_choice': {'type': 'function', 'function': {'name': TOOL_NAME}},
        'tools': [openrouter_submit_tool()],
    }
    # GPT-5 family only accepts temperature=1 (the default); omit for non-default values.
    if not model.startswith('gpt-5'):
        payload['temperature'] = temperature
    request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'api-key': api_key, 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=240) as response:
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
    with tempfile.TemporaryDirectory(prefix='cartha-2baruch-codex-') as temp_dir_name:
        temp_dir = pathlib.Path(temp_dir_name)
        schema_path = temp_dir / 'schema.json'
        instructions_path = temp_dir / 'system.txt'
        output_path = temp_dir / 'output.json'
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')
        instructions_path.write_text(system, encoding='utf-8')
        proc = subprocess.run([
            'codex', 'exec', '-m', model, '--ephemeral', '--sandbox', 'read-only', '--output-schema', str(schema_path), '-o', str(output_path), '-c', f'model_instructions_file="{instructions_path}"', '-c', f'model_reasoning_effort="{DEFAULT_CODEX_REASONING_EFFORT}"', '--color', 'never', '-'
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


def current_source_payload(chapter: int) -> dict[str, Any]:
    bundle = baruch_witness.chapter_bundle(chapter)
    primary = bundle['primary']
    source = {
        'edition': 'Ceriani 1871 primary Syriac (control-backed chapter corpus)',
        'language': 'Syriac',
        'chapter': chapter,
        'pages': primary['source_pdf_pages'],
        'text': primary['text'],
        'note': 'Chapter-ready source bucket built from the cleaned Ceriani corpus and tightened with targeted Kmosko control pages. Some edge pages may still carry medium-confidence boundary judgments.',
        'chapter_bucket_method': primary.get('method'),
        'overlap_expected': primary.get('overlap_expected'),
    }
    return prune_nulls(source)


def build_record(chapter: int, tool_input: dict[str, Any], *, model_id: str, model_version: str, prompt_id: str, prompt_sha256: str, temperature: float | None, output_hash: str) -> dict[str, Any]:
    bundle = baruch_witness.chapter_bundle(chapter)
    record: dict[str, Any] = {
        'id': f'2BA.{chapter:03d}',
        'reference': f'2 Baruch {chapter}',
        'unit': 'chapter',
        'book': '2 Baruch',
        'source': current_source_payload(chapter),
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
            'temperature': temperature,
            'primary_pages': bundle['primary']['source_pdf_pages'],
            'kmosko_control_pages': [block['page'] for block in bundle['secondary']['kmosko1907'] if block.get('usable')],
        },
        'status': 'draft',
    }
    footnotes = tool_input.get('footnotes')
    if footnotes:
        record['translation']['footnotes'] = footnotes
    theological_decisions = tool_input.get('theological_decisions')
    if theological_decisions:
        record['theological_decisions'] = theological_decisions
    if temperature is None:
        record['ai_draft'].pop('temperature', None)
    return prune_nulls(record)


def write_yaml(record: dict[str, Any], chapter: int) -> pathlib.Path:
    out_path = output_path_for_chapter(chapter)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False), encoding='utf-8')
    return out_path


def parse_chapter_spec(spec: str) -> list[int]:
    out: set[int] = set()
    for part in spec.split(','):
        token = part.strip()
        if not token:
            continue
        if '-' in token:
            a, b = token.split('-', 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(token))
    return sorted(ch for ch in out if 1 <= ch <= 87)


def draft_chapter(chapter: int, *, backend: str, model: str, temperature: float, prompt_id: str, force: bool) -> DraftResult:
    if existing_translation_text(chapter) and not force:
        raise RuntimeError(f'2 Baruch chapter {chapter} already has translation text; pass --force to overwrite')
    base_prompt = baruch_prompt.build_prompt(chapter)
    prompts = [
        base_prompt,
        base_prompt + "\n\nIMPORTANT REPAIR INSTRUCTION: Your previous output failed validation. You MUST include a non-empty `lexical_decisions` array with concrete source words, chosen renderings, and rationales. Return the function call only.\n",
        base_prompt + "\n\nSTRICT REQUIREMENT: Do not omit `lexical_decisions`. If the chapter is difficult, choose the 5-8 most important lexical decisions and supply them explicitly. Return the function call only.\n",
    ]

    last_error: Exception | None = None
    for prompt in prompts:
        prompt_sha = sha256_hex(SYSTEM_PROMPT + '\n\n---\n\n' + prompt)
        tool_input, model_version, raw_arguments, actual_temp = call_model(backend=backend, system=SYSTEM_PROMPT, user=prompt, model=model, temperature=temperature)
        try:
            validate_tool_input(tool_input)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        output_hash = sha256_hex(canonical_json(tool_input))
        record = build_record(chapter, tool_input, model_id=model, model_version=model_version, prompt_id=prompt_id, prompt_sha256=prompt_sha, temperature=actual_temp, output_hash=output_hash)
        output_path = write_yaml(record, chapter)
        return DraftResult(chapter=chapter, record=record, output_path=output_path, prompt_sha256=prompt_sha, model_version=model_version)

    raise RuntimeError(f'2 Baruch chapter {chapter} failed validation after retries: {last_error}')


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chapter', type=int)
    ap.add_argument('--chapters', help='Comma/range chapter spec, e.g. 2,3,5-7')
    ap.add_argument('--backend', default=DEFAULT_BACKEND, choices=[BACKEND_OPENAI, BACKEND_OPENROUTER, BACKEND_AZURE, BACKEND_CODEX])
    ap.add_argument('--model', default=DEFAULT_MODEL_ID)
    ap.add_argument('--temperature', type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument('--prompt-id', default=DEFAULT_PROMPT_ID)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true', help='Print the assembled prompt and exit')
    args = ap.parse_args()

    if args.chapter is not None:
        chapters = [args.chapter]
    elif args.chapters:
        chapters = parse_chapter_spec(args.chapters)
    else:
        ap.error('Provide --chapter or --chapters')
    if not chapters:
        raise SystemExit('No chapters resolved')

    if args.dry_run:
        for chapter in chapters:
            print('=' * 72)
            print(f'CHAPTER {chapter}')
            print('=' * 72)
            print(baruch_prompt.build_prompt(chapter))
        return 0

    results: list[DraftResult] = []
    for chapter in chapters:
        result = draft_chapter(chapter, backend=args.backend, model=args.model, temperature=args.temperature, prompt_id=args.prompt_id, force=args.force)
        results.append(result)
        print(f'wrote {result.output_path.relative_to(REPO_ROOT)}')
    print(f'drafted {len(results)} chapter(s): {", ".join(str(r.chapter) for r in results)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
