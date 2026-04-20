#!/usr/bin/env python3
"""review_gemini.py — Gemini 2.5 Pro cross-reviewer for Swete transcriptions.

Parallel to tools/review_transcription.py (Azure GPT-5.4), but uses Gemini
2.5 Pro as a *different-family* vision model so its independent judgments
complement the Azure reviewer's. The on-disk JSON schema is identical to
the Azure reviewer so outputs merge cleanly downstream.

Three prompt variants are supported via --variant:

  generic      — default proofreader prompt (matches the Azure one)
  tobit-dual   — tells the model explicitly that Tobit pages in Swete
                 print B-text (Vaticanus) and S-text (Sinaiticus) side by
                 side, and to treat them as two independent texts when
                 reviewing. Avoids the false-positive cascade the Azure
                 reviewer hit on vol2_p0832-vol2_p0862.
  esdras-verse — tells the model to pay special attention to whether
                 leading digits on a line are real inline verse markers
                 or left-margin line numbers; used to audit the
                 line-number-captured-as-verse stripping from
                 apply_transcription_reviews.py.

Output layout (one directory per scope):
  sources/lxx/swete/reviews/gemini/<stem>.review.json
  sources/lxx/swete/reviews/gemini/<stem>.review.meta.json

Env var:
  GEMINI_API_KEY   required. Fetchable from AWS Secrets Manager
                   `/cartha/openclaw/gemini_api_key` (us-west-2).

Usage:
  python3 tools/review_gemini.py --vol 2 --pages 148-192 \\
          --variant esdras-verse --output-dir sources/lxx/swete/reviews/gemini_esdras

  python3 tools/review_gemini.py --vol 2 --pages 832-862 \\
          --variant tobit-dual --output-dir sources/lxx/swete/reviews/gemini_tobit
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

try:
    import transcribe_source
except ImportError:
    # Allow running from repo root.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import transcribe_source  # type: ignore

REPO_ROOT = transcribe_source.REPO_ROOT
PROMPTS_DIR = REPO_ROOT / "tools" / "prompts"
TRANSCRIBED_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "gemini"

MODEL = "gemini-2.5-pro"
PROMPT_VERSION = "gemini_review_v1_2026-04-19"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

SECTION_VALUES = ["BODY", "APPARATUS", "RUNNING HEAD", "MARGINALIA"]
SEVERITY_VALUES = ["meaning-altering", "grammatical", "cosmetic"]
CONFIDENCE_VALUES = ["high", "medium", "low"]
CATEGORY_VALUES = [
    "apparatus-merge",
    "missing-prefix",
    "missing-letter",
    "extra-letter",
    "accent",
    "breathing",
    "name-misread",
    "case",
    "line-number-captured-as-verse",
    "missing-phrase",
    "punctuation",
    "siglum-decode",
    "nomen-sacrum",
    "other",
]

# Gemini responseSchema — subset of JSON schema Gemini supports.
# Keys map 1:1 to the Azure tool-call schema so outputs can be merged.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "running_head_match": {"type": "boolean"},
        "body_correct": {"type": "boolean"},
        "apparatus_correct": {"type": "boolean"},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": SECTION_VALUES},
                    "location": {"type": "string"},
                    "current": {"type": "string"},
                    "correct": {"type": "string"},
                    "severity": {"type": "string", "enum": SEVERITY_VALUES},
                    "category": {"type": "string", "enum": CATEGORY_VALUES},
                    "confidence": {"type": "string", "enum": CONFIDENCE_VALUES},
                    "note": {"type": "string"},
                },
                "required": [
                    "section",
                    "location",
                    "current",
                    "correct",
                    "severity",
                    "category",
                    "confidence",
                    "note",
                ],
                "propertyOrdering": [
                    "section",
                    "location",
                    "current",
                    "correct",
                    "severity",
                    "category",
                    "confidence",
                    "note",
                ],
            },
        },
        "uncertain": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["location", "note"],
                "propertyOrdering": ["location", "note"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": [
        "running_head_match",
        "body_correct",
        "apparatus_correct",
        "corrections",
        "uncertain",
        "notes",
    ],
    "propertyOrdering": [
        "running_head_match",
        "body_correct",
        "apparatus_correct",
        "corrections",
        "uncertain",
        "notes",
    ],
}


BASE_RULES = """You are a proofreader of a polytonic Greek transcription. You will
receive:

1. One scanned Swete LXX page image.
2. An existing UTF-8 transcription of that exact page.

Your job is **review only, not retranscription**. Compare the existing
transcription against the page image and report only real differences.
Preserve anything already correct.

Review rules:

1. Compare the page word-for-word. Verify running head, BODY, APPARATUS,
   and any marginalia present in the transcript.

2. BODY and APPARATUS are independent. Never import a variant reading
   from the apparatus into the BODY. If the BODY was altered to match an
   apparatus variant, report `category: "apparatus-merge"`.

3. Left-margin line numbers are not verse numbers. Swete sometimes
   prints page-line indicators in the outer margin. If these leaked into
   the BODY as verse markers, report `category: "line-number-captured-as-verse"`.

4. Be cautious with compound verbs. Prefixes like δι-, ἐπι-, κατα-, ἐν-,
   ἀπο- are easy to drop. Prefer `missing-prefix` when the core word is
   present but the prefix is wrong or missing.

5. Semitic names: in name lists, do not normalize toward familiar Greek
   vocabulary. Use `name-misread` when the transcript got the name wrong.

6. Sigla and nomina sacra: in apparatus, distinguish manuscript sigla
   (especially ℵ, A, B, C, Q) from ordinary Greek letters. Use
   `siglum-decode` or `nomen-sacrum` as appropriate.

7. Accent/breathing corrections should be conservative. Only report them
   if the image is clear enough.

8. Missing text must be anchored. If the transcript omitted a word or
   phrase, set `current` to the exact nearby transcript span where the
   insertion belongs, and set `correct` to that span with the missing
   text inserted. This keeps corrections mechanically applicable.

9. If you are not confident enough to correct it, put it under
   `uncertain`. Do not guess.

Output rules:

- Return a single JSON object matching the required schema.
- `running_head_match`, `body_correct`, `apparatus_correct` reflect the
  page as a whole.
- `corrections` lists real mistakes only.
- `confidence` reflects how visually certain you are about that specific
  correction.
- `notes` may mention unusual layout or anything helpful for triage.
"""

TOBIT_DUAL_ADDENDUM = """

**CRITICAL CONTEXT — TOBIT DUAL-RECENSION PAGES.**

Swete prints the book of Tobit in two parallel recensions on the same
page: the B-text (Codex Vaticanus — the upper block, usually labeled or
flush-left) and the S-text (Codex Sinaiticus — the lower block, usually
indented or visually separated). Both are the "body" of the page. They
are **independent witnesses** to Tobit, not corruptions of each other.

Do NOT flag BODY text as wrong merely because it differs from the OTHER
recension on the same page. Each recension is correct as its own text
and should be compared only against what the scan shows for THAT
recension. A word that appears in the S-text section but not in the
B-text section is NOT a transcript error in the B-text.

If the transcript has merged or swapped the two recensions, use
`category: "apparatus-merge"` with a note explaining which recension
leaked into which. Otherwise prefer not to flag cross-recension
differences at all.
"""

ESDRAS_VERSE_ADDENDUM = """

**CRITICAL CONTEXT — 1 ESDRAS VERSE-NUMBER AUDIT.**

This page may be from 1 Esdras. Swete's 1 Esdras uses inline verse
numbers that are *visually indistinguishable* from left-margin line
numbers. A prior automated pass may have stripped what it thought were
spurious line numbers, some of which were real verse markers.

For every leading digit or parenthesized digit in the BODY of this
page, verify against the image whether the digit is:

(a) A real inline verse marker (they appear inside or beside the text
    and must be preserved) — if the transcript is missing it, flag
    with `category: "missing-prefix"` and severity `meaning-altering`.

(b) A left-margin page-line indicator (must NOT be present in the body
    of the transcript) — if still present, flag with
    `category: "line-number-captured-as-verse"`.

Be generous with `uncertain` if you cannot tell from the scan which
kind a particular digit is.
"""


PROMPT_VARIANTS = {
    "generic": BASE_RULES,
    "tobit-dual": BASE_RULES + TOBIT_DUAL_ADDENDUM,
    "esdras-verse": BASE_RULES + ESDRAS_VERSE_ADDENDUM,
}


def gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. "
            "Fetch from AWS Secrets Manager `/cartha/openclaw/gemini_api_key` (us-west-2)."
        )
    return key


def transcript_path(vol: int, page: int) -> pathlib.Path:
    return TRANSCRIBED_DIR / f"vol{vol}_p{page:04d}.txt"


def review_paths(out_dir: pathlib.Path, vol: int, page: int) -> tuple[pathlib.Path, pathlib.Path]:
    stem = f"vol{vol}_p{page:04d}"
    return out_dir / f"{stem}.review.json", out_dir / f"{stem}.review.meta.json"


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_prompt(vol: int, page: int, transcript_text: str) -> str:
    return (
        f"Review Swete volume {vol}, scan page {page}, against the existing transcription below. "
        "Find transcription mistakes only. Preserve anything already correct.\n\n"
        "===EXISTING TRANSCRIPTION===\n"
        f"{transcript_text}\n"
        "===END TRANSCRIPTION===\n"
    )


def call_gemini_review(
    image_bytes: bytes,
    system_prompt: str,
    user_text: str,
    *,
    max_output_tokens: int,
    timeout: int = 300,
) -> tuple[dict[str, Any], str]:
    api_key = gemini_api_key()
    url = f"{API_BASE}/{MODEL}:generateContent?key={api_key}"
    b64 = base64.b64encode(image_bytes).decode("ascii")

    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": user_text},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "maxOutputTokens": max_output_tokens,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail[:600]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    candidates = body.get("candidates") or []
    if not candidates:
        # Some failure modes: safety block, truncation
        pf = body.get("promptFeedback") or {}
        raise RuntimeError(f"Gemini returned no candidates; promptFeedback={pf}")
    cand = candidates[0]
    if cand.get("finishReason") not in (None, "STOP", "MAX_TOKENS"):
        raise RuntimeError(f"Gemini finishReason={cand.get('finishReason')}")
    parts = (cand.get("content") or {}).get("parts") or []
    text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    raw_text = "".join(text_parts).strip()
    if not raw_text:
        raise RuntimeError("Gemini returned empty text")

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini response was not valid JSON: {exc}; text[:300]={raw_text[:300]!r}") from exc

    model_id = (body.get("modelVersion") or MODEL)
    return parsed, model_id


def process_page(
    vol: int,
    page: int,
    out_dir: pathlib.Path,
    system_prompt: str,
    variant: str,
    *,
    width: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    t_path = transcript_path(vol, page)
    if not t_path.exists():
        raise FileNotFoundError(f"missing transcript: {t_path}")

    transcript_text = t_path.read_text(encoding="utf-8")
    image_bytes, provenance_url = transcribe_source.fetch_swete_image(vol, page, width)
    image_sha = hashlib.sha256(image_bytes).hexdigest()

    started = time.time()
    review, model_id = call_gemini_review(
        image_bytes,
        system_prompt,
        user_prompt(vol, page, transcript_text),
        max_output_tokens=max_output_tokens,
    )
    duration = round(time.time() - started, 2)

    out_path, meta_path = review_paths(out_dir, vol, page)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _rel(p: pathlib.Path) -> str:
        try:
            return str(p.resolve().relative_to(REPO_ROOT))
        except ValueError:
            return str(p)

    meta = {
        "source": "swete",
        "vol": vol,
        "page": page,
        "transcript_path": _rel(t_path),
        "output_path": _rel(out_path),
        "image_width_px": width,
        "image_sha256": image_sha,
        "image_bytes": len(image_bytes),
        "provenance_url": provenance_url,
        "reviewer": "gemini",
        "model": model_id,
        "prompt_version": PROMPT_VERSION,
        "prompt_variant": variant,
        "reviewed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "transcript_sha256": sha256_hex(transcript_text),
        "corrections": len(review.get("corrections") or []),
        "uncertain": len(review.get("uncertain") or []),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vol", required=True, type=int, choices=[1, 2, 3])
    parser.add_argument("--page", type=int)
    parser.add_argument("--pages", help="Range(s), e.g. '148-192' or '148-192,832-862'")
    parser.add_argument("--width", type=int, default=1500)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--max-output-tokens", type=int, default=8000)
    parser.add_argument("--variant", choices=sorted(PROMPT_VARIANTS.keys()), default="generic")
    parser.add_argument("--output-dir")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        pages = transcribe_source.resolve_pages(args.page, args.pages)
    except ValueError as exc:
        parser.error(str(exc))

    out_dir = pathlib.Path(args.output_dir).resolve() if args.output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    system_prompt = PROMPT_VARIANTS[args.variant]

    def already_done(page: int) -> bool:
        out_path, _ = review_paths(out_dir, args.vol, page)
        return out_path.exists()

    todo = [pg for pg in pages if not (args.skip_existing and already_done(pg))]
    skipped = len(pages) - len(todo)

    if args.dry_run:
        print(f"would review {len(todo)} page(s) into {out_dir}  variant={args.variant}")
        for pg in todo:
            print(f"  vol{args.vol} p{pg:04d}")
        if skipped:
            print(f"skipping {skipped} existing page(s)")
        return 0

    results: dict[int, tuple[dict[str, Any] | None, str | None]] = {}

    def worker(page: int):
        try:
            return page, process_page(
                args.vol,
                page,
                out_dir,
                system_prompt,
                args.variant,
                width=args.width,
                max_output_tokens=args.max_output_tokens,
            ), None
        except Exception as exc:
            return page, None, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(worker, pg) for pg in todo]
        for future in as_completed(futures):
            page, meta, err = future.result()
            results[page] = (meta, err)
            if err:
                print(f"  FAIL vol{args.vol} p{page:04d}: {err[:400]}", flush=True)
            else:
                print(
                    f"  OK   vol{args.vol} p{page:04d}  {meta['duration_seconds']:>6.1f}s  "
                    f"{meta['corrections']:>2d} corr  {meta['uncertain']:>2d} uncertain  "
                    f"[{meta['prompt_variant']}]",
                    flush=True,
                )

    n_ok = sum(1 for meta, err in results.values() if err is None)
    n_fail = len(results) - n_ok
    print(
        f"\ndone: {n_ok} ok, {n_fail} failed, {skipped} skipped; reviews in {out_dir}",
        flush=True,
    )
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
