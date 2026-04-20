#!/usr/bin/env python3
"""apply_merged_reviews.py — apply Azure+Gemini merged corrections.

Consumes the per-page `*.merged.json` files produced by merge_reviews.py
and applies corrections back to the transcribed .txt files. Same safety
posture as apply_transcription_reviews.py:

  - Only corrections with `confidence: "high"` and a unique-match anchor
    in the current transcript are auto-applied.
  - Per-page `<stem>.txt.bak` is created on first edit (if it doesn't
    already exist from an earlier pass).
  - A per-page `<stem>.merged-applied.json` audit trail is written.

Tiers:
  --tier agreed          → only items both Azure AND Gemini flagged
  --tier gemini-body     → agreed + gemini-only BODY corrections
                           in translation-critical categories
                           (missing-prefix, missing-phrase, name-misread,
                           line-number-captured-as-verse)
  --tier all             → agreed + gemini-only unique-high, all sections

Usage:
  python3 tools/apply_merged_reviews.py --tier agreed --dry-run
  python3 tools/apply_merged_reviews.py --tier gemini-body
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys
from collections import Counter
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
MERGED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "merged"
APPLIED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "merged_applied"

TRANSLATION_CRITICAL_BODY_CATS = {
    "missing-prefix",
    "missing-phrase",
    "missing-letter",
    "name-misread",
    "line-number-captured-as-verse",
}


def classify_match(text: str, current: str) -> str:
    if not current:
        return "empty"
    n = text.count(current)
    if n == 0:
        return "no-match"
    if n == 1:
        return "unique"
    return "ambiguous"


def flatten_agreed(merged: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in merged.get("agreed", []):
        # merge_reviews writes `current`, `correct`, `severity`, etc at top level
        out.append(
            {
                **item,
                "_provenance": "agreed",
            }
        )
    return out


def flatten_gemini_only(merged: dict[str, Any], tier: str) -> list[dict[str, Any]]:
    out = []
    for g in merged.get("gemini_only", []):
        if g.get("confidence") != "high":
            continue
        section = g.get("section")
        category = g.get("category")
        if tier == "gemini-body":
            if section != "BODY":
                continue
            if category not in TRANSLATION_CRITICAL_BODY_CATS:
                continue
        # tier == "all" accepts everything high-confidence
        out.append({**g, "_provenance": "gemini_only"})
    return out


def apply_to_page(
    stem: str,
    txt_path: pathlib.Path,
    corrections: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    text = txt_path.read_text(encoding="utf-8")
    original = text
    applied: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []

    # Apply longest `current` first within each provenance bucket
    corrections_sorted = sorted(
        corrections,
        key=lambda c: (-len(c.get("current", "") or ""), c.get("_provenance", "")),
    )
    for c in corrections_sorted:
        cur = c.get("current", "") or ""
        cor = c.get("correct", "") or ""
        if not cur or not cor or cur == cor:
            deferred.append({**c, "_defer_reason": "no-op-or-empty"})
            continue
        m = classify_match(text, cur)
        if m != "unique":
            deferred.append({**c, "_defer_reason": f"match={m}"})
            continue
        new_text = text.replace(cur, cor, 1)
        if new_text == text:
            deferred.append({**c, "_defer_reason": "replace-no-change"})
            continue
        text = new_text
        applied.append(c)

    changed = text != original
    if changed and not dry_run:
        bak = txt_path.with_suffix(txt_path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(txt_path, bak)
        txt_path.write_text(text, encoding="utf-8")

    return {
        "stem": stem,
        "changed": changed,
        "applied": applied,
        "deferred": deferred,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["agreed", "gemini-body", "all"], default="gemini-body")
    ap.add_argument("--page", help="Restrict to a single stem (e.g. vol2_p0155)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    files = sorted(MERGED_DIR.glob("*.merged.json"))
    if args.page:
        files = [f for f in files if f.stem.replace(".merged", "") == args.page]
        if not files:
            print(f"No merged file for {args.page}", file=sys.stderr)
            return 2

    APPLIED_DIR.mkdir(parents=True, exist_ok=True)

    totals = Counter()
    per_category = Counter()
    per_provenance = Counter()
    pages_changed = 0
    for f in files:
        merged = json.loads(f.read_text())
        stem = merged["stem"]
        txt_path = TRANSCRIBED_DIR / f"{stem}.txt"
        if not txt_path.exists():
            continue
        candidates = flatten_agreed(merged)
        if args.tier in ("gemini-body", "all"):
            candidates += flatten_gemini_only(merged, args.tier)
        if not candidates:
            continue
        res = apply_to_page(stem, txt_path, candidates, args.dry_run)
        if res["changed"]:
            pages_changed += 1
        totals["applied"] += len(res["applied"])
        totals["deferred"] += len(res["deferred"])
        for a in res["applied"]:
            per_category[a.get("category", "other")] += 1
            per_provenance[a["_provenance"]] += 1
        if not args.dry_run:
            out = APPLIED_DIR / f"{stem}.merged-applied.json"
            out.write_text(
                json.dumps(
                    {
                        "stem": stem,
                        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "tier": args.tier,
                        "applied": res["applied"],
                        "deferred": res["deferred"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    print(f"Tier:            {args.tier}")
    print(f"Pages processed: {len(files)}")
    print(f"Pages changed:   {pages_changed}")
    print(f"Applied:         {totals['applied']}")
    print(f"Deferred:        {totals['deferred']}")
    print()
    print("By provenance:")
    for k, v in per_provenance.most_common():
        print(f"  {k}: {v}")
    print("Top applied categories:")
    for k, v in per_category.most_common(10):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
