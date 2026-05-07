#!/usr/bin/env python3
"""build_review_brief.py — write self-contained review briefs to disk.

Each brief is a single markdown file containing everything a Claude
reviewer needs to evaluate one verse against the v3 author-intent
prompt: target verse YAML, ±5 chapter context (source + English),
book-specific context, and the published-English reference panel
(when available).

Output path:
  /tmp/cob_briefs/<book_slug>/<chap:03d>/<verse:03d>.md

A companion file at the same path with extension `.target.json`
contains the metadata needed by the dispatcher to know where the
review JSON should be written:
  {
    "ref_id": "...",
    "yaml_path": "translation/...",
    "review_output_path": "state/reviews/claude/.../NNN/VVV.json",
    ...
  }

Usage:
    python3 tools/build_review_brief.py --worklist /tmp/uncovered.jsonl
    python3 tools/build_review_brief.py --worklist ... --filter testaments_twelve_patriarchs/asher
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
BOOK_CONTEXT_DIR = PROMPTS_DIR / "book_contexts"
REFS_DIR = REPO_ROOT / "sources" / "references"
PRIVATE_REFS_DIR = REPO_ROOT / "sources" / "references_private"
BRIEFS_ROOT = pathlib.Path("/tmp/cob_briefs")
REVIEWS_OUTPUT_ROOT = REPO_ROOT / "state" / "reviews" / "claude"

CONTEXT_WINDOW = 5
STRATEGY_DEFAULT = "claude_gap_closure_2026_05"
T12P_STRATEGY = "phase10_t12p_claude"


def strategy_for(entry: dict) -> str:
    if entry["book_slug"] == "testaments_twelve_patriarchs":
        return T12P_STRATEGY
    return STRATEGY_DEFAULT


def load_book_context(book_slug: str, sub_book: str | None) -> str:
    """Look up book context. Prefer sub_book (e.g. 'asher') over parent
    collection ('testaments_twelve_patriarchs') if both exist."""
    candidates = []
    if sub_book:
        candidates.append(sub_book)
    candidates.append(book_slug)
    for slug in candidates:
        p = BOOK_CONTEXT_DIR / f"{slug}.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def load_chapter_context(yaml_path: pathlib.Path, target_verse: int) -> str:
    """Return ±CONTEXT_WINDOW siblings, source + English only."""
    chap_dir = yaml_path.parent
    siblings: list[tuple[int, pathlib.Path]] = []
    for p in sorted(chap_dir.glob("*.yaml")):
        try:
            v = int(p.stem)
        except ValueError:
            continue
        siblings.append((v, p))
    target_idx = next((i for i, (v, _) in enumerate(siblings) if v == target_verse), None)
    if target_idx is None:
        return ""
    start = max(0, target_idx - CONTEXT_WINDOW)
    end = min(len(siblings), target_idx + CONTEXT_WINDOW + 1)
    out_lines: list[str] = []
    for i in range(start, end):
        v, p = siblings[i]
        if v == target_verse:
            continue
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        src = (d.get("source") or {}).get("text", "").strip()
        eng = (d.get("translation") or {}).get("text", "").strip()
        ref_id = d.get("id") or f"v{v}"
        tag = "before" if v < target_verse else "after"
        out_lines.append(f"### {ref_id} ({tag})\n- source: {src}\n- english: {eng}")
    return "\n\n".join(out_lines)


def load_reference_panel(book_slug: str, sub_book: str | None,
                         chap: int, verse: int) -> dict[str, str]:
    """Look up per-verse reference renderings. Tries public refs first,
    then private refs (gitignored). Returns {} if none."""
    out: dict[str, str] = {}
    for refs_dir in (REFS_DIR, PRIVATE_REFS_DIR):
        for slug in (sub_book, book_slug):
            if not slug:
                continue
            p = refs_dir / f"{slug}.json"
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            verses = data.get("verses") or {}
            v = verses.get(f"{chap}:{verse}")
            if isinstance(v, dict):
                # Merge — public panel comes first, private panel adds
                out.update(v)
                break
    return out


def build_brief(entry: dict) -> tuple[str, dict]:
    """Return (brief_markdown, target_metadata)."""
    yaml_path = REPO_ROOT / entry["yaml_path"]
    yaml_text = yaml_path.read_text(encoding="utf-8")
    yaml_data = yaml.safe_load(yaml_text) or {}

    book_slug = entry["book_slug"]
    sub_book = entry.get("sub_book")
    chap = int(entry["chapter"])
    verse = int(entry["verse"])
    ref_id = entry["ref_id"]

    book_context = load_book_context(book_slug, sub_book)
    chapter_context = load_chapter_context(yaml_path, verse)
    panel = load_reference_panel(book_slug, sub_book, chap, verse)

    md_lines: list[str] = []
    md_lines.append(f"# Review brief — {ref_id}\n")
    md_lines.append(f"- **YAML path**: `{entry['yaml_path']}`")
    md_lines.append(f"- **Book**: {book_slug}" + (f" / {sub_book}" if sub_book else ""))
    md_lines.append(f"- **Chapter / verse**: {chap}:{verse}\n")

    md_lines.append("## Target verse YAML (review this)\n")
    md_lines.append("```yaml\n" + yaml_text + "\n```\n")

    if chapter_context:
        md_lines.append("## Chapter context (neighboring verses — do NOT review these)\n")
        md_lines.append(chapter_context + "\n")

    if book_context:
        md_lines.append("## Book context\n")
        md_lines.append(book_context.strip() + "\n")

    if panel:
        md_lines.append("## Published English renderings (reference data only — NOT authority)\n")
        md_lines.append(
            "Per the v3 prompt: consensus among published translations does not "
            "make a reading correct. Twenty wrong translations do not outvote the "
            "Greek/Hebrew. Use these only to notice where the draft stands relative "
            "to existing English; arguments must come from the source.\n"
        )
        for panel_name, text in sorted(panel.items()):
            md_lines.append(f"- **{panel_name.upper()}**: {text}")
        md_lines.append("")

    brief_md = "\n".join(md_lines)

    strategy = strategy_for(entry)
    review_output_path = (
        REVIEWS_OUTPUT_ROOT / strategy / entry["testament"] / entry["review_book_slug"]
        / f"{chap:03d}" / f"{verse:03d}.json"
    )
    target_meta = {
        "ref_id": ref_id,
        "testament": entry["testament"],
        "book_slug": book_slug,
        "sub_book": sub_book,
        "review_book_slug": entry["review_book_slug"],
        "chapter": chap,
        "verse": verse,
        "strategy": strategy,
        "yaml_path": entry["yaml_path"],
        "review_output_path": str(review_output_path.relative_to(REPO_ROOT)),
        "has_book_context": bool(book_context),
        "has_reference_panel": bool(panel),
        "reference_panel_keys": sorted(panel.keys()) if panel else [],
    }
    return brief_md, target_meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worklist", default="/tmp/uncovered.jsonl")
    ap.add_argument("--filter", default=None,
                    help="Only emit briefs matching this slug (book or sub_book)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap number of briefs emitted")
    args = ap.parse_args()

    BRIEFS_ROOT.mkdir(parents=True, exist_ok=True)

    n = 0
    skipped = 0
    with open(args.worklist) as f:
        for line in f:
            entry = json.loads(line)
            if args.filter and (entry["book_slug"] != args.filter
                                and entry.get("sub_book") != args.filter):
                continue

            brief_md, target_meta = build_brief(entry)
            slug = entry.get("sub_book") or entry["book_slug"]
            chap = int(entry["chapter"])
            verse = int(entry["verse"])
            brief_dir = BRIEFS_ROOT / slug / f"{chap:03d}"
            brief_dir.mkdir(parents=True, exist_ok=True)
            brief_path = brief_dir / f"{verse:03d}.md"
            target_path = brief_dir / f"{verse:03d}.target.json"
            brief_path.write_text(brief_md, encoding="utf-8")
            target_path.write_text(
                json.dumps(target_meta, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            n += 1
            if args.limit and n >= args.limit:
                break

    print(f"Wrote {n} briefs under {BRIEFS_ROOT}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
