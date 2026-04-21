# Shepherd of Hermas source PDFs — manifest

Source scope: [`README.md`](README.md)

The local PDF scans are **not committed**. This file records the
expected files currently present in the workspace.

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Notes |
|---|---|---:|---:|---|---|
| `scans/lightfoot_1891_apostolic_fathers.pdf` | J. B. Lightfoot & J. R. Harmer, *The Apostolic Fathers* (revised texts; includes the Shepherd of Hermas) | 1891 | 32,598,336 | `61e70902ce15d4f11dc28b5d40dc5aa5853fb3330720cfef226ed081c68cb7af` | Internet Archive item visible in PDF metadata: `apostolicfathers00lighuoft` |

## Verification

```bash
shasum -a 256 sources/shepherd_of_hermas/scans/*.pdf
```
