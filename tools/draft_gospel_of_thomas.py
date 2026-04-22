#!/usr/bin/env python3
"""draft_gospel_of_thomas.py — Coptic-aware redrafter for one Thomas saying.

Reads the existing saying YAML (which already carries the Coptic
source from the Coptic Scriptorium Dilley 2025 edition), builds a
strict Coptic-aware prompt via build_gospel_of_thomas_prompt, calls
Gemini 3.1 Pro (cross-family from the original Azure GPT-5.4
drafter), validates the structured response, and writes the new
translation + lexical decisions + footnotes back into the YAML.

The source block is preserved. The old translation goes into a
`previous_drafts` field so full history survives.

Usage:
  python tools/draft_gospel_of_thomas.py --saying 74
  python tools/draft_gospel_of_thomas.py --saying 74 --dry-run
  python tools/draft_gospel_of_thomas.py --saying-range 1-20

Env:
  GEMINI_API_KEY (from AWS Secrets Manager /cartha/openclaw/gemini_api_key)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from typing import Any

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_gospel_of_thomas_prompt as bp  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_ID = os.environ.get("CARTHA_THOMAS_MODEL", "gemini-3.1-pro-preview")
ADJUDICATOR_LABEL = "gemini_3_1_pro_thomas_redraft"
TEMPERATURE = float(os.environ.get("CARTHA_THOMAS_TEMPERATURE", "0.2"))


# ---------------------------------------------------------------------------
# Structured response schema (the function Gemini must call)
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "english_text",
        "translation_philosophy",
        "lexical_decisions",
        "footnotes",
        "overall_notes",
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
                "required": ["source_word", "chosen", "rationale", "lexicon"],
                "properties": {
                    "source_word": {"type": "string"},
                    "chosen": {"type": "string"},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                    "lexicon": {"type": "string"},
                    "entry": {"type": "string"},
                    "rationale": {"type": "string"},
                },
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
                            "lexical_alternative",
                            "dialect_note",
                            "cultural_note",
                            "textual_variant",
                            "theological_note",
                            "cross_reference",
                            "register_note",
                        ],
                    },
                },
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
                    "alternatives_noted": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
            },
        },
        "overall_notes": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Gemini AI Studio call
# ---------------------------------------------------------------------------


def _fetch_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    # Try AWS Secrets Manager
    import subprocess
    try:
        r = subprocess.run(
            [
                "aws", "secretsmanager", "get-secret-value",
                "--secret-id", "/cartha/openclaw/gemini_api_key",
                "--region", "us-west-2",
                "--query", "SecretString", "--output", "text",
            ],
            capture_output=True, text=True, check=True, timeout=15,
        )
        raw = r.stdout.strip()
        try:
            return json.loads(raw).get("api_key", raw)
        except json.JSONDecodeError:
            return raw
    except Exception:
        return ""


def call_gemini_draft(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = MODEL_ID,
    timeout: int = 90,
    max_retries: int = 4,
) -> dict[str, Any]:
    key = _fetch_gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not available")

    url = f"{AI_STUDIO_BASE}/{model}:generateContent?key={key}"
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    headers = {"Content-Type": "application/json"}

    backoffs = [10, 25, 60, 120]
    last_err: Exception | None = None
    for attempt in range(max_retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
            candidates = resp_body.get("candidates") or []
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates; promptFeedback={resp_body.get('promptFeedback')}")
            cand = candidates[0]
            parts = (cand.get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts)
            return json.loads(text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            last_err = RuntimeError(f"Gemini HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            raise last_err
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = RuntimeError(f"Gemini request failed: {type(exc).__name__}: {exc}")
            if attempt < max_retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            raise last_err
    raise last_err  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Apply the new draft to the YAML
# ---------------------------------------------------------------------------


def write_new_draft(
    bundle: bp.ThomasPromptBundle,
    draft: dict[str, Any],
    *,
    dry_run: bool = False,
) -> None:
    data = dict(bundle.yaml_data)  # shallow copy

    # Preserve previous drafts for provenance
    previous_drafts = data.get("previous_drafts") or []
    prev_translation = (data.get("translation") or {}).get("text")
    if prev_translation:
        previous_drafts.append({
            "archived_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reason": "redraft_coptic_strict",
            "english_text": prev_translation,
            "previous_translation_block": data.get("translation"),
        })

    new_translation: dict[str, Any] = {
        "text": draft.get("english_text", ""),
        "philosophy": draft.get("translation_philosophy", "optimal-equivalence"),
        "drafter_model": MODEL_ID,
        "drafter_label": ADJUDICATOR_LABEL,
        "drafted_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if draft.get("footnotes"):
        new_translation["footnotes"] = draft["footnotes"]

    new_lex = draft.get("lexical_decisions") or []
    new_theo = draft.get("theological_decisions") or []

    # Assemble the new YAML preserving source + id + reference + unit + book
    kept_keys = ["id", "reference", "unit", "book", "source"]
    out: dict[str, Any] = {k: data[k] for k in kept_keys if k in data}
    out["translation"] = new_translation
    if new_lex:
        out["lexical_decisions"] = new_lex
    if new_theo:
        out["theological_decisions"] = new_theo
    if draft.get("overall_notes"):
        out["drafter_notes"] = draft["overall_notes"]
    out["previous_drafts"] = previous_drafts

    # Preserve any pre-existing revisions history from the v3 review pass
    if data.get("revisions"):
        out["revisions"] = data["revisions"]

    if dry_run:
        print(f"--- DRY RUN: saying {bundle.saying} ---")
        print(f"new text: {draft.get('english_text','')!r}")
        print(f"lexical decisions: {len(new_lex)}")
        print(f"footnotes: {len(draft.get('footnotes') or [])}")
        print(f"notes: {(draft.get('overall_notes') or '')[:200]}")
        return

    bundle.yaml_path.write_text(
        yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_saying_arg(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(s)]


def process_one(saying: int, *, dry_run: bool) -> dict[str, Any]:
    t0 = time.time()
    bundle = bp.build_prompt(saying)
    draft = call_gemini_draft(bundle.system_prompt, bundle.user_prompt)
    write_new_draft(bundle, draft, dry_run=dry_run)
    dur = round(time.time() - t0, 1)
    return {
        "saying": saying,
        "duration_s": dur,
        "chars": len(draft.get("english_text", "")),
        "lex": len(draft.get("lexical_decisions") or []),
        "foot": len(draft.get("footnotes") or []),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--saying", type=int, help="Single saying number (0 = incipit, 1-114)")
    group.add_argument("--saying-range", type=str, help="Inclusive range e.g. 1-20")
    group.add_argument("--sayings", type=str, help="Comma-separated list e.g. 8,47,74")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.saying is not None:
        targets = [args.saying]
    elif args.saying_range:
        targets = _parse_saying_arg(args.saying_range)
    else:
        targets = [int(x) for x in args.sayings.split(",")]

    for s in targets:
        try:
            result = process_one(s, dry_run=args.dry_run)
            print(f"[saying {s}] redrafted in {result['duration_s']}s ({result['chars']} chars, {result['lex']} lex, {result['foot']} foot)", flush=True)
        except Exception as exc:
            print(f"[saying {s}] FAILED: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
