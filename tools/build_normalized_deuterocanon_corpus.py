#!/usr/bin/env python3
"""build_normalized_deuterocanon_corpus.py

Create translation-ready overrides for deuterocanonical books whose raw
scan-adjudicated verse stream still contains known numbering contamination
or still needs canonical partitioning into reader-facing units.

The raw source of truth remains:
  sources/lxx/swete/final_corpus_adjudicated/

This script writes only the cleaned override files needed by the
translation layer under:
  sources/lxx/swete/final_corpus_normalized/

Current outputs:
- WIS: canonical Wisdom only (drop duplicate chapter 20 and Sirach spill)
- BAR: canonical Baruch only (trim back to 1:1-5:9)
- PAZ: Prayer of Azariah + Song of the Three (standalone extraction)
- SUS: Susanna (standalone extraction)
- BEL: Bel and the Dragon (standalone extraction)

Intentionally NOT output yet:
- ESG (Additions to Esther) — still needs a fuller additions-only
  partition, especially the middle of Addition E.
"""
from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated"
OUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_normalized"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"

import lxx_swete  # noqa: E402

VERSE_RE = re.compile(r"(?<!\d)(\d+)(?:[a-zαβ])?\s+")


def load_book(book: str) -> list[dict]:
    path = SRC_DIR / f"{book}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_book(book: str, records: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{book}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def chapter_counts(records: list[dict]) -> dict[int, int]:
    counts: Counter[int] = Counter()
    for rec in records:
        counts[int(rec["chapter"])] += 1
    return dict(sorted(counts.items()))


def body_text(vol: int, page: int) -> str:
    raw = (TRANSCRIBED_DIR / f"vol{vol}_p{page:04d}.txt").read_text(encoding="utf-8")
    return lxx_swete.extract_body(raw)


def normalize_greek_text(text: str) -> str:
    text = text.replace("¶", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"([Α-Ωα-ωἀ-ῼ])[-‐]\s+([Α-Ωα-ωἀ-ῼ])", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mark_record(
    rec: dict,
    *,
    book: str | None = None,
    chapter: int | None = None,
    verse: int | None = None,
    rule: str,
    note: str,
    source_note: str | None = None,
) -> dict:
    out = dict(rec)
    if book is not None:
        out["book"] = book
    if chapter is not None:
        out["chapter"] = chapter
    if verse is not None:
        out["verse"] = verse
    out["normalization"] = {
        "rule": rule,
        "note": note,
    }
    if source_note:
        out["source_note"] = source_note
    return out


def make_direct_record(
    *,
    book: str,
    chapter: int,
    verse: int,
    greek: str,
    source_pages: list[int],
    rule: str,
    note: str,
    confidence: str = "high",
) -> dict:
    return {
        "book": book,
        "chapter": chapter,
        "verse": verse,
        "greek": normalize_greek_text(greek),
        "ocr_method": "ai_vision",
        "source_pages": source_pages,
        "validation": "normalized_direct_extract",
        "adjudication": {
            "verdict": "normalized_direct_extract",
            "reasoning": note,
            "confidence": confidence,
            "prompt_version": "normalized_partition_2026-04-21",
        },
        "source_note": note,
        "normalization": {
            "rule": rule,
            "note": note,
        },
    }


def normalize_wis(records: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    dropped: list[str] = []
    for rec in records:
        ch = int(rec["chapter"])
        vs = int(rec["verse"])
        ref = f"WIS {ch}:{vs}"
        if ch == 20:
            dropped.append(f"{ref} — duplicate of canonical Wisdom 19 from the raw parser stream")
            continue
        if ch == 19 and vs >= 23:
            dropped.append(f"{ref} — adjacent Sirach contamination beyond canonical Wisdom 19:22")
            continue
        kept.append(
            mark_record(
                rec,
                rule="wisdom_trim_to_canonical_19",
                note="Translation-ready override derived from final_corpus_adjudicated; dropped duplicate chapter 20 and spillover beyond Wisdom 19:22.",
            )
        )
    return kept, dropped


def normalize_bar(records: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    dropped: list[str] = []
    for rec in records:
        ch = int(rec["chapter"])
        vs = int(rec["verse"])
        ref = f"BAR {ch}:{vs}"
        keep = False
        if ch == 1 and vs <= 22:
            keep = True
        elif ch == 2 and vs <= 35:
            keep = True
        elif ch == 3 and vs <= 38:
            keep = True
        elif ch == 4 and vs <= 37:
            keep = True
        elif ch == 5 and vs <= 9:
            keep = True

        if not keep:
            reason = "removed by canonical Baruch chapter/verse boundaries"
            if ch == 1 and vs >= 23:
                reason = "raw chapter-1 tail is actually Baruch 3:23-38"
            elif ch == 5 and vs >= 10:
                reason = "raw chapter-5 tail spills into Lamentations material"
            dropped.append(f"{ref} — {reason}")
            continue

        kept.append(
            mark_record(
                rec,
                rule="baruch_trim_to_canonical_5",
                note="Translation-ready override derived from final_corpus_adjudicated; kept canonical Baruch 1:1-5:9 only, with Letter of Jeremiah handled separately as LJE.",
            )
        )
    return kept, dropped


def normalize_paz(records: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    dropped: list[str] = []
    note = (
        "Standalone PAZ extraction from the curated ADA stream, using Daniel 3:24-90 as the source span and renumbering it to PAZ 1:1-67."
    )
    for rec in records:
        if int(rec["chapter"]) == 3 and 24 <= int(rec["verse"]) <= 90:
            kept.append(
                mark_record(
                    rec,
                    book="PAZ",
                    chapter=1,
                    verse=int(rec["verse"]) - 23,
                    rule="paz_extract_from_ada_ch3",
                    note=note,
                    source_note=note,
                )
            )
        else:
            dropped.append(f"ADA {rec['chapter']}:{rec['verse']} — outside PAZ extraction window")
    return kept, dropped


def sus_tail_records() -> list[dict]:
    out: list[dict] = []
    note = (
        "Standalone Susanna extraction currently follows the complete Theodotion stream in Swete, because that stream is the cleanest fully numbered extract available in the current corpus."
    )

    body606 = normalize_greek_text(body_text(3, 606))
    body606 = body606[body606.find("51 καὶ εἶπεν") :]
    positions = {int(m.group(1)): m.start() for m in VERSE_RE.finditer(body606) if 51 <= int(m.group(1)) <= 59}
    order = sorted(positions)
    for i, verse in enumerate(order):
        end = positions[order[i + 1]] if i + 1 < len(order) else body606.find("Καὶ ἀνεβόησεν πᾶσα ἡ συναγωγὴ")
        text = body606[positions[verse] : end]
        text = text[text.find(str(verse)) + len(str(verse)) :]
        out.append(
            make_direct_record(
                book="SUS",
                chapter=1,
                verse=verse,
                greek=text,
                source_pages=[606],
                rule="sus_partition_theodotion_tail",
                note=note,
            )
        )
    tail_start = body606.find("Καὶ ἀνεβόησεν πᾶσα ἡ συναγωγὴ")
    tail = body606[tail_start:]
    out.append(
        make_direct_record(
            book="SUS",
            chapter=1,
            verse=60,
            greek=tail,
            source_pages=[606],
            rule="sus_partition_theodotion_tail",
            note=note,
            confidence="medium",
        )
    )

    body608 = normalize_greek_text(body_text(3, 608))
    body608 = body608[body608.find("61 ") :]
    positions = {int(m.group(1)): m.start() for m in VERSE_RE.finditer(body608) if 61 <= int(m.group(1)) <= 64}
    order = sorted(positions)
    for i, verse in enumerate(order):
        end = positions[order[i + 1]] if i + 1 < len(order) else len(body608)
        text = body608[positions[verse] : end]
        text = text[text.find(str(verse)) + len(str(verse)) :]
        out.append(
            make_direct_record(
                book="SUS",
                chapter=1,
                verse=verse,
                greek=text,
                source_pages=[608],
                rule="sus_partition_theodotion_tail",
                note=note,
            )
        )
    return out


def normalize_sus(records: list[dict]) -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    dropped: list[str] = []
    note = (
        "Standalone Susanna extraction currently follows the complete Theodotion stream in Swete, because that stream is the cleanest fully numbered extract available in the current corpus."
    )
    for rec in records:
        ch = int(rec["chapter"])
        vs = int(rec["verse"])
        if ch == 1 and 1 <= vs <= 50:
            kept.append(
                mark_record(
                    rec,
                    book="SUS",
                    chapter=1,
                    verse=vs,
                    rule="sus_partition_theodotion",
                    note=note,
                    source_note=note,
                )
            )
        else:
            dropped.append(f"ADA {ch}:{vs} — outside Susanna 1:1-50 carry-over window")
    kept.extend(sus_tail_records())
    kept.sort(key=lambda r: (int(r["chapter"]), int(r["verse"])))
    return kept, dropped


def _parse_bel_page(page: int, start_verse: int, end_verse: int) -> list[dict]:
    body = normalize_greek_text(body_text(3, page))
    note = (
        "Standalone Bel extraction currently follows the complete Theodotion stream in Swete, because that stream is the cleanest fully numbered extract available in the current corpus."
    )
    if page == 610:
        body = body.replace("I. ", "", 1)
    if page == 616 and "37 καὶ ἐβόησεν" in body:
        body = body[body.find("37 καὶ ἐβόησεν") :]
    positions: dict[int, int] = {}
    for m in VERSE_RE.finditer(body):
        num = int(m.group(1))
        if start_verse <= num <= end_verse and num not in positions:
            positions[num] = m.start()
    order = sorted(positions)
    out: list[dict] = []

    if order and start_verse not in positions:
        first_end = positions[order[0]]
        first_text = body[:first_end]
        out.append(
            make_direct_record(
                book="BEL",
                chapter=1,
                verse=start_verse,
                greek=first_text,
                source_pages=[page],
                rule="bel_partition_theodotion",
                note=note,
            )
        )

    for i, verse in enumerate(order):
        end = positions[order[i + 1]] if i + 1 < len(order) else len(body)
        text = body[positions[verse] : end]
        text = text[text.find(str(verse)) + len(str(verse)) :]
        text = re.sub(rf"(?<!\d){verse}\s+", "", text)
        out.append(
            make_direct_record(
                book="BEL",
                chapter=1,
                verse=verse,
                greek=text,
                source_pages=[page],
                rule="bel_partition_theodotion",
                note=note,
            )
        )
    return out


def normalize_bel() -> tuple[list[dict], list[str]]:
    kept: list[dict] = []
    for page, start, end in [(610, 1, 10), (612, 11, 23), (614, 24, 36), (616, 37, 42)]:
        kept.extend(_parse_bel_page(page, start, end))
    kept.sort(key=lambda r: (int(r["chapter"]), int(r["verse"])))
    return kept, []


def summarize_job(summary_lines: list[str], *, book: str, raw_count: int | None, normalized: list[dict], dropped: list[str], note: str | None = None) -> None:
    summary_lines.append(f"## {book}")
    summary_lines.append("")
    if raw_count is not None:
        summary_lines.append(f"- Raw verses: **{raw_count}**")
    summary_lines.append(f"- Normalized verses: **{len(normalized)}**")
    summary_lines.append(f"- Dropped contaminated / duplicate refs: **{len(dropped)}**")
    summary_lines.append(f"- Chapter counts after normalization: `{chapter_counts(normalized)}`")
    if note:
        summary_lines.append(f"- Note: {note}")
    summary_lines.append("")
    for line in dropped[:120]:
        summary_lines.append(f"  - {line}")
    if len(dropped) > 120:
        summary_lines.append(f"  - … {len(dropped) - 120} more omitted from this summary")
    summary_lines.append("")


def main() -> int:
    summary_lines = [
        "# Normalized deuterocanonical corpus overrides",
        "",
        "These files are translation-ready overrides derived from `final_corpus_adjudicated/`.",
        "The raw adjudicated corpus remains untouched for audit. The translation layer prefers these overrides when present.",
        "",
    ]

    jobs = {
        "WIS": lambda: normalize_wis(load_book("WIS")),
        "BAR": lambda: normalize_bar(load_book("BAR")),
        "PAZ": lambda: normalize_paz(load_book("ADA")),
        "SUS": lambda: normalize_sus(load_book("ADA")),
        "BEL": normalize_bel,
    }
    raw_counts = {
        "WIS": len(load_book("WIS")),
        "BAR": len(load_book("BAR")),
        "PAZ": len(load_book("ADA")),
        "SUS": len(load_book("ADA")),
        "BEL": None,
    }
    notes = {
        "PAZ": "Standalone extraction from Daniel 3:24-90.",
        "SUS": "Standalone extraction currently follows the Theodotion stream because it is the cleanest complete extract in the current corpus.",
        "BEL": "Standalone extraction currently follows the Theodotion stream because it is the cleanest complete extract in the current corpus.",
    }

    for book, fn in jobs.items():
        normalized, dropped = fn()
        write_book(book, normalized)
        summarize_job(
            summary_lines,
            book=book,
            raw_count=raw_counts[book],
            normalized=normalized,
            dropped=dropped,
            note=notes.get(book),
        )

    summary_lines.extend(
        [
            "## Still not emitted",
            "",
            "- ESG (Additions to Esther) is intentionally still blocked. The outer boundaries are now understood, but Addition E 1-16 still needs a fuller additions-only verse segmentation pass before we should draft from it safely.",
            "",
        ]
    )

    (OUT_DIR / "SUMMARY.md").write_text("\n".join(summary_lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote normalized overrides to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
