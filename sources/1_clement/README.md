# 1 Clement source materials

Public-domain source editions for the Cartha Open Bible's Greek
extra-canonical pipeline for **1 Clement**.

Scope docs:

- [`../../FIRST_CLEMENT.md`](../../FIRST_CLEMENT.md) — dedicated 1 Clement track
- [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md) —
  shared Group A Greek pipeline

## Textual situation

1 Clement survives in Greek and is one of the most important early
Christian writings outside the New Testament. For COB's source setup,
public-domain Greek printed editions are enough to establish the OCR /
transcription layer.

## Local layout

```text
sources/1_clement/
├── README.md
├── MANIFEST.md
├── scans/                  (gitignored PDFs)
│   ├── lightfoot_1889_1clement.pdf
│   └── funk_1901_patres_apostolici.pdf
└── transcribed/
    └── raw/                future OCR output from the shared Greek tool
```

## Vendored editions

- **Lightfoot (1889)** — major PD Apostolic Fathers source including
  1 Clement
- **Funk (1901)** — *Patres Apostolici* Greek critical source

## OCR tool

Use the shared Group A OCR tool:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/1_clement/scans/lightfoot_1889_1clement.pdf \
  --pages 1-5 \
  --out-dir sources/1_clement/transcribed/raw \
  --book-hint "1 Clement — Lightfoot 1889" \
  --stem-prefix 1c_lightfoot1889
```

## Current OCR / normalization result

The current Funk 1901 pass now covers:

- page **260** = transition into 1 Clement
- pages **261, 263, 265, …, 343** = Greek text
- adjacent even-numbered pages = Latin translation / notes

Page **345** begins **2 Clement** and is excluded from the 1 Clement
normalized layer.

Raw OCR outputs live in `sources/1_clement/transcribed/raw/`.

Helper scaffold:

- [`../../tools/first_clement.py`](../../tools/first_clement.py)

Normalization / draft-ready tooling:

- [`../../tools/first_clement_normalize.py`](../../tools/first_clement_normalize.py)
- [`../../tools/build_first_clement_prompt.py`](../../tools/build_first_clement_prompt.py)

Normalized outputs now exist in `sources/1_clement/transcribed/`.
Current caveat: **chapter 42** is still marked missing in the normalized
Greek layer and needs a targeted recovery pass.
