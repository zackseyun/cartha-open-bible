# Translation Stance

This document states the translation commitments that guide every
decision in the Cartha Open Bible. Declaring them is an act of
honesty: critics can assess our output against our stated
commitments rather than guessing at hidden biases.

> **Status: first draft.** This document will be refined as the
> project matures. Input and disagreement are welcomed via GitHub
> issues.

## Theological stance

The Cartha Open Bible does not commit to a specific denominational
or creedal doctrinal stance. Where the source texts presuppose
theological claims — the divinity of Christ, the resurrection,
the personhood of the Holy Spirit, the unity of God — the
translation reflects those claims as the texts present them, not
as imposed commitments of the translator.

Readers from any tradition (Catholic, Eastern Orthodox, Protestant
of any stripe, non-denominational, inquirer) are invited to
evaluate COB against their own framework. Where a translation
decision is influenced by a theological reading — for example,
where a Greek construction is genuinely ambiguous and the English
choice leans one way or the other — that choice is documented in
the verse's `theological_decisions` block and the alternative
rendering is preserved in a footnote.

We do not pick sides on denominational distinctives (Reformed vs.
Arminian, infant vs. believer's baptism, real presence vs.
symbolic, cessationist vs. continuationist, etc.). Those questions
are for the reader and their faith community, not for the
translation.

## Translation philosophy

The Cartha Open Bible aims at **optimal equivalence**: a middle
path between formal ("word-for-word") and dynamic
("thought-for-thought") approaches.

Specifically:

1. **Original-language primacy over translation tradition.** Where
   long-standing English renderings reflect translation-tradition
   inertia rather than the source text's plain sense, we favor the
   source. Example: translating *doulos* as "slave" rather than
   "servant" in contexts where the term's bonded nature is
   theologically salient (Rom 1:1, Phil 1:1).

2. **Translate titles; transliterate names.** Christological
   titles are translated to preserve meaning (*Christos* →
   "Messiah", not "Christ" where context supports; *Kyrios* →
   "Lord"). Personal names are transliterated by standard
   conventions.

3. **Preserve theological tension rather than resolve it.** Where
   the source is genuinely ambiguous on a contested interpretive
   question (e.g., *pistis Christou* — "faith in Christ" vs.
   "faithfulness of Christ"), we render one in the main text and
   preserve the alternative in a footnote, documenting the
   decision in the per-verse YAML.

4. **Gender-inclusive where the original audience clearly
   included both.** Where Greek or Hebrew uses grammatically
   masculine plurals (*adelphoi*, "brothers") to address mixed-
   gender groups — which was standard in biblical-era usage — we
   render in modern English forms that match the audience the
   source author was actually addressing ("brothers and sisters").
   Where the reference is specifically to male persons (e.g., "the
   brothers of Jesus" meaning his male siblings), the masculine
   form is retained. The goal is audience-accuracy in the English,
   not gender erasure from the text.

5. **Consistency of key terms, or documented exception.** A given
   Greek or Hebrew word should receive a consistent English gloss
   across the translation, unless context demands variance — in
   which case the variance is documented per-verse with a
   rationale. The `consistency_lint.py` tool enforces this at
   commit time.

6. **Readable modern English, not archaic or academic.** The
   target reader is a literate 18–35-year-old English speaker.
   Vocabulary should be accessible without flattening theological
   weight. We avoid both ecclesiastical jargon ("propitiation" is
   footnoted, not required) and informality that undersells the
   text's gravity.

## Contested terms

The following terms appear frequently and carry heavy theological
weight. Our default rendering and rationale are recorded here.
Per-verse variance is documented in the individual YAML files.

| Greek / Hebrew | Default English | Alternatives considered | Rationale |
|---|---|---|---|
| Χριστός *Christos* | Messiah (where title; Christ where name-like) | Christ | Preserves Hebraic messianic context |
| κύριος *Kyrios* | Lord | LORD, Master | Matches covenantal and NT usage |
| δοῦλος *doulos* | slave (where bonded nature is salient) / servant | bondservant | Uses "slave" where ownership/service is theologically active |
| πίστις *pistis* | faith | faithfulness, trust | Main text: faith; footnote alternatives where contested |
| δικαιοσύνη *dikaiosynē* | righteousness | justice | Both renderings preserved in footnotes for Pauline passages |
| ἱλαστήριον *hilastērion* | atoning sacrifice | propitiation, mercy seat | Dynamic rendering for accessibility; alternatives footnoted |
| ἀγάπη *agapē* | love | charity (archaic) | Lexical cognates in source kept |
| σάρξ *sarx* | flesh (literal) / sinful nature (metaphorical) | — | Context-dependent; per-verse documented |
| μετανοέω *metanoeō* | change of mind / change your thinking (cognitive contexts); repent (specific-sin contexts) | repent (traditional) | See REVISION_METHODOLOGY.md §"μετανοέω → change of mind" for the per-context rule |
| νήφω *nēphō* | clear-minded (most contexts); sober (where Paul explicitly runs the drunk/sober metaphor) | sober-minded | See revision notes in 1 Pet 5:8, 1 Thess 5:6 |
| ἀδελφοί *adelphoi* | brothers and sisters (mixed-gender audience) / brothers (male-only reference) | siblings | Per §4 above |
| יְהוָה YHWH | the LORD | Yahweh, Jehovah | Follows Jewish reverence tradition + LXX pattern |
| אָדָם *adam* | man / humankind (context) | — | Context-dependent per usage |

## What the translation is not

To prevent misunderstanding:

- **Not a paraphrase.** Every English rendering is tied to a
  specific source-text word or phrase, documented in the per-verse
  YAML.
- **Not a study Bible.** Footnotes document translation decisions,
  not doctrinal application or devotional commentary.
- **Not a denominational product.** The translation is
  intentionally cross-denominational. Contested readings are
  preserved in footnotes, not smoothed away.
- **Not a finalized translation.** Every verse is currently an
  AI-drafted rendering, released openly with full rationale. There
  is no formal scholarly review process at this time.
- **Not a first-century English approximation.** We aim at modern
  English that honors source-language meaning, not at archaism.

## Change log for this document

Material changes to this document are themselves commits. Prior
versions of the stance are preserved in git history.

- **2026-04-21:** Removed creedal affirmations (Apostles' Creed,
  Nicene Creed, Chalcedonian Definition) and replaced with a
  theological-stance section that refuses specific creedal
  commitment. Reason: the project leader does not personally
  affirm specific creedal formulations with confidence, and
  putting unverified commitments into the project's named stance
  was dishonest. Translation decisions that previously cited those
  creeds are preserved in per-verse YAML as historical record of
  the drafter's reasoning at time of drafting; they are not
  retroactively revised. Flipped §4 from "gender-accurate over
  gender-neutral" to "gender-inclusive where the original audience
  clearly included both." Queued a project-wide revision pass on
  *adelphoi* renderings as a follow-up.
