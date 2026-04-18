#!/usr/bin/env python3
"""
consistency_lint.py — Scan drafted verse YAMLs for consistency issues.

Current checks:
- Same source word glossed differently without a sufficiently explicit rationale
- DOCTRINE.md contested-term defaults overridden without an explicit rationale
- Missing source text
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import draft  # noqa: E402
import sblgnt  # noqa: E402
import wlc  # noqa: E402


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
LINT_REPORTS_ROOT = REPO_ROOT / "lint_reports"


@dataclass
class LintFlag:
    category: str
    message: str
    verse_id: str | None = None


def load_yaml_records(
    *,
    testament: str | None = None,
    books: set[str] | None = None,
) -> list[tuple[pathlib.Path, dict[str, Any]]]:
    pattern = TRANSLATION_ROOT.glob("*/*/*/*.yaml")
    records: list[tuple[pathlib.Path, dict[str, Any]]] = []

    for path in sorted(pattern):
        parts = path.relative_to(TRANSLATION_ROOT).parts
        current_testament, slug = parts[0], parts[1]
        if testament and current_testament != testament:
            continue
        if books and slug not in books:
            continue
        records.append((path, yaml.safe_load(path.read_text(encoding="utf-8"))))

    return records


def resolve_book_slug_filters(tokens: list[str]) -> set[str]:
    if not tokens:
        return set()

    resolved: set[str] = set()
    nt_by_code = {code: slug for code, (_num, slug, _prefix) in sblgnt.NT_BOOKS.items()}
    ot_by_code = {code: slug for code, (_osis, slug, _title, _file) in wlc.OT_BOOKS.items()}

    for token in tokens:
        upper = token.upper()
        resolved.add(nt_by_code.get(upper, ot_by_code.get(upper, token.lower())))

    return resolved


def load_source_verse(record: dict[str, Any]) -> Any | None:
    verse_id = record.get("id", "")
    source = record.get("source", {})
    edition = source.get("edition")

    try:
        book_code, chapter_str, verse_str = str(verse_id).split(".")
        chapter = int(chapter_str)
        verse = int(verse_str)
    except ValueError:
        return None

    if edition == "SBLGNT":
        return sblgnt.load_verse(book_code, chapter, verse, draft.SOURCES_ROOT)
    if edition == "WLC":
        return wlc.load_verse(book_code, chapter, verse, draft.SOURCES_ROOT)
    return None


def has_documented_variance(rationale: str) -> bool:
    rationale = rationale.strip()
    if len(rationale) >= 40:
        return True
    return draft.explicit_override_rationale(rationale)


def gloss_variance_flags(records: list[tuple[pathlib.Path, dict[str, Any]]]) -> list[LintFlag]:
    by_lemma: dict[str, list[dict[str, str]]] = defaultdict(list)

    for _path, record in records:
        verse_id = str(record.get("id", ""))
        reference = str(record.get("reference", ""))
        source_verse = load_source_verse(record)
        for decision in record.get("lexical_decisions") or []:
            source_word = str(decision.get("source_word", "") or "").strip()
            chosen = str(decision.get("chosen", "") or "").strip()
            rationale = str(decision.get("rationale", "") or "").strip()
            norm = draft.normalize_term(source_word)
            if not norm or not chosen:
                continue
            matched_lemmas: list[tuple[str, str]] = []
            if source_verse is not None:
                seen: set[str] = set()
                for word in source_verse.words:
                    surface = getattr(word, "word", getattr(word, "text", ""))
                    if draft.decision_matches_lemma(source_word, word.lemma, [surface]):
                        lemma_norm = draft.normalize_term(word.lemma)
                        if lemma_norm and lemma_norm not in seen:
                            matched_lemmas.append((lemma_norm, word.lemma))
                            seen.add(lemma_norm)

            targets = matched_lemmas or [(norm, source_word)]
            for lemma_norm, lemma_display in targets:
                by_lemma[lemma_norm].append(
                    {
                        "source_word": source_word,
                        "lemma": lemma_display,
                        "chosen": chosen,
                        "chosen_norm": draft.normalize_term(chosen),
                        "rationale": rationale,
                        "verse_id": verse_id,
                        "reference": reference,
                    }
                )

    flags: list[LintFlag] = []
    for entries in by_lemma.values():
        glosses = {entry["chosen_norm"] for entry in entries if entry["chosen_norm"]}
        if len(glosses) <= 1:
            continue
        if all(has_documented_variance(entry["rationale"]) for entry in entries):
            continue

        gloss_counter = Counter(entry["chosen"] for entry in entries)
        lemma = entries[0]["lemma"]
        sample_refs = ", ".join(sorted({entry["reference"] for entry in entries})[:4])
        flags.append(
            LintFlag(
                category="Undocumented gloss variance",
                verse_id=entries[0]["verse_id"],
                message=(
                    f"{lemma} has multiple glosses {sorted(gloss_counter)} "
                    f"without strong rationale coverage across the set ({sample_refs})."
                ),
            )
        )

    return flags


def doctrine_flags(records: list[tuple[pathlib.Path, dict[str, Any]]]) -> list[LintFlag]:
    contested_terms = draft.load_contested_terms()
    flags: list[LintFlag] = []

    for _path, record in records:
        source_verse = load_source_verse(record)
        if source_verse is None:
            continue

        lexical_decisions = record.get("lexical_decisions") or []
        verse_terms: dict[str, list[str]] = defaultdict(list)
        for word in source_verse.words:
            lemma_norm = draft.normalize_term(word.lemma)
            if lemma_norm in contested_terms:
                verse_terms[lemma_norm].append(getattr(word, "word", getattr(word, "text", "")))

        for lemma_norm, surface_forms in verse_terms.items():
            term = contested_terms[lemma_norm]
            matches = [
                decision for decision in lexical_decisions
                if isinstance(decision, dict)
                and draft.decision_matches_lemma(
                    str(decision.get("source_word", "")),
                    term["lemma"],
                    surface_forms=surface_forms,
                )
            ]
            if not matches:
                flags.append(
                    LintFlag(
                        category="Doctrine contested-term gap",
                        verse_id=str(record.get("id", "")),
                        message=(
                            f"{record.get('reference')}: contested lemma {term['lemma']} "
                            "appears in the source but is missing from lexical_decisions."
                        ),
                    )
                )
                continue

            default_options = set(term.get("default_options", []))
            if not any(
                draft.normalize_term(str(match.get("chosen", ""))) in default_options
                or draft.explicit_override_rationale(str(match.get("rationale", "")))
                for match in matches
            ):
                flags.append(
                    LintFlag(
                        category="Doctrine contested-term override",
                        verse_id=str(record.get("id", "")),
                        message=(
                            f"{record.get('reference')}: contested lemma {term['lemma']} "
                            "uses a non-default gloss without an explicit override rationale."
                        ),
                    )
                )

    return flags


def source_text_flags(records: list[tuple[pathlib.Path, dict[str, Any]]]) -> list[LintFlag]:
    flags: list[LintFlag] = []
    for _path, record in records:
        source_text = str((record.get("source") or {}).get("text", "") or "").strip()
        if not source_text:
            flags.append(
                LintFlag(
                    category="Missing source text",
                    verse_id=str(record.get("id", "")),
                    message=f"{record.get('reference')}: source.text is empty.",
                )
            )
    return flags


def write_report(
    *,
    phase: str,
    records: list[tuple[pathlib.Path, dict[str, Any]]],
    flags: list[LintFlag],
    output_path: pathlib.Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Consistency lint report — {phase}",
        "",
        f"- Scanned verses: {len(records)}",
        f"- Unresolved flags: {len(flags)}",
        f"- Generated at: {draft.utc_timestamp()}",
        "",
    ]

    if not flags:
        lines.extend([
            "## Result",
            "",
            "No unresolved consistency-lint flags detected. ✅",
            "",
        ])
    else:
        categories = Counter(flag.category for flag in flags)
        lines.extend(["## Summary", ""])
        for category, count in sorted(categories.items()):
            lines.append(f"- {category}: {count}")
        lines.append("")

        for category in sorted(categories):
            lines.extend([f"## {category}", ""])
            for flag in [flag for flag in flags if flag.category == category]:
                prefix = f"`{flag.verse_id}` — " if flag.verse_id else ""
                lines.append(f"- {prefix}{flag.message}")
            lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def run_lint(
    *,
    phase: str,
    testament: str | None = None,
    book_filters: set[str] | None = None,
    output_path: pathlib.Path | None = None,
) -> tuple[list[LintFlag], pathlib.Path, int]:
    records = load_yaml_records(testament=testament, books=book_filters)
    output_path = output_path or (LINT_REPORTS_ROOT / f"{phase}.md")

    flags = (
        gloss_variance_flags(records)
        + doctrine_flags(records)
        + source_text_flags(records)
    )
    write_report(phase=phase, records=records, flags=flags, output_path=output_path)
    return flags, output_path, len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, help="Phase label used in the report filename/title")
    parser.add_argument("--testament", choices=["nt", "ot"])
    parser.add_argument("--books", nargs="*", default=[], help="Book codes or translation slugs to scan")
    parser.add_argument("--output", help="Explicit report path")
    args = parser.parse_args()

    book_filters = resolve_book_slug_filters(args.books)
    output_path = pathlib.Path(args.output) if args.output else None

    flags, report_path, scanned = run_lint(
        phase=args.phase,
        testament=args.testament,
        book_filters=book_filters or None,
        output_path=output_path,
    )

    print(f"Scanned {scanned} verse YAMLs")
    print(f"Wrote {report_path.relative_to(REPO_ROOT)}")
    print(f"Flags: {len(flags)}")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
