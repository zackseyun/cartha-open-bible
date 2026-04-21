# Greek extra-canonical source materials

This directory is the landing zone for **non-Swete Greek** source
editions used by the shared Group A extra-canonical pipeline.

Scope doc: [`../../GREEK_EXTRA_CANONICAL.md`](../../GREEK_EXTRA_CANONICAL.md)

## What belongs here

These texts are Greek-primary and do **not** need a new Latin,
Ethiopic, or Coptic OCR stack:

- Didache
- 1 Clement
- Shepherd of Hermas
- Testaments of the Twelve Patriarchs

## What does *not* belong here

- **Psalms of Solomon** — already lives inside the Swete corpus at
  `sources/lxx/swete/transcribed/vol3_p0788`–`vol3_p0810`
- deuterocanonical Swete books — remain under `sources/lxx/swete/`

## Planned layout

```text
sources/greek_extra/
├── README.md
├── didache/
│   ├── MANIFEST.md
│   ├── scans/
│   └── transcribed/
├── 1_clement/
│   ├── MANIFEST.md
│   ├── scans/
│   └── transcribed/
├── shepherd_of_hermas/
│   ├── MANIFEST.md
│   ├── scans/
│   └── transcribed/
└── testaments_twelve_patriarchs/
    ├── MANIFEST.md
    ├── scans/
    └── transcribed/
```

The shared OCR tool for these directories is
[`../../tools/greek_extra_pdf_ocr.py`](../../tools/greek_extra_pdf_ocr.py).

## Current state

- **Didache** — local scans already present; README + manifest now in place
- **1 Clement** — local scans already present; README + manifest now in place
- **Shepherd of Hermas** — local scan present; README + manifest now in place, first raw OCR pilot completed
- **Testaments of the Twelve Patriarchs** — source tree now in place; Greek-primary candidate + English reference recorded, first raw Greek OCR pilot completed
