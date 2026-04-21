# 1 Clement — scope and source strategy

This document covers the Cartha Open Bible's dedicated track for
**1 Clement**, part of the broader Phase 13 Greek-pipeline reuse group.

It complements:

- [`EXTRA_CANONICAL.md`](EXTRA_CANONICAL.md)
- [`GREEK_EXTRA_CANONICAL.md`](GREEK_EXTRA_CANONICAL.md)
- [`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md)
- [`sources/1_clement/README.md`](sources/1_clement/README.md)

> **Status: source-acquisition phase.** Public-domain Greek source
> editions are now vendored locally (gitignored + manifest-tracked).
> 1 Clement is a Greek-source Phase 13 text and reuses the same family
> of tooling as other Group A works.

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
| Funk, *Patres Apostolici* (1901) | PD Greek critical source | vendored locally |

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

## Immediate next steps

1. OCR the vendored Greek pages from the local PDFs
2. Structure the 65 chapters cleanly
3. Build the 1 Clement prompt builder
4. Draft + revise
