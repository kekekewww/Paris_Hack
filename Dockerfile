# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
COPY assets/brand.png ./assets/brand.png
COPY scripts/prepare-assets.mjs ./scripts/prepare-assets.mjs
COPY data/official-sources.json ./data/official-sources.json
ARG VITE_SERVICE_MODE=api
ENV VITE_SERVICE_MODE=${VITE_SERVICE_MODE}
# prepare-assets 會從鎖定的 pdfjs-dist 複製字型、CMap、WASM 與 ICC。
# Worker 由 Vite 的本機資產 import 併入 dist，不依賴外部 CDN。
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CASE_DB_PATH=/app/.local/cases.sqlite3 \
    LLM_PROVIDER=grounded_rules \
    SESSION_COOKIE_SECURE=false
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/constraints.txt /tmp/dependencies/
RUN python -m pip install --no-cache-dir \
    --constraint /tmp/dependencies/constraints.txt \
    --requirement /tmp/dependencies/requirements.txt \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin claim \
    && mkdir -p /app/.local \
    && chown 10001:10001 /app/.local
COPY backend/app ./backend/app
COPY data/official-sources.json ./data/official-sources.json
COPY --from=frontend /build/dist ./dist
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5).close()"]
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
