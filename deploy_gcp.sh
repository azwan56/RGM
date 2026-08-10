#!/bin/bash
set -e

# 配置变量
PROJECT_ID="gentrain-10952"
REGION="asia-east1"
SERVICE_NAME="rgm-backend"
CRON_SECRET="${CRON_SECRET:-rgm_cron_secret_2026}"

echo "=========================================="
echo "🚀 开始部署 RGM 后端至 GCP Cloud Run"
echo "Project ID: ${PROJECT_ID}"
echo "Region:     ${REGION}"
echo "=========================================="

# 1. 切换并设置当前 GCP 项目
gcloud config set project "${PROJECT_ID}"

# 2. 启用必须的 GCP 云服务 API
echo "📦 正在启用 GCP API 服务 (Cloud Run, Cloud Build, Cloud Scheduler)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com

# 3. 确保默认服务账号拥有 Cloud Datastore/Firestore 用户权限及 Cloud Run Invoker 权限
echo "🔑 正在配置 IAM 角色权限 (roles/datastore.user & roles/run.invoker)..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/datastore.user" || true

# Generate env.yaml for Cloud Run deployment
cat <<EOF > .env.yaml
DISABLE_IN_MEMORY_SCHEDULER: "true"
DISABLE_WECOM_BOT: "true"
CRON_SECRET: "${CRON_SECRET}"
CORS_ORIGINS: "http://localhost:3000,http://localhost:8000,https://rgm.vanpower.live"
EOF
# Append backend/.env contents to .env.yaml
awk -F '=' '/^[a-zA-Z_]+=/ { printf "%s: \"%s\"\n", $1, $2 }' backend/.env >> .env.yaml

gcloud run deploy "${SERVICE_NAME}" \
  --source ./backend \
  --region "${REGION}" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 10 \
  --env-vars-file .env.yaml

# 获取部署后的 Cloud Run 服务域名
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")

# 允许 Cloud Scheduler 的 Service Account 显式调用 Cloud Run
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --region "${REGION}" \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker" || true

echo "✅ Cloud Run 部署成功！后端 URL: ${SERVICE_URL}"

# 5. 创建 / 更新 GCP Cloud Scheduler 定时同步任务
SCHEDULER_JOB_NAME="rgm-daily-sync-job"
echo "⏰ 正在配置 Cloud Scheduler 每日定时同步任务 (${SCHEDULER_JOB_NAME})..."

if gcloud scheduler jobs describe "${SCHEDULER_JOB_NAME}" --location "${REGION}" >/dev/null 2>&1; then
  echo "更新已存在的 Cloud Scheduler 任务..."
  gcloud scheduler jobs update http "${SCHEDULER_JOB_NAME}" \
    --location "${REGION}" \
    --schedule "0 * * * *" \
    --uri "${SERVICE_URL}/api/cron/daily-sync" \
    --http-method POST \
    --update-headers "X-Cron-Secret=${CRON_SECRET}" \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${SERVICE_URL}"
else
  echo "新建 Cloud Scheduler 任务..."
  gcloud scheduler jobs create http "${SCHEDULER_JOB_NAME}" \
    --location "${REGION}" \
    --schedule "0 * * * *" \
    --uri "${SERVICE_URL}/api/cron/daily-sync" \
    --http-method POST \
    --headers "X-Cron-Secret=${CRON_SECRET}" \
    --oidc-service-account-email="${SERVICE_ACCOUNT}" \
    --oidc-token-audience="${SERVICE_URL}"
fi

echo "=========================================="
echo "🎉 部署与 Cron 定时任务配置全部完成！"
echo "1. 后端 API URL: ${SERVICE_URL}"
echo "2. 健康检查接口: ${SERVICE_URL}/api/health"
echo "3. 请更新前端 .env.local 中的 NEXT_PUBLIC_BACKEND_URL=${SERVICE_URL}"
echo "=========================================="
