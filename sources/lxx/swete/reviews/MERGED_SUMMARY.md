# Merged Azure + Gemini review summary

**Generated:** 2026-04-20 04:33 UTC

Pages with both Azure + Gemini reviews: **90**

## Cross-model agreement

- **Agreed corrections (high signal):** 432
- **Azure-only (Gemini did not flag):** 570
- **Gemini-only (Azure did not flag):** 1545

Agreed corrections are the highest-confidence items: two independent
vision models (GPT-5.4, Gemini 2.5 Pro) flagged essentially the same
fix. These should be auto-applied.

Azure-only and Gemini-only items represent *possible* real errors
that one model missed. These need human adjudication or a 
third-opinion pass.

## By Gemini scope

| Scope | Pages | Azure items | Gemini items | Agreed | Azure-only | Gemini-only |
|---|---:|---:|---:|---:|---:|---:|
| `gemini_esdras` | 38 | 444 | 976 | 199 | 245 | 777 |
| `gemini_tobit` | 30 | 326 | 580 | 121 | 205 | 459 |
| `gemini_wer` | 22 | 232 | 421 | 112 | 120 | 309 |

## Pages with most Gemini-only flags (possible Azure misses)

- `vol2_p0181` — gemini_only=51 (azure_total=21, gemini_total=59)
- `vol2_p0176` — gemini_only=45 (azure_total=10, gemini_total=51)
- `vol2_p0170` — gemini_only=40 (azure_total=19, gemini_total=51)
- `vol2_p0849` — gemini_only=39 (azure_total=11, gemini_total=44)
- `vol2_p0153` — gemini_only=32 (azure_total=9, gemini_total=36)
- `vol2_p0155` — gemini_only=32 (azure_total=19, gemini_total=39)
- `vol2_p0189` — gemini_only=31 (azure_total=11, gemini_total=33)
- `vol2_p0161` — gemini_only=28 (azure_total=6, gemini_total=32)
- `vol2_p0178` — gemini_only=28 (azure_total=24, gemini_total=40)
- `vol2_p0844` — gemini_only=27 (azure_total=6, gemini_total=31)
- `vol3_p0672` — gemini_only=27 (azure_total=11, gemini_total=33)
- `vol2_p0175` — gemini_only=26 (azure_total=14, gemini_total=34)
- `vol2_p0191` — gemini_only=26 (azure_total=10, gemini_total=32)
- `vol2_p0784` — gemini_only=26 (azure_total=2, gemini_total=27)
- `vol2_p0819` — gemini_only=26 (azure_total=10, gemini_total=29)
