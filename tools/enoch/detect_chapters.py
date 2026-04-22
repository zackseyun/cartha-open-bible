#!/usr/bin/env python3
"""detect_chapters.py — scan a Geʿez Enoch PDF and label every page.

For each page of the source PDF, asks Gemini 3.1 Pro whether the page:
  - STARTS one or more chapters (Arabic chapter numbers listed)
  - is a CONTINUATION of an in-progress chapter
  - is NON-GEEZ (front matter, apparatus, English, indices, blank)
  - ERRORED

Cache: sources/enoch/ethiopic/chapter_detection/<edition>.json
Resumable: cached pages are skipped unless --force.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import bakeoff_geez_ocr  # type: ignore

PAGE_MAP = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "page_map.json"
CACHE_ROOT = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "chapter_detection"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
CHAPTER_LINE_RE = re.compile(r"^\s*(\d{1,3})\s*$")


@dataclass
class PageClassification:
    page_number: int
    kind: str
    chapters: list[int]
    raw_response: str
    finish_reason: str
    duration_seconds: float
    tokens_out: int
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "kind": self.kind,
            "chapters": self.chapters,
            "raw_response": self.raw_response,
            "finish_reason": self.finish_reason,
            "duration_seconds": self.duration_seconds,
            "tokens_out": self.tokens_out,
            "error": self.error,
        }


DETECTION_PROMPT = (
    "This is a single page from an Ethiopic (Ge'ez) critical edition of "
    "the Book of 1 Enoch. Classify the page using EXACTLY ONE of these "
    "output formats, with no prose, no explanation, no markdown:\n\n"
    "1. If the page starts one or more chapters (look for the Ge'ez word "
    "ምዕራፍ followed by a Ge'ez numeral, a chapter numeral like ፩ ፪ "
    "standing alone as a heading, a Latin-numeral chapter heading, or a "
    "large Arabic numeral acting as a chapter heading), output each "
    "chapter number as an ARABIC INTEGER on its own line, in order of "
    "appearance on the page. Example output for a page starting chapters "
    "5 and 6:\n5\n6\n\n"
    "2. If the page shows continuous Ge'ez body text with no chapter "
    "heading on this page, output exactly:\ncontinuation\n\n"
    "3. If the page has no Ge'ez body text \u2014 e.g. title page, "
    "preface, table of contents, index, English/Latin/German critical "
    "apparatus or translation, blank page, or purely decorative page "
    "\u2014 output exactly:\nnon-geez\n\n"
    "Be strict: chapter numerals are ALWAYS at the top of a chapter's "
    "first paragraph, and are visually distinct from ordinary text. "
    "Ignore verse numbers (small Ge'ez numerals embedded inside body "
    "text), page numbers, footnote markers, and running heads when "
    "classifying. Output only what the format demands. No other text.\n\n"
    "Ge'ez numeral decoding (CRITICAL \u2014 do not confuse the tens "
    "place with the units place):\n"
    "  units: \u1369=1 \u136a=2 \u136b=3 \u136c=4 \u136d=5 \u136e=6 \u136f=7 \u1370=8 \u1371=9\n"
    "  tens:  \u1372=10 \u1373=20 \u1374=30 \u1375=40 \u1376=50 \u1377=60 \u1378=70 \u1379=80 \u137a=90\n"
    "  hundreds: \u137b=100\n"
    "Compound chapter numerals are read tens-then-units. Examples:\n"
    "  \u1372\u1369 = 11    \u1372\u136a = 12    \u1373 = 20    \u1373\u1369 = 21\n"
    "  \u1376\u136d = 55    \u1377\u136e = 66    \u1378\u136a = 72    \u1379 = 80\n"
    "  \u137b = 100   \u137b\u1369 = 101  \u137b\u1370 = 108\n"
    "Example wrong reading: confusing \u1378\u136a (72) with \u1372\u136a (12) "
    "by dropping the tens stroke. If you see two glyphs in the heading, "
    "decode BOTH; never report only the units."
)


def parse_classification(text: str) -> tuple[str, list[int]]:
    cleaned = text.strip().lower()
    if cleaned == "continuation":
        return "continuation", []
    if cleaned in {"non-geez", "non geez", "nongeez"}:
        return "non-geez", []
    chapters: list[int] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = CHAPTER_LINE_RE.match(line)
        if not m:
            return "error", []
        v = int(m.group(1))
        if 1 <= v <= 108:
            chapters.append(v)
    return ("chapter_start", chapters) if chapters else ("error", [])


def classify_page(pdf_path: pathlib.Path, page_num: int, *, dpi: int, model: str) -> PageClassification:
    image = bakeoff_geez_ocr.render_page_png(pdf_path, page_num, dpi=dpi)
    started = time.time()
    result = bakeoff_geez_ocr.call_gemini(image, DETECTION_PROMPT, model=model, thinking_budget=512, max_output_tokens=512)
    raw = (result.text or "").strip()
    kind, chapters = parse_classification(raw) if raw else ("error", [])
    error = result.error or ("" if raw else "empty response")
    if kind == "error" and not error:
        error = f"unparseable response: {raw[:160]!r}"
    return PageClassification(
        page_number=page_num,
        kind=kind,
        chapters=chapters,
        raw_response=raw,
        finish_reason=result.finish_reason,
        duration_seconds=round(time.time() - started, 2),
        tokens_out=result.tokens_out,
        error=error if kind == "error" else "",
    )


def load_map() -> dict[str, Any]:
    return json.loads(PAGE_MAP.read_text(encoding="utf-8"))


def pdf_page_count(pdf_path: pathlib.Path) -> int:
    out = subprocess.check_output(["pdfinfo", str(pdf_path)], text=True)
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"could not determine page count for {pdf_path}")


def cache_path(edition: str) -> pathlib.Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{edition}.json"


def load_cache(edition: str) -> dict[str, Any]:
    path = cache_path(edition)
    if not path.exists():
        return {"edition": edition, "model": DEFAULT_MODEL, "pages": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(edition: str, data: dict[str, Any]) -> None:
    data["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache_path(edition).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(edition: str, *, pages: list[int], force: bool, workers: int, dpi: int, model: str) -> dict[str, Any]:
    mapping = load_map()["editions"][edition]
    pdf_path = REPO_ROOT / mapping["pdf"]
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    cache = load_cache(edition)
    page_cache: dict[str, Any] = cache.setdefault("pages", {})

    to_do: list[int] = []
    skipped = 0
    for page in pages:
        key = str(page)
        if key in page_cache and not force and page_cache[key].get("kind") != "error":
            skipped += 1
            continue
        to_do.append(page)
    print(f"[detect] {edition}: {len(to_do)} pages to classify ({skipped} cached)")
    if not to_do:
        return cache

    cache["model"] = model
    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(classify_page, pdf_path, p, dpi=dpi, model=model): p for p in to_do}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                cls = fut.result()
            except Exception as exc:  # noqa: BLE001
                cls = PageClassification(p, "error", [], "", "error", 0.0, 0, str(exc))
            page_cache[str(p)] = cls.to_dict()
            completed += 1
            tag = cls.kind if cls.kind != "chapter_start" else f"ch{'+'.join(str(c) for c in cls.chapters)}"
            print(f"  [{completed}/{len(to_do)}] page {p:>3}: {tag} (dur={cls.duration_seconds}s)" + (f" err={cls.error[:80]!r}" if cls.error else ""), flush=True)
            if completed % 25 == 0:
                save_cache(edition, cache)
    save_cache(edition, cache)
    return cache


def parse_page_spec(spec: str, total: int) -> list[int]:
    if spec == "all":
        return list(range(1, total + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            pages.update(range(int(a), int(b) + 1))
        else:
            pages.add(int(token))
    return sorted(p for p in pages if 1 <= p <= total)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition", required=True, choices=["dillmann_1851", "charles_1906"])
    ap.add_argument("--pages", default="all")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    mapping = load_map()["editions"][args.edition]
    total = pdf_page_count(REPO_ROOT / mapping["pdf"])
    pages = parse_page_spec(args.pages, total)
    print(f"[detect] {args.edition}: PDF {total} pages, classifying {len(pages)} via {args.model} @ {args.dpi} DPI, {args.workers} workers")
    cache = run(args.edition, pages=pages, force=args.force, workers=args.workers, dpi=args.dpi, model=args.model)

    kinds: dict[str, int] = {"chapter_start": 0, "continuation": 0, "non-geez": 0, "error": 0}
    starts: list[int] = []
    for entry in cache["pages"].values():
        kinds[entry.get("kind", "error")] = kinds.get(entry.get("kind", "error"), 0) + 1
        starts.extend(entry.get("chapters") or [])
    starts = sorted(set(starts))
    missing = [c for c in range(1, 109) if c not in starts]
    print("[detect] summary:")
    for k, v in kinds.items():
        print(f"  {k}: {v}")
    print(f"  unique chapter starts: {len(starts)}")
    if missing:
        head = ", ".join(str(c) for c in missing[:30])
        print(f"  MISSING ({len(missing)}): {head}{' …' if len(missing) > 30 else ''}")
    else:
        print("  all 108 chapters detected ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
