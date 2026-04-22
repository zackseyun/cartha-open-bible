# 2 Baruch source files — manifest

Following the precedent of `sources/2esdras/MANIFEST.md`,
`sources/enoch/MANIFEST.md`, and the other extra-canonical source
manifests: the full source files are **not committed** to git. This
manifest records the expected local files, sizes, and SHA-256 hashes so
a fresh checkout can rehydrate the exact same inputs.

Scope and strategy: [`../../2BARUCH.md`](../../2BARUCH.md).

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Source locator |
|---|---|---|---:|---|---|
| `scans/ceriani_1871_monumenta_tom5.pdf` | Ceriani, *Apocalypsis Baruch syriace* in *Monumenta sacra et profana* 5.2 | 1871 | 14,988,501 | `012c2357c112e8fcb2230b7a787e09210b024e7771fce50d9e7f38e9335fc300` | Internet Archive item `Ceriani1868MonumentaSacraEtProfanaTom.V` (Baruch at pp. 113-180) |
| `scans/kmosko_1907_patrologia_syriaca_vol1_2.pdf` | Kmosko, *Liber Apocalypseos Baruch filii Neriae translatus de graeco in syriacum* in *Patrologia Syriaca* 1.2 | 1907 | 28,175,161 | `2e1cf48a45a29e91306afcd831c3eda2a08c439351ee44040500f6a07e8d94b6` | Internet Archive item `patrologiasyria02grafgoog` (Baruch at cols. 1056-1207) |
| `scans/violet_1924_gcs32_wbc.zip` | Violet, *Die Apokalypsen des Esra und des Baruch in deutscher Gestalt* (GCS 32) | 1924 | 42,597,564 | `0b93e9c6643d4d7ed1e71391c4d15cba3f0d4f577311a5d2d06694072d260f62` | Wielkopolska Biblioteka Cyfrowa edition `136133` (`/Content/136133/download/`) |
| `reference/charles_1896_apocalypse_of_baruch.pdf` | Charles, *The Apocalypse of Baruch* | 1896 | 11,671,625 | `d9ef9a5f1ba8b0f92e5a34529820f04454706ece145f5325af5a6e735f84216b` | Internet Archive item `theapocalypseofb00charuoft` |

## How to rehydrate

```bash
cd sources/2baruch
mkdir -p scans reference
curl -fsSL -o scans/ceriani_1871_monumenta_tom5.pdf \
  'https://archive.org/download/Ceriani1868MonumentaSacraEtProfanaTom.V/Ceriani%201868_Monumenta%20sacra%20et%20profana%20tom.%20V.pdf'
curl -fsSL -o scans/kmosko_1907_patrologia_syriaca_vol1_2.pdf \
  'https://archive.org/download/patrologiasyria02grafgoog/patrologiasyria02grafgoog.pdf'
curl -fsSL -o scans/violet_1924_gcs32_wbc.zip \
  'https://www.wbc.poznan.pl/Content/136133/download/'
curl -fsSL -o reference/charles_1896_apocalypse_of_baruch.pdf \
  'https://archive.org/download/theapocalypseofb00charuoft/theapocalypseofb00charuoft.pdf'

# Verify
shasum -a 256 scans/* reference/*
```

If you need the Violet pages unpacked locally for later inspection:

```bash
unzip -q -o scans/violet_1924_gcs32_wbc.zip -d scans/violet_1924_gcs32_wbc
```

That WBC export currently contains `index.djvu` plus 488 page-level
DjVu files (`p0001.djvu` ... `p0488.djvu`).

## License

All four source files above are public-domain witnesses or reference
editions. Our own derived OCR, cleaned transcriptions, and translation
output remain the CC-BY 4.0 layer published by COB. See
[`../../REFERENCE_SOURCES.md`](../../REFERENCE_SOURCES.md) for the full
Zone 1 / Zone 2 policy.
