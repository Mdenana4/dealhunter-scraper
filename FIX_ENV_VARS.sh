#!/bin/bash
# Fix: Set ALL env vars at once using --set-env-vars (which REPLACES all vars)

echo "Setting ALL environment variables on Cloud Run..."
echo "(Using --set-env-vars which REPLACES existing vars)"
echo ""

gcloud run services update dealhunter-api \
  --region=me-central1 \
  --set-env-vars="DATABASE_URL=postgresql://postgres:Egypt99%40%4077777@db.rmkaljwjskxihkuvxosc.supabase.co:5432/postgres,PAYMOB_API_KEY=ZXlKaGJHY2lPaUpJVXpVeE1pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SmpiR0Z6Y3lJNklrMWxjbU5vWVc1MElpd2ljSEp2Wm1sc1pWOXdheUk2TVRFMk16VXdOU3dpYm1GdFpTSTZJbWx1YVhScFlXd2lmUS5wTk54NnBibHhPS2dWUVQ0UHdITjQ2U2JuT3pVSnVHQ2R0Ukxoak9ONUpmMmpjamdxTzdxblFUWGNHQjYyaG1Fd3RINEktc0RIbklqdWNvQWhFbzFGUQ==,PAYMOB_INTEGRATION_ID=4547446,PAYMOB_IFRAME_ID=833328,MIN_DISCOUNT=40,FLASK_SECRET_KEY=dealhunter-secret-$(openssl rand -hex 16)"

echo ""
echo "Verifying env vars are set..."
gcloud run services describe dealhunter-api --region=me-central1 --format='value(spec.template.spec.containers[0].env)' | tr ',' '\n' | grep -E "DATABASE_URL|PAYMOB"

echo ""
echo "Testing health endpoint..."
sleep 5
API_URL=$(gcloud run services describe dealhunter-api --region=me-central1 --format='value(status.url)')
curl -s "$API_URL/health" | python3 -m json.tool 2>/dev/null
