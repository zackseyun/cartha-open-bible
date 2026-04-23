#!/usr/bin/env python3
"""check_regressions.py — Regression guard for Cartha Open Bible verse YAMLs.

Scans changed verse YAMLs (from git diff) for known regression patterns
defined in tools/known_regressions.yaml. Exits non-zero if any regression
is found — intended for use as a pre-commit hook.

Usage:
    python3 tools/check_regressions.py                  # check git-staged files
    python3 tools/check_regressions.py --all            # check all verse YAMLs
    python3 tools/check_regressions.py --files a.yaml   # check specific files
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REGRESSIONS_FILE = REPO_ROOT / "tools" / "known_regressions.yaml"

# Inline regression rules — single source of truth alongside known_regressions.yaml.
# Each rule: (pattern_in_translation_text, forbidden_word, correct_word, policy_note)
# We check translation.text only — not footnotes or rationale fields.
RULES = [
    {
        "id": "christos-as-christ",
        "check": lambda text: "\bChrist\b" in text or _word_in(text, "Christ"),
        "description": 'δοῦλος Χριστός rendered as "Christ" instead of "Messiah"',
        "details": (
            'Found "Christ" in translation.text. '
            "COB policy: Χριστός → Messiah. "
            'Never use "Christ" in translation.text. '
            "See DOCTRINE.md §Contested Terms."
        ),
        "nt_only": True,  # Χριστός only occurs in NT + deuterocanon
    },
    {
        "id": "doulos-as-servant",
        "check_wrong": "servant",
        "check_correct": "slave",
        "description": 'δοῦλος rendered as "servant" instead of "slave"',
        "details": (
            'Found "servant" where source is δοῦλος/עֶבֶד. '
            "COB policy: δοῦλος → slave (bonded ownership context). "
            '"servant" is only correct for διάκονος/ὑπηρέτης. '
            "See DOCTRINE.md §Contested Terms."
        ),
        "nt_only": False,
    },
]

# NT books (by directory name) — used for christos-as-christ which is NT-only
NT_BOOKS = {
    "matthew", "mark", "luke", "john", "acts", "romans",
    "1_corinthians", "2_corinthians", "galatians", "ephesians",
    "philippians", "colossians", "1_thessalonians", "2_thessalonians",
    "1_timothy", "2_timothy", "titus", "philemon", "hebrews",
    "james", "1_peter", "2_peter", "1_john", "2_john", "3_john",
    "jude", "revelation",
}


def _word_in(text: str, word: str) -> bool:
    import re
    return bool(re.search(rf'\b{re.escape(word)}\b', text))


def is_nt(path: pathlib.Path) -> bool:
    parts = path.parts
    if "nt" in parts:
        return True
    # deuterocanon sometimes has NT-era texts but Χριστός doesn't appear there
    return False


def check_file(path: pathlib.Path) -> list[dict]:
    """Check one verse YAML for regression patterns. Returns list of violations."""
    violations = []
    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except Exception as e:
        return [{"file": str(path), "rule": "parse_error", "details": str(e)}]

    if not isinstance(data, dict):
        return []

    translation = data.get("translation") or {}
    text = str(translation.get("text") or "").strip()
    if not text:
        return []

    nt = is_nt(path)

    # Rule 1: Χριστός → "Christ" regression (NT only)
    if nt and _word_in(text, "Christ"):
        violations.append({
            "file": str(path.relative_to(REPO_ROOT)),
            "rule": "christos-as-christ",
            "translation_text": text[:120],
            "details": (
                'Forbidden: "Christ" found in NT translation text. '
                "COB policy requires Χριστός → Messiah. "
                "See DOCTRINE.md §Contested Terms and tools/known_regressions.yaml."
            ),
        })

    # Rule 2: δοῦλος → "servant" regression
    # Heuristic: if source text contains δοῦλος or עֶבֶד AND translation has "servant"
    # We check the source field for the Greek/Hebrew term.
    source = data.get("source") or {}
    source_text = str(source.get("text") or "")
    if "δοῦλ" in source_text or "עֶבֶד" in source_text or "עֶ֫בֶד" in source_text:
        if _word_in(text, "servant"):
            violations.append({
                "file": str(path.relative_to(REPO_ROOT)),
                "rule": "doulos-as-servant",
                "translation_text": text[:120],
                "details": (
                    'Forbidden: "servant" found where source has δοῦλος/עֶבֶד. '
                    "COB policy requires → slave. "
                    '"servant" only for διάκονος/ὑπηρέτης. '
                    "See DOCTRINE.md §Contested Terms and tools/known_regressions.yaml."
                ),
            })

    return violations


def get_staged_yaml_files() -> list[pathlib.Path]:
    """Return list of staged YAML files under translation/."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return []
    paths = []
    for line in out.splitlines():
        p = REPO_ROOT / line
        if p.suffix == ".yaml" and "translation/" in line:
            paths.append(p)
    return paths


def get_all_yaml_files() -> list[pathlib.Path]:
    translation_root = REPO_ROOT / "translation"
    return sorted(translation_root.rglob("*.yaml"))


def main() -> int:
    parser = argparse.ArgumentParser(description="COB regression guard")
    parser.add_argument("--all", action="store_true", help="Check all verse YAMLs (not just staged)")
    parser.add_argument("--files", nargs="*", help="Check specific files")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only print violations, no progress")
    args = parser.parse_args()

    if args.files:
        paths = [pathlib.Path(f).resolve() for f in args.files]
    elif args.all:
        paths = get_all_yaml_files()
        if not args.quiet:
            print(f"Checking all {len(paths)} verse YAMLs...")
    else:
        paths = get_staged_yaml_files()
        if not args.quiet:
            print(f"Checking {len(paths)} staged YAML files...")

    if not paths:
        if not args.quiet:
            print("No YAML files to check.")
        return 0

    all_violations: list[dict] = []
    for path in paths:
        violations = check_file(path)
        all_violations.extend(violations)

    if not all_violations:
        if not args.quiet:
            print("OK — no regressions found.")
        return 0

    print(f"\n{'='*60}")
    print(f"REGRESSION CHECK FAILED — {len(all_violations)} violation(s) found")
    print(f"{'='*60}")
    for v in all_violations:
        print(f"\n  FILE:  {v['file']}")
        print(f"  RULE:  {v['rule']}")
        print(f"  TEXT:  {v.get('translation_text', '')!r}...")
        print(f"  WHY:   {v['details']}")
    print(f"\n{'='*60}")
    print("Fix these issues before committing.")
    print("Reference: tools/known_regressions.yaml")
    print(f"{'='*60}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
