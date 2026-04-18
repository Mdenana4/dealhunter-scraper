# CI/CD & Deployment Setup Guide

This document explains the CI/CD pipelines and deployment configuration for the DealHunter Scraper project.

## 📋 Overview

The project has been configured with multiple automated workflows:

1. **Backend Tests & Lint** - Code quality checks
2. **Docker Build Check** - Validates Docker image builds
3. **Flutter APK Build** - Builds the admin app for Android
4. **Deploy to Render** - Auto-deploys backend to Render hosting

## 🚀 GitHub Actions Workflows

### 1. Backend Tests & Lint (`.github/workflows/backend-tests.yml`)

**Triggers:**
- On push to `main` or `develop` branches
- On pull requests to `main` or `develop`
- Only when: `server.py`, `scraper.py`, or `requirements.txt` change

**What it does:**
- ✅ Lints Python code using `flake8`
- ✅ Verifies all dependencies install correctly
- ✅ Checks Python syntax

**View results:** GitHub Actions tab → Backend Tests & Lint

---

### 2. Docker Build Check (`.github/workflows/docker-build.yml`)

**Triggers:**
- On push to `main` or `develop` when `Dockerfile` or `requirements.txt` change
- On pull requests to `main` or `develop` with the same triggers

**What it does:**
- ✅ Builds Docker image without pushing
- ✅ Uses GitHub Actions cache for faster builds
- ✅ Validates Dockerfile syntax and dependencies

**View results:** GitHub Actions tab → Docker Build Check

---

### 3. Flutter APK Build (`.github/workflows/flutter-build.yml`)

**Triggers:**
- On push to `main` when `app/admin_app/**` changes
- Manual trigger with workflow_dispatch
- On pull requests when Flutter code changes

**What it does:**
- ✅ Sets up Java 17 and Flutter SDK
- ✅ Gets Flutter dependencies
- ✅ Builds release APK
- ✅ Uploads APK as artifact (30 day retention)
- ✅ Uploads build logs if build fails

**Download APK:**
1. Go to GitHub Actions → Flutter APK Build
2. Click the latest successful workflow run
3. Download `app-release.apk` artifact

---

### 4. Deploy to Render (`.github/workflows/deploy-render.yml`)

**Triggers:**
- On push to `main` branch when backend files change
- Manual trigger with workflow_dispatch

**What it does:**
- ✅ Triggers Render deployment via webhook
- ✅ Shows deployment status
- ✅ Links to Render dashboard

**Setup Instructions:**

1. Get your Render Deploy Hook:
   - Go to https://dashboard.render.com/
   - Select your service (dealhunter-scraper)
   - Go to Settings → Deploy Hook
   - Copy the full URL

2. Add as GitHub Secret:
   - Go to GitHub repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `RENDER_DEPLOY_HOOK`
   - Value: Paste the Render deploy hook URL
   - Click "Add secret"

3. Done! Future pushes to `main` will auto-deploy.

**Verify deployment:**
- Check: https://dashboard.render.com/web/srv-d7cnfijeo5us73fekul0/logs?r=1h

---

## 📦 Render Configuration

### File: `render.yaml`

This file configures the service on Render. Key settings:

```yaml
- runtime: docker         # Uses Dockerfile
- region: ohio           # US data center
- plan: free             # Free tier
- healthCheckPath: /health  # Health endpoint
- autoDeploy: true       # Auto-deploy on push
```

### Environment Variables on Render

Go to Service Settings → Environment:

```
FLASK_ENV=production
PYTHON_VERSION=3.11
FIREBASE_CREDENTIALS_JSON=[Your Firebase JSON]
```

**Important:** Configure `FIREBASE_CREDENTIALS_JSON` in Render dashboard with your Firebase service account JSON.

---

## 🔧 Local Testing

### Test Backend Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask server
python server.py

# Server runs on http://localhost:5000
```

### Test Docker Build

```bash
# Build image
docker build -t dealhunter-scraper .

# Run container
docker run -p 5000:5000 dealhunter-scraper
```

### Test Flutter Build

```bash
# Navigate to admin app
cd app/admin_app

# Get dependencies
flutter pub get

# Build APK
flutter build apk --release

# APK location: build/app/outputs/flutter-apk/app-release.apk
```

---

## 📊 Deployment Pipeline

```
┌─────────────────┐
│  Push to main   │
└────────┬────────┘
         │
         ├─→ Backend Tests & Lint ────┐
         ├─→ Docker Build Check ──────┤
         └─→ Flutter APK Build ───────┤
                                      │
                                      ▼
                            ✅ All Checks Pass?
                                      │
                            ┌─────────┴─────────┐
                            │   YES      NO     │
                            ▼                   ▼
                        Deploy         PR/Review
                        to Render      Required
```

---

## ✅ Build Status Badge

Add to your README:

```markdown
[![Backend Tests](https://github.com/Mdenana4/dealhunter-scraper/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/Mdenana4/dealhunter-scraper/actions)
[![Docker Build](https://github.com/Mdenana4/dealhunter-scraper/actions/workflows/docker-build.yml/badge.svg)](https://github.com/Mdenana4/dealhunter-scraper/actions)
[![Flutter Build](https://github.com/Mdenana4/dealhunter-scraper/actions/workflows/flutter-build.yml/badge.svg)](https://github.com/Mdenana4/dealhunter-scraper/actions)
```

---

## 🐛 Troubleshooting

### Render Deployment Not Triggering

**Problem:** "Warning: RENDER_DEPLOY_HOOK secret not configured"

**Solution:**
1. Go to https://dashboard.render.com/web/srv-d7cnfijeo5us73fekul0/settings
2. Copy Deploy Hook URL from Settings section
3. Add to GitHub Secrets as `RENDER_DEPLOY_HOOK`

### Docker Build Fails

Check `.github/workflows/docker-build.yml` logs in GitHub Actions:
1. Go to Actions tab
2. Click "Docker Build Check"
3. Click failed workflow
4. Expand the "Build Docker image" step to see error

### Flutter APK Build Fails

1. Go to Actions → Flutter APK Build → failed run
2. Check "Build APK (Release)" step output
3. Download `flutter-build-log` artifact for full logs

---

## 📝 Next Steps

1. ✅ Push this commit to `main`
2. ✅ Monitor GitHub Actions for first workflow run
3. ✅ Set up Render Deploy Hook secret if not already done
4. ✅ Verify deployment on https://dealhunter-scraper.onrender.com/

---

## 📚 Resources

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Render Deployment Docs](https://render.com/docs)
- [Docker Documentation](https://docs.docker.com)
- [Flutter Build Documentation](https://flutter.dev/docs/deployment/android)
