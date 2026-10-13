# syntax=docker/dockerfile:1
# =============================================================================
# Afya Smart — platform image (FastAPI :8000)
# Inajenga dashboard (admin), patient app na mobile PWA kwa Node, kisha
# inaendesha API pamoja na frontends zilizojengwa (dashboard/dist n.k.).
#
# Build context ni mzizi wa repo (si backend/):
#   docker build -f backend/Dockerfile -t afya-api .
# =============================================================================

# ---------- Stage 1: React frontends (Vite) ---------------------------------
FROM node:22-alpine AS frontend
WORKDIR /src

# Package manifests kwanza → Docker inaweza kucache `npm install` kwa kila app.
COPY dashboard/package.json dashboard/package-lock.json ./dashboard/
COPY patient/package.json patient/package-lock.json ./patient/
COPY mobile/package.json ./mobile/
RUN cd dashboard && npm ci --no-audit --no-fund
RUN cd patient  && npm ci --no-audit --no-fund
# mobile haina package-lock.json (hivyo npm install, si npm ci)
RUN cd mobile   && npm install --no-audit --no-fund

# Source (node_modules na dist zimekatazwa kwenye .dockerignore, hivyo
# COPY hii haiwezi kufuta node_modules zilizowekwa hapo juu).
COPY dashboard/ ./dashboard/
COPY patient/   ./patient/
COPY mobile/    ./mobile/
RUN cd dashboard && npm run build
RUN cd patient   && npm run build
RUN cd mobile    && npm run build

# ---------- Stage 2: Python runtime -----------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements kwanza → cache ya pip haivunjwi kila wakati source inabadilika.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

# Backend source + ML model (ml_triage.py inatafuta ../ml/models/triage_model.pkl)
COPY backend/ ./backend/
COPY ml/models/ ./ml/models/

# Frontends zilizojengwa kutoka stage ya kwanza
COPY --from=frontend /src/dashboard/dist ./dashboard/dist
COPY --from=frontend /src/patient/dist   ./patient/dist
COPY --from=frontend /src/mobile/dist    ./mobile/dist

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status==200 else 1)"

CMD ["sh", "start.sh"]
