# 2 Esdras (4 Ezra) source materials

This directory holds the public-domain source editions for the Cartha
Open Bible's forthcoming 2 Esdras translation. **Scope and strategy:
see [`../../2ESDRAS.md`](../../2ESDRAS.md).**

Unlike the LXX-based deuterocanonical books (which have Greek primary
sources; see [`../../DEUTEROCANONICAL.md`](../../DEUTEROCANONICAL.md)),
2 Esdras survives only through a chain of daughter translations from
a lost Hebrew and a lost Greek. The Latin is primary; the other
six languages serve as independent textual witnesses.

## Vendored scans

All PDFs below are Public Domain (pre-1929 or author-died before
1954 depending on jurisdiction). They are bundled in
`scans/` for OCR processing; cleaned UTF-8 text from each witness
will be produced into the corresponding subdirectory.

| File | Edition | Year | Purpose | License |
|---|---|---|---|---|
| `scans/violet_1910_vol1.pdf` | Violet, *Die Esra-Apokalypse (IV. Esra), I: Die Überlieferung* (GCS 18) | 1910 | Multi-witness critical edition: Latin + Syriac + Ethiopic + Arabic + Armenian + Georgian in parallel columns | PD |
| `scans/violet_1910_vol2.pdf` | Violet, GCS 18 vol. 2 | 1910 | Continuation / appendix material | PD |
| `scans/textsandstudies_v3.pdf` | *Texts and Studies: Contributions to Biblical and Patristic Literature* Vol. III | 1895 | Contains Bensly (ed. James), *The Fourth Book of Ezra: The Latin Version Edited from the MSS* as issue 2 | PD |
| `latin/bensly_1875_missing_fragment.pdf` | Bensly, *The Missing Fragment of the Latin Translation of the Fourth Book of Ezra* | 1875 | The Amiens Codex fragment — 7:36-140 — restored to the Latin after medieval manuscripts dropped it | PD |

## Directory layout

```
sources/2esdras/
├── README.md                 (this file)
├── scans/                    PDFs of the PD source editions
│   ├── violet_1910_vol1.pdf
│   ├── violet_1910_vol2.pdf
│   └── textsandstudies_v3.pdf
├── latin/
│   ├── bensly_1875_missing_fragment.pdf
│   └── transcribed/          (pending) per-chapter UTF-8 Latin text (`ch01.txt`, `ch02.txt`, ...)
├── syriac/
│   └── transcribed/          (pending) per-chapter UTF-8 Syriac text
├── ethiopic/
│   └── transcribed/          (pending) per-chapter UTF-8 Ge'ez text
└── arabic_armenian/
    └── transcribed/          (pending) Arabic + Armenian + Georgian
```

## Witness coverage

The seven textual witnesses to 2 Esdras, and how they're covered here:

| Witness | Language | Coverage of chs 3–14 (core) | Coverage of chs 1–2 / 15–16 | Source in this repo |
|---|---|---|---|---|
| **Latin (Vulgate tradition)** | Latin | Complete | Complete (only surviving witness for 1-2 and 15-16) | `latin/` + `scans/` |
| **Syriac** | Syriac | Complete | Absent | `syriac/` + Violet parallel |
| **Ethiopic** | Ge'ez | Complete | Absent | `ethiopic/` + Violet parallel |
| **Arabic (two recensions)** | Arabic | Complete (both) | Absent | `arabic_armenian/` + Violet parallel |
| **Armenian** | Armenian | Complete | Absent | `arabic_armenian/` + Violet parallel |
| **Georgian** | Georgian | Complete | Absent | `arabic_armenian/` + Violet parallel |
| **Coptic (Sahidic)** | Coptic | Fragmentary | Absent | Not vendored (optional future) |

## What this means for translation

- **Chs 1–2 and 15–16**: **only the Latin survives.** There are no
  other witnesses to cross-check against. Our translation anchors
  in Bensly 1895 with no multi-witness apparatus; any textual
  uncertainty is honestly disclosed.
- **Chs 3–14 (the core 4 Ezra)**: **six independent witnesses.** Our
  translation anchors in Bensly 1895 Latin, with Syriac/Ethiopic/
  Arabic/Armenian/Georgian readings shown in the per-verse YAML as
  textual apparatus. Disagreements that affect meaning get footnotes.
  In the rare cases where all non-Latin witnesses agree against the
  Latin, the translator can weight that consensus in the rendering
  decision (with rationale documented).

This is a real textual-criticism workflow — much closer to what
scholars do for NT or OT critical editions than the LXX-only
approach of Phase 8.

## Zone 2 (consult, not committed)

Per [`../../REFERENCE_SOURCES.md`](../../REFERENCE_SOURCES.md), these
copyrighted works are consulted during translation but never
reproduced or vendored:

- **Weber-Gryson, *Biblia Sacra Vulgata* 5th ed.** (2007) — modern
  critical Latin edition. Apparatus informs adjudication.
- **Metzger, "The Fourth Book of Ezra" in *The Old Testament
  Pseudepigrapha* vol. 1** (1983) — English translation +
  introduction. Consulted for context; English not tracked.
- **Stone, *Fourth Ezra: A Commentary*** (Hermeneia, 1990) —
  verse-by-verse scholarly commentary.
- **Bidawid, *The Syriac Apocalypse of Ezra*** (Peshitta Institute,
  1973) — modern critical Syriac edition.
- **Longenecker, *2 Esdras*** (Sheffield Guides to Apocrypha) — modern
  accessible commentary.

These are named in `tools/2esdras/multi_witness.py` (to be written)
as the Zone 2 consult registry for the 2 Esdras translator prompt,
analogous to the SIR/TOB/1ES registries in `tools/hebrew_parallels.py`.

## Status

**2026-04-21: source acquisition phase.** PDFs vendored. OCR scaffold
now exists at [`../../tools/2esdras/ocr_pipeline.py`](../../tools/2esdras/ocr_pipeline.py),
with source-specific prompts for Bensly Latin pages and Violet's
parallel-column witness pages.

Current OCR status:

- **Bensly 1895 main-text span (PDF pages 97–178)**: raw OCR complete
  into `raw_ocr/bensly1895/`
- **Bensly 1875 Missing Fragment (PDF pages 65–83)**: raw OCR complete
  into `raw_ocr/bensly1875/`
- **Violet 1910 vol. 1**: initial pilot pages OCR'd into
  `raw_ocr/violet1910-vol1/`

Next cleanup substrate:

- `../../tools/2esdras/extract_bensly_body.py` extracts just the
  `[BODY]` sections from the raw Bensly OCR into
  `latin/intermediate/bensly1895_body_pages/` plus a combined
  `latin/intermediate/bensly1895_body_main_text.txt`
  and, for the missing fragment, into
  `latin/intermediate/bensly1875_body_pages/` plus
  `latin/intermediate/bensly1875_body_main_text.txt`
- `../../tools/2esdras/segment_bensly_chapters.py` then splits the
  1895 combined working text into chapter candidate files under
  `latin/intermediate/bensly1895_chapter_candidates/`
- `../../tools/2esdras/build_missing_fragment_verses.py` builds a
  verse-indexed working file for VII 36–105 at
  `latin/intermediate/bensly1875_fragment_verses/ch07_036_105.txt`
- `../../tools/2esdras/build_ch07_hybrid.py` assembles a single
  chapter-VII hybrid working file at
  `latin/intermediate/bensly_ch07_hybrid_working.txt`
- `../../tools/2esdras/publish_ch07_fragment.py` and
  `../../tools/2esdras/publish_explicit_chapter_candidates.py`
  promote trusted working layers into the canonical loader path under
  `latin/transcribed/`

Current canonical loader coverage:

- `latin/transcribed/ch02.txt` — explicit-marker partial publication
- `latin/transcribed/ch06.txt` — explicit-marker partial publication
- `latin/transcribed/ch07.txt` — verses **36–105** from the Missing
  Fragment
- `latin/transcribed/ch08.txt` — explicit-marker partial publication
- `latin/transcribed/ch09.txt` — explicit-marker partial publication
- `latin/transcribed/ch11.txt` — explicit-marker partial publication
- `latin/transcribed/ch12.txt` — explicit-marker publication
- `latin/transcribed/ch14.txt` — explicit-marker partial publication
- `latin/transcribed/ch16.txt` — explicit-marker partial publication

As of the current automation pass, **all 16 chapters** now exist under
`latin/transcribed/`, but many are intentionally partial rather than
claimed-complete. For an honest per-chapter breakdown, see:

- `latin/transcribed/COVERAGE.md`
- `latin/transcribed/COVERAGE.json`
- `latin/transcribed/QUALITY_CHECK.md`
- `latin/transcribed/QUALITY_CHECK.json`

Follow-up note: the final remaining publication gaps were completed
from the **public-domain digital Latin 4 Esdras text** at
`vulgate.org`, and each chapter header records the exact chapter URL
used for supplementation. OCR-derived / fragment-derived text was
retained wherever already present.

To move back toward fuller **scan-grounded provenance**, see:

- `latin/transcribed/SCAN_GROUNDING_QUEUE.md`
- `latin/transcribed/SCAN_GROUNDING_QUEUE.json`

That queue now tracks which verses still depend on the PD supplement
rather than having been manually re-segmented from the Bensly page
text. Chapters 1, 2, 3, 4, 8, 11, 12, and 14 have now received
manual scan-grounded rescue passes.

Note: in the 1875 run, pages **75–76** are notes/apparatus-only in our
OCR output and therefore yield no `[BODY]` extraction, which is the
expected result rather than a failed parse.

Cleaned per-witness transcription and verse indexing are still
pending. Translation drafting begins after Phase 9 (LXX
deuterocanon) completes — see `2ESDRAS.md` for the full phased plan.

When the Latin cleanup pass begins, the normalized hand-checked output
should land in `latin/transcribed/chNN.txt`. The loader at
[`../../tools/2esdras/latin_bensly.py`](../../tools/2esdras/latin_bensly.py)
already targets that stable format.
