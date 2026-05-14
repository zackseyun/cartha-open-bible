#!/usr/bin/env python3
"""agentic_revise.py — per-verse agentic revision pass for POB.

A multi-turn reviewer agent that applies the framework in
tools/prompts/revision_policy.md. Each verse gets its own agent loop
with information-gathering tools (lookup_doctrine, lookup_occurrences,
lookup_book_context, read_drafter_reasoning) and one of two terminal
actions (submit_revision, submit_unchanged).

The harness is deliberately minimal in this first cut:
- One reviewer per verse, no sub-agents yet.
- Dry-run by default — writes a JSON manifest of proposed changes for
  human review before any YAML is touched.
- Audit-only mode finds candidate verses without calling the model.

Design rationale and rollout plan: tools/AGENTIC_REVISION.md.

Usage:
    # 0. (Optional, deterministic) Backfill `lemma` fields onto
    #    lexical_decisions entries by extracting from rationale text.
    #    Dry-run unless --apply-backfill is also set.
    python3 tools/agentic_revise.py --backfill-lemmas --out /tmp/lemma.json
    python3 tools/agentic_revise.py --backfill-lemmas --apply-backfill \\
        --out /tmp/lemma.json

    # 1. Find candidate verses with contested terms or non-trivial
    #    lexical_decisions — no LLM calls.
    python3 tools/agentic_revise.py --audit-only --out /tmp/audit.json

    # 2. Dry-run reviewer over the audit set — produces a manifest of
    #    proposed changes; does NOT modify YAML.
    python3 tools/agentic_revise.py --from-audit /tmp/audit.json \\
        --limit 20 --out /tmp/proposals.json

    # 3. Single-verse dry-run (debugging the framework on one case).
    python3 tools/agentic_revise.py --verse \\
        translation/nt/1_peter/005/008.yaml --out /tmp/one.json

    # 4. Apply approved proposals (writes YAMLs + revisions[] entries).
    python3 tools/agentic_revise.py --apply /tmp/proposals.json

Env:
    ANTHROPIC_API_KEY    — required for reviewer calls.
    ANTHROPIC_MODEL      — default claude-sonnet-4-6 (override for opus).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
DOCTRINE_FILE = REPO_ROOT / "DOCTRINE.md"
POLICY_FILE = REPO_ROOT / "tools" / "prompts" / "revision_policy.md"
INDEX_CACHE = pathlib.Path("/tmp/pob_lemma_index.json")
AUDIT_LOG_DIR = REPO_ROOT / "state" / "agentic_pass"  # per-decision trace

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANALYST_MODEL = os.environ.get("ANTHROPIC_ANALYST_MODEL", "claude-sonnet-4-6")
MAX_ITERATIONS = 6      # per-verse main reviewer cap
MAX_ANALYST_ITERATIONS = 4  # sub-agent cap (must be lower than main)


# ──────────────────────────────────────────────────────────────────
# DOCTRINE.md contested-terms parser
# ──────────────────────────────────────────────────────────────────

def parse_doctrine_contested_terms() -> dict[str, dict[str, str]]:
    """Parse the contested-terms table in DOCTRINE.md.

    Returns: { source_word_normalized: {greek, default, alternatives, rationale} }
    Keyed by both the Greek/Hebrew form and the transliterated form
    (so `lookup_doctrine("νήφω")` and `lookup_doctrine("nepho")` both hit).
    """
    if not DOCTRINE_FILE.exists():
        return {}
    text = DOCTRINE_FILE.read_text(encoding="utf-8")

    # Find the contested-terms table: a markdown table after the
    # "## Contested terms" header.
    m = re.search(r"## Contested terms\s*\n(.*?)(?=\n## )", text, re.DOTALL)
    if not m:
        return {}
    section = m.group(1)

    out: dict[str, dict[str, str]] = {}
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        # Skip header and separator
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if cells[0].lower().startswith("greek") or set(cells[0]) <= {"-", " "}:
            continue

        # cells[0] looks like "Χριστός *Christos*" — split into Greek + translit
        head = cells[0]
        greek_match = re.match(r"([^\s\*]+)", head)
        translit_match = re.search(r"\*([^*]+)\*", head)
        greek = greek_match.group(1) if greek_match else head
        translit = translit_match.group(1) if translit_match else ""

        entry = {
            "source_word": greek,
            "transliteration": translit,
            "default": cells[1],
            "alternatives_considered": cells[2],
            "rationale": cells[3] if len(cells) > 3 else "",
        }
        out[greek] = entry
        if translit:
            out[translit.lower()] = entry

    return out


# ──────────────────────────────────────────────────────────────────
# Lemma occurrence index (built from translation/ YAMLs)
# ──────────────────────────────────────────────────────────────────

def build_lemma_index(force: bool = False) -> dict[str, list[dict]]:
    """Walk translation/ and index every source_word from lexical_decisions.

    When a `lemma` field is present on the lexical_decisions entry, the
    occurrence is indexed under BOTH the inflected `source_word` and the
    `lemma` — so `lookup_occurrences("νήφω")` and
    `lookup_occurrences("νήψατε")` both hit the same verse.

    Returns: { key: [ {verse_id, reference, chosen, source_word, lemma, rationale_short}, ... ] }
    Cached at /tmp/pob_lemma_index.json to avoid full re-walks.
    """
    if INDEX_CACHE.exists() and not force:
        try:
            return json.loads(INDEX_CACHE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    index: dict[str, list[dict]] = defaultdict(list)
    for path in TRANSLATION_ROOT.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        verse_id = data.get("id") or path.stem
        reference = data.get("reference") or verse_id
        for ld in (data.get("lexical_decisions") or []):
            sw = ld.get("source_word")
            if not sw:
                continue
            lemma = ld.get("lemma") or ""
            occurrence = {
                "verse_id": verse_id,
                "reference": reference,
                "chosen": ld.get("chosen", ""),
                "source_word": sw,
                "lemma": lemma,
                "rationale_short": str(ld.get("rationale") or "")[:200],
            }
            # Key by the inflected form always; also by lemma when present
            # and distinct. Same occurrence dict is shared between keys.
            index[sw].append(occurrence)
            if lemma and lemma != sw:
                index[lemma].append(occurrence)

    INDEX_CACHE.write_text(json.dumps(index))
    return index


# ──────────────────────────────────────────────────────────────────
# Tool implementations (the four lookup tools + two terminals)
# ──────────────────────────────────────────────────────────────────

_DOCTRINE_CACHE: dict | None = None
_INDEX_CACHE: dict | None = None


def tool_lookup_doctrine(source_word: str) -> dict:
    global _DOCTRINE_CACHE
    if _DOCTRINE_CACHE is None:
        _DOCTRINE_CACHE = parse_doctrine_contested_terms()
    key = source_word.strip()
    entry = _DOCTRINE_CACHE.get(key) or _DOCTRINE_CACHE.get(key.lower())
    if entry:
        return {"found": True, **entry}
    return {"found": False, "source_word": source_word,
            "note": "No DOCTRINE.md contested-terms entry. You have full latitude on this word."}


def tool_lookup_occurrences(source_word: str, limit: int = 20) -> dict:
    """Return all corpus occurrences of `source_word` from lexical_decisions.

    The index is keyed by BOTH the inflected `source_word` and the `lemma`
    field (when present on a lexical_decisions entry). Either form resolves
    to the same set of occurrences. Verses whose lexical_decisions entries
    lack `lemma` are only findable by their inflected form — these are the
    legacy backfill candidates.
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        _INDEX_CACHE = build_lemma_index()
    hits = _INDEX_CACHE.get(source_word, [])
    # Aggregate distribution of `chosen` renderings to help spot patterns.
    distribution: dict[str, int] = defaultdict(int)
    for h in hits:
        distribution[h["chosen"]] += 1
    return {
        "source_word": source_word,
        "total_occurrences": len(hits),
        "distribution": dict(distribution),
        "sample_occurrences": hits[:limit],
    }


def _book_code_from_verse_id(verse_id: str) -> str:
    """1PE.5.8 -> 1PE; ROM.1.1 -> ROM. Returns '' if format unrecognized."""
    if not verse_id or "." not in verse_id:
        return ""
    return verse_id.split(".", 1)[0]


def _normalize_book_filter(book: str) -> str:
    """Accept either a slug ('1_peter') or a code ('1PE'). Return uppercase code-or-slug."""
    return book.strip().upper().replace(" ", "_")


def tool_lookup_book_context(book: str, source_word: str | None = None, top_n: int = 12) -> dict:
    """Return the most frequently rendered source-words in this book, with
    their chosen renderings. If source_word is given, narrow to that word's
    occurrences within the book (useful for author-pattern verification:
    "how has Peter rendered this word elsewhere in 1 Peter?").

    Backed by the same /tmp lemma index used by lookup_occurrences.
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        _INDEX_CACHE = build_lemma_index()
    target_book = _normalize_book_filter(book)

    # Build per-book aggregation lazily.
    by_book: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for sw, hits in _INDEX_CACHE.items():
        for h in hits:
            code = _book_code_from_verse_id(h.get("verse_id", ""))
            # Match by code (1PE) OR by slug (the slug is in the path, not verse_id —
            # tolerate either by matching prefix of the verse_id code).
            if not code:
                continue
            if target_book and not (code == target_book or code.startswith(target_book[:3])):
                continue
            by_book[code][sw].append(h)

    if not by_book:
        return {
            "book": book,
            "note": "No verses indexed for that book code/slug. Pass a verse-id prefix like '1PE' or '1_PETER'.",
            "patterns": [],
        }

    # Flatten to the top-N most-referenced source words across all matched books.
    rows: list[dict] = []
    for code, word_map in by_book.items():
        for sw, occurrences in word_map.items():
            if source_word and sw != source_word:
                continue
            distribution: dict[str, int] = defaultdict(int)
            for occ in occurrences:
                distribution[occ["chosen"]] += 1
            rows.append({
                "book_code": code,
                "source_word": sw,
                "count": len(occurrences),
                "distribution": dict(distribution),
                "sample_occurrences": occurrences[:4],
            })
    rows.sort(key=lambda r: r["count"], reverse=True)
    return {"book": book, "patterns": rows[:top_n]}


def tool_read_drafter_reasoning(verse_yaml_path: str) -> dict:
    p = pathlib.Path(verse_yaml_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        return {"error": f"verse not found: {verse_yaml_path}"}
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return {
        "verse_id": data.get("id"),
        "reference": data.get("reference"),
        "current_text": (data.get("translation") or {}).get("text", ""),
        "lexical_decisions": data.get("lexical_decisions") or [],
        "theological_decisions": data.get("theological_decisions") or [],
        "footnotes": (data.get("translation") or {}).get("footnotes") or [],
        "revisions": data.get("revisions") or [],
    }


TOOL_SCHEMAS = [
    {
        "name": "lookup_doctrine",
        "description": "Look up DOCTRINE.md's contested-terms entry for a Greek/Hebrew word. Returns the project-binding default rendering if one exists, or {found: false} if you have latitude. ALWAYS call this for any word you are considering changing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_word": {"type": "string", "description": "Greek or Hebrew word in original script (e.g. 'νήφω') OR transliteration (e.g. 'nepho')."},
            },
            "required": ["source_word"],
        },
    },
    {
        "name": "lookup_occurrences",
        "description": "Return every POB verse where this source_word appears in lexical_decisions, with current renderings. Use to test 'is this figurative throughout?' against actual usage in the corpus.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_word": {"type": "string"},
                "limit": {"type": "integer", "default": 20, "description": "Max sample occurrences to return (distribution counts always full)."},
            },
            "required": ["source_word"],
        },
    },
    {
        "name": "lookup_book_context",
        "description": "Return how source-words have been rendered within a specific book (verse-id code like '1PE', 'ROM', 'MAT' — or pass with source_word to narrow to one word's pattern in that book). Use for author-pattern checks: 'has the same author rendered this word differently elsewhere in this book?'",
        "input_schema": {
            "type": "object",
            "properties": {
                "book": {"type": "string", "description": "Verse-id book code, e.g. '1PE' for 1 Peter."},
                "source_word": {"type": "string", "description": "Optional: narrow to one source word's pattern within the book."},
                "top_n": {"type": "integer", "default": 12},
            },
            "required": ["book"],
        },
    },
    {
        "name": "read_drafter_reasoning",
        "description": "Return the verse's full lexical_decisions, theological_decisions, footnotes, and revision history. Required reading before any submit_revision call.",
        "input_schema": {
            "type": "object",
            "properties": {"verse_yaml_path": {"type": "string"}},
            "required": ["verse_yaml_path"],
        },
    },
    {
        "name": "spawn_lemma_analyst",
        "description": "Spawn a focused sub-agent that examines a Greek/Hebrew lemma's full corpus distribution and returns a structured verdict on the question you pose. Use when lookup_occurrences alone leaves you unsure about a figurative-vs-literal call, an author-pattern question, or a 'is this rendering consistent with usage elsewhere?' question. The sub-agent has its own narrow tool surface (lookup_occurrences, lookup_book_context) and returns a verdict + supporting evidence. Recursion-capped — sub-agents cannot spawn further sub-agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lemma": {"type": "string", "description": "Greek or Hebrew lemma in original script."},
                "question": {"type": "string", "description": "Specific question for the analyst, e.g. 'Is νήφω figurative in every NT occurrence, or are there literal-sober uses?'"},
            },
            "required": ["lemma", "question"],
        },
    },
    {
        "name": "submit_revision",
        "description": "Terminal: propose a change to the verse. The rationale field MUST address Q1 (what the author is doing with the word in context), Q2 (why the current English misses that), and Q3 (how this engages with — not bypasses — the drafter's lexical_decisions). A rationale that names only a lexicon preference will be rejected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "revised_text": {"type": "string"},
                "rationale": {"type": "string", "description": "Must address Q1/Q2/Q3 explicitly. Lexicon-preference-only rationales are invalid."},
            },
            "required": ["revised_text", "rationale"],
        },
    },
    {
        "name": "submit_unchanged",
        "description": "Terminal: the draft stands. This is the default outcome — every verse you leave alone is a verse you have validated.",
        "input_schema": {
            "type": "object",
            "properties": {"brief_reason": {"type": "string"}},
            "required": ["brief_reason"],
        },
    },
]


TOOL_DISPATCH = {
    "lookup_doctrine": lambda i: tool_lookup_doctrine(i["source_word"]),
    "lookup_occurrences": lambda i: tool_lookup_occurrences(i["source_word"], i.get("limit", 20)),
    "lookup_book_context": lambda i: tool_lookup_book_context(i["book"], i.get("source_word"), i.get("top_n", 12)),
    "read_drafter_reasoning": lambda i: tool_read_drafter_reasoning(i["verse_yaml_path"]),
    "spawn_lemma_analyst": lambda i: run_lemma_analyst(i["lemma"], i["question"]),
}


# ──────────────────────────────────────────────────────────────────
# Lemma-analyst sub-agent (focused reasoning over corpus distribution)
# ──────────────────────────────────────────────────────────────────

LEMMA_ANALYST_SYSTEM = """You are a lemma analyst for the People's Open Bible.

A verse reviewer has spawned you with a specific question about a Greek or Hebrew \
lemma. Your job is to examine the POB corpus's use of that lemma and return a \
structured verdict.

You have two information tools (lookup_occurrences, lookup_book_context) and \
one terminal action (submit_verdict). You cannot spawn further sub-agents — \
recursion is capped at one level.

Process:
1. Call lookup_occurrences for the lemma. Read the distribution.
2. If the question is author- or book-specific, also call lookup_book_context.
3. Reason about figurative vs literal, author patterns, or whatever the \
reviewer asked.
4. Submit a verdict via submit_verdict.

Be concise. The reviewer is waiting on you. Submit a verdict within """ + \
str(MAX_ANALYST_ITERATIONS) + """ rounds.

The verdict structure must include:
- usage_summary: one or two sentences on how the lemma is actually used in the corpus.
- discriminators: when there are split uses (some literal, some figurative), name \
the textual signals that mark the difference.
- verdict_for_question: a direct answer to the reviewer's question.
- supporting_verses: 2 to 4 most-illustrative occurrences (verse_id + current rendering)."""


LEMMA_ANALYST_TOOLS = [
    {
        "name": "lookup_occurrences",
        "description": "Return every POB verse where this source_word appears, with current renderings and distribution counts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_word": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["source_word"],
        },
    },
    {
        "name": "lookup_book_context",
        "description": "How source-words are rendered within a specific book (by verse-id code, e.g. '1PE').",
        "input_schema": {
            "type": "object",
            "properties": {
                "book": {"type": "string"},
                "source_word": {"type": "string"},
                "top_n": {"type": "integer", "default": 8},
            },
            "required": ["book"],
        },
    },
    {
        "name": "submit_verdict",
        "description": "Terminal: return your structured verdict to the reviewer who spawned you.",
        "input_schema": {
            "type": "object",
            "properties": {
                "usage_summary": {"type": "string"},
                "discriminators": {"type": "string"},
                "verdict_for_question": {"type": "string"},
                "supporting_verses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "verse_id": {"type": "string"},
                            "current_rendering": {"type": "string"},
                            "note": {"type": "string"},
                        },
                        "required": ["verse_id", "current_rendering"],
                    },
                },
            },
            "required": ["usage_summary", "verdict_for_question"],
        },
    },
]


def run_lemma_analyst(lemma: str, question: str) -> dict:
    """Sub-agent loop. Same Anthropic Messages plumbing as the main reviewer
    but with a narrower tool surface and a tighter iteration cap.

    Returns the analyst's verdict dict (or an error fallback). The main
    reviewer receives this as the tool_result content.
    """
    user_msg = (
        f"Lemma: {lemma}\n"
        f"Question from reviewer: {question}\n\n"
        f"Gather corpus evidence via tools, then submit_verdict."
    )
    messages: list[dict] = [{"role": "user", "content": user_msg}]

    for iteration in range(MAX_ANALYST_ITERATIONS):
        resp = anthropic_call(messages, LEMMA_ANALYST_SYSTEM, ANALYST_MODEL, tools=LEMMA_ANALYST_TOOLS)
        content = resp.get("content", [])
        messages.append({"role": "assistant", "content": content})

        tool_results: list[dict] = []
        verdict: dict | None = None
        for block in content:
            if block.get("type") != "tool_use":
                continue
            tname = block["name"]
            tin = block.get("input") or {}
            if tname == "submit_verdict":
                verdict = {
                    "lemma": lemma,
                    "question": question,
                    "iterations_used": iteration + 1,
                    **tin,
                }
                break
            if tname == "lookup_occurrences":
                tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(tool_lookup_occurrences(tin["source_word"], tin.get("limit", 20)))[:8000]})
            elif tname == "lookup_book_context":
                tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(tool_lookup_book_context(tin["book"], tin.get("source_word"), tin.get("top_n", 8)))[:8000]})
            else:
                tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps({"error": f"analyst cannot call {tname}"}), "is_error": True})

        if verdict is not None:
            return verdict
        if not tool_results:
            messages.append({"role": "user", "content": "You did not call a tool. Use lookup_occurrences or call submit_verdict."})
            continue
        messages.append({"role": "user", "content": tool_results})

    return {
        "lemma": lemma,
        "question": question,
        "error": f"analyst cap reached ({MAX_ANALYST_ITERATIONS} iterations) without a verdict",
        "iterations_used": MAX_ANALYST_ITERATIONS,
    }


# ──────────────────────────────────────────────────────────────────
# Reviewer agent loop
# ──────────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    base = """You are an agentic revision reviewer for the People's Open Bible.

You have information-gathering tools (lookup_doctrine, lookup_occurrences, \
lookup_book_context, read_drafter_reasoning) and two terminal actions \
(submit_revision, submit_unchanged). Use the lookup tools to gather evidence, \
then call exactly one terminal action.

The framework that governs your job is in the POLICY block below. Apply it. \
The default outcome is submit_unchanged. Every verse you leave alone is a verse \
you have validated. Submit a revision only when you can name a specific defect \
AND show the drafter's documented reasoning either does not address it or is \
wrong on the evidence.

You have at most """ + str(MAX_ITERATIONS) + """ tool-call rounds per verse. \
Use them to gather evidence first; do not propose a change without checking \
lookup_doctrine and (where the word has a documented decision) \
read_drafter_reasoning.
"""
    if POLICY_FILE.exists():
        return base + "\n\n---\n\n" + POLICY_FILE.read_text(encoding="utf-8")
    return base


def anthropic_call(messages: list[dict], system: str, model: str, tools: list[dict] | None = None) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system,
        "tools": tools if tools is not None else TOOL_SCHEMAS,
        "messages": messages,
    }
    req = urllib.request.Request(
        ANTHROPIC_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            if e.code in (429, 500, 503) and attempt < 4:
                time.sleep(15 + attempt * 15)
                continue
            raise RuntimeError(f"Anthropic HTTP {e.code}: {body[:300]}")
    raise RuntimeError("exhausted retries")


def review_verse(verse_path: pathlib.Path, model: str = DEFAULT_MODEL) -> dict:
    """Run the agentic reviewer on one verse. Returns a proposal dict."""
    data = yaml.safe_load(verse_path.read_text(encoding="utf-8"))
    source_text = (data.get("source") or {}).get("text", "")
    source_lang = (data.get("source") or {}).get("language", "Greek")
    current = (data.get("translation") or {}).get("text", "")
    reference = data.get("reference") or str(verse_path)

    user_msg = (
        f"Reference: {reference}\n"
        f"Verse YAML path: {verse_path.relative_to(REPO_ROOT)}\n"
        f"Source ({source_lang}):\n{source_text}\n\n"
        f"Current draft:\n{current}\n\n"
        f"Apply the framework. Gather evidence via tools, then call exactly one "
        f"terminal action."
    )
    messages: list[dict] = [{"role": "user", "content": user_msg}]
    system = load_system_prompt()

    trace: list[dict] = []
    for iteration in range(MAX_ITERATIONS):
        resp = anthropic_call(messages, system, model)
        content = resp.get("content", [])
        stop_reason = resp.get("stop_reason")

        # Record the assistant turn verbatim for replay/audit
        messages.append({"role": "assistant", "content": content})
        trace.append({"iteration": iteration, "stop_reason": stop_reason, "blocks": [b.get("type") for b in content]})

        # Dispatch any tool_use blocks
        tool_results: list[dict] = []
        terminal: dict | None = None
        for block in content:
            if block.get("type") != "tool_use":
                continue
            tname = block["name"]
            tin = block.get("input") or {}
            if tname == "submit_revision":
                terminal = {"kind": "revision", "revised_text": tin.get("revised_text", ""), "rationale": tin.get("rationale", "")}
                break
            if tname == "submit_unchanged":
                terminal = {"kind": "unchanged", "brief_reason": tin.get("brief_reason", "")}
                break
            handler = TOOL_DISPATCH.get(tname)
            if handler is None:
                tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps({"error": f"unknown tool {tname}"}), "is_error": True})
                continue
            try:
                result = handler(tin)
                tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps(result)[:8000]})
            except Exception as exc:
                tool_results.append({"type": "tool_result", "tool_use_id": block["id"], "content": json.dumps({"error": str(exc)}), "is_error": True})

        if terminal is not None:
            result = {
                "verse_path": str(verse_path.relative_to(REPO_ROOT)),
                "reference": reference,
                "current_text": current,
                "decision": terminal,
                "iterations_used": iteration + 1,
                "trace": trace,
                "messages": messages,  # full trace, including tool_results
                "model": model,
            }
            _write_audit_log(verse_path, result)
            return result

        if not tool_results:
            # Model emitted text without tools and without terminal — re-prompt once.
            messages.append({"role": "user", "content": "You did not call a tool. Use a lookup tool to gather evidence, or call submit_unchanged / submit_revision."})
            continue

        messages.append({"role": "user", "content": tool_results})

    # Cap reached without terminal — fail safe to unchanged + flag for human.
    result = {
        "verse_path": str(verse_path.relative_to(REPO_ROOT)),
        "reference": reference,
        "current_text": current,
        "decision": {"kind": "cap_reached_unchanged", "brief_reason": f"Max {MAX_ITERATIONS} iterations exhausted without a terminal call. Flagged for human review."},
        "iterations_used": MAX_ITERATIONS,
        "trace": trace,
        "messages": messages,
        "model": model,
    }
    _write_audit_log(verse_path, result)
    return result


def _write_audit_log(verse_path: pathlib.Path, result: dict) -> None:
    """Persist the full reviewer trace to state/agentic_pass/<verse_id>/<ts>.json.

    state/ is gitignored — these are local artifacts for project-level
    transparency, debugging, and future training data.
    """
    try:
        verse_id = pathlib.Path(result.get("verse_path", "")).stem
        book_dir = pathlib.Path(result.get("verse_path", "")).parts[-2] if "/" in result.get("verse_path", "") else "unknown"
        target = AUDIT_LOG_DIR / book_dir / f"{verse_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Strip non-JSON-serializable bits from messages (Anthropic returns content
        # blocks as dicts already, so this should serialize cleanly).
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except Exception:
        # Audit log must not break the review pipeline.
        pass


# ──────────────────────────────────────────────────────────────────
# Lemma backfill (deterministic, no LLM) — extracts lemmas from rationale
# ──────────────────────────────────────────────────────────────────

# Greek + Hebrew Unicode ranges. We treat any sequence of letters in these
# ranges (with diacritics) as a candidate lemma form.
_GREEK_OR_HEBREW = r"[\u0370-\u03FF\u1F00-\u1FFF\u0590-\u05FF]+"

# Patterns where rationales naming the lemma typically occur. Each pattern's
# group(1) is the candidate lemma. Ordered most-specific → most-generic.
_LEMMA_PATTERNS = [
    rf"(?<![\w]){_GREEK_OR_HEBREW}\s+is\s+(?:the\s+)?(?:dictionary|lemma|root)\s+(?:form\s+)?of",
    rf"(?:lemma|root|dictionary form)\s+(?:is\s+)?[\"']?({_GREEK_OR_HEBREW})",
    rf"(?:verb|noun|adjective|particle|preposition)\s+({_GREEK_OR_HEBREW})",
    rf"({_GREEK_OR_HEBREW})\s+(?:literally\s+(?:means|denotes)|in\s+the\s+sense|carries\s+the\s+sense)",
    rf"from\s+(?:the\s+)?(?:Greek|Hebrew)?\s*({_GREEK_OR_HEBREW})",
]


def extract_lemma_from_rationale(source_word: str, rationale: str) -> str | None:
    """Best-effort lemma extraction from rationale text.

    Returns a candidate lemma if confidently found, else None. The caller
    is responsible for validating before persisting (the function does NOT
    do morphological verification — that requires a lemmatizer).

    The function will not return:
    - source_word itself (the inflected form already in the field)
    - very short tokens (<3 chars — too noisy)
    """
    if not rationale:
        return None
    for pat in _LEMMA_PATTERNS:
        for m in re.finditer(pat, rationale):
            cand = m.group(1) if m.groups() else None
            if not cand:
                continue
            cand = cand.strip("\"'.,;:")
            if not cand or cand == source_word or len(cand) < 3:
                continue
            # Heuristic: lemma should share at least the first 2 chars with
            # the inflected form (handles νήψατε→νήφω, ἀγαπήσατε→ἀγαπάω).
            if cand[:2] == source_word[:2]:
                return cand
    return None


def backfill_lemmas(dry_run: bool = True) -> dict:
    """Walk translation/ and, for every lexical_decisions entry without a
    lemma, try to extract one from its rationale text. In dry-run, returns
    a proposals dict without writing. With dry_run=False, writes lemma:
    fields back to the YAMLs.
    """
    proposals: list[dict] = []
    written = 0
    skipped_no_match = 0
    skipped_has_lemma = 0
    for path in TRANSLATION_ROOT.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        lex = data.get("lexical_decisions") or []
        if not lex:
            continue
        modified = False
        for ld in lex:
            if not isinstance(ld, dict):
                continue
            if ld.get("lemma"):
                skipped_has_lemma += 1
                continue
            sw = ld.get("source_word")
            if not sw:
                continue
            candidate = extract_lemma_from_rationale(sw, str(ld.get("rationale") or ""))
            if not candidate:
                skipped_no_match += 1
                continue
            proposals.append({
                "verse_path": str(path.relative_to(REPO_ROOT)),
                "source_word": sw,
                "candidate_lemma": candidate,
            })
            if not dry_run:
                ld["lemma"] = candidate
                modified = True
        if modified and not dry_run:
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            written += 1
    return {
        "proposals": proposals,
        "stats": {
            "proposals_count": len(proposals),
            "yamls_written": written,
            "skipped_no_match": skipped_no_match,
            "skipped_has_lemma": skipped_has_lemma,
            "dry_run": dry_run,
        },
    }


# ──────────────────────────────────────────────────────────────────
# Audit (deterministic, no LLM) — finds candidate verses
# ──────────────────────────────────────────────────────────────────

def audit_corpus(testaments: list[str] | None = None) -> list[dict]:
    """Find verses where a contested term in DOCTRINE.md appears AND the
    current rendering may diverge from doctrine. No LLM calls.

    A verse is flagged if any of its lexical_decisions entries has a
    source_word OR lemma that matches a DOCTRINE.md contested term key.
    Triage of which actually need revision is left to the agentic reviewer.
    """
    doctrine = parse_doctrine_contested_terms()
    contested_keys = {k for k in doctrine if not k.islower()}  # original-script only
    testaments = testaments or ["nt", "ot", "extra_canonical", "deuterocanon"]

    flagged: list[dict] = []
    for testament in testaments:
        t_dir = TRANSLATION_ROOT / testament
        if not t_dir.exists():
            continue
        for path in t_dir.rglob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, UnicodeDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            lex = data.get("lexical_decisions") or []
            hits: list[str] = []
            for ld in lex:
                if not isinstance(ld, dict):
                    continue
                # Check both inflected source_word and lemma against contested keys.
                # Either match flags the verse; we record the matched contested term.
                for field in ("source_word", "lemma"):
                    val = ld.get(field)
                    if val and val in contested_keys:
                        hits.append(val)
                        break  # one match per ld is enough
            if hits:
                flagged.append({
                    "verse_path": str(path.relative_to(REPO_ROOT)),
                    "reference": data.get("reference"),
                    "contested_terms": sorted(set(hits)),
                    "has_revisions": bool(data.get("revisions")),
                })
    return flagged


# ──────────────────────────────────────────────────────────────────
# Apply: take an approved proposals manifest and write the YAMLs
# ──────────────────────────────────────────────────────────────────

def apply_proposals(manifest_path: pathlib.Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    proposals = manifest.get("proposals") or manifest  # accept either shape
    applied = 0
    skipped = 0
    for prop in proposals:
        decision = prop.get("decision", {})
        if decision.get("kind") != "revision":
            skipped += 1
            continue
        if not prop.get("approved"):
            skipped += 1
            continue
        path = REPO_ROOT / prop["verse_path"]
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        new_text = decision["revised_text"]
        old_text = data["translation"]["text"]
        if new_text == old_text:
            skipped += 1
            continue
        revisions = data.setdefault("revisions", [])
        revisions.append({
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "adjudicator": "agentic-revision-pass",
            "reviewer_model": prop.get("model", DEFAULT_MODEL),
            "category": "agentic_revision",
            "from": old_text,
            "to": new_text,
            "rationale": decision.get("rationale", ""),
        })
        data["translation"]["text"] = new_text
        data["revision_pass"] = {
            "model": "agentic-" + prop.get("model", DEFAULT_MODEL),
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "unchanged": False,
            "changes_summary": decision.get("rationale", "")[:500],
        }
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        applied += 1
    print(f"applied={applied} skipped={skipped}")


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backfill-lemmas", action="store_true", help="Extract lemma fields from rationale text across the corpus. Deterministic, no LLM. Dry-run unless --apply-backfill is also set.")
    parser.add_argument("--apply-backfill", action="store_true", help="When used with --backfill-lemmas, actually writes the lemma fields to YAMLs.")
    parser.add_argument("--audit-only", action="store_true", help="Find candidate verses; no LLM calls.")
    parser.add_argument("--from-audit", type=str, help="Run reviewer on verses listed in an audit JSON.")
    parser.add_argument("--verse", type=str, help="Run reviewer on a single verse YAML.")
    parser.add_argument("--apply", type=str, help="Apply an approved proposals manifest.")
    parser.add_argument("--out", type=str, default="/tmp/agentic_revise_out.json", help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=0, help="Max verses to process (0 = no limit).")
    parser.add_argument("--testament", nargs="*", default=None, help="Testaments to audit.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model.")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild of /tmp lemma index.")
    args = parser.parse_args()

    if args.rebuild_index:
        build_lemma_index(force=True)
        print(f"index rebuilt at {INDEX_CACHE}")
        return

    if args.backfill_lemmas:
        result = backfill_lemmas(dry_run=not args.apply_backfill)
        pathlib.Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        s = result["stats"]
        mode = "APPLIED" if args.apply_backfill else "DRY-RUN"
        print(f"backfill {mode}: proposals={s['proposals_count']} written={s['yamls_written']} no_match={s['skipped_no_match']} has_lemma={s['skipped_has_lemma']} → {args.out}")
        return

    if args.audit_only:
        flagged = audit_corpus(args.testament)
        out = {"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(flagged), "verses": flagged}
        pathlib.Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"audit: {len(flagged)} verses flagged → {args.out}")
        return

    if args.apply:
        apply_proposals(pathlib.Path(args.apply))
        return

    # Reviewer mode: --verse or --from-audit
    verse_paths: list[pathlib.Path] = []
    if args.verse:
        verse_paths = [REPO_ROOT / args.verse if not pathlib.Path(args.verse).is_absolute() else pathlib.Path(args.verse)]
    elif args.from_audit:
        audit = json.loads(pathlib.Path(args.from_audit).read_text())
        verses = audit.get("verses") or audit
        verse_paths = [REPO_ROOT / v["verse_path"] for v in verses]
        if args.limit:
            verse_paths = verse_paths[:args.limit]
    else:
        parser.error("specify --audit-only, --verse, --from-audit, or --apply")

    proposals: list[dict] = []
    for i, path in enumerate(verse_paths, 1):
        print(f"[{i}/{len(verse_paths)}] {path.relative_to(REPO_ROOT)}", flush=True)
        try:
            result = review_verse(path, model=args.model)
            proposals.append(result)
        except Exception as exc:
            proposals.append({"verse_path": str(path.relative_to(REPO_ROOT)), "error": str(exc)})

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "count": len(proposals),
        "proposals": proposals,
    }
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    n_revise = sum(1 for p in proposals if p.get("decision", {}).get("kind") == "revision")
    n_unchanged = sum(1 for p in proposals if p.get("decision", {}).get("kind") == "unchanged")
    n_cap = sum(1 for p in proposals if p.get("decision", {}).get("kind") == "cap_reached_unchanged")
    n_err = sum(1 for p in proposals if p.get("error"))
    print(f"\nproposals: revise={n_revise} unchanged={n_unchanged} cap={n_cap} err={n_err} → {args.out}")
    print("\nReview the proposals manifest. To apply approved ones, set 'approved': true on each\n"
          "and run:  python3 tools/agentic_revise.py --apply " + args.out)


if __name__ == "__main__":
    main()
