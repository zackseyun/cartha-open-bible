#!/usr/bin/env python3
"""azure_bulk_revise.py — bulk Azure GPT-5 revision pass for all POB verses.

Scans every verse YAML that lacks a `revision_pass` block and calls
Azure GPT-5 to review and improve the draft translation.

For 1 Enoch verses, automatically loads both the Charles 1906 and Dillmann
1851 Ge'ez witnesses via tools/enoch/multi_witness.py and adds an explicit
completeness check to catch any remaining OCR-truncation blind spots.

Usage:
    python3 tools/azure_bulk_revise.py
    python3 tools/azure_bulk_revise.py --concurrency 20
    python3 tools/azure_bulk_revise.py --testament nt        # nt | ot | extra_canonical
    python3 tools/azure_bulk_revise.py --book 1_enoch        # path substring filter
    python3 tools/azure_bulk_revise.py --dry-run             # count only, no API calls
    python3 tools/azure_bulk_revise.py --limit 5             # slow-ramp: start small
    python3 tools/azure_bulk_revise.py --progress-interval 5 # print every N verses

Env (auto-loaded from AWS Secrets Manager if not set):
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_DEPLOYMENT_ID  (default: gpt-5-deployment)
    AZURE_OPENAI_API_VERSION    (default: 2025-04-01-preview)
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

DEFAULT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-deployment")
DEFAULT_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
MODEL_LABEL = "gpt-5"
ADJUDICATOR_LABEL = "azure-gpt-5-revision-pass"
REVISION_TOOL_NAME = "submit_verse_revision"

MINI_DEPLOYMENT = "gpt-5-4-mini-deployment"
MINI_API_VERSION = "2025-04-01-preview"
MINI_MODEL_LABEL = "gpt-5.4-mini"
MINI_ADJUDICATOR_LABEL = "azure-gpt-5.4-mini-revision-pass"

# Lazily import multi_witness only when needed (avoids boto3/yaml import at module level)
_multi_witness = None

def _get_multi_witness():
    global _multi_witness
    if _multi_witness is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "multi_witness",
            REPO_ROOT / "tools" / "enoch" / "multi_witness.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _multi_witness = mod
    return _multi_witness


def _load_revision_policy() -> str:
    if REVISION_POLICY_FILE.exists():
        return "\n\n" + REVISION_POLICY_FILE.read_text(encoding="utf-8")
    return ""


_BASE_SYSTEM_PROMPT = """You are a biblical translation revisor for the People's Open Bible — \
a transparent, CC-BY 4.0 English Bible translated directly from the original Greek, Hebrew, and Aramaic.

Your job: perform a focused revision pass on one verse's draft English translation.

Review the draft for:
1. Lexical accuracy — does the English faithfully represent the source words and their range?
2. Completeness — are ALL source words accounted for? Do NOT assume completeness just because \
the English reads naturally. Verify every clause in the source has a counterpart in the English.
3. Natural English — is it readable without paraphrase or interpretive expansion?
4. Consistency — are key terms rendered consistently within the verse?
5. Register — is the tone appropriate for a formal translation?

If a SECONDARY WITNESS is provided alongside the primary source, use it to cross-check \
completeness and catch any content present in one witness but absent from the other.

Translation philosophy: optimal equivalence (balanced formal/dynamic).

Do NOT:
- Paraphrase beyond the source text
- Import theological claims not in the source
- Add explanatory expansions that belong in footnotes
- Omit contested alternatives that should be footnoted

If the draft is accurate and natural, submit it unchanged (set unchanged: true).
If you improve it, briefly note what changed in changes_summary.

Call submit_verse_revision exactly once. No other output."""

SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + _load_revision_policy()

REVISION_TOOL = {
    "type": "function",
    "function": {
        "name": REVISION_TOOL_NAME,
        "description": "Submit your revision decision for the verse.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": ["revised_text", "unchanged", "changes_summary"],
            "properties": {
                "revised_text": {
                    "type": "string",
                    "description": (
                        "The revised English translation text. "
                        "If unchanged=true, copy the original exactly."
                    ),
                },
                "unchanged": {
                    "type": "boolean",
                    "description": "True if no changes are needed.",
                },
                "changes_summary": {
                    "type": "string",
                    "description": "Brief summary of changes made, or 'No changes needed.' if unchanged.",
                },
            },
            "additionalProperties": False,
        },
    },
}

# Thread-safe counters
_lock = threading.Lock()
_stats: dict[str, int] = {"processed": 0, "changed": 0, "unchanged": 0, "errors": 0, "skipped": 0}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_azure_credentials(mini: bool = False) -> tuple[str, str]:
    """Return (endpoint, api_key) for the selected model tier."""
    if mini:
        env_ep = os.environ.get("AZURE_MINI_ENDPOINT", "").strip().rstrip("/")
        env_key = os.environ.get("AZURE_MINI_API_KEY", "").strip()
        if env_ep and env_key:
            return env_ep, env_key

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()

    if endpoint and api_key and not mini:
        return endpoint, api_key

    print("Loading Azure credentials from AWS Secrets Manager...", flush=True)
    raw = subprocess.check_output(
        [
            "aws", "secretsmanager", "get-secret-value",
            "--secret-id", "cartha-azure-openai-key",
            "--region", "us-west-2",
            "--query", "SecretString", "--output", "text",
        ],
        text=True,
    ).strip()
    obj = json.loads(raw)

    if mini:
        endpoint = obj.get("mini_endpoint", "").rstrip("/")
        api_key = obj.get("mini_api_key", "")
        if not endpoint or not api_key:
            raise RuntimeError("mini_endpoint / mini_api_key not found in secret")
        os.environ["AZURE_MINI_ENDPOINT"] = endpoint
        os.environ["AZURE_MINI_API_KEY"] = api_key
        os.environ["AZURE_OPENAI_DEPLOYMENT_ID"] = MINI_DEPLOYMENT
        os.environ["AZURE_OPENAI_API_VERSION"] = MINI_API_VERSION
    else:
        endpoint = obj.get("endpoint", "").rstrip("/")
        api_key = obj.get("api_key", "")
        if not endpoint or not api_key:
            raise RuntimeError(f"Incomplete Azure credentials in secret: {list(obj.keys())}")
        os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
        os.environ["AZURE_OPENAI_API_KEY"] = api_key

    print(f"  endpoint: {endpoint[:50]}...", flush=True)
    return endpoint, api_key


def call_azure(
    endpoint: str,
    api_key: str,
    *,
    reference: str,
    source_text: str,
    source_language: str,
    current_translation: str,
    context_block: str = "",
) -> dict[str, Any]:
    """Call Azure GPT-5.4 for a revision pass. Returns parsed tool args."""
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", DEFAULT_DEPLOYMENT)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    user_text = (
        f"Reference: {reference}\n"
        f"Source ({source_language}):\n{source_text}\n\n"
        f"Current draft:\n{current_translation}"
        + context_block
    )

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_completion_tokens": 8000,
        "tool_choice": {"type": "function", "function": {"name": REVISION_TOOL_NAME}},
        "tools": [REVISION_TOOL],
    }

    for attempt in range(6):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"api-key": api_key, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < 5:
                retry_after = int(exc.headers.get("Retry-After", 30 + attempt * 15))
                time.sleep(retry_after)
                continue
            if exc.code in (500, 503) and attempt < 5:
                time.sleep(10 + attempt * 10)
                continue
            raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:300]}")
        except Exception:
            if attempt < 5:
                time.sleep(5 + attempt * 5)
                continue
            raise

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices in response: {str(body)[:200]}")
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        raise RuntimeError(f"No tool calls in response: {str(message)[:200]}")
    fn = tool_calls[0].get("function") or {}
    if fn.get("name") != REVISION_TOOL_NAME:
        raise RuntimeError(f"Wrong tool called: {fn.get('name')!r}")
    args = json.loads(fn.get("arguments", "{}"))
    return args


def needs_revision(data: dict[str, Any]) -> bool:
    return "revision_pass" not in data


def _enoch_witness_block(path: pathlib.Path, data: dict[str, Any]) -> str:
    """Return a Dillmann 1851 context block for 1 Enoch verses, or '' otherwise."""
    if "1_enoch" not in str(path):
        return ""
    ref_id = str(data.get("id") or "")
    # id format: 1EN.{chapter}.{verse}
    parts = ref_id.split(".")
    if len(parts) != 3:
        return ""
    try:
        chapter, verse = int(parts[1]), int(parts[2])
    except ValueError:
        return ""
    try:
        mw = _get_multi_witness()
        ws = mw.load_verse(chapter, verse)
        if ws is None:
            return ""
        dillmann = ws.geez_dillmann
        if dillmann is None:
            return ""
        return (
            f"\n\nDILLMANN 1851 SECONDARY WITNESS (independent Ge'ez edition — "
            f"use to cross-check completeness; spelling variants are normal):\n"
            f"{dillmann.text}"
        )
    except Exception:
        return ""


def revise_verse(
    path: pathlib.Path,
    endpoint: str,
    api_key: str,
) -> dict[str, Any]:
    """Process one verse YAML. Returns result dict."""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
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

    # Skip chapter-level YAMLs (they store source as rows, not text)
    if (data.get("source") or {}).get("rows"):
        return {"path": str(path), "status": "skipped", "reason": "chapter-level yaml"}

    if not current_text:
        return {"path": str(path), "status": "skipped", "reason": "no translation text"}

    # Proceed even without source text — review on English quality only
    if not source_text:
        source_text = "(source text not available for this verse)"
        source_language = str(source.get("language") or "unknown").strip()

    # Build context: lexical decisions, footnotes, prior revisions
    context_parts = []
    lexical = data.get("lexical_decisions") or []
    if lexical:
        lex_lines = []
        for ld in lexical[:6]:  # cap at 6 to stay within token budget
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

    # Append Dillmann secondary witness for 1 Enoch verses
    context_block += _enoch_witness_block(path, data)

    try:
        args = call_azure(
            endpoint,
            api_key,
            reference=reference,
            source_text=source_text,
            source_language=source_language,
            current_translation=current_text,
            context_block=context_block,
        )
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}

    revised_text = str(args.get("revised_text") or "").strip()
    unchanged = bool(args.get("unchanged", False))
    changes_summary = str(args.get("changes_summary") or "").strip()

    if not revised_text:
        return {"path": str(path), "error": "empty revised_text from model"}

    # Build revision_pass block
    revision_pass = {
        "model": MODEL_LABEL,
        "timestamp": utc_now(),
        "unchanged": unchanged,
        "changes_summary": changes_summary,
    }

    # Update data
    data["revision_pass"] = revision_pass

    text_changed = (not unchanged) and (revised_text != current_text)
    if text_changed:
        # Record in revisions array before overwriting
        revisions = data.setdefault("revisions", [])
        revisions.append({
            "timestamp": utc_now(),
            "adjudicator": ADJUDICATOR_LABEL,
            "reviewer_model": MODEL_LABEL,
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

    return {
        "path": str(path),
        "status": "ok",
        "changed": text_changed,
        "changes_summary": changes_summary,
    }


def collect_verse_paths(testaments: list[str]) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for testament in testaments:
        t_dir = TRANSLATION_ROOT / testament
        if not t_dir.exists():
            print(f"  [skip] {t_dir} not found", flush=True)
            continue
        for p in sorted(t_dir.rglob("*.yaml")):
            paths.append(p)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk Azure GPT-5 revision pass")
    parser.add_argument(
        "--testament", "-t",
        nargs="*",
        default=["nt", "ot", "extra_canonical", "deuterocanon"],
        help="Testaments to process (default: all)",
    )
    parser.add_argument(
        "--book",
        default="",
        help="Optional path substring filter, e.g. '1_enoch' or 'matthew'",
    )
    parser.add_argument(
        "--concurrency", "-j",
        type=int,
        default=20,
        help="Parallel Azure calls (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count verses needing revision; no API calls",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N verses (0 = all). Start small to verify.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10,
        help="Print progress every N completed verses (default: 10)",
    )
    parser.add_argument(
        "--mini",
        action="store_true",
        help="Use o3-mini (westus) instead of GPT-5 (eastus2) — faster and cheaper",
    )
    args = parser.parse_args()

    # Select model labels based on --mini flag
    if args.mini:
        global MODEL_LABEL, ADJUDICATOR_LABEL, DEFAULT_DEPLOYMENT, DEFAULT_API_VERSION
        MODEL_LABEL = MINI_MODEL_LABEL
        ADJUDICATOR_LABEL = MINI_ADJUDICATOR_LABEL
        DEFAULT_DEPLOYMENT = MINI_DEPLOYMENT
        DEFAULT_API_VERSION = MINI_API_VERSION

    endpoint, api_key = load_azure_credentials(mini=args.mini)

    print(f"Scanning {args.testament}...", flush=True)
    all_paths = collect_verse_paths(args.testament)

    if args.book:
        all_paths = [p for p in all_paths if args.book in str(p)]
        print(f"  (filtered to paths containing '{args.book}')", flush=True)

    pending = [p for p in all_paths if needs_revision(yaml.safe_load(p.read_text(encoding="utf-8")) or {})]
    total = len(pending)
    print(f"  {len(all_paths)} total YAMLs, {total} need revision pass", flush=True)

    if args.dry_run:
        print("Dry run — exiting without API calls.", flush=True)
        return

    if args.limit and args.limit < total:
        pending = pending[: args.limit]
        print(f"  (limited to {args.limit})", flush=True)

    start = time.monotonic()

    def worker(path: pathlib.Path) -> dict[str, Any]:
        result = revise_verse(path, endpoint, api_key)
        with _lock:
            if result.get("status") == "skipped":
                _stats["skipped"] += 1
            elif "error" in result:
                _stats["errors"] += 1
                print(f"  ERROR {path.name}: {result['error'][:120]}", flush=True)
            else:
                _stats["processed"] += 1
                if result.get("changed"):
                    _stats["changed"] += 1
                else:
                    _stats["unchanged"] += 1
                done = _stats["processed"]
                interval = args.progress_interval if hasattr(args, "progress_interval") else 10
                if done % interval == 0 or done == total:
                    elapsed = time.monotonic() - start
                    rate = done / elapsed * 60 if elapsed > 0 else 0
                    remaining = (total - done) / (done / elapsed) if done and elapsed else 0
                    print(
                        f"  [{done}/{total}] {rate:.0f} v/min "
                        f"changed={_stats['changed']} unchanged={_stats['unchanged']} "
                        f"errors={_stats['errors']} ~{remaining/60:.1f}min left",
                        flush=True,
                    )
        return result

    limit_note = f" limit={args.limit}" if args.limit else ""
    book_note = f" book={args.book}" if args.book else ""
    print(
        f"\nStarting revision pass — model={MODEL_LABEL} deployment={DEFAULT_DEPLOYMENT} "
        f"workers={args.concurrency}{limit_note}{book_note}",
        flush=True,
    )
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
