#!/usr/bin/env python3
"""ocr_pipeline.py — Azure GPT-5 vision OCR for 2 Esdras source PDFs.

This is the non-Ethiopic OCR/transcription leg of the dedicated
2 Esdras pipeline. It handles two distinct page families:

  1. Bensly 1895 / Bensly 1875 Latin pages
  2. Violet 1910 parallel-column pages (Latin + Syriac + Ethiopic +
     Arabic + Armenian + Georgian, depending on the page)

Unlike `tools/transcribe_source.py`, which fetches Swete pages from
archive.org or renders Schechter plates, this pipeline works entirely
from local vendored PDFs under `sources/2esdras/`.

Outputs:
  - one UTF-8 `.txt` file per page
  - one `.meta.json` provenance sidecar per page

Typical usage:

    python tools/2esdras/ocr_pipeline.py --source bensly1895 --pages 120-130
    python tools/2esdras/ocr_pipeline.py --source violet1910-vol1 --page 44
    python tools/2esdras/ocr_pipeline.py --source violet1910-vol1 --pages 44-48 --dry-run

Environment:
  AZURE_OPENAI_API_KEY          required for live OCR
  AZURE_OPENAI_ENDPOINT         optional
  AZURE_OPENAI_VISION_DEPLOYMENT_ID optional
  AZURE_OPENAI_API_VERSION      optional
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
SOURCES_ROOT = REPO_ROOT / "sources" / "2esdras"
RAW_OCR_ROOT = SOURCES_ROOT / "raw_ocr"
PROMPT_VERSION = "2esdras_ocr_v1_2026-04-21"


SOURCE_CONFIGS: dict[str, dict[str, pathlib.Path | str]] = {
    "bensly1895": {
        "pdf_path": SOURCES_ROOT / "scans" / "textsandstudies_v3.pdf",
        "prompt_path": PROMPTS_DIR / "transcribe_2esdras_bensly_latin.md",
        "output_dir": RAW_OCR_ROOT / "bensly1895",
        "label": "Bensly 1895 Latin edition in Texts and Studies vol. III",
    },
    "bensly1875": {
        "pdf_path": SOURCES_ROOT / "latin" / "bensly_1875_missing_fragment.pdf",
        "prompt_path": PROMPTS_DIR / "transcribe_2esdras_bensly_latin.md",
        "output_dir": RAW_OCR_ROOT / "bensly1875",
        "label": "Bensly 1875 Missing Fragment Latin edition",
    },
    "violet1910-vol1": {
        "pdf_path": SOURCES_ROOT / "scans" / "violet_1910_vol1.pdf",
        "prompt_path": PROMPTS_DIR / "transcribe_2esdras_violet_parallel.md",
        "output_dir": RAW_OCR_ROOT / "violet1910-vol1",
        "label": "Violet 1910 parallel-column witness edition vol. 1",
    },
    "violet1910-vol2": {
        "pdf_path": SOURCES_ROOT / "scans" / "violet_1910_vol2.pdf",
        "prompt_path": PROMPTS_DIR / "transcribe_2esdras_violet_parallel.md",
        "output_dir": RAW_OCR_ROOT / "violet1910-vol2",
        "label": "Violet 1910 parallel-column witness edition vol. 2",
    },
}


def azure_endpoint() -> str:
    return os.environ.get(
        "AZURE_OPENAI_ENDPOINT",
        "https://eastus2.api.cognitive.microsoft.com",
    ).rstrip("/")


def azure_deployment() -> str:
    return os.environ.get(
        "AZURE_OPENAI_VISION_DEPLOYMENT_ID",
        "gpt-5-4-deployment",
    )


def azure_api_version() -> str:
    return os.environ.get(
        "AZURE_OPENAI_API_VERSION",
        "2025-04-01-preview",
    )


def parse_pages(page_arg: int | None, pages_arg: str | None) -> list[int]:
    if page_arg is not None:
        return [page_arg]
    if not pages_arg:
        raise ValueError("pass --page or --pages")
    pages: list[int] = []
    for chunk in pages_arg.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            start = int(a)
            end = int(b)
            if end < start:
                raise ValueError(f"descending page range: {chunk}")
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(chunk))
    if not pages:
        raise ValueError("no pages resolved")
    return sorted(dict.fromkeys(pages))


def render_pdf_page(pdf_path: pathlib.Path, page: int, dpi: int) -> bytes:
    """Render one local PDF page to JPEG via pdftocairo."""
    with tempfile.TemporaryDirectory(prefix="2esdras_ocr_") as tmpdir:
        out_prefix = pathlib.Path(tmpdir) / f"page_{page}"
        cmd = [
            "pdftocairo",
            "-jpeg",
            "-jpegopt",
            "quality=95",
            "-r",
            str(dpi),
            "-f",
            str(page),
            "-l",
            str(page),
            "-singlefile",
            str(pdf_path),
            str(out_prefix),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        jpg_path = pathlib.Path(f"{out_prefix}.jpg")
        return jpg_path.read_bytes()


def load_prompt(prompt_path: pathlib.Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def call_azure_vision(image_bytes: bytes, system_prompt: str, *, max_tokens: int) -> tuple[str, str]:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    url = (
        f"{azure_endpoint()}/openai/deployments/{azure_deployment()}/chat/completions"
        f"?api-version={azure_api_version()}"
    )
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
        raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:500]}") from exc
    text = body["choices"][0]["message"]["content"]
    model = body.get("model", azure_deployment())
    return text, model


def output_stem(source: str, page: int) -> str:
    return f"{source}_p{page:04d}"


def process_page(
    *,
    source: str,
    pdf_path: pathlib.Path,
    prompt: str,
    page: int,
    out_dir: pathlib.Path,
    dpi: int,
    max_tokens: int,
) -> dict:
    image_bytes = render_pdf_page(pdf_path, page, dpi=dpi)
    image_sha = hashlib.sha256(image_bytes).hexdigest()
    started = time.time()
    text, model_id = call_azure_vision(image_bytes, prompt, max_tokens=max_tokens)
    duration = round(time.time() - started, 2)

    stem = output_stem(source, page)
    (out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
    meta = {
        "source": source,
        "pdf_path": str(pdf_path),
        "page": page,
        "render_dpi": dpi,
        "image_sha256": image_sha,
        "image_bytes": len(image_bytes),
        "provenance_url": f"file://{pdf_path}#page={page}",
        "model": model_id,
        "deployment": azure_deployment(),
        "prompt_version": PROMPT_VERSION,
        "transcribed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "output_chars": len(text),
    }
    (out_dir / f"{stem}.meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, choices=sorted(SOURCE_CONFIGS))
    p.add_argument("--page", type=int, help="Single PDF page number")
    p.add_argument("--pages", help="Ranges, e.g. '44-48' or '44,51,60-62'")
    p.add_argument("--dpi", type=int, default=300, help="Render DPI (default 300)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument(
        "--max-completion-tokens",
        type=int,
        default=7000,
        help="Azure max_completion_tokens (default 7000)",
    )
    p.add_argument("--output-dir", help="Override default raw OCR output directory")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    try:
        pages = parse_pages(args.page, args.pages)
    except ValueError as exc:
        p.error(str(exc))

    cfg = SOURCE_CONFIGS[args.source]
    pdf_path = pathlib.Path(cfg["pdf_path"])
    prompt_path = pathlib.Path(cfg["prompt_path"])
    out_dir = pathlib.Path(args.output_dir).resolve() if args.output_dir else pathlib.Path(cfg["output_dir"])

    if not pdf_path.exists():
        raise SystemExit(f"source PDF missing: {pdf_path}")
    if not prompt_path.exists():
        raise SystemExit(f"prompt file missing: {prompt_path}")

    prompt = load_prompt(prompt_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    def already_done(page: int) -> bool:
        stem = output_stem(args.source, page)
        return (out_dir / f"{stem}.txt").exists() and (out_dir / f"{stem}.meta.json").exists()

    todo = [pg for pg in pages if not (args.skip_existing and already_done(pg))]
    skipped = len(pages) - len(todo)

    print(f"📘 source: {args.source} — {cfg['label']}")
    print(f"📄 pdf:    {pdf_path}")
    print(f"🧾 prompt: {prompt_path.name}")
    print(f"📂 out:    {out_dir}")
    print(f"📑 pages:  {', '.join(str(pg) for pg in pages)}")
    if skipped:
        print(f"↷ skipping {skipped} page(s) already on disk")
    if args.dry_run:
        print("🧪 dry run only — no OCR requests will be sent")
        return 0

    results: dict[int, tuple[dict | None, str | None]] = {}

    def worker(page: int):
        try:
            meta = process_page(
                source=args.source,
                pdf_path=pdf_path,
                prompt=prompt,
                page=page,
                out_dir=out_dir,
                dpi=args.dpi,
                max_tokens=args.max_completion_tokens,
            )
            return page, meta, None
        except Exception as exc:  # noqa: BLE001 - CLI should keep page-level failures isolated
            return page, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = [ex.submit(worker, pg) for pg in todo]
        for fut in as_completed(futs):
            page, meta, err = fut.result()
            results[page] = (meta, err)
            if err:
                print(f"  FAIL p{page}: {err[:300]}", flush=True)
            else:
                print(
                    f"  OK   p{page:>4d}  {meta['duration_seconds']:>5.1f}s  "
                    f"{meta['output_chars']:>6d} chars",
                    flush=True,
                )

    n_ok = sum(1 for meta, err in results.values() if err is None)
    n_fail = len(results) - n_ok
    print(f"\ndone: {n_ok} ok, {n_fail} failed, {skipped} skipped; output in {out_dir}", flush=True)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
