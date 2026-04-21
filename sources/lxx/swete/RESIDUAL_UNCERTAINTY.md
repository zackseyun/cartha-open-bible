# Residual uncertainty — medium/low-confidence verses

**Generated:** 2026-04-21 12:26 UTC

After the full Phase 8 pipeline (raw OCR → AI-vision re-parse →
scan-grounded adjudication → rescue passes v1, v2, and focused
manual-page rescue), this document enumerates every verse in the
corpus whose authoritative verdict did NOT reach high confidence.

This is the honesty layer: we disclose exactly where and why our
corpus falls short of certainty, so Phase 9 translators can apply
extra care and readers can audit our residuals. The counts here
match the `confidence` field in
`final_corpus_adjudicated/*.jsonl` verse-for-verse.

## Summary

- **Adjudicated verses:** 2671
- **High confidence:** 2662 (99.7%)
- **Medium confidence:** 4 (0.15%)
- **Low confidence:** 5 (0.19%)

## Per-book tally

| Book | Medium | Low |
|---|---:|---:|
| 1ES | 1 | 0 |
| ADE | 1 | 0 |
| BAR | 1 | 0 |
| SIR | 1 | 5 |

## What medium/low confidence means

- **Medium:** the scan-grounded adjudicator could read the Swete
  page, but the printed letterform is ambiguous (ligature, faded
  character), or candidate sources diverge and the adjudicator
  settled via source-convergence rather than direct scan visibility.
  Residual risk: a different scholar might disambiguate differently.

- **Low:** the adjudicator could not fully verify the reading from
  the page image. Either the page itself is genuinely ambiguous, or
  (in 2 of 5 remaining cases for SIR 3:x) the rescue tool's page-
  identification logic could not locate the correct scan page for
  the specific verse. These verses should receive explicit
  translator attention in Phase 9.

## Per-verse detail

### 1ES

- **1ES 9:35** — *medium*, verdict: `ours`
  > On p. 160 the scan clearly prints the long B-text list for this verse (sons of Βαανεί and of Ἐξωρά), matching our OCR against the image; First1KGreek and Amicarelli instead give the shorter list (Ὀομά …), which does not appear in Swete here. Adjusted minor letter to Ἐξωρά (ω).


### ADE

- **ADE 4:28** — *medium*, verdict: `neither`
  > In the scan v.28 reads ἐπὶ τράπεζαν Ἁμάν; First1K lacks the preposition. The rest matches. Chosen per the scan.


### BAR

- **BAR 1:1** — *medium*, verdict: `neither`
  > On p. 374 at the superscript 1, Swete prints ΚΑΙ ... Ἀσαδίου with smooth breathing and a final comma. This differs from Amicarelli’s rough-breathed Ἁσαδίου and from the others’ formatting/orthography.


### SIR

- **SIR 3:5** — ***LOW***, verdict: `rahlfs_match`
  > On the provided scans (pp. 666–667) the text begins at v. 8; v. 5 is not visible. Based on Swete’s usual text for Sir 3:5, the full clause matches candidate C (A/B are truncated; D conflates with the previous verse).

- **SIR 3:7** — ***LOW***, verdict: `ours`
  > Pages 666–667 begin at v.8; v.7 is not visible on the provided scans. Based on Swete’s usual Sirach text, the verse is printed without ἐν before τοῖς γεννήσασιν. Unable to visually verify on these pages.

- **SIR 33:14** — ***LOW***, verdict: `rahlfs_match`
  > Matched by content to the expected verse; Swete’s text appears to agree with the Rahlfs reading for this line. Unable to clearly locate the superscripted verse number on the provided scans.

- **SIR 33:15** — ***LOW***, verdict: `rahlfs_match`
  > The expected content for modern Sir 33:15 is the well-known line about the works of the Most High being in pairs; this matches Rahlfs. However, on the provided Swete pages (733–734) that section is not visible, so I could not confirm the punctuation or exact wording from the scan.

- **SIR 33:16** — ***LOW***, verdict: `rahlfs_match`
  > The target verse text matches the expected content for Sir 33:16; Swete’s printed form aligns with Rahlfs. I could not clearly locate the verse on the provided scans, which seem to cover a different section.

- **SIR 33:17** — *medium*, verdict: `neither`
  > Located the superscript 17 on page 734; Swete prints a petition beginning Ἐλέησον λαόν, Κύριε, … which differs from the provided candidate text.


## Remediation pathway

These residuals are addressed via the revision-later mechanism
(see [`../../../REVISION_LATER.md`](../../../REVISION_LATER.md)):

1. **Specialist review** — a trained paleographer could likely
   resolve most medium-confidence verses by consulting the
   underlying Codex Vaticanus imagery directly. Out of Phase 8
   scope; tracked as a revision-later candidate.
2. **Community correction** — the `community_correction` trigger
   in REVISION_LATER.md allows readers to file GitHub issues on
   specific verses; adopted corrections become `revise:` commits
   with full provenance.
3. **Tooling improvements** — the low-confidence verses caused by
   page-identification gaps can be eliminated by a future focused
   rescue pass with content-based per-verse page lookup.

Phase 9 translators receive the `confidence` field per verse in
the JSONL output, so medium/low cases get extra care at
translation time without special-casing.
