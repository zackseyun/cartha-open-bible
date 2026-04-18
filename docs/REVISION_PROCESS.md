# Cartha Open Bible — Revision Process

This document describes how COB should move from the current AI draft phase to a more stable revised phase without losing the transparency and reproducibility that make the project valuable.

## Current reality

Right now the repository is in a **draft-first** state:
- every verse is published as a draft,
- the AI rationale is visible,
- chapters are being landed phase-by-phase,
- consistency lint is the main quality gate during drafting.

That means the right revision model is **not** “wait until the whole Bible is perfect, then revise everything at once.”
It should be a structured pass that progressively tightens quality while preserving provenance.

## Best practical revision model

Use a **three-layer revision strategy**.

### Layer 1 — During drafting (live tightening)
This happens while chapters are still being produced.

Goals:
- keep terminology reasonably consistent,
- catch obvious doctrine-policy mismatches,
- prevent major style drift between nearby chapters.

Tools / checks:
- `tools/consistency_lint.py`
- phase-level review of flagged lemmas / gloss variance
- chapter-sized commits with clear lexical summaries

Rule:
- fix major consistency issues **within the current phase** before advancing.

### Layer 2 — Phase revision pass
This happens **after a phase draft is complete** (for example, all Pauline books).

Goals:
- normalize recurring translation choices across the completed phase,
- resolve repeated weak/awkward renderings,
- review all contested-term defaults for consistency,
- improve readability where the draft is technically accurate but clunky.

Recommended workflow:
1. complete the phase draft,
2. run `consistency_lint.py` across the phase,
3. group flags by lemma / issue,
4. revise in thematic batches (not random verse-by-verse hopping),
5. commit revisions in substantive batches,
6. rerun lint until the phase is clean.

Best batching strategy for revision:
- by **lemma family** when a term is drifting,
- by **book section** when tone/readability is drifting,
- by **contested doctrine bucket** when footnotes or renderings need harmonization.

### Layer 3 — Whole-Bible revision pass
This happens once the first full draft exists.

Goals:
- unify voice across OT + NT,
- resolve cross-phase inconsistencies,
- tighten repeated theological vocabulary,
- make sure the translation reads like one translation rather than many chapter batches.

This is the point where COB should get its first serious “release-candidate” revision cycle.

## What counts as a revision?

A revision should be triggered by one of these:
- consistency-lint flags,
- repeated lexical drift for a key lemma,
- awkward English that obscures the source text,
- a doctrinal default not being applied cleanly,
- a strong alternate rendering that deserves promotion or a footnote,
- phase-level harmonization work.

A revision should **not** be triggered just because another English translation reads more familiarly.
COB should preserve its own philosophy unless there is a real source-text reason to change.

## What should change during revision?

### Good revision targets
- repetitive clunky wording,
- inconsistent rendering of the same lemma,
- missing or weak lexical rationale,
- footnotes that should exist but do not,
- overly interpretive wording in the main text,
- places where title/name handling is inconsistent (e.g. Messiah/Christ behavior),
- weak handling of high-value terms such as:
  - Χριστός
  - κύριος
  - δοῦλος
  - πίστις
  - δικαιοσύνη
  - σάρξ
  - יְהוָה
  - אָדָם

### Bad revision targets
- smoothing away intentional lexical sharpness,
- hiding interpretive decisions instead of documenting them,
- silently harmonizing with another translation tradition,
- deleting provenance or making the process less auditable.

## Most effective revision workflow

The most effective way to do revisions is:

1. **Freeze a revision scope**
   - one phase, one book cluster, or one lemma cluster.
2. **Collect evidence first**
   - lint flags,
   - repeated renderings,
   - reader complaints / GitHub issues,
   - search-based spot checks.
3. **Revise in batches**
   - avoid one-off drive-by edits.
4. **Explain the reason for the batch**
   - commit messages should name the lexical / stylistic / doctrinal reason.
5. **Rerun lint immediately**
   - revisions should reduce inconsistency, not create new inconsistency.
6. **Preserve provenance**
   - don’t make the revised text more opaque than the draft.

## Suggested revision order after the draft is complete

Recommended order:

1. **Pauline terms pass**
   - because Romans / Corinthians / Galatians will drive a lot of core doctrinal vocabulary.
2. **Gospels + Acts harmonization pass**
   - to keep narrative voice and title usage coherent.
3. **General epistles + Revelation pass**
4. **Torah pass**
5. **Prophets / Writings pass**
6. **Whole-Bible final harmonization**

## Git strategy for revisions

Revision commits should be substantive and readable.

Good patterns:
- `revise: Pauline pistis renderings`
- `revise: harmonize Messiah title usage in Romans-Galatians`
- `revise: smooth clunky English in 2 Corinthians 1-4`
- `revise: resolve sarx gloss variance in Romans`

Avoid:
- one tiny commit per verse,
- giant unstructured “misc fixes” commits.

## Practical recommendation from the repo's current state

Given how COB is being produced now, the most effective path is:

- keep drafting in parallel chapter batches,
- keep phase-level lint clean,
- do a **focused Phase 1 revision pass** before moving too far ahead if Pauline terminology starts drifting,
- then do a larger whole-Bible revision pass once the first draft corpus exists.

In other words:

> **Draft broadly, revise deliberately, harmonize in batches.**

That gives you speed without turning the final product into a patchwork.
