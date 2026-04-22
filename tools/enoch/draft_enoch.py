#!/usr/bin/env python3
"""draft_enoch.py — draft one or more 1 Enoch verses into YAML.

This is the practical bridge from the OCR/prompt-builder layer to the
actual Cartha drafting pipeline for 1 Enoch.

It consumes `tools/enoch/build_translation_prompt.py`, asks an AI model
for a structured verse draft via a strict function-call / schema flow,
and writes verse YAMLs to:

    translation/extra_canonical/1_enoch/<chapter>/<verse>.yaml

Supported backends:
  - codex-cli (default when logged in)
  - openai-sdk
  - openrouter-sdk
  - azure-openai

Examples:
  python3 tools/enoch/draft_enoch.py --chapter 1 --verse 1
  python3 tools/enoch/draft_enoch.py --chapters 1 --all-verses
  python3 tools/enoch/draft_enoch.py --chapters 1-3 --all-verses --skip-existing
  python3 tools/enoch/draft_enoch.py --chapter 1 --verse 1 --dry-run
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
from typing import Any, Iterable

from dotenv import load_dotenv
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "1_enoch"
TOOLS_ROOT = REPO_ROOT / "tools"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_translation_prompt as enoch_prompt  # noqa: E402
import verse_parser  # noqa: E402

sys.path.insert(0, str(TOOLS_ROOT))
import draft as canonical_draft  # noqa: E402

DEFAULT_MODEL_ID = os.environ.get("CARTHA_MODEL_ID", "gpt-5.4")
DEFAULT_TEMPERATURE = float(os.environ.get("CARTHA_TEMPERATURE", "0.2"))
DEFAULT_MAX_COMPLETION_TOKENS = int(
    os.environ.get("CARTHA_MAX_COMPLETION_TOKENS", "4096")
)
DEFAULT_CODEX_REASONING_EFFORT = os.environ.get(
    "CARTHA_CODEX_REASONING_EFFORT",
    "medium",
)
DEFAULT_OPENROUTER_MODEL_ID = os.environ.get(
    "CARTHA_OPENROUTER_MODEL",
    "openai/gpt-5.4",
)
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get(
    "AZURE_OPENAI_DEPLOYMENT_ID",
    "gpt-5-4-deployment",
)
DEFAULT_AZURE_API_VERSION = os.environ.get(
    "AZURE_OPENAI_API_VERSION",
    "2025-04-01-preview",
)
DEFAULT_PROMPT_ID = os.environ.get("CARTHA_PROMPT_ID", "enoch_verse_draft_v1")

BACKEND_OPENAI = "openai-sdk"
BACKEND_OPENROUTER = "openrouter-sdk"
BACKEND_AZURE = "azure-openai"
BACKEND_CODEX = "codex-cli"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

TOOL_NAME = "submit_enoch_verse_draft"
TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
}

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE VERSE OF 1 ENOCH. Your job is to produce the highest-quality verse draft you can from the witness payload provided, while exposing the major lexical and theological decisions so the result stays fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the supplied project excerpts.

You will submit your draft by calling the `submit_enoch_verse_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the verse plainly demands one or the other.

Never:
- Paraphrase beyond what the Ge'ez witness warrants.
- Smooth away apocalyptic imagery, angelic speech, or judgment formulas into generic modern prose.
- Import New Testament wording just because later Christian texts echo the verse.
- Omit major lexical or theological decisions from the structured output just to make the verse read cleaner.
- Copy wording from copyrighted modern Enoch translations.
- Fabricate lexicon entry numbers. If you do not know the exact lexicon entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Submit a draft English translation for one 1 Enoch verse, including "
            "major lexical and theological decisions."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "required": [
                "english_text",
                "translation_philosophy",
                "lexical_decisions",
            ],
            "properties": {
                "english_text": {"type": "string"},
                "translation_philosophy": {
                    "type": "string",
                    "enum": ["formal", "dynamic", "optimal-equivalence"],
                },
                "lexical_decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["source_word", "chosen", "rationale"],
                        "properties": {
                            "source_word": {"type": "string"},
                            "chosen": {"type": "string"},
                            "alternatives": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "lexicon": {"type": "string"},
                            "entry": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "theological_decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["issue", "chosen_reading", "rationale"],
                        "properties": {
                            "issue": {"type": "string"},
                            "chosen_reading": {"type": "string"},
                            "alternative_readings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "rationale": {"type": "string"},
                            "doctrine_reference": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "footnotes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["marker", "text", "reason"],
                        "properties": {
                            "marker": {"type": "string"},
                            "text": {"type": "string"},
                            "reason": {
                                "type": "string",
                                "enum": sorted(TOOL_REASON_VALUES),
                            },
                        },
                        "additionalProperties": False,
                    },
                },
            },
            "additionalProperties": False,
        },
    },
}


@dataclass
class DraftResult:
    chapter: int
    verse: int
    record: dict[str, Any]
    output_path: pathlib.Path
    prompt_sha256: str
    model_version: str


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def prune_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: prune_nulls(inner)
            for key, inner in value.items()
            if inner is not None
        }
    if isinstance(value, list):
        return [prune_nulls(item) for item in value if item is not None]
    return value


def codex_login_available() -> bool:
    return canonical_draft.codex_login_available()


def default_backend() -> str:
    configured = os.environ.get("CARTHA_DRAFTER_BACKEND")
    if configured:
        return configured
    if codex_login_available():
        return BACKEND_CODEX
    return BACKEND_OPENAI


DEFAULT_BACKEND = default_backend()


def output_path_for_verse(chapter: int, verse: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{chapter:03d}" / f"{verse:03d}.yaml"


def parse_int_spec(spec: str) -> list[int]:
    values: set[int] = set()
    for part in spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"Invalid descending range: {token}")
            values.update(range(start, end + 1))
        else:
            values.add(int(token))
    return sorted(values)


def recovered_verses_for_chapter(chapter: int) -> list[int]:
    return verse_parser.recovered_verse_numbers(chapter)


def resolve_targets(
    *,
    chapters_spec: str,
    verse: int | None,
    verses_spec: str | None,
    all_verses: bool,
    limit: int | None,
) -> list[tuple[int, int]]:
    chapters = parse_int_spec(chapters_spec)
    for chapter in chapters:
        if not (1 <= chapter <= 108):
            raise ValueError(f"1 Enoch has chapters 1..108; got {chapter}")

    modes = sum(1 for flag in (verse is not None, verses_spec is not None, all_verses) if flag)
    if modes != 1:
        raise ValueError("Pick exactly one of --verse, --verses, or --all-verses")

    targets: list[tuple[int, int]] = []
    if verse is not None:
        if len(chapters) != 1:
            raise ValueError("--verse only supports a single chapter; use --verses or --all-verses for multi-chapter runs")
        targets = [(chapters[0], verse)]
    elif verses_spec is not None:
        verses = parse_int_spec(verses_spec)
        for chapter in chapters:
            targets.extend((chapter, v) for v in verses)
    else:
        for chapter in chapters:
            targets.extend((chapter, v) for v in recovered_verses_for_chapter(chapter))

    if limit is not None:
        targets = targets[:limit]
    return targets


def validate_tool_input(tool_input: dict[str, Any]) -> None:
    errors: list[str] = []
    english_text = str(tool_input.get("english_text", "") or "")
    philosophy = str(tool_input.get("translation_philosophy", "") or "")
    lexical_decisions = tool_input.get("lexical_decisions")
    theological_decisions = tool_input.get("theological_decisions")
    footnotes = tool_input.get("footnotes")

    if not english_text.strip():
        errors.append("english_text must be non-empty")
    if philosophy not in {"formal", "dynamic", "optimal-equivalence"}:
        errors.append("translation_philosophy must be formal/dynamic/optimal-equivalence")
    if not isinstance(lexical_decisions, list) or not lexical_decisions:
        errors.append("lexical_decisions must be a non-empty array")
    if theological_decisions is not None and not isinstance(theological_decisions, list):
        errors.append("theological_decisions must be an array when present")
    if footnotes is not None and not isinstance(footnotes, list):
        errors.append("footnotes must be an array when present")

    if isinstance(lexical_decisions, list):
        for index, decision in enumerate(lexical_decisions):
            if not isinstance(decision, dict):
                errors.append(f"lexical_decisions[{index}] must be an object")
                continue
            for field in ("source_word", "chosen", "rationale"):
                if not str(decision.get(field, "") or "").strip():
                    errors.append(f"lexical_decisions[{index}].{field} must be non-empty")

    if isinstance(footnotes, list):
        for index, note in enumerate(footnotes):
            if not isinstance(note, dict):
                errors.append(f"footnotes[{index}] must be an object")
                continue
            for field in ("marker", "text", "reason"):
                if not str(note.get(field, "") or "").strip():
                    errors.append(f"footnotes[{index}].{field} must be non-empty")
            if note.get("reason") not in TOOL_REASON_VALUES:
                errors.append(f"footnotes[{index}].reason must be one of {sorted(TOOL_REASON_VALUES)}")

    if errors:
        raise ValueError("; ".join(errors))


def build_record(
    bundle: enoch_prompt.EnochPromptBundle,
    tool_input: dict[str, Any],
    *,
    model_id: str,
    model_version: str,
    prompt_id: str,
    prompt_sha256: str,
    temperature: float | None,
    output_hash: str,
    backend: str,
) -> dict[str, Any]:
    source_payload = dict(bundle.source_payload)
    edition_code = str(source_payload.get("edition", "") or "")
    if edition_code == "charles_1906":
        source_payload["edition"] = "Charles 1906 Ethiopic Enoch"
        source_payload["edition_code"] = edition_code
    language = str(source_payload.get("language", "") or "")
    if language == "Geez":
        source_payload["language"] = "Geʿez"

    record: dict[str, Any] = {
        "id": f"ENO.{bundle.chapter}.{bundle.verse}",
        "reference": bundle.reference,
        "unit": "verse",
        "book": "1 Enoch",
        "section": bundle.source_payload.get("section"),
        "source": source_payload,
        "enoch_witnesses": bundle.witness_set,
        "source_warnings": bundle.source_warnings,
        "translation": {
            "text": str(tool_input["english_text"]).strip(),
            "philosophy": tool_input["translation_philosophy"],
        },
        "lexical_decisions": tool_input.get("lexical_decisions", []),
        "theological_decisions": tool_input.get("theological_decisions", []),
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_version,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha256,
            "timestamp": utc_timestamp(),
            "output_hash": output_hash,
            "backend": backend,
            "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
            "zone2_consults_known": bundle.zone2_consults_known,
        },
        "status": "draft",
    }

    footnotes = tool_input.get("footnotes")
    if footnotes:
        record["translation"]["footnotes"] = footnotes

    if temperature is not None:
        record["ai_draft"]["temperature"] = temperature

    return prune_nulls(record)


def write_yaml(record: dict[str, Any], chapter: int, verse: int) -> pathlib.Path:
    out_path = output_path_for_verse(chapter, verse)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return out_path


def _strictify_for_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema

    schema = dict(schema)
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        type_values = list(schema_type)
    elif schema_type is None:
        type_values = []
    else:
        type_values = [schema_type]

    if "object" in type_values:
        properties = {
            key: _strictify_for_schema(value)
            for key, value in schema.get("properties", {}).items()
        }
        original_required = set(schema.get("required", []))
        coerced: dict[str, Any] = {}
        for key, subschema in properties.items():
            if key not in original_required:
                subschema = dict(subschema)
                subtype = subschema.get("type")
                if isinstance(subtype, list):
                    if "null" not in subtype:
                        subschema["type"] = list(subtype) + ["null"]
                elif subtype is not None:
                    if subtype != "null":
                        subschema["type"] = [subtype, "null"]
                else:
                    subschema["type"] = ["null"]
            coerced[key] = subschema
        schema["properties"] = coerced
        schema["required"] = list(coerced.keys())
        schema["additionalProperties"] = False

    if "array" in type_values and "items" in schema:
        schema["items"] = _strictify_for_schema(schema["items"])

    return schema


def codex_output_schema() -> dict[str, Any]:
    return _strictify_for_schema(SUBMIT_TOOL["function"]["parameters"])


def openrouter_submit_tool() -> dict[str, Any]:
    tool = json.loads(json.dumps(SUBMIT_TOOL))
    tool["function"]["parameters"] = codex_output_schema()
    return tool


def _call_openai_compatible(
    *,
    api_key: str,
    base_url: str | None,
    extra_headers: dict[str, str] | None,
    tools: list[dict[str, Any]],
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
) -> tuple[dict[str, Any], str, str]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai package not installed. Run: pip install -r tools/requirements.txt"
        ) from exc

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        parallel_tool_calls=False,
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        tools=tools,
        extra_headers=extra_headers,
    )

    message = response.choices[0].message
    tool_calls = message.tool_calls or []
    if len(tool_calls) != 1:
        raise RuntimeError(f"Model must return exactly one tool call; got {len(tool_calls)}")
    tool_call = tool_calls[0]
    if tool_call.type != "function" or tool_call.function.name != TOOL_NAME:
        raise RuntimeError(f"Model called unexpected tool: {tool_call.function.name!r}")

    content = message.content
    if isinstance(content, str):
        content_text = content.strip()
    elif isinstance(content, list):
        content_text = "".join(
            part.text
            for part in content
            if getattr(part, "type", None) == "text" and getattr(part, "text", "")
        ).strip()
    else:
        content_text = ""
    if content_text:
        raise RuntimeError("Model returned assistant text in addition to the function call")

    raw_arguments = tool_call.function.arguments or "{}"
    try:
        parsed_arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Function-call arguments were not valid JSON: {exc}") from exc

    return prune_nulls(parsed_arguments), response.model, raw_arguments


def call_openai(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
) -> tuple[dict[str, Any], str, str]:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return _call_openai_compatible(
        api_key=api_key,
        base_url=None,
        extra_headers=None,
        tools=[SUBMIT_TOOL],
        system=system,
        user=user,
        model=model,
        temperature=temperature,
    )


def call_openrouter(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
) -> tuple[dict[str, Any], str, str]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return _call_openai_compatible(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        extra_headers={
            "HTTP-Referer": "https://cartha.com",
            "X-Title": "Cartha Open Bible Translation",
        },
        tools=[openrouter_submit_tool()],
        system=system,
        user=user,
        model=model,
        temperature=temperature,
    )


def call_azure_openai(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
) -> tuple[dict[str, Any], str, str]:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", DEFAULT_AZURE_DEPLOYMENT_ID)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)

    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_completion_tokens": DEFAULT_MAX_COMPLETION_TOKENS,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [openrouter_submit_tool()],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure OpenAI HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure OpenAI request failed: {exc}") from exc

    parsed_response = json.loads(response_body)
    choices = parsed_response.get("choices") or []
    if len(choices) != 1:
        raise RuntimeError(f"Azure OpenAI must return exactly one choice; got {len(choices)}")

    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if len(tool_calls) != 1:
        raise RuntimeError(f"Azure OpenAI must return exactly one tool call; got {len(tool_calls)}")

    tool_call = tool_calls[0]
    function = tool_call.get("function") or {}
    if tool_call.get("type") != "function" or function.get("name") != TOOL_NAME:
        raise RuntimeError(f"Azure OpenAI called unexpected tool: {function.get('name')!r}")

    content = message.get("content")
    if isinstance(content, str):
        content_text = content.strip()
    elif isinstance(content, list):
        content_text = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
    else:
        content_text = ""
    if content_text:
        raise RuntimeError("Azure OpenAI returned assistant text in addition to the function call")

    raw_arguments = function.get("arguments") or "{}"
    try:
        parsed_arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Azure function-call arguments were not valid JSON: {exc}") from exc

    return prune_nulls(parsed_arguments), str(parsed_response.get("model") or model), raw_arguments


def call_codex_cli(
    *,
    system: str,
    user: str,
    model: str,
) -> tuple[dict[str, Any], str, str]:
    if not codex_login_available():
        raise RuntimeError("codex-cli backend requested but Codex is not logged in. Run `codex login` first.")

    schema = codex_output_schema()
    with tempfile.TemporaryDirectory(prefix="cartha-enoch-codex-") as temp_dir_name:
        temp_dir = pathlib.Path(temp_dir_name)
        schema_path = temp_dir / "schema.json"
        instructions_path = temp_dir / "system.txt"
        output_path = temp_dir / "output.json"

        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        instructions_path.write_text(system, encoding="utf-8")

        proc = subprocess.run(
            [
                "codex",
                "exec",
                "-m",
                model,
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "-c",
                f'model_instructions_file="{instructions_path}"',
                "-c",
                f'model_reasoning_effort="{DEFAULT_CODEX_REASONING_EFFORT}"',
                "--color",
                "never",
                "-",
            ],
            cwd=REPO_ROOT,
            input=user,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip() or "unknown codex exec failure"
            raise RuntimeError(f"codex exec failed: {detail}")
        if not output_path.exists():
            raise RuntimeError("codex exec completed but did not produce an output file")

        raw_arguments = output_path.read_text(encoding="utf-8")
        parsed_arguments = json.loads(raw_arguments)
        return prune_nulls(parsed_arguments), model, raw_arguments


def call_model(
    *,
    backend: str,
    system: str,
    user: str,
    model: str,
    temperature: float,
) -> tuple[dict[str, Any], str, str, float | None]:
    if backend == BACKEND_OPENAI:
        tool_input, model_version, raw = call_openai(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
        )
        return tool_input, model_version, raw, temperature

    if backend == BACKEND_OPENROUTER:
        tool_input, model_version, raw = call_openrouter(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
        )
        return tool_input, model_version, raw, temperature

    if backend == BACKEND_AZURE:
        tool_input, model_version, raw = call_azure_openai(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
        )
        return tool_input, model_version, raw, temperature

    if backend == BACKEND_CODEX:
        tool_input, model_version, raw = call_codex_cli(
            system=system,
            user=user,
            model=model,
        )
        return tool_input, model_version, raw, None

    raise RuntimeError(f"Unknown backend: {backend}")


def draft_verse(
    chapter: int,
    verse: int,
    *,
    backend: str = DEFAULT_BACKEND,
    model: str = DEFAULT_MODEL_ID,
    temperature: float = DEFAULT_TEMPERATURE,
    prompt_id: str = DEFAULT_PROMPT_ID,
    write: bool = True,
) -> DraftResult:
    bundle = enoch_prompt.build_enoch_prompt(chapter, verse)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + "\n\n---\n\n" + bundle.prompt)

    tool_input, model_version, _raw_output, recorded_temperature = call_model(
        backend=backend,
        system=SYSTEM_PROMPT,
        user=bundle.prompt,
        model=model,
        temperature=temperature,
    )
    validate_tool_input(tool_input)
    output_hash = sha256_hex(canonical_json(tool_input))

    record = build_record(
        bundle,
        tool_input,
        model_id=model,
        model_version=model_version,
        prompt_id=prompt_id,
        prompt_sha256=prompt_sha,
        temperature=recorded_temperature,
        output_hash=output_hash,
        backend=backend,
    )

    output_path = output_path_for_verse(chapter, verse)
    if write:
        output_path = write_yaml(record, chapter, verse)

    return DraftResult(
        chapter=chapter,
        verse=verse,
        record=record,
        output_path=output_path,
        prompt_sha256=prompt_sha,
        model_version=model_version,
    )


def main(argv: Iterable[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, help="Single chapter shortcut")
    ap.add_argument("--chapters", help="Chapter spec like 1,3,5-7")
    ap.add_argument("--verse", type=int, help="Single verse (single chapter only)")
    ap.add_argument("--verses", help="Verse spec like 1,3,5-7")
    ap.add_argument("--all-verses", action="store_true", help="Draft all recovered verses in the selected chapter(s)")
    ap.add_argument("--limit", type=int, help="Optional cap on number of target verses after expansion")
    ap.add_argument("--backend", default=DEFAULT_BACKEND, choices=[BACKEND_CODEX, BACKEND_OPENAI, BACKEND_OPENROUTER, BACKEND_AZURE])
    ap.add_argument("--model", default=DEFAULT_MODEL_ID)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    ap.add_argument("--skip-existing", action="store_true", help="Skip verse YAMLs that already exist")
    ap.add_argument("--dry-run", action="store_true", help="Print the prompt for a single target verse instead of drafting")
    ap.add_argument("--fail-fast", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    chapters_spec = args.chapters or (str(args.chapter) if args.chapter is not None else None)
    if not chapters_spec:
        ap.error("Provide --chapter or --chapters")

    targets = resolve_targets(
        chapters_spec=chapters_spec,
        verse=args.verse,
        verses_spec=args.verses,
        all_verses=args.all_verses,
        limit=args.limit,
    )
    if not targets:
        raise SystemExit("No target verses resolved")

    if args.dry_run:
        if len(targets) != 1:
            raise SystemExit("--dry-run requires exactly one target verse")
        chapter, verse = targets[0]
        bundle = enoch_prompt.build_enoch_prompt(chapter, verse)
        print(bundle.prompt)
        return 0

    completed = skipped = failed = 0
    for idx, (chapter, verse) in enumerate(targets, start=1):
        out_path = output_path_for_verse(chapter, verse)
        ref = f"1 Enoch {chapter}:{verse}"
        if args.skip_existing and out_path.exists():
            print(f"[{idx}/{len(targets)}] skip {ref} -> {out_path.relative_to(REPO_ROOT)}")
            skipped += 1
            continue
        try:
            result = draft_verse(
                chapter,
                verse,
                backend=args.backend,
                model=args.model,
                temperature=args.temperature,
                prompt_id=args.prompt_id,
                write=True,
            )
            print(f"[{idx}/{len(targets)}] ok   {ref} -> {result.output_path.relative_to(REPO_ROOT)}")
            completed += 1
        except Exception as exc:
            print(f"[{idx}/{len(targets)}] FAIL {ref}: {exc}", file=sys.stderr)
            failed += 1
            if args.fail_fast:
                break

    print(
        f"Done: {completed} drafted, {skipped} skipped, {failed} failed "
        f"(backend={args.backend}, model={args.model})"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
