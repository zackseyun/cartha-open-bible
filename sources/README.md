# Source Texts

All source texts used by the Cartha Translation are vendored in this
directory with their original licenses preserved. No source text is
modified — any necessary normalization happens in downstream processing
under `tools/`.

## Vendored sources

### SBLGNT — Greek New Testament + morphological parsing
- **Directory:** `nt/sblgnt/`
- **Source repo:** https://github.com/morphgnt/sblgnt (MorphGNT SBLGNT edition)
- **Editor (text):** Michael W. Holmes
- **Editor (morphology):** James K. Tauber
- **Publisher:** Society of Biblical Literature / Logos Bible Software
- **Date:** 2010 (text), ongoing (morphology)
- **License — Greek text:** SBLGNT End User License Agreement
  (http://sblgnt.com/license/). Permits free personal and commercial use,
  quotation up to 1,000 verses per work with attribution, translation into
  other languages, and distribution in electronic products subject to
  attribution requirements.
- **License — morphological parsing:** Creative Commons Attribution-ShareAlike
  3.0 (CC-BY-SA 3.0). See `nt/sblgnt/LICENSE.md` for full details.
- **Required attribution:**
  > Scripture quotations marked SBLGNT are from the SBL Greek New Testament.
  > Copyright © 2010 Society of Biblical Literature and Logos Bible Software.

### Westminster Leningrad Codex (WLC) — via Open Scriptures Hebrew Bible
- **Directory:** `ot/wlc/`
- **Source repo:** https://github.com/openscriptures/morphhb (Open Scriptures
  Hebrew Bible — OSHB)
- **Maintainer:** Open Scriptures
- **Underlying text:** The Westminster Leningrad Codex, a transcription of
  the Leningrad Codex B19A (1008 AD), the oldest complete Hebrew Bible
  manuscript. The underlying WLC text is in the public domain.
- **License — this distribution:** Creative Commons Attribution 4.0
  International (CC-BY 4.0). See `ot/wlc/LICENSE.md`.
- **Required attribution:**
  > Original work of the Open Scriptures Hebrew Bible available at
  > https://github.com/openscriptures/morphhb

### unfoldingWord Hebrew Bible (UHB)
- **Directory:** `ot/uwhb/`
- **Source repo:** https://git.door43.org/unfoldingWord/hbo_uhb
- **Maintainer:** unfoldingWord
- **License:** Creative Commons Attribution-ShareAlike 4.0 International
  (CC-BY-SA 4.0). See `ot/uwhb/LICENSE.md`.
- **Underlying text:** Based on the Open Scriptures Hebrew Bible, with
  additional morphological tagging.
- **Trademark note:** "unfoldingWord" is a registered trademark of
  unfoldingWord. Redistribution of the UHB in modified form requires
  removing the trademark.
- **Required attribution:**
  > The original work by unfoldingWord is available from
  > https://www.unfoldingword.org/uhb

### Rahlfs Septuagint (LXX) — not yet vendored
- **Directory:** `lxx/rahlfs/`
- **Status:** Placeholder. See `lxx/rahlfs/README.md`.

## How sources are used

The Cartha Translation translates from:
- **NT:** SBLGNT primary (using morphology only as reference, not as
  translated output).
- **OT:** WLC primary (the longer, traditional transcription). UHB
  consulted for morphological parsing and where OSHB updates have been
  applied by unfoldingWord.
- **Cross-reference:** Rahlfs LXX (once vendored) where NT authors quote
  the Greek OT.

Each verse YAML in `translation/` records which source(s) it drew from
via the `edition` enum in `source` (see `schema/verse.schema.json`).

## License scope — important note

The Cartha Translation's output (the English translation) is released
under **CC-BY 4.0** (see root `LICENSE`).

**Source texts vendored in this directory retain their own licenses and
are not relicensed by our repository.** Anyone reusing content from this
directory must comply with the individual source's license:

| Source | License | Reuse constraint |
|---|---|---|
| SBLGNT text | SBLGNT EULA | Attribution + quotation limits |
| SBLGNT morphology | CC-BY-SA 3.0 | Share-alike propagates on derivatives |
| WLC (via OSHB) | CC-BY 4.0 | Attribution |
| UHB | CC-BY-SA 4.0 | Attribution + share-alike on derivatives + trademark restrictions |

The Cartha Translation's English output is a new creative work and is
licensed independently (CC-BY 4.0). The share-alike clauses on the morphology
and UHB do not propagate to our translation output, which is not a derivative
of those works in the share-alike sense.

That said — if you are building on the Cartha Translation AND incorporating
any of the vendored source data, you must comply with the source license
for that data separately.

## Vendoring procedure

Source texts are vendored (copied in) rather than referenced as git
submodules. Rationale:
- Full auditability — anyone cloning the repo has everything they need
  to verify the translation without separate network fetches.
- Stability — upstream repos can disappear or change.
- Reproducibility — `tools/verify.py` depends on exact byte-level source
  text.

To update a source to a newer version, the update is itself a git commit
with a clear message documenting what changed and why.
