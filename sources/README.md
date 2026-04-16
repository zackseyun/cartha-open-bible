# Source Texts

All source texts used by the Cartha Translation are vendored in this
directory with their original licenses preserved. No source text is
modified — any necessary normalization happens in downstream processing
under `tools/`.

## Vendored sources

### SBLGNT — Greek New Testament
- **Full name:** *The Greek New Testament: SBL Edition*
- **Editor:** Michael W. Holmes
- **Publisher:** Society of Biblical Literature / Logos Bible Software
- **Date:** 2010
- **License:** Creative Commons Attribution 4.0 International (CC-BY 4.0)
- **Source URL:** https://sblgnt.com/ (canonical distribution)
- **Directory:** `nt/sblgnt/`
- **Required attribution:** The SBLGNT is edited by Michael W. Holmes, who
  utilized a wide range of printed editions, all the major critical
  apparatuses, and the latest technical resources and manuscript discoveries
  as he established the text. The result is a critically edited text that
  differs from the Nestle-Aland/United Bible Societies text in more than
  540 variation units.

### Westminster Leningrad Codex (WLC)
- **Full name:** Transcription of the Leningrad Codex (B19A)
- **Maintainer:** J. Alan Groves Center for Advanced Biblical Research
- **Date:** Ongoing (based on the 1008 AD manuscript)
- **License:** Open transcription; see vendored license file
- **Source URL:** https://www.tanach.us/
- **Directory:** `ot/wlc/`
- **Note:** Oldest complete Hebrew Bible manuscript. Includes full vowels
  and cantillation marks.

### unfoldingWord Hebrew Bible (UHB)
- **Full name:** unfoldingWord Hebrew Bible
- **Maintainer:** unfoldingWord
- **License:** Creative Commons Attribution-ShareAlike 4.0 International
  (CC-BY-SA 4.0)
- **Source URL:** https://git.door43.org/unfoldingWord/hbo_uhb
- **Directory:** `ot/uwhb/`
- **Note:** Based on WLC with comprehensive morphological tagging that
  makes it easier for automated parsing.

### Rahlfs Septuagint (LXX)
- **Full name:** *Septuaginta*
- **Editor:** Alfred Rahlfs
- **Publisher:** Württembergische Bibelanstalt
- **Date:** 1935 (original); subsequent editions available but 1935 is the
  public domain reference
- **License:** Public domain (1935 edition)
- **Source URL:** https://github.com/Septuagint/lxx (digital transcriptions)
- **Directory:** `lxx/rahlfs/`
- **Note:** Used for cross-reference to NT quotations of the OT. Not a
  primary translation source, but essential context for understanding
  NT authors' quotation patterns.

## How sources are used

The Cartha Translation translates from:
- **NT**: SBLGNT primary
- **OT**: WLC primary, UHB for morphological parsing
- **Cross-reference**: Rahlfs LXX where NT authors quote the Greek OT

Each verse YAML in `translation/` records which source(s) it drew from
by the `edition` enum in `source` (see `schema/verse.schema.json`).

## License compatibility

All sources are either public domain or under permissive licenses
(CC-BY 4.0, CC-BY-SA 4.0) that are compatible with our output license
(CC-BY 4.0). No source imposes downstream restrictions that would
limit the Cartha Translation's adoption.

Note that unfoldingWord Hebrew Bible is CC-BY-SA 4.0, which has a
share-alike clause. This affects direct re-distribution of UHB itself
(which would need to remain CC-BY-SA), but **does not affect** our
translation output — a translation is a new creative work, not a
derivative in the share-alike-triggering sense.

## Vendoring procedure

Source texts are vendored (copied in) rather than referenced as git
submodules. Rationale:
- Full auditability — anyone cloning the repo has everything they need
  to verify the translation without separate network fetches.
- Stability — upstream repos can disappear or change.
- Reproducibility — `tools/verify.py` depends on exact byte-level source
  text.

To update a source to a newer version, the update is itself a git commit
with a clear message documenting what changed and why.
