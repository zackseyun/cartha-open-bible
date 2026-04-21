#!/usr/bin/env python3
"""build_esther_additions_corpus.py

Emit a standalone ESG (Additions to Esther) normalized corpus from the
Swete page transcriptions using First1KGreek only as a verse-boundary
anchor map. The emitted Greek text itself comes from our Swete page
transcriptions / adjudicated stream, not from First1KGreek.
"""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata
from typing import Callable

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_normalized"

import first1kgreek  # noqa: E402
import lxx_swete  # noqa: E402

WORD_RE = re.compile(r"[A-Za-zΑ-Ωα-ωἀ-ῼΆ-ώΐΰς]+")


def normalize_text(text: str) -> str:
    text = lxx_swete.extract_body(text) if "[BODY]" in text else text
    text = text.replace("¶", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"([Α-Ωα-ωἀ-ῼ])[-‐]\s+([Α-Ωα-ωἀ-ῼ])", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_segment_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"\b[IVXLCDM]+\s+(?=\d+[a-zαβ]?\b)", " ", text)
    text = re.sub(r"\b[A-F]\s+(?=\d+[a-zαβ]?\b)", " ", text)
    text = re.sub(r"(?<!\d)\b\d+[a-zαβ]?\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_token(token: str) -> str:
    s = unicodedata.normalize("NFD", token)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("ς", "σ")
    return re.sub(r"[^a-zα-ω]", "", s)


def tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    return [(normalize_token(m.group(0)), m.start(), m.end()) for m in WORD_RE.finditer(text)]


def accentless_with_map(text: str) -> tuple[str, list[int]]:
    out: list[str] = []
    mapping: list[int] = []
    for i, ch in enumerate(text):
        decomp = unicodedata.normalize("NFD", ch)
        for d in decomp:
            if unicodedata.combining(d):
                continue
            d = d.lower().replace("ς", "σ")
            out.append(d)
            mapping.append(i)
    return "".join(out), mapping


def find_phrase_pos(raw: str, phrase: str, cursor: int = 0) -> int:
    norm_sub, mapping = accentless_with_map(raw[cursor:])
    norm_phrase, _ = accentless_with_map(phrase)
    found = norm_sub.find(norm_phrase)
    return -1 if found == -1 else cursor + mapping[found]


def load_pages(vol: int, pages: list[int]) -> str:
    parts: list[str] = []
    for page in pages:
        raw = (REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed" / f"vol{vol}_p{page:04d}.txt").read_text(encoding="utf-8")
        parts.append(normalize_text(raw))
    return " ".join(parts)


def bounded_text(raw: str, start_hint: str, stop_hint: str | None) -> str:
    start = find_phrase_pos(raw, start_hint, 0)
    if start == -1:
        raise ValueError(f"start hint not found: {start_hint!r}")
    out = raw[start:]
    if stop_hint:
        stop = find_phrase_pos(out, stop_hint, 0)
        if stop != -1:
            out = out[:stop]
    return out.strip()


def first1k_section(chapter: str, selector: Callable[[str], bool]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    next_num = 1
    for verse in first1kgreek.iter_verses("ADE"):
        if verse.chapter != chapter:
            continue
        if selector(verse.verse):
            out.append((next_num, verse.greek_text))
            next_num += 1
    return out


def find_anchor(tokens: list[tuple[str, int, int]], anchor_tokens: list[str], start_idx: int) -> int:
    max_len = min(8, len(anchor_tokens))
    for prefix_len in range(max_len, 2, -1):
        target = anchor_tokens[:prefix_len]
        for i in range(start_idx, len(tokens) - prefix_len + 1):
            window = [t[0] for t in tokens[i : i + prefix_len]]
            mismatches = sum(1 for a, b in zip(window, target) if a != b)
            if mismatches == 0 or (prefix_len >= 4 and mismatches <= 1):
                return i
    if start_idx == 0:
        return 0
    raise ValueError(f"Could not anchor verse starting with: {' '.join(anchor_tokens[:6])}")


def segment_section(raw: str, verses: list[tuple[int, str]]) -> list[tuple[int, str]]:
    tokens = tokenize_with_spans(raw)
    starts: list[tuple[int, int]] = []
    cursor = 0
    for number, verse_text in verses:
        anchor_tokens = [normalize_token(m.group(0)) for m in WORD_RE.finditer(normalize_text(verse_text))]
        if not anchor_tokens:
            raise ValueError(f"empty anchor text for verse {number}")
        idx = find_anchor(tokens, anchor_tokens, cursor)
        starts.append((number, tokens[idx][1]))
        cursor = idx + 1
    out: list[tuple[int, str]] = []
    for i, (number, start_char) in enumerate(starts):
        end_char = starts[i + 1][1] if i + 1 < len(starts) else len(raw)
        out.append((number, raw[start_char:end_char].strip()))
    return out


def record(book: str, chapter: int, verse: int, greek: str, pages: list[int], note: str) -> dict:
    return {
        "book": book,
        "chapter": chapter,
        "verse": verse,
        "greek": clean_segment_text(greek),
        "ocr_method": "ai_vision",
        "source_pages": pages,
        "validation": "normalized_partition_extract",
        "adjudication": {
            "verdict": "normalized_partition_extract",
            "reasoning": note,
            "confidence": "high",
            "prompt_version": "esg_partition_2026-04-21",
        },
        "source_note": note,
        "normalization": {
            "rule": "esg_partition_af",
            "note": note,
        },
    }


def build_from_raw_ade(raw_chapter: int, verse_start: int, verse_end: int, *, out_chapter: int, note: str) -> list[dict]:
    source = [
        json.loads(line)
        for line in (REPO_ROOT / "sources" / "lxx" / "swete" / "final_corpus_adjudicated" / "ADE.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out: list[dict] = []
    next_verse = 1
    for rec in source:
        if int(rec["chapter"]) == raw_chapter and verse_start <= int(rec["verse"]) <= verse_end:
            out.append(
                {
                    **rec,
                    "book": "ESG",
                    "chapter": out_chapter,
                    "verse": next_verse,
                    "source_note": note,
                    "normalization": {"rule": "esg_partition_af", "note": note},
                }
            )
            next_verse += 1
    return out


def build_section(ch_num: int, pages: list[int], chapter: str, selector: Callable[[str], bool], start_hint: str, stop_hint: str | None, note: str) -> list[dict]:
    raw = load_pages(2, pages)
    raw = bounded_text(raw, start_hint, stop_hint)
    section = first1k_section(chapter, selector)
    segmented = segment_section(raw, section)
    return [record("ESG", ch_num, n, txt, pages, note) for n, txt in segmented]


def build_manual_section(ch_num: int, pages: list[int], anchors: list[tuple[int, str]], start_hint: str, stop_hint: str | None, note: str) -> list[dict]:
    raw = load_pages(2, pages)
    raw = bounded_text(raw, start_hint, stop_hint)
    starts: list[tuple[int, int]] = []
    cursor = 0
    for verse, phrase in anchors:
        idx = find_phrase_pos(raw, phrase, cursor)
        if idx == -1:
            raise ValueError(f"Could not find manual ESG anchor {verse}: {phrase!r}")
        starts.append((verse, idx))
        cursor = idx + 1
    out: list[dict] = []
    for i, (verse, idx) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(raw)
        out.append(record("ESG", ch_num, verse, raw[idx:end].strip(), pages, note))
    return out


def main() -> int:
    note_a = "Standalone ESG chapter 1 = Addition A, segmented from Swete pages 772-773 with First1KGreek used only as a verse-anchor map."
    note_b = "Standalone ESG chapter 2 = Addition B, renumbered from the curated ADE stream where this royal-letter section is already isolated cleanly."
    note_c = "Standalone ESG chapter 3 = Addition C, segmented from Swete pages 781-784 with First1KGreek used only as a verse-anchor map."
    note_d = "Standalone ESG chapter 4 = Addition D, segmented from Swete pages 784-785 with manual phrase anchors derived from the Swete transcription."
    note_e = "Standalone ESG chapter 5 = Addition E, segmented from Swete pages 790-792 with First1KGreek used only as a verse-anchor map."
    note_f = "Standalone ESG chapter 6 = Addition F, segmented from Swete pages 796-797 with First1KGreek used only as a verse-anchor map."

    records: list[dict] = []
    records += build_section(1, [772, 773], "prologue", lambda v: True, "ΕΤΟΥΣ δευτέρου", "Καὶ ἐγένετο μετὰ τοὺς λόγους τούτους", note_a)
    records += build_from_raw_ade(3, 14, 20, out_chapter=2, note=note_b)
    records += build_section(3, [782, 783, 784], "4", lambda v: v.endswith("a"), "ἐποίησεν ὅσα ἐνετείλατο", "Καὶ ἐγενήθη ἐν τῇ ἡμέρᾳ τῇ τρίτῃ", note_c)
    records += build_manual_section(
        4,
        [784, 785],
        [
            (1, "Καὶ ἐγενήθη ἐν τῇ ἡμέρᾳ τῇ τρίτῃ"),
            (2, "καὶ γενηθεῖσα ἐπιφανής"),
            (3, "καὶ τῇ μὲν μιᾷ"),
            (4, "ἑτέρα ἐπηκολούθει"),
            (5, "ἐρυθριῶσα ἀκμῇ"),
            (6, "καὶ εἰσελθοῦσα"),
            (7, "δύκει, ὅλος διὰ χρυσοῦ"),
            (8, "καὶ μετέβαλεν ὁ θεὸς"),
            (9, "καὶ εἶπεν αὐτῇ Τί ἐστιν"),
            (10, "οὐ μὴ ἀποθάνῃς"),
            (11, "πρόσελθε"),
            (12, "καὶ ἄρας τὴν χρυσῆν ῥάβδον"),
            (13, "καὶ εἶπεν αὐτῷ Εἶδόν σε"),
            (14, "ὅτι θαυμαστὸς εἶ"),
            (15, "ἐν δὲ τῷ διαλέγεσθαι"),
            (16, "καὶ ὁ βασιλεὺς ἐταράσσετο"),
        ],
        "Καὶ ἐγενήθη ἐν τῇ ἡμέρᾳ τῇ τρίτῃ",
        "καὶ εἶπεν ὁ βασιλεὺς Τί θέλεις",
        note_d,
    )
    records += build_section(5, [790, 791, 792], "8", lambda v: v.endswith("a"), "ΩΣ ἐστιν", "τὰ δὲ ἀντίγραφα ἐκτιθέσθωσαν", note_e)
    records += build_manual_section(
        6,
        [796, 797],
        [
            (1, "Καὶ εἶπεν Μαρδοχαι"),
            (2, "ἐμνήσθην γὰρ"),
            (3, "ἡ μικρὰ πηγ"),
            (4, "οἱ δὲ δύο δράκοντε"),
            (5, "τὰ δὲ ἔθνη"),
            (6, "τὸ δὲ ἔθνος τὸ ἐμόν"),
            (7, "διὰ τοῦτο ἐποίησεν κλήρους δύο"),
            (8, "καὶ ᾖλθον οἱ δύο κλῆροι"),
            (9, "καὶ ἐμνήσθη ὁ θεὸς"),
            (10, "καὶ ἔσονται αὐτοῖς"),
            (11, "Ἔτους τετάρτου"),
        ],
        "Καὶ εἶπεν Μαρδοχαι",
        None,
        note_f,
    )

    records.sort(key=lambda r: (r["chapter"], r["verse"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "ESG.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {out}")
    print({ch: sum(1 for r in records if r['chapter']==ch) for ch in range(1,7)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
