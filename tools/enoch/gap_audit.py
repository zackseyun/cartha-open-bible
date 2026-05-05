#!/usr/bin/env python3
"""
gap_audit.py — Detect and fix missing-content gaps in 1 Enoch YAML translations.

Pipeline:
  1. Parse Beta maṣāḥǝft TEI oracle → complete Ge'ez per chapter.
  2. For each at-risk chapter, load verse YAMLs from git (origin/main).
  3. Use gpt-5.4-nano via OpenRouter to detect whether the English
     translation covers all content in the oracle Ge'ez.
  4. For confirmed gaps, use gpt-5.4 (Azure) to draft the missing clause
     in POB optimal-equivalence style.
  5. Patch the YAML files and print a summary.

Usage:
  python3 tools/enoch/gap_audit.py [--dry-run] [--chapters 3,4,7,8]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import boto3
import yaml

# ── constants ────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
ORACLE_XML = Path.home() / "cartha-reference-local/enoch_betamasaheft/LIT1340EnochE.xml"
ENOCH_TRANS = REPO_ROOT / "translation/extra_canonical/1_enoch"
TEI_NS = "http://www.tei-c.org/ns/1.0"

# Chapters where Charles 1906 OCR is known/suspected to be truncated
AT_RISK_CHAPTERS = [
    3, 4, 7, 8, 11, 12, 16, 28, 29, 34, 35, 36,
    42, 44, 50, 51, 64, 66, 70, 88, 104, 107,
]

OPENROUTER_MODEL = "openai/gpt-5.4-nano"
AZURE_MODEL = "gpt-5.4"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── secrets ──────────────────────────────────────────────────────────────────

def _get_secret(name, region="us-west-2"):
    sm = boto3.client("secretsmanager", region_name=region)
    return sm.get_secret_value(SecretId=name)["SecretString"]


def get_openrouter_key():
    return _get_secret("/cartha/openclaw/openrouter_api_key")


def get_azure_creds():
    d = json.loads(_get_secret("cartha-azure-openai-key"))
    return d["api_key"], d["endpoint"], d.get("deployment_name", "gpt-5-deployment")

# ── oracle parsing ────────────────────────────────────────────────────────────

def load_oracle(xml_path: Path) -> dict[int, str]:
    """Return {chapter_number: full_geez_text} from Beta maṣāḥǝft TEI."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    chapters: dict[int, str] = {}
    for div in root.iter(f"{{{TEI_NS}}}div"):
        n = div.get("n", "")
        if not n.isdigit():
            continue
        ch = int(n)
        tokens = []
        for child in div:
            tag = child.tag.split("}")[-1]
            if tag in ("l", "ab", "p"):
                tokens.extend("".join(child.itertext()).split())
        if tokens:
            chapters[ch] = " ".join(tokens)
    return chapters

# ── YAML helpers ──────────────────────────────────────────────────────────────

def load_verse_yaml(chapter: int, verse: int) -> tuple[Path, dict | None]:
    ch_str = f"{chapter:03d}"
    v_str = f"{verse:03d}"
    path = ENOCH_TRANS / ch_str / f"{v_str}.yaml"
    if not path.exists():
        return path, None
    with open(path) as f:
        return path, yaml.safe_load(f)


def list_verses(chapter: int) -> list[int]:
    ch_str = f"{chapter:03d}"
    ch_dir = ENOCH_TRANS / ch_str
    if not ch_dir.exists():
        return []
    return sorted(
        int(p.stem) for p in ch_dir.glob("*.yaml") if p.stem.isdigit()
    )

# ── LLM calls ────────────────────────────────────────────────────────────────

def _openrouter_chat(messages: list[dict], key: str, max_tokens=512) -> str:
    import urllib.request
    body = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://cartha.com",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def _azure_chat(messages: list[dict], api_key: str, endpoint: str,
                deployment: str, max_tokens=400) -> str:
    import urllib.request
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        f"/chat/completions?api-version=2025-01-01-preview"
    )
    body = json.dumps({
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def detect_gap(oracle_geez: str, source_geez: str, english: str,
               ref: str, or_key: str) -> dict:
    """
    Ask gpt-5.4-nano: is anything in oracle_geez missing from english?
    Returns {"gap": bool, "missing_geez": str|None, "reasoning": str}
    """
    prompt = textwrap.dedent(f"""
        You are checking whether an English Bible translation covers its Ge'ez source completely.

        Reference: {ref}

        Complete Ge'ez (oracle, authoritative):
        {oracle_geez}

        Ge'ez used during drafting (may be truncated):
        {source_geez}

        Current English translation:
        {english}

        Task:
        1. Compare the oracle Ge'ez to the English translation.
        2. Identify any clause or phrase present in the oracle Ge'ez that is
           NOT represented in the English translation (not even paraphrastically).
        3. If the English is complete, reply with exactly: COMPLETE
        4. If content is missing, reply with:
           MISSING
           <the missing Ge'ez clause(s) only, verbatim from the oracle>

        Reply with only COMPLETE or MISSING followed by the Ge'ez. No explanations.
    """).strip()

    resp = _openrouter_chat([{"role": "user", "content": prompt}], or_key)
    if resp.startswith("COMPLETE"):
        return {"gap": False, "missing_geez": None, "reasoning": resp}
    elif resp.startswith("MISSING"):
        missing = resp[len("MISSING"):].strip()
        return {"gap": True, "missing_geez": missing, "reasoning": resp}
    else:
        return {"gap": False, "missing_geez": None, "reasoning": f"unexpected: {resp}"}


def translate_missing_clause(
    ref: str, full_oracle_geez: str, current_english: str,
    missing_geez: str, api_key: str, endpoint: str, deployment: str
) -> str:
    """Use Azure GPT-5.4 to render the missing Ge'ez clause in POB style."""
    prompt = textwrap.dedent(f"""
        You are translating a missing clause for the People's Open Bible (POB).
        POB translation philosophy: optimal-equivalence — accurate to the source,
        natural English, preserve imagery without smoothing. Avoid archaisms
        (no 'thee'/'thou'). Use vivid concrete language faithful to the Ge'ez.

        Reference: {ref}

        Full Ge'ez (oracle):
        {full_oracle_geez}

        Current English translation (correct but incomplete — missing a clause):
        {current_english}

        Missing Ge'ez clause to translate:
        {missing_geez}

        Provide ONLY the English for the missing clause, suitable for appending
        to the current translation with a comma. Do not repeat the existing
        translation. Do not add footnote markers. Plain text only.
    """).strip()

    return _azure_chat(
        [{"role": "user", "content": prompt}],
        api_key, endpoint, deployment, max_tokens=200,
    )

# ── YAML patching ─────────────────────────────────────────────────────────────

def patch_yaml(path: Path, data: dict, missing_geez: str,
               missing_english: str, oracle_geez: str) -> None:
    old_text: str = data["translation"]["text"]
    # Append missing clause (strip trailing period from old text if present)
    base = old_text.rstrip(".")
    new_text = f"{base}, {missing_english.lstrip(', ').rstrip('.')}.".rstrip(".,") + "."

    data["translation"]["text"] = new_text

    # Update source text to full oracle
    data["source"]["text"] = oracle_geez
    data["source"]["confidence"] = "high"
    old_note = data["source"].get("note", "")
    data["source"]["note"] = (
        f"Source corrected to full Beta maṣāḥǝft oracle text. "
        f"Prior Charles 1906 OCR was truncated. {old_note}"
    ).strip()

    # Also update witness text if present
    witnesses = (data.get("enoch_witnesses") or {}).get("available_witnesses") or []
    for w in witnesses:
        if w.get("witness") == "charles_1906":
            w["text"] = oracle_geez
            w["source_edition"] = "Beta maṣāḥǝft TEI oracle (Jerabek 1995)"
            w["confidence"] = "high"
            w["note"] = "Charles 1906 OCR was truncated; full text from oracle."

    # Add revision entry
    revisions = data.setdefault("revisions", [])
    revisions.append({
        "timestamp": TODAY,
        "adjudicator": "gap_audit.py",
        "category": "source_correction",
        "from": old_text,
        "to": new_text,
        "rationale": (
            f"Charles 1906 OCR truncated before clause: '{missing_geez}'. "
            f"Missing content detected by gpt-5.4-nano comparison against "
            f"Beta maṣāḥǝft oracle. Clause translated by Azure GPT-5.4 "
            f"and appended in POB optimal-equivalence style."
        ),
    })
    data["revision_pass"] = {
        "model": "gap_audit.py + gpt-5.4-nano (detection) + gpt-5.4 (translation)",
        "timestamp": TODAY,
        "unchanged": False,
        "changes_summary": f"Restored missing clause: '{missing_english}'",
    }
    data["status"] = "revised"

    with open(path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False,
                  default_flow_style=False, width=120)

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect gaps but do not patch files")
    parser.add_argument("--chapters", type=str, default=None,
                        help="Comma-separated chapter numbers to audit (default: all at-risk)")
    args = parser.parse_args()

    chapters = (
        [int(c) for c in args.chapters.split(",")]
        if args.chapters
        else AT_RISK_CHAPTERS
    )

    print(f"[gap_audit] Loading oracle from {ORACLE_XML}")
    oracle = load_oracle(ORACLE_XML)
    print(f"[gap_audit] Oracle loaded: {len(oracle)} chapters")

    print("[gap_audit] Fetching secrets...")
    or_key = get_openrouter_key()
    az_key, az_endpoint, az_deploy = get_azure_creds()

    results = []
    total_gaps = 0
    total_fixed = 0

    for ch in chapters:
        oracle_geez = oracle.get(ch)
        if not oracle_geez:
            print(f"[ch {ch:03d}] SKIP — not in oracle")
            continue

        verses = list_verses(ch)
        if not verses:
            print(f"[ch {ch:03d}] SKIP — no YAML files found")
            continue

        for v in verses:
            path, data = load_verse_yaml(ch, v)
            if data is None:
                continue

            ref = data.get("reference", f"1 Enoch {ch}:{v}")
            source_geez = (data.get("source") or {}).get("text", "")
            english = (data.get("translation") or {}).get("text", "")

            print(f"[{ref}] Checking with {OPENROUTER_MODEL}...", end=" ", flush=True)
            try:
                result = detect_gap(oracle_geez, source_geez, english, ref, or_key)
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            time.sleep(0.5)  # rate limit

            if not result["gap"]:
                print("COMPLETE")
                results.append({"ref": ref, "status": "complete"})
                continue

            total_gaps += 1
            missing_geez = result["missing_geez"]
            print(f"GAP DETECTED\n  Missing Ge'ez: {missing_geez[:80]}")

            if args.dry_run:
                results.append({"ref": ref, "status": "gap", "missing_geez": missing_geez})
                continue

            print(f"  Translating with Azure GPT-5.4...", end=" ", flush=True)
            try:
                missing_en = translate_missing_clause(
                    ref, oracle_geez, english, missing_geez,
                    az_key, az_endpoint, az_deploy,
                )
                print(f"OK: {missing_en[:80]}")
            except Exception as e:
                print(f"TRANSLATION ERROR: {e}")
                results.append({"ref": ref, "status": "gap", "missing_geez": missing_geez,
                                 "error": str(e)})
                continue

            patch_yaml(path, data, missing_geez, missing_en, oracle_geez)
            total_fixed += 1
            results.append({
                "ref": ref, "status": "fixed",
                "missing_geez": missing_geez,
                "missing_english": missing_en,
            })

    # ── summary ──
    print("\n" + "=" * 60)
    print(f"AUDIT COMPLETE: {len(chapters)} chapters, "
          f"{total_gaps} gaps found, {total_fixed} fixed")
    print("=" * 60)
    for r in results:
        status = r["status"].upper()
        ref = r["ref"]
        if r["status"] == "gap":
            print(f"  [{status}] {ref}: {r.get('missing_geez','')[:60]}")
        elif r["status"] == "fixed":
            print(f"  [{status}] {ref}: +'{r.get('missing_english','')[:60]}'")

    if not args.dry_run and total_fixed > 0:
        print("\n[gap_audit] Committing fixes...")
        fixed_refs = [r["ref"] for r in results if r["status"] == "fixed"]
        msg = (
            f"revise: 1 Enoch gap audit — restore {total_fixed} missing clause(s)\n\n"
            f"Detected by gpt-5.4-nano comparison against Beta maṣāḥǝft oracle.\n"
            f"Translated by Azure GPT-5.4 in POB optimal-equivalence style.\n"
            f"Affected: {', '.join(fixed_refs)}"
        )
        subprocess.run(["git", "add", str(ENOCH_TRANS)], cwd=REPO_ROOT, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=REPO_ROOT, check=True)
        subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=REPO_ROOT, check=True)
        print("[gap_audit] Pushed to main.")

    return 0 if total_gaps == total_fixed else 1


if __name__ == "__main__":
    sys.exit(main())
