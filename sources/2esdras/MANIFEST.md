# 2 Esdras source PDFs — manifest

Following the precedent set by `sources/lxx/swete/MANIFEST.md`, the
full source-edition PDFs are **not committed** to git (too large,
and they are public-domain editions anyone can retrieve). This file
records the expected files and their SHA-256 hashes so a fresh
checkout can verify authenticity after re-downloading.

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Archive.org identifier |
|---|---|---|---:|---|---|
| `latin/bensly_1875_missing_fragment.pdf` | Bensly, *The Missing Fragment of the Latin Translation of the Fourth Book of Ezra* | 1875 | 6,010,084 | `d4c690e01ac2ffcebcdb94a1a02aa242fe76c060c8c4aa1f2038e393adf60c67` | `missingfragmento00bensuoft` |
| `scans/textsandstudies_v3.pdf` | *Texts and Studies: Contributions to Biblical and Patristic Literature*, Vol. III (contains Bensly/James 1895 *Fourth Book of Ezra* at issue 2) | 1895 | 16,637,761 | `1748e59beed0e92193d0cda8f4934631918738d011f46bc882ee6a9aab206942` | `textsandstudies203unknuoft` |
| `scans/violet_1910_vol1.pdf` | Violet, *Die Esra-Apokalypse (IV. Esra), Erster Teil: Die Überlieferung* (GCS 18) | 1910 | 41,997,222 | `4b023b11eb59e47561abeafd32d7e3698f4cbd4160d80d1a9490ebc0deded6f5` | `dieesraapokalyps01viol` |
| `scans/violet_1910_vol2.pdf` | Violet, GCS 18 Zweiter Teil | 1910 | 35,383,432 | `355486c65e4007115b2a65cdf9f5e58c60c78522bf4cc64efa0845e09753c144` | `dieesraapokalyps02violuoft` |

## How to rehydrate on a fresh checkout

```bash
cd sources/2esdras
curl -fsSL -o latin/bensly_1875_missing_fragment.pdf \
  https://archive.org/download/missingfragmento00bensuoft/missingfragmento00bensuoft.pdf
curl -fsSL -o scans/textsandstudies_v3.pdf \
  https://archive.org/download/textsandstudies203unknuoft/textsandstudies203unknuoft.pdf
curl -fsSL -o scans/violet_1910_vol1.pdf \
  https://archive.org/download/dieesraapokalyps01viol/dieesraapokalyps01viol.pdf
curl -fsSL -o scans/violet_1910_vol2.pdf \
  https://archive.org/download/dieesraapokalyps02violuoft/dieesraapokalyps02violuoft.pdf

# Verify
shasum -a 256 latin/*.pdf scans/*.pdf
```

All files are Public Domain (pre-1929 US publications or author-expired
copyrights). Redistribution is permitted without attribution under any
framework; we cite them in the translation provenance nonetheless.

## License

See `../../REFERENCE_SOURCES.md` (Zone 1 policy) for how these sources
flow into the translation pipeline. In brief: PD source → our own
fresh OCR + vendored-licensed commits under CC-BY 4.0. The scanned
page images themselves are not redistributed here; only our derived
transcriptions and per-verse renderings will enter the repo.
