# Phase 5: API Reference & Testing Guide

## Base URL
```
https://your-render-url.com/api/v1
```

## Authentication
All endpoints (except public ones) require Firebase ID token in header:
```
Authorization: Bearer {idToken}
```

Get token from Firebase client SDK:
```javascript
const idToken = await firebase.auth().currentUser.getIdToken();
```

---

## 1. USER MANAGEMENT

### 1.1 Create User (Sign Up)
**POST** `/users`

**Request:**
```json
{
  "id_token": "firebase-id-token",
  "name": "Ahmed Hassan",
  "phone": "+201234567890",
  "referred_by_uid": "optional-referrer-uid"
}
```

**Response (201):**
```json
{
  "success": true,
  "user": {
    "uid": "firebase-uid-123",
    "email": "user@example.com",
    "tier": "free",
    "referral_code": "DEALABCD1234",
    "daily_deal_limit": 50,
    "created_at": "2026-04-14T10:00:00Z"
  }
}
```

---

### 1.2 Get User Profile
**GET** `/users/{uid}`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "id": "firebase-uid",
  "email": "user@example.com",
  "name": "Ahmed Hassan",
  "phone": "+201234567890",
  "tier": "premium",
  "subscription_active": true,
  "subscription_renewal_date": "2026-05-14T00:00:00Z",
  "daily_deal_limit": 500,
  "deals_shared_today": 42,
  "referral_code": "DEALABCD1234",
  "referred_by_uid": null,
  "created_at": "2026-03-14T10:00:00Z"
}
```

---

### 1.3 Update User Profile
**PUT** `/users/{uid}`

**Headers:** `Authorization: Bearer {idToken}`

**Request:**
```json
{
  "name": "Ahmed H.",
  "phone": "+201234567890",
  "language": "ar",
  "notifications_enabled": true
}
```

**Response (200):**
```json
{
  "success": true,
  "user": {...}
}
```

---

### 1.4 Get Referral Stats
**GET** `/users/{uid}/referral-stats`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "referral_code": "DEALABCD1234",
  "total_referrals": 5,
  "activated_referrals": 3,
  "redeemed_referrals": 2,
  "pending_rewards": 1,
  "referral_history": [
    {
      "referee_email": "friend@example.com",
      "status": "redeemed",
      "reward_type": "premium_week",
      "redeemed_at": "2026-04-10T00:00:00Z"
    }
  ]
}
```

---

### 1.5 Delete Account
**DELETE** `/users/{uid}`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "success": true,
  "message": "Account deleted"
}
```

---

## 2. SUBSCRIPTION MANAGEMENT

### 2.1 Create Checkout Session
**POST** `/subscriptions/checkout`

**Headers:** `Authorization: Bearer {idToken}`

**Request:**
```json
{
  "tier": "premium",
  "success_url": "app://subscription-success",
  "cancel_url": "app://subscription-cancel"
}
```

**Response (201):**
```json
{
  "success": true,
  "checkout_session_id": "cs_test_123456789",
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

**Next Steps:**
- Open `checkout_url` in mobile browser/WebView
- User completes payment with Stripe
- Redirect to `success_url` on completion
- Webhook fires automatically to update subscription

---

### 2.2 Get Current Subscription
**GET** `/subscriptions/current`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "subscription_id": "sub_1234567890",
  "tier": "premium",
  "status": "active",
  "current_period_end": "2026-05-14T00:00:00Z",
  "monthly_amount_egp": 99.00,
  "auto_renew": true,
  "cancel_at_period_end": false
}
```

**Status values:**
- `active` - Subscription is active
- `past_due` - Payment failed, retrying
- `canceled` - Subscription has been canceled
- `none` - No active subscription

---

### 2.3 Cancel Subscription
**POST** `/subscriptions/cancel`

**Headers:** `Authorization: Bearer {idToken}`

**Request:**
```json
{
  "feedback": "Too expensive" (optional)
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Subscription will cancel on 2026-05-14",
  "final_date": "2026-05-14T00:00:00Z"
}
```

**Note:** Subscription continues until `final_date`, then user is downgraded to `free` tier.

---

## 3. USER GROUPS

### 3.1 Create Group
**POST** `/groups`

**Headers:** `Authorization: Bearer {idToken}`

**Requirements:** `Premium+` tier only

**Request:**
```json
{
  "name": "Electronics Deals Egypt",
  "description": "Share best electronics deals and discounts",
  "is_public": true,
  "visibility": "public",
  "daily_share_limit": 15
}
```

**Response (201):**
```json
{
  "success": true,
  "group": {
    "id": "group_abc123xyz",
    "name": "Electronics Deals Egypt",
    "owner_id": "user@example.com",
    "member_count": 1,
    "created_at": "2026-04-14T10:00:00Z"
  }
}
```

---

### 3.2 Get Group Details
**GET** `/groups/{group_id}`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "id": "group_abc123xyz",
  "name": "Electronics Deals Egypt",
  "description": "Share best electronics deals",
  "owner_id": "owner@example.com",
  "member_count": 27,
  "is_public": true,
  "daily_share_limit": 15,
  "deals_shared_today": 8,
  "user_is_member": true,
  "user_role": "member",
  "created_at": "2026-04-14T10:00:00Z"
}
```

---

### 3.3 Join or Invite Member
**POST** `/groups/{group_id}/members`

**Headers:** `Authorization: Bearer {idToken}`

**Request (Join):**
```json
{
  "action": "join"
}
```

**Request (Invite):**
```json
{
  "action": "invite",
  "invite_user_id": "friend@example.com"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Joined group successfully"
}
```

---

### 3.4 Remove Member
**DELETE** `/groups/{group_id}/members/{user_id}`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "success": true,
  "message": "User removed from group"
}
```

---

## 4. DEAL GIFTING

### 4.1 Send Deal as Gift
**POST** `/deals/{deal_id}/gift`

**Headers:** `Authorization: Bearer {idToken}`

**Requirements:** `Premium+` tier only

**Request:**
```json
{
  "to_user_id": "friend@example.com",
  "message": "Check this out! Amazing deal on iPhone 15 Pro"
}
```

**Response (201):**
```json
{
  "success": true,
  "gift": {
    "gift_id": "gift_xyz123abc",
    "to_user_id": "friend@example.com",
    "deal_id": "deal_123456",
    "message": "Check this out! Amazing deal on iPhone 15 Pro",
    "status": "sent",
    "expires_at": "2026-05-14T00:00:00Z",
    "created_at": "2026-04-14T10:00:00Z"
  }
}
```

---

### 4.2 List Received Gifts
**GET** `/gifts/received`

**Headers:** `Authorization: Bearer {idToken}`

**Response (200):**
```json
{
  "gifts": [
    {
      "gift_id": "gift_xyz123abc",
      "from_user_id": "friend@example.com",
      "from_user_name": "Ahmed Hassan",
      "deal_id": "deal_123456",
      "deal_title": "iPhone 15 Pro - 25% OFF",
      "deal_current_price": 28999.00,
      "message": "Check this out! Amazing deal",
      "status": "sent",
      "expires_at": "2026-05-14T00:00:00Z",
      "created_at": "2026-04-14T10:00:00Z"
    }
  ],
  "total_unredeemed": 3
}
```

**Gift Status:**
- `sent` - Gift sent, waiting for recipient to view
- `viewed` - Recipient viewed the gift
- `claimed` - Recipient claimed the deal
- `expired` - Gift expired (30 days)

---

## 5. REFERRAL SYSTEM

### 5.1 Check Referral Code (Public)
**GET** `/referrals/check-code?code=DEALABCD1234`

**Headers:** None required

**Response (200):**
```json
{
  "valid": true,
  "referrer_name": "Ahmed Hassan",
  "reward_description": "Get 1 week of Premium"
}
```

**Response (Invalid):**
```json
{
  "valid": false,
  "reason": "Code expired"
}
```

---

### 5.2 Activate Referral Code (Public)
**POST** `/referrals/activate`

**Headers:** None required

**Request:**
```json
{
  "referral_code": "DEALABCD1234",
  "new_user_id": "newly-created-uid"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Referral activated",
  "reward": "7-day premium trial"
}
```

**Process:**
1. User signs up with referral code
2. Get `new_user_id` from Create User response
3. Call this endpoint immediately after signup
4. Referrer gets 1 week premium automatically
5. Referee becomes eligible for Premium features

---

## 6. TIER LIMITS & DAILY QUOTAS

### Daily Deal Limits (by tier):
| Tier | Daily Deals | Groups | Gifts/Month | Cost |
|------|------------|--------|------------|------|
| Free | 50 | 0 | 0 | EGP 0 |
| Trial | 100 | 1 | 0 | EGP 0 (7 days) |
| Premium | 500 | 5 | 5 | EGP 99/mo |
| VIP | Unlimited | Unlimited | Unlimited | EGP 199/mo |

### Features by Tier:
| Feature | Free | Trial | Premium | VIP |
|---------|------|-------|---------|-----|
| View Deals | ✅ | ✅ | ✅ | ✅ |
| Price History | ❌ | ✅ | ✅ | ✅ |
| Groups | ❌ | ✅ | ✅ | ✅ |
| Gift Deals | ❌ | ❌ | ✅ | ✅ |
| Email Alerts | ❌ | ✅ | ✅ | ✅ |
| Export CSV | ❌ | ❌ | ✅ | ✅ |

---

## TESTING WITH STRIPE TEST MODE

### Test Card Numbers:
```
✅ Success:      4242 4242 4242 4242
❌ Decline:      4000 0000 0000 0002
⏳ Requires Auth: 4000 0000 0000 0119
🔚 Expired:      4000 0000 0000 0069
```

### Test Expiry & CVC:
- **Expiry:** Any future date (e.g., 12/26)
- **CVC:** Any 3 digits (e.g., 123)

### Test Flow:
1. **Create test user:**
   ```bash
   curl -X POST http://localhost:10000/api/v1/users \
     -H "Content-Type: application/json" \
     -d '{
       "id_token": "test-token",
       "name": "Test User",
       "phone": "+201234567890"
     }'
   ```

2. **Create checkout:**
   ```bash
   curl -X POST http://localhost:10000/api/v1/subscriptions/checkout \
     -H "Authorization: Bearer {idToken}" \
     -H "Content-Type: application/json" \
     -d '{
       "tier": "premium",
       "success_url": "http://localhost:3000/success",
       "cancel_url": "http://localhost:3000/cancel"
     }'
   ```

3. **Open checkout URL** in browser and use test card `4242 4242 4242 4242`

4. **Verify subscription created:**
   - Check Firestore `subscriptions` collection
   - User's `tier` should be `premium`
   - `daily_deal_limit` should be `500`

5. **Monitor webhook:**
   - Check `webhooks_log` collection
   - Should see `customer.subscription.created` event

---

## ERROR RESPONSES

### 400 Bad Request
```json
{
  "error": "referral_code and new_user_id required"
}
```

### 401 Unauthorized
```json
{
  "error": "Missing authorization token"
}
```

### 403 Forbidden
```json
{
  "error": "Premium+ tier required"
}
```

### 404 Not Found
```json
{
  "error": "User not found"
}
```

### 500 Server Error
```json
{
  "error": "Internal server error"
}
```

---

## MOBILE APP INTEGRATION

### 1. Firebase Auth Setup
```javascript
import { initializeApp } from 'firebase/app';
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "dealhunter-egypt-70d29.firebaseapp.com",
  projectId: "dealhunter-egypt-70d29",
  storageBucket: "dealhunter-egypt-70d29.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
```

### 2. Sign Up Flow
```javascript
const handleSignup = async (email, password, name, referralCode) => {
  try {
    // 1. Create Firebase user
    const userCred = await createUserWithEmailAndPassword(auth, email, password);
    const idToken = await userCred.user.getIdToken();

    // 2. Create user in app
    const userResponse = await fetch('/api/v1/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id_token: idToken,
        name: name,
        referred_by_uid: null
      })
    });

    const userData = await userResponse.json();
    const userId = userData.user.uid;

    // 3. Activate referral if provided
    if (referralCode) {
      await fetch('/api/v1/referrals/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          referral_code: referralCode,
          new_user_id: userId
        })
      });
    }

    return userData;
  } catch (error) {
    console.error('Signup failed:', error);
  }
};
```

### 3. Subscribe to Premium
```javascript
const handleSubscribe = async (tier) => {
  try {
    const idToken = await auth.currentUser.getIdToken();

    // 1. Create checkout session
    const checkoutResponse = await fetch('/api/v1/subscriptions/checkout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${idToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        tier: tier,
        success_url: 'app://subscription-success',
        cancel_url: 'app://subscription-cancel'
      })
    });

    const checkout = await checkoutResponse.json();

    // 2. Open Stripe checkout in WebView
    window.location.href = checkout.checkout_url;
  } catch (error) {
    console.error('Subscription failed:', error);
  }
};
```

---

## NEXT STEPS

1. ✅ Deploy server.py to Render
2. ✅ Set Stripe environment variables
3. ✅ Create Firestore indexes
4. ✅ Create Stripe products & webhook
5. Test all endpoints with Stripe test mode
6. Deploy to production with live Stripe keys

**Phase 5 is 95% complete!** Just need to test the endpoints. 🚀
