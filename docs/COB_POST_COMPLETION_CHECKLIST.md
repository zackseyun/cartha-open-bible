# Cartha Open Bible — Post-Completion Checklist

This document is the handoff/checklist for the phase after the Cartha Open
Bible draft corpus is complete and the first revision pass has been finished.

## Goal

Move Cartha Open Bible from “preview translation with partial corpus” to
“first-class translation across app, backend, and public web surfaces.”

## Preconditions

Do these only after:

1. the full Bible draft exists,
2. the first revision pass is complete,
3. the project is ready to publish a stable translation snapshot.

## 1. Freeze a publishable translation snapshot

- Tag the translation repo with a release that represents the first stable COB corpus.
- Confirm `consistency_lint.py` has zero unresolved flags.
- Confirm the export script still produces a clean mobile artifact:
  - `tools/export_mobile_bible.py`

## 2. Rebuild the mobile preview asset

Generate a fresh app asset from the completed corpus:

```bash
source .venv/bin/activate
python tools/export_mobile_bible.py \
  --output "/Users/zackseyun/My Drive/Moltbot-Shared/Documents/GitHub/cartha.ai.mobile/cartha_ai_mobile/assets/bibles/cob_preview.json"
```

Future rename idea:
- promote `cob_preview.json` → `cob.json`
- remove “Preview” wording in the app once the corpus is stable enough

## 3. Generate COB semantic search vectors

The mobile API service is already prepared for multiple embedded Bible search
artifacts. To add COB vectors:

1. create a new embedded artifact folder under:
   - `CarthaCdkService/services/mobile-api-service-go/data/`
2. include:
   - `manifest.json`
   - `vectors.bin.gz`
3. ensure the manifest translation resolves cleanly, ideally:
   - `COB: Cartha Open Bible`

Suggested artifact naming pattern:
- `cob_v1_voyage-4-large/`

Expected outcome:
- the app can request `translation: "COB"`
- the backend registry resolves the COB artifact automatically
- no app protocol change should be needed

## 4. Promote COB from preview to full app translation

In the mobile app repo:

- update `/lib/screens/bible/bible_data.dart`
- remove “Preview” wording if appropriate
- refine picker copy if needed
- regenerate / replace the bundled JSON asset

Recommended copy target after full launch:
- short name: `COB`
- full name: `Cartha Open Bible`

## 5. Decide how scripture lookup should work

Right now some Bible lookup behavior still depends on non-COB sources.

Post-completion decision:

- either keep external lookup for generic translations,
- or add an internal COB lookup path so AI Bible tools can quote COB directly.

Recommended long-term direction:
- make COB a first-class internal lookup source for app Bible features

## 6. Public website / project page review

Current public explainer path:
- `https://cartha.com/cartha-open-bible/`

After completion:
- review copy for “Preview” / “in progress” wording
- update the page to reflect the stable published release
- confirm GitHub links still point to the correct repo/tag

## 7. QA before release

### Mobile app
- translation picker shows COB correctly
- Bible reader loads COB correctly
- spotlight search behaves correctly for COB
- bookmarks / notes still work with canonical verse IDs
- Bible study overlay uses COB text correctly

### Backend
- COB search artifact loads at startup
- `/bible/search` resolves `translation=COB`
- fallback behavior is still safe if COB vectors are missing

## 8. Nice-to-have follow-ups

- add a visible “translation version” field in app/backend responses
- add internal telemetry for COB selection and COB search usage
- add a small release note / changelog entry for each major COB revision
- consider moving from bundled asset only to a versioned remote translation feed later
