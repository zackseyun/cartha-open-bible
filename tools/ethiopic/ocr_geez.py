"""ocr_geez.py — Gemini 2.5 Pro Geʿez OCR, plaintext mode.

Validated 2026-04-21 on Enoch ch 1 (Dillmann 1851 page 7).

Why plaintext mode (not JSON response format):
  - Each Geʿez character is 3 bytes in UTF-8. JSON-escaped to
    \\u12XX form, it becomes 6 characters. A 1000-char Geʿez page
    becomes ~6000 response tokens before Gemini even finishes.
  - With response_mime_type='application/json', Pro hit MAX_TOKENS
    at 32K without completing a full page.
  - In plaintext mode, the same page completes in ~1200 output
    tokens with STOP finish reason.

Why low thinking budget (512-1024):
  - Higher budgets burn tokens on reasoning that doesn't help
    mechanical OCR.
  - thinkingBudget=0 is rejected by the API for Pro ("only works in
    thinking mode"), so 512 is our floor.

Why Pro (not Flash):
  - Flash produced Geʿez Unicode output but HALLUCINATED content —
    the words were not what the scan printed. Validated by diffing
    against Beta maṣāḥǝft ground truth. Pro matched within known
    textual-variant tolerance on the same page.

This started as a smoke-test scaffold. It now supports resumable batch
OCR runs that write per-page UTF-8 `.txt` plus sidecar `.json`
metadata, which is the concrete first step for Phase 11b (Enoch) and
Phase 12b (Jubilees).
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import Any


def resolve_gemini_api_key() -> str:
    raw = os.environ.get("GEMINI_API_KEY", "").strip()
    if not raw:
        raise RuntimeError("GEMINI_API_KEY not set")
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                if isinstance(obj.get("api_key"), str) and obj["api_key"].strip():
                    return obj["api_key"].strip()
                keys = obj.get("api_keys")
                if isinstance(keys, list):
                    for item in keys:
                        if isinstance(item, str) and item.strip():
                            return item.strip()
        except Exception:
            pass
    return raw


@dataclass
class OcrResult:
    page_number: int
    geez_text: str
    confidence: str
    finish_reason: str
    tokens_in: int
    tokens_out: int
    tokens_thinking: int
    error: str = ""


@dataclass(frozen=True)
class PageHints:
    chapter_hint: str = ""
    opening_hint: str = ""


def render_page_png(pdf_path: pathlib.Path, page_num: int, dpi: int = 400) -> bytes:
    """Render a PDF page to PNG via poppler's pdftocairo."""
    with tempfile.TemporaryDirectory(prefix="geez_ocr_") as tmpdir:
        out_prefix = pathlib.Path(tmpdir) / f"page_{page_num}"
        cmd = [
            "pdftocairo",
            "-png",
            "-r",
            str(dpi),
            "-f",
            str(page_num),
            "-l",
            str(page_num),
            "-singlefile",
            str(pdf_path),
            str(out_prefix),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        png_path = pathlib.Path(f"{out_prefix}.png")
        return png_path.read_bytes()


def call_gemini_pro_geez(
    image_bytes: bytes,
    *,
    book_hint: str = "a classical Ethiopic manuscript",
    chapter_hint: str = "",
    opening_hint: str = "",
    thinking_budget: int = 512,
    max_output_tokens: int = 20000,
) -> OcrResult:
    """OCR a single scan page via Gemini 2.5 Pro, plaintext mode.

    - book_hint: e.g. "Dillmann 1851 Liber Henoch" or "Charles 1895 Jubilees"
    - chapter_hint: e.g. "chapter 1 (ምዕራፍ ፩)"
    - opening_hint: first few words of expected Geʿez to anchor the model
    """
    api_key = resolve_gemini_api_key()

    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt_parts = [
        f"This is a page from {book_hint}.",
    ]
    if chapter_hint:
        prompt_parts.append(f"It shows {chapter_hint}.")
    if opening_hint:
        prompt_parts.append(f"It begins: \"{opening_hint}\"")
    prompt_parts.extend([
        "Transcribe every Geʿez character on this page verbatim using",
        "Ethiopic Unicode (U+1200–U+137F). Preserve the word separator ፡",
        "and the sentence terminator ። (or ፡፡). Preserve Geʿez numerals",
        "(፩ ፪ ፫ ፬ ፭ ፮ ፯ ፰ ፱ ፲ ፳ ፴ ፵ ፶ ፷ ፸ ፹ ፺ ፻ ፼). Skip any running head",
        "that repeats on every page. Skip any English or Latin critical",
        "apparatus at the bottom of the page. Output ONLY the verbatim",
        "Geʿez transcription, nothing else — no prose, no explanation.",
    ])
    prompt = " ".join(prompt_parts)

    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-pro:generateContent?key=" + api_key)
    body = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
        "generationConfig": {
            "temperature": 0.0,
            "max_output_tokens": max_output_tokens,
            "thinkingConfig": {"thinkingBudget": thinking_budget},
        },
    }

    for attempt in range(6):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.loads(r.read())
            cand = resp["candidates"][0]
            usage = resp.get("usageMetadata", {})
            finish = cand.get("finishReason", "?")
            parts = cand.get("content", {}).get("parts") or []
            if not parts:
                if attempt < 5:
                    time.sleep(5 + attempt * 3)
                    continue
                return OcrResult(
                    page_number=-1, geez_text="", confidence="low",
                    finish_reason=finish,
                    tokens_in=usage.get("promptTokenCount", 0),
                    tokens_out=usage.get("candidatesTokenCount", 0),
                    tokens_thinking=usage.get("thoughtsTokenCount", 0),
                    error="no content after retries",
                )
            text = parts[0].get("text", "").strip()
            return OcrResult(
                page_number=-1, geez_text=text,
                confidence="high" if finish == "STOP" else "medium",
                finish_reason=finish,
                tokens_in=usage.get("promptTokenCount", 0),
                tokens_out=usage.get("candidatesTokenCount", 0),
                tokens_thinking=usage.get("thoughtsTokenCount", 0),
            )
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503, 504) and attempt < 5:
                time.sleep(5 + attempt * 4)
                continue
            body_text = e.read().decode("utf-8", "ignore")
            return OcrResult(
                page_number=-1, geez_text="", confidence="low",
                finish_reason="error", tokens_in=0, tokens_out=0,
                tokens_thinking=0, error=f"HTTP {e.code}: {body_text[:300]}",
            )
    return OcrResult(
        page_number=-1, geez_text="", confidence="low",
        finish_reason="error", tokens_in=0, tokens_out=0,
        tokens_thinking=0, error="retries exhausted",
    )


def parse_page_spec(spec: str) -> list[int]:
    """Parse '7,9-12,18' into sorted unique page numbers."""
    if not spec.strip():
        raise ValueError("empty page spec")
    pages: set[int] = set()
    for part in spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if end < start:
                raise ValueError(f"invalid descending range: {token}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))
    if not pages:
        raise ValueError("page spec resolved to zero pages")
    return sorted(pages)


def load_hints_map(path: pathlib.Path | None) -> dict[int, PageHints]:
    """Load per-page hints from JSON.

    Expected shape:
      {
        "7": {"chapter_hint": "chapter 1 (ምዕራፍ ፩)", "opening_hint": "..." },
        "8": {"chapter_hint": "..."}
      }
    """
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, PageHints] = {}
    for k, v in raw.items():
        page = int(k)
        if isinstance(v, str):
            out[page] = PageHints(chapter_hint=v)
            continue
        if not isinstance(v, dict):
            raise ValueError(f"page hint for {k!r} must be string or object")
        out[page] = PageHints(
            chapter_hint=str(v.get("chapter_hint", "")),
            opening_hint=str(v.get("opening_hint", "")),
        )
    return out


def safe_stem(name: str) -> str:
    chars = []
    for ch in name.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {"-", "_"}:
            chars.append(ch)
        else:
            chars.append("_")
    stem = "".join(chars).strip("_")
    while "__" in stem:
        stem = stem.replace("__", "_")
    return stem or "ocr"


def output_base_name(pdf_path: pathlib.Path, page_num: int) -> str:
    return f"{safe_stem(pdf_path.stem)}_p{page_num:04d}"


def output_paths(out_dir: pathlib.Path, pdf_path: pathlib.Path, page_num: int) -> tuple[pathlib.Path, pathlib.Path]:
    stem = output_base_name(pdf_path, page_num)
    return out_dir / f"{stem}.txt", out_dir / f"{stem}.json"


def result_to_dict(
    result: OcrResult,
    *,
    pdf_path: pathlib.Path,
    dpi: int,
    book_hint: str,
    hints: PageHints,
) -> dict[str, Any]:
    return {
        "page_number": result.page_number,
        "source_pdf": str(pdf_path),
        "render_dpi": dpi,
        "book_hint": book_hint,
        "chapter_hint": hints.chapter_hint,
        "opening_hint": hints.opening_hint,
        "confidence": result.confidence,
        "finish_reason": result.finish_reason,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "tokens_thinking": result.tokens_thinking,
        "error": result.error,
        "transcribed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def ocr_pdf_page(
    pdf_path: pathlib.Path,
    page_num: int,
    *,
    dpi: int,
    book_hint: str,
    hints: PageHints,
    thinking_budget: int,
    max_output_tokens: int,
) -> OcrResult:
    image_bytes = render_page_png(pdf_path, page_num, dpi=dpi)
    result = call_gemini_pro_geez(
        image_bytes,
        book_hint=book_hint,
        chapter_hint=hints.chapter_hint,
        opening_hint=hints.opening_hint,
        thinking_budget=thinking_budget,
        max_output_tokens=max_output_tokens,
    )
    result.page_number = page_num
    return result


def write_output_files(
    *,
    out_dir: pathlib.Path,
    pdf_path: pathlib.Path,
    result: OcrResult,
    dpi: int,
    book_hint: str,
    hints: PageHints,
) -> tuple[pathlib.Path, pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path, meta_path = output_paths(out_dir, pdf_path, result.page_number)
    txt_path.write_text(result.geez_text, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            result_to_dict(result, pdf_path=pdf_path, dpi=dpi, book_hint=book_hint, hints=hints),
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return txt_path, meta_path


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="OCR Geʿez pages from a PDF via Gemini 2.5 Pro plaintext mode."
    )
    parser.add_argument("pdf_path", help="Path to the source PDF")
    parser.add_argument(
        "pages",
        help="Page spec like '7', '7-12', or '7,9-12,18'",
    )
    parser.add_argument("--out-dir", help="Write per-page .txt/.json outputs here")
    parser.add_argument(
        "--book-hint",
        default="a classical Ethiopic book",
        help="High-level source hint, e.g. 'Charles 1906 Ethiopic Enoch'",
    )
    parser.add_argument(
        "--chapter-hint",
        default="",
        help="Fallback chapter hint for all pages if --hints-json does not provide one",
    )
    parser.add_argument(
        "--opening-hint",
        default="",
        help="Fallback opening words hint for all pages if --hints-json does not provide one",
    )
    parser.add_argument(
        "--hints-json",
        help="JSON file mapping page numbers to chapter/opening hints",
    )
    parser.add_argument("--dpi", type=int, default=400, help="Render DPI (default: 400)")
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=512,
        help="Gemini thinking budget (default: 512)",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=20000,
        help="Gemini max_output_tokens (default: 20000)",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Pause between pages to reduce burstiness (default: 0)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip pages whose .txt and .json already exist in --out-dir",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which pages would run, but do not OCR them",
    )
    return parser


if __name__ == "__main__":
    import sys
    parser = build_arg_parser()
    args = parser.parse_args()

    pdf = pathlib.Path(args.pdf_path).resolve()
    if not pdf.exists():
        parser.error(f"PDF not found: {pdf}")

    try:
        pages = parse_page_spec(args.pages)
    except ValueError as exc:
        parser.error(str(exc))

    hints_map = load_hints_map(pathlib.Path(args.hints_json)) if args.hints_json else {}
    fallback_hints = PageHints(
        chapter_hint=args.chapter_hint,
        opening_hint=args.opening_hint,
    )
    out_dir = pathlib.Path(args.out_dir).resolve() if args.out_dir else None

    if args.resume and out_dir is None:
        parser.error("--resume requires --out-dir")

    print(f"📖 PDF:   {pdf}")
    print(f"📄 Pages: {', '.join(str(p) for p in pages)}")
    print(f"🧠 Model: Gemini 2.5 Pro plaintext mode (thinkingBudget={args.thinking_budget})")
    if out_dir:
        print(f"💾 Out:   {out_dir}")
    if args.dry_run:
        print("🧪 Dry run only — no OCR requests will be made.")
        sys.exit(0)

    success = 0
    skipped = 0
    failed = 0
    for idx, page_num in enumerate(pages, start=1):
        hints = hints_map.get(page_num, fallback_hints)
        if out_dir is not None and args.resume:
            txt_path, meta_path = output_paths(out_dir, pdf, page_num)
            if txt_path.exists() and meta_path.exists():
                print(f"↷ [{idx}/{len(pages)}] page {page_num}: already present, skipping")
                skipped += 1
                continue

        print(f"→ [{idx}/{len(pages)}] page {page_num}: rendering + OCR…", flush=True)
        try:
            result = ocr_pdf_page(
                pdf,
                page_num,
                dpi=args.dpi,
                book_hint=args.book_hint,
                hints=hints,
                thinking_budget=args.thinking_budget,
                max_output_tokens=args.max_output_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - CLI should keep going page-to-page
            failed += 1
            print(f"  ✗ page {page_num}: {exc}")
            continue

        if out_dir is not None:
            txt_path, meta_path = write_output_files(
                out_dir=out_dir,
                pdf_path=pdf,
                result=result,
                dpi=args.dpi,
                book_hint=args.book_hint,
                hints=hints,
            )
            print(
                f"  ✓ page {page_num}: {result.confidence} "
                f"finish={result.finish_reason} chars={len(result.geez_text)} "
                f"→ {txt_path.name}, {meta_path.name}"
            )
        else:
            print(f"  ✓ finish={result.finish_reason} chars={len(result.geez_text)}")
            print()
            print(result.geez_text[:1200])
            print()

        if result.error:
            print(f"  ! note: {result.error}")
        if result.geez_text and not result.error:
            success += 1
        else:
            failed += 1

        if args.sleep_seconds and idx != len(pages):
            time.sleep(args.sleep_seconds)

    print()
    print(
        f"Done. success={success} skipped={skipped} failed={failed} total={len(pages)}"
    )
    sys.exit(1 if failed else 0)
