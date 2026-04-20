#!/usr/bin/env python3
"""normalize_superscript_verses.py — convert Unicode superscript verse
markers in BODY sections to Swete's printed inline-digit style.

The Gemini-augmented apply pass (§8) restored stripped 1 Esdras verse
markers as Unicode superscripts (⁸ ⁹ ¹⁰). Swete's original typography
uses regular inline digits. This normalizer converts superscript digits
→ regular digits + single space, but ONLY in BODY sections, and ONLY
when the superscript is followed by a Greek letter (the verse-marker
pattern). It leaves alone:

  - APPARATUS superscripts (corrector-hand designations like V¹, B²)
  - BODY superscripts followed by non-Greek chars (e.g. ⁽⁶⁰⁾ line
    indicators, footnote markers in intros)
  - Duplicate-adjacent superscript markers like `⁵² ⁵²` — collapsed to
    a single `52 `.

Usage:
  python3 tools/normalize_superscript_verses.py           # apply
  python3 tools/normalize_superscript_verses.py --dry-run
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys
from collections import Counter

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"

SUPERSCRIPT_DIGITS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}
SUPER_DIGIT_SET = set(SUPERSCRIPT_DIGITS)

# Greek letter unicode ranges (basic + extended)
GREEK_RANGES = [
    (0x0370, 0x03FF),  # Greek and Coptic
    (0x1F00, 0x1FFF),  # Greek Extended
]


def is_greek_letter(ch: str) -> bool:
    if not ch:
        return False
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in GREEK_RANGES) and ch.isalpha()


def transliterate_super_run(s: str) -> str:
    return "".join(SUPERSCRIPT_DIGITS.get(c, c) for c in s)


def dedupe_repeated_number(digits: str) -> str:
    """If a digit string is the same number repeated (e.g. '1010', '1111',
    '525252'), return a single copy. Otherwise return input unchanged.

    This catches the double-apply bug from the two-pass applier where the
    same verse marker got inserted twice.
    """
    n = len(digits)
    if n < 2:
        return digits
    # Prefer the LONGEST repeating unit. '1111' should collapse to '11'
    # (verse 11 doubled), not '1' (verse 1 quadrupled).
    for k in range(n // 2, 0, -1):
        if n % k != 0:
            continue
        unit = digits[:k]
        if unit * (n // k) == digits:
            return unit
    return digits


SUPER_RUN_RE = re.compile(f"[{''.join(SUPER_DIGIT_SET)}]+")


def normalize_body_line(line: str) -> tuple[str, int]:
    """Normalize superscript verse markers on a BODY line. Returns (new_line, n_replacements)."""
    if not any(c in SUPER_DIGIT_SET for c in line):
        return line, 0
    out: list[str] = []
    i = 0
    n = 0
    while i < len(line):
        ch = line[i]
        if ch in SUPER_DIGIT_SET:
            # Scan run
            j = i
            while j < len(line) and line[j] in SUPER_DIGIT_SET:
                j += 1
            run = line[i:j]
            # Check preceding char (to avoid decoding things like `8⁷`
            # where `8⁷` forms a manuscript designation) and following
            # char (must be Greek letter to be a verse marker)
            prev = line[i - 1] if i > 0 else ""
            follow = line[j] if j < len(line) else ""
            if prev.isdigit():
                # `8⁷` — leave alone
                out.append(run)
                i = j
                continue
            if prev and prev in "(⟨【":
                # parenthesized — leave alone
                out.append(run)
                i = j
                continue
            if is_greek_letter(follow):
                digit_str = transliterate_super_run(run)
                digit_str = dedupe_repeated_number(digit_str)
                out.append(digit_str)
                # ensure a space between digit and Greek word
                out.append(" ")
                n += 1
                i = j
                continue
            # Not a verse-marker pattern — leave alone
            out.append(run)
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out), n


DUP_VERSE_RE = re.compile(r"(\d+)\s+\1(?:\s+\1)*(\s+)")
# Insert a space between a leading digit run and a following Greek letter:
# "10μὴ" → "10 μὴ". Only matches at word boundary (preceded by non-digit/
# non-letter) so we don't break things like "inline-33" or manuscript "87a".
DIGIT_GLUED_TO_GREEK_RE = re.compile(
    r"(?<![\d\w])(\d+)([\u0370-\u03FF\u1F00-\u1FFF])"
)


def collapse_duplicate_verse_markers(line: str) -> tuple[str, int]:
    """Collapse `52 52 52 Greek...` → `52 Greek...`.

    Only handles the space-separated duplicate case. Concat-duplicates
    like `1010` are handled inside the superscript-run path by
    `dedupe_repeated_number` (which runs only on known-superscript text),
    so we don't need a general `(\\d+)\\1+` regex here — that would
    over-match legitimate verse numbers like `11`, `22`, `33`.
    """
    n_collapsed = 0

    def sub(m: re.Match) -> str:
        nonlocal n_collapsed
        n_collapsed += 1
        return f"{m.group(1)}{m.group(2)}"

    new = DUP_VERSE_RE.sub(sub, line)
    return new, n_collapsed


def space_verse_markers(line: str) -> tuple[str, int]:
    """Insert a space between a leading verse-digit and the Greek word it
    introduces: `10μὴ` → `10 μὴ`."""
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        n += 1
        return f"{m.group(1)} {m.group(2)}"

    new = DIGIT_GLUED_TO_GREEK_RE.sub(sub, line)
    return new, n


def process_text(text: str) -> tuple[str, dict[str, int]]:
    stats = Counter()
    out_lines: list[str] = []
    in_body = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "[BODY]":
            in_body = True
            out_lines.append(line)
            continue
        if stripped in ("[APPARATUS]", "[RUNNING HEAD]", "[MARGINALIA]", "[PLATE]", "[BLANK]", "---END-PAGE---"):
            in_body = False
            out_lines.append(line)
            continue
        if not in_body:
            out_lines.append(line)
            continue
        # Preserve trailing newline
        nl = ""
        body = line
        if line.endswith("\n"):
            nl = "\n"
            body = line[:-1]
        new_body, n_super = normalize_body_line(body)
        new_body, n_dup = collapse_duplicate_verse_markers(new_body)
        new_body, n_space = space_verse_markers(new_body)
        stats["super_replaced"] += n_super
        stats["duplicates_collapsed"] += n_dup
        stats["verse_markers_spaced"] += n_space
        out_lines.append(new_body + nl)
    return "".join(out_lines), stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--page", help="Only operate on this stem (e.g. vol2_p0155)")
    args = ap.parse_args()

    files = sorted(TRANSCRIBED_DIR.glob("vol*_p*.txt"))
    if args.page:
        files = [f for f in files if f.stem == args.page]

    corpus_stats = Counter()
    pages_changed = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        new_text, stats = process_text(text)
        if new_text != text:
            pages_changed += 1
            corpus_stats.update(stats)
            if not args.dry_run:
                bak = f.with_suffix(f.suffix + ".bak")
                if not bak.exists():
                    shutil.copy2(f, bak)
                f.write_text(new_text, encoding="utf-8")
    print(f"Pages processed: {len(files)}")
    print(f"Pages changed:   {pages_changed}")
    print(f"Superscript verse markers converted to inline digits: {corpus_stats['super_replaced']}")
    print(f"Duplicate-adjacent verse markers collapsed:          {corpus_stats['duplicates_collapsed']}")
    print(f"Verse markers given space before Greek:              {corpus_stats['verse_markers_spaced']}")
    if args.dry_run:
        print("\n(dry run — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
