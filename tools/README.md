# Tools

Python scripts for drafting, cross-checking, verifying, signing, and
linting the Cartha Open Bible.

## Scripts

- `draft.py` — Feeds source-text verse + methodology prompt to a primary
  LLM, produces draft YAML with provenance metadata.
- `cross_check.py` — Runs draft against Claude Opus 4.7, GPT-5, and
  Gemini 2.5 Pro in parallel. Scores agreement. Flags divergences.
- `verify.py` — Re-runs the documented pipeline for a given verse.
  Confirms AI draft reproduces, cross-check reproduces, signature
  validates, reviewer is in `REVIEWERS.md`.
- `consistency_lint.py` — Checks internal consistency across the full
  translation. Flags undocumented lexical variance, missing signatures,
  missing citations.
- `sign.py` — Generates ed25519 signatures for reviewer sign-off.
  Reviewer private key stays local; only public key + signature go
  in the repo.

## Prerequisites

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Required environment variables:

```
ANTHROPIC_API_KEY=...    # for Claude drafting
OPENAI_API_KEY=...       # for GPT cross-check
GOOGLE_API_KEY=...       # for Gemini cross-check
```

## Status

Scripts are skeletons pending implementation. See individual files and
METHODOLOGY.md for specification.
