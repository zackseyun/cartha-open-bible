# Rahlfs Septuagint (LXX) — Zone 2 consultation only

**Status: NOT vendored. Used as Zone 2 consult-only reference.**

This directory is intentionally empty of source text. Earlier plans
called for vendoring a CC-BY digital transcription of the 1935
Rahlfs Septuagint here; that plan was abandoned in Phase 8 after
field research (2026-04-18) confirmed that every digital Rahlfs
edition is either CC-BY-NC, CC-BY-SA-derived-from-NC, or restrictive
(CCAT). No CC-BY-compatible Rahlfs exists.

## What we do instead

Our LXX source is **Swete 1909–1930** (fully public domain;
[`../swete/`](../swete/)), which we transcribe ourselves via AI
vision and release under CC-BY 4.0. Swete covers every LXX book
we need, including the entire deuterocanon.

**Rahlfs is still consulted as a Zone 2 reference** during
adjudication of uncertain readings — see
[`../../../REFERENCE_SOURCES.md`](../../../REFERENCE_SOURCES.md)
for the three-zone policy, and
[`../../../tools/rahlfs.py`](../../../tools/rahlfs.py) for the
consultation parser (which reads Eliran Wong's NC-licensed
digitization from `/tmp/rahlfs-ref/`, never committed to this
repo). The adjudicator (`tools/adjudicate_corpus.py`) compares our
Swete OCR against Rahlfs among several other witnesses; Rahlfs
readings never flow into our corpus output, only into our
confidence judgments.

## NT cross-reference use case

An earlier version of this README described a planned NT
cross-reference use case (flagging LXX-vs-MT differences in NT
quotations, e.g. Matthew 1:23 / Isaiah 7:14 παρθένος vs עַלְמָה).
That use case is still valid in principle, but for translation
purposes it is handled by fact-level citation in footnotes
(*Feist v. Rural* 1991 — facts aren't copyrightable), not by
vendoring a full Rahlfs text. Footnote form:
*"The NT quotation follows the LXX reading, which differs from the
Hebrew here."*

## If a clean Rahlfs ever appears

If STEPBible's announced TAGOT ships with a CC-BY license, or if
another clean-licensed Rahlfs appears, this directory can be
populated and the policy re-evaluated. Until then: Swete is
primary, Rahlfs is consultation-only.
