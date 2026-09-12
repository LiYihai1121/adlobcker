# syntax=docker/dockerfile:1
# ===== 多阶段构建：前端(TS+Tailwind) -> 后端(FastAPI+uvicorn) =====

# ---- Stage 1: 构建前端控制台（TypeScript 编译 + Tailwind 压缩）----
FROM node:20-slim AS frontend
WORKDIR /build
# 先拷 package.json 利用层缓存（package-lock 保证可复现安装）
COPY frontend/package.json frontend/package-lock.json* ./frontend/
# 构建依赖 typescript/tailwindcss/daisyui 在 devDependencies，故不省略 dev
RUN cd frontend && npm ci || npm install
# 再拷前端源码与已提交的 index.html 模板
COPY frontend/ ./frontend/
COPY app/static/ ./app/static/
# 构建：tsc -> ../app/static/app.js；tailwind -> ../app/static/style.css（均落在 /build/app/static/）
RUN cd frontend && npm run build

# ---- Stage 2: Python 运行时 ----
FROM python:3.11-slim
WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷后端代码（.dockerignore 已过滤 node_modules/venv/tests/data 等）
COPY . .

# 用第一阶段构建出的前端产物覆盖（保证镜像内始终是最新构建，而非陈旧提交）
COPY --from=frontend /build/app/static ./app/static

# SQLite 数据目录（持久化挂载点）
RUN mkdir -p /app/data
ENV ADBLOCK_DB_PATH=/app/data/adblock.db \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# 健康检查：探测 /health，失败则容器标记为 unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

