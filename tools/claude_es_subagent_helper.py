#!/usr/bin/env python3
"""claude_es_subagent_helper.py — companion to in-session Opus subagents.

A subagent processes one EN YAML at a time:
  1. Reads translation/<path>.yaml
  2. Generates the Spanish content (its own native inference)
  3. Pipes a single-line JSON object to this helper via stdin:

     {"en_path": "translation/extra_canonical/.../001.yaml",
      "spanish_text": "...",
      "translation_philosophy": "optimal-equivalence",
      "lexical_decisions": [...],
      "theological_decisions": [...],
      "footnotes": [...],
      "revision_awareness": "...",
      "spanish_consistency_notes": [...]}

This helper builds the canonical translation_es/<path>.yaml using the same
build_spanish_record path as the rest of the pipeline, validates, writes,
and prints OK/ERROR to stdout. Saves the subagent from constructing the
full YAML envelope by hand.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import spanish_pipeline as sp  # type: ignore

PROMPT_ID = "spanish_source_grounded_draft_opus_subagent_v1"
MODEL_ID = "claude-opus-4-7"


def normalize_en_path(raw: str) -> pathlib.Path:
    p = pathlib.Path(raw.strip())
    if p.is_absolute():
        p = p.relative_to(REPO_ROOT)
    s = str(p).replace("translation_es/", "translation/", 1)
    if not s.startswith("translation/"):
        raise ValueError(f"{raw!r}: not under translation/")
    return REPO_ROOT / s


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR json_decode: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("ERROR payload not object", file=sys.stderr)
        return 2

    en_raw = payload.pop("en_path", None)
    if not en_raw:
        print("ERROR missing en_path", file=sys.stderr)
        return 2
    try:
        en_path = normalize_en_path(en_raw)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR en_path: {exc}", file=sys.stderr)
        return 2

    target = sp.SPANISH_ROOT / en_path.relative_to(sp.TRANSLATION_ROOT)
    if target.exists():
        print(f"SKIP_EXISTING {target.relative_to(REPO_ROOT)}")
        return 0

    required = {
        "spanish_text",
        "translation_philosophy",
        "lexical_decisions",
        "theological_decisions",
        "footnotes",
        "revision_awareness",
        "spanish_consistency_notes",
    }
    missing = required - set(payload.keys())
    if missing:
        print(f"ERROR missing fields: {sorted(missing)}", file=sys.stderr)
        return 2

    try:
        english_record = sp.safe_load_yaml(en_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR read_en: {exc}", file=sys.stderr)
        return 2

    user_prompt = sp.build_draft_user_prompt(en_path, english_record)
    prompt_sha = sp.sha256_text(sp.DRAFT_SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt)
    raw_args = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    raw_output_hash = sp.sha256_text(raw_args)

    record = sp.build_spanish_record(
        source_path=en_path,
        english_record=english_record,
        tool_input=sp.prune_empty(payload),
        model_id=MODEL_ID,
        model_version=MODEL_ID,
        prompt_id=PROMPT_ID,
        prompt_sha=prompt_sha,
        raw_output_hash=raw_output_hash,
        usage={},
        deployment="claude_code_subagent",
    )
    record["ai_draft"]["usage"] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "estimated_cost_usd": 0.0,
        "billed_to": "claude_code_max_session_opus",
    }
    record["ai_draft"]["provider"] = "anthropic_claude_code_opus_subagent"
    record["ai_draft"]["fallback_reason"] = "azure_out_of_scope_extension"

    sp.write_yaml_atomic(target, sp.prune_empty(record))
    errs = sp.validate_spanish_record(target)
    if errs:
        invalid = target.with_suffix(target.suffix + f".invalid-{int(time.time())}")
        target.replace(invalid)
        print(f"ERROR validation: {errs}", file=sys.stderr)
        return 1
    print(f"OK {target.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
