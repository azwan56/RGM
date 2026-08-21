#!/bin/bash
set -e

# ==============================================================================
# RGM 国内版 (Alibaba Cloud ECS 一键生产部署与 SSL 签发脚本)
# 适用域名: rgm.vanpower.net
# ==============================================================================

DOMAIN="rgm.vanpower.net"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
SSL_DIR="${DEPLOY_DIR}/ssl"

echo "=========================================================="
echo "🚀 开始部署 RGM 跑团与 AI 教练服务到阿里云 ECS"
echo "🌐 绑定域名: ${DOMAIN}"
echo "📁 部署目录: ${DEPLOY_DIR}"
echo "=========================================================="

mkdir -p "${SSL_DIR}"

# 1. 检查并安装 Docker & Docker Compose (若未安装)
if ! command -v docker &> /dev/null; then
    echo "📦 正在安装 Docker..."
    curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
    systemctl enable docker
    systemctl start docker
fi

# 2. 检查 SSL 证书
if [ ! -f "${SSL_DIR}/fullchain.pem" ] || [ ! -f "${SSL_DIR}/privkey.pem" ]; then
    echo "🔒 未检测到现有 SSL 证书，正在使用 Certbot 自动为 ${DOMAIN} 申请免费 Let's Encrypt 证书..."
    
    # 临时释放 80 端口以完成 HTTP-01 验证
    docker stop rgm-nginx 2>/dev/null || true
    
    if ! command -v certbot &> /dev/null; then
        echo "📦 安装 Certbot 工具..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y certbot
        elif command -v yum &> /dev/null; then
            yum install -y epel-release certbot
        fi
    fi

    # 申请证书
    certbot certonly --standalone -d "${DOMAIN}" --agree-tos --register-unsafely-without-email --non-interactive || true

    if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
        echo "✅ 证书申请成功！正在链接到部署目录..."
        cp -L "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${SSL_DIR}/fullchain.pem"
        cp -L "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${SSL_DIR}/privkey.pem"
    else
        echo "⚠️ 自动申请证书未完成（若提示连接超时，请确认云服务器安全组已放行 80/443 端口）。"
        echo "正在生成自签名临时证书以确保 Nginx 顺利启动..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "${SSL_DIR}/privkey.pem" \
            -out "${SSL_DIR}/fullchain.pem" \
            -subj "/CN=${DOMAIN}"
    fi
else
    echo "✅ 已检测到有效 SSL 证书。"
fi

# 3. 准备环境变量文件
if [ ! -f "${DEPLOY_DIR}/.env.production" ]; then
    echo "⚙️ 创建 .env.production 配置文件..."
    cp "${DEPLOY_DIR}/.env.production.example" "${DEPLOY_DIR}/.env.production"
    echo "⚠️ 请确保在 ${DEPLOY_DIR}/.env.production 中填写正确的 Supabase 与微信凭据。"
fi

# 4. 构建并启动容器
echo "🐳 正在拉取镜像并构建启动容器..."
cd "${DEPLOY_DIR}"
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d --build

echo "=========================================================="
echo "🎉 RGM 生产服务部署成功！"
echo "🌐 访问地址: https://${DOMAIN}"
echo "📡 API 健康检测: https://${DOMAIN}/api/health"
echo "=========================================================="
docker compose -f docker-compose.prod.yml ps
