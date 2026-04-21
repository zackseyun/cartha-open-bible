#!/usr/bin/env python3
"""build_translation_prompt.py — assemble a Phase 9 deuterocanon prompt.

Builds the structured verse-level prompt described in
REFERENCE_SOURCES.md for deuterocanonical drafting:
  - Zone 1 primary Greek from the adjudicated Swete corpus
  - Zone 1 Hebrew / MT parallel where applicable (SIR / TOB / 1ES)
  - Zone 2 consult registry + live local consult excerpts
  - doctrine + philosophy excerpts
  - explicit derivative-work guardrails

This module is usable both as a CLI and as a library from tools/draft.py.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"

import hebrew_parallels  # noqa: E402
import lxx_swete  # noqa: E402


@dataclass
class PromptBundle:
    verse: lxx_swete.SwtVerse
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    revision_candidates: list[dict[str, str]]
    source_warnings: list[str]


def _git_head_short() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _snapshot_label(label: str) -> str:
    return f"{label} @{_git_head_short()}"


def _load_excerpt(path: pathlib.Path, keep_sections: set[str]) -> str:
    if not path.exists():
        return f"({path.name} not found)"
    lines = path.read_text(encoding="utf-8").splitlines()
    keeping = False
    out: list[str] = []
    for line in lines:
        if line.startswith("## "):
            keeping = line.strip() in keep_sections
        if keeping:
            out.append(line)
    return "\n".join(out).strip() or f"({path.name} excerpt empty)"


def doctrine_excerpt() -> str:
    return _load_excerpt(
        DOCTRINE_PATH,
        {"## Translation philosophy", "## Contested terms"},
    )


def philosophy_excerpt() -> str:
    return _load_excerpt(
        PHILOSOPHY_PATH,
        {"## What we are translating", '## What "transparent" actually means here'},
    )


def _numbering_note(book_code: str) -> str | None:
    if book_code == "ADE":
        return (
            "Swete's Greek Esther numbering differs from many English reader editions. "
            "Keep the source reference explicit in the draft metadata."
        )
    if book_code == "ADA":
        return (
            "This source stream preserves Swete's Additions-to-Daniel numbering/context, "
            "which does not line up cleanly with reader-facing PAZ / SUS / BEL splits."
        )
    return None


def _parallel_source_payload(zone1_parallel: dict | None) -> tuple[list[dict[str, Any]], list[str]]:
    if not zone1_parallel:
        return [], []

    parallel_sources: list[dict[str, Any]] = []
    labels: list[str] = []
    kind = zone1_parallel.get("kind")

    if kind == "direct_hebrew":
        parallel_sources.append(
            {
                "edition": "lxx-swete-1909",
                "text": "",
                "kind": "greek_parallel",
                "note": "Greek fallback / consistency check alongside the Hebrew Vorlage.",
            }
        )
        labels.append(_snapshot_label("Sefaria Ben Sira Kahana (Zone 1 Hebrew)"))
    elif kind == "indirect_hebrew":
        parallel_sources.append(
            {
                "edition": "neubauer-tobit-1878",
                "text": zone1_parallel.get("hebrew", ""),
                "kind": kind,
                "note": zone1_parallel.get("note", ""),
                "reference": f"{zone1_parallel.get('book_code')} {zone1_parallel.get('chapter')}:{zone1_parallel.get('verse')}",
            }
        )
        labels.append(_snapshot_label("Neubauer 1878 Tobit (Zone 1 Semitic reference)"))
    elif kind == "mt_parallel":
        parallel_sources.append(
            {
                "edition": "WLC",
                "text": zone1_parallel.get("hebrew", ""),
                "kind": kind,
                "note": zone1_parallel.get("note", ""),
                "reference": zone1_parallel.get("mt_ref", ""),
            }
        )
        labels.append(_snapshot_label("WLC MT alignment (Zone 1 Hebrew parallel)"))

    return parallel_sources, labels


def _build_source_payload(
    verse: lxx_swete.SwtVerse,
    parallel_info: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    zone1_parallel = parallel_info.get("zone_1_parallel") or {}
    kind = zone1_parallel.get("kind")

    source_payload: dict[str, Any] = {
        "edition": "lxx-swete-1909",
        "text": verse.greek_text,
        "language": "Greek",
        "pages": verse.source_pages,
        "confidence": verse.source_confidence,
        "validation": verse.source_validation,
    }
    primary_label = (
        "Swete LXX (normalized translation corpus)"
        if verse.translation == "swete-1909-normalized"
        else "Swete LXX (scan-adjudicated corpus)"
    )
    labels = [_snapshot_label(primary_label)]

    parallel_sources, parallel_labels = _parallel_source_payload(zone1_parallel)
    labels.extend(parallel_labels)

    if kind == "direct_hebrew":
        source_payload.update(
            {
                "edition": "sefaria-ben-sira-kahana",
                "text": zone1_parallel.get("hebrew", ""),
                "language": "Hebrew",
                "note": zone1_parallel.get("note", ""),
            }
        )
        parallel_sources[0]["text"] = verse.greek_text
        parallel_sources[0]["reference"] = verse.reference
    elif kind in {"indirect_hebrew", "mt_parallel"}:
        source_payload["note"] = (
            "Primary translation anchor remains the Greek; see parallel_sources for the Semitic / MT witness."
        )

    if parallel_sources:
        source_payload["parallel_sources"] = parallel_sources

    numbering_note = _numbering_note(verse.book_code)
    if numbering_note:
        source_payload["numbering_note"] = numbering_note
    if verse.translation == "swete-1909-normalized":
        source_payload["note"] = (
            (source_payload.get("note", "") + " " if source_payload.get("note") else "")
            + "This verse is being loaded from the normalized translation-ready override layer derived from the adjudicated corpus."
        ).strip()

    return source_payload, labels


def _revision_candidates(
    verse: lxx_swete.SwtVerse,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    ref = f"{verse.book_code} {verse.chapter}:{verse.verse}"

    if verse.book_code == "SIR" and (39, 27) <= (verse.chapter, verse.verse) <= (44, 17):
        out.append(
            {
                "reason": (
                    f"{ref} is in the Masada Ben Sira coverage range; if IAA image access opens, "
                    "upgrade the Masada witness from Zone 2 consult to Zone 1."
                ),
                "trigger": "iaa_masada_access_granted",
            }
        )
    if verse.book_code == "SIR" and (3, 6) <= (verse.chapter, verse.verse) <= (16, 26):
        out.append(
            {
                "reason": (
                    f"{ref} falls in the Schechter facsimile range; when direct MSS A/B transcription completes, "
                    "re-run the draft against the deepened Zone 1 Hebrew witness."
                ),
                "trigger": "schechter_pipeline_completes",
            }
        )
    if verse.book_code == "TOB":
        out.append(
            {
                "reason": (
                    f"{ref} may improve when Qumran Tobit fragments become Zone 1 via direct access."
                ),
                "trigger": "iaa_qumran_tobit_access_granted",
            }
        )
        out.append(
            {
                "reason": (
                    f"{ref} should be re-checked if Fitzmyer DJD XIX becomes redistributable for prompt use."
                ),
                "trigger": "djd_xix_copyright_expires",
            }
        )

    if verse.book_code == "BAR" and verse.chapter == 5 and verse.verse >= 10:
        out.append(
            {
                "reason": (
                    f"{ref} sits inside a known cross-book numbering spill and should be revisited once the Baruch/Lamentations boundary is normalized."
                ),
                "trigger": "page_metadata_corrected",
            }
        )
    if verse.book_code == "WIS" and verse.chapter == 19 and verse.verse >= 28:
        out.append(
            {
                "reason": (
                    f"{ref} sits inside a known chapter-boundary spill into adjacent Sirach material and should be rechecked once Wisdom chapter boundaries are normalized."
                ),
                "trigger": "page_metadata_corrected",
            }
        )

    return out


def integrity_issues_for_verse(verse: lxx_swete.SwtVerse) -> list[str]:
    issues = list(verse.source_warnings)
    if verse.book_code == "ADA":
        issues.append(
            "ADA is still stored as a monolithic Swete-derived stream rather than the reader-facing PAZ / SUS / BEL split. Draft against it only with explicit source-reference disclosure."
        )
    return issues


def build_deuterocanon_prompt(
    verse: lxx_swete.SwtVerse,
    *,
    allow_integrity_issues: bool = False,
) -> PromptBundle:
    if verse.book_code not in lxx_swete.DEUTEROCANONICAL_BOOKS:
        raise ValueError(f"{verse.book_code} is not a deuterocanonical Swete book")

    issues = integrity_issues_for_verse(verse)
    if issues and not allow_integrity_issues:
        raise ValueError(
            "Source integrity warning(s) block drafting for this verse by default: "
            + " | ".join(issues)
            + " -- rerun with an explicit override only if you intend to inspect the source manually."
        )

    parallel_info = hebrew_parallels.lookup_with_consult(
        verse.book_code,
        verse.chapter,
        verse.verse,
    )
    source_payload, zone1_sources = _build_source_payload(verse, parallel_info)
    zone2_registry = parallel_info.get("zone_2_registry") or []
    zone2_live = parallel_info.get("zone_2_live") or []
    zone2_known = [entry.get("name", "") for entry in zone2_registry if entry.get("name")]
    zone2_known.extend(
        entry.get("source_name", "")
        for entry in zone2_live
        if entry.get("source_name")
    )

    prompt = f"""# Verse

Reference: {verse.reference}
ID: {verse.canonical_id}
Source pages: {verse.source_pages or '(none recorded)'}
Source confidence: {verse.source_confidence or 'unspecified'}
Source validation: {verse.source_validation or 'unspecified'}

# Zone 1 primary source

{json.dumps(source_payload, ensure_ascii=False, indent=2)}

# Zone 2 consult registry

{json.dumps(zone2_registry, ensure_ascii=False, indent=2)}

# Zone 2 live consult excerpts (local-only; do not reproduce)

{json.dumps(zone2_live, ensure_ascii=False, indent=2)}

# Source integrity notes

{json.dumps(issues or ['No known integrity warnings for this verse.'], ensure_ascii=False, indent=2)}

# Derivative-work guardrails

- The English output must remain anchored in Zone 1 sources.
- Zone 2 material may inform judgment, but do NOT reproduce Zone 2 English phrasing or reconstructed wording.
- Fact-level notes are allowed (e.g. manuscript support, edition-level conclusions), but creative scholarly expression is not.
- If Zone 2 were redacted from this prompt, the translation should still be defensible from Zone 1 alone.
- Preserve source uncertainty honestly: if the Greek source itself is medium/low confidence, do not write as if the wording were indisputable.

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# Task

Produce the highest-quality draft English translation you can for {verse.reference}.

Requirements:
- Translate from the most-original Zone 1 witness available for this verse.
- If `source.parallel_sources` is present, use it as an actual translation input, not just a footnote source, while keeping the Greek in view.
- Preserve key lexical decisions in `lexical_decisions`.
- Preserve major alternative readings in `footnotes` when appropriate.
- Mention source-level uncertainty honestly if it materially affects the translation.
"""

    return PromptBundle(
        verse=verse,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1_sources,
        zone2_consults_known=zone2_known,
        revision_candidates=_revision_candidates(verse),
        source_warnings=issues,
    )


def _to_jsonable(bundle: PromptBundle) -> dict[str, Any]:
    return {
        "reference": bundle.verse.reference,
        "id": bundle.verse.canonical_id,
        "prompt": bundle.prompt,
        "source": bundle.source_payload,
        "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
        "zone2_consults_known": bundle.zone2_consults_known,
        "revision_candidates": bundle.revision_candidates,
        "source_warnings": bundle.source_warnings,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", required=True)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--verse", required=True, type=int)
    parser.add_argument("--json", action="store_true", help="Print JSON payload instead of raw prompt")
    parser.add_argument(
        "--allow-integrity-issues",
        action="store_true",
        help="Build the prompt even when the verse has a known source-integrity warning.",
    )
    args = parser.parse_args()

    verse = lxx_swete.load_verse(args.book.upper(), args.chapter, args.verse)
    bundle = build_deuterocanon_prompt(
        verse,
        allow_integrity_issues=args.allow_integrity_issues,
    )
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
