# DealHunter Admin API Endpoints

## Base URL
```
https://dealhunter-scraper.onrender.com/api/v1
```

## Authentication
All endpoints require Bearer token in Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

---

## Authentication Endpoints

### POST /auth/login
Login with email and password
- **Body:** `{ email, password }`
- **Returns:** `{ token, user_data }`
- **Status:** ✅ Already implemented

### GET /auth/me
Get current authenticated user
- **Returns:** Current user object
- **Status:** ✅ Already implemented

---

## Team Management Endpoints

### GET /admin/team
Get all team members
- **Permission:** Owner/Editor/Viewer
- **Returns:** `{ team: [ { email, name, role, permissions, status, last_login } ] }`
- **Status:** ✅ Already implemented (line 1832)

### POST /admin/team
Add new team member
- **Permission:** Owner only
- **Body:** `{ email, name, role, permissions, status }`
- **Returns:** `{ success: true }`
- **Status:** ✅ Already implemented (line 292)

### PUT /admin/team/<email>
Update team member
- **Permission:** Owner only
- **Body:** `{ role, permissions, status }`
- **Returns:** `{ success: true }`
- **Status:** ✅ Already implemented (line 337)

### DELETE /admin/team/<email>
Remove team member
- **Permission:** Owner only
- **Returns:** `{ success: true }`
- **Status:** ✅ Already implemented (line 384)

### GET /admin/check-permission/<resource>
Check if current admin has permission for resource
- **Returns:** `{ allowed: true/false, reason: "..." }`
- **Status:** ✅ Already implemented (line 404)

---

## User Management Endpoints

### GET /admin/users
Get all users with admin details
- **Permission:** Users management
- **Returns:** 
  ```json
  {
    "data": [
      {
        "id": "user_id",
        "email": "user@example.com",
        "name": "User Name",
        "tier": "premium",
        "daily_deal_limit": 500,
        "registered_at": "2026-01-01T00:00:00Z",
        "last_login": "2026-04-16T00:00:00Z",
        "is_active": true,
        "group_name": "group_name",
        "stripe_customer_id": "cus_xxx"
      }
    ]
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

### PUT /admin/users/<user_id>
Update user details
- **Permission:** Users management
- **Body:** 
  ```json
  {
    "name": "New Name",
    "tier": "vip",
    "daily_deal_limit": 1000,
    "is_active": true
  }
  ```
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION (Similar to line 565)

### DELETE /admin/users/<user_id>
Delete user
- **Permission:** Users management
- **Returns:** `{ success: true }`
- **Status:** ✅ Already implemented (line 1020)

### POST /admin/users/<user_id>/tier
Change user tier
- **Permission:** Users management
- **Body:** `{ new_tier: "premium", reason: "Upgrade" }`
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### POST /admin/users/<user_id>/reward
Grant referral reward
- **Permission:** Users management
- **Body:** `{ reward_amount: 100, reason: "Referral bonus" }`
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### GET /admin/users/<user_id>/referrals
Get user referral statistics
- **Permission:** Users management
- **Returns:** 
  ```json
  {
    "made": 5,
    "completed": 3,
    "pending": 2,
    "reward_balance": 150,
    "referrals": [
      {
        "referred_email": "friend@example.com",
        "referred_at": "2026-01-01T00:00:00Z",
        "status": "completed",
        "reward_tier": "premium"
      }
    ]
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

---

## Deal Management Endpoints

### GET /admin/deals
Get all deals with admin details
- **Permission:** Deals management
- **Returns:** 
  ```json
  {
    "data": [
      {
        "id": "deal_id",
        "title": "Product Title",
        "source": "amazon",
        "current_price": 99.99,
        "original_price": 149.99,
        "discount_percent": 33,
        "image_url": "https://...",
        "product_url": "https://...",
        "status": "active",
        "verdict": "genuine",
        "featured": false,
        "hidden": false,
        "views": 1250,
        "rating": 4.5,
        "reviews": 120,
        "added_at": "2026-04-16T00:00:00Z",
        "updated_at": "2026-04-16T12:00:00Z"
      }
    ]
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

### PUT /admin/deals/<deal_id>
Update deal details
- **Permission:** Deals management
- **Body:** 
  ```json
  {
    "title": "New Title",
    "current_price": 89.99,
    "discount_percent": 40,
    "verdict": "suspicious"
  }
  ```
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### DELETE /admin/deals/<deal_id>
Delete deal
- **Permission:** Deals management
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### PATCH /admin/deals/<deal_id>/visibility
Toggle deal visibility (hide/show)
- **Permission:** Deals management
- **Body:** `{ hidden: true }`
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### PATCH /admin/deals/<deal_id>/featured
Toggle deal featured status
- **Permission:** Deals management
- **Body:** `{ featured: true }`
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### PATCH /admin/deals/<deal_id>/verdict
Set fraud verdict on deal
- **Permission:** Deals management
- **Body:** `{ verdict: "genuine" }` // "genuine", "suspicious", "fake"
- **Returns:** `{ success: true }`
- **Status:** ❌ NEEDS IMPLEMENTATION

### GET /admin/deals/<deal_id>/analytics
Get deal analytics
- **Permission:** Deals management
- **Returns:** 
  ```json
  {
    "id": "deal_id",
    "views": 1250,
    "clicks": 450,
    "ctr": 0.36,
    "rating": 4.5,
    "reviews": 120,
    "trending": true
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

---

## Notification Endpoints

### GET /admin/notifications
Get notification history
- **Permission:** Notifications management
- **Returns:** 
  ```json
  {
    "data": [
      {
        "id": "notif_id",
        "title": "Hot Deal Alert",
        "message": "New amazing deal available!",
        "target_type": "all",
        "target_tier": null,
        "target_group": null,
        "sent_count": 25000,
        "sent_at": "2026-04-16T10:00:00Z",
        "sent_by": "admin@example.com"
      }
    ]
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

### POST /admin/notifications/send
Send notification to users
- **Permission:** Notifications management
- **Body:** 
  ```json
  {
    "title": "Hot Deal Alert",
    "message": "New amazing deal available!",
    "target_type": "all",
    "target_tier": null,
    "target_group": null
  }
  ```
- **Returns:** `{ success: true, sent_count: 25000 }`
- **Status:** ✅ Already implemented (line 846)

### GET /admin/notifications/<notif_id>/analytics
Get notification delivery analytics
- **Permission:** Notifications management
- **Returns:** 
  ```json
  {
    "id": "notif_id",
    "sent_count": 25000,
    "delivered_count": 24500,
    "opened_count": 12300,
    "clicked_count": 5600,
    "delivery_rate": 0.98,
    "open_rate": 0.49
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

### GET /admin/notifications/<notif_id>/delivery
Get delivery status details
- **Permission:** Notifications management
- **Returns:** 
  ```json
  {
    "id": "notif_id",
    "status": "delivered",
    "sent_at": "2026-04-16T10:00:00Z",
    "completed_at": "2026-04-16T10:05:00Z",
    "delivery_summary": {
      "total": 25000,
      "delivered": 24500,
      "failed": 300,
      "pending": 200
    }
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

---

## Permissions Endpoint

### GET /admin/permissions
Get all available permissions for current admin
- **Returns:** 
  ```json
  {
    "permissions": [
      "sources",
      "deals",
      "users",
      "notifications",
      "checker",
      "competitors",
      "scraper_control"
    ],
    "current_admin": {
      "email": "admin@example.com",
      "role": "editor",
      "permissions": ["deals", "users"]
    }
  }
  ```
- **Status:** ❌ NEEDS IMPLEMENTATION

---

## Summary

| Endpoint Category | Total | Implemented | Pending |
|-------------------|-------|-------------|---------|
| Authentication | 2 | 2 | 0 |
| Team Management | 5 | 4 | 1 |
| User Management | 6 | 1 | 5 |
| Deal Management | 8 | 0 | 8 |
| Notifications | 3 | 1 | 2 |
| Permissions | 1 | 0 | 1 |
| **TOTAL** | **25** | **8** | **17** |

---

## Implementation Priority

### Phase 1 (Critical - Required for screens to work)
1. GET /admin/users
2. PUT /admin/users/<user_id>
3. GET /admin/deals
4. PUT /admin/deals/<deal_id>
5. DELETE /admin/deals/<deal_id>
6. GET /admin/notifications
7. POST /admin/notifications/send (already exists)

### Phase 2 (Important - Enhanced functionality)
1. PATCH /admin/deals/<deal_id>/visibility
2. PATCH /admin/deals/<deal_id>/featured
3. PATCH /admin/deals/<deal_id>/verdict
4. POST /admin/users/<user_id>/tier
5. GET /admin/permissions

### Phase 3 (Nice to have - Analytics & extras)
1. GET /admin/deals/<deal_id>/analytics
2. GET /admin/notifications/<notif_id>/analytics
3. POST /admin/users/<user_id>/reward
4. GET /admin/users/<user_id>/referrals
