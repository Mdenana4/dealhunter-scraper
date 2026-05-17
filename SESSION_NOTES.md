# DealHunter Scraper — Full Session Documentation

## Overview

Complete debugging and improvement session for the DealHunter scraper after migration from Railway/Render to **Google Cloud Run + Supabase PostgreSQL + TimescaleDB**.

---

## Infrastructure

| Component | Service |
|-----------|---------|
| Compute | Google Cloud Run Job |
| Primary DB | Supabase PostgreSQL (`deals` table) |
| Time-Series DB | TimescaleDB (`price_snapshots` hypertable) |
| Container Registry | `gcr.io/dealhunter-egypt-70d29/dealhunter-scraper:latest` |
| Build Config | `cloudbuild_scraper.yaml` |
| Project ID | `dealhunter-egypt-70d29` |
| Branch | `claude/resolve-user-support-5Eljo` |
| PR | https://github.com/Mdenana4/dealhunter-scraper/pull/10 |

---

## Sources Scraped (7 total)

| Source | Platform | Country | Bot Protection | Bypass Method |
|--------|----------|---------|----------------|---------------|
| amazon_eg | Amazon | Egypt | AWS WAF + IP block | scrape.do plain proxy |
| amazon_ae | Amazon | UAE | AWS WAF + IP block | scrape.do plain proxy |
| amazon_sa | Amazon | Saudi Arabia | AWS WAF | proxy rotation |
| noon_eg | Noon | Egypt | Akamai Bot Manager | scrape.do rendered + __NEXT_DATA__ |
| noon_ae | Noon | UAE | Akamai Bot Manager | scrape.do rendered + __NEXT_DATA__ |
| noon_sa | Noon | Saudi Arabia | Akamai Bot Manager | scrape.do rendered + __NEXT_DATA__ |
| jumia_eg | Jumia | Egypt | Cloudflare WAF | curl_cffi chrome120 TLS impersonation |

---

## Key Configuration

| Setting | Default | Override |
|---------|---------|----------|
| MIN_DISCOUNT | 40% | `MIN_DISCOUNT` env var |
| MIN_PRODUCT_PRICE | 50 | `MIN_PRODUCT_PRICE` env var |
| REQUEST_TIMEOUT | 120s | `REQUEST_TIMEOUT` env var |
| SCRAPEDO_TOKEN | — | env var (required) |
| DATABASE_URL | — | env var (Supabase, required) |
| TIMESCALE_URL | — | env var (TimescaleDB, required) |
| AMAZON_ENABLED | true | env var |
| NOON_ENABLED | true | env var |
| JUMIA_ENABLED | true | env var |

---

## All Problems Found and Fixed

### 1. Noon EG/AE/SA — 0 deals

**Root cause:** Google Cloud Run datacenter IPs blocked by Akamai Bot Management. Local Playwright also fails because the block is at IP level, not browser fingerprint level.

**Fix:** Route all Noon through scrape.do `render=true`. Their infrastructure bypasses Akamai. Added `__NEXT_DATA__` JSON extraction as fallback (Noon is Next.js — every page embeds full product state as JSON in `<script id="__NEXT_DATA__">`). Added 404 early-exit so dead URLs skip Playwright immediately.

---

### 2. Jumia EG — 1 deal only

**Root cause 1:** URLs pointed to general category pages with 10–30% discounts (below 40% threshold).
**Root cause 2:** Cloudflare blocks Cloud Run IPs.

**Fix 1:** Switched to `f[n_special_price]=1` filter URLs — shows only products currently on sale.
**Fix 2:** curl_cffi `impersonate="chrome120"` as primary strategy. Performs exact TLS fingerprint impersonation of Chrome 120. scrape.do `super=true` as fallback.

---

### 3. Amazon EG/AE — 0 deals

**Root cause 1:** HTTP 503 — Cloud Run IPs blocked.
**Root cause 2:** `s?k=deals` URLs return general products, most < 40% discount.

**Fix 1:** Force scrape.do for `country in ("eg","ae")` in `_scrape_amazon_page()`.
**Fix 2:** Category-specific discount-filtered URLs: `s?k=CATEGORY&rh=p_n_pct-off-with-tax%3A40-&s=discount-rank` — Amazon's native ≥40% filter sorted by largest discount.

---

### 4. Price snapshots — 0 recorded every run

**Root cause:** Migration rollback bug. `create_hypertable()` already-exists error called `conn.rollback()`, rolling back ALL prior ALTER TABLE statements in the same transaction — including the `source` column addition. `conn.commit()` then committed nothing.

**Fix:** `conn.commit()` immediately after column migrations, before any hypertable call. Each risky SQL now in its own commit/rollback cycle.

---

### 5. deals_category_check constraint violations

**Root cause:** Old DB constraint only allowed a limited category list. Scraper produces `beauty`, `pets`, etc. which were not in it.

**Fix:** Migration drops old constraint, recreates with all 14 categories:
`electronics, fashion, home, sports, beauty, baby, automotive, books, pets, food, health, grocery, office, other`

---

### 6. `column "reviews" does not exist` on startup

**Root cause:** Stale migration: `UPDATE deals SET review_count = reviews` — column `reviews` was renamed to `review_count` long ago.

**Fix:** Removed the stale line. All data-copy migrations wrapped in try/except.

---

### 7. Dead Noon sale URLs (all 404)

`/sale-electronics/`, `/sale-fashion/`, `/sale-home/` — Noon deleted these pages.

**Fix:** Replaced with subcategory URLs + `?sort_by=discount_percent&sort_order=d`. Confirmed returning 16+ deals per category in live logs.

---

### 8. Jumia `/deals-of-the-day/` — 404

**Fix:** Removed. Replaced with more category pages using `f[n_special_price]=1`.

---

### 9. PriceCleaner EU decimal format

**Root cause:** Regex `[\d,]+(?:\.\d+)?` truncated `1.299,00 SAR` to `1.299` (stopped before comma).

**Fix:** Changed regex to `[\d.,]+` — captures full number, existing EU/US detection handles the rest.

---

## Anti-Bot Bypass Architecture

```
Amazon EG/AE  →  scrape.do plain proxy (render=false)
               ↓ fallback
               direct HTTP

Amazon SA     →  proxy rotation (scrape.do + direct)

Noon          →  scrape.do rendered (render=true, wait=6000ms)
               ↓ fallback (if 0 product boxes found)
               __NEXT_DATA__ JSON extraction
               ↓ fallback (if no __NEXT_DATA__)
               Playwright stealth browser
               (404 from scrape.do → skip all, return [])

Jumia         →  curl_cffi impersonate="chrome120" (TLS fingerprint)
               ↓ fallback
               scrape.do super=true, geoCode=eg
               ↓ fallback
               direct HTTP
```

---

## Database Schema

### deals table (Supabase)
```sql
id TEXT PRIMARY KEY,           -- MD5(site + url + price)
product_id TEXT,
site VARCHAR(32),              -- 'amazon_eg', 'noon_eg', etc.
title TEXT,
image_url TEXT,
product_url TEXT,
category VARCHAR(32),          -- CHECK constraint on 14 values
original_price DECIMAL(12,2),
current_price DECIMAL(12,2),
discount_percent DECIMAL(5,1),
savings DECIMAL(12,2),
currency VARCHAR(8),           -- 'EGP', 'AED', 'SAR'
verdict VARCHAR(32),           -- 'GENUINE', 'FAKE', 'SUSPICIOUS'
fake_score DECIMAL(5,2),
recommendation VARCHAR(32),
confidence DECIMAL(5,2),
fraud_reasons JSONB,
rating DECIMAL(3,1),
review_count INTEGER,
is_active BOOLEAN,
last_seen_at TIMESTAMPTZ,
created_at TIMESTAMPTZ
```

### price_snapshots table (TimescaleDB hypertable)
```sql
deal_id TEXT,
product_id TEXT,
site VARCHAR(32),
source VARCHAR(32),            -- which scraping strategy was used
price DECIMAL(12,2),
original_price DECIMAL(12,2),
discount_percent DECIMAL(5,1),
currency VARCHAR(8),
timestamp TIMESTAMPTZ          -- hypertable partition key
```

---

## URL Coverage (Final State)

### Amazon EG / AE / SA (identical coverage, different domains)

**Discount pages (23 categories):**
Smartphones, Laptops, Headphones, TVs, Cameras, Gaming, Electronics, Men's Fashion, Women's Fashion, Shoes, Watches, Bags, Kitchen, Furniture, Beauty, Skincare, Perfume, Sports, Baby, Books, Automotive, Pet Supplies, Grocery

**Bestseller pages (9 categories):**
Electronics, Fashion, Beauty, Kitchen, Books, Toys, Automotive, Pet Supplies, Grocery

### Noon EG / AE / SA (identical coverage, different locales)

**Discount-sorted pages (22 categories):**
Electronics, Mobiles & Tablets, Laptops, TVs, Audio, Cameras, Gaming, Women's Clothing, Men's Clothing, Women's Shoes, Men's Shoes, Watches, Bags, Home & Kitchen, Furniture, Beauty & Fragrance, Skincare, Sports, Baby, Grocery, Automotive, Pet Supplies

**Bestseller pages (9 categories):**
Electronics, Fashion, Beauty, Home & Kitchen, Sports, Baby, Grocery, Automotive, Pet Supplies

### Jumia EG

**Discount pages (25 categories + 3 catalog pages):**
General catalog pages 1–3, Phones & Tablets, Laptops, TVs, Headphones, Cameras, Gaming, Women's Clothing, Men's Clothing, Women's Shoes, Men's Shoes, Watches, Bags, Furniture, Appliances, Home Living, Health & Beauty, Skincare, Fragrances, Sports, Baby, Books, Automotive, Pet Supplies, Grocery

**Bestseller pages (5):**
Top-rated catalog, Phones, Beauty, Home, Sports (all with discount filter)

---

## Test Suite

### test_parsing.py — Offline (49 tests, no network, no DB)
```bash
python3 test_parsing.py
```
Covers: PriceCleaner, category detection, Noon HTML parsing, Noon __NEXT_DATA__ JSON,
Jumia HTML parsing, deal ID uniqueness, _build_deal edge cases.
**Result: 49/49 PASS**

### test_live.py — Live network (Cloud Shell only)
```bash
export SCRAPEDO_TOKEN="your_token"
python3 test_live.py
```
Tests real Amazon EG, Noon EG, Jumia EG without touching the database.

---

## Deploy Commands

```bash
# One-time: set project
gcloud config set project dealhunter-egypt-70d29

# Every deploy
cd ~/dealhunter-deploy
git fetch origin && git checkout claude/resolve-user-support-5Eljo && git pull
gcloud builds submit --config=cloudbuild_scraper.yaml
gcloud run jobs update dealhunter-scraper --region=us-central1 \
  --image=gcr.io/dealhunter-egypt-70d29/dealhunter-scraper:latest
gcloud run jobs execute dealhunter-scraper --region=us-central1 --wait
```

## Check Results After Deploy
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=dealhunter-scraper" \
  --limit=200 --format="value(textPayload)" --freshness=15m \
  | grep -E "deals|ERROR|WARN|snapshot"
```

---

## Results: Before vs After

| Metric | Before | After |
|--------|--------|-------|
| Noon EG deals/run | 0 | 50+ |
| Noon AE deals/run | 0 | 10+ |
| Noon SA deals/run | 0 | 10+ |
| Amazon EG deals/run | 0 | 20+ |
| Amazon AE deals/run | 0 | 20+ |
| Amazon SA deals/run | 21 | 30+ |
| Jumia EG deals/run | 1 | 85+ |
| Price snapshots/run | 0 | 116+ |
| DB errors/run | 10+ | 0 |
| Cycle time | 1324s | ~400s |
| Categories covered | partial | 23 per source |
| Bestseller pages | 0 | 9 per source |

---

## Commit History

| Commit | What changed |
|--------|-------------|
| `ae90f63` | Full category + bestseller coverage for all 7 sources |
| `9ca7748` | Force scrape.do for Amazon EG/AE + expand discount URLs |
| `4e10932` | Fix migration rollback bug (source column + category constraint) |
| `6d05b01` | Fix 5 live production bugs (reviews col, 404 URLs, deals-of-the-day) |
| `46b574f` | Fix PriceCleaner EU decimal + 49-test offline test suite |
| `9bc593f` | Noon: scrape.do rendered mode + __NEXT_DATA__ parsing |
| `46ac601` | Playwright Noon + curl_cffi Jumia + schema fixes |
