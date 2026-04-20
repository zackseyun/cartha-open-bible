#!/usr/bin/env python3
"""measure_wer.py — sampled word-error-rate audit of the Swete corpus.

Parallel to tools/review_transcription.py but with a different prompt
and a different output shape: the model is asked to *count* real
errors and total words on each page, not to list corrections. The
result is a headline WER number for the quality doc.

Env var:
  AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_DEPLOYMENT_ID
  (fetch from AWS Secrets Manager `cartha-azure-openai-key`)

Usage:
  python3 tools/measure_wer.py --vol 2 --pages 148,170 --output-dir sources/lxx/swete/reviews/wer_measurement
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

try:
    import transcribe_source
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import transcribe_source  # type: ignore

REPO_ROOT = transcribe_source.REPO_ROOT
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "wer_measurement"
PROMPT_VERSION = "wer_v1_2026-04-19"
TOOL_NAME = "submit_wer_measurement"

WER_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Submit a measured word-error rate for a Swete page. Count "
            "Greek words in BODY and APPARATUS; list confirmed errors."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "required": [
                "total_body_words",
                "total_apparatus_words",
                "body_errors",
                "apparatus_errors",
                "body_correct",
                "apparatus_correct",
                "note",
            ],
            "properties": {
                "total_body_words": {"type": "integer"},
                "total_apparatus_words": {"type": "integer"},
                "body_errors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["word", "note"],
                        "properties": {
                            "word": {"type": "string"},
                            "note": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "apparatus_errors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["word", "note"],
                        "properties": {
                            "word": {"type": "string"},
                            "note": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "body_correct": {"type": "boolean"},
                "apparatus_correct": {"type": "boolean"},
                "note": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
}


def azure_endpoint() -> str:
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "https://eastus2.api.cognitive.microsoft.com").rstrip("/")


def azure_deployment() -> str:
    return (
        os.environ.get("AZURE_OPENAI_VISION_DEPLOYMENT_ID")
        or os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID")
        or "gpt-5-4-deployment"
    )


def azure_api_version() -> str:
    return os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")


def load_prompt() -> str:
    return (PROMPTS_DIR / "wer_adjudicator_azure.md").read_text(encoding="utf-8")


def call_azure(image_bytes: bytes, system_prompt: str, user_text: str, *, max_tokens: int) -> tuple[dict[str, Any], str]:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    url = f"{azure_endpoint()}/openai/deployments/{azure_deployment()}/chat/completions?api-version={azure_api_version()}"
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
        "temperature": 0.0,
        "max_completion_tokens": max_tokens,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [WER_TOOL],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:600]}") from exc

    choices = body.get("choices") or []
    if len(choices) != 1:
        raise RuntimeError(f"Azure must return 1 choice; got {len(choices)}")
    msg = choices[0].get("message") or {}
    tool_calls = msg.get("tool_calls") or []
    if len(tool_calls) != 1:
        raise RuntimeError(f"Azure must return 1 tool call; got {len(tool_calls)}")
    fn = tool_calls[0].get("function") or {}
    if fn.get("name") != TOOL_NAME:
        raise RuntimeError(f"Azure called unexpected tool: {fn.get('name')!r}")
    args = json.loads(fn.get("arguments") or "{}")
    return args, body.get("model") or azure_deployment()


def process_page(vol: int, page: int, out_dir: pathlib.Path, prompt: str, *, width: int, max_tokens: int) -> dict[str, Any]:
    t_path = TRANSCRIBED_DIR / f"vol{vol}_p{page:04d}.txt"
    if not t_path.exists():
        raise FileNotFoundError(f"missing transcript: {t_path}")
    transcript = t_path.read_text(encoding="utf-8")
    image_bytes, provenance_url = transcribe_source.fetch_swete_image(vol, page, width)
    image_sha = hashlib.sha256(image_bytes).hexdigest()
    started = time.time()
    user_text = (
        f"Measure WER for Swete vol {vol} page {page}. Current transcript:\n\n"
        f"===TRANSCRIPT===\n{transcript}\n===END===\n"
    )
    result, model_id = call_azure(image_bytes, prompt, user_text, max_tokens=max_tokens)
    duration = round(time.time() - started, 2)

    stem = f"vol{vol}_p{page:04d}"
    out_path = out_dir / f"{stem}.wer.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    body_words = result.get("total_body_words", 0)
    body_errs = len(result.get("body_errors", []))
    app_words = result.get("total_apparatus_words", 0)
    app_errs = len(result.get("apparatus_errors", []))

    meta = {
        "stem": stem,
        "vol": vol,
        "page": page,
        "duration_seconds": duration,
        "model": model_id,
        "prompt_version": PROMPT_VERSION,
        "image_sha256": image_sha,
        "provenance_url": provenance_url,
        "measured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "body_words": body_words,
        "body_errors": body_errs,
        "apparatus_words": app_words,
        "apparatus_errors": app_errs,
        "body_wer": (body_errs / body_words) if body_words else None,
        "apparatus_wer": (app_errs / app_words) if app_words else None,
    }
    (out_dir / f"{stem}.wer.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", required=True, type=int, choices=[1, 2, 3])
    ap.add_argument("--page", type=int)
    ap.add_argument("--pages")
    ap.add_argument("--width", type=int, default=1500)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--output-dir")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    pages = transcribe_source.resolve_pages(args.page, args.pages)
    out_dir = pathlib.Path(args.output_dir).resolve() if args.output_dir else DEFAULT_OUTPUT_DIR
    prompt = load_prompt()

    def done(page: int) -> bool:
        return (out_dir / f"vol{args.vol}_p{page:04d}.wer.json").exists()

    todo = [p for p in pages if not (args.skip_existing and done(p))]
    if not todo:
        print("nothing to do")
        return 0

    results = {}

    def worker(page: int):
        try:
            return page, process_page(args.vol, page, out_dir, prompt, width=args.width, max_tokens=args.max_tokens), None
        except Exception as exc:
            return page, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(worker, p) for p in todo]
        for fut in as_completed(futures):
            p, meta, err = fut.result()
            results[p] = (meta, err)
            if err:
                print(f"  FAIL vol{args.vol} p{p:04d}: {err[:300]}", flush=True)
            else:
                bw = meta["body_words"]; be = meta["body_errors"]
                aw = meta["apparatus_words"]; ae = meta["apparatus_errors"]
                bwer = f"{meta['body_wer']*100:.2f}%" if meta["body_wer"] is not None else "-"
                awer = f"{meta['apparatus_wer']*100:.2f}%" if meta["apparatus_wer"] is not None else "-"
                print(
                    f"  OK   vol{args.vol} p{p:04d}  {meta['duration_seconds']:>6.1f}s  "
                    f"body {be}/{bw} ({bwer})  app {ae}/{aw} ({awer})",
                    flush=True,
                )

    n_ok = sum(1 for m, e in results.values() if e is None)
    print(f"\ndone: {n_ok} ok, {len(results)-n_ok} failed; outputs in {out_dir}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
