#!/usr/bin/env python3
"""greek_extra_pdf_ocr.py — shared OCR for local Greek extra-canonical PDFs.

This is the Group A companion to:

- `tools/transcribe_source.py` (Swete pages fetched from archive.org)
- `tools/2esdras/ocr_pipeline.py` (local PDFs, source-config driven)

Unlike those, this tool is intentionally generic: it OCRs *any* local
Greek PDF page range into `.txt` + `.meta.json` files using the shared
extra-canonical Greek prompt.

Backends:
  - Azure GPT-5.4 vision (default)
  - Gemini Pro via the global AI Studio endpoint
  - Gemini Pro via Vertex AI (global)

Gemini keys can be supplied directly via `GEMINI_API_KEY` or resolved
from AWS Secrets Manager (`/cartha/openclaw/gemini_api_key`, us-west-2).
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

import boto3


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROMPT_PATH = REPO_ROOT / "tools" / "prompts" / "transcribe_greek_extra_generic.md"
PROMPT_VERSION = "greek_extra_generic_v1_2026-04-21"
DEFAULT_GEMINI_SECRET_ID = "/cartha/openclaw/gemini_api_key"
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
DEFAULT_VERTEX_SECRET_ID = "/cartha/openclaw/gemini_api_key_2"
DEFAULT_VERTEX_LOCATION = "global"
_VERTEX_CACHE: dict[str, object] = {"token": "", "expiry": 0.0, "project": ""}


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


def resolve_gemini_api_keys() -> list[str]:
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return [env_key]
    sm = boto3.client("secretsmanager", region_name="us-west-2")
    raw = sm.get_secret_value(
        SecretId=os.environ.get("GEMINI_SECRET_ID", DEFAULT_GEMINI_SECRET_ID)
    )["SecretString"].strip()

    keys: list[str] = []
    try:
        obj = json.loads(raw)
    except Exception:
        if raw:
            keys = [raw]
    else:
        if isinstance(obj, dict):
            vals = obj.get("api_keys")
            if isinstance(vals, list):
                keys.extend(str(v).strip() for v in vals if str(v).strip())
            for k in ("api_key", "apiKey", "key", "GEMINI_API_KEY"):
                v = obj.get(k)
                if isinstance(v, str) and v.strip():
                    keys.append(v.strip())
                    break
        elif isinstance(obj, list):
            keys.extend(str(v).strip() for v in obj if str(v).strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)

    if not deduped:
        raise RuntimeError("No Gemini API keys resolved from secret")
    return deduped


def resolve_gemini_api_key(index: int = 1) -> str:
    deduped = resolve_gemini_api_keys()
    if index < 1 or index > len(deduped):
        raise RuntimeError(f"Requested Gemini key index {index} out of range 1..{len(deduped)}")
    return deduped[index - 1]


def resolve_vertex_service_account_info() -> dict[str, object]:
    raw = os.environ.get("VERTEX_SA_JSON", "").strip()
    if not raw:
        sm = boto3.client("secretsmanager", region_name="us-west-2")
        raw = sm.get_secret_value(
            SecretId=os.environ.get("VERTEX_SECRET_ID", DEFAULT_VERTEX_SECRET_ID)
        )["SecretString"].strip()
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not obj.get("project_id"):
        raise RuntimeError("Vertex service-account secret is not a valid service-account JSON object")
    return obj


def vertex_access_token() -> tuple[str, str]:
    now = time.time()
    if _VERTEX_CACHE["token"] and isinstance(_VERTEX_CACHE["expiry"], float) and _VERTEX_CACHE["expiry"] > now + 300:
        return str(_VERTEX_CACHE["token"]), str(_VERTEX_CACHE["project"])

    from google.oauth2 import service_account  # type: ignore
    from google.auth.transport.requests import Request  # type: ignore

    info = resolve_vertex_service_account_info()
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(Request())
    token = creds.token
    expiry = creds.expiry.timestamp() if getattr(creds, "expiry", None) else (now + 3000)
    _VERTEX_CACHE["token"] = token or ""
    _VERTEX_CACHE["expiry"] = float(expiry)
    _VERTEX_CACHE["project"] = str(info["project_id"])
    return str(token), str(info["project_id"])


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
    return sorted(dict.fromkeys(pages))


def render_pdf_page(pdf_path: pathlib.Path, page: int, dpi: int) -> bytes:
    with tempfile.TemporaryDirectory(prefix="greek_extra_ocr_") as tmpdir:
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
        return pathlib.Path(f"{out_prefix}.jpg").read_bytes()


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
    return body["choices"][0]["message"]["content"], body.get("model", azure_deployment())


def call_gemini_vision(
    image_bytes: bytes,
    system_prompt: str,
    *,
    max_tokens: int,
    model: str,
    key_index: int,
) -> tuple[str, str]:
    keys = resolve_gemini_api_keys()
    if not keys:
        raise RuntimeError("No Gemini keys available")
    start = max(0, key_index - 1)
    ordered = keys[start:] + keys[:start]

    last_err: RuntimeError | None = None
    for slot, api_key in enumerate(ordered, start=1):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": system_prompt + "\n\nTranscribe this page following the instructions exactly."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode("ascii")}},
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": max_tokens,
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and ("RESOURCE_EXHAUSTED" in detail or "depleted" in detail.lower()) and slot < len(ordered):
                last_err = RuntimeError(f"Gemini key slot exhausted; trying fallback key {slot + 1}/{len(ordered)}")
                continue
            raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:500]}") from exc

        cand = (body.get("candidates") or [None])[0]
        if not cand:
            raise RuntimeError(f"Gemini returned no candidates; promptFeedback={body.get('promptFeedback')}")
        parts = cand.get("content", {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise RuntimeError("Gemini returned empty text")
        return text, body.get("modelVersion", model)

    raise last_err or RuntimeError("Gemini call failed on all configured keys")


def call_gemini_vertex_vision(
    image_bytes: bytes,
    system_prompt: str,
    *,
    max_tokens: int,
    model: str,
) -> tuple[str, str]:
    token, project_id = vertex_access_token()
    location = os.environ.get("VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
    api_host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    url = (
        f"https://{api_host}/v1/projects/{project_id}/locations/{location}/"
        f"publishers/google/models/{model}:generateContent"
    )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": system_prompt + "\n\nTranscribe this page following the instructions exactly."},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode("ascii")}},
            ],
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": max_tokens,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini Vertex HTTP {exc.code}: {detail[:500]}") from exc
    cand = (body.get("candidates") or [None])[0]
    if not cand:
        raise RuntimeError(f"Gemini Vertex returned no candidates; promptFeedback={body.get('promptFeedback')}")
    parts = cand.get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini Vertex returned empty text")
    return text, body.get("modelVersion", model)


def output_stem(prefix: str, page: int) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in prefix).strip("_")
    return f"{safe or 'greek_extra'}_p{page:04d}"


def process_page(
    *,
    pdf_path: pathlib.Path,
    page: int,
    out_dir: pathlib.Path,
    prompt: str,
    dpi: int,
    max_tokens: int,
    stem_prefix: str,
    book_hint: str,
    backend: str,
    gemini_model: str,
    gemini_key_index: int,
) -> dict:
    image_bytes = render_pdf_page(pdf_path, page, dpi=dpi)
    image_sha = hashlib.sha256(image_bytes).hexdigest()
    started = time.time()
    if backend == "gemini":
        text, model_id = call_gemini_vision(
            image_bytes,
            prompt,
            max_tokens=max_tokens,
            model=gemini_model,
            key_index=gemini_key_index,
        )
    elif backend == "gemini-vertex":
        text, model_id = call_gemini_vertex_vision(
            image_bytes,
            prompt,
            max_tokens=max_tokens,
            model=gemini_model,
        )
    else:
        text, model_id = call_azure_vision(image_bytes, prompt, max_tokens=max_tokens)
    duration = round(time.time() - started, 2)

    stem = output_stem(stem_prefix, page)
    (out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
    meta = {
        "source": "greek_extra_pdf",
        "backend": backend,
        "book_hint": book_hint,
        "pdf_path": str(pdf_path),
        "page": page,
        "render_dpi": dpi,
        "image_sha256": image_sha,
        "image_bytes": len(image_bytes),
        "provenance_url": f"file://{pdf_path}#page={page}",
        "model": model_id,
        "deployment": azure_deployment() if backend == "azure" else "",
        "gemini_key_index": gemini_key_index if backend == "gemini" else None,
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
    p.add_argument("--pdf", required=True, help="Local PDF path")
    p.add_argument("--page", type=int, help="Single PDF page number")
    p.add_argument("--pages", help="Ranges, e.g. '120-125' or '120,132,140-142'")
    p.add_argument("--out-dir", required=True, help="Output directory for .txt/.meta.json files")
    p.add_argument("--book-hint", required=True, help="Human-readable source hint")
    p.add_argument("--stem-prefix", default="greek_extra", help="Output filename prefix")
    p.add_argument("--dpi", type=int, default=300, help="Render DPI (default 300)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--max-completion-tokens", type=int, default=7000)
    p.add_argument("--backend", choices=["azure", "gemini", "gemini-vertex"], default="azure")
    p.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL)
    p.add_argument("--gemini-key-index", type=int, default=1)
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    pdf_path = pathlib.Path(args.pdf).resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    try:
        pages = parse_pages(args.page, args.pages)
    except ValueError as exc:
        p.error(str(exc))

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    out_dir = pathlib.Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    def already_done(page: int) -> bool:
        stem = output_stem(args.stem_prefix, page)
        return (out_dir / f"{stem}.txt").exists() and (out_dir / f"{stem}.meta.json").exists()

    todo = [pg for pg in pages if not (args.skip_existing and already_done(pg))]
    skipped = len(pages) - len(todo)

    print(f"📘 book:   {args.book_hint}")
    print(f"📄 pdf:    {pdf_path}")
    print(f"📂 out:    {out_dir}")
    print(f"📑 pages:  {', '.join(str(pg) for pg in pages)}")
    if args.backend == "gemini":
        backend_label = f"{args.backend} ({args.gemini_model}, key #{args.gemini_key_index})"
    elif args.backend == "gemini-vertex":
        backend_label = f"{args.backend} ({args.gemini_model}, secret {os.environ.get('VERTEX_SECRET_ID', DEFAULT_VERTEX_SECRET_ID)})"
    else:
        backend_label = args.backend
    print(f"🤖 backend:{backend_label}")
    if skipped:
        print(f"↷ skipping {skipped} page(s) already on disk")
    if args.dry_run:
        print("🧪 dry run only — no OCR requests will be sent")
        return 0

    results: dict[int, tuple[dict | None, str | None]] = {}

    def worker(page: int):
        try:
            meta = process_page(
                pdf_path=pdf_path,
                page=page,
                out_dir=out_dir,
                prompt=prompt,
                dpi=args.dpi,
                max_tokens=args.max_completion_tokens,
                stem_prefix=args.stem_prefix,
                book_hint=args.book_hint,
                backend=args.backend,
                gemini_model=args.gemini_model,
                gemini_key_index=args.gemini_key_index,
            )
            return page, meta, None
        except Exception as exc:  # noqa: BLE001
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
