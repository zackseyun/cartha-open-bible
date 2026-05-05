#!/usr/bin/env python3
"""gemini_bulk_revise.py — Gemini 3.1 Pro revision pass for verses skipped by Azure.

Handles two cases:
  1. Verses Azure content-filtered (HTTP 400) — violent/sensitive passages
  2. Any verse still missing a revision_pass block

Uses the same revision_policy.md constraints and submit_verse_revision schema
as azure_bulk_revise.py, but via Gemini 3.1 Pro.

Usage:
    python3 tools/gemini_bulk_revise.py                     # all missing
    python3 tools/gemini_bulk_revise.py --testament extra_canonical
    python3 tools/gemini_bulk_revise.py --dry-run
    python3 tools/gemini_bulk_revise.py --concurrency 5
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
REVISION_POLICY_FILE = REPO_ROOT / "tools" / "prompts" / "revision_policy.md"

GEMINI_MODEL = "gemini-3.1-pro-preview"
AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_lock = threading.Lock()
_stats: dict[str, int] = {
    "processed": 0, "changed": 0, "unchanged": 0, "errors": 0, "skipped": 0
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_policy() -> str:
    if REVISION_POLICY_FILE.exists():
        return "\n\n" + REVISION_POLICY_FILE.read_text(encoding="utf-8")
    return ""


SYSTEM_PROMPT = """You are a biblical translation revisor for the People's Open Bible — \
a transparent, CC-BY 4.0 English Bible translated directly from the original Greek, Hebrew, and Aramaic.

Your job: perform a focused revision pass on one verse's draft English translation.

Review the draft for:
1. Lexical accuracy — does the English faithfully represent the source words and their range?
2. Completeness — are all source words accounted for (no unintended omissions)?
3. Natural English — is it readable without paraphrase or interpretive expansion?
4. Consistency — are key terms rendered consistently within the verse?
5. Register — is the tone appropriate for a formal translation?

Translation philosophy: optimal equivalence (balanced formal/dynamic).

Do NOT:
- Paraphrase beyond the source text
- Import theological claims not in the source
- Add explanatory expansions that belong in footnotes
- Omit contested alternatives that should be footnoted

If the draft is accurate and natural, respond with unchanged=true.
If you improve it, briefly note what changed in changes_summary.

Respond with valid JSON only — no markdown fences, no commentary:
{
  "revised_text": "<full revised translation>",
  "unchanged": true|false,
  "changes_summary": "<brief note or 'No changes needed.'>"
}""" + load_policy()


def resolve_gemini_key() -> str:
    env = os.environ.get("GEMINI_API_KEY", "").strip()
    if env:
        return env
    raw = subprocess.check_output([
        "aws", "secretsmanager", "get-secret-value",
        "--secret-id", "/cartha/openclaw/gemini_api_key",
        "--region", "us-west-2",
        "--query", "SecretString", "--output", "text",
    ], text=True).strip()
    obj = json.loads(raw)
    # Secret stores either "api_key" (single) or "api_keys" (list — use first)
    if "api_key" in obj:
        return obj["api_key"]
    keys = obj.get("api_keys", [])
    return keys[0] if isinstance(keys, list) else str(keys)


def call_gemini(api_key: str, reference: str, source_text: str,
                source_language: str, current_translation: str,
                context_block: str = "") -> dict[str, Any]:
    url = f"{AI_STUDIO_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"

    user_text = (
        f"Reference: {reference}\n"
        f"Source ({source_language}):\n{source_text}\n\n"
        f"Current draft:\n{current_translation}"
        + context_block
    )

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 4096,
            "temperature": 0.1,
        },
    }

    for attempt in range(6):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read())
            candidates = resp.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"no candidates: {str(resp)[:200]}")
            parts = candidates[0].get("content", {}).get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts).strip()
            if not raw_text:
                raise RuntimeError("empty response from Gemini")
            # Strip markdown fences if present
            raw_text = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(raw_text)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code in (429, 500, 503) and attempt < 5:
                wait = 20 + attempt * 15
                print(f"    [retry {attempt+1}] HTTP {e.code}, sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}")
        except Exception as exc:
            if attempt < 5:
                time.sleep(5 + attempt * 5)
                continue
            raise
    raise RuntimeError("exhausted retries")


def needs_revision(data: dict[str, Any]) -> bool:
    return "revision_pass" not in data


def revise_verse(path: pathlib.Path, api_key: str) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return {"path": str(path), "error": f"yaml: {e}"}

    if not isinstance(data, dict):
        return {"path": str(path), "error": "not a YAML mapping"}

    if not needs_revision(data):
        return {"path": str(path), "status": "skipped"}

    source = data.get("source") or {}
    source_text = str(source.get("text") or "").strip()
    source_language = str(source.get("language") or "Greek").strip()
    translation = data.get("translation") or {}
    current_text = str(translation.get("text") or "").strip()
    reference = str(data.get("reference") or path.stem)

    if not source_text or not current_text:
        return {"path": str(path), "error": "missing source or translation text"}

    context_parts = []
    lexical = data.get("lexical_decisions") or []
    if lexical:
        lex_lines = []
        for ld in lexical[:6]:
            word = ld.get("source_word", "")
            chosen = ld.get("chosen", "")
            rationale = str(ld.get("rationale") or "")[:200]
            alts = ", ".join(ld.get("alternatives") or [])
            lex_lines.append(f"  {word} → '{chosen}' (alts: {alts})\n    Rationale: {rationale}")
        context_parts.append("ESTABLISHED LEXICAL DECISIONS (do not override these):\n" + "\n".join(lex_lines))
    footnotes = (translation.get("footnotes") or [])
    if footnotes:
        fn_lines = [f"  [{f.get('marker')}] {str(f.get('text',''))[:150]}" for f in footnotes[:4]]
        context_parts.append("TRANSLATION FOOTNOTES (reflect translator intent):\n" + "\n".join(fn_lines))
    prior_revisions = data.get("revisions") or []
    if prior_revisions:
        last = prior_revisions[-1]
        context_parts.append(
            f"MOST RECENT REVISION ({last.get('adjudicator','?')}):\n"
            f"  Changed: {str(last.get('from',''))[:100]!r}\n"
            f"  To:      {str(last.get('to',''))[:100]!r}\n"
            f"  Reason:  {str(last.get('rationale',''))[:150]}"
        )
    context_block = ("\n\n" + "\n\n".join(context_parts)) if context_parts else ""

    try:
        result = call_gemini(
            api_key,
            reference=reference,
            source_text=source_text,
            source_language=source_language,
            current_translation=current_text,
            context_block=context_block,
        )
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}

    revised_text = str(result.get("revised_text") or "").strip()
    unchanged = bool(result.get("unchanged", False))
    changes_summary = str(result.get("changes_summary") or "").strip()

    if not revised_text:
        return {"path": str(path), "error": "empty revised_text from Gemini"}

    revision_pass = {
        "model": GEMINI_MODEL,
        "timestamp": utc_now(),
        "unchanged": unchanged,
        "changes_summary": changes_summary,
    }
    data["revision_pass"] = revision_pass

    text_changed = (not unchanged) and (revised_text != current_text)
    if text_changed:
        revisions = data.setdefault("revisions", [])
        revisions.append({
            "timestamp": utc_now(),
            "adjudicator": f"gemini-{GEMINI_MODEL}-revision-pass",
            "reviewer_model": GEMINI_MODEL,
            "category": "revision_pass",
            "from": current_text,
            "to": revised_text,
            "rationale": changes_summary,
        })
        data["translation"]["text"] = revised_text

    data["status"] = "revised"

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {"path": str(path), "status": "ok", "changed": text_changed, "changes_summary": changes_summary}


def collect_paths(testaments: list[str]) -> list[pathlib.Path]:
    paths = []
    for t in testaments:
        t_dir = TRANSLATION_ROOT / t
        if not t_dir.exists():
            print(f"  [skip] {t_dir} not found", flush=True)
            continue
        for p in sorted(t_dir.rglob("*.yaml")):
            paths.append(p)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini 3.1 Pro revision pass fallback")
    parser.add_argument("--testament", "-t", nargs="*",
                        default=["nt", "ot", "extra_canonical", "deuterocanon"])
    parser.add_argument("--concurrency", "-j", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    api_key = resolve_gemini_key()

    print(f"Scanning {args.testament}...", flush=True)
    all_paths = collect_paths(args.testament)

    def safe_load(p: pathlib.Path):
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    pending = [p for p in all_paths if needs_revision(safe_load(p))]
    total = len(pending)
    print(f"  {len(all_paths)} total YAMLs, {total} need Gemini revision pass", flush=True)

    if args.dry_run:
        print("Dry run — exiting.", flush=True)
        return

    if args.limit and args.limit < total:
        pending = pending[:args.limit]
        print(f"  (limited to {args.limit})", flush=True)

    start = time.monotonic()

    def worker(path: pathlib.Path) -> dict[str, Any]:
        result = revise_verse(path, api_key)
        with _lock:
            if result.get("status") == "skipped":
                _stats["skipped"] += 1
            elif "error" in result:
                _stats["errors"] += 1
                print(f"  ERROR {path.name}: {result['error'][:100]}", flush=True)
            else:
                _stats["processed"] += 1
                if result.get("changed"):
                    _stats["changed"] += 1
                else:
                    _stats["unchanged"] += 1
                done = _stats["processed"]
                if done % 50 == 0:
                    elapsed = time.monotonic() - start
                    rate = done / elapsed * 60
                    remaining = (total - done) / (done / elapsed) if done else 0
                    print(
                        f"  [{done}/{total}] {rate:.0f}/min "
                        f"changed={_stats['changed']} errors={_stats['errors']} "
                        f"~{remaining/60:.1f}min remaining",
                        flush=True,
                    )
        return result

    print(f"\nStarting Gemini revision pass ({args.concurrency} workers)...", flush=True)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker, p): p for p in pending}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                p = futures[fut]
                print(f"  EXCEPTION {p}: {exc}", flush=True)

    elapsed = time.monotonic() - start
    print(
        f"\nDone in {elapsed/60:.1f} min. "
        f"processed={_stats['processed']} changed={_stats['changed']} "
        f"unchanged={_stats['unchanged']} errors={_stats['errors']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
