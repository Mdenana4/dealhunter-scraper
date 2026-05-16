FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 curl ca-certificates \
    libxml2 libxslt1.1 && rm -rf /var/lib/apt/lists/*

COPY scraper_requirements.txt .
RUN pip install --no-cache-dir -r scraper_requirements.txt

RUN python -m playwright install chromium --with-deps

COPY scraper_cloudrun.py ./
COPY scraper_job.py ./

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
ENV SCRAPEDO_TOKEN=3041e7da00be45828a61c399c063750ba0cb05219d0
ENV DATABASE_URL=postgresql://postgres:Egypt99%40%4077777@db.rmkaljwjskxihkuvxosc.supabase.co:5432/postgres
ENV TIMESCALE_URL=postgresql://postgres:Egypt99%40%4077777@db.rmkaljwjskxihkuvxosc.supabase.co:5432/postgres
ENV AMAZON_ENABLED=true
ENV NOON_ENABLED=true
ENV JUMIA_ENABLED=true
ENV MIN_DISCOUNT=40
ENV MIN_PRODUCT_PRICE=50
ENV MAX_DISCOUNT_THRESHOLD=90
ENV REQUEST_TIMEOUT=45
ENV MIN_REQUEST_INTERVAL=2.0
ENV KEYWORD_DISCOVERY_ENABLED=false

CMD ["python3", "scraper_job.py"]
