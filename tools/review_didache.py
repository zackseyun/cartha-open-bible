#!/usr/bin/env python3
"""review_didache.py — Gemini Pro chapter-level Didache reviewer/reviser.

Takes an existing Didache chapter YAML, the normalized Greek source, and
the Schaff 1885 secondary witness excerpt, then asks Gemini Pro for a
careful revision/audit pass. Writes the revised YAML back in place and
saves a review report JSON alongside it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

import yaml

import didache
import didache_secondary


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "didache"
REVIEWS_DIR = REPO_ROOT / "state" / "reviews" / "didache"

TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
}


def review_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "english_text": {"type": "string"},
            "translation_philosophy": {
                "type": "string",
                "enum": ["formal", "dynamic", "optimal-equivalence"],
            },
            "lexical_decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_word": {"type": "string"},
                        "chosen": {"type": "string"},
                        "alternatives": {"type": "array", "items": {"type": "string"}},
                        "lexicon": {"type": "string"},
                        "entry": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["source_word", "chosen", "rationale"],
                },
            },
            "theological_decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "issue": {"type": "string"},
                        "chosen_reading": {"type": "string"},
                        "alternative_readings": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                        "doctrine_reference": {"type": "string"},
                    },
                    "required": ["issue", "chosen_reading", "rationale"],
                },
            },
            "footnotes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "marker": {"type": "string"},
                        "text": {"type": "string"},
                        "reason": {"type": "string", "enum": sorted(TOOL_REASON_VALUES)},
                    },
                    "required": ["marker", "text", "reason"],
                },
            },
            "review_summary": {"type": "string"},
            "issues_found": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "english_text",
            "translation_philosophy",
            "lexical_decisions",
            "review_summary",
            "issues_found",
        ],
    }


def sanitize_footnotes(notes: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for note in notes or []:
        note = dict(note)
        if note.get("reason") not in TOOL_REASON_VALUES:
            note["reason"] = "lexical_alternative"
        out.append(note)
    return out

SYSTEM_PROMPT = """You are a textual reviewer and reviser for the Cartha Open Bible.

You are reviewing ONE Didache chapter draft. Your job is:
1. audit the current English against the Greek source;
2. use the secondary Schaff 1885 witness as a cross-check, not as a source of derivative phrasing;
3. improve the draft only where the revision is genuinely better.

Look especially for:
- source drift from the Greek
- flattened liturgical or moral language
- weak or under-specified lexical decisions
- careless or insufficient footnotes
- over-smoothing where the Greek is intentionally sharp or strange

Do not reproduce copyrighted phrasing from modern translations.
Do not revise merely for stylistic preference.
Return exactly one JSON object matching the requested schema."""


def gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return key


def chapter_path(chapter: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{chapter:03d}.yaml"


def load_draft(chapter: int) -> dict[str, Any]:
    return yaml.safe_load(chapter_path(chapter).read_text(encoding="utf-8"))


def review_paths(chapter: int) -> tuple[pathlib.Path, pathlib.Path]:
    out_dir = REVIEWS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"ch{chapter:02d}.review.json", out_dir / f"ch{chapter:02d}.review.meta.json"


def build_user_prompt(chapter_num: int, draft: dict[str, Any]) -> str:
    primary = didache.load_chapter(chapter_num)
    if primary is None:
        raise LookupError(f"Didache chapter {chapter_num} not found in normalized source")
    secondary = didache_secondary.load_chapter(chapter_num)

    return f"""# Didache chapter under review

Reference: Didache {chapter_num}

# Primary Greek source (normalized Hitchcock 1884)

{primary.text}

# Secondary witness / cross-check (Schaff 1885 extracted pages)

{secondary}

# Current draft YAML

{yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, default_flow_style=False)}

# Review task

Revise this Didache chapter draft only where there is a genuine improvement.
Use the primary Greek as the anchor. Use the secondary witness as a cross-check,
not as a phrasing source to copy from.
"""


def call_gemini_review(user_prompt: str) -> tuple[dict[str, Any], str]:
    key = gemini_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={key}"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": review_output_schema(),
            "maxOutputTokens": 12000,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    cand = (body.get("candidates") or [None])[0]
    if not cand:
        raise RuntimeError(f"Gemini returned no candidates; promptFeedback={body.get('promptFeedback')}")
    finish = cand.get("finishReason")
    if finish != "STOP":
        raise RuntimeError(f"Gemini finishReason={finish}")
    parts = cand.get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned empty JSON text")
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini response was not valid JSON: {exc}; head={text[:300]!r}") from exc
    model_id = body.get("modelVersion") or body.get("model") or "gemini-2.5-pro"
    return parsed, str(model_id)


def apply_review(chapter_num: int, draft: dict[str, Any], review: dict[str, Any], reviewer_model: str, prompt_sha: str) -> dict[str, Any]:
    revised = dict(draft)

    if "english_text" in review:
        revised["translation"]["text"] = review["english_text"].strip()
        revised["translation"]["philosophy"] = review["translation_philosophy"]
        if review.get("footnotes"):
            revised["translation"]["footnotes"] = sanitize_footnotes(review["footnotes"])
        elif "footnotes" in revised.get("translation", {}):
            revised["translation"].pop("footnotes", None)
        revised["lexical_decisions"] = review.get("lexical_decisions", [])
        revised["theological_decisions"] = review.get("theological_decisions", [])
        review_summary = review.get("review_summary", "")
        issues_found = review.get("issues_found", [])
    else:
        # Gemini sometimes returns a full revised record rather than the
        # narrower review schema. Accept that shape too.
        revised["translation"] = review.get("translation", revised.get("translation", {}))
        if "footnotes" in revised.get("translation", {}):
            revised["translation"]["footnotes"] = sanitize_footnotes(revised["translation"]["footnotes"])
        revised["lexical_decisions"] = review.get("lexical_decisions", revised.get("lexical_decisions", []))
        revised["theological_decisions"] = review.get("theological_decisions", revised.get("theological_decisions", []))
        review_summary = "Gemini returned a full revised record."
        issues_found = []

    review_passes = list(revised.get("review_passes", []))
    review_passes.append(
        {
            "reviewer_model": reviewer_model,
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "prompt_sha256": prompt_sha,
            "summary": review_summary,
            "issues_found": issues_found,
        }
    )
    revised["review_passes"] = review_passes
    return revised


def write_yaml(record: dict[str, Any], chapter_num: int) -> pathlib.Path:
    path = chapter_path(chapter_num)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", required=True, type=int)
    args = parser.parse_args()

    draft = load_draft(args.chapter)
    user_prompt = build_user_prompt(args.chapter, draft)
    prompt_sha = hashlib.sha256((SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt).encode("utf-8")).hexdigest()
    review, model = call_gemini_review(user_prompt)

    revised = apply_review(args.chapter, draft, review, model, prompt_sha)
    out_path = write_yaml(revised, args.chapter)

    review_path, meta_path = review_paths(args.chapter)
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "chapter": args.chapter,
                "reviewer_model": model,
                "prompt_sha256": prompt_sha,
                "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Reviewed {out_path.relative_to(REPO_ROOT)} with {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
