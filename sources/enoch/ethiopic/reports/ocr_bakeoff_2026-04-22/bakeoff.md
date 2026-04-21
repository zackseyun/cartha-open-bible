# Ge'ez OCR bake-off — run 2026-04-22

- Scan: `sources/enoch/scans/charles_1906_ethiopic.pdf` page **40** @ **400 DPI**
- Truth: `charles_1906` chapter 1 verses 1–5 (**398** normalized chars)

## Scoreboard

| Engine | Model | Accuracy vs scan-truth | Distance | Chars out | Thinking tokens | Duration | Finish |
|---|---|---:|---:|---:|---:|---:|---|
| `gemini-3.1-pro` | `gemini-3.1-pro-preview` | **80.15%** | 79 | ? | 0 | 7.23s | STOP |
| `gemini-2.5-pro` | `gemini-2.5-pro` | **65.33%** | 138 | ? | 561 | 13.23s | STOP |
| `azure-gpt-5.4` | `gpt-5.4-2026-03-05` | **46.48%** | 213 | ? | 0 | 21.67s | stop |

## azure-gpt-5.4 — gpt-5.4-2026-03-05
- Accuracy: **46.48%** (distance 213)
- Finish: `stop` — 21.67s — thinking tokens 0

Sample disagreements:
- `replace` — OCR `በ` vs truth `ዘ`
- `replace` — OCR `ይከው` vs truth `ሀለው፡ይኩ`
- `replace` — OCR `ሎ፡ኃጥኣ` vs truth `ሉ፡እኩያ`
- `replace` — OCR `ሱ` vs truth `ሲ`
- `replace` — OCR `ን` vs truth `ው`

## gemini-3.1-pro — gemini-3.1-pro-preview
- Accuracy: **80.15%** (distance 79)
- Finish: `STOP` — 7.23s — thinking tokens 0

Sample disagreements:
- `replace` — OCR `በ` vs truth `ዘ`
- `replace` — OCR `ዉ` vs truth `ው`
- `replace` — OCR `ሎ፡እኩያነ` vs truth `ሉ፡እኩያን`
- `replace` — OCR `ነ፡` vs truth `ን።`
- `replace` — OCR `እምኀበ` vs truth `አንሥኦ`

## gemini-2.5-pro — gemini-2.5-pro
- Accuracy: **65.33%** (distance 138)
- Finish: `STOP` — 13.23s — thinking tokens 561

Sample disagreements:
- `replace` — OCR `ዉ፡ይከዉ` vs truth `ው፡ይኩ`
- `replace` — OCR `ን` vs truth `ው`
- `delete` — OCR `፡ምሳሌሁ` vs truth ``
- `replace` — OCR `ኀበ` vs truth `አንሥኦ`
- `replace` — OCR `ግዚእ` vs truth `ንዘ`
