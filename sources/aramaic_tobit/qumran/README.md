# Aramaic (and Hebrew) Tobit — Qumran Fragments

Tobit was composed in Aramaic (with some scholars arguing Hebrew)
sometime between 225–175 BC. The original Aramaic/Hebrew text was
lost for nearly two millennia; the Greek LXX translation became the
operative witness.

In 1952 the caves at Qumran yielded fragmentary Aramaic and Hebrew
manuscripts of Tobit:

- **4Q196** (papyrus, Aramaic) — 4QpapToba ar
- **4Q197** (parchment, Aramaic) — 4QTobb ar
- **4Q198** (parchment, Aramaic) — 4QTobc ar
- **4Q199** (parchment, Aramaic) — 4QTobd ar
- **4Q200** (parchment, Hebrew) — 4QTobe

Together these fragments cover approximately 20% of Tobit and
decisively support the Long Recension (Codex Sinaiticus) Greek text
over the Short Recension (Codex Vaticanus, Codex Alexandrinus).

## Current source status

The surviving photographs of the Qumran Tobit fragments are held
under restrictive license terms that are not compatible with direct
CC-BY inclusion. Our current working source for Tobit is therefore
**Swete's LXX Greek** (`../../lxx/swete/`), specifically the Long
Recension preserved in Codex Sinaiticus. This is what NRSV, NABRE,
and Orthodox Study Bible also use as their primary text for Tobit.

Where published scholarship has reached factual textual-critical
conclusions about what the Qumran fragments attest, we cite those
conclusions in footnotes — which is fact-level citation, not
reproduction of creative expression (*Feist v. Rural*, 1991). A
typical footnote form:

> *"Qumran 4Q196 supports the Long Recension reading here."*

We do not reproduce scholars' transcriptions of the fragments in
our published output.

If cleaner access to the Qumran Aramaic/Hebrew becomes available
later, the ~20% of Tobit verses those fragments cover will be
upgraded transparently. Until then, every verse is translated from
the Greek with its provenance clearly marked.

### Licensing confirmed blocked — 2026-04-20

Re-checked the IAA Leon Levy Dead Sea Scrolls Digital Library
terms: text and images "may not be reproduced, displayed, modified
or distributed in any form" without written permission. Same
situation as Masada Sirach. The principal scholarly transcription
(Fitzmyer, DJD XIX, 1995) is likewise under commercial copyright.
**No clean-licensed path to the Qumran Aramaic Tobit exists as of
this date.** We continue with Swete Greek (Long Recension via
TOB_S / Codex Sinaiticus) as the working source.

### Fallback Hebrew witness now vendored

Adolf Neubauer's *The Book of Tobit: A Chaldee Text...* (Oxford:
Clarendon, 1878) includes a Hebrew back-translation from the
Aramaic Munich MS he edited. It is Public Domain (Neubauer d.
1907) and is hosted by Sefaria. We have vendored it at
`../../lxx/hebrew_parallels/sefaria_tobit.json` (76 verses,
100% Hebrew coverage). This is **not an ancient witness** — it is
a 19th-century scholarly reconstruction — and it is marked
accordingly by `tools/hebrew_parallels.py` as `kind:
indirect_hebrew`. Use it for proper names, idiom checks, and
Semitic-flavor phrasing during the translation phase; do NOT
treat it as a Vorlage.

## Reconstruction caveat

The Qumran Tobit fragments are small and heavily reconstructed by
specialist scholarship. Under *Qimron v. Shanks* (Israeli Supreme
Court, 2000), creative scholarly reconstructions of damaged Dead
Sea Scroll texts can carry copyright. Even if we had access to the
photographs, our policy would be to transcribe only what is legibly
present on the physical fragment and mark lacunae as lacunae — not
to generate or reproduce reconstructions of missing letters. This
keeps us clearly clear of reconstruction-copyright concerns and is
also the more honest scholarly posture.
