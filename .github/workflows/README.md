# GitHub Actions intentionally disabled

This repository now uses AWS CodeBuild for the automated POB operational jobs that used to live in GitHub Actions:

- `cartha-open-bible-publish-pob`
- `cartha-open-bible-regen-status`
- `cartha-open-bible-regen-summary-cache`
- `cartha-open-bible-regen-embeddings`

The old workflows are preserved under `.github/workflows/disabled/*.disabled` for audit/rollback, but GitHub will not execute them.

See `docs/CODEBUILD_OPERATIONS.md` and `scripts/setup_codebuild_deploys.sh`.
