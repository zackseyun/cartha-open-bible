#!/usr/bin/env python3
"""draft_truth.py — produce an AI draft for one Gospel of Truth section."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_truth_section_prompt as bp  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSLATION_ROOT = REPO_ROOT / 'translation' / 'extra_canonical' / 'gospel_of_truth'
DEFAULT_MODEL_ID = os.environ.get('CARTHA_MODEL_ID', 'gpt-5.4')
DEFAULT_TEMPERATURE = float(os.environ.get('CARTHA_TEMPERATURE', '1.0'))
DEFAULT_MAX_COMPLETION_TOKENS = int(os.environ.get('CARTHA_MAX_COMPLETION_TOKENS', '20000'))
DEFAULT_REQUEST_TIMEOUT_SECONDS = int(os.environ.get('CARTHA_REQUEST_TIMEOUT_SECONDS', '300'))
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get('AZURE_OPENAI_DEPLOYMENT_ID', 'gpt-5-4-deployment')
DEFAULT_AZURE_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2025-04-01-preview')
TOOL_NAME = 'submit_truth_section_draft'
FOOTNOTE_REASONS = {'alternative_reading','lexical_alternative','textual_variant','cultural_note','cross_reference','damage_repair','technical_term'}
SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE SECTION of the Gospel of Truth directly from the Coptic primary facsimile OCR. When a Codex XII overlap fragment is present, use it as a repair/check witness and record meaningful repair decisions explicitly.

You MUST follow the doctrinal stance and translation philosophy in the DOCTRINE.md and PHILOSOPHY.md excerpts provided. You will submit your draft by calling the `submit_truth_section_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence with explicit protection for theological/technical vocabulary.

Never:
- Paraphrase from a modern English translation.
- Flatten reified theological terms just to sound smoother.
- Silently repair a damaged place from the overlap witness without saying so.
- Invent lexicon entry numbers.
- Turn difficult contemplative prose into generic devotional English."""
SUBMIT_TOOL = {
    'type': 'function',
    'function': {
        'name': TOOL_NAME,
        'description': 'Submit a draft English translation for one Gospel of Truth section, including technical vocabulary and repair decisions.',
        'parameters': {
            'type': 'object',
            'required': ['english_text','translation_philosophy','lexical_decisions','technical_vocabulary_note','textual_note'],
            'properties': {
                'english_text': {'type': 'string'},
                'translation_philosophy': {'type': 'string','enum': ['formal','dynamic','optimal-equivalence']},
                'lexical_decisions': {'type': 'array','items': {'type': 'object','required': ['source_word','chosen','rationale'],'properties': {'source_word': {'type':'string'},'chosen': {'type':'string'},'alternatives': {'type':'array','items': {'type':'string'}},'lexicon': {'type':'string'},'rationale': {'type':'string'}},'additionalProperties': False}},
                'technical_vocabulary_note': {'type': 'string'},
                'textual_note': {'type': 'string'},
                'overlap_repair_note': {'type': 'string'},
                'theological_decisions': {'type': 'array','items': {'type':'object','required':['issue','chosen_reading','rationale'],'properties': {'issue': {'type':'string'},'chosen_reading': {'type':'string'},'alternative_readings': {'type':'array','items': {'type':'string'}},'rationale': {'type':'string'}},'additionalProperties': False}},
                'footnotes': {'type': 'array','items': {'type':'object','required':['marker','text','reason'],'properties': {'marker': {'type':'string'},'text': {'type':'string'},'reason': {'type':'string','enum': sorted(FOOTNOTE_REASONS)}},'additionalProperties': False}},
                'revision_risk_note': {'type': 'string'},
            },
            'additionalProperties': False,
        },
    },
}

@dataclass
class DraftResult:
    section_id: str
    record: dict[str, Any]
    output_path: pathlib.Path
    prompt_sha256: str
    model_version: str


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def azure_endpoint() -> str:
    return os.environ.get('AZURE_OPENAI_ENDPOINT', '').rstrip('/')


def _message_text_content(message: dict[str, Any]) -> str:
    content = message.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(str(item.get('text','')) for item in content if isinstance(item, dict) and item.get('type') == 'text')
    return ''


def _try_parse_json_content(raw: str) -> dict[str, Any] | None:
    text = (raw or '').strip()
    if not text:
        return None
    candidates = [text]
    if text.startswith('```') and text.endswith('```'):
        inner = text.split('\n', 1)
        if len(inner) == 2:
            candidates.append(inner[1].rsplit('```', 1)[0].strip())
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_tool_payload(body: dict[str, Any], model: str) -> tuple[dict[str, Any], str]:
    choices = body.get('choices') or []
    if len(choices) != 1:
        raise RuntimeError(f'Azure OpenAI must return exactly one choice; got {len(choices)}')
    message = choices[0].get('message') or {}
    tool_calls = message.get('tool_calls') or []
    if len(tool_calls) == 1:
        tool_call = tool_calls[0]
        function = tool_call.get('function') or {}
        if tool_call.get('type') != 'function' or function.get('name') != TOOL_NAME:
            raise RuntimeError(f"Azure OpenAI called unexpected tool: {function.get('name')!r}")
        raw_arguments = function.get('arguments') or '{}'
        return json.loads(raw_arguments), str(body.get('model') or model)
    parsed = _try_parse_json_content(_message_text_content(message))
    if parsed is not None:
        return parsed, str(body.get('model') or model)
    raise RuntimeError(f"Azure OpenAI must return exactly one tool call; got {len(tool_calls)}")


def call_azure_openai(*, system: str, user: str, model: str, temperature: float, max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS, request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS, retries: int = 2) -> tuple[dict[str, Any], str]:
    endpoint = azure_endpoint(); api_key = os.environ.get('AZURE_OPENAI_API_KEY', ''); deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT_ID', DEFAULT_AZURE_DEPLOYMENT_ID); api_version = os.environ.get('AZURE_OPENAI_API_VERSION', DEFAULT_AZURE_API_VERSION)
    if not endpoint:
        raise RuntimeError('AZURE_OPENAI_ENDPOINT not set')
    if not api_key:
        raise RuntimeError('AZURE_OPENAI_API_KEY not set')
    url = f'{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}'
    payload = {'messages': [{'role':'system','content':system},{'role':'user','content':user}], 'temperature': temperature, 'max_completion_tokens': max_completion_tokens, 'parallel_tool_calls': False, 'tool_choice': {'type':'function','function': {'name': TOOL_NAME}}, 'tools': [SUBMIT_TOOL]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'api-key': api_key, 'Content-Type':'application/json'}, method='POST')
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=request_timeout_seconds) as response:
                body = json.loads(response.read().decode('utf-8'))
            return _extract_tool_payload(body, model)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            last_error = RuntimeError(f'Azure OpenAI HTTP {exc.code}: {detail}')
            if attempt < retries and exc.code in {408,409,429,500,502,503,504}:
                time.sleep(2 * (attempt + 1)); continue
            raise last_error from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = RuntimeError(f'Azure OpenAI request failed: {exc}')
            if attempt < retries:
                time.sleep(2 * (attempt + 1)); continue
            raise last_error from exc
        except RuntimeError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1)); continue
            raise
    assert last_error is not None
    raise last_error


def validate_tool_input(tool_input: dict[str, Any], *, has_overlap: bool) -> None:
    errors=[]
    if not str(tool_input.get('english_text','') or '').strip():
        errors.append('english_text must be non-empty')
    if str(tool_input.get('translation_philosophy','') or '') not in {'formal','dynamic','optimal-equivalence'}:
        errors.append('translation_philosophy invalid')
    if not isinstance(tool_input.get('lexical_decisions'), list) or not tool_input.get('lexical_decisions'):
        errors.append('lexical_decisions must be non-empty array')
    if not str(tool_input.get('technical_vocabulary_note','') or '').strip():
        errors.append('technical_vocabulary_note must be non-empty')
    if not str(tool_input.get('textual_note','') or '').strip():
        errors.append('textual_note must be non-empty')
    if has_overlap and not str(tool_input.get('overlap_repair_note','') or '').strip():
        errors.append('overlap_repair_note required when overlap fragments exist')
    if errors:
        raise ValueError('; '.join(errors))


def output_path_for_section(section_id: str) -> pathlib.Path:
    return TRANSLATION_ROOT / f'{section_id}.yaml'


def build_record(bundle: bp.PromptBundle, tool_input: dict[str, Any], *, model_id: str, model_version: str, prompt_id: str, prompt_sha256: str, temperature: float, output_hash: str) -> dict[str, Any]:
    return {
        'id': f'TRUTH.{bundle.section_id}',
        'reference': f'Gospel of Truth — {bundle.section_label}',
        'unit': 'section',
        'book': 'Gospel of Truth',
        'source': bundle.source_payload,
        'translation': {'text': str(tool_input['english_text']).strip(), 'philosophy': tool_input['translation_philosophy']},
        'lexical_decisions': tool_input.get('lexical_decisions', []),
        'technical_vocabulary_note': tool_input.get('technical_vocabulary_note', ''),
        'textual_note': tool_input.get('textual_note', ''),
        'ai_draft': {
            'model_id': model_id,
            'model_version': model_version,
            'prompt_id': prompt_id,
            'prompt_sha256': prompt_sha256,
            'temperature': temperature,
            'timestamp': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
            'output_hash': output_hash,
            'zone1_sources_at_draft': bundle.zone1_sources_at_draft,
            'zone2_consults_known': bundle.zone2_consults_known,
        },
        **({k: tool_input[k] for k in ('overlap_repair_note','theological_decisions','revision_risk_note') if k in tool_input})
    }


def write_yaml(record: dict[str, Any], section_id: str) -> pathlib.Path:
    out = output_path_for_section(section_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False), encoding='utf-8')
    return out


def draft_section(section_id: str, *, model: str = DEFAULT_MODEL_ID, temperature: float = DEFAULT_TEMPERATURE, max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS, request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS, prompt_id: str = 'truth_section_draft_v1', write: bool = True) -> DraftResult:
    bundle = bp.build_truth_section_prompt(section_id)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + '\n\n---\n\n' + bundle.prompt)
    tool_input, model_version = call_azure_openai(system=SYSTEM_PROMPT, user=bundle.prompt, model=model, temperature=temperature, max_completion_tokens=max_completion_tokens, request_timeout_seconds=request_timeout_seconds)
    validate_tool_input(tool_input, has_overlap=bundle.has_overlap_fragments)
    output_hash = sha256_hex(canonical_json(tool_input))
    record = build_record(bundle, tool_input, model_id=model, model_version=model_version, prompt_id=prompt_id, prompt_sha256=prompt_sha, temperature=temperature, output_hash=output_hash)
    out = output_path_for_section(section_id)
    if write:
        out = write_yaml(record, section_id)
    return DraftResult(section_id, record, out, prompt_sha, model_version)


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--section', required=True)
    ap.add_argument('--model', default=DEFAULT_MODEL_ID)
    ap.add_argument('--temperature', type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument('--max-completion-tokens', type=int, default=DEFAULT_MAX_COMPLETION_TOKENS)
    ap.add_argument('--request-timeout-seconds', type=int, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    bundle = bp.build_truth_section_prompt(args.section)
    if args.dry_run:
        print(bundle.prompt); return 0
    if not os.environ.get('AZURE_OPENAI_ENDPOINT') or not os.environ.get('AZURE_OPENAI_API_KEY'):
        print('ERROR: Azure env not set.', file=sys.stderr); return 2
    try:
        result = draft_section(args.section, model=args.model, temperature=args.temperature, max_completion_tokens=args.max_completion_tokens, request_timeout_seconds=args.request_timeout_seconds)
    except Exception as exc:
        print(f'ERROR: draft failed: {exc}', file=sys.stderr); return 4
    print(f'Wrote {result.output_path.relative_to(REPO_ROOT)}')
    print(f'model_version={result.model_version}')
    print(f'prompt_sha256={result.prompt_sha256}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
