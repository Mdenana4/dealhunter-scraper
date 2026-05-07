# DealHunter Egypt — Full Session Log

> **First user message:** "Can you check this, my application we build that together."
> **Project:** DealHunter Egypt — multi-source deal scraper + Flutter mobile app deployed on Railway

---

## 1. CHRONOLOGICAL TIMELINE

### Phase 1 — Initial Review & Diagnosis
- User asked Claude to review the app they built together
- Reviewed `scraper.py`, `server.py`, `admin.html`, Flutter app code
- Identified multiple broken components across Amazon, Noon, Jumia scrapers

### Phase 2 — Noon Parser Overhaul
- Noon `regex_matched=0` bug discovered — SKU regex was wrong
- Fixed SKU regex: pattern `/[A-Za-z0-9]{5,}/p/` introduced (Method D)
- Noon was walking DOM to shared grid container → shared prices across 20+ products
- Added container boundary guard: `if len(container.find_all("a", href=noon_sku_re)) > 1: break`
- Standalone number regex introduced: `(?<![A-Za-z\d])([\d,]+(?:\.\d+)?)(?![A-Za-z\d])`
- Title exclusion introduced: strip title text before price scan to remove spec numbers
- Ratio bounds `[1.15, 8.0]` introduced
- `cp >= 200` floor introduced to exclude supplement counts, badge percentages

### Phase 3 — Amazon Keyword Scan Failures
- Discovered 54 HTTP 400 errors per cycle from `scrape.do` structured API
- Root cause: Egypt (`eg`), UAE (`ae`), Saudi (`sa`) not in `_AMAZON_API_GEOCODES`
- Bug: `.get(country_code, country_code)` — fallback was the key itself, so "eg" still passed
- Fixed: `.get(country_code)` with explicit `if not geocode: return None`
- Added `AMAZON_KEYWORD_ENABLED = os.getenv("AMAZON_KEYWORD_ENABLED", "false").lower() == "true"`
- Defaulted to `false` to stop credit waste immediately
- User said: *"STOP. The new cycle at 20:05 UTC is already wasting credits... ADD THIS ONE LINE RIGHT NOW... If I still see [amz-api] HTTP 400, I'm hiring another AI"*

### Phase 4 — Admin Notification Modal Bug
- User reported: notification modal closes when selecting target audience dropdown
- Root cause: `querySelector('div:has(#nt-user)')` matched the entire `.mo` backdrop div
- Fixed: gave wrapper explicit `id="user-input-div"` + `getElementById('user-input-div')`
- Result: dropdown selection no longer closes the modal

### Phase 5 — SportQ Duplicate Entries
- 17 identical products per cycle from SportQ keyword pages
- Root cause: `seen_skus` set was not shared across keyword pages — same SKU processed on each page
- Fixed: `_seen_noon_skus: set = set()` shared across all `_parse_noon_products` calls in `_scrape_noon_region`

### Phase 6 — Noon Three-Bug Report (User's specific list)
User reported three remaining Noon bugs:
1. Discount badge ("59%") extracted as current price
2. Category mapping broken — perfume→electronics, vitamins→fashion
3. Source label showing "Noon Egypt do electronics"

**Bug 1 Fix:** Stage 1 price floor raised from `cp < 50` → `cp < 200`

**Bug 2 Fix:**
- Root cause: `detect_category()` returned `"general"` (truthy string) instead of `None`
- `cat = detect_category(title) or default_cat` → `"general"` is truthy → `default_cat` never used
- Fixed: `return None` instead of `return "general"`
- Added keywords to fashion regex: `parfum`, `fragrance`, `eau.?de`, `attar`, `oud`
- Added keywords to beauty regex: `omega`, `collagen`, `fish.?oil`, `probiotic`

**Bug 3 Investigation:**
- Source label "Noon Egypt do electronics" comes from `deal_detail_screen.dart` lines 168–182
- Flutter Row widget shows `deal.store` icon + text + `deal.category` icon + text side by side
- Scraper is correct — `site_display="Noon Egypt"` always set properly
- No code change needed

### Phase 7 — LG Washing Machine (1400 RPM as Price)
- User confirmed: app shows EGP 1,400 for LG washing machine (real price: EGP 26,199)
- 1400 = spin speed in RPM from product title "1400 RPM"
- Root cause: Stage 1 (data-qa elements) had **no ratio check**
  - cp=1400, op=26999 → cp>=200 ✓, op>cp ✓ → saved as 95% off deal ❌
- Fixed: added ratio check `1.15 <= op/cp <= 8.0` to Stage 1
- Restructured: Stage 1 now falls through to Stage 2 on bad values (instead of hard-skipping)
- Stage 2 number ceiling added: `<= 500_000`

### Phase 8 — Purge Function for Old Bad Deals
- Old Firestore document (cp=1400) was permanent: `deal_id = MD5(site+url+price)`
- Scraper can never overwrite a deal with a different price → bad deals live forever
- Added `_purge_bad_deals()`: runs end of every cycle, deletes deals where:
  - `cp < 200`
  - `op/cp > 8.0`
  - `cp > op`

### Phase 9 — Critical Bug: `__main__` Guard Deleted
- `_purge_bad_deals()` edit accidentally consumed `if __name__ == "__main__":` as anchor text
- Startup code (`run_scraper()`, `while True:`) ended up inside `_purge_bad_deals()` body at 4-space indent
- Python syntax was valid — no error shown — but `python scraper.py` defined all functions and exited immediately
- Scraper produced zero output; only "initialization messages" (the startup prints inside the function) showed
- Fixed: restored `if __name__ == "__main__":` guard, moved startup code back out of function
- Added requested log line: `"Scraper started, waiting for first cycle..."`

### Phase 10 — Admin Panel Login Broken (Firebase CDN Blocked)
- User reported: "Cannot access 'auth' before initialization"
- Browser console: `ERR_CONNECTION_TIMED_OUT` for all three gstatic.com Firebase SDK URLs
- Attempt 1: switched to unpkg.com → still blocked
- Attempt 2: self-hosted solution
  - Dockerfile: downloads Firebase 9.22.0 compat JS at build time (`curl` during `docker build`)
  - Flask: added `/sdk/<filename>` route serving files from container filesystem
  - admin.html: changed `<script src="/sdk/firebase-app-compat.js">` etc.
  - Browser now only needs to reach Railway server — zero external CDN requests

---

## 2. BUGS FOUND

| # | Bug | Discovered | Root Cause | Fix | Worked? | Status |
|---|-----|-----------|-----------|-----|---------|--------|
| 1 | Noon `regex_matched=0` | Early session | SKU regex wrong pattern | Method D with correct regex `/[A-Za-z0-9]{5,}/p/` | YES | FIXED |
| 2 | Noon shared prices (op=3800 for 20+ products) | Phase 2 | DOM walk reached shared grid container | Boundary guard: break if container has >1 product links | YES | FIXED |
| 3 | Noon specs as prices ("83" from "83JG0095ED") | Phase 2 | Regex matched all digits including alphanumeric substrings | Standalone regex with non-alphanumeric boundary | YES | FIXED |
| 4 | Supplement specs as prices (cp=140 = 140 servings) | Phase 2 | No price floor | `cp >= 200` floor | YES | FIXED |
| 5 | Amazon keyword scan 54× HTTP 400 | Phase 3 | Egypt geocode "eg" not in supported list but still passed via bad fallback | Fixed `.get()` + `AMAZON_KEYWORD_ENABLED=false` | YES | FIXED |
| 6 | Noon `waitUntil=networkidle2` HTTP 400 | Phase 3 | scrape.do doesn't support `waitUntil` param for Noon URLs | Reverted immediately | YES (reverted) | FIXED |
| 7 | Admin notification modal closes on dropdown | Phase 4 | `div:has(#nt-user)` matched backdrop div not inner wrapper | Explicit `id="user-input-div"` on wrapper | YES | FIXED |
| 8 | SportQ 17 duplicate entries per cycle | Phase 5 | `seen_skus` not shared across keyword pages | Shared `_seen_noon_skus` set across all parse calls | YES | FIXED |
| 9 | Discount badge "59%" used as price | Phase 6 | Stage 1 floor was `cp < 50`, badge value 59 passes | Raised floor to `cp < 200` | YES | FIXED |
| 10 | Category fallback broken (perfume→electronics) | Phase 6 | `detect_category` returned `"general"` (truthy) instead of `None` | Changed `return "general"` to `return None` | YES | FIXED |
| 11 | Missing fashion/beauty keywords | Phase 6 | "parfum", "eau de", "omega", "collagen" not in regexes | Added to fashion + beauty patterns | YES | FIXED |
| 12 | LG Washing Machine 1400 RPM as price | Phase 7 | Stage 1 had no ratio check — 1400/26999 = 19.3× passed | Added ratio `[1.15, 8.0]` to Stage 1; fall through to Stage 2 | YES | FIXED |
| 13 | Toshiba 400W/E1050 model number as price | Phase 7 | Same root cause as #12 | Same fix | YES | FIXED (by purge) |
| 14 | Old bad Firestore deals never cleaned up | Phase 8 | `deal_id` includes price → can't overwrite wrong-price doc | `_purge_bad_deals()` at end of each cycle | YES | FIXED |
| 15 | Scraper not running after purge commit | Phase 9 | `if __name__ == "__main__":` guard deleted by edit | Restored guard | YES | FIXED |
| 16 | Admin login broken — Firebase undefined | Phase 10 | gstatic.com CDN blocked by ISP/region | Self-hosted Firebase SDK via Railway + Flask `/sdk/` route | YES | FIXED |
| 17 | Noon JSON-LD never found | All phases | Noon doesn't emit JSON-LD in search pages | Accepted; Method D handles it | N/A | ACCEPTED |
| 18 | Safqa "not found" on every product | All phases | Safqa has limited Egypt product coverage | Accepted; falls back to local verdict | N/A | ACCEPTED |
| 19 | Amazon RapidAPI 403 | Early session | Free plan doesn't support this endpoint | Removed from flow | YES | FIXED |
| 20 | Jumia flash sales URL wrong (`mlp-flash-sales`) | Earlier session | URL path changed on Jumia site | Fixed to `/flash-sales` | YES | FIXED |

---

## 3. FIXES THAT WORKED

| Fix | Description |
|-----|-------------|
| Noon Method D | Complete rewrite of product link scanner — walks DOM from `<a href="/p/">` upward, boundary guard prevents grid bleed |
| Noon per-product prices | Each product now gets its own price from its own card container |
| Noon title exclusion | Strips product title from text before price scan — removes spec numbers |
| Noon ratio bounds | `[1.15, 8.0]` — rejects AC with 1% off (ratio 1.01) and DDR5 5600 (ratio ~11) |
| Noon cp floor | `>= 200` removes supplement serving counts, badge percentages, small specs |
| Noon Stage 1 ratio check | Prevents RPM/wattage model numbers from being used as price |
| Noon Stage 1 fallthrough | Bad Stage 1 values → Stage 2 text scan instead of hard-skip |
| Amazon geocode fix | `_AMAZON_API_GEOCODES.get(country_code)` with explicit None check |
| AMAZON_KEYWORD_ENABLED | Kill switch defaults to `false` — zero credit waste on unsupported geocodes |
| Admin modal fix | `getElementById('user-input-div')` replaces broken `:has()` selector |
| SKU dedup | Shared `seen_skus` set stops duplicate deals across keyword pages |
| detect_category returns None | `or default_cat` fallback now activates correctly for unrecognized titles |
| Category keywords expanded | parfum/fragrance/eau de/attar/oud → fashion; omega/collagen/fish oil/probiotic → beauty |
| _purge_bad_deals() | Deletes deals with `cp<200`, `ratio>8×`, `cp>op` at end of every cycle |
| __main__ guard restored | Scraper process actually starts and runs cycles |
| Firebase self-hosted | SDK served from `/sdk/` on Railway — no external CDN dependency |
| Jumia flash-sales URL | Corrected path from `mlp-flash-sales` to `flash-sales` |
| FCM push notifications | Tier-based topics working for vip/premium/free |

---

## 4. FIXES THAT FAILED OR WERE REVERTED

| Fix | What Was Tried | Why It Failed |
|-----|---------------|--------------|
| Noon `waitUntil=networkidle2` | Passed `waitUntil` param to scrape.do for Noon pages | scrape.do returned HTTP 400 — param not supported for non-Amazon URLs; reverted immediately |
| scrape.do for Amazon | Used structured `/plugin/amazon/search` and `/pdp` endpoints | Egypt/UAE/Saudi not in supported geocodes; all returned HTTP 400 |
| Amazon HTML keyword scan | Attempted regex extraction from raw Amazon HTML | Amazon aggressively blocks scrapers; 0 products extracted consistently |
| CDN switch to unpkg.com | Changed Firebase SDK URLs from gstatic.com to unpkg.com | unpkg.com also blocked in user's region |
| DOM walking to lvl=2+ | Walking parent nodes to find price containers | Reached shared grid — 20+ products got same op/cp |

---

## 5. CREDIT USAGE

| Source | Behavior | Credit Impact |
|--------|----------|--------------|
| Amazon keyword scan | 54 requests × HTTP 400 per cycle | HIGH WASTE — now disabled |
| scrape.do Noon | Direct fetch → ScraperAPI fallback cascade | Moderate — scrape.do often dead |
| scrape.do Amazon structured | 54 requests × HTTP 400 | HIGH WASTE — blocked |
| ScraperAPI Noon fallback | Renders JS for Noon search pages | Moderate usage, works |
| Noon successful scrapes | `regex_matched=46-48` per search term | Normal |

**Plan:** scrape.do Hobby ($29/month, 250k credits)
**Assessment:** With Amazon keyword scan disabled and scrape.do falling back to ScraperAPI for Noon, credit usage is within plan limits. Amazon was the primary waste source.

---

## 6. CURRENT SYSTEM STATUS

### ✅ Working

| Component | Detail |
|-----------|--------|
| Noon Egypt parser | Method D, `regex_matched=46-48`, per-product prices |
| Noon beauty/home | Correct prices, correct categories |
| Noon electronics | Working via ScraperAPI; 15% discount threshold |
| Noon category detection | Returns None on unknown → falls back to search term default_cat |
| Jumia Egypt | Flash sales, phones, electronics, home office, sporting goods, baby |
| Amazon Egypt | Static product list only (14 deals from hardcoded ASINs) |
| FCM notifications | Tier topics: tier_vip, tier_premium, tier_free |
| Fraud detection | FAKE / SUSPICIOUS / UNVERIFIED / GENUINE badges |
| Cycle summary | End-of-cycle log with total deals, proxy status, next interval |
| Admin login | Firebase SDK self-hosted — no CDN dependency |
| Admin notification modal | Dropdown no longer closes modal |
| Post-cycle purge | Deletes deals with impossible price ratios automatically |
| Scraper process | Starts correctly, logs "Scraper started, waiting for first cycle..." |

### ❌ Broken / Not Implemented

| Component | Issue |
|-----------|-------|
| Amazon keyword search | Disabled by default (`AMAZON_KEYWORD_ENABLED=false`); geocodes unsupported |
| Jumia fashion | Selector broken — 0 products |
| Jumia beauty-health | URL returns 404/502 |
| Noon JSON-LD | Never found on Noon search pages — accepted, Method D covers it |
| Safqa price checker | "not found" on most Egypt products — limited coverage |
| Amazon scrape.do | HTTP 400 for all Egypt/UAE/Saudi requests |

---

## 7. OUTSTANDING TASKS (Priority Order)

| Priority | Task | Status |
|----------|------|--------|
| 1 | ~~DISABLE Amazon keyword scan~~ | ✅ DONE |
| 2 | Fix Jumia fashion selectors | PENDING |
| 3 | Fix Jumia beauty-health URL | PENDING |
| 4 | Add credit usage counter to cycle summary | PENDING |
| 5 | Find working Amazon Egypt data source (not keyword API) | PENDING |
| 6 | Fix Safqa coverage / replace with alternative price checker | PENDING |
| 7 | Add failure alerts / monitoring for 0-product scrape runs | PENDING |
| 8 | ~~Admin notification modal~~ | ✅ DONE |
| 9 | ~~ASIN/SKU dedup for Noon cross-keyword pages~~ | ✅ DONE |
| 10 | Explore `__NEXT_DATA__` as Noon JSON alternative | PENDING |

---

## 8. KEY TECHNICAL DECISIONS

### Noon Parsing Architecture (Method D)
```
For each <a href="*/p/*"> product link:
  Walk up DOM (max 7 levels)
  At each level:
    - If container has >1 product links → BREAK (shared grid boundary)
    - Stage 1: look for data-qa="product-price" and data-qa="product-old-price"
      - Validate: cp >= 200, op > cp, ratio in [1.15, 8.0]
      - If valid → use these prices, skip Stage 2
      - If invalid → fall through to Stage 2 (not hard-skip)
    - Stage 2: get container text, strip title substring, extract standalone numbers
      - Floor: 200 ≤ n ≤ 500,000
      - op = largest, find cp where 1.15 ≤ op/cp ≤ 8.0
      - If no valid pair → D-miss, log and continue
    - Validate discount threshold (15% electronics, MIN_DISCOUNT% others)
    - Save deal
```

### Deal ID Design (Known Limitation)
```python
deal_id = MD5(site + url + current_price)
```
- Including price in ID means a deal at wrong price (e.g. 1400) has permanent unique ID
- Scraper can never overwrite it — only `_purge_bad_deals()` or manual deletion removes it
- Considered changing ID to exclude price, but would break existing Firestore documents

### Amazon Kill Switch
```python
AMAZON_KEYWORD_ENABLED = os.getenv("AMAZON_KEYWORD_ENABLED", "false").lower() == "true"
```
- Defaults to `false` — safe by default, no credit waste
- Enable by setting Railway env var `AMAZON_KEYWORD_ENABLED=true`

### Firebase SDK Self-Hosting
```dockerfile
RUN curl -sL https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js -o firebase-app-compat.js
```
- Build-time download (Railway build environment has unrestricted internet)
- Runtime serving via Flask `/sdk/<filename>` route
- Browser never makes external requests for JS

---

## 9. BUSINESS CONTEXT

- **Product:** DealHunter Egypt — mobile app for finding discounted products on Amazon, Noon, Jumia
- **Tech stack:** Python/Flask backend + Firebase/Firestore + Flutter mobile app
- **Deployment:** Railway (backend) + Firebase (database/auth) + Codemagic (Flutter CI/CD)
- **Monetization:** Free / Trial / Premium / VIP tiers with FCM push notifications
- **Revenue discussion:** 30% revenue share proposed; Claude recommended 10–15% net profit, time-limited arrangement
- **Markets:** Egypt (primary), UAE, Saudi Arabia

---

## 10. KEY LEARNINGS

1. **scrape.do geocode support:** Egypt/UAE/Saudi not supported for Amazon structured API — check geocode whitelist before sending any requests
2. **Noon HTML structure:** No JSON-LD on search pages; product cards are `<a href="/p/">` elements with prices either in `data-qa` attributes or as standalone numbers in card text
3. **DOM boundary guards are critical:** Without the `>1 links` check, prices from one product bleed into adjacent cards
4. **Ratio bounds catch specs effectively:** Numbers like "5600" (DDR5), "1400" (RPM), "144" (Hz) all have ratios > 8× against real prices — clean exclusion
5. **deal_id must not include mutable fields:** Including `current_price` in the ID means price corrections require purge logic; URL-only IDs would be cleaner
6. **CDN failures cascade:** One blocked CDN script → entire admin panel broken; always self-host critical dependencies
7. **Edit anchors can destroy guards:** Using `if __name__ == "__main__":` as an edit anchor in `old_string` and replacing it with new code deletes the guard — use surrounding context as anchor instead
8. **`return "general"` vs `return None`:** Python's truthiness means a non-None fallback string breaks `or default_cat` patterns — always return None when meaning "no match"
9. **Purge is complementary to prevention:** Parser fixes stop new bad deals; purge cleans existing ones. Both are needed because deal_id makes bad documents permanent.
10. **Simple one-line fixes have the highest ROI:** `AMAZON_KEYWORD_ENABLED=false` (1 line) stopped 54 HTTP 400s per cycle immediately

---

## 11. COMMIT HISTORY (THIS SESSION)

| Commit | Description |
|--------|-------------|
| `b73d9ae` | Disable Amazon keyword scan by default; fix geocode lookup bug |
| `a47e967` | Noon: fix price floor, category fallback, expand category keywords |
| `e71fd99` | Merge main: bring in Amazon keyword kill switch + geocode fix |
| `8985e2e` | Noon: add ratio check to Stage 1, fall through to Stage 2 on bad values |
| `684a252` | Add post-cycle purge for deals with impossible price ratios |
| `01ca2ae` | Fix critical bug: restore `if __name__ == '__main__'` guard |
| `9c7c4f9` | Fix admin login: switch Firebase SDK from gstatic.com to unpkg.com |
| `f1a380d` | Self-host Firebase SDK — eliminate external CDN dependency |

---

*Generated: 2026-05-06 | Branch: main | Deployment: Railway*
