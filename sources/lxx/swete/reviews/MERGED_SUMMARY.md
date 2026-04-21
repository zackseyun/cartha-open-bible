# Merged GPT-5.4 + Gemini review summary

**Generated:** 2026-04-20 04:50 UTC

Pages with both GPT-5.4 + Gemini reviews: **99**

## Cross-model agreement

- **Agreed corrections (high signal):** 503
- **GPT-5.4-only (Gemini did not flag):** 650
- **Gemini-only (GPT-5.4 did not flag):** 1903

Agreed corrections are the highest-confidence items: two independent
vision models (GPT-5.4, Gemini 2.5 Pro) flagged essentially the same
fix. These should be auto-applied.

GPT-5.4-only and Gemini-only items represent *possible* real errors
that one model missed. These need human adjudication or a 
third-opinion pass.

## By Gemini scope

| Scope | Pages | GPT-5.4 items | Gemini items | Agreed | GPT-5.4-only | Gemini-only |
|---|---:|---:|---:|---:|---:|---:|
| `gemini_esdras` | 44 | 568 | 1261 | 255 | 313 | 1006 |
| `gemini_tobit` | 31 | 337 | 627 | 128 | 209 | 499 |
| `gemini_wer` | 24 | 248 | 518 | 120 | 128 | 398 |

## Pages with most Gemini-only flags (possible GPT-5.4 misses)

- `vol3_p0902` — gemini_only=74 (azure_total=5, gemini_total=77)
- `vol2_p0160` — gemini_only=58 (azure_total=27, gemini_total=72)
- `vol2_p0177` — gemini_only=58 (azure_total=16, gemini_total=61)
- `vol2_p0181` — gemini_only=51 (azure_total=21, gemini_total=59)
- `vol2_p0176` — gemini_only=45 (azure_total=10, gemini_total=51)
- `vol2_p0168` — gemini_only=42 (azure_total=29, gemini_total=53)
- `vol2_p0170` — gemini_only=40 (azure_total=19, gemini_total=51)
- `vol2_p0843` — gemini_only=40 (azure_total=11, gemini_total=47)
- `vol2_p0849` — gemini_only=39 (azure_total=11, gemini_total=44)
- `vol2_p0153` — gemini_only=32 (azure_total=9, gemini_total=36)
- `vol2_p0155` — gemini_only=32 (azure_total=19, gemini_total=39)
- `vol2_p0189` — gemini_only=31 (azure_total=11, gemini_total=33)
- `vol2_p0159` — gemini_only=28 (azure_total=22, gemini_total=40)
- `vol2_p0161` — gemini_only=28 (azure_total=6, gemini_total=32)
- `vol2_p0178` — gemini_only=28 (azure_total=24, gemini_total=40)
