#!/usr/bin/env python3
"""pilot_reference_triangulation.py — A/B pilot measuring the signal of
injecting a published scholarly English reference (Charles 1913 APOT)
into the v3 author-intent review prompt.

For each verse in a target list, runs TWO reviews with Gemini 3.1 Pro:
  arm A (control)   : v3 author-intent system prompt + verse + ±5v context
  arm B (treatment) : same + Charles 1913 English for this chapter

Saves per-verse JSON into state/reviews/pilot/<timestamp>/<arm>/ and
emits a diff report comparing findings across arms.

Usage:
  tools/pilot_reference_triangulation.py \
      --book psalms_of_solomon --chapter 17 \
      --verses 1,3,6,15,23,32,44,47,50 \
      --reference sources/lxx/psalms_of_solomon/references/charles_1913_vol2_pss17.txt
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gemini_review_worker as grw  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PILOT_ROOT = REPO_ROOT / "state" / "reviews" / "pilot"
AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def fetch_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    # Fall back to AWS Secrets Manager
    r = subprocess.run(
        [
            "aws", "secretsmanager", "get-secret-value",
            "--secret-id", "/cartha/openclaw/gemini_api_key",
            "--region", "us-west-2",
            "--query", "SecretString", "--output", "text",
        ],
        capture_output=True, text=True, check=True, timeout=15,
    )
    raw = r.stdout.strip()
    try:
        return json.loads(raw).get("api_key", raw)
    except json.JSONDecodeError:
        return raw


def build_user_payload(
    *,
    verse_yaml: str,
    context_block: str,
    reference_block: str = "",
    book_context: str = "",
) -> str:
    parts: list[str] = [
        "Review the following verse draft. Return a structured JSON review per the schema.",
        "",
    ]
    if book_context:
        parts += [
            "===BOOK CONTEXT (author, audience, edition, translation challenges)===",
            book_context,
            "===END BOOK CONTEXT===",
            "",
        ]
    if context_block:
        parts += [
            "===CHAPTER CONTEXT (neighboring verses for reference only — do not review these)===",
            context_block,
            "===END CONTEXT===",
            "",
        ]
    if reference_block:
        parts += [
            "===PUBLISHED ENGLISH REFERENCE (scholarly comparison for this chapter)===",
            "The following is a published scholarly English translation of THIS CHAPTER "
            "from a peer reference edition. It is NOT authority — do not recommend changes "
            "on the basis of 'the reference says X.' Use it as a data point to check "
            "whether the current draft diverges from what a careful English reader of the "
            "source would expect. Cite source-language evidence for any finding. The "
            "reference may use different verse numbering; locate the equivalent verse "
            "yourself.",
            "",
            reference_block,
            "===END PUBLISHED REFERENCE===",
            "",
        ]
    parts += [
        "===TARGET VERSE YAML===",
        verse_yaml,
        "===END===",
    ]
    return "\n".join(parts)


def call_gemini(
    *,
    system_prompt: str,
    user_text: str,
    api_key: str,
    model: str = "gemini-3.1-pro-preview",
    timeout: int = 180,
    max_output_tokens: int = 12000,
    retries: int = 5,
) -> tuple[dict[str, Any], str]:
    url = f"{AI_STUDIO_BASE}/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": grw.RESPONSE_SCHEMA,
            "maxOutputTokens": max_output_tokens,
        },
    }
    backoffs = [10, 30, 60, 120, 240]
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_err = RuntimeError(f"Gemini HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)] + random.uniform(0, 3))
                continue
            raise last_err
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = RuntimeError(f"{type(exc).__name__}: {exc}")
            if attempt < retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            raise last_err
    else:
        raise last_err or RuntimeError("exhausted retries")

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"no candidates; promptFeedback={body.get('promptFeedback')}")
    cand = candidates[0]
    parts = (cand.get("content") or {}).get("parts") or []
    raw = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    if not raw:
        raise RuntimeError(f"empty text; finishReason={cand.get('finishReason')}")
    parsed = json.loads(raw)
    model_id = body.get("modelVersion") or model
    return parsed, model_id


def run_arm(
    *,
    arm_name: str,
    testament: str,
    book_slug: str,
    chapter: int,
    verse: int,
    reference_block: str,
    system_prompt: str,
    book_context: str,
    api_key: str,
    output_dir: pathlib.Path,
) -> dict[str, Any]:
    t0 = time.time()
    verse_yaml = grw.read_verse_yaml(testament, book_slug, chapter, verse)
    context_block = grw.read_context_snippet(testament, book_slug, chapter, verse)
    user_text = build_user_payload(
        verse_yaml=verse_yaml,
        context_block=context_block,
        reference_block=reference_block,
        book_context=book_context,
    )
    parsed, model_id = call_gemini(
        system_prompt=system_prompt,
        user_text=user_text,
        api_key=api_key,
    )
    dur = round(time.time() - t0, 2)
    record = {
        "arm": arm_name,
        "reference": "charles_1913_apot_vol2" if reference_block else None,
        "testament": testament,
        "book_slug": book_slug,
        "chapter": chapter,
        "verse": verse,
        "model_id": model_id,
        "duration_s": dur,
        "review": parsed,
        "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = output_dir / arm_name / f"{book_slug}_{chapter:03d}_{verse:03d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"[{arm_name}] {book_slug} {chapter}:{verse} "
        f"score={parsed.get('agreement_score')} "
        f"verdict={parsed.get('verdict')} "
        f"issues={len(parsed.get('issues') or [])} "
        f"({dur}s)",
        flush=True,
    )
    return record


def summarize(records: list[dict[str, Any]], output_dir: pathlib.Path) -> None:
    """Produce a diff report comparing arms per verse."""
    by_verse: dict[int, dict[str, dict[str, Any]]] = {}
    for r in records:
        v = r["verse"]
        arm = r["arm"]
        by_verse.setdefault(v, {})[arm] = r
    lines: list[str] = []
    lines.append("# Pilot: reference-triangulation signal measurement")
    lines.append("")
    lines.append(f"- Generated: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append(f"- Reference: Charles 1913 APOT vol 2 (public domain)")
    lines.append(f"- Model: gemini-3.1-pro-preview")
    lines.append(f"- System prompt: gemini_review_v3_author_intent.md")
    lines.append("")
    lines.append("## Per-verse comparison")
    lines.append("")
    for v in sorted(by_verse.keys()):
        a = by_verse[v].get("control")
        b = by_verse[v].get("treatment")
        a_rev = (a or {}).get("review") or {}
        b_rev = (b or {}).get("review") or {}
        a_issues = a_rev.get("issues") or []
        b_issues = b_rev.get("issues") or []
        lines.append(f"### verse {v}")
        lines.append("")
        lines.append(
            f"- control   : score={a_rev.get('agreement_score'):<5} "
            f"verdict={a_rev.get('verdict'):<12} "
            f"issues={len(a_issues)}"
        )
        lines.append(
            f"- treatment : score={b_rev.get('agreement_score'):<5} "
            f"verdict={b_rev.get('verdict'):<12} "
            f"issues={len(b_issues)}"
        )
        lines.append("")
        if a_issues:
            lines.append("**Control issues:**")
            for i, iss in enumerate(a_issues, 1):
                lines.append(
                    f"  {i}. [{iss.get('category')}/{iss.get('severity')}] "
                    f"{iss.get('current_rendering')!r} → {iss.get('suggested_rewrite')!r}"
                )
                lines.append(f"     rationale: {iss.get('rationale', '')[:250]}")
            lines.append("")
        if b_issues:
            lines.append("**Treatment issues:**")
            for i, iss in enumerate(b_issues, 1):
                lines.append(
                    f"  {i}. [{iss.get('category')}/{iss.get('severity')}] "
                    f"{iss.get('current_rendering')!r} → {iss.get('suggested_rewrite')!r}"
                )
                lines.append(f"     rationale: {iss.get('rationale', '')[:250]}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Aggregate stats
    c_scores = [
        (by_verse[v]["control"]["review"].get("agreement_score") or 0)
        for v in by_verse if "control" in by_verse[v]
    ]
    t_scores = [
        (by_verse[v]["treatment"]["review"].get("agreement_score") or 0)
        for v in by_verse if "treatment" in by_verse[v]
    ]
    c_issues = sum(
        len(by_verse[v]["control"]["review"].get("issues") or [])
        for v in by_verse if "control" in by_verse[v]
    )
    t_issues = sum(
        len(by_verse[v]["treatment"]["review"].get("issues") or [])
        for v in by_verse if "treatment" in by_verse[v]
    )
    lines.append("## Aggregate")
    lines.append("")
    if c_scores:
        lines.append(f"- Control   mean agreement: {sum(c_scores)/len(c_scores):.3f} ({len(c_scores)} verses)")
    if t_scores:
        lines.append(f"- Treatment mean agreement: {sum(t_scores)/len(t_scores):.3f} ({len(t_scores)} verses)")
    lines.append(f"- Control   total issues flagged: {c_issues}")
    lines.append(f"- Treatment total issues flagged: {t_issues}")

    out = output_dir / "pilot_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--testament", default="deuterocanon")
    ap.add_argument("--book", required=True, help="book slug e.g. psalms_of_solomon")
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--verses", required=True, help="comma-separated verse numbers, e.g. 1,3,6,15")
    ap.add_argument("--reference", required=True, help="path to reference text file (chapter-scope)")
    ap.add_argument("--arms", default="control,treatment", help="which arms to run")
    ap.add_argument("--output-root", default=None)
    args = ap.parse_args()

    verses = [int(x.strip()) for x in args.verses.split(",") if x.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    ref_path = REPO_ROOT / args.reference
    reference_block = ref_path.read_text(encoding="utf-8")

    system_prompt = grw.load_v3_system_prompt()
    book_context = grw.load_book_context(args.book)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        pathlib.Path(args.output_root)
        if args.output_root
        else PILOT_ROOT / f"{args.book}_{args.chapter:03d}_{stamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = fetch_gemini_key()

    records: list[dict[str, Any]] = []
    for v in verses:
        for arm in arms:
            ref = reference_block if arm == "treatment" else ""
            try:
                r = run_arm(
                    arm_name=arm,
                    testament=args.testament,
                    book_slug=args.book,
                    chapter=args.chapter,
                    verse=v,
                    reference_block=ref,
                    system_prompt=system_prompt,
                    book_context=book_context,
                    api_key=api_key,
                    output_dir=output_dir,
                )
                records.append(r)
            except Exception as exc:
                print(f"[{arm}] v{v} FAILED: {type(exc).__name__}: {exc}", flush=True)

    summarize(records, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
