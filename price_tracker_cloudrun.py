#!/usr/bin/env python3
"""
DealHunter — System 1: Price History Collector
===============================================
Standalone scraper that crawls ALL products across all 7 sources and all
categories WITHOUT any discount filter. Saves a price snapshot for every
product every run. Builds the historical price database that System 2 uses
to verify whether a claimed discount is genuine or fake.

Runs as its own independent Cloud Run Job (dealhunter-tracker).
Does NOT depend on or call scraper_cloudrun.py (System 2).
System 2 queries this system's tables to verify discounts.

Tables owned by this system:
  product_catalog       — every product ever seen (one row per product)
  price_snapshots       — time-series prices (shared with System 2,
                          snapshot_type='catalog' here vs 'deal' in S2)
  discount_verdicts     — cached fake/genuine verdicts keyed by product+site

Run independently:
  python3 price_tracker_job.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
import threading
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import psycopg2
import psycopg2.pool
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────── Config ──────────────────────────────────────

DATABASE_URL   = os.environ.get("DATABASE_URL", "")
TIMESCALE_URL  = os.environ.get("TIMESCALE_URL", DATABASE_URL)
SCRAPEDO_TOKEN = (
    os.environ.get("SCRAPEDO_TOKEN")
    or os.environ.get("SCRAPE_DO_TOKEN", "")
)

REQUEST_TIMEOUT  = int(os.environ.get("REQUEST_TIMEOUT", "60"))
MIN_PRICE        = float(os.environ.get("TRACKER_MIN_PRICE", "10"))
MAX_PAGES_PER_CAT = int(os.environ.get("TRACKER_MAX_PAGES", "2"))

# ─────────────────────── Category URL Catalogue ──────────────────────────────
# NO discount filters here. These are plain category browse pages.
# System 1 collects ALL products at whatever price they currently have.

_CATALOG_URLS: Dict[str, List[str]] = {
    # ── Amazon Egypt ─────────────────────────────────────────────────────────
    "amazon_eg": [
        "https://www.amazon.eg/s?k=smartphones&language=en_AE",
        "https://www.amazon.eg/s?k=laptops&language=en_AE",
        "https://www.amazon.eg/s?k=headphones&language=en_AE",
        "https://www.amazon.eg/s?k=television&language=en_AE",
        "https://www.amazon.eg/s?k=cameras&language=en_AE",
        "https://www.amazon.eg/s?k=gaming&language=en_AE",
        "https://www.amazon.eg/s?k=electronics&language=en_AE",
        "https://www.amazon.eg/s?k=mens+fashion&language=en_AE",
        "https://www.amazon.eg/s?k=womens+fashion&language=en_AE",
        "https://www.amazon.eg/s?k=shoes&language=en_AE",
        "https://www.amazon.eg/s?k=watches&language=en_AE",
        "https://www.amazon.eg/s?k=bags&language=en_AE",
        "https://www.amazon.eg/s?k=kitchen&language=en_AE",
        "https://www.amazon.eg/s?k=furniture&language=en_AE",
        "https://www.amazon.eg/s?k=beauty&language=en_AE",
        "https://www.amazon.eg/s?k=skincare&language=en_AE",
        "https://www.amazon.eg/s?k=perfume&language=en_AE",
        "https://www.amazon.eg/s?k=sports&language=en_AE",
        "https://www.amazon.eg/s?k=baby&language=en_AE",
        "https://www.amazon.eg/s?k=books&language=en_AE",
        "https://www.amazon.eg/s?k=automotive&language=en_AE",
        "https://www.amazon.eg/s?k=pet+supplies&language=en_AE",
        "https://www.amazon.eg/s?k=grocery&language=en_AE",
    ],
    # ── Amazon UAE ────────────────────────────────────────────────────────────
    "amazon_ae": [
        "https://www.amazon.ae/s?k=smartphones&language=en_AE",
        "https://www.amazon.ae/s?k=laptops&language=en_AE",
        "https://www.amazon.ae/s?k=headphones&language=en_AE",
        "https://www.amazon.ae/s?k=television&language=en_AE",
        "https://www.amazon.ae/s?k=cameras&language=en_AE",
        "https://www.amazon.ae/s?k=gaming&language=en_AE",
        "https://www.amazon.ae/s?k=electronics&language=en_AE",
        "https://www.amazon.ae/s?k=mens+fashion&language=en_AE",
        "https://www.amazon.ae/s?k=womens+fashion&language=en_AE",
        "https://www.amazon.ae/s?k=shoes&language=en_AE",
        "https://www.amazon.ae/s?k=watches&language=en_AE",
        "https://www.amazon.ae/s?k=bags&language=en_AE",
        "https://www.amazon.ae/s?k=kitchen&language=en_AE",
        "https://www.amazon.ae/s?k=furniture&language=en_AE",
        "https://www.amazon.ae/s?k=beauty&language=en_AE",
        "https://www.amazon.ae/s?k=skincare&language=en_AE",
        "https://www.amazon.ae/s?k=perfume&language=en_AE",
        "https://www.amazon.ae/s?k=sports&language=en_AE",
        "https://www.amazon.ae/s?k=baby&language=en_AE",
        "https://www.amazon.ae/s?k=books&language=en_AE",
        "https://www.amazon.ae/s?k=automotive&language=en_AE",
        "https://www.amazon.ae/s?k=pet+supplies&language=en_AE",
        "https://www.amazon.ae/s?k=grocery&language=en_AE",
    ],
    # ── Amazon Saudi Arabia ───────────────────────────────────────────────────
    "amazon_sa": [
        "https://www.amazon.sa/s?k=smartphones&language=en_AE",
        "https://www.amazon.sa/s?k=laptops&language=en_AE",
        "https://www.amazon.sa/s?k=headphones&language=en_AE",
        "https://www.amazon.sa/s?k=television&language=en_AE",
        "https://www.amazon.sa/s?k=cameras&language=en_AE",
        "https://www.amazon.sa/s?k=gaming&language=en_AE",
        "https://www.amazon.sa/s?k=electronics&language=en_AE",
        "https://www.amazon.sa/s?k=mens+fashion&language=en_AE",
        "https://www.amazon.sa/s?k=womens+fashion&language=en_AE",
        "https://www.amazon.sa/s?k=shoes&language=en_AE",
        "https://www.amazon.sa/s?k=watches&language=en_AE",
        "https://www.amazon.sa/s?k=bags&language=en_AE",
        "https://www.amazon.sa/s?k=kitchen&language=en_AE",
        "https://www.amazon.sa/s?k=furniture&language=en_AE",
        "https://www.amazon.sa/s?k=beauty&language=en_AE",
        "https://www.amazon.sa/s?k=skincare&language=en_AE",
        "https://www.amazon.sa/s?k=perfume&language=en_AE",
        "https://www.amazon.sa/s?k=sports&language=en_AE",
        "https://www.amazon.sa/s?k=baby&language=en_AE",
        "https://www.amazon.sa/s?k=books&language=en_AE",
        "https://www.amazon.sa/s?k=automotive&language=en_AE",
        "https://www.amazon.sa/s?k=pet+supplies&language=en_AE",
        "https://www.amazon.sa/s?k=grocery&language=en_AE",
    ],
    # ── Noon Egypt ────────────────────────────────────────────────────────────
    "noon_eg": [
        "https://www.noon.com/egypt-en/electronics-and-mobiles/",
        "https://www.noon.com/egypt-en/electronics-and-mobiles/mobiles-and-tablets/",
        "https://www.noon.com/egypt-en/laptops-and-computers/",
        "https://www.noon.com/egypt-en/tv-and-audio/tvs/",
        "https://www.noon.com/egypt-en/electronics-and-mobiles/audio/",
        "https://www.noon.com/egypt-en/electronics-and-mobiles/cameras/",
        "https://www.noon.com/egypt-en/gaming/",
        "https://www.noon.com/egypt-en/fashion/womens-clothing/",
        "https://www.noon.com/egypt-en/fashion/mens-clothing/",
        "https://www.noon.com/egypt-en/fashion/womens-shoes/",
        "https://www.noon.com/egypt-en/fashion/mens-shoes/",
        "https://www.noon.com/egypt-en/fashion/watches/",
        "https://www.noon.com/egypt-en/fashion/bags-and-luggage/",
        "https://www.noon.com/egypt-en/home-and-kitchen/",
        "https://www.noon.com/egypt-en/home-and-kitchen/furniture/",
        "https://www.noon.com/egypt-en/health-and-beauty/fragrance/",
        "https://www.noon.com/egypt-en/health-and-beauty/skincare/",
        "https://www.noon.com/egypt-en/sports-and-outdoors/",
        "https://www.noon.com/egypt-en/baby-products/",
        "https://www.noon.com/egypt-en/automotive/",
        "https://www.noon.com/egypt-en/pet-supplies/",
    ],
    # ── Noon UAE ──────────────────────────────────────────────────────────────
    "noon_ae": [
        "https://www.noon.com/uae-en/electronics-and-mobiles/",
        "https://www.noon.com/uae-en/electronics-and-mobiles/mobiles-and-tablets/",
        "https://www.noon.com/uae-en/laptops-and-computers/",
        "https://www.noon.com/uae-en/tv-and-audio/tvs/",
        "https://www.noon.com/uae-en/electronics-and-mobiles/audio/",
        "https://www.noon.com/uae-en/electronics-and-mobiles/cameras/",
        "https://www.noon.com/uae-en/gaming/",
        "https://www.noon.com/uae-en/fashion/womens-clothing/",
        "https://www.noon.com/uae-en/fashion/mens-clothing/",
        "https://www.noon.com/uae-en/fashion/womens-shoes/",
        "https://www.noon.com/uae-en/fashion/mens-shoes/",
        "https://www.noon.com/uae-en/fashion/watches/",
        "https://www.noon.com/uae-en/fashion/bags-and-luggage/",
        "https://www.noon.com/uae-en/home-and-kitchen/",
        "https://www.noon.com/uae-en/home-and-kitchen/furniture/",
        "https://www.noon.com/uae-en/health-and-beauty/fragrance/",
        "https://www.noon.com/uae-en/health-and-beauty/skincare/",
        "https://www.noon.com/uae-en/sports-and-outdoors/",
        "https://www.noon.com/uae-en/baby-products/",
        "https://www.noon.com/uae-en/automotive/",
        "https://www.noon.com/uae-en/pet-supplies/",
    ],
    # ── Noon Saudi Arabia ─────────────────────────────────────────────────────
    "noon_sa": [
        "https://www.noon.com/saudi-en/electronics-and-mobiles/",
        "https://www.noon.com/saudi-en/electronics-and-mobiles/mobiles-and-tablets/",
        "https://www.noon.com/saudi-en/laptops-and-computers/",
        "https://www.noon.com/saudi-en/tv-and-audio/tvs/",
        "https://www.noon.com/saudi-en/electronics-and-mobiles/audio/",
        "https://www.noon.com/saudi-en/electronics-and-mobiles/cameras/",
        "https://www.noon.com/saudi-en/gaming/",
        "https://www.noon.com/saudi-en/fashion/womens-clothing/",
        "https://www.noon.com/saudi-en/fashion/mens-clothing/",
        "https://www.noon.com/saudi-en/fashion/womens-shoes/",
        "https://www.noon.com/saudi-en/fashion/mens-shoes/",
        "https://www.noon.com/saudi-en/fashion/watches/",
        "https://www.noon.com/saudi-en/fashion/bags-and-luggage/",
        "https://www.noon.com/saudi-en/home-and-kitchen/",
        "https://www.noon.com/saudi-en/home-and-kitchen/furniture/",
        "https://www.noon.com/saudi-en/health-and-beauty/fragrance/",
        "https://www.noon.com/saudi-en/health-and-beauty/skincare/",
        "https://www.noon.com/saudi-en/sports-and-outdoors/",
        "https://www.noon.com/saudi-en/baby-products/",
        "https://www.noon.com/saudi-en/automotive/",
        "https://www.noon.com/saudi-en/pet-supplies/",
    ],
    # ── Jumia Egypt ───────────────────────────────────────────────────────────
    "jumia_eg": [
        "https://www.jumia.com.eg/phones-tablets/",
        "https://www.jumia.com.eg/laptops/",
        "https://www.jumia.com.eg/televisions/",
        "https://www.jumia.com.eg/headphones/",
        "https://www.jumia.com.eg/cameras/",
        "https://www.jumia.com.eg/video-games/",
        "https://www.jumia.com.eg/womens-clothing/",
        "https://www.jumia.com.eg/men-clothing/",
        "https://www.jumia.com.eg/womens-shoes/",
        "https://www.jumia.com.eg/mens-shoes/",
        "https://www.jumia.com.eg/watches/",
        "https://www.jumia.com.eg/home-office-furniture/",
        "https://www.jumia.com.eg/small-appliances/",
        "https://www.jumia.com.eg/home-living/",
        "https://www.jumia.com.eg/health-beauty/",
        "https://www.jumia.com.eg/sporting-goods/",
        "https://www.jumia.com.eg/baby-products/",
        "https://www.jumia.com.eg/books/",
        "https://www.jumia.com.eg/automotive/",
        "https://www.jumia.com.eg/pet-supplies/",
        "https://www.jumia.com.eg/groceries/",
    ],
}

# Currency map by site
_CURRENCY = {
    "amazon_eg": "EGP", "noon_eg": "EGP", "jumia_eg": "EGP",
    "amazon_ae": "AED", "noon_ae": "AED",
    "amazon_sa": "SAR", "noon_sa": "SAR",
}

# ──────────────────────────────── Logging ────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("price_tracker")


# ──────────────────────────── Helpers ────────────────────────────────────────

def _make_product_id(site: str, url: str) -> str:
    key = f"{site}::{url.split('?')[0].rstrip('/')}"
    return hashlib.md5(key.encode()).hexdigest()


def _clean_price(text: str) -> float:
    if not text:
        return 0.0
    m = re.search(r"[\d.,]+", str(text))
    if not m:
        return 0.0
    raw = m.group(0)
    if "," in raw and "." in raw:
        if raw.index(",") < raw.index("."):
            raw = raw.replace(",", "")
        else:
            raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        parts = raw.split(",")
        raw = raw.replace(",", ".") if len(parts[-1]) <= 2 else raw.replace(",", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return 0.0


def _detect_category(url: str) -> str:
    url_l = url.lower()
    if any(x in url_l for x in ["phone", "mobile", "tablet", "smartphone"]):
        return "electronics"
    if any(x in url_l for x in ["laptop", "computer", "gaming", "tv", "audio", "camera", "electronic"]):
        return "electronics"
    if any(x in url_l for x in ["clothing", "fashion", "shoes", "bags", "watch", "luggage"]):
        return "fashion"
    if any(x in url_l for x in ["home", "kitchen", "furniture", "appliance", "living"]):
        return "home"
    if any(x in url_l for x in ["beauty", "skincare", "fragrance", "health"]):
        return "beauty"
    if any(x in url_l for x in ["sport", "outdoor", "fitness"]):
        return "sports"
    if any(x in url_l for x in ["baby", "kid", "child"]):
        return "baby"
    if any(x in url_l for x in ["book"]):
        return "books"
    if any(x in url_l for x in ["auto", "car"]):
        return "automotive"
    if any(x in url_l for x in ["pet"]):
        return "pets"
    if any(x in url_l for x in ["grocer", "food", "beverage"]):
        return "food"
    return "other"


# ─────────────────────────── Database Layer ──────────────────────────────────

class TrackerDB:
    """Manages DB connections and schema for System 1."""

    def __init__(self):
        self.db_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self.ts_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self._connect()
        self._ensure_schema()

    def _connect(self):
        keepalive = {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
        if DATABASE_URL:
            try:
                self.db_pool = psycopg2.pool.ThreadedConnectionPool(
                    1, 3, dsn=DATABASE_URL, **keepalive
                )
                logger.info("[OK] Supabase pool connected")
            except Exception as e:
                logger.error(f"[ERROR] Supabase connect failed: {e}")

        ts_url = TIMESCALE_URL or DATABASE_URL
        if ts_url:
            try:
                self.ts_pool = psycopg2.pool.ThreadedConnectionPool(
                    1, 3, dsn=ts_url, **keepalive
                )
                logger.info("[OK] TimescaleDB pool connected")
            except Exception as e:
                logger.error(f"[ERROR] TimescaleDB connect failed: {e}")

    def _ensure_schema(self):
        if not self.db_pool:
            return
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                # product_catalog table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS product_catalog (
                        product_id  TEXT PRIMARY KEY,
                        site        VARCHAR(32) NOT NULL,
                        category    VARCHAR(32),
                        title       TEXT,
                        product_url TEXT,
                        image_url   TEXT,
                        currency    VARCHAR(8) DEFAULT 'EGP',
                        last_price  DECIMAL(12,2),
                        first_seen_at TIMESTAMPTZ DEFAULT NOW(),
                        last_seen_at  TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                conn.commit()

                # discount_verdicts table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS discount_verdicts (
                        product_id       TEXT NOT NULL,
                        site             VARCHAR(32) NOT NULL,
                        claimed_original DECIMAL(12,2),
                        current_price    DECIMAL(12,2),
                        verdict          VARCHAR(16) DEFAULT 'UNVERIFIED',
                        confidence       DECIMAL(5,2) DEFAULT 0,
                        reason           TEXT,
                        analyzed_at      TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY (product_id, site)
                    )
                """)
                conn.commit()

            logger.info("[OK] Tracker schema ensured")
        except Exception as e:
            logger.error(f"[ERROR] Schema init failed: {e}")
            conn.rollback()
        finally:
            self.db_pool.putconn(conn)

        # Add snapshot_type column to price_snapshots if missing
        ts_conn = (self.ts_pool or self.db_pool)
        if ts_conn:
            conn2 = ts_conn.getconn()
            try:
                with conn2.cursor() as cur:
                    cur.execute(
                        "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS "
                        "snapshot_type VARCHAR(16) DEFAULT 'deal'"
                    )
                    conn2.commit()
            except Exception:
                conn2.rollback()
            finally:
                ts_conn.putconn(conn2)

    def upsert_catalog(self, products: List[dict]):
        """Insert/update product_catalog rows in chunks."""
        if not products or not self.db_pool:
            return
        sql = """
            INSERT INTO product_catalog
                (product_id, site, category, title, product_url, image_url,
                 currency, last_price, last_seen_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (product_id) DO UPDATE SET
                last_price   = EXCLUDED.last_price,
                last_seen_at = NOW(),
                title        = COALESCE(EXCLUDED.title, product_catalog.title),
                image_url    = COALESCE(EXCLUDED.image_url, product_catalog.image_url)
        """
        chunk_size = 50
        for i in range(0, len(products), chunk_size):
            chunk = products[i: i + chunk_size]
            conn = self.db_pool.getconn()
            try:
                with conn.cursor() as cur:
                    for p in chunk:
                        cur.execute(sql, (
                            p["product_id"], p["site"], p["category"],
                            p["title"][:500], p["product_url"][:2000],
                            (p.get("image_url") or "")[:2000],
                            p["currency"], p["price"],
                        ))
                conn.commit()
            except Exception as e:
                logger.warning(f"[WARN] catalog upsert chunk {i}: {e}")
                conn.rollback()
            finally:
                self.db_pool.putconn(conn)

    def save_snapshots(self, products: List[dict]) -> int:
        """Write price snapshots with snapshot_type='catalog'."""
        if not products:
            return 0
        pool = self.ts_pool or self.db_pool
        if not pool:
            return 0
        sql = """
            INSERT INTO price_snapshots
                (deal_id, product_id, site, source, price, currency, snapshot_type)
            VALUES (%s, %s, %s, %s, %s, %s, 'catalog')
            ON CONFLICT DO NOTHING
        """
        count = 0
        chunk_size = 50
        for i in range(0, len(products), chunk_size):
            chunk = products[i: i + chunk_size]
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    for p in chunk:
                        cur.execute(sql, (
                            p["product_id"], p["product_id"],
                            p["site"], p["site"],
                            p["price"], p["currency"],
                        ))
                        count += 1
                conn.commit()
            except Exception as e:
                logger.warning(f"[WARN] snapshot chunk {i}: {e}")
                conn.rollback()
            finally:
                pool.putconn(conn)
        return count

    def get_price_history(
        self, product_id: str, site: str, days: int = 90
    ) -> List[Tuple[datetime, float]]:
        """Return (timestamp, price) pairs for a product over the last N days."""
        pool = self.ts_pool or self.db_pool
        if not pool:
            return []
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT timestamp, price
                    FROM price_snapshots
                    WHERE product_id = %s AND site = %s
                      AND timestamp > NOW() - INTERVAL '%s days'
                    ORDER BY timestamp ASC
                """, (product_id, site, days))
                return [(row[0], float(row[1])) for row in cur.fetchall()]
        except Exception:
            return []
        finally:
            pool.putconn(conn)

    def save_verdict(self, product_id: str, site: str,
                     claimed_original: float, current_price: float,
                     verdict: str, confidence: float, reason: str):
        if not self.db_pool:
            return
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO discount_verdicts
                        (product_id, site, claimed_original, current_price,
                         verdict, confidence, reason, analyzed_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
                    ON CONFLICT (product_id, site) DO UPDATE SET
                        claimed_original = EXCLUDED.claimed_original,
                        current_price    = EXCLUDED.current_price,
                        verdict          = EXCLUDED.verdict,
                        confidence       = EXCLUDED.confidence,
                        reason           = EXCLUDED.reason,
                        analyzed_at      = NOW()
                """, (product_id, site, claimed_original, current_price,
                      verdict, confidence, reason))
            conn.commit()
        except Exception as e:
            logger.warning(f"[WARN] verdict save failed: {e}")
            conn.rollback()
        finally:
            self.db_pool.putconn(conn)

    def get_cached_verdict(self, product_id: str, site: str) -> Optional[dict]:
        """Return cached verdict if analyzed within last 24 hours."""
        if not self.db_pool:
            return None
        conn = self.db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT verdict, confidence, reason
                    FROM discount_verdicts
                    WHERE product_id = %s AND site = %s
                      AND analyzed_at > NOW() - INTERVAL '24 hours'
                """, (product_id, site))
                row = cur.fetchone()
                if row:
                    return {"verdict": row[0], "confidence": row[1], "reason": row[2]}
                return None
        except Exception:
            return None
        finally:
            self.db_pool.putconn(conn)


# ─────────────────────── Fake Discount Detector ──────────────────────────────

class FakeDiscountDetector:
    """
    Analyses price history from System 1 to determine if a discount is genuine.

    Decision logic:
      UNVERIFIED  — fewer than 7 data points in the last 90 days
      FAKE        — median historical price ≤ claimed_current * 1.10
                    (product never sold anywhere near the claimed "original")
      SUSPICIOUS  — claimed_original > 2× median historical price
                    (original inflated well above what was ever charged)
      GENUINE     — historical prices corroborate the original price
    """

    def __init__(self, db: TrackerDB):
        self.db = db

    def verify(
        self,
        product_id: str,
        site: str,
        claimed_original: float,
        current_price: float,
    ) -> dict:
        # Check cache first
        cached = self.db.get_cached_verdict(product_id, site)
        if cached:
            return cached

        history = self.db.get_price_history(product_id, site, days=90)

        if len(history) < 7:
            result = {
                "verdict": "UNVERIFIED",
                "confidence": 0.0,
                "reason": f"Only {len(history)} price points — need ≥7 days",
            }
            self.db.save_verdict(product_id, site, claimed_original,
                                 current_price, **result)
            return result

        prices = [p for _, p in history]
        median = sorted(prices)[len(prices) // 2]
        avg = sum(prices) / len(prices)
        price_max = max(prices)

        if claimed_original <= 0 or current_price <= 0:
            result = {"verdict": "UNVERIFIED", "confidence": 0.0,
                      "reason": "Invalid prices"}
        elif median <= current_price * 1.10:
            # Product historically sold at or below the current "sale" price
            result = {
                "verdict": "FAKE",
                "confidence": min(95.0, 60 + len(history) * 1.5),
                "reason": (
                    f"Historical median {median:.0f} ≤ current {current_price:.0f}. "
                    f"Product never sold at claimed original {claimed_original:.0f}."
                ),
            }
        elif claimed_original > price_max * 1.30:
            # Claimed original is 30% above the highest price we ever recorded
            result = {
                "verdict": "SUSPICIOUS",
                "confidence": min(80.0, 40 + len(history)),
                "reason": (
                    f"Claimed original {claimed_original:.0f} far exceeds "
                    f"our recorded max {price_max:.0f}."
                ),
            }
        else:
            genuine_pct = ((claimed_original - current_price) / claimed_original) * 100
            result = {
                "verdict": "GENUINE",
                "confidence": min(90.0, 50 + len(history) * 2),
                "reason": (
                    f"History supports {genuine_pct:.0f}% discount. "
                    f"Avg historical price: {avg:.0f}."
                ),
            }

        self.db.save_verdict(product_id, site, claimed_original,
                             current_price, **result)
        return result


# ──────────────────────────── Page Scrapers ──────────────────────────────────

class CatalogScraper:
    """Fetches category pages and extracts product prices."""

    def __init__(self, db: TrackerDB):
        self.db = db
        self._lock = threading.Lock()
        self._last_req: Dict[str, float] = {}

    # ── Rate limiting ─────────────────────────────────────────────────────────

    def _rate_limit(self, domain: str, min_gap: float = 2.0):
        with self._lock:
            last = self._last_req.get(domain, 0)
            wait = min_gap - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
            self._last_req[domain] = time.time()

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _fetch_via_scrapedo(self, url: str, render: bool = False,
                             geo: str = "") -> Optional[str]:
        if not SCRAPEDO_TOKEN:
            return None
        try:
            encoded = urllib.parse.quote(url, safe="")
            sd = (
                f"https://api.scrape.do/?token={SCRAPEDO_TOKEN}"
                f"&url={encoded}"
                f"&render={'true' if render else 'false'}"
                + (f"&wait=5000" if render else "")
                + (f"&geoCode={geo}" if geo else "")
            )
            r = requests.get(sd, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.text
            logger.warning(f"[TRACKER] scrape.do HTTP {r.status_code} for {url}")
        except Exception as e:
            logger.warning(f"[TRACKER] scrape.do error: {e}")
        return None

    def _fetch_direct(self, url: str) -> Optional[str]:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            logger.warning(f"[TRACKER] Direct fetch error: {e}")
        return None

    def _fetch_jumia(self, url: str) -> Optional[str]:
        try:
            from curl_cffi import requests as cf_requests
            r = cf_requests.get(
                url,
                impersonate="chrome120",
                headers={"Accept-Language": "en-US,en;q=0.9"},
                timeout=35,
            )
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        # fallback to scrape.do super
        return self._fetch_via_scrapedo(url, render=False)

    # ── Platform parsers ──────────────────────────────────────────────────────

    def _parse_amazon(self, html: str, site: str, url: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        products = []
        currency = _CURRENCY.get(site, "EGP")

        for card in soup.select("div[data-component-type='s-search-result']"):
            try:
                asin = card.get("data-asin", "")
                if not asin:
                    continue

                title_el = card.select_one("h2 a span") or card.select_one("h2 span")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # Use offscreen price (avoids double-period bug)
                price_el = card.select_one(
                    "span.a-price:not(.a-text-price) span.a-offscreen"
                )
                price_str = price_el.get_text(strip=True) if price_el else ""
                price = _clean_price(price_str)
                if price < MIN_PRICE:
                    continue

                country = site.split("_")[-1]
                product_url = f"https://www.amazon.{country}/dp/{asin}"
                product_id = _make_product_id(site, product_url)

                img = card.select_one("img")
                image_url = img.get("src", "") if img else ""

                products.append({
                    "product_id": product_id,
                    "site": site,
                    "category": _detect_category(url),
                    "title": title,
                    "product_url": product_url,
                    "image_url": image_url,
                    "currency": currency,
                    "price": price,
                })
            except Exception:
                continue
        return products

    def _parse_noon(self, html: str, site: str, url: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        products = []
        currency = _CURRENCY.get(site, "EGP")
        country_code = site.split("_")[-1]
        base = f"https://www.noon.com"

        for box in soup.select('[data-qa="plp-product-box"]'):
            try:
                title_el = box.select_one('[data-qa="plp-product-box-name"]')
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                price_el = box.select_one('[data-qa="plp-product-box-price"]')
                price_str = price_el.get_text(strip=True) if price_el else ""
                price = _clean_price(price_str)
                if price < MIN_PRICE:
                    continue

                link_el = box.select_one("a[href]")
                href = link_el.get("href", "") if link_el else ""
                if not href:
                    continue
                product_url = href if href.startswith("http") else base + href
                product_id = _make_product_id(site, product_url)

                img = box.select_one("img")
                image_url = img.get("src", "") if img else ""

                products.append({
                    "product_id": product_id,
                    "site": site,
                    "category": _detect_category(url),
                    "title": title,
                    "product_url": product_url,
                    "image_url": image_url,
                    "currency": currency,
                    "price": price,
                })
            except Exception:
                continue

        # Try __NEXT_DATA__ if no boxes found
        if not products:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                          html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    items = (
                        data.get("props", {})
                            .get("pageProps", {})
                            .get("catalog", {})
                            .get("items", [])
                        or data.get("props", {})
                            .get("initialState", {})
                            .get("catalog", {})
                            .get("hits", [])
                    )
                    for item in items:
                        title = item.get("name") or item.get("title", "")
                        price = _clean_price(str(item.get("price") or item.get("sale_price", 0)))
                        slug = item.get("sku") or item.get("id", "")
                        if not title or price < MIN_PRICE or not slug:
                            continue
                        locale = "egypt-en" if "eg" in site else ("uae-en" if "ae" in site else "saudi-en")
                        product_url = f"{base}/{locale}/{slug}/"
                        product_id = _make_product_id(site, product_url)
                        products.append({
                            "product_id": product_id,
                            "site": site,
                            "category": _detect_category(url),
                            "title": title,
                            "product_url": product_url,
                            "image_url": item.get("image_key", ""),
                            "currency": currency,
                            "price": price,
                        })
                except Exception:
                    pass
        return products

    def _parse_jumia(self, html: str, site: str, url: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        products = []
        currency = _CURRENCY.get(site, "EGP")
        base = "https://www.jumia.com.eg"

        for card in soup.select("article.prd"):
            try:
                title_el = (card.select_one("h3.name")
                            or card.select_one("div.name"))
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                price_el = card.select_one("div.prc")
                price = _clean_price(price_el.get_text(strip=True)) if price_el else 0.0
                if price < MIN_PRICE:
                    continue

                link_el = card.select_one("a.core")
                href = link_el.get("href", "") if link_el else ""
                product_url = base + href if href.startswith("/") else href
                product_id = _make_product_id(site, product_url)

                img = card.select_one("img")
                image_url = (img.get("data-src") or img.get("src", "")) if img else ""

                products.append({
                    "product_id": product_id,
                    "site": site,
                    "category": _detect_category(url),
                    "title": title,
                    "product_url": product_url,
                    "image_url": image_url,
                    "currency": currency,
                    "price": price,
                })
            except Exception:
                continue
        return products

    # ── Main entry per URL ────────────────────────────────────────────────────

    def scrape_url(self, url: str, site: str) -> List[dict]:
        domain = urllib.parse.urlparse(url).netloc
        self._rate_limit(domain)

        platform = site.split("_")[0]
        country = site.split("_")[-1]
        geo = {"eg": "eg", "ae": "ae", "sa": "sa"}.get(country, "")

        html = None
        if platform == "amazon":
            html = self._fetch_via_scrapedo(url, render=False, geo=geo)
            if not html:
                html = self._fetch_direct(url)
        elif platform == "noon":
            html = self._fetch_via_scrapedo(url, render=True, geo=geo)
        elif platform == "jumia":
            html = self._fetch_jumia(url)

        if not html:
            logger.warning(f"[TRACKER] No HTML for {url}")
            return []

        if platform == "amazon":
            return self._parse_amazon(html, site, url)
        elif platform == "noon":
            return self._parse_noon(html, site, url)
        elif platform == "jumia":
            return self._parse_jumia(html, site, url)
        return []


# ──────────────────────────── Orchestrator ───────────────────────────────────

class PriceTracker:
    """Runs System 1: collects all-product price history."""

    def __init__(self):
        self.db = TrackerDB()
        self.scraper = CatalogScraper(self.db)
        self.detector = FakeDiscountDetector(self.db)

    def run_cycle(self) -> dict:
        start = time.time()
        total_products = 0
        total_snapshots = 0
        by_source: Dict[str, int] = {}

        for site, urls in _CATALOG_URLS.items():
            site_products = []
            logger.info(f"[TRACKER] Starting {site} — {len(urls)} URLs")

            for url in urls:
                try:
                    products = self.scraper.scrape_url(url, site)
                    site_products.extend(products)
                    logger.info(f"[TRACKER] {site} {url}: {len(products)} products")
                except Exception as e:
                    logger.error(f"[ERROR] {site} {url}: {e}")

            # Deduplicate by product_id
            seen: Dict[str, dict] = {}
            for p in site_products:
                seen[p["product_id"]] = p
            unique = list(seen.values())

            # Save to DB
            self.db.upsert_catalog(unique)
            saved = self.db.save_snapshots(unique)

            by_source[site] = len(unique)
            total_products += len(unique)
            total_snapshots += saved
            logger.info(f"[TRACKER] {site}: {len(unique)} unique, {saved} snapshots saved")

        elapsed = round(time.time() - start, 1)
        logger.info(
            f"[TRACKER] === Cycle complete in {elapsed}s: "
            f"{total_products} products, {total_snapshots} snapshots ==="
        )
        return {
            "products_found": total_products,
            "snapshots_saved": total_snapshots,
            "by_source": by_source,
            "elapsed_seconds": elapsed,
        }

    def verify_discount(
        self, product_id: str, site: str,
        claimed_original: float, current_price: float
    ) -> dict:
        """
        Public API — called by System 2 before showing a deal to users.
        Returns {"verdict": "GENUINE"/"FAKE"/"SUSPICIOUS"/"UNVERIFIED", ...}
        """
        return self.detector.verify(product_id, site, claimed_original, current_price)


# ─────────────────────────────── Entry point ─────────────────────────────────

if __name__ == "__main__":
    tracker = PriceTracker()
    result = tracker.run_cycle()
    print(json.dumps(result, indent=2))
