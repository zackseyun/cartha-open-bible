# Didache source PDFs — manifest

These PDFs are kept local and **not committed** to git. This manifest
records the expected files, sizes, and SHA-256 hashes so a fresh
checkout can rehydrate them.

Scope and strategy: [`../../DIDACHE.md`](../../DIDACHE.md).

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Archive.org identifier |
|---|---|---|---:|---|---|
| `scans/hitchcock_brown_1884.pdf` | Hitchcock & Brown, *Teaching of the Twelve Apostles* | 1884 | 3,190,201 | `33616035c2b9d8d5ba026d010ca9e5dde4ab2a8d023a162b5d63fde451d67327` | `teachingoftwelve00hitc` |
| `scans/schaff_1885_oldest_church_manual.pdf` | Schaff, *The Oldest Church Manual* | 1885 | 9,715,451 | `a2b8020106238aaab0df0f8a364096f3d33d3d22ff3c25e9f507312bafc9a3c1` | `oldestchurchman00schagoog` |

## How to rehydrate

```bash
cd sources/didache
mkdir -p scans
curl -fsSL -o scans/hitchcock_brown_1884.pdf \
  'https://archive.org/download/teachingoftwelve00hitc/teachingoftwelve00hitc.pdf'
curl -fsSL -o scans/schaff_1885_oldest_church_manual.pdf \
  'https://archive.org/download/oldestchurchman00schagoog/oldestchurchman00schagoog.pdf'

shasum -a 256 scans/*.pdf
```
