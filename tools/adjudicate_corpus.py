#!/usr/bin/env python3
"""adjudicate_corpus.py — scan-grounded verse adjudication.

For every verse where our OCR disagrees with First1KGreek (minor or
major mismatch), this tool:

  1. Fetches the Swete scan page image(s) the verse is printed on.
  2. Sends Azure GPT-5.4 vision the IMAGE, our candidate text, and the
     First1KGreek candidate text.
  3. Asks: "What does the scan ACTUALLY say for this verse?"
  4. Records the verdict, reasoning, and confidence — grounded in the
     printed page, not in either transcription.

No text is copied from First1KGreek into our corpus. First1KGreek's
transcription is shown to the model only as a second opinion to help
it focus on the right spot; the final Greek text is adjudicated
against the scan image.

Per-chapter batched (one call per chapter containing disagreements)
to keep API volume reasonable.

Output:
  sources/lxx/swete/adjudications/<BOOK>_<CHAPTER>.json
    {verse: {"verdict_greek": "...", "verdict": "ours|first1k|other",
             "reasoning": "...", "confidence": "high|medium|low"}}
"""
from __future__ import annotations

import argparse
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
import transcribe_source  # noqa: E402
try:
    import rahlfs  # noqa: E402
    RAHLFS_AVAILABLE = rahlfs.is_available()
except Exception:
    RAHLFS_AVAILABLE = False

REPO_ROOT = lxx_swete.REPO_ROOT
OURS_CORPUS_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "ours_only_corpus"
ADJ_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "adjudications"
TOOL_NAME = "submit_adjudication"
PROMPT_VERSION = "adjudicate_v1_2026-04-20"


SYSTEM_PROMPT = """You are a meticulous Greek-text auditor for Swete's 1909 LXX (diplomatic edition of Codex Vaticanus). You are shown:

1. Scanned page image(s) from Swete — THE source of truth for our corpus.
2. Multiple explicit candidate readings:
   - Candidate A: our OCR of the Swete scan
   - Candidate B: First1KGreek's TEI-XML encoding of the same Swete edition (independent encoder)
   - Candidate C (when present): Rahlfs-Hanhart eclectic critical text of the LXX — DIFFERENT edition (eclectic, reconstructed from multiple manuscripts). Disagreements with C may represent legitimate textual-tradition differences; do NOT change what Swete prints to match Rahlfs.

ADDITIONALLY, you MUST draw on your training-time knowledge of these scholarly LXX editions when adjudicating ambiguous verses:
- Cambridge LXX (Brooke-McLean-Thackeray, 1906-1940) — another diplomatic Vaticanus-based edition, closely related to Swete
- Tischendorf's Sixtine LXX (1850) — earlier diplomatic edition of Codex Vaticanus
- Göttingen Septuagint (various editors) — most authoritative critical edition
- NETS (New English Translation of the Septuagint) — consensus scholarly English translation

Use this knowledge to help disambiguate hard-to-read scan passages. In your reasoning, note when a reading aligns with Cambridge / Tischendorf / Göttingen / NETS so it's auditable.

Your job for EACH verse: decide what the Swete scan actually prints.

Rules:
- THE SWETE SCAN IS THE GROUND TRUTH. A/B/C and your training knowledge are just focus hints.
- If A matches the scan: emit A's reading (possibly with accent refinement).
- If B matches the scan better than A: emit B's reading.
- If BOTH A and B differ from the scan: emit a fresh scan-based reading.
- C (Rahlfs) is a DIFFERENT edition. Only follow C if it happens to also match what Swete's scan shows. Never import Rahlfs readings that contradict the Swete scan.
- Preserve polytonic accents, breathings, iota subscripts EXACTLY as the Swete scan prints them.
- Preserve final sigma ς.
- If the scan has a variant marked in the apparatus (not the main body), do NOT use the apparatus variant — use what Swete printed as the primary body text.
- For Tobit pages with both B-text (Vaticanus) and S-text (Sinaiticus) printed in parallel: use only the B-text (the primary, upper block).

Confidence:
- high: unambiguous scan reading, corroborated by at least one candidate or by training knowledge of Cambridge/Tischendorf/Göttingen
- medium: some scan ambiguity (faint print, ligatures), but best-guess is defensible
- low: scan is hard to read at this spot; even with all sources considered, there's residual uncertainty

Return ONLY the structured function call. Per verse:
- verdict_greek: the exact Greek text as printed in the Swete scan
- verdict: "ours" (A best matches scan), "first1k" (B best matches), "both_ok" (both A & B OK), "rahlfs_match" (A & B differ but C happens to also match scan), or "neither" (fresh scan-based reading)
- reasoning: one sentence explaining what you saw on the scan; if training-knowledge of another edition helped resolve ambiguity, cite it (e.g. "Cambridge LXX also prints X here")
- confidence: high | medium | low
"""


ADJ_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit adjudicated readings for a set of verses against a Swete scan.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": ["book", "chapter", "verdicts", "notes"],
            "properties": {
                "book": {"type": "string"},
                "chapter": {"type": "integer"},
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["verse", "verdict_greek", "verdict", "reasoning", "confidence"],
                        "properties": {
                            "verse": {"type": "integer"},
                            "verdict_greek": {"type": "string"},
                            "verdict": {"type": "string", "enum": ["ours", "first1k", "both_ok", "rahlfs_match", "neither"]},
                            "reasoning": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
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


def call_azure_adjudicate(images: list[bytes], user_text: str, max_tokens: int = 16000) -> dict:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    user_parts = [{"type": "text", "text": user_text}]
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
        "tools": [ADJ_TOOL],
    }

    for attempt in range(8):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"api-key": api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < 7:
                retry_after = exc.headers.get("Retry-After")
                try:
                    wait_s = float(retry_after) if retry_after else 10 * (2 ** min(attempt, 4))
                except (TypeError, ValueError):
                    wait_s = 10 * (2 ** min(attempt, 4))
                wait_s = min(max(wait_s, 10), 120)
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:400]}")
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt < 7:
                time.sleep(10 * (2 ** min(attempt, 4)))
                continue
            raise RuntimeError(f"Azure error: {exc}")

    choices = body.get("choices") or []
    if len(choices) != 1:
        raise RuntimeError(f"Azure returned {len(choices)} choices")
    msg = choices[0].get("message") or {}
    tool_calls = msg.get("tool_calls") or []
    if len(tool_calls) != 1:
        raise RuntimeError(f"Azure returned {len(tool_calls)} tool calls")
    fn = tool_calls[0].get("function") or {}
    return json.loads(fn.get("arguments") or "{}")


def collect_disagreements(book_code: str) -> dict[int, list[dict]]:
    """Read ours_only_corpus and return per-chapter list of disagreement
    verses (minor OR major mismatch, or missing-in-ours). Each entry has
    our_text, their_text, pages."""
    corpus_path = OURS_CORPUS_DIR / f"{book_code}.jsonl"
    if not corpus_path.exists():
        return {}
    ours: dict[tuple[int, int], dict] = {}
    for line in corpus_path.read_text().split("\n"):
        if not line.strip():
            continue
        r = json.loads(line)
        ours[(r["chapter"], r["verse"])] = r

    theirs: dict[tuple[int, int], str] = {}
    try:
        for v in first1kgreek.iter_verses(book_code):
            ch = v.chapter_int
            vn = v.verse_int
            if ch is None or vn is None:
                continue
            theirs[(ch, vn)] = v.greek_text
    except Exception:
        pass

    rahlfs_map: dict[tuple[int, int], str] = {}
    if RAHLFS_AVAILABLE:
        try:
            for v in rahlfs.iter_verses(book_code):
                rahlfs_map[(v.chapter, v.verse)] = v.greek_text
        except Exception:
            pass

    by_chapter: dict[int, list[dict]] = {}
    all_keys = set(ours) | set(theirs)
    for key in sorted(all_keys):
        ch, vs = key
        o = ours.get(key)
        t = theirs.get(key)
        our_text = o.get("greek", "") if o else ""
        their_text = t or ""
        rahlfs_text = rahlfs_map.get(key, "")
        if o and t:
            sim = first1kgreek.similarity(our_text, their_text)
            if sim >= 0.85:
                continue  # ours & First1K already agree — skip
        elif o and not t:
            # We have it, they don't — adjudicate anyway if Rahlfs has it
            if not rahlfs_text:
                continue
        elif t and not o:
            # They have, we don't — definitely adjudicate
            pass
        else:
            continue
        by_chapter.setdefault(ch, []).append({
            "verse": vs,
            "our_text": our_text,
            "their_text": their_text,
            "rahlfs_text": rahlfs_text,
            "pages": (o or {}).get("source_pages") or [],
        })
    return by_chapter


def adjudicate_chapter(book_code: str, chapter: int, verses: list[dict]) -> dict:
    """Adjudicate all disagreement verses in one chapter via a single
    Azure call with the chapter's pages as images."""
    vol, first, last = lxx_swete.book_page_range(book_code)

    # Collect the union of pages mentioned by the verses, plus a bit of
    # context if sparse.
    page_set: set[int] = set()
    for v in verses:
        for p in v["pages"]:
            if p:
                page_set.add(p)
    # Fall back: locate chapter pages via running head if page set empty
    if not page_set:
        import lxx_swete_ai
        page_set = set(lxx_swete_ai.locate_chapter_pages(book_code, chapter))
    if not page_set:
        raise RuntimeError(f"No pages located for {book_code} ch {chapter}")

    pages_sorted = sorted(page_set)
    images: list[bytes] = []
    for p in pages_sorted:
        try:
            img, _ = transcribe_source.fetch_swete_image(vol, p, 1500)
            images.append(img)
        except Exception:
            pass

    # Build the user prompt
    book_title = lxx_swete.DEUTEROCANONICAL_BOOKS[book_code][3]
    lines = [
        f"Book: {book_title}",
        f"Chapter: {chapter}",
        f"Scan pages attached: {pages_sorted}",
        "",
        "Disagreement verses. References:",
        "  A = our OCR of the Swete scan",
        "  B = First1KGreek TEI-XML encoding of same Swete edition",
        "  C (when present) = Rahlfs-Hanhart eclectic critical LXX — DIFFERENT edition, for context only",
        "",
    ]
    for v in verses:
        lines.append(f"-- verse {v['verse']} --")
        lines.append(f"A (ours): {v['our_text'][:500]}")
        lines.append(f"B (first1k): {v['their_text'][:500]}")
        if v.get("rahlfs_text"):
            lines.append(f"C (rahlfs — different edition): {v['rahlfs_text'][:500]}")
        lines.append("")

    started = time.time()
    result = call_azure_adjudicate(images, "\n".join(lines))
    duration = round(time.time() - started, 2)

    return {
        "book": book_code,
        "chapter": chapter,
        "pages": pages_sorted,
        "verses_reviewed": len(verses),
        "verdicts": result.get("verdicts", []),
        "notes": result.get("notes", ""),
        "reviewed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": duration,
        "prompt_version": PROMPT_VERSION,
    }


def chapter_out_path(book: str, chapter: int) -> pathlib.Path:
    return ADJ_DIR / f"{book}_{chapter:03d}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book")
    ap.add_argument("--chapter", type=int)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-verses-per-call", type=int, default=25)
    args = ap.parse_args()

    ADJ_DIR.mkdir(parents=True, exist_ok=True)

    # Build worklist of (book, chapter, verse_batch) chunks
    worklist: list[tuple[str, int, list[dict]]] = []
    books = ([args.book] if args.book else
             [b for b in first1kgreek.BOOK_TO_TLG if b in lxx_swete.DEUTEROCANONICAL_BOOKS])
    for book in books:
        if lxx_swete.book_page_range(book)[0] == 0:
            continue
        by_chapter = collect_disagreements(book)
        for ch, vlist in by_chapter.items():
            if args.chapter is not None and ch != args.chapter:
                continue
            # Chunk into batches of max_verses_per_call
            for i in range(0, len(vlist), args.max_verses_per_call):
                chunk = vlist[i:i + args.max_verses_per_call]
                worklist.append((book, ch, chunk))

    print(f"Worklist: {len(worklist)} chapter-batches across {len(set((b,c) for b,c,_ in worklist))} chapters")

    def worker(book: str, chapter: int, chunk: list[dict]):
        out = chapter_out_path(book, chapter)
        if out.exists() and not args.force:
            return book, chapter, len(chunk), None, "cached"
        try:
            result = adjudicate_chapter(book, chapter, chunk)
            # If cached data exists and we're adding a chunk, merge verdicts
            if out.exists():
                prev = json.loads(out.read_text())
                result["verdicts"] = prev.get("verdicts", []) + result["verdicts"]
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return book, chapter, len(chunk), None, f"{len(result['verdicts'])}v in {result['duration_seconds']}s"
        except Exception as exc:
            return book, chapter, len(chunk), f"{type(exc).__name__}: {str(exc)[:200]}", None

    n_ok = n_fail = n_cached = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(worker, b, c, chunk) for b, c, chunk in worklist]
        for fut in as_completed(futures):
            b, c, n, err, info = fut.result()
            if err:
                n_fail += 1
                print(f"  FAIL {b} ch{c} ({n}v): {err}", flush=True)
            elif info == "cached":
                n_cached += 1
            else:
                n_ok += 1
                print(f"  OK   {b} ch{c}: {info}", flush=True)

    print(f"\nDone: ok={n_ok}  failed={n_fail}  cached={n_cached}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
