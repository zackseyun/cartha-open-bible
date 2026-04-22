#!/usr/bin/env python3
"""draft.py — produce an AI draft for one 1 Enoch verse.

This is the first actual drafter runner for the Enoch pipeline. It consumes
``tools/enoch/build_translation_prompt.py`` and writes per-verse YAML under:

    translation/extra_canonical/1_enoch/<chapter>/<verse>.yaml

The runner is intentionally narrow:

- one verse at a time,
- Charles 1906 Ge'ez OCR as the current primary witness,
- transparent metadata about which witness lanes are actually loaded,
- standard COB verse schema plus an ``enoch_witnesses`` block.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from jsonschema import Draft202012Validator
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "1_enoch"
SCHEMA_PATH = REPO_ROOT / "schema" / "verse.schema.json"

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_translation_prompt  # noqa: E402

DEFAULT_MODEL_ID = os.environ.get("CARTHA_MODEL_ID", "gpt-5.4")
DEFAULT_TEMPERATURE = float(os.environ.get("CARTHA_TEMPERATURE", "0.2"))
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-4-deployment")
DEFAULT_AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
DEFAULT_PROMPT_ID = os.environ.get("CARTHA_PROMPT_ID", "enoch_verse_draft_v1")

TOOL_NAME = "submit_enoch_verse_draft"
TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
}
_REF_RE = re.compile(r"^\s*(?:1\s*)?enoch\s+(\d+)\s*:\s*(\d+)\s*$", re.IGNORECASE)

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE VERSE OF 1 ENOCH. Your job is to produce the highest-quality draft you can, while exposing every significant lexical or theological decision so the draft is fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the DOCTRINE.md and PHILOSOPHY.md excerpts provided in the user prompt.

You will submit your draft by calling the `submit_enoch_verse_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the verse plainly demands one or the other.

Never:
- Paraphrase beyond what the Ge'ez witness warrants.
- Flatten apocalyptic imagery, angelic speech, or judgment formulas into generic modern religious prose.
- Import New Testament phrasing just because a passage is echoed later.
- Omit significant lexical decisions from `lexical_decisions` just to make the English smoother.
- Copy from copyrighted modern English Enoch translations.
- Fabricate lexicon entry numbers. If you do not know the specific lexicon entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit a draft English translation for one 1 Enoch verse, including major lexical and theological decisions.",
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
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_ref(ref: str) -> tuple[int, int]:
    m = _REF_RE.match(ref)
    if not m:
        raise argparse.ArgumentTypeError("Reference must look like '1 Enoch 1:1'.")
    return int(m.group(1)), int(m.group(2))


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
    max_completion_tokens: int = 6000,
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


def load_schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def output_path_for_verse(chapter: int, verse: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{chapter:03d}" / f"{verse:03d}.yaml"


def _attestation_summary(chapter: int) -> dict[str, Any]:
    greek = {
        "attested": False,
        "status": "no known Greek witness for this chapter in current pipeline notes",
    }
    if 1 <= chapter <= 32:
        greek = {"attested": True, "status": "Panopolitanus Greek witness survives for this chapter range"}
    elif 72 <= chapter <= 82:
        greek = {"attested": True, "status": "Greek fragments survive for parts of the Astronomical Book"}
    elif 97 <= chapter <= 107:
        greek = {"attested": True, "status": "Chester Beatty Greek survives for this chapter range"}

    aramaic = {
        "zone2_consult_possible": False,
        "status": "No Qumran Aramaic consultation expected for this chapter range in current notes",
    }
    if (1 <= chapter <= 36) or (72 <= chapter <= 108):
        aramaic = {
            "zone2_consult_possible": True,
            "status": "Qumran Aramaic fragments exist for at least part of this chapter range",
        }

    return {"greek": greek, "aramaic": aramaic}


def _build_enoch_witnesses(bundle: build_translation_prompt.EnochPromptBundle) -> dict[str, Any]:
    available = list(bundle.witness_set.get("available_witnesses", []))
    by_language: dict[str, list[str]] = {}
    for witness in available:
        lang = str(witness.get("language", "") or "unknown")
        by_language.setdefault(lang, []).append(str(witness.get("witness", "unknown")))

    return {
        "section": bundle.witness_set.get("section"),
        "loaded_witnesses_by_language": by_language,
        "available_witnesses": available,
        "attestation_expectations": _attestation_summary(bundle.chapter),
        "geez_only_zone1": 37 <= bundle.chapter <= 71,
        "source_warnings": bundle.source_warnings,
    }


def build_record(
    bundle: build_translation_prompt.EnochPromptBundle,
    tool_input: dict[str, Any],
    *,
    model_id: str,
    model_version: str,
    prompt_id: str,
    prompt_sha256: str,
    temperature: float,
    output_hash: str,
) -> dict[str, Any]:
    source_note_parts = [str(bundle.source_payload.get("note", "") or "").strip()]
    source_note_parts.extend(str(w).strip() for w in bundle.source_warnings if str(w).strip())
    source_note = " | ".join(part for part in source_note_parts if part)

    record: dict[str, Any] = {
        "id": f"1EN.{bundle.chapter}.{bundle.verse}",
        "reference": bundle.reference,
        "book": "1 Enoch",
        "source": {
            "edition": bundle.source_payload["edition"],
            "text": bundle.source_payload["text"],
            "language": bundle.source_payload["language"],
            "pages": bundle.source_payload.get("pages", []),
            "confidence": bundle.source_payload.get("confidence"),
            "validation": bundle.source_payload.get("validation"),
            "note": source_note,
        },
        "translation": {
            "text": str(tool_input["english_text"]).strip(),
            "philosophy": tool_input["translation_philosophy"],
        },
        "lexical_decisions": tool_input.get("lexical_decisions", []),
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_version,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha256,
            "temperature": temperature,
            "timestamp": utc_timestamp(),
            "output_hash": output_hash,
            "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
            "zone2_consults_known": bundle.zone2_consults_known,
        },
        "status": "draft",
        "enoch_witnesses": _build_enoch_witnesses(bundle),
    }

    footnotes = tool_input.get("footnotes")
    if footnotes:
        record["translation"]["footnotes"] = footnotes

    theological_decisions = tool_input.get("theological_decisions")
    if theological_decisions:
        record["theological_decisions"] = theological_decisions

    return record


def validate_record(record: dict[str, Any]) -> None:
    validator = load_schema_validator()
    errors = sorted(validator.iter_errors(record), key=lambda err: list(err.path))
    if errors:
        rendered = "; ".join(
            f"{'.'.join(str(part) for part in err.path) or '<root>'}: {err.message}"
            for err in errors
        )
        raise ValueError(f"Schema validation failed: {rendered}")
    if not str(record["translation"]["text"]).strip():
        raise ValueError("translation.text must be non-empty")


def write_yaml(record: dict[str, Any], chapter: int, verse: int) -> pathlib.Path:
    out_path = output_path_for_verse(chapter, verse)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return out_path


def draft_verse(
    chapter: int,
    verse: int,
    *,
    model: str = DEFAULT_MODEL_ID,
    temperature: float = DEFAULT_TEMPERATURE,
    prompt_id: str = DEFAULT_PROMPT_ID,
    write: bool = True,
) -> DraftResult:
    bundle = build_translation_prompt.build_enoch_prompt(chapter, verse)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + "\n\n---\n\n" + bundle.prompt)
    tool_input, model_version = call_azure_openai(
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
        temperature=temperature,
        output_hash=output_hash,
    )
    validate_record(record)
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


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="Reference like '1 Enoch 1:1'")
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--verse", type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    parser.add_argument("--dry-run", action="store_true", help="Print the assembled prompt and exit")
    args = parser.parse_args()

    if args.ref:
        try:
            chapter, verse = parse_ref(args.ref)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
            return 2
    elif args.chapter and args.verse:
        chapter = args.chapter
        verse = args.verse
    else:
        parser.error("Provide either --ref '1 Enoch C:V' or --chapter/--verse.")
        return 2

    bundle = build_translation_prompt.build_enoch_prompt(chapter, verse)
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
        if bundle.source_warnings:
            print()
            print("=" * 72)
            print("SOURCE WARNINGS")
            print("=" * 72)
            for warning in bundle.source_warnings:
                print(f"- {warning}")
        return 0

    if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        print("ERROR: AZURE_OPENAI_ENDPOINT not set.", file=sys.stderr)
        return 2
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        print("ERROR: AZURE_OPENAI_API_KEY not set.", file=sys.stderr)
        return 2

    try:
        result = draft_verse(
            chapter,
            verse,
            model=args.model,
            temperature=args.temperature,
            prompt_id=args.prompt_id,
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
