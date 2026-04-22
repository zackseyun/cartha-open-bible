#!/usr/bin/env python3
"""draft_thomas.py — produce an AI draft for one Gospel of Thomas saying.

Drafts from the CopticScriptorium (Dilley 2025, CC-BY 4.0) primary
Coptic witness using Azure OpenAI GPT-5.4 via a strict function-call
interface. Writes per-saying YAML under:

    translation/extra_canonical/gospel_of_thomas/<saying_id>.yaml

Mirrors the audit-trail conventions established by draft_didache.py /
draft_first_clement.py.
"""
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
except ImportError:  # pragma: no cover - optional convenience only
    def load_dotenv() -> bool:
        return False
import yaml

# sys.path shim so we can import the sibling prompt builder cleanly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_thomas_saying_prompt as bp  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "gospel_of_thomas"

DEFAULT_MODEL_ID = os.environ.get("CARTHA_MODEL_ID", "gpt-5.4")
DEFAULT_TEMPERATURE = float(os.environ.get("CARTHA_TEMPERATURE", "1.0"))
DEFAULT_MAX_COMPLETION_TOKENS = int(
    os.environ.get("CARTHA_MAX_COMPLETION_TOKENS", "20000")
)
DEFAULT_REQUEST_TIMEOUT_SECONDS = int(
    os.environ.get("CARTHA_REQUEST_TIMEOUT_SECONDS", "300")
)
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get(
    "AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-4-deployment"
)
DEFAULT_AZURE_API_VERSION = os.environ.get(
    "AZURE_OPENAI_API_VERSION", "2025-04-01-preview"
)

TOOL_NAME = "submit_thomas_saying_draft"
FOOTNOTE_REASONS = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
    "dialect_note",
    "lacuna_or_restoration",
}

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE GOSPEL-OF-THOMAS SAYING directly from the Coptic. The Coptic source is the Paul Dilley 2025 edition (CopticScriptorium, CC-BY 4.0). When a POxy Greek fragment overlaps the saying, use it as a cross-witness — record divergences rather than silently reconciling them.

You MUST follow the doctrinal stance and translation philosophy in the DOCTRINE.md and PHILOSOPHY.md excerpts provided at the project level. You will submit your draft by calling the `submit_thomas_saying_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic). Where Thomas deliberately sounds strange, preserve the strangeness instead of smoothing it.

Never:
- Paraphrase based on a modern English translation. Translate the Coptic.
- Harmonize Thomas toward Synoptic canonical wording — Synoptic parallels are context, not pressure.
- Invent lexicon entry numbers. Cite lexicon by name (Crum, Smith, Lambdin, Layton) without fabricating entry identifiers.
- Silently fill lacunae. If Dilley marks a restoration or ambiguity, say so in a footnote.
- Drop a meaningful lexical, dialectal, or Greek-divergence decision from the decision arrays just to read smoother."""


SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit a draft English translation of one Gospel of Thomas saying, with lexical / textual / Greek-overlap / Synoptic decisions.",
        "parameters": {
            "type": "object",
            "required": [
                "english_text",
                "translation_philosophy",
                "lexical_decisions",
                "textual_note",
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
                            "rationale": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "textual_note": {
                    "type": "string",
                    "description": "Dialect observations, lacunae, restorations, orthographic oddities in this saying.",
                },
                "greek_overlap_decision": {
                    "type": "object",
                    "description": "Required only if a POxy Greek fragment overlaps this saying.",
                    "properties": {
                        "witness": {"type": "string"},
                        "agreement": {
                            "type": "string",
                            "enum": ["aligned", "minor_divergence", "substantive_divergence", "too_fragmentary"],
                        },
                        "chosen_basis": {
                            "type": "string",
                            "enum": ["coptic", "greek", "blended_with_note"],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["witness", "agreement", "chosen_basis", "rationale"],
                    "additionalProperties": False,
                },
                "synoptic_parallel_check": {
                    "type": "object",
                    "description": "Record whether any Synoptic canonical parallel exists, and how it was handled.",
                    "properties": {
                        "parallels": {"type": "array", "items": {"type": "string"}},
                        "handling": {
                            "type": "string",
                            "enum": ["no_parallel", "context_only", "intentional_echo", "intentional_divergence"],
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": ["handling"],
                    "additionalProperties": False,
                },
                "footnotes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["marker", "text", "reason"],
                        "properties": {
                            "marker": {"type": "string"},
                            "text": {"type": "string"},
                            "reason": {"type": "string", "enum": sorted(FOOTNOTE_REASONS)},
                        },
                        "additionalProperties": False,
                    },
                },
                "revision_risk_note": {
                    "type": "string",
                    "description": "Plain-language statement of what a reviewer should look at most carefully.",
                },
            },
            "additionalProperties": False,
        },
    },
}


@dataclass
class DraftResult:
    saying_id: str
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


def _message_text_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return ""


def _try_parse_json_content(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    candidates = [text]
    if text.startswith("```") and text.endswith("```"):
        inner = text.split("\n", 1)
        if len(inner) == 2:
            fenced = inner[1].rsplit("```", 1)[0].strip()
            if fenced:
                candidates.append(fenced)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_tool_payload(body: dict[str, Any], model: str) -> tuple[dict[str, Any], str]:
    choices = body.get("choices") or []
    if len(choices) != 1:
        raise RuntimeError(f"Azure OpenAI must return exactly one choice; got {len(choices)}")
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if len(tool_calls) == 1:
        tool_call = tool_calls[0]
        function = tool_call.get("function") or {}
        if tool_call.get("type") != "function" or function.get("name") != TOOL_NAME:
            raise RuntimeError(
                f"Azure OpenAI called unexpected tool: {function.get('name')!r}"
            )
        raw_arguments = function.get("arguments") or "{}"
        try:
            parsed_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Azure OpenAI function-call arguments were not valid JSON: {exc}"
            ) from exc
        model_version = str(body.get("model") or model)
        return parsed_arguments, model_version

    content_text = _message_text_content(message)
    parsed_content = _try_parse_json_content(content_text)
    if parsed_content is not None:
        model_version = str(body.get("model") or model)
        return parsed_content, model_version

    excerpt = content_text.strip().replace("\n", " ")
    if len(excerpt) > 280:
        excerpt = excerpt[:277] + "..."
    raise RuntimeError(
        "Azure OpenAI must return exactly one tool call; "
        f"got {len(tool_calls)}. content_excerpt={excerpt!r}"
    )


def call_azure_openai(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    retries: int = 2,
    retry_delay_seconds: float = 2.0,
) -> tuple[dict[str, Any], str]:
    endpoint = azure_endpoint()
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", DEFAULT_AZURE_DEPLOYMENT_ID)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_AZURE_API_VERSION)
    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    url = (
        f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={api_version}"
    )
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
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=request_timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
            return _extract_tool_payload(body, model)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"Azure OpenAI HTTP {exc.code}: {detail}")
            if attempt < retries and exc.code in {408, 409, 429, 500, 502, 503, 504}:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise last_error from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = RuntimeError(f"Azure OpenAI request failed: {exc}")
            if attempt < retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise last_error from exc
        except RuntimeError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise
    assert last_error is not None
    raise last_error


def validate_tool_input(tool_input: dict[str, Any], *, has_greek_overlap: bool) -> None:
    errors: list[str] = []
    english_text = str(tool_input.get("english_text", "") or "")
    philosophy = str(tool_input.get("translation_philosophy", "") or "")
    lex = tool_input.get("lexical_decisions")
    textual_note = str(tool_input.get("textual_note", "") or "")

    if not english_text.strip():
        errors.append("english_text must be non-empty")
    if philosophy not in {"formal", "dynamic", "optimal-equivalence"}:
        errors.append("translation_philosophy must be formal/dynamic/optimal-equivalence")
    if not isinstance(lex, list):
        errors.append("lexical_decisions must be an array")
    if not textual_note.strip():
        errors.append("textual_note must be non-empty (even if 'no issues to report')")

    if has_greek_overlap and "greek_overlap_decision" not in tool_input:
        errors.append(
            "greek_overlap_decision is required for this saying (Greek POxy fragment overlaps)"
        )

    footnotes = tool_input.get("footnotes")
    if footnotes is not None and not isinstance(footnotes, list):
        errors.append("footnotes must be an array when present")
    if isinstance(footnotes, list):
        for i, note in enumerate(footnotes):
            if not isinstance(note, dict):
                errors.append(f"footnotes[{i}] must be an object")
                continue
            for field in ("marker", "text", "reason"):
                if not str(note.get(field, "") or "").strip():
                    errors.append(f"footnotes[{i}].{field} must be non-empty")
            if note.get("reason") not in FOOTNOTE_REASONS:
                errors.append(
                    f"footnotes[{i}].reason must be one of {sorted(FOOTNOTE_REASONS)}"
                )

    if errors:
        raise ValueError("; ".join(errors))


def output_path_for_saying(saying_id: str) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{saying_id}.yaml"


def build_record(
    bundle: bp.PromptBundle,
    tool_input: dict[str, Any],
    *,
    model_id: str,
    model_version: str,
    prompt_id: str,
    prompt_sha256: str,
    temperature: float,
    output_hash: str,
) -> dict[str, Any]:
    saying_id = bundle.saying_id
    if saying_id == "subtitle":
        ref = "Gospel of Thomas — subtitle"
        rec_id = "THOM.SUBTITLE"
    elif saying_id == "000":
        ref = "Gospel of Thomas — incipit"
        rec_id = "THOM.INCIPIT"
    else:
        ref = f"Gospel of Thomas — {bundle.saying_label}"
        rec_id = f"THOM.{int(saying_id):03d}"

    record: dict[str, Any] = {
        "id": rec_id,
        "reference": ref,
        "unit": "saying",
        "book": "Gospel of Thomas",
        "source": {
            "edition": bundle.source_payload["edition"],
            "license": bundle.source_payload["license"],
            "urn": bundle.source_payload["urn"],
            "language": bundle.source_payload["language"],
            "manuscript": bundle.source_payload["manuscript"],
            "codex_pages": bundle.source_payload.get("codex_pages", []),
            "coptic_orig": bundle.source_payload["coptic_orig"],
            "coptic_norm": bundle.source_payload["coptic_norm"],
            "lines": bundle.source_payload.get("lines", []),
            "greek_overlap_witnesses": bundle.source_payload.get(
                "greek_overlap_witnesses", []
            ),
        },
        "translation": {
            "text": str(tool_input["english_text"]).strip(),
            "philosophy": tool_input["translation_philosophy"],
        },
        "lexical_decisions": tool_input.get("lexical_decisions", []),
        "textual_note": tool_input.get("textual_note", ""),
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_version,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha256,
            "temperature": temperature,
            "timestamp": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "output_hash": output_hash,
            "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
            "zone2_consults_known": bundle.zone2_consults_known,
        },
    }
    for optional in (
        "greek_overlap_decision",
        "synoptic_parallel_check",
        "revision_risk_note",
    ):
        if optional in tool_input:
            record[optional] = tool_input[optional]
    if tool_input.get("footnotes"):
        record["translation"]["footnotes"] = tool_input["footnotes"]
    return record


def write_yaml(record: dict[str, Any], saying_id: str) -> pathlib.Path:
    out_path = output_path_for_saying(saying_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(
            record, sort_keys=False, allow_unicode=True, default_flow_style=False
        ),
        encoding="utf-8",
    )
    return out_path


def draft_saying(
    saying_id: str,
    *,
    model: str = DEFAULT_MODEL_ID,
    temperature: float = DEFAULT_TEMPERATURE,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    prompt_id: str = "thomas_saying_draft_v1",
    write: bool = True,
) -> DraftResult:
    bundle = bp.build_thomas_saying_prompt(saying_id)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + "\n\n---\n\n" + bundle.prompt)
    tool_input, model_version = call_azure_openai(
        system=SYSTEM_PROMPT,
        user=bundle.prompt,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        request_timeout_seconds=request_timeout_seconds,
    )
    validate_tool_input(
        tool_input,
        has_greek_overlap=bool(bundle.greek_overlap_ids),
    )
    output_hash = sha256_hex(canonical_json(tool_input))
    record = build_record(
        bundle,
        tool_input,
        model_id=model,
        model_version=model_version,
        prompt_id=prompt_id,
        prompt_sha256=prompt_sha,
        temperature=temperature,
        output_hash=output_hash,
    )
    output_path = output_path_for_saying(saying_id)
    if write:
        output_path = write_yaml(record, saying_id)
    return DraftResult(
        saying_id=saying_id,
        record=record,
        output_path=output_path,
        prompt_sha256=prompt_sha,
        model_version=model_version,
    )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--saying",
        required=True,
        help="Saying id: 000 (incipit), 001..114, or 'subtitle'.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=DEFAULT_MAX_COMPLETION_TOKENS,
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the assembled system + user prompt and exit",
    )
    args = parser.parse_args()

    bundle = bp.build_thomas_saying_prompt(args.saying)
    if args.dry_run:
        print("=" * 72)
        print("SYSTEM")
        print("=" * 72)
        print(SYSTEM_PROMPT)
        print()
        print("=" * 72)
        print("USER")
        print("=" * 72)
        print(bundle.prompt)
        return 0

    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        print("ERROR: AZURE_OPENAI_ENDPOINT not set.", file=sys.stderr)
        return 2
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        print("ERROR: AZURE_OPENAI_API_KEY not set.", file=sys.stderr)
        return 2

    try:
        result = draft_saying(
            args.saying,
            model=args.model,
            temperature=args.temperature,
            max_completion_tokens=args.max_completion_tokens,
            request_timeout_seconds=args.request_timeout_seconds,
        )
    except ValueError as exc:
        print(f"ERROR: validation failed: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(f"ERROR: draft failed: {exc}", file=sys.stderr)
        return 4

    print(f"Wrote {result.output_path.relative_to(REPO_ROOT)}")
    print(f"model_version={result.model_version}")
    print(f"prompt_sha256={result.prompt_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
