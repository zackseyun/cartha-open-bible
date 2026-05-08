#!/usr/bin/env python3
"""azure_phase2_realign.py — Phase 2 English-to-Greek alignment via Azure GPT-5.4.

Phase 2 is alignment, not generic revision. The Greek source.text was
recently corrected for the T12P patriarchs. For each per-verse YAML the
model compares the clean Greek source to the existing English
translation and judges:

    KEEP   — English describes the same content as Greek (allowing for
             natural translation variation).
    REWRITE: <new English> — English is misaligned (different content,
             dropped material, bleed from another verse, contradicts
             Greek). Rewrite to match Greek per v3 author-intent
             principles.

Only `translation.text` is edited. A `revisions[]` entry and a
`phase2_realign_pass` block record what happened.

Files already realigned in commit 6651b98e8e are skipped — they were
done by Claude before quota termination and don't need a second pass.

Usage:
    python3 tools/azure_phase2_realign.py --book joseph
    python3 tools/azure_phase2_realign.py --book joseph --book benjamin
    python3 tools/azure_phase2_realign.py --book joseph --dry-run
    python3 tools/azure_phase2_realign.py --book joseph --limit 3
    python3 tools/azure_phase2_realign.py --book joseph --concurrency 6

Auth: auto-loads from AWS Secrets Manager `cartha-azure-openai-key`
(us-west-2). Same helper as tools/azure_bulk_revise.py.
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
T12P_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "testaments_twelve_patriarchs"

# Reuse Azure config from azure_bulk_revise.py
DEFAULT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", "gpt-5-deployment")
DEFAULT_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
MODEL_LABEL = "gpt-5.4"
ADJUDICATOR_LABEL = "azure-gpt-5.4-phase2-realign"
TOOL_NAME = "submit_alignment_decision"

# Commit whose Joseph + Benjamin edits should be skipped — already done
# by Claude before quota termination. Files touched in this commit have
# already been realigned.
PRIOR_PASS_COMMIT = "6651b98e8edc9bfd3da3455bc024fdf3d5d76e82"


SYSTEM_PROMPT = """You are doing English-to-Greek alignment for the Cartha Open Bible \
Testaments of the Twelve Patriarchs. The Greek source.text has been corrected from \
earlier OCR corruption. Your job is to verify that the existing English translation.text \
describes the same content as the Greek; if not, rewrite the English to match the Greek.

Decision rule:
- If the English clearly describes the same content as the Greek (allowing for natural \
translation variation, idiom adjustment, and minor word-order differences), call \
submit_alignment_decision with action="keep".
- If the English is misaligned — describes different content, has material from another \
verse bled in, drops material that is in the Greek, or contradicts the Greek — call \
submit_alignment_decision with action="rewrite" and provide a new English text that \
matches the Greek.

Translation principles for any rewrite:
- Author-intent: render what the original audience would understand, not what tradition \
softens. Render Χριστός as "Messiah" (never "Christ"). Render δοῦλος as "slave" (never \
"servant").
- Preserve register: testamentary, paraenetic, exhortation tone — the patriarch on his \
deathbed addressing his sons.
- Preserve any Charles 1908 bracketed Christian-interpolation passages [...] verbatim if \
they are in the Greek source — do not delete brackets, do not strip their content.
- Don't add material not in the Greek; don't drop material that is in the Greek.
- Honor the drafter's lexical_decisions — those are conscious editorial choices.

Do NOT propose stylistic improvements. The bar is "does English describe this Greek?" \
— only rewrite when the answer is no. A defensible English rendering of the same Greek \
content stays.

Call submit_alignment_decision exactly once. No other output."""


TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit your alignment decision for the verse.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": ["action", "revised_text", "rationale"],
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["keep", "rewrite"],
                    "description": (
                        "'keep' if the English already describes the same Greek content "
                        "(allowing natural translation variation). 'rewrite' if "
                        "misaligned and needs new English."
                    ),
                },
                "revised_text": {
                    "type": "string",
                    "description": (
                        "If action='rewrite', the new English that matches the Greek. "
                        "If action='keep', copy the original English exactly."
                    ),
                },
                "rationale": {
                    "type": "string",
                    "description": (
                        "Brief reason for the decision. For 'keep': one phrase such as "
                        "'aligned'. For 'rewrite': what was wrong (e.g. 'English describes "
                        "different verse', 'dropped clause about X', 'bleed from verse N')."
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
}


# Thread-safe counters
_lock = threading.Lock()
_stats: dict[str, int] = {
    "processed": 0,
    "kept": 0,
    "rewritten": 0,
    "errors": 0,
    "skipped_prior": 0,
    "skipped_other": 0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_azure_credentials() -> tuple[str, str]:
    """Return (endpoint, api_key) — same as azure_bulk_revise.py."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    if endpoint and api_key:
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
    endpoint = obj.get("endpoint", "").rstrip("/")
    api_key = obj.get("api_key", "")
    if not endpoint or not api_key:
        raise RuntimeError(f"Incomplete Azure credentials in secret: {list(obj.keys())}")
    os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
    os.environ["AZURE_OPENAI_API_KEY"] = api_key
    print(f"  endpoint: {endpoint[:50]}...", flush=True)
    return endpoint, api_key


def get_prior_pass_files() -> set[pathlib.Path]:
    """Return absolute paths touched by PRIOR_PASS_COMMIT — these are
    already realigned and should be skipped."""
    try:
        out = subprocess.check_output(
            ["git", "show", "--name-only", "--pretty=format:", PRIOR_PASS_COMMIT],
            cwd=str(REPO_ROOT),
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Could not read prior commit {PRIOR_PASS_COMMIT}: {exc}")
    paths: set[pathlib.Path] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "joseph/" not in line and "benjamin/" not in line:
            continue
        # only per-verse YAMLs (NNN/VVV.yaml)
        rel = pathlib.Path(line)
        if rel.suffix != ".yaml":
            continue
        # skip chapter-level YAMLs
        if len(rel.parts) < 3:
            continue
        if not rel.parts[-1][:3].isdigit():
            continue
        if not rel.parts[-2].isdigit():
            continue
        paths.add((REPO_ROOT / rel).resolve())
    return paths


def collect_verse_paths(books: list[str]) -> list[pathlib.Path]:
    """Return per-verse YAMLs for the requested books."""
    paths: list[pathlib.Path] = []
    for book in books:
        book_dir = T12P_ROOT / book
        if not book_dir.exists():
            print(f"  [skip] {book_dir} not found", flush=True)
            continue
        for p in sorted(book_dir.rglob("*.yaml")):
            # only per-verse YAMLs (chapter dir / verse file)
            rel = p.relative_to(book_dir)
            if len(rel.parts) != 2:
                continue
            if not rel.parts[0].isdigit():
                continue
            if not rel.parts[1][:3].isdigit():
                continue
            paths.append(p)
    return paths


def call_azure(
    endpoint: str,
    api_key: str,
    *,
    reference: str,
    source_text: str,
    current_translation: str,
    lexical_decisions: list[dict[str, Any]],
    book: str,
) -> dict[str, Any]:
    """Call Azure GPT-5.4 for an alignment decision. Returns parsed tool args."""
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID", DEFAULT_DEPLOYMENT)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    lex_json = "[]"
    if lexical_decisions:
        capped = []
        for ld in lexical_decisions[:6]:
            capped.append({
                "source_word": ld.get("source_word", ""),
                "chosen": ld.get("chosen", ""),
                "alternatives": ld.get("alternatives", []),
                "rationale": str(ld.get("rationale", ""))[:200],
            })
        lex_json = json.dumps(capped, ensure_ascii=False)

    user_text = (
        f"Book: Testament of {book.capitalize()}\n"
        f"Reference: {reference}\n\n"
        f"Greek source:\n{source_text}\n\n"
        f"Existing English:\n{current_translation}\n\n"
        f"Drafter's lexical decisions: {lex_json}"
    )

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_completion_tokens": 8000,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [TOOL],
    }

    last_exc: Exception | None = None
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
        except Exception as exc:
            last_exc = exc
            if attempt < 5:
                time.sleep(5 + attempt * 5)
                continue
            raise
    else:
        if last_exc:
            raise last_exc

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices in response: {str(body)[:200]}")
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        raise RuntimeError(f"No tool calls in response: {str(message)[:200]}")
    fn = tool_calls[0].get("function") or {}
    if fn.get("name") != TOOL_NAME:
        raise RuntimeError(f"Wrong tool called: {fn.get('name')!r}")
    args = json.loads(fn.get("arguments", "{}"))
    return args


def realign_verse(
    path: pathlib.Path,
    endpoint: str,
    api_key: str,
    book: str,
) -> dict[str, Any]:
    """Process one verse YAML. Returns result dict."""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        return {"path": str(path), "error": "not a YAML mapping"}

    source = data.get("source") or {}
    source_text = str(source.get("text") or "").strip()
    translation = data.get("translation") or {}
    current_text = str(translation.get("text") or "").strip()
    reference = str(data.get("reference") or path.stem)

    if not source_text:
        return {"path": str(path), "status": "skipped", "reason": "empty Greek source"}
    if not current_text:
        return {"path": str(path), "status": "skipped", "reason": "no translation text"}

    lexical = data.get("lexical_decisions") or []

    try:
        args = call_azure(
            endpoint,
            api_key,
            reference=reference,
            source_text=source_text,
            current_translation=current_text,
            lexical_decisions=lexical,
            book=book,
        )
    except Exception as exc:
        return {"path": str(path), "error": str(exc)}

    action = str(args.get("action") or "").strip().lower()
    revised_text = str(args.get("revised_text") or "").strip()
    rationale = str(args.get("rationale") or "").strip()

    if action not in ("keep", "rewrite"):
        return {"path": str(path), "error": f"invalid action {action!r}"}
    if not revised_text:
        return {"path": str(path), "error": "empty revised_text"}

    text_changed = (action == "rewrite") and (revised_text != current_text)

    # KEEP path: no write. The decision is implicit in absence of a
    # phase2 entry. This avoids reformatting unchanged YAMLs and
    # minimizes diff noise for review.
    if not text_changed:
        return {
            "path": str(path),
            "status": "ok",
            "action": action,
            "changed": False,
            "rationale": rationale,
        }

    # REWRITE path: append revisions entry, set phase2_realign_pass,
    # update translation.text only.
    revisions = data.setdefault("revisions", [])
    revisions.append({
        "timestamp": utc_now(),
        "adjudicator": ADJUDICATOR_LABEL,
        "reviewer_model": MODEL_LABEL,
        "category": "phase2_english_realignment",
        "from": current_text,
        "to": revised_text,
        "rationale": rationale,
    })
    data["phase2_realign_pass"] = {
        "model": MODEL_LABEL,
        "timestamp": utc_now(),
        "action": action,
        "rationale": rationale,
    }
    if not isinstance(data.get("translation"), dict):
        data["translation"] = {}
    data["translation"]["text"] = revised_text

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=4096),
        encoding="utf-8",
    )

    return {
        "path": str(path),
        "status": "ok",
        "action": action,
        "changed": text_changed,
        "rationale": rationale,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 2 English-to-Greek alignment via Azure GPT-5.4"
    )
    parser.add_argument(
        "--book",
        action="append",
        default=[],
        help="T12P book name (joseph, benjamin). Can repeat. Default: joseph + benjamin",
    )
    parser.add_argument(
        "--concurrency", "-j",
        type=int,
        default=6,
        help="Parallel Azure calls (default: 6 — keep modest for GPT-5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List verses that would be processed; no API calls",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N verses (0 = all)",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=5,
        help="Print progress every N completed verses (default: 5)",
    )
    parser.add_argument(
        "--include-prior-pass",
        action="store_true",
        help="Don't skip files touched in commit 6651b98e8e (NOT recommended)",
    )
    args = parser.parse_args()

    books = args.book or ["joseph", "benjamin"]
    print(f"Books: {books}", flush=True)

    prior_paths = set() if args.include_prior_pass else get_prior_pass_files()
    print(f"Prior-pass files to skip: {len(prior_paths)}", flush=True)

    all_paths = collect_verse_paths(books)
    print(f"  {len(all_paths)} total per-verse YAMLs across {books}", flush=True)

    pending: list[tuple[pathlib.Path, str]] = []
    for p in all_paths:
        if p.resolve() in prior_paths:
            with _lock:
                _stats["skipped_prior"] += 1
            continue
        # determine book from path
        for book in books:
            if f"/{book}/" in str(p):
                pending.append((p, book))
                break

    total = len(pending)
    print(f"  {total} verses pending realignment (after skipping prior-pass)", flush=True)

    if args.dry_run:
        for p, book in pending[:50]:
            print(f"  [{book}] {p.relative_to(REPO_ROOT)}", flush=True)
        if total > 50:
            print(f"  ... and {total - 50} more", flush=True)
        print(f"\nDry run — exiting without API calls.", flush=True)
        return

    if args.limit and args.limit < total:
        pending = pending[: args.limit]
        total = len(pending)
        print(f"  (limited to {args.limit})", flush=True)

    endpoint, api_key = load_azure_credentials()

    start = time.monotonic()

    def worker(item: tuple[pathlib.Path, str]) -> dict[str, Any]:
        path, book = item
        result = realign_verse(path, endpoint, api_key, book)
        with _lock:
            if result.get("status") == "skipped":
                _stats["skipped_other"] += 1
            elif "error" in result:
                _stats["errors"] += 1
                print(f"  ERROR {path.name}: {result['error'][:160]}", flush=True)
            else:
                _stats["processed"] += 1
                if result.get("action") == "rewrite" and result.get("changed"):
                    _stats["rewritten"] += 1
                else:
                    _stats["kept"] += 1
                done = _stats["processed"]
                if done % args.progress_interval == 0 or done == total:
                    elapsed = time.monotonic() - start
                    rate = done / elapsed * 60 if elapsed > 0 else 0
                    remaining = (total - done) / (done / elapsed) if done and elapsed else 0
                    print(
                        f"  [{done}/{total}] {rate:.0f} v/min "
                        f"kept={_stats['kept']} rewritten={_stats['rewritten']} "
                        f"errors={_stats['errors']} ~{remaining/60:.1f}min left",
                        flush=True,
                    )
        return result

    print(
        f"\nStarting Phase 2 realign — model={MODEL_LABEL} "
        f"deployment={DEFAULT_DEPLOYMENT} workers={args.concurrency}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker, item): item for item in pending}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                p = futures[fut][0]
                print(f"  EXCEPTION {p}: {exc}", flush=True)

    elapsed = time.monotonic() - start
    print(
        f"\nDone in {elapsed/60:.1f} min. "
        f"processed={_stats['processed']} kept={_stats['kept']} "
        f"rewritten={_stats['rewritten']} errors={_stats['errors']} "
        f"skipped_prior={_stats['skipped_prior']} skipped_other={_stats['skipped_other']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
