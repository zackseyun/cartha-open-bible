#!/usr/bin/env python3
"""detect_chapters_from_ocr.py — infer Jubilees chapter starts from OCR text.

Unlike the Gemini vision detector, this works locally against the already-OCR'd
Charles 1895 page texts. It looks for sequential Ge'ez chapter numerals at the
start of lines (e.g. `፪`, `፫`, `፲`) and emits the same cache schema as the
AI detector so `tools/jubilees/build_page_map.py` can consume it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BODY_DIR = REPO_ROOT / "sources" / "jubilees" / "ethiopic" / "transcribed" / "charles_1895" / "body"
DEFAULT_OUT = REPO_ROOT / "sources" / "jubilees" / "ethiopic" / "chapter_detection" / "charles_1895_from_ocr.json"

ETHIOPIC_CHAR_RE = re.compile(r"[\u1200-\u137F]")
RUNNING_HEAD_RE = re.compile(r"^\s*መጽሐፈ፡\s+ኩፋሌ[:፡።]?\s*$", re.MULTILINE)
GEEZ_UNITS = {1: "፩", 2: "፪", 3: "፫", 4: "፬", 5: "፭", 6: "፮", 7: "፯", 8: "፰", 9: "፱"}
GEEZ_TENS = {1: "፲", 2: "፳", 3: "፴", 4: "፵", 5: "፶", 6: "፷", 7: "፸", 8: "፹", 9: "፺"}


def geez_numeral(n: int) -> str:
    if n <= 0:
        return str(n)
    if n >= 100:
        rest = n - 100
        return "፻" + (geez_numeral(rest) if rest else "")
    tens, units = divmod(n, 10)
    out = ""
    if tens:
        out += GEEZ_TENS[tens]
    if units:
        out += GEEZ_UNITS[units]
    return out or "፩"


def display_path(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def parse_page_spec(spec: str) -> list[int]:
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
    return sorted(pages)


def cleaned_text(raw: str) -> str:
    return RUNNING_HEAD_RE.sub("", raw).strip()


def geez_char_count(text: str) -> int:
    return len(ETHIOPIC_CHAR_RE.findall(text))


def likely_body_text(text: str) -> bool:
    return geez_char_count(text) >= 80


def find_sequential_starts(text: str, *, next_expected: int) -> list[int]:
    """Return the next chapter start(s) visible on this page.

    Conservative rule for now: allow at most ONE new chapter per page.
    Jubilees averages ~3-4 pages per chapter, so this sharply reduces false
    positives from ordinary Ge'ez numerals appearing at line starts.
    """
    if next_expected > 50:
        return []
    marker = geez_numeral(next_expected)
    pattern = re.compile(rf"(?m)^\s*{re.escape(marker)}(?:\s+|፡)")
    return [next_expected] if pattern.search(text) else []


def detect(pages: list[int]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "edition": "charles_1895",
        "model": "local_ocr_regex",
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": {},
    }
    current_chapter = 0
    for page in pages:
        path = BODY_DIR / f"charles_1895_ethiopic_p{page:04d}.txt"
        if not path.exists():
            result["pages"][str(page)] = {
                "page_number": page,
                "kind": "error",
                "chapters": [],
                "raw_response": "",
                "finish_reason": "missing_ocr",
                "duration_seconds": 0.0,
                "tokens_out": 0,
                "error": "missing OCR page text",
            }
            continue

        raw = path.read_text(encoding="utf-8")
        text = cleaned_text(raw)
        if not likely_body_text(text):
            result["pages"][str(page)] = {
                "page_number": page,
                "kind": "non-geez",
                "chapters": [],
                "raw_response": "",
                "finish_reason": "local",
                "duration_seconds": 0.0,
                "tokens_out": 0,
                "error": "",
                "geez_char_count": geez_char_count(text),
            }
            continue

        starts: list[int] = []
        if page == 37 and current_chapter == 0:
            starts.append(1)
            current_chapter = 1
        starts.extend(find_sequential_starts(text, next_expected=current_chapter + 1))
        if starts:
            current_chapter = starts[-1]
            result["pages"][str(page)] = {
                "page_number": page,
                "kind": "chapter_start",
                "chapters": starts,
                "raw_response": "\n".join(str(s) for s in starts),
                "finish_reason": "local",
                "duration_seconds": 0.0,
                "tokens_out": 0,
                "error": "",
                "geez_char_count": geez_char_count(text),
            }
        else:
            result["pages"][str(page)] = {
                "page_number": page,
                "kind": "continuation" if current_chapter else "non-geez",
                "chapters": [],
                "raw_response": "continuation" if current_chapter else "non-geez",
                "finish_reason": "local",
                "duration_seconds": 0.0,
                "tokens_out": 0,
                "error": "",
                "geez_char_count": geez_char_count(text),
            }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages", default="37-210")
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    pages = parse_page_spec(args.pages)
    data = detect(pages)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    starts = sorted({c for entry in data["pages"].values() for c in (entry.get("chapters") or [])})
    print(f"wrote {display_path(args.out)}")
    print(f"pages scanned: {len(pages)}")
    print(f"chapter starts found: {starts[:20]}{' …' if len(starts) > 20 else ''}")
    print(f"count: {len(starts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
