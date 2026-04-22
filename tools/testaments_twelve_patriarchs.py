#!/usr/bin/env python3
"""testaments_twelve_patriarchs.py — parser/scaffold for T. XII Patriarchs.

This module does two related jobs for the Testaments track:

1. **Classify the currently vendored raw OCR pages** under
   ``sources/testaments_twelve_patriarchs/transcribed/raw/`` so we can tell
   whether we actually have a continuous Greek base text yet.
2. **Provide the parser API for future normalized text**, splitting one
   testament into chapter blocks by Roman-numeral chapter headings.

At the moment, the currently vendored Sinker 1879 local PDF proves to be an
appendix / collation witness rather than a continuous Greek reading text. That
means the raw OCR pilot is still valuable, but it is *not* yet enough to draft
from directly. This tool makes that state explicit instead of silently treating
the appendix as a translation base.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import asdict, dataclass
from typing import Iterable


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES_ROOT = REPO_ROOT / "sources" / "testaments_twelve_patriarchs"
RAW_DIR = SOURCES_ROOT / "transcribed" / "raw"
NORMALIZED_DIR = SOURCES_ROOT / "transcribed" / "normalized"
RAW_PREFIXES = (
    "t12p_sinker1879",
    "t12p_sinker1879_g31",
    "t12p_charles1908gk",
)

BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:RUNNING HEAD|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)
RUNNING_HEAD_RE = re.compile(
    r"\[RUNNING HEAD\]\s*\n(.*?)(?=\n\[(?:BODY|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)
GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
MULTISPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class TestamentMeta:
    order: int
    slug: str
    display_name: str
    chapter_count: int


@dataclass(frozen=True)
class RawPageRecord:
    page: int
    classification: str
    running_head: str
    body_preview: str
    path: str


@dataclass(frozen=True)
class TestamentChapter:
    testament_slug: str
    chapter: int
    text: str
    marker_raw: str


TESTAMENTS: list[TestamentMeta] = [
    TestamentMeta(1, "reuben", "Testament of Reuben", 7),
    TestamentMeta(2, "simeon", "Testament of Simeon", 9),
    TestamentMeta(3, "levi", "Testament of Levi", 19),
    TestamentMeta(4, "judah", "Testament of Judah", 26),
    TestamentMeta(5, "issachar", "Testament of Issachar", 7),
    TestamentMeta(6, "zebulun", "Testament of Zebulun", 10),
    TestamentMeta(7, "dan", "Testament of Dan", 7),
    TestamentMeta(8, "naphtali", "Testament of Naphtali", 9),
    TestamentMeta(9, "gad", "Testament of Gad", 8),
    TestamentMeta(10, "asher", "Testament of Asher", 8),
    TestamentMeta(11, "joseph", "Testament of Joseph", 20),
    TestamentMeta(12, "benjamin", "Testament of Benjamin", 12),
]
TESTAMENT_BY_SLUG = {meta.slug: meta for meta in TESTAMENTS}

ROMAN_NUMERALS: dict[str, int] = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
    "XXI": 21,
    "XXII": 22,
    "XXIII": 23,
    "XXIV": 24,
    "XXV": 25,
    "XXVI": 26,
}
ROMAN_HEADING_RE = re.compile(
    r"^\s*(?:[A-Za-zΑ-Ωα-ωβγδεζηθικλμνξοπρστυφχψω,\-· ]{0,20}\s+)?(?P<num>[IVXLCDMΙ]+)\.\s*",
    re.MULTILINE,
)


def _normalize_heading_token(token: str) -> str:
    """Normalize OCR variants used in chapter numerals.

    The Charles 1908 OCR often emits Greek capital iota ``Ι`` instead of Latin
    ``I`` inside Roman numerals (e.g. ``Ι.`` or ``ΙΙ.``). For heading parsing
    those are equivalent.
    """
    return token.replace("Ι", "I")


def extract_running_head(page_text: str) -> str:
    match = RUNNING_HEAD_RE.search(page_text)
    return match.group(1).strip() if match else ""


def extract_body(page_text: str) -> str:
    match = BODY_RE.search(page_text)
    return match.group(1).strip() if match else ""


def available_raw_pages() -> list[int]:
    pages: set[int] = set()
    for prefix in RAW_PREFIXES:
        for path in RAW_DIR.glob(f"{prefix}_p*.txt"):
            match = re.search(r"_p(\d{4})\.txt$", path.name)
            if match:
                pages.add(int(match.group(1)))
    return sorted(pages)


def raw_page_path(page: int) -> pathlib.Path | None:
    for pattern in tuple(f"{prefix}_p{page:04d}.txt" for prefix in RAW_PREFIXES):
        candidate = RAW_DIR / pattern
        if candidate.exists():
            return candidate
    return None


def load_raw_page(page: int) -> str | None:
    path = raw_page_path(page)
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def classify_page_text(page_text: str) -> str:
    running_head = extract_running_head(page_text)
    body = extract_body(page_text)
    combined = f"{running_head}\n{body}".strip()
    upper = combined.upper()

    if not combined:
        return "blank"
    if "GOOGLE" in upper or "HARVARD COLLEGE LIBRARY" in upper:
        return "google_front_matter"
    if "TESTAMENTA XII PATRIARCHARUM" in upper and "APPENDIX" not in upper:
        return "front_matter_title"
    if "TESTAMENTA XII PATRIARCHARUM" in upper and "APPENDIX" in upper:
        return "appendix_title"
    if "COLLATIONS" in upper:
        return "appendix_collation_title"
    if any(
        marker in upper
        for marker in (
            "PREFACE.",
            "ADDENDA.",
            "CORRIGENDA.",
            "THE GREEK MSS.",
            "THE LATIN VERSION.",
            "THE ENGLISH VERSIONS.",
            "THE WELSH VERSION.",
            "THE GERMAN VERSIONS.",
            "THE DUTCH AND FLEMISH VERSIONS.",
            "THE ARMENIAN VERSION.",
        )
    ):
        return "front_matter"
    if "CAMBRIDGE:" in upper or "PRINTED BY" in upper:
        return "front_matter"
    if "COLLATION OF CD." in upper:
        return "appendix_collation"
    if re.search(r"\bc\.\s*\d+", body) and GREEK_RE.search(body):
        return "appendix_collation"
    if GREEK_RE.search(body):
        return "greek_main_candidate"
    return "other"


def classify_page(page: int) -> str:
    text = load_raw_page(page)
    if text is None:
        return "missing"
    return classify_page_text(text)


def page_record(page: int) -> RawPageRecord:
    path = raw_page_path(page)
    text = load_raw_page(page) or ""
    body = extract_body(text)
    preview = MULTISPACE_RE.sub(" ", body).strip()[:180]
    return RawPageRecord(
        page=page,
        classification=classify_page_text(text) if text else "missing",
        running_head=extract_running_head(text),
        body_preview=preview,
        path=str(path.relative_to(REPO_ROOT)) if path is not None else "",
    )


def greek_main_candidate_pages() -> list[int]:
    return [page for page in available_raw_pages() if classify_page(page) == "greek_main_candidate"]


def normalized_chapter_path(testament_slug: str, chapter: int) -> pathlib.Path:
    return NORMALIZED_DIR / testament_slug / f"ch{chapter:02d}.txt"


def available_normalized_chapters(testament_slug: str) -> list[int]:
    base = NORMALIZED_DIR / testament_slug
    out: list[int] = []
    if not base.exists():
        return out
    for path in sorted(base.glob("ch*.txt")):
        match = re.match(r"ch(\d{2})\.txt$", path.name)
        if match:
            out.append(int(match.group(1)))
    return out


def load_chapter(testament_slug: str, chapter: int) -> TestamentChapter | None:
    path = normalized_chapter_path(testament_slug, chapter)
    if not path.exists():
        return None
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    text = " ".join(lines).strip()
    if not text:
        return None
    return TestamentChapter(
        testament_slug=testament_slug,
        chapter=chapter,
        text=text,
        marker_raw=f"{chapter}",
    )


def _strip_leading_title_lines(lines: list[str], testament_slug: str) -> list[str]:
    out: list[str] = []
    slug_upper = testament_slug.replace("_", " ").upper()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if upper.startswith("THE TESTAMENT OF "):
            continue
        if "TESTAMENT" in upper and slug_upper in upper:
            continue
        out.append(stripped)
    return out


def parse_testament_text(testament_slug: str, raw_text: str) -> tuple[list[TestamentChapter], list[str]]:
    meta = TESTAMENT_BY_SLUG.get(testament_slug)
    if meta is None:
        raise KeyError(f"Unknown testament slug: {testament_slug!r}")

    lines = _strip_leading_title_lines(raw_text.splitlines(), testament_slug)
    normalized = "\n".join(lines).strip()
    warnings: list[str] = []

    if not normalized:
        return [], ["Input text was empty after trimming title/blank lines."]

    matches = list(ROMAN_HEADING_RE.finditer(normalized))
    if not matches:
        warnings.append(
            "No Roman-numeral chapter headings were found; treating the whole text as one chapter block."
        )
        return (
            [
                TestamentChapter(
                    testament_slug=testament_slug,
                    chapter=1,
                    text=MULTISPACE_RE.sub(" ", normalized).strip(),
                    marker_raw="",
                )
            ],
            warnings,
        )

    chapters: list[TestamentChapter] = []
    last_chapter_num = 0
    for idx, match in enumerate(matches):
        normalized_num = _normalize_heading_token(match.group("num"))
        if normalized_num not in ROMAN_NUMERALS:
            warnings.append(f"Skipping unrecognized chapter heading token: {match.group('num')!r}.")
            continue
        chapter_num = ROMAN_NUMERALS[normalized_num]
        if chapter_num <= last_chapter_num:
            warnings.append(
                f"Ignoring non-increasing heading token {match.group('num')!r} parsed as chapter {chapter_num} after chapter {last_chapter_num}."
            )
            continue
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized)
        chapter_text = normalized[match.end() : next_start].strip()
        chapter_text = MULTISPACE_RE.sub(" ", chapter_text).strip()
        if not chapter_text:
            warnings.append(f"Chapter {chapter_num} was detected but its body text was empty.")
            continue
        chapters.append(
            TestamentChapter(
                testament_slug=testament_slug,
                chapter=chapter_num,
                text=chapter_text,
                marker_raw=match.group(0).strip(),
            )
        )
        last_chapter_num = chapter_num

    chapter_numbers = [chapter.chapter for chapter in chapters]
    if chapter_numbers and chapter_numbers[0] != 1:
        warnings.append(f"First recovered chapter is {chapter_numbers[0]}, not 1.")
    for prev, curr in zip(chapter_numbers, chapter_numbers[1:]):
        if curr != prev + 1:
            warnings.append(f"Non-consecutive chapter sequence: {prev} -> {curr}.")
    if chapter_numbers and chapter_numbers[-1] != meta.chapter_count:
        warnings.append(
            f"Recovered through chapter {chapter_numbers[-1]}, but the reference structure expects {meta.chapter_count} chapters."
        )

    return chapters, warnings


def summary() -> dict[str, object]:
    page_records = [page_record(page) for page in available_raw_pages()]
    candidate_pages = [record.page for record in page_records if record.classification == "greek_main_candidate"]
    notes: list[str] = []
    if not candidate_pages:
        notes.append(
            "Current raw OCR pages appear to come from front matter / appendix / collations, not from a continuous Greek base text."
        )
        notes.append(
            "Parser support for normalized testament text is ready, but a true Greek reading-text witness still needs to be OCRed or vendored."
        )

    return {
        "book": "Testaments of the Twelve Patriarchs",
        "raw_page_count": len(page_records),
        "raw_page_classification": {str(record.page): record.classification for record in page_records},
        "greek_main_candidate_pages": candidate_pages,
        "source_state": "appendix_only" if not candidate_pages else "main_text_present",
        "testaments": [asdict(meta) for meta in TESTAMENTS],
        "normalized_chapters_present": {
            meta.slug: available_normalized_chapters(meta.slug) for meta in TESTAMENTS
        },
        "notes": notes,
    }


def _to_jsonable_chapters(chapters: list[TestamentChapter], warnings: list[str]) -> dict[str, object]:
    return {
        "chapter_count": len(chapters),
        "chapters": [asdict(chapter) for chapter in chapters],
        "warnings": warnings,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="Print current source/parser summary JSON.")
    parser.add_argument("--classify-page", type=int, help="Classify one raw OCR page number.")
    parser.add_argument(
        "--parse-file",
        type=pathlib.Path,
        help="Parse a normalized testament text file into chapters.",
    )
    parser.add_argument(
        "--testament",
        choices=[meta.slug for meta in TESTAMENTS],
        help="Required with --parse-file; testament slug to parse.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.classify_page is not None:
        print(json.dumps(asdict(page_record(args.classify_page)), ensure_ascii=False, indent=2))
        return 0

    if args.parse_file is not None:
        if not args.testament:
            parser.error("--testament is required with --parse-file")
        raw_text = args.parse_file.read_text(encoding="utf-8")
        chapters, warnings = parse_testament_text(args.testament, raw_text)
        print(json.dumps(_to_jsonable_chapters(chapters, warnings), ensure_ascii=False, indent=2))
        return 0

    print(json.dumps(summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
