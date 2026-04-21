#!/usr/bin/env python3
"""rescue_manual_pages.py — adjudicate specific verses with manually-
specified scan pages.

For the cases where content-matching fails (short verses with common
words) or where the adjudication `pages` list was never correct
(books/chapters whose range excludes pages we later discovered).

Usage: edit MANUAL_TARGETS at the top of this file and run.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402
import first1kgreek  # noqa: E402
import rahlfs  # noqa: E402
import swete_amicarelli  # noqa: E402
import transcribe_source  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
ADJ_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "adjudications"

# Hand-curated (book, chapter, verse, [pages]) targets.
# Pages were verified by direct visual inspection of the scans.
MANUAL_TARGETS: list[tuple[str, int, int, list[int]]] = [
    # SIR 3:5, 3:7 — these are visible on vol2 p665 (not 666-667).
    ("SIR", 3, 5, [665]),
    ("SIR", 3, 7, [665]),

    # SIR 33:14-16 — visible on vol2 p728, where Swete's alternate
    # Sirach numbering prints these content-lines in the XXX / XXXIII
    # overlap section. Prior rescue runs were pointed at 733-734, which
    # is why they honestly stayed LOW.
    ("SIR", 33, 14, [728]),
    ("SIR", 33, 15, [728]),
    ("SIR", 33, 16, [728]),

    # SIR 33:17 — current corpus maps this verse to the prayer section
    # visible on vol2 p734.
    ("SIR", 33, 17, [734]),
]


SYSTEM_PROMPT_SIRACH_OVERRIDE = """You are a Greek paleographer doing a FOCUSED adjudication on a single Sirach verse.

IMPORTANT: Swete's 1909 LXX uses a rearranged chapter numbering for Sirach that differs from modern critical editions. In particular:

  - Modern Sir 30:25-33:13a  ==  Swete Sir XXXIII 13b-XXXVI 16a (shifted +3)
  - Modern Sir 33:13b-36:16a ==  Swete Sir XXX 25-XXXIII 13a   (shifted -3)

So for the target verse you are given:
  - If we say "SIR 33:14", look for Swete's label "XXX 27" or nearby
    (modern 33:13b-36:16 ≈ Swete XXX 25 onwards, so 33:14 ≈ XXX 28/29).
  - Actually the simplest rule for these verses: **find the verse by
    its Greek content match against the candidates**, not by number.
    The candidates A/B/C/D contain the Greek text we expect; locate
    that text on the scan page, and record what Swete prints.

You are shown 2-3 high-resolution scan page images of Swete's 1909 LXX and up to 4 candidate Greek readings. Your job: find the target verse on the scan by matching its Greek content and emit what Swete PRINTS.

EXPLICIT CONFIDENCE RUBRIC (apply strictly):

  HIGH: every character readable, diacritics clear, no damage in verse area
  MEDIUM: readable substantively but specific characters ambiguous
  LOW: verse not legibly visible on any provided page

Calibrate honestly: better MEDIUM-and-correct than HIGH-and-overconfident.

Per verse, output via submit_manual_adjudication:
  - verse: int
  - verdict_greek: the definitive Greek text as printed
  - verdict: "ours" | "first1k" | "amicarelli" | "rahlfs_match" | "neither" | "swete_consensus" | "both_ok"
  - reasoning: 1-2 sentences
  - confidence: "high" | "medium" | "low"
  - page_used: int -- which page number you found the verse on
"""


SYSTEM_PROMPT = """You are a Greek paleographer doing a FOCUSED adjudication on a single verse.

You are shown 2-3 high-resolution scan page images of Swete's 1909 LXX and up to 4 candidate Greek readings. Your job: find the target verse on the scan and emit what Swete PRINTS.

EXPLICIT CONFIDENCE RUBRIC (apply strictly):

  HIGH:
    - You can clearly read every character including diacritics
    - Reading matches scan exactly (either a candidate or fresh transcription)
    - No visible smudging, fading, or ambiguous letterforms in the verse area

  MEDIUM:
    - Verse readable substantively but specific characters ambiguous
    - Best-guess call made; scan permits alternative a specialist might prefer
    - Verse boundary or punctuation genuinely ambiguous

  LOW:
    - Verse not legibly visible on any provided page
    - Severe damage or missing text
    - Relying on candidates without visual verification

Calibrate honestly: better MEDIUM-and-correct than HIGH-and-overconfident.

Per verse, output via submit_manual_adjudication:
  - verse: int
  - verdict_greek: the definitive Greek text as printed
  - verdict: "ours" | "first1k" | "amicarelli" | "rahlfs_match" | "neither" | "swete_consensus" | "both_ok"
  - reasoning: 1-2 sentences explaining what you saw and your confidence call
  - confidence: "high" | "medium" | "low"
  - page_used: int -- which of the provided pages contains the target verse
"""

MANUAL_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_manual_adjudication",
        "description": "Submit adjudication verdict for this verse.",
        "parameters": {
            "type": "object",
            "properties": {
                "verse": {"type": "integer"},
                "verdict_greek": {"type": "string"},
                "verdict": {"type": "string", "enum": ["ours", "first1k", "amicarelli", "rahlfs_match", "neither", "swete_consensus", "both_ok"]},
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "page_used": {"type": "integer"},
            },
            "required": ["verse", "verdict_greek", "verdict", "reasoning", "confidence"],
        },
    },
}


def azure_endpoint() -> str:
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")


def azure_deployment() -> str:
    return os.environ.get("AZURE_OPENAI_VISION_DEPLOYMENT_ID") or os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID") or "gpt-5-deployment"


def azure_api_version() -> str:
    return os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")


def load_candidates(book: str, chapter: int, verse: int) -> dict:
    out = {"ours": "", "first1k": "", "rahlfs": "", "amicarelli": ""}
    try:
        for src in lxx_swete.iter_source_verses(book):
            if src.chapter == chapter and src.verse == verse:
                out["ours"] = src.greek_text
                break
    except Exception:
        pass
    for name, loader in [("first1k", first1kgreek.load_verse), ("rahlfs", rahlfs.load_verse), ("amicarelli", swete_amicarelli.load_verse)]:
        try:
            v = loader(book, chapter, verse)
            if v:
                out[name] = v.greek_text
        except Exception:
            pass
    return out


def call_azure(page_images: list[tuple[int, bytes]], user_text: str) -> dict:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")
    parts: list[dict] = [{"type": "text", "text": user_text}]
    for pnum, img in page_images:
        parts.append({"type": "text", "text": f"--- Page {pnum} (high-res scan) ---"})
        b64 = base64.b64encode(img).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    url = f"{azure_endpoint()}/openai/deployments/{azure_deployment()}/chat/completions?api-version={azure_api_version()}"
    # Pick system prompt based on book (Sirach gets the numbering-override note)
    sp = SYSTEM_PROMPT_SIRACH_OVERRIDE if "Book: Sirach" in user_text else SYSTEM_PROMPT
    payload = {
        "messages": [
            {"role": "system", "content": sp},
            {"role": "user", "content": parts},
        ],
        "max_completion_tokens": 6000,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": "submit_manual_adjudication"}},
        "tools": [MANUAL_TOOL],
    }
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                          headers={"Content-Type": "application/json", "api-key": api_key})
            with urllib.request.urlopen(req, timeout=200) as r:
                resp = json.loads(r.read())
            tc = resp["choices"][0]["message"].get("tool_calls") or []
            if not tc:
                raise RuntimeError("no tool call")
            return json.loads(tc[0]["function"]["arguments"])
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code in (429, 500, 503, 504) and attempt < 7:
                time.sleep(5 + attempt * 4)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}")
        except Exception:
            if attempt < 7:
                time.sleep(5)
                continue
            raise
    raise RuntimeError("retries exhausted")


def process(book: str, chapter: int, verse: int, pages: list[int], image_width: int = 4000) -> dict:
    vol = lxx_swete.DEUTEROCANONICAL_BOOKS[book][0]
    images: list[tuple[int, bytes]] = []
    for p in pages:
        img = None
        for attempt in range(4):
            try:
                img, _ = transcribe_source.fetch_swete_image(vol, p, image_width)
                break
            except Exception:
                time.sleep(2 + attempt * 2)
        if img is not None:
            images.append((p, img))
    if not images:
        return {"book": book, "chapter": chapter, "verse": verse, "error": "no images fetched"}

    cands = load_candidates(book, chapter, verse)
    lines = [
        f"Book: {lxx_swete.DEUTEROCANONICAL_BOOKS[book][3]} ({book})",
        f"Target: {book} {chapter}:{verse}",
        f"Scan pages attached: {pages}",
        "",
        "Greek candidates:",
        f"  A (ours):       {cands.get('ours','')}",
        f"  B (first1k):    {cands.get('first1k','')}",
        f"  C (rahlfs):     {cands.get('rahlfs','')}",
        f"  D (amicarelli): {cands.get('amicarelli','')}",
        "",
        f"Find {book} {chapter}:{verse} on the attached pages and emit what Swete prints. Locate it by its verse number marker (small superscript integer before the Greek word).",
    ]
    try:
        result = call_azure(images, "\n".join(lines))
    except Exception as e:
        return {"book": book, "chapter": chapter, "verse": verse, "error": str(e)}

    # Update adjudication file
    adj_path = ADJ_DIR / f"{book}_{chapter:03d}.json"
    adj_data = json.loads(adj_path.read_text())
    # Ensure pages list includes the ones we used
    existing = set(adj_data.get("pages", []))
    adj_data["pages"] = sorted(existing | set(pages))
    for v in adj_data.get("verdicts", []):
        if v.get("verse") == verse:
            v["verdict_greek"] = result["verdict_greek"]
            v["verdict"] = result["verdict"]
            v["reasoning"] = result["reasoning"]
            v["confidence"] = result["confidence"]
            v["manual_pass"] = True
            v["manual_page_used"] = result.get("page_used")
            break
    adj_data["manual_pass_applied"] = True
    adj_data["manual_timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
    adj_path.write_text(json.dumps(adj_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"book": book, "chapter": chapter, "verse": verse,
            "verdict": result["verdict"], "confidence": result["confidence"],
            "page_used": result.get("page_used"), "pages_sent": pages}


def main():
    print(f"Manual-pages rescue: {len(MANUAL_TARGETS)} targets")
    ok = failed = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(process, b, c, v, p): (b, c, v) for b, c, v, p in MANUAL_TARGETS}
        for fut in as_completed(futs):
            b, c, v = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                print(f"  FAIL {b} {c}:{v}: {e}", flush=True)
                failed += 1
                continue
            if r.get("error"):
                print(f"  FAIL {b} {c}:{v}: {r['error']}", flush=True)
                failed += 1
            else:
                print(f"  OK   {b} {c}:{v}  verdict={r['verdict']}  conf={r['confidence']}  page_used={r.get('page_used')}", flush=True)
                ok += 1
    print(f"\nDone: ok={ok}  failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
