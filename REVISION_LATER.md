# Revision-later — deferred-source integration policy

This document defines how the Cartha Open Bible integrates new
sources that become available AFTER a book has been drafted and
published. It is the operational companion to
[REVISION_METHODOLOGY.md](REVISION_METHODOLOGY.md) (what counts as
a revision, how it is committed) and [REFERENCE_SOURCES.md](REFERENCE_SOURCES.md)
(the three-zone model for source classification).

## Why a dedicated doc

Phase 9 (translation drafting) will ship before several important
original-language sources become accessible under a clean license:

| Source | Affects | Status | Earliest revision trigger |
|---|---|---|---|
| Masada Ben Sira scroll (Mas1h) | Sir 39:27–44:17 (~150 verses) | IAA request pending | IAA grants photographic access |
| Qumran Tobit 4Q196–200 | ~20% of Tobit (Aramaic) | DJD XIX + IAA blocked | License path opens (DJD XIX out of copyright 2061 US; IAA policy change earlier) |
| Cairo Geniza MSS C–F (deeper than Kahana) | Sir portions not in MS A or B | Pipeline in progress | Fresh transcription from PD photos |
| 11QPsa Psalm 151 (Hebrew counterpart) | Psalm 151 | Local consult path now in place; no vendorable source yet | Upgrade to vendored Zone 1 only if a clean-license image/text source becomes available |

We do NOT want the existence of these deferred sources to delay Phase
9. A deferred source reduces maximum achievable quality by a small
amount per affected verse — not enough to block translation, but
enough to warrant a targeted revision when the source arrives.

## Per-verse tracking — what Phase 9 must record

The per-verse YAML schema (`schema/verse.schema.json`) already carries
source provenance. To support revision-later, each drafted verse must
record *which Zone 1 sources were available at drafting time*.
Specifically, the `ai_draft` block will carry:

```yaml
ai_draft:
  model: "gpt-5-4"
  prompt_version: "2026-05-DD"
  zone1_sources_at_draft:
    - "Swete LXX (our OCR) v2026-04-20"
    - "Sefaria Ben Sira Kahana v2026-04-20"     # only for SIR
    - "Sefaria Tobit Neubauer v2026-04-20"      # only for TOB
    - "WLC MT alignment v2026-04-20"            # only for 1ES
  zone2_consults_known:
    - "Fitzmyer DJD XIX"
    - "Beentjes 1997"
    - "Skehan & Di Lella 1987"
    - "Yadin 1965"                              # only for SIR 39:27-44:17
  revision_candidates:
    - reason: "Masada scroll (Yadin 1965) is Zone 2 consult only; if IAA access opens, upgrade to Zone 1 for 39:27-44:17"
      trigger: "iaa_masada_access_granted"
```

`revision_candidates` is the critical field. It declares ahead of
time what events *would* warrant revisiting this verse. When one of
those events fires, `tools/revise_verses.py --trigger <name>` can
automatically find all candidate verses.

## Revision triggers — the catalog

Each trigger below describes a real future event. When it fires, a
targeted revision pass runs.

### `iaa_masada_access_granted`
- **Effect:** Masada Ben Sira scroll images (Mas1h) become Zone 1
- **Affects:** Sir 39:27–44:17 (~150 verses)
- **Revision action:** Re-draft each affected verse with scroll
  photograph added to Zone 1 input. Yadin's reconstruction (previously
  Zone 2) may now be audited against the image.
- **Expected delta:** Small. The Kahana composite + Yadin consult
  already produced a good rendering; Masada direct access mainly
  refines textual-critical footnotes.

### `iaa_qumran_tobit_access_granted`
- **Effect:** 4Q196–200 Aramaic becomes Zone 1
- **Affects:** ~20% of Tobit verses (the specific chapter-verses
  covered by each fragment)
- **Revision action:** Re-draft affected verses with the Aramaic
  scroll text as Zone 1 Hebrew parallel. Footnote annotation shifts
  from "Qumran supports Long Recension" to "Qumran reads X, which we
  render as Y."
- **Expected delta:** Medium. Specific phrasing improvements on
  verses where the Semitic original is now directly accessible.

### `djd_xix_copyright_expires`
- **Effect:** Fitzmyer's transcription and reconstruction becomes
  freely redistributable (2061 US)
- **Affects:** Same ~20% Tobit verses as above
- **Revision action:** Zone 2 → Zone 1 for Fitzmyer's reconstruction
  (not the photographs, which are separately licensed by IAA).
- **Expected delta:** Mainly footnote upgrades.

### `schechter_pipeline_completes`
- **Effect:** Our own fresh transcriptions of Cairo Geniza MSS A/B
  from Schechter 1899 facsimiles (Zone 1) become complete
- **Affects:** Sir 3:6–16:26 (MS A range) and portions covered by MS
  B within Schechter 1899
- **Revision action:** Deepen Zone 1 Hebrew for these verses from
  the Kahana composite to the direct-facsimile transcription.
- **Expected delta:** Small-to-medium. Catches any Kahana composite
  editorial choices that diverge from the actual MS reading.

### `genizah_msc_msd_mse_msf_transcribed`
- **Effect:** PD-licensed photographs of Geniza MSS C, D, E, F
  transcribed via our vision pipeline
- **Affects:** Sir verses where MSS C–F have coverage that MS A/B do
  not (notably parts of Sir 1, 18, 19, 26)
- **Revision action:** Extend Zone 1 Hebrew coverage.
- **Expected delta:** Moderate for affected verses; no change for
  verses where the additional MSS agree with what we already had.

### `page_metadata_corrected`

- **Effect:** The authoritative `pages` list in an adjudication JSON
  gets corrected to include pages the running-head parser missed.
  Most commonly affects books with named sections that break
  running-head parsing (Greek Esther Additions A-F, Tobit B-text /
  S-text recension columns, Psalm of Manasseh appendix).
- **Affects:** any verse whose scan-adjudication was produced without
  the correct page image attached (the adjudicator will typically have
  defaulted to `verdict: first1k` with `confidence: low` and a
  reasoning like "verse not in provided scans").
- **Revision action:** once the page metadata is fixed, re-run
  `tools/rescue_low_conf_focused.py` to target those verses with
  content-based per-verse page identification. Each verse gets a
  focused single-page adjudication.
- **Expected delta:** direct promotion to high confidence; the
  adjudicator was never denying the verse, it simply didn't have
  the image. First observed and resolved during Phase 8 for ADE
  Additions (pages 783-785) and TOB 14:3-15 (pages 863-865).

### `community_correction`
- **Effect:** A GitHub issue or pull request identifies a specific
  verse where our rendering is clearly wrong or where better Zone 1
  evidence exists
- **Affects:** individual verses
- **Revision action:** Per-verse revision with explanation in commit
  message. Standard revision-pass mechanics.

## How a revision pass runs

The mechanics already exist in the `revise:` / `polish:` /
`normalize:` commit-prefix convention (see CLAUDE.md). A revision
pass adds one more step specific to deferred-source integration:

1. **Identify affected verses.** `python3 tools/find_revision_candidates.py
   --trigger iaa_masada_access_granted` reads `revision_candidates`
   across all verse YAML files and emits a worklist.
2. **Update Zone 1 sources.** The new source is added to Zone 1 in
   `REFERENCE_SOURCES.md`; the relevant parser/loader is committed
   under `sources/`; the consult registry in `hebrew_parallels.py`
   is adjusted (source moves from Zone 2 to Zone 1, or from missing
   to Zone 2).
3. **Re-draft.** The translation prompt builder re-runs against only
   the affected verses with the newly-available source in the
   context. The model produces a fresh draft, aware of what the
   prior draft said (to preserve stable renderings) and free to
   revise where the new source warrants.
4. **Reviser pass.** The reviser (Claude Opus per REVISION_METHODOLOGY)
   verifies the three-zone derivative-work check still passes on the
   revised verse.
5. **Commit.** Commit subject follows the convention:
   `revise: integrate <trigger_name> for <book> <verse_range>`.
   Commit body explains the specific textual delta.
6. **Regenerate status.json and republish.** One-shot via
   `scripts/sync_cob.sh`.

## What this does NOT cover

- **Translation-quality revisions** (improving our English rendering
  without a source change) — those are standard `polish:` commits
  under REVISION_METHODOLOGY.md. They are not triggered by this
  document.
- **Corpus-source corrections** (fixing an OCR error in our Swete
  transcription) — those touch `sources/lxx/swete/*` and are not
  verse-level revisions. They precede the translation layer.
- **Canonicity reshuffles** — if a tradition adds or removes a book,
  that is a scope change, not a revision. Requires a DOCTRINE.md
  update.

## Commitment to readers

Every COB verse is traceable back to the Zone 1 sources that produced
it. When a new Zone 1 source becomes available and demonstrably
improves a verse, we say so — in the commit message, in the
per-verse YAML's revision history, and in the reader-facing
provenance page. Revision-later is not "we'll fix it when we get
around to it"; it is a formal integration pipeline that triggers on
specific named events and leaves an auditable record.
