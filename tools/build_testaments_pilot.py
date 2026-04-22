#!/usr/bin/env python3
"""build_testaments_pilot.py — normalize one Testament pilot into chapter files.

This takes a raw OCR page range for a single Testament source witness, extracts
only the BODY block from each page, concatenates the result, and then uses
`tools/testaments_twelve_patriarchs.py` to split the material into chapter
files under:

    sources/testaments_twelve_patriarchs/transcribed/normalized/<slug>/chNN.txt

It is intentionally lightweight and pilot-oriented. The first target is Reuben
from Charles 1908 Greek pages 66-79.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
from typing import Iterable

import testaments_twelve_patriarchs as t12p


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "sources" / "testaments_twelve_patriarchs" / "transcribed" / "raw"
NORMALIZED_DIR = REPO_ROOT / "sources" / "testaments_twelve_patriarchs" / "transcribed" / "normalized"


def parse_pages(spec: str) -> list[int]:
    pages: list[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if end < start:
                raise ValueError(f"Descending page range: {chunk}")
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(chunk))
    return sorted(dict.fromkeys(pages))


def raw_page_file(prefix: str, page: int) -> pathlib.Path:
    return RAW_DIR / f"{prefix}_p{page:04d}.txt"


def running_head_chapter(running_head: str) -> int | None:
    match = re.search(r"([IVXLCDMΙΧ]+)[⁰¹²³⁴⁵⁶⁷⁸⁹0-9]*\.", running_head)
    if not match:
        return None
    token = t12p._normalize_heading_token(match.group(1))
    return t12p.ROMAN_NUMERALS.get(token)


def build_page_bodies(prefix: str, pages: list[int], testament_slug: str) -> tuple[list[tuple[int, str, str]], list[str]]:
    """Return ordered `(page, running_head, body)` tuples with obvious duplicates removed."""
    chunks: list[tuple[int, str, str]] = []
    warnings: list[str] = []
    last_running_head_num: int | None = None
    for page in pages:
        path = raw_page_file(prefix, page)
        if not path.exists():
            warnings.append(f"Missing raw OCR file for page {page}; continuing with remaining pages.")
            continue
        page_text = path.read_text(encoding="utf-8")
        running_head = t12p.extract_running_head(page_text)
        nums = [int(n) for n in re.findall(r"\d+", running_head)]
        if nums:
            running_head_num = max(nums)
            if last_running_head_num is not None and running_head_num <= last_running_head_num:
                continue
            last_running_head_num = running_head_num
        body = t12p.extract_body(page_text)
        if not chunks:
            body = t12p._trim_before_testament_title(body, testament_slug)
        if body.strip():
            chunks.append((page, running_head, body.strip()))
    return chunks, warnings


def build_chapter_map(prefix: str, pages: list[int], testament_slug: str) -> tuple[dict[int, list[str]], list[str]]:
    page_bodies, warnings = build_page_bodies(prefix, pages, testament_slug)
    chapter_map: dict[int, list[str]] = collections.defaultdict(list)
    current_chapter: int | None = None

    for page, running_head, body in page_bodies:
        head_chapter = running_head_chapter(running_head)
        if head_chapter is not None:
            current_chapter = head_chapter

        matches = list(t12p.ROMAN_HEADING_RE.finditer(body))
        if not matches:
            if current_chapter is None:
                warnings.append(f"Page {page} has no detectable chapter heading or running-head chapter.")
                continue
            chapter_map[current_chapter].append(body)
            continue

        first = matches[0]
        leading = body[: first.start()].strip()
        if leading:
            target = current_chapter
            if target is None:
                token = t12p._normalize_heading_token(first.group("num"))
                target = t12p.ROMAN_NUMERALS.get(token)
            if target is not None:
                chapter_map[target].append(leading)

        for idx, match in enumerate(matches):
            token = t12p._normalize_heading_token(match.group("num"))
            chapter_num = t12p.ROMAN_NUMERALS.get(token)
            if chapter_num is None:
                warnings.append(f"Page {page} has unrecognized chapter token {match.group('num')!r}.")
                continue
            next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
            chunk = body[match.end() : next_start].strip()
            if chunk:
                chapter_map[chapter_num].append(chunk)
                current_chapter = chapter_num

    return dict(chapter_map), warnings


def write_chapter_files(
    *,
    testament_slug: str,
    pages: list[int],
    source_label: str,
    prefix: str,
) -> tuple[list[pathlib.Path], list[str]]:
    chapter_map, warnings = build_chapter_map(prefix, pages, testament_slug)
    meta = t12p.TESTAMENT_BY_SLUG[testament_slug]
    chapter_nums = sorted(chapter_map)
    if chapter_nums:
        for prev, curr in zip(chapter_nums, chapter_nums[1:]):
            if curr != prev + 1:
                warnings.append(f"Non-consecutive chapter sequence: {prev} -> {curr}.")
        if chapter_nums[-1] != meta.chapter_count:
            warnings.append(
                f"Recovered through chapter {chapter_nums[-1]}, but the reference structure expects {meta.chapter_count} chapters."
            )
    out_paths: list[pathlib.Path] = []
    out_dir = NORMALIZED_DIR / testament_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    for chapter_num in chapter_nums:
        path = out_dir / f"ch{chapter_num:02d}.txt"
        chapter_text = " ".join(part.strip() for part in chapter_map[chapter_num] if part.strip()).strip()
        payload = (
            f"# testament: {testament_slug}\n"
            f"# chapter: {chapter_num}\n"
            f"# source_pages: {','.join(str(p) for p in pages)}\n"
            f"# source_prefix: {prefix}\n"
            f"# source_edition: {source_label}\n"
            f"# normalization: pilot chapter split from raw OCR; verify against source before drafting full-book production.\n\n"
            f"{chapter_text}\n"
        )
        path.write_text(payload, encoding="utf-8")
        out_paths.append(path)

    return out_paths, warnings


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testament", required=True, choices=sorted(t12p.TESTAMENT_BY_SLUG))
    parser.add_argument("--pages", required=True, help="Page spec, e.g. 66-79")
    parser.add_argument("--prefix", required=True, help="Raw OCR stem prefix, e.g. t12p_charles1908gk")
    parser.add_argument("--source-label", required=True, help="Human-readable source label")
    args = parser.parse_args(list(argv) if argv is not None else None)

    pages = parse_pages(args.pages)
    out_paths, warnings = write_chapter_files(
        testament_slug=args.testament,
        pages=pages,
        source_label=args.source_label,
        prefix=args.prefix,
    )

    print(f"Wrote {len(out_paths)} chapter file(s) for {args.testament}:")
    for path in out_paths:
        print(f"- {path.relative_to(REPO_ROOT)}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
