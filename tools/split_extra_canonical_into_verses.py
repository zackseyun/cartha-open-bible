#!/usr/bin/env python3
"""split_extra_canonical_into_verses.py

Takes chapter-level Didache / 1 Clement YAMLs and splits each chapter
into per-verse YAMLs that match standard scholarly verse divisions.

Strategy per chapter:
  1. Load the flat chapter YAML at
     ``translation/extra_canonical/<slug>/NNN.yaml``.
  2. Detect whether the Greek source carries inline verse markers
     (``\\s\\d+\\.\\s`` pattern). 1 Clement does; Didache does not
     (its Hitchcock & Brown 1884 OCR normalizer stripped them).
  3. Build a per-chapter prompt to Gemini Pro asking it to return a
     JSON array of ``{verse, greek, english}`` tuples where:
       - ``verse`` is the scholarly-standard verse number (1..N)
       - ``greek`` is the Greek text for that verse (split at existing
         markers if present; split per scholarly-consensus divisions
         if not)
       - ``english`` is the English translation for that verse, taken
         verbatim from the chapter-level draft and split at the same
         point the Greek was split
  4. Write per-verse YAMLs at
     ``translation/extra_canonical/<slug>/NNN/VVV.yaml`` preserving
     provenance fields from the chapter draft.

Does NOT delete the chapter-level flat YAML. That remains the
authoritative chapter-level record of the draft + review passes.
The per-verse YAMLs are derivations suitable for reading surfaces
(mobile app, CDN publish, per-verse bookmarks).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EXTRA_CANONICAL_ROOT = REPO_ROOT / "translation" / "extra_canonical"

# Books to split. Each tuple: (slug, display_name, chapter_count,
# canonical_verse_counts). Verse counts follow Lightfoot / Funk /
# Niederwimmer for Didache and Lightfoot / Funk / Holmes for 1 Clement.
BOOKS: list[dict[str, Any]] = [
    {
        "slug": "didache",
        "display": "Didache",
        "code": "DID",
        "verses_per_chapter": {
            1: 6, 2: 7, 3: 10, 4: 14, 5: 2, 6: 3, 7: 4, 8: 3,
            9: 5, 10: 7, 11: 12, 12: 5, 13: 7, 14: 3, 15: 4, 16: 8,
        },
    },
    {
        "slug": "1_clement",
        "display": "1 Clement",
        "code": "1CLEM",
        # 1 Clement verse counts per Lightfoot 1891 / Funk 1901 / Holmes
        # (Apostolic Fathers 3rd ed). These are target counts used to
        # validate the LLM's split — if the model returns a different
        # count, we log it and keep the model's structure (the Greek
        # markers may themselves disagree slightly with modern editions).
        "verses_per_chapter": {
            1: 3, 2: 8, 3: 4, 4: 13, 5: 7, 6: 4, 7: 7, 8: 5,
            9: 4, 10: 7, 11: 2, 12: 8, 13: 4, 14: 5, 15: 7, 16: 17,
            17: 6, 18: 17, 19: 3, 20: 12, 21: 9, 22: 8, 23: 5, 24: 5,
            25: 5, 26: 3, 27: 7, 28: 4, 29: 3, 30: 8, 31: 4, 32: 4,
            33: 8, 34: 8, 35: 12, 36: 6, 37: 5, 38: 4, 39: 9, 40: 5,
            41: 4, 42: 5, 43: 6, 44: 6, 45: 8, 46: 9, 47: 7, 48: 6,
            49: 6, 50: 7, 51: 5, 52: 4, 53: 5, 54: 4, 55: 6, 56: 16,
            57: 7, 58: 2, 59: 4, 60: 4, 61: 3, 62: 3, 63: 4, 64: 1,
            65: 2,
        },
    },
]


def detect_greek_verse_markers(greek: str) -> list[int]:
    """Return list of verse numbers found as inline markers.
    Pattern: ``\\s<digits>.\\s`` where digits are 2-99 (verse 1 is
    implicit at the start of the chapter)."""
    found = []
    for m in re.finditer(r"(?<=[\s.·;])(\d{1,2})\.\s+", greek):
        n = int(m.group(1))
        if 1 <= n <= 99:
            found.append(n)
    return found


SYSTEM_PROMPT = """You are splitting a chapter-level translation of an early Christian text into per-verse records that match the standard scholarly verse divisions.

Inputs you receive:
  - book_name: e.g. "Didache" or "1 Clement"
  - chapter: integer
  - expected_verse_count: the canonical number of verses scholars divide this chapter into
  - greek: the complete Greek text of the chapter
  - english: the complete English translation of the chapter, drafted as continuous prose
  - greek_has_verse_markers: boolean. If true, the Greek has inline verse markers like "2.", "3.", ... (verse 1 is implicit at the start). Use those markers.

Your job: return a JSON array of verses, each with {verse, greek, english}.

Rules:
  1. If greek_has_verse_markers is true: split the Greek at the existing markers. Do not remove the markers silently; return the Greek text BETWEEN markers (exclude the marker digit itself). Produce exactly as many verses as the markers indicate (+ 1 for the implicit verse 1 at the start).
  2. If greek_has_verse_markers is false: split the Greek into exactly expected_verse_count verses at the scholarly-consensus division points. If you are uncertain, prefer natural sentence boundaries at the scholarly-standard locations (e.g., Didache 1: 1, 2, 3, 4, 5, 6 — each a distinct ethical command block).
  3. Split the English at the SAME semantic points the Greek was split. The English should be verbatim from the input (preserving punctuation, capitalization, footnote markers like [1], [2] if present) — just split, don't rewrite.
  4. Every word of the input Greek must appear in exactly one verse's greek field. Same for English. No content dropped, no duplication.
  5. Return only the JSON array. No commentary, no markdown fences.

Output JSON shape:
[
  {"verse": 1, "greek": "...", "english": "..."},
  {"verse": 2, "greek": "...", "english": "..."},
  ...
]
"""


def resolve_gemini_key() -> str:
    env = os.environ.get("GEMINI_API_KEY", "").strip()
    if env:
        return env
    raw = subprocess.check_output([
        "aws", "secretsmanager", "get-secret-value",
        "--secret-id", "/cartha/openclaw/gemini_api_key",
        "--region", "us-west-2",
        "--query", "SecretString", "--output", "text",
    ], text=True).strip()
    obj = json.loads(raw)
    return obj["api_key"]


def call_gemini(api_key: str, user_text: str) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.1-pro-preview:generateContent?key=" + api_key
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 24000,
            "thinkingConfig": {"thinkingBudget": 512},
        },
    }
    for attempt in range(6):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=240) as r:
                resp = json.loads(r.read())
            candidates = resp.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"no candidates: {resp}")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise RuntimeError("empty response")
            return text
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code in (429, 500, 503) and attempt < 5:
                time.sleep(5 + attempt * 5)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}")
        except Exception:
            if attempt < 5:
                time.sleep(5 + attempt * 3)
                continue
            raise
    raise RuntimeError("exhausted retries")


def split_chapter(
    api_key: str,
    book: dict[str, Any],
    chapter: int,
    chapter_yaml_path: pathlib.Path,
) -> dict[str, Any]:
    doc = yaml.safe_load(chapter_yaml_path.read_text(encoding="utf-8"))
    greek = str(((doc.get("source") or {}).get("text") or "")).strip()
    english = str(((doc.get("translation") or {}).get("text") or "")).strip()
    if not greek or not english:
        return {"chapter": chapter, "error": "empty greek or english"}

    markers = detect_greek_verse_markers(greek)
    has_markers = len(markers) > 0
    expected = book["verses_per_chapter"].get(chapter, len(markers) + 1 if has_markers else 1)

    user_text = json.dumps({
        "book_name": book["display"],
        "chapter": chapter,
        "expected_verse_count": expected,
        "greek": greek,
        "english": english,
        "greek_has_verse_markers": has_markers,
    }, ensure_ascii=False)

    raw = call_gemini(api_key, user_text)
    try:
        verses = json.loads(raw)
    except json.JSONDecodeError:
        # Try to recover JSON array from response
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return {"chapter": chapter, "error": f"non-json: {raw[:200]}"}
        verses = json.loads(m.group(0))

    if not isinstance(verses, list) or not verses:
        return {"chapter": chapter, "error": f"bad shape: {str(verses)[:200]}"}

    # Normalize + validate
    out_verses = []
    for v in verses:
        try:
            vn = int(v.get("verse"))
            g = str(v.get("greek", "")).strip()
            e = str(v.get("english", "")).strip()
            if not g or not e:
                continue
            out_verses.append({"verse": vn, "greek": g, "english": e})
        except Exception:
            continue
    if not out_verses:
        return {"chapter": chapter, "error": "no valid verses after parse"}

    # Write per-verse YAMLs
    chapter_dir = chapter_yaml_path.parent / f"{chapter:03d}"
    chapter_dir.mkdir(exist_ok=True)

    written = 0
    for v in out_verses:
        vn = v["verse"]
        verse_path = chapter_dir / f"{vn:03d}.yaml"
        record = {
            "id": f"{book['code']}.{chapter}.{vn}",
            "reference": f"{book['display']} {chapter}:{vn}",
            "unit": "verse",
            "book": book["display"],
            "source": {
                "edition": (doc.get("source") or {}).get("edition"),
                "text": v["greek"],
                "language": "Greek",
            },
            "translation": {
                "text": v["english"],
                "philosophy": (doc.get("translation") or {}).get("philosophy"),
            },
            "note": (
                "Derived from the chapter-level draft at "
                f"translation/extra_canonical/{book['slug']}/{chapter:03d}.yaml "
                "by tools/split_extra_canonical_into_verses.py. The "
                "chapter-level flat YAML remains the authoritative record "
                "of the AI draft and review passes; per-verse YAMLs exist "
                "for the reading surface (mobile/web) and per-verse "
                "bookmark/note IDs."
            ),
            "ai_draft_provenance": (doc.get("ai_draft") or {}),
            "ai_draft_chapter_review_passes": (doc.get("review_passes") or []),
        }
        verse_path.write_text(
            yaml.safe_dump(record, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        written += 1

    return {
        "chapter": chapter,
        "verses_requested": expected,
        "verses_written": written,
        "had_markers": has_markers,
    }


def process_book(api_key: str, book: dict[str, Any], concurrency: int, chapters: list[int] | None = None) -> None:
    book_dir = EXTRA_CANONICAL_ROOT / book["slug"]
    target_chapters = chapters if chapters else sorted(book["verses_per_chapter"].keys())

    tasks = []
    for ch in target_chapters:
        path = book_dir / f"{ch:03d}.yaml"
        if not path.exists():
            print(f"  [skip] {book['display']} ch{ch}: no flat YAML")
            continue
        tasks.append((ch, path))

    print(f"\n=== {book['display']}: {len(tasks)} chapters to split ===")
    ok = failed = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = {pool.submit(split_chapter, api_key, book, ch, path): ch for ch, path in tasks}
        for fut in as_completed(futs):
            ch = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                print(f"  FAIL {book['display']} ch{ch}: {e}", flush=True)
                failed += 1
                continue
            if r.get("error"):
                print(f"  FAIL {book['display']} ch{ch}: {r['error']}", flush=True)
                failed += 1
                continue
            marker_note = "(markers)" if r["had_markers"] else "(inferred)"
            print(
                f"  OK   {book['display']} ch{ch}: "
                f"{r['verses_written']}/{r['verses_requested']} verses {marker_note}",
                flush=True,
            )
            ok += 1
    print(f"  done: ok={ok} failed={failed}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--book", choices=[b["slug"] for b in BOOKS] + ["all"], default="all")
    p.add_argument("--chapters", help="Comma-separated chapter list or range (e.g. '1' or '1,2,3' or '1-5'). Default: all chapters for the book.")
    args = p.parse_args()

    chapters = None
    if args.chapters:
        out = []
        for tok in args.chapters.split(","):
            tok = tok.strip()
            if "-" in tok:
                a, b = tok.split("-", 1)
                out.extend(range(int(a), int(b) + 1))
            else:
                out.append(int(tok))
        chapters = out

    api_key = resolve_gemini_key()

    books = BOOKS if args.book == "all" else [b for b in BOOKS if b["slug"] == args.book]
    for book in books:
        process_book(api_key, book, args.concurrency, chapters=chapters)


if __name__ == "__main__":
    sys.exit(main() or 0)
