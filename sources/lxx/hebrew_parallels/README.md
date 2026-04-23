# Hebrew parallels for LXX deuterocanon

For several of our LXX books, there is Hebrew/Aramaic material that
predates the Greek and must be consulted during translation. This
directory vendors **clean-licensed** Hebrew witnesses and the
mapping tables the translator needs to find them.

**See also:** [`REFERENCE_SOURCES.md`](../../../REFERENCE_SOURCES.md) —
the repo-root operational policy for using reference sources during
translation. This directory holds only **Zone 1** (vendored, safe as
both reference and Vorlage). Zone 2 consulted-reference sources
(Fitzmyer DJD XIX, Beentjes, Skehan/Di Lella, Göttingen) are named
in that policy and are surfaced per-verse by
`tools/hebrew_parallels.py::lookup_with_consult`.

## Contents

| File | Book | Verses | License | Use as |
|---|---|---:|---|---|
| `sefaria_ben_sira.json` | Sirach (SIR) | 1,019 (1,018 w/ Hebrew) | CC0 (Sefaria / Kahana ed.) | Direct Hebrew witness |
| `sefaria_tobit.json` | Tobit (TOB) | 76 (100% Hebrew) | Public Domain (Sefaria / Neubauer 1878) | Translation reference only — NOT a Vorlage |
| `1esdras_mt_alignment.json` | 1 Esdras (1ES) | 15 alignment rows | Our editorial work (CC-BY 4.0) | Maps 1ES verses to WLC Hebrew |

## Psalm 151 Hebrew counterpart

Psalm 151 is a special case. The Greek seven-verse form we draft from is
already in the repo via Swete. The longer Hebrew counterpart survives in
**11QPsᵃ / 11Q5 col. XXVIII**, but the currently accessible image source
(Leon Levy / IAA) is not vendorable under the site's terms.

So Psalm 151 Hebrew is handled as **local Zone 2 consult**, not vendored
Zone 1:

- `tools/fetch_psalm_151_hebrew.py` stages a local-only cache at
  `~/cartha-reference-local/psalm151_hebrew/psalm151_kahana_1937.json`
  using Sefaria's API.
- `tools/psalm151_hebrew.py` maps the Greek 7-verse COB Psalm 151 to the
  longer Hebrew 10-verse form.
- `tools/hebrew_parallels.lookup_with_consult('PS151', 1, v)` now exposes
  the mapped Hebrew as a live Zone 2 consult block for Psalm 151 prompts.

This means the enhancement is now available in the drafting/revision
pipeline without committing restricted images or direct derivative
transcriptions into the repository.

## How it plugs in

`tools/hebrew_parallels.py` wraps all three sources behind a single
`lookup(book_code, chapter, verse)` call. The translation pipeline
calls that function whenever it drafts a verse in SIR, TOB, or 1ES;
the returned dict tells the translator:

- **`direct_hebrew`** (SIR) — the verse has a real Hebrew witness.
  Translate from Hebrew first, consult Greek as secondary.
- **`indirect_hebrew`** (TOB) — Hebrew back-translation exists but
  is 19th-century, not ancient. Use for sanity checks on Semitic
  phrasing only; Greek remains primary.
- **`mt_parallel`** (1ES) — the verse corresponds to a passage in
  the Hebrew MT (WLC). Greek remains primary (1ES is a Greek
  composition), but MT gives authoritative spelling of proper
  names and locks idiom choices.
- **`no_parallel`** (1ES 3:1–5:6) — Three Youths block. No Hebrew.
  Greek-only.
- **`direct_hebrew_missing`** / **`indirect_hebrew_missing`** —
  lookup succeeded but this specific verse has no Hebrew text
  (common in Sirach chapters 17, 22-24, 26-29, 36 where the
  Cairo Geniza is fragmentary). Fall back to Greek.

## Why these specific sources

**Sirach — Sefaria Kahana edition (CC0).** David Kahana's 1913
Wikisource edition is a composite of the Cairo Geniza
manuscripts. It is not as philologically rigorous as Beentjes 1997
or Skehan & Di Lella 1987, but those are copyrighted and cannot
be vendored into a CC-BY-4.0 project. The fuller
manuscript-level material (Schechter 1899, Masada request pending)
lives in `../../../hebrew_sirach/` and will upgrade this dataset
when processed.

**Tobit — Sefaria Neubauer back-translation (PD).** The actual
ancient witnesses are the Qumran Aramaic fragments 4Q196–200,
which the IAA Leon Levy library explicitly blocks from
redistribution (terms checked 2026-04-20). Fitzmyer's DJD XIX
transcription is likewise commercially licensed. Neubauer (1878)
is the best Hebrew path we have access to under a clean license.
Treat as reference, not Vorlage.

**1 Esdras — MT alignment table (editorial, CC-BY 4.0).** 1 Esdras
has no underlying Hebrew of its own — it was composed in Greek
from Hebrew sources that survive in canonical 2 Chr, Ezra, and
Neh. The alignment follows the standard table in NETS and
Talshir's SBL commentary; the Hebrew text itself comes from our
`sources/ot/wlc/` WLC corpus (PD).

## What is NOT in this directory

- **Masada Ben Sira scroll** (Sir 39:27–43:30 + 51:13–30) — IAA-licensed
  photographs, pending a formal permissions request. Yadin's 1965
  editio princeps is consulted locally as Zone 2 via
  `tools/yadin_masada.py` (see below).
- **Qumran Tobit (4Q196-200)** — IAA-licensed, blocked.
- **Scholarly critical editions** (Beentjes, Skehan/Di Lella,
  Hanhart, Fitzmyer) — commercial copyright; cited in footnotes
  where they establish uncontested facts, never reproduced.

These remain referenceable via footnotes under fact-level citation
(*Feist v. Rural*, 1991). If any of them becomes available under
a compatible license later, they can be vendored here.

## Zone 2 live consult — Yadin 1965 Masada scroll

For the 150 verses of Sir 39:27–44:17 and the ~18-verse acrostic at
Sir 51:13–30, `tools/hebrew_parallels.lookup_with_consult` surfaces a
**live Zone 2 entry** carrying the Masada-scroll Hebrew that Yadin
transcribed, plus his column-level scholarly notes, whenever the
local extraction exists at `~/cartha-reference-local/yadin_1965/`.
On clean checkouts (no local reference library) this silently
returns empty — exactly the intended behavior.

The scaffold is in `tools/yadin_masada.py`. Mechanics are documented
in `sources/hebrew_sirach/masada/README.md`. Translator-prompt
integration is documented in `REFERENCE_SOURCES.md`.
