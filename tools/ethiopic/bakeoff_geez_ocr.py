#!/usr/bin/env python3
"""bakeoff_geez_ocr.py — head-to-head OCR test for Ge'ez.

Runs the same rendered scan page through:
  - Azure GPT-5.4 vision (Chat Completions, gpt-5-4-deployment)
  - Gemini 3.1 Pro preview (AI Studio, gemini-3.1-pro-preview)
  - Gemini 2.5 Pro plaintext (existing validated baseline, control)

Each engine gets the **same verbatim-transcription prompt** derived from
`tools/ethiopic/ocr_geez.py`, so this measures the engine, not the
prompt.

Accuracy is measured against the hand-corrected scan-truth set under
`sources/enoch/ethiopic/hand_truth/<edition>/ch<NN>/vNNN.txt`. Beta
maṣāḥǝft is explicitly NOT the target — that edition is an apparatus
witness, not an OCR ground truth.

Outputs per engine:
  - raw .txt (exact engine response)
  - .meta.json (model id, token usage, timing, image SHA)
  - per-engine scan-truth validation (.json + .md)
and a combined comparison report at
  sources/enoch/ethiopic/reports/ocr_bakeoff_<stamp>/bakeoff.md

Keys:
  - AZURE_OPENAI_API_KEY (fallback: secret `cartha-azure-openai-key`)
  - GEMINI_API_KEY (fallback: secret `/cartha/openclaw/gemini_api_key`)
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
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
from normalize import normalize_for_alignment, normalize_for_comparison  # type: ignore

TRUTH_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "hand_truth"
REPORTS_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "reports"
BETAMASAHEFT = pathlib.Path.home() / "cartha-reference-local" / "enoch_betamasaheft" / "LIT1340EnochE.xml"


# ---------------------------------------------------------------------------
# Prompt — prompt parity across engines. Do not tune per engine.
# ---------------------------------------------------------------------------

GEEZ_PROMPT = (
    "This is a page from {book_hint}. It shows {chapter_hint}. "
    "It begins: \"{opening_hint}\". "
    "Transcribe every Ge'ez character on this page verbatim using "
    "Ethiopic Unicode (U+1200\u2013U+137F). Preserve the word "
    "separator \u1361 and the sentence terminator \u1362 (or \u1361\u1361). "
    "Preserve Ge'ez numerals "
    "(\u1369 \u136a \u136b \u136c \u136d \u136e \u136f \u1370 \u1371 "
    "\u1372 \u1373 \u1374 \u1375 \u1376 \u1377 \u1378 \u1379 \u137a "
    "\u137b \u137c). Preserve Arabic verse numbers (1., 2., 3., ...) when "
    "they appear at the start of a Ge'ez line. Skip any running head "
    "that repeats on every page. Skip any English, German, or Latin "
    "critical apparatus at the bottom of the page. Output ONLY the "
    "verbatim Ge'ez transcription, nothing else \u2014 no prose, no "
    "explanation, no markdown fences."
)


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def resolve_azure_key() -> str:
    key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    if key:
        return key
    raw = _run([
        "aws", "secretsmanager", "get-secret-value",
        "--secret-id", "cartha-azure-openai-key",
        "--region", "us-west-2",
        "--query", "SecretString", "--output", "text",
    ])
    obj = json.loads(raw)
    return obj["api_key"].strip()


def resolve_gemini_key() -> str:
    raw = os.environ.get("GEMINI_API_KEY", "").strip()
    if raw:
        if raw.startswith("{"):
            obj = json.loads(raw)
            if isinstance(obj, dict):
                for k in ("api_key", "apiKey", "key"):
                    if isinstance(obj.get(k), str) and obj[k].strip():
                        return obj[k].strip()
                keys = obj.get("api_keys")
                if isinstance(keys, list):
                    for item in keys:
                        if isinstance(item, str) and item.strip():
                            return item.strip()
        return raw
    raw = _run([
        "aws", "secretsmanager", "get-secret-value",
        "--secret-id", "/cartha/openclaw/gemini_api_key",
        "--region", "us-west-2",
        "--query", "SecretString", "--output", "text",
    ])
    try:
        obj = json.loads(raw)
    except Exception:
        return raw.strip()
    if isinstance(obj, dict):
        for k in ("api_key", "apiKey", "key"):
            if isinstance(obj.get(k), str) and obj[k].strip():
                return obj[k].strip()
        keys = obj.get("api_keys")
        if isinstance(keys, list):
            for item in keys:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    return str(obj).strip()


# ---------------------------------------------------------------------------
# Image rendering
# ---------------------------------------------------------------------------

def render_page_png(pdf_path: pathlib.Path, page_num: int, dpi: int = 400) -> bytes:
    with tempfile.TemporaryDirectory(prefix="geez_bakeoff_") as tmpdir:
        out_prefix = pathlib.Path(tmpdir) / f"page_{page_num}"
        subprocess.run([
            "pdftocairo", "-png", "-r", str(dpi),
            "-f", str(page_num), "-l", str(page_num),
            "-singlefile", str(pdf_path), str(out_prefix),
        ], check=True, capture_output=True)
        return pathlib.Path(f"{out_prefix}.png").read_bytes()


# ---------------------------------------------------------------------------
# Engine calls
# ---------------------------------------------------------------------------

@dataclass
class EngineResult:
    engine: str
    model_id: str
    text: str
    finish_reason: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_thinking: int = 0
    duration_seconds: float = 0.0
    error: str = ""
    raw_response: dict[str, Any] | None = field(default=None, repr=False)


def call_azure_gpt54(image_bytes: bytes, prompt: str) -> EngineResult:
    api_key = resolve_azure_key()
    endpoint = os.environ.get(
        "AZURE_OPENAI_ENDPOINT",
        "https://eastus2.api.cognitive.microsoft.com",
    ).rstrip("/")
    deployment = os.environ.get("AZURE_OPENAI_VISION_DEPLOYMENT_ID", "gpt-5-4-deployment")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe this page following the instructions exactly."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ],
        "temperature": 0.0,
        "max_completion_tokens": 20000,
    }
    started = time.time()
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
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return EngineResult(
            engine="azure-gpt-5.4",
            model_id=deployment,
            text="",
            finish_reason="error",
            duration_seconds=round(time.time() - started, 2),
            error=f"HTTP {exc.code}: {detail}",
        )
    duration = round(time.time() - started, 2)
    choice = (body.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    usage = body.get("usage") or {}
    return EngineResult(
        engine="azure-gpt-5.4",
        model_id=body.get("model", deployment),
        text=text.strip(),
        finish_reason=choice.get("finish_reason", "?"),
        tokens_in=int(usage.get("prompt_tokens", 0)),
        tokens_out=int(usage.get("completion_tokens", 0)),
        tokens_thinking=int(
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        ),
        duration_seconds=duration,
        raw_response=body,
    )


def call_gemini(
    image_bytes: bytes,
    prompt: str,
    *,
    model: str,
    thinking_budget: int = 512,
    max_output_tokens: int = 20000,
) -> EngineResult:
    api_key = resolve_gemini_key()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "text/plain",
            "maxOutputTokens": max_output_tokens,
            "thinkingConfig": {"thinkingBudget": thinking_budget},
        },
    }
    started = time.time()
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return EngineResult(
            engine=f"gemini::{model}",
            model_id=model,
            text="",
            finish_reason="error",
            duration_seconds=round(time.time() - started, 2),
            error=f"HTTP {exc.code}: {detail}",
        )
    duration = round(time.time() - started, 2)
    cand = (resp.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    usage = resp.get("usageMetadata", {})
    return EngineResult(
        engine=f"gemini::{model}",
        model_id=resp.get("modelVersion", model),
        text=text,
        finish_reason=cand.get("finishReason", "?"),
        tokens_in=int(usage.get("promptTokenCount", 0)),
        tokens_out=int(usage.get("candidatesTokenCount", 0)),
        tokens_thinking=int(usage.get("thoughtsTokenCount", 0)),
        duration_seconds=duration,
        raw_response=resp,
    )


# ---------------------------------------------------------------------------
# Measurement against hand-truth
# ---------------------------------------------------------------------------

def load_truth(edition: str, chapter: int, verses: list[int]) -> dict[str, Any]:
    truth_dir = TRUTH_ROOT / edition / f"ch{chapter:02d}"
    manifest = json.loads((truth_dir / "manifest.json").read_text(encoding="utf-8"))
    joined_parts: list[str] = []
    per_verse: dict[int, str] = {}
    for verse in verses:
        text = (truth_dir / f"v{verse:03d}.txt").read_text(encoding="utf-8").strip()
        per_verse[verse] = text
        joined_parts.append(text)
    return {"manifest": manifest, "per_verse": per_verse, "joined": "\n".join(joined_parts)}


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def sample_diffs(a: str, b: str, limit: int = 12) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if tag == "equal":
            continue
        out.append({
            "tag": tag,
            "ocr": a[i1:i2],
            "truth": b[j1:j2],
            "ocr_context": a[max(0, i1 - 20):min(len(a), i2 + 20)],
            "truth_context": b[max(0, j1 - 20):min(len(b), j2 + 20)],
        })
        if len(out) >= limit:
            break
    return out


def measure(ocr_text: str, truth_text: str) -> dict[str, Any]:
    ocr_norm = normalize_for_comparison(ocr_text)
    truth_norm = normalize_for_comparison(truth_text)
    ocr_align = normalize_for_alignment(ocr_text)
    truth_align = normalize_for_alignment(truth_text)
    dist = levenshtein(ocr_align, truth_align)
    denom = max(len(ocr_align), len(truth_align), 1)
    accuracy = max(0.0, 1.0 - dist / denom)
    return {
        "ocr_chars_normalized": len(ocr_align),
        "truth_chars_normalized": len(truth_align),
        "distance": dist,
        "accuracy": round(accuracy, 6),
        "length_delta": len(ocr_align) - len(truth_align),
        "ocr_normalized_preview": ocr_norm[:500],
        "truth_normalized_preview": truth_norm[:500],
        "samples": sample_diffs(ocr_align, truth_align),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_engine_output(out_dir: pathlib.Path, result: EngineResult, *, scan_meta: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = result.engine.replace("::", "_").replace("/", "_").replace(":", "_")
    (out_dir / f"{safe}.txt").write_text(
        result.text + ("\n" if result.text and not result.text.endswith("\n") else ""),
        encoding="utf-8",
    )
    meta = {
        "engine": result.engine,
        "model_id": result.model_id,
        "finish_reason": result.finish_reason,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "tokens_thinking": result.tokens_thinking,
        "duration_seconds": result.duration_seconds,
        "error": result.error or None,
        "captured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scan": scan_meta,
    }
    (out_dir / f"{safe}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="sources/enoch/scans/charles_1906_ethiopic.pdf")
    ap.add_argument("--page", type=int, default=40)
    ap.add_argument("--book-hint", default="Charles 1906 Ethiopic Enoch (Anecdota Oxoniensia Semitic Series I.vii)")
    ap.add_argument("--chapter-hint", default="chapter 1 (ምዕራፍ ፩)")
    ap.add_argument("--opening-hint", default="ቃለ ፡ በረከት ፡ ዘሄኖክ")
    ap.add_argument("--truth-edition", default="charles_1906")
    ap.add_argument("--truth-chapter", type=int, default=1)
    ap.add_argument("--truth-verses", default="1-5")
    ap.add_argument("--dpi", type=int, default=400)
    ap.add_argument("--run-id", default=timestamp())
    ap.add_argument("--skip-azure", action="store_true")
    ap.add_argument("--skip-gemini-31", action="store_true")
    ap.add_argument("--skip-gemini-25", action="store_true")
    ap.add_argument(
        "--gemini-31-model",
        default="gemini-3.1-pro-preview",
        help="Gemini 3.1 Pro model id (default: gemini-3.1-pro-preview)",
    )
    ap.add_argument(
        "--gemini-25-model",
        default="gemini-2.5-pro",
        help="Gemini 2.5 Pro baseline model id (default: gemini-2.5-pro)",
    )
    args = ap.parse_args()

    pdf_path = (REPO_ROOT / args.pdf).resolve() if not pathlib.Path(args.pdf).is_absolute() else pathlib.Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    start, end = [int(x) for x in args.truth_verses.split("-", 1)]
    truth_verses = list(range(start, end + 1))
    truth = load_truth(args.truth_edition, args.truth_chapter, truth_verses)

    print(f"[bakeoff] rendering {pdf_path.name} page {args.page} at {args.dpi} DPI")
    image = render_page_png(pdf_path, args.page, dpi=args.dpi)
    image_sha = hashlib.sha256(image).hexdigest()
    scan_meta = {
        "pdf": str(pdf_path.relative_to(REPO_ROOT)) if str(pdf_path).startswith(str(REPO_ROOT)) else str(pdf_path),
        "page": args.page,
        "dpi": args.dpi,
        "image_sha256": image_sha,
        "image_bytes": len(image),
    }

    prompt = GEEZ_PROMPT.format(
        book_hint=args.book_hint,
        chapter_hint=args.chapter_hint,
        opening_hint=args.opening_hint,
    )

    out_dir = REPORTS_ROOT / f"ocr_bakeoff_{args.run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    # Save the image for forensic review
    (out_dir / "page.png").write_bytes(image)

    runs: list[tuple[str, EngineResult]] = []

    if not args.skip_azure:
        print("[bakeoff] Azure GPT-5.4 vision \u2026", flush=True)
        r = call_azure_gpt54(image, prompt)
        print(f"  finish={r.finish_reason} chars={len(r.text)} dur={r.duration_seconds}s err={r.error or '-'}")
        write_engine_output(out_dir, r, scan_meta=scan_meta)
        runs.append(("azure-gpt-5.4", r))

    if not args.skip_gemini_31:
        print(f"[bakeoff] Gemini {args.gemini_31_model} \u2026", flush=True)
        r = call_gemini(image, prompt, model=args.gemini_31_model)
        print(f"  finish={r.finish_reason} chars={len(r.text)} dur={r.duration_seconds}s err={r.error or '-'}")
        write_engine_output(out_dir, r, scan_meta=scan_meta)
        runs.append(("gemini-3.1-pro", r))

    if not args.skip_gemini_25:
        print(f"[bakeoff] Gemini {args.gemini_25_model} (control baseline) \u2026", flush=True)
        r = call_gemini(image, prompt, model=args.gemini_25_model)
        print(f"  finish={r.finish_reason} chars={len(r.text)} dur={r.duration_seconds}s err={r.error or '-'}")
        write_engine_output(out_dir, r, scan_meta=scan_meta)
        runs.append(("gemini-2.5-pro", r))

    # Measure each against hand-truth
    scoreboard: list[dict[str, Any]] = []
    for label, result in runs:
        metrics = measure(result.text, truth["joined"]) if result.text else {
            "accuracy": 0.0,
            "distance": 0,
            "samples": [],
            "ocr_chars_normalized": 0,
            "truth_chars_normalized": len(normalize_for_alignment(truth["joined"])),
        }
        scoreboard.append({
            "label": label,
            "engine": result.engine,
            "model_id": result.model_id,
            "accuracy": metrics["accuracy"],
            "distance": metrics["distance"],
            "length_delta": metrics.get("length_delta"),
            "duration_seconds": result.duration_seconds,
            "tokens_out": result.tokens_out,
            "tokens_thinking": result.tokens_thinking,
            "finish_reason": result.finish_reason,
            "error": result.error,
            "samples": metrics.get("samples", [])[:5],
        })

    report = {
        "run_id": args.run_id,
        "captured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scan": scan_meta,
        "truth": {
            "edition": args.truth_edition,
            "chapter": args.truth_chapter,
            "verses": truth_verses,
            "manifest": truth["manifest"],
            "truth_chars_normalized": len(normalize_for_alignment(truth["joined"])),
        },
        "prompt": prompt,
        "scoreboard": scoreboard,
    }
    (out_dir / "bakeoff.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines: list[str] = [
        f"# Ge'ez OCR bake-off \u2014 run {args.run_id}",
        "",
        f"- Scan: `{scan_meta['pdf']}` page **{scan_meta['page']}** @ **{scan_meta['dpi']} DPI**",
        f"- Truth: `{args.truth_edition}` chapter {args.truth_chapter} verses {start}\u2013{end} "
        f"(**{report['truth']['truth_chars_normalized']}** normalized chars)",
        "",
        "## Scoreboard",
        "",
        "| Engine | Model | Accuracy vs scan-truth | Distance | Chars out | Thinking tokens | Duration | Finish |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(scoreboard, key=lambda r: r["accuracy"], reverse=True):
        lines.append(
            f"| `{row['label']}` | `{row['model_id']}` | "
            f"**{row['accuracy']:.2%}** | {row['distance']} | "
            f"{row.get('ocr_chars_normalized', '?')} | {row['tokens_thinking']} | "
            f"{row['duration_seconds']}s | {row['finish_reason']} |"
        )
    lines.append("")

    for row in scoreboard:
        lines.append(f"## {row['label']} \u2014 {row['model_id']}")
        if row["error"]:
            lines.append(f"- error: `{row['error']}`")
        lines.append(f"- Accuracy: **{row['accuracy']:.2%}** (distance {row['distance']})")
        lines.append(f"- Finish: `{row['finish_reason']}` \u2014 {row['duration_seconds']}s \u2014 thinking tokens {row['tokens_thinking']}")
        if row["samples"]:
            lines.append("")
            lines.append("Sample disagreements:")
            for item in row["samples"]:
                lines.append(f"- `{item['tag']}` \u2014 OCR `{item['ocr']}` vs truth `{item['truth']}`")
        lines.append("")

    (out_dir / "bakeoff.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(json.dumps({
        "run_id": args.run_id,
        "report_dir": str(out_dir.relative_to(REPO_ROOT)),
        "scoreboard": [
            {k: v for k, v in r.items() if k not in ("samples",)}
            for r in scoreboard
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
