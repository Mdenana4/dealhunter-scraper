# Phase 5 Deployment Guide

## Deployment Checklist

- [ ] Verify all Phase 5 endpoints work locally
- [ ] Create Stripe products (Premium & VIP)
- [ ] Get Stripe API keys (test & live)
- [ ] Set environment variables on Render
- [ ] Create Stripe webhook endpoint
- [ ] Create Firestore indexes
- [ ] Deploy to Render
- [ ] Test with Stripe test mode
- [ ] Switch to live Stripe keys (production)

---

## Step 1: Local Testing

### Run the test script:
```bash
cd D:\Python\Panadas\dealhunter
python test_phase5.py
```

**Expected output:**
```
=== HEALTH CHECK ===
✓ Health check

=== ENDPOINT AVAILABILITY ===
✓ POST /api/v1/users (Status: 400)
✓ GET /api/v1/users/test-uid (Status: 401)
✓ POST /api/v1/subscriptions/checkout (Status: 401)
...
```

---

## Step 2: Stripe Setup

### 2.1 Create Stripe Products

1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Navigate to **Products** → **+ Add Product**

**Product 1: Premium Monthly**
- **Name:** `Premium Monthly`
- **Type:** Service
- **Price:** EGP 99.00
- **Billing period:** Monthly
- **Save product**

**Product 2: VIP Monthly**
- **Name:** `VIP Monthly`
- **Type:** Service
- **Price:** EGP 199.00
- **Billing period:** Monthly
- **Save product**

### 2.2 Get API Keys

1. Go to **Developers** → **API Keys**
2. Copy **Secret Key** (test mode)
   - Example: `sk_test_51234567890abcdefg...`
3. Copy **Publishable Key** (test mode)
   - Example: `pk_test_51234567890abcdefg...`

---

## Step 3: Set Environment Variables (Render)

### 3.1 Render Dashboard

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your DealHunter service
3. Go to **Environment**
4. Add the following variables:

```
STRIPE_SECRET_KEY=sk_test_51234567890abcdefg...
STRIPE_PUBLISHABLE_KEY=pk_test_51234567890abcdefg...
STRIPE_WEBHOOK_SECRET=(leave blank for now)
```

5. Click **Save** and wait for auto-redeploy

---

## Step 4: Deploy to Render

### Check if already deployed:
```bash
git status
git log -1 --oneline
```

### Deploy latest code:
```bash
cd D:\Python\Panadas\dealhunter
git add -A
git commit -m "feat: Phase 5 - Stripe integration, user groups, referrals"
git push origin main
```

### Monitor deployment:
- Go to Render dashboard
- Watch the **Build & Deploy** logs
- Should see:
  ```
  ✓ Firebase Admin SDK initialized
  ✓ Stripe API key configured
  Starting Flask server on port 10000
  ```

---

## Step 5: Create Stripe Webhook

### 5.1 Create Webhook Endpoint

1. In Stripe Dashboard → **Developers** → **Webhooks**
2. Click **+ Add endpoint**
3. **Endpoint URL:** `https://your-render-url.onrender.com/webhooks/stripe`
   - Replace `your-render-url` with your actual Render service URL
   - Example: `https://dealhunter-scraper.onrender.com/webhooks/stripe`
4. **Events to listen to:** Select these events:
   - `customer.created`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `charge.succeeded`
   - `charge.failed`
   - `invoice.payment_failed`
5. Click **Add endpoint**

### 5.2 Get Webhook Secret

1. After endpoint created, click on it
2. Copy **Signing secret** (starts with `whsec_`)
3. Go back to Render dashboard
4. Add environment variable:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_1234567890abcdefg...
   ```
5. Save and wait for redeploy

---

## Step 6: Create Firestore Indexes

### 6.1 Auto-created Indexes

Firebase will automatically create indexes when you query with multiple fields. But we can create them manually:

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select **dealhunter-egypt-70d29** project
3. Go to **Firestore Database** → **Indexes**
4. Click **Create Index**

**Index 1:**
- Collection: `users`
- Fields: `stripe_customer_id (Ascending)`, `referral_code (Ascending)`
- Create Index

**Index 2:**
- Collection: `subscriptions`
- Fields: `user_id (Ascending)`, `status (Ascending)`
- Create Index

**Index 3:**
- Collection: `referrals`
- Fields: `referrer_id (Ascending)`, `status (Ascending)`
- Create Index

**Index 4:**
- Collection: `user_groups`
- Fields: `owner_id (Ascending)`, `created_at (Descending)`
- Create Index

---

## Step 7: Test Phase 5 with Stripe Test Mode

### 7.1 Test User Creation

```bash
curl -X POST https://your-render-url.onrender.com/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "valid-firebase-token",
    "name": "Test User",
    "phone": "+201234567890"
  }'
```

**Expected response:**
```json
{
  "success": true,
  "user": {
    "uid": "firebase-uid",
    "email": "test@example.com",
    "tier": "free",
    "referral_code": "DEALABCD1234",
    "daily_deal_limit": 50,
    "created_at": "2026-04-14T10:00:00Z"
  }
}
```

### 7.2 Test Stripe Checkout

```bash
curl -X POST https://your-render-url.onrender.com/api/v1/subscriptions/checkout \
  -H "Authorization: Bearer {valid-id-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "tier": "premium",
    "success_url": "https://example.com/success",
    "cancel_url": "https://example.com/cancel"
  }'
```

**Expected response:**
```json
{
  "success": true,
  "checkout_session_id": "cs_test_...",
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

### 7.3 Complete Test Payment

1. Open the returned `checkout_url`
2. Use test card: **4242 4242 4242 4242**
3. Expiry: Any future date (e.g., **12/26**)
4. CVC: Any 3 digits (e.g., **123**)
5. Click **Pay**

### 7.4 Verify Subscription Created

Check Firestore:
1. Go to **Firestore Database**
2. Check **subscriptions** collection
3. Should see a new document with:
   - `status: "active"`
   - `product_name: "Premium Monthly"`
   - `price_amount: 9900` (in cents = EGP 99)

Check webhook logs:
1. Check **webhooks_log** collection
2. Should see entries for:
   - `customer.created`
   - `customer.subscription.created`

---

## Step 8: Production Setup (Live Stripe Keys)

**⚠️ ONLY AFTER TESTING COMPLETE**

### 8.1 Get Live Stripe Keys

1. In Stripe Dashboard, toggle **Test mode** OFF
2. Go to **Developers** → **API Keys**
3. Copy live keys:
   - **Secret Key:** `sk_live_...`
   - **Publishable Key:** `pk_live_...`

### 8.2 Update Environment Variables

On Render:
1. Go to **Environment**
2. Update:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   ```
3. Save and redeploy

### 8.3 Create Live Webhook

1. In Stripe (production mode) → **Developers** → **Webhooks**
2. Create new webhook endpoint with live URL
3. Get signing secret (`whsec_...`)
4. Update Render:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

---

## Troubleshooting

### Webhook not receiving events

**Problem:** Events not showing in `webhooks_log`

**Solutions:**
1. Verify webhook endpoint URL is correct
2. Check Stripe dashboard → **Webhooks** → View details
3. Check Stripe **Event Log** for failed attempts
4. Verify `STRIPE_WEBHOOK_SECRET` is set correctly
5. Restart Render service (redeploy)

### Subscription not created after payment

**Problem:** User paid but subscription not in Firestore

**Solutions:**
1. Check `webhooks_log` for `customer.subscription.created` event
2. If missing, webhook didn't fire → check Stripe webhook settings
3. If present, check Firestore permission rules
4. Check Render logs for errors:
   ```
   Render Dashboard → Logs → Filter by "ERROR"
   ```

### Test card declining

**Problem:** "Your card was declined" when paying

**Solutions:**
1. Use correct test card: **4242 4242 4242 4242**
2. Use future expiry date (current month/year won't work)
3. Use any CVC (e.g., 123)
4. Make sure you're in **test mode** in Stripe dashboard

---

## Monitoring in Production

### Daily Checks:
1. **Stripe Dashboard** → **Payments** (verify transactions)
2. **Render Dashboard** → **Logs** (check for errors)
3. **Firestore** → **subscriptions** collection (verify new subscriptions)
4. **Firestore** → **webhooks_log** collection (verify webhook processing)

### Alerts to Set Up:
1. Stripe failed payments → Email admin
2. Render server errors → Pagerduty/Slack
3. Webhook failures → Firestore trigger Cloud Function

---

## Phase 5 Complete! 🎉

**Next Steps:**
1. Mobile app integration (see `PHASE5_API_GUIDE.md`)
2. Admin dashboard subscription management
3. User analytics & reporting
4. Phase 6: Advanced features (coupons, seasonal deals, etc.)

---

## Support

For issues, check:
- Stripe docs: https://stripe.com/docs
- Firebase docs: https://firebase.google.com/docs
- Render docs: https://render.com/docs
- DealHunter API Guide: `PHASE5_API_GUIDE.md`
