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
