#!/bin/bash

# Determine current directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/backend"

# Force gRPC to use macOS native DNS resolver (resolves timeout errors under NordVPN)
export GRPC_DNS_RESOLVER=native

# Find local IP
LOCAL_IP=$(ipconfig getifaddr en0)
echo "------------------------------------------------"
echo "🚀 RGM 本地后端启动助手"
echo "Mac 当前局域网 IP: $LOCAL_IP"
echo "------------------------------------------------"

# Detect if a local proxy is running on common ports (7890, 1087)
PROXY_PORT=""
if lsof -i :7890 -sTCP:LISTEN >/dev/null 2>&1; then
    PROXY_PORT="7890"
elif lsof -i :1087 -sTCP:LISTEN >/dev/null 2>&1; then
    PROXY_PORT="1087"
fi

if [ -n "$PROXY_PORT" ]; then
    echo "💡 检测到本地代理服务器运行在端口: $PROXY_PORT"
    echo "正在自动为命令行终端配置代理环境 (http/https_proxy)..."
    export http_proxy="http://127.0.0.1:$PROXY_PORT"
    export https_proxy="http://127.0.0.1:$PROXY_PORT"
    export grpc_proxy="http://127.0.0.1:$PROXY_PORT"
else
    echo "⚠️ 未检测到运行在 7890 或 1087 端口的本地代理。"
    echo "如果稍后连接 Firestore/Firebase 超时，请确认是否需要开启代理并将代理端口配置在此脚本中。"
fi

# Run Uvicorn
echo "------------------------------------------------"
echo "正在启动 FastAPI 服务 (0.0.0.0:8000)..."
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
