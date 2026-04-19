# Swete LXX — Vision-transcribed working text

Clean UTF-8 polytonic Greek transcribed from the Swete 1909–1930 scan
pages on Internet Archive via Azure GPT-5.4 vision
(`tools/transcribe_source.py`).

## Files

- `vol{1,2,3}_p{NNNN}.txt` — verbatim transcription of a single scan
  page. Begins with `---SWETE-PAGE---` and ends with `---END-PAGE---`.
  Section markers: `[RUNNING HEAD]`, `[BODY]`, `[APPARATUS]`,
  `[MARGINALIA]`, `[PLATE]`, `[BLANK]`.
- `vol{1,2,3}_p{NNNN}.meta.json` — per-page provenance: image SHA-256,
  source URL on archive.org, model id, deployment, prompt version,
  timestamp, duration, output length.
- `page_index.json` — being built up as pages are transcribed: maps
  `vol` + `page` (scan page) → book code + chapter range + notes.
  Used by downstream code (planned `tools/lxx_swete.py`) to find which
  file holds a given book/chapter.

## Reproducing a transcription

The transcription is deterministic given the same image, prompt
version, and model deployment. To reproduce any page:

```bash
AZURE_OPENAI_API_KEY=... \
python3 tools/transcribe_source.py --source swete --vol 2 --page 60
```

The `meta.json` sidecar records the exact prompt version and model
deployment used, so a future rerun against the same scan image
(verifiable via `image_sha256`) can be compared to the current text.

## Scope

We prioritize the deuterocanonical sections of each volume:

- **Vol. II** — Tobit, Judith, Greek Additions to Esther, Wisdom of
  Solomon, Sirach.
- **Vol. III** — 1-4 Maccabees, Baruch + Letter of Jeremiah, Greek
  Additions to Daniel (Pr Azariah, Song of the Three, Susanna, Bel),
  Prayer of Manasseh, Psalm 151.

The Protestant canonical books that Swete also contains (Genesis
through Malachi) are *not* a priority for vision transcription — those
books are drafted from SBLGNT (NT) and WLC/UHB (OT). They will be
transcribed later only as a cross-reference aid.
