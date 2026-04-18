#!/usr/bin/env python3
"""
cross_check.py — Run a verse draft through Claude, GPT, and Gemini in
parallel, compute agreement scores, and surface divergences.

Pipeline stage 3 of the Cartha Open Bible methodology. Takes a verse
YAML produced by draft.py and augments it with cross-check results.

Usage:

    python tools/cross_check.py translation/nt/philippians/001/001.yaml

Environment:

    ANTHROPIC_API_KEY        required for Claude
    OPENAI_API_KEY           required for GPT
    GOOGLE_API_KEY           required for Gemini

Agreement thresholds (per METHODOLOGY.md Stage 3):
- >= 0.90: draft proceeds with divergences noted as alternatives.
- 0.75-0.90: divergences surfaced as footnotes.
- <  0.75: disagreement escalated into a public GitHub issue.

This skeleton is intentionally functional but unimplemented — wiring up
OpenAI + Google SDKs with the same tool schema pattern used in draft.py,
then scoring agreement via normalized edit distance on english_text
plus Jaccard overlap on lexical_decisions, is tracked as a follow-up.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "cross_check.py is not yet implemented. "
        "See METHODOLOGY.md Stage 3 for the spec. "
        "The follow-up task is tracked as #13 (Build draft pipeline).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
