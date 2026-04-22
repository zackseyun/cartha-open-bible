# Phase E: Nag Hammadi scaffold

This document tracks the Phase E prep layer for bringing three Nag Hammadi texts into the open-translation workflow used in this repo.

## Texts in scope

- Gospel of Thomas
- Gospel of Truth
- Thunder, Perfect Mind

## What the scaffold adds

1. A primary-witness fetch layer for the Mattison/Zinner ecosystem and related HTML witnesses.
2. OCR job scaffolding for witnesses that still need local PDF/image inputs.
3. Claremont CCDL facsimile fetch helpers for primary Nag Hammadi codex page staging.
4. Vertex-backed parallel OCR for high-throughput facsimile runs.
5. Segment indexes so work can happen at the right unit size.
6. Witness bundles and prompt generation for overview and per-segment drafting.

## Layout

```text
tools/coptic/
  common.py
  segment_extractors.py
  fetch_mattison_zinner.py
  segment_nh_texts.py
  ocr_coptic.py
  coptic_witness.py
  fetch_claremont_nag_hammadi_images.py
  build_nh_prompt.py
  run_parallel_coptic_ocr.py
  README.md

sources/nag_hammadi/
  catalog.json
  consult_registry.json
  texts/*/manifest.json
  segment_index/*.csv
  raw/
  staging/
  ocr/
  witnesses/
  prompts/
  README.md
```

## Command flow

```bash
python3 tools/coptic/fetch_mattison_zinner.py --all
python3 tools/coptic/segment_nh_texts.py --all
python3 tools/coptic/ocr_coptic.py prepare --all
python3 tools/coptic/fetch_claremont_nag_hammadi_images.py --text gospel_of_truth
python3 tools/coptic/coptic_witness.py build --all
python3 tools/coptic/build_nh_prompt.py --all
```

## Current Phase E state

- Thomas has a saying-level segment map plus live Greek overlap HTML witnesses (P.Oxy. 654, 1, 655).
- Truth has a 16-section segment map, a completed XII.2 overlap OCR witness, and a staged Codex I.3 primary facsimile OCR witness.
- Thunder has a 123 line-block segment map plus a staged Codex VI.2 primary facsimile OCR witness.
- Raw witness snapshots are stored under `sources/nag_hammadi/raw/` so prompts and bundles can point at stable source captures.

## Still pending

- Register an OCR input for the Gebhardt-Klein Thomas cross-check witness.
- Finish adjudication / downstream segmentation against the newly OCRed primary facsimile layers for Truth and Thunder.
- Wire Thomas prompts into the broader NT parallel lookup once that integration step is ready.
