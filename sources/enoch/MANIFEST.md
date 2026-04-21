# 1 Enoch source PDFs — manifest

Following the precedent of `sources/lxx/swete/MANIFEST.md` and
`sources/2esdras/MANIFEST.md`: full source-edition PDFs are **not
committed** to git (they are large and publicly re-retrievable). This
file records expected files with SHA-256 hashes so a fresh checkout
can verify authenticity after re-downloading.

Scope and strategy: see [`../../ENOCH.md`](../../ENOCH.md).

## Files

| Expected path | Edition | Year | Size (bytes) | SHA-256 | Archive.org identifier |
|---|---|---|---:|---|---|
| `scans/charles_1906_ethiopic.pdf` | Charles, *The Ethiopic Version of the Book of Enoch* (Anecdota Oxoniensia Semitic Series I.vii, Clarendon Press) | 1906 | 19,936,177 | `505f248c667cebd5136991d7c570841a0a3ed9396d5b28b85bf07f4a3957053e` | `ethiopicversiono00charuoft` |
| `scans/dillmann_1851_ethiopic.pdf` | Dillmann, *Liber Henoch, Aethiopice* (Leipzig: Vogel) | 1851 | 12,209,841 | `3800be7c3408d2f8a3e9f112b18025c6541fe946226654b4818ab60979880cdc` | `bub_gb_DigVAAAAQAAJ` |
| `scans/bouriant_1892_greek.pdf` | Bouriant, *Fragments grecs du livre d'Hénoch* (Akhmim / Codex Panopolitanus), in *Mémoires publiés par les membres de la Mission archéologique française au Caire* IX.1 | 1892 | 14,043,854 | `4859e461875902fa0dac438fdf39da1d63b175fd985da43ca34fee5edbda1c2c` | `lelivredhnochfra0000unse` |
| `scans/flemming_1901_greek.pdf` | Flemming & Radermacher, *Das Buch Henoch* (GCS 5, Leipzig: Hinrichs) — Greek + German | 1901 | 19,566,343 | `d3d2541035eeaec840cc154d6ba87820242942e8ee059933c66b95c65f4cfe81` | `dasbuchhenochhrs00flemuoft` |
| `scans/schodde_1882_english.pdf` | Schodde, *The Book of Enoch Translated from the Ethiopic* (Andover: Draper) | 1882 | 6,353,623 | `4a008766a89530fc7260f5581b1c1f6ba567b8536b57408f085d564ac8532897` | `bookenochtransl00schogoog` |
| `scans/apot_vol2_1913.pdf` | Charles (ed.), *The Apocrypha and Pseudepigrapha of the Old Testament* Vol. 2 (Clarendon Press) — contains revised English Enoch | 1913 | 88,836,200 | `104db36866c2164b204a19522e395989cc5384220ce0326edc449c96ee6b6cb4` | `apocryphapseudep0002rhch_w1w3` |

## How to rehydrate on a fresh checkout

```bash
cd sources/enoch
mkdir -p scans
curl -fsSL -o scans/charles_1906_ethiopic.pdf \
  https://archive.org/download/ethiopicversiono00charuoft/ethiopicversiono00charuoft.pdf
curl -fsSL -o scans/dillmann_1851_ethiopic.pdf \
  https://archive.org/download/bub_gb_DigVAAAAQAAJ/bub_gb_DigVAAAAQAAJ.pdf
curl -fsSL -o scans/bouriant_1892_greek.pdf \
  https://archive.org/download/lelivredhnochfra0000unse/lelivredhnochfra0000unse.pdf
curl -fsSL -o scans/flemming_1901_greek.pdf \
  https://archive.org/download/dasbuchhenochhrs00flemuoft/dasbuchhenochhrs00flemuoft.pdf
curl -fsSL -o scans/schodde_1882_english.pdf \
  https://archive.org/download/bookenochtransl00schogoog/bookenochtransl00schogoog.pdf
curl -fsSL -o scans/apot_vol2_1913.pdf \
  https://archive.org/download/apocryphapseudep0002rhch_w1w3/apocryphapseudep0002rhch_w1w3.pdf

# Verify
shasum -a 256 scans/*.pdf
```

All files are Public Domain (pre-1929 publications with attributed,
long-deceased authors).

## License note on the Beta maṣāḥǝft XML (Zone 1 validation oracle)

The Hiob Ludolf Centre's Beta maṣāḥǝft project publishes a TEI XML
digital Ge'ez text of 1 Enoch at
https://github.com/BetaMasaheft/Works (file
`1001-2000/LIT1340EnochE.xml`). This file declares itself CC-BY-SA
4.0 on the outer wrapper but embeds Jerabek's 1995 copyright with
"noncommercial only" language. These are in tension, and we do NOT
vendor it.

We use it only as a Zone 1 **validation oracle** — an independent
digital Ge'ez text to cross-check our own fresh OCR of Charles 1906
and Dillmann 1851. This is exactly the pattern we applied to
First1KGreek (CC-BY-SA) for LXX Swete: oracle for cross-check, never
derived-from. A local copy is kept at
`~/cartha-reference-local/enoch_betamasaheft/LIT1340EnochE.xml` on
the drafter's workstation.

## License

Our derived transcriptions (Gemini OCR of Charles 1906 + Dillmann
1851, validated against Beta maṣāḥǝft) will be published under
CC-BY 4.0 as the Zone 1 Ge'ez primary for COB Enoch. See
[`../../REFERENCE_SOURCES.md`](../../REFERENCE_SOURCES.md) for the full
policy.
