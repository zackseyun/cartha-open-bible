# COB 5.5 Revision Pass — Design Doc

**Status:** DRAFT — not yet approved to run
**Author:** Cartha drafting team
**Date:** 2026-04-28

## What this is

A third revision pass over Cartha Open Bible verses, using GPT-5.5 with
the **full prior history of each verse as context** — not a from-scratch
re-translation, but a *judgment* on whether the existing rendering is the
best we can do given everything we now know.

This is *not* an additional initial-draft pass. It's an evaluator with
memory. Its job is to either **endorse** the current rendering or
**propose an improvement**, with a rationale grounded in the evidence
that's already on the verse.

## Why this exists (the requirement that drives the design)

> "It needs to be an improvement beyond our first initial draft and our
> first initial revision pass. We need to be able to take our learnings
> from there and do something even better. And to even look at our draft
> and revision as context as well, so that when we do decide, we can pick
> something even better."

Translation into design constraints:

1. The 5.5 pass must **see** the existing draft + the existing revision
   pass + their rationales. Not running blind.
2. Its default action should be **endorse**, not propose. Most drafts
   are good. The pass earns its keep on the few that aren't.
3. When it proposes a change, it must explain **why this is better than
   what's already there** — citing the prior reasoning by name.
4. It must not silently overwrite. Output goes to a review queue
   (matches the existing `state/reviews/` machinery) for human accept/
   reject.

## What 5.5 has access to that 5.4 didn't

For each verse we hand the model:

```
SOURCE LANGUAGE (Hebrew/Greek/etc. with apparatus markers)
INITIAL DRAFT TEXT (translation.text)
INITIAL DRAFT MODEL (model_id, model_version, prompt_id, timestamp)
LEXICAL DECISIONS    (every chosen gloss + alternatives + rationale)
THEOLOGICAL DECISIONS (where applicable: chosen_reading + alternatives + rationale)
FOOTNOTES            (with reasons: alternative_reading, lexical_alternative, etc.)
REVISION PASS RECORD (revision_pass: { changes_summary, model, timestamp })
PRIOR REVISIONS LIST (revisions[]: every applied edit with timestamp + reason)
COMPARISON RENDERINGS (for the same verse from KJV, NRSV, ESV, NIV, NLT, NET, NASB)
ADJACENT VERSES      (the verse before and the verse after, for flow)
KEY CROSS-REFS       (if known: where this verse anchors a doctrine or quotes another)
CONCEPT TAGS         (what theological concepts the verse anchors)
```

That's a 4-6K token input per verse. The model thus has more context
than either the initial drafter or the revision pass had — including
the *log* of how the verse got to its current state.

## What the model is told to do

System prompt (sketch):

> You are an experienced biblical translator reviewing a verse rendering
> for the Cartha Open Bible. The verse already has an initial draft and a
> revision pass; you can see both, including the lexical and theological
> rationales that produced the current text.
>
> Your default verdict is **endorse**. Only propose a revision if you can
> identify a specific, concrete improvement — a more accurate gloss, a
> better-flowing English, a footnote that should now be in the body
> (or vice versa), or a lexical decision that no longer holds against
> the broader translation lens.
>
> When you propose a revision, you must explain (a) what is being changed
> and why, (b) why this is *better* than the existing rendering — naming
> the prior reasoning if you're disagreeing with it, (c) which lexicons
> or comparison translations support your suggestion.
>
> You may not invent citations. You may not fabricate verse cross-refs.
> If you don't have a specific source for a point, you do not propose
> based on it.

User prompt: the structured context block above.

## Output schema

Per verse, the pass produces a YAML record at
`state/reviews/gpt-5.5/<book>/<chapter>/<verse>.yaml`:

```yaml
verse_id: GEN.1.1
reviewer:
  model_id: gpt-5.5
  model_version: gpt-5.5-2026-04-24
  effort: low
  timestamp: 2026-04-28T...
  prompt_id: cob_revision_5_5_v1
  prompt_sha256: <hash>

# What the model decided.
verdict: endorse              # endorse | propose_revision | flag_for_human

# If endorse, that's it. If propose_revision:
proposed_text: |-
  ... (the model's suggested rendering)
rationale: >-
  A specific, citation-grounded explanation of why this is better.
  References lexicon entries (HALOT, BDAG, LSJ), comparison
  translations, and/or prior decisions on the verse by name.
delta_kind:                   # one or more of:
  - lexical_choice            # different gloss for a key word
  - syntax                    # different clause boundary or word order
  - footnote_to_body          # promote a footnote alternative into the body
  - body_to_footnote          # demote a body reading into a footnote
  - register                  # tone (formal/idiomatic) at fault
  - flow                      # English flow with surrounding verses
  - cross_translation_outlier # we diverge from all majors without justification
supporting_evidence:
  lexicons: [HALOT.X, BDAG.Y]
  comparison_translations: [NRSV, ESV]   # whose rendering we'd move toward
  prior_decision_disagreed_with: lexical_decisions[2]  # by index, or null

# If flag_for_human (rare): the model thinks this is contested and
# wants a human eye, not an AI proposal.
flag_reason: >-
  ... (e.g., "The lexical choice depends on a textual variant the
  model can't adjudicate; recommend manual review with apparatus.")

# Confidence the model places on its own verdict (0..1). Useful for
# sorting the review queue: humans look at high-confidence proposals
# first, then medium, then flag_for_human.
self_confidence: 0.83
```

## How it integrates with what already exists

### Inputs
- `translation/**/<book>/<chapter>/<verse>.yaml` — every field is read
- The COB JSON manifest (`bible.cartha.com/cob_preview.json`) — for
  comparison translation renderings
- A side-table of public-domain comparison translations (KJV, NRSV/RSV,
  ASV, ESV draft, etc.) — pre-fetched once, joined per verse

### Outputs
- `state/reviews/gpt-5.5/...` — the per-verse review records (gitignored;
  lives only on the maintainer's Mac, same pattern as
  `state/reviews/azure-gpt-5.4/`)
- `revisions.json` — flywheel picks up endorsement counts + proposal
  counts + acceptance rate per book; status dashboard surfaces them
- A new column on the public progress page: "second-pass review
  coverage (5.5)" alongside the existing "review coverage" number

### Human review loop
- A small review CLI: `tools/review_5_5_proposals.py`
  - Walks proposals sorted by self_confidence DESC
  - Shows: verse_id, source, current draft, proposed text, rationale,
    delta_kind, supporting_evidence
  - Maintainer keypress: A (accept) / R (reject) / S (skip / come back) /
    E (open in editor for hand-edit)
  - Accepted proposals get applied to the verse YAML and pushed through
    the normal commit flow (with `revise:` prefix, attribution to
    gpt-5.5-2026-04-24)

## Filtering — which verses get the 5.5 pass?

41,936 verses × ~$0.05 (5.5 low) = $2,097 — fits in the $3K budget but
leaves no room for the concept sweep. We won't run on all 41,936. We
prioritize by **expected revision yield**, in this order:

| Layer | Approx count | Why prioritize |
|---|---|---|
| Verses with revision_pass.unchanged: false (already touched) | ~5,500 | The pass identified them as worth touching once; second pass may find more. |
| Verses with footnotes | ~3,000 | Footnotes mark known ambiguity. Did we put the right reading in the body? |
| Verses with theological_decisions | ~600 | Doctrinal weight; fresh model may surface a better reading. |
| Verses linked to concept atlas (top concept anchors) | ~6,000 | High-traffic verses; quality matters most here. |
| Verses where COB diverges from ≥3 of {KJV, NRSV, ESV, NIV} without footnote | ~2,500 | Outlier rendering with no recorded justification. |
| Pseudepigrapha (we know these had splitter issues) | ~3,000 | Translation quality known-uneven. |
| **Subtotal (deduped)** | **~15,000** | |

That leaves ~27K verses untouched. The triaged 15K is the highest-
yield set; we can always run a second sweep later on the remainder when
we have more budget or a stronger model.

## Cost & schedule

- 15,000 verses × $0.05/verse (5.5 low) = ~$750
- ~30 workers × ~12s/verse = 100 min wall time
- Total spend: ~$750 (vs the $1,200 originally allocated; saves $450
  for the concept sweep reserve)

Schedule:
- Day 1: build prompt + integration scripts, pilot on 50 verses across
  triage layers, human-grade output
- Day 2: full triaged sweep (~100 min wall)
- Day 3: maintainer reviews top-confidence proposals, applies accepted
  ones; flywheel updates revisions.json

## Pre-flight tests before committing

The user's requirement: this must be an improvement, not just another
opinion. To validate, before running on 15K verses:

1. **Pilot 50 verses** drawn from each triage layer.
2. Maintainer hand-grades each proposal as: clear improvement /
   defensible alternative / no improvement / regression.
3. **Acceptance threshold:** ≥30% clear improvement, ≤10% regression.
   If we don't hit that, we iterate the prompt before scaling.
4. Specifically watch for these failure modes:
   - The model proposes alternates without engaging prior rationale
     (didn't read the lexical_decisions field).
   - The model defaults toward NRSV/ESV homogenization (drops Cartha's
     distinctive choices).
   - The model fabricates lexicon citations.
   - The model proposes registry shifts (KJV-flavored prose) without
     justification.
5. If any failure mode shows up at >5% of pilot verses, prompt iterates
   until it doesn't.

## What this design does NOT do

- It does not run before pilot grading. We're not giving 5.5 carte
  blanche to "improve" 15K verses sight-unseen.
- It does not auto-apply. Every proposal is queued for human review.
- It does not run on every verse. The triage filter is part of the
  design, not a post-hoc cost cap.
- It does not retire prior revisions. The 5.5 record is additive — the
  full history (initial draft + revision_pass + 5.5 review) stays
  visible to anyone reading the verse YAML.

## Open questions for sign-off

1. **Comparison translations license** — KJV (PD), ASV (PD), WEB (CC0),
   Berean Standard (PD) are safe. Modern majors (NIV, ESV, NRSV) are
   not redistributable; we can use them as model context internally
   but should not leak them into committed YAMLs. Is that the right
   call?
2. **Endorsement records** — when verdict=endorse, do we still write a
   YAML record (provenance: "gpt-5.5 reviewed and approved on date X")?
   I'd say yes — endorsements are useful signal too. Extra ~$0.005 per
   verse storage / no token cost.
3. **Self-confidence calibration** — first 50 verses, also have the
   maintainer score "would you have accepted this" → calibrate
   self_confidence threshold for review-queue sorting.
4. **Order of operations** — concept sweep finishes first, then 5.5
   COB pass uses concept-tag context (which verses anchor which
   concepts). Or run them in parallel. I'd vote sequential: concept
   sweep informs the verse pass.

## Decision needed

Sign off on:
- Triage filter (the 15K subset)
- Output schema (per-verse YAML at `state/reviews/gpt-5.5/...`)
- The four pre-flight failure modes to watch
- Sequential ordering (concept sweep first, then verse pass)

Once signed off: I implement the prompt + pilot script, run the 50-verse
pilot, hand-graded results to you for accept/iterate decision.
