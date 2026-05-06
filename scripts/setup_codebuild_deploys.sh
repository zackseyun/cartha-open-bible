#!/usr/bin/env bash
set -euo pipefail

REGION="${AWS_REGION:-us-east-2}"
AWS_RESOURCE_REGION="${AWS_RESOURCE_REGION:-us-west-2}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
REPO_OWNER="${REPO_OWNER:-zackseyun}"
REPO_NAME="${REPO_NAME:-cartha-open-bible}"
REPO_URL="${REPO_URL:-https://github.com/${REPO_OWNER}/${REPO_NAME}.git}"
ROLE_NAME="${CODEBUILD_ROLE_NAME:-cartha-open-bible-codebuild-role}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
EVENTS_ROLE_NAME="${EVENTS_ROLE_NAME:-cartha-open-bible-codebuild-events-role}"
EVENTS_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EVENTS_ROLE_NAME}"
CONNECTION_ARN="${CODEBUILD_GITHUB_CONNECTION_ARN:-}"

PUBLISH_PROJECT="${PUBLISH_PROJECT:-cartha-open-bible-publish-pob}"
STATUS_PROJECT="${STATUS_PROJECT:-cartha-open-bible-regen-status}"
SUMMARY_PROJECT="${SUMMARY_PROJECT:-cartha-open-bible-regen-summary-cache}"
EMBEDDINGS_PROJECT="${EMBEDDINGS_PROJECT:-cartha-open-bible-regen-embeddings}"
STATUS_RULE="${STATUS_RULE:-cartha-open-bible-regen-status-hourly}"
SUMMARY_RULE="${SUMMARY_RULE:-cartha-open-bible-regen-summary-cache-hourly}"
STATUS_DEPLOY_KEY_SECRET="${STATUS_DEPLOY_KEY_SECRET:-cartha-open-bible/codebuild-status-deploy-key}"
STATUS_DEPLOY_KEY_TITLE="${STATUS_DEPLOY_KEY_TITLE:-codebuild-cartha-open-bible-status}"

if [[ -z "$CONNECTION_ARN" ]]; then
  CONNECTION_ARN=$(aws codeconnections list-connections --region "$REGION" \
    --query "Connections[?ProviderType=='GitHub' && ConnectionStatus=='AVAILABLE'] | [0].ConnectionArn" \
    --output text 2>/dev/null || true)
fi

if [[ -z "$CONNECTION_ARN" || "$CONNECTION_ARN" == "None" ]]; then
  cat >&2 <<EOF
No AVAILABLE GitHub CodeConnections connection found in $REGION.
Set AWS_REGION to the region containing the GitHub connection, or set CODEBUILD_GITHUB_CONNECTION_ARN explicitly, then rerun.
EOF
  exit 1
fi

if ! aws codebuild list-source-credentials --region "$REGION" \
  --query "sourceCredentialsInfos[?serverType=='GITHUB' && authType=='CODECONNECTIONS'] | [0].arn" \
  --output text 2>/dev/null | grep -q '^arn:'; then
  echo "Importing CodeBuild GitHub source credentials from CodeConnections"
  aws codebuild import-source-credentials \
    --region "$REGION" \
    --server-type GITHUB \
    --auth-type CODECONNECTIONS \
    --token "$CONNECTION_ARN" >/dev/null
else
  echo "CodeBuild GitHub source credentials already imported"
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/codebuild-trust.json" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "codebuild.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "Creating IAM role $ROLE_NAME"
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TMP_DIR/codebuild-trust.json" >/dev/null
else
  echo "IAM role $ROLE_NAME already exists"
fi

cat > "$TMP_DIR/codebuild-policy.json" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CodeBuildLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": [
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${PUBLISH_PROJECT}",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${PUBLISH_PROJECT}:*",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${STATUS_PROJECT}",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${STATUS_PROJECT}:*",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${SUMMARY_PROJECT}",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${SUMMARY_PROJECT}:*",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${EMBEDDINGS_PROJECT}",
        "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/codebuild/${EMBEDDINGS_PROJECT}:*"
      ]
    },
    {
      "Sid": "CodeBuildReports",
      "Effect": "Allow",
      "Action": [
        "codebuild:CreateReportGroup",
        "codebuild:CreateReport",
        "codebuild:UpdateReport",
        "codebuild:BatchPutTestCases",
        "codebuild:BatchPutCodeCoverages"
      ],
      "Resource": "arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:report-group/cartha-open-bible-*"
    },
    {
      "Sid": "UseGithubConnection",
      "Effect": "Allow",
      "Action": [
        "codeconnections:GetConnection",
        "codeconnections:GetConnectionToken",
        "codeconnections:UseConnection",
        "codestar-connections:GetConnection",
        "codestar-connections:GetConnectionToken",
        "codestar-connections:UseConnection"
      ],
      "Resource": "${CONNECTION_ARN}"
    },
    {
      "Sid": "InvokeCobPublisher",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:function:cartha-cob-publisher"
    },
    {
      "Sid": "SummaryCacheWrite",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:BatchGetItem",
        "dynamodb:PutItem",
        "dynamodb:Scan",
        "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:table/BibleSummaryCache-alpha"
    },
    {
      "Sid": "ReadGeminiSecrets",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:secret:/cartha/openclaw/gemini_api_key-*",
        "arn:aws:secretsmanager:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:secret:/cartha/openclaw/gemini_api_key_2-*",
        "arn:aws:secretsmanager:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:secret:/cartha/vertex/gemini-sa-*",
        "arn:aws:secretsmanager:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:secret:/cartha/openclaw/gemini_vertex_cbv_sa-*"
      ]
    },
    {
      "Sid": "ReadStatusDeployKey",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${STATUS_DEPLOY_KEY_SECRET}-*"
    },
    {
      "Sid": "EksEmbeddingAccess",
      "Effect": "Allow",
      "Action": ["eks:DescribeCluster", "eks:AccessKubernetesApi"],
      "Resource": "arn:aws:eks:${AWS_RESOURCE_REGION}:${ACCOUNT_ID}:cluster/cartha-eks-cluster"
    }
  ]
}
JSON

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name cartha-open-bible-codebuild-policy \
  --policy-document "file://$TMP_DIR/codebuild-policy.json"
echo "Updated IAM inline policy for $ROLE_NAME"

ensure_status_deploy_key() {
  if aws secretsmanager describe-secret --region "$REGION" --secret-id "$STATUS_DEPLOY_KEY_SECRET" >/dev/null 2>&1; then
    echo "Status deploy key secret already exists: $STATUS_DEPLOY_KEY_SECRET"
    return
  fi
  if ! command -v gh >/dev/null 2>&1; then
    echo "gh is required to create the repo-scoped status deploy key. Install/auth gh or create $STATUS_DEPLOY_KEY_SECRET manually." >&2
    exit 1
  fi
  if ! command -v ssh-keygen >/dev/null 2>&1; then
    echo "ssh-keygen is required to create the repo-scoped status deploy key." >&2
    exit 1
  fi
  echo "Creating repo-scoped deploy key for status.json pushes"
  ssh-keygen -t ed25519 -N '' -C "$STATUS_DEPLOY_KEY_TITLE" -f "$TMP_DIR/status_key" >/dev/null
  local key_title="$STATUS_DEPLOY_KEY_TITLE"
  if gh api "repos/${REPO_OWNER}/${REPO_NAME}/keys" --paginate --jq '.[].title' | grep -qx "$key_title"; then
    key_title="${STATUS_DEPLOY_KEY_TITLE}-$(date +%Y%m%d%H%M%S)"
  fi
  gh api -X POST "repos/${REPO_OWNER}/${REPO_NAME}/keys" \
    -f title="$key_title" \
    -f key="$(cat "$TMP_DIR/status_key.pub")" \
    -F read_only=false >/dev/null
  jq -n --arg privateKey "$(cat "$TMP_DIR/status_key")" '{privateKey: $privateKey}' > "$TMP_DIR/status-secret.json"
  aws secretsmanager create-secret \
    --region "$REGION" \
    --name "$STATUS_DEPLOY_KEY_SECRET" \
    --secret-string "file://$TMP_DIR/status-secret.json" >/dev/null
  chmod 600 "$TMP_DIR/status_key"
  echo "Created deploy key secret $STATUS_DEPLOY_KEY_SECRET"
}

ensure_status_deploy_key

# Give IAM + Secrets Manager a moment to propagate before project creation/builds.
sleep 8

write_project_json() {
  local project_name="$1"
  local description="$2"
  local buildspec="$3"
  local compute_type="$4"
  local timeout_minutes="$5"
  local git_depth="$6"
  local output="$7"

  cat > "$output" <<JSON
{
  "name": "${project_name}",
  "description": "${description}",
  "source": {
    "type": "GITHUB",
    "location": "${REPO_URL}",
    "gitCloneDepth": ${git_depth},
    "buildspec": "${buildspec}",
    "auth": {
      "type": "CODECONNECTIONS",
      "resource": "${CONNECTION_ARN}"
    },
    "reportBuildStatus": true,
    "buildStatusConfig": {
      "context": "CodeBuild ${project_name}",
      "targetUrl": "https://${REGION}.console.aws.amazon.com/codesuite/codebuild/projects/${project_name}/history?region=${REGION}"
    }
  },
  "artifacts": { "type": "NO_ARTIFACTS" },
  "environment": {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:7.0",
    "computeType": "${compute_type}",
    "imagePullCredentialsType": "CODEBUILD",
    "privilegedMode": false
  },
  "serviceRole": "${ROLE_ARN}",
  "timeoutInMinutes": ${timeout_minutes},
  "queuedTimeoutInMinutes": 30,
  "concurrentBuildLimit": 1,
  "cache": {
    "type": "LOCAL",
    "modes": ["LOCAL_SOURCE_CACHE", "LOCAL_CUSTOM_CACHE"]
  },
  "logsConfig": {
    "cloudWatchLogs": {
      "status": "ENABLED",
      "groupName": "/aws/codebuild/${project_name}"
    }
  }
}
JSON
}

upsert_project() {
  local project_name="$1"
  local json_file="$2"
  if aws codebuild batch-get-projects --region "$REGION" --names "$project_name" \
    --query 'projects[0].name' --output text 2>/dev/null | grep -qx "$project_name"; then
    echo "Updating CodeBuild project $project_name"
    aws codebuild update-project --region "$REGION" --cli-input-json "file://$json_file" >/dev/null
  else
    echo "Creating CodeBuild project $project_name"
    aws codebuild create-project --region "$REGION" --cli-input-json "file://$json_file" >/dev/null
  fi
}

write_project_json "$PUBLISH_PROJECT" "Publish POB CDN from cartha-open-bible commits" "buildspecs/codebuild-publish-pob.yml" "BUILD_GENERAL1_SMALL" 20 1 "$TMP_DIR/publish-project.json"
write_project_json "$STATUS_PROJECT" "Regenerate and commit status.json for cartha-open-bible" "buildspecs/codebuild-regen-status.yml" "BUILD_GENERAL1_SMALL" 20 0 "$TMP_DIR/status-project.json"
write_project_json "$SUMMARY_PROJECT" "Fill BibleSummaryCache-alpha gaps from cartha-open-bible" "buildspecs/codebuild-regen-summary-cache.yml" "BUILD_GENERAL1_MEDIUM" 120 1 "$TMP_DIR/summary-project.json"
write_project_json "$EMBEDDINGS_PROJECT" "Submit scripture embedding regeneration job to EKS" "buildspecs/codebuild-regen-embeddings.yml" "BUILD_GENERAL1_MEDIUM" 90 1 "$TMP_DIR/embeddings-project.json"

upsert_project "$PUBLISH_PROJECT" "$TMP_DIR/publish-project.json"
upsert_project "$STATUS_PROJECT" "$TMP_DIR/status-project.json"
upsert_project "$SUMMARY_PROJECT" "$TMP_DIR/summary-project.json"
upsert_project "$EMBEDDINGS_PROJECT" "$TMP_DIR/embeddings-project.json"

ensure_eks_access_entry() {
  if aws eks describe-access-entry \
    --region "$AWS_RESOURCE_REGION" \
    --cluster-name cartha-eks-cluster \
    --principal-arn "$ROLE_ARN" >/dev/null 2>&1; then
    echo "EKS access entry already exists for $ROLE_ARN"
    aws eks update-access-entry \
      --region "$AWS_RESOURCE_REGION" \
      --cluster-name cartha-eks-cluster \
      --principal-arn "$ROLE_ARN" \
      --kubernetes-groups cartha-embedders \
      --username codebuild-embedder >/dev/null || true
  else
    echo "Creating EKS access entry for embeddings CodeBuild role"
    aws eks create-access-entry \
      --region "$AWS_RESOURCE_REGION" \
      --cluster-name cartha-eks-cluster \
      --principal-arn "$ROLE_ARN" \
      --kubernetes-groups cartha-embedders \
      --username codebuild-embedder >/dev/null
  fi
}

ensure_eks_access_entry

create_or_replace_webhook() {
  local project_name="$1"
  local file_pattern="$2"
  local filter_file="$TMP_DIR/${project_name}-filters.json"
  python3 - "$file_pattern" > "$filter_file" <<'PY_FILTERS'
import json
import sys
pattern = sys.argv[1]
print(json.dumps([[
    {"type": "EVENT", "pattern": "PUSH"},
    {"type": "HEAD_REF", "pattern": "^refs/heads/main$"},
    {"type": "FILE_PATH", "pattern": pattern},
]]))
PY_FILTERS

  local has_webhook
  has_webhook=$(aws codebuild batch-get-projects --region "$REGION" --names "$project_name" \
    --query 'projects[0].webhook.payloadUrl || projects[0].webhook.url' --output text 2>/dev/null || true)
  if [[ -n "$has_webhook" && "$has_webhook" != "None" ]]; then
    echo "Replacing webhook for $project_name"
    aws codebuild delete-webhook --region "$REGION" --project-name "$project_name" >/dev/null || true
    sleep 3
  else
    echo "Creating webhook for $project_name"
  fi

  local webhook_out="$TMP_DIR/${project_name}-webhook.json"
  aws codebuild create-webhook \
    --region "$REGION" \
    --project-name "$project_name" \
    --manual-creation \
    --filter-groups "file://$filter_file" > "$webhook_out"

  local payload_url secret
  payload_url=$(jq -r '.webhook.payloadUrl // empty' "$webhook_out")
  secret=$(jq -r '.webhook.secret // empty' "$webhook_out")
  if [[ -z "$payload_url" || -z "$secret" ]]; then
    echo "CodeBuild did not return manual webhook payloadUrl/secret for $project_name" >&2
    exit 1
  fi

  if command -v gh >/dev/null 2>&1 && [[ "${INSTALL_GITHUB_WEBHOOKS:-true}" != "false" ]]; then
    local hook_id
    hook_id=$(PAYLOAD_URL="$payload_url" gh api "repos/${REPO_OWNER}/${REPO_NAME}/hooks" --paginate \
      --jq '.[] | select(.config.url == env.PAYLOAD_URL) | .id' | head -n 1 || true)
    if [[ -n "$hook_id" ]]; then
      echo "Updating GitHub repository webhook for $project_name"
      gh api -X PATCH "repos/${REPO_OWNER}/${REPO_NAME}/hooks/$hook_id" \
        -f name=web \
        -F active=true \
        -F 'events[]=push' \
        -f 'config[content_type]=json' \
        -f "config[url]=$payload_url" \
        -f "config[secret]=$secret" >/dev/null
    else
      echo "Creating GitHub repository webhook for $project_name"
      gh api -X POST "repos/${REPO_OWNER}/${REPO_NAME}/hooks" \
        -f name=web \
        -F active=true \
        -F 'events[]=push' \
        -f 'config[content_type]=json' \
        -f "config[url]=$payload_url" \
        -f "config[secret]=$secret" >/dev/null
    fi
  else
    cat >&2 <<EOF_MANUAL
Manual GitHub webhook needed for $project_name:
  Payload URL: $payload_url
  Content type: application/json
  Secret: [hidden; rerun with gh installed or inspect CodeBuild webhook output]
  Events: push
EOF_MANUAL
  fi
}

if command -v gh >/dev/null 2>&1 && [[ "${INSTALL_GITHUB_WEBHOOKS:-true}" != "false" ]]; then
  echo "Removing stale GitHub CodeBuild repository webhooks before reinstall"
  gh api "repos/${REPO_OWNER}/${REPO_NAME}/hooks" --paginate \
    --jq '.[] | select(.config.url | contains("codebuild.")) | .id' \
    | while read -r hook_id; do
        [[ -n "$hook_id" ]] || continue
        gh api -X DELETE "repos/${REPO_OWNER}/${REPO_NAME}/hooks/$hook_id" >/dev/null
      done
fi

PUBLISH_FILE_PATTERN='^(translation/|revisions\.json$|buildspecs/codebuild-publish-pob\.yml$)'
STATUS_FILE_PATTERN='^(translation/|tools/build_status\.py$|buildspecs/codebuild-regen-status\.yml$)'
SUMMARY_FILE_PATTERN='^(translation/|tools/gemini_summary_prewarm\.py$|buildspecs/codebuild-regen-summary-cache\.yml$)'
EMBEDDINGS_FILE_PATTERN='^(translation/|buildspecs/codebuild-regen-embeddings\.yml$|buildspecs/embedding-job-template\.yaml$)'

create_or_replace_webhook "$PUBLISH_PROJECT" "$PUBLISH_FILE_PATTERN"
create_or_replace_webhook "$STATUS_PROJECT" "$STATUS_FILE_PATTERN"
create_or_replace_webhook "$SUMMARY_PROJECT" "$SUMMARY_FILE_PATTERN"
create_or_replace_webhook "$EMBEDDINGS_PROJECT" "$EMBEDDINGS_FILE_PATTERN"

cat > "$TMP_DIR/events-trust.json" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "events.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

if ! aws iam get-role --role-name "$EVENTS_ROLE_NAME" >/dev/null 2>&1; then
  echo "Creating EventBridge role $EVENTS_ROLE_NAME"
  aws iam create-role \
    --role-name "$EVENTS_ROLE_NAME" \
    --assume-role-policy-document "file://$TMP_DIR/events-trust.json" >/dev/null
else
  echo "EventBridge role $EVENTS_ROLE_NAME already exists"
fi

cat > "$TMP_DIR/events-policy.json" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "codebuild:StartBuild",
      "Resource": [
        "arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${STATUS_PROJECT}",
        "arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${SUMMARY_PROJECT}"
      ]
    }
  ]
}
JSON
aws iam put-role-policy \
  --role-name "$EVENTS_ROLE_NAME" \
  --policy-name cartha-open-bible-codebuild-events-policy \
  --policy-document "file://$TMP_DIR/events-policy.json"

sleep 5
aws events put-rule \
  --region "$REGION" \
  --name "$STATUS_RULE" \
  --schedule-expression 'cron(17 * * * ? *)' \
  --state ENABLED \
  --description "Hourly status.json regeneration for ${REPO_OWNER}/${REPO_NAME} via CodeBuild" >/dev/null
aws events put-targets \
  --region "$REGION" \
  --rule "$STATUS_RULE" \
  --targets "Id"="${STATUS_PROJECT}","Arn"="arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${STATUS_PROJECT}","RoleArn"="${EVENTS_ROLE_ARN}" >/dev/null

aws events put-rule \
  --region "$REGION" \
  --name "$SUMMARY_RULE" \
  --schedule-expression 'cron(37 * * * ? *)' \
  --state ENABLED \
  --description "Hourly BibleSummaryCache regeneration for ${REPO_OWNER}/${REPO_NAME} via CodeBuild" >/dev/null
aws events put-targets \
  --region "$REGION" \
  --rule "$SUMMARY_RULE" \
  --targets "Id"="${SUMMARY_PROJECT}","Arn"="arn:aws:codebuild:${REGION}:${ACCOUNT_ID}:project/${SUMMARY_PROJECT}","RoleArn"="${EVENTS_ROLE_ARN}" >/dev/null

cat <<EOF
✅ CodeBuild projects are configured for ${REPO_OWNER}/${REPO_NAME}.

Region: $REGION
GitHub connection: $CONNECTION_ARN
Projects:
- $PUBLISH_PROJECT
- $STATUS_PROJECT
- $SUMMARY_PROJECT
- $EMBEDDINGS_PROJECT

Hourly schedules:
- $STATUS_RULE at minute 17
- $SUMMARY_RULE at minute 37

GitHub Actions are intentionally disabled in this repo; see .github/workflows/README.md.
EOF
