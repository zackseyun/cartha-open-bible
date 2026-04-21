#!/usr/bin/env python3
"""rescue_low_conf_focused.py — per-verse focused rescue.

For verses where the chapter-level rescue is overwhelmed by too many
scan pages, do a tighter adjudication:
  - Identify the SPECIFIC page each verse is on (by scanning the
    transcribed per-page text files)
  - Send ONLY that page (or adjacent pages if the verse straddles
    two) to the adjudicator
  - Explicitly tell the model which page it's looking at
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import re
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
TRANSCRIBED = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"

TOOL_NAME = "submit_focused_adjudication"
PROMPT_VERSION = "rescue_focused_v1_2026-04-20"


SYSTEM_PROMPT = """You are a Greek paleographer doing a FOCUSED adjudication on a single verse.

You are shown:
  1. ONE (or at most two) specific scan page image(s) from Swete 1909 LXX.
  2. Our OCR of that exact page (as text), so you can reference it.
  3. The target verse reference (e.g. "ADE 4:26").
  4. Up to 4 candidate Greek readings (ours/first1k/rahlfs/amicarelli).

Your job: find the verse on the page image and emit what Swete PRINTS there.

Rules:
  - The image is the source of truth.
  - Our OCR text of the page is given ONLY as a guide to where on the page the verse sits — use it to orient yourself, don't trust it for the final Greek.
  - If the verse is genuinely not on the page (e.g. chapter ended earlier, or the numbering scheme differs), set confidence=low and verdict=neither and explain.

EXPLICIT CONFIDENCE RUBRIC (apply strictly):

  HIGH:
    - You can clearly read every character of the verse in the scan,
      including all diacritics (accents, breathings, iota subscripts).
    - The reading you output exactly matches what is printed, or
      matches one of the 4 candidates exactly.
    - No visible smudging, faded ink, torn paper, or ambiguous letterforms
      in the verse area.

  MEDIUM:
    - You can read the verse substantively, but there is ambiguity about
      specific characters (e.g. ε vs ω on a worn letter, a diacritic
      that could be acute or circumflex, a letter that could be α or δ).
    - You have made a best-guess call but acknowledge the scan permits
      an alternative reading a specialist might prefer.
    - Verse boundary or punctuation placement is genuinely ambiguous.

  LOW:
    - The verse is not legibly on the provided scan page.
    - Severe damage, ink bleed, or missing text.
    - You are essentially relying on the candidate readings alone,
      without visual verification.

Calibrate honestly: it is better to mark MEDIUM and be correct about
your uncertainty than to mark HIGH and be overconfident.

Per verse, output via submit_focused_adjudication:
  - verse: int
  - verdict_greek: the definitive Greek text as printed
  - verdict: "ours" | "first1k" | "amicarelli" | "rahlfs_match" | "neither" | "swete_consensus" | "both_ok"
  - reasoning: 1-2 sentences explaining what you saw on the scan and why you made this confidence call
  - confidence: "high" | "medium" | "low"
"""


FOCUSED_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Focused per-verse adjudication verdict.",
        "parameters": {
            "type": "object",
            "properties": {
                "verse": {"type": "integer"},
                "verdict_greek": {"type": "string"},
                "verdict": {"type": "string", "enum": ["ours", "first1k", "amicarelli", "rahlfs_match", "neither", "swete_consensus", "both_ok"]},
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["verse", "verdict_greek", "verdict", "reasoning", "confidence"],
        },
    },
}


def azure_endpoint() -> str:
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "https://eastus2.api.cognitive.microsoft.com").rstrip("/")


def azure_deployment() -> str:
    return (
        os.environ.get("AZURE_OPENAI_VISION_DEPLOYMENT_ID")
        or os.environ.get("AZURE_OPENAI_DEPLOYMENT_ID")
        or "gpt-5-deployment"
    )


def azure_api_version() -> str:
    return os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")


# Chapter -> verse marker regex. Swete prints verse numbers as superscript
# digits preceded by space and followed by text. We look for " Nword" where
# N is the verse number.

def find_page_for_verse(book: str, chapter: int, verse: int) -> list[int]:
    """Return scan pages that contain this verse, by matching the Greek OCR
    content against each page's transcribed text. More reliable than
    running-head parsing on Additions pages."""
    vol = lxx_swete.DEUTEROCANONICAL_BOOKS[book][0]
    first = lxx_swete.DEUTEROCANONICAL_BOOKS[book][1]
    last = lxx_swete.DEUTEROCANONICAL_BOOKS[book][2]
    if book == "TOB":
        last = max(last, 870)
    if book == "ADE":
        last = max(last, 800)

    # Load the verse's Greek from our OCR (ours_only_corpus), then find
    # pages whose transcription contains a distinctive substring from it.
    our_greek = ""
    try:
        for src in lxx_swete.iter_source_verses(book):
            if src.chapter == chapter and src.verse == verse:
                our_greek = src.greek_text
                break
    except Exception:
        pass
    if not our_greek:
        # Fall back to first1k
        try:
            v = first1kgreek.load_verse(book, chapter, verse)
            if v:
                our_greek = v.greek_text
        except Exception:
            pass
    if not our_greek:
        return []

    # Extract distinctive Greek words (length >= 5 chars, not in a stop list)
    import unicodedata

    def nfd_nomarks(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()

    words = re.findall(r"[\u0370-\u03ff\u1f00-\u1fff]{5,}", our_greek)
    # Pick 5-8 distinctive words from the verse
    probes = [nfd_nomarks(w) for w in words if len(w) >= 5][:8]
    if not probes:
        return []

    found: list[tuple[int, int]] = []
    for p in range(first, last + 1):
        path = TRANSCRIBED / f"vol{vol}_p{p:04d}.txt"
        if not path.exists():
            continue
        text_norm = nfd_nomarks(path.read_text(encoding="utf-8"))
        hits = sum(1 for pr in probes if pr in text_norm)
        if hits >= 3:  # at least 3 of our probe words appear on this page
            found.append((p, hits))
    # Sort by hits desc, then page asc
    found.sort(key=lambda x: (-x[1], x[0]))
    return [p for p, _ in found]


def load_candidates(book: str, chapter: int, verse: int) -> dict:
    out = {"ours": "", "first1k": "", "rahlfs": "", "amicarelli": ""}
    try:
        for src in lxx_swete.iter_source_verses(book):
            if src.chapter == chapter and src.verse == verse:
                out["ours"] = src.greek_text
                break
    except Exception:
        pass
    try:
        v = first1kgreek.load_verse(book, chapter, verse)
        if v:
            out["first1k"] = v.greek_text
    except Exception:
        pass
    try:
        v = rahlfs.load_verse(book, chapter, verse)
        if v:
            out["rahlfs"] = v.greek_text
    except Exception:
        pass
    try:
        v = swete_amicarelli.load_verse(book, chapter, verse)
        if v:
            out["amicarelli"] = v.greek_text
    except Exception:
        pass
    return out


def call_azure(page_images: list[tuple[int, bytes]], user_text: str, max_tokens: int = 6000) -> dict:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")
    parts: list[dict] = [{"type": "text", "text": user_text}]
    for pnum, img in page_images:
        parts.append({"type": "text", "text": f"--- Page {pnum} (high-res scan) ---"})
        b64 = base64.b64encode(img).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    url = f"{azure_endpoint()}/openai/deployments/{azure_deployment()}/chat/completions?api-version={azure_api_version()}"
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": parts},
        ],
        "max_completion_tokens": max_tokens,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [FOCUSED_TOOL],
    }

    for attempt in range(8):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "api-key": api_key},
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read())
            tc = resp["choices"][0]["message"].get("tool_calls") or []
            if not tc:
                raise RuntimeError("No tool call")
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


def process_verse(book: str, chapter: int, verse: int, image_width: int = 3000) -> dict:
    pages = find_page_for_verse(book, chapter, verse)
    if not pages:
        return {"book": book, "chapter": chapter, "verse": verse, "error": "page not found in transcribed text"}
    # Limit to at most 2 pages for focus
    pages = pages[:2]
    vol = lxx_swete.DEUTEROCANONICAL_BOOKS[book][0]
    images: list[tuple[int, bytes]] = []
    ocr_parts: list[str] = []
    for p in pages:
        # Fetch image with retries
        img = None
        for attempt in range(4):
            try:
                img, _ = transcribe_source.fetch_swete_image(vol, p, image_width)
                break
            except Exception:
                time.sleep(2 + attempt * 2)
        if img is None:
            continue
        images.append((p, img))
        txt_path = TRANSCRIBED / f"vol{vol}_p{p:04d}.txt"
        if txt_path.exists():
            ocr_parts.append(f"--- Page {p} OCR ---\n{txt_path.read_text(encoding='utf-8')[:3500]}")
    if not images:
        return {"book": book, "chapter": chapter, "verse": verse, "error": "no images fetched"}

    cands = load_candidates(book, chapter, verse)
    lines = [
        f"Book: {lxx_swete.DEUTEROCANONICAL_BOOKS[book][3]} ({book})",
        f"Target verse reference: {book} {chapter}:{verse}",
        f"Scan pages attached: {[p for p, _ in images]}",
        "",
        "Greek candidates:",
        f"  A (ours):       {cands.get('ours','')}",
        f"  B (first1k):    {cands.get('first1k','')}",
        f"  C (rahlfs):     {cands.get('rahlfs','')}",
        f"  D (amicarelli): {cands.get('amicarelli','')}",
        "",
        "Our OCR of the scan pages (for orientation only, not authority):",
        "",
        *ocr_parts,
        "",
        f"Emit the Swete printed reading for verse {verse}. Find it on the image, not in the OCR text.",
    ]
    user_text = "\n".join(lines)

    try:
        result = call_azure(images, user_text)
    except Exception as e:
        return {"book": book, "chapter": chapter, "verse": verse, "error": str(e)}

    # Update adjudication file
    adj_path = ADJ_DIR / f"{book}_{chapter:03d}.json"
    adj_data = json.loads(adj_path.read_text())
    for v in adj_data.get("verdicts", []):
        if v.get("verse") == verse:
            v["verdict_greek"] = result["verdict_greek"]
            v["verdict"] = result["verdict"]
            v["reasoning"] = result["reasoning"]
            v["confidence"] = result["confidence"]
            v["focused_pass"] = True
            break
    adj_data["focused_pass_applied"] = True
    adj_data["focused_timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
    adj_path.write_text(json.dumps(adj_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"book": book, "chapter": chapter, "verse": verse, "verdict": result["verdict"],
            "confidence": result["confidence"], "page": pages[0]}


def build_worklist(target_confs: set[str] = frozenset({"low"})) -> list[tuple[str, int, int]]:
    wl = []
    for p in sorted(ADJ_DIR.glob("*.json")):
        data = json.loads(p.read_text())
        for v in data.get("verdicts", []):
            if v.get("confidence") in target_confs:
                wl.append((data.get("book"), data.get("chapter"), v.get("verse")))
    return wl


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-medium", action="store_true",
                        help="Also re-run on medium-confidence verses")
    parser.add_argument("--image-width", type=int, default=3000)
    args = parser.parse_args()

    target = {"low", "medium"} if args.include_medium else {"low"}
    wl = build_worklist(target_confs=target)
    print(f"Focused worklist: {len(wl)} verses (confidences={sorted(target)}, image_width={args.image_width}px)")
    for b, c, v in wl:
        print(f"  {b} {c}:{v}")

    if not wl:
        return 0

    ok = failed = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(process_verse, b, c, v, args.image_width): (b, c, v) for b, c, v in wl}
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
                print(f"  OK   {b} {c}:{v}  verdict={r['verdict']}  conf={r['confidence']}  page={r['page']}", flush=True)
                ok += 1
    print(f"\nDone: ok={ok}  failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
