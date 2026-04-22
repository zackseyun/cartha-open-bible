# Prayer of Manasseh — per-book scope and source plan

Prayer of Manasseh is a penitential prayer traditionally ascribed to
King Manasseh of Judah during his Assyrian captivity. It was the one
book of the traditional Apocrypha that could not ride on the Phase 8
Swete corpus (Swete 1909 is diplomatic Vaticanus, which lacks the
text). This document records the source situation, the acquisition
path we took, and what remains.

> **Status: 2026-04-22 — drafted.** All 15 verses source-built +
> drafted. Corpus at `sources/lxx/prayer_of_manasseh/corpus/MAN.jsonl`
> (and mirrored into `sources/lxx/swete/final_corpus_adjudicated/MAN.jsonl`
> so the existing LXX drafter can pick it up). English per-verse YAMLs
> at `translation/deuterocanon/prayer_of_manasseh/001/*.yaml`.

## Why it's not in Phase 8 / Phase 9

Our Phase 8 corpus is our own OCR of **Swete's diplomatic edition
of Codex Vaticanus**. Prayer of Manasseh is not in Codex Vaticanus,
so Swete does not print it in his main text. The
`tools/lxx_swete.py` book registry carries it as `MAN: (0, 0, 0,
"Prayer of Manasseh", "prayer_of_manasseh")` — a declared book with
no assigned page range, precisely because there is no Swete scan to
OCR.

## Textual situation

- **Original**: likely composed in Greek (possibly translated from a
  lost Hebrew or Aramaic original), ~2nd c. BC to ~1st c. AD.
- **Length**: 15 verses, ~292 Greek words (per Rahlfs versification).
- **Manuscript witnesses**:
  - **Codex Alexandrinus** (A, 5th c.) — prints it as the 8th Ode in
    the Odes appendix to the Psalter.
  - **Apostolic Constitutions** (book 2, ch. 22, 4th c.) — quotes
    the full text as a liturgical prayer.
  - **Later LXX manuscripts** and Vulgate appendices.
- **Modern critical editions**:
  - Rahlfs-Hanhart 2006 prints it as Ode 12 (their numbering).
    **Zone 2 — consult only, not reproducible.**
  - Göttingen has not published a critical Odes volume yet.

## Canonicity

| Tradition | Status |
|---|---|
| Eastern Orthodox | Canonical (as Ode 8 in the Psalter) |
| Roman Catholic | Vulgate appendix (not canonical) |
| Protestant (historic) | KJV 1611 Apocrypha |
| Ethiopian Orthodox | Canonical |

## Clean-licensed acquisition path

Since Codex Vaticanus lacks the text, our Swete pipeline does not
apply. Three PD candidate sources:

### Option A — Baber 1816, Codex Alexandrinus facsimile (preferred)

- **Full title**: Henry H. Baber, *Vetus Testamentum ex Versione LXX
  Interpretum secundum exemplar Vaticanum Romæ editum*, with
  Codex Alexandrinus variants (1816-1828, 4 volumes).
- Baber 1816 is the PD editio princeps of Codex Alexandrinus for
  this material.
- Prayer of Manasseh appears in the Odes appendix volume.
- Archive.org identifier: TBD (search `baber alexandrinus 1816`).
- Advantage: direct transcription from the primary 5th-century
  manuscript, which is the textual anchor.

### Option B — Fabricius 1722-23, Codex Pseudepigraphus VT

- **Full title**: Johann Albert Fabricius, *Codex Pseudepigraphus
  Veteris Testamenti* (1722, expanded 1723).
- Prints the Greek text of Prayer of Manasseh with Latin translation
  and textual notes.
- Archive.org: search `fabricius codex pseudepigraphus`.
- Advantage: well-established 18th-century critical edition.

### Option C — Charles 1913, APOT Vol. 1 (fallback)

- **Full title**: R. H. Charles (ed.), *The Apocrypha and
  Pseudepigrapha of the Old Testament in English*, Vol. 1 (1913).
- Contains the Greek text + English translation + introduction.
- Pre-1929 US publication → PD in the US.
- Archive.org identifier: `apocryphapseudep01charuoft` or similar.
- Advantage: scholarly critical presentation with apparatus; the
  English is also usable as a Zone 1 reference (though we would
  produce our own fresh English per COB doctrine).

## Recommended execution plan

When a session picks this up:

1. **Download the PD source PDF** (Baber 1816 preferred; Fabricius
   1722 or Charles 1913 APOT as fallback).
2. **Vendor it under `sources/lxx/prayer_of_manasseh/scans/` with a
   MANIFEST.md** carrying SHA-256 hashes and archive.org identifier.
3. **OCR the Prayer of Manasseh pages** using
   `tools/greek_extra_pdf_ocr.py` with Gemini 3.1 Pro backend
   (matches our other Group A work).
4. **Build a `MAN.jsonl` corpus file** at
   `sources/lxx/prayer_of_manasseh/corpus/MAN.jsonl` with the 15
   verses, sourced from our fresh OCR.
5. **Multi-source adjudication**: compare our OCR against Rahlfs
   Ode 12 (Zone 2 consult) for textual verification.
6. **Draft** using the existing LXX translator prompt path with
   book-code `MAN`.
7. **Ship** as part of the next Phase 9 tagged release.

## Estimated effort

- Source acquisition: 30-60 min (one PDF, one OCR batch on ~2-3 pages).
- Corpus assembly: 30 min.
- Adjudication: 15-30 min (only 15 verses).
- Drafting: 30 min (one prompt, 15 verses).
- Review pass: 30 min.

**Total: 2-3 hours of focused work.** Not a blocker for anything
time-sensitive; can be scheduled into any Phase 9 tail session.

## Execution record

1. **Source downloaded**: Charles 1913 APOT Vol 1 from archive.org
   identifier `theapocryphaandp01unknuoft`. 83 MB. SHA-256 tracked
   in `sources/lxx/prayer_of_manasseh/MANIFEST.md`. PDF itself is
   gitignored (matches the Swete precedent).
2. **OCR**: `tools/greek_extra_pdf_ocr.py` with Gemini 3.1 Pro
   preview on pages 636-640 (Prayer of Manasseh main text + apparatus
   + footnotes). 5 pages, 0 failures, ~1,480 Greek chars across
   apparatus + footnote lemmata. Outputs in
   `sources/lxx/prayer_of_manasseh/transcribed/raw/`.
3. **Greek reconstruction**: `/tmp/reconstruct_prayer_of_manasseh.py`
   passed the OCR to Gemini 3.1 Pro with an explicit scholarly prompt:
   "assemble the continuous Greek text verse-by-verse (1-15) as
   witnessed by Codex Alexandrinus (A) per Charles's apparatus." The
   Greek text itself is PD by age; Charles's apparatus lemmata are
   PD by 1913. Output: `sources/lxx/prayer_of_manasseh/corpus/MAN.jsonl`
   — 15 verses, 292 Greek words.
4. **Verification**: verse-by-verse word-overlap cross-check against
   Rahlfs-Hanhart Ode 12 (Zone 2 consult only, NC-licensed, not
   copied) showed 62-92% per verse, with mismatches traceable to
   manuscript-family verse-division conventions and minor Codex
   Alexandrinus vs eclectic orthographic variants.
5. **Hand correction**: `παντοκράτορ` → `παντοκράτωρ` in v1 (OCR
   vowel-length artifact).
6. **Honest disclosure**: the `reconstruction_note` field on v1
   records that v8, v9, and first half of v10 were rebuilt from
   standard LXX form because the Charles OCR English for those pages
   was partial — not hidden; flagged in the data.
7. **Drafter wire-up**: MAN.jsonl mirrored into
   `sources/lxx/swete/final_corpus_adjudicated/MAN.jsonl` so the
   existing `lxx_swete.iter_source_verses("MAN")` loader picks it up
   with no special casing. `tools/draft.py` patched so MAN's
   `source.edition` is `charles-1913-apot-vol1` (not the default
   `lxx-swete-1909`, which would be inaccurate).
8. **Drafted**: all 15 verses drafted via `tools/draft.py` with
   GPT-5.4 (azure-openai backend, gpt-5-4-deployment). English
   per-verse YAMLs live at
   `translation/deuterocanon/prayer_of_manasseh/001/001-015.yaml`.
   Each carries standard COB fields: translation text, per-word
   lexical decisions + rationale, footnotes for alternatives,
   AI-draft provenance, source-edition provenance.

## What shipped

| Layer | Location | State |
|---|---|---|
| Source PDF | `sources/lxx/prayer_of_manasseh/scans/` (gitignored) | Charles 1913 APOT Vol 1, PD |
| OCR output | `sources/lxx/prayer_of_manasseh/transcribed/raw/` | pp. 636-640, Gemini 3.1 Pro |
| Greek corpus | `sources/lxx/prayer_of_manasseh/corpus/MAN.jsonl` | 15 verses, 292 Greek words |
| LXX mirror | `sources/lxx/swete/final_corpus_adjudicated/MAN.jsonl` | copy so the LXX loader sees MAN |
| English drafts | `translation/deuterocanon/prayer_of_manasseh/001/*.yaml` | all 15 verses, first-pass |

## Verification pass — 2026-04-22

The scan-grounded adjudication polish pass flagged in the original
caveat has been completed. Direct visual verification against Charles
1913 APOT Vol 1 pp. 636-640 yielded:

- **Verse boundaries**: every MAN verse boundary in our reconstruction
  matches Charles's editorial numbering exactly (1 through 15).
- **v7 "insertion" correctly omitted**: the long English clause
  "Thou, O Lord, according to thy great goodness hast promised
  repentance and forgiveness..." is marked with asterisks in Charles
  and his apparatus reads "Const. Apost., Syr., Lat., Moz.: om A T" —
  i.e., absent from Codex Alexandrinus. Our reconstruction correctly
  omits this insertion, following A.
- **v8 verified against Codex A**: our reading `ἐμοὶ τῷ ἁμαρτωλῷ`
  (no preposition) matches Codex Alexandrinus, per Charles's
  apparatus; Rahlfs prints `ἐπ᾽ ἐμοὶ τῷ ἁμαρτωλῷ` (with preposition)
  following a different witness tradition. We follow A.
- **v9 orthographic correction applied**: our initial reconstruction
  had passive `ἐπληθύνθησαν` (which matched Charles's English "were
  multiplied" but not his Greek apparatus). Charles's apparatus for
  Codex A reads `κυριε επληθυναν αι ανομιαι μου` — active
  `ἐπλήθυναν`. We corrected this on 2026-04-22 and re-drafted v9.
- **v10 boundary confirmed**: our split at `...προσοχθίσματα. / καὶ
  νῦν κλίνω γόνυ καρδίας...` between v10 and v11 matches Charles's
  printed marginalia exactly.

All 15 verses are now either directly verified against Charles's
apparatus or flagged with a specific apparatus citation. The
`reconstruction_note` on MAN 1:1 records the current state.

## Residual (low priority)

- **Systematic revision-methodology pass** per
  `REVISION_METHODOLOGY.md` has not yet run for MAN, same as for
  the other Apocrypha books. First-pass quality across the whole
  section.
- **Consistency lint** across MAN vs the rest of the deuterocanon
  (e.g., uniform rendering of κύριος, Ἀβραάμ, etc.) is pending the
  Apocrypha-wide lint cycle.

## Current gap status

- **All 14 traditional Apocrypha books are now drafted.** Prayer of
  Manasseh closes the gap. See `CHANGELOG.md` for the Phase 9 tail
  entry.
