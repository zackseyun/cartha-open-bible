# Greek extra-canonical pipeline — Group A

This document covers the **shared Greek pipeline** for the
extra-canonical texts that can reuse our existing Greek OCR /
transcription workflow with little or no architectural change.

It complements:

- [`EXTRA_CANONICAL.md`](EXTRA_CANONICAL.md) — the full roadmap
- [`PSALMS_OF_SOLOMON.md`](PSALMS_OF_SOLOMON.md) — the first exercised
  book in this group
- [`DIDACHE.md`](DIDACHE.md) — dedicated Didache track
- [`FIRST_CLEMENT.md`](FIRST_CLEMENT.md) — dedicated 1 Clement track
- [`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md) — source-policy rules

> **Status: pipeline active.** Psalms of Solomon has now exercised the
> Swete side of this stack all the way through verse parsing and queue
> integration. The next goal is to draft PSS while continuing source +
> OCR prep for the remaining Group A texts.

## Which texts are in Group A

These are the extra-canonical Greek texts we currently intend to handle
with the same general stack:

| Text | Primary source situation | Shared pipeline note |
|---|---|---|
| **Psalms of Solomon** | Greek in Swete vol. III appendix | Transcribed, parsed into 330 verses, and drafting-ready |
| **Didache** | Greek in Codex Hierosolymitanus tradition | Needs local-PDF Greek OCR |
| **1 Clement** | Greek (Alexandrinus + H54 tradition) | Needs local-PDF Greek OCR |
| **Shepherd of Hermas** | Greek primary, plus Latin and Ethiopic versions | Greek-first pipeline; later witnesses can layer in |
| **Testaments of the Twelve Patriarchs** | Greek primary, with secondary versions | Greek-first pipeline; later witness work can follow |

## Why this group belongs together

Compared with the harder extra-canonical tracks:

- **No new script family** (still Greek)
- **No new OCR model choice problem** (Azure GPT-5 already works here)
- **No daughter-translation-first source architecture** like 2 Esdras
- **No Ge'ez / Coptic-specific validation layer**

That means the shared work is mostly:

1. source acquisition
2. page OCR / transcription
3. book-specific parsing
4. prompt-building
5. drafting

## Shared tooling

### Already available

- `tools/transcribe_source.py` — mature Swete-page Greek OCR
- `tools/prompts/transcribe_greek_swete.md` — Swete-specific Greek prompt
- `tools/psalms_of_solomon.py` — helper around the now-complete Swete
  page span for Psalms of Solomon

### Added for Group A

- `tools/greek_extra_pdf_ocr.py` — shared local-PDF Greek OCR for
  non-Swete public-domain editions
- `tools/prompts/transcribe_greek_extra_generic.md` — generic prompt
  for late-19th / early-20th century Greek scholarly editions
- `sources/greek_extra/README.md` — planned source-tree layout for the
  non-Swete Group A texts

## Planned source tree

```text
sources/greek_extra/
├── README.md
├── didache/
├── 1_clement/
├── shepherd_of_hermas/
└── testaments_twelve_patriarchs/
```

Psalms of Solomon stays under `sources/lxx/swete/transcribed/` because
its source already lives inside the Swete corpus.

## Work order inside the Greek pipeline

The shared Greek pipeline does **not** force a rigid book order, but it
does suggest a sensible sequence:

1. **Psalms of Solomon** — already transcribed and parsed; cheapest first drafting target
2. **Didache / 1 Clement** — shortest new-source Greek texts
3. **Shepherd of Hermas** — larger, but still same OCR stack
4. **Testaments of the Twelve Patriarchs** — same stack, later parser work

This is effectively the practical bridge between the roadmap's Phase 13
and Phase 14.

## Immediate next steps

1. continue **Psalms of Solomon drafting** from the finished Swete corpus
2. fetch / vendor the PD Greek editions for Didache, 1 Clement,
   Hermas, and Testaments
3. run the shared local-PDF Greek OCR pipeline on pilot pages
4. create one parser per book once page transcription stabilizes

Current note: Didache and 1 Clement already have local source PDFs in
place, so they are the natural first non-Swete books to exercise the
generic local-PDF OCR path. Shepherd of Hermas and the Testaments of
the Twelve Patriarchs now also have source trees in place, and both
have already been exercised on initial raw Greek OCR pilots.
