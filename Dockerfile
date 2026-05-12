# DealHunter Scraper - Python Flask Backend
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=server.py \
    FLASK_ENV=production \
    PORT=5000

# Install system dependencies (including Chromium for Playwright/Safqa)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxss1 \
    libgtk-3-0 \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install playwright && \
    playwright install chromium

# Cache bust to force fresh code copy (increment when deploying new code)
ARG CACHE_BUST=4

# Copy all application code (see .dockerignore for exclusions)
COPY . .
RUN chmod +x start.sh railway_start.sh

# Download Firebase SDK at build time so it's self-hosted from Railway.
# The browser only needs to reach our own domain — no gstatic.com / unpkg needed.
RUN curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js      -o firebase-app-compat.js && \
    curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore-compat.js -o firebase-firestore-compat.js && \
    curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-auth-compat.js      -o firebase-auth-compat.js

# Health check uses $PORT (Railway overrides at runtime via env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose default port (Railway overrides PORT env var at runtime)
EXPOSE ${PORT}

# Railway: use lightweight health_server.py instead of heavy server.py
CMD ["sh", "railway_start.sh"]
