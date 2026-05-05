# Testaments of the Twelve Patriarchs source materials

Public-domain source editions for the People's Open Bible's Greek
extra-canonical pipeline for the **Testaments of the Twelve Patriarchs**.

Shared scope doc: [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md)

## Textual situation

The Testaments survive primarily in **Greek**, with important secondary
versions in Armenian, Slavonic, and other traditions. For the first POB
pass, the goal is a Greek-primary workflow.

## Current source state

We currently have:

- a **continuous Greek critical edition** suitable for actual drafting work:
  `scans/charles_1908_greek_versions.pdf`
- a **Sinker appendix / collation volume**:
  `scans/sinker_1879_testamenta_xii_patriarcharum.pdf`
- an **English reference translation**:
  `scans/charles_1908_testaments.pdf`

Important correction: **Sinker 1879 is not the continuous Greek base
text.** It is an appendix volume containing collations and
bibliographical notes. Its OCR is still useful for apparatus work, but
it should not be treated as the primary drafting witness.

The actual Greek drafting witness now present locally is Charles's
Greek edition (`charles_1908_greek_versions.pdf`). A first real pilot
OCR for **Reuben** now exists from that source under
`transcribed/raw/t12p_charles1908gk_p0066.txt` through
`..._p0079.txt`, and a first normalized Reuben pilot has been written
under `transcribed/normalized/reuben/`.

## Local layout

```text
sources/testaments_twelve_patriarchs/
├── README.md
├── MANIFEST.md
├── scans/          local PDFs (gitignored)
└── transcribed/    future OCR / cleaned UTF-8 output
```

## OCR tool

Use the shared Group A OCR tool against the **Charles Greek source**
for actual drafting pilots:

```bash
python3 tools/greek_extra_pdf_ocr.py \
  --pdf sources/testaments_twelve_patriarchs/scans/charles_1908_greek_versions.pdf \
  --pages 66-79 \
  --out-dir sources/testaments_twelve_patriarchs/transcribed/raw \
  --book-hint "Testaments of the Twelve Patriarchs — Charles 1908 Greek Versions" \
  --stem-prefix t12p_charles1908gk
```

The old Sinker OCR command remains useful only for appendix / collation
support work.
