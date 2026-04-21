# 1 Clement source PDFs — manifest

Source scope: [`README.md`](README.md)

The local PDF scans are **not committed**. This file records the
expected files currently present in the workspace.

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Notes |
|---|---|---:|---:|---|---|
| `scans/lightfoot_1889_1clement.pdf` | J. B. Lightfoot, *The Apostolic Fathers* (1 Clement volume) | 1889 | 48,831,213 | `f7050157bbcc48fc5a19c45656038b53a94f84710bd83b13e66237f0bee51209` | Internet Archive item visible in PDF metadata: `apostolicfathep2v1clemuoft` |
| `scans/funk_1901_patres_apostolici.pdf` | Franz Xaver Funk, *Patres apostolici* | 1901 | 26,096,952 | `3e2bd8f4dc99487daa8bfe399e65a93f1e19546ae2d678cba674303626f49a00` | Google Books PDF |

## Verification

```bash
shasum -a 256 sources/1_clement/scans/*.pdf
```
