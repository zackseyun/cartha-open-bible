"""Regenerate the Thomas segment index + per-saying prompts from the
CopticScriptorium primary witness.

Replaces the old scaffold (built from Mattison/Zinner English) with a
Coptic-grounded version:

- segment_index/gospel_of_thomas.csv is rewritten to match the 116 div1
  units in the TEI (incipit + 114 sayings + subtitle).
- prompts/gospel_of_thomas/segments/*.md now embed the actual Coptic
  text (orig + normalized Sahidic + per-line breakdown) from coptic.jsonl
  instead of an English summary.

Run after any refresh of coptic.jsonl.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(".")
COPTIC_JSONL = ROOT / "sources/nag_hammadi/texts/gospel_of_thomas/coptic.jsonl"
MANIFEST = ROOT / "sources/nag_hammadi/texts/gospel_of_thomas/manifest.json"
SEG_INDEX = ROOT / "sources/nag_hammadi/segment_index/gospel_of_thomas.csv"
PROMPT_DIR = ROOT / "sources/nag_hammadi/prompts/gospel_of_thomas/segments"
OVERVIEW = ROOT / "sources/nag_hammadi/prompts/gospel_of_thomas/overview.md"
INDEX_MD = PROMPT_DIR / "index.md"

POXY_COVERAGE = {
    "poxy654_greek": {"ranges": [(1, 7)], "label": "Sayings 1–7"},
    "poxy1_greek": {"ranges": [(26, 33)], "label": "Sayings 26–33"},
    "poxy655_greek": {
        "ranges": [(24, 24), (36, 39)],
        "label": "Sayings 24 and 36–39",
    },
}

GUARDRAILS = [
    "If a Greek fragment overlaps a saying and differs meaningfully from the Coptic, record both readings and defend the decision.",
    "Treat Synoptic parallels as context, not as pressure to harmonize Thomas into the canonical gospels.",
    "Keep odd or sharp Thomasine diction when the witness supports it instead of smoothing it into familiar church English.",
    "The Coptic has Lycopolitan features in a mostly Sahidic base — where the dialect interacts with meaning, note it instead of flattening it to standard Sahidic.",
]


def load_sayings() -> list[dict]:
    with COPTIC_JSONL.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_manifest() -> dict:
    with MANIFEST.open() as fh:
        return json.load(fh)


def greek_overlap_for(saying_num: int | None) -> list[str]:
    if saying_num is None:
        return []
    hits = []
    for wid, cov in POXY_COVERAGE.items():
        for lo, hi in cov["ranges"]:
            if lo <= saying_num <= hi:
                hits.append(f"{wid} ({cov['label']})")
                break
    return hits


def segment_label(rec: dict) -> str:
    if rec["saying_id"] == "subtitle":
        return "Subtitle"
    if rec["saying_id"] == "000":
        return "Incipit"
    return rec["label"]


def build_segment_row(rec: dict, idx: int) -> dict:
    sid = rec["saying_id"]
    pages = ",".join(rec.get("codex_pages", []))
    heading = rec["label"]
    # start/end_ref: codex page-line anchors when available
    lines = rec.get("lines") or []
    if lines:
        start_ref = f"{lines[0]['codex_page']}:lb{lines[0]['lb']}"
        end_ref = f"{lines[-1]['codex_page']}:lb{lines[-1]['lb']}"
    else:
        start_ref = pages
        end_ref = pages
    return {
        "segment_id": sid,
        "label": rec["label"],
        "status": "planned",
        "heading": heading,
        "start_ref": start_ref,
        "end_ref": end_ref,
        "chapter_index": sid if sid != "subtitle" else "",
        "block_index": "",
        "notes": "",
    }


def write_segment_index(rows: list[dict]) -> None:
    SEG_INDEX.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "segment_id",
        "label",
        "status",
        "heading",
        "start_ref",
        "end_ref",
        "chapter_index",
        "block_index",
        "notes",
    ]
    with SEG_INDEX.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def fmt_line_block(rec: dict) -> str:
    lines = rec.get("lines") or []
    if not lines:
        return "(no line-level data)"
    out = []
    for line in lines:
        out.append(
            f"- **{line['codex_page']} / lb {line['lb']}** — `{line['orig']}`"
        )
        if line.get("norm") and line["norm"] != line["orig"]:
            out.append(f"  - normalized: `{line['norm']}`")
    return "\n".join(out)


def write_prompt(rec: dict, out_path: Path, manifest: dict) -> None:
    sid = rec["saying_id"]
    saying_num: int | None
    if sid == "subtitle":
        saying_num = None
    elif sid == "000":
        saying_num = 0
    else:
        try:
            saying_num = int(sid)
        except ValueError:
            saying_num = None

    hdr = rec["label"]
    header = f"# Gospel of Thomas — {hdr}"

    primary = "coptic_scriptorium_thomas_dilley_2025"
    prim_w = next(
        w for w in manifest["primary_witnesses"] if w["witness_id"] == primary
    )

    greek_overlaps = greek_overlap_for(saying_num)

    parts = [
        header,
        "",
        f"- Segment id: `{sid}`",
        f"- Segment unit: saying",
        f"- Label: {hdr}",
        f"- Codex pages: {', '.join(rec.get('codex_pages', [])) or '(n/a)'}",
        "",
        "## Primary Coptic witness (Dilley 2025, Coptic Scriptorium)",
        "",
        f"- License: {prim_w['license']}",
        f"- URN: `{prim_w['urn']}`",
        f"- Manuscript: {prim_w['manuscript']}",
        "",
        "### Printed form (morphemes joined)",
        "",
        "```coptic",
        rec["coptic_orig"] or "(no Coptic text)",
        "```",
        "",
        "### Normalized Sahidic",
        "",
        "```coptic",
        rec["coptic_norm"] or "(no normalized text)",
        "```",
        "",
        "### Line-level breakdown",
        "",
        fmt_line_block(rec),
        "",
    ]

    if greek_overlaps:
        parts += [
            "## Greek overlap witnesses",
            "",
        ]
        for line in greek_overlaps:
            parts.append(f"- {line}")
        parts += [
            "",
            "Consult the Greek fragment alongside the Coptic. Where they diverge, record both readings and defend the rendering chosen.",
            "",
        ]

    parts += [
        "## Consult-only references (no text reuse)",
        "",
        "- **Layton NHS 20 (1989)** — for difficult Coptic readings.",
        "- **Bethge et al. 1996** — for Synopsis Quattuor Evangeliorum alignment.",
        "- **Plisch 2008**, **DeConick 2007**, **Meyer 2007** — interpretive consults.",
        "- **Mattison/Zinner OGV** — English-comprehension check only, never a text source.",
        "",
        "## Translation stance",
        "",
        "- Translate from the Coptic, not from any English paraphrase.",
        "- Keep Thomasine diction — sharp, terse, riddling — when the Coptic supports it.",
        "- If the Dilley edition marks a lacuna (`[ ]`) or restoration, preserve the ambiguity in the English note rather than silently smoothing it.",
        "- Where a Greek POxy fragment overlaps, compare and record divergences.",
        "- Treat Synoptic NT parallels as context; do not harmonize.",
        "",
        "## Guardrails",
        "",
    ]
    for g in GUARDRAILS:
        parts.append(f"- {g}")
    parts += [
        "",
        "## Required output",
        "",
        "- translation draft",
        "- textual note (lacuna flags, dialect features, lemma surprises)",
        "- Greek-overlap decision note (if applicable)",
        "- Synoptic-parallel check (if any canonical parallel exists)",
        "- revision risk note",
        "",
    ]

    out_path.write_text("\n".join(parts), encoding="utf-8")


def write_overview(manifest: dict, records: list[dict]) -> None:
    prim = next(
        w for w in manifest["primary_witnesses"] if w["role"] == "primary_coptic"
    )
    body = [
        "# Gospel of Thomas — Phase E overview prompt",
        "",
        "You are preparing an accuracy-first Coptic-grounded English translation of the",
        f"Gospel of Thomas from the **{prim['edition']}** ({prim['license']}).",
        "",
        "## Primary witness",
        "",
        f"- **{prim['witness_id']}** — {prim['edition']}, license {prim['license']}.",
        f"- Source: {prim['manuscript']}. URN: `{prim['urn']}`.",
        f"- Parsed text: `{manifest['primary_coptic_source_jsonl']}`.",
        "",
        "## Scope",
        "",
        f"- {len(records)} segments: incipit + 114 sayings + subtitle (per TEI `div1` units).",
        "",
        "## Consult-only references",
        "",
        "- Layton NHS 20 (1989), Bethge et al. 1996, Plisch 2008, DeConick 2007, Meyer 2007.",
        "- Mattison/Zinner OGV — English comprehension cross-check only.",
        "",
        "## Guardrails",
        "",
    ]
    for g in GUARDRAILS:
        body.append(f"- {g}")
    body.append("")
    body.append("## Required output per saying")
    body.append("")
    body.append("- translation draft")
    body.append("- textual note")
    body.append("- Greek-overlap decision note (if applicable)")
    body.append("- Synoptic-parallel check (if any)")
    body.append("- revision risk note")
    body.append("")
    OVERVIEW.write_text("\n".join(body), encoding="utf-8")


def write_index(records: list[dict]) -> None:
    body = [
        "# Gospel of Thomas — segment prompts",
        "",
        f"Total segments: {len(records)}",
        "",
    ]
    for rec in records:
        body.append(f"- `{rec['saying_id']}` — {rec['label']}")
    body.append("")
    INDEX_MD.write_text("\n".join(body), encoding="utf-8")


def main() -> None:
    manifest = load_manifest()
    records = load_sayings()
    rows = [build_segment_row(r, i) for i, r in enumerate(records)]
    write_segment_index(rows)
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    for rec in records:
        out = PROMPT_DIR / f"{rec['saying_id']}.md"
        write_prompt(rec, out, manifest)
    write_index(records)
    write_overview(manifest, records)
    print(f"wrote {len(records)} segment rows -> {SEG_INDEX}")
    print(f"wrote {len(records)} per-segment prompts -> {PROMPT_DIR}")
    print(f"wrote index -> {INDEX_MD}")
    print(f"wrote overview -> {OVERVIEW}")


if __name__ == "__main__":
    main()
