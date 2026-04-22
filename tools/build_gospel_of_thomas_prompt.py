#!/usr/bin/env python3
"""build_gospel_of_thomas_prompt.py — assemble a strict Coptic-aware
prompt for re-drafting one Gospel of Thomas saying.

Reads the existing saying YAML (which already embeds the Coptic
source text from the Coptic Scriptorium Dilley 2025 edition), the
project overview prompt, and the author-intent book context. Returns
a system+user prompt pair ready for a chat-completions call.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "gospel_of_thomas"
PROMPT_DIR = REPO_ROOT / "sources" / "nag_hammadi" / "prompts" / "gospel_of_thomas"
BOOK_CONTEXT = REPO_ROOT / "tools" / "prompts" / "book_contexts" / "gospel_of_thomas.md"
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"


@dataclass
class ThomasPromptBundle:
    saying: int
    yaml_path: pathlib.Path
    yaml_data: dict[str, Any]
    system_prompt: str
    user_prompt: str


def _doctrinal_excerpts() -> str:
    """Short extracts from DOCTRINE.md + PHILOSOPHY.md that guide any
    Cartha Open Bible drafter. Keep brief to save tokens."""
    extracts = []
    if DOCTRINE_PATH.exists():
        text = DOCTRINE_PATH.read_text(encoding="utf-8")
        # Pull a small summary section if marked, else first ~800 chars
        extracts.append("### DOCTRINE (excerpt)\n\n" + text[:1200])
    if PHILOSOPHY_PATH.exists():
        text = PHILOSOPHY_PATH.read_text(encoding="utf-8")
        extracts.append("### PHILOSOPHY (excerpt)\n\n" + text[:800])
    return "\n\n".join(extracts) if extracts else ""


def _overview_prompt() -> str:
    p = PROMPT_DIR / "overview.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _book_context() -> str:
    return BOOK_CONTEXT.read_text(encoding="utf-8") if BOOK_CONTEXT.exists() else ""


def _segment_prompt(saying: int) -> str:
    """Per-saying guidance if one exists in sources/nag_hammadi/prompts/gospel_of_thomas/segments."""
    p = PROMPT_DIR / "segments" / f"{saying:03d}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


STRICT_CORRECTION_BLOCK = """\
## CRITICAL: Coptic-grammar strictness

An earlier draft of this text confused Coptic morphology and
produced hallucinated verses. You must NOT do that. Specifically:

1. Every lexical choice you make must cite **Crum's Coptic
   Dictionary** (by head-word, and page if you know it) or another
   named Coptic lexicon (Lambdin, Layton, Plumley).
2. Distinguish carefully:
   - ⲙⲛⲛⲥⲁ (preposition: 'after')
   - ⲙⲡⲁⲧⲉ- (negative temporal prefix: 'not yet')
   - ⲉⲓⲥ (deictic: 'behold')
   - ⲉⲛⲉ- (conditional particle)
   - ⲧⲣⲉ- (causative infinitive prefix)
3. Coptic circumstantial perfect (ⲉϥ-/ⲉⲥ-/ⲉⲩ- + sT stem)
   attributively modifies the referent; do NOT drop the attributive
   meaning.
4. ⲟⲩⲁ ⲟⲩⲱⲧ ('one / single') and ⲙⲟⲛⲁⲭⲟⲥ ('solitary') are
   theologically loaded in Thomas. Preserve them — do not paraphrase
   away.
5. The negative existential ⲙⲛ is NOT the conjunction ⲙⲛ̄. Read
   from context.
6. If the Coptic is genuinely ambiguous, render conservatively and
   flag the ambiguity in a footnote with a Crum citation.

## CRITICAL: do not assimilate to canonical Gospels

Where Thomas has a saying that parallels Matthew / Mark / Luke / John,
the English must preserve any **divergence** in Thomas's wording.
Do not substitute the canonical Gospel's English when the Coptic
says something different. Differences between Thomas and the
canonical parallels are Thomas's authorial choice, not errors to
be smoothed.

## P.Oxy. Greek fragments

Sayings 1, 2, 3, 4, 5, 6, 7, 24, 26, 27, 28, 29, 30, 31, 32, 33,
36, 37, 38, 39, 77 have partial Greek witness in P.Oxy. 1, 654, 655.
Where the Greek fragment survives and differs from the Coptic:
- Note the variant in a footnote with the P.Oxy. number.
- Do NOT silently follow the Greek and drop the Coptic reading
  without comment — both are textual witnesses.
"""


def build_prompt(saying: int) -> ThomasPromptBundle:
    """Build the redraft prompt for a specific saying number."""
    yaml_path = TRANSLATION_ROOT / f"{saying:03d}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(yaml_path)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    source = data.get("source") or {}
    coptic_orig = source.get("coptic_orig") or ""
    coptic_norm = source.get("coptic_norm") or ""
    lines = source.get("lines") or []
    greek_witnesses = source.get("greek_overlap_witnesses") or []
    codex_pages = source.get("codex_pages") or []

    # Current draft — for context (so the redrafter can see what to fix)
    current_translation = (data.get("translation") or {}).get("text") or ""

    # Compose system prompt
    parts_system: list[str] = []
    parts_system.append(_overview_prompt())
    parts_system.append(STRICT_CORRECTION_BLOCK)
    parts_system.append("## AUTHOR-INTENT CONTEXT\n\n" + _book_context())
    parts_system.append(_doctrinal_excerpts())
    seg = _segment_prompt(saying)
    if seg:
        parts_system.append("## SAYING-SPECIFIC GUIDANCE\n\n" + seg)
    parts_system.append("""## Output format (strict)

Submit your draft by calling the function `submit_thomas_draft` exactly
once. No other output. Every lexical choice must appear in
`lexical_decisions` with a Crum or named-lexicon citation.""")

    system_prompt = "\n\n---\n\n".join(p for p in parts_system if p.strip())

    # User payload
    user_lines = [
        f"# Saying {saying}",
        "",
        "## Coptic source (original orthography — from Coptic Scriptorium / Dilley 2025)",
        "",
        coptic_orig or "(missing)",
        "",
        "## Coptic source (normalized lemmatization)",
        "",
        coptic_norm or "(missing)",
        "",
    ]
    if lines:
        user_lines.append("## Per-line breakdown")
        user_lines.append("")
        for ln in lines:
            lb = ln.get("lb", "?")
            page = ln.get("codex_page", "?")
            orig = ln.get("orig", "")
            norm = ln.get("norm", "")
            user_lines.append(f"- lb {lb} ({page}): orig: `{orig}`  /  norm: `{norm}`")
        user_lines.append("")
    if codex_pages:
        user_lines.append(f"Codex page(s): {', '.join(codex_pages)}")
        user_lines.append("")
    if greek_witnesses:
        user_lines.append("## Greek overlap witnesses")
        user_lines.append("")
        for w in greek_witnesses:
            user_lines.append(f"- {w}")
        user_lines.append("")
    if current_translation:
        user_lines.append("## Current draft (under review — improve or replace)")
        user_lines.append("")
        user_lines.append(current_translation)
        user_lines.append("")

    user_lines.append(
        "## Task\n\n"
        "Produce the best possible English draft for this saying, "
        "grounded strictly in the Coptic source above. Submit via the "
        "function call."
    )

    user_prompt = "\n".join(user_lines)

    return ThomasPromptBundle(
        saying=saying,
        yaml_path=yaml_path,
        yaml_data=data,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
