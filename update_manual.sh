#!/bin/bash
# update_manual.sh
# 更新用户手册：重新生成 PDF，并同步到 Vercel public 目录
# 用法: bash update_manual.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📄 生成 PDF..."
node "$SCRIPT_DIR/make_pdf_temp.js"

echo "📦 同步到 frontend/public/manual/..."
cp "$SCRIPT_DIR/docs/user_manual.html" "$SCRIPT_DIR/frontend/public/manual/"
cp "$SCRIPT_DIR/docs/user_manual.pdf"  "$SCRIPT_DIR/frontend/public/manual/"

echo "✅ 完成！可以 git add & commit 了。"
