# Vertex Coptic OCR full-run summary — 2026-04-22

- Model: `gemini-3.1-pro-preview`
- Backend: Vertex AI
- Standard crop box: `0.16,0.03,0.84,0.97`
- Standard band count: `6` (with targeted higher-band reruns on edge pages where needed)
- Parallel mode: `run_parallel_coptic_ocr.py`

## Operational notes

- Gospel of Truth ran successfully across both Vertex credentials.
- Thunder, Perfect Mind staging succeeded across the facsimile page set, but production OCR used `/cartha/vertex/gemini-sa-2` after `/cartha/vertex/gemini-sa` returned a billing 403 during Thunder smoke testing.
- Gospel of Truth page 16 and page 43 are tractate-boundary edge cases; Thunder has one analogous edge page with a single `MAX_TOKENS` region.

## Corpus totals

### gospel_of_truth

- Witness: `nhc_i_3_facsimile_primary`
- Pages OCRed: `25`
- Total output chars: `36796`
- Finish counts: `{'STOP': 23, 'STOP+STOP+STOP+STOP+STOP+STOP+MAX_TOKENS+STOP+STOP+STOP': 1, 'STOP+STOP+STOP+STOP+STOP+MAX_TOKENS+STOP+STOP+STOP+STOP': 1}`

### thunder_perfect_mind

- Witness: `nhc_vi_2_facsimile_primary`
- Pages OCRed: `9`
- Total output chars: `14276`
- Finish counts: `{'STOP': 8, 'STOP+STOP+STOP+STOP+MAX_TOKENS+STOP': 1}`
