#!/usr/bin/env python3
"""spanish_summary_writer.py — companion to in-session subagents that
translate English book summaries (BibleSummaryCache-alpha) into Spanish.

The subagent processes one English entry at a time:
  1. Reads /tmp/spanish_summary_inputs/<entry>.json  (frozen English payload)
  2. Generates a Spanish equivalent via its own native inference
  3. Pipes a single-line JSON object to this helper via stdin:

     {"english_input_path": "/tmp/spanish_summary_inputs/0000_DIDACHE_simplify.json",
      "spanish_output": "..."}

This helper resolves the source row, builds the parallel Spanish item
keyed under translation="SPOB" (no schema change to summary_cache.go —
SPOB is a sibling translation token), and writes it to DDB. Spanish
entries reuse the same prompt_version as English so callers querying
the cache from the Spanish reader just substitute the translation
token; everything else lines up.

  english key:  POB |unspecified|book|GENESIS|simplify|bible_shared_summary_v1|gpt-5.4-2026-03-05
  spanish key:  SPOB|unspecified|book|GENESIS|simplify|bible_shared_summary_v1|claude-sonnet-4-6

idempotent: writes are PutItem keyed on summary_key, so retrying a
verse is safe.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import sys

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
TABLE = os.environ.get("CARTHA_SUMMARY_CACHE_TABLE", "BibleSummaryCache-alpha")
SPANISH_TRANSLATION_TOKEN = "SPOB"
SPANISH_MODEL_VERSION = os.environ.get(
    "CARTHA_SPANISH_SUMMARY_MODEL", "claude-sonnet-4-6"
)
SPANISH_PROMPT_VERSION_SUFFIX = ""  # keep aligned with English prompt_version

_dynamo = None


def dynamo_client():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.client("dynamodb", region_name=REGION)
    return _dynamo


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_token(s: str) -> str:
    return (s or "").strip().upper()


def build_spanish_key(en_row: dict) -> str:
    # Mirror summary_cache.go:summaryKeyWithModel exactly, just with the
    # Spanish translation token + Spanish model_version.
    parts = [
        SPANISH_TRANSLATION_TOKEN,
        en_row.get("translation_version") or "unspecified",
        en_row.get("scope") or "book",
        normalize_token(en_row.get("book") or ""),  # scope id for book scope
        en_row.get("tool") or "",
        en_row.get("prompt_version") or "bible_shared_summary_v1",
        SPANISH_MODEL_VERSION,
    ]
    if (en_row.get("scope") or "book") != "book":
        # Chapter scope keys include chapter — book scope does not.
        chapter = en_row.get("chapter") or 0
        parts[3] = f"{normalize_token(en_row.get('book') or '')}.{int(chapter):03d}"
    return "|".join(parts)


def write_spanish_entry(en_row: dict, spanish_text: str) -> str:
    spanish_key = build_spanish_key(en_row)
    item = {
        "summary_key": {"S": spanish_key},
        "translation": {"S": SPANISH_TRANSLATION_TOKEN},
        "translation_version": {"S": en_row.get("translation_version") or "unspecified"},
        "scope": {"S": en_row.get("scope") or "book"},
        "book": {"S": en_row.get("book") or ""},
        "tool": {"S": en_row.get("tool") or ""},
        "output": {"S": spanish_text},
        "prompt_version": {"S": en_row.get("prompt_version") or "bible_shared_summary_v1"},
        "model_version": {"S": SPANISH_MODEL_VERSION},
        "source_hash": {"S": en_row.get("source_hash") or ""},
        "verse_count": {"N": str(en_row.get("verse_count") or 0)},
        "generated_at": {"S": utc_now()},
        "updated_at": {"S": utc_now()},
        # Provenance for the Spanish translation pass — recoverable
        # from the row alone without joining back to English.
        "translated_from": {"S": en_row.get("summary_key") or ""},
        "translated_from_model": {"S": en_row.get("model_version") or ""},
        "translation_pass_method": {"S": "anthropic_claude_code_subagent"},
    }
    if "chapter" in en_row and en_row["chapter"]:
        item["chapter"] = {"N": str(int(en_row["chapter"]))}

    dynamo_client().put_item(TableName=TABLE, Item=item)
    return spanish_key


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

    in_path = payload.get("english_input_path")
    spanish_text = (payload.get("spanish_output") or "").strip()
    if not in_path or not spanish_text:
        print("ERROR missing english_input_path or spanish_output", file=sys.stderr)
        return 2

    try:
        en_row = json.loads(pathlib.Path(in_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR read_input: {exc}", file=sys.stderr)
        return 2

    if len(spanish_text) < 40:
        print(f"ERROR spanish_too_short ({len(spanish_text)} chars)", file=sys.stderr)
        return 2

    key = write_spanish_entry(en_row, spanish_text)
    print(f"OK wrote {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
