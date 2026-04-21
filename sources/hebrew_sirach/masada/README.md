# Masada Ben Sira Scroll (Mas1h)

The Masada Ben Sira scroll, discovered in the 1964 excavation of
Masada, contains approximately **Sirach 39:27–43:30** in
pre-medieval Hebrew (c. 100 BC). It is the oldest Hebrew witness to
Ben Sira by roughly a millennium and the most important single
source for Hebrew Sirach outside the Cairo Genizah.

## Current source status

The surviving high-resolution photographs of the Masada scroll are
held under restrictive license terms that are not compatible with
direct CC-BY inclusion. Our current working source for this passage
is **Swete's LXX Greek** (`../../lxx/swete/`), which for Sirach is the
grandson's c. 132 BC translation and is the operative text for every
major modern translation that includes the Apocrypha.

Where Cairo Genizah **MS B** covers Masada content (much of the
39:27–43:30 range), the Hebrew Genizah text remains available to us
as Phase 2 primary source via Schechter 1899 and later
public-domain publications.

If cleaner access to the pre-medieval Hebrew becomes available
later, the Sirach 39:27–43:30 source layer will be upgraded
transparently, with every per-verse YAML updated in place and
attributed to its new primary source.

Until then, the front-matter of Sirach in COB flags this passage as
"primary source: Greek (Swete LXX); pre-medieval Hebrew witness
exists but is not in our current source pipeline" so readers are
not misled about what text underlies the translation.

## Yadin 1965 — editio princeps consulted as Zone 2

Yigael Yadin's *The Ben Sira Scroll from Masada* (Jerusalem: Israel
Exploration Society, 1965) is the editio princeps of this scroll.
It remains copyrighted (Yadin died 1984; IL copyright runs to 2054)
and is not vendored into this repository.

Per [REFERENCE_SOURCES.md](../../../REFERENCE_SOURCES.md) Zone 2
policy, we treat Yadin as **consulted reference only**:

- A local-only extraction of the book lives outside the repo at
  `~/cartha-reference-local/yadin_1965/` on machines with legitimate
  access. The scaffold in `tools/yadin_masada.py` silently reports
  unavailable on clean checkouts.
- `tools/hebrew_parallels.lookup_with_consult('SIR', ch, vs)`
  surfaces Masada-scroll Hebrew + Yadin's column-level apparatus in
  the translator prompt for verses in Sir 39:27–44:17 (and Sir
  51:13–30, the acrostic poem fragment).
- Yadin's **Hebrew transcription** of the physical letters on the
  scroll is reference data the translator sees. Bracketed
  reconstructions `[...]` are preserved as-marked so the translator
  distinguishes what Yadin read directly from what he reconstructed.
- Yadin's **English translation** is deliberately excluded from the
  translator prompt context. We do not track his English word-for-
  word; our output must be our own fresh rendering.
- Where Masada and Cairo Genizah MS B disagree on a reading,
  Masada typically wins on textual-critical grounds (1st c. BC vs.
  10th c. AD). Such divergences are noted in COB footnotes at
  fact level — *"Masada scroll reads X where MS B reads Y"* — which
  is uncopyrightable fact citation under *Feist v. Rural* (1991),
  not reproduction of Yadin's creative apparatus.

Yadin's edition is dated (1965); more recent scholarly editions
(Ben-Ḥayyim 1973, Beentjes 1997) incorporate later re-examinations
of the scroll and reconcile it against the growing Geniza corpus.
Those later works are also Zone 2. For the core editio-princeps
task of reading what the scroll says, Yadin remains canonical and
is what every subsequent edition cites.

## Revision when IAA access opens

If direct IAA photographic access to the Masada scroll is granted
later (see `REVISION_LATER.md`), the ~150 affected Sirach verses
will be re-drafted with the scroll images as Zone 1 (vendored,
derivable). At that point Yadin demotes from "our only Masada
witness" to "one among several" — but his scholarly apparatus
remains useful as Zone 2 consult indefinitely.
