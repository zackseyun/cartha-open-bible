#!/usr/bin/env python3
"""build_translation_prompt.py — assemble a Jubilees verse translation prompt.

Phase 12 translator prompt for the Book of Jubilees. Parallels the shape of
`tools/build_translation_prompt.py` (LXX deuterocanon verse prompts) and
`tools/build_didache_prompt.py` (per-chapter Greek extra-canonical), adapted
for Jubilees's multi-witness Ethiopic + Latin-fragment situation.

Source layers consulted:

  Zone 1 primary    — Charles 1895 Ge'ez via Gemini 3.1 Pro OCR
                      (`sources/jubilees/ethiopic/transcribed/charles_1895/`).
  Zone 1 secondary  — Dillmann/Rönsch 1874 Latin fragments (chs 13-49)
                      when OCR lands; stubbed until that pipeline runs.
  Zone 1 reference  — Charles 1902 English translation, used only as a
                      *semantic* cross-check guide, never as phrasing.
  Zone 2 consult    — VanderKam DJD XIII (Hebrew fragments), VanderKam
                      1989 CSCO, Segal 2007, Wintermute OTP 1985. Consult
                      registry lives in `tools/jubilees/multi_witness.py`.

Usage:

    python3 tools/jubilees/build_translation_prompt.py --chapter 1 --verse 1
    python3 tools/jubilees/build_translation_prompt.py --chapter 1 --verse 1 --json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
JUBILEES_ROOT = REPO_ROOT / "sources" / "jubilees"
PAGE_MAP_PATH = JUBILEES_ROOT / "page_map.json"
CHARLES_1895_ROOT = JUBILEES_ROOT / "ethiopic" / "transcribed" / "charles_1895"
BODY_DIR = CHARLES_1895_ROOT / "body"
PILOT_CH1_DIR = CHARLES_1895_ROOT / "pilot_ch01_3p1_run1"
LEGACY_PILOT_CH1_DIR = CHARLES_1895_ROOT / "pilot_ch01"

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import verse_parser  # noqa: E402  (sibling module)
from multi_witness import CONSULT_REGISTRY  # noqa: E402


LATIN_FRAGMENT_CHAPTERS = set(range(13, 50))  # Rönsch 1874 coverage


@dataclass
class JubileesPromptBundle:
    chapter: int
    verse: int
    reference: str
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    source_warnings: list[str]
    witness_set: dict[str, Any]


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


def _load_page_map() -> dict[str, Any]:
    if not PAGE_MAP_PATH.exists():
        raise FileNotFoundError(f"page_map.json missing at {PAGE_MAP_PATH}")
    return json.loads(PAGE_MAP_PATH.read_text(encoding="utf-8"))


def _chapter_pages(chapter: int) -> tuple[list[int], list[str]]:
    """Return (pdf_page_list, warnings) for a given chapter.

    Warnings surface when the chapter isn't yet in `page_map.chapters`
    (the `tbd_chapters` state) so the prompt makes the uncertainty visible.
    """
    warnings: list[str] = []
    page_map = _load_page_map()
    charles = page_map["editions"]["charles_1895"]
    chapters = charles.get("chapters", {})
    key = f"{chapter:03d}"
    if key in chapters:
        return chapters[key]["pages"], warnings
    warnings.append(
        f"Chapter {chapter} is not yet in page_map.chapters; OCR witness loading falls back to heuristic PDF offset."
    )
    offset_start = charles.get("ge_ez_body_start_pdf_page", 37)
    approx_printed = offset_start + (chapter - 1) * 4
    return [approx_printed, approx_printed + 1, approx_printed + 2, approx_printed + 3], warnings


def _candidate_source_dirs(chapter: int) -> list[tuple[pathlib.Path, str]]:
    """Return OCR source dirs in preference order.

    During a full-book OCR rerun, `body/` may exist but still be only partially
    populated. For chapter 1 we keep the validated pilot directory as a
    fallback so prompt-building remains stable until the body run is complete.
    """
    out: list[tuple[pathlib.Path, str]] = []
    if BODY_DIR.exists():
        out.append((BODY_DIR, "body"))
    if chapter == 1 and PILOT_CH1_DIR.exists():
        out.append((PILOT_CH1_DIR, "pilot_ch01_3p1_run1"))
    if chapter == 1 and LEGACY_PILOT_CH1_DIR.exists():
        out.append((LEGACY_PILOT_CH1_DIR, "pilot_ch01_legacy"))
    if not out:
        raise FileNotFoundError(
            f"No OCR source directory found for chapter {chapter}. Looked at {BODY_DIR}, {PILOT_CH1_DIR}, and {LEGACY_PILOT_CH1_DIR}."
        )
    return out


def _load_charles_1895_verse_geez(
    chapter: int,
    verse: int,
) -> tuple[dict[str, Any], list[str]]:
    """Load the Ge'ez text for a specific verse from the Charles 1895 OCR layer.

    Returns (payload, warnings). Payload is always populated; warnings list
    captures any quality caveats (page-map gap, parser fallbacks, missing
    verse record).
    """
    pages, warnings = _chapter_pages(chapter)
    page_texts: list[tuple[int, str]] = []
    missing_pages: list[int] = []
    labels_used: list[str] = []
    for p in pages:
        chosen = False
        for candidate_dir, candidate_label in _candidate_source_dirs(chapter):
            path = candidate_dir / f"charles_1895_ethiopic_p{p:04d}.txt"
            if not path.exists():
                continue
            page_texts.append((p, path.read_text(encoding="utf-8")))
            if candidate_label not in labels_used:
                labels_used.append(candidate_label)
            chosen = True
            break
        if not chosen:
            missing_pages.append(p)
    src_label = labels_used[0] if len(labels_used) == 1 else f"mixed:{','.join(labels_used)}"
    if missing_pages:
        warnings.append(
            f"OCR pages missing from {src_label}: {missing_pages}. Continuing with available pages."
        )
    if len(labels_used) > 1:
        warnings.append(
            f"Mixed OCR source directories used for chapter {chapter}: {labels_used}. "
            "This is expected while the full-body OCR rerun is still incomplete."
        )
    if "pilot_ch01_legacy" in labels_used:
        warnings.append(
            "Using legacy `pilot_ch01` fallback pages where newer body/3.1 pages are not yet present."
        )
    if not page_texts:
        raise FileNotFoundError(
            f"No OCR text files for chapter {chapter} (pages={pages}) in any configured source dir."
        )

    rows = verse_parser.parse_chapter_pages(page_texts)
    target = next((r for r in rows if r.verse == verse), None)
    if target is None:
        warnings.append(
            f"Verse parser did not recover Jubilees {chapter}:{verse} from pages {pages}. "
            "Using raw chapter concatenation as a degraded fallback; manual inspection required."
        )
        raw = "\n\n".join(text for _, text in page_texts)
        return (
            {
                "edition": "charles_1895",
                "ocr_source": src_label,
                "language": "Geez",
                "text": "",
                "fallback_chapter_raw": raw,
                "pages": pages,
                "confidence": "low",
                "validation": "verse_not_recovered",
            },
            warnings,
        )

    return (
        {
            "edition": "charles_1895",
            "ocr_source": src_label,
            "language": "Geez",
            "text": target.text,
            "marker_raw": target.marker_raw,
            "pages": pages,
            "source_page": target.source_page,
            "confidence": (
                "high" if src_label == "body"
                else "high_pilot" if src_label == "pilot_ch01_3p1_run1"
                else "mixed_fallback"
            ),
            "validation": "verse_parser_ok",
        },
        warnings,
    )


def _latin_fragment_applies(chapter: int) -> bool:
    return chapter in LATIN_FRAGMENT_CHAPTERS


def _zone2_registry() -> list[dict[str, Any]]:
    return [dict(entry) for entry in CONSULT_REGISTRY]


JUBILEES_GUARDRAILS = """\
- The English output must remain anchored in the Ge'ez primary witness above.
- Jubilees retells Genesis and Exodus. Where a verse restates canonical OT
  material, keep proper names consistent with the WLC Hebrew canonical form
  our OT translation uses (e.g. Moses = Moshe-style rendering is NOT used
  here; keep the traditional English form our OT layer already adopted).
- Jubilees is a *revelation* text: the Angel of the Presence is dictating
  history to Moses on Sinai. Preserve that framing; do not collapse the
  narrator's voice into neutral third-person retelling.
- Preserve Jubilees's distinctive calendrical vocabulary verbatim at the
  conceptual level: "jubilee", "week of years", "seven-year period", "year
  of this jubilee". These are not ordinary time words — they are the book's
  theological architecture. Do NOT paraphrase them into generic numeric
  spans.
- Do NOT harmonize Jubilees back to the Masoretic Text when Jubilees
  deliberately diverges (chronologies, added dialogue, angelic actors). The
  divergences are the text's theological content; preserve them.
- Do NOT reproduce phrasing from Charles 1902, VanderKam, Wintermute, or
  any modern critical English Jubilees translation. Zone 2 works may
  inform judgment at the fact level (manuscript support, lexical meaning,
  commentary consensus), but the English must be freshly produced from the
  Ge'ez witness.
- If the Ge'ez witness is low-confidence (verse_parser failed, OCR noise,
  apparatus-variant ambiguity), surface that uncertainty honestly in
  `footnotes` or `lexical_decisions` rather than over-smoothing.
"""


def build_jubilees_prompt(
    chapter: int,
    verse: int,
) -> JubileesPromptBundle:
    if chapter < 1 or chapter > 50:
        raise ValueError(f"Jubilees has 50 chapters; {chapter} out of range")
    if verse < 0:
        raise ValueError(f"Verse must be >= 0; got {verse}")

    reference = f"Jubilees {chapter}:{verse}" if verse >= 1 else f"Jubilees {chapter} prologue"
    canonical_id = f"JUB.{chapter:03d}.{verse:03d}"

    source_payload, warnings = _load_charles_1895_verse_geez(chapter, verse)

    zone1_sources = [_snapshot_label("Charles 1895 Ethiopic Jubilees (Gemini 3.1 Pro OCR)")]
    parallel_sources: list[dict[str, Any]] = []

    if _latin_fragment_applies(chapter):
        parallel_sources.append(
            {
                "edition": "ronsch_1874_latin_fragments",
                "language": "Latin",
                "text": "",
                "status": "ocr_pending",
                "note": (
                    "Rönsch 1874 preserves Latin lemmata for Jubilees chapters 13-49 embedded in "
                    "a German commentary. Latin OCR for this source is not yet wired; consult "
                    "manually if critical wording is disputed."
                ),
            }
        )
        zone1_sources.append(_snapshot_label("Rönsch 1874 Latin fragments (pending OCR)"))

    parallel_sources.append(
        {
            "edition": "charles_1902_english",
            "language": "English",
            "text": "",
            "role": "semantic_cross_check_only",
            "note": (
                "Charles 1902 is a reference guide for canonical verse boundaries and semantic "
                "intent only. Do NOT reproduce any of its phrasing in the English output."
            ),
        }
    )

    if parallel_sources:
        source_payload["parallel_sources"] = parallel_sources

    zone2_registry = _zone2_registry()
    zone2_known = [entry["name"] for entry in zone2_registry]

    witness_set = {
        "zone1_primary": "charles_1895_ethiopic_gemini_3p1_pro_ocr",
        "zone1_secondary": [
            "ronsch_1874_latin_fragments" if _latin_fragment_applies(chapter) else None,
        ],
        "zone1_reference_crosscheck": "charles_1902_english",
        "zone2_consults": zone2_known,
    }

    prompt = f"""# Verse

Reference: {reference}
ID: {canonical_id}
Source edition: Charles 1895 Ethiopic critical edition of Jubilees
Source pages: {source_payload.get('pages') or '(none recorded)'}
Source confidence: {source_payload.get('confidence') or 'unspecified'}
Source validation: {source_payload.get('validation') or 'unspecified'}

# Zone 1 primary source (Ge'ez)

{json.dumps(source_payload, ensure_ascii=False, indent=2)}

# Zone 2 consult registry (do not reproduce wording)

{json.dumps(zone2_registry, ensure_ascii=False, indent=2)}

# Source integrity notes

{json.dumps(warnings or ['No known integrity warnings for this verse.'], ensure_ascii=False, indent=2)}

# Jubilees-specific derivative-work guardrails

{JUBILEES_GUARDRAILS}

# DOCTRINE.md excerpt

{doctrine_excerpt()}

# PHILOSOPHY.md excerpt

{philosophy_excerpt()}

# Task

Produce the highest-quality draft English translation you can for {reference}.

Requirements:
- Translate from the Ge'ez witness above. The parallel_sources block is
  reference scaffolding, not a second translation input.
- Preserve key lexical decisions (calendrical terms, proper names, angelic
  titles, covenantal terminology) in `lexical_decisions`.
- Record major textual uncertainties in `footnotes` (OCR ambiguity,
  apparatus variants, chapter/verse boundary cases).
- If the Ge'ez text is low-confidence or was not recovered by the verse
  parser (see `source.validation`), say so explicitly in the footnotes and
  do not write as if the wording were indisputable.
- Output format: JSON with keys `english`, `lexical_decisions`, `footnotes`,
  `translation_notes`.
"""

    return JubileesPromptBundle(
        chapter=chapter,
        verse=verse,
        reference=reference,
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=zone1_sources,
        zone2_consults_known=zone2_known,
        source_warnings=warnings,
        witness_set=witness_set,
    )


def _to_jsonable(bundle: JubileesPromptBundle) -> dict[str, Any]:
    return {
        "reference": bundle.reference,
        "id": f"JUB.{bundle.chapter:03d}.{bundle.verse:03d}",
        "prompt": bundle.prompt,
        "source": bundle.source_payload,
        "zone1_sources_at_draft": bundle.zone1_sources_at_draft,
        "zone2_consults_known": bundle.zone2_consults_known,
        "source_warnings": bundle.source_warnings,
        "witness_set": bundle.witness_set,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--verse", required=True, type=int)
    parser.add_argument("--json", action="store_true", help="Print JSON payload instead of raw prompt")
    args = parser.parse_args()

    bundle = build_jubilees_prompt(args.chapter, args.verse)
    if args.json:
        print(json.dumps(_to_jsonable(bundle), ensure_ascii=False, indent=2))
    else:
        print(bundle.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
