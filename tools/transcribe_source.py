#!/usr/bin/env python3
"""transcribe_source.py — Vision-based transcription of Swete LXX and Schechter Hebrew Sirach pages.

Produces clean UTF-8 polytonic Greek (Swete) or Hebrew (Schechter) from
archival scan images via Azure GPT-5.4 vision. Each page yields a `.txt`
transcript and a `.meta.json` provenance sidecar (image SHA-256, source
URL, model, timestamp, prompt version).

Env vars:
  AZURE_OPENAI_API_KEY          required
  AZURE_OPENAI_ENDPOINT         default: https://eastus2.api.cognitive.microsoft.com
  AZURE_OPENAI_VISION_DEPLOYMENT_ID  default: gpt-5-4-deployment
  AZURE_OPENAI_API_VERSION      default: 2025-04-01-preview

Usage:
  tools/transcribe_source.py --source swete --vol 2 --page 60
  tools/transcribe_source.py --source swete --vol 2 --pages 60-70 --concurrency 5
  tools/transcribe_source.py --source schechter --page 12
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

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
PROMPT_VERSION = "transcribe_v1_2026-04-18"

SWETE_ARCHIVE_ITEM = "theoldtestamenti03swetuoft_202003"
SWETE_VOL_BASENAME = {
    1: "oldtestamentingr01swet",
    2: "oldtestamentingr02swet",
    3: "theoldtestamenti03swetuoft",
}
SWETE_PAGE_URL_TEMPLATE = (
    "https://archive.org/download/{item}/{basename}/page/n{page}_w{width}.jpg"
)

SCHECHTER_PDF = REPO_ROOT / "sources" / "hebrew_sirach" / "schechter_1899" / "schechter_1899.pdf"


def azure_endpoint() -> str:
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "https://eastus2.api.cognitive.microsoft.com").rstrip("/")


def azure_deployment() -> str:
    return os.environ.get("AZURE_OPENAI_VISION_DEPLOYMENT_ID", "gpt-5-4-deployment")


def azure_api_version() -> str:
    return os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")


def fetch_swete_image(vol: int, page: int, width: int) -> tuple[bytes, str]:
    basename = SWETE_VOL_BASENAME[vol]
    url = SWETE_PAGE_URL_TEMPLATE.format(item=SWETE_ARCHIVE_ITEM, basename=basename, page=page, width=width)
    req = urllib.request.Request(url, headers={"User-Agent": "cartha-open-bible/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), url


def fetch_schechter_image(page: int, width: int) -> tuple[bytes, str]:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF required for Schechter PDF extraction. pip install pymupdf") from exc
    doc = fitz.open(SCHECHTER_PDF)
    try:
        p = doc.load_page(page)
        # DPI that yields roughly `width` px wide
        zoom = width / p.rect.width
        mat = fitz.Matrix(zoom, zoom)
        pix = p.get_pixmap(matrix=mat)
        data = pix.tobytes("jpeg")
    finally:
        doc.close()
    return data, f"file://{SCHECHTER_PDF}#page={page}"


def call_azure_vision(image_bytes: bytes, system_prompt: str, *, max_tokens: int = 4000) -> tuple[str, str]:
    """Call Azure chat completions with an image_url content part.
    Returns (content_text, model_id). Raises on non-200."""
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
                    {"type": "text", "text": "Transcribe this page following the instructions exactly."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
        "temperature": 0.0,
        "max_completion_tokens": max_tokens,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:400]}") from exc
    text = body["choices"][0]["message"]["content"]
    model = body.get("model", azure_deployment())
    return text, model


def process_page(source: str, vol: int | None, page: int, output_dir: pathlib.Path, prompt: str, width: int) -> dict:
    if source == "swete":
        assert vol is not None
        image_bytes, provenance_url = fetch_swete_image(vol, page, width)
        stem = f"vol{vol}_p{page:04d}"
    elif source == "schechter":
        image_bytes, provenance_url = fetch_schechter_image(page, width)
        stem = f"p{page:04d}"
    else:
        raise ValueError(f"unknown source {source!r}")

    image_sha = hashlib.sha256(image_bytes).hexdigest()
    started = time.time()
    text, model_id = call_azure_vision(image_bytes, prompt)
    duration = round(time.time() - started, 2)

    (output_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
    meta = {
        "source": source,
        "vol": vol,
        "page": page,
        "image_width_px": width,
        "image_sha256": image_sha,
        "image_bytes": len(image_bytes),
        "provenance_url": provenance_url,
        "model": model_id,
        "deployment": azure_deployment(),
        "prompt_version": PROMPT_VERSION,
        "transcribed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "output_chars": len(text),
    }
    (output_dir / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def resolve_pages(page_arg: int | None, pages_arg: str | None) -> list[int]:
    if page_arg is not None:
        return [page_arg]
    if not pages_arg:
        raise ValueError("pass --page or --pages")
    pages: list[int] = []
    for chunk in pages_arg.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(chunk))
    return pages


def output_dir_for(source: str, override: str | None) -> pathlib.Path:
    if override:
        return pathlib.Path(override).resolve()
    if source == "swete":
        return REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
    return REPO_ROOT / "sources" / "hebrew_sirach" / "schechter_1899" / "transcribed"


def load_prompt(source: str) -> str:
    fname = "transcribe_greek_swete.md" if source == "swete" else "transcribe_hebrew_schechter.md"
    return (PROMPTS_DIR / fname).read_text(encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, choices=["swete", "schechter"])
    p.add_argument("--vol", type=int, choices=[1, 2, 3], help="Swete volume (required for swete)")
    p.add_argument("--page", type=int, help="Single scan-page number")
    p.add_argument("--pages", help="Range(s), e.g. '60-70' or '60,65,70-75'")
    p.add_argument("--width", type=int, default=1500, help="Image width in pixels (default 1500)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--output-dir", help="Override output directory")
    p.add_argument("--skip-existing", action="store_true", help="Skip pages whose .txt already exists")
    args = p.parse_args()

    if args.source == "swete" and args.vol is None:
        p.error("--vol is required when --source=swete")

    try:
        pages = resolve_pages(args.page, args.pages)
    except ValueError as exc:
        p.error(str(exc))

    out_dir = output_dir_for(args.source, args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = load_prompt(args.source)

    def already_done(page: int) -> bool:
        stem = f"vol{args.vol}_p{page:04d}" if args.source == "swete" else f"p{page:04d}"
        return (out_dir / f"{stem}.txt").exists()

    todo = [pg for pg in pages if not (args.skip_existing and already_done(pg))]
    skipped = len(pages) - len(todo)
    if skipped:
        print(f"skipping {skipped} already-transcribed page(s)", flush=True)

    results: dict[int, tuple[dict | None, str | None]] = {}

    def worker(page: int):
        try:
            return page, process_page(args.source, args.vol, page, out_dir, prompt, args.width), None
        except Exception as e:
            return page, None, f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = [ex.submit(worker, pg) for pg in todo]
        for f in as_completed(futs):
            page, meta, err = f.result()
            results[page] = (meta, err)
            if err:
                print(f"  FAIL p{page}: {err[:300]}", flush=True)
            else:
                print(f"  OK   p{page:>4d}  {meta['duration_seconds']:>5.1f}s  "
                      f"{meta['output_chars']:>6d} chars", flush=True)

    n_ok = sum(1 for meta, err in results.values() if err is None)
    n_fail = len(results) - n_ok
    print(f"\ndone: {n_ok} ok, {n_fail} failed, {skipped} skipped; output in {out_dir}", flush=True)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
