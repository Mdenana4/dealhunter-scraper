# Price Tracking Schema & Data Collection Strategy

## 1. Overview

This document explains every design decision behind the price-history system
built into `price_tracker.py`.  It is aimed at someone who knows the basics of
databases but has not designed a time-series or price-tracking system before.

The goal is to record **every price capture** for every product on Amazon, Noon,
and Jumia across Egypt (EGP), UAE (AED), and Saudi Arabia (SAR), and to answer
queries like:

- "Show me the full price history for this Samsung TV on Amazon Egypt."
- "What changed in price on Noon UAE in the last 24 hours?"
- "Is this Amazon Egypt 'sale' price genuinely lower than it was 3 months ago?"

---

## 2. Why Firestore (NoSQL) Instead of SQL

The project already uses Firebase / Firestore, so the schema is designed for
Firestore rather than a relational database like PostgreSQL.

| Property | Firestore | PostgreSQL + TimescaleDB |
|---|---|---|
| Already integrated | ✓ | Needs new infrastructure |
| Scales automatically | ✓ | Requires manual sharding |
| No migrations needed | ✓ | Requires Alembic / Flyway |
| Time-series queries | Adequate | Excellent (TimescaleDB extension) |
| Joins across tables | Not supported | Full SQL JOINs |

If the project ever outgrows Firestore for price-history, a future migration to
TimescaleDB (PostgreSQL extension) is the natural next step.

---

## 3. Firestore Collection Layout

```
Firestore root
│
├── products/                          ← one document per product-marketplace pair
│   └── {doc_id}/                      ← e.g. "amazon_eg_B08N5WRWNW"
│       │   (all fields listed in §4)
│       └── price_history/             ← subcollection: one doc per scrape
│           └── {auto_id}/             ← e.g. "3kXpQwZ..."
│               (fields listed in §5)
│
├── price_change_events/               ← flat log of every price change (§6)
│   └── {auto_id}/
│
└── price_alerts/                      ← user alert subscriptions (§7)
    └── {auto_id}/
```

### Why two separate places for prices?

`price_history` lives as a **subcollection** under each product.  This is the
authoritative, detailed record.  You can retrieve the full chart data for one
product by reading `products/{doc_id}/price_history`.

`price_change_events` is a **flat top-level collection**.  It only contains
documents where the price actually changed (or a product was seen for the first
time).  Because it is flat, you can ask "what changed on Amazon Egypt in the
last hour?" with a single collection query — no need to scan thousands of
subcollections.

---

## 4. `products` Collection — Fields

| Field | Type | Description |
|---|---|---|
| `product_id` | string | The store's own identifier (Amazon ASIN, Noon SKU, Jumia ID) |
| `marketplace` | string | `"amazon"`, `"noon"`, or `"jumia"` |
| `country` | string | `"eg"`, `"ae"`, or `"sa"` |
| `marketplace_country` | string | Combined key: `"amazon_eg"`, `"noon_ae"`, `"jumia_eg"`, etc. |
| `name` | string | Product title as scraped |
| `brand` | string | Optional brand name |
| `category` | string | Category detected by the scraper |
| `url` | string | Current canonical product URL |
| `image_url` | string | Product thumbnail URL |
| `currency` | string | `"EGP"`, `"AED"`, or `"SAR"` |
| `current_price` | number | Most recently scraped price |
| `original_price` | number | The "was" / crossed-out price shown on the site (may be null) |
| `current_discount_pct` | number | `(original - current) / original × 100` (may be null) |
| `in_stock` | boolean | Whether the product is available right now |
| `first_seen_at` | timestamp | When the product was first added to our database |
| `last_updated_at` | timestamp | When any field was last written |
| `scrape_priority` | string | `"high"`, `"medium"`, or `"low"` — controls re-scrape frequency |
| `total_snapshots` | number | Running counter of how many times this product has been scraped |

### Document ID format

```
{marketplace_country}_{sanitised_product_id}

Examples:
  amazon_eg_B08N5WRWNW
  noon_ae_Z233BFAA
  jumia_eg_MP263HEAB4G6WNAFAMZ
```

This makes every document ID human-readable and stable.  Two scrapes of the
same product always resolve to the same document — so there is never a
duplicate product in the database.

---

## 5. `price_history` Subcollection — Fields

Every time the scraper visits a product page, it appends **one document** here.
This means the subcollection grows by one row per scrape, forming a full
chronological record.

| Field | Type | Description |
|---|---|---|
| `price` | number | The scraped price at this moment |
| `original_price` | number | The "was" price at this moment (may be null) |
| `discount_pct` | number | Discount at this moment (may be null) |
| `currency` | string | Currency code |
| `in_stock` | boolean | Stock status at this moment |
| `timestamp` | timestamp | Exact date and time of this capture (UTC) |
| `change_from` | number | Previous price (null for the very first snapshot) |
| `change_amount` | number | `price − change_from` — negative means the price dropped |
| `change_pct` | number | Percentage change from previous — negative means dropped |

### How chronological order is maintained

Firestore does not auto-order documents.  The `timestamp` field is indexed
(see `firestore-indexes.json`) and all queries pass `.order_by("timestamp",
ASCENDING)`.  This guarantees the chart always shows oldest on the left and
newest on the right regardless of how documents were written.

### Example — what the data looks like

```
timestamp               price    change_from  change_amount  change_pct
2026-04-01 08:00 UTC    2500     null         0              0          ← first ever snapshot
2026-04-01 14:00 UTC    2500     2500         0              0          ← no change
2026-04-02 09:00 UTC    2510     2500        +10            +0.4        ← went UP by 10 EGP
2026-04-07 11:00 UTC    2299     2510       -211            -8.4        ← dropped 211 EGP
2026-04-07 17:00 UTC    2299     2299         0              0          ← no change
```

---

## 6. `price_change_events` Collection — Fields

This is the "fast query" collection.  A document is written here **only when
the price actually changes** (or the product is first seen).  A product scraped
100 times with the same price creates 100 rows in `price_history` but only
**1** row in `price_change_events`.

| Field | Type | Description |
|---|---|---|
| `product_doc_id` | string | ID of the parent product document |
| `product_name` | string | Copy of the product name for easy display |
| `marketplace` | string | `"amazon"`, `"noon"`, `"jumia"` |
| `country` | string | `"eg"`, `"ae"`, `"sa"` |
| `marketplace_country` | string | Combined key |
| `url` | string | Product URL |
| `image_url` | string | Thumbnail |
| `category` | string | Category |
| `old_price` | number | Price before the change (null if first snapshot) |
| `new_price` | number | Price after the change |
| `change_amount` | number | `new − old` (negative = price dropped) |
| `change_pct` | number | Percentage change (negative = dropped) |
| `currency` | string | Currency code |
| `timestamp` | timestamp | When the change was detected |
| `is_new_product` | boolean | True if this was the first-ever scrape |

### Why this collection exists

Suppose you want "show me all price drops in the last 24 hours on Amazon Egypt."
Without this collection you would need to open every product's `price_history`
subcollection and scan through it — that is thousands of reads.
With `price_change_events` you make **one query** with two filters
(`marketplace_country == "amazon_eg"` AND `timestamp >= 24 hours ago`).

---

## 7. `price_alerts` Collection — Fields

| Field | Type | Description |
|---|---|---|
| `user_id` | string | ID of the user who set the alert |
| `product_doc_id` | string | Which product to watch |
| `marketplace_country` | string | Marketplace of the product |
| `product_id` | string | Store's product identifier |
| `target_price` | number | Fire when price drops to ≤ this value (absolute) |
| `alert_threshold_pct` | number | Fire when price drops by ≥ this % (relative) |
| `notification_channels` | array | e.g. `["push", "email"]` |
| `is_active` | boolean | Set to false once the alert has fired, or the user cancels |
| `created_at` | timestamp | When the alert was created |
| `last_alerted_at` | timestamp | Last time a notification was sent (prevents spam) |

Users can set either or both trigger types.  For example:
- `target_price = 1999` → fire when price falls to 1,999 EGP or below.
- `alert_threshold_pct = 10` → fire whenever the price drops by 10% or more at once.

---

## 8. Firestore Composite Indexes

Firestore requires a **composite index** for any query that filters on one
field and orders by a different field.  All required indexes are defined in
`firestore-indexes.json`.

| Collection | Filter field | Order field | Used by |
|---|---|---|---|
| `price_change_events` | `marketplace_country` | `timestamp DESC` | Recent changes per store |
| `price_change_events` | `marketplace` | `timestamp DESC` | Recent changes per platform |
| `price_change_events` | `country` | `timestamp DESC` | Recent changes per country |
| `price_change_events` | *(none)* | `timestamp DESC` | All recent changes |
| `price_history` (group) | `timestamp` | `timestamp ASC` | Chart data per product |
| `products` | `marketplace_country` | `last_updated_at DESC` | Admin product list |
| `products` | `scrape_priority` | `last_updated_at ASC` | Scraper queue |
| `price_alerts` | `product_doc_id` | `is_active` | Find alerts for a product |
| `price_alerts` | `user_id` | `is_active` | List alerts for a user |

Deploy indexes with:
```bash
firebase deploy --only firestore:indexes
```

---

## 9. Data Collection Strategy

### How the scraper calls the tracker

In `scraper.py`, after extracting a product's price from the page, call:

```python
from price_tracker import record_price

record_price(
    marketplace_country = "amazon_eg",       # which store
    product_id          = asin,              # ASIN / SKU / slug
    name                = title,
    url                 = product_url,
    price               = current_price,
    original_price      = original_price,    # the crossed-out "was" price
    in_stock            = True,
    image_url           = image_url,
    category            = category,
)
```

`record_price` handles everything atomically: reading the previous price,
writing the history snapshot, updating the product document, and writing the
change event if needed.  The scraper does not need to manage any of that logic.

### Scrape frequency by priority

| Priority | Re-scrape every | Set when |
|---|---|---|
| `high` | 5 minutes | A user has set a price alert on the product |
| `medium` | 30 minutes | Product has been viewed recently or is trending |
| `low` | 60 minutes | Everything else in the catalog |

The admin dashboard can update `scrape_priority` on any product.  The scraper
reads the priority field and skips products scraped too recently.

### Handling multiple marketplaces and regions

Each `(marketplace, country)` pair is treated as an independent product.
A Samsung TV on Amazon Egypt and the same model on Noon UAE are **two separate
product documents** with two separate price histories.  This is intentional:
prices, currencies, and discount patterns differ by region, so mixing them
would make the history charts confusing.

The `marketplace_country` field is a single indexed string that covers both
dimensions, making filter queries simple:
```
"amazon_eg" — Amazon Egypt (EGP)
"amazon_ae" — Amazon UAE (AED)
"amazon_sa" — Amazon Saudi Arabia (SAR)
"noon_eg"   — Noon Egypt (EGP)
"noon_ae"   — Noon UAE (AED)
"noon_sa"   — Noon Saudi Arabia (SAR)
"jumia_eg"  — Jumia Egypt (EGP)
```

---

## 10. Detecting Fake Discounts (like Kanbkam)

The `price_history` data makes fake discounts visible.  A fake discount looks
like this: the "original price" shown during a sale is higher than the product
ever actually sold for.

Detection logic (already in `server.py` → `detect_fraud_safqa`):

1. **All-time high check** — if `original_price > historical_high × 1.10`,
   the "original" was never real.
2. **Current price vs baseline** — if `current_price ≈ historical_average`,
   there is no real saving.
3. **Math mismatch** — if the claimed discount % does not match
   `(original − current) / original × 100`, the numbers were fabricated.

This is the core feature that differentiates Kanbkam from a plain price
listing site.  The richer the `price_history` subcollection (more snapshots
over a longer period), the more accurate the fake-discount detection becomes.

---

## 11. API Endpoints Reference

All endpoints are implemented in `server.py`.

### Record a price snapshot (internal, called by scraper)
```
POST /api/v1/tracker/record
Body: { marketplace_country, product_id, name, url, price,
        original_price?, currency?, in_stock?, image_url?, category?, brand? }
```

### Full price history chart data
```
GET /api/v1/tracker/history
    ?marketplace_country=amazon_eg
    &product_id=B08N5WRWNW
    &days=90
    &changes_only=false
```

### Product summary with statistics
```
GET /api/v1/tracker/product
    ?marketplace_country=noon_ae
    &product_id=Z233BFAA
    &days=90
```
Response includes: current price, lowest/highest/average over the window,
price trend direction (rising / falling / stable), change count.

### Recent price changes
```
GET /api/v1/tracker/recent-changes
    ?marketplace_country=amazon_eg   ← or marketplace=amazon or country=eg
    &hours=24
    &limit=50
```

### Top price drops
```
GET /api/v1/tracker/top-drops
    ?marketplace_country=noon_sa
    &hours=24
    &min_drop_pct=5
    &limit=20
```

### Create a price alert
```
POST /api/v1/tracker/alert
Body: { user_id, marketplace_country, product_id,
        target_price? OR alert_threshold_pct?,
        notification_channels? }
```

---

## 12. Best Practices Summary

| Practice | Why it matters |
|---|---|
| **One document ID per product-marketplace pair** | Prevents duplicate products and makes upserts cheap |
| **Atomic transactions for record_price** | Guarantees the product document and price_history always stay in sync |
| **Separate `price_change_events` collection** | Makes "what changed recently?" queries O(1) instead of O(products) |
| **Store `change_amount` and `change_pct` on every snapshot** | Avoids recomputing deltas at query time |
| **Timestamp all writes in UTC** | Consistent across Egypt (UTC+2/3), UAE (UTC+4), Saudi Arabia (UTC+3) |
| **Keep `original_price` separate from `price`** | Allows fake-discount detection and real-saving calculation |
| **Index `(marketplace_country, timestamp)` together** | A WHERE + ORDER BY on two fields requires a composite index in Firestore |
| **`scrape_priority` field on product** | Lets the system scrape trending / alerted products more frequently |
| **`is_active` flag on alerts** | Never delete alert documents — deactivate them so history is preserved |
