#!/usr/bin/env python3
"""spanish_pipeline.py — source-grounded Spanish POB drafting/review pipeline.

This intentionally does *not* do a simple English->Spanish localization. Each
Spanish record is drafted with the original source payload, the existing English
POB rendering, lexical/theological decisions, and revision context.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
SPANISH_ROOT = REPO_ROOT / "translation_es"
STATE_ROOT = REPO_ROOT / "state" / "spanish_pipeline"
STATUS_PATH = REPO_ROOT / "status.json"

sys.path.insert(0, str(REPO_ROOT / "tools"))
try:
    import draft as english_draft  # type: ignore
except Exception:  # pragma: no cover - source packet fallback handles this
    english_draft = None

DEFAULT_DRAFT_MODEL_ID = os.environ.get("CARTHA_SPANISH_DRAFT_MODEL", "gpt-5.4-mini")
DEFAULT_REVIEW_MODEL_ID = os.environ.get("CARTHA_SPANISH_REVIEW_MODEL", "gpt-5.4")
DEFAULT_DRAFT_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_MINI_DEPLOYMENT_ID",
    os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-4-mini-deployment"),
)
DEFAULT_REVIEW_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_REVIEW_DEPLOYMENT_ID",
    os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-4-deployment"),
)
DEFAULT_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
DEFAULT_TEMPERATURE = 1.0
DEFAULT_TIMEOUT_SECONDS = 240

MODEL_PRICES_USD_PER_MTOK = {
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50, "cached_input": 0.075},
    "gpt-5.4": {"input": 2.50, "output": 15.00, "cached_input": 0.25},
}

SPANISH_STYLE_AND_GLOSSARY = """
# Spanish target style

Language target: Spanish (neutral Latin American / broadly church-readable),
modern but dignified. Avoid wooden calques when Spanish grammar would become
unnatural, but do not paraphrase beyond the source evidence.

Use Spanish punctuation and capitalization conventions. Prefer clear modern
Spanish over archaic Reina-Valera phrasing unless a traditional form is the most
faithful and intelligible option.

# Project-level Spanish terminology defaults

These are defaults, not blind replacements. Preserve context-sensitive nuance
and explain exceptions in lexical/theological decisions.

- יהוה / YHWH -> "Yahvé" in the main Spanish text, not "SEÑOR" as a masking
  convention. If the immediate source is Greek κύριος quoting or alluding to the
  divine name, explain the decision.
- Χριστός / Messiah language -> usually "Mesías" when the source uses the title;
  preserve "Cristo" only where the English POB already documented a fixed
  liturgical/name-form carve-out or where Spanish idiom genuinely requires it.
- Ἰησοῦς -> "Jesús".
- θεός / אֱלֹהִים -> "Dios"; maintain singular/plural/contextual force in notes
  where relevant.
- πνεῦμα / רוּחַ -> "espíritu" / "Espíritu" by context; do not flatten wind,
  breath, spirit, and Holy Spirit senses.
- δοῦλος -> normally "esclavo" where the English POB chose "slave" for lexical
  force; use "siervo" only with documented contextual reason.
- μετάνοια / μετανοέω -> context-sensitive: "arrepentimiento/arrepentirse" in
  sin-turning contexts; "cambio de mente/pensamiento" where the cognitive force
  is primary.
- σάρξ -> usually "carne"; explain when "naturaleza humana" or another rendering
  is necessary for Spanish clarity.
- δικαιοσύνη -> "justicia" / "rectitud" by context; preserve covenant/legal force
  when present.
- χάρις -> "gracia" unless the source clearly means favor/thanks in a way Spanish
  should make explicit.

# Required output discipline

Work from the original source evidence first. Use the English POB translation,
English lexical decisions, footnotes, and revisions as audited context, not as an
opaque base text to translate mechanically.

For every significant source-language choice, produce a Spanish lexical decision
that explains the Spanish rendering. Preserve meaningful alternatives in Spanish
footnotes when the English POB preserved them, or when Spanish creates a new
ambiguity. Use unique footnote markers in order (a, b, c, ...); never reuse a
marker for two different notes in the same record. If you include any footnote
object, the exact marker must also appear in `spanish_text` at the relevant word
or phrase, formatted like `[a]`. If no anchor belongs in the text, do not create
that footnote.
""".strip()

DRAFT_SYSTEM_PROMPT = f"""You are producing a source-grounded Spanish draft for the People's Open Bible.

The People's Open Bible is transparent, CC-BY 4.0, and translated directly from
original-language sources with auditable reasoning. Your task is not ordinary
localization. You are drafting one Spanish verse/section using the original
source text plus the existing English POB audit trail.

You must call `submit_spanish_draft` exactly once and output no other text.

Never:
- translate mechanically from English while ignoring the original source;
- paraphrase beyond what the source warrants;
- erase a documented lexical/theological tension;
- replace documented POB terminology with traditional church wording without a
  source-based rationale;
- invent lexicon entry numbers.

{SPANISH_STYLE_AND_GLOSSARY}
"""

REVIEW_SYSTEM_PROMPT = f"""You are an independent source-facing reviewer for the Spanish People's Open Bible.

Read the original source evidence, the English POB audit trail, and the Spanish
draft. Decide whether the Spanish draft faithfully preserves the source meaning,
POB terminology, Spanish readability, and documented lexical/theological
rationale.

You must call `submit_spanish_review` exactly once and output no other text.

{SPANISH_STYLE_AND_GLOSSARY}
"""

DRAFT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_spanish_draft",
        "description": "Submit a source-grounded Spanish draft with auditable lexical/theological decisions.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": ["spanish_text", "translation_philosophy", "lexical_decisions", "theological_decisions", "footnotes", "revision_awareness", "spanish_consistency_notes"],
            "properties": {
                "spanish_text": {"type": "string"},
                "translation_philosophy": {"type": "string", "enum": ["formal", "dynamic", "optimal-equivalence"]},
                "lexical_decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["source_word", "english_pob_choice", "chosen_spanish", "alternatives_spanish", "lexicon", "rationale"],
                        "properties": {
                            "source_word": {"type": "string"},
                            "english_pob_choice": {"type": "string"},
                            "chosen_spanish": {"type": "string"},
                            "alternatives_spanish": {"type": "array", "items": {"type": "string"}},
                            "lexicon": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "theological_decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["issue", "english_pob_reading", "chosen_spanish_reading", "alternative_spanish_readings", "rationale", "doctrine_reference"],
                        "properties": {
                            "issue": {"type": "string"},
                            "english_pob_reading": {"type": "string"},
                            "chosen_spanish_reading": {"type": "string"},
                            "alternative_spanish_readings": {"type": "array", "items": {"type": "string"}},
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
                                "enum": [
                                    "alternative_reading",
                                    "lexical_alternative",
                                    "textual_variant",
                                    "cultural_note",
                                    "cross_reference",
                                    "theological_note",
                                    "source_note",
                                    "spanish_style_note",
                                ],
                            },
                        },
                        "additionalProperties": False,
                    },
                },
                "revision_awareness": {"type": "string"},
                "spanish_consistency_notes": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    },
}

REVIEW_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_spanish_review",
        "description": "Review a Spanish POB draft against source evidence and project terminology.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": ["verdict", "source_alignment_summary", "spanish_quality_summary", "glossary_alignment", "issues", "revised_spanish_text", "revised_footnotes", "revision_rationale", "requires_gpt54_adjudication"],
            "properties": {
                "verdict": {"type": "string", "enum": ["approve", "revise", "reject"]},
                "source_alignment_summary": {"type": "string"},
                "spanish_quality_summary": {"type": "string"},
                "glossary_alignment": {"type": "string"},
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["severity", "issue", "rationale"],
                        "properties": {
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                            "issue": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "revised_spanish_text": {"type": "string"},
                "revised_footnotes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["marker", "text", "reason"],
                        "properties": {
                            "marker": {"type": "string"},
                            "text": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "revision_rationale": {"type": "string"},
                "requires_gpt54_adjudication": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
    },
}

@dataclass(frozen=True)
class SourceRecord:
    source_path: pathlib.Path
    target_path: pathlib.Path
    testament: str
    book: str
    slug: str
    index: int


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def current_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ""


def prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: prune_empty(v) for k, v in value.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [prune_empty(v) for v in value if v not in (None, "", [], {})]
    return value


def rel(path: pathlib.Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def safe_load_yaml(path: pathlib.Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected YAML object")
    return data


def write_yaml_atomic(path: pathlib.Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        tmp.write(rendered)
        tmp_path = pathlib.Path(tmp.name)
    tmp_path.replace(path)


def acquire_lock(path: pathlib.Path, worker_id: str) -> pathlib.Path | None:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"worker_id": worker_id, "locked_at": utc_now()}) + "\n")
    return lock_path


def release_lock(lock_path: pathlib.Path | None) -> None:
    if lock_path and lock_path.exists():
        lock_path.unlink()


def choose_source_files(book_dir: pathlib.Path) -> list[pathlib.Path]:
    if book_dir.name == "testaments_twelve_patriarchs":
        return sorted(book_dir.rglob("*.yaml"))
    nested = sorted(book_dir.glob("*/*.yaml"))
    if nested:
        return nested
    return sorted(book_dir.glob("*.yaml"))


def iter_status_records(*, book_filter: set[str] | None = None, testament_filter: set[str] | None = None) -> list[SourceRecord]:
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    records: list[SourceRecord] = []
    idx = 0
    for book in status.get("books", []):
        testament = str(book.get("testament"))
        slug = str(book.get("slug"))
        name = str(book.get("book"))
        if book_filter and slug not in book_filter and name.lower().replace(" ", "_") not in book_filter:
            continue
        if testament_filter and testament not in testament_filter:
            continue
        book_dir = TRANSLATION_ROOT / testament / slug
        for source_path in choose_source_files(book_dir):
            idx += 1
            target_path = SPANISH_ROOT / source_path.relative_to(TRANSLATION_ROOT)
            records.append(SourceRecord(source_path, target_path, testament, name, slug, idx))
    return records


def infer_id_parts(record: dict[str, Any]) -> tuple[str, int, int] | None:
    raw = str(record.get("id") or "")
    m = re.match(r"^([A-Z0-9]+)\.(\d+)\.(\d+)$", raw)
    if not m:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


def canonical_source_packet(record: dict[str, Any]) -> str:
    if english_draft is None:
        return "(canonical source helper unavailable; use source payload below)"
    parts = infer_id_parts(record)
    if not parts:
        return "(not a canonical/deuterocanonical verse id; use source payload below)"
    code, chapter, verse = parts
    try:
        verse_obj = english_draft.load_source_verse(code, chapter, verse)
        source_text = english_draft.source_text_for_verse(verse_obj)
        morph = english_draft.morphology_lines_for_verse(verse_obj)
        language = english_draft.source_language_label(code)
        return f"Reference: {verse_obj.reference}\n{language}: {source_text}\n\nMorphology table:\n{morph or '(none supplied)'}"
    except Exception as exc:
        return f"(canonical source helper failed: {type(exc).__name__}: {exc}; use source payload below)"


def compact_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=1000).strip()


def build_draft_user_prompt(source_path: pathlib.Path, record: dict[str, Any]) -> str:
    translation = record.get("translation") or {}
    context = {
        "source_yaml_path": rel(source_path),
        "id": record.get("id"),
        "reference": record.get("reference"),
        "source_payload": record.get("source") or {},
        "english_pob_translation": {
            "text": translation.get("text"),
            "footnotes": translation.get("footnotes") or [],
            "philosophy": translation.get("philosophy"),
        },
        "english_lexical_decisions": record.get("lexical_decisions") or [],
        "english_theological_decisions": record.get("theological_decisions") or [],
        "applied_revisions": record.get("revisions") or [],
        "latest_revision_pass": record.get("revision_pass") or {},
        "cross_check_summary": summarize_cross_check(record.get("cross_check") or {}),
    }
    return f"""# Spanish source-grounded draft task

Draft a Spanish POB record for this one verse/section.

## Canonical source packet when available

{canonical_source_packet(record)}

## Full source + English audit context

{compact_yaml(context)}

## Task

Return exactly one `submit_spanish_draft` function call.

The main `spanish_text` should be publication-readable Spanish. The lexical and
theological decisions should explain Spanish choices from the original source,
using the English POB audit trail as context.
""".strip()


def summarize_cross_check(cross_check: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(cross_check, dict):
        return {}
    keep = {
        "status": cross_check.get("status"),
        "verdict": cross_check.get("verdict"),
        "agreement": cross_check.get("agreement"),
        "agreement_score": cross_check.get("agreement_score"),
        "reviewer_model": cross_check.get("reviewer_model"),
        "pass_count": cross_check.get("pass_count"),
        "passes_with_issues": cross_check.get("passes_with_issues"),
        "verdict_counts": cross_check.get("verdict_counts"),
    }
    return prune_empty(keep)


def build_review_user_prompt(source_path: pathlib.Path, english_record: dict[str, Any], spanish_record: dict[str, Any]) -> str:
    context = {
        "source_yaml_path": rel(source_path),
        "spanish_yaml_path": rel(source_to_spanish_path(source_path)),
        "id": english_record.get("id"),
        "reference": english_record.get("reference"),
        "source_payload": english_record.get("source") or {},
        "canonical_source_packet": canonical_source_packet(english_record),
        "english_pob_translation": (english_record.get("translation") or {}),
        "english_lexical_decisions": english_record.get("lexical_decisions") or [],
        "english_theological_decisions": english_record.get("theological_decisions") or [],
        "applied_revisions": english_record.get("revisions") or [],
        "spanish_draft": {
            "text": ((spanish_record.get("translation") or spanish_record.get("spanish_translation") or {}).get("text")),
            "footnotes": ((spanish_record.get("translation") or spanish_record.get("spanish_translation") or {}).get("footnotes") or []),
            "lexical_decisions": spanish_record.get("lexical_decisions") or [],
            "theological_decisions": spanish_record.get("theological_decisions") or [],
        },
    }
    return f"""# Spanish POB review task

Review this Spanish draft against the source and the English POB audit trail.

{compact_yaml(context)}

## Task

Return exactly one `submit_spanish_review` function call. If the text needs a
small repair, set verdict `revise` and provide `revised_spanish_text` plus a
complete `revised_footnotes` array whose markers exactly match the revised text.
If you approve without changes, set `revised_spanish_text` and
`revision_rationale` to empty strings and `revised_footnotes` to an empty array.
Set `requires_gpt54_adjudication` true only when the issue is genuinely hard,
doctrinally sensitive, source-uncertain, or the Spanish reviewer should not be
trusted to auto-apply it.
""".strip()


def source_to_spanish_path(source_path: pathlib.Path) -> pathlib.Path:
    return SPANISH_ROOT / source_path.relative_to(TRANSLATION_ROOT)


def fetch_azure_env() -> None:
    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
        return
    try:
        raw = subprocess.check_output(
            [
                "aws",
                "secretsmanager",
                "get-secret-value",
                "--secret-id",
                "cartha-azure-openai-key",
                "--region",
                "us-west-2",
                "--query",
                "SecretString",
                "--output",
                "text",
            ],
            text=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY/AZURE_OPENAI_ENDPOINT are not set and AWS secret fetch failed"
        ) from exc
    secret = json.loads(raw)
    os.environ["AZURE_OPENAI_API_KEY"] = secret["api_key"]
    os.environ["AZURE_OPENAI_ENDPOINT"] = secret.get("endpoint") or "https://eastus2.api.cognitive.microsoft.com"
    os.environ.setdefault("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)


def model_prices(model_id: str) -> dict[str, float]:
    normalized = model_id.lower()
    if "mini" in normalized:
        return MODEL_PRICES_USD_PER_MTOK["gpt-5.4-mini"]
    return MODEL_PRICES_USD_PER_MTOK["gpt-5.4"]


def usage_cost_usd(usage: dict[str, Any], model_id: str) -> float:
    prices = model_prices(model_id)
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    return (prompt / 1_000_000 * prices["input"]) + (completion / 1_000_000 * prices["output"])


def call_azure_tool(
    *,
    system_prompt: str,
    user_prompt: str,
    tool: dict[str, Any],
    tool_name: str,
    deployment: str,
    model_id: str,
    max_completion_tokens: int,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    retries: int = 2,
) -> tuple[dict[str, Any], str, dict[str, Any], str]:
    fetch_azure_env()
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    api_key = os.environ["AZURE_OPENAI_API_KEY"]
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": max_completion_tokens,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": tool_name}},
        "tools": [tool],
    }
    # GPT-5-family Azure deployments commonly only accept the default temp=1.
    if temperature != 1.0:
        payload["temperature"] = temperature

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            data=encoded,
            headers={"Content-Type": "application/json", "api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            choices = body.get("choices") or []
            if not choices:
                raise RuntimeError(f"Azure response had no choices: {body}")
            message = choices[0].get("message") or {}
            tool_calls = message.get("tool_calls") or []
            if len(tool_calls) != 1:
                raise RuntimeError(f"Expected exactly one tool call; got {len(tool_calls)}: {body}")
            fn = (tool_calls[0].get("function") or {})
            if fn.get("name") != tool_name:
                raise RuntimeError(f"Expected tool {tool_name}; got {fn.get('name')}")
            raw_args = fn.get("arguments") or "{}"
            parsed = json.loads(raw_args)
            if not isinstance(parsed, dict):
                raise RuntimeError("Tool arguments were not an object")
            return prune_empty(parsed), str(body.get("model") or model_id), body.get("usage") or {}, raw_args
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"HTTP {exc.code}: {detail[:1200]}")
        except Exception as exc:  # noqa: BLE001 - preserve retry surface
            last_error = exc
        if attempt < retries:
            time.sleep(2 + attempt * 5)
    assert last_error is not None
    raise last_error


def build_spanish_record(
    *,
    source_path: pathlib.Path,
    english_record: dict[str, Any],
    tool_input: dict[str, Any],
    model_id: str,
    model_version: str,
    prompt_id: str,
    prompt_sha: str,
    raw_output_hash: str,
    usage: dict[str, Any],
    deployment: str,
) -> dict[str, Any]:
    translation_block: dict[str, Any] = {
        "text": str(tool_input["spanish_text"]).strip(),
        "philosophy": tool_input.get("translation_philosophy") or "optimal-equivalence",
    }
    if tool_input.get("footnotes"):
        translation_block["footnotes"] = tool_input["footnotes"]
    record = {
        "id": english_record.get("id"),
        "reference": english_record.get("reference"),
        "language": {
            "code": "es",
            "name": "Spanish",
            "variant": "neutral Latin American",
        },
        "source": english_record.get("source") or {},
        "base_translation": {
            "language": "en",
            "yaml_path": rel(source_path),
            "text": ((english_record.get("translation") or {}).get("text")),
            "footnotes": ((english_record.get("translation") or {}).get("footnotes") or []),
            "ai_draft": english_record.get("ai_draft") or {},
            "revision_pass": english_record.get("revision_pass") or {},
        },
        "translation": {"language": "es", **translation_block},
        "lexical_decisions": tool_input.get("lexical_decisions") or [],
        "theological_decisions": tool_input.get("theological_decisions") or [],
        "translation_notes": {
            "revision_awareness": tool_input.get("revision_awareness"),
            "spanish_consistency_notes": tool_input.get("spanish_consistency_notes") or [],
        },
        "source_grounding": {
            "english_pob_role": "consult_only",
            "english_pob_path": rel(source_path),
            "source_text_sha256": sha256_text(compact_yaml(english_record.get("source") or {})),
            "english_pob_commit_sha": current_git_sha(),
        },
        "ai_draft": {
            "model_id": model_id,
            "model_version": model_version,
            "azure_deployment": deployment,
            "prompt_id": prompt_id,
            "prompt_sha256": prompt_sha,
            "timestamp": utc_now(),
            "output_hash": raw_output_hash,
            "usage": normalize_usage(usage, model_id),
        },
        "status": "spanish_draft",
    }
    return prune_empty(record)


def normalize_usage(usage: dict[str, Any], model_id: str) -> dict[str, Any]:
    usage = dict(usage or {})
    details = usage.get("completion_tokens_details") or {}
    normalized = {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
        "estimated_cost_usd": round(usage_cost_usd(usage, model_id), 6),
    }
    return normalized


def validate_spanish_record(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    try:
        record = safe_load_yaml(path)
    except Exception as exc:
        return [f"{type(exc).__name__}: {exc}"]
    text = str(((record.get("translation") or record.get("spanish_translation") or {}).get("text") or "")).strip()
    if not text:
        errors.append("translation.text missing")
    if (record.get("language") or {}).get("code") != "es":
        errors.append("language.code is not es")
    if not isinstance(record.get("lexical_decisions"), list):
        errors.append("lexical_decisions missing/non-list")
    elif len(text.split()) >= 5 and not record.get("lexical_decisions"):
        errors.append("lexical_decisions empty for non-trivial text")
    footnotes = ((record.get("translation") or record.get("spanish_translation") or {}).get("footnotes") or [])
    markers = [str(note.get("marker") or "") for note in footnotes if isinstance(note, dict)]
    if len(markers) != len(set(markers)):
        errors.append("duplicate footnote markers")
    for marker in markers:
        if marker and f"[{marker}]" not in text:
            errors.append(f"footnote marker [{marker}] not present in translation text")
    if not (record.get("ai_draft") or {}).get("prompt_sha256"):
        errors.append("ai_draft.prompt_sha256 missing")
    if re.search(r"\b(the|and|of|with|shall|Messiah Jesus)\b", text, re.IGNORECASE):
        errors.append("possible untranslated English residue in Spanish text")
    return errors


def draft_one(src: SourceRecord, *, args: argparse.Namespace) -> bool:
    if src.target_path.exists() and not args.force:
        return False
    lock = acquire_lock(src.target_path, args.worker_id)
    if lock is None:
        return False
    try:
        english_record = safe_load_yaml(src.source_path)
        user_prompt = build_draft_user_prompt(src.source_path, english_record)
        prompt_sha = sha256_text(DRAFT_SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt)
        if args.dry_run_prompt:
            print(user_prompt)
            return True
        validation_note = ""
        last_errors: list[str] = []
        for validation_attempt in range(args.validation_retries + 1):
            attempt_prompt = user_prompt + validation_note
            attempt_prompt_sha = sha256_text(DRAFT_SYSTEM_PROMPT + "\n\n---\n\n" + attempt_prompt)
            tool_input, model_version, usage, raw_args = call_azure_tool(
                system_prompt=DRAFT_SYSTEM_PROMPT,
                user_prompt=attempt_prompt,
                tool=DRAFT_TOOL,
                tool_name="submit_spanish_draft",
                deployment=args.deployment,
                model_id=args.model,
                max_completion_tokens=args.max_completion_tokens,
                temperature=args.temperature,
                timeout_seconds=args.timeout_seconds,
                retries=args.retries,
            )
            out_record = build_spanish_record(
                source_path=src.source_path,
                english_record=english_record,
                tool_input=tool_input,
                model_id=args.model,
                model_version=model_version,
                prompt_id=args.prompt_id,
                prompt_sha=attempt_prompt_sha,
                raw_output_hash=sha256_text(raw_args),
                usage=usage,
                deployment=args.deployment,
            )
            write_yaml_atomic(src.target_path, out_record)
            errors = validate_spanish_record(src.target_path)
            if not errors:
                print(f"drafted {rel(src.target_path)} cost=${out_record['ai_draft']['usage']['estimated_cost_usd']:.4f}", flush=True)
                return True
            last_errors = errors
            invalid_path = src.target_path.with_suffix(src.target_path.suffix + f".invalid-{int(time.time())}-{validation_attempt}")
            src.target_path.replace(invalid_path)
            validation_note = (
                "\n\n# Previous output failed validation\n"
                f"Errors: {errors}\n"
                "Return a corrected function call. Footnotes are allowed only when every marker appears exactly in spanish_text, e.g. [a]. "
                "Use unique markers and include no unanchored footnotes.\n"
            )
        raise RuntimeError(f"validation failed for {rel(src.target_path)} after retries: {last_errors}")
    finally:
        release_lock(lock)


def review_one(src: SourceRecord, *, args: argparse.Namespace) -> bool:
    target = src.target_path
    if not target.exists():
        return False
    lock = acquire_lock(target.with_suffix(target.suffix + ".review"), args.worker_id)
    if lock is None:
        return False
    try:
        english_record = safe_load_yaml(src.source_path)
        spanish_record = safe_load_yaml(target)
        if spanish_record.get("review_pass") and not args.force:
            return False
        user_prompt = build_review_user_prompt(src.source_path, english_record, spanish_record)
        prompt_sha = sha256_text(REVIEW_SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt)
        tool_input, model_version, usage, raw_args = call_azure_tool(
            system_prompt=REVIEW_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tool=REVIEW_TOOL,
            tool_name="submit_spanish_review",
            deployment=args.deployment,
            model_id=args.model,
            max_completion_tokens=args.max_completion_tokens,
            temperature=args.temperature,
            timeout_seconds=args.timeout_seconds,
            retries=args.retries,
        )
        translation_obj = spanish_record.setdefault("translation", {})
        old_text = str(((translation_obj or spanish_record.get("spanish_translation") or {}).get("text") or "")).strip()
        old_footnotes = list((translation_obj or spanish_record.get("spanish_translation") or {}).get("footnotes") or [])
        revised = str(tool_input.get("revised_spanish_text") or "").strip()
        revised_footnotes = tool_input.get("revised_footnotes") if isinstance(tool_input.get("revised_footnotes"), list) else old_footnotes
        apply_revision = args.apply_revisions and tool_input.get("verdict") == "revise" and revised and revised != old_text and not bool(tool_input.get("requires_gpt54_adjudication"))
        auto_apply_blocked_errors: list[str] = []
        if apply_revision:
            candidate = dict(spanish_record)
            candidate_translation = dict(translation_obj)
            candidate_translation["text"] = revised
            if revised_footnotes:
                candidate_translation["footnotes"] = revised_footnotes
            elif "footnotes" in candidate_translation:
                candidate_translation.pop("footnotes", None)
            candidate["translation"] = candidate_translation
            temp_validate_path = target.with_suffix(target.suffix + ".review-candidate")
            write_yaml_atomic(temp_validate_path, candidate)
            auto_apply_blocked_errors = validate_spanish_record(temp_validate_path)
            temp_validate_path.unlink(missing_ok=True)
            if auto_apply_blocked_errors:
                apply_revision = False
        if apply_revision:
            spanish_record.setdefault("revisions", []).append(
                {
                    "from": old_text,
                    "to": revised,
                    "rationale": tool_input.get("revision_rationale") or tool_input.get("source_alignment_summary"),
                    "reviewer_model": args.model,
                    "timestamp": utc_now(),
                }
            )
            translation_obj["text"] = revised
            if revised_footnotes:
                translation_obj["footnotes"] = revised_footnotes
            else:
                translation_obj.pop("footnotes", None)
            spanish_record["status"] = "spanish_reviewed"
        elif tool_input.get("verdict") == "approve":
            spanish_record["status"] = "spanish_reviewed"
        else:
            spanish_record["status"] = "spanish_needs_adjudication" if tool_input.get("requires_gpt54_adjudication") else "spanish_needs_revision"
        spanish_record["review_pass"] = prune_empty(
            {
                **tool_input,
                "model_id": args.model,
                "model_version": model_version,
                "azure_deployment": args.deployment,
                "prompt_id": args.prompt_id,
                "prompt_sha256": prompt_sha,
                "timestamp": utc_now(),
                "output_hash": sha256_text(raw_args),
                "usage": normalize_usage(usage, args.model),
                "applied_revision": apply_revision,
                "auto_apply_blocked_errors": auto_apply_blocked_errors,
            }
        )
        write_yaml_atomic(target, spanish_record)
        print(f"reviewed {rel(target)} verdict={tool_input.get('verdict')} cost=${spanish_record['review_pass']['usage']['estimated_cost_usd']:.4f}", flush=True)
        return True
    finally:
        release_lock(lock)


def selected_records(args: argparse.Namespace) -> list[SourceRecord]:
    books = set(args.book or []) or None
    tests = set(args.testament or []) or None
    records = iter_status_records(book_filter=books, testament_filter=tests)
    if args.shard_count > 1:
        records = [r for i, r in enumerate(records) if i % args.shard_count == args.shard_index]
    return records


def command_draft(args: argparse.Namespace) -> int:
    records = selected_records(args)
    done = 0
    for src in records:
        if done >= args.limit > 0:
            break
        try:
            if draft_one(src, args=args):
                done += 1
        except Exception as exc:  # noqa: BLE001 - CLI surface
            print(f"FAILED draft {rel(src.source_path)}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if not args.keep_going:
                return 1
    print(f"draft command completed: wrote_or_processed={done}")
    return 0


def command_review(args: argparse.Namespace) -> int:
    records = selected_records(args)
    done = 0
    for src in records:
        if done >= args.limit > 0:
            break
        try:
            if review_one(src, args=args):
                done += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED review {rel(src.source_path)}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if not args.keep_going:
                return 1
    print(f"review command completed: wrote_or_processed={done}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    records = selected_records(args)
    checked = failed = 0
    for src in records:
        if args.only_existing and not src.target_path.exists():
            continue
        if checked >= args.limit > 0:
            break
        checked += 1
        errors = validate_spanish_record(src.target_path) if src.target_path.exists() else ["missing Spanish YAML"]
        if errors:
            failed += 1
            print(f"{rel(src.target_path)}: {errors}")
    print(f"validated={checked} failed={failed}")
    return 1 if failed else 0


def collect_usage() -> dict[str, Any]:
    totals = {
        "draft_prompt_tokens": 0,
        "draft_completion_tokens": 0,
        "draft_cost_usd": 0.0,
        "review_prompt_tokens": 0,
        "review_completion_tokens": 0,
        "review_cost_usd": 0.0,
        "files": 0,
        "reviewed": 0,
        "needs_adjudication": 0,
    }
    by_status: dict[str, int] = {}
    totals["invalid_files"] = 0
    for path in sorted(SPANISH_ROOT.glob("**/*.yaml*")):
        if path.name.endswith(".lock") or ".review" in path.name:
            continue
        record = safe_load_yaml(path)
        is_invalid = ".invalid-" in path.name
        if is_invalid:
            totals["invalid_files"] += 1
        else:
            totals["files"] += 1
            by_status[str(record.get("status") or "unknown")] = by_status.get(str(record.get("status") or "unknown"), 0) + 1
        usage = ((record.get("ai_draft") or {}).get("usage") or {})
        totals["draft_prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        totals["draft_completion_tokens"] += int(usage.get("completion_tokens") or 0)
        totals["draft_cost_usd"] += float(usage.get("estimated_cost_usd") or 0)
        review = record.get("review_pass") or {}
        if review:
            totals["reviewed"] += 1
            rusage = review.get("usage") or {}
            totals["review_prompt_tokens"] += int(rusage.get("prompt_tokens") or 0)
            totals["review_completion_tokens"] += int(rusage.get("completion_tokens") or 0)
            totals["review_cost_usd"] += float(rusage.get("estimated_cost_usd") or 0)
        if record.get("status") == "spanish_needs_adjudication":
            totals["needs_adjudication"] += 1
    totals["draft_cost_usd"] = round(totals["draft_cost_usd"], 6)
    totals["review_cost_usd"] = round(totals["review_cost_usd"], 6)
    totals["total_cost_usd"] = round(totals["draft_cost_usd"] + totals["review_cost_usd"], 6)
    totals["by_status"] = by_status
    return totals


def command_summary(args: argparse.Namespace) -> int:
    records = selected_records(args)
    expected = len(records)
    existing = sum(1 for r in records if r.target_path.exists())
    reviewed = 0
    status_counts: dict[str, int] = {}
    for r in records:
        if not r.target_path.exists():
            continue
        record = safe_load_yaml(r.target_path)
        status = str(record.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        if record.get("review_pass"):
            reviewed += 1
    payload = {
        "expected_records": expected,
        "spanish_files": existing,
        "pending_draft": expected - existing,
        "reviewed": reviewed,
        "pending_review": existing - reviewed,
        "status_counts": status_counts,
        "usage": collect_usage(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def estimate_tokens_for_text(text: str) -> int:
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("o200k_base")
        return len(enc.encode(text))
    except Exception:
        # Conservative English-ish fallback. Greek/Hebrew source text tokenizes
        # denser, so this is only for preflight estimates when tiktoken is absent.
        return max(1, int(len(text) / 3.2))


def command_estimate(args: argparse.Namespace) -> int:
    records = selected_records(args)
    draft_prompt_tokens = 0
    for src in records[: args.limit if args.limit > 0 else len(records)]:
        record = safe_load_yaml(src.source_path)
        draft_prompt_tokens += estimate_tokens_for_text(DRAFT_SYSTEM_PROMPT) + estimate_tokens_for_text(build_draft_user_prompt(src.source_path, record))
    sampled = len(records[: args.limit]) if args.limit > 0 else len(records)
    avg = draft_prompt_tokens / sampled if sampled else 0
    projected_input = int(avg * len(records))
    # Spanish structured output tends to be in the same ballpark as English output;
    # use 2,000 tokens/record as a conservative full-audit estimate unless real
    # usage has already been collected.
    projected_output = int(len(records) * args.output_tokens_per_record)
    prices = model_prices(args.model)
    cost = projected_input / 1_000_000 * prices["input"] + projected_output / 1_000_000 * prices["output"]
    print(json.dumps({
        "records": len(records),
        "sampled_records": sampled,
        "avg_estimated_input_tokens_per_record": round(avg, 1),
        "projected_input_tokens": projected_input,
        "projected_output_tokens": projected_output,
        "model": args.model,
        "estimated_draft_cost_usd": round(cost, 2),
    }, indent=2))
    return 0


def add_common_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--book", action="append", help="Book slug/name filter, repeatable")
    parser.add_argument("--testament", action="append", choices=["ot", "nt", "deuterocanon", "extra_canonical"])
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("draft", help="Draft Spanish YAML records")
    add_common_filters(p)
    p.add_argument("--limit", type=int, default=1, help="0 = no limit")
    p.add_argument("--worker-id", default=f"spanish-draft-{os.getpid()}")
    p.add_argument("--model", default=DEFAULT_DRAFT_MODEL_ID)
    p.add_argument("--deployment", default=DEFAULT_DRAFT_DEPLOYMENT)
    p.add_argument("--prompt-id", default="spanish_source_grounded_draft_v1")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    p.add_argument("--max-completion-tokens", type=int, default=12000)
    p.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--validation-retries", type=int, default=1)
    p.add_argument("--force", action="store_true")
    p.add_argument("--keep-going", action="store_true")
    p.add_argument("--dry-run-prompt", action="store_true")
    p.set_defaults(func=command_draft)

    p = sub.add_parser("review", help="Review existing Spanish YAML records")
    add_common_filters(p)
    p.add_argument("--limit", type=int, default=1, help="0 = no limit")
    p.add_argument("--worker-id", default=f"spanish-review-{os.getpid()}")
    p.add_argument("--model", default=DEFAULT_REVIEW_MODEL_ID)
    p.add_argument("--deployment", default=DEFAULT_REVIEW_DEPLOYMENT)
    p.add_argument("--prompt-id", default="spanish_source_review_v1")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    p.add_argument("--max-completion-tokens", type=int, default=8000)
    p.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--validation-retries", type=int, default=1)
    p.add_argument("--force", action="store_true")
    p.add_argument("--apply-revisions", action="store_true")
    p.add_argument("--keep-going", action="store_true")
    p.set_defaults(func=command_review)

    p = sub.add_parser("validate", help="Validate Spanish YAML records")
    add_common_filters(p)
    p.add_argument("--limit", type=int, default=0, help="0 = no limit")
    p.add_argument("--only-existing", action="store_true")
    p.set_defaults(func=command_validate)

    p = sub.add_parser("summary", help="Summarize progress and observed API costs")
    add_common_filters(p)
    p.set_defaults(func=command_summary)

    p = sub.add_parser("estimate", help="Estimate draft cost for selected records")
    add_common_filters(p)
    p.add_argument("--limit", type=int, default=250, help="sample records for input estimate; 0 = all")
    p.add_argument("--model", default=DEFAULT_DRAFT_MODEL_ID)
    p.add_argument("--output-tokens-per-record", type=int, default=2000)
    p.set_defaults(func=command_estimate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.shard_index < 0 or args.shard_count < 1 or args.shard_index >= args.shard_count:
        parser.error("shard-index must be in [0, shard-count)")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
