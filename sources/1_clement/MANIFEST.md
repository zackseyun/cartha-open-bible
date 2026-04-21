# 1 Clement source PDFs — manifest

These PDFs are kept local and **not committed** to git. This manifest
records the expected files, sizes, and SHA-256 hashes so a fresh
checkout can rehydrate them.

Scope and strategy: [`../../FIRST_CLEMENT.md`](../../FIRST_CLEMENT.md).

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Archive.org identifier |
|---|---|---|---:|---|---|
| `scans/lightfoot_1889_1clement.pdf` | Lightfoot, *The Apostolic Fathers* (1 Clement volume) | 1889 | 48,831,213 | `f7050157bbcc48fc5a19c45656038b53a94f84710bd83b13e66237f0bee51209` | `apostolicfathep2v1clemuoft` |
| `scans/funk_1901_patres_apostolici.pdf` | Funk, *Patres Apostolici* | 1901 | 26,096,952 | `3e2bd8f4dc99487daa8bfe399e65a93f1e19546ae2d678cba674303626f49a00` | `patresapostolic00piongoog` |

## How to rehydrate

```bash
cd sources/1_clement
mkdir -p scans
curl -fsSL -o scans/lightfoot_1889_1clement.pdf \
  'https://archive.org/download/apostolicfathep2v1clemuoft/apostolicfathep2v1clemuoft.pdf'
curl -fsSL -o scans/funk_1901_patres_apostolici.pdf \
  'https://archive.org/download/patresapostolic00piongoog/patresapostolic00piongoog.pdf'

shasum -a 256 scans/*.pdf
```
