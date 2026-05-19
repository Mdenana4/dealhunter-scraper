#!/bin/bash
# ═════════════════════════════════════════════════════════════════
# DealHunter Scraper — Cloud Run Job Deployment
# Run this in Google Cloud Shell: https://shell.cloud.google.com
# ═════════════════════════════════════════════════════════════════

set -e

echo "=========================================="
echo "  DealHunter Scraper — Deploy to Cloud Run Job"
echo "=========================================="

PROJECT_ID="dealhunter-egypt-70d29"
REGION="me-central1"

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

# ─── Step 1: Build scraper container ─────────────────────────────
echo ""
echo "Step 1: Building scraper container..."
cd $HOME/dealhunter-deploy

# Create scraper Dockerfile if not exists
cat > Dockerfile.scraper << 'DOCKERFILE'
FROM python:3.11-slim
WORKDIR /app
COPY scraper_requirements.txt .
RUN pip install --no-cache-dir -r scraper_requirements.txt
COPY scraper_cloudrun.py scraper_job.py .
CMD ["python", "scraper_job.py"]
DOCKERFILE

gcloud builds submit --tag gcr.io/$PROJECT_ID/dealhunter-scraper:latest --file Dockerfile.scraper . 2>&1 | tail -5

# ─── Step 2: Deploy as Cloud Run Job ─────────────────────────────
echo ""
echo "Step 2: Deploying scraper as Cloud Run Job..."
gcloud run jobs create dealhunter-scraper \
  --image gcr.io/$PROJECT_ID/dealhunter-scraper:latest \
  --region $REGION \
  --max-retries 1 \
  --tasks 1 \
  --set-env-vars="DATABASE_URL=postgresql://postgres:Egypt99%40%4077777@db.rmkaljwjskxihkuvxosc.supabase.co:5432/postgres" \
  --set-env-vars="MIN_DISCOUNT=40" \
  --set-env-vars="AMAZON_ENABLED=true" \
  --set-env-vars="NOON_ENABLED=true" \
  --set-env-vars="JUMIA_ENABLED=true" \
  --set-env-vars="KEYWORD_DISCOVERY_ENABLED=false" \
  2>&1 || echo "Job may already exist, updating..."

# If job exists, update it
gcloud run jobs update dealhunter-scraper \
  --image gcr.io/$PROJECT_ID/dealhunter-scraper:latest \
  --region $REGION \
  --max-retries 1 \
  --set-env-vars="DATABASE_URL=postgresql://postgres:Egypt99%40%4077777@db.rmkaljwjskxihkuvxosc.supabase.co:5432/postgres" \
  --set-env-vars="MIN_DISCOUNT=40" \
  2>&1 | tail -5

# ─── Step 3: Create Cloud Scheduler (every 4 hours) ──────────────
echo ""
echo "Step 3: Creating Cloud Scheduler trigger (every 4 hours)..."
gcloud scheduler jobs create http dealhunter-scraper-cron \
  --schedule "0 */4 * * *" \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/dealhunter-scraper:run" \
  --http-method POST \
  --oauth-service-account "$PROJECT_ID@appspot.gserviceaccount.com" \
  --location $REGION \
  2>&1 || echo "Scheduler may already exist"

echo ""
echo "Step 4: Run scraper manually now?"
echo "  gcloud run jobs execute dealhunter-scraper --region=$REGION"

echo ""
echo "=========================================="
echo "  SCRAPER DEPLOYED"
echo "=========================================="
echo "Schedule: Every 4 hours (6 times/day)"
echo "Job: dealhunter-scraper"
echo "Image: gcr.io/$PROJECT_ID/dealhunter-scraper:latest"
echo ""
echo "To run now: gcloud run jobs execute dealhunter-scraper --region=$REGION"
echo "To check logs: gcloud logging read 'resource.type=cloud_run_job' --limit=20"
