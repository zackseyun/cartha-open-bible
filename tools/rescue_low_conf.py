#!/usr/bin/env python3
"""rescue_low_conf.py — targeted rescue pass for low/medium confidence verses.

For every verse adjudicated with low or medium confidence in the first
pass, re-run with 4 reference sources + higher scan-image resolution +
enhanced prompt that requests extra rigor.

Sources:
  A = our OCR (pre-adjudication reading)
  B = First1KGreek Swete encoding
  C = Rahlfs eclectic text
  D = Amicarelli Swete encoding (second independent Swete transcription)

Only rescue verses that are low/medium confidence. High-confidence
verses are already stable. Output updates the same adjudication files.
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
import rahlfs  # noqa: E402
import swete_amicarelli  # noqa: E402
import transcribe_source  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
ADJ_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "adjudications"
OURS_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "ours_only_corpus"

TOOL_NAME = "submit_rescue_adjudication"
PROMPT_VERSION = "rescue_v1_2026-04-20"


SYSTEM_PROMPT = """You are a senior Greek paleographer performing a RESCUE PASS on verses the first adjudication pass could not confidently resolve. Apply extra care.

You are shown:

1. HIGH-RESOLUTION scan page image(s) from Swete's 1909 LXX (diplomatic edition of Codex Vaticanus).
2. Four independent candidate readings per verse:
   - A: our OCR (pre-adjudication)
   - B: First1KGreek TEI-XML encoding (independent Swete transcription)
   - C: Rahlfs-Hanhart (eclectic critical edition — different textual tradition)
   - D: Amicarelli/BibleBento Swete encoding (second independent Swete transcription, from BibleWorks module)

ALSO draw on your training-time knowledge of Cambridge LXX (Brooke-McLean-Thackeray), Tischendorf's Sixtine LXX, the Göttingen Septuagint, and NETS for disambiguation.

Goal for each verse: determine EXACTLY what Swete's printed page says, using every available signal.

Rules:
- The IMAGE is the source of truth. All candidates and training knowledge are focus hints.
- When A, B, D agree: they are three independent transcriptions of the same Swete edition. That convergence is very strong evidence of what Swete printed.
- When A and D agree (both Swete transcriptions) but B disagrees: trust the Swete-transcription consensus; First1KGreek likely has an encoding error.
- When all three Swete transcriptions (A, B, D) agree but differ from C (Rahlfs): this is a legitimate Swete-vs-eclectic textual difference. Preserve Swete's reading.
- When you can read the scan clearly, trust the scan over all candidates.
- When the scan is damaged/faded, prefer the convergent reading from Swete-family transcriptions (A+B+D).
- Only diverge from both scan and candidates when you have VERY strong scholarly evidence (Cambridge/Göttingen) for a different reading.

For Tobit pages with B-text + S-text in parallel: use only B-text (Vaticanus, primary upper block).

Return a structured function call. Per verse:
- verdict_greek: the exact Greek text as you determine it
- verdict: "ours" | "first1k" | "amicarelli" | "swete_consensus" (A+B+D agree) | "rahlfs_match" (A/B/D differ but C matches scan) | "both_ok" (A & B minor differences) | "neither" (fresh scan-based reading)
- reasoning: 1-2 sentences explaining what you saw on the scan and how the candidates aligned
- confidence: high | medium | low

Target: move as many verses as possible from low/medium → high confidence, through more rigorous triangulation.
"""


RESCUE_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit rescue-pass adjudicated readings.",
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
                            "verdict": {"type": "string", "enum": [
                                "ours", "first1k", "amicarelli", "swete_consensus",
                                "rahlfs_match", "both_ok", "neither"
                            ]},
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


def call_azure_rescue(images: list[bytes], user_text: str, max_tokens: int = 16000) -> dict:
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
        "max_completion_tokens": max_tokens,
        "parallel_tool_calls": False,
        "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        "tools": [RESCUE_TOOL],
    }

    for attempt in range(10):
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
            if exc.code == 429 and attempt < 9:
                wait_s = min(max(10 * (2 ** min(attempt, 4)), 10), 120)
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Azure HTTP {exc.code}: {detail[:400]}")
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt < 9:
                time.sleep(10 * (2 ** min(attempt, 4)))
                continue
            raise RuntimeError(f"Azure error: {exc}")

    choices = body.get("choices") or []
    msg = choices[0].get("message") or {}
    tool_calls = msg.get("tool_calls") or []
    fn = tool_calls[0].get("function") or {}
    return json.loads(fn.get("arguments") or "{}")


def load_ours_verse(book: str, chapter: int, verse: int) -> str:
    path = OURS_DIR / f"{book}.jsonl"
    if not path.exists():
        return ""
    for line in path.read_text().split("\n"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r["chapter"] == chapter and r["verse"] == verse:
            return r["greek"]
    return ""


def load_first1k_verse(book: str, chapter: int, verse: int) -> str:
    try:
        v = first1kgreek.load_verse(book, chapter, verse)
        return v.greek_text if v else ""
    except Exception:
        return ""


def load_rahlfs_verse(book: str, chapter: int, verse: int) -> str:
    try:
        v = rahlfs.load_verse(book, chapter, verse)
        return v.greek_text if v else ""
    except Exception:
        return ""


def load_amicarelli_verse(book: str, chapter: int, verse: int) -> str:
    try:
        v = swete_amicarelli.load_verse(book, chapter, verse)
        return v.greek_text if v else ""
    except Exception:
        return ""


def rescue_chapter_batch(book: str, chapter: int, verses: list[int], image_width: int = 3000) -> dict:
    """Rescue a batch of low-conf verses on one chapter."""
    vol = lxx_swete.book_page_range(book)[0]

    # Locate source pages via ours_only corpus
    pages_needed = set()
    verse_data = []
    for vn in verses:
        # Find source page(s)
        path = OURS_DIR / f"{book}.jsonl"
        src_pages = []
        for line in path.read_text().split("\n"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["chapter"] == chapter and r["verse"] == vn:
                src_pages = r.get("source_pages") or []
                break
        for p in src_pages:
            if p:
                pages_needed.add(p)
        verse_data.append({
            "verse": vn,
            "ours": load_ours_verse(book, chapter, vn),
            "first1k": load_first1k_verse(book, chapter, vn),
            "rahlfs": load_rahlfs_verse(book, chapter, vn),
            "amicarelli": load_amicarelli_verse(book, chapter, vn),
            "pages": src_pages,
        })

    # Fall back: if no pages, use chapter-location lookup
    if not pages_needed:
        import lxx_swete_ai
        pages_needed = set(lxx_swete_ai.locate_chapter_pages(book, chapter))

    pages_sorted = sorted(pages_needed)
    images = []
    missing_pages = []
    for p in pages_sorted:
        img = None
        last_err = None
        for attempt in range(4):
            try:
                img, _ = transcribe_source.fetch_swete_image(vol, p, image_width)
                break
            except Exception as e:
                last_err = e
                time.sleep(2 + attempt * 3)
        if img is not None:
            images.append(img)
        else:
            missing_pages.append(p)
            print(f"    WARN: failed to fetch scan page {p} for {book} ch{chapter} after 4 attempts: {last_err}", flush=True)
    if not images:
        raise RuntimeError(f"No scan images fetched for {book} ch{chapter} (pages {pages_sorted}) — aborting batch")

    book_title = lxx_swete.DEUTEROCANONICAL_BOOKS[book][3]
    lines = [
        f"Book: {book_title} ({book})",
        f"Chapter: {chapter}",
        f"Scan pages (HIGH-RES {image_width}px): {pages_sorted}",
        "",
        "RESCUE PASS — these verses were low/medium confidence in the first pass. Apply extra care.",
        "",
        "References:",
        "  A = our OCR of the Swete scan",
        "  B = First1KGreek TEI encoding (Swete)",
        "  C = Rahlfs-Hanhart (DIFFERENT edition — eclectic critical text)",
        "  D = Amicarelli/BibleBento Swete (second independent Swete transcription)",
        "",
    ]
    for vd in verse_data:
        lines.append(f"-- verse {vd['verse']} --")
        lines.append(f"A (ours):       {vd['ours'][:500]}")
        if vd["first1k"]:
            lines.append(f"B (first1k):    {vd['first1k'][:500]}")
        if vd["rahlfs"]:
            lines.append(f"C (rahlfs):     {vd['rahlfs'][:500]}")
        if vd["amicarelli"]:
            lines.append(f"D (amicarelli): {vd['amicarelli'][:500]}")
        lines.append("")

    started = time.time()
    result = call_azure_rescue(images, "\n".join(lines))
    duration = round(time.time() - started, 2)

    return {
        "book": book,
        "chapter": chapter,
        "pages": pages_sorted,
        "verses_rescued": len(verses),
        "verdicts": result.get("verdicts", []),
        "notes": result.get("notes", ""),
        "reviewed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": duration,
        "prompt_version": PROMPT_VERSION,
        "image_width": image_width,
    }


def integrate_rescue(book: str, chapter: int, rescue_verdicts: list[dict]):
    """Update the chapter's adjudication JSON with rescued verdicts."""
    path = ADJ_DIR / f"{book}_{chapter:03d}.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    existing = {v["verse"]: i for i, v in enumerate(data["verdicts"])}
    for rv in rescue_verdicts:
        vn = rv["verse"]
        if vn in existing:
            data["verdicts"][existing[vn]] = rv
        else:
            data["verdicts"].append(rv)
    data["rescue_pass_applied"] = True
    data["rescue_timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--max-per-batch", type=int, default=10)
    ap.add_argument("--image-width", type=int, default=3000)
    args = ap.parse_args()

    # Collect low/med verses per chapter
    targets: dict[tuple[str, int], list[int]] = {}
    for f in sorted(ADJ_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        book, ch = data["book"], data["chapter"]
        for v in data["verdicts"]:
            if v["confidence"] in ("low", "medium"):
                targets.setdefault((book, ch), []).append(v["verse"])

    total_verses = sum(len(vs) for vs in targets.values())
    print(f"Rescue worklist: {total_verses} verses across {len(targets)} chapters")

    # Chunk large chapters
    worklist = []
    for (book, ch), vs in targets.items():
        for i in range(0, len(vs), args.max_per_batch):
            worklist.append((book, ch, vs[i:i + args.max_per_batch]))

    print(f"Rescue batches: {len(worklist)}")

    def worker(book: str, ch: int, verses: list[int]):
        try:
            result = rescue_chapter_batch(book, ch, verses, image_width=args.image_width)
            integrate_rescue(book, ch, result["verdicts"])
            return book, ch, len(verses), None, f"{len(result['verdicts'])}v in {result['duration_seconds']}s"
        except Exception as exc:
            return book, ch, len(verses), f"{type(exc).__name__}: {str(exc)[:200]}", None

    n_ok = n_fail = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(worker, b, c, vs) for b, c, vs in worklist]
        for fut in as_completed(futures):
            b, c, n, err, info = fut.result()
            if err:
                n_fail += 1
                print(f"  FAIL {b} ch{c} ({n}v): {err}", flush=True)
            else:
                n_ok += 1
                print(f"  OK   {b} ch{c}: {info}", flush=True)

    print(f"\nDone: ok={n_ok}  failed={n_fail}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
