# tools/coptic

Small Python stdlib-only helpers for Phase E Nag Hammadi prep.

## Scripts

- `fetch_mattison_zinner.py` — fetches HTML witnesses from the Mattison/Zinner ecosystem and stores raw HTML + visible text snapshots under `sources/nag_hammadi/raw/`
- `segment_nh_texts.py` — derives segment indexes from the fetched primary witnesses so prompts can be emitted per saying / section / line block
- `ocr_coptic.py` — scaffolds OCR jobs for non-HTML Coptic witnesses and lets you register local PDF/image inputs later
- `coptic_witness.py` — builds per-text witness bundles from manifests + fetched/OCR state
- `build_nh_prompt.py` — emits translator-ready overview prompts and per-segment prompt files with text-specific guardrails

## Typical flow

```bash
python3 tools/coptic/fetch_mattison_zinner.py --all
python3 tools/coptic/segment_nh_texts.py --all
python3 tools/coptic/ocr_coptic.py prepare --all
python3 tools/coptic/coptic_witness.py build --all
python3 tools/coptic/build_nh_prompt.py --all
```

## Notes

- These tools intentionally avoid third-party Python dependencies.
- Raw witness snapshots are intended to be tracked here for provenance and reproducibility.
- OCR jobs are scaffolded now so PDFs/images can be registered without redesigning the pipeline later.
