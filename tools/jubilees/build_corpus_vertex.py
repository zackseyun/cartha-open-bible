#!/usr/bin/env python3
"""build_corpus_vertex.py — build a Jubilees corpus with Vertex fallback.

Strategy:
- run the deterministic parser first
- if a chapter yields too few verses, ask Gemini on Vertex to split that
  chapter's OCR text into verse records

This is a practical extraction finisher, not the final ideal parser.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import os
import time
import urllib.request
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

import sys
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import ocr_geez  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_corpus as jub_corpus  # noqa: E402
import verse_parser  # noqa: E402


SYSTEM_PROMPT = """You are extracting verse rows from OCR'd Ge'ez text of one chapter of the Book of Jubilees.

Important layout facts:
- The source is Charles 1895 Ethiopic Jubilees.
- The first page may contain the tail of the PREVIOUS chapter before the target chapter begins.
- The final page may contain the start of the NEXT chapter after the target chapter ends.
- On some pages, a line-initial Ethiopic numeral equal to the CHAPTER number marks the start of the chapter; that line contains verse 1 and the chapter numeral itself is NOT a verse number.
- Subsequent verses may be marked by Ethiopic or Arabic numerals at line starts.
- Running heads and critical apparatus are not part of the main text.

Return ONLY a JSON array. Each item must be:
{"verse": <int>, "text": "<Ge'ez text>"}

Rules:
- Include ONLY verses belonging to the requested chapter.
- Start at verse 1.
- Keep verse numbers ascending.
- Preserve the Ge'ez main-text wording.
- Exclude running heads, apparatus, and explicit next-chapter material.
- Do not invent text that is not present in the OCR.
"""


def call_vertex_json(user_text: str, *, model: str) -> str:
    secret_ids = [s.strip() for s in os.environ.get(
        "VERTEX_SECRET_IDS",
        "/cartha/vertex/gemini-sa,/cartha/openclaw/gemini_api_key_2",
    ).split(",") if s.strip()]
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "maxOutputTokens": 24000,
            "thinkingConfig": {"thinkingBudget": 512},
        },
    }
    last_err: Exception | None = None
    for secret_id in secret_ids:
        try:
            os.environ["VERTEX_SECRET_ID"] = secret_id
            ocr_geez._VERTEX_CACHE["token"] = ""
            ocr_geez._VERTEX_CACHE["expiry"] = 0.0
            ocr_geez._VERTEX_CACHE["project"] = ""
            token, project_id = ocr_geez.vertex_access_token()
            location = ocr_geez.DEFAULT_VERTEX_LOCATION
            api_host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
            url = (
                f"https://{api_host}/v1/projects/{project_id}/locations/{location}/"
                f"publishers/google/models/{model}:generateContent"
            )
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.loads(r.read().decode("utf-8"))
            cand = (resp.get("candidates") or [None])[0]
            if not cand:
                raise RuntimeError(f"no candidates: {resp}")
            parts = cand.get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if not text:
                raise RuntimeError("empty response")
            return text
        except Exception as exc:
            last_err = exc
            time.sleep(2)
            continue
    raise last_err or RuntimeError("vertex call failed across all configured secrets")


def llm_extract_chapter(
    *,
    chapter: int,
    page_texts: list[tuple[int, str]],
    model: str,
) -> list[dict[str, Any]]:
    joined = []
    for page, text in page_texts:
        joined.append(f"[[PDF_PAGE_{page}]]\n{text.strip()}\n")
    user_text = json.dumps(
        {
            "book": "Jubilees",
            "chapter": chapter,
            "ocr_pages": [page for page, _ in page_texts],
            "ocr_text": "\n\n".join(joined),
        },
        ensure_ascii=False,
    )
    raw = call_vertex_json(user_text, model=model)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            raise
        data = json.loads(m.group(0))
    out: list[dict[str, Any]] = []
    for item in data:
        try:
            verse = int(item["verse"])
            text = str(item["text"]).strip()
        except Exception:
            continue
        if verse < 1 or not text:
            continue
        out.append({"verse": verse, "text": text})
    out.sort(key=lambda x: x["verse"])
    dedup: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in out:
        if item["verse"] in seen:
            continue
        seen.add(item["verse"])
        dedup.append(item)
    return dedup


def chapter_records(
    *,
    chapter: int,
    page_map: dict[str, Any],
    low_threshold: int,
    model: str,
) -> tuple[list[dict[str, Any]], str]:
    pages = jub_corpus.chapter_pages(page_map, chapter)
    page_texts, _, labels_used = jub_corpus.load_page_texts(chapter, pages, allow_missing_pages=True)
    rows = verse_parser.parse_chapter_pages_for_target(page_texts, chapter, next_chapter=(chapter + 1 if chapter < 50 else None))
    verse_rows = [r for r in rows if r.verse >= 1]
    mode = "deterministic"
    if len(verse_rows) < low_threshold:
        llm_rows = llm_extract_chapter(chapter=chapter, page_texts=page_texts, model=model)
        if len(llm_rows) >= len(verse_rows):
            mode = "vertex_fallback"
            return [
                {
                    "book": "JUB",
                    "book_title": "Jubilees",
                    "chapter": chapter,
                    "verse": item["verse"],
                    "geez": item["text"],
                    "chapter_source_pages": pages,
                    "source_edition": jub_corpus.SOURCE_EDITION,
                    "witness": "charles_1895",
                    "ocr_source_dirs": labels_used,
                    "validation": "vertex_chapter_split",
                }
                for item in llm_rows
            ], mode

    return [
        {
            "book": "JUB",
            "book_title": "Jubilees",
            "chapter": chapter,
            "verse": row.verse,
            "geez": row.text,
            "source_page_start": row.source_page,
            "chapter_source_pages": pages,
            "source_edition": jub_corpus.SOURCE_EDITION,
            "witness": "charles_1895",
            "ocr_source_dirs": labels_used,
            "validation": "jubilees_verse_parser",
        }
        for row in verse_rows
    ], mode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page-map", type=pathlib.Path, default=jub_corpus.DEFAULT_PAGE_MAP)
    ap.add_argument("--out", type=pathlib.Path, default=REPO_ROOT / "sources" / "jubilees" / "ethiopic" / "corpus" / "JUBILEES.vertex.jsonl")
    ap.add_argument("--low-threshold", type=int, default=5)
    ap.add_argument("--model", default="gemini-3.1-pro-preview")
    ap.add_argument("--chapters", default="all")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    page_map = jub_corpus.load_page_map(args.page_map)
    chapters = list(range(1, 51)) if args.chapters == "all" else []
    if args.chapters != "all":
        for part in args.chapters.split(","):
            token = part.strip()
            if not token:
                continue
            if "-" in token:
                a, b = token.split("-", 1)
                chapters.extend(range(int(a), int(b) + 1))
            else:
                chapters.append(int(token))
        chapters = sorted(set(ch for ch in chapters if 1 <= ch <= 50))

    existing: list[dict[str, Any]] = []
    completed: set[int] = set()
    if args.resume and args.out.exists():
        existing = [json.loads(line) for line in args.out.read_text(encoding="utf-8").splitlines() if line.strip()]
        completed = {int(r["chapter"]) for r in existing}

    records: list[dict[str, Any]] = list(existing)
    modes: dict[str, int] = {"deterministic": 0, "vertex_fallback": 0}
    for chapter in chapters:
        if chapter in completed:
            print(f"ch {chapter:02d}: resume skip", flush=True)
            continue
        chapter_recs, mode = chapter_records(
            chapter=chapter,
            page_map=page_map,
            low_threshold=args.low_threshold,
            model=args.model,
        )
        modes[mode] = modes.get(mode, 0) + 1
        records.extend(chapter_recs)
        print(f"ch {chapter:02d}: {mode} -> {len(chapter_recs)} verses", flush=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"wrote {args.out}")
    print(f"records={len(records)}")
    print(f"chapters_deterministic={modes['deterministic']} vertex_fallback={modes['vertex_fallback']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
