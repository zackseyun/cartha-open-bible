# Didache source PDFs — manifest

Source scope: [`README.md`](README.md)

The local PDF scans are **not committed**. This file records the
expected files currently present in the workspace.

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Notes |
|---|---|---:|---:|---|---|
| `scans/hitchcock_brown_1884.pdf` | Hitchcock & Brown, *Διδαχὴ τῶν δώδεκα ἀποστόλων / Teaching of the Twelve Apostles* | 1884 | 3,190,201 | `33616035c2b9d8d5ba026d010ca9e5dde4ab2a8d023a162b5d63fde451d67327` | Internet Archive item visible in PDF metadata: `teachingoftwelve00hitc` |
| `scans/schaff_1885_oldest_church_manual.pdf` | Philip Schaff, *The Oldest Church Manual Called The Teaching of the Twelve Apostles* | 1885 | 9,715,451 | `a2b8020106238aaab0df0f8a364096f3d33d3d22ff3c25e9f507312bafc9a3c1` | Google Books PDF |

## Verification

```bash
shasum -a 256 sources/didache/scans/*.pdf
```
