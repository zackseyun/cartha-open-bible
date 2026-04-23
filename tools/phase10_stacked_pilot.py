#!/usr/bin/env python3
"""phase10_stacked_pilot.py — run the Phase 10 stacked-review pilot.

This pilot evaluates whether a two-call "stacked" review flow surfaces
better revisions than the current baseline review passes:

1. Blind draft
   - Gemini 3.1 Pro sees only the source-language verse and project
     translation philosophy, never the existing English draft.
2. Stacked adjudication
   - Gemini 3.1 Pro compares the source text, the existing Cartha draft,
     the blind draft, published translation excerpts, and commentary
     context, then returns a retain/modify/reject verdict plus rationale.

Outputs are written ONLY under the requested pilot directory (for
example `/tmp/cob-pilot/sirach_24/`). This script never writes back to
translation YAML files.

Usage:
  python3 tools/phase10_stacked_pilot.py --book sirach --chapter 24 \
      --out /tmp/cob-pilot/sirach_24
  python3 tools/phase10_stacked_pilot.py --book prayer_of_manasseh \
      --chapter 1 --out /tmp/cob-pilot/prayer_of_manasseh
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AI_STUDIO_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_ID = os.environ.get("CARTHA_PHASE10_MODEL", "gemini-3.1-pro-preview")
TEMPERATURE = float(os.environ.get("CARTHA_PHASE10_TEMPERATURE", "0.2"))
MAX_OUTPUT_TOKENS = 16384
DOCTRINE_PATH = REPO_ROOT / "DOCTRINE.md"
PHILOSOPHY_PATH = REPO_ROOT / "PHILOSOPHY.md"
BOOK_CONTEXTS_DIR = REPO_ROOT / "tools" / "prompts" / "book_contexts"

REFERENCE_BUNDLE_PATHS: dict[tuple[str, int], pathlib.Path] = {
    ("sirach", 24): REPO_ROOT / "sources" / "references" / "sirach_24.json",
    ("prayer_of_manasseh", 1): REPO_ROOT / "sources" / "references" / "prayer_of_manasseh.json",
}


BLIND_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["english_text", "lexical_decisions", "translator_notes"],
    "properties": {
        "english_text": {"type": "string"},
        "lexical_decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_word", "chosen", "lexicon", "rationale"],
                "properties": {
                    "source_word": {"type": "string"},
                    "chosen": {"type": "string"},
                    "lexicon": {"type": "string"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "translator_notes": {"type": "string"},
    },
}

STACKED_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "verse_id",
        "verdict",
        "confidence",
        "reference_divergences",
        "commentary_alignment",
        "proposed_rewrite",
        "key_issues",
        "reasoning",
        "agreement_with_blind_draft",
    ],
    "properties": {
        "verse_id": {"type": "string"},
        "verdict": {"type": "string", "enum": ["retain", "modify", "reject"]},
        "confidence": {"type": "number"},
        "reference_divergences": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "rendering", "alignment", "notes"],
                "properties": {
                    "source": {"type": "string"},
                    "rendering": {"type": "string"},
                    "alignment": {"type": "string", "enum": ["aligned", "partial", "divergent"]},
                    "notes": {"type": "string"},
                },
            },
        },
        # Gemini's response-schema handling is stricter with bare strings than
        # with nullable unions, so we normalize "" -> null after parsing.
        "commentary_alignment": {"type": "string"},
        "proposed_rewrite": {"type": "string"},
        "key_issues": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "agreement_with_blind_draft": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
    },
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_verse_selector(spec: str) -> list[int]:
    verses: list[int] = []
    for chunk in spec.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if end < start:
                raise ValueError(f"descending verse range: {part}")
            verses.extend(range(start, end + 1))
        else:
            verses.append(int(part))
    return sorted(dict.fromkeys(verses))


def _fetch_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            [
                "aws",
                "secretsmanager",
                "get-secret-value",
                "--secret-id",
                "/cartha/openclaw/gemini_api_key",
                "--region",
                "us-west-2",
                "--query",
                "SecretString",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
    except Exception as exc:  # pragma: no cover - depends on local AWS state
        raise RuntimeError("Unable to fetch GEMINI_API_KEY from AWS Secrets Manager") from exc

    raw = result.stdout.strip()
    try:
        return json.loads(raw).get("api_key", raw)
    except json.JSONDecodeError:
        return raw


def call_gemini_json(
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict[str, Any],
    model: str = MODEL_ID,
    timeout: int = 300,
    max_retries: int = 5,
) -> dict[str, Any]:
    key = _fetch_gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not available")

    url = f"{AI_STUDIO_BASE}/{model}:generateContent?key={key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        },
    }
    headers = {"Content-Type": "application/json"}

    backoffs = [10, 25, 60, 120, 180]
    last_err: Exception | None = None

    for attempt in range(max_retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates") or []
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates; promptFeedback={body.get('promptFeedback')}")
            parts = (candidates[0].get("content") or {}).get("parts") or []
            raw_text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
            if not raw_text:
                raise RuntimeError(f"Gemini returned empty JSON; finishReason={candidates[0].get('finishReason')}")
            return json.loads(raw_text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_err = RuntimeError(f"Gemini HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)] + random.uniform(0, 3))
                continue
            raise last_err
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = RuntimeError(f"Gemini request failed: {type(exc).__name__}: {exc}")
            if attempt < max_retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)] + random.uniform(0, 2))
                continue
            raise last_err
        except json.JSONDecodeError as exc:
            last_err = RuntimeError(f"Gemini returned invalid JSON: {exc}")
            if attempt < max_retries - 1:
                time.sleep(backoffs[min(attempt, len(backoffs) - 1)])
                continue
            raise last_err

    raise last_err or RuntimeError("Gemini call failed")


def doctrinal_excerpts() -> str:
    excerpts: list[str] = []
    if DOCTRINE_PATH.exists():
        excerpts.append("### DOCTRINE (excerpt)\n\n" + DOCTRINE_PATH.read_text(encoding="utf-8")[:1500].strip())
    if PHILOSOPHY_PATH.exists():
        excerpts.append("### PHILOSOPHY (excerpt)\n\n" + PHILOSOPHY_PATH.read_text(encoding="utf-8")[:1200].strip())
    return "\n\n".join(excerpts)


def load_book_context(book_slug: str) -> str:
    path = BOOK_CONTEXTS_DIR / f"{book_slug}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_reference_bundle(book_slug: str, chapter: int, explicit_path: pathlib.Path | None = None) -> dict[str, Any]:
    path = explicit_path or REFERENCE_BUNDLE_PATHS.get((book_slug, chapter))
    if path is None:
        raise FileNotFoundError(f"No reference bundle configured for {book_slug} {chapter}")
    return json.loads(path.read_text(encoding="utf-8"))


def verse_yaml_path(testament: str, book_slug: str, chapter: int, verse: int) -> pathlib.Path:
    return REPO_ROOT / "translation" / testament / book_slug / f"{chapter:03d}" / f"{verse:03d}.yaml"


def load_source_fallback(book_slug: str, chapter: int, verse: int) -> tuple[str, str] | None:
    if book_slug == "sirach":
        parsed_path = REPO_ROOT / "sources" / "lxx" / "swete" / "parsed_ai" / f"SIR_{chapter:03d}.json"
        if parsed_path.exists():
            data = json.loads(parsed_path.read_text(encoding="utf-8"))
            for item in data.get("verses") or []:
                if int(item.get("verse", -1)) == verse and (item.get("greek") or "").strip():
                    return item["greek"].strip(), str(parsed_path)
    if book_slug == "prayer_of_manasseh":
        corpus_path = REPO_ROOT / "sources" / "lxx" / "prayer_of_manasseh" / "corpus" / "MAN.jsonl"
        if corpus_path.exists():
            for raw in corpus_path.read_text(encoding="utf-8").splitlines():
                if not raw.strip():
                    continue
                item = json.loads(raw)
                if int(item.get("chapter", -1)) == chapter and int(item.get("verse", -1)) == verse:
                    greek = (item.get("greek") or "").strip()
                    if greek:
                        return greek, str(corpus_path)
    return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u00a0", " ")).strip()


def load_verse_record(testament: str, book_slug: str, chapter: int, verse: int) -> dict[str, Any]:
    path = verse_yaml_path(testament, book_slug, chapter, verse)
    if not path.exists():
        raise FileNotFoundError(path)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    source = dict(data.get("source") or {})
    source_text = normalize_text(source.get("text") or source.get("body") or "")
    fallback_used = False
    fallback_path = ""
    if not source_text:
        fallback = load_source_fallback(book_slug, chapter, verse)
        if fallback is not None:
            source_text, fallback_path = fallback
            source_text = normalize_text(source_text)
            fallback_used = True
            source["text"] = source_text
            source.setdefault("language", "Greek")

    return {
        "yaml_path": str(path),
        "yaml_data": data,
        "verse_id": data.get("id") or f"{book_slug}.{chapter}.{verse}",
        "reference": data.get("reference") or f"{book_slug.replace('_', ' ').title()} {chapter}:{verse}",
        "source": source,
        "source_text": source_text,
        "source_fallback_used": fallback_used,
        "source_fallback_path": fallback_path,
        "translation_text": normalize_text((data.get("translation") or {}).get("text") or ""),
        "lexical_decisions": data.get("lexical_decisions") or [],
        "theological_decisions": data.get("theological_decisions") or [],
    }


def load_chapter_records(
    *,
    testament: str,
    book_slug: str,
    chapter: int,
    selected_verses: list[int] | None,
) -> list[dict[str, Any]]:
    chapter_dir = REPO_ROOT / "translation" / testament / book_slug / f"{chapter:03d}"
    if not chapter_dir.exists():
        raise FileNotFoundError(chapter_dir)
    wanted = set(selected_verses or [])
    records: list[dict[str, Any]] = []
    for yaml_path in sorted(chapter_dir.glob("*.yaml")):
        try:
            verse = int(yaml_path.stem)
        except ValueError:
            continue
        if wanted and verse not in wanted:
            continue
        records.append(load_verse_record(testament, book_slug, chapter, verse))
    return records


def build_blind_system_prompt(*, book_slug: str, book_context: str) -> str:
    parts: list[str] = [
        "You are producing a fresh English translation of a single ancient Greek verse for the Cartha Open Bible project.",
        "CRITICAL: you have NOT seen the existing Cartha English draft for this verse. Do not assume it, imitate it, or compare against familiar published Bible wording.",
        "Translate from the source text alone.",
        "",
        "## Task rules",
        "- Preserve the author's meaning, register, imagery, and ambiguity where possible.",
        "- Produce natural but source-faithful English.",
        "- Every lexical decision must cite one of: BDAG, LSJ, LEH, or Muraoka.",
        "- Do not mention any existing English translation.",
        "- Return JSON only.",
        "",
        doctrinal_excerpts(),
    ]
    if book_context.strip():
        parts.extend(["", "## Book context", book_context.strip()])
    return "\n".join(part for part in parts if part is not None).strip()


def build_blind_user_prompt(*, record: dict[str, Any]) -> str:
    language = normalize_text(record["source"].get("language") or "Greek")
    return (
        f"# Verse\n"
        f"Reference: {record['reference']}\n"
        f"Verse ID: {record['verse_id']}\n"
        f"Source language: {language}\n\n"
        f"## Source text\n"
        f"{record['source_text'] or '(missing)'}\n\n"
        "## Task\n"
        "Produce a fresh English translation of this verse from the source text alone. "
        "Then list the key lexical decisions, each citing BDAG, LSJ, LEH, or Muraoka, "
        "and add short translator notes about the main interpretive pressure points."
    )


def build_stacked_system_prompt(*, book_context: str) -> str:
    v3_path = REPO_ROOT / "tools" / "prompts" / "gemini_review_v3_author_intent.md"
    base = v3_path.read_text(encoding="utf-8") if v3_path.exists() else ""
    extra = """
---

## Stacked-review pilot instructions

You are adjudicating between an existing Cartha draft and an
independent blind draft.

Your single question is:

> Which rendering is closest to what the author meant for the original
> audience, given the source text, commentary context, and published
> reference translations as secondary data points?

Return one JSON object matching the supplied schema.

- `retain` = keep the existing Cartha draft as-is.
- `modify` = keep the draft's basic direction but rewrite it.
- `reject` = the current draft fundamentally misses the verse and should
  be replaced.

Published translations and commentary are evidence, not authority.
Ground the verdict in the source text first.
"""
    if book_context.strip():
        extra += "\n## Book context\n\n" + book_context.strip() + "\n"
    return (base.strip() + "\n\n" + extra.strip()).strip()


def _format_decision_block(title: str, decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return f"## {title}\n(none)\n"
    lines = [f"## {title}"]
    for idx, item in enumerate(decisions, start=1):
        lines.append(
            f"{idx}. source_word={item.get('source_word')!r}; "
            f"chosen={item.get('chosen')!r}; "
            f"lexicon={item.get('lexicon')!r}; "
            f"rationale={normalize_text(item.get('rationale') or '')!r}"
        )
    lines.append("")
    return "\n".join(lines)


def build_stacked_user_prompt(
    *,
    record: dict[str, Any],
    blind_draft: dict[str, Any],
    reference_bundle: dict[str, Any],
) -> str:
    verse_num = str(int(pathlib.Path(record["yaml_path"]).stem))
    verse_ref = (reference_bundle.get("verses") or {}).get(verse_num) or {}
    commentary_block = normalize_text(reference_bundle.get("commentary_block") or "")
    verse_commentary = normalize_text(verse_ref.get("verse_commentary") or "")
    charles_apot = normalize_text(verse_ref.get("charles_apot") or "")
    nets = normalize_text(verse_ref.get("nets") or "")
    nrsv = normalize_text(verse_ref.get("nrsv") or "")
    source_note = ""
    if record["source_fallback_used"]:
        source_note = (
            "\nNOTE: the verse YAML's `source.text` was blank, so the source text "
            f"below was filled from `{record['source_fallback_path']}`. "
            "Judge the current English draft against this recovered source text."
        )

    parts = [
        f"# Verse under adjudication\nReference: {record['reference']}\nVerse ID: {record['verse_id']}{source_note}",
        "## Source text",
        record["source_text"] or "(missing)",
        "## Existing Cartha draft",
        record["translation_text"] or "(missing)",
        _format_decision_block("Existing lexical decisions", record["lexical_decisions"]),
        _format_decision_block("Existing theological decisions", record["theological_decisions"]),
        "## Independent AI draft — produced without seeing the existing Cartha draft",
        normalize_text(blind_draft.get("english_text") or ""),
        _format_decision_block("Blind draft lexical decisions", blind_draft.get("lexical_decisions") or []),
        "## Published reference translations",
        "These reference excerpts may reflect different versification, longer or shorter textual additions, or chapter traditions. Use them as comparison data, not as a rigid verse-numbering authority.",
        f"- Charles APOT 1913 (PD): {charles_apot or '(not supplied)'}",
        f"- NETS excerpt: {nets or '(not supplied)'}",
        f"- NRSV excerpt: {nrsv or '(not supplied)'}",
        "## Commentary context",
        commentary_block or "(not supplied)",
        "## Verse-specific commentary",
        verse_commentary or "(none)",
        "## Task",
        (
            "Return a verdict of retain / modify / reject for the existing Cartha draft. "
            "Use source-language evidence first, then explain how the blind draft, reference "
            "translations, and commentary affect your judgment. If modification is needed, "
            "provide the best rewrite."
        ),
    ]
    return "\n\n".join(part.strip() for part in parts if str(part).strip())


def normalize_stacked_review(raw: dict[str, Any], *, fallback_verse_id: str) -> dict[str, Any]:
    out = dict(raw or {})
    out["verse_id"] = normalize_text(out.get("verse_id") or fallback_verse_id)
    out["commentary_alignment"] = normalize_text(out.get("commentary_alignment") or "")
    proposed = normalize_text(out.get("proposed_rewrite") or "")
    out["proposed_rewrite"] = proposed or None
    out["key_issues"] = [normalize_text(item) for item in (out.get("key_issues") or []) if normalize_text(item)]
    out["reasoning"] = normalize_text(out.get("reasoning") or "")
    out["reference_divergences"] = [
        {
            "source": normalize_text(item.get("source") or ""),
            "rendering": normalize_text(item.get("rendering") or ""),
            "alignment": normalize_text(item.get("alignment") or ""),
            "notes": normalize_text(item.get("notes") or ""),
        }
        for item in (out.get("reference_divergences") or [])
        if isinstance(item, dict)
    ]
    return out


def process_one_verse(
    *,
    record: dict[str, Any],
    reference_bundle: dict[str, Any],
    book_context: str,
    model: str,
) -> dict[str, Any]:
    if not record["source_text"]:
        raise ValueError(f"{record['reference']}: source text missing and no fallback available")

    blind_system = build_blind_system_prompt(book_slug=record["verse_id"].split(".")[0].lower(), book_context=book_context)
    blind_user = build_blind_user_prompt(record=record)
    t0 = time.time()
    blind = call_gemini_json(
        system_prompt=blind_system,
        user_prompt=blind_user,
        response_schema=BLIND_DRAFT_SCHEMA,
        model=model,
    )
    blind_elapsed = round(time.time() - t0, 2)

    stacked_system = build_stacked_system_prompt(book_context=book_context)
    stacked_user = build_stacked_user_prompt(
        record=record,
        blind_draft=blind,
        reference_bundle=reference_bundle,
    )
    t1 = time.time()
    stacked = call_gemini_json(
        system_prompt=stacked_system,
        user_prompt=stacked_user,
        response_schema=STACKED_SCHEMA,
        model=model,
    )
    stacked_elapsed = round(time.time() - t1, 2)

    return {
        "pilot_version": "phase10_stacked_pilot_v1",
        "generated_at": utc_now(),
        "model": model,
        "status": "completed",
        "verse_id": record["verse_id"],
        "reference": record["reference"],
        "source": {
            "text": record["source_text"],
            "language": normalize_text(record["source"].get("language") or ""),
            "edition": normalize_text(record["source"].get("edition") or ""),
            "yaml_path": record["yaml_path"],
            "fallback_used": record["source_fallback_used"],
            "fallback_path": record["source_fallback_path"],
        },
        "existing_draft": {
            "text": record["translation_text"],
            "lexical_decisions": record["lexical_decisions"],
            "theological_decisions": record["theological_decisions"],
        },
        "references": {
            "chapter_commentary_block": normalize_text(reference_bundle.get("commentary_block") or ""),
            "verse_reference_bundle": (reference_bundle.get("verses") or {}).get(str(int(pathlib.Path(record["yaml_path"]).stem))) or {},
        },
        "blind_draft": blind,
        "stacked_review": normalize_stacked_review(stacked, fallback_verse_id=record["verse_id"]),
        "timing": {
            "blind_seconds": blind_elapsed,
            "stacked_seconds": stacked_elapsed,
            "total_seconds": round(blind_elapsed + stacked_elapsed, 2),
        },
    }


async def process_records(
    *,
    records: list[dict[str, Any]],
    reference_bundle: dict[str, Any],
    book_context: str,
    model: str,
    out_dir: pathlib.Path,
    concurrency: int,
) -> list[dict[str, Any]]:
    verses_dir = out_dir / "verses"
    verses_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(max(1, concurrency))
    results: list[dict[str, Any]] = []

    async def run_one(record: dict[str, Any]) -> None:
        verse = int(pathlib.Path(record["yaml_path"]).stem)
        out_path = verses_dir / f"{verse:03d}.json"
        async with sem:
            try:
                result = await asyncio.to_thread(
                    process_one_verse,
                    record=record,
                    reference_bundle=reference_bundle,
                    book_context=book_context,
                    model=model,
                )
                result["book_slug"] = pathlib.Path(record["yaml_path"]).parent.parent.name
                result["chapter"] = int(pathlib.Path(record["yaml_path"]).parent.name)
                result["verse"] = verse
            except Exception as exc:
                result = {
                    "pilot_version": "phase10_stacked_pilot_v1",
                    "generated_at": utc_now(),
                    "status": "error",
                    "book_slug": pathlib.Path(record["yaml_path"]).parent.parent.name,
                    "chapter": int(pathlib.Path(record["yaml_path"]).parent.name),
                    "verse": verse,
                    "verse_id": record["verse_id"],
                    "reference": record["reference"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(result)

    await asyncio.gather(*(run_one(record) for record in records))
    return sorted(results, key=lambda item: int(item.get("verse", 0)))


def summarize_results(
    *,
    testament: str,
    book_slug: str,
    chapter: int,
    model: str,
    reference_path: pathlib.Path,
    results: list[dict[str, Any]],
    started_at: str,
) -> dict[str, Any]:
    verdict_counts = {"retain": 0, "modify": 0, "reject": 0}
    blind_agreement = {"high": 0, "medium": 0, "low": 0}
    completed = 0
    errors = 0
    fallback_verses: list[int] = []
    for item in results:
        if item.get("status") != "completed":
            errors += 1
            continue
        completed += 1
        stacked = item.get("stacked_review") or {}
        blind = normalize_text(stacked.get("agreement_with_blind_draft") or "")
        verdict = normalize_text(stacked.get("verdict") or "")
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1
        if blind in blind_agreement:
            blind_agreement[blind] += 1
        source = item.get("source") or {}
        if source.get("fallback_used"):
            fallback_verses.append(int(item["verse"]))

    return {
        "pilot_version": "phase10_stacked_pilot_v1",
        "generated_at": utc_now(),
        "started_at": started_at,
        "testament": testament,
        "book_slug": book_slug,
        "chapter": chapter,
        "model": model,
        "reference_bundle_path": str(reference_path),
        "verse_count": len(results),
        "completed_count": completed,
        "error_count": errors,
        "verdict_counts": verdict_counts,
        "blind_agreement_counts": blind_agreement,
        "source_fallback_verses": fallback_verses,
        "verse_files": [f"verses/{int(item['verse']):03d}.json" for item in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", required=True, choices=["sirach", "prayer_of_manasseh"])
    parser.add_argument("--chapter", required=True, type=int)
    parser.add_argument("--testament", default="deuterocanon")
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--references", type=pathlib.Path, help="Override reference bundle JSON path")
    parser.add_argument("--verses", help="Optional verse selector like 1-5,9,11")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    selected = parse_verse_selector(args.verses) if args.verses else None
    records = load_chapter_records(
        testament=args.testament,
        book_slug=args.book,
        chapter=args.chapter,
        selected_verses=selected,
    )
    reference_path = args.references or REFERENCE_BUNDLE_PATHS.get((args.book, args.chapter))
    if reference_path is None:
        raise FileNotFoundError(f"No reference bundle configured for {args.book} {args.chapter}")
    reference_bundle = load_reference_bundle(args.book, args.chapter, explicit_path=reference_path)
    book_context = load_book_context(args.book)

    args.out.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        payload = {
            "book": args.book,
            "chapter": args.chapter,
            "testament": args.testament,
            "out": str(args.out),
            "reference_bundle": str(reference_path),
            "verses": [int(pathlib.Path(record["yaml_path"]).stem) for record in records],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    started_at = utc_now()
    results = asyncio.run(
        process_records(
            records=records,
            reference_bundle=reference_bundle,
            book_context=book_context,
            model=args.model,
            out_dir=args.out,
            concurrency=args.concurrency,
        )
    )
    summary = summarize_results(
        testament=args.testament,
        book_slug=args.book,
        chapter=args.chapter,
        model=args.model,
        reference_path=reference_path,
        results=results,
        started_at=started_at,
    )
    (args.out / "pilot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
