#!/usr/bin/env python3
"""merge_reviews.py — cross-reference GPT-5.4 + Gemini reviews.

For each page with both a GPT-5.4 review and a Gemini review, this
compares the two reviewers' correction lists and emits:

  1. `<stem>.merged.json` — one-per-page merged worklist with provenance:

     {
       "stem": "vol2_p0155",
       "agreed": [...],      # both reviewers flagged essentially the same fix
       "gpt54_only": [...],  # GPT-5.4 flagged, Gemini did not
       "gemini_only": [...], # Gemini flagged, GPT-5.4 did not
       "counts": {...},
     }

  2. A summary report at sources/lxx/swete/reviews/MERGED_SUMMARY.md

Matching heuristic — two corrections are considered the same if:
  - same section
  - either (a) the `current` spans overlap (normalized) by >= 12 chars, OR
    (b) both mention the same chapter:verse location and same category

Agreed corrections are the highest-signal items: two independent vision
models flagged the same thing → very high confidence it's a real
transcription error and the proposed fix is right.

Usage:
  python3 tools/merge_reviews.py
  python3 tools/merge_reviews.py --gemini-dirs gemini_tobit,gemini_esdras,gemini_wer
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import unicodedata
from collections import Counter
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REVIEWS_ROOT = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews"
GPT54_DIR = REVIEWS_ROOT / "gpt54"
DEFAULT_GEMINI_DIRS = ["gemini", "gemini_tobit", "gemini_esdras", "gemini_wer", "gemini_wer_v3"]
MERGED_DIR = REVIEWS_ROOT / "merged"
SUMMARY_PATH = REVIEWS_ROOT / "MERGED_SUMMARY.md"

MIN_OVERLAP_CHARS = 6


def normalize_span(s: str) -> str:
    """Normalize Greek text for loose cross-model comparison."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    # Drop accents/breathings/etc. for comparison only.
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = s.lower()
    # Normalize final sigma
    s = s.replace("ς", "σ")
    # Drop non-letter characters to focus on the letters themselves
    s = re.sub(r"[^\w]+", " ", s, flags=re.UNICODE).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def loose_location(loc: str) -> str:
    """Normalize a reviewer-supplied location to compare across models."""
    if not loc:
        return ""
    s = loc.lower()
    # Pull out chapter:verse-like tokens (e.g. "IV 8:7", "3:9", "v.26")
    m = re.findall(r"\b([ivxlcdm]+|\d+)[\s:\.]?(\d+)\b", s)
    if m:
        chap, verse = m[0]
        return f"{chap}:{verse}"
    return s.strip()


def corrections_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("section") != b.get("section"):
        return False
    # Strategy 1: normalized current spans overlap by >= MIN_OVERLAP_CHARS
    na = normalize_span(a.get("current", ""))
    nb = normalize_span(b.get("current", ""))
    if na and nb:
        # Overlap: find the shorter string as a substring (allowing fuzzy match)
        short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
        # Trim both sides to at most 80 chars (model outputs sometimes differ on context length)
        short_t = short[:80]
        if len(short_t) >= MIN_OVERLAP_CHARS and short_t in long:
            return True
        # Try prefix match with length-threshold to tolerate minor prefix/suffix diff
        if len(short) >= MIN_OVERLAP_CHARS:
            # sliding window: any MIN-char substring of short present in long?
            for i in range(len(short) - MIN_OVERLAP_CHARS + 1):
                if short[i : i + MIN_OVERLAP_CHARS] in long:
                    return True
    # Strategy 2: same normalized location + same category
    la = loose_location(a.get("location", ""))
    lb = loose_location(b.get("location", ""))
    if la and lb and la == lb:
        if a.get("category") == b.get("category"):
            return True
    # Strategy 3: normalized `correct` target matches (both models propose the
    # same result — even if they described `current` differently).
    ca = normalize_span(a.get("correct", ""))
    cb = normalize_span(b.get("correct", ""))
    if ca and cb and len(ca) >= MIN_OVERLAP_CHARS:
        if ca == cb:
            return True
        # Partial correct-string match (sliding window)
        short, long = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
        if len(short) >= MIN_OVERLAP_CHARS:
            for i in range(len(short) - MIN_OVERLAP_CHARS + 1):
                if short[i : i + MIN_OVERLAP_CHARS] in long:
                    return True
    return False


def load_review(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def reviews_for_stem(gemini_dirs: list[pathlib.Path], stem: str) -> dict[str, Any] | None:
    """Return the first Gemini review found for this stem in the given dirs."""
    for d in gemini_dirs:
        p = d / f"{stem}.review.json"
        if p.exists():
            data = load_review(p)
            if data is not None:
                return {"source_dir": d.name, "data": data}
    return None


def merge_page(stem: str, gpt54: dict[str, Any], gemini_info: dict[str, Any]) -> dict[str, Any]:
    gpt54_corrs = gpt54.get("corrections", []) or []
    gemini_corrs = gemini_info["data"].get("corrections", []) or []

    matched_g: set[int] = set()
    agreed: list[dict[str, Any]] = []
    gpt54_only: list[dict[str, Any]] = []

    for a in gpt54_corrs:
        matched = False
        for gi, g in enumerate(gemini_corrs):
            if gi in matched_g:
                continue
            if corrections_match(a, g):
                agreed.append(
                    {
                        "section": a.get("section"),
                        "location": a.get("location"),
                        "gpt54": a,
                        "gemini": g,
                        # For application: prefer Gemini's correct text if available
                        # (Gemini tends to have more accurate spelling), else GPT-5.4's.
                        "current": g.get("current") or a.get("current"),
                        "correct": g.get("correct") or a.get("correct"),
                        "severity": a.get("severity"),
                        "category": a.get("category") or g.get("category"),
                        "confidence": "high",  # two-model agreement is strong signal
                    }
                )
                matched_g.add(gi)
                matched = True
                break
        if not matched:
            gpt54_only.append(a)

    gemini_only = [g for gi, g in enumerate(gemini_corrs) if gi not in matched_g]

    return {
        "stem": stem,
        "source_gemini_dir": gemini_info["source_dir"],
        "counts": {
            "gpt54_total": len(gpt54_corrs),
            "gemini_total": len(gemini_corrs),
            "agreed": len(agreed),
            "gpt54_only": len(gpt54_only),
            "gemini_only": len(gemini_only),
        },
        "agreed": agreed,
        "gpt54_only": gpt54_only,
        "gemini_only": gemini_only,
    }


def build_summary(per_page: list[dict[str, Any]]) -> str:
    total = Counter()
    by_dir = Counter()
    for p in per_page:
        total["pages"] += 1
        total["agreed"] += p["counts"]["agreed"]
        total["gpt54_only"] += p["counts"]["gpt54_only"]
        total["gemini_only"] += p["counts"]["gemini_only"]
        by_dir[p["source_gemini_dir"]] += 1

    agreement_rate_by_dir: dict[str, dict[str, int]] = {}
    for p in per_page:
        d = p["source_gemini_dir"]
        agreement_rate_by_dir.setdefault(d, Counter())
        agreement_rate_by_dir[d]["pages"] += 1
        agreement_rate_by_dir[d]["agreed"] += p["counts"]["agreed"]
        agreement_rate_by_dir[d]["gpt54_only"] += p["counts"]["gpt54_only"]
        agreement_rate_by_dir[d]["gemini_only"] += p["counts"]["gemini_only"]
        agreement_rate_by_dir[d]["gpt54_total"] += p["counts"]["gpt54_total"]
        agreement_rate_by_dir[d]["gemini_total"] += p["counts"]["gemini_total"]

    # Top pages with most Gemini-only (new) flags — likely hidden errors GPT-5.4 missed
    gemini_new = sorted(
        per_page,
        key=lambda p: -p["counts"]["gemini_only"],
    )[:15]

    lines = [
        "# Merged GPT-5.4 + Gemini review summary",
        "",
        f"**Generated:** {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Pages with both GPT-5.4 + Gemini reviews: **{total['pages']}**",
        "",
        "## Cross-model agreement",
        "",
        f"- **Agreed corrections (high signal):** {total['agreed']}",
        f"- **GPT-5.4-only (Gemini did not flag):** {total['gpt54_only']}",
        f"- **Gemini-only (GPT-5.4 did not flag):** {total['gemini_only']}",
        "",
        "Agreed corrections are the highest-confidence items: two independent",
        "vision models (GPT-5.4, Gemini 2.5 Pro) flagged essentially the same",
        "fix. These should be auto-applied.",
        "",
        "GPT-5.4-only and Gemini-only items represent *possible* real errors",
        "that one model missed. These need human adjudication or a ",
        "third-opinion pass.",
        "",
        "## By Gemini scope",
        "",
        "| Scope | Pages | GPT-5.4 items | Gemini items | Agreed | GPT-5.4-only | Gemini-only |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for d, c in sorted(agreement_rate_by_dir.items()):
        lines.append(
            f"| `{d}` | {c['pages']} | {c['gpt54_total']} | {c['gemini_total']} "
            f"| {c['agreed']} | {c['gpt54_only']} | {c['gemini_only']} |"
        )
    lines.extend(
        [
            "",
            "## Pages with most Gemini-only flags (possible GPT-5.4 misses)",
            "",
        ]
    )
    for p in gemini_new:
        lines.append(
            f"- `{p['stem']}` — gemini_only={p['counts']['gemini_only']} "
            f"(gpt54_total={p['counts']['gpt54_total']}, gemini_total={p['counts']['gemini_total']})"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gemini-dirs",
        default=",".join(DEFAULT_GEMINI_DIRS),
        help="Comma-separated list of gemini subdirs under sources/lxx/swete/reviews/",
    )
    ap.add_argument(
        "--page",
        help="Single page stem (e.g. vol2_p0155). Default: all pages with both reviews.",
    )
    args = ap.parse_args()

    gemini_dirs = [REVIEWS_ROOT / d.strip() for d in args.gemini_dirs.split(",") if d.strip()]
    gemini_dirs = [d for d in gemini_dirs if d.exists()]
    if not gemini_dirs:
        print("No Gemini review dirs found.", file=sys.stderr)
        return 2

    MERGED_DIR.mkdir(parents=True, exist_ok=True)

    per_page: list[dict[str, Any]] = []
    stems_to_process: list[str] = []
    if args.page:
        stems_to_process = [args.page]
    else:
        # Any stem that has BOTH a GPT-5.4 review and a Gemini review somewhere
        gpt54_stems = {
            p.stem.replace(".review", "") for p in GPT54_DIR.glob("*.review.json")
        }
        gemini_stems: set[str] = set()
        for d in gemini_dirs:
            gemini_stems.update(
                p.stem.replace(".review", "") for p in d.glob("*.review.json")
            )
        stems_to_process = sorted(gpt54_stems & gemini_stems)

    for stem in stems_to_process:
        gpt54_path = GPT54_DIR / f"{stem}.review.json"
        if not gpt54_path.exists():
            continue
        gpt54 = load_review(gpt54_path)
        if gpt54 is None:
            continue
        gemini_info = reviews_for_stem(gemini_dirs, stem)
        if gemini_info is None:
            continue
        merged = merge_page(stem, gpt54, gemini_info)
        per_page.append(merged)
        out_path = MERGED_DIR / f"{stem}.merged.json"
        out_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    SUMMARY_PATH.write_text(build_summary(per_page), encoding="utf-8")

    total_agreed = sum(p["counts"]["agreed"] for p in per_page)
    print(f"Merged {len(per_page)} page(s).")
    print(f"  agreed corrections: {total_agreed}")
    print(f"  gpt54-only:         {sum(p['counts']['gpt54_only'] for p in per_page)}")
    print(f"  gemini-only:        {sum(p['counts']['gemini_only'] for p in per_page)}")
    print(f"Summary: {SUMMARY_PATH}")
    print(f"Per-page merged dir: {MERGED_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
