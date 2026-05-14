#!/bin/bash
# Final comprehensive test of DealHunter API

echo "========================================"
echo "  DealHunter API - Final Test"
echo "========================================"

API_URL=$(gcloud run services describe dealhunter-api --region=me-central1 --format='value(status.url)')
echo "API URL: $API_URL"
echo ""

echo "[1/8] Health Check"
curl -s "$API_URL/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  Status: {d['data']['status']}\"); print(f\"  Supabase: {d['data']['databases']['supabase']['status']}\"); print(f\"  PayMob: {d['data']['config']['paymob_configured']}\")"

echo ""
echo "[2/8] List Deals (default min_discount=40)"
curl -s "$API_URL/api/deals?limit=3" | python3 -c "import sys,json; d=json.load(sys.stdin); deals=d.get('data',{}).get('deals',[]); print(f\"  Deals: {len(deals)}\"); [print(f\"    {x['title'][:40]} | {x['site']} | {x['discount_percent']}% | {x['verdict']}\") for x in deals]"

echo ""
echo "[3/8] Filter by Source (amazon_eg)"
curl -s "$API_URL/api/deals?source=amazon_eg&limit=3" | python3 -c "import sys,json; d=json.load(sys.stdin); deals=d.get('data',{}).get('deals',[]); print(f\"  Amazon deals: {len(deals)}\"); [print(f\"    {x['title'][:40]} | {x['discount_percent']}%\") for x in deals]"

echo ""
echo "[4/8] Filter by Category (electronics)"
curl -s "$API_URL/api/deals?category=electronics&limit=3" | python3 -c "import sys,json; d=json.load(sys.stdin); deals=d.get('data',{}).get('deals',[]); print(f\"  Electronics deals: {len(deals)}\")"

echo ""
echo "[5/8] Membership Tiers"
curl -s "$API_URL/api/membership/tiers" | python3 -c "import sys,json; d=json.load(sys.stdin); tiers=d.get('data',{}).get('tiers',[]); print(f\"  Tiers: {len(tiers)}\"); [print(f\"    {x['id']}: {x['name']} - {x['price_egp']} EGP\") for x in tiers]"

echo ""
echo "[6/8] Deal Verification"
curl -s "$API_URL/api/verify?marketplace_country=amazon_eg&product_id=B08N5WRWNW" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',{}); print(f\"  Verdict: {data.get('verdict')}\"); print(f\"  Confidence: {data.get('confidence')}\"); print(f\"  Recommendation: {data.get('recommendation')}\")"

echo ""
echo "[7/8] Response Time Test"
for i in 1 2 3; do
    TIME=$(curl -o /dev/null -s -w "%{time_total}" "$API_URL/health")
    echo "  Request $i: ${TIME}s"
done

echo ""
echo "[8/8] PayMob Payment Initiate (test)"
curl -s -X POST "$API_URL/api/payment/paymob/initiate" \
  -H "Content-Type: application/json" \
  -d '{"tier":"premium","user_id":"test_user_123"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  Success: {d.get('success')}\"); print(f\"  Has iframe_url: {'iframe_url' in d.get('data',{})}\")"

echo ""
echo "========================================"
echo "  ALL TESTS COMPLETE"
echo "========================================"
