#!/usr/bin/env python3
"""segment_chapters.py — build tentative 2 Baruch chapter buckets from the Ceriani page corpus.

This is an explicitly *translation-prep* layer, not a claim of final verse-level
alignment. It turns the full Ceriani page corpus into tentative chapter buckets so
translation work can proceed chapter-by-chapter while later spot-checks / control
witnesses refine the boundaries.

Method:
- use a small set of chapter-start anchors inferred from representative pages
- interpolate a likely chapter start for every Ceriani PDF page in reading order
- define each page's chapter coverage as start..next_page_start (inclusive)
- invert that into per-chapter page buckets

The resulting chapter buckets intentionally overlap at boundary pages. That is
preferred to prematurely dropping boundary material.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, asdict
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PAGE_INDEX_PATH = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'page_index.json'
PAGES_DIR = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'pages'
CHAPTER_ROOT = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'chapters'
ANCHOR_PATH = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'chapter_anchors.json'
PAGE_RANGE_PATH = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'page_chapter_ranges.json'
BUCKET_PATH = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'chapter_buckets.json'
SEGMENTATION_NOTE = REPO_ROOT / 'sources' / '2baruch' / 'syriac' / 'transcribed' / 'ceriani1871' / 'CHAPTER_SEGMENTATION.md'
TRANSLATION_ROOT = REPO_ROOT / 'translation' / 'extra_canonical' / '2_baruch'
TRANSLATION_MANIFEST = TRANSLATION_ROOT / 'README.md'

BOOK = '2 Baruch'
BOOK_ID = '2BA'
CHAPTER_COUNT = 87

# These anchors are intentionally sparse and explicit. They came from direct inspection
# of representative pages plus model-assisted page-level chapter identification.
ANCHORS = [
    {
        'pdf_page': 228,
        'chapter_start': 1,
        'chapter_end_hint': 3,
        'confidence': 'high',
        'basis': 'Opening Ceriani page contains the title, chapter 1 opening, and reaches chapter 3.',
    },
    {
        'pdf_page': 224,
        'chapter_start': 9,
        'chapter_end_hint': 11,
        'confidence': 'medium',
        'basis': 'Model-assisted early-book anchor; used as a stabilizing point between the opening page and chapter 14 anchor.',
    },
    {
        'pdf_page': 220,
        'chapter_start': 14,
        'chapter_end_hint': 15,
        'confidence': 'high',
        'basis': 'Model-assisted anchor on a manually rescued page.',
    },
    {
        'pdf_page': 205,
        'chapter_start': 40,
        'chapter_end_hint': 42,
        'confidence': 'medium',
        'basis': 'Model-assisted mid-book anchor used to keep the interpolation from drifting.',
    },
    {
        'pdf_page': 190,
        'chapter_start': 56,
        'chapter_end_hint': 58,
        'confidence': 'medium',
        'basis': 'Model-assisted later-book anchor, checked against the monotonic printed-page map.',
    },
    {
        'pdf_page': 162,
        'chapter_start': 85,
        'chapter_end_hint': 87,
        'confidence': 'medium',
        'basis': 'Model-assisted epistle-end anchor near the end of the Ceriani scan span.',
    },
]

@dataclass(frozen=True)
class PageRange:
    pdf_page: int
    printed_page: int | None
    chapter_start: int
    chapter_end: int
    anchor: bool
    confidence: str
    basis: str


def load_page_index() -> dict[str, Any]:
    return json.loads(PAGE_INDEX_PATH.read_text(encoding='utf-8'))


def page_text(pdf_page: int) -> str:
    path = PAGES_DIR / f'p{pdf_page:04d}.txt'
    lines = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('#'):
            continue
        if line.strip():
            lines.append(line)
    return '\n'.join(lines).strip()


def interpolate_pages(pages_desc: list[int]) -> dict[int, int]:
    anchors = sorted(ANCHORS, key=lambda a: a['pdf_page'], reverse=True)
    out: dict[int, int] = {}

    # assign anchor starts exactly
    for a in anchors:
        out[a['pdf_page']] = a['chapter_start']

    for i in range(len(anchors) - 1):
        left = anchors[i]
        right = anchors[i + 1]
        p_hi = left['pdf_page']
        p_lo = right['pdf_page']
        c_hi = left['chapter_start']
        c_lo = right['chapter_start']
        span = p_hi - p_lo
        for p in range(p_hi - 1, p_lo, -1):
            frac = (p_hi - p) / span
            est = round(c_hi + ((c_lo - c_hi) * frac))
            out[p] = est

    # enforce monotonicity in reading order (pdf desc => chapter asc)
    last = None
    for p in pages_desc:
        cur = out[p]
        if last is not None and cur < last:
            cur = last
        out[p] = cur
        last = cur
    return out


def build_page_ranges(index: dict[str, Any]) -> list[PageRange]:
    pages_desc = sorted((int(k) for k in index['pages'].keys()), reverse=True)
    starts = interpolate_pages(pages_desc)
    anchor_lookup = {a['pdf_page']: a for a in ANCHORS}
    ranges: list[PageRange] = []
    for i, p in enumerate(pages_desc):
        next_start = starts[pages_desc[i + 1]] if i + 1 < len(pages_desc) else CHAPTER_COUNT
        end = max(starts[p], next_start)
        meta = index['pages'][f'{p:04d}']
        if p in anchor_lookup:
            a = anchor_lookup[p]
            end = max(end, a['chapter_end_hint'])
            confidence = a['confidence']
            basis = a['basis']
            is_anchor = True
        else:
            confidence = 'tentative'
            basis = 'Interpolated between nearby anchor pages; boundary pages intentionally overlap.'
            is_anchor = False
        ranges.append(PageRange(
            pdf_page=p,
            printed_page=meta.get('source_printed_page'),
            chapter_start=starts[p],
            chapter_end=min(CHAPTER_COUNT, end),
            anchor=is_anchor,
            confidence=confidence,
            basis=basis,
        ))
    return ranges


def build_chapter_buckets(page_ranges: list[PageRange]) -> dict[int, dict[str, Any]]:
    buckets: dict[int, dict[str, Any]] = {}
    range_lookup = {r.pdf_page: r for r in page_ranges}
    for ch in range(1, CHAPTER_COUNT + 1):
        pages = [r.pdf_page for r in page_ranges if r.chapter_start <= ch <= r.chapter_end]
        pages.sort(reverse=True)
        texts = []
        printed = []
        for p in pages:
            r = range_lookup[p]
            printed.append(r.printed_page)
            texts.append(f'# Source page p{p:04d} (printed {r.printed_page})\n{page_text(p)}')
        buckets[ch] = {
            'chapter': ch,
            'reference': f'2 Baruch {ch}',
            'source_pdf_pages': pages,
            'source_printed_pages': printed,
            'chapter_bucket_method': 'tentative_page_interpolation_v1',
            'overlap_expected': True,
            'source_text': '\n\n'.join(texts).strip(),
        }
    return buckets


def write_outputs(page_ranges: list[PageRange], buckets: dict[int, dict[str, Any]]) -> None:
    CHAPTER_ROOT.mkdir(parents=True, exist_ok=True)
    ANCHOR_PATH.write_text(json.dumps(ANCHORS, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    PAGE_RANGE_PATH.write_text(json.dumps([asdict(r) for r in page_ranges], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    BUCKET_PATH.write_text(json.dumps({f'{ch:02d}': payload for ch, payload in buckets.items()}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    for ch, payload in buckets.items():
        txt_path = CHAPTER_ROOT / f'ch{ch:02d}.txt'
        json_path = CHAPTER_ROOT / f'ch{ch:02d}.json'
        txt_path.write_text(
            '\n'.join([
                f'# {payload["reference"]}',
                f'# method: {payload["chapter_bucket_method"]}',
                f'# source_pdf_pages: {", ".join(str(p) for p in payload["source_pdf_pages"])}',
                f'# overlap_expected: {payload["overlap_expected"]}',
                payload['source_text'],
                ''
            ]),
            encoding='utf-8',
        )
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    SEGMENTATION_NOTE.write_text(
        f'''# 2 Baruch — tentative chapter segmentation\n\nThis layer turns the full Ceriani page corpus into **tentative chapter buckets** so\ntranslation can begin before final verse alignment is done.\n\n## Method\n\n- primary substrate: `sources/2baruch/syriac/transcribed/ceriani1871/pages/`\n- page order: **PDF 228 -> 162** (book start to book end)\n- anchor pages: `chapter_anchors.json`\n- interpolation: `page_chapter_ranges.json`\n- chapter buckets: `chapter_buckets.json` + `chapters/chNN.*`\n\n## Important warning\n\nThese are **translation-prep buckets**, not final critical-edition boundaries.\nBoundary pages intentionally overlap between adjacent chapters so no source text is\naccidentally dropped before later control-witness review.\n\n## Next refinement path\n\n1. targeted Kmosko control OCR around weak / boundary pages\n2. chapter-level review of bucket transitions\n3. later verse alignment inside each chapter bucket\n''',
        encoding='utf-8',
    )

    TRANSLATION_ROOT.mkdir(parents=True, exist_ok=True)
    TRANSLATION_MANIFEST.write_text(
        '# 2 Baruch translation scaffold\n\n'
        'This directory is now chapter-ready. Each YAML file points at a tentative '\
        'Ceriani chapter bucket and is intended as the landing zone for future '\
        'chapter drafting.\n',
        encoding='utf-8',
    )

    for ch, payload in buckets.items():
        yaml_path = TRANSLATION_ROOT / f'{ch:03d}.yaml'
        if yaml_path.exists():
            continue
        src_text = payload['source_text'].rstrip()
        pages = '[' + ', '.join(str(p) for p in payload['source_pdf_pages']) + ']'
        yaml_path.write_text(
            f'''id: {BOOK_ID}.{ch:03d}\nreference: 2 Baruch {ch}\nunit: chapter\nbook: 2 Baruch\nsource:\n  edition: Ceriani 1871 primary Syriac (tentative chapter bucket)\n  language: Syriac\n  chapter: {ch}\n  pages: {pages}\n  text: |-\n'''
            + ''.join(f'    {line}\n' for line in src_text.splitlines())
            + '''  note: Tentative chapter bucket built from the full Ceriani page corpus. Boundary pages may overlap with adjacent chapters until later control-witness review and verse alignment.\ntranslation:\n  text: ""\n  philosophy: optimal-equivalence\n  footnotes: []\n''',
            encoding='utf-8',
        )


def main() -> int:
    index = load_page_index()
    page_ranges = build_page_ranges(index)
    buckets = build_chapter_buckets(page_ranges)
    write_outputs(page_ranges, buckets)
    print(f'wrote {ANCHOR_PATH.relative_to(REPO_ROOT)}')
    print(f'wrote {PAGE_RANGE_PATH.relative_to(REPO_ROOT)}')
    print(f'wrote {BUCKET_PATH.relative_to(REPO_ROOT)}')
    print(f'wrote {CHAPTER_COUNT} chapter buckets under {CHAPTER_ROOT.relative_to(REPO_ROOT)}')
    print(f'scaffolded translation YAMLs under {TRANSLATION_ROOT.relative_to(REPO_ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
