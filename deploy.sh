#!/bin/bash
set -e

echo "============================================================"
echo " Starting ADK Cloud Run Deployment Setup"
echo "============================================================"

# 1. GCP プロジェクトIDの自動解決 (Google Cloud Shell / ローカル両対応)
PROJECT_ID="${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-${DEVSHELL_PROJECT_ID}}}"
if [ -z "${PROJECT_ID}" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi

if [ -z "${PROJECT_ID}" ]; then
  echo "Error: GCP Project ID is not set."
  echo "Please run: gcloud config set project <YOUR_PROJECT_ID>"
  exit 1
fi

# 2. リージョン・サービス名・GCSバケット名
REGION="${REGION:-${CLOUD_RUN_REGION:-asia-northeast1}}"
SERVICE_NAME="${SERVICE_NAME:-bq-slidegen-agent}"
GCS_BUCKET="${GCS_BUCKET:-${PROJECT_ID}-slide-images}"

echo "Project ID    : ${PROJECT_ID}"
echo "Region        : ${REGION}"
echo "Service Name  : ${SERVICE_NAME}"
echo "GCS Bucket    : ${GCS_BUCKET}"
echo "Agent Model   : gemini-3.7-flash"
echo "Image Model   : gemini-3.1-flash-image"
echo "============================================================"

# 3. 必要な Google Cloud API の有効化
echo "[1/6] Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  dataplex.googleapis.com \
  storage.googleapis.com \
  --project="${PROJECT_ID}" --quiet

# 4. GCS バケットの存在確認 & 自動作成
echo "[2/6] Checking GCS bucket: gs://${GCS_BUCKET}..."
if ! gcloud storage buckets describe "gs://${GCS_BUCKET}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Bucket gs://${GCS_BUCKET} does not exist. Creating..."
  gcloud storage buckets create "gs://${GCS_BUCKET}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access || true
  echo "Bucket gs://${GCS_BUCKET} created."
else
  echo "Bucket gs://${GCS_BUCKET} already exists."
fi

# 5. Cloud Run 実行サービスアカウントへの IAM 権限の付与
echo "[3/6] Configuring IAM permissions for Cloud Run service account..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null || true)
if [ -n "${PROJECT_NUMBER}" ]; then
  COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  echo "Granting roles to ${COMPUTE_SA}..."
  for ROLE in "roles/aiplatform.user" "roles/bigquery.jobUser" "roles/bigquery.dataViewer" "roles/storage.objectAdmin"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${COMPUTE_SA}" \
      --role="${ROLE}" \
      --condition=None --quiet &>/dev/null || true
  done
fi

# 6. requirements.txt の同期と insight/.env の動的生成
echo "[4/6] Synchronizing requirements.txt and generating insight/.env..."
cp requirements.txt insight/requirements.txt

cat <<EOF > insight/.env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=global
GCS_BUCKET=${GCS_BUCKET}
EOF

# 7. ADK CLI の準備 (未インストールの場合は自動インストール)
echo "[5/6] Resolving ADK CLI tool..."
if [ -f ".venv/bin/adk" ]; then
  ADK_CMD=".venv/bin/adk"
elif command -v adk &> /dev/null; then
  ADK_CMD="adk"
else
  echo "'adk' command not found. Installing dependencies..."
  pip install --quiet -r requirements.txt || pip3 install --quiet -r requirements.txt
  if command -v adk &> /dev/null; then
    ADK_CMD="adk"
  else
    ADK_CMD="python3 -m google.adk.cli"
  fi
fi

# 8. ADK Cloud Run デプロイの実行
echo "[6/6] Deploying '${SERVICE_NAME}' with Web UI to Cloud Run..."
${ADK_CMD} deploy cloud_run \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --service_name "${SERVICE_NAME}" \
  --with_ui \
  insight \
  -- \
  --allow-unauthenticated \
  --env-vars-file=insight/.env \
  --memory=2Gi \
  --timeout=600

echo "============================================================"
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)" 2>/dev/null || true)
echo " Deployment completed successfully!"
if [ -n "${SERVICE_URL}" ]; then
  echo " Access Web UI at: ${SERVICE_URL}"
fi
echo "============================================================"


