# Phase 5 Deployment Checklist ✅

**Status:** Code deployed to GitHub, Render auto-deploying

---

## 1. Monitor Deployment on Render

### Check Render Dashboard:
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select your DealHunter service
3. Watch **Build & Deploy** logs
4. Should see:
   ```
   ✓ Firebase Admin SDK initialized
   ✓ Stripe API key configured
   Starting Flask server on port 10000
   ```

**Deployment takes ~2-5 minutes**

---

## 2. Stripe Setup (Do This Now)

### 2.1 Create Stripe Account
- [ ] Go to [Stripe.com](https://stripe.com)
- [ ] Create account (or login if existing)
- [ ] Verify email

### 2.2 Get API Keys (Test Mode)
- [ ] Go to **Developers** → **API Keys**
- [ ] Toggle to **Test Mode** (if not already)
- [ ] Copy **Secret Key** (starts with `sk_test_`)
- [ ] Copy **Publishable Key** (starts with `pk_test_`)

### 2.3 Create Stripe Products

**Product 1: Premium Monthly**
- [ ] Click **Products** → **+ Add Product**
- [ ] Name: `Premium Monthly`
- [ ] Type: Service
- [ ] Add pricing:
  - Amount: `99.00`
  - Currency: `EGP`
  - Billing: Monthly
- [ ] **Save Product**

**Product 2: VIP Monthly**
- [ ] Click **Products** → **+ Add Product**
- [ ] Name: `VIP Monthly`
- [ ] Type: Service
- [ ] Add pricing:
  - Amount: `199.00`
  - Currency: `EGP`
  - Billing: Monthly
- [ ] **Save Product**

---

## 3. Update Render Environment Variables

### 3.1 Add Stripe Keys to Render
1. [ ] Go to Render Dashboard
2. [ ] Select DealHunter service
3. [ ] Go to **Environment**
4. [ ] Click **Add Environment Variable**
5. [ ] Add:
   ```
   Key: STRIPE_SECRET_KEY
   Value: sk_test_xxxxx...
   ```
6. [ ] Click **Add Environment Variable**
7. [ ] Add:
   ```
   Key: STRIPE_PUBLISHABLE_KEY
   Value: pk_test_xxxxx...
   ```
8. [ ] **Save** → Render auto-redeploys

**Wait 2-3 minutes for redeploy**

---

## 4. Create Stripe Webhook

### 4.1 Create Webhook Endpoint
1. [ ] In Stripe Dashboard (Test Mode)
2. [ ] Go to **Developers** → **Webhooks**
3. [ ] Click **+ Add an endpoint**
4. [ ] Paste URL:
   ```
   https://your-render-url.onrender.com/webhooks/stripe
   ```
   (Replace `your-render-url` with your actual service name)
5. [ ] Click **Select events** and choose:
   - [ ] `customer.created`
   - [ ] `customer.subscription.created`
   - [ ] `customer.subscription.updated`
   - [ ] `customer.subscription.deleted`
   - [ ] `charge.succeeded`
   - [ ] `charge.failed`
   - [ ] `invoice.payment_failed`
6. [ ] Click **Add events**
7. [ ] Click **Add endpoint**

### 4.2 Get Webhook Secret
1. [ ] Click on the newly created webhook
2. [ ] Copy **Signing secret** (starts with `whsec_`)
3. [ ] Go to Render Dashboard
4. [ ] Add environment variable:
   ```
   Key: STRIPE_WEBHOOK_SECRET
   Value: whsec_xxxxx...
   ```
5. [ ] **Save** → Render redeploys

---

## 5. Test Phase 5 APIs

### 5.1 Test Health Check
```bash
curl https://your-render-url.onrender.com/
```

**Expected response:**
```
DealHunter Scraper is running!
```

### 5.2 Test Public Referral Endpoint
```bash
curl https://your-render-url.onrender.com/api/v1/referrals/check-code?code=TESTCODE
```

**Expected response:**
```json
{
  "valid": false
}
```

### 5.3 Test User Creation (requires Firebase token)
- Use your admin dashboard email/password to login
- Get the ID token from Firebase
- Test:
```bash
curl -X POST https://your-render-url.onrender.com/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "your-firebase-id-token",
    "name": "Test User",
    "phone": "+201234567890"
  }'
```

---

## 6. Test Stripe Checkout (Manually)

### 6.1 Create Test Checkout
1. [ ] Get valid Firebase ID token from your user account
2. [ ] Call checkout endpoint:
   ```bash
   curl -X POST https://your-render-url.onrender.com/api/v1/subscriptions/checkout \
     -H "Authorization: Bearer {your-id-token}" \
     -H "Content-Type: application/json" \
     -d '{
       "tier": "premium",
       "success_url": "https://example.com/success",
       "cancel_url": "https://example.com/cancel"
     }'
   ```

### 6.2 Complete Test Payment
1. [ ] Copy the returned `checkout_url`
2. [ ] Open in browser
3. [ ] Fill in test card:
   - **Card Number:** `4242 4242 4242 4242`
   - **Expiry:** Any future date (e.g., `12/26`)
   - **CVC:** Any 3 digits (e.g., `123`)
4. [ ] Click **Pay**

### 6.3 Verify in Firestore
1. [ ] Go to Firebase Console → **Firestore Database**
2. [ ] Check **subscriptions** collection
3. [ ] Should see new document with:
   - [ ] `status: "active"`
   - [ ] `product_name: "Premium Monthly"`
   - [ ] `price_amount: 9900`

### 6.4 Verify Webhook
1. [ ] Check **webhooks_log** collection in Firestore
2. [ ] Should see entries:
   - [ ] `event_type: "customer.created"`
   - [ ] `event_type: "customer.subscription.created"`
   - [ ] `status: "success"`

---

## 7. Go Live (After Testing Complete)

### 7.1 Get Live Stripe Keys
1. [ ] In Stripe Dashboard, toggle **Test mode OFF**
2. [ ] Go to **Developers** → **API Keys**
3. [ ] Copy **Live Secret Key** (starts with `sk_live_`)
4. [ ] Copy **Live Publishable Key** (starts with `pk_live_`)

### 7.2 Update Render with Live Keys
1. [ ] Go to Render Environment
2. [ ] Update:
   ```
   STRIPE_SECRET_KEY=sk_live_xxxxx...
   STRIPE_PUBLISHABLE_KEY=pk_live_xxxxx...
   ```
3. [ ] **Save** → Redeploys

### 7.3 Create Live Webhook
1. [ ] In Stripe (production mode)
2. [ ] Go to **Developers** → **Webhooks**
3. [ ] Create new endpoint:
   ```
   https://your-render-url.onrender.com/webhooks/stripe
   ```
4. [ ] Select same events
5. [ ] Copy **Signing secret** (`whsec_...`)
6. [ ] Update Render:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_live_xxxxx...
   ```
7. [ ] **Save**

---

## 8. Firestore Indexes (Optional but Recommended)

### 8.1 Create Indexes Manually
1. [ ] Go to Firebase Console
2. [ ] **Firestore Database** → **Indexes**
3. [ ] Create indexes for:
   - [ ] `users: stripe_customer_id, referral_code`
   - [ ] `subscriptions: user_id, status`
   - [ ] `referrals: referrer_id, status`
   - [ ] `user_groups: owner_id, created_at`

**Note:** Firebase auto-creates indexes as needed, but manual creation ensures they're ready.

---

## 9. Verify Deployment Success

### Checklist:
- [ ] Render shows "Build successful"
- [ ] Health check returns "DealHunter Scraper is running!"
- [ ] All 17 endpoints return 401/403 (auth errors, meaning they exist)
- [ ] Stripe keys configured in Render
- [ ] Stripe webhook created and accepting events
- [ ] Test payment completes
- [ ] Subscription appears in Firestore
- [ ] Webhook events logged in Firestore

---

## 10. Monitor in Production

### Daily Checks:
```
□ Render logs - No errors
□ Stripe Dashboard - Recent transactions
□ Firestore subscriptions - New subscriptions
□ webhooks_log - Recent webhook events
```

---

## 🎯 You're All Set!

**Phase 5 is now live!** 🚀

Next steps:
- Integrate with mobile app
- Create user dashboard UI
- Set up email notifications
- Monitor for issues

---

## Support Files

- 📖 `PHASE5_API_GUIDE.md` - Complete API reference
- 📖 `PHASE5_DEPLOYMENT.md` - Detailed deployment guide
- 🧪 `test_phase5.py` - Run tests locally
- 📋 `firestore-indexes.json` - Index configuration

---

**Questions?** Check the guides above or review the API endpoint code in `server.py`.
