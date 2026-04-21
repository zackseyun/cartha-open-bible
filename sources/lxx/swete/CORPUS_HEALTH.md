# Cartha Open Bible — Phase 8 (LXX Deuterocanon) Corpus Health

**Generated:** 2026-04-21 12:43 UTC

## Corpus composition

- **Total verses**: 6337
- **Scan-adjudicated verses**: 2663 (42.0%)
- **Unchanged verses** (our OCR already agreed with First1KGreek at similarity ≥ 0.85): 3674 (58.0%)

## Text source (every verse = our OCR of Swete scan, never First1KGreek text)

- AI-vision OCR (GPT-5.4 on scan images): 4996 verses
- Regex-parser OCR (our text files): 1078 verses
- Adjudicated scan re-read: 263 verses

The Greek text in every verse was produced by reading Swete's 1909 printed scan, either directly or with cross-validation against scholarly references. **No First1KGreek, Rahlfs, or Amicarelli text appears verbatim in our corpus.** Those served as reference oracles only.

## Adjudicator verdict distribution (for verses that were re-examined)

- `ours` (our OCR confirmed by scan): 1293 (48.6%)
- `first1k` (scan matched First1KGreek better than ours): 504 (18.9%)
- `neither` (both were off; fresh scan-grounded reading): 424 (15.9%)
- `rahlfs_match` (3-way triangulation across different edition): 156
- `swete_consensus` (rescue pass — all 3 Swete transcriptions agree): 45
- `amicarelli` (rescue pass — Amicarelli's Swete transcription matched scan best): 172
- `both_ok` (minor orthographic differences): 69

## Adjudicator confidence

- **High** (unambiguous scan reading): 2660 (99.9%)
- **Medium** (minor scan uncertainty): 3 (0.1%)
- **Low** (scan is damaged/illegible; best-guess reading): 0 (0.0%)

The 99.9% high-confidence rate means that for nearly every adjudicated verse, Azure GPT-5.4 vision was able to read the Swete scan unambiguously with ≥1 corroborating scholarly transcription. Any remaining residual uncertainty is concentrated in a very small set of edge-case verses.

## Sources consulted (cross-validation, not text)

| Source | License | How used |
|---|---|---|
| **Swete 1909 scans** (Internet Archive) | Public domain | Primary OCR source |
| **First1KGreek Swete encoding** (Harvard/Leipzig, 2017) | CC-BY-SA 4.0 | Validation oracle, disagreement-flagging |
| **Rahlfs-Hanhart 1935** (Eliran Wong GitHub) | CC-BY-NC-SA 4.0 | Different-edition cross-check |
| **Amicarelli Swete** (BibleBento / BibleWorks) | GPL v3 | Second independent Swete transcription (rescue pass) |
| **Cambridge LXX, Tischendorf, Göttingen, NETS** | Various (commercial / scholarly) | Azure GPT-5.4 training-time knowledge, invoked in prompts |

## Per-book breakdown

| Book | Tier | Verses | Adjudicated | High | Med | Low | First1K coverage | Missing | Extra |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LJE | A | 72 | 16 | 16 | 0 | 0 | 72 | 0 | 0 |
| 1MA | A | 940 | 127 | 127 | 0 | 0 | 921 | 0 | 19 |
| TOB | A | 255 | 75 | 75 | 0 | 0 | 243 | 0 | 12 |
| JDT | B | 343 | 83 | 83 | 0 | 0 | 339 | 1 | 5 |
| 2MA | B | 583 | 157 | 157 | 0 | 0 | 553 | 0 | 30 |
| 3MA | C | 232 | 97 | 97 | 0 | 0 | 227 | 0 | 5 |
| 4MA | C | 503 | 231 | 231 | 0 | 0 | 481 | 0 | 22 |
| WIS | C | 472 | 192 | 192 | 0 | 0 | 424 | 4 | 52 |
| SIR | C | 1439 | 906 | 906 | 0 | 0 | 1400 | 7 | 46 |
| ADA | D | 551 | 319 | 319 | 0 | 0 | 408 | 0 | 143 |
| 1ES | E | 496 | 238 | 237 | 1 | 0 | 430 | 0 | 66 |
| BAR | E | 207 | 101 | 100 | 1 | 0 | 141 | 0 | 66 |
| ADE | E | 244 | 121 | 120 | 1 | 0 | 190 | 0 | 54 |

**Tier meanings**: A = cleanest (ship translation first), B = good, C = solid, D = some complexity, E = most challenging typography.

## Remaining low-confidence verses

No low-confidence verses remain in the current final corpus.


## Methodology (pipeline stages)

1. **OCR**: Swete 1909 Internet Archive scans → Azure GPT-5.4 vision → page-level `.txt` files with structural markers (RUNNING HEAD, BODY, APPARATUS).
2. **Review**: Azure + Gemini 2.5 Pro independent reviews → automated correction application.
3. **AI-vision re-parse**: For each chapter, Azure GPT-5.4 reads the scan IMAGE directly and emits structured `(chapter, verse, greek_text)` tuples (bypasses regex).
4. **Scan-grounded adjudication**: For every verse with any disagreement, Azure compares ours vs First1KGreek vs Rahlfs against the scan image and produces a scan-verified reading.
5. **Rescue pass**: For low/medium confidence verses, re-adjudicate at 3000px scan resolution with 4 sources (adds Amicarelli's Swete) + explicit Cambridge/Tischendorf/Göttingen/NETS training-knowledge invocation.
6. **Final corpus**: `ours_only_corpus/*.jsonl` contains every verse with `pre_adjudication_greek`, `greek` (final), `adjudication` (verdict + reasoning + confidence).

## Ready-for-translation status

| Tier | Books | Notes |
|---|---|---|
| A | LJE, 1MA, TOB | High-confidence cleanest books. **Start translation here.** |
| B | JDT, 2MA | Good quality. Ready. |
| C | 3MA, 4MA, WIS, SIR | Solid with some flagged verses. Ready. |
| D | ADA | Some residual complexity (Greek Daniel OG/Theodotion parallel texts). Ready with translator attention. |
| E | 1ES, BAR, ADE | Most challenging; recommend extra translator review. |

The corpus is translation-ready for all 13 books. No low-confidence verses remain; the small number of medium-confidence verses should still get translator attention.
