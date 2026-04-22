#!/usr/bin/env python3
"""ocr_pipeline.py — OCR pipeline for 2 Baruch local source files.

This is the first executable OCR/transcription leg of the dedicated
2 Baruch pipeline. It currently supports the two page families already
rehydrated under `sources/2baruch/`:

  1. Ceriani 1871 primary Syriac pages
  2. Kmosko 1907 Syriac/Latin scholarly pages

Outputs:
  - one UTF-8 `.txt` file per page
  - one `.meta.json` provenance sidecar per page

Typical usage:

    python tools/2baruch/ocr_pipeline.py --source ceriani1871 --pages 187,190,195,205,220
    python tools/2baruch/ocr_pipeline.py --source kmosko1907 --page 620 --backend gemini

Backends:
  - Azure GPT-5.4 vision
  - Gemini Pro via the AI Studio endpoint
  - Gemini Pro via Vertex AI

Keys are resolved from the environment when present, otherwise via the
same AWS Secrets Manager paths already used elsewhere in this repo.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from PIL import Image, ImageOps


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
SOURCES_ROOT = REPO_ROOT / "sources" / "2baruch"
RAW_OCR_ROOT = SOURCES_ROOT / "raw_ocr"
PROMPT_VERSION = "2baruch_ocr_v1_2026-04-21"
DEFAULT_GEMINI_SECRET_ID = "/cartha/openclaw/gemini_api_key"
DEFAULT_GEMINI_MODEL = "gemini-3.1-pro-preview"
DEFAULT_VERTEX_SECRET_ID = "/cartha/openclaw/gemini_api_key_2"
DEFAULT_VERTEX_LOCATION = "global"
_VERTEX_CACHE: dict[str, object] = {"token": "", "expiry": 0.0, "project": ""}
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*|\s*```$", re.MULTILINE)
_LINE_PREFIX_RE = re.compile(r"^Line\s+\d+\s*:\s*")


SOURCE_CONFIGS: dict[str, dict[str, pathlib.Path | str]] = {
    "ceriani1871": {
        "pdf_path": SOURCES_ROOT / "scans" / "ceriani_1871_monumenta_tom5.pdf",
        "prompt_path": PROMPTS_DIR / "transcribe_2baruch_ceriani_syriac.md",
        "output_dir": RAW_OCR_ROOT / "ceriani1871",
        "label": "Ceriani 1871 primary Syriac edition in Monumenta sacra et profana 5.2",
    },
    "kmosko1907": {
        "pdf_path": SOURCES_ROOT / "scans" / "kmosko_1907_patrologia_syriaca_vol1_2.pdf",
        "prompt_path": PROMPTS_DIR / "transcribe_2baruch_kmosko_syriac_latin.md",
        "output_dir": RAW_OCR_ROOT / "kmosko1907",
        "label": "Kmosko 1907 Patrologia Syriaca scholarly witness",
    },
}

CERIANI_REGION_PROMPTS = {
    "running_head": (
        "You are transcribing only the running-head strip from a Ceriani 1871 2 Baruch page. "
        "Output only the visible text exactly as printed. No commentary."
    ),
    "column": (
        "You are transcribing one cropped main Syriac text column from Ceriani 1871 2 Baruch. "
        "Output only the Syriac text visible in this crop, top-to-bottom, preserving Syriac Unicode, "
        "line breaks, punctuation, and inline verse numbers exactly as printed. Do not translate. "
        "Do not normalize. Do not add commentary or labels."
    ),
    "apparatus": (
        "You are transcribing one cropped lower apparatus column from Ceriani 1871 2 Baruch. "
        "This crop may contain Latin editorial notes plus quoted Syriac words. Output only the "
        "visible text in reading order, preserving scripts and line breaks. Do not translate. "
        "Do not add commentary or labels."
    ),
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


def render_pdf_page(pdf_path: pathlib.Path, page: int, dpi: int) -> tuple[bytes, str]:
    """Render one local PDF page to PNG bytes."""
    with tempfile.TemporaryDirectory(prefix="2baruch_ocr_") as tmpdir:
        out_prefix = pathlib.Path(tmpdir) / f"page_{page}"
        cmd = [
            "pdftocairo",
            "-png",
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
        png_path = pathlib.Path(f"{out_prefix}.png")
        return png_path.read_bytes(), "image/png"


def load_prompt(prompt_path: pathlib.Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def sanitize_model_text(text: str) -> str:
    text = text.strip()
    text = _FENCE_RE.sub("", text).strip()
    cleaned: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("I will now transcribe", "Here is the transcription", "Transcription:")):
            continue
        if line.startswith("Wait,"):
            break
        line = _LINE_PREFIX_RE.sub("", line).strip()
        line = line.strip("`").strip()
        if not line:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def png_bytes_from_image(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def dark_pixel_stats(img: Image.Image, *, threshold: int = 40) -> tuple[int, float]:
    total = img.size[0] * img.size[1]
    hist = img.histogram()
    cutoff = max(0, 255 - threshold)
    dark = sum(hist[:cutoff])
    ratio = (dark / total) if total else 0.0
    return dark, ratio


def trim_to_ink(img: Image.Image, *, threshold: int = 40, margin: int = 20) -> Image.Image:
    inv = ImageOps.invert(img)
    mask = inv.point(lambda p: 255 if p > threshold else 0)
    bbox = mask.getbbox()
    if not bbox:
        return img
    trimmed = img.crop(bbox)
    canvas = Image.new("L", (trimmed.size[0] + (2 * margin), trimmed.size[1] + (2 * margin)), 255)
    canvas.paste(trimmed, (margin, margin))
    return canvas


def crop_ceriani_regions(image_bytes: bytes) -> dict[str, dict[str, object]]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("L")
        w, h = img.size

        def box(x1: float, y1: float, x2: float, y2: float) -> tuple[int, int, int, int]:
            return (
                max(0, int(round(w * x1))),
                max(0, int(round(h * y1))),
                min(w, int(round(w * x2))),
                min(h, int(round(h * y2))),
            )

        regions = {
            "running_head": img.crop(box(0.28, 0.00, 0.72, 0.055)),
            "column1": img.crop(box(0.16, 0.05, 0.53, 0.81)),
            "column2": img.crop(box(0.53, 0.05, 0.92, 0.81)),
            "apparatus1": img.crop(box(0.03, 0.78, 0.52, 0.99)),
            "apparatus2": img.crop(box(0.50, 0.78, 0.98, 0.99)),
        }
        trimmed_names = {"apparatus1", "apparatus2"}
        out: dict[str, dict[str, object]] = {}
        for name, region in regions.items():
            region_img = trim_to_ink(region) if name in trimmed_names else region
            dark_pixels, dark_ratio = dark_pixel_stats(region_img)
            out[name] = {
                "bytes": png_bytes_from_image(region_img),
                "dark_pixels": dark_pixels,
                "dark_ratio": dark_ratio,
                "blankish": (
                    (name == "running_head" and dark_pixels < 150)
                    or (name.startswith("apparatus") and dark_pixels < 350)
                ),
            }
        return out


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


def call_azure_vision(image_bytes: bytes, mime_type: str, system_prompt: str, *, max_tokens: int) -> tuple[str, str]:
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
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
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
    return sanitize_model_text(text), model


def call_gemini_vision(
    image_bytes: bytes,
    mime_type: str,
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
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{
                "parts": [
                    {"text": "Transcribe this page following the instructions exactly."},
                    {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "text/plain",
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
        text = sanitize_model_text("".join(part.get("text", "") for part in parts if isinstance(part, dict)))
        if not text:
            raise RuntimeError("Gemini returned empty text")
        return text, body.get("modelVersion", model)

    raise last_err or RuntimeError("Gemini call failed on all configured keys")


def call_gemini_vertex_vision(
    image_bytes: bytes,
    mime_type: str,
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
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{
            "role": "user",
            "parts": [
                {"text": "Transcribe this page following the instructions exactly."},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
            ],
        }],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "text/plain",
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
    text = sanitize_model_text("".join(part.get("text", "") for part in parts if isinstance(part, dict)))
    if not text:
        raise RuntimeError("Gemini Vertex returned empty text")
    return text, body.get("modelVersion", model)


def output_stem(source: str, page: int) -> str:
    return f"{source}_p{page:04d}"


def assemble_ceriani_page(regions_text: dict[str, str]) -> str:
    raw_head = regions_text.get("running_head", "").strip()
    head = raw_head if re.search(r"\d", raw_head) else "[BLANK]"
    col1 = regions_text.get("column1", "").strip() or "[BLANK]"
    col2 = regions_text.get("column2", "").strip() or "[BLANK]"
    app_left = regions_text.get("apparatus1", "").strip()
    app_right = regions_text.get("apparatus2", "").strip()
    apparatus_parts = [part for part in (app_left, app_right) if part]
    apparatus = "\n\n".join(apparatus_parts) if apparatus_parts else "[BLANK]"
    return (
        "---2BARUCH-CERIANI-PAGE---\n"
        "[RUNNING HEAD]\n"
        f"{head}\n"
        "[SYRIAC COLUMN 1]\n"
        f"{col1}\n"
        "[SYRIAC COLUMN 2]\n"
        f"{col2}\n"
        "[LATIN APPARATUS]\n"
        f"{apparatus}\n"
        "---END-PAGE---\n"
    )


def call_backend(
    *,
    backend: str,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    max_tokens: int,
    gemini_model: str,
    gemini_key_index: int,
) -> tuple[str, str]:
    if backend == "gemini":
        return call_gemini_vision(
            image_bytes,
            mime_type,
            prompt,
            max_tokens=max_tokens,
            model=gemini_model,
            key_index=gemini_key_index,
        )
    if backend == "gemini-vertex":
        return call_gemini_vertex_vision(
            image_bytes,
            mime_type,
            prompt,
            max_tokens=max_tokens,
            model=gemini_model,
        )
    return call_azure_vision(image_bytes, mime_type, prompt, max_tokens=max_tokens)


def process_page(
    *,
    source: str,
    pdf_path: pathlib.Path,
    prompt: str,
    page: int,
    out_dir: pathlib.Path,
    dpi: int,
    max_tokens: int,
    backend: str,
    gemini_model: str,
    gemini_key_index: int,
) -> dict:
    image_bytes, mime_type = render_pdf_page(pdf_path, page, dpi=dpi)
    image_sha = hashlib.sha256(image_bytes).hexdigest()
    started = time.time()
    region_meta: list[dict[str, object]] | None = None

    if source == "ceriani1871":
        crops = crop_ceriani_regions(image_bytes)
        regions_text: dict[str, str] = {}
        region_meta = []
        model_id = ""
        region_budgets = {
            "running_head": min(300, max_tokens),
            "column1": max_tokens,
            "column2": max_tokens,
            "apparatus1": min(2500, max_tokens),
            "apparatus2": min(2500, max_tokens),
        }
        for region_name in ("running_head", "column1", "column2", "apparatus1", "apparatus2"):
            region_prompt_key = "running_head" if region_name == "running_head" else ("apparatus" if region_name.startswith("apparatus") else "column")
            crop_info = crops[region_name]
            crop_bytes = crop_info["bytes"]
            region_started = time.time()
            if crop_info["blankish"]:
                region_text = ""
                region_model_id = model_id or ""
            else:
                try:
                    region_text, region_model_id = call_backend(
                        backend=backend,
                        image_bytes=crop_bytes,
                        mime_type="image/png",
                        prompt=CERIANI_REGION_PROMPTS[region_prompt_key],
                        max_tokens=region_budgets[region_name],
                        gemini_model=gemini_model,
                        gemini_key_index=gemini_key_index,
                    )
                except Exception:
                    if region_name == "running_head":
                        region_text = ""
                        region_model_id = model_id or ""
                    elif region_name.startswith("apparatus"):
                        # Apparatus may genuinely be absent on some edge pages;
                        # keep the sweep moving and let later control witnesses
                        # fill any real gaps.
                        region_text = ""
                        region_model_id = model_id or ""
                    else:
                        raise
            regions_text[region_name] = region_text.strip()
            model_id = model_id or region_model_id
            region_meta.append({
                "region": region_name,
                "image_sha256": hashlib.sha256(crop_bytes).hexdigest(),
                "image_bytes": len(crop_bytes),
                "dark_pixels": crop_info["dark_pixels"],
                "dark_ratio": crop_info["dark_ratio"],
                "blankish": crop_info["blankish"],
                "duration_seconds": round(time.time() - region_started, 2),
                "output_chars": len(region_text),
            })
        text = assemble_ceriani_page(regions_text)
    else:
        text, model_id = call_backend(
            backend=backend,
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
            max_tokens=max_tokens,
            gemini_model=gemini_model,
            gemini_key_index=gemini_key_index,
        )

    duration = round(time.time() - started, 2)
    stem = output_stem(source, page)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
    meta = {
        "source": source,
        "backend": backend,
        "pdf_path": str(pdf_path),
        "page": page,
        "render_dpi": dpi,
        "image_mime_type": mime_type,
        "image_sha256": image_sha,
        "image_bytes": len(image_bytes),
        "provenance_url": f"file://{pdf_path}#page={page}",
        "model": model_id,
        "deployment": azure_deployment() if backend == "azure" else "",
        "gemini_model": gemini_model if backend in {"gemini", "gemini-vertex"} else None,
        "gemini_key_index": gemini_key_index if backend == "gemini" else None,
        "layout_mode": "ceriani_region_assembled" if source == "ceriani1871" else "page_direct",
        "regions": region_meta,
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
    p.add_argument("--pages", help="Ranges, e.g. '187-191' or '187,190,205'")
    p.add_argument("--dpi", type=int, default=300, help="Render DPI (default 300)")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--max-completion-tokens", type=int, default=9000)
    p.add_argument("--backend", choices=["azure", "gemini", "gemini-vertex"], default="gemini")
    p.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL)
    p.add_argument("--gemini-key-index", type=int, default=1)
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

    print(f"📘 source:  {args.source} — {cfg['label']}")
    print(f"📄 pdf:     {pdf_path}")
    print(f"🧾 prompt:  {prompt_path.name}")
    print(f"📂 out:     {out_dir}")
    print(f"📑 pages:   {', '.join(str(pg) for pg in pages)}")
    if args.backend == "gemini":
        backend_label = f"{args.backend} ({args.gemini_model}, key #{args.gemini_key_index})"
    elif args.backend == "gemini-vertex":
        backend_label = f"{args.backend} ({args.gemini_model})"
    else:
        backend_label = args.backend
    print(f"🤖 backend: {backend_label}")
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
