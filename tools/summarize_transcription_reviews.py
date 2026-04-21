#!/usr/bin/env python3
"""summarize_transcription_reviews.py — summarize Azure/Opus page-review outputs.

Understands:
- strict Azure review outputs (`*.review.json`)
- Claude Opus review outputs (`*.opus-review.json`), including a few
  sloppy cases like fenced JSON or prose before the JSON object

Useful for quickly answering:
- how many review files are actually parseable?
- how many corrections are meaning-altering vs cosmetic?
- which pages are highest risk for manual adjudication?
"""
from __future__ import annotations

import argparse
import json
import pathlib
from collections import Counter
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_GPT54_DIR = REPO_ROOT / "sources" / "lxx" / "swete" / "reviews" / "gpt54"
DEFAULT_OPUS_GLOB = REPO_ROOT / "sources" / "lxx" / "swete" / "transcribed"
KNOWN_SEVERITIES = {"meaning-altering", "grammatical", "cosmetic"}
KNOWN_SECTIONS = {"BODY", "APPARATUS", "RUNNING HEAD", "MARGINALIA"}
KNOWN_CATEGORIES = {
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
}


def strip_code_fences(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_relaxed_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    candidates = []
    raw = text.strip()
    if raw:
        candidates.append(raw)
        stripped = strip_code_fences(raw)
        if stripped != raw:
            candidates.append(stripped)
        if "{" in raw and "}" in raw:
            candidates.append(raw[raw.find("{"): raw.rfind("}") + 1].strip())
            if stripped != raw and "{" in stripped and "}" in stripped:
                candidates.append(stripped[stripped.find("{"): stripped.rfind("}") + 1].strip())

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value, None
    lowered = raw.lower()
    if "hit your limit" in lowered:
        return None, "limit"
    if not raw:
        return None, "empty"
    return None, "invalid"


def iter_review_files(paths: list[pathlib.Path]) -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    for path in paths:
        if path.is_file():
            found.append(path)
            continue
        if path.is_dir():
            found.extend(sorted(path.rglob("*.review.json")))
            found.extend(sorted(path.rglob("*.opus-review.json")))
    # de-duplicate while preserving order
    deduped: list[pathlib.Path] = []
    seen = set()
    for path in found:
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def stem_name(path: pathlib.Path) -> str:
    name = path.name
    if name.endswith(".opus-review.json"):
        return name[:-len(".opus-review.json")]
    if name.endswith(".review.json"):
        return name[:-len(".review.json")]
    return path.stem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=pathlib.Path,
        help="Files or directories to scan (default: Azure review dir + transcribed Opus outputs)",
    )
    parser.add_argument("--top", type=int, default=20, help="How many high-risk pages to print")
    args = parser.parse_args()

    scan_paths = args.paths or [DEFAULT_GPT54_DIR, DEFAULT_OPUS_GLOB]
    files = iter_review_files(scan_paths)
    if not files:
        print("No review files found.")
        return 1

    parse_status = Counter()
    severity = Counter()
    section = Counter()
    category = Counter()
    model_family = Counter()
    high_risk: list[tuple[int, int, int, str]] = []

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        data, status = parse_relaxed_json(text)
        if data is None:
            parse_status[status or "invalid"] += 1
            continue
        parse_status["ok"] += 1
        family = "opus" if path.name.endswith(".opus-review.json") else "gpt54"
        model_family[family] += 1
        corrections = data.get("corrections") or []
        uncertain = data.get("uncertain") or []
        meaning = 0
        for item in corrections:
            if not isinstance(item, dict):
                severity["<invalid:item>"] += 1
                continue
            sev_raw = str(item.get("severity", ""))
            sec_raw = str(item.get("section", ""))
            cat_raw = str(item.get("category", ""))
            sev = sev_raw if sev_raw in KNOWN_SEVERITIES else f"<invalid:{sev_raw or 'blank'}>"
            sec = sec_raw if sec_raw in KNOWN_SECTIONS else f"<invalid:{sec_raw or 'blank'}>"
            cat = cat_raw if cat_raw in KNOWN_CATEGORIES else f"<invalid:{cat_raw or 'blank'}>"
            severity[sev] += 1
            section[sec] += 1
            category[cat] += 1
            if sev_raw == "meaning-altering":
                meaning += 1
        high_risk.append((meaning, len(corrections), len(uncertain), stem_name(path)))

    total = len(files)
    ok = parse_status["ok"]
    failed = total - ok

    print("# Transcription review summary")
    print()
    print(f"- Files scanned: {total}")
    print(f"- Parseable review files: {ok}")
    print(f"- Unparseable review files: {failed}")
    if model_family:
        fam = ", ".join(f"{k}={v}" for k, v in sorted(model_family.items()))
        print(f"- Parseable by family: {fam}")
    if failed:
        details = ", ".join(f"{k}={v}" for k, v in sorted(parse_status.items()) if k != "ok")
        print(f"- Unparseable breakdown: {details}")
    print()

    def print_counter(title: str, counter: Counter[str]) -> None:
        if not counter:
            return
        print(f"## {title}")
        for key, value in counter.most_common():
            label = key or "<blank>"
            print(f"- {label}: {value}")
        print()

    print_counter("Corrections by severity", severity)
    print_counter("Corrections by section", section)
    print_counter("Corrections by category", category)

    print(f"## Top {min(args.top, len(high_risk))} high-risk pages")
    for meaning, corr, uncertain, stem in sorted(high_risk, reverse=True)[: args.top]:
        print(f"- {stem}: meaning={meaning}, corrections={corr}, uncertain={uncertain}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
