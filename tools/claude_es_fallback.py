#!/usr/bin/env python3
"""claude_es_fallback.py — Claude-based fallback drafter for Spanish POB.

Used for verses Azure refused with content_filter / ResponsibleAIPolicyViolation.
Re-uses the same source-grounded prompt + YAML schema as spanish_pipeline.py
but drives a Claude model via the local `claude -p` CLI so the user's Claude
Code subscription is the funding source (no Azure cost).

Input: a text file with paths like translation/<...>.yaml (one per line),
       OR --paths arguments.
Output: writes translation_es/<...>.yaml records via build_spanish_record.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import spanish_pipeline as sp  # type: ignore

CLAUDE_BIN = os.environ.get("CARTHA_CLAUDE_BIN", "claude")
CLAUDE_MODEL = os.environ.get("CARTHA_CLAUDE_MODEL", "claude-sonnet-4-6")
PROMPT_ID = "spanish_source_grounded_draft_claude_v1"

# Pricing reference (Sonnet 4.6 list price). Just used to estimate cost in the
# YAML; actual billing for the user is via Claude Code subscription/OAuth.
CLAUDE_PRICES_USD_PER_MTOK = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cached_input": 0.30},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0, "cached_input": 1.50},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0, "cached_input": 0.10},
}

CLAUDE_DRAFT_SCHEMA = sp.DRAFT_TOOL["function"]["parameters"]


def normalize_input_path(raw: str) -> pathlib.Path:
    """Accept absolute, repo-relative, or ES-target paths and return repo-relative
    English source path under translation/."""
    p = raw.strip()
    if not p:
        raise ValueError("empty path")
    path = pathlib.Path(p)
    if path.is_absolute():
        path = path.relative_to(REPO_ROOT)
    sp_str = str(path)
    if sp_str.startswith("translation_es/"):
        sp_str = "translation/" + sp_str[len("translation_es/") :]
    if not sp_str.startswith("translation/"):
        raise ValueError(f"{raw!r}: not under translation/ or translation_es/")
    return REPO_ROOT / sp_str


def call_claude_cli(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    timeout_seconds: int,
    workdir: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    cmd = [
        CLAUDE_BIN,
        "--print",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--output-format",
        "json",
        "--system-prompt",
        system_prompt,
        "--json-schema",
        json.dumps(CLAUDE_DRAFT_SCHEMA, ensure_ascii=False),
        "--model",
        model,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(workdir),
        input=user_prompt,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exit={proc.returncode} stderr={proc.stderr.strip()[:1500]} stdout={proc.stdout.strip()[:1500]}"
        )
    try:
        wrapper = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude returned non-JSON wrapper: {exc}: {proc.stdout[:1500]}")
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude reported error: {wrapper}")
    # When --json-schema is used, the structured object lives at .structured_output
    # and .result is empty. Without a schema, .result holds the JSON string.
    parsed = wrapper.get("structured_output")
    raw_result = ""
    if isinstance(parsed, dict):
        raw_result = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
    else:
        raw_result = wrapper.get("result") or ""
        if not isinstance(raw_result, str) or not raw_result.strip():
            raise RuntimeError(f"claude result missing/empty: {wrapper}")
        try:
            parsed = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"claude result is not JSON: {exc}: {raw_result[:1500]}")
    if not isinstance(parsed, dict):
        raise RuntimeError("claude returned non-object result")
    usage = wrapper.get("usage") or {}
    return sp.prune_empty(parsed), usage, raw_result


def claude_usage_to_normalized(usage: dict[str, Any], model_id: str) -> dict[str, Any]:
    prompt_tokens = int(
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )
    completion_tokens = int(usage.get("output_tokens") or 0)
    prices = CLAUDE_PRICES_USD_PER_MTOK.get(model_id, CLAUDE_PRICES_USD_PER_MTOK["claude-sonnet-4-6"])
    cached = int(usage.get("cache_read_input_tokens") or 0)
    fresh_input = max(0, prompt_tokens - cached)
    cost = (
        fresh_input / 1_000_000 * prices["input"]
        + cached / 1_000_000 * prices["cached_input"]
        + completion_tokens / 1_000_000 * prices["output"]
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "reasoning_tokens": 0,
        "cache_read_input_tokens": cached,
        "cache_creation_input_tokens": int(usage.get("cache_creation_input_tokens") or 0),
        "estimated_cost_usd": round(cost, 6),
    }


def build_claude_record(
    *,
    source_path: pathlib.Path,
    english_record: dict[str, Any],
    tool_input: dict[str, Any],
    model_id: str,
    prompt_sha: str,
    raw_output_hash: str,
    usage: dict[str, Any],
) -> dict[str, Any]:
    record = sp.build_spanish_record(
        source_path=source_path,
        english_record=english_record,
        tool_input=tool_input,
        model_id=model_id,
        model_version=model_id,
        prompt_id=PROMPT_ID,
        prompt_sha=prompt_sha,
        raw_output_hash=raw_output_hash,
        usage={},  # we'll overwrite below
        deployment="claude_code_cli",
    )
    # Overwrite ai_draft.usage with our Claude-flavored estimate; mark provenance.
    record["ai_draft"]["usage"] = claude_usage_to_normalized(usage, model_id)
    record["ai_draft"]["provider"] = "anthropic_claude_code_cli"
    record["ai_draft"]["fallback_reason"] = "azure_content_filter"
    return sp.prune_empty(record)


def draft_one_via_claude(
    source_path: pathlib.Path,
    *,
    model: str,
    timeout_seconds: int,
    workdir: pathlib.Path,
    validation_retries: int,
) -> tuple[bool, str]:
    target_path = sp.SPANISH_ROOT / source_path.relative_to(sp.TRANSLATION_ROOT)
    if target_path.exists():
        return True, f"skip-existing {target_path.relative_to(REPO_ROOT)}"
    lock = sp.acquire_lock(target_path, "claude-fallback")
    if lock is None:
        return False, f"locked {target_path.relative_to(REPO_ROOT)}"
    try:
        english_record = sp.safe_load_yaml(source_path)
        user_prompt = sp.build_draft_user_prompt(source_path, english_record)
        validation_note = ""
        last_errors: list[str] = []
        for attempt in range(validation_retries + 1):
            attempt_user = user_prompt + validation_note
            attempt_prompt_sha = sp.sha256_text(sp.DRAFT_SYSTEM_PROMPT + "\n\n---\n\n" + attempt_user)
            tool_input, usage, raw_result = call_claude_cli(
                system_prompt=sp.DRAFT_SYSTEM_PROMPT,
                user_prompt=attempt_user,
                model=model,
                timeout_seconds=timeout_seconds,
                workdir=workdir,
            )
            record = build_claude_record(
                source_path=source_path,
                english_record=english_record,
                tool_input=tool_input,
                model_id=model,
                prompt_sha=attempt_prompt_sha,
                raw_output_hash=sp.sha256_text(raw_result),
                usage=usage,
            )
            sp.write_yaml_atomic(target_path, record)
            errors = sp.validate_spanish_record(target_path)
            if not errors:
                cost = record["ai_draft"]["usage"].get("estimated_cost_usd", 0.0)
                return True, f"OK {target_path.relative_to(REPO_ROOT)} cost=${cost:.4f} attempt={attempt}"
            last_errors = errors
            invalid = target_path.with_suffix(target_path.suffix + f".invalid-{int(time.time())}-{attempt}")
            target_path.replace(invalid)
            validation_note = (
                "\n\n# Previous output failed validation\n"
                f"Errors: {errors}\n"
                "Return a corrected JSON object. Footnotes are allowed only when every "
                "marker like [a] appears verbatim in spanish_text. Use unique markers."
            )
        return False, f"FAIL {target_path.relative_to(REPO_ROOT)} validation_errors={last_errors}"
    except Exception as exc:  # noqa: BLE001
        return False, f"ERROR {target_path.relative_to(REPO_ROOT)} {type(exc).__name__}: {exc}"
    finally:
        sp.release_lock(lock)


def collect_paths(args: argparse.Namespace) -> list[pathlib.Path]:
    raws: list[str] = list(args.path or [])
    if args.input:
        for line in pathlib.Path(args.input).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                raws.append(line)
    out: list[pathlib.Path] = []
    seen: set[str] = set()
    for r in raws:
        try:
            p = normalize_input_path(r)
        except Exception as exc:
            print(f"skip {r!r}: {exc}", file=sys.stderr)
            continue
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude-based fallback for Azure-blocked Spanish POB drafts")
    ap.add_argument("--input", help="File with translation/... paths, one per line")
    ap.add_argument("--path", action="append", help="Repeatable: a translation/... path")
    ap.add_argument("--model", default=CLAUDE_MODEL)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout-seconds", type=int, default=240)
    ap.add_argument("--validation-retries", type=int, default=1)
    ap.add_argument("--workdir", default=tempfile.gettempdir(),
                    help="CWD for claude (kept outside repo so CLAUDE.md isn't auto-loaded)")
    args = ap.parse_args()

    paths = collect_paths(args)
    if not paths:
        print("no input paths", file=sys.stderr)
        return 2

    workdir = pathlib.Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if shutil.which(CLAUDE_BIN) is None:
        print(f"claude binary not found: {CLAUDE_BIN}", file=sys.stderr)
        return 3

    print(f"[claude_es_fallback] paths={len(paths)} model={args.model} workers={args.workers} workdir={workdir}", flush=True)
    ok = 0
    fail = 0
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {
            pool.submit(
                draft_one_via_claude,
                p,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                workdir=workdir,
                validation_retries=args.validation_retries,
            ): p
            for p in paths
        }
        for fut in concurrent.futures.as_completed(futs):
            success, msg = fut.result()
            if success:
                ok += 1
            else:
                fail += 1
            print(f"[{ok+fail}/{len(paths)}] {msg}", flush=True)
    dur = time.time() - started
    print(f"[claude_es_fallback] done ok={ok} fail={fail} elapsed={dur:.1f}s", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
