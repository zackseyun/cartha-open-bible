#!/usr/bin/env python3
"""build_page_map.py — assemble Jubilees page_map from chapter detection cache.

Consumes `sources/jubilees/ethiopic/chapter_detection/charles_1895.json` and
proposes an updated `sources/jubilees/page_map.proposed.json`.

Rules:
  - `chapter_start` with chapters [a, b, c]: each chapter owns the page;
    the LAST chapter on the page also owns following continuation pages.
  - `continuation`: appended to the most recently started chapter.
  - `non-geez`: skipped.
  - `error`: warns + breaks continuation.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CACHE_ROOT = REPO_ROOT / "sources" / "jubilees" / "ethiopic" / "chapter_detection"
PAGE_MAP = REPO_ROOT / "sources" / "jubilees" / "page_map.json"
PROPOSED = REPO_ROOT / "sources" / "jubilees" / "page_map.proposed.json"

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


def chapter_hint(n: int) -> str:
    return f"Jubilees chapter {n} (መጽሐፈ፡ ኩፋሌ {geez_numeral(n)})"


def load_detection(edition: str, cache_path: pathlib.Path | None = None) -> dict[int, dict[str, Any]]:
    path = cache_path or (CACHE_ROOT / f"{edition}.json")
    if not path.exists():
        raise SystemExit(f"detection cache missing for {edition}: {path}")
    pages = json.loads(path.read_text(encoding="utf-8")).get("pages", {})
    return {int(k): v for k, v in pages.items()}


def assemble_chapters(classifications: dict[int, dict[str, Any]], *, edition: str) -> tuple[dict[int, list[int]], list[str]]:
    warnings: list[str] = []
    chapter_pages: dict[int, list[int]] = {}
    current_chapter: int | None = None
    last_seen_chapter = 0

    for page in sorted(classifications.keys()):
        entry = classifications[page]
        kind = entry.get("kind")
        if kind == "chapter_start":
            chapters = list(entry.get("chapters") or [])
            if not chapters:
                warnings.append(f"{edition} p{page}: chapter_start with empty chapters")
                continue
            for chapter in chapters:
                chapter_pages.setdefault(chapter, [])
                if page not in chapter_pages[chapter]:
                    chapter_pages[chapter].append(page)
            first = chapters[0]
            if first < last_seen_chapter:
                warnings.append(
                    f"{edition} p{page}: chapter {first} starts after later chapter {last_seen_chapter} "
                    "was already seen — likely numeral misread"
                )
            else:
                last_seen_chapter = max(last_seen_chapter, max(chapters))
            current_chapter = chapters[-1]
        elif kind == "continuation":
            if current_chapter is None:
                warnings.append(f"{edition} p{page}: continuation before any chapter start")
                continue
            chapter_pages.setdefault(current_chapter, [])
            if page not in chapter_pages[current_chapter]:
                chapter_pages[current_chapter].append(page)
        elif kind == "error":
            warnings.append(
                f"{edition} p{page}: classification error "
                f"({(entry.get('error') or '?')[:80]}); breaks continuation"
            )
            current_chapter = None
    return chapter_pages, warnings


def load_existing_map() -> dict[str, Any]:
    return json.loads(PAGE_MAP.read_text(encoding="utf-8"))


def build_edition_section(edition: str, chapter_pages: dict[int, list[int]], existing: dict[str, Any]) -> dict[str, Any]:
    existing_chapters = existing.get("chapters", {})
    out = copy.deepcopy(existing)
    chapters_out: dict[str, Any] = {}

    # Preserve already-curated chapters, then overlay detected results.
    for key, value in existing_chapters.items():
        chapters_out[key] = copy.deepcopy(value)

    for chapter in sorted(chapter_pages.keys()):
        key = f"{chapter:03d}"
        prior = chapters_out.get(key, {})
        prior_pages = [int(p) for p in (prior.get("pages") or [])]
        merged_pages = sorted(set(prior_pages) | set(chapter_pages[chapter]))
        chapters_out[key] = {
            **prior,
            "pages": merged_pages,
            "chapter_hint": prior.get("chapter_hint") or chapter_hint(chapter),
            "opening_hint": prior.get("opening_hint", ""),
        }

    out["chapters"] = chapters_out
    missing = [c for c in range(1, 51) if f"{c:03d}" not in chapters_out]
    if missing:
        out["tbd_chapters"] = {
            "_remaining": (
                f"Still missing {len(missing)} chapters after automated detection: "
                + ", ".join(str(c) for c in missing[:20])
                + (" …" if len(missing) > 20 else "")
            )
        }
    else:
        out.pop("tbd_chapters", None)
    return out


def summarise(edition: str, proposed: dict[str, Any], existing: dict[str, Any]) -> str:
    lines = [f"{edition}:"]
    existing_chapters = existing.get("chapters", {})
    new_chapters = proposed["chapters"]
    added = sorted(set(new_chapters) - set(existing_chapters))
    changed = []
    for key in sorted(set(new_chapters) & set(existing_chapters)):
        if existing_chapters[key].get("pages") != new_chapters[key].get("pages"):
            changed.append((key, existing_chapters[key].get("pages"), new_chapters[key].get("pages")))
    lines.append(f"  chapters covered: {len(new_chapters)} (added {len(added)}, changed {len(changed)})")
    if added:
        head = ", ".join(added[:10])
        lines.append(f"  added first 10: {head}{' …' if len(added) > 10 else ''}")
    for key, old, new in changed[:8]:
        lines.append(f"  changed {key}: {old} -> {new}")
    missing = sorted(c for c in range(1, 51) if f"{c:03d}" not in new_chapters)
    if missing:
        head = ", ".join(str(c) for c in missing[:20])
        lines.append(f"  STILL MISSING ({len(missing)}): {head}{' …' if len(missing) > 20 else ''}")
    else:
        lines.append("  all 50 chapters covered ✓")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edition", default="charles_1895", choices=["charles_1895"])
    ap.add_argument("--cache-path", type=pathlib.Path, help="Override detection cache JSON path")
    args = ap.parse_args()

    existing = load_existing_map()
    proposed = copy.deepcopy(existing)
    proposed["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    classifications = load_detection(args.edition, cache_path=args.cache_path)
    chapter_pages, warnings = assemble_chapters(classifications, edition=args.edition)
    existing_section = existing.get("editions", {}).get(args.edition, {})
    proposed.setdefault("editions", {})[args.edition] = build_edition_section(args.edition, chapter_pages, existing_section)

    PROPOSED.write_text(json.dumps(proposed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote: {PROPOSED.relative_to(REPO_ROOT)}")
    print()
    print(summarise(args.edition, proposed["editions"][args.edition], existing_section))
    print()
    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings[:50]:
            print(f"  {w}")
        if len(warnings) > 50:
            print(f"  … and {len(warnings) - 50} more")
    else:
        print("No warnings.")
    print()
    print(f"To promote: mv {PROPOSED.relative_to(REPO_ROOT)} {PAGE_MAP.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
