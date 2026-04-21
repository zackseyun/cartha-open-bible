#!/usr/bin/env python3
"""generate_residual_uncertainty.py — write RESIDUAL_UNCERTAINTY.md

Enumerates every medium/low-confidence verse in the current final
adjudicated corpus, using the latest confidence state from
sources/lxx/swete/final_corpus_adjudicated/*.jsonl.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lxx_swete  # noqa: E402

REPO_ROOT = lxx_swete.REPO_ROOT
FINAL_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated"
OUT_PATH = REPO_ROOT / "sources" / "lxx" / "swete" / "RESIDUAL_UNCERTAINTY.md"


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(FINAL_DIR.glob("*.jsonl")):
        book = path.stem
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            conf = obj.get("confidence") or (obj.get("adjudication") or {}).get("confidence") or "high"
            if conf not in {"medium", "low"}:
                continue
            adj = obj.get("adjudication") or {}
            rows.append({
                "book": book,
                "chapter": obj["chapter"],
                "verse": obj["verse"],
                "greek": obj.get("greek", ""),
                "confidence": conf,
                "verdict": adj.get("verdict", ""),
                "reasoning": adj.get("reasoning", "").strip(),
            })
    return rows


def format_md(rows: list[dict]) -> str:
    total_verses = 0
    conf_tot = Counter()
    for path in FINAL_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            total_verses += 1
            obj = json.loads(line)
            conf = obj.get("confidence") or (obj.get("adjudication") or {}).get("confidence") or "high"
            conf_tot[conf] += 1

    by_book: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_book[row["book"]].append(row)

    lines = [
        "# Residual uncertainty — medium/low-confidence verses",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "After the Phase 8 pipeline (raw OCR → AI-vision re-parse → scan-grounded",
        "adjudication → rescue passes), this document enumerates every verse",
        "that did NOT reach high confidence in the current final corpus.",
        "",
        "## Summary",
        "",
        f"- **Total adjudicated verses:** {total_verses}",
        f"- **High confidence:** {conf_tot['high']} ({conf_tot['high']/max(1,total_verses)*100:.1f}%)",
        f"- **Medium confidence:** {conf_tot['medium']} ({conf_tot['medium']/max(1,total_verses)*100:.2f}%)",
        f"- **Low confidence:** {conf_tot['low']} ({conf_tot['low']/max(1,total_verses)*100:.2f}%)",
        "",
        "## What medium/low confidence means",
        "",
        "- **Medium:** the scan-grounded adjudicator could read the Swete page,",
        "  but either a specific letterform, accent, punctuation mark, or",
        "  versification boundary remained genuinely debatable.",
        "- **Low:** the scan-grounded adjudicator could not fully verify the",
        "  reading from the page image itself.",
        "",
        "## Per-book tally",
        "",
        "| Book | Medium | Low |",
        "|---|---:|---:|",
    ]
    for book in sorted(set(path.stem for path in FINAL_DIR.glob("*.jsonl"))):
        book_rows = by_book.get(book, [])
        lines.append(
            f"| {book} | {sum(1 for r in book_rows if r['confidence']=='medium')} "
            f"| {sum(1 for r in book_rows if r['confidence']=='low')} |"
        )

    lines.extend([
        "",
        "## Per-verse detail",
        "",
    ])

    if not rows:
        lines.extend([
            "No medium- or low-confidence verses remain in the current final corpus.",
            "",
        ])
    else:
        for book in sorted(by_book):
            lines.append(f"### {book}")
            lines.append("")
            for row in sorted(by_book[book], key=lambda r: (r["chapter"], r["verse"])):
                conf_label = row["confidence"].upper() if row["confidence"] == "low" else row["confidence"]
                lines.append(
                    f"- **{row['book']} {row['chapter']}:{row['verse']}** — *{conf_label}*, "
                    f"verdict: `{row['verdict']}`"
                )
                if row["reasoning"]:
                    lines.append(f"  > {row['reasoning']}")
                lines.append("")

    lines.extend([
        "## Remediation pathway",
        "",
        "Any remaining residuals are handled through the revision-later workflow",
        f"in [`{REPO_ROOT / 'REVISION_LATER.md'}`] via specialist review,",
        "community correction, or newly available source evidence.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    rows = load_rows()
    OUT_PATH.write_text(format_md(rows), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
