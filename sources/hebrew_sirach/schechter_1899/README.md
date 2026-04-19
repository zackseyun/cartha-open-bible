# Schechter & Taylor (1899) — *The Wisdom of Ben Sira*

**Publication:** Solomon Schechter and Charles Taylor, *The Wisdom of Ben
Sira: Portions of the Book Ecclesiasticus from Hebrew Manuscripts in the
Cairo Genizah Collection Presented to the University of Cambridge by the
Editors*. Cambridge: University Press, 1899.

**Status:** Public domain worldwide. Schechter died 1915, Taylor died 1908.
Publication more than 75 years old in every jurisdiction.

## Why this source matters

Schechter's 1896 discovery of Hebrew Sirach fragments in the Cairo Genizah
was the first physical evidence in a millennium that the original Hebrew
Sirach had survived. The 1899 volume is his and Taylor's published
transcription of the first two manuscripts to emerge (MSS A and B),
with commentary and facsimile plates.

It is our cleanest public-domain path to the Hebrew text of Sirach for
the portions it covers, without depending on any of the 20th-century
copyrighted scholarly editions (Lévi, Ben-Ḥayyim, Beentjes).

## Files in this directory

- `schechter_1899.pdf` — complete book, vendored directly (~8 MB)
- `schechter_1899_djvu.txt` — Archive.org's automated OCR. Captures the
  English commentary reasonably but loses almost all Hebrew (OCR is
  English-tuned and skips Hebrew script). Retained as a reference
  search index for the English portions.
- `schechter_1899_page_numbers.json` — Archive.org's scan→print page
  mapping.

## Coverage (what the book actually transcribes)

Schechter and Taylor present Hebrew transcriptions of:

- **MS A** — Sirach 3:6 – 16:26 (roughly; with some lacunae)
- **MS B** — Sirach 30:11 – 33:3, 35:11 – 38:27, 39:15 – 49:11
  (with later publications extending MS B coverage)

Not in this 1899 volume (added by later discoveries):
- MS C (discovered later): various passages
- MS D (Paris BnF): 36:29 – 38:1a
- MS E (JTS): 32:16 – 34:1 + extension
- MS F (Cambridge, discovered 1980s): 31:24 – 33:8

For those, we will use later public-domain publications (Lévi 1901,
Peters 1902, Marcus 1931, etc. — all now PD by year of publication)
or fresh AI-vision transcription from public-domain Cambridge/Oxford/JTS
photographs. See `../genizah_photos/` for that workflow.

## Working-text extraction

The printed Hebrew in this 1899 volume is clear typeset Hebrew (not
manuscript reproduction). Extracting it as UTF-8 Hebrew is tractable
via AI vision transcription — the typography is 19th-century but the
letters are standard print forms.

Per-verse extracted Hebrew will be committed to `transcribed/`
(created as pages are processed), alongside provenance metadata:
- source PDF page number
- SHA-256 of the page image
- transcribing model + timestamp
- verse range transcribed
- known issues (e.g., "MS A has lacuna at 7:26b")

## Source provenance

Original file: https://archive.org/details/wisdomofbensirap00scheuoft
SHA-256 of `schechter_1899.pdf`:
`d3e8cf95077d7b40c382a68677f898da8d2f9c5a2b3be1b0af821080e11a8328`

## Required attribution

> Hebrew text of Sirach extracted from Solomon Schechter and Charles Taylor,
> *The Wisdom of Ben Sira* (Cambridge University Press, 1899), public
> domain. Transcription to UTF-8 by Cartha Open Bible, CC-BY 4.0.
