#!/usr/bin/env python3
"""draft_testament.py — produce an AI draft for one Testament chapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
import yaml

import build_testaments_prompt
import testaments_twelve_patriarchs as t12p


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "testaments_twelve_patriarchs"

DEFAULT_MODEL_ID = os.environ.get("CARTHA_MODEL_ID", "gpt-5.4")
DEFAULT_TEMPERATURE = float(os.environ.get("CARTHA_TEMPERATURE", "0.2"))
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-4-deployment")
DEFAULT_AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

TOOL_NAME = "submit_testament_draft"
TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
}

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE CHAPTER from the Testaments of the Twelve Patriarchs. Your job is to produce the highest-quality chapter draft you can, while exposing the major lexical and theological decisions so the result is fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the DOCTRINE.md and PHILOSOPHY.md excerpts provided.

You will submit your draft by calling the `submit_testament_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the chapter plainly demands one or the other.

Never:
- Paraphrase beyond what the Greek warrants.
- Flatten testamentary exhortation into generic modern prose.
- Omit a significant lexical decision from `lexical_decisions` just to make the chapter read smoother.
- Fabricate lexicon entry numbers. If you do not know the specific lexicon entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit a draft English translation for one Testament chapter, including major lexical and theological decisions.",
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
                            "alternatives": {"type": "array", "items": {"type": "string"}},
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
                            "alternative_readings": {"type": "array", "items": {"type": "string"}},
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
                            "reason": {"type": "string", "enum": sorted(TOOL_REASON_VALUES)},
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
    testament_slug: str
    chapter: int
    record: dict[str, Any]
    output_path: pathlib.Path
    prompt_sha256: str
    model_version: str


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def azure_endpoint() -> str:
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")


def azure_api_version() -> str:
    return os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)


def call_azure_openai(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_completion_tokens: int = 12000,
) -> tuple[dict[str, Any], str]:
    endpoint = azure_endpoint()
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", DEFAULT_AZURE_DEPLOYMENT_ID)
    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={azure_api_version()}"
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [SUBMIT_TOOL],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure OpenAI HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure OpenAI request failed: {exc}") from exc

    choices = body.get("choices") or []
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

    raw_arguments = function.get("arguments") or "{}"
    try:
        parsed_arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Azure OpenAI function-call arguments were not valid JSON: {exc}") from exc

    model_version = str(body.get("model") or model)
    return parsed_arguments, model_version


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


def output_path_for_chapter(testament_slug: str, chapter: int) -> pathlib.Path:
    return TRANSLATION_ROOT / testament_slug / f"{chapter:03d}.yaml"


def build_record(
    bundle: build_testaments_prompt.PromptBundle,
    tool_input: dict[str, Any],
    *,
    model_id: str,
    model_version: str,
    prompt_sha256: str,
    temperature: float,
) -> dict[str, Any]:
    code = t12p.testament_code(bundle.chapter.testament_slug)
    record: dict[str, Any] = {
        "id": bundle.chapter_id,
        "reference": bundle.reference,
        "source": {
            "edition": bundle.chapter.source_edition,
            "text": bundle.chapter.text,
            "language": "Greek",
            "source_pages": bundle.chapter.source_pages,
        },
        "translation": {
            "text": str(tool_input["english_text"]).strip(),
            "philosophy": tool_input["translation_philosophy"],
        },
        "lexical_decisions": tool_input.get("lexical_decisions", []),
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_version,
            "prompt_id": "testaments_draft_v1",
            "prompt_sha256": prompt_sha256,
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "temperature": temperature,
        },
        "status": "draft",
        "work": {
            "collection": "Testaments of the Twelve Patriarchs",
            "testament_slug": bundle.chapter.testament_slug,
            "testament_code": code,
        },
    }

    footnotes = tool_input.get("footnotes")
    if footnotes:
        record["translation"]["footnotes"] = footnotes

    theological_decisions = tool_input.get("theological_decisions")
    if theological_decisions:
        record["theological_decisions"] = theological_decisions

    return record


def write_yaml(record: dict[str, Any], testament_slug: str, chapter: int) -> pathlib.Path:
    path = output_path_for_chapter(testament_slug, chapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            record,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return path


def draft_chapter(
    *,
    testament_slug: str,
    chapter: int,
    model: str,
    temperature: float,
    dry_run: bool,
) -> DraftResult | None:
    bundle = build_testaments_prompt.build_testaments_prompt(testament_slug, chapter)
    prompt_sha256 = sha256_hex(bundle.prompt)
    if dry_run:
        print(bundle.prompt)
        return None

    tool_input, model_version = call_azure_openai(
        system=SYSTEM_PROMPT,
        user=bundle.prompt,
        model=model,
        temperature=temperature,
    )
    validate_tool_input(tool_input)
    record = build_record(
        bundle,
        tool_input,
        model_id=model,
        model_version=model_version,
        prompt_sha256=prompt_sha256,
        temperature=temperature,
    )
    output_path = write_yaml(record, testament_slug, chapter)
    return DraftResult(
        testament_slug=testament_slug,
        chapter=chapter,
        record=record,
        output_path=output_path,
        prompt_sha256=prompt_sha256,
        model_version=model_version,
    )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testament", required=True, choices=sorted(t12p.TESTAMENT_BY_SLUG))
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = draft_chapter(
        testament_slug=args.testament,
        chapter=args.chapter,
        model=args.model,
        temperature=args.temperature,
        dry_run=args.dry_run,
    )
    if result is None:
        return 0
    print(f"Wrote {result.output_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
