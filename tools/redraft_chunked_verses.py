#!/usr/bin/env python3
"""redraft_chunked_verses.py — re-draft a list of verses that have
verse-boundary chunking errors (verse YAML containing content from
multiple verses). Calls Vertex Gemini 3.1 Pro Preview with strict
per-verse boundary instructions, then writes the corrected YAML.

The chunking-error verses can't be fixed via apply_gemini_revision
(no clean find/replace exists — the wrong content needs to be
removed entirely and the right content drafted). Instead we re-prompt
Gemini with:
  - the canonical scholarly source-text for THAT specific verse
    (looked up from Gemini's training knowledge of the standard
    editions: R.H. Charles 1902 for Jubilees, Charles 1896 for 2 Baruch)
  - explicit "translate ONLY this verse number, nothing else"
  - the existing verse YAML structure to preserve

Usage:
    GOOGLE_APPLICATION_CREDENTIALS=~/.config/cartha/gemini-vertex-cbv.json \\
    GCP_LOCATION=global \\
    python3 tools/redraft_chunked_verses.py --commit
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.request

import yaml as pyyaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TRANSLATION_ROOT = REPO_ROOT / "translation"
MODEL = "gemini-3.1-pro-preview"
LOCATION = os.environ.get("GCP_LOCATION", "global")

# Verses with confirmed chunking errors. Format:
#   (testament, slug, ch, v, source_edition, brief_problem_description)
# More can be added by the caller via --verses-json or by appending
# here as the comprehensive review pass turns up more.
VERSES: list[dict] = [
    {"testament": "extra_canonical", "slug": "jubilees", "ch": 30, "v": 19,
     "source_edition": "charles_1902", "lang": "Geʿez",
     "problem": "Verse YAML contains content from verses 19, 20, AND 21. Should be ONLY verse 19."},
    {"testament": "extra_canonical", "slug": "jubilees", "ch": 8, "v": 7,
     "source_edition": "charles_1902", "lang": "Geʿez",
     "problem": "Verse YAML contains content from verses 5-6 (marriages and offspring of Shelah and Eber). Verse 7 should describe the birth of Peleg and the division of the earth."},
    {"testament": "extra_canonical", "slug": "jubilees", "ch": 4, "v": 13,
     "source_edition": "charles_1902", "lang": "Geʿez",
     "problem": "Verse YAML contains content from 4:18b-19 (Enoch recounting sabbaths and dream visions). Verse 13 should be about Jared taking Baraka as wife and begetting Enoch."},
    {"testament": "extra_canonical", "slug": "jubilees", "ch": 35, "v": 2,
     "source_edition": "charles_1902", "lang": "Geʿez",
     "problem": "Verse YAML missing the phrase 'the days of the life of Jacob' which belongs to the end of verse 1; verse 2 content is incomplete."},
    {"testament": "extra_canonical", "slug": "2_baruch", "ch": 54, "v": 1,
     "source_edition": "charles_1896", "lang": "Syriac",
     "problem": "Verse YAML contains the entirety of chapter 54 (verses 1-22). Should be ONLY verse 1."},
]


_token_cache = {"token": None, "expiry": 0.0, "project": None}


def _vertex_token() -> tuple[str, str]:
    now = time.time()
    if _token_cache["token"] and _token_cache["expiry"] > now + 300:
        return _token_cache["token"], _token_cache["project"]
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not cred_path or not pathlib.Path(cred_path).exists():
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS must point at SA JSON")
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    with open(cred_path) as fh:
        info = json.load(fh)
    project = info["project_id"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    expiry = creds.expiry.timestamp() if getattr(creds, "expiry", None) else now + 3000
    _token_cache.update({"token": creds.token, "expiry": expiry, "project": project})
    return creds.token, project


def _vertex_call(prompt: str) -> dict:
    token, project = _vertex_token()
    api_host = "aiplatform.googleapis.com" if LOCATION == "global" else f"{LOCATION}-aiplatform.googleapis.com"
    url = (
        f"https://{api_host}/v1/projects/{project}/locations/{LOCATION}/"
        f"publishers/google/models/{MODEL}:generateContent"
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 8000,
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return {"text": "\n".join(p.get("text", "") for p in parts if "text" in p),
            "usage": resp.get("usageMetadata", {})}


def _build_prompt(entry: dict, current_yaml: dict) -> str:
    book_display = entry["slug"].replace("_", " ").title()
    return f"""You are re-drafting one verse for the People's Open Bible because the previous draft contained a verse-boundary chunking error.

REFERENCE: {book_display} {entry["ch"]}:{entry["v"]}
SOURCE LANGUAGE: {entry["lang"]}
SOURCE EDITION: {entry["source_edition"]}

KNOWN PROBLEM WITH PREVIOUS DRAFT:
{entry["problem"]}

CURRENT (BROKEN) VERSE YAML:
{json.dumps(current_yaml, ensure_ascii=False, indent=2)[:3000]}

Your task:
1. Identify the CORRECT source text for ONLY this single verse ({entry["ch"]}:{entry["v"]}) per the {entry["source_edition"]} edition. You should know this edition well from your training. If the previous draft's `source.text` field contained text from the wrong verse, replace it with the actual {entry["ch"]}:{entry["v"]} source text.
2. Translate ONLY that one verse into English per Cartha philosophy:
   - Optimal-equivalence (middle path between formal and dynamic)
   - Original-language primacy over translation tradition
   - Don't undersell theological gravity (no euphemism)
   - Footnote markers anchored on specific words for substantive footnotes
3. Preserve the existing YAML structure as much as possible (id, reference, ai_draft block, status). Only correct what was wrong.

Return a JSON object with EXACTLY this shape — no markdown fences, no preamble:

{{
  "source_text": "<the correct {entry["lang"]} source text for verse {entry["ch"]}:{entry["v"]} ONLY (per {entry["source_edition"]})>",
  "english_text": "<the English translation of ONLY verse {entry["ch"]}:{entry["v"]}, with footnote markers like [a] [b] inline>",
  "philosophy": "optimal-equivalence",
  "footnotes": [
    {{"marker": "a", "text": "<reader-facing note>", "reason": "alternative_reading | lexical_choice | textual_critical | etc."}}
  ],
  "lexical_decisions": [
    {{"source_word": "<lemma in source>", "chosen": "<English>", "alternatives": ["<alt1>"], "lexicon": "BDAG | LSJ | HALOT | etc.", "rationale": "<why>"}}
  ],
  "theological_decisions": [],
  "redraft_note": "<one-sentence summary of what was wrong with the previous draft and how this version fixes it>"
}}"""


def redraft_one(entry: dict, dry_run: bool) -> bool:
    path = TRANSLATION_ROOT / entry["testament"] / entry["slug"] / f'{entry["ch"]:03d}' / f'{entry["v"]:03d}.yaml'
    if not path.exists():
        print(f"  ✗ {entry['slug']} {entry['ch']}:{entry['v']}: file not found")
        return False
    current = pyyaml.safe_load(path.read_text(encoding="utf-8"))
    prompt = _build_prompt(entry, current)
    if dry_run:
        print(f"  (dry) would re-draft {entry['slug']} {entry['ch']}:{entry['v']}")
        return True
    try:
        resp = _vertex_call(prompt)
    except Exception as e:
        print(f"  ✗ {entry['slug']} {entry['ch']}:{entry['v']}: {type(e).__name__}: {e}")
        return False
    try:
        new = json.loads(resp["text"])
    except json.JSONDecodeError as e:
        print(f"  ✗ {entry['slug']} {entry['ch']}:{entry['v']}: bad JSON from model: {e}")
        return False

    # Update the existing YAML, preserving fields that didn't change
    current.setdefault("source", {})
    current["source"]["text"] = new["source_text"]
    if entry["lang"] not in current["source"].get("language", ""):
        current["source"]["language"] = entry["lang"]
    if "edition" not in current["source"]:
        current["source"]["edition"] = entry["source_edition"]
    current.setdefault("translation", {})
    current["translation"]["text"] = new["english_text"]
    current["translation"]["philosophy"] = new.get("philosophy", "optimal-equivalence")
    current["translation"]["footnotes"] = new.get("footnotes", [])
    current["lexical_decisions"] = new.get("lexical_decisions", [])
    current["theological_decisions"] = new.get("theological_decisions", []) or []
    # Stamp re-draft provenance
    current.setdefault("revisions", []).append({
        "id": f"redraft-chunk-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "category": "verse_boundary_redraft",
        "tier": 3,
        "adjudicator": "vertex-gemini-3.1-pro-redraft-chunk",
        "reviewer_model": MODEL,
        "from_summary": "verse-boundary chunking error — previous draft contained content from other verses",
        "to_summary": new.get("redraft_note", ""),
        "rationale": entry["problem"],
    })
    current["status"] = "redrafted_after_chunk_error"

    path.write_text(
        pyyaml.safe_dump(current, allow_unicode=True, sort_keys=False, width=10000),
        encoding="utf-8",
    )
    usage = resp.get("usage", {})
    print(f"  ✓ {entry['slug']} {entry['ch']}:{entry['v']} — tokens={usage.get('totalTokenCount','?')}; note: {new.get('redraft_note','')[:120]}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="Actually call Vertex + write YAMLs (default dry-run)")
    parser.add_argument("--verses-json",
                        help="Optional path to JSON list of additional {testament,slug,ch,v,source_edition,lang,problem} entries")
    args = parser.parse_args()
    entries = list(VERSES)
    if args.verses_json:
        with open(args.verses_json) as fh:
            entries.extend(json.load(fh))
    print(f"Verses to re-draft: {len(entries)}")
    for e in entries:
        print(f"  {e['slug']} {e['ch']}:{e['v']} ({e['lang']})")
    if not args.commit:
        print("\nDRY RUN — pass --commit to call Vertex.")
        return 0
    ok = 0
    for e in entries:
        if redraft_one(e, dry_run=False):
            ok += 1
    print(f"\nDone. Successfully re-drafted: {ok}/{len(entries)}")
    return 0 if ok == len(entries) else 1


if __name__ == "__main__":
    sys.exit(main())
