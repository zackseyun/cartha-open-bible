# Vertex Coptic OCR smoke test — 2026-04-22

- Backend: Vertex AI
- Model: `gemini-3.1-pro-preview`
- Credentials tested: `/cartha/vertex/gemini-sa`, `/cartha/vertex/gemini-sa-2`

## truth_fragment_page59

- Cross-credential similarity: `0.7021`
- `/cartha/vertex/gemini-sa` → project `seventh-hallway-492218-a8`, finish `STOP`, chars `359`, lines `45`, Coptic ratio `0.8245`, reference ratio `0.017`
- `/cartha/vertex/gemini-sa-2` → project `gen-lang-client-0860843968`, finish `STOP`, chars `356`, lines `45`, Coptic ratio `0.8258`, reference ratio `0.017`

## truth_primary_page16

- Cross-credential similarity: `0.1204`
- `/cartha/vertex/gemini-sa` → project `seventh-hallway-492218-a8`, finish `MAX_TOKENS`, chars `5464`, lines `31`, Coptic ratio `0.9689`
- `/cartha/vertex/gemini-sa-2` → project `gen-lang-client-0860843968`, finish `MAX_TOKENS`, chars `5451`, lines `31`, Coptic ratio `0.9721`
