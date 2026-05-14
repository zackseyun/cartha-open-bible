#!/usr/bin/env python3
"""Normalize inline footnote markers in translation YAMLs.

Reader text supports compact footnote anchors like ``[a]`` / ``[b]``. A few
extra-canonical records accidentally used verse references as markers
(``[1:21]``, ``[30:4-5]``), which can leak into the reading surface because
client marker stripping intentionally expects simple labels.

This tool rewrites files that contain unsafe footnote markers. In those files,
every footnote marker is reassigned to ``a``..``z`` in the order the anchors
appear in ``translation.text``. Existing safe markers in the same file are
renumbered too, so there are no collisions. When a marker used to be a verse
reference or phrase label, the old value is preserved as ``anchor_ref`` for
splitters that need to route chapter-level notes back to verse-level reader
files.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import string
from typing import Any

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
INLINE_MARKER_RE = re.compile(r"\[([^\[\]\n]{1,40})\]")
COLON_MARKER_RE = re.compile(r"\[[0-9]+:[0-9]+(?:[-–—][0-9]+)?\]")
SAFE_MARKER_RE = re.compile(r"[A-Za-z0-9]{1,4}")


def strip_orphan_colon_markers(text: str) -> str:
    """Remove leaked ``[chapter:verse]`` marker tokens from user-facing text."""
    cleaned = COLON_MARKER_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,;:!?])", r"\1", cleaned)
    return cleaned


def is_safe_marker(marker: str) -> bool:
    return bool(SAFE_MARKER_RE.fullmatch(marker)) and ":" not in marker


def load_yaml(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - report-only path
        print(f"[parse-error] {path.relative_to(REPO_ROOT)}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def marker_order(text: str, markers: list[str]) -> list[str]:
    marker_set = set(markers)
    ordered: list[str] = []
    seen: set[str] = set()
    for match in INLINE_MARKER_RE.finditer(text):
        marker = match.group(1).strip()
        if marker in marker_set and marker not in seen:
            ordered.append(marker)
            seen.add(marker)
    for marker in markers:
        if marker not in seen:
            ordered.append(marker)
            seen.add(marker)
    return ordered


def normalize_file(path: pathlib.Path, *, write: bool) -> tuple[bool, dict[str, str]]:
    doc = load_yaml(path)
    if not doc:
        return False, {}
    translation = doc.get("translation")
    if not isinstance(translation, dict):
        return False, {}
    text = str(translation.get("text") or "")
    footnotes = translation.get("footnotes") or []
    if not isinstance(footnotes, list):
        footnotes = []

    markers: list[str] = []
    for footnote in footnotes:
        if not isinstance(footnote, dict):
            continue
        marker = str(footnote.get("marker") or "").strip()
        if marker:
            markers.append(marker)
    unsafe_marker_refs = any(not is_safe_marker(marker) for marker in markers)
    colon_marker_refs = any(":" in marker for marker in markers)
    colon_text_refs = bool(COLON_MARKER_RE.search(text))
    colon_note_refs = any(
        isinstance(footnote, dict)
        and isinstance(footnote.get("text"), str)
        and COLON_MARKER_RE.search(footnote["text"])
        for footnote in footnotes
    )
    if not unsafe_marker_refs and not colon_text_refs and not colon_note_refs:
        return False, {}

    ordered = marker_order(text, markers) if markers else []
    if len(ordered) > len(string.ascii_lowercase):
        raise ValueError(
            f"{path.relative_to(REPO_ROOT)} has {len(ordered)} footnotes; "
            "single-letter normalization only supports 26"
        )

    mapping = {
        old: string.ascii_lowercase[index]
        for index, old in enumerate(ordered)
    }

    def replace_marker(match: re.Match[str]) -> str:
        marker = match.group(1).strip()
        if marker not in mapping:
            return match.group(0)
        return f"[{mapping[marker]}]"

    new_text = strip_orphan_colon_markers(INLINE_MARKER_RE.sub(replace_marker, text))
    for footnote in footnotes:
        if not isinstance(footnote, dict):
            continue
        marker = str(footnote.get("marker") or "").strip()
        if marker in mapping:
            if marker != mapping[marker] and not footnote.get("anchor_ref"):
                footnote["anchor_ref"] = marker
            footnote["marker"] = mapping[marker]
        note_text = footnote.get("text")
        if isinstance(note_text, str):
            footnote["text"] = strip_orphan_colon_markers(note_text)

    changed = new_text != text or any(
        isinstance(footnote, dict)
        and str(footnote.get("marker") or "").strip() in mapping
        and str(footnote.get("marker") or "").strip() != mapping[str(footnote.get("marker") or "").strip()]
        for footnote in footnotes
    )
    # The marker loop above mutates footnotes before `changed` can compare old
    # values, so use the easier source-of-truth: this file was selected because
    # it had a marker/ref that the normalization pass should remove.
    changed = changed or unsafe_marker_refs or colon_text_refs or colon_note_refs

    if write and changed:
        translation["text"] = new_text
        path.write_text(
            yaml.safe_dump(
                doc,
                allow_unicode=True,
                sort_keys=False,
                width=10_000,
            ),
            encoding="utf-8",
        )
    return changed, mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite files in place. Without this flag, only report changes.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(TRANSLATION_ROOT)],
        help="Files or directories to scan; defaults to translation/.",
    )
    args = parser.parse_args()

    yaml_paths: list[pathlib.Path] = []
    for raw in args.paths:
        path = pathlib.Path(raw)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.is_dir():
            yaml_paths.extend(sorted(path.rglob("*.yaml")))
        elif path.suffix in {".yaml", ".yml"}:
            yaml_paths.append(path)

    changed = 0
    for path in sorted(set(yaml_paths)):
        did_change, mapping = normalize_file(path, write=args.write)
        if not did_change:
            continue
        changed += 1
        pretty = ", ".join(f"{old}->{new}" for old, new in mapping.items())
        print(f"{'rewrote' if args.write else 'would rewrite'} {path.relative_to(REPO_ROOT)}: {pretty}")

    print(f"{'Rewrote' if args.write else 'Would rewrite'} {changed} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
