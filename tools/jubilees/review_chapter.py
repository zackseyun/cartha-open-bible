#!/usr/bin/env python3
"""review_chapter.py — Gemini 3.1 Pro review/revision for one Jubilees chapter."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

import yaml

import build_review_prompt

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

import sys
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import ocr_geez  # noqa: E402

MODEL_ID = "gemini-3.1-pro-preview"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def call_vertex_json(user_text: str, *, model: str) -> str:
    secret_ids = [s.strip() for s in os.environ.get(
        "VERTEX_SECRET_IDS",
        "/cartha/vertex/gemini-sa,/cartha/openclaw/gemini_api_key_2",
    ).split(",") if s.strip()]
    body = {
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "maxOutputTokens": 24000,
            "thinkingConfig": {"thinkingBudget": 512},
        },
    }
    last_err: Exception | None = None
    for secret_id in secret_ids:
        try:
            os.environ["VERTEX_SECRET_ID"] = secret_id
            ocr_geez._VERTEX_CACHE["token"] = ""
            ocr_geez._VERTEX_CACHE["expiry"] = 0.0
            ocr_geez._VERTEX_CACHE["project"] = ""
            token, project_id = ocr_geez.vertex_access_token()
            location = ocr_geez.DEFAULT_VERTEX_LOCATION
            api_host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
            url = (
                f"https://{api_host}/v1/projects/{project_id}/locations/{location}/"
                f"publishers/google/models/{model}:generateContent"
            )
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.loads(r.read().decode("utf-8"))
            cand = (resp.get("candidates") or [None])[0]
            if not cand:
                raise RuntimeError(f"no candidates: {resp}")
            parts = cand.get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if not text:
                raise RuntimeError("empty response")
            return text
        except Exception as exc:
            last_err = exc
            time.sleep(2)
            continue
    raise last_err or RuntimeError("vertex review failed across all configured secrets")


def parse_review_json(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    philosophy = str(out.get("translation_philosophy", "") or "").strip().lower()
    aliases = {
        "optimal equivalence": "optimal-equivalence",
        "optimal_equivalence": "optimal-equivalence",
        "optimal equivalence.": "optimal-equivalence",
    }
    if philosophy in aliases:
        out["translation_philosophy"] = aliases[philosophy]
    elif "optimal" in philosophy:
        out["translation_philosophy"] = "optimal-equivalence"
    elif "formal" in philosophy and "dynamic" not in philosophy:
        out["translation_philosophy"] = "formal"
    elif "dynamic" in philosophy and "formal" not in philosophy:
        out["translation_philosophy"] = "dynamic"
    if isinstance(out.get("issues_found"), str):
        out["issues_found"] = [out["issues_found"]]
    if out.get("theological_decisions") is None:
        out["theological_decisions"] = []
    if out.get("footnotes") is None:
        out["footnotes"] = []
    return out


def validate_payload(data: dict[str, Any]) -> None:
    required = ["english_text", "translation_philosophy", "lexical_decisions", "review_summary", "issues_found"]
    for key in required:
        if key not in data:
            raise ValueError(f"review payload missing {key}")
    if not str(data["english_text"]).strip():
        raise ValueError("english_text empty")
    if data["translation_philosophy"] not in {"formal", "dynamic", "optimal-equivalence"}:
        data["translation_philosophy"] = "optimal-equivalence"
    if not isinstance(data["lexical_decisions"], list):
        raise ValueError("lexical_decisions must be list")
    if not isinstance(data["issues_found"], list):
        raise ValueError("issues_found must be list")


def apply_review(chapter: int, payload: dict[str, Any], *, prompt_sha: str, model_version: str) -> pathlib.Path:
    path = build_review_prompt.chapter_yaml_path(chapter)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["translation"]["text"] = str(payload["english_text"]).strip()
    doc["translation"]["philosophy"] = payload["translation_philosophy"]
    if payload.get("footnotes"):
        doc["translation"]["footnotes"] = payload["footnotes"]
    elif "footnotes" in doc.get("translation", {}):
        doc["translation"].pop("footnotes", None)
    doc["lexical_decisions"] = payload.get("lexical_decisions", [])
    doc["theological_decisions"] = payload.get("theological_decisions", [])
    review_pass = {
        "reviewer_model": MODEL_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "prompt_sha256": prompt_sha,
        "summary": str(payload["review_summary"]).strip(),
        "issues_found": [str(x).strip() for x in payload.get("issues_found", []) if str(x).strip()],
        "model_version": model_version,
    }
    doc.setdefault("review_passes", []).append(review_pass)
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, required=True)
    args = ap.parse_args()
    prompt, _ = build_review_prompt.build_prompt(args.chapter)
    prompt_sha = sha256_hex(prompt)
    raw = call_vertex_json(prompt, model=MODEL_ID)
    payload = normalize_payload(parse_review_json(raw))
    validate_payload(payload)
    out = apply_review(args.chapter, payload, prompt_sha=prompt_sha, model_version=MODEL_ID)
    print(f"Wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
