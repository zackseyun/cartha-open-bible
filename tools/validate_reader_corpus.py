#!/usr/bin/env python3
"""Validate reader-facing POB corpus files before publish.

This is a deterministic, local guardrail for a class of reader regressions
where a synthetic chapter-as-verse-1 mirror is left beside real per-verse
YAMLs. In that state the reader can show verse 1 as the whole chapter while
verses 2+ also exist separately.

Checks:
  1. Every YAML file under translation/ parses.
  2. Synthetic mirror 001.yaml files do not coexist with later verse files.
  3. Verse 1 does not contain the exact normalized text of any later verse in
     the same chapter.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import re
import sys
import time
import unicodedata
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
NUMERIC_STEM_RE = re.compile(r"^\d{3}$")
FOOTNOTE_MARKER_RE = re.compile(r"\[[A-Za-z0-9]{1,6}\]")
SYNTHETIC_NOTE_MARKERS = (
    "synthetic single-verse mirror",
    "chapter-as-verse-1",
    "chapter as verse 1",
    "mirror_extra_canonical_for_cdn.py",
    "chapter-level authoritative yaml",
    "temporary synthetic verse-1 mirror",
)


@dataclasses.dataclass(frozen=True)
class CorpusRecord:
    path: pathlib.Path
    text: str
    normalized_text: str
    note: str
    unit: str
    reference: str
    yaml_kind: str


@dataclasses.dataclass(frozen=True)
class Issue:
    rule: str
    path: pathlib.Path
    details: str
    related_path: pathlib.Path | None = None
    sample: str = ""


def repo_relative(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def normalize_text(text: str) -> str:
    """Normalize text for exact containment checks without style noise."""
    text = unicodedata.normalize("NFKC", text or "")
    text = FOOTNOTE_MARKER_RE.sub("", text)
    # Keep punctuation: exact phrase containment should not become too fuzzy.
    return re.sub(r"\s+", " ", text).strip().casefold()


def preview(text: str, limit: int = 180) -> str:
    one_line = re.sub(r"\s+", " ", text or "").strip()
    return one_line if len(one_line) <= limit else one_line[: limit - 1] + "…"


def load_yaml(path: pathlib.Path) -> tuple[dict[str, Any] | None, str | None]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.load(raw, Loader=YAML_LOADER)
    except Exception as exc:  # noqa: BLE001 - report parser-specific context.
        return None, f"{type(exc).__name__}: {exc}"
    if data is None:
        data = {}
    if not isinstance(data, dict):
        # Syntactically valid, but translation YAMLs are expected to be maps.
        return {}, None
    return data, None


def record_from_doc(path: pathlib.Path, doc: dict[str, Any]) -> CorpusRecord:
    translation = doc.get("translation") or {}
    source = doc.get("source") or {}
    text = str(translation.get("text") or "")
    note = str(doc.get("note") or source.get("note") or "")
    return CorpusRecord(
        path=path,
        text=text,
        normalized_text=normalize_text(text),
        note=note,
        unit=str(doc.get("unit") or ""),
        reference=str(doc.get("reference") or ""),
        yaml_kind="reader_verse" if is_reader_verse_path(path) else "chapter_or_other",
    )


def is_reader_verse_path(path: pathlib.Path) -> bool:
    return (
        path.suffix == ".yaml"
        and NUMERIC_STEM_RE.fullmatch(path.stem) is not None
        and NUMERIC_STEM_RE.fullmatch(path.parent.name) is not None
    )


def is_flat_chapter_path(path: pathlib.Path) -> bool:
    return (
        path.suffix == ".yaml"
        and NUMERIC_STEM_RE.fullmatch(path.stem) is not None
        and NUMERIC_STEM_RE.fullmatch(path.parent.name) is None
    )


def synthetic_mirror_reason(
    verse_one: CorpusRecord,
    flat_chapter: CorpusRecord | None,
    *,
    min_flat_match_chars: int,
) -> str | None:
    note = verse_one.note.casefold()
    for marker in SYNTHETIC_NOTE_MARKERS:
        if marker in note:
            return f"synthetic note marker: {marker}"

    if (
        flat_chapter
        and len(verse_one.normalized_text) >= min_flat_match_chars
        and verse_one.normalized_text == flat_chapter.normalized_text
    ):
        return "001.yaml translation.text exactly matches the sibling flat chapter YAML"

    return None


def scan_corpus(
    *,
    translation_root: pathlib.Path,
    skip_yaml_syntax: bool,
) -> tuple[dict[pathlib.Path, CorpusRecord], list[Issue], int]:
    yaml_paths = sorted(translation_root.rglob("*.yaml"))
    records: dict[pathlib.Path, CorpusRecord] = {}
    issues: list[Issue] = []

    for path in yaml_paths:
        if skip_yaml_syntax and not (is_reader_verse_path(path) or is_flat_chapter_path(path)):
            continue
        doc, error = load_yaml(path)
        if error:
            issues.append(
                Issue(
                    rule="malformed-yaml",
                    path=path,
                    details=error,
                )
            )
            continue
        if doc is not None and (is_reader_verse_path(path) or is_flat_chapter_path(path)):
            records[path] = record_from_doc(path, doc)

    return records, issues, len(yaml_paths)


def check_reader_chapters(
    records: dict[pathlib.Path, CorpusRecord],
    *,
    min_contained_chars: int,
    min_containment_extra_chars: int,
    min_flat_match_chars: int,
) -> tuple[list[Issue], int]:
    groups: dict[pathlib.Path, list[CorpusRecord]] = {}
    for record in records.values():
        if record.yaml_kind == "reader_verse":
            groups.setdefault(record.path.parent, []).append(record)

    issues: list[Issue] = []
    for chapter_dir, chapter_records in sorted(groups.items()):
        by_stem = {record.path.stem: record for record in chapter_records}
        verse_one = by_stem.get("001")
        later_verses = [
            record
            for stem, record in sorted(by_stem.items())
            if stem.isdigit() and int(stem) > 1
        ]
        if not verse_one or not later_verses:
            continue

        flat_path = chapter_dir.parent / f"{chapter_dir.name}.yaml"
        flat_chapter = records.get(flat_path)
        reason = synthetic_mirror_reason(
            verse_one,
            flat_chapter,
            min_flat_match_chars=min_flat_match_chars,
        )
        if reason:
            issues.append(
                Issue(
                    rule="synthetic-mirror-with-real-verses",
                    path=verse_one.path,
                    related_path=later_verses[0].path,
                    details=(
                        f"{reason}; found {len(later_verses)} later reader verse file(s) "
                        "in the same chapter directory"
                    ),
                    sample=preview(verse_one.text),
                )
            )

        verse_one_norm = verse_one.normalized_text
        for later in later_verses:
            later_norm = later.normalized_text
            if len(later_norm) < min_contained_chars:
                continue
            if len(verse_one_norm) < len(later_norm) + min_containment_extra_chars:
                continue
            if later_norm in verse_one_norm:
                issues.append(
                    Issue(
                        rule="verse1-contains-later-verse",
                        path=verse_one.path,
                        related_path=later.path,
                        details=(
                            "001.yaml translation.text contains the exact normalized "
                            "translation.text of a later verse in the same chapter"
                        ),
                        sample=preview(later.text),
                    )
                )
                # One containment hit is enough to prove the chapter is unsafe.
                break

    return issues, len(groups)


def print_issues(issues: list[Issue], *, report_limit: int) -> None:
    for issue in issues[:report_limit]:
        print(f"\n  RULE: {issue.rule}")
        print(f"  FILE: {repo_relative(issue.path)}")
        if issue.related_path:
            print(f"  RELATED: {repo_relative(issue.related_path)}")
        print(f"  WHY:  {issue.details}")
        if issue.sample:
            print(f"  TEXT: {issue.sample!r}")
    if len(issues) > report_limit:
        print(f"\n  ... {len(issues) - report_limit} additional issue(s) omitted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--translation-root",
        type=pathlib.Path,
        default=TRANSLATION_ROOT,
        help="Corpus root to scan (default: repo translation/)",
    )
    parser.add_argument(
        "--skip-yaml-syntax",
        action="store_true",
        help="Only parse reader-relevant YAMLs; faster, but skips full-corpus YAML syntax validation.",
    )
    parser.add_argument(
        "--malformed-yaml",
        choices=("error", "warn", "ignore"),
        default="error",
        help="Whether YAML parse failures should fail, warn, or be ignored (default: error).",
    )
    parser.add_argument(
        "--min-contained-chars",
        type=int,
        default=60,
        help="Minimum normalized later-verse length required for containment violations.",
    )
    parser.add_argument(
        "--min-containment-extra-chars",
        type=int,
        default=12,
        help="Minimum extra normalized characters verse 1 must have beyond the contained later verse.",
    )
    parser.add_argument(
        "--min-flat-match-chars",
        type=int,
        default=120,
        help="Minimum normalized text length before 001.yaml vs flat-chapter equality is considered synthetic.",
    )
    parser.add_argument("--report-limit", type=int, default=30)
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output on success.")
    args = parser.parse_args()

    translation_root = args.translation_root.resolve()
    if not translation_root.exists():
        print(f"ERROR: translation root not found: {translation_root}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    records, yaml_issues, yaml_file_count = scan_corpus(
        translation_root=translation_root,
        skip_yaml_syntax=args.skip_yaml_syntax,
    )
    reader_issues, reader_chapter_count = check_reader_chapters(
        records,
        min_contained_chars=args.min_contained_chars,
        min_containment_extra_chars=args.min_containment_extra_chars,
        min_flat_match_chars=args.min_flat_match_chars,
    )
    issues = (yaml_issues if args.malformed_yaml == "error" else []) + reader_issues
    elapsed = time.perf_counter() - started

    if issues:
        print(f"Reader corpus validation FAILED — {len(issues)} issue(s) found")
        print(
            f"Scanned {yaml_file_count} YAML file(s), "
            f"{reader_chapter_count} reader chapter dir(s) in {elapsed:.1f}s."
        )
        counts = collections.Counter(issue.rule for issue in issues)
        print("Issue counts:")
        for rule, count in sorted(counts.items()):
            print(f"  {rule}: {count}")
        print_issues(issues, report_limit=args.report_limit)
        return 1

    if args.malformed_yaml == "warn" and yaml_issues:
        print(f"WARNING — malformed YAML found but not blocking: {len(yaml_issues)} issue(s)")
        print_issues(yaml_issues, report_limit=min(args.report_limit, 10))

    if not args.quiet:
        syntax_note = "skipped" if args.skip_yaml_syntax else "ok"
        if yaml_issues and args.malformed_yaml == "ignore":
            syntax_note = f"ignored {len(yaml_issues)} malformed file(s)"
        elif yaml_issues and args.malformed_yaml == "warn":
            syntax_note = f"warned on {len(yaml_issues)} malformed file(s)"
        print("OK — reader corpus guardrails passed.")
        print(f"  YAML syntax: {syntax_note} ({yaml_file_count} file(s))")
        print(f"  Reader chapter directories checked: {reader_chapter_count}")
        print("  Synthetic mirror collisions: 0")
        print("  Verse-1 later-verse containment hits: 0")
        print(f"  Elapsed: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
