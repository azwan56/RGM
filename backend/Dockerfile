FROM python:3.11-slim

WORKDIR /app

# 防止 Python 生成 .pyc 文件并允许 stdout/stderr 实时打印
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有文件
COPY . .

# 暴露 8000 端口（Cloud Run 会注入 PORT 环境变量）
ENV PORT=8000
EXPOSE 8000

# 使用 uvicorn 启动
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
