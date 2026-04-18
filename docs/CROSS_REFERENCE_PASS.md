# Cartha Open Bible — Cross-Reference Pass

This document describes the pass that should happen **after a phase draft exists** and alongside the broader revision process.

The goal is not to turn COB into a harmonized paraphrase. The goal is to make sure:
- quotations are translated transparently,
- repeated formulas are handled consistently,
- important internal echoes are not missed,
- and doctrinally sensitive parallels are surfaced for review.

## What this pass is for

A cross-reference pass should answer questions like:
- When Paul quotes or echoes the OT, did we preserve the wording pattern clearly enough?
- When the same phrase appears across books, did we translate it in a way that makes the connection visible?
- When a verse strongly alludes to another passage, should that be preserved with a footnote or rationale note?
- When a later NT author uses a key term that was established earlier in the phase, are we drifting without explanation?

## What this pass is not for

This pass is **not** permission to flatten meaningful variation.

Do not use it to:
- force identical English in places where the source wording actually differs,
- harmonize away Pauline or Johannine style,
- import interpretive cross references into the main text,
- smooth over a difficult phrase just because another verse sounds more familiar.

## Best timing

Run the cross-reference pass at two levels:

### 1. Phase-level pass
After a phase is fully drafted and before the phase is considered truly stable.

Examples:
- Pauline epistles cross-reference pass after Phase 1
- Gospel quotation/allusion pass after Phase 2
- OT quotation + reuse pass after Phase 3 once the NT is complete

### 2. Whole-Bible pass
After the full draft exists.

This is where the largest inter-testamental links should be reviewed:
- OT citations in the NT
- title usage that spans OT/NT expectations
- major covenant vocabulary patterns
- repeated salvation / judgment / kingdom formulas

## High-value cross-reference targets

### Quotations and explicit citations
Examples:
- phrases introduced by “it is written”
- OT citations in Romans, Galatians, Hebrews, Revelation
- gospel citation formulas

Questions:
- Is the source wording reflected clearly enough?
- Are we preserving the fact that this is a citation rather than a fresh phrase?
- Should the YAML footnotes include a `cross_reference` note?

### Strong allusions
Examples:
- Adam / new Adam patterns
- suffering servant echoes
- Abraham promise language
- Exodus / wilderness motifs
- Son of Man / kingdom / day-of-the-Lord language

Questions:
- Is the main text still faithful without over-signaling the allusion?
- Would a light `cross_reference` footnote make the connection more auditable?

### Repeated doctrinal vocabulary
Examples:
- Χριστός / Messiah
- κύριος / Lord
- πίστις / faith / faithfulness
- δικαιοσύνη / righteousness / justice
- σάρξ / flesh
- νόμος / law
- χάρις / grace
- ζωή αἰώνιος / eternal life

Questions:
- Are we drifting in a way that obscures important links?
- If we vary the gloss, did we explain why?

## Recommended workflow

1. **Freeze a scope**
   - one phase,
   - one doctrinal cluster,
   - or one citation family.

2. **Collect references**
   - use verse IDs,
   - existing lexical decisions,
   - doctrine-contested terms,
   - citation formulas,
   - lint flags.

3. **Group by issue type**
   - quotation alignment,
   - title reuse,
   - lemma drift,
   - allusion visibility,
   - footnote gaps.

4. **Revise in batches**
   - not random one-off edits.

5. **Preserve transparency**
   - if a cross-reference matters, prefer documenting it in a footnote or rationale,
   - not silently harmonizing the main text.

6. **Rerun consistency lint**
   - every cross-reference pass should reduce confusion, not create more gloss drift.

## Suggested commit patterns

Good commit examples:
- `revise: add Pauline cross-reference footnotes for Abraham citations`
- `revise: harmonize explicit OT citation handling in Romans and Galatians`
- `revise: preserve Isaiah quotation echoes in Matthew 1-4`
- `revise: align Messiah title usage across direct quotations`

Avoid:
- `misc cross reference fixes`
- one tiny commit per verse
- invisible harmonization without explanation

## Practical recommendation for COB

For COB, the most effective order is:

1. finish the phase draft,
2. run consistency lint,
3. run the phase revision pass,
4. then run a **cross-reference pass** focused on:
   - citations,
   - repeated doctrinal vocabulary,
   - allusions worth surfacing,
5. only then consider the phase stable enough to advance.

In short:

> **Draft first, revise second, cross-reference third, then advance.**

That keeps COB auditable while still letting the translation grow phase-by-phase.
