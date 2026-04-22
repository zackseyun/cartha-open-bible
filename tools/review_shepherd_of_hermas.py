#!/usr/bin/env python3
"""review_shepherd_of_hermas.py — Gemini 3.1 Pro second-pass Hermas reviewer.

Reviews one drafted Hermas unit against the normalized Greek source,
book context, and neighboring-unit context, then writes a revised YAML
back in place plus a review JSON report.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any

import boto3
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation" / "extra_canonical" / "shepherd_of_hermas"
REVIEWS_DIR = REPO_ROOT / "state" / "reviews" / "shepherd_of_hermas"
PROMPT_PATH = REPO_ROOT / "tools" / "prompts" / "gemini_review_v3_author_intent.md"
BOOK_CONTEXT_PATH = REPO_ROOT / "tools" / "prompts" / "book_contexts" / "shepherd_of_hermas.md"
DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_GEMINI_SECRET_ID = "/cartha/openclaw/gemini_api_key"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import shepherd_of_hermas as hermas  # noqa: E402

TOOL_REASON_VALUES = {
    "alternative_reading",
    "lexical_alternative",
    "textual_variant",
    "cultural_note",
    "cross_reference",
}

ZONE2_CONSULTS = [
    "Holmes / Lake / Lightfoot Apostolic Fathers editions and notes (consult only)",
    "Modern Hermas commentary and translation literature (consult only)",
    "Secondary Latin / Ethiopic witness discussion for fact-level context only",
]


def review_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "revised_english_text": {"type": "string"},
            "agreement_score": {"type": "number"},
            "verdict": {"type": "string", "enum": ["agree", "minor-issues", "major-issues"]},
            "review_summary": {"type": "string"},
            "issues_found": {"type": "array", "items": {"type": "string"}},
            "recommended_footnotes": {
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
        },
        "required": ["revised_english_text", "agreement_score", "verdict", "review_summary", "issues_found"],
    }


def gemini_api_key() -> str:
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    sm = boto3.client("secretsmanager", region_name="us-west-2")
    raw = sm.get_secret_value(SecretId=os.environ.get("GEMINI_SECRET_ID", DEFAULT_GEMINI_SECRET_ID))["SecretString"].strip()
    try:
        obj = json.loads(raw)
    except Exception:
        if raw:
            return raw
        raise RuntimeError("No Gemini API key resolved")
    if isinstance(obj, dict):
        vals = obj.get("api_keys")
        if isinstance(vals, list) and vals:
            return str(vals[0]).strip()
        for k in ("api_key", "apiKey", "key", "GEMINI_API_KEY"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    if isinstance(obj, list) and obj:
        return str(obj[0]).strip()
    raise RuntimeError("No Gemini API key resolved")


def review_paths(sequence: int) -> tuple[pathlib.Path, pathlib.Path]:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    return (
        REVIEWS_DIR / f"{sequence:03d}.review.json",
        REVIEWS_DIR / f"{sequence:03d}.review.meta.json",
    )


def unit_yaml_path(sequence: int) -> pathlib.Path:
    return TRANSLATION_ROOT / f"{sequence:03d}.yaml"


def load_draft(sequence: int) -> dict[str, Any]:
    return yaml.safe_load(unit_yaml_path(sequence).read_text(encoding="utf-8"))


def sanitize_footnotes(notes: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for note in notes or []:
        note = dict(note)
        if note.get("reason") not in TOOL_REASON_VALUES:
            note["reason"] = "lexical_alternative"
        out.append(note)
    return out


def book_context() -> str:
    return BOOK_CONTEXT_PATH.read_text(encoding="utf-8").strip() if BOOK_CONTEXT_PATH.exists() else "(book context missing)"


def prompt_preamble() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip() if PROMPT_PATH.exists() else "(review prompt missing)"


def neighbor_payload(sequence: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, target in (("previous", sequence - 1), ("next", sequence + 1)):
        unit = hermas.load_normalized_unit(sequence=target)
        if unit is None:
            continue
        payload: dict[str, Any] = {
            "unit_id": unit.unit_id,
            "label": unit.label,
            "source_greek": unit.text,
        }
        yaml_path = unit_yaml_path(target)
        if yaml_path.exists():
            draft = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            payload["current_english"] = ((draft.get("translation") or {}).get("text", "") or "").strip()
        out[label] = payload
    return out


def source_warnings(sequence: int) -> list[str]:
    payload = hermas.load_unit_map()
    target = hermas.load_normalized_unit(sequence=sequence)
    if target is None:
        return []
    for row in payload.get("units", []):
        if row.get("unit_id") == target.unit_id:
            return [str(n) for n in (row.get("notes") or [])]
    return []


def build_user_prompt(sequence: int, draft: dict[str, Any]) -> str:
    unit = hermas.load_normalized_unit(sequence=sequence)
    if unit is None:
        raise LookupError(f"Hermas unit sequence {sequence} not found")
    return f"""# Author-intent review framework

{prompt_preamble()}

# Book context

{book_context()}

# Unit under review

Reference: Shepherd of Hermas — {unit.label}
ID: HERM.{unit.unit_id}
Sequence: {sequence}
Source pages: {unit.source_pages}

# Primary Greek source

{unit.text}

# Neighboring context

{json.dumps(neighbor_payload(sequence), ensure_ascii=False, indent=2)}

# Zone 2 consult registry

{json.dumps(ZONE2_CONSULTS, ensure_ascii=False, indent=2)}

# Source-integrity notes

{json.dumps(source_warnings(sequence) or ['No known source-integrity warnings for this unit.'], ensure_ascii=False, indent=2)}

# Current draft YAML

{yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, default_flow_style=False)}

# Review task

Review this Hermas unit draft for author-intent fidelity and return a revised English text only where there is a genuine improvement. Use the Greek source as the anchor. Preserve the register, moral pressure, and symbolic force of Hermas. If the current draft is already good, keep the revised text very close to the current one. Keep your review summary concise.
"""


def _fallback_plaintext_prompt(user_prompt: str) -> str:
    return user_prompt + """

# Fallback serialization mode

The previous structured response failed. This time, do NOT return JSON.
Return exactly this format:

---REVISED-ENGLISH---
<full revised English text only>
---END-REVISED-ENGLISH---
---SUMMARY---
<1 short paragraph summarizing the main fidelity issues you corrected>
---END-SUMMARY---
"""


def call_gemini_plaintext(user_prompt: str, *, model: str) -> tuple[dict[str, Any], str]:
    key = gemini_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": _fallback_plaintext_prompt(user_prompt)}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "text/plain",
            "maxOutputTokens": 12000,
        },
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        body = json.loads(r.read())
    cand = (body.get("candidates") or [None])[0]
    if not cand:
        raise RuntimeError(f"Gemini fallback returned no candidates; promptFeedback={body.get('promptFeedback')}")
    parts = cand.get("content", {}).get("parts") or []
    raw = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not raw:
        raise RuntimeError("Gemini fallback returned empty text")
    def section(name: str) -> str:
        start = raw.find(f"---{name}---")
        end = raw.find(f"---END-{name}---")
        if start == -1 or end == -1 or end < start:
            return ""
        start += len(f"---{name}---")
        return raw[start:end].strip()
    revised_text = section('REVISED-ENGLISH')
    summary = section('SUMMARY')
    if not revised_text:
        raise RuntimeError(f"Gemini fallback did not return a revised English block; head={raw[:1200]!r}")
    model_id = body.get("modelVersion") or body.get("model") or model
    return ({
        "revised_english_text": revised_text,
        "agreement_score": 0.75,
        "verdict": "minor-issues",
        "review_summary": summary or "Gemini plaintext fallback revision applied.",
        "issues_found": ["plaintext fallback revision"],
    }, str(model_id))


def call_gemini_review(user_prompt: str, *, model: str) -> tuple[dict[str, Any], str]:
    key = gemini_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": review_output_schema(),
            "maxOutputTokens": 12000,
        },
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    cand = (body.get("candidates") or [None])[0]
    if not cand:
        raise RuntimeError(f"Gemini returned no candidates; promptFeedback={body.get('promptFeedback')}")
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
    except json.JSONDecodeError:
        return call_gemini_plaintext(user_prompt, model=model)
    model_id = body.get("modelVersion") or body.get("model") or model
    return parsed, str(model_id)


def apply_review(sequence: int, draft: dict[str, Any], review: dict[str, Any], reviewer_model: str, prompt_sha: str) -> dict[str, Any]:
    revised = dict(draft)
    revised_translation = dict(revised.get("translation", {}))
    revised_translation["text"] = review["revised_english_text"].strip()
    if review.get("recommended_footnotes"):
        revised_translation["footnotes"] = sanitize_footnotes(review["recommended_footnotes"])
    revised["translation"] = revised_translation
    review_passes = list(revised.get("review_passes", []))
    review_passes.append(
        {
            "reviewer_model": reviewer_model,
            "timestamp": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "prompt_sha256": prompt_sha,
            "agreement_score": review.get("agreement_score"),
            "verdict": review.get("verdict"),
            "summary": review.get("review_summary", ""),
            "issues_found": review.get("issues_found", []),
        }
    )
    revised["review_passes"] = review_passes
    return revised


def write_yaml(record: dict[str, Any], sequence: int) -> pathlib.Path:
    path = unit_yaml_path(sequence)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True, type=int)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    draft = load_draft(args.sequence)
    user_prompt = build_user_prompt(args.sequence, draft)
    prompt_sha = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()
    review, model = call_gemini_review(user_prompt, model=args.model)
    revised = apply_review(args.sequence, draft, review, model, prompt_sha)
    out_path = write_yaml(revised, args.sequence)

    review_path, meta_path = review_paths(args.sequence)
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "sequence": args.sequence,
                "reviewer_model": model,
                "prompt_sha256": prompt_sha,
                "reviewed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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
