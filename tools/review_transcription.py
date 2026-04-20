#!/usr/bin/env python3
"""review_transcription.py — Azure GPT-5.4 reviewer for existing Swete transcriptions.

This is the Azure-native follow-on to the first-pass transcription run:
instead of re-transcribing a page from scratch, it shows GPT-5.4 the page
image plus the existing transcript and asks for *corrections only* via a
strict function call.

Outputs:
- <stem>.review.json      structured correction payload
- <stem>.review.meta.json provenance + runtime metadata

Default output directory:
  sources/lxx/swete/reviews/azure/

Usage:
  python3 tools/review_transcription.py --vol 2 --page 650
  python3 tools/review_transcription.py --vol 2 --pages 626-665 --concurrency 5
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
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("review_transcription.py must run from the repo's tools/ context") from exc

REPO_ROOT = transcribe_source.REPO_ROOT
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "azure"
PROMPT_VERSION = "review_v1_2026-04-19"
TOOL_NAME = "submit_transcription_review"

SECTION_VALUES = ["BODY", "APPARATUS", "RUNNING HEAD", "MARGINALIA"]
SEVERITY_VALUES = ["meaning-altering", "grammatical", "cosmetic"]
CONFIDENCE_VALUES = ["high", "medium", "low"]
CATEGORY_VALUES = [
    "apparatus-merge",
    "missing-prefix",
    "missing-letter",
    "extra-letter",
    "accent",
    "breathing",
    "name-misread",
    "case",
    "line-number-captured-as-verse",
    "missing-phrase",
    "punctuation",
    "siglum-decode",
    "nomen-sacrum",
    "other",
]

REVIEW_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Submit a page-level transcription review for a Swete LXX scan. "
            "Report only real transcript mistakes plus genuinely uncertain items."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "required": [
                "running_head_match",
                "body_correct",
                "apparatus_correct",
                "corrections",
                "uncertain",
                "notes",
            ],
            "properties": {
                "running_head_match": {"type": "boolean"},
                "body_correct": {"type": "boolean"},
                "apparatus_correct": {"type": "boolean"},
                "corrections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "section",
                            "location",
                            "current",
                            "correct",
                            "severity",
                            "category",
                            "confidence",
                            "note",
                        ],
                        "properties": {
                            "section": {"type": "string", "enum": SECTION_VALUES},
                            "location": {"type": "string"},
                            "current": {"type": "string"},
                            "correct": {"type": "string"},
                            "severity": {"type": "string", "enum": SEVERITY_VALUES},
                            "category": {"type": "string", "enum": CATEGORY_VALUES},
                            "confidence": {"type": "string", "enum": CONFIDENCE_VALUES},
                            "note": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "uncertain": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["location", "note"],
                        "properties": {
                            "location": {"type": "string"},
                            "note": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "notes": {"type": "string"},
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
    return (PROMPTS_DIR / "review_greek_swete_azure.md").read_text(encoding="utf-8")


def review_output_dir(override: str | None) -> pathlib.Path:
    return pathlib.Path(override).resolve() if override else DEFAULT_OUTPUT_DIR


def transcript_path(vol: int, page: int) -> pathlib.Path:
    return TRANSCRIBED_DIR / f"vol{vol}_p{page:04d}.txt"


def review_paths(out_dir: pathlib.Path, vol: int, page: int) -> tuple[pathlib.Path, pathlib.Path]:
    stem = f"vol{vol}_p{page:04d}"
    return out_dir / f"{stem}.review.json", out_dir / f"{stem}.review.meta.json"


def canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_prompt(vol: int, page: int, transcript_text: str) -> str:
    return (
        f"Review Swete volume {vol}, scan page {page}, against the existing transcription below. "
        "Find transcription mistakes only. Preserve anything already correct.\n\n"
        "===EXISTING TRANSCRIPTION===\n"
        f"{transcript_text}\n"
        "===END TRANSCRIPTION===\n"
    )


def call_azure_review(image_bytes: bytes, system_prompt: str, user_text: str, *, max_tokens: int) -> tuple[dict[str, Any], str, str]:
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
        "tools": [REVIEW_TOOL],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:600]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Azure request failed: {exc}") from exc

    choices = body.get("choices") or []
    if len(choices) != 1:
        raise RuntimeError(f"Azure must return exactly one choice; got {len(choices)}")

    message = choices[0].get("message") or {}
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
        raise RuntimeError("Azure returned assistant prose in addition to the function call")

    tool_calls = message.get("tool_calls") or []
    if len(tool_calls) != 1:
        raise RuntimeError(f"Azure must return exactly one tool call; got {len(tool_calls)}")
    tool_call = tool_calls[0]
    function = tool_call.get("function") or {}
    if tool_call.get("type") != "function" or function.get("name") != TOOL_NAME:
        raise RuntimeError(f"Azure called unexpected tool: {function.get('name')!r}")

    raw_arguments = function.get("arguments") or "{}"
    try:
        parsed_arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Tool-call arguments were not valid JSON: {exc}") from exc

    model_version = str(body.get("model") or azure_deployment())
    return parsed_arguments, model_version, raw_arguments


def process_page(vol: int, page: int, out_dir: pathlib.Path, prompt: str, *, width: int, max_tokens: int) -> dict[str, Any]:
    t_path = transcript_path(vol, page)
    if not t_path.exists():
        raise FileNotFoundError(f"missing transcript: {t_path}")

    transcript_text = t_path.read_text(encoding="utf-8")
    image_bytes, provenance_url = transcribe_source.fetch_swete_image(vol, page, width)
    image_sha = hashlib.sha256(image_bytes).hexdigest()

    started = time.time()
    review, model_id, raw_arguments = call_azure_review(
        image_bytes,
        prompt,
        user_prompt(vol, page, transcript_text),
        max_tokens=max_tokens,
    )
    duration = round(time.time() - started, 2)

    out_path, meta_path = review_paths(out_dir, vol, page)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    meta = {
        "source": "swete",
        "vol": vol,
        "page": page,
        "transcript_path": str(t_path.relative_to(REPO_ROOT)),
        "output_path": str(out_path.relative_to(REPO_ROOT)),
        "image_width_px": width,
        "image_sha256": image_sha,
        "image_bytes": len(image_bytes),
        "provenance_url": provenance_url,
        "model": model_id,
        "deployment": azure_deployment(),
        "api_version": azure_api_version(),
        "prompt_version": PROMPT_VERSION,
        "reviewed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "transcript_sha256": sha256_hex(transcript_text),
        "raw_arguments_sha256": sha256_hex(raw_arguments),
        "corrections": len(review.get("corrections") or []),
        "uncertain": len(review.get("uncertain") or []),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vol", required=True, type=int, choices=[1, 2, 3], help="Swete volume")
    parser.add_argument("--page", type=int, help="Single scan page")
    parser.add_argument("--pages", help="Range(s), e.g. '626-665' or '148-192,626-665'")
    parser.add_argument("--width", type=int, default=1500, help="Image width in pixels (default 1500)")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--max-completion-tokens", type=int, default=4000)
    parser.add_argument("--output-dir", help="Override review output directory")
    parser.add_argument("--skip-existing", action="store_true", help="Skip pages whose .review.json already exists")
    parser.add_argument("--dry-run", action="store_true", help="Show the pages that would be reviewed")
    args = parser.parse_args()

    try:
        pages = transcribe_source.resolve_pages(args.page, args.pages)
    except ValueError as exc:
        parser.error(str(exc))

    out_dir = review_output_dir(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = load_prompt()

    def already_done(page: int) -> bool:
        out_path, _ = review_paths(out_dir, args.vol, page)
        return out_path.exists()

    todo = [pg for pg in pages if not (args.skip_existing and already_done(pg))]
    skipped = len(pages) - len(todo)

    if args.dry_run:
        print(f"would review {len(todo)} page(s) into {out_dir}")
        for pg in todo:
            print(f"  vol{args.vol} p{pg:04d}")
        if skipped:
            print(f"skipping {skipped} existing page(s)")
        return 0

    results: dict[int, tuple[dict[str, Any] | None, str | None]] = {}

    def worker(page: int):
        try:
            return page, process_page(
                args.vol,
                page,
                out_dir,
                prompt,
                width=args.width,
                max_tokens=args.max_completion_tokens,
            ), None
        except Exception as exc:  # pragma: no cover
            return page, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(worker, page) for page in todo]
        for future in as_completed(futures):
            page, meta, err = future.result()
            results[page] = (meta, err)
            if err:
                print(f"  FAIL vol{args.vol} p{page:04d}: {err[:400]}", flush=True)
            else:
                print(
                    f"  OK   vol{args.vol} p{page:04d}  {meta['duration_seconds']:>6.1f}s  "
                    f"{meta['corrections']:>2d} corr  {meta['uncertain']:>2d} uncertain",
                    flush=True,
                )

    n_ok = sum(1 for meta, err in results.values() if err is None)
    n_fail = len(results) - n_ok
    print(
        f"\ndone: {n_ok} ok, {n_fail} failed, {skipped} skipped; reviews in {out_dir}",
        flush=True,
    )
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
