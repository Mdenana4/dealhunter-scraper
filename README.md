# DealHunter Egypt — Deployment Guide

## 3 Services to Deploy

| Service | Platform | What It Does | Folder |
|---------|----------|-------------|--------|
| **Flutter App** | GitHub → CodeMagic | Mobile app (Android/iOS) | `flutter/` |
| **Flask API** | Render | Backend REST API | `api/` |
| **Python Scraper** | Railway | Daily deal scraping | `scraper/` |

---

## QUICK START (3 Steps)

### Step 1: Push Flutter to GitHub (30 seconds)

```bash
cd flutter/
git init
git add -A
git commit -m "init: DealHunter Egypt v1.0"
git branch -M main
# Paste YOUR repo URL:
git remote add origin https://github.com/YOUR_USERNAME/dealhunter.git
git push -u origin main --force
```

### Step 2: Deploy API to Render (2 minutes)

**Option A — GitHub Auto-Deploy (Recommended):**
1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repo
4. Select the `api/` folder as root
5. Click "Create Web Service"

**Option B — CLI:**
```bash
npm install -g @render/cli
render login
cd api/
render deploy
```

### Step 3: Deploy Scraper to Railway (2 minutes)

```bash
npm install -g @railway/cli
railway login
railway init --name dealhunter-scraper
cd scraper/
railway up
```

---

## Environment Variables

### Render (API) — Set in Dashboard
```
FIREBASE_KEY_JSON=<your-firebase-service-account-json>
SCRAPEDO_TOKEN=<your-scrape.do-token>
PAYMOB_API_KEY=<your-paymob-key>
PAYMOB_INTEGRATION_ID=<your-integration-id>
PAYMOB_HMAC_SECRET=<your-hmac-secret>
TAP_SECRET_KEY=<your-tap-secret>
FLASK_SECRET_KEY=<random-secret>
```

### Railway (Scraper) — Set in Dashboard
```
FIREBASE_KEY_JSON=<your-firebase-service-account-json>
SCRAPEDO_TOKEN=<your-scrape.do-token>
SCRAPER_API_KEY=<your-scraperapi-key>
RAPIDAPI_KEY=<your-rapidapi-key>
SAFQA_ACCESS_TOKEN=<your-safqa-token>
MIN_DISCOUNT=40
SCRAPE_INTERVAL_MINUTES=360
```

---

## After Deployment

1. **CodeMagic**: Go to https://codemagic.io → Sign in with GitHub → Add `dealhunter` app → Build → Download APK
2. **Test**: Install APK on Android device, open app, verify all 5 screens work
3. **Monitor**: Check Render/Railway dashboards for logs
