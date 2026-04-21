# 2 Baruch (Syriac Apocalypse of Baruch) — scope and source strategy

This document covers the Cartha Open Bible's dedicated sub-phase for
**2 Baruch**, also called the **Syriac Apocalypse of Baruch**. It sits
in the same pipeline family as [2ESDRAS.md](2ESDRAS.md): both are late
Jewish apocalypses transmitted through layered daughter traditions,
and both need a multi-witness workflow rather than the LXX-only
pipeline used for the deuterocanonical books.

It complements [EXTRA_CANONICAL.md](EXTRA_CANONICAL.md) (overall
roadmap) and applies the three-zone source policy in
[REFERENCE_SOURCES.md](REFERENCE_SOURCES.md).

> **Status: scope-design phase.** We are including 2 Baruch in the
> shared apocalypse-pipeline architecture **now**, even though source
> acquisition and transcription work have not started yet. The goal is
> to avoid building a 2 Esdras-only system that later has to be
> refactored.

## Why 2 Baruch belongs in the same family as 2 Esdras

2 Baruch and 2 Esdras are not the same textual problem, but they are
close cousins from an engineering point of view:

- both are **post-70 CE Jewish apocalypses**
- both survive through **translation history**, not through a clean
  original-language base text inside our repo
- both require **primary-witness translation plus secondary-witness
  apparatus**, not reconstructed-source speculation
- both benefit from a **per-verse (or per-section) provenance block**
  listing which witnesses survive and where they diverge

So the right abstraction is not merely "the 2 Esdras pipeline," but a
broader **Semitic apocalypse multi-witness family**, with 2 Esdras and
2 Baruch as the first two members.

## Textual situation

The broad scholarly picture is:

1. **Original composition**: probably Hebrew or Aramaic, shortly after
   the destruction of the Second Temple.
2. **Greek stage**: the surviving Syriac points back to a Greek stage.
3. **Primary surviving witness**: the full work is preserved in
   **Syriac**.
4. **Secondary witnesses**: a few **Greek fragments** and a tiny
   **Latin** remnant survive, but not enough to replace the Syriac as
   the primary base text.

In other words: **2 Baruch is to Syriac what 2 Esdras is to Latin** —
the primary living witness is not the original language, but it is the
base text we can responsibly translate.

## Structure of the book

2 Baruch is usually divided into **87 chapters**:

- **Chs. 1–77** — the apocalypse proper
- **Chs. 78–87** — the epistle / closing exhortation

That division matters for the pipeline because the back section should
be modeled explicitly rather than treated as miscellaneous appendix
matter.

## Source editions (planned)

The following are the natural candidates for the 2 Baruch source stack.
We are documenting them now so later source acquisition follows an
already-audited plan.

### Zone 1 primary / secondary (public domain or otherwise cleanly usable)

- **Ceriani, *Apocalypsis Baruch Syriace*** (1871) — primary Syriac
  base text
- **Kmosko, Patrologia Syriaca edition** (1907) — secondary Syriac /
  Latin-side scholarly witness
- **Charles, *The Apocalypse of Baruch*** (1896) — PD English
  reference only, for numbering / orientation, never as translation base
- **Violet, *Die Apokalypsen des Esra und des Baruch in deutscher
  Gestalt*** (1924, GCS 32) — companion volume in the same family as
  the 2 Esdras material already on our roadmap

### Zone 2 consult (not reproduced)

- modern critical Syriac editions / commentaries
- modern translations in OTP / similar scholarly collections
- specialist studies on the Greek fragments and Syriac textual history

These may inform adjudication, but the same no-derivative-text rule
applies here as everywhere else in COB.

## Translation strategy

Adapted from [METHODOLOGY.md](METHODOLOGY.md) and
[REFERENCE_SOURCES.md](REFERENCE_SOURCES.md):

1. **Syriac is the primary source text.**
2. **Greek / Latin remnants are apparatus, not replacement base
   texts.**
3. The translator **does not reconstruct** a hypothetical Hebrew or
   Greek original.
4. Witness disagreements are exposed in the per-verse / per-section
   YAML with plain-English rationale.
5. Output remains **fully auditable** the same way our 2 Esdras and
   deuterocanonical work is.

## Planned pipeline components

These are intentionally parallel to the 2 Esdras track:

| Component | Status | Purpose |
|---|---|---|
| `sources/2baruch/` | ⏳ pending | Source PDFs / manifests / rehydration notes |
| `tools/2baruch/ocr_pipeline.py` | ⏳ pending | OCR of Syriac / fragment witnesses from local PDFs |
| `tools/2baruch/syriac_primary.py` | ⏳ pending | Chapter/verse loader for cleaned primary Syriac |
| `tools/2baruch/multi_witness.py` | ⏳ pending | Aggregator returning Syriac + Greek/Latin fragment data |
| `tools/2baruch/build_translation_prompt.py` | ⏳ pending | Phase-15 translator prompt assembly |

## Relationship to 2 Esdras work happening now

The current 2 Esdras work is already producing reusable pieces:

- local-PDF OCR pipeline design
- provenance sidecars per OCR page
- chapter-indexed cleaned primary-witness format
- multi-witness data model
- prompt-builder architecture

That means 2 Baruch should be **included in the architecture now**,
even if its own source acquisition starts later.

## Tentative timing

- **Now**: include 2 Baruch in the shared apocalypse-pipeline docs and
  abstractions
- **After 2 Esdras Latin path stabilizes**: vendor 2 Baruch sources and
  scaffold the Syriac-primary loader
- **Drafting phase**: after earlier higher-priority phases complete,
  using the already-proven family tooling

## Why this is worth doing

- 2 Baruch is one of the most important Jewish apocalypses adjacent to
  2 Esdras.
- It fits the same COB value proposition: **transparent, auditable,
  open-license, witness-aware translation**.
- Doing the architectural inclusion now saves rework later.
