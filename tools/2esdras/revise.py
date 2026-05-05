#!/usr/bin/env python3
"""revise.py — Gemini 3.1 Pro revision sweep for 2 Esdras chapter drafts.

Takes each chapter YAML under translation/extra_canonical/2_esdras/NN.yaml
and runs a multi-model cross-check: Gemini 3.1 Pro reviews the GPT-5.4
draft against the Latin source, simultaneously producing:

  1. Revision report — translation-quality issues, suggested rewrites,
     flagged lexical choices, missed theological decisions.
  2. Latin-gap findings — places where the English contains content
     that appears to outrun the Latin source, which indicates the
     drafter silently restored material missing from our transcribed
     Latin (the 1:29 'ut sitis mihi in populum' pattern).

Both sets of findings are saved to
  state/reviews/2esdras/<NN>.revision.json

This is an advisory report, not an auto-applier. The user decides
which findings to apply in a subsequent patch commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DRAFT_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "2_esdras"
REVIEWS_ROOT = REPO_ROOT / "state" / "reviews" / "2esdras"

AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-pro-preview")
PROMPT_VERSION = "2esdras_revision_v1_2026-04-22"

SYSTEM_PROMPT = """You are a senior biblical translation reviewer auditing a draft English translation of 2 Esdras (4 Ezra) for the People's Open Bible — a CC-BY 4.0 translation project with auditable per-verse reasoning.

You are reviewing a chapter produced by GPT-5.4 with a Latin primary source (Bensly 1895 + 1875 Missing Fragment). Your role is NOT to re-translate; it is to flag specific, actionable issues so a human reviewer can apply targeted revisions.

CRITICAL INSTRUCTIONS:

1. Latin-English faithfulness: Compare verse-by-verse. For each verse where the English drifts from the Latin in a substantive way, flag it.

2. Dropped-clause detection: If the English contains phrases or clauses that are NOT supported by the Latin source text shown to you, flag it as a `latin_source_gap`. This suggests the drafter restored content from memory that was missing from our OCR/transcription. These are the MOST IMPORTANT findings — they indicate silent corrections of the source text. Example: if Latin reads 'nutrix paruulos suos' but English renders 'that you should be my people, and I should be your God,' that English content isn't in the Latin shown — flag it.

3. Compositional-layer voice: Chapters 1-2 are '5 Ezra' (Christian addition, supersessionist rhetoric). Chapters 3-14 are '4 Ezra' (Jewish apocalypse, lament). Chapters 15-16 are '6 Ezra' (Christian prophetic oracles). If the voice drifts in ways that blend these layers, flag it.

4. Theological hard edges: 4 Ezra 7:45-61, 7:102-115, 8:38-41, 9:13-22 teach narrow-way / refused-intercession / few-saved doctrines. If the English softens these edges, flag it.

5. Project lexical policy:
   - `Altissimus` -> 'the Most High' (not 'God')
   - `cor malignum` -> 'evil heart' thread, especially 3:21, 4:30, 7:48
   - `filius meus Christus` -> 'my son the Messiah' (not 'my son Christ')
   - `angelus domini` -> 'messenger of the Lord' when in apposition to a proper name (malachi)

6. Be SPECIFIC. Cite the verse number and quote the exact Latin and English text under review. Don't give vague feedback. Don't invent issues where none exist.

You will submit your review by calling the `submit_revision_report` function exactly once. Do not output any other text — only the function call."""

SUBMIT_TOOL_SCHEMA = {
    "name": "submit_revision_report",
    "description": "Submit a structured revision report for one chapter of 2 Esdras.",
    "parameters": {
        "type": "object",
        "required": ["overall_assessment", "verse_findings", "summary_agreement_score"],
        "properties": {
            "overall_assessment": {
                "type": "string",
                "description": "One-paragraph overview of chapter quality, voice preservation, and most important issues.",
            },
            "summary_agreement_score": {
                "type": "number",
                "description": "Your agreement score with the draft on a 0.0-1.0 scale (1.0 = ready to ship, 0.5 = substantive issues, 0.0 = fundamental problems).",
            },
            "verse_findings": {
                "type": "array",
                "description": "Per-verse specific findings — only verses with ACTUAL issues. Empty array is fine if the chapter has no issues.",
                "items": {
                    "type": "object",
                    "required": ["verse", "category", "severity", "latin_quote", "english_quote", "issue", "suggested_fix"],
                    "properties": {
                        "verse": {
                            "type": "string",
                            "description": "Verse reference like '7:28' or '1:29'.",
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "latin_source_gap",
                                "translation_drift",
                                "lexical_policy_violation",
                                "theological_softening",
                                "compositional_layer_bleed",
                                "missing_footnote",
                                "missing_theological_decision",
                                "textual_crux_unacknowledged",
                                "punctuation_or_cadence",
                                "other",
                            ],
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "major", "minor", "stylistic"],
                            "description": "critical = blocks publication; major = should fix before next release; minor = nice to have; stylistic = optional polish.",
                        },
                        "latin_quote": {
                            "type": "string",
                            "description": "Exact Latin text quoted from source.",
                        },
                        "english_quote": {
                            "type": "string",
                            "description": "Exact English text quoted from draft.",
                        },
                        "issue": {
                            "type": "string",
                            "description": "What is wrong, specifically.",
                        },
                        "suggested_fix": {
                            "type": "string",
                            "description": "Concrete suggested revision. If the issue is a latin_source_gap, describe what needs to be verified in the Bensly scan rather than suggesting an English fix.",
                        },
                    },
                },
            },
            "latin_gaps_summary": {
                "type": "string",
                "description": "Optional summary specifically of latin_source_gap findings if there are any, with verse list.",
            },
        },
    },
}


@dataclass
class ReviewResult:
    chapter: int
    report: dict[str, Any]
    report_path: pathlib.Path
    model_version: str
    duration_s: float


def gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return key


def load_draft(chapter: int) -> dict[str, Any]:
    path = DRAFT_ROOT / f"{chapter:02d}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open() as f:
        return yaml.safe_load(f)


def build_user_prompt(chapter: int, draft: dict[str, Any]) -> str:
    source = draft["source"]
    translation = draft["translation"]
    lexical = draft.get("lexical_decisions", [])
    theological = draft.get("theological_decisions", [])
    footnotes = translation.get("footnotes", [])
    layer = draft.get("compositional_layer", "unknown")

    parts = [
        f"# 2 Esdras chapter {chapter} — revision review",
        f"Compositional layer: **{layer}**",
        f"Verse count (from source): {source.get('verse_count', 'unknown')}",
        "",
        "## Latin source (Bensly 1895 + 1875 Missing Fragment, cleaned)",
        "",
        "```",
        source["text"],
        "```",
        "",
        "## English draft",
        "",
        "```",
        translation["text"],
        "```",
        "",
        f"Draft translation philosophy: {translation.get('philosophy', 'unknown')}",
        "",
        "## Existing lexical decisions (already documented)",
        "",
        f"{len(lexical)} lexical decisions documented.",
        "",
    ]
    for ld in lexical[:40]:
        parts.append(f"- `{ld.get('source_word')}` -> {ld.get('chosen')!r} ({ld.get('rationale','')[:120]})")
    if len(lexical) > 40:
        parts.append(f"- ... {len(lexical) - 40} more")
    parts.extend([
        "",
        "## Existing theological decisions",
        "",
        f"{len(theological)} theological decisions documented.",
        "",
    ])
    for td in theological:
        parts.append(f"- {td.get('issue','')}: chose {td.get('chosen_reading','')!r}")
    parts.extend([
        "",
        "## Existing footnotes",
        "",
        f"{len(footnotes)} footnotes documented.",
        "",
    ])
    for fn in footnotes:
        parts.append(f"- {fn.get('marker','')} ({fn.get('reason','')}): {fn.get('text','')[:150]}")

    parts.extend([
        "",
        "---",
        "",
        "Produce your revision report by calling `submit_revision_report` with all findings.",
        "Focus especially on `latin_source_gap` findings — places where the English outruns the Latin shown above, which would indicate dropped clauses in our OCR transcription.",
    ])
    return "\n".join(parts)


def call_gemini(prompt: str, model: str = DEFAULT_MODEL) -> tuple[dict[str, Any], str, float]:
    api_key = gemini_api_key()
    url = f"{AI_STUDIO_BASE}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 16000,
        },
        "tools": [{"functionDeclarations": [SUBMIT_TOOL_SCHEMA]}],
        "toolConfig": {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": ["submit_revision_report"],
            }
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:800]}") from exc
    duration = time.time() - started

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(body)[:400]}")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    for p in parts:
        if "functionCall" in p:
            fc = p["functionCall"]
            if fc.get("name") == "submit_revision_report":
                return fc.get("args") or {}, body.get("modelVersion", model), duration
    raise RuntimeError(f"Gemini did not call submit_revision_report: parts={parts!r}")


def review_chapter(chapter: int, *, model: str = DEFAULT_MODEL, write: bool = True) -> ReviewResult:
    draft = load_draft(chapter)
    prompt = build_user_prompt(chapter, draft)
    report, model_version, duration = call_gemini(prompt, model=model)

    prompt_sha = hashlib.sha256((SYSTEM_PROMPT + "\n---\n" + prompt).encode("utf-8")).hexdigest()
    envelope = {
        "reference": f"2 Esdras {chapter}",
        "id": f"2ES.{chapter:02d}",
        "compositional_layer": draft.get("compositional_layer"),
        "reviewer_model": model,
        "reviewer_model_version": model_version,
        "drafter_model": draft.get("ai_draft", {}).get("model_id"),
        "drafter_model_version": draft.get("ai_draft", {}).get("model_version"),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "duration_seconds": round(duration, 2),
        "report": report,
    }

    report_path = REVIEWS_ROOT / f"{chapter:02d}.revision.json"
    if write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return ReviewResult(
        chapter=chapter,
        report=envelope,
        report_path=report_path,
        model_version=model_version,
        duration_s=duration,
    )


def summarize(report: dict[str, Any]) -> str:
    r = report.get("report") or {}
    score = r.get("summary_agreement_score", "?")
    findings = r.get("verse_findings") or []
    by_cat: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    for f in findings:
        by_cat[f.get("category", "?")] = by_cat.get(f.get("category", "?"), 0) + 1
        by_sev[f.get("severity", "?")] = by_sev.get(f.get("severity", "?"), 0) + 1
    parts = [f"score={score}", f"findings={len(findings)}"]
    if by_sev:
        parts.append("sev=" + ",".join(f"{k}:{v}" for k, v in sorted(by_sev.items())))
    gaps = by_cat.get("latin_source_gap", 0)
    if gaps:
        parts.append(f"LATIN_GAPS={gaps}")
    return "  ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", type=int, help="Review a single chapter (1-16)")
    parser.add_argument("--all", action="store_true", help="Review all 16 chapters")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true", help="Print prompt and exit")
    args = parser.parse_args()

    if not args.chapter and not args.all:
        parser.error("pass --chapter N or --all")

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set.", file=sys.stderr)
        return 2

    chapters = [args.chapter] if args.chapter else list(range(1, 17))
    if args.dry_run and args.chapter:
        draft = load_draft(args.chapter)
        print(build_user_prompt(args.chapter, draft))
        return 0

    for ch in chapters:
        try:
            result = review_chapter(ch, model=args.model)
            print(f"ch{ch:02d}: {result.duration_s:5.1f}s  {summarize(result.report)}", flush=True)
        except Exception as exc:
            print(f"ch{ch:02d}: FAIL {type(exc).__name__}: {exc}", flush=True, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
