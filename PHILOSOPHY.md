# Why this translation exists

Every major modern English Bible is the product of a closed process. A
committee of scholars makes thousands of translation decisions behind closed
doors; readers receive the finished text; the reasoning behind any given
word choice — why *doulos* was rendered "servant" here and "slave" there,
why the footnote elevates one reading over another — is almost never
surfaced to the people actually reading scripture.

This worked for centuries because it had to. Assembling the scholarship for
a Bible translation required publishers, institutional funding, and
closed-room deliberation. The opacity wasn't a choice — it was the cost of
getting the work done at all.

It isn't any longer.

## The moment this becomes possible

Three things are true now that were not true a decade ago:

1. **Open source infrastructure** — public repositories, issue trackers,
   collaborative editing, cryptographic signing — is free, instant, and
   globally accessible. A scholar in Nairobi can audit a translation decision
   made in Dallas the moment it's committed.

2. **Frontier AI models** — Claude, GPT, Gemini — can produce competent first
   drafts of biblical Greek and Hebrew translation with full lexical
   reasoning, and can be cross-checked against each other to surface exactly
   where human judgment is needed. The model isn't the translator. The model
   is a drafting tool that makes the scholar's bottleneck — reviewing every
   verse against every alternative — tractable.

3. **Modern reproducibility standards** — "same input, same output" applied to
   translation means any third party with the source text, the prompt, and
   the model identifier can regenerate the draft and verify it matches.
   Nothing like this exists in the history of Bible translation.

Together, these make something new possible: a translation where every
decision is documented, every disagreement is public, every verse is
reproducible, and every word can be traced back to the Greek or Hebrew it
came from — in under 60 seconds, from a phone, anywhere in the world.

That is the Cartha Open Bible.

## What we are translating

We translate directly from the openly-licensed scholarly critical editions of
the original-language texts:

- **SBLGNT** (Greek New Testament, ed. Michael W. Holmes) — the closest
  legally-available approximation to the autographs the NT authors wrote.
- **Westminster Leningrad Codex** and **unfoldingWord Hebrew Bible** — based
  on the Leningrad Codex (1008 AD), the oldest complete Hebrew Bible
  manuscript in existence.

We are not paraphrasing or smoothing an existing English translation. We are
translating from the same sources the scholarly community works from — the
Greek and Hebrew — applying documented translation philosophy to each verse,
with every decision auditable.

## What "transparent" actually means here

Every verse in this translation is a file in this repository. Each file
contains:

- The **source text** (Greek or Hebrew) being translated
- The **English rendering** that ships to readers
- Every **lexical decision** made — the source word, the chosen English
  gloss, the alternatives considered, the lexicon consulted, and *why* the
  chosen gloss was preferred
- Every **theologically-contested reading**, with the alternative preserved
  in footnotes rather than buried
- The **AI model**, **prompt hash**, and **timestamp** of the initial draft
- The **cross-check** results across three frontier models, with agreement
  scores and divergence resolution
- The **named human reviewer** who approved the verse, with their
  credentials, their signature, and a link to the public discussion where
  any disagreement was worked out
- A **git commit history** documenting every revision

If you disagree with a rendering, you don't have to send a letter to a
publisher and hope for a reply. You open an issue on GitHub, cite the
specific verse, and engage publicly. We commit to responding substantively
to every serious concern. When we revise, the revision is itself a commit
with documented rationale. Nothing happens in private.

This is transparency in the same sense scientific papers are transparent:
we show the data, we show the methods, we show the reasoning, and we invite
the rest of the world to check our work.

## Open by principle, not by default

We release this translation under **Creative Commons Attribution 4.0
International (CC-BY 4.0)** — the canonical open-content license. This
means:

- **Anyone may use it** — in apps, websites, books, sermons, study
  curriculum, audio Bibles, video content, academic papers.
- **Anyone may use it commercially** — publish a paid study Bible, sell an
  app, build a paid tool. No royalties flow to us. No permission required.
- **Anyone may create derivative works** — paraphrases, adaptations,
  commentaries, translations into other languages, revisions.
- **Anyone may redistribute it**, including modified versions.
- Attribution is the only requirement: credit the Cartha Open Bible, link
  to the license, and indicate if you made changes.

This is a deliberate theological choice, not a pragmatic one. Every major
Bible before 1900 was effectively public domain — the KJV, Geneva, Tyndale,
Luther's German, Wycliffe. Paid licensing of scripture is a modern
innovation, not a historical norm. Our commitment is to recover the older
pattern: *freely you have received, freely give* (Matthew 10:8).

We do not want to own a Bible. We want to help produce one, hand it to the
church, and have people read it.

## What this is not

Several things it helps to say explicitly:

- **Not an AI-generated Bible.** AI drafts every verse; named human
  scholars review and sign every verse. No verse ships to readers without a
  human signature. The AI is a drafting tool, not an authority.
- **Not a replacement for scholarship.** We stand on the shoulders of
  centuries of Greek and Hebrew lexicography, textual criticism, and
  theological scholarship. Every lexical decision cites the lexicons
  (BDAG, HALOT, LSJ, Louw-Nida) the academy already uses.
- **Not a denominational product.** Translation decisions operate within
  historic ecumenical Christian orthodoxy (Apostles' Creed, Nicene Creed,
  Chalcedonian Definition). Within that, we do not promote one denomination's
  distinctives over another's — contested readings are preserved in
  footnotes, not smoothed away.
- **Not a study Bible.** Footnotes document translation decisions, not
  devotional application. The aim is to deliver the most accurate and
  understandable English rendering of what the Greek and Hebrew say,
  nothing more.
- **Not finished.** This is a multi-year effort. We ship phase-by-phase,
  book-by-book, with every stage transparently marked as preview or
  reviewed-and-finalized.

## How to engage

- **Read it.** When a book is published, use it in your prayer, study, and
  teaching. Tell us what lands and what doesn't.
- **Critique it.** File an issue on GitHub for any verse you'd translate
  differently. Lexical disagreements, theological disagreements, and general
  concerns all have templates. Your academic training, denominational
  perspective, and relationship to scripture are all welcome.
- **Cite it.** In academic work, sermons, or published material, cite the
  Cartha Open Bible with a link back. Attribution keeps the paper trail
  visible and invites others into the work.
- **Fork it.** If you have a specific scholarly disagreement you want to
  pursue, fork the repository and publish your alternative. Our provenance
  records travel with the fork, so forks remain academically legible.
- **Translate it.** CC-BY 4.0 permits derivative translations into other
  languages. A translator working from the Cartha Open Bible into any other
  language inherits the full provenance chain back to the Greek and Hebrew.

## Our commitment

We commit to:

- **Never paywall scripture.** The text will always be free to read.
- **Never hide decisions.** Every translation choice remains documented,
  publicly inspectable, and reproducible.
- **Never silence disagreement.** Public issues remain open; responses are
  public; revisions are public.
- **Never claim authority the text doesn't have.** This translation is a
  human-and-tool-assisted rendering of ancient documents into modern English.
  It is not itself inspired. Scripture is.

The Word belongs to the church. We are stewards of a process, not owners of
a text.

*Soli Deo gloria.*
