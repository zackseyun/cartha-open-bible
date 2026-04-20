#!/usr/bin/env python3
"""apply_transcription_reviews.py — tiered applier for Azure GPT-5.4 reviews.

Reads the structured corrections in sources/lxx/swete/reviews/azure/*.review.json
and applies them to sources/lxx/swete/transcribed/*.txt in tiers.

Safety rules:
  - Only auto-apply a correction if `current` matches the transcript exactly ONCE.
  - Skip `apparatus-merge` corrections on Tobit dual-recension pages (false positives).
  - Skip anything whose `confidence` is not `high`.
  - Preserve a one-time backup at <stem>.txt.bak before the first write for that page.
  - Everything not auto-applied goes into a human-review worklist.

Tier selection:
  --tier cosmetic      → RUNNING HEAD + MARGINALIA + APPARATUS/BODY cosmetic-severity
  --tier grammatical   → severity == grammatical
  --tier body-meaning  → BODY meaning-altering, non-apparatus-merge
  --tier apparatus-meaning → APPARATUS meaning-altering
  --tier all           → everything above, in the order listed

Usage:
  python3 tools/apply_transcription_reviews.py --tier cosmetic --dry-run
  python3 tools/apply_transcription_reviews.py --tier all
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys
from collections import Counter, defaultdict
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
REVIEWS_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "azure"
APPLIED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "applied"
WORKLIST_PATH = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "HUMAN_REVIEW_WORKLIST.md"

# Tobit in Swete vol 2 prints B-text + S-text in parallel on the same page.
# The reviewer (GPT-5.4) frequently flags one recension as "wrong" because it
# matches the other. apparatus-merge corrections on these pages are unreliable.
TOBIT_PAGE_RANGE = ("vol2_p0832", "vol2_p0862")

TIER_COSMETIC = "cosmetic"
TIER_GRAMMATICAL = "grammatical"
TIER_BODY_MEANING = "body-meaning"
TIER_APPARATUS_MEANING = "apparatus-meaning"
TIER_ALL = "all"

TIER_ORDER = [TIER_COSMETIC, TIER_GRAMMATICAL, TIER_BODY_MEANING, TIER_APPARATUS_MEANING]


def is_tobit_page(stem: str) -> bool:
    lo, hi = TOBIT_PAGE_RANGE
    return lo <= stem <= hi


def tier_matches(tier: str, correction: dict[str, Any]) -> bool:
    section = correction.get("section", "")
    severity = correction.get("severity", "")
    category = correction.get("category", "")
    if tier == TIER_COSMETIC:
        return severity == "cosmetic"
    if tier == TIER_GRAMMATICAL:
        return severity == "grammatical"
    if tier == TIER_BODY_MEANING:
        return (
            section == "BODY"
            and severity == "meaning-altering"
            and category != "apparatus-merge"
        )
    if tier == TIER_APPARATUS_MEANING:
        return section == "APPARATUS" and severity == "meaning-altering"
    return False


def classify_match(text: str, current: str) -> tuple[str, int]:
    """Return (status, count) where status is 'unique', 'ambiguous', 'no-match', 'empty'."""
    if not current:
        return "empty", 0
    n = text.count(current)
    if n == 0:
        return "no-match", 0
    if n == 1:
        return "unique", 1
    return "ambiguous", n


def load_review(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def page_stem_from_review(path: pathlib.Path) -> str:
    return path.stem.replace(".review", "")


def apply_to_page(
    stem: str,
    txt_path: pathlib.Path,
    corrections: list[dict[str, Any]],
    tiers: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    text = txt_path.read_text(encoding="utf-8")
    original = text
    applied: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    is_tobit = is_tobit_page(stem)

    # Apply in tier order, longest-current first within each tier to avoid
    # accidental substring matches after shorter replacements.
    for tier in tiers:
        in_tier = [c for c in corrections if tier_matches(tier, c)]
        in_tier.sort(key=lambda c: len(c.get("current", "")), reverse=True)
        for c in in_tier:
            reason = None
            if c.get("confidence") != "high":
                reason = f"confidence={c.get('confidence')}"
            elif is_tobit and c.get("category") == "apparatus-merge":
                reason = "tobit-dual-recension-false-positive"
            else:
                status, _ = classify_match(text, c.get("current", ""))
                if status != "unique":
                    reason = f"match={status}"

            if reason:
                deferred.append({**c, "_defer_reason": reason, "_tier": tier})
                continue

            correct = c.get("correct", "")
            current = c.get("current", "")
            if current == correct:
                # pointless correction
                deferred.append({**c, "_defer_reason": "no-op", "_tier": tier})
                continue
            # str.replace with count=1 (we already confirmed uniqueness above)
            new_text = text.replace(current, correct, 1)
            if new_text == text:
                deferred.append({**c, "_defer_reason": "replace-no-change", "_tier": tier})
                continue
            text = new_text
            applied.append({**c, "_tier": tier})

    changed = text != original
    if changed and not dry_run:
        bak = txt_path.with_suffix(txt_path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(txt_path, bak)
        txt_path.write_text(text, encoding="utf-8")

    return {
        "stem": stem,
        "changed": changed,
        "applied_count": len(applied),
        "deferred_count": len(deferred),
        "applied": applied,
        "deferred": deferred,
    }


def build_worklist(deferred_by_page: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# Human-review worklist — Azure Swete review",
        "",
        f"**Generated:** {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Corrections that were flagged by Azure GPT-5.4 but *not* auto-applied.",
        "Reasons include: non-unique transcript match, missing anchor, non-`high` confidence,",
        "or apparatus-merge flags on Tobit dual-recension pages (false positives).",
        "",
    ]

    reason_counter: Counter[str] = Counter()
    for items in deferred_by_page.values():
        for item in items:
            reason_counter[item["_defer_reason"]] += 1

    lines.append("## Deferral reasons (counts)")
    lines.append("")
    for reason, count in reason_counter.most_common():
        lines.append(f"- `{reason}`: {count}")
    lines.append("")

    # Tobit false positives get their own section — they should not be touched.
    lines.append("## Tobit dual-recension false positives (skip — not real errors)")
    lines.append("")
    for stem, items in sorted(deferred_by_page.items()):
        tobit_items = [i for i in items if i["_defer_reason"] == "tobit-dual-recension-false-positive"]
        if not tobit_items:
            continue
        lines.append(f"### {stem} — {len(tobit_items)} item(s)")
        lines.append("")
        for item in tobit_items[:5]:
            lines.append(f"- {item.get('section')} / {item.get('location', '?')} — "
                         f"{item.get('note','')}")
        if len(tobit_items) > 5:
            lines.append(f"- … +{len(tobit_items) - 5} more")
        lines.append("")

    # Real deferrals: ambiguous / no-match / low-confidence BODY meaning-altering
    lines.append("## BODY meaning-altering items needing human adjudication")
    lines.append("")
    real_pages: list[tuple[str, list[dict[str, Any]]]] = []
    for stem, items in sorted(deferred_by_page.items()):
        interesting = [
            i for i in items
            if i.get("section") == "BODY"
            and i.get("severity") == "meaning-altering"
            and i["_defer_reason"] not in ("tobit-dual-recension-false-positive", "no-op", "replace-no-change")
        ]
        if interesting:
            real_pages.append((stem, interesting))

    lines.append(f"**{sum(len(p[1]) for p in real_pages)} items across "
                 f"{len(real_pages)} pages.**")
    lines.append("")
    for stem, items in real_pages:
        lines.append(f"### {stem}")
        lines.append("")
        for item in items:
            loc = item.get("location", "?")
            reason = item["_defer_reason"]
            cat = item.get("category", "?")
            conf = item.get("confidence", "?")
            cur = (item.get("current") or "")[:120]
            cor = (item.get("correct") or "")[:120]
            note = item.get("note", "") or ""
            lines.append(f"- **{loc}** · `{reason}` · cat=`{cat}` · conf=`{conf}`")
            lines.append(f"  - current: `{cur}`")
            lines.append(f"  - correct: `{cor}`")
            if note:
                lines.append(f"  - note: {note}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=[*TIER_ORDER, TIER_ALL], default=TIER_ALL)
    ap.add_argument("--page", help="Apply only to this page stem (e.g. vol2_p0838)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--worklist", action="store_true",
                    help="Rebuild the human-review worklist.")
    args = ap.parse_args()

    if args.tier == TIER_ALL:
        tiers = TIER_ORDER
    else:
        tiers = [args.tier]

    review_files = sorted(REVIEWS_DIR.glob("*.review.json"))
    if args.page:
        review_files = [p for p in review_files if p.stem.replace(".review", "") == args.page]
        if not review_files:
            print(f"No review file for {args.page}", file=sys.stderr)
            return 2

    APPLIED_DIR.mkdir(parents=True, exist_ok=True)

    totals = Counter()
    per_tier_applied = Counter()
    per_category_applied = Counter()
    deferred_by_page: dict[str, list[dict[str, Any]]] = {}
    pages_changed = 0

    for rf in review_files:
        stem = page_stem_from_review(rf)
        txt_path = TRANSCRIBED_DIR / f"{stem}.txt"
        if not txt_path.exists():
            continue
        review = load_review(rf)
        if review is None:
            continue
        corrections = review.get("corrections", []) or []
        if not corrections:
            continue

        result = apply_to_page(stem, txt_path, corrections, tiers, args.dry_run)
        totals["applied"] += result["applied_count"]
        totals["deferred"] += result["deferred_count"]
        if result["changed"]:
            pages_changed += 1
        for a in result["applied"]:
            per_tier_applied[a["_tier"]] += 1
            per_category_applied[a.get("category", "other")] += 1
        if result["deferred"]:
            deferred_by_page[stem] = result["deferred"]

        if not args.dry_run:
            applied_path = APPLIED_DIR / f"{stem}.applied.json"
            applied_path.write_text(
                json.dumps(
                    {
                        "stem": stem,
                        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
                        "tier_filter": tiers,
                        "applied": result["applied"],
                        "deferred": result["deferred"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    print(f"Tiers applied: {tiers}")
    print(f"Pages processed: {len(review_files)}")
    print(f"Pages changed:   {pages_changed}")
    print(f"Corrections applied:  {totals['applied']}")
    print(f"Corrections deferred: {totals['deferred']}")
    print()
    print("Applied by tier:")
    for tier in TIER_ORDER:
        print(f"  {tier}: {per_tier_applied[tier]}")
    print()
    print("Top 10 applied categories:")
    for cat, count in per_category_applied.most_common(10):
        print(f"  {cat}: {count}")

    if args.worklist:
        worklist = build_worklist(deferred_by_page)
        if args.dry_run:
            print("\n--- WORKLIST PREVIEW (first 40 lines) ---")
            for line in worklist.splitlines()[:40]:
                print(line)
        else:
            WORKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            WORKLIST_PATH.write_text(worklist, encoding="utf-8")
            print(f"\nWorklist written to {WORKLIST_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
