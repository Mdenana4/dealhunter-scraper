# DealHunter Scraper
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PIP_NO_CACHE_DIR=1     PORT=5000

RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl wget ca-certificates fonts-liberation     libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2     libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3     libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2     libxss1 libgtk-3-0 fontconfig     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip &&     pip install -r requirements.txt &&     pip install playwright &&     playwright install chromium

# CACHE BUST v7
COPY . .
RUN chmod +x start.sh

RUN curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js -o firebase-app-compat.js &&     curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-firestore-compat.js -o firebase-firestore-compat.js &&     curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-auth-compat.js -o firebase-auth-compat.js

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3     CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}
CMD ["sh", "start.sh"]
