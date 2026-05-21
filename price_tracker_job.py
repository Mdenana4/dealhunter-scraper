#!/usr/bin/env python3
"""
DealHunter Price Tracker — System 1
Runs every 8 hours via Cloud Scheduler.

Two-phase job:
  Phase 1 — Web scraping (System 1): collect prices for ALL products from
             bestseller/category pages across all sources, no discount filter.
             Inserts rows into price_snapshots so we build a true price history.

  Phase 2 — DB analysis: use accumulated price_snapshots to compute
             highest/lowest prices, then re-evaluate fake_score and verdict
             for every active deal.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
import random
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

# Optional scraping imports — tracker Dockerfile includes these
try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPING_AVAILABLE = True
except ImportError:
    _SCRAPING_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
TIMESCALE_URL = os.environ.get("TIMESCALE_URL", DATABASE_URL)
SCRAPEDO_TOKEN = os.environ.get("SCRAPEDO_TOKEN", "")
SCRAPEDO_API = "https://api.scrape.do/"

CURRENCY = {"eg": "EGP", "ae": "AED", "sa": "SAR"}

# ── System 1: Pages to track (all products, no discount filter) ───────────────

_TRACKER_URLS: dict[str, list[str]] = {
    "amazon_eg": [
        "https://www.amazon.eg/-/en/gp/bestsellers",
        "https://www.amazon.eg/-/en/gp/bestsellers/electronics",
        "https://www.amazon.eg/-/en/gp/bestsellers/computers",
        "https://www.amazon.eg/-/en/gp/bestsellers/videogames",
        "https://www.amazon.eg/-/en/gp/bestsellers/fashion",
        "https://www.amazon.eg/-/en/gp/bestsellers/beauty",
        "https://www.amazon.eg/-/en/gp/bestsellers/home",
        "https://www.amazon.eg/-/en/gp/bestsellers/books",
        "https://www.amazon.eg/-/en/gp/bestsellers/toys",
        "https://www.amazon.eg/-/en/gp/bestsellers/automotive",
        "https://www.amazon.eg/-/en/gp/bestsellers/pet-supplies",
        "https://www.amazon.eg/-/en/gp/bestsellers/grocery",
        "https://www.amazon.eg/-/en/gp/bestsellers/sports",
    ],
    "amazon_ae": [
        "https://www.amazon.ae/-/en/gp/bestsellers",
        "https://www.amazon.ae/-/en/gp/bestsellers/electronics",
        "https://www.amazon.ae/-/en/gp/bestsellers/computers",
        "https://www.amazon.ae/-/en/gp/bestsellers/videogames",
        "https://www.amazon.ae/-/en/gp/bestsellers/fashion",
        "https://www.amazon.ae/-/en/gp/bestsellers/beauty",
        "https://www.amazon.ae/-/en/gp/bestsellers/home",
        "https://www.amazon.ae/-/en/gp/bestsellers/books",
        "https://www.amazon.ae/-/en/gp/bestsellers/toys",
        "https://www.amazon.ae/-/en/gp/bestsellers/automotive",
        "https://www.amazon.ae/-/en/gp/bestsellers/pet-supplies",
        "https://www.amazon.ae/-/en/gp/bestsellers/grocery",
        "https://www.amazon.ae/-/en/gp/bestsellers/sports",
    ],
    "amazon_sa": [
        "https://www.amazon.sa/-/en/gp/bestsellers",
        "https://www.amazon.sa/-/en/gp/bestsellers/electronics",
        "https://www.amazon.sa/-/en/gp/bestsellers/computers",
        "https://www.amazon.sa/-/en/gp/bestsellers/videogames",
        "https://www.amazon.sa/-/en/gp/bestsellers/fashion",
        "https://www.amazon.sa/-/en/gp/bestsellers/beauty",
        "https://www.amazon.sa/-/en/gp/bestsellers/home",
        "https://www.amazon.sa/-/en/gp/bestsellers/books",
        "https://www.amazon.sa/-/en/gp/bestsellers/toys",
        "https://www.amazon.sa/-/en/gp/bestsellers/automotive",
        "https://www.amazon.sa/-/en/gp/bestsellers/pet-supplies",
        "https://www.amazon.sa/-/en/gp/bestsellers/grocery",
        "https://www.amazon.sa/-/en/gp/bestsellers/sports",
    ],
    "noon_eg": [
        "https://www.noon.com/egypt-en/electronics-and-mobiles/",
        "https://www.noon.com/egypt-en/mobiles-and-accessories/",
        "https://www.noon.com/egypt-en/laptops-and-computers/",
        "https://www.noon.com/egypt-en/televisions/",
        "https://www.noon.com/egypt-en/cameras-and-accessories/",
        "https://www.noon.com/egypt-en/headphones-and-speakers/",
        "https://www.noon.com/egypt-en/gaming/",
        "https://www.noon.com/egypt-en/men-s-fashion/",
        "https://www.noon.com/egypt-en/women-s-fashion/",
        "https://www.noon.com/egypt-en/watches/",
        "https://www.noon.com/egypt-en/bags-and-luggage/",
        "https://www.noon.com/egypt-en/home-and-kitchen/",
        "https://www.noon.com/egypt-en/beauty-and-fragrance/",
        "https://www.noon.com/egypt-en/skincare/",
        "https://www.noon.com/egypt-en/sports-and-outdoors/",
        "https://www.noon.com/egypt-en/baby-products/",
        "https://www.noon.com/egypt-en/grocery/",
    ],
    "noon_ae": [
        "https://www.noon.com/uae-en/electronics-and-mobiles/",
        "https://www.noon.com/uae-en/mobiles-and-accessories/",
        "https://www.noon.com/uae-en/laptops-and-computers/",
        "https://www.noon.com/uae-en/televisions/",
        "https://www.noon.com/uae-en/cameras-and-accessories/",
        "https://www.noon.com/uae-en/headphones-and-speakers/",
        "https://www.noon.com/uae-en/gaming/",
        "https://www.noon.com/uae-en/men-s-fashion/",
        "https://www.noon.com/uae-en/women-s-fashion/",
        "https://www.noon.com/uae-en/watches/",
        "https://www.noon.com/uae-en/bags-and-luggage/",
        "https://www.noon.com/uae-en/home-and-kitchen/",
        "https://www.noon.com/uae-en/beauty-and-fragrance/",
        "https://www.noon.com/uae-en/skincare/",
        "https://www.noon.com/uae-en/sports-and-outdoors/",
        "https://www.noon.com/uae-en/baby-products/",
        "https://www.noon.com/uae-en/grocery/",
    ],
    "noon_sa": [
        "https://www.noon.com/saudi-en/electronics-and-mobiles/",
        "https://www.noon.com/saudi-en/mobiles-and-accessories/",
        "https://www.noon.com/saudi-en/laptops-and-computers/",
        "https://www.noon.com/saudi-en/televisions/",
        "https://www.noon.com/saudi-en/cameras-and-accessories/",
        "https://www.noon.com/saudi-en/headphones-and-speakers/",
        "https://www.noon.com/saudi-en/gaming/",
        "https://www.noon.com/saudi-en/men-s-fashion/",
        "https://www.noon.com/saudi-en/women-s-fashion/",
        "https://www.noon.com/saudi-en/watches/",
        "https://www.noon.com/saudi-en/bags-and-luggage/",
        "https://www.noon.com/saudi-en/home-and-kitchen/",
        "https://www.noon.com/saudi-en/beauty-and-fragrance/",
        "https://www.noon.com/saudi-en/skincare/",
        "https://www.noon.com/saudi-en/sports-and-outdoors/",
        "https://www.noon.com/saudi-en/baby-products/",
        "https://www.noon.com/saudi-en/grocery/",
    ],
    "jumia_eg": [
        "https://www.jumia.com.eg/electronics/",
        "https://www.jumia.com.eg/phones-tablets/",
        "https://www.jumia.com.eg/tvs-audio-video/",
        "https://www.jumia.com.eg/computing/",
        "https://www.jumia.com.eg/cameras-accessories/",
        "https://www.jumia.com.eg/gaming/",
        "https://www.jumia.com.eg/fashion/",
        "https://www.jumia.com.eg/men-shoes/",
        "https://www.jumia.com.eg/women-shoes/",
        "https://www.jumia.com.eg/watches/",
        "https://www.jumia.com.eg/bags-travel/",
        "https://www.jumia.com.eg/home-office/",
        "https://www.jumia.com.eg/furniture/",
        "https://www.jumia.com.eg/sports-fitness/",
        "https://www.jumia.com.eg/beauty-perfumes-hair/",
        "https://www.jumia.com.eg/baby-products/",
        "https://www.jumia.com.eg/books-movies-music/",
        "https://www.jumia.com.eg/automotive/",
        "https://www.jumia.com.eg/pet-supplies/",
        "https://www.jumia.com.eg/groceries/",
    ],
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────

_session: Optional["requests.Session"] = None


def _get_session() -> "requests.Session":
    global _session
    if _session is None:
        import requests as _req
        _session = _req.Session()
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; DealHunterTracker/1.0)"
        })
    return _session


def _fetch(url: str, render_js: bool = False) -> Optional[str]:
    sess = _get_session()
    try:
        if SCRAPEDO_TOKEN:
            params: dict = {"token": SCRAPEDO_TOKEN, "url": url}
            if render_js:
                params["render"] = "true"
                params["gotoWaitUntil"] = "domcontentloaded"
            resp = sess.get(SCRAPEDO_API, params=params, timeout=90)
        else:
            resp = sess.get(url, timeout=30)
        if resp.status_code == 200:
            return resp.text
        logger.warning(f"  HTTP {resp.status_code} for {url}")
    except Exception as exc:
        logger.error(f"  Fetch error {url}: {exc}")
    return None


def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    text = text.strip().replace(",", "").replace("\xa0", "").replace(" ", "")
    m = re.search(r"\d+\.?\d*", text)
    return float(m.group()) if m else None


# ── Parsers ───────────────────────────────────────────────────────────────────

_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
_NOON_SKU_RE = re.compile(r"/p/([A-Z0-9N][A-Z0-9]{5,})/")
_JUMIA_ID_RE = re.compile(r"-(\d+)\.html")


def _parse_amazon(html: str, site: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    country = site.rsplit("_", 1)[-1]
    currency = CURRENCY.get(country, "EGP")
    results = []

    items = (
        soup.select("li.zg-item-immersion")
        or soup.select("div.zg-grid-general-faceout")
        or soup.select("[data-asin]")
    )
    for item in items:
        asin = item.get("data-asin", "")
        if not asin or len(asin) != 10:
            link = item.select_one("a[href*='/dp/']")
            if not link:
                continue
            m = _ASIN_RE.search(link.get("href", ""))
            if not m:
                continue
            asin = m.group(1)

        price_el = (
            item.select_one(".p13n-sc-price")
            or item.select_one(".a-price .a-offscreen")
            or item.select_one(".a-price-whole")
        )
        if not price_el:
            continue
        price = _parse_price(price_el.get_text())
        if not price or price < 1:
            continue

        orig_el = (
            item.select_one(".a-text-strike")
            or item.select_one(".a-price.a-text-price .a-offscreen")
        )
        orig = _parse_price(orig_el.get_text()) if orig_el else price

        disc = round((1 - price / orig) * 100, 1) if orig and orig > price else 0.0
        results.append({
            "deal_id": f"{site}_{asin}",
            "product_id": asin,
            "site": site,
            "price": price,
            "original_price": orig or price,
            "discount_percent": disc,
            "currency": currency,
        })
    return results


def _parse_noon(html: str, site: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    country = site.rsplit("_", 1)[-1]
    currency = CURRENCY.get(country, "EGP")
    results = []

    items = (
        soup.select("[data-qa='product-item']")
        or soup.select("div[class*='productContainer']")
        or soup.select("div[class*='sc-'][class*='product']")
    )
    for item in items:
        link = item.select_one("a[href*='/p/']")
        if not link:
            continue
        m = _NOON_SKU_RE.search(link.get("href", ""))
        if not m:
            continue
        sku = m.group(1)

        price_el = (
            item.select_one("[class*='sellingPrice']")
            or item.select_one("[class*='price']")
            or item.select_one("strong")
        )
        if not price_el:
            continue
        price = _parse_price(price_el.get_text())
        if not price or price < 1:
            continue

        orig_el = (
            item.select_one("[class*='oldPrice']")
            or item.select_one("[class*='wasPrice']")
            or item.select_one("s")
        )
        orig = _parse_price(orig_el.get_text()) if orig_el else price

        disc = round((1 - price / orig) * 100, 1) if orig and orig > price else 0.0
        results.append({
            "deal_id": f"{site}_{sku}",
            "product_id": sku,
            "site": site,
            "price": price,
            "original_price": orig or price,
            "discount_percent": disc,
            "currency": currency,
        })
    return results


def _parse_jumia(html: str, site: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    results = []

    for item in soup.select("article.prd"):
        link = item.select_one("a[href]")
        if not link:
            continue
        m = _JUMIA_ID_RE.search(link.get("href", ""))
        if not m:
            continue
        pid = m.group(1)

        price_el = item.select_one(".prc")
        if not price_el:
            continue
        price = _parse_price(price_el.get_text())
        if not price or price < 1:
            continue

        orig_el = item.select_one(".old")
        orig = _parse_price(orig_el.get_text()) if orig_el else price

        disc = round((1 - price / orig) * 100, 1) if orig and orig > price else 0.0
        results.append({
            "deal_id": f"{site}_{pid}",
            "product_id": pid,
            "site": site,
            "price": price,
            "original_price": orig or price,
            "discount_percent": disc,
            "currency": "EGP",
        })
    return results


# ── Phase 1: Collect ALL prices ───────────────────────────────────────────────

def collect_all_prices(conn: psycopg2.extensions.connection) -> int:
    """
    Scrape bestseller/category pages for ALL sources without discount filter.
    Inserts price snapshots for every product found.
    Returns total snapshots saved.
    """
    if not _SCRAPING_AVAILABLE:
        logger.warning("[WARN] requests/BeautifulSoup not installed — skipping web scraping")
        return 0

    all_snapshots: list[dict] = []
    total_pages = sum(len(v) for v in _TRACKER_URLS.values())
    logger.info(f"[Phase 1] Scraping {total_pages} pages across {len(_TRACKER_URLS)} sources")

    for site, urls in _TRACKER_URLS.items():
        logger.info(f"  {site}: {len(urls)} pages")
        for url in urls:
            try:
                render_js = "noon" in site
                html = _fetch(url, render_js=render_js)
                if not html:
                    continue

                if "amazon" in site:
                    items = _parse_amazon(html, site)
                elif "noon" in site:
                    items = _parse_noon(html, site)
                else:
                    items = _parse_jumia(html, site)

                all_snapshots.extend(items)
                logger.info(f"    {url}: {len(items)} products")
                time.sleep(random.uniform(1.5, 3.5))

            except Exception as exc:
                logger.error(f"    [ERROR] {url}: {exc}")

    if not all_snapshots:
        logger.warning("[Phase 1] No snapshots collected")
        return 0

    now = datetime.now(timezone.utc)
    rows = [
        (s["deal_id"], s["product_id"], s["site"],
         s["price"], s["original_price"], s["discount_percent"],
         s["currency"], now)
        for s in all_snapshots
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO price_snapshots
                (deal_id, product_id, site, price, original_price,
                 discount_percent, currency, timestamp)
            VALUES %s
            """,
            rows,
        )
    conn.commit()
    logger.info(f"[Phase 1] Saved {len(rows)} price snapshots")
    return len(rows)


# ── Phase 2: DB analysis ──────────────────────────────────────────────────────

def get_conn(url: str):
    return psycopg2.connect(url, connect_timeout=15)


def update_price_history(conn) -> int:
    """Populate highest_price_ever and lowest_price_ever from price_snapshots."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE deals d
            SET
                highest_price_ever = subq.max_original,
                lowest_price_ever  = subq.min_price
            FROM (
                SELECT
                    product_id,
                    MAX(original_price) AS max_original,
                    MIN(price)          AS min_price
                FROM price_snapshots
                WHERE product_id IS NOT NULL
                  AND product_id <> ''
                GROUP BY product_id
            ) subq
            WHERE d.product_id = subq.product_id
        """)
        updated = cur.rowcount
        conn.commit()
        logger.info(f"[OK] Updated price history fields for {updated} deals")
        return updated


def re_evaluate_verdicts(conn) -> dict:
    """
    Re-score deals using real price history.

    Fake detection (priority order):
    1. original_price > 1.8x lowest_price_ever → FAKE
    2. original_price > 1.4x lowest_price_ever → SUSPICIOUS
    3. discount >= 85% with no history           → FAKE
    4. discount >= 65% with no history           → SUSPICIOUS
    5. Otherwise                                 → GENUINE
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, product_id, original_price, current_price,
                   discount_percent, highest_price_ever, lowest_price_ever,
                   verdict
            FROM deals
            WHERE is_active = true
        """)
        rows = cur.fetchall()

    fake_count = suspicious_count = genuine_count = skipped = 0
    updates = []

    for row in rows:
        (deal_id, product_id, original_price, current_price,
         discount_pct, highest_ever, lowest_ever, old_verdict) = row

        if not original_price or not current_price:
            skipped += 1
            continue

        fake_score = 0
        fraud_reasons = []
        verdict = "GENUINE"

        if lowest_ever and lowest_ever > 0:
            inflation_ratio = float(original_price) / float(lowest_ever)

            if inflation_ratio > 1.8:
                verdict = "FAKE"
                fake_score = min(95, int((inflation_ratio - 1) * 40))
                fraud_reasons.append(
                    f"Original price ({original_price:.0f}) is {inflation_ratio:.1f}x "
                    f"higher than historical low ({lowest_ever:.0f}) — price artificially inflated"
                )
                fake_count += 1
            elif inflation_ratio > 1.4:
                verdict = "SUSPICIOUS"
                fake_score = min(70, int((inflation_ratio - 1) * 30))
                fraud_reasons.append(
                    f"Original price ({original_price:.0f}) is {inflation_ratio:.1f}x "
                    f"higher than historical low ({lowest_ever:.0f}) — possible inflation"
                )
                suspicious_count += 1
            else:
                verdict = "GENUINE"
                fake_score = max(0, int((inflation_ratio - 1) * 10))
                genuine_count += 1
        else:
            if discount_pct and discount_pct >= 85:
                verdict = "FAKE"
                fake_score = 90
                fraud_reasons.append(
                    f"Discount of {discount_pct}% is statistically implausible"
                )
                fake_count += 1
            elif discount_pct and discount_pct >= 65:
                verdict = "SUSPICIOUS"
                fake_score = 55
                fraud_reasons.append(
                    f"Discount of {discount_pct}% is unusually high — no price history"
                )
                suspicious_count += 1
            else:
                verdict = "GENUINE"
                fake_score = 0
                genuine_count += 1

        confidence = round(0.85 if lowest_ever else 0.35, 2)
        recommendation = (
            "avoid" if verdict == "FAKE"
            else "caution" if verdict == "SUSPICIOUS"
            else "buy"
        )
        updates.append((verdict, fake_score, fraud_reasons, confidence, recommendation, deal_id))

    if updates:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(
                cur,
                """
                UPDATE deals
                SET verdict        = %s,
                    fake_score     = %s,
                    fraud_reasons  = %s,
                    confidence     = %s,
                    recommendation = %s
                WHERE id = %s
                """,
                updates,
                page_size=200,
            )
        conn.commit()

    result = {
        "fake": fake_count,
        "suspicious": suspicious_count,
        "genuine": genuine_count,
        "skipped": skipped,
    }
    logger.info(
        f"[OK] Verdicts: {fake_count} FAKE, {suspicious_count} SUSPICIOUS, "
        f"{genuine_count} GENUINE, {skipped} skipped"
    )
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    logger.info("[START] DealHunter Price Tracker Job (System 1 + DB analysis)")

    if not DATABASE_URL:
        logger.error("[ERROR] DATABASE_URL not set")
        sys.exit(1)

    snap_url = TIMESCALE_URL or DATABASE_URL
    deals_url = DATABASE_URL

    try:
        snap_conn = get_conn(snap_url)
        logger.info("[OK] Connected to price_snapshots database")
    except Exception as e:
        logger.error(f"[ERROR] Cannot connect to snapshots DB: {e}")
        sys.exit(1)

    try:
        deals_conn = get_conn(deals_url) if snap_url != deals_url else snap_conn
    except Exception as e:
        logger.error(f"[ERROR] Cannot connect to deals DB: {e}")
        snap_conn.close()
        sys.exit(1)

    try:
        # Phase 1: collect prices for ALL products (System 1)
        saved = collect_all_prices(snap_conn)
        logger.info(f"[Phase 1 complete] {saved} snapshots collected")

        # Phase 2a: check snapshot count
        with snap_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM price_snapshots")
            count = cur.fetchone()[0]
            logger.info(f"[Phase 2] price_snapshots total: {count} rows")

        if count == 0:
            logger.warning("[WARN] price_snapshots empty — skipping history update")
        else:
            updated = update_price_history(deals_conn)
            logger.info(f"[Phase 2a] Price history updated for {updated} deals")

        # Phase 2b: re-evaluate verdicts
        stats = re_evaluate_verdicts(deals_conn)
        logger.info(f"[Phase 2b] Verdict re-evaluation: {stats}")

    except Exception as e:
        logger.error(f"[ERROR] Tracker job failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        snap_conn.close()
        if snap_url != deals_url:
            deals_conn.close()

    logger.info("[DONE] Price tracker complete")


if __name__ == "__main__":
    main()
