#!/usr/bin/env python3
"""lxx_swete_ai.py — AI-based chapter parser for Swete LXX pages.

Used when the regex parser in lxx_swete.py fails or produces incomplete
results on a specific chapter. Feeds Azure GPT-5.4 vision the scanned
pages containing the chapter and asks for a structured list of verses.

Outputs match SwtVerse's interface so results can merge cleanly with
the regex parser.

Cached results live under:
  sources/lxx/swete/parsed_ai/<BOOK>_<CHAPTER>.json

Usage:
  python3 tools/lxx_swete_ai.py --book TOB --chapter 10
  python3 tools/lxx_swete_ai.py --gap-report  # list chapters needing re-parse
  python3 tools/lxx_swete_ai.py --fill-all-gaps
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
    import lxx_swete
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import transcribe_source  # type: ignore
    import lxx_swete  # type: ignore

REPO_ROOT = transcribe_source.REPO_ROOT
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
PARSED_AI_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "parsed_ai"
PROMPT_VERSION = "gap_parse_v1_2026-04-20"
TOOL_NAME = "submit_chapter_verses"

# Known chapter counts for validation / --fill-all-gaps
EXPECTED_VERSE_COUNTS: dict[str, dict[int, int]] = {
    "1ES": {1: 55, 2: 30, 3: 24, 4: 63, 5: 71, 6: 34, 7: 15, 8: 92, 9: 55},
    "TOB": {1: 22, 2: 14, 3: 17, 4: 21, 5: 22, 6: 17, 7: 18, 8: 21,
            9: 6, 10: 13, 11: 18, 12: 22, 13: 18, 14: 15},
    "WIS": {1: 16, 2: 24, 3: 19, 4: 20, 5: 23, 6: 25, 7: 30, 8: 21,
            9: 18, 10: 21, 11: 26, 12: 27, 13: 19, 14: 31, 15: 19,
            16: 29, 17: 21, 18: 25, 19: 22},
    "JDT": {1: 16, 2: 28, 3: 10, 4: 15, 5: 24, 6: 21, 7: 32, 8: 36,
            9: 14, 10: 23, 11: 23, 12: 20, 13: 20, 14: 19, 15: 14, 16: 25},
    "SIR": {},  # 51 chapters, variable verse counts — skip validation
    "1MA": {1: 64, 2: 70, 3: 60, 4: 61, 5: 68, 6: 63, 7: 50, 8: 32,
            9: 73, 10: 89, 11: 74, 12: 53, 13: 53, 14: 49, 15: 41, 16: 24},
    "2MA": {1: 36, 2: 33, 3: 40, 4: 50, 5: 27, 6: 31, 7: 42, 8: 36,
            9: 29, 10: 38, 11: 38, 12: 45, 13: 26, 14: 46, 15: 39},
    "3MA": {1: 29, 2: 33, 3: 30, 4: 21, 5: 51, 6: 41, 7: 23},
    "4MA": {1: 35, 2: 24, 3: 21, 4: 26, 5: 38, 6: 35, 7: 23, 8: 29,
            9: 32, 10: 21, 11: 27, 12: 19, 13: 27, 14: 20, 15: 32,
            16: 25, 17: 24, 18: 24},
    "BAR": {1: 22, 2: 35, 3: 38, 4: 37, 5: 9},
    "LJE": {1: 73},
    "ADA": {},  # Greek Daniel additions — complex structure, skip validation
    "ADE": {},  # Greek Esther chapter lettering — skip validation
}


SYSTEM_PROMPT = """You are a Greek-text parser extracting chapter+verse structure from Swete's 1909 LXX edition.

You will receive:
1. One or more scan page images for a chapter.
2. The book name + chapter number (Arabic numeral).
3. The current UTF-8 transcription of those pages' BODY sections.

Your job: produce a STRICT, ORDERED list of verses for that chapter by calling the function `submit_chapter_verses` exactly once.

Rules:

1. Return only verses that belong to the SPECIFIED chapter. Verses from adjacent chapters (same page but different chapter) must be excluded.
2. Each verse's Greek text must come from the transcription — do not fabricate Greek from the image alone. If transcription has errors, keep the transcribed form (review is a separate pass).
3. If the chapter's text spans the boundary between the transcription's chapter markers, use the images to resolve which verses belong to the requested chapter.
4. Swete's marginal line numbers (digits in parens like "(25)" or standalone digits at line start) are NOT verse markers. Ignore them.
5. Include ALL verses of the requested chapter, even if some were omitted by the transcription. If a verse is clearly visible on the image but missing from the transcription, still include it (using your best read of the image for that verse).
6. Verse numbers must be strictly increasing within the chapter, starting at 1 (or the chapter's actual first verse number if Swete's text genuinely begins mid-verse).

For books with parallel recensions (Tobit B-text + S-text in Swete): return only the B-text (primary, Codex Vaticanus) recension.
"""


PARSE_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit the ordered list of verses for a chapter.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": ["book", "chapter", "verses", "notes"],
            "properties": {
                "book": {"type": "string"},
                "chapter": {"type": "integer"},
                "verses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["verse", "greek"],
                        "properties": {
                            "verse": {"type": "integer"},
                            "greek": {"type": "string"},
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


def locate_chapter_pages(book_code: str, chapter: int) -> list[int]:
    """Return scan pages whose running head chapter includes `chapter`,
    plus one page on each side as safety margin."""
    vol, first, last = lxx_swete.book_page_range(book_code)
    pages_for_chapter = []
    for p in range(first, last + 1):
        path = TRANSCRIBED_DIR / f"vol{vol}_p{p:04d}.txt"
        if not path.exists():
            continue
        rh = lxx_swete.parse_running_head_chapter(path.read_text(encoding="utf-8"))
        if rh is None:
            # Title/indeterminate page — include it as context
            pages_for_chapter.append(p)
            continue
        if abs(rh - chapter) <= 1:
            pages_for_chapter.append(p)
    return pages_for_chapter


def call_azure_parse(
    images: list[bytes],
    book_title: str,
    chapter: int,
    transcripts: list[str],
    *,
    max_tokens: int,
) -> dict[str, Any]:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    user_parts: list[dict[str, Any]] = [{
        "type": "text",
        "text": f"Book: {book_title}\nChapter: {chapter}\n\nTranscriptions of the pages containing this chapter:\n\n"
                + "\n\n---PAGE BREAK---\n\n".join(transcripts),
    }]
    for img in images:
        b64 = base64.b64encode(img).decode("ascii")
        user_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    url = f"{azure_endpoint()}/openai/deployments/{azure_deployment()}/chat/completions?api-version={azure_api_version()}"
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_parts},
        ],
        "temperature": 0.0,
        "max_completion_tokens": max_tokens,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [PARSE_TOOL],
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
    return json.loads(fn.get("arguments") or "{}")


def parse_chapter(book_code: str, chapter: int, width: int = 1500, max_tokens: int = 8000) -> dict[str, Any]:
    """Parse a single chapter. Returns the raw Azure response plus metadata."""
    pages = locate_chapter_pages(book_code, chapter)
    if not pages:
        raise RuntimeError(f"No pages located for {book_code} ch {chapter}")

    vol, _, _ = lxx_swete.book_page_range(book_code)
    book_title = lxx_swete.DEUTEROCANONICAL_BOOKS[book_code][3]
    transcripts: list[str] = []
    images: list[bytes] = []
    for p in pages:
        path = TRANSCRIBED_DIR / f"vol{vol}_p{p:04d}.txt"
        transcripts.append(f"[p{p}]\n{path.read_text(encoding='utf-8')}")
        img_bytes, _ = transcribe_source.fetch_swete_image(vol, p, width)
        images.append(img_bytes)

    started = time.time()
    result = call_azure_parse(images, book_title, chapter, transcripts, max_tokens=max_tokens)
    duration = round(time.time() - started, 2)

    return {
        "book": book_code,
        "chapter": chapter,
        "pages": pages,
        "verses": result.get("verses", []),
        "notes": result.get("notes", ""),
        "parsed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": duration,
        "prompt_version": PROMPT_VERSION,
    }


def chapter_output_path(book_code: str, chapter: int) -> pathlib.Path:
    return PARSED_AI_DIR / f"{book_code}_{chapter:03d}.json"


def save_chapter(data: dict[str, Any]) -> pathlib.Path:
    PARSED_AI_DIR.mkdir(parents=True, exist_ok=True)
    path = chapter_output_path(data["book"], data["chapter"])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def identify_gaps() -> list[tuple[str, int, str]]:
    """Walk regex-parser output and return chapters that fail validation.

    Returns [(book_code, chapter, reason), ...].
    """
    gaps = []
    for book, expected in EXPECTED_VERSE_COUNTS.items():
        if not expected:
            continue
        try:
            chapters: dict[int, list[int]] = {}
            for v in lxx_swete.iter_source_verses(book):
                chapters.setdefault(v.chapter, []).append(v.verse)
        except Exception as exc:
            gaps.append((book, 0, f"parser-error: {exc}"))
            continue
        for ch, exp_last in expected.items():
            vs = chapters.get(ch, [])
            if not vs:
                gaps.append((book, ch, "missing"))
            elif min(vs) > 2:
                gaps.append((book, ch, f"starts-at-{min(vs)}"))
            elif max(vs) < exp_last - 2:
                gaps.append((book, ch, f"ends-at-{max(vs)}-exp-{exp_last}"))
    return gaps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book")
    ap.add_argument("--chapter", type=int)
    ap.add_argument("--gap-report", action="store_true")
    ap.add_argument("--fill-all-gaps", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--force", action="store_true", help="Re-parse even if cached")
    args = ap.parse_args()

    if args.gap_report:
        gaps = identify_gaps()
        print(f"{'Book':<6} {'Ch':>3}  Reason")
        for b, c, r in gaps:
            print(f"{b:<6} {c:>3}  {r}")
        print(f"\n{len(gaps)} gap(s)")
        return 0

    if args.fill_all_gaps:
        gaps = identify_gaps()
        if not gaps:
            print("No gaps.")
            return 0
        print(f"Filling {len(gaps)} gap(s) with concurrency {args.concurrency}...")
        results: dict[tuple[str, int], tuple[str | None, str | None]] = {}

        def worker(book: str, ch: int):
            out = chapter_output_path(book, ch)
            if out.exists() and not args.force:
                return book, ch, None, "cached"
            try:
                data = parse_chapter(book, ch, max_tokens=args.max_tokens)
                save_chapter(data)
                return book, ch, None, f"{len(data['verses'])}v in {data['duration_seconds']}s"
            except Exception as exc:
                return book, ch, f"{type(exc).__name__}: {exc}", None

        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(worker, b, c) for b, c, _ in gaps if c > 0]
            for fut in as_completed(futures):
                b, c, err, info = fut.result()
                if err:
                    print(f"  FAIL {b} ch{c}: {err[:200]}", flush=True)
                else:
                    print(f"  OK   {b} ch{c}: {info}", flush=True)
        return 0

    if not (args.book and args.chapter):
        ap.error("Provide --book and --chapter, or --gap-report, or --fill-all-gaps")

    data = parse_chapter(args.book, args.chapter, max_tokens=args.max_tokens)
    out = save_chapter(data)
    print(f"Saved {out}")
    print(f"{args.book} ch{args.chapter}: {len(data['verses'])} verses")
    print(f"Duration: {data['duration_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
