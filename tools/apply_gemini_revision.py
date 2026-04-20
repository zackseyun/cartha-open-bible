#!/usr/bin/env python3
"""apply_gemini_revision.py — apply an adjudicated Gemini-proposed revision to a verse YAML.

Preserves GPT-5.4's provenance (ai_draft block stays unchanged) and
records the revision with adjudicator + rationale + source review path.
The original rendering is preserved as a footnote marked
`reason: previous_rendering` so it stays visible to readers.

Usage:
  python3 tools/apply_gemini_revision.py \\
      --testament ot --book genesis --chapter 3 --verse 4 \\
      --find "You will not surely die." \\
      --replace "You will surely not die." \\
      --rationale "Hebrew לֹא+inf-abs+finite = emphatic denial..."
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def yaml_path_for(testament: str, book_slug: str, chapter: int, verse: int) -> pathlib.Path:
    return REPO_ROOT / "translation" / testament / book_slug / f"{chapter:03d}" / f"{verse:03d}.yaml"


def next_footnote_marker(existing: list[dict[str, Any]] | None) -> str:
    if not existing:
        return "a"
    taken = {f.get("marker") for f in existing if isinstance(f, dict)}
    for c in "abcdefghijklmnopqrstuvwxyz":
        if c not in taken:
            return c
    return "z"


def apply_revision(
    *,
    path: pathlib.Path,
    find: str,
    replace: str,
    rationale: str,
    review_path: str | None,
    issue_category: str = "mistranslation",
) -> None:
    if not path.exists():
        raise FileNotFoundError(path)

    # Preserve formatting: use ruamel-like round-trip via raw text edit
    # when possible, else fall back to yaml.safe_load/dump.
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: not a YAML mapping")

    translation = data.setdefault("translation", {})
    current_text = translation.get("text", "")
    if find not in current_text:
        raise ValueError(
            f"Find text not present in {path}. Existing:\n  {current_text!r}\n"
            f"Looked for:\n  {find!r}"
        )
    new_text = current_text.replace(find, replace, 1)
    if new_text == current_text:
        raise ValueError("replacement yielded no change")
    translation["text"] = new_text

    # Record original rendering as a footnote so readers can see it.
    footnotes = translation.setdefault("footnotes", [])
    marker = next_footnote_marker(footnotes)
    footnotes.append({
        "marker": marker,
        "text": f"Or {find!r}.",
        "reason": "previous_rendering",
    })

    # Record the revision event at top level.
    revisions = data.setdefault("revisions", [])
    revisions.append({
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adjudicator": "claude-opus-4-7",
        "reviewer_model": "gemini-2.5-pro",
        "source_review": review_path,
        "category": issue_category,
        "from": find,
        "to": replace,
        "rationale": rationale,
    })

    new_yaml = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(new_yaml, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--testament", required=True, choices=["nt", "ot", "deuterocanon"])
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True, type=int)
    ap.add_argument("--verse", required=True, type=int)
    ap.add_argument("--find", required=True)
    ap.add_argument("--replace", required=True)
    ap.add_argument("--rationale", required=True)
    ap.add_argument("--review-path")
    ap.add_argument("--category", default="mistranslation")
    args = ap.parse_args()

    path = yaml_path_for(args.testament, args.book, args.chapter, args.verse)
    apply_revision(
        path=path,
        find=args.find,
        replace=args.replace,
        rationale=args.rationale,
        review_path=args.review_path,
        issue_category=args.category,
    )
    print(f"Updated {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
