#!/usr/bin/env python3
"""gemini_summary_prewarm.py — fill gaps in BibleSummaryCache via Gemini 2.5 Pro.

Azure GPT-5.4's content filter rejected many OT passages (Sodom, Judges 19,
Song of Songs, etc.), so some chapter/book summaries never landed in the
DynamoDB cache at `BibleSummaryCache-{stage}`. This script walks the
translation repo, compares against the cache, and generates the missing
summaries via Gemini 2.5 Pro through the AI Studio endpoint (separate
quota pool from Vertex, so it doesn't compete with the review pass).

Cache keys follow the Go pipeline's scheme verbatim, but written with an
honest `model_version="gemini-3.1-pro-preview-2026-04"` so the provenance of each
record is recoverable. The Go `SummaryCache.GetOrGenerate` needs a small
change to try the Gemini model_version on cache miss — see the companion
change in internal/bible/summary_cache.go.

Prompts, scope IDs, source_hash, passage formatting are ported verbatim
from internal/bible/summary_cache.go (commit as of 2026-04-21).

Run:
  python3 tools/gemini_summary_prewarm.py --stage alpha --workers 10
  python3 tools/gemini_summary_prewarm.py --dry-run         # just counts gaps
  python3 tools/gemini_summary_prewarm.py --chapters-only   # skip book scope
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import boto3
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Constants that MUST match internal/bible/summary_cache.go
PROMPT_VERSION = "bible_shared_summary_v1"
PRIMARY_MODEL_VERSION = "gpt-5.4-2026-03-05"
GEMINI_MODEL_VERSION = "gemini-3.1-pro-preview-2026-04"

SCOPE_CHAPTER = "chapter"
SCOPE_BOOK = "book"

TOOL_SIMPLIFY = "simplify"
TOOL_RECONTEXTUALIZE_BIBLE = "recontextualize_bible"
TOOL_RECONTEXTUALIZE_HIST = "recontextualize_historical"
TOOLS = [TOOL_SIMPLIFY, TOOL_RECONTEXTUALIZE_BIBLE, TOOL_RECONTEXTUALIZE_HIST]

AI_STUDIO_MODEL = "gemini-3.1-pro-preview"
AI_STUDIO_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{AI_STUDIO_MODEL}:generateContent"
)

# Vertex AI backend defaults — used when --backend=vertex is passed.
# Vertex bills Gemini calls against the GCP project tied to the service
# account in `/cartha/openclaw/gemini_api_key_2`, bypassing AI Studio's
# 250 req/model/day free-tier cap.
VERTEX_LOCATION_DEFAULT = "us-central1"
VERTEX_MODEL_DEFAULT = "gemini-2.5-pro"
VERTEX_OAUTH_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


# ── ported verbatim from Go ────────────────────────────────────────────

def normalize_token(s: str) -> str:
    return s.strip().upper()


def scope_id(scope: str, book: str, chapter: int) -> str:
    if scope == SCOPE_BOOK:
        return normalize_token(book)
    return f"{normalize_token(book)}.{chapter:03d}"


def summary_key(
    translation: str,
    translation_version: str,
    scope: str,
    book: str,
    chapter: int,
    tool: str,
    prompt_version: str,
    model_version: str,
) -> str:
    tv = (translation_version or "").strip() or "unspecified"
    parts = [
        normalize_token(translation),
        tv,
        scope,
        scope_id(scope, book, chapter),
        tool,
        prompt_version,
        model_version,
    ]
    return "|".join(parts)


def canonical_source_hash(verses: list[dict]) -> str:
    rows = []
    for v in verses:
        rows.append({
            "book": normalize_token(v["book"]),
            "chapter": int(v["chapter"]),
            "verse": int(v["verse"]),
            "text": v["text"].strip(),
        })
    rows.sort(key=lambda r: (r["book"], r["chapter"], r["verse"]))
    # Must match Go's encoding/json — keys sorted alphabetically by struct tag
    # order but json.Marshal for Go uses struct field order. The Go struct is
    # Book, Chapter, Verse, Text — json keys emit in that order.
    payload = "[" + ",".join(
        json.dumps(
            {"book": r["book"], "chapter": r["chapter"], "verse": r["verse"], "text": r["text"]},
            ensure_ascii=False, separators=(",", ":"),
        )
        for r in rows
    ) + "]"
    # Actually, json.dumps with dict in Python 3.7+ preserves insertion order,
    # so this matches Go's order too.
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── corpus-aware prompt dispatch ───────────────────────────────────────
# Mirrors internal/bible/summary_cache.go: bookCorpus + three prompt variants.
# Default is "biblical" — that covers the 66-book canon plus the deuterocanon
# (Tobit, Wisdom of Solomon, Sirach, Maccabees, etc.), which are framed as
# Scripture in Catholic/Orthodox traditions. Patristic and pseudepigraphal
# corpora get distinct framing so summaries don't imply they're Scripture.

CORPUS_BIBLICAL = "biblical"
CORPUS_PATRISTIC = "patristic"
CORPUS_PSEUDEPIGRAPHAL = "pseudepigraphal"

_PATRISTIC_BOOKS = {
    "DIDACHE", "1 CLEMENT", "2 CLEMENT",
    "SHEPHERD OF HERMAS",
    "BARNABAS", "EPISTLE OF BARNABAS",
    "IGNATIUS", "POLYCARP", "MARTYRDOM OF POLYCARP", "DIOGNETUS",
}
_PSEUDEPIGRAPHAL_BOOKS = {
    "ENOCH", "1 ENOCH", "2 ENOCH", "3 ENOCH",
    "JUBILEES",
    "TESTAMENTS OF THE TWELVE PATRIARCHS", "TESTAMENTS",
    "2 ESDRAS", "4 EZRA",
    "ASCENSION OF ISAIAH",
    "ASSUMPTION OF MOSES",
    "APOCALYPSE OF ABRAHAM",
}


def book_corpus(book: str) -> str:
    key = normalize_token(book)
    if key in _PATRISTIC_BOOKS:
        return CORPUS_PATRISTIC
    if key in _PSEUDEPIGRAPHAL_BOOKS:
        return CORPUS_PSEUDEPIGRAPHAL
    return CORPUS_BIBLICAL


def summary_system_prompt(tool: str, scope: str, book: str = "") -> str:
    corpus = book_corpus(book) if book else CORPUS_BIBLICAL
    if corpus == CORPUS_PATRISTIC:
        return _patristic_prompt(tool, scope)
    if corpus == CORPUS_PSEUDEPIGRAPHAL:
        return _pseudepigraphal_prompt(tool, scope)
    return _biblical_prompt(tool, scope)


def _biblical_prompt(tool: str, scope: str) -> str:
    if scope == SCOPE_BOOK:
        if tool == TOOL_SIMPLIFY:
            return (
                "You are a Bible-study assistant in the Cartha app. A shared book-level "
                "summary is being generated for all users.\n\n"
                "Summarize this entire biblical book in clear, modern English. Use 4 to 8 "
                "sentences. Preserve the theological weight and central movement of the "
                "book. Highlight the main argument, major turning points, and key emphases. "
                "Do not use headers, bullets, or preamble."
            )
        if tool == TOOL_RECONTEXTUALIZE_BIBLE:
            return (
                "You are a Bible-study assistant in the Cartha app. A shared book-level "
                "in-Bible context summary is being generated for all users.\n\n"
                "Explain where this biblical book sits in the story and theology of "
                "Scripture. In under 250 words, cover the book's role in its testament, "
                "two to five important biblical echoes or cross-references (cite them like "
                '"Book C:V"), and the major biblical themes it advances. Respond in '
                "flowing prose only."
            )
        return (
            "You are a Bible-study assistant in the Cartha app. A shared book-level "
            "original-context summary is being generated for all users.\n\n"
            "Explain the original historical, cultural, and linguistic context of this "
            "biblical book. In under 250 words, cover the likely audience, setting, and "
            "the most important original-language themes that shape how the book should be "
            "heard. Be specific, readable, and non-speculative. Respond in flowing prose only."
        )
    if tool == TOOL_SIMPLIFY:
        return (
            "You are a Bible-study assistant in the Cartha app. A shared chapter summary "
            "is being generated for all users.\n\n"
            "Restate the whole chapter in plain, modern, accessible English in 3 to 6 "
            "sentences. Preserve the theological weight and major movement of the passage. "
            "Do not flatten hard sayings or add doctrine the text does not make explicit. "
            "Respond with the summary only."
        )
    if tool == TOOL_RECONTEXTUALIZE_BIBLE:
        return (
            "You are a Bible-study assistant in the Cartha app. A shared chapter "
            "in-Bible context summary is being generated for all users.\n\n"
            "In under 220 words, explain where this chapter sits in its book's argument, "
            "identify two to four meaningful biblical cross-references or echoes, and "
            "connect it to broader biblical themes when genuinely relevant. Respond in "
            "flowing prose only."
        )
    return (
        "You are a Bible-study assistant in the Cartha app. A shared chapter "
        "original-context summary is being generated for all users.\n\n"
        "In under 220 words, explain the historical, cultural, and linguistic context "
        "that most helps modern readers hear this chapter well. Surface one to three "
        "original-language words or concepts only when they materially change "
        "understanding. Respond in flowing prose only."
    )


def _patristic_prompt(tool: str, scope: str) -> str:
    if scope == SCOPE_BOOK:
        if tool == TOOL_SIMPLIFY:
            return (
                "You are a Bible-study assistant in the Cartha app. A shared book-level "
                "summary is being generated for all users.\n\n"
                "Summarize this entire early Christian document in clear, modern English. "
                "Use 4 to 8 sentences. The text is from the Apostolic Fathers or an adjacent "
                "post-apostolic writing — not Scripture, but a primary witness to first- and "
                "second-century Christian teaching and practice. Highlight the main argument, "
                "major turning points, and key emphases. Do not frame it as Scripture. "
                "Do not use headers, bullets, or preamble."
            )
        if tool == TOOL_RECONTEXTUALIZE_BIBLE:
            return (
                "You are a Bible-study assistant in the Cartha app. A shared book-level "
                "in-Bible context summary is being generated for all users.\n\n"
                "Explain how this early Christian document relates to Scripture and to the "
                "apostolic witness. It is not part of the biblical canon. In under 250 words, "
                "cover the document's audience, its relationship to New Testament teaching, "
                "two to five important biblical echoes or parallels (cite them like "
                '"Book C:V"), and any distinctive emphases that go beyond what the New '
                "Testament explicitly teaches. Respond in flowing prose only."
            )
        return (
            "You are a Bible-study assistant in the Cartha app. A shared book-level "
            "original-context summary is being generated for all users.\n\n"
            "Explain the original historical, cultural, and linguistic context of this "
            "early Christian document. In under 250 words, cover the likely date, audience, "
            "setting, and the most important original-language themes or terminology that "
            "shape how the work should be heard. Be specific about which early Christian "
            "community produced or received it. Respond in flowing prose only."
        )
    if tool == TOOL_SIMPLIFY:
        return (
            "You are a Bible-study assistant in the Cartha app. A shared chapter summary "
            "is being generated for all users.\n\n"
            "This chapter is from an early Christian document — not Scripture, but a primary "
            "witness to post-apostolic Christian teaching and practice. Restate the whole "
            "chapter in plain, modern, accessible English in 3 to 6 sentences. Preserve the "
            "theological weight and major movement of the passage. Do not flatten difficult "
            "sayings or add doctrine the text does not make explicit. Do not frame it as "
            "Scripture. Respond with the summary only."
        )
    if tool == TOOL_RECONTEXTUALIZE_BIBLE:
        return (
            "You are a Bible-study assistant in the Cartha app. A shared chapter "
            "in-Bible context summary is being generated for all users.\n\n"
            "This chapter is from an early Christian document outside the biblical canon. "
            "In under 220 words, explain where the chapter sits in its text's argument, "
            "identify two to four meaningful echoes of or references to Scripture (cite "
            'them like "Book C:V"), and note any distinctive points of emphasis beyond what '
            "the New Testament explicitly teaches. Respond in flowing prose only."
        )
    return (
        "You are a Bible-study assistant in the Cartha app. A shared chapter "
        "original-context summary is being generated for all users.\n\n"
        "This chapter is from an early Christian document, likely composed in the first or "
        "second century. In under 220 words, explain the historical, cultural, and ecclesial "
        "context that most helps modern readers hear it well. Surface one to three Greek "
        "words or concepts only when they materially change understanding. Be specific about "
        "the era, community, and circumstances the text likely addresses. Respond in flowing "
        "prose only."
    )


def _pseudepigraphal_prompt(tool: str, scope: str) -> str:
    if scope == SCOPE_BOOK:
        if tool == TOOL_SIMPLIFY:
            return (
                "You are a Bible-study assistant in the Cartha app. A shared book-level "
                "summary is being generated for all users.\n\n"
                "Summarize this entire Second Temple Jewish text in clear, modern English. "
                "Use 4 to 8 sentences. The text is not part of the biblical canon, but it "
                "preserves important apocalyptic, ethical, or historical material from the "
                "intertestamental period. Highlight the main argument, major turning points, "
                "and key emphases. Do not frame it as Scripture. Do not use headers, bullets, "
                "or preamble."
            )
        if tool == TOOL_RECONTEXTUALIZE_BIBLE:
            return (
                "You are a Bible-study assistant in the Cartha app. A shared book-level "
                "in-Bible context summary is being generated for all users.\n\n"
                "Explain how this Second Temple Jewish text relates to the biblical canon. "
                "It is not Scripture. In under 250 words, cover the work's audience, its "
                "relationship to canonical books (including places where New Testament "
                "writers appear to draw on similar material), two to five important "
                'parallels or echoes (cite them like "Book C:V"), and any distinctive '
                "teachings that the biblical canon does not affirm. Respond in flowing prose only."
            )
        return (
            "You are a Bible-study assistant in the Cartha app. A shared book-level "
            "original-context summary is being generated for all users.\n\n"
            "Explain the historical, cultural, and linguistic context of this Second Temple "
            "Jewish text. In under 250 words, cover the likely date and setting, the "
            "community that produced or preserved it, and the most important original-"
            "language themes or apocalyptic concepts. Be specific about what part of the "
            "intertestamental Jewish world it reflects. Respond in flowing prose only."
        )
    if tool == TOOL_SIMPLIFY:
        return (
            "You are a Bible-study assistant in the Cartha app. A shared chapter summary "
            "is being generated for all users.\n\n"
            "This chapter is from a Second Temple Jewish text outside the biblical canon — "
            "it helps illuminate the world of the intertestamental period but is not "
            "Scripture. Restate the whole chapter in plain, modern, accessible English in 3 "
            "to 6 sentences. Preserve the theological or apocalyptic weight of the passage. "
            "Do not flatten difficult passages. Respond with the summary only."
        )
    if tool == TOOL_RECONTEXTUALIZE_BIBLE:
        return (
            "You are a Bible-study assistant in the Cartha app. A shared chapter "
            "in-Bible context summary is being generated for all users.\n\n"
            "This chapter is from a Second Temple Jewish text outside the biblical canon. "
            "In under 220 words, explain where it sits in its text's argument and identify "
            "two to four meaningful connections to biblical books — parallels, allusions, or "
            'themes the New Testament also takes up (cite them like "Book C:V"). Note '
            "distinctive points that the biblical canon does not affirm. Respond in flowing "
            "prose only."
        )
    return (
        "You are a Bible-study assistant in the Cartha app. A shared chapter "
        "original-context summary is being generated for all users.\n\n"
        "This chapter is from an intertestamental Jewish text likely composed between the "
        "third century BC and the first century AD. In under 220 words, explain the "
        "historical, cultural, and linguistic context that most helps modern readers hear "
        "it well. Surface one to three original-language words or apocalyptic concepts only "
        "when they materially change understanding. Be specific about the community and "
        "moment in Second Temple Judaism the text likely addresses. Respond in flowing prose "
        "only."
    )


def format_chapter_passage(translation: str, book: str, chapter: int, verses: list[dict]) -> str:
    ref = f"{normalize_token(book)} {chapter}"
    lines = [
        f"Scope: {SCOPE_CHAPTER}",
        f"Reference: {ref}",
        f"Translation: {normalize_token(translation)}",
        "",
        "Passage:",
    ]
    for v in verses:
        lines.append(f"  {v['verse']}. {v['text'].strip()}")
    return "\n".join(lines)


def format_book_passage(translation: str, book: str, chapter_summaries: list[tuple[int, str]]) -> str:
    """Book-scope user prompt — assembles chapter summaries into an aggregate.

    Mirrors the Go cmd/prewarm-bible-summary-cache/main.go buildBookPrompt
    behavior: the "Passage" section contains the numbered chapter summaries.
    """
    ref = normalize_token(book)
    lines = [
        f"Scope: {SCOPE_BOOK}",
        f"Reference: {ref}",
        f"Translation: {normalize_token(translation)}",
        "",
        "Passage:",
    ]
    for ch, text in chapter_summaries:
        lines.append(f"Chapter {ch}: {text.strip()}")
    return "\n".join(lines)


# ── book slug → canonical label ────────────────────────────────────────

BOOK_LABEL_OVERRIDES = {
    "1_corinthians": "1 CORINTHIANS",
    "2_corinthians": "2 CORINTHIANS",
    "1_thessalonians": "1 THESSALONIANS",
    "2_thessalonians": "2 THESSALONIANS",
    "1_timothy": "1 TIMOTHY",
    "2_timothy": "2 TIMOTHY",
    "1_peter": "1 PETER",
    "2_peter": "2 PETER",
    "1_john": "1 JOHN",
    "2_john": "2 JOHN",
    "3_john": "3 JOHN",
    "1_samuel": "1 SAMUEL",
    "2_samuel": "2 SAMUEL",
    "1_kings": "1 KINGS",
    "2_kings": "2 KINGS",
    "1_chronicles": "1 CHRONICLES",
    "2_chronicles": "2 CHRONICLES",
    "song_of_songs": "SONG OF SONGS",
}


def slug_to_label(slug: str) -> str:
    if slug in BOOK_LABEL_OVERRIDES:
        return BOOK_LABEL_OVERRIDES[slug]
    return slug.replace("_", " ").upper()


# ── chapter loader ─────────────────────────────────────────────────────

def load_chapters(translation_code: str) -> list[dict]:
    """Return list of {book_label, chapter, verses:[{book,chapter,verse,text,translation}]}."""
    chapters = []
    # Include canonical testaments + deuterocanon (LXX-only Scripture in Catholic/
    # Orthodox traditions) + extra_canonical (Apostolic Fathers, Second Temple
    # pseudepigrapha, etc.). Corpus-aware prompt dispatch in summary_system_prompt
    # picks the right framing per book.
    for testament in ("nt", "ot", "deuterocanon", "extra_canonical"):
        base = REPO_ROOT / "translation" / testament
        if not base.exists():
            continue
        for book_dir in sorted(base.iterdir()):
            if not book_dir.is_dir():
                continue
            book_label = slug_to_label(book_dir.name)
            for ch_dir in sorted(book_dir.iterdir()):
                if not ch_dir.is_dir():
                    continue
                try:
                    ch_num = int(ch_dir.name)
                except ValueError:
                    continue
                verse_files = sorted(ch_dir.glob("*.yaml"))
                if not verse_files:
                    continue
                verses = []
                for vf in verse_files:
                    try:
                        data = yaml.safe_load(vf.read_text(encoding="utf-8"))
                    except Exception as exc:
                        print(f"[warn] failed to parse {vf}: {exc}", file=sys.stderr)
                        continue
                    try:
                        vnum = int(vf.stem)
                    except ValueError:
                        continue
                    text = ((data or {}).get("translation") or {}).get("text") or ""
                    if not text.strip():
                        continue
                    verses.append({
                        "book": book_label,
                        "chapter": ch_num,
                        "verse": vnum,
                        "text": text,
                        "translation": translation_code,
                    })
                if verses:
                    chapters.append({
                        "book_label": book_label,
                        "chapter": ch_num,
                        "verses": verses,
                    })
    return chapters


# ── AI Studio Gemini caller ────────────────────────────────────────────

def call_gemini(api_key: str, system_prompt: str, user_prompt: str, max_tokens: int = 2048,
                timeout: int = 90, retries: int = 5) -> str:
    url = f"{AI_STUDIO_URL}?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            # 2.5 Pro always thinks. Default thinking consumes ~800 tokens, so
            # maxOutputTokens has to leave room for thinking + the actual prose.
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 1024},
        },
    }
    backoff = [2, 5, 15, 30, 60]
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates") or []
            if not candidates:
                raise RuntimeError(f"no candidates: {json.dumps(body)[:400]}")
            parts = candidates[0].get("content", {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise RuntimeError(f"empty text response: {json.dumps(body)[:400]}")
            return text
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_err = RuntimeError(f"HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = backoff[min(attempt, len(backoff) - 1)] + random.uniform(0, 2)
                time.sleep(wait)
                continue
            raise last_err
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
            last_err = RuntimeError(f"{type(exc).__name__}: {exc}")
            if attempt < retries - 1:
                time.sleep(backoff[min(attempt, len(backoff) - 1)])
                continue
            raise last_err
    raise last_err or RuntimeError("unknown call_gemini failure")


# ── Vertex AI backend ──────────────────────────────────────────────────
#
# Routes through `<location>-aiplatform.googleapis.com` with OAuth bearer
# auth. One authed `VertexClient` holds a refreshable credential (service
# account JSON -> Google access token) and reuses it across workers.
# Token refresh is threadsafe under a lock; workers past the lock grab
# the cached token.

class VertexClient:
    def __init__(self, service_account_json: dict, project_id: str,
                 location: str = VERTEX_LOCATION_DEFAULT,
                 model: str = VERTEX_MODEL_DEFAULT):
        from google.oauth2 import service_account as sa
        from google.auth.transport.requests import Request as GoogleAuthRequest
        self._request_cls = GoogleAuthRequest
        self._creds = sa.Credentials.from_service_account_info(
            service_account_json, scopes=VERTEX_OAUTH_SCOPES,
        )
        self._project_id = project_id
        self._location = location
        self._model = model
        self._url = (
            f"https://{location}-aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/{location}/publishers/"
            f"google/models/{model}:generateContent"
        )
        self._lock = threading.Lock()

    def _token(self) -> str:
        with self._lock:
            if not self._creds.valid:
                self._creds.refresh(self._request_cls())
            return self._creds.token

    @property
    def describe(self) -> str:
        return f"vertex://{self._project_id}/{self._location}/{self._model}"

    def generate(self, system_prompt: str, user_prompt: str,
                 max_tokens: int = 2048, timeout: int = 90,
                 retries: int = 5) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
                "thinkingConfig": {"thinkingBudget": 1024},
            },
        }
        backoff = [2, 5, 15, 30, 60]
        last_err = None
        for attempt in range(retries):
            try:
                token = self._token()
            except Exception as exc:
                raise RuntimeError(f"vertex token refresh failed: {exc}")
            req = urllib.request.Request(
                self._url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                candidates = body.get("candidates") or []
                if not candidates:
                    raise RuntimeError(f"no candidates: {json.dumps(body)[:400]}")
                parts = candidates[0].get("content", {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts).strip()
                if not text:
                    raise RuntimeError(f"empty text response: {json.dumps(body)[:400]}")
                return text
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
                last_err = RuntimeError(f"HTTP {exc.code}: {detail}")
                if exc.code == 401:
                    # Force a refresh on the next loop iteration.
                    with self._lock:
                        self._creds.expiry = None
                if exc.code in (401, 429, 500, 502, 503, 504) and attempt < retries - 1:
                    wait = backoff[min(attempt, len(backoff) - 1)] + random.uniform(0, 2)
                    time.sleep(wait)
                    continue
                raise last_err
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = RuntimeError(f"{type(exc).__name__}: {exc}")
                if attempt < retries - 1:
                    time.sleep(backoff[min(attempt, len(backoff) - 1)])
                    continue
                raise last_err
        raise last_err or RuntimeError("unknown vertex call failure")


def load_vertex_client(secret_id: str, location: str, model: str) -> "VertexClient":
    """Pull a service account JSON from Secrets Manager and build a Vertex
    client. Raises if the secret isn't a valid SA JSON so the caller can
    decide whether to fall back to AI Studio."""
    sm = boto3.client("secretsmanager", region_name="us-west-2")
    raw = sm.get_secret_value(SecretId=secret_id)["SecretString"]
    sa_json = json.loads(raw)
    if sa_json.get("type") != "service_account":
        raise RuntimeError(
            f"secret {secret_id} isn't a Google service-account JSON "
            f"(type={sa_json.get('type')!r})"
        )
    project = sa_json.get("project_id")
    if not project:
        raise RuntimeError(f"secret {secret_id} missing project_id")
    return VertexClient(
        service_account_json=sa_json,
        project_id=project,
        location=location,
        model=model,
    )


# ── DynamoDB helpers ───────────────────────────────────────────────────

_ddb_lock = threading.Lock()


def _extract_keys_from_secret(raw: str) -> list[str]:
    """Parse a Secrets Manager value — raw string OR JSON with api_key /
    api_keys — into the list of API keys it carries."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("{"):
        j = json.loads(raw)
        keys = j.get("api_keys")
        if isinstance(keys, list):
            out = [k.strip() for k in keys if isinstance(k, str) and k.strip()]
            if out:
                return out
        for field in ("api_key", "apiKey", "key", "GEMINI_API_KEY"):
            v = j.get(field)
            if isinstance(v, str) and v.strip():
                return [v.strip()]
        raise RuntimeError(f"no known key field in secret JSON: {list(j.keys())}")
    return [raw]


def get_api_key() -> str:
    """Back-compat: return the first key from the primary secret."""
    return get_api_keys(["/cartha/openclaw/gemini_api_key"])[0]


def get_api_keys(secret_ids: list[str]) -> list[str]:
    """Fetch and flatten keys across multiple Secrets Manager entries.
    Missing/invalid secrets are skipped with a warning so one broken
    secret doesn't block a run. Dedupes while preserving order so
    round-robin stays balanced across the unique keys we actually have."""
    sm = boto3.client("secretsmanager", region_name="us-west-2")
    seen: set[str] = set()
    collected: list[str] = []
    for sid in secret_ids:
        try:
            raw = sm.get_secret_value(SecretId=sid)["SecretString"]
            keys = _extract_keys_from_secret(raw)
        except Exception as exc:
            print(f"[warn] could not load {sid}: {exc}")
            continue
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            collected.append(k)
    if not collected:
        raise RuntimeError(f"no Gemini API keys resolved from {secret_ids}")
    return collected


# Atomic counter for round-robin key selection — threadsafe and
# avoids the GIL-fighting + mod-cache races a plain int would have.
_key_cursor = threading.Lock()
_key_idx = [0]

def pick_key(keys: list[str]) -> str:
    """Round-robin the key pool so every concurrent worker spreads
    its calls evenly across both AI Studio accounts."""
    if len(keys) == 1:
        return keys[0]
    with _key_cursor:
        i = _key_idx[0] % len(keys)
        _key_idx[0] = (i + 1) % len(keys)
    return keys[i]


def batch_check_existence(ddb, table: str, keys: list[str]) -> set[str]:
    """Return subset of `keys` that already exist in table (under `summary_key`)."""
    present = set()
    for i in range(0, len(keys), 100):
        batch = keys[i:i + 100]
        resp = ddb.batch_get_item(RequestItems={
            table: {"Keys": [{"summary_key": {"S": k}} for k in batch],
                    "ProjectionExpression": "summary_key"}
        })
        for item in resp.get("Responses", {}).get(table, []):
            present.add(item["summary_key"]["S"])
    return present


def put_summary(ddb, table: str, entry: dict) -> None:
    item = {
        "summary_key": {"S": entry["summary_key"]},
        "translation": {"S": entry["translation"]},
        "translation_version": {"S": entry["translation_version"]},
        "scope": {"S": entry["scope"]},
        "book": {"S": entry["book"]},
        "tool": {"S": entry["tool"]},
        "output": {"S": entry["output"]},
        "prompt_version": {"S": entry["prompt_version"]},
        "model_version": {"S": entry["model_version"]},
        "source_hash": {"S": entry["source_hash"]},
        "verse_count": {"N": str(entry["verse_count"])},
        "generated_at": {"S": entry["generated_at"]},
        "updated_at": {"S": entry["updated_at"]},
    }
    if entry.get("chapter"):
        item["chapter"] = {"N": str(entry["chapter"])}
    ddb.put_item(TableName=table, Item=item)


# ── main orchestration ────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_expected_keys(chapters: list[dict], include_books: bool) -> list[tuple]:
    """Build list of (key, scope, book, chapter, tool) for all gpt-5.4-keyed entries."""
    expected = []
    for ch in chapters:
        for tool in TOOLS:
            k = summary_key(
                "COB", "unspecified", SCOPE_CHAPTER, ch["book_label"], ch["chapter"],
                tool, PROMPT_VERSION, PRIMARY_MODEL_VERSION,
            )
            expected.append((k, SCOPE_CHAPTER, ch["book_label"], ch["chapter"], tool))
    if include_books:
        books = sorted(set(c["book_label"] for c in chapters))
        for book in books:
            for tool in TOOLS:
                k = summary_key(
                    "COB", "unspecified", SCOPE_BOOK, book, 0,
                    tool, PROMPT_VERSION, PRIMARY_MODEL_VERSION,
                )
                expected.append((k, SCOPE_BOOK, book, 0, tool))
    return expected


def fetch_existing_chapter_output(ddb, table: str, book: str, chapter: int, tool: str) -> str | None:
    """For book-level generation — look up chapter summary under either key."""
    for mv in (PRIMARY_MODEL_VERSION, GEMINI_MODEL_VERSION):
        k = summary_key("COB", "unspecified", SCOPE_CHAPTER, book, chapter, tool, PROMPT_VERSION, mv)
        resp = ddb.get_item(TableName=table, Key={"summary_key": {"S": k}},
                            ProjectionExpression="#o", ExpressionAttributeNames={"#o": "output"})
        if "Item" in resp:
            return resp["Item"]["output"]["S"]
    return None


def _generate_via_backend(backend, system_prompt: str, user_prompt: str,
                          max_tokens: int) -> str:
    """Dispatch to either the AI Studio key pool or a VertexClient."""
    if isinstance(backend, VertexClient):
        return backend.generate(system_prompt, user_prompt, max_tokens=max_tokens)
    if isinstance(backend, list):
        key = pick_key(backend)
    else:
        key = backend
    return call_gemini(key, system_prompt, user_prompt, max_tokens=max_tokens)


def generate_chapter(ddb, table: str, api_key_or_keys, chapter_data: dict, tool: str) -> str:
    book = chapter_data["book_label"]
    chap = chapter_data["chapter"]
    verses = chapter_data["verses"]
    sys_prompt = summary_system_prompt(tool, SCOPE_CHAPTER, book)
    user_prompt = format_chapter_passage("COB", book, chap, verses)
    text = _generate_via_backend(api_key_or_keys, sys_prompt, user_prompt, max_tokens=2048)
    key = summary_key("COB", "unspecified", SCOPE_CHAPTER, book, chap, tool,
                      PROMPT_VERSION, GEMINI_MODEL_VERSION)
    entry = {
        "summary_key": key,
        "translation": "COB",
        "translation_version": "unspecified",
        "scope": SCOPE_CHAPTER,
        "book": normalize_token(book),
        "chapter": chap,
        "tool": tool,
        "output": text,
        "prompt_version": PROMPT_VERSION,
        "model_version": GEMINI_MODEL_VERSION,
        "source_hash": canonical_source_hash(verses),
        "verse_count": len(verses),
        "generated_at": now_iso(),
        "updated_at": now_iso(),
    }
    with _ddb_lock:
        put_summary(ddb, table, entry)
    return key


def generate_book(ddb, table: str, api_key_or_keys, chapters_of_book: list[dict], book: str, tool: str) -> str:
    # Collect chapter summaries from cache (either key)
    chapter_summaries = []
    for ch in chapters_of_book:
        out = fetch_existing_chapter_output(ddb, table, book, ch["chapter"], tool)
        if not out:
            raise RuntimeError(f"missing chapter summary {book} {ch['chapter']} ({tool}) — chapter must be filled first")
        chapter_summaries.append((ch["chapter"], out))
    sys_prompt = summary_system_prompt(tool, SCOPE_BOOK, book)
    user_prompt = format_book_passage("COB", book, chapter_summaries)
    text = _generate_via_backend(api_key_or_keys, sys_prompt, user_prompt, max_tokens=2560)
    key = summary_key("COB", "unspecified", SCOPE_BOOK, book, 0, tool,
                      PROMPT_VERSION, GEMINI_MODEL_VERSION)
    # source_hash for book scope: hash of the concatenated chapter summaries
    joined = "\n".join(s for _, s in chapter_summaries)
    source_hash = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    entry = {
        "summary_key": key,
        "translation": "COB",
        "translation_version": "unspecified",
        "scope": SCOPE_BOOK,
        "book": normalize_token(book),
        "chapter": 0,
        "tool": tool,
        "output": text,
        "prompt_version": PROMPT_VERSION,
        "model_version": GEMINI_MODEL_VERSION,
        "source_hash": source_hash,
        "verse_count": sum(len(ch["verses"]) for ch in chapters_of_book),
        "generated_at": now_iso(),
        "updated_at": now_iso(),
    }
    with _ddb_lock:
        put_summary(ddb, table, entry)
    return key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="alpha")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="enumerate gaps but don't call Gemini")
    ap.add_argument("--chapters-only", action="store_true", help="skip book-level summaries")
    ap.add_argument("--limit", type=int, default=0, help="cap on entries to generate (0=all)")
    ap.add_argument("--book", default=None, help="restrict to one book (canonical label)")
    ap.add_argument(
        "--secret-ids",
        default="/cartha/openclaw/gemini_api_key,/cartha/openclaw/gemini_api_key_2",
        help=(
            "Comma-separated Secrets Manager IDs to pull Gemini keys from. "
            "Defaults to both the paid and free-tier Cartha keys; workers "
            "round-robin across every key that resolves."
        ),
    )
    ap.add_argument(
        "--backend",
        choices=["studio", "vertex"],
        default="studio",
        help=(
            "Which Gemini endpoint to call. 'studio' = AI Studio raw "
            "?key=<> endpoint (daily per-key quota applies). 'vertex' = "
            "Vertex AI endpoint authed via a service-account JSON; uses the "
            "project's billed Vertex quota instead of the AI Studio cap."
        ),
    )
    ap.add_argument(
        "--vertex-secret-id",
        default="/cartha/openclaw/gemini_api_key_2",
        help="Secrets Manager ID holding the Google service-account JSON for Vertex.",
    )
    ap.add_argument(
        "--vertex-location",
        default=VERTEX_LOCATION_DEFAULT,
        help="Vertex region, e.g. us-central1.",
    )
    ap.add_argument(
        "--vertex-model",
        default=VERTEX_MODEL_DEFAULT,
        help="Vertex model id, e.g. gemini-2.5-pro.",
    )
    args = ap.parse_args()

    table = f"BibleSummaryCache-{args.stage}"
    chapters = load_chapters("COB")
    print(f"loaded {len(chapters)} chapters across {len(set(c['book_label'] for c in chapters))} books")

    if args.book:
        bk = normalize_token(args.book)
        chapters = [c for c in chapters if c["book_label"] == bk]
        print(f"filtered to {len(chapters)} chapters for book={bk}")

    expected = compute_expected_keys(chapters, include_books=not args.chapters_only)
    # Build gemini variant keys
    keys_primary = [e[0] for e in expected]
    keys_gemini = [k.replace(PRIMARY_MODEL_VERSION, GEMINI_MODEL_VERSION) for k in keys_primary]

    ddb = boto3.client("dynamodb", region_name="us-west-2")
    print("checking cache existence...")
    present_primary = batch_check_existence(ddb, table, keys_primary)
    present_gemini = batch_check_existence(ddb, table, keys_gemini)
    print(f"  present under gpt-5.4 key: {len(present_primary)}")
    print(f"  present under gemini key:  {len(present_gemini)}")

    # Chapter gaps
    chapter_gaps = []
    book_gaps = []
    for k, scope, book, chap, tool in expected:
        gk = k.replace(PRIMARY_MODEL_VERSION, GEMINI_MODEL_VERSION)
        if k in present_primary or gk in present_gemini:
            continue
        (chapter_gaps if scope == SCOPE_CHAPTER else book_gaps).append((book, chap, tool))

    print(f"\ngaps: {len(chapter_gaps)} chapter + {len(book_gaps)} book")
    if args.dry_run:
        print("\n=== chapter gaps (first 40) ===")
        for g in chapter_gaps[:40]:
            print(f"  {g[0]} {g[1]} {g[2]}")
        print("\n=== book gaps (first 40) ===")
        for g in book_gaps[:40]:
            print(f"  {g[0]} {g[2]}")
        return 0

    # Resolve the generation backend. Vertex sidesteps the AI Studio
    # daily per-key quota by authing against a service-account JSON and
    # billing Gemini calls to our GCP project. AI Studio mode stays the
    # fallback when the user doesn't have a Vertex project wired up.
    if args.backend == "vertex":
        backend = load_vertex_client(
            secret_id=args.vertex_secret_id,
            location=args.vertex_location,
            model=args.vertex_model,
        )
        print(f"using Vertex backend: {backend.describe}")
    else:
        secret_ids = [s.strip() for s in args.secret_ids.split(",") if s.strip()]
        api_keys = get_api_keys(secret_ids)
        print(
            f"got {len(api_keys)} AI Studio key(s) across {len(secret_ids)} secret(s): "
            + ", ".join(f"len={len(k)}" for k in api_keys)
        )
        backend = api_keys
    # generate_chapter / generate_book accept the backend polymorphically.
    api_key = backend

    # Index chapters by (book, chapter) for fast lookup
    ch_index = {(c["book_label"], c["chapter"]): c for c in chapters}
    by_book = {}
    for c in chapters:
        by_book.setdefault(c["book_label"], []).append(c)
    for v in by_book.values():
        v.sort(key=lambda c: c["chapter"])

    # Apply limit: chapter gaps first, then books
    work_chapter = chapter_gaps if not args.limit else chapter_gaps[:args.limit]
    remaining = (args.limit - len(work_chapter)) if args.limit else 0
    work_book = book_gaps if not args.limit else (book_gaps[:remaining] if remaining > 0 else [])

    # Phase 1: chapter gaps (parallel)
    done = 0
    errors = 0
    t0 = time.time()
    print(f"\n=== phase 1: filling {len(work_chapter)} chapter summaries (workers={args.workers}) ===")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for book, chap, tool in work_chapter:
            cd = ch_index.get((book, chap))
            if not cd:
                print(f"[skip] no YAML data for {book} {chap}")
                continue
            fut = pool.submit(generate_chapter, ddb, table, api_key, cd, tool)
            futures[fut] = (book, chap, tool)
        for fut in as_completed(futures):
            book, chap, tool = futures[fut]
            try:
                key = fut.result()
                done += 1
                if done % 10 == 0 or done == len(futures):
                    rate = done / max(time.time() - t0, 0.01)
                    print(f"  [{done}/{len(futures)}] {book} {chap} {tool} ✓  ({rate:.1f}/s)")
            except Exception as exc:
                errors += 1
                print(f"  [ERR] {book} {chap} {tool}: {exc}")
    print(f"phase 1 done: {done} written, {errors} errors in {time.time()-t0:.1f}s")

    # Phase 2: book gaps — only run after chapters land so we can pull outputs
    if work_book:
        print(f"\n=== phase 2: filling {len(work_book)} book summaries ===")
        # Group by book for batching chapter pulls
        b_done = 0
        b_err = 0
        t1 = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {}
            for book, _, tool in work_book:
                chs = by_book.get(book)
                if not chs:
                    print(f"[skip book] no chapters for {book}")
                    continue
                fut = pool.submit(generate_book, ddb, table, api_key, chs, book, tool)
                futures[fut] = (book, tool)
            for fut in as_completed(futures):
                book, tool = futures[fut]
                try:
                    fut.result()
                    b_done += 1
                    print(f"  [{b_done}/{len(futures)}] {book} {tool} (book) ✓")
                except Exception as exc:
                    b_err += 1
                    print(f"  [ERR book] {book} {tool}: {exc}")
        print(f"phase 2 done: {b_done} written, {b_err} errors in {time.time()-t1:.1f}s")

    print(f"\nTOTAL: {done + (b_done if work_book else 0)} entries written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
