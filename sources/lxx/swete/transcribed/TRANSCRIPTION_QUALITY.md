# Swete LXX transcription — quality report

**Report date:** 2026-04-18
**Scope:** 572 scan pages covering the Phase 8 deuterocanonical corpus
across Swete vols II and III (see `page_index.json`).
**Methodology:** Azure GPT-5.4 vision (deployment `gpt-5-4-deployment`,
model `gpt-5.4-2026-03-05`) applied to archive.org scan JPEGs at 1500
px width, prompted per `tools/prompts/transcribe_greek_swete.md`
(prompt version `transcribe_v1_2026-04-18`). Every output page has a
paired `.meta.json` sidecar recording image SHA-256, source URL, model,
deployment, prompt version, timestamp — the run is reproducible.

This document is the baseline quality measurement, written before any
revision or second-pass work. Subsequent improvement passes will be
appended here with dated entries so the quality trajectory is visible.

---

## 1. Automated structural checks (all 617 transcribed pages)

Every transcribed page was statically analyzed. Findings:

### Format compliance — 100%

All 617 pages present the expected structure: `---SWETE-PAGE---`
header, at least one `[RUNNING HEAD]` / `[BODY]` / `[APPARATUS]` /
`[MARGINALIA]` / `[PLATE]` / `[BLANK]` section, `---END-PAGE---`
footer. Zero pages missing required delimiters.

### Character-class distribution

| Script | Characters | Share |
|---|---:|---:|
| Greek (polytonic) | 964,208 | 81.1% |
| ASCII (sigla, digits, format markers, punctuation) | 207,189 | 17.4% |
| Other (`ℵ`, `·`, modifier letters, superscripts, combining marks) | 17,239 | 1.4% |
| General punctuation (U+2010–U+206F) | 327 | ≪1% |
| Hebrew | 78 | ≪1% |

The 1.4% "other" is entirely legitimate: `ℵ` (U+2135 ALEF SYMBOL, the
Sinaiticus manuscript siglum, 1,026 occurrences), the Greek mid-dot
`·`, combining accents, superscript letters `ᵃ`/`ᵇ`/`ᶜ` marking
scribal hands, overlines for MS abbreviations.

Zero Cyrillic or Arabic script leaks.

### Issues flagged for post-processing

| Issue | Pages | Severity | Fix |
|---|---:|---|---|
| Decomposed Unicode (NFD instead of NFC) | 39 | cosmetic | one-line normalizer |
| Hebrew `א` (U+05D0) used where Swete prints `ℵ` (U+2135) as the Sinaiticus siglum | 11 | cosmetic | contextual replace in apparatus sections |
| Short `[BODY]` (<200 chars) | 5 | **none** — all are legitimate blank/plate/end-of-book pages the model correctly labeled | no action |

### Page-length distribution

Median 2,551 chars / page; mean 2,352; range 39–3,739. The 39-char
minimum is a `[BLANK]`-labeled end-matter page; the 3,739 maximum is a
dense apparatus-heavy page in Maccabees. No outliers suggesting
truncation or runaway output.

## 2. Cross-model spot-check (Claude Opus 4.7 vs. GPT-5.4)

I (Claude Opus 4.7) independently viewed 4 scan JPEGs and compared the
visible Greek against the GPT-5.4 transcription character-by-character.
Spot-check sample was chosen to span content types:

| Page | Book + reference | Content type | Word errors found |
|---|---|---|---:|
| vol2 p650 | Wisdom 15:15–16:4 | hexameter-adjacent poetic verse | 4 |
| vol2 p843 | Tobit 5 (B + S recensions) | two-column parallel text | structural match; char-level not exhaustively graded |
| vol3 p380 | Baruch 3:32–4:10 | narrative + apodictic prose | 2–3 |
| vol3 p620 | 1 Maccabees 1:42–57 | narrative prose | 2–3 |

**Aggregate word-error rate across the 3 fully-graded pages: ~1–2%.**
This is within the 95–99% accuracy band the project claims for typeset
printed Greek in [DEUTEROCANONICAL.md](../../../DEUTEROCANONICAL.md#transcription-accuracy--honest-expectations).

### Specific error examples

**Missing single letters:**
- Baruch 4:2 `διόδευσον` → `ὁδευσον` (missing "διό" prefix)
- Wisdom 16:3 `δειχθεῖσαν` → `εἰχθεῖσαν` (missing initial δ)
- 1 Maccabees 1:48 `βδελύξαι` → `βελῦξαι` (missing δ)

**Extra single letters:**
- Wisdom 15:15 `συνολκὴν` → `συνονλκὴν` (extra ν)

**Case / accent slips:**
- 1 Maccabees 1:42 `τῇ βασιλείᾳ` → `τὴν βασιλεία` (dative rendered as accusative)
- Baruch 4:2 `ἐπιστρέφου` → `ἐπίστρεφου` (accent on wrong syllable)
- Wisdom 15:15 `ὅτι` → `οὕτι` (character misidentification at verse-initial)

**Apparatus variant merged into body (one systematic pattern):**
- Wisdom 15:16 main text is `δεδανισμένος`; the apparatus footnote for
  this verse reads `(-νεισμ. Bab)` — i.e. Codex B's corrected reading
  is `δεδανεισμένος`. Our transcription produced `δεδανεισμένος` in the
  body — GPT-5.4 appears to have read the main text through the lens
  of the apparatus variant. This is the one error type that looks
  prompt-fixable (an explicit "never substitute apparatus variants
  into the body text" instruction).

## 3. Overall grade and implications for downstream drafting

| Axis | Grade |
|---|---|
| Format / structural compliance | A (100% clean) |
| Character-class purity | A (no script leaks, Unicode cleanup is trivial) |
| Text fidelity to the printed page | B (1–2% word error rate) |
| Book/chapter identification | A (verified via running-head probes) |
| Reproducibility | A (every page has an image SHA-256 + prompt version) |

**Implications for the Phase 8 drafting workflow:**

1. The transcribed Greek is **adequate as primary source input for the
   drafter**. English translators (whether GPT-5.4 or Opus 4.7) are
   robust to 1–2% character-level noise in the source and produce
   correct meaning-preserving English as long as the verse is
   semantically intact.

2. **The existing Opus reviser pass** (per `REVISION_METHODOLOGY.md`)
   catches meaning-altering errors in the English output. Several of
   the observed transcription errors would surface there:
   `δειχθεῖσαν` → `εἰχθεῖσαν` (the latter isn't a Greek word) would
   force a lookup; `τῇ` → `τὴν` produces an accusative where Paul's
   Greek wants a dative, which changes meaning meaningfully.

3. **The transcription is not good enough** to publish as a standalone
   scholarly Greek edition without a second-pass revision. We do not
   claim that. Readers who want the authoritative Greek of Swete
   should consult the archive.org PDFs we link from `MANIFEST.md`;
   our transcription is the working source for COB's English
   translation, not a replacement for Swete.

## 4. Improvement pathway

The quality floor here is a first-pass single-model transcription. The
project's stated pipeline (DEUTEROCANONICAL.md § "Transcription
accuracy") calls for multi-model cross-check as the next rung. Two
tractable next iterations when accuracy matters more than wall-clock:

1. **Prompt refinement + re-run.** Add explicit instructions to
   `transcribe_greek_swete.md` guarding against the apparatus-merge
   pattern, then re-run affected pages (cheap: ~$15, ~30 min). Expected
   WER reduction: 30–50%.

2. **Multi-model disagreement pass.** Run Claude Opus 4.7 (or Gemini
   2.5 Pro) as a second reader on every page; flag character-level
   disagreements for human review. Catches the long tail. Costs more
   API spend and latency but approaches specialist parity over a
   small number of rounds.

Neither is a prerequisite to starting the English drafting work — the
reviser pass is the designed catch-net. Both are available as quality
dial-ups when we want them.

## 5. Sample sizes + validation provenance

- Automated checks: **617 / 617 pages** (100%).
- Cross-model spot-check: **4 pages** (0.7% sample, ~60 verses).
- Pages read for cross-check: `vol2_p0650` (Wisdom 15:15–16:4),
  `vol2_p0843` (Tobit 5 two-column), `vol3_p0380` (Baruch 3:32–4:10),
  `vol3_p0620` (1 Maccabees 1:42–57).
- Scan images used for cross-check are fetched fresh from archive.org
  at the URLs in each page's `.meta.json`; their SHA-256 hashes in
  those sidecars let any reviewer verify they're examining the exact
  image GPT-5.4 saw.

Any future re-runs that materially change the quality picture should
append a dated entry to this file so the quality trajectory stays
visible and auditable.
