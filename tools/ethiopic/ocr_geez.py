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

This module is a SCAFFOLD — the interface below is frozen. Actual
bulk OCR runs happen in Phase 11b (Enoch) and Phase 12b (Jubilees).
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


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


def render_page_png(pdf_path: pathlib.Path, page_num: int, dpi: int = 400) -> bytes:
    """Render a PDF page to PNG via poppler's pdftocairo."""
    out_prefix = f"/tmp/geez_ocr_page_{page_num}"
    cmd = ["pdftocairo", "-png", "-r", str(dpi), "-f", str(page_num),
           "-l", str(page_num), "-singlefile", str(pdf_path), out_prefix]
    subprocess.run(cmd, check=True, capture_output=True)
    p = pathlib.Path(f"{out_prefix}.png")
    data = p.read_bytes()
    p.unlink(missing_ok=True)
    return data


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
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

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


if __name__ == "__main__":
    # Smoke test
    import sys
    if len(sys.argv) < 3:
        print("Usage: ocr_geez.py <pdf_path> <page_num> [book_hint] [chapter_hint]")
        sys.exit(1)
    pdf = pathlib.Path(sys.argv[1])
    pg = int(sys.argv[2])
    book = sys.argv[3] if len(sys.argv) > 3 else "a classical Ethiopic book"
    chap = sys.argv[4] if len(sys.argv) > 4 else ""
    print(f"Rendering {pdf.name} page {pg} at 400 DPI...")
    img = render_page_png(pdf, pg)
    print(f"  {len(img)} bytes PNG")
    print("Calling Gemini 2.5 Pro (plaintext mode)...")
    result = call_gemini_pro_geez(img, book_hint=book, chapter_hint=chap)
    print(f"\n--- Result ---")
    print(f"finish: {result.finish_reason}")
    print(f"tokens: in={result.tokens_in} out={result.tokens_out} thinking={result.tokens_thinking}")
    print(f"chars:  {len(result.geez_text)}")
    print(f"error:  {result.error or '(none)'}")
    print()
    print(result.geez_text[:800])
