"""build_thomas_saying_prompt.py — assemble one Gospel of Thomas saying
translation prompt.

Mirrors the shape of `tools/build_didache_prompt.py` but the translation
unit is a **saying** (Coptic Scriptorium div1 unit: incipit, sayings 1-114,
or the closing subtitle).

Input: a saying_id string matching a record in
    sources/nag_hammadi/texts/gospel_of_thomas/coptic.jsonl

Output: a PromptBundle with the fully-assembled user prompt plus metadata
needed for audit-trail bookkeeping in the drafter.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
COPTIC_JSONL = REPO_ROOT / "sources/nag_hammadi/texts/gospel_of_thomas/coptic.jsonl"
MANIFEST = REPO_ROOT / "sources/nag_hammadi/texts/gospel_of_thomas/manifest.json"
POXY_DIR = REPO_ROOT / "sources/nag_hammadi/raw/gospel_of_thomas"

POXY_COVERAGE = {
    "poxy654_greek": {"ranges": [(1, 7)], "file": "poxy654_greek.txt", "label": "POxy 654 (Sayings 1–7)"},
    "poxy1_greek": {"ranges": [(26, 33)], "file": "poxy1_greek.txt", "label": "POxy 1 (Sayings 26–33)"},
    "poxy655_greek": {"ranges": [(24, 24), (36, 39)], "file": "poxy655_greek.txt", "label": "POxy 655 (Sayings 24 and 36–39)"},
}

ZONE1_SOURCES = [
    "Coptic Scriptorium — Paul Dilley 2025 (CC-BY 4.0) primary Coptic TEI",
    "Agraphos public-domain overlap-witness page captures for POxy 1 / 654 / 655",
]

ZONE2_CONSULTS = [
    "Layton NHS 20 (1989) — Coptic critical edition (consult only, no text reuse)",
    "Bethge et al. 1996 (Synopsis Quattuor Evangeliorum) — Coptic consult (consult only)",
    "Plisch 2008, DeConick 2007, Meyer 2007 — interpretive consults (consult only)",
    "Mattison/Zinner OGV — English comprehension check only",
]


@dataclass
class PromptBundle:
    saying_id: str
    saying_label: str
    prompt: str
    source_payload: dict[str, Any]
    zone1_sources_at_draft: list[str]
    zone2_consults_known: list[str]
    greek_overlap_ids: list[str]


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _load_sayings() -> list[dict[str, Any]]:
    with COPTIC_JSONL.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _saying_num(saying_id: str) -> int | None:
    if saying_id == "subtitle":
        return None
    try:
        return int(saying_id)
    except ValueError:
        return None


def _greek_overlap_files(saying_num: int | None) -> list[tuple[str, str]]:
    if saying_num is None or saying_num <= 0:
        return []
    hits: list[tuple[str, str]] = []
    for wid, cov in POXY_COVERAGE.items():
        for lo, hi in cov["ranges"]:
            if lo <= saying_num <= hi:
                path = POXY_DIR / cov["file"]
                if path.exists():
                    hits.append(
                        (
                            cov["label"],
                            _extract_overlap_excerpt(
                                path.read_text(encoding="utf-8"), saying_num
                            ),
                        )
                    )
                else:
                    hits.append((cov["label"], "(fragment text not available on disk)"))
                break
    return hits


def _extract_overlap_excerpt(raw_text: str, saying_num: int) -> str:
    """Extract the current saying's overlap block from an Agraphos page capture."""
    text = re.sub(r"\s+", " ", raw_text).strip()
    patterns = (
        [
            rf"(Logion {saying_num}\b.*?)(?=Logion \d+\b|Unidentified POxy 655 Fragments|© 1995-2026 Gospel of Thomas|$)",
        ]
        if "Logion " in text
        else []
    ) + [
        rf"(\({saying_num}\).*?)(?=\(\d+\)|© 1995-2026 Gospel of Thomas|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text[:4000]


def _format_lines(rec: dict[str, Any]) -> str:
    lines = rec.get("lines") or []
    if not lines:
        return "(no line-level data)"
    out = []
    for line in lines:
        out.append(f"- {line['codex_page']} / lb {line['lb']}: {line['orig']}")
        if line.get("norm") and line["norm"] != line["orig"]:
            out.append(f"    normalized: {line['norm']}")
    return "\n".join(out)


def build_thomas_saying_prompt(saying_id: str) -> PromptBundle:
    manifest = _load_manifest()
    sayings = _load_sayings()
    by_id = {r["saying_id"]: r for r in sayings}
    if saying_id not in by_id:
        raise SystemExit(f"Unknown saying_id: {saying_id!r}")
    rec = by_id[saying_id]
    saying_num = _saying_num(saying_id)
    greek_hits = _greek_overlap_files(saying_num)

    source_payload: dict[str, Any] = {
        "edition": "Coptic Scriptorium — Paul Dilley, 2025 (v6.2.0)",
        "license": "CC-BY 4.0",
        "urn": "urn:cts:copticLit:nh.thomas.NHAM02:0-114",
        "language": "Sahidic Coptic with Lycopolitan features",
        "manuscript": "Nag Hammadi Codex II (NHAM 02), pp. 32–51",
        "codex_pages": rec.get("codex_pages", []),
        "coptic_orig": rec["coptic_orig"],
        "coptic_norm": rec["coptic_norm"],
        "lines": rec.get("lines", []),
        "greek_overlap_witnesses": [label for label, _ in greek_hits],
    }

    parts: list[str] = []
    parts.append("## Task")
    parts.append(
        f"Draft a faithful English translation of Gospel of Thomas — "
        f"**{rec['label']}** (segment id `{saying_id}`) from the Coptic below."
    )
    parts.append("")
    parts.append("You must submit your result by calling the `submit_thomas_saying_draft` function exactly once.")
    parts.append("")
    parts.append("## Primary Coptic source — Dilley 2025 (Coptic Scriptorium), CC-BY 4.0")
    parts.append("")
    parts.append(f"- URN: {source_payload['urn']}")
    parts.append(f"- Dialect: {source_payload['language']}")
    parts.append(f"- Manuscript: {source_payload['manuscript']}")
    pages = ", ".join(source_payload["codex_pages"]) or "(n/a)"
    parts.append(f"- Codex pages: {pages}")
    parts.append("")
    parts.append("### Printed form (phrase-joined morphemes)")
    parts.append("```coptic")
    parts.append(rec["coptic_orig"] or "(empty)")
    parts.append("```")
    parts.append("")
    parts.append("### Normalized Sahidic (Dilley's lemmatization)")
    parts.append("```coptic")
    parts.append(rec["coptic_norm"] or "(empty)")
    parts.append("```")
    parts.append("")
    parts.append("### Line-level breakdown with codex-page refs")
    parts.append(_format_lines(rec))
    parts.append("")

    if greek_hits:
        parts.append("## Greek overlap witness capture(s) — Agraphos public-domain page text")
        parts.append("")
        parts.append(
            "These on-disk captures are **page-text summaries of the Greek overlap fragments** "
            "(including lacuna structure / translation-layer cues), not diplomatic Greek-script transcriptions. "
            "Use them honestly as overlap checks; do not pretend they provide more certainty than they do."
        )
        parts.append("")
        for label, text in greek_hits:
            parts.append(f"### {label}")
            parts.append("```text")
            parts.append(text)
            parts.append("```")
            parts.append("")

    parts.append("## Translation stance (Phase E — Thomas)")
    parts.append("")
    parts.append(
        "- Translate from the Coptic. Do NOT paraphrase a modern English edition.\n"
        "- Preserve Thomasine terseness, riddle-structure, and sharp diction. Do not smooth into familiar church cadence.\n"
        "- If a Greek POxy fragment is present and diverges meaningfully from the Coptic, record BOTH readings and defend which you chose.\n"
        "- Treat any Synoptic NT parallels as context only — do not harmonize Thomas toward canonical wording.\n"
        "- If Dilley's edition has a lacuna or conjectural restoration inside this saying, note it in the textual-note field.\n"
        "- The dialect is Sahidic with Lycopolitan features; where the dialect affects meaning, note it rather than flattening it."
    )
    parts.append("")
    parts.append("## Consult-only references (no text reuse; attribute by name if influenced)")
    parts.append("")
    for c in ZONE2_CONSULTS:
        parts.append(f"- {c}")
    parts.append("")
    prompt = "\n".join(parts)
    return PromptBundle(
        saying_id=saying_id,
        saying_label=rec["label"],
        prompt=prompt,
        source_payload=source_payload,
        zone1_sources_at_draft=list(ZONE1_SOURCES),
        zone2_consults_known=list(ZONE2_CONSULTS),
        greek_overlap_ids=[label for label, _ in greek_hits],
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saying", required=True, help="saying id (000=incipit, 001-114, subtitle)")
    args = ap.parse_args()
    bundle = build_thomas_saying_prompt(args.saying)
    print(bundle.prompt)


if __name__ == "__main__":
    main()
