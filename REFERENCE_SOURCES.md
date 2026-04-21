# Reference sources — operational policy for translation

This document defines, operationally and legally, how copyrighted and
restricted-license scholarly sources may be used during translation
of the Cartha Open Bible. It is a companion to
[DEUTEROCANONICAL.md](DEUTEROCANONICAL.md) (scope/strategy) and
[METHODOLOGY.md](METHODOLOGY.md) (pipeline).

The core claim: **consultation is not reproduction.** Scholars and
translators have always read the leading critical editions, let those
editions inform their judgment, and then produced their own fresh
work. That is what every serious modern translation does. This
document translates that long-standing practice into concrete rules
for our AI-assisted pipeline.

## Position assessment — where we stand per book

Our source position across the deuterocanonical corpus, as of
**2026-04-20**:

| Book | Original language | Position | Why |
|---|---|---|---|
| **Sirach** (SIR) | Hebrew | **Strongest** | Schechter 1899 Cairo Geniza (PD) covers ~½ directly; Sefaria/Kahana composite covers ~⅔. Translate from Hebrew for most of it, LXX (Swete) for the rest — exactly what NRSV does. |
| **Tobit** (TOB) | Aramaic | **Near-optimal** | LXX Long Recension (Codex Sinaiticus via Swete, PD) tracks the same textual tradition as Qumran 4Q196-200. Neubauer 1878 Hebrew back-translation (PD, via Sefaria) supplies Semitic phrasing. Fitzmyer DJD XIX consulted as reference for the ~20% Qumran overlap. Result is nearly indistinguishable from a Qumran-first translation — a specialist would notice maybe 5-10 verses. |
| **1 Esdras** (1ES) | Greek | **Optimal** | 1ES is a Greek composition. Swete LXX (PD) is the primary source. Our MT alignment table maps 1ES verses to WLC Hebrew parallels in 2 Chr / Ezra / Neh for name-spelling and idiom locks. The "Three Youths" block (3:1-5:6) is Greek-only; no Hebrew parallel exists. |
| **Wisdom of Solomon** (WIS) | Greek | **Optimal** | Greek is the original language. No older source exists. Swete LXX (PD) is definitive. |
| **Judith** (JDT) | Hebrew (lost) | **Optimal** | The Hebrew Vorlage is entirely lost. Swete LXX (PD) is the sole surviving witness. |
| **Baruch** (BAR) | Hebrew (lost) | **Optimal** | Hebrew lost. Swete LXX (PD) sole witness. |
| **Letter of Jeremiah** (LJE) | Hebrew (lost) | **Optimal** | Hebrew lost. Swete LXX (PD) sole witness. |
| **1 Maccabees** (1MA) | Hebrew (lost) | **Optimal** | Hebrew lost. Swete LXX (PD) sole witness. |
| **2 Maccabees** (2MA) | Greek | **Optimal** | Greek original. Swete LXX (PD). |
| **3 Maccabees** (3MA) | Greek | **Optimal** | Greek original. Swete LXX (PD). |
| **4 Maccabees** (4MA) | Greek | **Optimal** | Greek original. Swete LXX (PD). |
| **Greek Additions to Esther** (ADE) | Greek | **Optimal** | Greek is the original for the additions proper. Swete LXX (PD). |
| **Greek Additions to Daniel** (ADA — Susanna, Bel, Prayer of Azariah, Song of Three) | Greek | **Optimal** | Greek is the original. Swete LXX (PD). |

**Net assessment:** We are at optimal — or within a hair of it — for
the entire deuterocanonical corpus. The only meaningful original-
language gap is Tobit's ~20% Qumran coverage, and the consulted-
reference approach defined below closes most of that gap in practice
without any licensing risk.

## The three zones

Every scholarly source sits in one of three zones with respect to our
pipeline. The zones are defined by how the source influences the
output, not by whether anyone looks at it.

### Zone 1 — Vendored (safe as both reference and Vorlage)

Clean-licensed sources that we can commit into the repository and use
as primary input for translation. Output is free to derive from these.

| Source | License | Location |
|---|---|---|
| Our Swete OCR | CC-BY 4.0 (ours) / source PD | `sources/lxx/swete/final_corpus_adjudicated/` |
| Sefaria Ben Sira (Kahana) | CC0 | `sources/lxx/hebrew_parallels/sefaria_ben_sira.json` |
| Sefaria Tobit (Neubauer 1878) | Public Domain | `sources/lxx/hebrew_parallels/sefaria_tobit.json` |
| WLC (Westminster Leningrad Codex) | Public Domain | `sources/ot/wlc/` |
| Schechter 1899 *Wisdom of Ben Sira* | Public Domain | `sources/hebrew_sirach/schechter_1899/` |
| First1KGreek TEI-XML (validation only) | CC-BY-SA 4.0 | not in repo — consulted |
| Eliran Wong Rahlfs / Amicarelli Swete | NC / GPL (consultation only) | `/tmp/*` — adjudicator reference |

Zone 1 content MAY appear in the prompt context used to generate the
English translation and MAY influence specific word choices.

### Zone 2 — Consulted reference (aware of, not derived from)

Copyrighted or restricted-license scholarly sources that inform our
judgment without appearing in the output. Examples:

- **Fitzmyer, *Discoveries in the Judaean Desert* Vol. XIX (Qumran Tobit)** — reconstructed Aramaic of 4Q196-200
- **Beentjes 1997, *The Book of Ben Sira in Hebrew*** — critical edition of all recovered Hebrew Sirach
- **Skehan & Di Lella 1987, Anchor Bible 39** — English Sirach with critical apparatus
- **Göttingen LXX critical editions** (Hanhart and others)
- **Rahlfs-Hanhart 2006 Stuttgart revised LXX** — reading text
- **Leon Levy DSS Digital Library images** — Qumran photographs

Rules for Zone 2:

1. **Access is legitimate.** A translator (human or AI) may read
   these works, the same way any paid scholarly translator does.
2. **The output must not track the source's creative expression.**
   Specifically: where the Zone 2 source supplies a *reconstruction*
   of missing or damaged text (filled-in letters, chosen readings
   among variants, editorial ordering), our English rendering must
   not word-for-word follow that reconstruction. It may be *informed*
   by it — confirming a reading the LXX also attests, or flagging a
   suggested divergence — but the primary anchor of our English is
   a Zone 1 source.
3. **Fact-level citation is allowed.** Footnotes of the form "Qumran
   4Q196 supports the Long Recension reading here" cite a *fact*
   about what the manuscript attests, not the scholar's creative
   expression. *Feist v. Rural Telephone Service* (1991) establishes
   facts are not copyrightable.
4. **Nothing from Zone 2 is committed to the repository.** Vendoring
   would propagate the source's license to every downstream consumer
   of COB. Consultation is private to the translator's workspace.

### Zone 3 — Forbidden

A small set of sources that we actively avoid consulting:

- **Translations under commercial copyright** (NIV, NLT, ESV). We do
  not consult these — our English must not track their word choices,
  and the cleanest way to avoid derivative-work exposure is to not
  read them during drafting.
- **Sources where the license explicitly prohibits even internal use**
  (none currently).

## How this flows into the translation prompt

The translator agent (AI drafter + human/AI reviser) receives a
structured context per verse. The context includes all Zone 1 and
Zone 2 sources available for that verse, with each labeled by zone.

### Context block shape

```yaml
verse_ref: "SIR 1:1"
zone_1_primary:
  greek:
    source: "Swete LXX (our OCR, CC-BY 4.0)"
    text: "Πᾶσα σοφία παρὰ Κυρίου καὶ μετ᾽ αὐτοῦ ἐστιν εἰς τὸν αἰῶνα."
  hebrew:  # present only for SIR, TOB, and 1ES with MT parallel
    source: "Sefaria Ben Sira / Kahana (CC0)"
    kind: "direct_hebrew"
    text: "כָּל חָכְמָה מֵיהֹוָה, וִעמּוֹ הִיא לְעוֹלָמִים."
    note: "Kahana composite of Cairo Geniza MSS. This is a real Hebrew witness -- treat as primary Vorlage for Sirach."
zone_1_secondary:
  - "First1KGreek (CC-BY-SA): <Greek variant, if any>"
  - "Rahlfs-Hanhart (NC, consultation only): <Greek reading>"
  - "Swete-Amicarelli (GPL, consultation only): <Greek reading>"
zone_2_consult:  # reference only -- do not reproduce or track word-for-word
  - name: "Beentjes 1997"
    book_scope: "SIR"
    guidance: "Critical edition of Hebrew Sirach MSS A-F. Consult if Kahana reading seems wrong or if this verse is in a Kahana gap."
  - name: "Skehan & Di Lella 1987 (Anchor Bible 39)"
    book_scope: "SIR"
    guidance: "English Sirach with critical apparatus. Consult for argued interpretive cruxes -- do NOT track their English phrasing."
instructions_to_translator:
  primacy: >
    For Sirach verses with a direct_hebrew witness, translate from
    the Hebrew (Zone 1 primary hebrew). Use the Greek as a consistency
    check and for verses where the Hebrew is lost/damaged. Where Zone
    2 scholarship suggests a different reading from our Zone 1 Hebrew,
    document the disagreement in the apparatus but keep the output
    anchored in Zone 1.
  forbidden: >
    Do not reproduce word-for-word translations from Zone 2. Footnote
    their conclusions as facts where relevant.
```

For Tobit specifically, the Zone 2 block carries Fitzmyer's DJD XIX
reconstruction of 4Q196-200 where the verse falls in the ~20%
overlap. The translator knows the reconstruction exists, can factor
in its textual-critical verdict, and can note disagreements in
footnotes — but the English output anchors in the LXX Long Recension
(Zone 1 Greek) + Neubauer (Zone 1 Hebrew back-translation).

### Implementation

`tools/hebrew_parallels.py` already returns Zone 1 Hebrew/MT data per
verse. It is extended to also list the Zone 2 sources applicable to
each book, so a translation-phase prompt builder can assemble the
context block mechanically without per-book special-casing.

The translator-prompt builder itself (Phase 9 work, not yet written)
will:

1. Load the Greek verse from `sources/lxx/swete/final_corpus_adjudicated/`
2. Call `hebrew_parallels.lookup(book, ch, vs)` for Zone 1 Hebrew/MT
3. Pull Zone 1 secondary reference readings where available
4. Inject the Zone 2 "consult" block from the book's Zone 2 registry
5. Wrap with the doctrine and style instructions from DOCTRINE.md
6. Call the translator model (GPT-5.4) with the assembled prompt

## Derivative-work exposure — concrete test

Before shipping any verse, the reviser asks three questions:

1. **Anchor:** is the English primarily supported by a Zone 1 source?
2. **Zone 2 independence:** if the Zone 2 reading were redacted from
   the translator's context, would the English still be defensible
   from Zone 1 alone? (This is the "consulted, not derived" test.)
3. **Fact vs. expression:** is anything we *reproduce* from Zone 2
   a fact (manuscript reading, dating, scholarly conclusion) rather
   than creative expression (reconstructed wording, editorial
   phrasing)?

A verse passes if all three answer "yes." A verse that fails gets
re-drafted from Zone 1 alone and re-reviewed.

## Rationale — why this is the right path

**For accuracy.** A translator who consults every leading scholarly
edition produces better work than one who works from a single source.
This is how every serious modern translation is produced (NRSV,
NABRE, Orthodox Study Bible). We match that standard.

**For license cleanliness.** CC-BY 4.0 on our output requires that
output be free to redistribute. Derivative works of Zone 2 sources
are not free to redistribute. The three-zone discipline keeps our
output demonstrably downstream of only Zone 1, while still benefiting
from Zone 2 through consultation.

**For honesty with readers.** Each verse's provenance can be reported
in the per-verse YAML with full disclosure: which Zone 1 sources
anchored the translation, which Zone 2 sources informed it, and
whether any scholarly disagreement is footnoted. Readers can audit
exactly what shaped each rendering.

**For scalability.** The pipeline is mechanical. Zone assignments are
declared once per source; translator prompts assemble automatically;
derivative-work checks are explicit. No ad-hoc judgment per verse.

## Per-book Zone 2 registry

(Maintained alongside this document; may grow as scholarship is
identified.)

| Book | Zone 2 sources |
|---|---|
| SIR | Beentjes 1997; Skehan & Di Lella 1987; Ben-Ḥayyim 1973 |
| TOB | Fitzmyer 1995 (DJD XIX); Moore 1996 (Anchor Bible 40A) |
| JDT | Moore 1985 (Anchor Bible 40) |
| WIS | Winston 1979 (Anchor Bible 43) |
| BAR | Moore 1977 (Anchor Bible 44) |
| LJE | Moore 1977 (Anchor Bible 44) |
| 1MA | Goldstein 1976 (Anchor Bible 41) |
| 2MA | Goldstein 1983 (Anchor Bible 41A) |
| 3MA | NETS (Wright); Emmet 1913 |
| 4MA | Hadas 1953; deSilva 2006 |
| ADE | Moore 1977 (Anchor Bible 44) |
| ADA (Susanna/Bel/Pr Azariah/Song of Three) | Moore 1977 (Anchor Bible 44) |
| 1ES | Myers 1974 (Anchor Bible 42); Talshir 2001 (SBL) |
| All LXX books | Göttingen LXX critical editions; Rahlfs-Hanhart 2006 |

These are for *private consultation* during translation, cited by name
in footnotes where their fact-level conclusions matter, and never
reproduced in COB output.
