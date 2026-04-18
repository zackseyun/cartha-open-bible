# Revision Methodology

This document describes how committed drafts are revised, who does the
revising, and what changes qualify as a revision vs. a redraft. It
complements [METHODOLOGY.md](METHODOLOGY.md) which covers the initial
AI-drafting pipeline.

## Why there's a revision stage

The drafting pipeline (`tools/draft.py`) produces schema-valid YAML per
verse with full provenance. Those drafts are good but not final:

- GPT-5.4 (current primary drafter) occasionally produces awkward
  English where the Greek is compact (stranded prepositions, literal
  constructions that don't parse naturally).
- Per-verse decisions sometimes drift from each other — the same Greek
  phrase can be rendered differently in two verses because each call is
  independent.
- Some lexical choices are defensible in isolation but read less well
  alongside sibling verses.

A revision pass by a second model (currently Claude Opus 4.7) catches
these issues without incurring the cost of redrafting from scratch.

## What triggers a revision

A verse is revised when a reviewer identifies one of these:

1. **Real English-grammar awkwardness** — stranded prepositions
   ("being testified to by"), literal-but-unnatural constructions
   ("in that by which you judge another"), double-noun stacks
   ("the one who justifies the one who"), or participial forms that
   don't parse cleanly in English ("becoming in the likeness of").
2. **Rhetorical-force loss** — when the Greek has a concessive,
   emphatic, or adversative force that a flat translation suppresses
   (Phil 2:6 `ὑπάρχων` → "though he was" rather than "existing").
3. **Wordplay that the draft flattens** — when the Greek pairs or
   echoes words the English could preserve more elegantly (Rom 3:26
   δίκαιον/δικαιοῦντα → "just and the justifier").
4. **Scholarly-preference shifts** — when a defensible but unusual
   rendering deviates from mainstream consensus for no textual reason
   (Rom 1:17 "from faith for faith" → "from faith to faith").
5. **Project-wide inconsistencies** — when per-verse drafter decisions
   produce corpus-level drift (see the Χριστός normalization below).

## What does NOT trigger a revision

- **Stylistic preference.** If the existing rendering is defensible and
  reads cleanly, it stays. The revision bar is "materially better,"
  not "my preference."
- **Theological re-interpretation.** Revisions don't change the
  meaning the translator intended — they polish the expression of that
  meaning. If a rendering is theologically contested, that's handled
  via `theological_decisions` and footnotes, not revision.
- **Lexicon-entry quibbles.** The drafter's lexicon call stands unless
  it's plainly wrong. BDAG entry disputes go through public issues on
  the GitHub repo, not silent revision.

## How a revision is committed

Each revision is a discrete git commit attributed to the revising
model. The commit message states:

- Which verses changed
- The specific rendering(s) replaced
- Why the change (category from the list above)
- What was preserved as an alternative (in footnote or
  `lexical_decisions.alternatives`)

The original AI draft's `ai_draft` metadata (model_id, prompt_sha256,
output_hash, timestamp) is preserved exactly — the drafter's
provenance stands. The revision is visible only in git log, not in
the verse YAML's top-level metadata. This keeps the chain of custody
clean: GPT-5.4 drafted this verse on such-and-such date; Claude Opus
polished it on such-and-such date; git shows both.

## Global-scope normalizations

Some corrections apply across every verse at once, not per-verse.
These are scripted and committed in a single pass.

### Χριστός → Messiah (accepted 2026-04-18)

After reviewing ~20 verses and noticing per-verse drift, the project
adopted a consistent rule for rendering the Greek title Χριστός:

| Greek form | COB rendering |
|---|---|
| `ὁ Χριστός` (the Christ) | the Messiah |
| `Χριστός` (bare, titular) | the Messiah |
| `Χριστὸς Ἰησοῦς` (title first) | Messiah Jesus |
| `Ἰησοῦς Χριστός` (name first) | Jesus the Messiah |
| `Ἰησοῦ Χριστοῦ` (genitive) | Jesus the Messiah / of Jesus the Messiah |
| `ἐν Χριστῷ Ἰησοῦ` | in Messiah Jesus |

**Rationale.** Χριστός literally means "anointed one" — it is the
Greek translation of Hebrew מָשִׁיחַ. In modern English, "Christ" has
drifted so far toward proper-name status that Paul's messianic claim
is skipped by most readers. DOCTRINE.md's principle — translate titles
rather than transliterate them — points toward consistent "Messiah."
Per-verse judgment between "Christ" and "Messiah" produces corpus-level
drift that can't be defended to a critic.

The one concession: standalone "Christ" in iconic English phrases
(e.g., Phil 1:21 "to live is Christ") is currently left as-is. A
follow-up pass may address these; for now, they're left for per-verse
judgment.

**Execution.** A mechanical script (`/tmp/normalize_messiah.py` at
time of writing; not committed) applied the compound-form rules to
every drafted verse in a single pass (68 substitutions across 68
verses). Footnotes, lexical_decisions, and theological_decisions were
left untouched so they continue to preserve "Christ" as the traditional
alternative where the drafter documented it.

### Χριστός → Messiah: liturgical carve-outs (accepted 2026-04-18)

After the mechanical pass, two classes of verse were reverted from
"Jesus the Messiah" back to "Jesus Christ" because the phrases function
as fixed liturgical forms in English-speaking Christian use, not as
fresh theological claims where the titular force of Χριστός is in
play:

1. **Pauline benediction formulas** — the closing "the grace of our
   Lord Jesus Christ [be with you]" appears as a fixed liturgical
   stamp at the end of most Pauline letters and is used verbatim in
   church benedictions. Reverted verses: Rom 16:20, Rom 16:24,
   2 Cor 13:13, Gal 6:18, Phil 4:23, 1 Thess 5:28, 2 Thess 3:18,
   Philemon 25. Also 2 Cor 8:9 ("the grace of our Lord Jesus Christ,
   that though he was rich…"), which functions as a mid-letter fixed
   phrase rather than an argued titular claim.
2. **The Phil 2:11 confession** — "Jesus Christ is Lord" (`κύριος
   Ἰησοῦς Χριστός`) is the earliest recorded Christian creed and is
   recited verbatim in liturgy across traditions. Keeping "Messiah"
   here would sound like a scholarly gloss intruding on a confession.

All other occurrences of `Ἰησοῦς Χριστός` remain as "Jesus the
Messiah" per the normalization rule. The carve-outs are narrow and
named: benediction formulas and the Phil 2:11 confession. Any future
carve-out must be documented here with rationale.

**Execution.** A second mechanical script
(`/tmp/renormalize_liturgical.py` at time of writing; not committed)
applied three phrase-level reverts across the 10 verses above.
Footnotes and `lexical_decisions.alternatives` continue to preserve
"Messiah" as the alternative rendering.

## Roles

| Model | Role |
|---|---|
| GPT-5.4 | Primary drafter. Produces first-pass verse YAMLs via `tools/draft.py`. Most verses ship as drafted. |
| Claude Opus 4.7 | Revision reviewer. Reads drafts, identifies revision-worthy issues per the criteria above, commits targeted polish. Does not redraft from scratch. |
| (Future) Named human scholars | Not currently engaged. When they are, they sign individual verses via ed25519 signatures — that process is specified in METHODOLOGY.md but not yet active. |

## What revisions are NOT

- A redraft. Revisions take the drafter's rendering as the starting
  point and make targeted improvements. They don't ignore the draft
  and produce an alternative.
- Silent. Every revision is a git commit with rationale. Critics can
  read the commit log to see exactly what changed and why.
- A substitute for human review. When credentialed scholars engage
  with the project, their signatures supersede any AI revision. This
  revision stage exists to make the AI-drafted text as good as
  possible *before* that review begins.

## Observed patterns so far

From the first ~20 verses reviewed by Opus (Philippians + Romans 1–5):

- Revision rate: ~30% of verses reviewed (6 of ~20).
- Of those: half were English-grammar fixes, the rest were
  rhetorical-force or wordplay-preservation polish.
- **No revisions changed theological meaning.** Every revised verse
  preserves the drafter's interpretive calls; only the English
  expression of those calls is adjusted.
- This suggests the GPT-5.4 drafts are semantically reliable and
  revision is mostly polish. A follow-up global pass may find
  cross-verse inconsistencies (like the Χριστός normalization)
  that any single-verse review would miss.

### Cross-genre benchmark: Revelation sample (2026-04-18)

To check whether the revision rate is an artifact of Paul's dense
argumentative style — or a consistent property of GPT-5.4 drafting —
Opus sampled 9 verses from Revelation (Rev 3:12, 3:15–16, 3:20–21;
11:1, 11:11, 11:15, 11:17). Results:

- Revision rate: ~11% (1 of 9), landing inside the same band as the
  Pauline pass once the first-pass high-friction verses are excluded.
- The one fix (Rev 11:1) is category 1 English-grammar awkwardness —
  a dangling participle that makes the reed appear to speak.
- The drafter handled Revelation's well-known difficulties (Hebraisms,
  ingressive aorists in worship formulas, OT intertextuality) with
  principled restraint: `ἐβασίλευσας` as "have begun to reign"
  (ingressive, guarding against the implication that God wasn't
  previously sovereign); `πνεῦμα ζωῆς` as "a breath of life"
  (echoing Ezekiel 37 without forcing "the Spirit of life");
  `εἰς τοὺς αἰῶνας τῶν αἰώνων` as "forever and ever" rather than
  the wooden "to the ages of ages"; `ἐμέσαι` kept as "vomit"
  rather than softened. The repeated "my God" in Rev 3:12 was
  preserved all four times rather than smoothed away.

This suggests the drafter's quality is genre-stable, and the
revision methodology generalizes across Paul and apocalyptic without
re-tuning.
