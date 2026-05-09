# Safqa Migration Guide: Proxy → Headless Browser

## Problem
Both scrape.do and ScraperAPI are dead (502/401). Safqa price verification
has been returning `[SAFQA] Not found` for weeks because the scraper cannot
reach safqaprice.com.

## Solution: Playwright Headless Browser
`safqa_browser.py` uses Chromium to render Safqa's React SPA directly.
No proxy needed. Cloudflare sees a real browser and doesn't block.

## Railway Setup (One-Time, 5 Minutes)

### Step 1: Update Dockerfile
Add system dependencies for Chromium. In your Railway Dockerfile, add:

```dockerfile
# Add BEFORE pip install:
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libxss1 libgtk-3-0 wget curl ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Add AFTER pip install:
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps chromium
```

See `Dockerfile.safqa` for the complete reference.

### Step 2: Update requirements.txt
Add: `playwright>=1.40.0`

### Step 3: Update fake_checker.py
At the top, add:
```python
from safqa_browser import check_safqa
```

Replace the old `check_safqa(asin)` call with:
```python
result = check_safqa(asin=asin)
```

At scraper shutdown, add:
```python
from safqa_browser import shutdown_browser
shutdown_browser()
```

### Step 4: Deploy
Railway auto-deploys from `main`. Or trigger: `railway up`

## How It Works

```
fake_checker.py → safqa_browser.py → Headless Chromium → safqaprice.com
                                      (renders React SPA)
```

## Memory
- Chromium: ~250MB RAM (one-time, browser is reused)
- Railway free tier (512MB): sufficient
- If OOM: upgrade to Starter plan (1GB)

## Files Added
- `safqa_browser.py` — Main module (drop-in replacement)
- `Dockerfile.safqa` — Dockerfile reference
- `MIGRATION_GUIDE.md` — This file
