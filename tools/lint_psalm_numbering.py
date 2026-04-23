#!/usr/bin/env python3
"""lint_psalm_numbering.py — guard against superscription-as-verse-1 regressions.

Fails with exit code 1 if any Psalm verse 001 looks like a pure superscription
(i.e., contains only header text like "For the choir director. A psalm of David."
with no actual content). This enforces the English numbering convention where
superscriptions are verse 0 (a header), not verse 1.

Run as a pre-commit check or in CI:
  python3 tools/lint_psalm_numbering.py          # exits 0 if clean
  python3 tools/lint_psalm_numbering.py --strict # also checks is_superscription on v000
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PSALMS_DIR = REPO_ROOT / "translation" / "ot" / "psalms"

# Import detection from the normalization script to keep logic in one place
sys.path.insert(0, str(REPO_ROOT / "tools"))
from renumber_psalm_superscriptions import is_superscription


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="Also verify verse 000 files carry is_superscription: true")
    args = ap.parse_args()

    errors: list[str] = []

    for psalm_dir in sorted(PSALMS_DIR.iterdir()):
        if not psalm_dir.is_dir():
            continue
        psalm_num = psalm_dir.name

        # Primary check: verse 001 must NOT be a superscription
        v1 = psalm_dir / "001.yaml"
        if v1.exists():
            try:
                data = yaml.safe_load(v1.read_text(encoding="utf-8")) or {}
                text = (data.get("translation") or {}).get("text") or ""
                if is_superscription(text):
                    errors.append(
                        f"Psalm {psalm_num}: verse 001 looks like a superscription: "
                        f'"{text[:80]}" — run tools/renumber_psalm_superscriptions.py'
                    )
            except Exception as exc:
                errors.append(f"Psalm {psalm_num}/001.yaml: parse error — {exc}")

        # Strict check: verse 000 files must have is_superscription: true
        if args.strict:
            v0 = psalm_dir / "000.yaml"
            if v0.exists():
                try:
                    data = yaml.safe_load(v0.read_text(encoding="utf-8")) or {}
                    if not data.get("is_superscription"):
                        errors.append(
                            f"Psalm {psalm_num}: verse 000 is missing is_superscription: true"
                        )
                except Exception as exc:
                    errors.append(f"Psalm {psalm_num}/000.yaml: parse error — {exc}")

    if errors:
        print("PSALM NUMBERING ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        print(f"\n{len(errors)} error(s) found.")
        return 1

    psalm_count = sum(1 for d in PSALMS_DIR.iterdir() if d.is_dir())
    print(f"✓ Psalm numbering clean ({psalm_count} psalms checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
