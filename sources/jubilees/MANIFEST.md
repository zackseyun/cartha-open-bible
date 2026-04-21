# Jubilees source PDFs — manifest

Following the precedent of `sources/lxx/swete/MANIFEST.md`,
`sources/2esdras/MANIFEST.md`, and `sources/enoch/MANIFEST.md`: full
PDFs are **not committed** to git. SHA-256 hashes recorded here for
verification.

Scope and strategy: [`../../JUBILEES.md`](../../JUBILEES.md).

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Archive.org identifier |
|---|---|---|---:|---|---|
| `scans/charles_1895_ethiopic.pdf` | Charles, *The Ethiopic Version of the Hebrew Book of Jubilees* (Oxford, Anecdota Oxoniensia Semitic Series I.viii) | 1895 | 10,339,546 | `2883e2c68247c2b3172467bfaaa9147901a6b88b18f28e5ad3a7cc2c20636dfe` | `CharlesEthiopicJubilees` |
| `scans/charles_1902_english.pdf` | Charles, *The Book of Jubilees, or The Little Genesis* (London: Black) | 1902 | 11,259,940 | `c2815f886f575101831c08b67a024f3978d12da41c06a5c7f8261dbaee697a29` | `TheBookOfJubileesOrTheLittleGenesisTranslatedFromTheEditorsEthiopocTextByRHCharles1902` |
| `scans/dillmann_ronsch_1874_composite.pdf` | Dillmann & Rönsch, *Das Buch der Jubiläen oder die kleine Genesis* (Leipzig) — Dillmann's German translation + Rönsch's critical Latin fragments | 1874 | 43,878,057 | `8fcd5b5e9b67e0623bd11d98a3a8fe7891913c768fad25f6ab4ac966f92c48c1` | `dasbuchderjubile00dill` |

## How to rehydrate

```bash
cd sources/jubilees
mkdir -p scans
curl -fsSL -o scans/charles_1895_ethiopic.pdf \
  "https://archive.org/download/CharlesEthiopicJubilees/The_Ethiopic_version_of_the_Hebrew_Book.pdf"
curl -fsSL -o scans/charles_1902_english.pdf \
  "https://archive.org/download/TheBookOfJubileesOrTheLittleGenesisTranslatedFromTheEditorsEthiopocTextByRHCharles1902/The%20Book%20of%20Jubilees%2C%20or%2C%20The%20Little%20Genesis%20Translated%20from%20the%20Editors%20Ethiopoc%20Text%20by%20R%20H%20Charles%201902.pdf"
curl -fsSL -o scans/dillmann_ronsch_1874_composite.pdf \
  "https://archive.org/download/dasbuchderjubile00dill/dasbuchderjubile00dill.pdf"

shasum -a 256 scans/*.pdf
```

All files are Public Domain (pre-1929 US publications, long-deceased
authors — Charles d. 1931, Dillmann d. 1894, Rönsch d. 1888).

## License

Our derived transcriptions (Gemini OCR of Charles 1895 Ge'ez +
Rönsch Latin, validated against Dillmann-Rönsch 1874) will be
published under CC-BY 4.0 as the Zone 1 primary for COB Jubilees.
