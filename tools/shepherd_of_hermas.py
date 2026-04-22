#!/usr/bin/env python3
"""shepherd_of_hermas.py — parser and normalizer for the Hermas OCR layer.

The Lightfoot 1891 OCR currently lives as raw page files under
``sources/shepherd_of_hermas/transcribed/raw/``. Those pages are already good
enough to work with, but Hermas has two layout quirks that make a dedicated
parser necessary:

1. A single page can contain the *end* of one Hermas unit and the *start* of the
   next (for example a new Vision / Mandate / Similitude heading mid-page).
2. The running heads use Lightfoot's compact scholarly notation
   (``V. 3. xiii``, ``M. 4. ii``, ``S. 5. vi``), while the body text sometimes
   introduces the same transitions with Greek headings like ``Ἐντολὴ β´.`` or
   ``[Παραβολὴ ϛ´.]``.

This module turns the raw pages into stable normalized units that the future
Hermas prompt-builder / drafter can consume directly.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Iterable


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "sources" / "shepherd_of_hermas" / "transcribed" / "raw"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "shepherd_of_hermas" / "transcribed"
NORMALIZED_DIR = TRANSCRIBED_DIR / "normalized"
UNIT_MAP_PATH = TRANSCRIBED_DIR / "unit_map.json"

BODY_RE = re.compile(
    r"\[BODY\]\s*\n(.*?)(?=\n\[(?:RUNNING HEAD|APPARATUS|FOOTNOTES|MARGINALIA|BLANK|PLATE)\]|\n---END-PAGE---|\Z)",
    re.DOTALL,
)
RUNNING_HEAD_RE = re.compile(r"\[RUNNING HEAD\]\s*\n(.*?)(?=\n\[)", re.DOTALL)
PAGE_RE = re.compile(r"_p(\d{4})\.txt$")
RUN_HEAD_KEY_RE = re.compile(r"([VMS])\.\s*(\d+)(?:\.\s*([ivxlcdm]+|\d+))?", re.IGNORECASE)
MINOR_HEAD_RE = re.compile(r"^([IVXLCDM]+)\.\s*(.*)$")
MAJOR_HEAD_RE = re.compile(r"^\[?\s*(Ὅρασις|Ἀποκάλυψις|Ἐντολὴ|Παραβολὴ)\s+([^\]]+?)\s*\]?\.?$")

_GREEK_CHAR = r"[\u0370-\u03FF\u1F00-\u1FFF]"
_HYPHEN_BREAK_RE = re.compile(rf"({_GREEK_CHAR})[-‐]\s+({_GREEK_CHAR})")
_MULTI_SPACE_RE = re.compile(r"\s+")

_PRIME_CHARS = {
    "\u0374",  # Greek numeral sign
    "\u0384",  # tonos
    "\u02B9",  # modifier prime
    "\u00B4",  # acute accent
    "\u2032",  # prime
    "'",
}

_GREEK_NUMERAL_VALUES = {
    "α": 1,
    "β": 2,
    "γ": 3,
    "δ": 4,
    "ε": 5,
    "ϛ": 6,
    "ϝ": 6,
    "ς": 6,
    "ζ": 7,
    "η": 8,
    "θ": 9,
    "ι": 10,
    "κ": 20,
}

PART_LABELS = {
    "V": "Vision",
    "M": "Mandate",
    "S": "Similitude",
}
PART_ORDER = {"V": 0, "M": 1, "S": 2}
MAJOR_HEADING_TO_PART = {
    "Ὅρασις": "V",
    "Ἀποκάλυψις": "V",
    "Ἐντολὴ": "M",
    "Παραβολὴ": "S",
}


@dataclass(frozen=True)
class HermasUnitKey:
    part: str
    major: int
    minor: str | None = None

    @property
    def unit_id(self) -> str:
        if self.minor:
            return f"{self.part}.{self.major}.{self.minor}"
        return f"{self.part}.{self.major}"

    @property
    def label(self) -> str:
        base = f"{PART_LABELS[self.part]} {self.major}"
        return f"{base}, section {self.minor}" if self.minor else base

    @property
    def filename(self) -> str:
        if self.minor:
            return f"{self.part.lower()}{self.major:02d}_{self.minor}.txt"
        return f"{self.part.lower()}{self.major:02d}.txt"


@dataclass(frozen=True)
class RawPage:
    page: int
    path: pathlib.Path
    running_head: str
    body_lines: list[str]
    page_hint: HermasUnitKey | None


@dataclass
class HermasUnit:
    key: HermasUnitKey
    text: str
    source_pages: list[int]
    source_files: list[str]
    heading: str | None = None
    notes: list[str] = field(default_factory=list)
    source_edition: str = "Lightfoot & Harmer 1891 (normalized OCR)"

    @property
    def unit_id(self) -> str:
        return self.key.unit_id

    @property
    def label(self) -> str:
        return self.key.label

    @property
    def output_path(self) -> pathlib.Path:
        return NORMALIZED_DIR / self.key.filename


def _strip_diacritics(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _strip_primes(s: str) -> str:
    s = s.strip()
    while s and (s[-1] in _PRIME_CHARS or s[-1] in ".,;:])}"):
        s = s[:-1]
    return s.strip()


def _parse_greek_numeral(token: str) -> int | None:
    cleaned = _strip_primes(_strip_diacritics(token)).lower().strip()
    cleaned = cleaned.strip("[](){} ")
    if cleaned.isdigit():
        return int(cleaned)
    if not cleaned:
        return None
    total = 0
    for ch in cleaned:
        value = _GREEK_NUMERAL_VALUES.get(ch)
        if value is None:
            return None
        total += value
    return total or None


def _roman_to_int(token: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    token = token.upper()
    total = 0
    prev = 0
    for ch in reversed(token):
        value = values[ch]
        if value < prev:
            total -= value
        else:
            total += value
            prev = value
    return total


def _int_to_roman(n: int) -> str:
    table = (
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
    )
    out: list[str] = []
    remaining = n
    for value, symbol in table:
        while remaining >= value:
            out.append(symbol)
            remaining -= value
    return "".join(out)


def _normalize_minor(token: str | None) -> str | None:
    if token is None:
        return None
    token = token.strip().lower().strip("[](){}.")
    if not token:
        return None
    if token.isdigit():
        return _int_to_roman(int(token))
    return _int_to_roman(_roman_to_int(token.upper()))


def raw_page_path(page: int) -> pathlib.Path:
    candidates = sorted(RAW_DIR.glob(f"*_p{page:04d}.txt"))
    return candidates[0] if candidates else RAW_DIR / f"missing_p{page:04d}.txt"


def available_raw_pages() -> list[int]:
    out: list[int] = []
    for path in sorted(RAW_DIR.glob("*.txt")):
        m = PAGE_RE.search(path.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(set(out))


def extract_body(page_text: str) -> str:
    m = BODY_RE.search(page_text)
    return m.group(1).strip() if m else ""


def extract_running_head(page_text: str) -> str:
    m = RUNNING_HEAD_RE.search(page_text)
    return _MULTI_SPACE_RE.sub(" ", m.group(1).strip()) if m else ""


def _clean_body_lines(body_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in body_text.splitlines():
        line = raw_line.replace("|", " ").strip()
        line = line.strip('"`“”')
        if not line:
            continue
        lines.append(line)
    return lines


def parse_running_head(head: str) -> HermasUnitKey | None:
    m = RUN_HEAD_KEY_RE.search(head)
    if not m:
        return None
    part = m.group(1).upper()
    major = int(m.group(2))
    minor = _normalize_minor(m.group(3))
    return HermasUnitKey(part=part, major=major, minor=minor)


def load_raw_page(page: int) -> RawPage | None:
    path = raw_page_path(page)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if "---GREEK-EXTRA-PAGE---" not in text or "[BODY]" not in text:
        return None
    running_head = extract_running_head(text)
    body = extract_body(text)
    if not body.strip():
        return None
    return RawPage(
        page=page,
        path=path,
        running_head=running_head,
        body_lines=_clean_body_lines(body),
        page_hint=parse_running_head(running_head),
    )


def valid_raw_pages() -> list[RawPage]:
    out: list[RawPage] = []
    for page in available_raw_pages():
        record = load_raw_page(page)
        if record is not None:
            out.append(record)
    return out


def invalid_raw_pages() -> list[int]:
    valid = {page.page for page in valid_raw_pages()}
    return [page for page in available_raw_pages() if page not in valid]


def _minorized_majors(pages: list[RawPage]) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for page in pages:
        if page.page_hint and page.page_hint.minor:
            out.add((page.page_hint.part, page.page_hint.major))
    return out


def _default_key_for_major(part: str, major: int, minorized: set[tuple[str, int]]) -> HermasUnitKey:
    if (part, major) in minorized:
        return HermasUnitKey(part=part, major=major, minor="i")
    return HermasUnitKey(part=part, major=major, minor=None)


def _detect_major_heading(line: str, minorized: set[tuple[str, int]]) -> tuple[HermasUnitKey, str] | None:
    candidate = line.strip().strip('"`“”')
    m = MAJOR_HEAD_RE.match(candidate)
    if not m:
        return None
    part = MAJOR_HEADING_TO_PART.get(m.group(1))
    major = _parse_greek_numeral(m.group(2))
    if part is None or major is None:
        return None
    return _default_key_for_major(part, major, minorized), candidate.strip("[]")


def _detect_minor_heading(line: str) -> tuple[str, str] | None:
    candidate = line.strip().strip('"`“”')
    m = MINOR_HEAD_RE.match(candidate)
    if not m:
        return None
    marker = _normalize_minor(m.group(1))
    remainder = m.group(2).strip()
    if not marker:
        return None
    return marker, remainder


def _normalize_unit_text(lines: list[str]) -> str:
    if not lines:
        return ""
    joined = "\n".join(lines)
    joined = joined.replace("|", " ")
    joined = _HYPHEN_BREAK_RE.sub(r"\1\2", joined)
    joined = re.sub(r"\s*\n\s*", " ", joined)
    joined = _MULTI_SPACE_RE.sub(" ", joined)
    return joined.strip()


def parse_units() -> list[HermasUnit]:
    pages = valid_raw_pages()
    minorized = _minorized_majors(pages)

    units: list[HermasUnit] = []
    current_key: HermasUnitKey | None = None
    current_heading: str | None = None
    current_lines: list[str] = []
    current_pages: list[int] = []
    current_files: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_heading, current_lines, current_pages, current_files
        if current_key is None:
            return
        text = _normalize_unit_text(current_lines)
        if text:
            units.append(
                HermasUnit(
                    key=current_key,
                    heading=current_heading,
                    text=text,
                    source_pages=current_pages[:],
                    source_files=current_files[:],
                )
            )
        current_key = None
        current_heading = None
        current_lines = []
        current_pages = []
        current_files = []

    def start_unit(key: HermasUnitKey, *, page: int, file_name: str, heading: str | None = None) -> None:
        nonlocal current_key, current_heading, current_pages, current_files
        current_key = key
        current_heading = heading
        current_pages = [page]
        current_files = [file_name]

    def touch_current(page: int, file_name: str) -> None:
        if current_key is None:
            return
        if page not in current_pages:
            current_pages.append(page)
        if file_name not in current_files:
            current_files.append(file_name)

    for page in pages:
        has_major_heading = any(_detect_major_heading(line, minorized) is not None for line in page.body_lines)
        has_minor_heading = any(_detect_minor_heading(line) is not None for line in page.body_lines)
        has_explicit_heading = has_major_heading or has_minor_heading

        if current_key is None:
            if page.page_hint is not None:
                start_unit(page.page_hint, page=page.page, file_name=page.path.name)
        elif page.page_hint is not None and page.page_hint != current_key:
            same_major = (
                page.page_hint.part == current_key.part
                and page.page_hint.major == current_key.major
            )
            if same_major:
                if not has_explicit_heading:
                    flush()
                    start_unit(page.page_hint, page=page.page, file_name=page.path.name)
            else:
                if has_major_heading:
                    pass
                elif has_minor_heading and page.page_hint.minor is not None:
                    flush()
                    start_unit(
                        _default_key_for_major(page.page_hint.part, page.page_hint.major, minorized),
                        page=page.page,
                        file_name=page.path.name,
                    )
                else:
                    flush()
                    start_unit(page.page_hint, page=page.page, file_name=page.path.name)

        if current_key is not None:
            touch_current(page.page, page.path.name)

        for raw_line in page.body_lines:
            line = raw_line.strip()
            major = _detect_major_heading(line, minorized)
            if major is not None:
                key, heading = major
                flush()
                start_unit(key, page=page.page, file_name=page.path.name, heading=heading)
                continue

            minor = _detect_minor_heading(line)
            if minor is not None and current_key is not None:
                marker, remainder = minor
                candidate_key = HermasUnitKey(part=current_key.part, major=current_key.major, minor=marker)
                if candidate_key != current_key:
                    flush()
                    start_unit(candidate_key, page=page.page, file_name=page.path.name)
                else:
                    touch_current(page.page, page.path.name)
                if remainder:
                    current_lines.append(remainder)
                continue

            if current_key is None:
                inferred = page.page_hint or HermasUnitKey(part="V", major=1, minor="i")
                start_unit(inferred, page=page.page, file_name=page.path.name)
            current_lines.append(line)

    flush()

    merged: dict[str, HermasUnit] = {}
    for unit in units:
        existing = merged.get(unit.unit_id)
        if existing is None:
            merged[unit.unit_id] = unit
            continue
        existing.text = _normalize_unit_text([existing.text, unit.text])
        for page_num in unit.source_pages:
            if page_num not in existing.source_pages:
                existing.source_pages.append(page_num)
        for file_name in unit.source_files:
            if file_name not in existing.source_files:
                existing.source_files.append(file_name)
        if existing.heading is None and unit.heading is not None:
            existing.heading = unit.heading

    return sorted(
        merged.values(),
        key=lambda unit: (
            PART_ORDER[unit.key.part],
            unit.key.major,
            _roman_to_int(unit.key.minor.upper()) if unit.key.minor else 0,
        ),
    )


def unit_map_payload() -> dict[str, object]:
    units = parse_units()
    return {
        "book": "Shepherd of Hermas",
        "source": "Lightfoot 1891 raw OCR",
        "valid_raw_pages": [page.page for page in valid_raw_pages()],
        "invalid_raw_pages": invalid_raw_pages(),
        "unit_count": len(units),
        "units": [
            {
                "unit_id": unit.unit_id,
                "label": unit.label,
                "part": unit.key.part,
                "part_name": PART_LABELS[unit.key.part],
                "major": unit.key.major,
                "minor": unit.key.minor,
                "heading": unit.heading,
                "source_pages": unit.source_pages,
                "source_files": unit.source_files,
                "text_path": str(unit.output_path.relative_to(REPO_ROOT)),
            }
            for unit in units
        ],
    }


def write_normalized() -> dict[str, object]:
    units = parse_units()
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    for stale in NORMALIZED_DIR.glob("*.txt"):
        stale.unlink()
    for unit in units:
        lines = [
            f"# unit_id: {unit.unit_id}",
            f"# label: {unit.label}",
            f"# source_pages: {','.join(str(p) for p in unit.source_pages)}",
            f"# source_files: {','.join(unit.source_files)}",
            f"# source_edition: {unit.source_edition}",
        ]
        if unit.heading:
            lines.append(f"# heading: {unit.heading}")
        lines.extend(["", unit.text, ""])
        unit.output_path.write_text("\n".join(lines), encoding="utf-8")

    payload = unit_map_payload()
    UNIT_MAP_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_unit(unit_id: str) -> HermasUnit | None:
    for unit in parse_units():
        if unit.unit_id == unit_id:
            return unit
    return None


def summary() -> dict[str, object]:
    payload = unit_map_payload()
    payload["normalized_dir"] = str(NORMALIZED_DIR.relative_to(REPO_ROOT))
    payload["unit_ids"] = [unit["unit_id"] for unit in payload["units"]]
    return payload


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse and normalize the Shepherd of Hermas OCR layer.")
    ap.add_argument("--write-normalized", action="store_true", help="Write normalized unit files and unit_map.json.")
    ap.add_argument("--unit", help="Print one parsed unit as JSON (e.g. V.3.xiii or M.4.ii).")
    ap.add_argument("--json", action="store_true", help="Emit JSON summary.")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.write_normalized:
        payload = write_normalized()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.unit:
        unit = load_unit(args.unit)
        if unit is None:
            raise SystemExit(f"Unknown unit: {args.unit}")
        print(json.dumps({
            "unit_id": unit.unit_id,
            "label": unit.label,
            "heading": unit.heading,
            "source_pages": unit.source_pages,
            "source_files": unit.source_files,
            "text": unit.text,
        }, ensure_ascii=False, indent=2))
        return 0

    payload = summary()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Shepherd of Hermas: {payload['unit_count']} parsed units")
        print(f"Valid raw pages: {len(payload['valid_raw_pages'])}; invalid raw pages: {len(payload['invalid_raw_pages'])}")
        print("First units:")
        for unit_id in payload["unit_ids"][:12]:
            print(f"- {unit_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
