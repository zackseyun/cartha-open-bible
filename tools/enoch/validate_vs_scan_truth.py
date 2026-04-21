#!/usr/bin/env python3
"""validate_vs_scan_truth.py — compare OCR output against hand-corrected scan truth.

This is the metric we actually want for OCR quality. Beta maṣāḥǝft remains
valuable as an apparatus/comparison witness, but not as the OCR accuracy target.
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
sys.path.insert(0, str(REPO_ROOT / 'tools' / 'ethiopic'))
from normalize import normalize_for_comparison, normalize_for_alignment  # type: ignore

TRUTH_ROOT = REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'hand_truth'
TRANSCRIBED_ROOT = REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'transcribed'
REPORTS_ROOT = REPO_ROOT / 'sources' / 'enoch' / 'ethiopic' / 'reports'

VERSE_MARK_RE = re.compile(r'(?m)(?<!\S)([1-9][0-9]?)\.\s*')


def levenshtein_distance(a: str, b: str) -> int:
    n, m = len(a), len(b)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            cur = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = min(prev + 1, dp[j] + 1, dp[j - 1] + 1)
            prev = cur
    return dp[m]


def sample_differences(a: str, b: str, limit: int = 10) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if tag == 'equal':
            continue
        out.append({
            'tag': tag,
            'ocr': a[i1:i2],
            'truth': b[j1:j2],
            'ocr_context': a[max(0, i1-20):min(len(a), i2+20)],
            'truth_context': b[max(0, j1-20):min(len(b), j2+20)],
        })
        if len(out) >= limit:
            break
    return out


def load_truth(edition: str, chapter: int, verses: list[int]) -> tuple[dict[int, str], dict[str, Any]]:
    truth_dir = TRUTH_ROOT / edition / f'ch{chapter:02d}'
    manifest = json.loads((truth_dir / 'manifest.json').read_text(encoding='utf-8'))
    truth: dict[int, str] = {}
    for verse in verses:
        path = truth_dir / f'v{verse:03d}.txt'
        truth[verse] = path.read_text(encoding='utf-8').strip()
    return truth, manifest


def load_ocr_text(edition: str, page: int, ocr_path: str | None) -> str:
    if ocr_path:
        return pathlib.Path(ocr_path).read_text(encoding='utf-8')
    path = TRANSCRIBED_ROOT / edition / 'pages' / f'p{page:04d}.txt'
    return path.read_text(encoding='utf-8')


def extract_ocr_verses(page_text: str) -> dict[int, str]:
    cleaned = page_text
    matches = list(VERSE_MARK_RE.finditer(cleaned.replace('I.', '1. ')))
    out: dict[int, str] = {}
    if not matches:
        return out
    text = cleaned.replace('I.', '1. ')
    matches = list(VERSE_MARK_RE.finditer(text))
    for idx, match in enumerate(matches):
        verse = int(match.group(1))
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        out[verse] = text[start:end].strip()
    return out


def token_metrics(ocr_norm: str, truth_norm: str) -> dict[str, Any]:
    splitter = re.compile(r'[\s፡።፤፥፦፧፨]+')
    ocr_tokens = [t for t in splitter.split(ocr_norm) if t]
    truth_tokens = [t for t in splitter.split(truth_norm) if t]
    ocr_set = set(ocr_tokens)
    truth_set = set(truth_tokens)
    shared = ocr_set & truth_set
    return {
        'ocr_token_count': len(ocr_tokens),
        'truth_token_count': len(truth_tokens),
        'shared_token_count': len(shared),
        'token_precision': round(len(shared) / max(len(ocr_set), 1), 6),
        'token_recall': round(len(shared) / max(len(truth_set), 1), 6),
        'missing_truth_tokens_sample': sorted(list(truth_set - ocr_set))[:25],
        'extra_ocr_tokens_sample': sorted(list(ocr_set - truth_set))[:25],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--edition', default='charles_1906')
    ap.add_argument('--chapter', type=int, default=1)
    ap.add_argument('--page', type=int, default=40)
    ap.add_argument('--verses', default='1-5')
    ap.add_argument('--ocr-path', default=None, help='Optional path to OCR text to validate instead of the default page transcript')
    ap.add_argument('--report-suffix', default='scan_truth_validation', help='Suffix for output report filenames')
    args = ap.parse_args()

    start, end = [int(x) for x in args.verses.split('-', 1)]
    wanted = list(range(start, end + 1))
    truth_by_verse, manifest = load_truth(args.edition, args.chapter, wanted)
    truth_joined = '\n'.join(truth_by_verse[v] for v in wanted)

    ocr_page = load_ocr_text(args.edition, args.page, args.ocr_path)
    ocr_by_verse = extract_ocr_verses(ocr_page)
    if any(v in ocr_by_verse for v in wanted):
        ocr_joined = '\n'.join(ocr_by_verse[v] for v in wanted if v in ocr_by_verse)
    else:
        ocr_joined = ocr_page.strip()

    ocr_norm = normalize_for_comparison(ocr_joined)
    truth_norm = normalize_for_comparison(truth_joined)
    ocr_align = normalize_for_alignment(ocr_joined)
    truth_align = normalize_for_alignment(truth_joined)
    dist = levenshtein_distance(ocr_align, truth_align)
    denom = max(len(ocr_align), len(truth_align), 1)
    accuracy = max(0.0, 1.0 - (dist / denom))

    report = {
        'edition': args.edition,
        'chapter': args.chapter,
        'page': args.page,
        'ocr_path': args.ocr_path,
        'verse_scope': wanted,
        'truth_manifest': manifest,
        'ocr_verse_keys_found': sorted(ocr_by_verse.keys()),
        'missing_ocr_verses': [v for v in wanted if v not in ocr_by_verse],
        'truth_chars_normalized': len(truth_align),
        'ocr_chars_normalized': len(ocr_align),
        'distance': dist,
        'accuracy': round(accuracy, 6),
        'token_metrics': token_metrics(ocr_norm, truth_norm),
        'samples': sample_differences(ocr_align, truth_align),
        'truth_text': truth_joined,
        'ocr_text': ocr_joined,
    }

    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_ROOT / f'ch{args.chapter:02d}_{args.report_suffix}.json'
    md_path = REPORTS_ROOT / f'ch{args.chapter:02d}_{args.report_suffix}.md'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lines = [
        f'# 1 Enoch chapter {args.chapter} — scan-truth validation ({args.report_suffix})',
        '',
        f'- Edition: **{args.edition}**',
        f'- OCR source page: **{args.page}**',
        f'- Truth scope: verses **{wanted[0]}–{wanted[-1]}**',
        f'- Normalized character accuracy: **{report["accuracy"]:.2%}**',
        f'- Levenshtein distance: **{dist}** over max **{denom}** normalized chars',
        f'- OCR verse markers found: **{report["ocr_verse_keys_found"]}**',
        f'- Missing OCR verses in scope: **{report["missing_ocr_verses"]}**',
        f'- Token precision / recall: **{report["token_metrics"]["token_precision"]:.2%} / {report["token_metrics"]["token_recall"]:.2%}**',
        '',
        '## Notes',
        '- This is the OCR metric we care about: OCR against a hand-corrected scan truth set.',
        '- Beta maṣāḥǝft is still useful as a comparison/apparatus witness, but not the OCR accuracy target.',
        '',
        '## Sample differences',
    ]
    for item in report['samples'][:6]:
        lines.append(f"- `{item['tag']}` — OCR `{item['ocr']}` vs truth `{item['truth']}`")
    md_path.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')

    print(json.dumps({'json_report': str(json_path), 'markdown_report': str(md_path), 'accuracy': report['accuracy']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
