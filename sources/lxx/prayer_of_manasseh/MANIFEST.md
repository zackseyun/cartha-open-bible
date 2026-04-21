# Prayer of Manasseh source PDFs — manifest

PDFs are **not committed** to git (size + reproducibility from PD
archive). This file records hashes for verification on a fresh
checkout.

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Archive.org |
|---|---|---|---:|---|---|
| `scans/charles_1913_apot_vol1.pdf` | R. H. Charles (ed.), *The Apocrypha and Pseudepigrapha of the Old Testament in English*, Vol. 1 | 1913 | 83,353,067 | `3b2f6c382a13ad2c11a1e99e1e05a1a9e6c79db49b7a01f4213080fcf6a754f9` | `theapocryphaandp01unknuoft` |

## Rehydrate

```bash
cd sources/lxx/prayer_of_manasseh
curl -fsSL -o scans/charles_1913_apot_vol1.pdf \
  https://archive.org/download/theapocryphaandp01unknuoft/theapocryphaandp01unknuoft.pdf
shasum -a 256 scans/*.pdf
```

License: Public Domain (US pre-1929 publication; author Robert Henry
Charles d. 1931 — work has entered US PD).
