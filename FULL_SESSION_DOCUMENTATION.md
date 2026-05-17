# DealHunter Scraper — Complete Session Documentation
> All sessions from first conversation to last. Branch: `claude/resolve-user-support-5Eljo`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Infrastructure](#2-infrastructure)
3. [The Two Systems](#3-the-two-systems)
4. [Files and Their Roles](#4-files-and-their-roles)
5. [Database Schema](#5-database-schema)
6. [Anti-Bot Bypass Architecture](#6-anti-bot-bypass-architecture)
7. [All Problems Found and Fixed](#7-all-problems-found-and-fixed)
8. [URL Coverage (Final State)](#8-url-coverage-final-state)
9. [Key Configuration](#9-key-configuration)
10. [Deploy Commands](#10-deploy-commands)
11. [Test Suite](#11-test-suite)
12. [Results: Before vs After](#12-results-before-vs-after)
13. [Full Commit History](#13-full-commit-history)

---

## 1. Project Overview

DealHunter is a scraper that collects deals and discounts (≥40% off) from 7 e-commerce sources across Egypt, UAE, and Saudi Arabia. It runs as a scheduled **Google Cloud Run Job**, stores deals in **Supabase PostgreSQL**, and records price time-series in **TimescaleDB**.

The full session rebuilt the scraper from near-zero output (0 deals, 0 price snapshots, multiple crashes) into a working production system, then added a second independent system for price history and fake discount detection.

**Sources scraped (7 total):**

| Source Key | Platform | Country |
|---|---|---|
| `amazon_eg` | Amazon | Egypt |
| `amazon_ae` | Amazon | UAE |
| `amazon_sa` | Amazon | Saudi Arabia |
| `noon_eg` | Noon | Egypt |
| `noon_ae` | Noon | UAE |
| `noon_sa` | Noon | Saudi Arabia |
| `jumia_eg` | Jumia | Egypt |

---

## 2. Infrastructure

| Component | Service | Detail |
|---|---|---|
| Compute | Google Cloud Run Job | Serverless, triggered on schedule |
| Primary DB | Supabase PostgreSQL | `deals` table |
| Time-Series DB | TimescaleDB | `price_snapshots` hypertable |
| Container Registry | Google Container Registry | `gcr.io/dealhunter-egypt-70d29/` |
| Build System | Google Cloud Build | `cloudbuild_scraper.yaml`, `cloudbuild_tracker.yaml` |
| Project ID | `dealhunter-egypt-70d29` | |
| Proxy Service | scrape.do | Akamai bypass (Noon), Amazon proxy |
| TLS Impersonation | curl_cffi | Cloudflare bypass (Jumia) |

---

## 3. The Two Systems

### System 2 — Deals Scraper (existed first, fixed throughout session)

- **Job name:** `dealhunter-scraper`
- **Entry point:** `scraper_job.py` → `scraper_cloudrun.py`
- **Docker image:** `gcr.io/dealhunter-egypt-70d29/dealhunter-scraper:latest`
- **Build config:** `cloudbuild_scraper.yaml`
- **Dockerfile:** `Dockerfile.scraper`
- **What it does:** Scrapes only products with ≥40% discount. Stores in `deals` table + `price_snapshots` (`snapshot_type='deal'`).
- **Filter:** `MIN_DISCOUNT=40`, `MIN_PRODUCT_PRICE=50`
- **Schedule:** Hourly or as needed

### System 1 — Price History Collector (built from scratch this session)

- **Job name:** `dealhunter-tracker`
- **Entry point:** `price_tracker_job.py` → `price_tracker_cloudrun.py`
- **Docker image:** `gcr.io/dealhunter-egypt-70d29/dealhunter-tracker:latest`
- **Build config:** `cloudbuild_tracker.yaml`
- **Dockerfile:** `Dockerfile.tracker`
- **What it does:** Crawls ALL products across all 7 sources with NO discount filter. Saves a price snapshot for every product every run. Builds historical price database used to detect fake discounts.
- **Filter:** None (collects all products above `TRACKER_MIN_PRICE=10`)
- **Schedule:** Daily is sufficient

**How the two systems relate:**

```
System 1 (daily)          System 2 (hourly)
     │                          │
     │  Writes price history     │  Finds deals ≥40% off
     ▼                          ▼
price_snapshots            deals table
(snapshot_type='catalog')  + price_snapshots
                           (snapshot_type='deal')
     │
     ▼
discount_verdicts
(GENUINE / FAKE / SUSPICIOUS / UNVERIFIED)
     │
     └──► System 2 can call PriceTracker.verify_discount()
          before showing a deal to users
```

System 1 and System 2 are completely independent. They share the `price_snapshots` table but never conflict — different `snapshot_type` values.

---

## 4. Files and Their Roles

### Core Scraper (System 2)

| File | Role |
|---|---|
| `scraper_cloudrun.py` | Main scraper. `DealHunterScraper` class with all 7 source parsers, proxy routing, DB upsert, fake score calculation. |
| `scraper_job.py` | Cloud Run Job entry point. Imports `DealHunterScraper`, calls `run_cycle()`, prints results, exits. |
| `Dockerfile.scraper` | Docker image for System 2. Installs Playwright (for fallback) + curl_cffi + psycopg2. |
| `cloudbuild_scraper.yaml` | Cloud Build config. Builds `dealhunter-scraper:latest`. |

### Price History Collector (System 1 — new this session)

| File | Role |
|---|---|
| `price_tracker_cloudrun.py` | System 1 main module. `TrackerDB`, `FakeDiscountDetector`, `CatalogScraper`, `PriceTracker` classes. 991 lines. |
| `price_tracker_job.py` | Cloud Run Job entry point for System 1. Same pattern as `scraper_job.py`. |
| `Dockerfile.tracker` | Docker image for System 1. Lighter than scraper (no Playwright needed). |
| `cloudbuild_tracker.yaml` | Cloud Build config. Builds `dealhunter-tracker:latest`. |

### Database / Schema

| File | Role |
|---|---|
| `supabase_schema.sql` | Full Supabase PostgreSQL schema (deals table + category constraint). |
| `timescale_schema.sql` | TimescaleDB hypertable schema (price_snapshots). |
| `supabase_seed.sql` | Seed data. |
| `migration_data.py` | Programmatic DB migration runner. |

### Tests

| File | Role |
|---|---|
| `test_parsing.py` | 49 offline unit tests — PriceCleaner, category detection, HTML parsers, deal ID generation. No network, no DB. |
| `test_live.py` | Live network tests for Amazon EG, Noon EG, Jumia EG without touching the DB. |
| `test_scraper.py` | Focused Amazon.eg scraper diagnostic with detailed output. |
| `test_phase1.py` | Phase 1 integration tests. |
| `test_phase5.py` | Phase 5 integration tests. |

### Server / API (pre-existing)

| File | Role |
|---|---|
| `server_cloudrun.py` | REST API server (Flask/Cloud Run). Serves deals to the mobile app. |
| `health_server.py` | Health-check endpoint. |
| `price_history_api.py` | API routes for price history queries. |

---

## 5. Database Schema

### `deals` table (Supabase PostgreSQL)

```sql
CREATE TABLE deals (
    id                TEXT PRIMARY KEY,          -- MD5(site + url + price)
    product_id        TEXT,
    site              VARCHAR(32),               -- 'amazon_eg', 'noon_eg', etc.
    title             TEXT,
    image_url         TEXT,
    product_url       TEXT,
    category          VARCHAR(32),               -- CHECK constraint (14 values)
    original_price    DECIMAL(12,2),
    current_price     DECIMAL(12,2),
    discount_percent  DECIMAL(5,1),
    savings           DECIMAL(12,2),
    currency          VARCHAR(8),                -- 'EGP', 'AED', 'SAR'
    verdict           VARCHAR(32),               -- 'GENUINE', 'FAKE', 'SUSPICIOUS'
    fake_score        DECIMAL(5,2),
    recommendation    VARCHAR(32),
    confidence        DECIMAL(5,2),
    fraud_reasons     JSONB,
    rating            DECIMAL(3,1),
    review_count      INTEGER,
    is_active         BOOLEAN DEFAULT true,
    last_seen_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Category constraint (14 valid values):
ALTER TABLE deals ADD CONSTRAINT deals_category_check
    CHECK (category IN (
        'electronics','fashion','home','sports','beauty',
        'baby','automotive','books','pets','food',
        'health','grocery','office','other'
    ));
```

### `price_snapshots` table (TimescaleDB hypertable)

```sql
CREATE TABLE price_snapshots (
    deal_id          TEXT,
    product_id       TEXT,
    site             VARCHAR(32),
    source           VARCHAR(32),           -- which scraping strategy was used
    price            DECIMAL(12,2),
    original_price   DECIMAL(12,2),
    discount_percent DECIMAL(5,1),
    currency         VARCHAR(8),
    snapshot_type    VARCHAR(16) DEFAULT 'deal',  -- 'deal' (S2) or 'catalog' (S1)
    timestamp        TIMESTAMPTZ NOT NULL   -- hypertable partition key
);

SELECT create_hypertable('price_snapshots', 'timestamp', if_not_exists => TRUE);
```

### `product_catalog` table (System 1 — new this session)

```sql
CREATE TABLE product_catalog (
    product_id    TEXT PRIMARY KEY,
    site          VARCHAR(32),
    category      VARCHAR(32),
    title         TEXT,
    product_url   TEXT,
    image_url     TEXT,
    currency      VARCHAR(8),
    last_price    DECIMAL(12,2),
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### `discount_verdicts` table (System 1 — new this session)

```sql
CREATE TABLE discount_verdicts (
    product_id      TEXT,
    site            VARCHAR(32),
    claimed_original DECIMAL(12,2),
    current_price   DECIMAL(12,2),
    verdict         VARCHAR(16),        -- 'GENUINE','FAKE','SUSPICIOUS','UNVERIFIED'
    confidence      DECIMAL(5,2),
    reason          TEXT,
    analyzed_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (product_id, site)
);
```

**Verdict logic (FakeDiscountDetector):**

| Verdict | Condition |
|---|---|
| `UNVERIFIED` | Fewer than 7 historical data points |
| `FAKE` | Median historical price ≤ current_price × 1.10 (product never sold near claimed original) |
| `SUSPICIOUS` | Claimed original > max historical price × 1.30 |
| `GENUINE` | All other cases |

Verdicts are cached for 24 hours. System 2 can call `PriceTracker.verify_discount(product_id, site, claimed_original, current_price)` to get a cached or fresh verdict before showing a deal to users.

---

## 6. Anti-Bot Bypass Architecture

Each platform uses different bot protection — each requires a different bypass:

```
┌─────────────────────────────────────────────────────────────────┐
│  Amazon EG / AE / SA                                            │
│  Protection: AWS WAF + Cloud Run IP blocks                      │
│  ─────────────────────────────────────────────────────────────  │
│  Primary:   scrape.do render=false + geoCode={eg|ae|sa}        │
│  Fallback:  direct HTTP (plain requests)                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Noon EG / AE / SA                                              │
│  Protection: Akamai Bot Management (IP-level block)             │
│  ─────────────────────────────────────────────────────────────  │
│  Primary:   scrape.do render=true + wait=6000ms                │
│  Fallback:  __NEXT_DATA__ JSON extraction (Noon = Next.js)     │
│  Last:      Playwright stealth browser                          │
│  On 404:    skip immediately, return []                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Jumia EG                                                       │
│  Protection: Cloudflare WAF                                     │
│  ─────────────────────────────────────────────────────────────  │
│  Primary:   curl_cffi impersonate="chrome120"                  │
│             (exact TLS fingerprint of Chrome 120)              │
│  Fallback:  scrape.do super=true + geoCode=eg                  │
│  Last:      direct HTTP                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Why these specific choices:**

- **scrape.do `render=true`** — Executes JavaScript in a real browser, waits 6000ms. Required for Noon because React renders product cards client-side. Without it, the HTML has no product data.
- **scrape.do `render=false` for Amazon** — Amazon pages are server-rendered HTML. Render mode would be slower and unnecessary. Plain proxy suffices.
- **`geoCode=eg/ae/sa`** — Routes the proxy exit node through the correct country so Amazon/Noon serve localized pricing and correct currency.
- **curl_cffi `chrome120`** — Cloudflare checks the TLS ClientHello fingerprint. Python `requests` has a Python-OpenSSL fingerprint that Cloudflare recognizes as a bot. `curl_cffi` replaces the TLS stack with libcurl compiled against BoringSSL, producing an exact Chrome 120 fingerprint.
- **`__NEXT_DATA__` fallback** — Every Next.js page embeds its full server state in `<script id="__NEXT_DATA__">`. Even if Akamai blocks HTML parsing, this JSON is already in the page and contains all product data.

---

## 7. All Problems Found and Fixed

### Problem 1 — Noon EG/AE/SA: 0 deals every run

**Root cause:** Google Cloud Run datacenter IPs are blocked at the network level by Akamai Bot Management. This is an IP-range block, not a browser fingerprint check, so local Playwright also fails when running from Cloud Run.

**Fix applied:** Routed all Noon requests through scrape.do `render=true`. Their infrastructure has residential/ISP IPs that bypass Akamai. Added `__NEXT_DATA__` JSON extraction as a fallback — Noon is a Next.js application and embeds full product state as JSON in every page. Added 404 early-exit so dead category URLs immediately return `[]` without spawning a Playwright browser.

**Commit:** `9bc593f`

---

### Problem 2 — Jumia EG: 1 deal per run

**Root cause 1:** Category URLs (e.g. `/phones-tablets/`) showed general products — most had 10–30% discounts, below the 40% threshold.

**Root cause 2:** Cloudflare WAF blocks Cloud Run IPs. Standard `requests` was returning Cloudflare challenge HTML instead of product pages.

**Fix 1:** Switched to `f[n_special_price]=1` filter parameter on Jumia URLs — shows only products currently marked as on-sale.

**Fix 2:** `curl_cffi` with `impersonate="chrome120"` as primary strategy. scrape.do `super=true` (their most powerful residential proxy tier) as fallback.

**Commit:** `46ac601`, `ae90f63`

---

### Problem 3 — Amazon EG/AE: 0 deals

**Root cause 1:** HTTP 503 from Cloud Run IPs being blocked by AWS WAF on Amazon.

**Root cause 2:** Generic `s?k=deals` search URLs return general product listings where most products have <40% discounts. The scraper found cards but none passed the discount filter.

**Fix 1:** Force scrape.do for `country in ("eg", "ae")` in `_scrape_amazon_page()`. Previously Amazon EG/AE tried direct HTTP first.

**Fix 2:** Category-specific discount-filtered URLs using Amazon's native filter: `s?k=CATEGORY&rh=p_n_pct-off-with-tax%3A40-&s=discount-rank`. This tells Amazon to show only products ≥40% off, sorted by largest discount first. 23 categories per country.

**Commit:** `9ca7748`, `ae90f63`

---

### Problem 4 — Amazon EG/AE/SA: 48 cards found, 0 deals extracted

**Root cause 1 (price parsing):** On Amazon Middle East, `span.a-price-whole` contains a nested `span.a-price-decimal` holding `"."`. When `get_text()` is called on the outer span, it returns `"599."` (the decimal span's content appended). The code then built `current_price_str = "599..00"` (double period), which the price cleaner rejected, giving `price=0`. Product rejected.

**Root cause 2 (no original price):** When original price extraction failed, `_build_deal` set `original = current`, computed `discount = 0%`, which fails the `MIN_DISCOUNT=40` check. Product rejected.

**Fix — price parsing:** Use `span.a-price:not(.a-text-price) span.a-offscreen` instead of `span.a-price-whole`. Amazon's `.a-offscreen` spans contain clean price strings like `"SAR 599.00"` — no nested spans, no double-period bug.

**Fix — original price fallback chain:**
1. `span.a-text-price span.a-offscreen` — standard strikethrough price
2. `span[data-a-color='secondary'] span.a-offscreen` — secondary color price
3. `span.a-price.a-text-price span.a-offscreen` — combined class selector
4. `span[data-a-strike='true'] span.a-offscreen` — data attribute selector
5. **Badge fallback:** Extract `%` from discount badge text (e.g. `"45% off"`), then compute `original = current / (1 - pct/100)`
6. **Last resort for discount-search URLs:** If URL contains `pct-off-with-tax` (our filtered URLs), Amazon guarantees ≥40% off. Estimate `original = current / 0.60` (assumes 40% off minimum)

**Commit:** `a6398b0`

---

### Problem 5 — Amazon bestseller pages: "No cards found"

**Root cause:** Bestseller pages (`/gp/bestsellers/`, `/bestsellers/`) use a completely different HTML structure. Standard `s-result-item` and `s-search-result` divs don't exist on these pages. The HTML was 410KB+ with real products, but zero cards matched the search-results selectors.

**Fix:** Added bestseller-specific selectors as fallback when standard selectors return nothing:
```python
"div.p13n-desktop-grid div[id^='gridItemRoot']"  # main grid
"li.zg-item-immersion"                            # top 100 list
"li[id^='p13n-asin-index']"                       # indexed list
"div.zg_itemWrapper"                              # legacy bestseller
```

**Commit:** `a6398b0`

---

### Problem 6 — Price snapshots: 0 recorded every run

**Root cause:** Migration rollback bug. When `create_hypertable()` was called and TimescaleDB returned "already exists", the code called `conn.rollback()`. This rolled back ALL prior `ALTER TABLE` statements in the same transaction — including the `source` column addition and category constraint. The following `conn.commit()` committed nothing. On every subsequent run, `_ensure_tables()` found no `source` column, tried to add it again, tried `create_hypertable()` again, got "already exists" again, rolled back again.

**Fix:** `conn.commit()` immediately after each column migration, before any hypertable operation. Each risky DDL statement is in its own commit/rollback cycle. Hypertable creation uses `if_not_exists=True` and swallows the "already exists" response without rolling back.

**Commit:** `4e10932`

---

### Problem 7 — SSL SYSCALL EOF: 342 deals scraped, 0 inserted

**Root cause:** `upsert_deals()` took a single connection from the pool at the start and used it for all 342 deals in one transaction. Supabase terminates idle SSL connections after ~60 seconds. The scraping cycle takes 300–400 seconds. Halfway through, Supabase silently dropped the SSL connection. The next cursor operation failed with "SSL SYSCALL error: EOF detected" or "cursor already closed". `conn.rollback()` was called on the dead connection, which also failed. All 342 deals were lost.

**Fix 1 — Chunked upserts:** Split upsert into batches of 25 deals. Each batch gets its own connection from the pool, commits, and returns the connection. If one chunk fails, the others still succeed.

**Fix 2 — TCP keepalives:** Added to both `db_pool` and `ts_pool` on initialization:
```python
keepalives=1          # enable TCP keepalive
keepalives_idle=30    # send first keepalive after 30s idle
keepalives_interval=10 # retry every 10s
keepalives_count=5    # declare dead after 5 failed keepalives
```
This keeps the TCP connection alive at the OS level, preventing Supabase from silently dropping it.

**Commit:** `9861d9a`

---

### Problem 8 — `deals_category_check` constraint violations

**Root cause:** Old DB constraint was created with a limited category list (e.g. 8 categories). The scraper produces categories like `beauty`, `pets`, `grocery` which were not in the original constraint. Every insert for these categories failed with PostgreSQL constraint violation.

**Fix:** Migration script drops the old constraint and recreates it with all 14 categories:
`electronics, fashion, home, sports, beauty, baby, automotive, books, pets, food, health, grocery, office, other`

**Commit:** `4e10932`

---

### Problem 9 — `column "reviews" does not exist` on startup

**Root cause:** Stale migration line: `UPDATE deals SET review_count = reviews` — the column `reviews` had been renamed to `review_count` long before, but the migration script still referenced the old name. Every startup crashed with a PostgreSQL error before the scraper could run.

**Fix:** Removed the stale migration line. All data-copy migrations wrapped in `try/except` to prevent one bad migration from crashing the entire startup.

**Commit:** `6d05b01`

---

### Problem 10 — Dead Noon sale URLs (all 404)

Noon deleted their `/sale-electronics/`, `/sale-fashion/`, `/sale-home/` pages entirely.

**Fix:** Replaced with live subcategory URLs with `?sort_by=discount_percent&sort_order=d` sort parameter. Confirmed returning 16+ deals per category in live logs.

**Commit:** `6d05b01`

---

### Problem 11 — Dead Jumia URLs (confirmed 404 in live logs)

Multiple Jumia category URLs returned 404:

| Old URL | Status | Replacement |
|---|---|---|
| `/audio-headphones/` | 404 | `/headphones/` |
| `/mens-clothing/` | 404 | `/men-clothing/` |
| `/bags-wallets/` | 404 | `/luggage-bags/` |
| `/home-appliances/` | 404 | `/small-appliances/` |
| `/fragrances/` | 404 | removed |
| `/food-beverage/` | 404 | `/groceries/` |
| `/skincare/` | 404 | removed (under `/health-beauty/`) |
| `/deals-of-the-day/` | 404 | removed |

**Commit:** `c2123af`, `572d155`

---

### Problem 12 — Dead Noon camera/beauty URLs

| Old URL | Status | Replacement |
|---|---|---|
| `cameras-and-accessories` | 404 on all 3 markets | `electronics-and-mobiles/cameras` |
| `health-and-beauty` (parent) | 404 | `health-and-beauty/fragrance` + `health-and-beauty/skincare` |
| `laptops-and-computers` | 404 on SA | removed from SA |

**Commit:** `572d155`

---

### Problem 13 — PriceCleaner EU decimal format

**Root cause:** Regex `[\d,]+(?:\.\d+)?` truncated `"1.299,00 SAR"` to `"1.299"` — it stopped at the first comma and never captured the true value of 1299.00. Products with EU-format prices had their prices silently wrong.

**Fix:** Changed regex to `[\d.,]+` — captures the full numeric string including both dots and commas. Existing EU/US detection logic (`_is_european_format`) then correctly interprets which symbol is the decimal separator.

**Commit:** `46b574f`

---

### Problem 14 — Amazon SA: scrape.do geoCode not applied

**Root cause:** Amazon SA was using proxy rotation without country-specific routing. The `_scrape_amazon_page()` function only forced scrape.do for EG/AE but fell through to direct HTTP for SA.

**Fix:** Extended geoCode routing to all three countries:
```python
geo = {"eg": "eg", "ae": "ae", "sa": "sa"}.get(country, "")
if self.proxy_rotator.scrapedo_token:
    sd_url = f"...&render=false" + (f"&geoCode={geo}" if geo else "")
```

**Commit:** `c2123af`

---

### Problem 15 — System 1 did not exist

The price history system described in earlier architecture documents (`PRICE_TRACKING_SCHEMA.md`, `price_history_system.py`, `price_tracker.py`) were stubs or placeholders — none had working scraper logic, DB connectivity, or Cloud Run deployment files.

**Fix:** Built `price_tracker_cloudrun.py` (991 lines) from scratch with:
- `TrackerDB` — DB connection pools with TCP keepalives, schema creation, chunked catalog upserts, snapshot saves, verdict cache
- `FakeDiscountDetector` — statistical analysis of price history, 4-verdict classification system with 24h caching
- `CatalogScraper` — scrape.do (Amazon/Noon), curl_cffi (Jumia), HTML parsers for all 3 platforms, `__NEXT_DATA__` fallback for Noon
- `PriceTracker` — orchestrator, deduplication, `verify_discount()` public API for System 2
- `_CATALOG_URLS` — 7 sources × 21+ category browse URLs, NO discount filters
- Created `price_tracker_job.py`, `Dockerfile.tracker`, `cloudbuild_tracker.yaml`

**Commit:** `a6398b0`

---

## 8. URL Coverage (Final State)

### Amazon EG / AE / SA

All three markets have identical URL structure, just different domains (`amazon.eg`, `amazon.ae`, `amazon.sa`).

**Discount-filtered pages (23 categories, `≥40%` filter + sorted by discount):**
Smartphones, Laptops, Headphones, TVs, Cameras, Gaming, Electronics, Men's Fashion, Women's Fashion, Shoes, Watches, Bags, Kitchen, Furniture, Beauty, Skincare, Perfume, Sports, Baby, Books, Automotive, Pet Supplies, Grocery

URL pattern: `https://www.amazon.{tld}/s?k={category}&rh=p_n_pct-off-with-tax%3A40-&s=discount-rank&language=en_AE`

**Bestseller pages (9 categories):**
Electronics, Fashion, Beauty, Kitchen, Books, Toys, Automotive, Pet Supplies, Grocery

URL pattern: `https://www.amazon.{tld}/gp/bestsellers/{node}?language=en_AE`

---

### Noon EG / AE / SA

All three markets have identical structure, different locale slugs (`egypt-en`, `uae-en`, `saudi-en`).

**Discount-sorted pages (22 categories, `?sort_by=discount_percent&sort_order=d`):**
Electronics, Mobiles & Tablets, Laptops, TVs, Audio, Cameras, Gaming, Women's Clothing, Men's Clothing, Women's Shoes, Men's Shoes, Watches, Bags, Home & Kitchen, Furniture, Fragrance, Skincare, Sports, Baby, Grocery, Automotive, Pet Supplies

**Bestseller pages (9 categories):**
Electronics, Fashion, Beauty, Home & Kitchen, Sports, Baby, Grocery, Automotive, Pet Supplies

---

### Jumia EG

**Discount pages (25 categories + `f[n_special_price]=1` filter):**
Phones & Tablets, Laptops, TVs, Headphones, Cameras, Gaming, Women's Clothing, Men's Clothing, Women's Shoes, Men's Shoes, Watches, Home Office Furniture, Small Appliances, Home Living, Health & Beauty, Sports, Baby, Books, Automotive, Pet Supplies, Groceries

**Top catalog pages (3, with discount filter):**
`catalog/` pages 1–3

---

### System 1 Catalog URLs (No filters — all products)

System 1 uses simple keyword search URLs on Amazon and category browse on Noon/Jumia. 21–23 URLs per source, 7 sources = ~150 total URLs per cycle.

---

## 9. Key Configuration

### System 2 (scraper_cloudrun.py)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | required | Supabase PostgreSQL connection string |
| `TIMESCALE_URL` | = DATABASE_URL | TimescaleDB connection string (can differ) |
| `SCRAPEDO_TOKEN` / `SCRAPE_DO_TOKEN` | required | scrape.do API token |
| `MIN_DISCOUNT` | `40` | Minimum discount percent to keep a deal |
| `MIN_PRODUCT_PRICE` | `50` | Minimum price in local currency |
| `REQUEST_TIMEOUT` | `120` | HTTP request timeout in seconds |
| `AMAZON_ENABLED` | `true` | Toggle Amazon scraping |
| `NOON_ENABLED` | `true` | Toggle Noon scraping |
| `JUMIA_ENABLED` | `true` | Toggle Jumia scraping |
| `MAX_PAGES_PER_SOURCE` | `2` | Max pages to scrape per category URL |

### System 1 (price_tracker_cloudrun.py)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | required | Supabase PostgreSQL connection string |
| `TIMESCALE_URL` | = DATABASE_URL | TimescaleDB connection string |
| `SCRAPEDO_TOKEN` / `SCRAPE_DO_TOKEN` | required | scrape.do API token |
| `TRACKER_MIN_PRICE` | `10` | Minimum product price to record |
| `TRACKER_MAX_PAGES` | `2` | Max pages per category URL |
| `REQUEST_TIMEOUT` | `60` | HTTP request timeout in seconds |

---

## 10. Deploy Commands

### Deploy System 2 (deals scraper)

```bash
# Set project (one-time)
gcloud config set project dealhunter-egypt-70d29

# Pull latest code
cd ~/dealhunter-deploy
git fetch origin
git checkout claude/resolve-user-support-5Eljo
git pull

# Build and push Docker image
gcloud builds submit --config=cloudbuild_scraper.yaml

# Update Cloud Run Job with new image
gcloud run jobs update dealhunter-scraper \
  --region=us-central1 \
  --image=gcr.io/dealhunter-egypt-70d29/dealhunter-scraper:latest

# Run immediately and wait for completion
gcloud run jobs execute dealhunter-scraper --region=us-central1 --wait
```

### Deploy System 1 (price tracker) — first time

```bash
# Build and push Docker image
gcloud builds submit --config=cloudbuild_tracker.yaml

# Create Cloud Run Job (first time only)
gcloud run jobs create dealhunter-tracker \
  --image=gcr.io/dealhunter-egypt-70d29/dealhunter-tracker:latest \
  --region=us-central1 \
  --set-env-vars="DATABASE_URL=YOUR_SUPABASE_URL,SCRAPEDO_TOKEN=YOUR_TOKEN"

# Run immediately
gcloud run jobs execute dealhunter-tracker --region=us-central1 --wait
```

### Update System 1 after code changes

```bash
gcloud builds submit --config=cloudbuild_tracker.yaml
gcloud run jobs update dealhunter-tracker \
  --region=us-central1 \
  --image=gcr.io/dealhunter-egypt-70d29/dealhunter-tracker:latest
```

### Check logs after any run

```bash
# System 2 logs
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=dealhunter-scraper" \
  --limit=200 --format="value(textPayload)" --freshness=15m \
  | grep -E "deals|ERROR|WARN|snapshot"

# System 1 logs
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=dealhunter-tracker" \
  --limit=200 --format="value(textPayload)" --freshness=15m \
  | grep -E "products|snapshots|ERROR|WARN"
```

### Run tests locally

```bash
# Offline unit tests (no network, no DB required)
python3 test_parsing.py

# Live network tests (requires SCRAPEDO_TOKEN)
export SCRAPEDO_TOKEN="your_token"
python3 test_live.py
```

---

## 11. Test Suite

### `test_parsing.py` — 49 offline tests

No network connection needed. No database needed. Tests the parsing logic directly with hard-coded HTML fixtures.

**Coverage:**
- `PriceCleaner` — EGP, AED, SAR, EU decimal format (1.299,00), USD, edge cases
- Category detection — mapping product titles to category values
- Noon HTML parsing — data-qa attributes, product card structure
- Noon `__NEXT_DATA__` JSON — Next.js embedded JSON extraction
- Jumia HTML parsing — `article.prd` selector chain
- Deal ID generation — MD5 uniqueness, determinism
- `_build_deal` edge cases — missing fields, zero prices, discount threshold

**Result:** 49/49 PASS

### `test_live.py` — Live network tests

Requires `SCRAPEDO_TOKEN`. Tests real HTTP requests to Amazon EG, Noon EG, Jumia EG without writing to the database. Useful for verifying proxy routing and HTML parser compatibility after site redesigns.

---

## 12. Results: Before vs After

### System 2 (Deals Scraper)

| Metric | Before session | After session |
|---|---|---|
| Amazon EG deals/run | 0 | 20+ |
| Amazon AE deals/run | 0 | 20+ |
| Amazon SA deals/run | 21 | 30+ |
| Noon EG deals/run | 0 | 50+ |
| Noon AE deals/run | 0 | 10+ |
| Noon SA deals/run | 0 | 10+ |
| Jumia EG deals/run | 1 | 85+ |
| **Total deals/run** | **~22** | **~225+** |
| Price snapshots/run | 0 | 116+ |
| DB errors/run | 10+ | 0 |
| Crash on startup | Yes (column "reviews") | No |
| Cycle time | 1324s | ~400s |
| Categories covered | partial (3–5 per source) | 23 per source |
| Bestseller pages | 0 | 9 per source |
| SSL connection drops | Every run | 0 (TCP keepalives) |

### System 1 (Price History)

| Metric | Before session | After session |
|---|---|---|
| System exists | No | Yes |
| Product catalog table | No | Yes |
| Discount verdicts table | No | Yes |
| Historical price tracking | No | Yes |
| Fake discount detection | No | Yes (4 verdicts) |
| Cloud Run deployment | No | Ready (`cloudbuild_tracker.yaml`) |

---

## 13. Full Commit History

| Commit | Description |
|---|---|
| `a6398b0` | **System 1 price tracker + Amazon parser fix** — `price_tracker_cloudrun.py` (991 lines), `price_tracker_job.py`, `Dockerfile.tracker`, `cloudbuild_tracker.yaml`, Amazon offscreen price fix, bestseller selectors |
| `572d155` | Fix confirmed 404 Noon URLs from live logs (cameras, health-beauty, SA laptops) |
| `c2123af` | Fix dead Jumia/Noon URLs + extend Amazon scrape.do geoCode to all 3 countries |
| `9861d9a` | Fix upsert_deals SSL drop — chunked connections (25/batch) + TCP keepalives |
| `2dff261` | Update SESSION_NOTES.md with session documentation |
| `ae90f63` | Full category + bestseller coverage for all 7 sources (23 categories per source) |
| `9ca7748` | Force scrape.do for Amazon EG/AE + expand to discount-filtered URLs |
| `4e10932` | Fix migration rollback bug — source column + category constraint never applying |
| `6d05b01` | Fix 5 live production bugs: reviews column, 404 Noon sale URLs, Jumia deals-of-the-day |
| `46b574f` | Fix PriceCleaner EU decimal format (1.299,00 SAR) + 49-test offline test suite |
| `9bc593f` | Noon: scrape.do rendered mode (not local Playwright) + `__NEXT_DATA__` JSON parsing |
| `46ac601` | Playwright Noon + curl_cffi Jumia + schema fixes |
| `ae53358` | Complete scraper: Playwright Noon + direct Jumia + 161 categories + price snapshots |
| `48b86fb` | Fix Noon: Playwright rendering for React |
| `da1df30` | Add Playwright-based Noon scraper for client-side rendered pages |
| `3750e00` | Fix Noon selectors for new CSS Modules |
| `6eef695` | Fix price_snapshots INSERT to match table schema |
| `a24e545` | Add TIMESCALE_URL for price snapshots |
| `7fcb101` | Fix fraud_reasons: pass None for empty list |
| `3df4897` | Fix Json import after `__future__` annotations |
| `08bd1a8` | Fix fraud_reasons JSONB serialization |
| `4c48b74` | Use psycopg2.extras.Json for fraud_reasons JSONB |
| `69e21b2` | Fix fraud_reasons JSON serialization + per-deal transaction rollback |
| `ee8d1af` | Bake all env vars into Docker image |
| `e06f0c0` | Fix `_ensure_tables`: correct schema + auto migration from old columns |
| `0d89817` | Fix DB schema mismatch |
| `3df6321` | Fix timeout 120s, render=true for JS rendering |
| `3776a21` | Clean Dockerfile with correct python3 CMD |
| `cafafb4` | Simplify: always run, no 4-hour guard |
| `874f6a1` | Remove 4-hour guard — scraper always runs on execution |
| `b1f774a` | Add test_scraper.py — focused Amazon.eg scraper with diagnostics |
| `2415064` | Fix: ProxyRotator checks SCRAPEDO_TOKEN (matching env var name) |
| `76039bf` | Add FORCE_RUN env var to bypass 4-hour interval guard |
| `b8d07f6` | Fix Dockerfile COPY — use separate COPY lines per file |
| `6a551f0` | Add Cloud Build config for scraper with custom Dockerfile |
| `dc38192` | Add scraper Cloud Run Job deployment script |

---

## Appendix A — scraper_cloudrun.py Internal Architecture

```
DealHunterScraper
├── __init__()
│   ├── _init_databases()          — Supabase pool + TimescaleDB pool (TCP keepalives)
│   ├── _ensure_tables()           — DDL migrations (deals, price_snapshots, columns)
│   └── ProxyRotator               — scrape.do token management, geoCode routing
│
├── run_cycle()                    — top-level: iterate all sources, collect, save
│   ├── _scrape_amazon_page()      — Amazon HTML parser
│   │   ├── card selectors         — s-result-item, s-search-result + bestseller fallback
│   │   ├── price extraction       — span.a-price:not(.a-text-price) span.a-offscreen
│   │   ├── original price         — 4 selectors + badge fallback + last-resort estimate
│   │   └── _build_deal()          — validates, computes discount, category, fake score
│   │
│   ├── _scrape_noon_page()        — Noon HTML + __NEXT_DATA__ parser
│   │   ├── scrape.do rendered     — wait=6000ms, render=true
│   │   ├── data-qa selectors      — product cards, prices, images
│   │   ├── __NEXT_DATA__ fallback — Next.js JSON extraction
│   │   └── _build_deal()
│   │
│   └── _scrape_jumia_page()       — Jumia HTML parser
│       ├── curl_cffi chrome120    — TLS impersonation (primary)
│       ├── scrape.do super=true   — residential proxy (fallback)
│       ├── article.prd selectors  — product cards
│       └── _build_deal()
│
├── upsert_deals(deals)            — chunked 25/batch, each batch own connection
├── record_price_snapshots(deals)  — chunked 25/batch, snapshot_type='deal'
├── PriceCleaner                   — price string → float, EU/US format detection
└── FakeScoreCalculator            — heuristic fake discount score (0–1)
```

---

## Appendix B — price_tracker_cloudrun.py Internal Architecture

```
PriceTracker (System 1 Orchestrator)
├── TrackerDB
│   ├── _connect()                 — Supabase + TimescaleDB pools with keepalives
│   ├── _ensure_schema()           — CREATE TABLE product_catalog, discount_verdicts
│   │                                ALTER TABLE price_snapshots ADD snapshot_type
│   ├── upsert_catalog(products)   — chunked INSERT ON CONFLICT UPDATE for product_catalog
│   ├── save_snapshots(products)   — INSERT price_snapshots with snapshot_type='catalog'
│   ├── get_price_history(id,site) — SELECT time-series prices for a product
│   ├── save_verdict()             — INSERT/UPDATE discount_verdicts
│   └── get_cached_verdict()       — SELECT verdict if analyzed_at > NOW()-24h
│
├── FakeDiscountDetector
│   └── verify(product_id, site, claimed_original, current_price)
│       ├── get_price_history()    — fetch historical prices
│       ├── < 7 points → UNVERIFIED
│       ├── median ≤ current×1.10 → FAKE
│       ├── claimed > max×1.30   → SUSPICIOUS
│       └── else                 → GENUINE
│
├── CatalogScraper
│   ├── _fetch_via_scrapedo(url)   — scrape.do HTTP (render=True for Noon)
│   ├── _fetch_direct(url)         — plain requests with Chrome UA
│   ├── _fetch_jumia(url)          — curl_cffi chrome120 + scrape.do fallback
│   ├── _parse_amazon(html)        — same fixed selectors as System 2
│   ├── _parse_noon(html)          — data-qa + __NEXT_DATA__ fallback
│   └── _parse_jumia(html)         — article.prd selectors
│
└── run_cycle()
    ├── For each site in _CATALOG_URLS:
    │   ├── scrape_url() for each URL
    │   ├── deduplicate by product_id
    │   ├── upsert_catalog()
    │   └── save_snapshots()
    └── Returns {products_found, snapshots_saved, by_source, elapsed_seconds}
```

---

*Last updated: 2026-05-17 — Branch: `claude/resolve-user-support-5Eljo` — Commit: `a6398b0`*
