# DealHunter Scraper — Session Notes
**Date:** 2026-05-02  
**Project:** `Mdenana4/dealhunter-scraper`  
**Branch:** `claude/review-app-deployment-o70ke` → merged to `main`

---

## Summary

Full debug, fix, and infrastructure migration session for the DealHunter admin panel and backend.

---

## Root Causes Found & Fixed

### 1. Login Completely Broken — "429 Quota exceeded"
**Root cause:** `admin_stats()` called `db.collection('deals').stream()` (ALL deals) + `db.collection('users').stream()` (ALL users) on every request. Monitor page polled every 60 seconds = **400,000+ Firestore reads/day** against a 50,000/day free-tier limit. Once quota exhausted, every Firestore call including login failed with 429.

**Fixes applied:**
- `server.py`: Load `admin_users` into memory at startup (`_admin_cache`), refresh hourly — login now needs **zero Firestore reads**
- `server.py`: Cache stats response for 5 minutes (`_stats_cache`)
- `admin.html`: Reduce stats polling from 60s → 300s
- `admin.html`: Add localStorage session cache — valid for 4 hours, skips check-auth on repeated page loads

### 2. Server Using verify_id_token → Firebase API Quota
**Root cause:** Old `check-auth` endpoint called `fb_auth.verify_id_token()` which hits Google's `identitytoolkit.googleapis.com` — a separate quota from Firestore.

**Fix:** `_uid_email_from_token()` — pure local JWT base64 decode, zero network calls, zero quota usage.

### 3. Admin Stats 500 Error
**Root cause:** `deals.index(d)` — Python `list.index()` compares dict objects containing Firestore Timestamp values; always throws ValueError.

**Fix:** Store `_doc_id` inside each deal dict during stream, extract cleanly at end.

### 4. Revenue Endpoint 500 — `list.index(x): x not in list`
**Root cause:** `['free','trial','premium','vip'].index(tier)` crashes when tier value is empty string or unknown name.

**Fix:** Safe `_tier_rank()` function with try/except.

### 5. Logs Endpoint 500
**Root cause:** `order_by('timestamp')` on `admin_logs` collection fails when collection is new/empty (Firestore index not yet built).

**Fix:** Try ordered fetch, fall back to unordered, sort in Python.

### 6. Offers Endpoint 500
**Root cause:** `order_by('timestamp').where('site', '==', source)` requires a Firestore composite index that was never created.

**Fix:** Fetch with order only, filter by source/category in Python.

### 7. Proxy PATCH 500
**Root cause:** Firestore `update()` fails with NOT_FOUND if document doesn't exist.

**Fix:** Changed to `set(merge=True)` which creates or updates.

### 8. Team Tab "Error loading team"
**Root cause:** `m.role.toUpperCase()` throws TypeError when `role` field is missing from Firestore admin_users document.

**Fix:** Null-safe rendering: `(m.role || 'admin').toUpperCase()` for all fields.

### 9. Duplicate Function Name Breaking Daily Limit Save
**Root cause:** Two functions named `updateDailyLimit` — second (modal helper) overwrote first (API call function).

**Fix:** Renamed modal helper to `syncAddUserLimit()`.

### 10. Tier Pricing Reading Wrong Collection
**Root cause:** Frontend wrote to `tier_config` but `admin_tiers` read from `tiers`.

**Fix:** `admin_tiers()` tries `tier_config` first, falls back to `tiers`.

### 11. Notifications Saved Twice
**Root cause:** `saveNotif()` in admin.html called `dbp('notifications', ...)` AND then called the server endpoint which also saved to Firestore.

**Fix:** Removed client-side `dbp` save; server handles both FCM + Firestore.

### 12. Source Filter Showing Only 3 Sites
**Root cause:** `while(sel.options.length>3) sel.remove(3)` removed all Egypt/UAE/Saudi static options.

**Fix:** Use `data-custom='1'` attribute to only remove dynamically-added options.

### 13. Render Never Deployed Code
**Root cause:** GitHub Actions workflow required `RENDER_DEPLOY_HOOK` secret (not configured). Render's native GitHub integration also not connected. `autoDeploy: true` in render.yaml has no effect without integration.

**Status:** User upgraded Render plan + Firebase to Blaze.

### 14. Railway Health Check Failing
**Root cause:** Railway assigns dynamic `PORT` env var. App was hardcoded to listen on port 5000. Railway health checker hit its assigned port, got nothing, killed container.

**Fix:** `server.py` reads `PORT = int(os.getenv('PORT', 5000))`. `start.sh` passes `PORT` through. Dockerfile sets `ENV PORT=5000` as default.

### 15. Railway Firebase Credentials Not Found
**Root cause:** User set env var as `FIREBASE_CREDENTIALS_JSON` but code expected `FIREBASE_KEY_JSON`.

**Fix:** Code now accepts `FIREBASE_KEY_JSON`, `FIREBASE_CREDENTIALS_JSON`, or `FIREBASE_SERVICE_ACCOUNT_JSON` — whichever is set.

---

## Architecture Changes

### Infrastructure Migration
- **From:** Render Free → **To:** Render Paid ($7/mo) + Railway Hobby ($5/mo)
- **Database:** Firebase Spark (50K reads/day) → **Firebase Blaze** (pay-per-use, no limits)
- **Auto-deploy:** GitHub push to `main` → Railway auto-deploys

### New Server-Side Features Added
- `_uid_email_from_token()` — local JWT decode, no Firebase API calls
- `_admin_cache` — in-memory admin users cache, refreshes hourly
- `_stats_cache` — 5-minute stats cache
- `_log_event()` — structured logging to Firestore `admin_logs` collection
- Global exception handler — catches all 500s and logs them
- `/api/v1/admin/logs` — returns recent error logs
- `/api/v1/admin/alarms` — real-time health alarms
- `/api/v1/admin/revenue` — financial dashboard data
- `/api/v1/admin/country-pricing` — per-country pricing management
- `/api/v1/notifications/send` — FCM topic/token push with Firestore save
- Generic Firestore proxy — `GET/POST/PATCH/PUT/DELETE /api/v1/admin/db/<collection>[/<doc_id>]`

### New Admin Panel Features Added
- Revenue tab with MRR, tier breakdown, tier change history
- Logs tab with error viewer and stack traces
- Alarm banner on Monitor page
- Bulk user tier change (select multiple → apply tier)
- Country pricing editor (Egypt EGP, Saudi SAR, UAE AED, Kuwait KWD, Qatar QAR)
- Membership overrides table in Pricing tab
- localStorage session cache (4-hour, survives page reloads)
- Fallback login path using Firestore client SDK direct read

---

## Pending Issues (Still Open)

| Issue | Root Cause | Status |
|---|---|---|
| Amazon/Jumia deals not updated | Scraper may be blocked or hitting old URLs | Not fixed |
| Noon scraper returns 0 deals | Scraper endpoint/selectors broken | Not fixed |
| Team add/edit/delete | Server endpoints may be missing POST/PATCH/DELETE | Under investigation |
| Tier add/edit modals | `openTierModal()` / `openTierEditModal()` JS may not call correct endpoint | Under investigation |
| Country pricing "Loading..." | `loadTierPricing()` → `renderCountryPricing()` chain needs verification | Under investigation |
| FCM notifications delivery | Users not subscribed to FCM topics in mobile app | Needs mobile app fix |
| Deal fake-checker from deals list | No "open deal" modal/route in current admin panel | Missing feature |
| Revenue Excel export | Feature not implemented | Missing feature |
| Dashboard user/revenue stats | Partial — needs country breakdown, login count | Partially implemented |

---

## Key Files

| File | Purpose |
|---|---|
| `server.py` | Flask backend (~2500 lines) |
| `admin.html` | Admin panel SPA (~3500 lines) |
| `scraper.py` | Deal scraper (Amazon, Noon, Jumia, etc.) |
| `fake_checker.py` | Fake deal detection logic |
| `price_tracker.py` | Price history tracking |
| `scraper_health.py` | Scraper health monitoring |
| `start.sh` | Container startup (scraper + server) |
| `Dockerfile` | Docker image definition |
| `railway.json` | Railway deployment config |
| `render.yaml` | Render deployment config |
| `.github/workflows/deploy-render.yml` | GitHub Actions CI/CD |

---

## Environment Variables Required

| Variable | Description |
|---|---|
| `FIREBASE_KEY_JSON` | Firebase service account JSON (full content) |
| `FLASK_ENV` | Set to `production` |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `SCRAPERAPI_KEY` | ScraperAPI key for scraping |

---

## Firestore Collections Used

| Collection | Purpose |
|---|---|
| `admin_users` | Admin panel users (email or uid as doc ID) |
| `admin_logs` | Structured error/event logs |
| `deals` | All scraped deals |
| `users` | App users |
| `tier_config` | Tier pricing and features |
| `notifications` | Sent notifications history |
| `user_groups` | User groups for shared plans |
| `country_pricing` | Per-country price configs |
| `tier_history` | Tier upgrade/downgrade audit trail |
| `scraper_health` | Per-source scraper health stats |

---

## Recommended Next Steps

1. **Fix scraper selectors** for Amazon EG, Jumia, Noon — site layouts change and selectors break
2. **Add Composite Firestore Indexes** for queries that need order_by + where
3. **Mobile app FCM topic subscription** — app must call `subscribeToTopic("all_users")` on startup
4. **Migrate to PostgreSQL** (Supabase) when ready — better for complex queries, no per-read quota
5. **Add Excel export** for revenue and user data
6. **Complete deal viewer modal** in admin panel

---

## Scaling Recommendations

| Phase | Users | Stack | Cost |
|---|---|---|---|
| Now | <10K | Railway + Firebase Blaze | ~$7/mo |
| Phase 2 | 10K-100K | Railway + Supabase + Redis | ~$50/mo |
| Phase 3 | 100K-1M | Google Cloud Run + Firestore Blaze + CloudFlare | ~$150/mo |
| Phase 4 | 1M+ | AWS ECS + RDS + ElastiCache | ~$500+/mo |
