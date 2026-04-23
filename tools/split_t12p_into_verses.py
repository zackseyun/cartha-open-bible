#!/usr/bin/env python3
"""split_t12p_into_verses.py

Splits T12P chapter-level YAMLs into per-verse YAMLs.

The chapter-level files live at:
  translation/extra_canonical/testaments_twelve_patriarchs/<testament>/NNN.yaml

Per-verse output:
  translation/extra_canonical/testaments_twelve_patriarchs/<testament>/NNN/VVV.yaml

The Greek source text (Charles 1908 critical edition) embeds verse markers as
``2. Text 3. Text`` BUT also includes apparatus-footnote numbers in the same
format. The English draft embeds verse numbers as ``2 Text 3 Text`` (standalone
numbers before each verse, first verse has no number). We use BOTH signals and
let the LLM resolve ambiguity.
"""
from __future__ import annotations

import argparse
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
T12P_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "testaments_twelve_patriarchs"

TESTAMENTS: list[dict[str, Any]] = [
    {"slug": "asher",     "code": "T12P.ASH", "display": "Testament of Asher"},
    {"slug": "benjamin",  "code": "T12P.BEN", "display": "Testament of Benjamin"},
    {"slug": "dan",       "code": "T12P.DAN", "display": "Testament of Dan"},
    {"slug": "gad",       "code": "T12P.GAD", "display": "Testament of Gad"},
    {"slug": "issachar",  "code": "T12P.ISS", "display": "Testament of Issachar"},
    {"slug": "joseph",    "code": "T12P.JOS", "display": "Testament of Joseph"},
    {"slug": "judah",     "code": "T12P.JUD", "display": "Testament of Judah"},
    {"slug": "levi",      "code": "T12P.LEV", "display": "Testament of Levi"},
    {"slug": "naphtali",  "code": "T12P.NAP", "display": "Testament of Naphtali"},
    {"slug": "reuben",    "code": "T12P.REU", "display": "Testament of Reuben"},
    {"slug": "simeon",    "code": "T12P.SIM", "display": "Testament of Simeon"},
    {"slug": "zebulun",   "code": "T12P.ZEB", "display": "Testament of Zebulun"},
]

SYSTEM_PROMPT = """You are splitting a chapter of the Testaments of the Twelve Patriarchs into individual verse records.

The T12P translation draft embeds verse numbers inline in the English like this:
  "First verse text, which has no leading number. 2 Second verse text. 3 Third verse text."
Verse 1 is ALWAYS the implicit first text before any number. Each subsequent verse starts with a standalone number followed by a space and uppercase letter.

The Greek source text also has verse markers (e.g. "2. Text 3. Text") but the Greek contains apparatus footnote numbers in similar format — use the ENGLISH verse numbers as the authoritative split guide, and use the Greek markers only to confirm.

Your job: return a JSON array of verse objects.

Rules:
1. Use the English inline verse numbers (standalone digits before each verse) to identify verse boundaries. Verse 1 is the text before the first number.
2. Split the English at those boundaries. Each verse's english field should contain the text of that verse ONLY (without the leading verse number).
3. For the Greek, find the corresponding Greek text for each verse using the Greek verse markers (e.g. "2.") that align with the English verse numbers. The first verse is everything before the first Greek marker.
4. Every word of the English must appear in exactly one verse's english field. Same for the Greek. No content dropped, no duplication.
5. If the English has no embedded verse numbers at all, treat the entire chapter as a single verse (verse 1).
6. Ignore apparatus footnote notations in the Greek (superscript-like numbers embedded within or after words — those are critical apparatus markers, not verse numbers).
7. Return ONLY the JSON array. No commentary, no markdown fences.

Output JSON shape:
[
  {"verse": 1, "greek": "...", "english": "..."},
  {"verse": 2, "greek": "...", "english": "..."},
  ...
]
"""


def detect_english_verse_count(english: str) -> int:
    """Count the number of verses based on inline English verse numbers.
    Returns the max verse number found (+ 1 implicit verse 1 if any found)."""
    nums = []
    for m in re.finditer(r'(?:(?<=[.!?"\'])\s+|(?:^|\n)\s*)(\d+)\s+[A-Z"\'(]', english):
        n = int(m.group(1))
        if 2 <= n <= 50:
            nums.append(n)
    if not nums:
        return 1
    return max(nums)


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
            "maxOutputTokens": 16000,
            "thinkingConfig": {"thinkingBudget": 256},
        },
    }
    for attempt in range(6):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=180) as r:
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
                wait = 15 + attempt * 10
                print(f"    [retry {attempt+1}] HTTP {e.code}, sleeping {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}")
        except Exception as exc:
            if attempt < 5:
                time.sleep(5 + attempt * 3)
                continue
            raise
    raise RuntimeError("exhausted retries")


def split_chapter(
    api_key: str,
    testament: dict[str, Any],
    chapter_num: int,
    chapter_yaml_path: pathlib.Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    # Check if already split
    chapter_dir = chapter_yaml_path.parent / f"{chapter_num:03d}"
    if chapter_dir.exists() and not overwrite:
        existing = list(chapter_dir.glob("*.yaml"))
        if existing:
            return {"chapter": chapter_num, "status": "already_split", "verses": len(existing)}

    doc = yaml.safe_load(chapter_yaml_path.read_text(encoding="utf-8"))
    greek = str(((doc.get("source") or {}).get("text") or "")).strip()
    english = str(((doc.get("translation") or {}).get("text") or "")).strip()
    if not greek or not english:
        return {"chapter": chapter_num, "error": "empty greek or english"}

    expected_verses = detect_english_verse_count(english)

    user_text = json.dumps({
        "testament": testament["display"],
        "chapter": chapter_num,
        "expected_verse_count": expected_verses,
        "greek": greek,
        "english": english,
    }, ensure_ascii=False)

    raw = call_gemini(api_key, user_text)
    try:
        verses = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            return {"chapter": chapter_num, "error": f"non-json: {raw[:200]}"}
        verses = json.loads(m.group(0))

    if not isinstance(verses, list) or not verses:
        return {"chapter": chapter_num, "error": f"bad shape: {str(verses)[:200]}"}

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
        return {"chapter": chapter_num, "error": "no valid verses after parse"}

    chapter_dir.mkdir(exist_ok=True)

    written = 0
    for v in out_verses:
        vn = v["verse"]
        verse_path = chapter_dir / f"{vn:03d}.yaml"
        record = {
            "id": f"{testament['code']}.{chapter_num}.{vn}",
            "reference": f"{testament['display']} {chapter_num}:{vn}",
            "unit": "verse",
            "book": testament["display"],
            "collection": "Testaments of the Twelve Patriarchs",
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
                f"Derived from chapter-level draft at "
                f"translation/extra_canonical/testaments_twelve_patriarchs/"
                f"{testament['slug']}/{chapter_num:03d}.yaml "
                "by tools/split_t12p_into_verses.py. "
                "The chapter-level YAML is the authoritative draft record; "
                "per-verse YAMLs exist for the reading surface and "
                "per-verse bookmark/note IDs."
            ),
            "ai_draft_provenance": (doc.get("ai_draft") or {}),
        }
        verse_path.write_text(
            yaml.safe_dump(record, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        written += 1

    return {
        "chapter": chapter_num,
        "status": "ok",
        "expected_verses": expected_verses,
        "verses_written": written,
    }


def process_testament(
    api_key: str,
    testament: dict[str, Any],
    concurrency: int,
    chapters: list[int] | None = None,
    overwrite: bool = False,
) -> None:
    testament_dir = T12P_ROOT / testament["slug"]
    if not testament_dir.exists():
        print(f"  [skip] {testament['display']}: directory not found")
        return

    chapter_yamls = sorted(testament_dir.glob("*.yaml"))
    if not chapter_yamls:
        print(f"  [skip] {testament['display']}: no chapter YAMLs")
        return

    tasks = []
    for path in chapter_yamls:
        ch = int(path.stem)
        if chapters and ch not in chapters:
            continue
        tasks.append((ch, path))

    print(f"\n{testament['display']}: {len(tasks)} chapters to split")

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(split_chapter, api_key, testament, ch, path, overwrite): ch
            for ch, path in tasks
        }
        for fut in as_completed(futures):
            ch = futures[fut]
            try:
                result = fut.result()
                status = result.get("status", "ok")
                if "error" in result:
                    print(f"  ch{ch:03d}: ERROR — {result['error']}")
                elif status == "already_split":
                    print(f"  ch{ch:03d}: already split ({result['verses']} verses)")
                else:
                    print(f"  ch{ch:03d}: wrote {result['verses_written']} verses "
                          f"(expected {result['expected_verses']})")
            except Exception as exc:
                print(f"  ch{ch:03d}: EXCEPTION — {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split T12P chapter YAMLs into verse YAMLs")
    parser.add_argument(
        "--testament", "-t",
        nargs="*",
        help="Testament slug(s) to process (e.g. reuben levi). Omit for all.",
    )
    parser.add_argument(
        "--chapter", "-c",
        nargs="*",
        type=int,
        help="Specific chapter number(s) to process.",
    )
    parser.add_argument(
        "--concurrency", "-j",
        type=int,
        default=3,
        help="Parallel API calls per testament (default 3).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-split chapters that already have verse YAMLs.",
    )
    args = parser.parse_args()

    api_key = resolve_gemini_key()

    testament_filter = set(args.testament) if args.testament else None

    for testament in TESTAMENTS:
        if testament_filter and testament["slug"] not in testament_filter:
            continue
        process_testament(
            api_key,
            testament,
            concurrency=args.concurrency,
            chapters=args.chapter,
            overwrite=args.overwrite,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
