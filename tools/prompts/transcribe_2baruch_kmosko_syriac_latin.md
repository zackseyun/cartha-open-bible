You are transcribing an early-20th-century scholarly page from Mihály
Kmosko's 1907 2 Baruch edition in *Patrologia Syriaca* 1.2.

These pages are usually **Latin scholarly discussion / apparatus with
inline Syriac quotations or lemma forms**. They are not the same page
family as Ceriani's main Syriac text.

Your task: produce a verbatim Unicode transcription of what is
physically printed on the page. Do not translate. Do not normalize. Do
not silently correct. Preserve Latin in Latin script and Syriac in
Syriac Unicode.

## Output format

Begin the output with exactly one header line:

```
---2BARUCH-KMOSKO-PAGE---
```

Then transcribe top-to-bottom using these markers as needed, each on
its own line:

- `[RUNNING HEAD]`
- `[LATIN MAIN TEXT]`
- `[SYRIAC INLINE]` — only when a block or line is dominantly Syriac
- `[APPARATUS]`
- `[MARGINALIA]`
- `[BLANK]`

End with exactly one footer line:

```
---END-PAGE---
```

## Fidelity rules

- Preserve paragraph structure, section references, and line breaks
  where they carry structure.
- Preserve inline Syriac exactly where it appears inside Latin prose.
- Preserve bold / small-cap headings only as text, not styling.
- Preserve sigla, column references, and numerals exactly as printed.
- If something is illegible, use `[⋯]` with a short note rather than
  guessing.

## Not in scope

- Do not translate or summarize Kmosko's argument.
- Do not normalize Syriac spellings.
- Do not collapse apparatus material into cleaned prose.
- Do not add commentary outside the structured format above.
