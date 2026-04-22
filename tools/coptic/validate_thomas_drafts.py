#!/usr/bin/env python3
"""validate_thomas_drafts.py — structural QA for Gospel of Thomas draft YAMLs."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COPTIC_JSONL = REPO_ROOT / "sources/nag_hammadi/texts/gospel_of_thomas/coptic.jsonl"
TRANSLATION_ROOT = REPO_ROOT / "translation/extra_canonical/gospel_of_thomas"

REQUIRED_TOP_LEVEL = {
    "id",
    "reference",
    "unit",
    "book",
    "source",
    "translation",
    "lexical_decisions",
    "textual_note",
    "ai_draft",
}
VALID_PHILOSOPHIES = {"formal", "dynamic", "optimal-equivalence"}


def expected_ids() -> list[str]:
    with COPTIC_JSONL.open() as fh:
        return [json.loads(line)["saying_id"] for line in fh if line.strip()]


def has_greek_overlap(saying_id: str) -> bool:
    if saying_id == "subtitle":
        return False
    try:
        num = int(saying_id)
    except ValueError:
        return False
    return (1 <= num <= 7) or num == 24 or (26 <= num <= 33) or (36 <= num <= 39)


def validate_one(saying_id: str) -> list[str]:
    errors: list[str] = []
    path = TRANSLATION_ROOT / f"{saying_id}.yaml"
    if not path.exists():
        return [f"{saying_id}: missing file"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"{saying_id}: YAML parse failed: {exc}"]
    if not isinstance(data, dict):
        return [f"{saying_id}: top-level YAML is not an object"]

    missing = sorted(REQUIRED_TOP_LEVEL - set(data))
    if missing:
        errors.append(f"{saying_id}: missing top-level keys: {', '.join(missing)}")

    translation = data.get("translation") or {}
    if not str(translation.get("text", "")).strip():
        errors.append(f"{saying_id}: translation.text is empty")
    if translation.get("philosophy") not in VALID_PHILOSOPHIES:
        errors.append(f"{saying_id}: invalid translation philosophy")

    lexical = data.get("lexical_decisions")
    if not isinstance(lexical, list) or not lexical:
        errors.append(f"{saying_id}: lexical_decisions missing or empty")

    if not str(data.get("textual_note", "")).strip():
        errors.append(f"{saying_id}: textual_note is empty")

    source = data.get("source") or {}
    if not str(source.get("coptic_orig", "")).strip():
        errors.append(f"{saying_id}: source.coptic_orig is empty")
    if not isinstance(source.get("lines"), list) or not source.get("lines"):
        errors.append(f"{saying_id}: source.lines missing or empty")

    ai_draft = data.get("ai_draft") or {}
    for key in ("model_id", "model_version", "prompt_id", "prompt_sha256", "output_hash"):
        if not str(ai_draft.get(key, "")).strip():
            errors.append(f"{saying_id}: ai_draft.{key} is empty")

    if has_greek_overlap(saying_id) and "greek_overlap_decision" not in data:
        errors.append(f"{saying_id}: missing greek_overlap_decision")

    return errors


def main() -> int:
    expected = expected_ids()
    errors: list[str] = []
    for saying_id in expected:
        errors.extend(validate_one(saying_id))
    if errors:
        print("\n".join(errors))
        print(f"\nFAILED: {len(errors)} issue(s) across {len(expected)} expected files.")
        return 1
    print(f"OK: validated {len(expected)} Gospel of Thomas draft files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
