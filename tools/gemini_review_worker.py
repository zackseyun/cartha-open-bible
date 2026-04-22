#!/usr/bin/env python3
"""gemini_review_worker.py — claim + run Gemini Pro translation-review jobs.

Parallel to chapter_worker.py (drafting worker). Claims rows from the
`review_jobs` table, runs a Gemini 2.5 Pro call against the verse YAML,
saves a structured review report, and updates the job row.

Output: one immutable review JSON per review job under
  state/reviews/gemini/<strategy>/<testament>/<book_slug>/<NNN>/<VVV>.job-<id>.json

Each review contains:
  - verse ref, source Greek/Hebrew, current English
  - Gemini's verdict: agreement_score (0..1), a list of flagged issues
    with category + severity + suggested rewrite, and an overall note.

Env:
  GEMINI_API_KEY — fetchable from AWS Secrets Manager
                   `/cartha/openclaw/gemini_api_key` (us-west-2).

Usage:
  python3 tools/gemini_review_worker.py --worker-id g1 --max-jobs 100
  python3 tools/gemini_review_worker.py --worker-id g1 --strategy high_scrutiny
  python3 tools/gemini_review_worker.py --worker-id g1 --stop-when-empty
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import json
import os
import pathlib
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import chapter_queue  # noqa: E402
import gemini_review_queue as rq  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = chapter_queue.DEFAULT_DB_PATH
REVIEWS_DIR = REPO_ROOT / "state" / "reviews" / "gemini"

# Two Gemini endpoint modes — we prefer Vertex AI when a service-account key
# is configured (billed project with real quotas) and fall back to AI Studio
# (free-tier API key) otherwise.
AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_PROMPTS_DIR = pathlib.Path(__file__).resolve().parent / "prompts"
CONTEXT_WINDOW_VERSES = 5  # ±5 verses around target for Pass 2
VERTEX_LOCATION = (os.environ.get("GCP_LOCATION", "global") or "global").strip()
PROMPT_VERSION = "gemini_translation_review_v1_2026-04-21"
PROMPT_VERSION_V2 = "gemini_translation_review_v2_enhanced_2026-04-21"
PROMPT_VERSION_V3 = "gemini_translation_review_v3_author_intent_2026-04-22"

# Strategies that should use the v2 (enhanced, context-rich) prompt.
V2_STRATEGIES = {"enhanced_review", "low_agreement_recheck"}

# Strategies that should use the v3 (author-intent, book-aware) prompt.
# Phase 9 strategies opt in here; canonical strategies stay on v1/v2 for now
# to avoid mid-pass prompt drift.
V3_STRATEGIES = {
    "phase9_review",
    "phase9_greek",
    "phase9_latin_multiwitness",
    "phase9_nag_hammadi",
    "phase9_geez",
    "phase9_syriac",
    "phase10_greek_apocrypha",
    "phase10_ethiopic_pseudepigrapha",
    "phase10_coptic_gnostic",
}


_vertex_cached_token: dict[str, Any] = {"token": None, "expiry": 0.0, "project": None}


def _load_service_account_credentials() -> tuple[object, str] | None:
    """If GOOGLE_APPLICATION_CREDENTIALS points to a valid JSON, return
    `(credentials, project_id)`; else None."""
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not cred_path or not pathlib.Path(cred_path).exists():
        return None
    try:
        from google.oauth2 import service_account  # type: ignore
    except ImportError:
        return None
    with open(cred_path, encoding="utf-8") as fh:
        info = json.load(fh)
    project_id = info.get("project_id")
    if not project_id:
        return None
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return creds, project_id


def _vertex_access_token(force_refresh: bool = False) -> tuple[str, str]:
    """Get (access_token, project_id) for Vertex AI. Cached in-process.
    Treat tokens as expired 5 minutes before actual expiry to avoid the
    boundary where a long Gemini call outlives its token.
    """
    now = time.time()
    if (
        not force_refresh
        and _vertex_cached_token["token"]
        and _vertex_cached_token["expiry"] > now + 300  # 5-min safety margin
    ):
        return _vertex_cached_token["token"], _vertex_cached_token["project"]
    loaded = _load_service_account_credentials()
    if loaded is None:
        raise RuntimeError(
            "Vertex AI requires GOOGLE_APPLICATION_CREDENTIALS pointing at a "
            "service-account JSON with google-auth installed."
        )
    creds, project_id = loaded
    from google.auth.transport.requests import Request  # type: ignore
    creds.refresh(Request())
    token = creds.token
    expiry = creds.expiry.timestamp() if getattr(creds, "expiry", None) else (now + 3000)
    _vertex_cached_token["token"] = token
    _vertex_cached_token["expiry"] = expiry
    _vertex_cached_token["project"] = project_id
    return token, project_id


def _vertex_endpoint(model: str, force_refresh: bool = False) -> tuple[str, dict[str, str]]:
    """Return (URL, headers) for a Vertex AI generateContent call."""
    token, project_id = _vertex_access_token(force_refresh=force_refresh)
    location = VERTEX_LOCATION or "global"
    api_host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    url = (
        f"https://{api_host}/v1/"
        f"projects/{project_id}/locations/{location}/"
        f"publishers/google/models/{model}:generateContent"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return url, headers


def _aistudio_endpoint(model: str) -> tuple[str, dict[str, str]]:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Fetch from AWS Secrets Manager "
            "`/cartha/openclaw/gemini_api_key` (us-west-2)."
        )
    url = f"{AI_STUDIO_BASE}/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    return url, headers


def _gemini_endpoint(model: str) -> tuple[str, dict[str, str]]:
    """Pick Vertex AI when service account is configured, else AI Studio."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return _vertex_endpoint(model)
    return _aistudio_endpoint(model)

SYSTEM_PROMPT = """You are an expert biblical translator serving as a second-opinion reviewer for an English translation project.

You will receive:
  - One verse's original Greek (SBLGNT for NT) or Hebrew (WLC for OT) text.
  - The current English draft, produced by GPT-5.4.
  - The drafter's lexical/translation decisions (which senses they picked for ambiguous words).
  - Footnotes + alternatives already attached to the verse.
  - The drafter's translation philosophy ("optimal-equivalence" — a balance between formal and dynamic).

Your job is to flag REAL issues — not stylistic preferences. The current draft is allowed to stand as-is unless you can point to a specific improvement grounded in the source text.

Flag if:
  - The English meaning does not match the Greek/Hebrew (mistranslation).
  - A lexical choice is defensible in isolation but wrong given this context.
  - An English construction is awkward in a way that obscures the meaning.
  - Grammar/syntax force is lost in a meaning-affecting way.
  - A theologically weighted word is rendered in a way that loses the source's force.
  - Verse-internal consistency is broken (the same Greek word is rendered two ways in a way that misleads).

Do NOT flag:
  - Style preferences where the current reading is defensible.
  - Paraphrase-vs-literal balance, unless the current rendering is wrong.
  - Footnote gloss choices already present as lexical alternatives.
  - Settled project doctrine decisions unless this specific verse applies them incorrectly.

Prefer 0–2 issues. If a concern is only about a footnote, lexical-decision note, or metadata, set `target` accordingly and do NOT attach it to the main translation text.

Return a single JSON object matching the schema: agreement_score (0-1), issues[] (each with target, category, severity, confidence, span, current_rendering, suggested_rewrite, rationale), and an overall `notes` field.

Targets: translation_text, footnote, lexical_decision, theological_note, metadata, notes_only.
Categories: mistranslation, lexical, grammar, awkward_english, theological_weight, consistency, missing_nuance, other.
Severities: major, minor, suggestion.
"""


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "agreement_score": {"type": "number"},
        "verdict": {"type": "string", "enum": ["agree", "minor-issues", "major-issues"]},
        "issues": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": [
                            "translation_text",
                            "footnote",
                            "lexical_decision",
                            "theological_note",
                            "metadata",
                            "notes_only",
                        ],
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "mistranslation", "lexical", "grammar", "awkward_english",
                            "theological_weight", "consistency",
                            "missing_nuance", "other",
                        ],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["major", "minor", "suggestion"],
                    },
                    "confidence": {"type": "number"},
                    "span": {"type": "string"},
                    "current_rendering": {"type": "string"},
                    "suggested_rewrite": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "target", "category", "severity", "confidence", "span",
                    "current_rendering", "suggested_rewrite", "rationale",
                ],
                "propertyOrdering": [
                    "target", "category", "severity", "confidence", "span",
                    "current_rendering", "suggested_rewrite", "rationale",
                ],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["agreement_score", "verdict", "issues", "notes"],
    "propertyOrdering": ["agreement_score", "verdict", "issues", "notes"],
}


def utc_now() -> str:
    return chapter_queue.utc_now()


def gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Fetch from AWS Secrets Manager "
            "`/cartha/openclaw/gemini_api_key` (us-west-2)."
        )
    return key


def review_output_path(
    *,
    job_id: int,
    strategy: str,
    testament: str,
    book_slug: str,
    chapter: int,
    verse: int,
) -> pathlib.Path:
    return (
        REVIEWS_DIR
        / strategy
        / testament
        / book_slug
        / f"{chapter:03d}"
        / f"{verse:03d}.job-{job_id}.json"
    )


def read_verse_yaml(testament: str, book_slug: str, chapter: int, verse: int) -> str:
    # Normal chapter/verse layout
    path = REPO_ROOT / "translation" / testament / book_slug / f"{chapter:03d}" / f"{verse:03d}.yaml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Flat layout (section-per-file books like gospel_of_truth or jubilees):
    # the queue stores chapter=1, verse=section_number
    flat = REPO_ROOT / "translation" / testament / book_slug / f"{verse:03d}.yaml"
    if flat.exists() and chapter == 1:
        return flat.read_text(encoding="utf-8")
    raise FileNotFoundError(path)


_V2_PROMPT_CACHE: str | None = None


def load_v2_system_prompt() -> str:
    global _V2_PROMPT_CACHE
    if _V2_PROMPT_CACHE is None:
        p = _PROMPTS_DIR / "gemini_review_v2_enhanced.md"
        _V2_PROMPT_CACHE = p.read_text(encoding="utf-8")
    return _V2_PROMPT_CACHE


_V3_PROMPT_CACHE: str | None = None
_BOOK_CONTEXT_CACHE: dict[str, str] = {}


def load_v3_system_prompt() -> str:
    """v3 author-intent baseline. Single criterion: faithfulness to what
    the author wrote and meant for their original audience."""
    global _V3_PROMPT_CACHE
    if _V3_PROMPT_CACHE is None:
        p = _PROMPTS_DIR / "gemini_review_v3_author_intent.md"
        _V3_PROMPT_CACHE = p.read_text(encoding="utf-8")
    return _V3_PROMPT_CACHE


def load_book_context(book_slug: str) -> str:
    """Return the book-specific context (author, audience, source edition,
    translation challenges) for this book if a file exists, else empty.

    Looked up at `tools/prompts/book_contexts/<book_slug>.md`. Cached.
    """
    if book_slug in _BOOK_CONTEXT_CACHE:
        return _BOOK_CONTEXT_CACHE[book_slug]
    p = _PROMPTS_DIR / "book_contexts" / f"{book_slug}.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    _BOOK_CONTEXT_CACHE[book_slug] = text
    return text


def read_context_snippet(testament: str, book_slug: str, chapter: int, verse: int) -> str:
    """Return a compact text digest of neighboring verses (±CONTEXT_WINDOW_VERSES)
    for chapter context. Each verse is just source + English, no full YAML,
    so the prompt stays within budget."""
    import yaml as _yaml  # local import so top-level works w/o PyYAML for v1
    lines = []
    base_dir = REPO_ROOT / "translation" / testament / book_slug / f"{chapter:03d}"
    if not base_dir.exists():
        # Flat layout fallback: context lives in sibling section files
        flat_root = REPO_ROOT / "translation" / testament / book_slug
        if flat_root.exists() and any(p.suffix == ".yaml" for p in flat_root.iterdir()):
            base_dir = flat_root
        else:
            return ""
    verse_files: list[tuple[int, pathlib.Path]] = []
    for p in sorted(base_dir.glob("*.yaml")):
        try:
            v = int(p.stem)
        except ValueError:
            continue
        verse_files.append((v, p))
    target_idx = next((i for i, (v, _) in enumerate(verse_files) if v == verse), None)
    if target_idx is None:
        return ""
    start = max(0, target_idx - CONTEXT_WINDOW_VERSES)
    end = min(len(verse_files), target_idx + CONTEXT_WINDOW_VERSES + 1)
    for i in range(start, end):
        v, p = verse_files[i]
        if v == verse:
            continue  # the target itself is shown separately
        try:
            d = _yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        src = (d.get("source") or {}).get("text", "").strip()
        eng = (d.get("translation") or {}).get("text", "").strip()
        tag = "before" if v < verse else "after"
        lines.append(
            f"[{book_slug} {chapter}:{v} — context, {tag}]\n"
            f"  source: {src}\n"
            f"  english: {eng}\n"
        )
    return "\n".join(lines)


def call_gemini_review(
    verse_yaml: str,
    *,
    model: str,
    timeout: int = 240,
    max_output_tokens: int = 32000,
    retries: int = 6,
    system_prompt: str | None = None,
    context_block: str = "",
) -> tuple[dict[str, Any], str]:
    url, headers = _gemini_endpoint(model)

    user_parts: list[str] = [
        "Review the following verse draft. Return a structured JSON review per the schema.",
        "",
    ]
    if context_block:
        user_parts += [
            "===CHAPTER CONTEXT (neighboring verses for reference only — do not review these)===",
            context_block,
            "===END CONTEXT===",
            "",
        ]
    user_parts += [
        "===TARGET VERSE YAML===",
        verse_yaml,
        "===END===",
    ]
    user_text = "\n".join(user_parts)

    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_prompt or SYSTEM_PROMPT}]},
        "contents": [
            {"role": "user", "parts": [{"text": user_text}]},
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "maxOutputTokens": max_output_tokens,
        },
    }

    # Retry schedule: 429/503 can take minutes to clear. Use aggressive
    # exponential backoff with jitter. Parse Retry-After header if present.
    backoff_schedule = [15, 45, 90, 180, 300, 600]  # seconds; up to 10 min
    last_err: Exception | None = None
    force_token_refresh = False
    for attempt in range(retries):
        # Refresh URL+headers each attempt so we pick up rotated Vertex
        # OAuth tokens if the previous one expired.
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            url, headers = _vertex_endpoint(model, force_refresh=force_token_refresh)
            force_token_refresh = False  # reset; only force on 401
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
            detail = exc.read().decode("utf-8", errors="replace")
            last_err = RuntimeError(f"Gemini HTTP {exc.code}: {detail[:400]}")
            # 401 = expired OAuth token. Force a refresh and retry immediately.
            if exc.code == 401 and attempt < retries - 1:
                force_token_refresh = True
                time.sleep(1 + random.uniform(0, 2))
                continue
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after and retry_after.isdigit():
                    wait = min(int(retry_after), 600)
                else:
                    wait = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
                wait += random.uniform(0, 5)
                time.sleep(wait)
                continue
            raise last_err
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
            last_err = RuntimeError(f"Gemini request failed: {type(exc).__name__}: {exc}")
            if attempt < retries - 1:
                wait = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
                time.sleep(wait + random.uniform(0, 3))
                continue
            raise last_err

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates; promptFeedback={body.get('promptFeedback')}")
    cand = candidates[0]
    finish = cand.get("finishReason")
    if finish not in (None, "STOP", "MAX_TOKENS"):
        raise RuntimeError(f"Gemini finishReason={finish}")
    parts = (cand.get("content") or {}).get("parts") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    raw = "".join(texts).strip()
    if not raw:
        raise RuntimeError(
            f"Gemini returned empty text; finishReason={finish} "
            f"safetyRatings={cand.get('safetyRatings')}"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini response was not valid JSON: {exc}; head={raw[:300]!r}")
    model_id = body.get("modelVersion") or model
    return parsed, model_id


def connect() -> sqlite3.Connection:
    return rq.connect()


def claim_next(
    conn: sqlite3.Connection, worker_id: str, strategy: str | None, book_slug: str | None
) -> dict[str, Any] | None:
    conn.execute("BEGIN IMMEDIATE")
    # Pick a strategy weighted by sqrt(pending_count) + 1. This gives the
    # largest strategy more workers (proportional-ish) without completely
    # starving tiny strategies like random_sample. The sqrt softens extreme
    # ratios so even a 1-job-left strategy still gets occasional picks.
    if strategy:
        strategy_candidates: list[tuple[str, int]] = [(strategy, 1)]
    else:
        strategy_rows = conn.execute(
            "SELECT strategy, COUNT(*) AS cnt FROM review_jobs WHERE status=? GROUP BY strategy",
            (rq.STATUS_PENDING,),
        ).fetchall()
        strategy_candidates = [(r["strategy"], r["cnt"]) for r in strategy_rows]
    if not strategy_candidates:
        conn.commit()
        return None

    # Weights ~ sqrt(pending) + 1 so big pools get more but small ones
    # aren't starved.
    import math
    weights = [math.sqrt(n) + 1 for _, n in strategy_candidates]
    strategy_names = [s for s, _ in strategy_candidates]
    chosen_strategy = random.choices(strategy_names, weights=weights, k=1)[0]

    query = "SELECT * FROM review_jobs WHERE status=? AND strategy=?"
    params: list[Any] = [rq.STATUS_PENDING, chosen_strategy]
    if book_slug:
        query += " AND book_slug=?"
        params.append(book_slug)
    query += " ORDER BY id LIMIT 1"
    row = conn.execute(query, params).fetchone()
    if row is None:
        conn.commit()
        return None
    now = utc_now()
    conn.execute(
        """
        UPDATE review_jobs
        SET status=?, worker_id=?, attempts=attempts+1, claimed_at=?, updated_at=?
        WHERE id=?
        """,
        (rq.STATUS_RUNNING, worker_id, now, now, row["id"]),
    )
    conn.commit()
    claimed = conn.execute("SELECT * FROM review_jobs WHERE id=?", (row["id"],)).fetchone()
    return dict(claimed)


def mark_complete(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    review_path: str,
    agreement_score: float,
    issues_found: int,
) -> None:
    now = utc_now()
    conn.execute(
        """
        UPDATE review_jobs
        SET status=?, completed_at=?, updated_at=?, review_path=?,
            agreement_score=?, issues_found=?
        WHERE id=?
        """,
        (rq.STATUS_COMPLETED, now, now, review_path, agreement_score, issues_found, job_id),
    )
    conn.commit()


def mark_failed(conn: sqlite3.Connection, job_id: int, err: str) -> None:
    now = utc_now()
    conn.execute(
        """
        UPDATE review_jobs
        SET status=?, last_error=?, updated_at=?
        WHERE id=?
        """,
        (rq.STATUS_FAILED, err[:800], now, job_id),
    )
    conn.commit()


def run_job(
    conn: sqlite3.Connection, job: dict[str, Any], model_override: str | None = None
) -> dict[str, Any]:
    testament = job["testament"]
    book_slug = job["book_slug"]
    chapter = int(job["chapter"])
    verse = int(job["verse"])
    model = model_override or job["model"]
    strategy = job["strategy"]
    job_id = int(job["id"])

    verse_yaml = read_verse_yaml(testament, book_slug, chapter, verse)

    # Dispatch: v3 author-intent strategies get the v3 prompt + per-book
    # context + chapter context. v2 strategies get the enhanced prompt + chapter
    # context. Everything else gets the v1 generic prompt.
    is_v3 = strategy in V3_STRATEGIES
    is_v2 = strategy in V2_STRATEGIES
    if is_v3:
        system_prompt = load_v3_system_prompt()
        book_ctx = load_book_context(book_slug)
        if book_ctx:
            system_prompt = system_prompt + "\n\n---\n\n" + book_ctx
        context_block = read_context_snippet(testament, book_slug, chapter, verse)
        prompt_version = PROMPT_VERSION_V3
    elif is_v2:
        system_prompt = load_v2_system_prompt()
        context_block = read_context_snippet(testament, book_slug, chapter, verse)
        prompt_version = PROMPT_VERSION_V2
    else:
        system_prompt = SYSTEM_PROMPT
        context_block = ""
        prompt_version = PROMPT_VERSION

    t0 = time.time()
    review, model_id = call_gemini_review(
        verse_yaml,
        model=model,
        system_prompt=system_prompt,
        context_block=context_block,
    )
    duration = round(time.time() - t0, 2)

    agreement = float(review.get("agreement_score") or 0.0)
    issues = review.get("issues") or []

    out_path = review_output_path(
        job_id=job_id,
        strategy=strategy,
        testament=testament,
        book_slug=book_slug,
        chapter=chapter,
        verse=verse,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "review_job_id": job_id,
        "id": f"{book_slug}.{chapter}.{verse}",
        "strategy": strategy,
        "testament": testament,
        "book_slug": book_slug,
        "chapter": chapter,
        "verse": verse,
        "reviewer_model": model_id,
        "prompt_version": prompt_version,
        "vertex_location": VERTEX_LOCATION,
        "context_window_verses": CONTEXT_WINDOW_VERSES if (is_v2 or is_v3) else 0,
        "book_context_loaded": bool(is_v3 and load_book_context(book_slug)),
        "reviewed_at": utc_now(),
        "duration_seconds": duration,
        "agreement_score": agreement,
        "verdict": review.get("verdict"),
        "issues": issues,
        "notes": review.get("notes") or "",
    }
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mark_complete(
        conn,
        job_id,
        review_path=str(out_path.relative_to(REPO_ROOT)),
        agreement_score=agreement,
        issues_found=len(issues),
    )
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--strategy", default=None)
    ap.add_argument("--book", default=None, help="Restrict to one book_slug (e.g. 'romans')")
    ap.add_argument("--max-jobs", type=int, default=100)
    ap.add_argument("--stop-when-empty", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0, help="Sleep between jobs (s)")
    ap.add_argument(
        "--model-override",
        default=None,
        help="If set, ignore job['model'] and use this model id (e.g. gemini-2.5-flash). Reviewer_model in output JSON reflects the override.",
    )
    args = ap.parse_args()

    done = 0
    failures = 0
    with contextlib.closing(connect()) as conn:
        rq.ensure_schema(conn)
        while done < args.max_jobs:
            job = claim_next(conn, args.worker_id, args.strategy, args.book)
            if not job:
                if args.stop_when_empty:
                    print(f"[{args.worker_id}] queue empty, stopping.", flush=True)
                    return 0
                print(f"[{args.worker_id}] queue empty, sleeping…", flush=True)
                time.sleep(10)
                continue
            try:
                record = run_job(conn, job, model_override=args.model_override)
                done += 1
                print(
                    f"[{args.worker_id}] ✓ {job['strategy']} {job['book_slug']} {job['chapter']}:{job['verse']} "
                    f"(agreement={record.get('agreement_score','—')}, issues={len(record.get('issues') or [])}, "
                    f"location={record.get('vertex_location')})",
                    flush=True,
                )
            except Exception as exc:
                failures += 1
                err = f"{type(exc).__name__}: {exc}"
                print(f"[{args.worker_id}] ✗ {job['book_slug']} {job['chapter']}:{job['verse']}: {err[:160]}", flush=True)
                mark_failed(conn, int(job["id"]), err)
                if failures >= 5 and done == 0:
                    print(f"[{args.worker_id}] too many failures with no successes, stopping.", flush=True)
                    return 2
            time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
