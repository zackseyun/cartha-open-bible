#!/usr/bin/env python3
"""refine_chapter_vertex.py — targeted Vertex extraction for one Jubilees chapter.

Use this for chapters whose page boundaries are known from running heads but
whose generic extraction remains weak.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import time
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

import sys
sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
import ocr_geez  # noqa: E402


SYSTEM_PROMPT = """You are refining a single chapter extraction from OCR'd Ge'ez text of the Book of Jubilees.

You will receive:
- the target chapter number
- the expected last verse number
- OCR text for the relevant PDF pages
- explicit running-head notes that describe where the target chapter begins and ends

Return ONLY a JSON array of:
{"verse": <int>, "text": "<Ge'ez text>"}

Rules:
- Include ONLY verses from the target chapter.
- Start at verse 1 and end at the expected last verse.
- Do not skip verse numbers unless the OCR genuinely lacks the verse.
- Exclude preceding-chapter and following-chapter material.
- Preserve Ge'ez text; do not translate or paraphrase.
- Ignore running heads, apparatus, and editorial notes.
"""


def parse_pages(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(token))
    return sorted(dict.fromkeys(out))


def call_vertex_json(user_text: str, *, model: str) -> str:
    secret_ids = [s.strip() for s in os.environ.get(
        "VERTEX_SECRET_IDS",
        "/cartha/vertex/gemini-sa,/cartha/openclaw/gemini_api_key_2",
    ).split(",") if s.strip()]
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
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
    raise last_err or RuntimeError("vertex call failed across all configured secrets")


def load_page_text(page: int) -> str:
    path = REPO_ROOT / "sources" / "jubilees" / "ethiopic" / "transcribed" / "charles_1895" / "body" / f"charles_1895_ethiopic_p{page:04d}.txt"
    return path.read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--expected-last-verse", type=int, required=True)
    ap.add_argument("--head-note", action="append", default=[])
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--model", default="gemini-3.1-pro-preview")
    args = ap.parse_args()

    pages = parse_pages(args.pages)
    joined = []
    for page in pages:
        joined.append(f"[[PDF_PAGE_{page}]]\n{load_page_text(page).strip()}\n")

    user_text = json.dumps(
        {
            "book": "Jubilees",
            "chapter": args.chapter,
            "expected_last_verse": args.expected_last_verse,
            "pages": pages,
            "running_head_notes": args.head_note,
            "ocr_text": "\n\n".join(joined),
        },
        ensure_ascii=False,
    )
    raw = call_vertex_json(user_text, model=args.model)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            raise
        data = json.loads(m.group(0))
    cleaned = []
    for item in data:
        try:
            verse = int(item["verse"])
            text = str(item["text"]).strip()
        except Exception:
            continue
        if verse < 1 or verse > args.expected_last_verse or not text:
            continue
        cleaned.append({"verse": verse, "text": text})
    cleaned.sort(key=lambda x: x["verse"])
    dedup = []
    seen = set()
    for item in cleaned:
        if item["verse"] in seen:
            continue
        seen.add(item["verse"])
        dedup.append(item)
    args.out.write_text(json.dumps(dedup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"verses={len(dedup)} first_last={(dedup[0]['verse'], dedup[-1]['verse']) if dedup else None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
