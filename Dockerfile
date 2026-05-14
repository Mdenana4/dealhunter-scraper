# DealHunter Egypt - Production Dockerfile for Google Cloud Run
# =============================================================
# Multi-stage build with Python 3.11-slim for minimal image size
#
# Build:
#   docker build -t dealhunter-api .
#
# Run:
#   docker run -p 8080:8080 --env-file .env dealhunter-api
#
# Deploy:
#   gcloud run deploy dealhunter-api --source .

FROM python:3.11-slim

LABEL maintainer="DealHunter Engineering"
LABEL version="1.0.0"
LABEL description="DealHunter Egypt API - Flask backend for Cloud Run"

# ---- Environment ----
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PORT=8080

# ---- Security: Create non-root user ----
RUN groupadd -r dealhunter && useradd -r -g dealhunter -s /sbin/nologin -d /app dealhunter

# ---- System Dependencies ----
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libc6-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# ---- Working Directory ----
WORKDIR /app

# ---- Python Dependencies (cached layer) ----
# Copy only requirements first for optimal Docker layer caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libc6-dev libssl-dev

# ---- Application Code ----
COPY server_cloudrun.py /app/main.py

# ---- Ownership ----
RUN chown -R dealhunter:dealhunter /app

# ---- Health Check ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# ---- User ----
USER dealhunter

# ---- Expose Port ----
EXPOSE 8080

# ---- Run ----
# Gunicorn: 2 workers, 4 threads each, 120s timeout
# Using Uvicorn worker for async compatibility if needed in future
CMD exec gunicorn \
    --bind :8080 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance \
    main:app
