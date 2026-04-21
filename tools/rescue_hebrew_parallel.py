#!/usr/bin/env python3
"""rescue_hebrew_parallel.py — 5-source rescue for medium-conf verses
in books with Hebrew/MT parallel coverage (SIR, TOB, 1ES).

For verses still sitting at medium confidence after rescue_low_conf.py,
add the Hebrew witness as a FIFTH source and ask the adjudicator to
cross-check proper names (via transliteration) and content (via
Greek-Hebrew idiom correspondence).

Sources (up to 5):
  A = our OCR of the Swete scan
  B = First1KGreek TEI-XML encoding (independent Swete transcription)
  C = Rahlfs-Hanhart (eclectic critical text)
  D = Amicarelli/BibleBento Swete (second independent Swete transcription)
  E = Hebrew witness:
        SIR -> Sefaria/Kahana composite (direct Hebrew Vorlage)
        TOB -> Neubauer 1878 Hebrew back-translation
        1ES -> MT parallel from our WLC corpus (2 Chr / Ezra / Neh)

Only runs on verses where a Zone 1 Hebrew is actually loadable.
Leaves all other verses untouched.
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
import hebrew_parallels  # noqa: E402
import transcribe_source  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
ADJ_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "adjudications"

TOOL_NAME = "submit_hebrew_parallel_adjudication"
PROMPT_VERSION = "rescue_hebrew_v1_2026-04-20"

ELIGIBLE_BOOKS = {"SIR", "TOB", "1ES"}


SYSTEM_PROMPT = """You are a senior Greek paleographer and philologist performing a FIFTH-SOURCE rescue on verses that could not be resolved with Greek evidence alone. For these verses, we now have an additional HEBREW WITNESS.

You are shown:

1. HIGH-RESOLUTION scan page image(s) from Swete's 1909 LXX (diplomatic edition of Codex Vaticanus).
2. Five candidate/reference readings per verse:
   - A: our OCR (pre-adjudication)
   - B: First1KGreek TEI-XML encoding (independent Swete transcription)
   - C: Rahlfs-Hanhart eclectic text
   - D: Amicarelli/BibleBento Swete (second independent Swete transcription)
   - E: HEBREW WITNESS
     * For SIR: Sefaria/Kahana composite of the Cairo Geniza manuscripts (the Hebrew Vorlage)
     * For TOB: Neubauer 1878 Hebrew back-translation from the Aramaic Munich MS (NOT a Vorlage -- use only for Semitic phrasing/name validation, not as authority)
     * For 1ES: MT parallel from 2 Chronicles / Ezra / Nehemiah (1 Esdras reworks these; Hebrew has the authoritative proper names)

Also draw on your training-time knowledge of Cambridge LXX (Brooke-McLean-Thackeray), Tischendorf's Sixtine LXX, the Göttingen Septuagint, and NETS.

Goal for each verse: determine EXACTLY what Swete's printed page says, using the Hebrew as an independent textual-critical anchor.

HOW TO USE THE HEBREW WITNESS:

For PROPER NAMES (villages, persons, genealogies, returnee lists in 1ES 5 / 9):
- The Hebrew gives you the underlying Semitic name form.
- Standard LXX Greek-Hebrew transliteration rules apply (sibilant shifts, vocalic reductions, common LXX substitutions).
- A Greek candidate that plausibly transliterates the Hebrew is MORE LIKELY to be what the scan actually prints, even if a competing candidate is equally plausible from Greek alone.
- If ALL Greek candidates are equally plausible transliterations of the Hebrew, still pick by the scan; no tiebreaker needed.
- If NO Greek candidate plausibly transliterates the Hebrew, emit verdict="neither" and reconstruct from the scan + Hebrew cross-check.

For CONTENT VERSES (Sirach wisdom passages, 1 Esdras letters, Tobit prose):
- The Hebrew Vorlage (SIR) gives you idiom/word-order clues. Greek translations of Hebrew tend to preserve certain particles and construct forms. If a Greek candidate matches the Hebrew idiom better, it is more likely correct.
- For TOB, Neubauer is NOT authoritative (it is 19th-century back-translation); treat as tertiary signal only.
- For 1ES content with MT parallel: the Hebrew lexicon constrains which Greek word-choice is likely original.

GENERAL RULES:
- The IMAGE is the source of truth. Hebrew is a CORROBORATING signal, not an override.
- When you can read the scan clearly, trust the scan over all candidates.
- When the scan is damaged/faded and A+B+D converge AND E transliterates to one of them, confidence should be HIGH.
- When the scan is damaged and candidates diverge, pick the one best supported by Hebrew E + scholarly scholarship.
- Fill in any clearly missing verses you can now resolve with this 5-source view.

OUTPUT per verse via the submit_hebrew_parallel_adjudication tool:
- verse: int
- verdict_greek: the definitive Greek reading as printed on the Swete scan
- verdict: "ours" | "first1k" | "amicarelli" | "swete_consensus" (A+B+D agree) | "rahlfs_match" (A/B/D differ but C matches scan) | "both_ok" (A & B minor differences) | "neither" (fresh scan-based reading)
- hebrew_anchor: brief note on HOW the Hebrew supported your call (e.g. "Hebrew has נטפה = 'Netophah'; Greek Νετέβας plausibly transliterates")
- reasoning: 1-2 sentences on scan + candidate agreement
- confidence: "high" | "medium" | "low"

Emit one tool call with all verses resolved, in a `verdicts` array.
"""


RESCUE_TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Submit 5-source Hebrew-parallel adjudication verdicts.",
        "parameters": {
            "type": "object",
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "verse": {"type": "integer"},
                            "verdict_greek": {"type": "string"},
                            "verdict": {
                                "type": "string",
                                "enum": ["ours", "first1k", "amicarelli", "swete_consensus",
                                         "rahlfs_match", "both_ok", "neither"],
                            },
                            "hebrew_anchor": {"type": "string"},
                            "reasoning": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        },
                        "required": ["verse", "verdict_greek", "verdict", "reasoning", "confidence"],
                    },
                },
            },
            "required": ["verdicts"],
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


def load_candidates(book: str, chapter: int, verse: int) -> dict:
    """Gather the 4 Greek candidates (A/B/C/D) for a verse."""
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


def load_hebrew_e(book: str, chapter: int, verse: int) -> dict | None:
    """Return Zone 1 Hebrew (source E) or None if not available."""
    hit = hebrew_parallels.lookup(book, chapter, verse)
    if not hit:
        return None
    # Reject empty-Hebrew kinds
    if hit.get("kind") == "no_parallel":
        return None
    if hit.get("kind") in ("direct_hebrew_missing", "indirect_hebrew_missing"):
        return None
    if hit.get("kind") == "mt_parallel" and not hit.get("hebrew"):
        return None
    if hit.get("kind") in ("direct_hebrew", "indirect_hebrew") and not hit.get("hebrew"):
        return None
    return hit


def call_azure(images: list[bytes], user_text: str, max_tokens: int = 16000) -> dict:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")

    user_parts: list[dict] = [{"type": "text", "text": user_text}]
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
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "api-key": api_key},
            )
            with urllib.request.urlopen(req, timeout=240) as r:
                resp = json.loads(r.read())
            tool_calls = resp["choices"][0]["message"].get("tool_calls") or []
            if not tool_calls:
                raise RuntimeError("No tool call in response")
            args = json.loads(tool_calls[0]["function"]["arguments"])
            return args
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code == 429 and attempt < 9:
                wait = min(120, 10 * (attempt + 1))
                time.sleep(wait)
                continue
            raise RuntimeError(f"Azure HTTP {e.code}: {body[:400]}")
        except Exception:
            if attempt < 9:
                time.sleep(5 + attempt * 3)
                continue
            raise
    raise RuntimeError("Azure retries exhausted")


def build_worklist() -> list[tuple[str, int, list[int]]]:
    """Find medium-conf verses in eligible books with Hebrew actually loadable."""
    worklist_by_chapter: dict[tuple[str, int], list[int]] = {}
    for p in sorted(ADJ_DIR.glob("*.json")):
        data = json.loads(p.read_text())
        book = data.get("book")
        chapter = data.get("chapter")
        if book not in ELIGIBLE_BOOKS:
            continue
        for v in data.get("verdicts", []):
            if v.get("confidence") != "medium":
                continue
            vs = v.get("verse")
            if load_hebrew_e(book, chapter, vs) is None:
                continue
            worklist_by_chapter.setdefault((book, chapter), []).append(vs)
    return [(b, c, sorted(set(verses))) for (b, c), verses in sorted(worklist_by_chapter.items())]


def process_batch(book: str, chapter: int, verses: list[int], image_width: int) -> dict:
    vol = lxx_swete.DEUTEROCANONICAL_BOOKS[book][0]

    # Find scan page range from adjudication file
    adj_path = ADJ_DIR / f"{book}_{chapter:03d}.json"
    adj_data = json.loads(adj_path.read_text())
    pages_needed = sorted(set(adj_data.get("pages", [])))

    images = []
    missing = []
    for pg in pages_needed:
        img = None
        for attempt in range(4):
            try:
                img, _ = transcribe_source.fetch_swete_image(vol, pg, image_width)
                break
            except Exception:
                time.sleep(2 + attempt * 3)
        if img is not None:
            images.append(img)
        else:
            missing.append(pg)
    if not images:
        return {"book": book, "chapter": chapter, "verses": verses, "error": f"no images fetched (missing pages {missing})"}

    # Build the prompt with Greek candidates + Hebrew witness per verse
    book_title = lxx_swete.DEUTEROCANONICAL_BOOKS[book][3]
    lines = [
        f"Book: {book_title} ({book})",
        f"Chapter: {chapter}",
        f"Scan pages (HIGH-RES {image_width}px): {pages_needed}",
        "",
        "FIFTH-SOURCE HEBREW PARALLEL RESCUE — these verses were medium confidence after 4-source Greek adjudication. Use the Hebrew witness (source E) as an additional textual-critical anchor.",
        "",
        "Sources:",
        "  A = our OCR of the Swete scan",
        "  B = First1KGreek TEI encoding (Swete)",
        "  C = Rahlfs-Hanhart (eclectic)",
        "  D = Amicarelli/BibleBento Swete (second independent Swete)",
        "  E = Hebrew witness (see system prompt for per-book role)",
        "",
    ]
    for vs in verses:
        cands = load_candidates(book, chapter, vs)
        heb = load_hebrew_e(book, chapter, vs)
        lines.append(f"-- verse {vs} --")
        lines.append(f"  A (ours):       {cands.get('ours','')}")
        lines.append(f"  B (first1k):    {cands.get('first1k','')}")
        lines.append(f"  C (rahlfs):     {cands.get('rahlfs','')}")
        lines.append(f"  D (amicarelli): {cands.get('amicarelli','')}")
        if heb:
            hebrew_text = heb.get("hebrew", "")[:500]
            hebrew_kind = heb.get("kind", "")
            mt_ref = heb.get("mt_range") or ""
            lines.append(f"  E (hebrew, kind={hebrew_kind}{' / '+mt_ref if mt_ref else ''}): {hebrew_text}")
            if heb.get("note"):
                lines.append(f"      [E-note]: {heb['note'][:180]}")
        lines.append("")
    lines.append("")
    lines.append(f"Return verdicts for verses {verses} via the tool. Include hebrew_anchor explaining how Hebrew E supported your call.")
    user_text = "\n".join(lines)

    try:
        result = call_azure(images, user_text)
    except Exception as e:
        return {"book": book, "chapter": chapter, "verses": verses, "error": str(e)}

    # Merge verdicts into existing adjudication file
    verdict_map = {v["verse"]: v for v in result.get("verdicts", [])}
    updated = 0
    for v in adj_data.get("verdicts", []):
        vs = v.get("verse")
        if vs in verdict_map and v.get("confidence") == "medium":
            new = verdict_map[vs]
            v["verdict_greek"] = new["verdict_greek"]
            v["verdict"] = new["verdict"]
            v["reasoning"] = new["reasoning"]
            v["confidence"] = new["confidence"]
            if "hebrew_anchor" in new:
                v["hebrew_anchor"] = new["hebrew_anchor"]
            updated += 1
    adj_data["hebrew_parallel_pass_applied"] = True
    adj_data["hebrew_parallel_timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
    adj_data["hebrew_parallel_prompt_version"] = PROMPT_VERSION
    adj_path.write_text(json.dumps(adj_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"book": book, "chapter": chapter, "verses": verses, "updated": updated}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--image-width", type=int, default=3000)
    args = parser.parse_args()

    worklist = build_worklist()
    total_verses = sum(len(verses) for _, _, verses in worklist)
    print(f"Hebrew-parallel rescue worklist: {total_verses} verses in {len(worklist)} chapters")
    for book, chapter, verses in worklist:
        print(f"  {book} ch{chapter}: {verses}")
    if not worklist:
        print("Nothing to do.")
        return 0

    ok = failed = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(process_batch, book, chapter, verses, args.image_width): (book, chapter, verses)
            for book, chapter, verses in worklist
        }
        for fut in as_completed(futures):
            book, chapter, verses = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                print(f"  FAIL {book} ch{chapter} verses {verses}: {e}", flush=True)
                failed += 1
                continue
            if r.get("error"):
                print(f"  FAIL {book} ch{chapter} verses {verses}: {r['error']}", flush=True)
                failed += 1
            else:
                print(f"  OK   {book} ch{chapter} verses {verses}: updated {r.get('updated', 0)}", flush=True)
                ok += 1
    print(f"\nDone: ok={ok}  failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
