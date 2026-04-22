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

# These anchors now come from *cleaned Ceriani page evidence* rather than only
# a few coarse hand-picked checkpoints. Each anchor records the earliest and latest
# trustworthy chapter markers visible on that page.
#
# Why not trust every printed numeral blindly? Because some pages still contain
# apparatus spill, repeated running numerals, or OCR-noise digits. So this list is a
# curated subset of the explicit page-level chapter markers that survived cleanup.
ANCHORS = [
    {"pdf_page": 228, "chapter_start": 1,  "chapter_end_hint": 3,  "confidence": "high",   "basis": "Opening Ceriani page contains the title plus explicit starts for chapters 1 and 3."},
    {"pdf_page": 227, "chapter_start": 4,  "chapter_end_hint": 5,  "confidence": "medium", "basis": "Single-page gap between the 1–3 opening anchor and the 5–6 Ceriani anchor; tightened as a control-backed transition page."},
    {"pdf_page": 226, "chapter_start": 5,  "chapter_end_hint": 6,  "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 5 and 6."},
    {"pdf_page": 225, "chapter_start": 7,  "chapter_end_hint": 8,  "confidence": "medium", "basis": "Single-page gap between the 5–6 and 9–10 anchor pages; tightened as the 7–8 transition page."},
    {"pdf_page": 224, "chapter_start": 9,  "chapter_end_hint": 10, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 9 and 10."},
    {"pdf_page": 222, "chapter_start": 11, "chapter_end_hint": 12, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 11 and 12."},
    {"pdf_page": 221, "chapter_start": 13, "chapter_end_hint": 13, "confidence": "high",   "basis": "Kmosko p0554 explicitly begins chapter XIII; mapped back onto the intervening Ceriani page."},
    {"pdf_page": 220, "chapter_start": 14, "chapter_end_hint": 14, "confidence": "high",   "basis": "Explicit chapter 14 numeral on a manually rescued Ceriani page."},
    {"pdf_page": 218, "chapter_start": 16, "chapter_end_hint": 19, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 16 through 19."},
    {"pdf_page": 217, "chapter_start": 20, "chapter_end_hint": 21, "confidence": "medium", "basis": "Single-page gap between the 16–19 Ceriani anchor and the explicit chapter-21 page; tightened as the chapter-20 transition page."},
    {"pdf_page": 216, "chapter_start": 21, "chapter_end_hint": 21, "confidence": "high",   "basis": "Explicit chapter 21 numeral visible at line start in Ceriani."},
    {"pdf_page": 214, "chapter_start": 22, "chapter_end_hint": 22, "confidence": "high",   "basis": "Explicit chapter 22 numeral visible at line start in Ceriani."},
    {"pdf_page": 212, "chapter_start": 25, "chapter_end_hint": 27, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 25 through 27."},
    {"pdf_page": 211, "chapter_start": 29, "chapter_end_hint": 29, "confidence": "high",   "basis": "Kmosko p0568 explicitly begins chapter XXIX; mapped to the matching Ceriani gap page."},
    {"pdf_page": 210, "chapter_start": 30, "chapter_end_hint": 31, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 30 and 31."},
    {"pdf_page": 209, "chapter_start": 32, "chapter_end_hint": 33, "confidence": "high",   "basis": "Kmosko p0570 explicitly begins chapter XXXII; used to tighten the Ceriani chapter-32/33 zone."},
    {"pdf_page": 208, "chapter_start": 34, "chapter_end_hint": 35, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 34 and 35."},
    {"pdf_page": 207, "chapter_start": 37, "chapter_end_hint": 39, "confidence": "medium", "basis": "Kmosko p0574 explicitly carries chapters XXXVIII–XXXIX; used to anchor the immediately preceding Ceriani transition page."},
    {"pdf_page": 206, "chapter_start": 38, "chapter_end_hint": 40, "confidence": "high",   "basis": "Ceriani page shows chapters 38 and 39; the extra stray digit was rejected as noise."},
    {"pdf_page": 205, "chapter_start": 41, "chapter_end_hint": 42, "confidence": "high",   "basis": "Kmosko p0576 explicitly begins chapter XLII; mapped back onto the Ceriani page between the 38–40 and 43–44 anchors."},
    {"pdf_page": 204, "chapter_start": 43, "chapter_end_hint": 44, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 43 and 44 after OCR rescue."},
    {"pdf_page": 203, "chapter_start": 45, "chapter_end_hint": 46, "confidence": "medium", "basis": "Single-page gap between the 43–44 and 46–48 anchored pages; tightened as the chapter-45 transition page."},
    {"pdf_page": 202, "chapter_start": 46, "chapter_end_hint": 48, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 46 through 48."},
    {"pdf_page": 198, "chapter_start": 49, "chapter_end_hint": 50, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 49 and 50."},
    {"pdf_page": 197, "chapter_start": 51, "chapter_end_hint": 51, "confidence": "high",   "basis": "Kmosko p0586 explicitly begins chapter LI; mapped to the matching Ceriani page."},
    {"pdf_page": 196, "chapter_start": 52, "chapter_end_hint": 52, "confidence": "high",   "basis": "Kmosko p0588 explicitly begins chapter LII; mapped to the matching Ceriani page."},
    {"pdf_page": 195, "chapter_start": 53, "chapter_end_hint": 53, "confidence": "medium", "basis": "Placed between explicit Kmosko/Ceriani chapter-52 and chapter-56 control points; tightened as chapter 53."},
    {"pdf_page": 194, "chapter_start": 54, "chapter_end_hint": 54, "confidence": "medium", "basis": "Placed inside the Kmosko cloud-vision control zone between chapter 53 and the later chapter-56 anchor."},
    {"pdf_page": 193, "chapter_start": 55, "chapter_end_hint": 55, "confidence": "medium", "basis": "Placed inside the Kmosko cloud-vision control zone between chapter 54 and the later chapter-56 anchor."},
    {"pdf_page": 190, "chapter_start": 56, "chapter_end_hint": 58, "confidence": "medium", "basis": "Later-book control anchor retained where Kmosko and Ceriani still leave some spread across late-middle chapters."},
    {"pdf_page": 189, "chapter_start": 60, "chapter_end_hint": 60, "confidence": "high",   "basis": "Kmosko p0598 explicitly begins chapter LX; mapped to the matching Ceriani page."},
    {"pdf_page": 188, "chapter_start": 61, "chapter_end_hint": 61, "confidence": "medium", "basis": "Control-backed interpolation between Kmosko chapter LX and Ceriani/Kmosko chapter LXIII anchors."},
    {"pdf_page": 187, "chapter_start": 62, "chapter_end_hint": 62, "confidence": "medium", "basis": "Control-backed interpolation between Kmosko chapter LX and Ceriani/Kmosko chapter LXIII anchors."},
    {"pdf_page": 186, "chapter_start": 63, "chapter_end_hint": 63, "confidence": "high",   "basis": "Explicit chapter 63 numeral visible at line start in Ceriani."},
    {"pdf_page": 184, "chapter_start": 65, "chapter_end_hint": 66, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 65 and 66."},
    {"pdf_page": 183, "chapter_start": 67, "chapter_end_hint": 68, "confidence": "high",   "basis": "Kmosko p0604 explicitly begins chapter LXVII; the adjacent Ceriani page is used to carry the 67–68 transition."},
    {"pdf_page": 182, "chapter_start": 69, "chapter_end_hint": 70, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 69 and 70."},
    {"pdf_page": 181, "chapter_start": 72, "chapter_end_hint": 73, "confidence": "high",   "basis": "Kmosko p0608 explicitly begins chapters LXXII and LXXIII; mapped to the matching Ceriani page."},
    {"pdf_page": 180, "chapter_start": 73, "chapter_end_hint": 74, "confidence": "high",   "basis": "Ceriani chapter 73 plus Kmosko p0609 chapter LXXIV tighten this page to the 73–74 edge."},
    {"pdf_page": 179, "chapter_start": 75, "chapter_end_hint": 75, "confidence": "high",   "basis": "Kmosko p0610 explicitly begins chapter LXXV; mapped to the matching Ceriani late-apocalypse page."},
    {"pdf_page": 178, "chapter_start": 76, "chapter_end_hint": 77, "confidence": "high",   "basis": "Clean Ceriani page-level numerals show chapters 76 and 77."},
    {"pdf_page": 176, "chapter_start": 78, "chapter_end_hint": 78, "confidence": "high",   "basis": "Kmosko p0621 gives the opening of the epistle (internal chapter I), mapped onto the first post-apocalypse Ceriani page."},
    {"pdf_page": 174, "chapter_start": 79, "chapter_end_hint": 79, "confidence": "medium", "basis": "Epistle ladder inferred from Kmosko epistle I plus the later IV–V checkpoint and the Ceriani 85–87 end anchor."},
    {"pdf_page": 172, "chapter_start": 80, "chapter_end_hint": 80, "confidence": "medium", "basis": "Epistle ladder inferred from Kmosko epistle I plus the later IV–V checkpoint and the Ceriani 85–87 end anchor."},
    {"pdf_page": 170, "chapter_start": 81, "chapter_end_hint": 81, "confidence": "medium", "basis": "Kmosko p0624 carries epistle chapter IV; mapped onto the corresponding Ceriani page in the epistle run."},
    {"pdf_page": 168, "chapter_start": 82, "chapter_end_hint": 82, "confidence": "medium", "basis": "Kmosko p0624 carries epistle chapter V; mapped onto the corresponding Ceriani page in the epistle run."},
    {"pdf_page": 166, "chapter_start": 83, "chapter_end_hint": 83, "confidence": "medium", "basis": "Epistle ladder continued between the Kmosko IV–V checkpoint and the Ceriani 85–87 end anchor."},
    {"pdf_page": 164, "chapter_start": 84, "chapter_end_hint": 84, "confidence": "medium", "basis": "Epistle ladder continued between the Kmosko IV–V checkpoint and the Ceriani 85–87 end anchor."},
    {"pdf_page": 162, "chapter_start": 85, "chapter_end_hint": 87, "confidence": "high",   "basis": "Epistle-end anchor near the end of the Ceriani scan span; chapter 87 is explicit here."},
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
