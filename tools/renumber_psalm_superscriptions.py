#!/usr/bin/env python3
"""renumber_psalm_superscriptions.py

Fix psalm verse numbering so it matches the English Bible convention:
superscriptions are headers (verse 0), not verse 1.

Two error patterns exist in the drafted files:

  STANDALONE — verse 001 is entirely a superscription, no content:
    001.yaml: "For the choir director. A psalm of David."     ← pure header
    002.yaml: "Blessed is the one who considers the poor…"   ← actual v1

  FUSED — verse 001 has the superscription prefix fused with the first
  content sentence (the draft model didn't separate them):
    001.yaml: "A psalm of David. Yahweh is my shepherd; I will not lack."

Fix applied:
  STANDALONE:  rename 001 → 000, 002 → 001, 003 → 002, etc.
  FUSED:       split verse 001 text; create 000.yaml (superscription part),
               rewrite 001.yaml (content part only).

Run:
  python3 tools/renumber_psalm_superscriptions.py --dry-run   # list only
  python3 tools/renumber_psalm_superscriptions.py             # apply
  python3 tools/renumber_psalm_superscriptions.py --psalm 41  # one psalm
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

from ruamel.yaml import YAML

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PSALMS_DIR = REPO_ROOT / "translation" / "ot" / "psalms"

# ── Content detection ──────────────────────────────────────────────────────
# A verse has *content* if it contains a main predication — Yahweh/God doing
# something, first-person prayer, imperatives of praise/lament, beatitudes, etc.
# Superscription clauses are purely nominal/attributive with no such predicate.

_CONTENT_RE = re.compile(
    r"""(
        # Vocative address to God — always content, never superscription
        \bO\s+(Yahweh|God|Lord|my\s+God)\b
        |\bYahweh,\s+(my|our|your|O|hear|answer|arise)\b
        # Yahweh / God as subject with any predicate
        |\bYahweh\s+(is\b|are\b|will\b|shall\b|has\b|have\b|was\b|were\b
                    |my\b|your\b|comes?\b|came\b|speaks?\b|spoke\b
                    |delivers?\b|delivered\b|saves?\b|saved\b
                    |reigns?\b|reigned\b|dwells?\b|stands?\b|judges?\b
                    |loves?\b|hears?\b|sees?\b|gives?\b|takes?\b)
        |\bGod\s+(is\b|are\b|will\b|has\b|my\b|your\b|hears?\b|sees?\b
                  |stands?\b|reigns?\b|judges?\b|speaks?\b|gives?\b)
        # First-person subject (prayer / testimony voice)
        |\bI\s+(will\b|have\b|am\b|was\b|shall\b|call\b|cry\b|praise\b
                |lift\b|trust\b|take\b|seek\b|wait\b|put\b|rest\b
                |declare\b|love\b|say\b|know\b|believe\b|walk\b|fear\b)
        |\bmy\s+(soul\b|heart\b|strength\b|God\b|King\b|help\b
                 |refuge\b|rock\b|shield\b|portion\b|prayer\b|cry\b)
        # Second-person address / imperatives to God
        |\b(Hear\s+(my|me|o|a)\b|Save\s+me\b|Help\s+me\b
            |Deliver\s+me\b|Vindicate\s+me\b|Arise\b|Awake\b
            |Contend\b|Give\s+(your|me|ear|thanks|glory)\b
            |Do\s+not\s+(forsake|hide|forget|be\b)\b
            |Answer\s+me\b|Look\s+(on|upon)\b)
        # Lament / question openers
        |\b(How\s+long\b|Why\s+(do|have|has|did|O)\b
            |Blessed\s+(is|are)\b
            |Shout\s+(for|to)\b|Praise\s+(the|Yahweh|God)\b
            |Sing\s+(to|a)\b)
        # Doctrinal / narrative statements
        |\bThe\s+(earth\b|heavens\b|nations\b|fool\b|righteous\b|wicked\b
                  |Mighty\s+One\b|LORD\s+is\b)
        |\bAll\s+the\s+(nations\b|earth\b|peoples\b)
        |\bSurely\s+(God|Yahweh)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Sentence starters that indicate the clause is attributive (superscription),
# not predicative (content). Used when splitting fused verses.
_SUPER_CLAUSE_START = re.compile(
    r"""^(
        for\s+the\s+(choir\s+director|choirmaster|director\s+of\s+music)
        |a\s+(psalm|song|prayer|miktam|maskil|shiggaion|hymn|petition)
        |a\s+song\s+of\s+(ascents|degrees)
        |of\s+(david|asaph|solomon|moses|ethan|heman)
        |of\s+the\s+sons\s+of\s+korah|by\s+the\s+sons\s+of\s+korah
        |according\s+to\b
        |on\s+the\s+(sheminith|gittith|alamoth)
        |with\s+(stringed\s+instruments|flutes)
        |when\s+(he|david|saul|the\s+philistines|joab)\b
        |for\s+(remembrance|the\s+memorial\s+offering|memorial)
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)


def is_superscription(text: str) -> bool:
    """Return True if text is entirely a superscription (no content verse)."""
    return not _has_content(text.strip()) if text.strip() else False


def _has_content(text: str) -> bool:
    # Primary: explicit content-marker regex
    if _CONTENT_RE.search(text):
        return True
    # Secondary: split into period-delimited clauses; if ANY clause cannot be
    # identified as a superscription phrase, the verse contains content.
    # This catches past-tense forms ("I called", "he answered"), narrative
    # openers ("By the rivers of", "His foundation is"), etc.
    clauses = [c.strip().rstrip(".;:,—") for c in re.split(r"\.\s+", text) if c.strip()]
    for clause in clauses:
        if clause and not _SUPER_CLAUSE_START.match(clause):
            return True
    return False


def classify_verse1(text: str) -> str:
    """
    Returns:
      'standalone'  — entire verse is a superscription, no content
      'fused'       — superscription prefix + content in same verse
      'content'     — no superscription, pure content (Ps 1, 2, etc.)
    """
    t = text.strip()
    if not t:
        return "content"

    if not _has_content(t):
        return "standalone"

    # Has content — check if it also starts with a superscription clause
    # Split by ". " to get sentence fragments
    first_clause = re.split(r"\.\s+", t)[0].strip()
    if _SUPER_CLAUSE_START.match(first_clause):
        return "fused"
    return "content"


def split_fused(text: str) -> tuple[str, str]:
    """
    Split a fused verse text into (superscription, content).
    E.g. "A psalm of David. Yahweh is my shepherd; I will not lack."
      → ("A psalm of David.", "Yahweh is my shepherd; I will not lack.")
    """
    # Split on period+space boundaries
    parts = re.split(r"(\.\s+)", text)
    # Reassemble into full sentences: ['A psalm of David', '. ', 'Yahweh is...']
    sentences: list[str] = []
    i = 0
    while i < len(parts):
        s = parts[i]
        if i + 1 < len(parts) and parts[i + 1].startswith("."):
            sentences.append(s + parts[i + 1].rstrip())
            i += 2
        else:
            if s.strip():
                sentences.append(s)
            i += 1

    super_parts: list[str] = []
    content_parts: list[str] = []
    in_content = False
    for sent in sentences:
        if in_content:
            content_parts.append(sent)
            continue
        clause = sent.rstrip(". ")
        if not _has_content(sent) and _SUPER_CLAUSE_START.match(clause.strip()):
            super_parts.append(sent.rstrip() if sent.endswith(". ") else sent)
        else:
            in_content = True
            content_parts.append(sent)

    super_text = " ".join(super_parts).strip()
    content_text = " ".join(content_parts).strip()
    # Ensure superscription ends with a period
    if super_text and not super_text.endswith("."):
        super_text += "."
    return super_text, content_text


def _update_fields(data: dict, new_verse: int) -> None:
    """Update id, reference, and verse-number fields to new_verse."""
    id_val = str(data.get("id") or "")
    new_id = re.sub(r"(\bPSA\.\d+\.)(\d+)$", lambda m: f"{m.group(1)}{new_verse}", id_val, flags=re.I)
    if new_id != id_val:
        data["id"] = new_id
    ref_val = str(data.get("reference") or "")
    new_ref = re.sub(r"(\bPsalms\s+\d+:)(\d+)\b", lambda m: f"{m.group(1)}{new_verse}", ref_val)
    if new_ref != ref_val:
        data["reference"] = new_ref


def process_psalm(psalm_dir: pathlib.Path, dry_run: bool, yaml: YAML
                  ) -> tuple[str, str] | None:
    """Return (psalm_num, type) if action taken, else None."""
    v1_path = psalm_dir / "001.yaml"
    if not v1_path.exists():
        return None

    raw = v1_path.read_text(encoding="utf-8")
    data = yaml.load(raw)
    if not isinstance(data, dict):
        return None

    tr = data.get("translation") or {}
    v1_text = (tr.get("text") or "").strip()
    kind = classify_verse1(v1_text)
    psalm_num = psalm_dir.name

    if kind == "content":
        return None

    if dry_run:
        preview = v1_text[:70]
        print(f"  Ps {psalm_num} [{kind}]: \"{preview}\"")
        return psalm_num, kind

    if kind == "standalone":
        # Rename 001 → 000, 002 → 001, etc. (ascending order: each target slot was
        # just vacated by the previous step, so no collision)
        verse_files = sorted(psalm_dir.glob("*.yaml"), key=lambda p: int(p.stem))
        for vf in verse_files:
            old_num = int(vf.stem)
            new_num = old_num - 1
            vdata = yaml.load(vf.read_text(encoding="utf-8"))
            _update_fields(vdata, new_num)
            if new_num == 0:
                vdata["is_superscription"] = True
            new_path = psalm_dir / f"{new_num:03d}.yaml"
            with new_path.open("w", encoding="utf-8") as fh:
                yaml.dump(vdata, fh)
            vf.unlink()

    elif kind == "fused":
        super_text, content_text = split_fused(v1_text)
        if not super_text or not content_text:
            # Splitting failed — leave for manual review
            print(f"  [SKIP Ps {psalm_num}] split failed: super={repr(super_text[:40])}, "
                  f"content={repr(content_text[:40])}", file=sys.stderr)
            return None

        # Create verse 000 (superscription only)
        super_data = yaml.load(raw)  # copy of v1 as base
        super_data["is_superscription"] = True
        super_data.setdefault("translation", {})["text"] = super_text
        _update_fields(super_data, 0)
        # Remove fields that belong to the content verse only
        for k in ("lexical_decisions", "theological_decisions", "ai_draft", "revision_pass"):
            super_data.pop(k, None)
        v0_path = psalm_dir / "000.yaml"
        with v0_path.open("w", encoding="utf-8") as fh:
            yaml.dump(super_data, fh)

        # Rewrite verse 001 with content text only
        data["translation"]["text"] = content_text
        with v1_path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

    return psalm_num, kind


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--psalm", type=int, default=None)
    args = ap.parse_args()

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096

    dirs = sorted(PSALMS_DIR.iterdir(), key=lambda d: int(d.name) if d.name.isdigit() else 999)
    if args.psalm:
        dirs = [PSALMS_DIR / f"{args.psalm:03d}"]

    standalone_count = 0
    fused_count = 0
    skipped = 0

    if args.dry_run:
        print("=== STANDALONE (entire v1 is superscription) ===")
    for d in dirs:
        if not d.is_dir():
            continue
        result = process_psalm(d, dry_run=args.dry_run, yaml=yaml)
        if result:
            _, kind = result
            if kind == "standalone":
                standalone_count += 1
            elif kind == "fused":
                fused_count += 1
        elif args.dry_run:
            pass

    if args.dry_run:
        # Second pass for fused
        print(f"\n=== FUSED (superscription prefix + content in v1) ===")
        for d in dirs:
            if not d.is_dir():
                continue
            v1 = d / "001.yaml"
            if not v1.exists():
                continue
            try:
                data = yaml.load(v1.read_text(encoding="utf-8")) or {}
                text = ((data.get("translation") or {}).get("text") or "").strip()
                if classify_verse1(text) == "fused":
                    sup, con = split_fused(text)
                    print(f"  Ps {d.name}: SUPER=\"{sup[:50]}\" | CONTENT=\"{con[:50]}\"")
            except Exception:
                pass

    label = "would fix" if args.dry_run else "fixed"
    if not args.dry_run:
        print(f"\n{label}: {standalone_count} standalone + {fused_count} fused psalms")
    else:
        print(f"\n(dry run — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
