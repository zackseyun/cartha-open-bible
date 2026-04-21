# Prayer of Manasseh — per-book scope and source plan

Prayer of Manasseh is a penitential prayer traditionally ascribed to
King Manasseh of Judah during his Assyrian captivity. It is the one
book of the traditional Apocrypha not yet drafted in Phase 9.
This document explains why it's a gap, what the clean-licensed
acquisition path is, and what drafting requires.

> **Status: 2026-04-22.** Scope gap identified. Source acquisition
> pending.

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

## Current gap status

- 14 of 14 traditional Apocrypha books from the LXX are drafted.
- Prayer of Manasseh is the one book not yet in the corpus or
  translation, for the reasons explained above.
- Gap is documented here and in `CHANGELOG.md` (Phase 9 entry) for
  transparency. When it ships, `status.json` will flip to 100%.
