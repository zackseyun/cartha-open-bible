#!/usr/bin/env python3
"""validate_vs_betamasaheft.py — compare OCR'd Enoch against Beta maṣāḥǝft.

This is an edition-comparison/apparatus tool, not the primary OCR-accuracy
metric. OCR quality should be measured against hand-corrected scan truth.
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sys
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
BETAMASAHEFT = pathlib.Path.home() / "cartha-reference-local" / "enoch_betamasaheft" / "LIT1340EnochE.xml"
TRANSCRIBED = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "transcribed"
REPORTS = REPO_ROOT / "sources" / "enoch" / "ethiopic" / "reports"

sys.path.insert(0, str(REPO_ROOT / "tools" / "ethiopic"))
from normalize import normalize_for_comparison, normalize_for_alignment  # type: ignore


def extract_beta_chapter(chapter: int) -> str:
    text = BETAMASAHEFT.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(rf'<div[^>]+type="chapter"[^>]+n="{chapter}"[^>]*>.*?<ab>(.*?)</ab>', re.S)
    m = pattern.search(text)
    if not m:
        raise RuntimeError(f"Could not find chapter {chapter} in {BETAMASAHEFT}")
    chunk = m.group(1)
    chunk = re.sub(r"<[^>]+>", " ", chunk)
    return re.sub(r"\s+", " ", chunk).strip()


def levenshtein_ops(a: str, b: str) -> tuple[int, list[tuple[str, int, int, int, int]]]:
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, str] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = (i - 1, 0, "delete")
    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = (0, j - 1, "insert")
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
                back[i][j] = (i - 1, j - 1, "equal")
            else:
                choices = [
                    (dp[i - 1][j] + 1, (i - 1, j, "delete")),
                    (dp[i][j - 1] + 1, (i, j - 1, "insert")),
                    (dp[i - 1][j - 1] + 1, (i - 1, j - 1, "replace")),
                ]
                cost, prev = min(choices, key=lambda x: x[0])
                dp[i][j] = cost
                back[i][j] = prev
    ops: list[tuple[str, int, int, int, int]] = []
    i, j = n, m
    while i > 0 or j > 0:
        prev = back[i][j]
        if prev is None:
            break
        pi, pj, op = prev
        ops.append((op, pi, i, pj, j))
        i, j = pi, pj
    ops.reverse()
    return dp[n][m], ops


def sample_differences(a: str, b: str, *, limit: int = 12) -> list[dict[str, Any]]:
    matcher = difflib.SequenceMatcher(a=a, b=b)
    out: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        ctx_a = a[max(0, i1 - 20):min(len(a), i2 + 20)]
        ctx_b = b[max(0, j1 - 20):min(len(b), j2 + 20)]
        out.append({
            "tag": tag,
            "ocr": a[i1:i2],
            "oracle": b[j1:j2],
            "ocr_context": ctx_a,
            "oracle_context": ctx_b,
        })
        if len(out) >= limit:
            break
    return out


def classify_samples(edition_name: str, edition_text: str, beta_text: str, other_name: str, other_text: str) -> list[dict[str, Any]]:
    raw = sample_differences(edition_text, beta_text, limit=10)
    classified: list[dict[str, Any]] = []
    for item in raw:
        ocr = item["ocr"]
        oracle = item["oracle"]
        classification = "unresolved"
        if oracle and oracle in other_text and ocr not in other_text:
            classification = "likely_ocr_error"
        elif ocr and ocr in other_text and oracle not in other_text:
            classification = "likely_witness_variant"
        elif (not ocr or not oracle) and item["tag"] in {"insert", "delete"}:
            classification = "likely_spacing_or_omission"
        classified.append({
            "edition": edition_name,
            "other_edition": other_name,
            "classification": classification,
            **item,
        })
    return classified


def measure_one(ocr_text: str, beta_text: str) -> dict[str, Any]:
    norm_ocr = normalize_for_comparison(ocr_text)
    norm_beta = normalize_for_comparison(beta_text)
    align_ocr = normalize_for_alignment(ocr_text)
    align_beta = normalize_for_alignment(beta_text)
    distance, _ = levenshtein_ops(align_ocr, align_beta)
    denom = max(len(align_ocr), len(align_beta), 1)
    accuracy = max(0.0, 1.0 - (distance / denom))
    return {
        "chars_raw": len(ocr_text.strip()),
        "chars_normalized": len(align_ocr),
        "oracle_chars_normalized": len(align_beta),
        "distance": distance,
        "accuracy": round(accuracy, 6),
        "length_delta": len(align_ocr) - len(align_beta),
        "ocr_normalized": norm_ocr,
        "oracle_normalized": norm_beta,
        "samples": sample_differences(align_ocr, align_beta),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", required=True, type=int)
    ap.add_argument("--editions", nargs="+", default=["dillmann_1851", "charles_1906"])
    args = ap.parse_args()

    beta = extract_beta_chapter(args.chapter)
    results: dict[str, Any] = {
        "chapter": args.chapter,
        "beta_chars": len(beta),
        "beta_normalized_chars": len(normalize_for_alignment(beta)),
        "editions": {},
    }

    edition_texts: dict[str, str] = {}
    for edition in args.editions:
        path = TRANSCRIBED / edition / f"ch{args.chapter:02d}.txt"
        text = path.read_text(encoding="utf-8")
        edition_texts[edition] = text
        results["editions"][edition] = measure_one(text, beta)

    if len(args.editions) == 2:
        a_name, b_name = args.editions
        a_text = normalize_for_alignment(edition_texts[a_name])
        b_text = normalize_for_alignment(edition_texts[b_name])
        dist, _ = levenshtein_ops(a_text, b_text)
        denom = max(len(a_text), len(b_text), 1)
        results["between_editions"] = {
            "distance": dist,
            "agreement": round(1.0 - (dist / denom), 6),
            "samples": sample_differences(a_text, b_text),
        }
        results["editions"][a_name]["classified_samples"] = classify_samples(a_name, a_text, normalize_for_alignment(beta), b_name, b_text)
        results["editions"][b_name]["classified_samples"] = classify_samples(b_name, b_text, normalize_for_alignment(beta), a_name, a_text)

    REPORTS.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS / f"ch{args.chapter:02d}_betamasaheft_validation.json"
    md_path = REPORTS / f"ch{args.chapter:02d}_betamasaheft_validation.md"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# 1 Enoch chapter {args.chapter} — Beta maṣāḥǝft validation",
        "",
        f"- Oracle normalized chars: **{results['beta_normalized_chars']}**",
    ]
    for edition in args.editions:
        row = results["editions"][edition]
        lines.append(f"- **{edition}**: accuracy **{row['accuracy']:.2%}** ({row['distance']} edits over {row['oracle_chars_normalized']} oracle chars)")
    if "between_editions" in results:
        lines.append(f"- **Charles vs Dillmann agreement**: **{results['between_editions']['agreement']:.2%}**")
    lines.append("")
    lines.append("## Sample disagreements")
    for edition in args.editions:
        lines.append(f"### {edition}")
        for item in results["editions"][edition].get("classified_samples", [])[:5]:
            lines.append(f"- `{item['classification']}` — OCR `{item['ocr']}` vs oracle `{item['oracle']}`")
        lines.append("")
    md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(json.dumps({
        "json_report": str(json_path),
        "markdown_report": str(md_path),
        "summary": {
            edition: results["editions"][edition]["accuracy"] for edition in args.editions
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
