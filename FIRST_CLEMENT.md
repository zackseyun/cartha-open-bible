# 1 Clement — scope and source strategy

This document covers the Cartha Open Bible's dedicated track for
**1 Clement**, part of the broader Phase 13 Greek-pipeline reuse group.

It complements:

- [`EXTRA_CANONICAL.md`](EXTRA_CANONICAL.md)
- [`GREEK_EXTRA_CANONICAL.md`](GREEK_EXTRA_CANONICAL.md)
- [`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md)
- [`sources/1_clement/README.md`](sources/1_clement/README.md)

> **Status: source-acquisition + draft-ready normalized phase.** Public-domain Greek source
> editions are now vendored locally (gitignored + manifest-tracked).
> 1 Clement is a Greek-source Phase 13 text and reuses the same family
> of tooling as other Group A works. An initial OCR pass is now underway
> from **Funk 1901**, and the opening Greek sequence of *1 Clement I*
> has been captured from PDF pages **261, 263, 265, 267, 269, 271,
> 273**. That OCR pass has now been extended through the Greek 1 Clement
> span in Funk and normalized into chapter files. The one OCR gap
> (**chapter 42**, with chapter 43 start also affected) is now filled
> provisionally from a public digital Greek supplement so the book is
> structurally complete and prompt-ready.

## Why 1 Clement

1. **It is one of the earliest and most important post-apostolic
   Christian writings.**
2. **It mattered canonically and liturgically.** Codex Alexandrinus
   transmits it with biblical material, which makes it unusually
   important for canon-formation context.
3. **It belongs beside Hebrews, 1 Peter, and the Pauline church-order
   world.**
4. **It is still a Greek-source text.** That makes it far cheaper to
   set up than Latin-, Ethiopic-, or Coptic-primary works.

## Textual situation

- **Language:** Greek
- **Primary witnesses in tradition:** Codex Alexandrinus + later
  manuscript tradition; printed modern editions collate the key
  witnesses
- **Scope:** 65 chapters in the standard division

COB's first setup pass uses public-domain Greek printed editions as the
Zone 1 source layer.

## Zone 1 sources

| Edition | Role | Status |
|---|---|---|
| Lightfoot, *The Apostolic Fathers* (1889) | major PD Greek/English critical source for 1 Clement | vendored locally |
| Funk, *Patres Apostolici* (1901) | PD Greek critical source | vendored locally; active OCR source |

## Zone 2 consult

- Later Apostolic Fathers editions / commentaries
- modern English translations for interpretive context only

These remain consult-only under the normal COB source policy.

## Pipeline fit

1 Clement belongs to **Group A** in `EXTRA_CANONICAL.md`:

- Greek
- public-domain source editions
- no new script / OCR backend
- clean reuse of the Greek-side transparency and provenance workflow

The shared local-PDF OCR tool for this track is
[`tools/greek_extra_pdf_ocr.py`](tools/greek_extra_pdf_ocr.py).

The helper scaffold for the current raw layer is
[`tools/first_clement.py`](tools/first_clement.py).

Normalization / draft-ready tools:

- [`tools/first_clement_normalize.py`](tools/first_clement_normalize.py)
- [`tools/build_first_clement_prompt.py`](tools/build_first_clement_prompt.py)

## Current source-layout note

The current OCR work shows that **Funk 1901** is the cleanest practical
starting source for 1 Clement. In the PDF:

- page **260** is the transition into 1 Clement
- odd-numbered pages from **261** through **343** carry the Greek text
- adjacent even-numbered pages carry the Latin translation / notes

Page **345** begins **2 Clement** and is excluded from the normalized
1 Clement layer.

## Normalized status

The current normalization pass now produces:

- `sources/1_clement/transcribed/ch01.txt` … `ch65.txt`
- `sources/1_clement/transcribed/chapter_map.json`

The current caveat is now narrower:

- **chapters 42 and 43** are currently supplied by a documented
  supplemental public digital Greek recovery rather than directly from
  the OCRed Funk page stream, pending a future direct-source recovery

## Immediate next steps

1. Begin drafting from the normalized chapter files
2. Revise + audit
3. Optionally replace supplemental chapter-42/43 recovery with direct
   source-layer OCR later
