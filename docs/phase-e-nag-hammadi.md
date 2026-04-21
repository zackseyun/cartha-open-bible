# Phase E: Nag Hammadi scaffold

This document tracks the Phase E prep layer for bringing three Nag Hammadi texts into the open-translation workflow used in this repo.

## Texts in scope

- Gospel of Thomas
- Gospel of Truth
- Thunder, Perfect Mind

## What the scaffold adds

1. A primary-witness fetch layer for the Mattison/Zinner ecosystem and related HTML witnesses.
2. OCR job scaffolding for witnesses that still need local PDF/image inputs.
3. Segment indexes so work can happen at the right unit size.
4. Witness bundles and prompt generation for overview and per-segment drafting.

## Layout

```text
tools/coptic/
  common.py
  segment_extractors.py
  fetch_mattison_zinner.py
  segment_nh_texts.py
  ocr_coptic.py
  coptic_witness.py
  build_nh_prompt.py
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
python3 tools/coptic/coptic_witness.py build --all
python3 tools/coptic/build_nh_prompt.py --all
```

## Current Phase E state

- Thomas has a saying-level segment map plus live Greek overlap HTML witnesses (P.Oxy. 654, 1, 655).
- Truth has a 16-section segment map plus an OCR placeholder for the XII.2 overlap witness.
- Thunder has a 123 line-block segment map derived from the Zinner JSON witness.
- Raw witness snapshots are stored under `sources/nag_hammadi/raw/` so prompts and bundles can point at stable source captures.

## Still pending

- Register an OCR input for the Gebhardt-Klein Thomas cross-check witness.
- Register an OCR input for the Gospel of Truth XII.2 overlap witness.
- Wire Thomas prompts into the broader NT parallel lookup once that integration step is ready.
