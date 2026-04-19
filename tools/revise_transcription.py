#!/usr/bin/env python3
"""revise_transcription.py — Claude Opus 4.7 second-reader for Swete scans.

For each page already transcribed by GPT-5.4 via transcribe_source.py,
ask Opus 4.7 (via OpenRouter, which serves anthropic/claude-opus-4.7
with vision) to independently transcribe the same scan image. Writes
the Opus transcription to a `.opus.txt` sidecar and emits a
`.revision.json` summary with a line-level diff against the GPT-5.4
output so disagreements become a manageable worklist.

This is the second-pass step called out in DEUTEROCANONICAL.md Phase B
('multi-model cross-check + disagreement queue') and the remediation
pathway named in TRANSCRIPTION_QUALITY.md. Different model + same
pixels = different failure modes, which is what makes cross-read
catch the random character-level errors a same-model rerun can't.

Env vars:
  OPENROUTER_API_KEY          required
  REVISER_MODEL               default: anthropic/claude-opus-4.7

Usage:
  tools/revise_transcription.py --vol 2 --page 650
  tools/revise_transcription.py --vol 2 --pages 626-665 --concurrency 3
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import difflib
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
PROMPT_VERSION = "transcribe_v1_2026-04-18"  # same prompt as the GPT-5.4 pass — apples-to-apples

SWETE_ARCHIVE_ITEM = "theoldtestamenti03swetuoft_202003"
SWETE_VOL_BASENAME = {
    1: "oldtestamentingr01swet",
    2: "oldtestamentingr02swet",
    3: "theoldtestamenti03swetuoft",
}
SWETE_PAGE_URL = "https://archive.org/download/{item}/{basename}/page/n{page}_w{width}.jpg"

DEFAULT_MODEL = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-7")
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-west-2")


def fetch_swete_image(vol: int, page: int, width: int) -> tuple[bytes, str]:
    url = SWETE_PAGE_URL.format(item=SWETE_ARCHIVE_ITEM, basename=SWETE_VOL_BASENAME[vol], page=page, width=width)
    req = urllib.request.Request(url, headers={"User-Agent": "cartha-open-bible/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), url


def call_bedrock_opus(image_bytes: bytes, system_prompt: str, *, model: str, region: str, max_tokens: int = 4000) -> tuple[str, str]:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 required. pip install boto3") from exc
    client = boto3.client("bedrock-runtime", region_name=region)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "system": system_prompt,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": "Transcribe this page following the instructions exactly."},
            ],
        }],
    }
    resp = client.invoke_model(
        modelId=model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    parsed = json.loads(resp["body"].read())
    text_parts = [b["text"] for b in parsed.get("content", []) if b.get("type") == "text"]
    text = "\n".join(text_parts)
    return text, parsed.get("model", model)


def extract_body(page_text: str) -> str:
    """Match lxx_swete.extract_body — concatenate [BODY] sections."""
    bodies = re.findall(r"\[BODY\]\s*\n(.*?)(?=\n\[(?:APPARATUS|MARGINALIA|RUNNING HEAD|PLATE|BLANK)\]|\Z)", page_text, re.DOTALL)
    return "\n\n".join(b.strip() for b in bodies).strip()


def normalize_for_diff(s: str) -> str:
    """NFC-normalize + collapse whitespace so cosmetic noise doesn't dominate the diff."""
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n+", "\n", s)
    return s.strip()


def body_diff(gpt_text: str, opus_text: str) -> dict:
    """Produce a structured diff focused on BODY sections (where real errors matter)."""
    gpt_body = normalize_for_diff(extract_body(gpt_text))
    opus_body = normalize_for_diff(extract_body(opus_text))
    sm = difflib.SequenceMatcher(None, gpt_body, opus_body, autojunk=False)
    ratio = sm.ratio()
    # Collect all non-equal diff hunks with surrounding context
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ctx_before = gpt_body[max(0, i1-30):i1]
        ctx_after = gpt_body[i2:min(len(gpt_body), i2+30)]
        hunks.append({
            "tag": tag,
            "gpt": gpt_body[i1:i2],
            "opus": opus_body[j1:j2],
            "context_before": ctx_before,
            "context_after": ctx_after,
        })
    return {
        "body_similarity_ratio": round(ratio, 4),
        "gpt_body_len": len(gpt_body),
        "opus_body_len": len(opus_body),
        "hunk_count": len(hunks),
        "hunks": hunks,
    }


def severity_flag(diff: dict) -> str:
    r = diff["body_similarity_ratio"]
    if r >= 0.99: return "clean"
    if r >= 0.97: return "minor"
    if r >= 0.93: return "notable"
    return "major"


def process_page(vol: int, page: int, out_dir: pathlib.Path, prompt: str, width: int, model: str, region: str) -> dict:
    stem = f"vol{vol}_p{page:04d}"
    gpt_txt_path = out_dir / f"{stem}.txt"
    if not gpt_txt_path.exists():
        raise RuntimeError(f"no prior GPT-5.4 transcription at {gpt_txt_path}")
    gpt_text = gpt_txt_path.read_text(encoding="utf-8")

    image_bytes, provenance_url = fetch_swete_image(vol, page, width)
    image_sha = hashlib.sha256(image_bytes).hexdigest()
    started = time.time()
    opus_text, model_id = call_bedrock_opus(image_bytes, prompt, model=model, region=region)
    duration = round(time.time() - started, 2)

    (out_dir / f"{stem}.opus.txt").write_text(opus_text, encoding="utf-8")
    diff = body_diff(gpt_text, opus_text)
    flag = severity_flag(diff)

    meta = {
        "vol": vol,
        "page": page,
        "image_sha256": image_sha,
        "provenance_url": provenance_url,
        "reviewer_model": model_id,
        "reviewer_deployment": model,
        "reviewer_region": region,
        "reviewer_role": "cross-read",
        "primary_model": "gpt-5.4-2026-03-05",
        "primary_deployment": "gpt-5-4-deployment",
        "prompt_version": PROMPT_VERSION,
        "reviewed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "severity": flag,
        **diff,
    }
    (out_dir / f"{stem}.revision.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def resolve_pages(page_arg, pages_arg):
    if page_arg is not None:
        return [page_arg]
    pages = []
    for chunk in pages_arg.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            pages.extend(range(int(a), int(b)+1))
        else:
            pages.append(int(chunk))
    return pages


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="swete", choices=["swete"])
    p.add_argument("--vol", type=int, required=True, choices=[1, 2, 3])
    p.add_argument("--page", type=int)
    p.add_argument("--pages", help="Range(s), e.g. '626-665' or '626,650,665'")
    p.add_argument("--width", type=int, default=1500)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--skip-existing", action="store_true")
    args = p.parse_args()

    pages = resolve_pages(args.page, args.pages)
    out_dir = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
    prompt = (PROMPTS_DIR / "transcribe_greek_swete.md").read_text(encoding="utf-8")

    todo = [pg for pg in pages if not (args.skip_existing and (out_dir / f"vol{args.vol}_p{pg:04d}.revision.json").exists())]
    if len(pages) != len(todo):
        print(f"skipping {len(pages)-len(todo)} already-reviewed page(s)", flush=True)

    def worker(page):
        try:
            return page, process_page(args.vol, page, out_dir, prompt, args.width, args.model, args.region), None
        except Exception as e:
            return page, None, f"{type(e).__name__}: {e}"

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = [ex.submit(worker, pg) for pg in todo]
        for f in as_completed(futs):
            page, meta, err = f.result()
            results.append((page, meta, err))
            if err:
                print(f"  FAIL p{page}: {err[:250]}", flush=True)
            else:
                print(f"  {meta['severity']:<7} p{page:>4}  sim={meta['body_similarity_ratio']:.4f}  hunks={meta['hunk_count']:>2}  {meta['duration_seconds']:>5.1f}s", flush=True)

    n_ok = sum(1 for _, m, e in results if e is None)
    n_fail = len(results) - n_ok
    # aggregate severity breakdown
    sev = {"clean": 0, "minor": 0, "notable": 0, "major": 0}
    for _, m, e in results:
        if m: sev[m["severity"]] += 1
    print(f"\nreviewed {n_ok} pages ({n_fail} failed)   severity: clean={sev['clean']} minor={sev['minor']} notable={sev['notable']} major={sev['major']}", flush=True)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
