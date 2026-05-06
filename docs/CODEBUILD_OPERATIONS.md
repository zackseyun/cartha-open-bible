# CodeBuild operations for Public Open Bible

GitHub Actions are disabled for this repository. The operational jobs now run in AWS CodeBuild so GitHub runner minutes stay out of the critical path.

> Note: `zackseyun/cartha-open-bible` is public, so its standard GitHub-hosted Actions minutes generally do **not** count against the private-account included-minute quota. The migration is still useful because it centralizes operational jobs in AWS, uses AWS-native IAM, and removes noisy/failing Actions runs.

## CodeBuild projects

| Project | Trigger | Replaces | What it does |
| --- | --- | --- | --- |
| `cartha-open-bible-publish-pob` | Push to `main` touching `translation/**` or `revisions.json` | `publish-pob.yml` | Invokes `cartha-cob-publisher`, then waits for `https://bible.cartha.com/manifest.json` to match the pushed commit SHA. |
| `cartha-open-bible-regen-status` | Push to `main` touching `translation/**`/`tools/build_status.py`, plus hourly EventBridge at minute 17 | `regen-status.yml` | Runs `tools/build_status.py`; commits `status.json` back to `main` with `[skip ci]` if changed. |
| `cartha-open-bible-regen-summary-cache` | Push to `main` touching `translation/**`/summary tooling, plus hourly EventBridge at minute 37 | `regen-summary-cache.yml` | Counts missing BibleSummaryCache entries, then fills gaps with Vertex/Gemini unless `DRY_RUN=true`. Installs `requests` explicitly because the old Actions job was failing without it. |
| `cartha-open-bible-regen-embeddings` | Push to `main` touching `translation/**` or embedding buildspec/template | `regen-embeddings.yml` | Submits a one-shot EKS Job in namespace `alpha` to run `scripts/ingest_scripture.py` in-cluster. |

All jobs skip commits whose message contains `[skip ci]`.

## Setup / refresh

From the repository root:

```bash
AWS_REGION=us-east-2 ./scripts/setup_codebuild_deploys.sh
```

The setup script is idempotent. It creates/updates:

- CodeBuild projects in `us-east-2` using the existing GitHub CodeConnections connection, with `concurrentBuildLimit=1` to avoid overlapping runs.
- The CodeBuild service role `cartha-open-bible-codebuild-role`.
- A repo-scoped GitHub deploy key for status pushes, stored in Secrets Manager as `cartha-open-bible/codebuild-status-deploy-key`.
- GitHub repository webhooks that send `push` events directly to CodeBuild.
- EventBridge hourly schedules for status and summary cache jobs.
- An EKS access entry mapping the CodeBuild role to Kubernetes group `cartha-embedders`.

## Manual runs

```bash
aws codebuild start-build --region us-east-2 --project-name cartha-open-bible-publish-pob
aws codebuild start-build --region us-east-2 --project-name cartha-open-bible-regen-status
aws codebuild start-build --region us-east-2 --project-name cartha-open-bible-regen-summary-cache
aws codebuild start-build --region us-east-2 --project-name cartha-open-bible-regen-embeddings
```

Useful overrides:

```bash
# Summary cache dry run only
aws codebuild start-build \
  --region us-east-2 \
  --project-name cartha-open-bible-regen-summary-cache \
  --environment-variables-override name=DRY_RUN,value=true,type=PLAINTEXT

# Embeddings for a wider testament set
aws codebuild start-build \
  --region us-east-2 \
  --project-name cartha-open-bible-regen-embeddings \
  --environment-variables-override \
    name=TESTAMENTS,value=nt,ot,deuterocanon,extra_canonical,type=PLAINTEXT \
    name=WORKERS,value=4,type=PLAINTEXT
```

## Operating style

- Keep Actions disabled unless we intentionally roll back. Old workflow files are preserved under `.github/workflows/disabled/*.disabled`.
- Use CodeBuild for push-driven operational automation; use local scripts for heavy drafting/review batches that do not need to run on every commit.
- Keep status commits small and `[skip ci]` so they do not cause publish/embedding loops.
- Watch CodeBuild and CloudWatch logs for failures. Summary cache can legitimately run longer than publish/status because it may generate many missing summaries. CodeBuild project concurrency is capped at 1 so hourly backups do not pile up parallel expensive jobs.
- Do not promote a new embedder image or change the EKS/Kubernetes group without verifying the CodeBuild role still has access to `alpha` namespace Jobs.

## Rollback

If CodeBuild has an outage, move the required workflow file(s) from `.github/workflows/disabled/*.disabled` back to `.github/workflows/*.yml` and disable the corresponding CodeBuild webhook/schedule. Prefer a narrow rollback, for example publish only, rather than re-enabling every workflow.
