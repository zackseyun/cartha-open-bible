You are transcribing a page from Bruno Violet's *Die Apokalypsen des
Esra und des Baruch in deutscher Gestalt* (1924, GCS 32), the 2 Baruch
companion volume in the same broader apocalypse family as the 2 Esdras
materials.

Important: this is **not** the 1910-style multi-witness parallel-column
page family. The accessible 1924 volume is a **German-form scholarly
book** with headings, running text, footnotes, and occasional Greek /
Hebrew / Syriac citations.

Your task: produce a verbatim Unicode transcription of what is
physically printed on the page. Do not translate. Do not normalize. Do
not silently correct. Preserve every script in its own native Unicode
characters.

## Output format

Begin the output with exactly one header line:

```
---2BARUCH-VIOLET1924-PAGE---
```

Then transcribe top-to-bottom using these markers as needed, each on
its own line:

- `[RUNNING HEAD]`
- `[HEADING]`
- `[GERMAN MAIN TEXT]`
- `[APPARATUS]`
- `[QUOTED SOURCE TEXT]`
- `[MARGINALIA]`
- `[BLANK]`

End with exactly one footer line:

```
---END-PAGE---
```

## Fidelity rules

- Preserve German exactly as printed, including old spelling or
  editorial punctuation.
- Preserve Greek, Hebrew, Syriac, or other cited source words in their
  own scripts.
- Preserve headings such as `Visio`, `Brief`, and numbered section
  labels exactly as printed.
- Preserve footnote markers, apparatus sigla, and page / line numbers.
- If a character or word is illegible, use `[⋯]` with a short note. Do
  not guess.

## Not in scope

- Do not translate German into English.
- Do not reconstruct an underlying source text.
- Do not turn the page into a cleaned summary.
- Do not add commentary outside the structured format above.
