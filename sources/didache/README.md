# Didache source materials

Public-domain source editions for the Cartha Open Bible's Greek
extra-canonical pipeline for the **Didache** (*Teaching of the Twelve
Apostles*).

Scope docs:

- [`../../DIDACHE.md`](../../DIDACHE.md) — dedicated Didache track
- [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md) —
  shared Group A Greek pipeline

## Textual situation

The Didache survives in Greek and is transmitted most famously in the
Jerusalem manuscript / Codex Hierosolymitanus (H54), discovered in the
19th century. For COB's source-acquisition phase, public-domain Greek
printed editions are sufficient to establish the OCR / transcription
layer.

## Local layout

```text
sources/didache/
├── README.md
├── MANIFEST.md
├── scans/                  (gitignored PDFs)
│   ├── hitchcock_brown_1884.pdf
│   └── schaff_1885_oldest_church_manual.pdf
└── transcribed/
    └── raw/                future OCR output from the shared Greek tool
```

## Vendored editions

- **Hitchcock & Brown (1884)** — Greek text + translation
- **Schaff (1885)** — *The Oldest Church Manual*, with Greek text and
  related discussion / facsimile context

## OCR tool

Use the shared Group A OCR tool:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/didache/scans/hitchcock_brown_1884.pdf \
  --pages 1-5 \
  --out-dir sources/didache/transcribed/raw \
  --book-hint "Didache — Hitchcock & Brown 1884" \
  --stem-prefix didache_hb1884
```

Pilot output already exists for pages 16 and 20 in
`sources/didache/transcribed/raw/`.
