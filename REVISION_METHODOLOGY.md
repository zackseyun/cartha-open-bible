# Revision Methodology

This document describes how committed drafts are revised, who does the
revising, and what changes qualify as a revision vs. a redraft. It
complements [METHODOLOGY.md](METHODOLOGY.md) which covers the initial
AI-drafting pipeline.

## Why there's a revision stage

Every committed draft gets a second read. The drafting pipeline
(`tools/draft.py`) produces schema-valid YAML with full provenance,
and most verses ship as drafted — but a second-model review pass gives
every verse a second editorial eye before it's considered final.
Committing that pass as its own layer keeps the drafter's provenance
intact and makes every editorial change inspectable in git history.
See *What triggers a revision* below for the specific criteria.

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

### μετανοέω → "change of mind" / "change your thinking" (accepted 2026-04-19)

After a project-wide review of all 51 NT occurrences of μετανοέω
and μετάνοια, the project adopted a context-sensitive rule for
rendering the verb and its noun.

**The drift.** μετανοέω literally = "to change one's mind/thinking"
(μετά "change" + νοέω "think, perceive"). BDAG's gloss: "to change
one's mind or thinking." The traditional English rendering "repent"
preserved this in older usage but has drifted in modern English
toward "feel guilty about sin / apologize," which collapses the
cognitive force the Greek carries. Hearers of John the Baptist and
Jesus heard a call for fundamental worldview reorientation, not
primarily an emotional response.

**The rule.** Render μετανοέω / μετάνοια in three buckets, by
context:

1. **Worldview-reorientation contexts** (Jesus's and John the
   Baptist's kingdom proclamation, apostolic preaching to outsiders,
   theological summaries of the gospel call) → **"change your
   thinking" / "a change of mind"**. The cognitive force is dominant
   and "repent" obscures it.
2. **Specific-sin departure contexts** (Revelation's calls to the
   seven churches, Paul correcting specific moral failures, the
   adjective ἀμετανόητος "unrepentant") → **keep "repent" /
   "repentance"**. The Greek here pairs the verb with named sins
   (μετανοήσωσιν ἐκ τῶν ἔργων αὐτῆς, "repent of her works"), and
   English "repent" carries the right combined cognitive-and-
   behavioral force.
3. **Fixed liturgical formula** ("baptism of repentance," βάπτισμα
   μετανοίας — Mark 1:4, Luke 3:3, Acts 13:24, 19:4, and the
   parallel Matt 3:11) → **keep "baptism of repentance"**. The
   phrase is a 2,000-year-established English formula naming a
   ritual; replacing it would be jarring without illuminating the
   underlying Greek.

**Distinct verb: μεταμέλομαι.** The related verb μεταμέλομαι ("to
regret, change one's mind about something done") appears 6× in the
NT (Matt 21:29, 21:32, 27:3; 2 Cor 7:8 ×2; Heb 7:21) and is
distinct from μετανοέω. It carries the regret/remorse sense that
modern English "repent" has drifted toward. We render
μεταμέλομαι as "regret" or "change one's mind [about a prior
action]" — keeping it lexically separate from μετανοέω.

**Execution.** Two scripts (`/tmp/metanoia_revise.py`,
`/tmp/metanoia_revise2.py`; plus a lexical-decisions updater
`/tmp/metanoia_lex.py`; none committed) applied the per-verse
revisions across 30 verses. The remaining 21 verses (Revelation
specific-sin contexts, the baptism-of-repentance formula, the
ἀμετανόητος adjective in Rom 2:5, the interpersonal Luke 17:3-4,
the contested Heb 12:17 about Esau, and the μεταμέλομαι verses)
were deliberately kept as-is per the rule. An anchor footnote was
added to Matt 3:2 (the first NT occurrence) explaining the
project-level decision for reader transparency.

## Roles

| Model | Role |
|---|---|
| GPT-5.4 | Primary drafter. Produces first-pass verse YAMLs via `tools/draft.py`. Most verses ship as drafted. |
| Claude Opus 4.7 | Revision reviewer. Reads drafts, identifies revision-worthy issues per the criteria above, commits targeted polish. Does not redraft from scratch. |

## What revisions are NOT

- A redraft. Revisions take the drafter's rendering as the starting
  point and make targeted improvements. They don't ignore the draft
  and produce an alternative.
- Silent. Every revision is a git commit with rationale. Critics can
  read the commit log to see exactly what changed and why.
