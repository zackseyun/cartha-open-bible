#!/usr/bin/env python3
"""Audit translation YAMLs for footnote markers that aren't anchored in
the verse text. The publisher Lambda silently filters those out, so any
orphaned footnote never reaches readers.

Usage:
  python3 tools/audit_footnotes.py                # report only
  python3 tools/audit_footnotes.py --auto-fix     # insert [marker] at
                                                  # end of sentence and
                                                  # rewrite YAML in place

The auto-fix is conservative: it only acts when the verse text contains
no marker at all, AND the verse has exactly ONE footnote. Multi-footnote
verses are reported but require manual placement (you have to decide
which clause each marker goes after).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "translation"

# Match any [a]…[z] inline marker — what the publisher Lambda expects
MARKER_RE = re.compile(r"\[([a-z])\]")


def audit_one(path: Path) -> tuple[str, list[dict]]:
    """Return (status, footnotes_list) for one YAML.

    status ∈ {"ok", "no_footnotes", "orphaned", "partial", "extra_marker"}
    """
    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        return "parse_error", []
    tr = doc.get("translation") if isinstance(doc, dict) else None
    if not isinstance(tr, dict):
        return "no_footnotes", []
    text = str(tr.get("text") or "")
    footnotes = tr.get("footnotes") or []
    if not isinstance(footnotes, list) or not footnotes:
        return "no_footnotes", []
    declared_markers = {str(f.get("marker", "")).strip() for f in footnotes if isinstance(f, dict)}
    declared_markers.discard("")
    inline_markers = set(MARKER_RE.findall(text))
    orphaned = declared_markers - inline_markers
    extra = inline_markers - declared_markers
    if not orphaned and not extra:
        return "ok", footnotes
    if orphaned and not extra:
        return ("orphaned" if orphaned == declared_markers else "partial"), footnotes
    if extra:
        return "extra_marker", footnotes
    return "ok", footnotes


def _compute_anchored(text: str, marker: str) -> str:
    """Return `text` with [marker] inserted at a sensible position."""
    # Insert before the FIRST sentence terminator. Prefer comma so the
    # marker sits close to the opening lexical site (most footnotes in
    # this corpus discuss the first word or phrase). Fall back to period.
    for terminator in [", ", ". ", "; "]:
        idx = text.find(terminator)
        if idx > 0:
            return text[:idx] + f"[{marker}]" + text[idx:]
    if text.endswith("."):
        return text[:-1] + f"[{marker}]" + "."
    return text + f"[{marker}]"


def _compute_anchored_many(text: str, markers: list[str]) -> str:
    """Distribute multiple markers across sentence/clause boundaries.

    Strategy: collect all comma + period + semicolon boundary indexes,
    then assign markers to evenly-spaced boundaries so they don't all
    pile up in one spot. If there are fewer boundaries than markers, the
    remainder are appended at the end.
    """
    if not markers:
        return text
    if len(markers) == 1:
        return _compute_anchored(text, markers[0])
    # Find all boundary indexes (positions just before the punctuation)
    boundaries = []
    for i, ch in enumerate(text):
        if ch in (",", ";", "."):
            # Skip the absolute final period — we don't want to anchor
            # the LAST marker after the closing period
            if i == len(text) - 1 and ch == ".":
                continue
            # Need a space (or end) right after to avoid mid-word matches
            if i + 1 < len(text) and text[i + 1] not in (" ", "\n", "\t"):
                continue
            boundaries.append(i)
    if not boundaries:
        # No boundaries — append all markers in sequence at end
        suffix = "".join(f"[{m}]" for m in markers)
        if text.endswith("."):
            return text[:-1] + suffix + "."
        return text + suffix

    # Pick `len(markers)` evenly-spaced boundary indexes. Always assign
    # the FIRST marker to the FIRST boundary (close to the opening
    # lexical site, where most footnotes anchor).
    n = len(markers)
    if n == 1:
        chosen = [boundaries[0]]
    else:
        step = max(1, len(boundaries) // n)
        chosen = []
        for i in range(n):
            idx = min(i * step, len(boundaries) - 1)
            if chosen and idx <= chosen[-1]:
                idx = min(chosen[-1] + 1, len(boundaries) - 1)
            if idx < len(boundaries):
                chosen.append(boundaries[idx])
        # If we ran out of boundary slots, append remaining markers at end
        while len(chosen) < n:
            chosen.append(None)

    # Build new text by inserting markers right-to-left so indexes stay valid
    result = text
    for marker, pos in sorted(
        zip(markers, chosen),
        key=lambda mp: -1 if mp[1] is None else mp[1],
        reverse=True,
    ):
        if pos is None:
            # Append at end (before final period if present)
            if result.endswith("."):
                result = result[:-1] + f"[{marker}]" + "."
            else:
                result = result + f"[{marker}]"
        else:
            result = result[:pos] + f"[{marker}]" + result[pos:]
    return result


def auto_fix_orphan(path: Path, allow_multi: bool = False) -> bool:
    """Insert footnote anchors inside translation.text and rewrite the YAML.

    `allow_multi=False` (default) only fixes verses with exactly one
    footnote. `allow_multi=True` also fixes verses with multiple
    orphaned markers, distributing them across sentence boundaries.

    Returns True if the file was rewritten.
    """
    with open(path) as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict):
        return False
    tr = doc.get("translation")
    if not isinstance(tr, dict):
        return False
    text = str(tr.get("text") or "")
    footnotes = tr.get("footnotes") or []
    if not footnotes or not text:
        return False
    declared = [str(f.get("marker", "")).strip() for f in footnotes if isinstance(f, dict)]
    declared = [m for m in declared if m]
    inline = set(MARKER_RE.findall(text))
    missing = [m for m in declared if m not in inline]
    if not missing:
        return False  # nothing orphaned

    if len(missing) == 1 and len(declared) == 1:
        new_text = _compute_anchored(text, missing[0])
    else:
        if not allow_multi:
            return False
        # In multi-mode, only place markers that are ACTUALLY missing —
        # don't disturb any markers already inline correctly.
        new_text = _compute_anchored_many(text, missing)
    if new_text == text:
        return False
    tr["text"] = new_text

    # Round-trip: dump everything back. allow_unicode preserves Hebrew/
    # Greek source text; sort_keys=False keeps id/reference/source/
    # translation order; default_flow_style=False keeps the verbose layout
    # the rest of the corpus uses; width keeps long lines from wrapping
    # awkwardly.
    with open(path, "w") as f:
        yaml.safe_dump(
            doc, f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10_000,  # don't fold long lines
        )
    return True


def yaml_safe_value(s: str) -> str:
    """Render a string for inline YAML scalar context. Quote if necessary."""
    needs_quote = (
        any(c in s for c in [":", "#", "[", "]", "{", "}", ",", "&", "*", "!", "|", ">", '"', "'", "%", "@", "`"])
        or s.strip() != s
        or not s
    )
    if needs_quote:
        # Use single quotes; escape internal single quotes by doubling.
        return "'" + s.replace("'", "''") + "'"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto-fix", action="store_true",
                    help="Rewrite YAMLs where exactly one footnote is orphaned")
    ap.add_argument("--auto-fix-multi", action="store_true",
                    help="Also fix multi-footnote orphans by distributing markers across clause boundaries")
    args = ap.parse_args()

    counts = {"ok": 0, "no_footnotes": 0, "orphaned": 0, "partial": 0,
              "extra_marker": 0, "parse_error": 0}
    orphan_paths = []
    multi_orphans = []
    extras = []

    for p in sorted(ROOT.rglob("*.yaml")):
        status, footnotes = audit_one(p)
        counts[status] = counts.get(status, 0) + 1
        if status == "orphaned":
            if len(footnotes) == 1:
                orphan_paths.append(p)
            else:
                multi_orphans.append((p, len(footnotes)))
        elif status == "partial":
            multi_orphans.append((p, len(footnotes)))
        elif status == "extra_marker":
            extras.append(p)

    print(f"Audited {sum(counts.values()):,} YAMLs:")
    for k, v in counts.items():
        print(f"  {k:15s}: {v:,}")
    print()
    print(f"Single-footnote orphans (auto-fixable): {len(orphan_paths):,}")
    print(f"Multi-footnote orphans/partials (manual): {len(multi_orphans):,}")
    print(f"Stray inline markers (no matching footnote): {len(extras):,}")

    if multi_orphans:
        print("\nMulti-footnote files needing manual placement:")
        for p, n in multi_orphans[:20]:
            print(f"  {p.relative_to(ROOT.parent)}  ({n} footnotes)")
        if len(multi_orphans) > 20:
            print(f"  ... and {len(multi_orphans) - 20} more")

    if extras:
        print("\nFiles with inline marker but no matching footnote:")
        for p in extras[:10]:
            print(f"  {p.relative_to(ROOT.parent)}")

    if args.auto_fix or args.auto_fix_multi:
        all_targets = orphan_paths + ([p for p, _ in multi_orphans] if args.auto_fix_multi else [])
        print(f"\nAuto-fixing {len(all_targets):,} files (multi={args.auto_fix_multi})...")
        fixed = 0
        for p in all_targets:
            if auto_fix_orphan(p, allow_multi=args.auto_fix_multi):
                fixed += 1
        print(f"Fixed: {fixed:,}")
    elif orphan_paths:
        print(f"\nRun with --auto-fix to anchor {len(orphan_paths):,} single-footnote orphans.")
        print(f"Add --auto-fix-multi to also distribute markers in {len(multi_orphans):,} multi-footnote files.")


if __name__ == "__main__":
    main()
