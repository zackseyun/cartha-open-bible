#!/usr/bin/env python3
"""normalize_yahweh.py — replace 'the LORD' with 'Yahweh' wherever source uses יְהוָה.

Policy change: wherever the Hebrew source text contains the Tetragrammaton
(יְהוָה / YHWH), the English translation uses 'Yahweh' rather than the
traditional 'the LORD' substitution. Where the source has Adonai (אֲדֹנָי),
'Lord' is kept unchanged.

Detection: a verse needs updating if its source.text field contains יְהוָה.
This is the authoritative signal — more reliable than grep on translation text.

Changes made per file:
  - translation.text: 'the LORD' / 'The LORD' / 'LORD' → 'Yahweh'
  - lexical_decisions[i].chosen where source_word is יְהוָה
  - lexical_decisions[i].rationale: update boilerplate to reflect new policy
  - theological_decisions[i].chosen_reading for the divine name entry
  - theological_decisions[i].rationale: update boilerplate

Footnotes are intentionally left unchanged — they explain translation choices
and the explanatory context remains valid (e.g., "Hebrew YHWH, ...").

Run:
  python3 tools/normalize_yahweh.py --dry-run    # count + sample, no writes
  python3 tools/normalize_yahweh.py              # apply to all OT + deuterocanon
  python3 tools/normalize_yahweh.py --book psalms
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from datetime import datetime, timezone

from ruamel.yaml import YAML

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Match YHWH in any pointing/cantillation form. Hebrew cantillation marks and
# vowel points (U+0591–U+05C7) appear interspersed between the consonants in
# the WLC source text, e.g. יְהוָ֥ה (with a merkha between qamats and final heh).
# Matching the four base consonants י-ה-ו-ה with optional diacritics between
# them is more reliable than a bare string comparison.
TETRAGRAMMATON = "יְהוָה"  # bare form for lexical_decisions lookup
_YHWH_RE = re.compile(r'י[\u0591-\u05C7]*ה[\u0591-\u05C7]*ו[\u0591-\u05C7]*ה')

NEW_RATIONALE = (
    "Per doctrine, the Tetragrammaton יְהוָה is rendered 'Yahweh' — the "
    "transliteration of the divine name — rather than the traditional 'the "
    "LORD' substitution. This preserves the personal name God revealed to "
    "Israel rather than substituting a title."
)
NEW_THEOLOGICAL_RATIONALE = (
    "The verse uses the Tetragrammaton יְהוָה directly. Per updated doctrine, "
    "the divine name is rendered 'Yahweh' rather than 'the LORD', preserving "
    "the covenant name God revealed at Sinai."
)


def _replace_lord(text: str) -> tuple[str, bool]:
    """Replace LORD-as-YHWH renderings with Yahweh. Returns (new_text, changed)."""
    original = text
    # 'the LORD' and 'The LORD' → 'Yahweh' (drops the article, which is not in Hebrew)
    text = re.sub(r'\b[Tt]he LORD\b', 'Yahweh', text)
    # Standalone LORD (vocative 'O LORD', 'LORD of hosts', start of sentence)
    text = re.sub(r'\bLORD\b', 'Yahweh', text)
    return text, text != original


def process_file(path: pathlib.Path, dry_run: bool, yaml: YAML) -> bool:
    """Return True if file was (or would be) changed."""
    raw = path.read_text(encoding="utf-8")
    # Quick pre-filter on raw bytes before YAML parse (fast path for ~98% of files)
    if not _YHWH_RE.search(raw):
        return False

    data = yaml.load(raw)
    if not isinstance(data, dict):
        return False

    source = data.get("source") or {}
    source_text = str(source.get("text") or "")
    if not _YHWH_RE.search(source_text):
        return False

    changed = False

    # 1. translation.text
    tr = data.get("translation") or {}
    if isinstance(tr, dict):
        t = tr.get("text") or ""
        new_t, c = _replace_lord(str(t))
        if c:
            tr["text"] = new_t
            changed = True

    # 2. lexical_decisions — find YHWH entry/-ies
    for ld in (data.get("lexical_decisions") or []):
        if not isinstance(ld, dict):
            continue
        if ld.get("source_word") == TETRAGRAMMATON:
            chosen = str(ld.get("chosen") or "")
            new_chosen, c = _replace_lord(chosen)
            if not c and chosen.strip().upper() in ("THE LORD", "LORD"):
                new_chosen = "Yahweh"
                c = True
            if c:
                ld["chosen"] = new_chosen
                changed = True
            # Update alternatives list to put Yahweh first if present
            alts = list(ld.get("alternatives") or [])
            if alts:
                alts_str = [str(a) for a in alts]
                if "Yahweh" in alts_str:
                    alts_str.remove("Yahweh")
                ld["alternatives"] = alts_str
            # Update rationale
            rat = str(ld.get("rationale") or "")
            if "the LORD" in rat or "the LORD" in rat or "Jewish reverence" in rat:
                ld["rationale"] = NEW_RATIONALE
                changed = True

    # 3. theological_decisions — find divine name entry/-ies
    for td in (data.get("theological_decisions") or []):
        if not isinstance(td, dict):
            continue
        issue = str(td.get("issue") or "").lower()
        if TETRAGRAMMATON in str(td.get("issue") or "") or "divine name" in issue or "rendering the" in issue:
            cr = str(td.get("chosen_reading") or "")
            new_cr, c = _replace_lord(cr)
            if not c and cr.strip().upper() in ("THE LORD", "LORD"):
                new_cr = "Yahweh"
                c = True
            if c:
                td["chosen_reading"] = new_cr
                changed = True
            rat = str(td.get("rationale") or "")
            if "the LORD" in rat or "Jewish reverence" in rat:
                td["rationale"] = NEW_THEOLOGICAL_RATIONALE
                changed = True
            # Update doctrine_reference
            dr = str(td.get("doctrine_reference") or "")
            if "the LORD" in dr:
                td["doctrine_reference"] = "DOCTRINE.md: Contested terms — יְהוָה YHWH → Yahweh"
                changed = True

    if not changed:
        return False

    if dry_run:
        return True

    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--book", default=None, help="restrict to one book directory name (e.g. psalms)")
    ap.add_argument("--testament", default=None, help="restrict to one testament (ot, deuterocanon)")
    args = ap.parse_args()

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # prevent line-wrapping in text fields

    testaments = [args.testament] if args.testament else ["ot", "deuterocanon"]

    paths: list[pathlib.Path] = []
    for testament in testaments:
        base = REPO_ROOT / "translation" / testament
        if not base.exists():
            continue
        if args.book:
            book_dirs = [base / args.book]
        else:
            book_dirs = [d for d in sorted(base.iterdir()) if d.is_dir()]
        for book_dir in book_dirs:
            if not book_dir.is_dir():
                continue
            paths.extend(sorted(book_dir.rglob("*.yaml")))

    print(f"scanning {len(paths)} files...")
    updated = 0
    sample = []
    for p in paths:
        try:
            changed = process_file(p, dry_run=args.dry_run, yaml=yaml)
        except Exception as exc:
            print(f"[warn] {p.relative_to(REPO_ROOT)}: {exc}", file=sys.stderr)
            continue
        if changed:
            updated += 1
            if len(sample) < 5:
                sample.append(str(p.relative_to(REPO_ROOT)))

    label = "would update" if args.dry_run else "updated"
    print(f"\n{label}: {updated} / {len(paths)} files")
    if sample:
        print("sample files:")
        for s in sample:
            print(f"  {s}")

    if args.dry_run:
        print("\n(dry run — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
