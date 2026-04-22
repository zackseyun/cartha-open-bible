# tools/coptic

Small Python stdlib-only helpers for Phase E Nag Hammadi prep.

## Scripts

- `fetch_mattison_zinner.py` — fetches HTML witnesses from the Mattison/Zinner ecosystem and stores raw HTML + visible text snapshots under `sources/nag_hammadi/raw/`
- `segment_nh_texts.py` — derives segment indexes from the fetched primary witnesses so prompts can be emitted per saying / section / line block
- `ocr_coptic.py` — scaffolds OCR jobs for non-HTML Coptic witnesses and lets you register local files or download direct remote PDFs/images into staging later
- `coptic_witness.py` — builds per-text witness bundles from manifests + fetched/OCR state
- `build_nh_prompt.py` — emits translator-ready overview prompts and per-segment prompt files with text-specific guardrails
- `run_coptic_ocr.py` — runs Gemini-based OCR against queued Coptic witness jobs and writes per-page/per-image plaintext plus sidecar metadata; now supports Vertex AI, crop boxes, and multi-band page assembly
- `run_parallel_coptic_ocr.py` — fans Coptic OCR out across multiple Vertex credentials or AI Studio keys for max-throughput runs
- `fetch_claremont_nag_hammadi_images.py` — stages Claremont CCDL facsimile images for Gospel of Truth and Thunder, Perfect Mind

## Typical flow

```bash
python3 tools/coptic/fetch_mattison_zinner.py --all
python3 tools/coptic/segment_nh_texts.py --all
python3 tools/coptic/ocr_coptic.py prepare --all
# then either register a local file or pull a direct remote source URL
python3 tools/coptic/ocr_coptic.py register --text gospel_of_truth --witness nhc_xii_2_fragments --input /path/to/source.pdf
python3 tools/coptic/ocr_coptic.py register-url --text gospel_of_truth --witness nhc_xii_2_fragments --url https://example.com/source.pdf
python3 tools/coptic/fetch_claremont_nag_hammadi_images.py --text gospel_of_truth
python3 tools/coptic/coptic_witness.py build --all
python3 tools/coptic/build_nh_prompt.py --all
python3 tools/coptic/run_coptic_ocr.py --text gospel_of_truth --witness nhc_i_3_facsimile_primary --backend vertex --crop-box 0.16,0.03,0.84,0.97 --band-count 6 --limit 1
python3 tools/coptic/run_parallel_coptic_ocr.py --text gospel_of_truth --witness nhc_i_3_facsimile_primary --backend vertex --workers-per-key 2 --resume --crop-box 0.16,0.03,0.84,0.97 --band-count 6
```

## Notes

- Vertex mode requires the same Google auth dependencies already used elsewhere in the repo (`google-auth` via the repo venv).
- Raw witness snapshots are intended to be tracked here for provenance and reproducibility.
- OCR jobs are scaffolded now so PDFs/images can be registered without redesigning the pipeline later.
