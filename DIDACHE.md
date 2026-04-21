# Didache — scope and source strategy

This document covers the Cartha Open Bible's dedicated track for the
**Didache** (*Teaching of the Twelve Apostles*), part of the broader
Phase 13 Greek-pipeline reuse group.

It complements:

- [`EXTRA_CANONICAL.md`](EXTRA_CANONICAL.md)
- [`GREEK_EXTRA_CANONICAL.md`](GREEK_EXTRA_CANONICAL.md)
- [`REFERENCE_SOURCES.md`](REFERENCE_SOURCES.md)
- [`sources/didache/README.md`](sources/didache/README.md)

> **Status: source-acquisition + pilot OCR phase.** Public-domain Greek
> source editions are now vendored locally (gitignored + manifest-tracked).
> The Didache reuses the existing Greek OCR / drafting stack; no new
> language pipeline is needed. A first OCR pilot on Hitchcock & Brown
> pages 16 and 20 has already been produced under
> `sources/didache/transcribed/raw/`.

## Why the Didache

1. **It is one of the most important non-canonical early Christian
   texts.** For moral teaching, liturgical practice, church order, and
   catechesis, few extra-canonical works matter more.
2. **It belongs naturally beside the New Testament.** It is especially
   valuable next to Matthew, James, and the Sermon-on-the-Mount moral
   tradition.
3. **It is short and high-leverage.** Sixteen chapters make it one of
   the cheapest historically significant Phase 13 texts.
4. **It reuses the Greek stack cleanly.** No Ethiopic, Latin, Syriac,
   or Coptic source architecture is required to begin.

## Textual situation

- **Language:** Greek
- **Primary witness:** Codex Hierosolymitanus (H54)
- **Scope:** 16 chapters

For COB's first release, the Greek printed source is sufficient to
begin. The Didache does not require the kind of multi-witness recovery
that 2 Esdras, Enoch, or Jubilees require.

## Zone 1 sources

| Edition | Role | Status |
|---|---|---|
| Hitchcock & Brown, *Teaching of the Twelve Apostles* (1884) | Greek base text + translation apparatus | vendored locally |
| Schaff, *The Oldest Church Manual* (1885) | Greek text, translation, facsimiles, discussion | vendored locally |

## Zone 2 consult

- Later Apostolic Fathers critical editions / translations
- Patristic and liturgical commentary where needed

These can be consulted under the normal three-zone policy, but the
first pipeline pass does not depend on them.

## Pipeline fit

The Didache belongs to **Group A** in `EXTRA_CANONICAL.md`:

- Greek text
- public-domain printed editions
- no new OCR backend
- compatible with the same OCR / prompt / audit approach used for other
  Greek-source works

The shared local-PDF OCR tool for this track is
[`tools/greek_extra_pdf_ocr.py`](tools/greek_extra_pdf_ocr.py).

## Immediate next steps

1. OCR the vendored Greek pages from the local PDFs
2. Normalize the chapter structure
3. Build the Didache prompt builder
4. Draft + revise
