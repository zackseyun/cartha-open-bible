# Schaff 1885 — Didache secondary witness extracts

This directory holds chapter-mapped **secondary-source** text extracts
for the Didache revision pass, derived from the public-domain Internet
Archive DjVu XML for:

- Philip Schaff, *The Oldest Church Manual Called The Teaching of the
  Twelve Apostles* (1885)

These files are **not** the primary translation source. The primary
source remains the normalized Hitchcock & Brown 1884 Greek layer in
`sources/didache/transcribed/`.

Instead, this directory exists to support:

- chapter-level cross-checking
- revision / audit work
- locating places where the first OCR/source layer may need a second
  look

## Files

- `chapter_map.json` — Didache chapter → Internet Archive DjVu page map
- `chapters/ch01.txt` … `ch16.txt` — extracted Schaff chapter witness
  text (mixed Greek + translation/commentary context from the DjVu XML)

## Provenance

- Internet Archive item: `oldestchurchman00schagoog`
- Extracted by `tools/didache_secondary.py`

Because the Schaff source includes translation and notes in addition to
the Greek, these chapter files are best used as **revision witnesses**
rather than as a primary text layer.
