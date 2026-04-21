#!/usr/bin/env python3
"""draft.py — produce an AI draft for one 2 Esdras chapter.

Parallel to tools/draft_first_clement.py but specialized for 2 Esdras:

  - Latin primary source (verse-numbered text from Bensly 1895/1875)
  - Per-chapter draft unit (chs 1-16)
  - Compositional-layer tagging (5 Ezra / 4 Ezra / 6 Ezra)
  - Reader-facing labels propagated into the record (book_headnote,
    section_header, special_footnotes) so the publishing pipeline
    can render them correctly
  - Output at translation/extra_canonical/2_esdras/NN.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
import yaml

import build_translation_prompt


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "2_esdras"

DEFAULT_MODEL_ID = os.environ.get("CARTHA_MODEL_ID", "gpt-5.4")
DEFAULT_TEMPERATURE = float(os.environ.get("CARTHA_TEMPERATURE", "0.2"))
DEFAULT_AZURE_DEPLOYMENT_ID = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-4-deployment")
DEFAULT_AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

TOOL_NAME = "submit_2esdras_draft"
TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
    "compositional_layer",
    "recovered_fragment",
    "messianic_passage",
}

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible and broader-canon project translated directly from original-language sources with auditable reasoning.

You are drafting ONE CHAPTER OF 2 ESDRAS (4 Ezra). 2 Esdras is an Appendix book; the core (chapters 3–14) is a Jewish apocalypse from c. 100 AD, while chapters 1–2 and 15–16 are later Christian additions preserved only in Latin. Your job is to produce the highest-quality chapter draft you can, while exposing major lexical, theological, and compositional decisions so the result is fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the DOCTRINE.md and PHILOSOPHY.md excerpts provided.

You will submit your draft by calling the `submit_2esdras_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the chapter plainly demands one or the other. Apocalyptic vision material tilts formal; prophetic oracles (chs 15-16) tilt formal with declamatory cadence.

Never:
- Paraphrase beyond what the Latin warrants.
- Smooth away Ezra's protest, Uriel's refusals, or the narrow-way passages (7:45-61, 7:102-115, 8:38-41, 9:13-22).
- Render `Altissimus` as generic "God"; it is "the Most High."
- Break the `cor malignum` / "evil heart" thread where the Latin supports it (3:21-22, 4:30, 7:48).
- Blend 5 Ezra and 4 Ezra voices — 5 Ezra is Christian supersessionist rhetoric, 4 Ezra is a Jewish seer's lament.
- Omit significant lexical decisions from `lexical_decisions` just to make the chapter read smoother.
- Copy from copyrighted modern English translations (Metzger, Stone, NRSV).
- Fabricate lexicon entry numbers. If you do not know the specific lexicon entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit a draft English translation for one 2 Esdras chapter, including major lexical, theological, and compositional decisions.",
        "parameters": {
            "type": "object",
            "required": [
                "english_text",
                "translation_philosophy",
                "lexical_decisions",
            ],
            "properties": {
                "english_text": {
                    "type": "string",
                    "description": "The full English translation of the chapter. Start at verse 1. Do NOT include the book headnote or section header in the body — those are structural metadata rendered by the publishing pipeline.",
                },
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
                            "marker": {
                                "type": "string",
                                "description": "Anchor for the footnote — a verse number ('5') or verse reference ('7:28'). For the two mandated special footnotes in chapter 7, use exactly '7:28' and '7:36'.",
                            },
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
    max_completion_tokens: int = 16000,
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
        with urllib.request.urlopen(request, timeout=240) as response:
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


def validate_tool_input(tool_input: dict[str, Any], *, chapter: int) -> None:
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

    # Chapter 7 has two mandated special footnotes (7:28 and 7:36).
    if chapter == 7 and isinstance(footnotes, list):
        markers = {str(n.get("marker", "")).strip() for n in footnotes if isinstance(n, dict)}
        for required in ("7:28", "7:36"):
            if required not in markers:
                errors.append(
                    f"chapter 7 must include a footnote with marker {required!r} per 2ESDRAS.md "
                    "(messianic death / Bensly recovered fragment)"
                )

    if errors:
        raise ValueError("; ".join(errors))


def output_path_for_chapter(chapter: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{chapter:02d}.yaml"


def build_record(
    bundle: build_translation_prompt.PromptBundle,
    tool_input: dict[str, Any],
    *,
    model_id: str,
    model_version: str,
    prompt_id: str,
    prompt_sha256: str,
    temperature: float,
    output_hash: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": f"2ES.{bundle.chapter:02d}",
        "reference": f"2 Esdras {bundle.chapter}",
        "unit": "chapter",
        "book": "2 Esdras",
        "appendix": True,
        "compositional_layer": bundle.layer_name,
        "source": {
            "edition": bundle.source_payload["edition"],
            "text": bundle.source_payload["text"],
            "language": bundle.source_payload["language"],
            "chapter": bundle.source_payload["chapter"],
            "verse_count": bundle.source_payload["verse_count"],
            "witness_situation": bundle.source_payload["witness_situation"],
            "note": bundle.source_payload.get("normalization_note", ""),
        },
        "translation": {
            "text": str(tool_input["english_text"]).strip(),
            "philosophy": tool_input["translation_philosophy"],
        },
        "lexical_decisions": tool_input.get("lexical_decisions", []),
        "theological_decisions": tool_input.get("theological_decisions", []),
        "reader_facing": bundle.reader_facing,
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_version,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha256,
            "temperature": temperature,
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "output_hash": output_hash,
            "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
            "zone2_consults_known": bundle.zone2_consults_known,
        },
    }
    footnotes = tool_input.get("footnotes")
    if footnotes:
        record["translation"]["footnotes"] = footnotes
    return record


def write_yaml(record: dict[str, Any], chapter: int) -> pathlib.Path:
    out_path = output_path_for_chapter(chapter)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return out_path


def draft_chapter(
    chapter_num: int,
    *,
    model: str = DEFAULT_MODEL_ID,
    temperature: float = DEFAULT_TEMPERATURE,
    prompt_id: str = "2esdras_chapter_draft_v1",
    write: bool = True,
) -> DraftResult:
    bundle = build_translation_prompt.build_2esdras_prompt(chapter_num)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + "\n\n---\n\n" + bundle.prompt)
    tool_input, model_version = call_azure_openai(
        system=SYSTEM_PROMPT,
        user=bundle.prompt,
        model=model,
        temperature=temperature,
    )
    validate_tool_input(tool_input, chapter=chapter_num)
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
    output_path = output_path_for_chapter(chapter_num)
    if write:
        output_path = write_yaml(record, chapter_num)
    return DraftResult(
        chapter=chapter_num,
        record=record,
        output_path=output_path,
        prompt_sha256=prompt_sha,
        model_version=model_version,
    )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--dry-run", action="store_true", help="Print the assembled prompt and exit")
    args = parser.parse_args()

    bundle = build_translation_prompt.build_2esdras_prompt(args.chapter)
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
        result = draft_chapter(args.chapter, model=args.model, temperature=args.temperature)
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
