#!/usr/bin/env python3
"""
draft.py — Produce an AI-drafted translation for a single verse.

Pipeline stage 2 of the Cartha Open Bible methodology. Reads the source
text, builds the doctrinally-constrained prompt, forces a single
`submit_verse_draft` function call from GPT-5.4, validates the response,
and writes a schema-valid YAML record with full provenance metadata.

Usage:

    python tools/draft.py --ref "Philippians 1:1"
    python tools/draft.py --book PHP --chapter 1 --verse 1
    python tools/draft.py --book PHP --chapter 1 --verse 1 --dry-run

Environment:

    CARTHA_DRAFTER_BACKEND  optional (default: codex-cli when available,
                            otherwise openai-sdk)
    OPENAI_API_KEY          required only for openai-sdk backend
    OPENROUTER_API_KEY      required only for openrouter-sdk backend
    AZURE_OPENAI_ENDPOINT   required only for azure-openai backend
    AZURE_OPENAI_API_KEY    required only for azure-openai backend
    AZURE_OPENAI_DEPLOYMENT_ID optional (default: gpt-5-4-deployment)
    AZURE_OPENAI_API_VERSION optional (default: 2025-04-01-preview)
    CARTHA_OPENROUTER_MODEL optional (default: openai/gpt-5.4)
    CARTHA_MODEL_ID         optional (default: gpt-5.4)
    CARTHA_PROMPT_ID        optional (default: nt_draft_v1)
    CARTHA_TEMPERATURE      optional (default: 0.2)

Exit codes: 0 success, 2 usage/config error, 3 parse error,
4 API error, 5 validation error.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from dotenv import load_dotenv
from jsonschema import Draft202012Validator

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sblgnt  # noqa: E402
import wlc  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_ROOT = REPO_ROOT / "sources"
TRANSLATION_ROOT = REPO_ROOT / "translation"
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
SCHEMA_PATH = REPO_ROOT / "schema" / "verse.schema.json"
FAILED_VERSES_PATH = REPO_ROOT / "failed_verses.txt"

DEFAULT_MODEL_ID = os.environ.get("CARTHA_MODEL_ID", "gpt-5.4")
DEFAULT_PROMPT_ID = os.environ.get("CARTHA_PROMPT_ID", "nt_draft_v1")
DEFAULT_TEMPERATURE = float(os.environ.get("CARTHA_TEMPERATURE", "0.2"))
DEFAULT_MAX_COMPLETION_TOKENS = int(
    os.environ.get("CARTHA_MAX_COMPLETION_TOKENS", "4096")
)
DEFAULT_CODEX_REASONING_EFFORT = os.environ.get(
    "CARTHA_CODEX_REASONING_EFFORT",
    "medium",
)
BACKEND_OPENAI = "openai-sdk"
BACKEND_OPENROUTER = "openrouter-sdk"
BACKEND_AZURE = "azure-openai"
BACKEND_CODEX = "codex-cli"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
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

TOOL_NAME = "submit_verse_draft"
TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
}
SCRIPT_TERM_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff\u0590-\u05ff]+")
_REF_RE = re.compile(r"^\s*([123]?\s*[A-Za-z]+)\s+(\d+)\s*:\s*(\d+)\s*$")

ALL_BOOK_NAME_TO_CODE: dict[str, str] = dict(sblgnt.BOOK_NAME_TO_CODE)
for code, (_osis, slug, title, _filename) in wlc.OT_BOOKS.items():
    ALL_BOOK_NAME_TO_CODE[title.lower()] = code
    ALL_BOOK_NAME_TO_CODE[slug.replace("_", " ")] = code

SYSTEM_PROMPT = """You are a translator producing a draft English translation for the Cartha Open Bible — a transparent, CC-BY 4.0 English Bible translated directly from the original Greek and Hebrew with commit-level provenance for every translation decision.

You are drafting ONE verse. Your job is to produce the highest-quality draft you can, and to expose every significant lexical or theological decision so that the draft is fully auditable.

You MUST follow the doctrinal stance and translation philosophy in the DOCTRINE.md excerpt provided. If a verse involves a contested reading listed in the "Contested terms" table, use the stated default rendering and preserve the alternative in a footnote, with your rationale explicitly documented in `lexical_decisions` or `theological_decisions`.

You will submit your draft by calling the `submit_verse_draft` function exactly once. Do not output any other text — only the function call.

Translation philosophy: optimal equivalence (balanced formal/dynamic) unless the verse plainly demands one or the other.

Never:
- Paraphrase beyond what the source text warrants.
- Import doctrinal claims the text does not make.
- Omit a significant lexical decision from `lexical_decisions` to look cleaner.
- Resolve a contested reading that DOCTRINE.md marks as preserved-in-footnote.
- Fabricate lexicon entry numbers. If you don't know the specific BDAG/HALOT/LSJ/Louw-Nida entry, cite the lexicon by name only."""

SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Submit a draft translation for one verse. Include every "
            "significant lexical and theological decision. Include footnotes "
            "for any reading where an alternative is worth preserving."
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
    verse: sblgnt.Verse
    record: dict[str, Any]
    output_path: pathlib.Path
    prompt_sha256: str
    user_prompt: str
    model_version: str


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_term(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(
        ch for ch in decomposed
        if not unicodedata.combining(ch)
    )
    return "".join(ch.lower() for ch in stripped if ch.isalnum())


def extract_primary_script_term(cell: str) -> str:
    matches = SCRIPT_TERM_RE.findall(cell)
    return matches[0] if matches else cell.strip().split()[0]


def explicit_override_rationale(rationale: str) -> bool:
    lowered = rationale.lower()
    override_cues = (
        "override",
        "context",
        "contextual",
        "name-like",
        "title",
        "figurative",
        "metaphor",
        "metaphorical",
        "idiom",
        "idiomatic",
        "here",
        "salient",
        "covenantal",
        "default",
        "footnote",
        "preserve",
    )
    return any(cue in lowered for cue in override_cues)


def default_gloss_options(default_english: str) -> set[str]:
    options: set[str] = set()

    def add_fragment(fragment: str) -> None:
        cleaned = re.sub(r"\([^)]*\)", "", fragment)
        cleaned = re.split(
            r"\bwhere\b|\bcontext\b|\bliteral\b|\bmetaphorical\b",
            cleaned,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" ,;:-")
        normalized = normalize_term(cleaned)
        if normalized:
            options.add(normalized)

    for fragment in re.split(r"[;/]", default_english):
        add_fragment(fragment)

    for parenthetical in re.findall(r"\(([^)]*)\)", default_english):
        for fragment in re.split(r"[;/]", parenthetical):
            add_fragment(fragment)

    if not options:
        normalized = normalize_term(default_english)
        if normalized:
            options.add(normalized)

    return options


def decision_matches_lemma(
    decision_source_word: str,
    lemma: str,
    surface_forms: Iterable[str] = (),
) -> bool:
    decision_norm = normalize_term(decision_source_word)
    lemma_norm = normalize_term(lemma)
    if not decision_norm or not lemma_norm:
        return False
    if (
        decision_norm == lemma_norm
        or lemma_norm in decision_norm
        or decision_norm in lemma_norm
    ):
        return True
    return any(
        decision_norm == surface_norm
        or decision_norm in surface_norm
        or surface_norm in decision_norm
        for surface_norm in (normalize_term(surface) for surface in surface_forms)
        if surface_norm
    )


def translation_path_for_verse(verse: sblgnt.Verse) -> pathlib.Path:
    chapter_dir = TRANSLATION_ROOT / verse_testament(verse.book_code) / verse.book_slug / f"{verse.chapter:03d}"
    return chapter_dir / f"{verse.verse:03d}.yaml"


def verse_testament(book_code: str) -> str:
    if book_code in sblgnt.NT_BOOKS:
        return "nt"
    if book_code in wlc.OT_BOOKS:
        return "ot"
    raise ValueError(f"Unknown book code: {book_code}")


def source_edition_for_book(book_code: str) -> str:
    if book_code in sblgnt.NT_BOOKS:
        return "SBLGNT"
    if book_code in wlc.OT_BOOKS:
        return "WLC"
    raise ValueError(f"Unknown book code: {book_code}")


def source_language_label(book_code: str) -> str:
    if book_code in sblgnt.NT_BOOKS:
        return "Greek (SBLGNT)"
    if book_code in wlc.OT_BOOKS:
        return "Hebrew (WLC)"
    raise ValueError(f"Unknown book code: {book_code}")


def source_text_for_verse(verse: Any) -> str:
    if hasattr(verse, "greek_text"):
        return verse.greek_text
    if hasattr(verse, "hebrew_text"):
        return verse.hebrew_text
    raise TypeError(f"Unsupported verse object: {type(verse)!r}")


def morphology_lines_for_verse(verse: Any) -> str:
    if verse.book_code in sblgnt.NT_BOOKS:
        return sblgnt.morphology_lines(verse)
    if verse.book_code in wlc.OT_BOOKS:
        return wlc.morphology_lines(verse)
    raise ValueError(f"Unknown book code: {verse.book_code}")


def load_source_verse(book_code: str, chapter: int, verse: int) -> Any:
    if book_code in sblgnt.NT_BOOKS:
        return sblgnt.load_verse(book_code, chapter, verse, SOURCES_ROOT)
    if book_code in wlc.OT_BOOKS:
        return wlc.load_verse(book_code, chapter, verse, SOURCES_ROOT)
    raise ValueError(f"Unknown book code: {book_code}")


def iter_source_verses(book_code: str) -> Iterable[Any]:
    if book_code in sblgnt.NT_BOOKS:
        return sblgnt.iter_verses(book_code, SOURCES_ROOT)
    if book_code in wlc.OT_BOOKS:
        return wlc.iter_verses(book_code, SOURCES_ROOT)
    raise ValueError(f"Unknown book code: {book_code}")


def book_slug_for_code(book_code: str) -> str:
    if book_code in sblgnt.NT_BOOKS:
        return sblgnt.NT_BOOKS[book_code][1]
    if book_code in wlc.OT_BOOKS:
        return wlc.OT_BOOKS[book_code][1]
    raise ValueError(f"Unknown book code: {book_code}")


def codex_login_available() -> bool:
    try:
        proc = subprocess.run(
            ["codex", "login", "status"],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    combined_output = f"{proc.stdout}\n{proc.stderr}"
    return proc.returncode == 0 and "Logged in" in combined_output


def default_backend() -> str:
    configured = os.environ.get("CARTHA_DRAFTER_BACKEND")
    if configured:
        return configured
    if codex_login_available():
        return BACKEND_CODEX
    return BACKEND_OPENAI


DEFAULT_BACKEND = default_backend()


@functools.lru_cache(maxsize=1)
def load_schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@functools.lru_cache(maxsize=1)
def load_doctrine_excerpt() -> str:
    if not DOCTRINE_PATH.exists():
        return "(DOCTRINE.md not found; apply default optimal-equivalence.)"

    keep_sections = {
        "## Affirmations",
        "## Translation philosophy",
        "## Contested terms",
    }
    lines = DOCTRINE_PATH.read_text(encoding="utf-8").splitlines()
    keeping = False
    excerpt: list[str] = []

    for line in lines:
        if line.startswith("## "):
            keeping = line.strip() in keep_sections
        if keeping:
            excerpt.append(line)

    return "\n".join(excerpt).strip()


@functools.lru_cache(maxsize=1)
def load_contested_terms() -> dict[str, dict[str, str]]:
    lines = DOCTRINE_PATH.read_text(encoding="utf-8").splitlines()
    in_section = False
    terms: dict[str, dict[str, str]] = {}

    for line in lines:
        if line.startswith("## "):
            if in_section:
                break
            in_section = line.strip() == "## Contested terms"
            continue

        if not in_section or not line.startswith("|") or line.startswith("|---"):
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "Greek / Hebrew":
            continue

        lemma = extract_primary_script_term(cells[0])
        lemma_norm = normalize_term(lemma)
        if not lemma_norm:
            continue

        terms[lemma_norm] = {
            "lemma": lemma,
            "default_english": cells[1],
            "default_options": sorted(default_gloss_options(cells[1])),
        }

    return terms


def build_user_prompt(verse: Any) -> str:
    morph = morphology_lines_for_verse(verse)
    doctrine = load_doctrine_excerpt()
    return f"""# Verse

Reference: {verse.reference}
ID: {verse.canonical_id}

# Source text

{source_language_label(verse.book_code)}: {source_text_for_verse(verse)}

# Morphology table

{morph}

# DOCTRINE.md excerpt

{doctrine}

# Task

Produce the highest-quality draft English translation you can for {verse.reference}.

Return exactly one `{TOOL_NAME}` function call with:
- `english_text`
- `translation_philosophy`
- `lexical_decisions`
- optional `theological_decisions`
- optional `footnotes`

Document every significant lexical choice, and preserve alternatives in footnotes when the doctrine excerpt requires it.
"""


def content_word_count(verse: Any) -> int:
    function_tags = {"ART", "CONJ", "PREP", "PRT"}
    function_prefixes = ("C-", "I-", "P-", "T-")

    count = 0
    for word in verse.words:
        word_text = getattr(word, "word", getattr(word, "text", ""))
        if not any(ch.isalpha() for ch in word_text):
            continue
        tag = str(getattr(word, "pos", "")).upper()
        if not tag:
            count += 1
            continue
        if tag in function_tags or tag.startswith(function_prefixes):
            continue
        count += 1
    return count


def validate_tool_input(verse: Any, tool_input: dict[str, Any]) -> None:
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

    if not isinstance(lexical_decisions, list):
        errors.append("lexical_decisions must be an array")
        lexical_decisions = []

    if content_word_count(verse) >= 5 and not lexical_decisions:
        errors.append("verse has 5+ content words and needs at least one lexical_decisions entry")

    for index, decision in enumerate(lexical_decisions):
        if not isinstance(decision, dict):
            errors.append(f"lexical_decisions[{index}] must be an object")
            continue
        for field in ("source_word", "chosen", "rationale"):
            if not str(decision.get(field, "") or "").strip():
                errors.append(f"lexical_decisions[{index}].{field} must be non-empty")

    if theological_decisions is not None:
        if not isinstance(theological_decisions, list):
            errors.append("theological_decisions must be an array when present")
        else:
            for index, decision in enumerate(theological_decisions):
                if not isinstance(decision, dict):
                    errors.append(f"theological_decisions[{index}] must be an object")
                    continue
                for field in ("issue", "chosen_reading", "rationale"):
                    if not str(decision.get(field, "") or "").strip():
                        errors.append(f"theological_decisions[{index}].{field} must be non-empty")

    if footnotes is not None:
        if not isinstance(footnotes, list):
            errors.append("footnotes must be an array when present")
        else:
            for index, note in enumerate(footnotes):
                if not isinstance(note, dict):
                    errors.append(f"footnotes[{index}] must be an object")
                    continue
                for field in ("marker", "text", "reason"):
                    if not str(note.get(field, "") or "").strip():
                        errors.append(f"footnotes[{index}].{field} must be non-empty")
                reason = note.get("reason")
                if reason not in TOOL_REASON_VALUES:
                    errors.append(f"footnotes[{index}].reason must be one of {sorted(TOOL_REASON_VALUES)}")

    contested_terms = load_contested_terms()
    verse_surface_forms: dict[str, list[str]] = {}
    for word in verse.words:
        lemma_norm = normalize_term(word.lemma)
        if lemma_norm in contested_terms:
            verse_surface_forms.setdefault(lemma_norm, []).append(word.word)

    for lemma_norm, surface_forms in verse_surface_forms.items():
        term = contested_terms[lemma_norm]
        matches = [
            decision for decision in lexical_decisions
            if isinstance(decision, dict)
            and decision_matches_lemma(
                str(decision.get("source_word", "")),
                term["lemma"],
                surface_forms=surface_forms,
            )
        ]
        if not matches:
            errors.append(
                f"contested lemma {term['lemma']} appears in {verse.reference} but has no lexical_decisions entry"
            )
            continue

        default_options = set(term.get("default_options", []))
        if not any(
            normalize_term(str(match.get("chosen", ""))) in default_options
            or explicit_override_rationale(str(match.get("rationale", "")))
            for match in matches
        ):
            errors.append(
                f"contested lemma {term['lemma']} lacks default rendering or explicit override rationale"
            )

    if errors:
        raise ValueError("Validation failed for function-call args: " + "; ".join(errors))


def build_verse_record(
    verse: Any,
    tool_input: dict[str, Any],
    *,
    model_id: str,
    model_version: str,
    prompt_id: str,
    prompt_sha256: str,
    temperature: float | None,
    output_hash: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": verse.canonical_id,
        "reference": verse.reference,
        "source": {
            "edition": source_edition_for_book(verse.book_code),
            "text": source_text_for_verse(verse),
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
            "timestamp": utc_timestamp(),
            "output_hash": output_hash,
        },
        "status": "draft",
    }

    footnotes = tool_input.get("footnotes")
    if footnotes:
        record["translation"]["footnotes"] = footnotes

    theological_decisions = tool_input.get("theological_decisions")
    if theological_decisions:
        record["theological_decisions"] = theological_decisions

    if temperature is not None:
        record["ai_draft"]["temperature"] = temperature

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


def write_verse_yaml(record: dict[str, Any], verse: Any) -> pathlib.Path:
    import yaml

    out_path = translation_path_for_verse(verse)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(
            record,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return out_path


def _strictify_for_codex_schema(schema: Any, required_keys: set[str] | None = None) -> Any:
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
            key: _strictify_for_codex_schema(value)
            for key, value in schema.get("properties", {}).items()
        }
        original_required = set(schema.get("required", []))
        coerced_properties: dict[str, Any] = {}

        for key, subschema in properties.items():
            if key not in original_required:
                subschema = dict(subschema)
                sub_type = subschema.get("type")
                if isinstance(sub_type, list):
                    if "null" not in sub_type:
                        subschema["type"] = list(sub_type) + ["null"]
                elif sub_type is not None:
                    if sub_type != "null":
                        subschema["type"] = [sub_type, "null"]
                else:
                    subschema["type"] = ["null"]
            coerced_properties[key] = subschema

        schema["properties"] = coerced_properties
        schema["required"] = list(coerced_properties.keys())
        schema["additionalProperties"] = False

    if "array" in type_values and "items" in schema:
        schema["items"] = _strictify_for_codex_schema(schema["items"])

    return schema


def codex_output_schema() -> dict[str, Any]:
    return _strictify_for_codex_schema(SUBMIT_TOOL["function"]["parameters"])


def openrouter_tool_schema() -> dict[str, Any]:
    return _strictify_for_codex_schema(SUBMIT_TOOL["function"]["parameters"])


def openrouter_submit_tool() -> dict[str, Any]:
    tool = json.loads(json.dumps(SUBMIT_TOOL))
    tool["function"]["parameters"] = openrouter_tool_schema()
    return tool


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
        raise RuntimeError(
            f"Model must return exactly one tool call; got {len(tool_calls)}"
        )

    tool_call = tool_calls[0]
    if tool_call.type != "function" or tool_call.function.name != TOOL_NAME:
        raise RuntimeError(
            f"Model called unexpected tool: {tool_call.function.name!r}"
        )

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

    return parsed_arguments, response.model, raw_arguments


def call_openai(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
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
        max_completion_tokens=max_completion_tokens,
    )


def call_openrouter(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
) -> tuple[dict[str, Any], str, str]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    parsed_arguments, model_version, raw_arguments = _call_openai_compatible(
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
        max_completion_tokens=max(max_completion_tokens, 16),
    )
    return prune_nulls(parsed_arguments), model_version, raw_arguments


def call_azure_openai(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
) -> tuple[dict[str, Any], str, str]:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    deployment = os.environ.get(
        "AZURE_OPENAI_DEPLOYMENT_ID",
        DEFAULT_AZURE_DEPLOYMENT_ID,
    )
    api_version = os.environ.get(
        "AZURE_OPENAI_API_VERSION",
        DEFAULT_AZURE_API_VERSION,
    )

    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")
    if not deployment:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT_ID not set")

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
        "tools": [openrouter_submit_tool()],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
        },
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

    try:
        parsed_response = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Azure OpenAI returned invalid JSON: {exc}") from exc

    choices = parsed_response.get("choices") or []
    if len(choices) != 1:
        raise RuntimeError(
            f"Azure OpenAI must return exactly one choice; got {len(choices)}"
        )

    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if len(tool_calls) != 1:
        raise RuntimeError(
            f"Azure OpenAI must return exactly one tool call; got {len(tool_calls)}"
        )

    tool_call = tool_calls[0]
    function = tool_call.get("function") or {}
    if tool_call.get("type") != "function" or function.get("name") != TOOL_NAME:
        raise RuntimeError(
            f"Azure OpenAI called unexpected tool: {function.get('name')!r}"
        )

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
        raise RuntimeError(
            "Azure OpenAI returned assistant text in addition to the function call"
        )

    raw_arguments = function.get("arguments") or "{}"
    try:
        parsed_arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Azure OpenAI function-call arguments were not valid JSON: {exc}"
        ) from exc

    model_version = str(parsed_response.get("model") or model)
    return prune_nulls(parsed_arguments), model_version, raw_arguments


def call_codex_cli(
    *,
    system: str,
    user: str,
    model: str,
) -> tuple[dict[str, Any], str, str]:
    if not codex_login_available():
        raise RuntimeError(
            "codex-cli backend requested but Codex is not logged in. Run `codex login` first."
        )

    schema = codex_output_schema()

    with tempfile.TemporaryDirectory(prefix="cartha-codex-") as temp_dir_name:
        temp_dir = pathlib.Path(temp_dir_name)
        schema_path = temp_dir / "schema.json"
        instructions_path = temp_dir / "system.txt"
        output_path = temp_dir / "output.json"

        schema_path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
        try:
            parsed_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"codex exec output was not valid JSON: {exc}") from exc

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
        tool_input, model_version, raw_output = call_openai(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
        )
        return tool_input, model_version, raw_output, temperature

    if backend == BACKEND_OPENROUTER:
        tool_input, model_version, raw_output = call_openrouter(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
        )
        return tool_input, model_version, raw_output, temperature

    if backend == BACKEND_AZURE:
        try:
            tool_input, model_version, raw_output = call_azure_openai(
                system=system,
                user=user,
                model=model,
                temperature=temperature,
            )
        except RuntimeError as exc:
            detail = str(exc)
            azure_filtered = (
                "content_filter" in detail
                or "ResponsibleAIPolicyViolation" in detail
            )
            if azure_filtered and os.environ.get("OPENROUTER_API_KEY"):
                tool_input, model_version, raw_output = call_openrouter(
                    system=system,
                    user=user,
                    model=DEFAULT_OPENROUTER_MODEL_ID,
                    temperature=temperature,
                )
            else:
                raise
        return tool_input, model_version, raw_output, temperature

    if backend == BACKEND_CODEX:
        tool_input, model_version, raw_output = call_codex_cli(
            system=system,
            user=user,
            model=model,
        )
        return tool_input, model_version, raw_output, None

    raise RuntimeError(f"Unknown drafting backend: {backend}")


def draft_verse(
    verse: Any,
    *,
    backend: str = DEFAULT_BACKEND,
    model: str = DEFAULT_MODEL_ID,
    temperature: float = DEFAULT_TEMPERATURE,
    prompt_id: str = DEFAULT_PROMPT_ID,
    write: bool = True,
) -> DraftResult:
    user_prompt = build_user_prompt(verse)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt)

    tool_input, model_version, _raw_arguments, recorded_temperature = call_model(
        backend=backend,
        system=SYSTEM_PROMPT,
        user=user_prompt,
        model=model,
        temperature=temperature,
    )
    validate_tool_input(verse, tool_input)
    output_hash = sha256_hex(canonical_json(tool_input))

    record = build_verse_record(
        verse,
        tool_input,
        model_id=model,
        model_version=model_version,
        prompt_id=prompt_id,
        prompt_sha256=prompt_sha,
        temperature=recorded_temperature,
        output_hash=output_hash,
    )
    validate_record(record)

    output_path = translation_path_for_verse(verse)
    if write:
        output_path = write_verse_yaml(record, verse)

    return DraftResult(
        verse=verse,
        record=record,
        output_path=output_path,
        prompt_sha256=prompt_sha,
        user_prompt=user_prompt,
        model_version=model_version,
    )


def retry_draft_verse(
    verse: Any,
    *,
    backend: str = DEFAULT_BACKEND,
    model: str = DEFAULT_MODEL_ID,
    temperature: float = DEFAULT_TEMPERATURE,
    prompt_id: str = DEFAULT_PROMPT_ID,
    max_attempts: int = 3,
    initial_backoff_seconds: float = 2.0,
) -> DraftResult:
    last_error: Exception | None = None
    backoff = initial_backoff_seconds

    for attempt in range(1, max_attempts + 1):
        try:
            return draft_verse(
                verse,
                backend=backend,
                model=model,
                temperature=temperature,
                prompt_id=prompt_id,
            )
        except Exception as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(backoff)
            backoff *= 2

    assert last_error is not None
    raise last_error


def parse_ref(ref: str) -> tuple[str, int, int]:
    match = _REF_RE.match(ref)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Couldn't parse reference {ref!r}. Expected 'Book C:V' "
            "(e.g., 'Philippians 1:1' or '1 Corinthians 13:4')."
        )

    book_name = re.sub(r"\s+", " ", match.group(1).strip().lower())
    chapter = int(match.group(2))
    verse = int(match.group(3))

    if book_name not in ALL_BOOK_NAME_TO_CODE:
        raise argparse.ArgumentTypeError(
            f"Unknown book {book_name!r}. Known: {sorted(ALL_BOOK_NAME_TO_CODE)}"
        )

    return ALL_BOOK_NAME_TO_CODE[book_name], chapter, verse


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="'Book C:V', e.g., 'Philippians 1:1'")
    parser.add_argument("--book", help="3-letter NT book code (e.g., PHP, ROM, 1CO)")
    parser.add_argument("--chapter", type=int)
    parser.add_argument("--verse", type=int)
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=[BACKEND_CODEX, BACKEND_OPENAI, BACKEND_OPENROUTER],
        help=f"Drafting backend (default: {DEFAULT_BACKEND})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_ID,
        help=f"Model ID / alias (default: {DEFAULT_MODEL_ID})",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=f"Sampling temperature (default: {DEFAULT_TEMPERATURE})",
    )
    parser.add_argument("--prompt-id", default=DEFAULT_PROMPT_ID)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the assembled prompt and exit without calling OpenAI.",
    )
    args = parser.parse_args()

    if args.ref:
        try:
            book_code, chapter, verse_num = parse_ref(args.ref)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
            return 2
    elif args.book and args.chapter and args.verse:
        book_code = args.book.upper()
        chapter = args.chapter
        verse_num = args.verse
    else:
        parser.error("Provide either --ref 'Book C:V' or --book/--chapter/--verse.")
        return 2

    if book_code not in sblgnt.NT_BOOKS and book_code not in wlc.OT_BOOKS:
        parser.error(
            f"Unknown book code: {book_code}. Known NT: {sorted(sblgnt.NT_BOOKS)}; "
            f"Known OT: {sorted(wlc.OT_BOOKS)}"
        )
        return 2

    try:
        verse = load_source_verse(book_code, chapter, verse_num)
    except Exception as exc:
        print(f"ERROR: failed to load verse: {exc}", file=sys.stderr)
        return 3

    user_prompt = build_user_prompt(verse)
    prompt_sha = sha256_hex(SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt)

    if args.dry_run:
        print("=" * 72)
        print("SYSTEM")
        print("=" * 72)
        print(SYSTEM_PROMPT)
        print()
        print("=" * 72)
        print(f"USER (prompt_sha256={prompt_sha})")
        print("=" * 72)
        print(user_prompt)
        return 0

    if args.backend == BACKEND_OPENAI and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set for openai-sdk backend.", file=sys.stderr)
        return 2
    if args.backend == BACKEND_OPENROUTER and not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set for openrouter-sdk backend.", file=sys.stderr)
        return 2
    if args.backend == BACKEND_CODEX and not codex_login_available():
        print("ERROR: codex-cli backend requested but Codex is not logged in.", file=sys.stderr)
        return 2

    try:
        result = retry_draft_verse(
            verse,
            backend=args.backend,
            model=args.model,
            temperature=args.temperature,
            prompt_id=args.prompt_id,
        )
    except ValueError as exc:
        print(f"ERROR: validation failed: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(f"ERROR: API call failed: {exc}", file=sys.stderr)
        return 4

    print(f"Wrote {result.output_path.relative_to(REPO_ROOT)}")
    print(f"model_version={result.model_version}")
    print(f"prompt_sha256={result.prompt_sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
