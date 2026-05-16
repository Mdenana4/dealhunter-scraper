#!/usr/bin/env python3
"""
DealHunter Scraper — Production Cloud Run Job
Scrapes Amazon.eg/ae/sa, Noon.com (eg/ae/sa), and Jumia.com.eg for deals.
Writes to Supabase PostgreSQL (deals) and TimescaleDB (price snapshots).

Author: DealHunter Engineering
"""

from __future__ import annotations
from psycopg2.extras import Json

import hashlib
import json
import logging
import os
import random
import re
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.pool
import requests
from bs4 import BeautifulSoup

# ──────────────────────────── Configuration ────────────────────────────

# Environment-variable kill switches for credit-heavy operations
AMAZON_ENABLED = os.environ.get("AMAZON_ENABLED", "true").lower() == "true"
NOON_ENABLED = os.environ.get("NOON_ENABLED", "true").lower() == "true"
JUMIA_ENABLED = os.environ.get("JUMIA_ENABLED", "true").lower() == "true"
KEYWORD_DISCOVERY_ENABLED = os.environ.get(
    "KEYWORD_DISCOVERY_ENABLED", "false"
).lower() == "true"

# Minimum thresholds
MIN_PRODUCT_PRICE = int(os.environ.get("MIN_PRODUCT_PRICE", "50"))
MAX_DISCOUNT_THRESHOLD = int(os.environ.get("MAX_DISCOUNT_THRESHOLD", "90"))
MIN_DISCOUNT = int(os.environ.get("MIN_DISCOUNT", "40"))

# Timeouts
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "120"))
MIN_REQUEST_INTERVAL = float(os.environ.get("MIN_REQUEST_INTERVAL", "2.0"))

# Database URLs
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    os.environ.get("SUPABASE_DATABASE_URL", ""),
)
TIMESCALE_URL = os.environ.get(
    "TIMESCALE_URL",
    os.environ.get("TIMESCALE_DATABASE_URL", ""),
)

# Deal sources (primary Egypt sources)
_DEAL_SOURCES = {"amazon_eg", "noon_eg", "jumia_eg"}

# URLs to scrape per source
_DEAL_URLS: Dict[str, List[str]] = {
    "amazon_eg": [
        "https://www.amazon.eg/-/en/gp/goldbox",
        "https://www.amazon.eg/s?k=deals",
    ],
    "amazon_ae": [
        "https://www.amazon.ae/-/en/gp/goldbox",
        "https://www.amazon.ae/s?k=deals",
    ],
    "amazon_sa": [
        "https://www.amazon.sa/-/en/gp/goldbox",
        "https://www.amazon.sa/s?k=deals",
    ],
    "noon_eg": [
        "https://www.noon.com/egypt-en/sale-electronics/",
        "https://www.noon.com/egypt-en/sale-fashion/",
        "https://www.noon.com/egypt-en/sale-home/",
        "https://www.noon.com/egypt-en/electronics-and-mobiles/",
    ],
    "noon_ae": [
        "https://www.noon.com/uae-en/sale-electronics/",
        "https://www.noon.com/uae-en/sale-fashion/",
        "https://www.noon.com/uae-en/electronics-and-mobiles/",
    ],
    "noon_sa": [
        "https://www.noon.com/saudi-en/sale-electronics/",
        "https://www.noon.com/saudi-en/sale-fashion/",
        "https://www.noon.com/saudi-en/electronics-and-mobiles/",
    ],
    "jumia_eg": [
        "https://www.jumia.com.eg/deals-of-the-day/",
        "https://www.jumia.com.eg/catalog/?f%5Bn_special_price%5D=1",
        "https://www.jumia.com.eg/catalog/?f%5Bn_special_price%5D=1&page=2",
        "https://www.jumia.com.eg/phones-tablets/?f%5Bn_special_price%5D=1",
        "https://www.jumia.com.eg/laptops/?f%5Bn_special_price%5D=1",
    ],
}

# Grocery URLs
_GROCERY_URLS: Dict[str, List[str]] = {
    "amazon_eg": ["https://www.amazon.eg/s?k=grocery"],
    "noon_eg": ["https://www.noon.com/egypt-en/grocery/"],
    "jumia_eg": ["https://www.jumia.com.eg/groceries/"],
}

# ──────────────────────────── Logging ────────────────────────────


class ColoredFormatter(logging.Formatter):
    """Custom formatter matching DealHunter log format."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        level = record.levelname
        if level == "INFO":
            level_tag = "[OK]"
        elif level == "WARNING":
            level_tag = "[WARN]"
        elif level == "ERROR":
            level_tag = "[ERROR]"
        elif level == "DEBUG":
            level_tag = "[DEBUG]"
        else:
            level_tag = f"[{level}]"
        return f"[{ts}] {level_tag} {record.getMessage()}"


logger = logging.getLogger("dealhunter")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    _ch = logging.StreamHandler(sys.stdout)
    _ch.setFormatter(ColoredFormatter())
    logger.addHandler(_ch)

# ──────────────────────────── Price Utilities ────────────────────────────


class PriceCleaner:
    """Extract and normalize prices from scraped text."""

    # Currency symbols and codes to strip
    CURRENCY_PATTERNS = [
        r"EGP\s*",
        r"AED\s*",
        r"SAR\s*",
        r"JOD\s*",
        r"USD\s*\$?\s*",
        r"\$\s*",
        r"£\s*",
        r"ر\.س\s*",
        r"د\.إ\s*",
        r"ج\.م\s*",
    ]

    @classmethod
    def clean_price(cls, text: Any) -> float:
        """Extract FIRST number from price text.

        Examples:
            'EGP 1,299 (was 1,899)' -> 1299.0
            'AED 450.00' -> 450.0
            '1.299,00 TL' -> 1299.0
            '' -> 0.0
            None -> 0.0
        """
        if text is None:
            return 0.0
        text = str(text).strip()
        if not text:
            return 0.0

        # Remove currency symbols/codes
        for pattern in cls.CURRENCY_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = text.strip()

        # Find the first number group (handles 1,299 and 1.299)
        # Match digits with optional comma/dot thousand separators
        m = re.search(r"[\d,]+(?:\.\d+)?", text)
        if not m:
            return 0.0

        num_str = m.group()
        # Handle European format: 1.299,00 -> 1299.00
        if "," in num_str and "." in num_str:
            # Determine which is the decimal separator (last one)
            last_comma = num_str.rfind(",")
            last_dot = num_str.rfind(".")
            if last_comma > last_dot:
                # comma is decimal separator
                num_str = num_str.replace(".", "").replace(",", ".")
            else:
                # dot is decimal separator
                num_str = num_str.replace(",", "")
        elif "," in num_str:
            # Could be 1,299 (US/UK) or 1299,00 (European)
            # If comma has exactly 2 digits after it, it's decimal
            parts_after_comma = num_str.split(",")[-1]
            if len(parts_after_comma) == 2:
                num_str = num_str.replace(",", ".")
            else:
                num_str = num_str.replace(",", "")
        # else: dot is already decimal separator, keep as is

        try:
            return float(num_str)
        except (ValueError, TypeError):
            return 0.0

    @classmethod
    def calculate_discount(cls, original: float, current: float) -> dict:
        """Calculate discount percentage and savings amount.

        Returns dict with 'percent' and 'savings' keys.
        Discount capped at 99% to prevent division issues.
        """
        if original <= 0 or current <= 0:
            return {"percent": 0, "savings": 0}
        savings = original - current
        if savings <= 0:
            return {"percent": 0, "savings": 0}
        percent = min(round((savings / original) * 100, 1), 99.0)  # Cap at 99%
        return {"percent": percent, "savings": round(savings, 2)}


# ──────────────────────────── Proxy Rotation ────────────────────────────


class ProxyRotator:
    """Rotate between available proxy services with fallback to direct."""

    def __init__(self):
        self.proxies: List[str] = []
        self.current_index = 0
        self._lock = threading.Lock()

        # Scrape.do proxy
        self.scrapedo_token = os.environ.get("SCRAPEDO_TOKEN", os.environ.get("SCRAPE_DO_TOKEN", ""))
        if self.scrapedo_token:
            self.proxies.append("scrapedo")

        # Crawlbase proxy
        self.crawlbase_token = os.environ.get("CRAWLBASE_TOKEN", "")
        if self.crawlbase_token:
            self.proxies.append("crawlbase")

        # ScrapingBee proxy
        self.scrapingbee_token = os.environ.get("SCRAPINGBEE_TOKEN", "")
        if self.scrapingbee_token:
            self.proxies.append("scrapingbee")

        # Direct fetch as fallback — always available
        self.proxies.append("direct")

        logger.info(
            f"[OK] ProxyRotator initialized with {len(self.proxies)} strategies: "
            f"{self.proxies}"
        )

    def get_proxy_url(self, target_url: str) -> str:
        """Return proxied URL based on active proxy strategy."""
        with self._lock:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)

        encoded_url = urllib.parse.quote(target_url, safe="")

        if proxy == "scrapedo":
            return (
                f"http://api.scrape.do/?token={self.scrapedo_token}"
                f"&url={encoded_url}&render=true"
            )
        elif proxy == "crawlbase":
            return (
                f"https://api.crawlbase.com/?token={self.crawlbase_token}"
                f"&url={encoded_url}"
            )
        elif proxy == "scrapingbee":
            return (
                f"https://app.scrapingbee.com/api/v1/?api_key="
                f"{self.scrapingbee_token}&url={encoded_url}&render_js=false"
            )
        else:
            return target_url

    def get_next_proxy(self) -> str:
        """Get next proxy strategy name."""
        with self._lock:
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy


# ──────────────────────────── Category Detection ────────────────────────────

_CATEGORIES: Dict[str, List[str]] = {
    "electronics": [
        "phone",
        "laptop",
        "tv",
        "camera",
        "headphone",
        "tablet",
        "monitor",
        "smartwatch",
        "charger",
        "cable",
        "adapter",
        "keyboard",
        "mouse",
        "speaker",
        "console",
        "iphone",
        "samsung",
        "xiaomi",
        "oppo",
        "huawei",
        "realme",
        "nokia",
        "honor",
        "ipad",
        "macbook",
        "dell",
        "hp",
        "lenovo",
        "asus",
        "msi",
        "smart tv",
        "oled",
        "led tv",
        "4k",
        "power bank",
        "earbuds",
        "airpods",
        "bluetooth",
        "wireless",
        "router",
        "modem",
        "hard drive",
        "ssd",
        "flash",
        "usb",
        "hdmi",
        "electronic",
    ],
    "fashion": [
        "shoe",
        "shirt",
        "dress",
        "watch",
        "bag",
        "jacket",
        "sneaker",
        "t-shirt",
        "jeans",
        "sandal",
        "boot",
        "clothing",
        "apparel",
        "sunglasses",
        "belt",
        "wallet",
        "handbag",
        "backpack",
        "suit",
        "hoodie",
        "sweater",
        "skirt",
        "blouse",
        "pant",
        "short",
        "sock",
        "underwear",
        "lingerie",
        "jewelry",
        "bracelet",
        "necklace",
        "ring",
        "fashion",
    ],
    "home": [
        "furniture",
        "mattress",
        "sofa",
        "table",
        "chair",
        "lamp",
        "curtain",
        "pillow",
        "blanket",
        "vacuum",
        "cooker",
        "refrigerator",
        "fridge",
        "microwave",
        "oven",
        "blender",
        "mixer",
        "toaster",
        "kettle",
        "iron",
        "washing machine",
        "dryer",
        "dishwasher",
        "air conditioner",
        "fan",
        "heater",
        "bathroom",
        "kitchen",
        "bedroom",
        "living room",
        "decor",
        "rug",
        "carpet",
        "shelf",
        "cabinet",
        "wardrobe",
        "desk",
        "home",
        "appliance",
    ],
    "sports": [
        "treadmill",
        "dumbbell",
        "yoga",
        "bicycle",
        "fitness",
        "gym",
        "sports",
        "running",
        "swimming",
        "football",
        "basketball",
        "tennis",
        "badminton",
        "camping",
        "hiking",
        "tent",
        "sleeping bag",
        "fishing",
        "skate",
        "roller",
        "protein",
        "supplement",
        "exercise",
        "workout",
    ],
    "grocery": [
        "food",
        "snack",
        "coffee",
        "tea",
        "oil",
        "rice",
        "water",
        "juice",
        "chocolate",
        "milk",
        "bread",
        "egg",
        "cheese",
        "butter",
        "yogurt",
        "cereal",
        "pasta",
        "noodle",
        "sauce",
        "spice",
        "sugar",
        "salt",
        "flour",
        "can",
        "frozen",
        "fresh",
        "fruit",
        "vegetable",
        "meat",
        "chicken",
        "fish",
        "grocery",
        "beverage",
        "soft drink",
        "energy drink",
    ],
    "beauty": [
        "perfume",
        "fragrance",
        "makeup",
        "lipstick",
        "foundation",
        "mascara",
        "eyeliner",
        "shampoo",
        "conditioner",
        "cream",
        "lotion",
        "serum",
        "sunscreen",
        "skin care",
        "hair care",
        "nail",
        "beauty",
        "cosmetic",
    ],
    "baby": [
        "baby",
        "diaper",
        "stroller",
        "crib",
        "toy",
        "formula",
        "feeding",
        "maternity",
        "pregnant",
        "newborn",
        "infant",
        "nursery",
        "toddler",
    ],
    "automotive": [
        "car",
        "tire",
        "battery",
        "oil",
        "filter",
        "accessory",
        "gps",
        "dashcam",
        "cover",
        "mat",
        "automotive",
        "motorcycle",
        "bike",
        "tool",
    ],
    "books": [
        "book",
        "novel",
        "stationery",
        "pen",
        "notebook",
        "ebook",
        "kindle",
    ],
    "pets": [
        "pet",
        "dog",
        "cat",
        "food",
        "toy",
        "leash",
        "collar",
        "aquarium",
        "bird",
    ],
}


def detect_category(title: str, url: str) -> Optional[str]:
    """Return category from keywords in title/URL, or None."""
    text = f"{title} {url}".lower()
    for category, keywords in _CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return None


# ──────────────────────────── Deal Helpers ────────────────────────────


def make_deal_id(site: str, url: str, price: float) -> str:
    """MD5 of site+url+price — changing price = new deal ID."""
    return hashlib.md5(f"{site}:{url}:{price}".encode()).hexdigest()


def extract_image_url(img_tag: Any, base_url: str = "") -> Optional[str]:
    """Extract image URL from various HTML img tag formats."""
    if img_tag is None:
        return None

    # data-src (lazy loading)
    for attr in ["data-src", "data-original", "data-lazy", "src", "data-image"]:
        val = img_tag.get(attr)
        if val and not val.startswith("data:") and "placeholder" not in val.lower():
            return urllib.parse.urljoin(base_url, val.strip())

    # srcset
    srcset = img_tag.get("srcset")
    if srcset:
        parts = srcset.split(",")
        if parts:
            first = parts[0].strip().split(" ")[0]
            if first and not first.startswith("data:"):
                return urllib.parse.urljoin(base_url, first)

    return None


def resolve_url(href: str, base_url: str) -> str:
    """Resolve relative URL to absolute."""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    return urllib.parse.urljoin(base_url, href)


# ──────────────────────────── Browser Headers ────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
]


def get_headers(referer: str = "") -> dict:
    """Return realistic browser headers."""
    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# ──────────────────────────── DealHunter Scraper ────────────────────────────


class DealHunterScraper:
    """Main scraper orchestrator for DealHunter Egypt."""

    def __init__(self):
        self.price_cleaner = PriceCleaner()
        self.proxy_rotator = ProxyRotator()
        self.db_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self.ts_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self._last_request_time: Dict[str, float] = {}
        self._request_lock = threading.Lock()
        self._init_databases()
        self._ensure_tables()

    # ── Database ──

    def _init_databases(self):
        """Initialize PostgreSQL connection pools."""
        min_conn = 1
        max_conn = 5

        if DATABASE_URL:
            try:
                self.db_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    dsn=DATABASE_URL,
                )
                logger.info("[OK] Supabase connection pool initialized")
            except Exception as e:
                logger.error(f"[ERROR] Failed to connect to Supabase: {e}")
                self.db_pool = None
        else:
            logger.warning("[WARN] DATABASE_URL not set — Supabase writes disabled")

        if TIMESCALE_URL:
            try:
                self.ts_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    dsn=TIMESCALE_URL,
                )
                logger.info("[OK] TimescaleDB connection pool initialized")
            except Exception as e:
                logger.error(f"[ERROR] Failed to connect to TimescaleDB: {e}")
                self.ts_pool = None
        else:
            logger.warning("[WARN] TIMESCALE_URL not set — price snapshots disabled")

    def _ensure_tables(self):
        """Ensure required tables exist with correct schema.
        Handles both fresh deployments (CREATE TABLE) and existing tables
        with old schema (automatic migration via ALTER TABLE + UPDATE).
        """
        # Supabase deals table
        if self.db_pool:
            try:
                conn = self.db_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS deals (
                            id TEXT PRIMARY KEY,
                            product_id TEXT,
                            site VARCHAR(32) NOT NULL,
                            title TEXT NOT NULL,
                            image_url TEXT,
                            product_url TEXT,
                            category VARCHAR(32),
                            original_price DECIMAL(12,2) NOT NULL DEFAULT 0,
                            current_price DECIMAL(12,2) NOT NULL DEFAULT 0,
                            discount_percent DECIMAL(5,1) NOT NULL DEFAULT 0,
                            savings DECIMAL(12,2) NOT NULL DEFAULT 0,
                            currency VARCHAR(8) DEFAULT 'EGP',
                            verdict VARCHAR(32) DEFAULT 'GENUINE',
                            fake_score DECIMAL(5,2) DEFAULT 0,
                            recommendation VARCHAR(32) DEFAULT 'good_deal',
                            confidence DECIMAL(5,2) DEFAULT 0,
                            fraud_reasons JSONB DEFAULT '[]',
                            rating DECIMAL(3,1),
                            review_count INTEGER DEFAULT 0,
                            is_active BOOLEAN DEFAULT TRUE,
                            last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        )
                        """
                    )
                    # MIGRATE: Add columns that don't exist yet
                    migrations = [
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS product_id TEXT",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS product_url TEXT",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS savings DECIMAL(12,2) NOT NULL DEFAULT 0",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS currency VARCHAR(8) DEFAULT 'EGP'",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS verdict VARCHAR(32) DEFAULT 'GENUINE'",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS fake_score DECIMAL(5,2) DEFAULT 0",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS recommendation VARCHAR(32) DEFAULT 'good_deal'",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS confidence DECIMAL(5,2) DEFAULT 0",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS fraud_reasons JSONB DEFAULT '[]'",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
                        "ALTER TABLE deals ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW()",
                    ]
                    for sql in migrations:
                        cur.execute(sql)
                    # MIGRATE: Copy data from old column names
                    #cur.execute("UPDATE deals SET product_url = url WHERE product_url IS NULL AND url IS NOT NULL")
                    cur.execute("UPDATE deals SET savings = discount_amount WHERE savings = 0 AND discount_amount > 0")
                    cur.execute("UPDATE deals SET review_count = reviews WHERE review_count = 0 AND reviews > 0")
                    cur.execute("UPDATE deals SET currency = 'EGP' WHERE currency IS NULL")
                    cur.execute("UPDATE deals SET verdict = 'GENUINE' WHERE verdict IS NULL")
                    # Indexes
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_site ON deals(site)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_discount ON deals(discount_percent DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_deals_category ON deals(category)")
                    conn.commit()
                self.db_pool.putconn(conn)
                logger.info("[OK] Supabase deals table ensured with correct schema")
            except Exception as e:
                logger.error(f"[ERROR] Failed to ensure Supabase tables: {e}")

        # TimescaleDB price snapshots hypertable
        if self.ts_pool:
            try:
                conn = self.ts_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS price_snapshots (
                            deal_id TEXT NOT NULL,
                            product_id TEXT,
                            site VARCHAR(32) NOT NULL,
                            price DECIMAL(12,2) NOT NULL,
                            original_price DECIMAL(12,2),
                            discount_percent DECIMAL(5,1),
                            currency VARCHAR(8) DEFAULT 'EGP',
                            source VARCHAR(32),
                            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    # Add missing columns for existing tables
                    for col_sql in [
                        "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS product_id TEXT",
                        "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS site VARCHAR(32)",
                        "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS original_price DECIMAL(12,2)",
                        "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS discount_percent DECIMAL(5,1)",
                        "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS currency VARCHAR(8) DEFAULT 'EGP'",
                    ]:
                        try:
                            cur.execute(col_sql)
                        except psycopg2.Error:
                            conn.rollback()
                    # Convert to hypertable if TimescaleDB is available
                    try:
                        cur.execute(
                            """
                            SELECT create_hypertable(
                                'price_snapshots', 'timestamp',
                                if_not_exists => TRUE,
                                migrate_data => TRUE
                            )
                            """
                        )
                    except psycopg2.Error:
                        conn.rollback()
                        # Hypertable might already exist or TimescaleDB extension not loaded
                        pass

                    # Price change events table
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS price_change_events (
                            id SERIAL PRIMARY KEY,
                            deal_id TEXT NOT NULL,
                            old_price DECIMAL(12,2) NOT NULL,
                            new_price DECIMAL(12,2) NOT NULL,
                            change_percent DECIMAL(5,1) NOT NULL,
                            source VARCHAR(32) NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    try:
                        cur.execute(
                            """
                            SELECT create_hypertable(
                                'price_change_events', 'timestamp',
                                if_not_exists => TRUE,
                                migrate_data => TRUE
                            )
                            """
                        )
                    except psycopg2.Error:
                        conn.rollback()
                        pass

                    conn.commit()
                self.ts_pool.putconn(conn)
                logger.info("[OK] TimescaleDB tables ensured")
            except Exception as e:
                logger.error(f"[ERROR] Failed to ensure TimescaleDB tables: {e}")

    def _get_db_conn(self, pool: Optional[psycopg2.pool.ThreadedConnectionPool]):
        """Safely get a connection from pool."""
        if pool is None:
            return None
        try:
            return pool.getconn()
        except Exception as e:
            logger.error(f"[ERROR] Failed to get DB connection: {e}")
            return None

    def _put_db_conn(
        self,
        pool: Optional[psycopg2.pool.ThreadedConnectionPool],
        conn,
    ):
        """Safely return a connection to pool."""
        if pool and conn:
            try:
                pool.putconn(conn)
            except Exception as e:
                logger.error(f"[ERROR] Failed to return DB connection: {e}")

    # ── Rate Limiting ──

    def _rate_limit(self, domain: str):
        """Enforce minimum interval between requests to same domain."""
        with self._request_lock:
            last = self._last_request_time.get(domain, 0)
            elapsed = time.time() - last
            if elapsed < MIN_REQUEST_INTERVAL:
                sleep_time = MIN_REQUEST_INTERVAL - elapsed
                time.sleep(sleep_time)
            self._last_request_time[domain] = time.time()

    # ── HTTP Request ──

    def _fetch(
        self,
        url: str,
        headers: Optional[dict] = None,
        proxy: Optional[str] = None,
        timeout: int = REQUEST_TIMEOUT,
        retries: int = 3,
    ) -> Optional[requests.Response]:
        """Fetch URL with proxy rotation, retries, and rate limiting."""
        # Extract domain for rate limiting
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc or "unknown"

        self._rate_limit(domain)

        if headers is None:
            headers = get_headers(referer=f"https://{domain}/")

        # Get proxy URL (may be same as target if using direct)
        fetch_url = self.proxy_rotator.get_proxy_url(url) if proxy is None else url

        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(
                    fetch_url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True,
                )
                if resp.status_code == 200:
                    return resp
                elif resp.status_code in (403, 429, 503):
                    logger.warning(
                        f"[WARN] HTTP {resp.status_code} from {domain}, "
                        f"attempt {attempt}/{retries}"
                    )
                    if attempt < retries:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        # Try next proxy on next attempt
                        fetch_url = self.proxy_rotator.get_proxy_url(url)
                else:
                    logger.warning(
                        f"[WARN] HTTP {resp.status_code} from {domain}"
                    )
                    return None
            except requests.exceptions.Timeout:
                last_exception = "timeout"
                logger.warning(
                    f"[WARN] Request timeout to {domain}, "
                    f"attempt {attempt}/{retries}"
                )
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    fetch_url = self.proxy_rotator.get_proxy_url(url)
            except requests.exceptions.ConnectionError:
                last_exception = "connection"
                logger.warning(
                    f"[WARN] Connection error to {domain}, "
                    f"attempt {attempt}/{retries}"
                )
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    fetch_url = self.proxy_rotator.get_proxy_url(url)
            except Exception as e:
                last_exception = str(e)
                logger.warning(
                    f"[WARN] Request error to {domain}: {e}, "
                    f"attempt {attempt}/{retries}"
                )
                if attempt < retries:
                    time.sleep(2 ** attempt)

        logger.error(
            f"[ERROR] Failed to fetch {url} after {retries} attempts: "
            f"{last_exception}"
        )
        return None

    # ── Deal Builders ──

    def _build_deal(
        self,
        site: str,
        platform: str,
        country: str,
        title: str,
        url: str,
        current_price: float,
        original_price: float,
        image_url: Optional[str] = None,
        rating: Optional[float] = None,
        reviews: int = 0,
        is_grocery: bool = False,
    ) -> Optional[dict]:
        """Build and validate a deal dict. Returns None if invalid."""
        if not title or not url:
            return None

        # Clean prices
        current = self.price_cleaner.clean_price(current_price)
        original = self.price_cleaner.clean_price(original_price)

        # Ensure original >= current for meaningful discount
        if original <= 0 or original < current:
            original = current

        # Skip if below minimum price
        if current < MIN_PRODUCT_PRICE:
            return None

        # Calculate discount
        discount = self.price_cleaner.calculate_discount(original, current)

        # Skip if discount below threshold (unless it's a low-priced item)
        if discount["percent"] < MIN_DISCOUNT and current >= 100:
            return None

        # Cap discount
        if discount["percent"] > MAX_DISCOUNT_THRESHOLD:
            discount["percent"] = MAX_DISCOUNT_THRESHOLD

        category = detect_category(title, url)

        deal = {
            "id": make_deal_id(site, url, current),
            "product_id": "",
            "site": site,
            "title": title.strip()[:500],
            "image_url": (image_url or "")[:2000],
            "product_url": url.strip()[:2000],
            "category": category,
            "original_price": original,
            "current_price": current,
            "discount_percent": discount["percent"],
            "savings": discount["savings"],
            "currency": "EGP",
            "verdict": "GENUINE",
            "fake_score": 0.0,
            "recommendation": "good_deal",
            "confidence": 0.0,
            "fraud_reasons": [],
            "rating": rating,
            "review_count": reviews,
        }
        return deal

    # ═══════════════════════════════════════════════════════════════
    # PLATFORM SCRAPERS
    # ═══════════════════════════════════════════════════════════════

    # ── Amazon Egypt ──

    def scrape_amazon_eg(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Amazon Egypt deals page."""
        if not AMAZON_ENABLED:
            logger.info("[OK] Amazon EG disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("amazon_eg", [])

        for url in urls:
            try:
                deals = self._scrape_amazon_page(url, "amazon_eg", "amazon", "eg", proxy)
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped amazon_eg ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Amazon EG scrape failed for {url}: {e}")

        # Deduplicate by URL
        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)

        logger.info(f"[OK] Amazon EG total: {len(unique_deals)} unique deals")
        return unique_deals

    def _scrape_amazon_page(
        self,
        url: str,
        site: str,
        platform: str,
        country: str,
        proxy: Optional[str] = None,
    ) -> List[dict]:
        """Scrape a single Amazon deals page."""
        resp = self._fetch(url, proxy=proxy)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        deals: List[dict] = []

        # Try multiple selectors for deal cards
        selectors = [
            "div[data-component-type='s-search-result']",
            "div.s-result-item[data-component-type='s-search-result']",
            "div.dealTile",
            "div.a-section.a-spacing-base",
            "div.a-section.dealContainer",
            "div.s-card-container",
            "div.sg-col-inner div.a-section",
        ]

        cards = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                break

        if not cards:
            logger.warning(f"[WARN] No deal cards found on Amazon {country}: {url}")
            return []

        for card in cards:
            try:
                # Title
                title_el = (
                    card.select_one("h2 a span")
                    or card.select_one("h2 span")
                    or card.select_one(".s-size-mini span")
                    or card.select_one("a.a-text-normal span")
                    or card.select_one("[data-cy='title-recipe-title']")
                )
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # URL
                link_el = (
                    card.select_one("h2 a")
                    or card.select_one("a.a-link-normal.a-text-normal")
                    or card.select_one("a[href*='/dp/']")
                    or card.select_one("a.a-link-normal")
                )
                href = link_el.get("href", "") if link_el else ""
                product_url = resolve_url(href, f"https://www.amazon.{country}")
                if not product_url or "/dp/" not in product_url:
                    # Try to extract ASIN and build URL
                    asin = card.get("data-asin") or ""
                    if asin:
                        product_url = (
                            f"https://www.amazon.{country}/dp/{asin}"
                        )
                    else:
                        continue

                # Price - current
                price_whole = card.select_one("span.a-price-whole")
                price_fraction = card.select_one("span.a-price-fraction")
                if price_whole:
                    whole = price_whole.get_text(strip=True).replace(",", "")
                    fraction = (
                        price_fraction.get_text(strip=True)
                        if price_fraction
                        else "00"
                    )
                    current_price_str = f"{whole}.{fraction}"
                else:
                    price_el = card.select_one("span.a-price span.a-offscreen")
                    current_price_str = (
                        price_el.get_text(strip=True) if price_el else ""
                    )

                # Original price (was / list price)
                original_el = (
                    card.select_one("span.a-text-price span.a-offscreen")
                    or card.select_one("span[data-a-color='secondary'] span.a-offscreen")
                    or card.select_one("span.a-price.a-text-price span.a-offscreen")
                )
                original_price_str = (
                    original_el.get_text(strip=True) if original_el else ""
                )

                # If no original price, try to find discount badge
                if not original_price_str:
                    discount_badge = (
                        card.select_one("span.a-badge-text")
                        or card.select_one("span.s-coupon-highlight-color")
                    )
                    if discount_badge:
                        badge_text = discount_badge.get_text(strip=True)
                        # e.g. "-30%"
                        m = re.search(r"(\d+)", badge_text)
                        if m and current_price_str:
                            pct = int(m.group(1))
                            current_f = self.price_cleaner.clean_price(
                                current_price_str
                            )
                            if current_f > 0 and pct > 0:
                                original_f = current_f / (1 - pct / 100)
                                original_price_str = str(round(original_f, 2))

                # Image
                img = card.select_one("img")
                image_url = extract_image_url(img, f"https://www.amazon.{country}")

                # Rating
                rating_el = card.select_one("span.a-icon-alt")
                rating = None
                if rating_el:
                    rating_text = rating_el.get_text(strip=True)
                    m = re.search(r"([\d.]+)", rating_text)
                    if m:
                        rating = float(m.group(1))

                # Reviews count
                reviews_el = card.select_one("span.a-size-base")
                reviews = 0
                if reviews_el:
                    reviews_text = reviews_el.get_text(strip=True).replace(",", "")
                    m = re.search(r"(\d+)", reviews_text)
                    if m:
                        reviews = int(m.group(1))

                deal = self._build_deal(
                    site=site,
                    platform=platform,
                    country=country,
                    title=title,
                    url=product_url,
                    current_price=current_price_str,
                    original_price=original_price_str,
                    image_url=image_url,
                    rating=rating,
                    reviews=reviews,
                )
                if deal:
                    deals.append(deal)

            except Exception as e:
                logger.debug(f"[DEBUG] Error parsing Amazon card: {e}")
                continue

        return deals

    # ── Amazon UAE ──

    def scrape_amazon_ae(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Amazon UAE deals page."""
        if not AMAZON_ENABLED:
            logger.info("[OK] Amazon AE disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("amazon_ae", [])

        for url in urls:
            try:
                deals = self._scrape_amazon_page(url, "amazon_ae", "amazon", "ae", proxy)
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped amazon_ae ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Amazon AE scrape failed for {url}: {e}")

        # Deduplicate
        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)

        logger.info(f"[OK] Amazon AE total: {len(unique_deals)} unique deals")
        return unique_deals

    # ── Amazon Saudi Arabia ──

    def scrape_amazon_sa(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Amazon Saudi Arabia deals page."""
        if not AMAZON_ENABLED:
            logger.info("[OK] Amazon SA disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("amazon_sa", [])

        for url in urls:
            try:
                deals = self._scrape_amazon_page(url, "amazon_sa", "amazon", "sa", proxy)
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped amazon_sa ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Amazon SA scrape failed for {url}: {e}")

        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)

        logger.info(f"[OK] Amazon SA total: {len(unique_deals)} unique deals")
        return unique_deals

    # ── Noon Egypt ──

    def scrape_noon_eg(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Noon Egypt deals.

        Primary: scrape.do rendered (Akamai bypass via their infra).
        Fallback: stealth Playwright (only if scrape.do unavailable).
        """
        if not NOON_ENABLED:
            logger.info("[OK] Noon EG disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("noon_eg", [])

        for url in urls:
            try:
                deals = self._scrape_noon_page(url, "noon_eg", "noon", "eg")
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped noon_eg ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Noon EG scrape failed for {url}: {e}")

        # Deduplicate
        seen = set()
        unique_deals = []
        failed_images = 0
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)
                if not d.get("image_url"):
                    failed_images += 1

        if failed_images > 0:
            logger.warning(
                f"[WARN] Noon image extraction failed for {failed_images} items"
            )

        logger.info(f"[OK] Noon EG total: {len(unique_deals)} unique deals")
        return unique_deals

    def _scrape_noon_page(
        self,
        url: str,
        site: str,
        platform: str,
        country: str,
        proxy: Optional[str] = None,
    ) -> List[dict]:
        """Scrape a single Noon page.

        Noon uses Akamai Bot Management, which blocks Google Cloud Run IPs.
        The winning strategy is to route through scrape.do's rendered mode —
        their infrastructure handles Akamai on our behalf and returns fully
        hydrated React HTML. We then parse data-qa attributes with BeautifulSoup.

        We also try __NEXT_DATA__ JSON (embedded in every Next.js SSR page) as
        a fast path that doesn't require JavaScript rendering at all.
        """
        html: Optional[str] = None

        # ── Strategy 1: scrape.do rendered (Akamai bypass via their infra) ──
        if self.proxy_rotator.scrapedo_token:
            try:
                encoded = urllib.parse.quote(url, safe="")
                # render=true → execute JS  |  wait=6000 → let React hydrate
                sd_url = (
                    f"https://api.scrape.do/?token="
                    f"{self.proxy_rotator.scrapedo_token}"
                    f"&url={encoded}&render=true&wait=6000"
                )
                resp = requests.get(sd_url, timeout=90)
                if resp.status_code == 200:
                    html = resp.text
                    logger.info(f"[NOON] scrape.do rendered OK for {url}")
                else:
                    logger.warning(
                        f"[NOON] scrape.do HTTP {resp.status_code} for {url}"
                    )
            except Exception as e:
                logger.warning(f"[NOON] scrape.do rendered error: {e}")

        # ── Strategy 2: Playwright stealth browser (fallback) ──
        if not html:
            return self._scrape_noon_playwright(url, site, country)

        # ── Parse rendered HTML ──
        soup = BeautifulSoup(html, "lxml")

        # Primary: data-qa product boxes (React-rendered)
        products = soup.select('[data-qa="plp-product-box"]')
        logger.info(
            f"[NOON] {len(products)} product boxes in rendered HTML for {url}"
        )

        if not products:
            # Fallback: try __NEXT_DATA__ JSON (embedded in all Next.js pages)
            return self._parse_noon_next_data(html, site, platform, country)

        deals: List[dict] = []
        for product in products:
            try:
                name_el = product.select_one('[data-qa="plp-product-box-name"]')
                price_el = product.select_one('[data-qa="plp-product-box-price"]')
                old_price_el = product.select_one(
                    '[data-qa="plp-product-box-old-price"]'
                )
                discount_el = product.select_one(
                    '[data-qa="plp-product-box-discount"]'
                )
                link_el = product.select_one("a[href]")
                img_el = product.select_one("img")

                if not name_el or not price_el or not link_el:
                    continue

                name = name_el.get_text(strip=True)
                if not name:
                    continue

                price_text = price_el.get_text(strip=True)
                current_price = self.price_cleaner.clean_price(price_text)
                if current_price < MIN_PRODUCT_PRICE:
                    continue

                original_price = current_price
                if old_price_el:
                    op = self.price_cleaner.clean_price(
                        old_price_el.get_text(strip=True)
                    )
                    if op > current_price:
                        original_price = op

                if discount_el and original_price <= current_price:
                    m = re.search(r"(\d+)", discount_el.get_text(strip=True))
                    if m:
                        pct = int(m.group(1))
                        if 0 < pct < 100:
                            original_price = round(
                                current_price / (1 - pct / 100), 2
                            )

                href = link_el.get("href", "")
                product_url = (
                    f"https://www.noon.com{href}"
                    if href.startswith("/")
                    else href
                )
                if not product_url or "/p/" not in product_url:
                    continue

                image_url = (
                    extract_image_url(img_el, "https://www.noon.com")
                    if img_el
                    else ""
                )

                deal = self._build_deal(
                    site=site,
                    platform=platform,
                    country=country,
                    title=name,
                    url=product_url,
                    current_price=current_price,
                    original_price=original_price,
                    image_url=image_url,
                )
                if deal:
                    deals.append(deal)

            except Exception as e:
                logger.debug(f"[NOON] Card parse error: {e}")
                continue

        return deals

    def _parse_noon_next_data(
        self, html: str, site: str, platform: str, country: str
    ) -> List[dict]:
        """Parse Noon's __NEXT_DATA__ JSON embedded in every Next.js page.

        When the React page is rendered (by scrape.do or direct), Next.js
        embeds all initial state as JSON in <script id="__NEXT_DATA__">.
        This is faster and more reliable than DOM parsing.
        """
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script or not script.string:
            return []

        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            return []

        # Navigate the Next.js props tree — Noon's structure varies by page type
        page_props = data.get("props", {}).get("pageProps", {})

        # Try multiple known paths where Noon hides product data
        hits: List[dict] = []
        for path in [
            ["catalog", "hits"],
            ["initialData", "hits"],
            ["initialData", "data", "products"],
            ["data", "products"],
            ["products"],
        ]:
            obj = page_props
            for key in path:
                obj = obj.get(key, {}) if isinstance(obj, dict) else {}
            if isinstance(obj, list) and obj:
                hits = obj
                break

        if not hits:
            logger.debug(f"[NOON] __NEXT_DATA__ found but no product hits for {site}")
            return []

        logger.info(f"[NOON] __NEXT_DATA__: {len(hits)} products for {site}")
        deals: List[dict] = []

        for hit in hits:
            try:
                title = hit.get("name", "") or hit.get("title", "")
                if not title:
                    continue

                price_obj = hit.get("price", {}) or {}
                current_price = float(
                    price_obj.get("salePrice", 0)
                    or price_obj.get("sellingPrice", 0)
                    or price_obj.get("price", 0)
                    or 0
                )
                original_price = float(
                    price_obj.get("oldPrice", 0)
                    or price_obj.get("originalPrice", 0)
                    or current_price
                )
                if original_price < current_price:
                    original_price = current_price

                sku = hit.get("sku", "") or hit.get("id", "")
                url_path = (
                    hit.get("url", "")
                    or hit.get("purl", "")
                    or hit.get("productUrl", "")
                )
                if url_path:
                    product_url = (
                        f"https://www.noon.com{url_path}"
                        if url_path.startswith("/")
                        else url_path
                    )
                elif sku:
                    product_url = (
                        f"https://www.noon.com/{country}-en/product/{sku}/"
                    )
                else:
                    continue

                image_keys = hit.get("imageKeys", []) or hit.get("images", [])
                image_url = ""
                if image_keys:
                    k = image_keys[0] if isinstance(image_keys[0], str) else ""
                    if k:
                        image_url = (
                            f"https://f.nooncdn.com/p/pnsku/{k}/45/_/1.jpg"
                        )

                deal = self._build_deal(
                    site=site,
                    platform=platform,
                    country=country,
                    title=title,
                    url=product_url,
                    current_price=current_price,
                    original_price=original_price,
                    image_url=image_url,
                )
                if deal:
                    deals.append(deal)
            except Exception as e:
                logger.debug(f"[NOON] __NEXT_DATA__ hit parse error: {e}")
                continue

        return deals

    def _scrape_noon_playwright(
        self, url: str, site: str, country: str
    ) -> List[dict]:
        """Scrape Noon using headless Chromium with anti-detection patches.

        Noon runs on Next.js with Akamai Bot Management. Static HTTP requests
        return empty React containers. We need a real (stealth) browser that
        patches navigator.webdriver and other bot-detection signals so Akamai
        lets the page hydrate and serve product data.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            logger.error("[NOON] playwright not installed — cannot scrape Noon")
            return []

        deals: List[dict] = []
        _UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--window-size=1920,1080",
                        "--disable-extensions",
                        "--disable-plugins",
                    ],
                )
                context = browser.new_context(
                    user_agent=_UA,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="Africa/Cairo",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;"
                            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                        ),
                        "Sec-CH-UA": (
                            '"Not_A Brand";v="8", "Chromium";v="120", '
                            '"Google Chrome";v="120"'
                        ),
                        "Sec-CH-UA-Mobile": "?0",
                        "Sec-CH-UA-Platform": '"Windows"',
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                    },
                )
                page = context.new_page()

                # Patch bot-detection properties that Akamai inspects
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [{ name: 'Chrome PDF Plugin' },
                                    { name: 'Chrome PDF Viewer' },
                                    { name: 'Native Client' }]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en', 'ar']
                    });
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) =>
                        parameters.name === 'notifications'
                            ? Promise.resolve({ state: Notification.permission })
                            : originalQuery(parameters);
                """)

                # Block images, fonts and trackers — speed up page load
                page.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf,ico}",
                    lambda r: r.abort(),
                )
                page.route(
                    "**/*(analytics|gtm|pixel|facebook|doubleclick|googlesyndication)*",
                    lambda r: r.abort(),
                )

                logger.info(f"[NOON] Navigating to {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=50000)
                except Exception as nav_err:
                    logger.warning(f"[NOON] Navigation error for {url}: {nav_err}")
                    browser.close()
                    return []

                # Wait for React hydration and product grid
                try:
                    page.wait_for_selector(
                        '[data-qa="plp-product-box"]', timeout=25000
                    )
                except PWTimeout:
                    # Log what actually loaded to help debug
                    snippet = page.content()[:3000]
                    logger.warning(
                        f"[NOON] Product grid did not appear on {url}. "
                        f"Page snippet: {snippet[:500]}"
                    )
                    browser.close()
                    return []

                # Scroll halfway to trigger lazy-load of lower products
                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight * 0.5)"
                )
                page.wait_for_timeout(1500)

                products = page.query_selector_all('[data-qa="plp-product-box"]')
                logger.info(
                    f"[NOON] {len(products)} product boxes found on {url}"
                )

                for product in products:
                    try:
                        name_el = product.query_selector(
                            '[data-qa="plp-product-box-name"]'
                        )
                        price_el = product.query_selector(
                            '[data-qa="plp-product-box-price"]'
                        )
                        old_price_el = product.query_selector(
                            '[data-qa="plp-product-box-old-price"]'
                        )
                        discount_el = product.query_selector(
                            '[data-qa="plp-product-box-discount"]'
                        )
                        link_el = product.query_selector("a[href]")
                        img_el = product.query_selector("img")

                        if not name_el or not price_el or not link_el:
                            continue

                        name = name_el.inner_text().strip()
                        if not name:
                            continue

                        price_text = price_el.inner_text().strip()
                        current_price = self.price_cleaner.clean_price(price_text)
                        if current_price < MIN_PRODUCT_PRICE:
                            continue

                        original_price = current_price
                        if old_price_el:
                            old_text = old_price_el.inner_text().strip()
                            op = self.price_cleaner.clean_price(old_text)
                            if op > current_price:
                                original_price = op

                        # Derive original price from discount badge when not shown
                        if discount_el and original_price <= current_price:
                            disc_text = discount_el.inner_text().strip()
                            m = re.search(r"(\d+)", disc_text)
                            if m:
                                pct = int(m.group(1))
                                if 0 < pct < 100:
                                    original_price = round(
                                        current_price / (1 - pct / 100), 2
                                    )

                        href = link_el.get_attribute("href") or ""
                        product_url = (
                            f"https://www.noon.com{href}"
                            if href.startswith("/")
                            else href
                        )
                        if not product_url or "/p/" not in product_url:
                            continue

                        image_url = ""
                        if img_el:
                            image_url = (
                                img_el.get_attribute("data-src")
                                or img_el.get_attribute("src")
                                or ""
                            )

                        deal = self._build_deal(
                            site=site,
                            platform="noon",
                            country=country,
                            title=name,
                            url=product_url,
                            current_price=current_price,
                            original_price=original_price,
                            image_url=image_url,
                        )
                        if deal:
                            deals.append(deal)

                    except Exception as e:
                        logger.debug(f"[NOON] Product parse error: {e}")
                        continue

                browser.close()

        except Exception as e:
            logger.error(f"[NOON] Playwright failed for {url}: {e}")

        logger.info(f"[NOON] {site}: {len(deals)} deals from {url}")
        return deals

    # ── Noon UAE ──

    def scrape_noon_ae(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Noon UAE deals via Playwright."""
        if not NOON_ENABLED:
            logger.info("[OK] Noon AE disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("noon_ae", [])

        for url in urls:
            try:
                deals = self._scrape_noon_page(url, "noon_ae", "noon", "ae")
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped noon_ae ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Noon AE scrape failed for {url}: {e}")

        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)

        logger.info(f"[OK] Noon AE total: {len(unique_deals)} unique deals")
        return unique_deals

    # ── Noon Saudi Arabia ──

    def scrape_noon_sa(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Noon Saudi Arabia deals."""
        if not NOON_ENABLED:
            logger.info("[OK] Noon SA disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("noon_sa", [])

        for url in urls:
            try:
                deals = self._scrape_noon_page(url, "noon_sa", "noon", "sa")
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped noon_sa ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Noon SA scrape failed for {url}: {e}")

        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)

        logger.info(f"[OK] Noon SA total: {len(unique_deals)} unique deals")
        return unique_deals

    # ── Jumia Egypt ──

    def scrape_jumia_eg(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Jumia Egypt deals."""
        if not JUMIA_ENABLED:
            logger.info("[OK] Jumia EG disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("jumia_eg", [])

        for url in urls:
            try:
                deals = self._scrape_jumia_page(
                    url, "jumia_eg", "jumia", "eg", proxy
                )
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped jumia_eg ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Jumia EG scrape failed for {url}: {e}")

        # Deduplicate
        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["product_url"] not in seen:
                seen.add(d["product_url"])
                unique_deals.append(d)

        logger.info(f"[OK] Jumia EG total: {len(unique_deals)} unique deals")
        return unique_deals

    def _scrape_jumia_page(
        self,
        url: str,
        site: str,
        platform: str,
        country: str,
        proxy: Optional[str] = None,
    ) -> List[dict]:
        """Scrape a single Jumia deals page.

        Jumia is protected by Cloudflare WAF. Google Cloud Run IPs are blocked
        directly. We use a three-strategy cascade:
          1. curl_cffi — impersonates Chrome TLS fingerprint exactly (best bypass)
          2. scrape.do super mode — residential proxies + anti-bot
          3. Direct HTTP — last resort (may work on fresh container IPs)
        """
        html: Optional[str] = None
        referer_headers = get_headers(referer="https://www.jumia.com.eg/")

        # ── Strategy 1: curl_cffi TLS impersonation ──
        try:
            from curl_cffi import requests as cf_requests
            cf_resp = cf_requests.get(
                url,
                impersonate="chrome120",
                headers=referer_headers,
                timeout=35,
                allow_redirects=True,
            )
            if cf_resp.status_code == 200:
                html = cf_resp.text
                logger.info(f"[Jumia] curl_cffi strategy OK for {url}")
            else:
                logger.warning(
                    f"[Jumia] curl_cffi HTTP {cf_resp.status_code} for {url}"
                )
        except ImportError:
            logger.warning("[Jumia] curl_cffi not installed — skipping strategy 1")
        except Exception as e:
            logger.warning(f"[Jumia] curl_cffi error: {e}")

        # ── Strategy 2: scrape.do super proxy (residential + anti-bot) ──
        if not html and self.proxy_rotator.scrapedo_token:
            try:
                encoded = urllib.parse.quote(url, safe="")
                super_url = (
                    f"https://api.scrape.do/?token="
                    f"{self.proxy_rotator.scrapedo_token}"
                    f"&url={encoded}&super=true&render=false&geoCode=eg"
                )
                sd_resp = requests.get(
                    super_url,
                    headers={"Accept": "text/html,application/xhtml+xml,*/*"},
                    timeout=65,
                )
                if sd_resp.status_code == 200:
                    html = sd_resp.text
                    logger.info(f"[Jumia] scrape.do super strategy OK for {url}")
                else:
                    logger.warning(
                        f"[Jumia] scrape.do super HTTP {sd_resp.status_code}"
                    )
            except Exception as e:
                logger.warning(f"[Jumia] scrape.do super error: {e}")

        # ── Strategy 3: direct HTTP (last resort) ──
        if not html:
            direct_resp = self._fetch(url, headers=referer_headers)
            if direct_resp and direct_resp.status_code == 200:
                html = direct_resp.text
                logger.info(f"[Jumia] direct HTTP strategy OK for {url}")

        if not html:
            logger.warning(f"[Jumia] All strategies failed for {url}")
            return []

        # ── Parse HTML ──
        soup = BeautifulSoup(html, "lxml")
        deals: List[dict] = []

        # Jumia product card selectors (server-rendered article tags)
        cards = soup.select("article.prd")
        if not cards:
            cards = soup.select("div[data-brand]")
        if not cards:
            # Fallback: group anchors that link to products by nearest article/div
            links = soup.find_all("a", href=re.compile(r"\.html$"))
            seen_parents: set = set()
            for link in links:
                parent = link.find_parent("article") or link.find_parent(
                    "div", class_=re.compile(r"prd|card|sku")
                )
                if parent:
                    pid = id(parent)
                    if pid not in seen_parents:
                        seen_parents.add(pid)
                        cards.append(parent)

        if not cards:
            logger.warning(f"[Jumia] No product cards found in HTML for {url}")
            return []

        logger.info(f"[Jumia] {len(cards)} product cards found on {url}")

        for card in cards:
            try:
                # Title — Jumia uses h3.name or div.name
                title_el = (
                    card.select_one("h3.name")
                    or card.select_one("div.name")
                    or card.select_one("[class*='name']")
                    or card.select_one("h3")
                )
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # Product URL — anchor with .html suffix or a.core
                link_el = (
                    card.select_one("a.core")
                    or card.select_one("a[href*='.html']")
                    or card.select_one("a[href]")
                )
                href = link_el.get("href", "") if link_el else ""
                product_url = resolve_url(href, "https://www.jumia.com.eg")
                if not product_url:
                    continue

                # Current price — div.prc contains "EGP 1,234"
                price_el = (
                    card.select_one("div.prc")
                    or card.select_one("span.prc")
                    or card.select_one("[data-price]")
                )
                current_price_str = (
                    price_el.get_text(strip=True) if price_el else ""
                )

                # Original price — div.old contains crossed-out price
                original_el = (
                    card.select_one("div.old")
                    or card.select_one("span.old")
                )
                original_price_str = (
                    original_el.get_text(strip=True) if original_el else ""
                )

                # Discount badge — span.bdg._dsct or span[class*=dsct]
                # Jumia shows "-40%" in a badge element
                if not original_price_str and current_price_str:
                    discount_el = (
                        card.select_one("span.bdg._dsct")
                        or card.select_one("span[class*='dsct']")
                        or card.select_one("div.bdg")
                    )
                    if discount_el:
                        m = re.search(r"(\d+)", discount_el.get_text(strip=True))
                        if m:
                            pct = int(m.group(1))
                            current_f = self.price_cleaner.clean_price(
                                current_price_str
                            )
                            if current_f > 0 and 0 < pct < 100:
                                original_price_str = str(
                                    round(current_f / (1 - pct / 100), 2)
                                )

                # Image — Jumia lazy-loads with data-src
                img = card.select_one("img")
                image_url = extract_image_url(img, "https://www.jumia.com.eg")

                # Rating — div.stars with data-rate attribute or text
                rating: Optional[float] = None
                rating_el = card.select_one("div.stars")
                if rating_el:
                    rating_data = rating_el.get("data-rate", "")
                    if rating_data:
                        try:
                            rating = float(rating_data)
                        except (ValueError, TypeError):
                            pass
                    if rating is None:
                        m = re.search(r"([\d.]+)", rating_el.get_text(strip=True))
                        if m:
                            rating = float(m.group(1))

                # Reviews count — div.rev "(123)"
                reviews = 0
                reviews_el = card.select_one("div.rev")
                if reviews_el:
                    m = re.search(r"(\d+)", reviews_el.get_text(strip=True))
                    if m:
                        reviews = int(m.group(1))

                deal = self._build_deal(
                    site=site,
                    platform=platform,
                    country=country,
                    title=title,
                    url=product_url,
                    current_price=current_price_str,
                    original_price=original_price_str,
                    image_url=image_url,
                    rating=rating,
                    reviews=reviews,
                )
                if deal:
                    deals.append(deal)

            except Exception as e:
                logger.debug(f"[Jumia] Card parse error: {e}")
                continue

        return deals

    # ═══════════════════════════════════════════════════════════════
    # DATABASE OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    def upsert_deals(self, deals: List[dict]) -> dict:
        """Batch upsert deals to Supabase PostgreSQL.

        Returns counts: inserted, updated, unchanged.
        """
        if not deals or not self.db_pool:
            return {"inserted": 0, "updated": 0, "unchanged": 0}

        conn = self._get_db_conn(self.db_pool)
        if conn is None:
            logger.error("[ERROR] No database connection for upsert")
            return {"inserted": 0, "updated": 0, "unchanged": 0}

        inserted = 0
        updated = 0
        unchanged = 0

        try:
            with conn.cursor() as cur:
                for deal in deals:
                    try:
                        # Check if deal exists and if price changed
                        cur.execute(
                            """
                            SELECT current_price FROM deals WHERE id = %s
                            """,
                            (deal["id"],),
                        )
                        row = cur.fetchone()

                        if row is None:
                            cur.execute(
                                """
                                INSERT INTO deals (
                                    id, product_id, site, title, image_url,
                                    product_url, category, original_price, current_price,
                                    discount_percent, savings, currency,
                                    verdict, fake_score, recommendation, confidence,
                                    fraud_reasons, rating, review_count, created_at
                                ) VALUES (
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                                )
                                """,
                                (
                                    deal["id"],
                                    deal.get("product_id", ""),
                                    deal["site"],
                                    deal["title"],
                                    deal.get("image_url", ""),
                                    deal.get("product_url", ""),
                                    deal.get("category"),
                                    deal["original_price"],
                                    deal["current_price"],
                                    deal["discount_percent"],
                                    deal["savings"],
                                    deal.get("currency", "EGP"),
                                    deal.get("verdict", "GENUINE"),
                                    deal.get("fake_score", 0.0),
                                    deal.get("recommendation", "good_deal"),
                                    deal.get("confidence", 0.0),
                                    (deal.get("fraud_reasons") or None),
                                    deal.get("rating"),
                                    deal.get("review_count", 0),
                                ),
                            )
                            inserted += 1
                        else:
                            old_price = float(row[0])
                            new_price = float(deal["current_price"])

                            if abs(old_price - new_price) > 0.01:
                                cur.execute(
                                    """
                                    UPDATE deals SET
                                        current_price = %s,
                                        original_price = %s,
                                        discount_percent = %s,
                                        savings = %s,
                                        title = %s,
                                        image_url = %s,
                                        product_url = %s,
                                        category = %s,
                                        rating = %s,
                                        review_count = %s,
                                        recommendation = %s
                                    WHERE id = %s
                                    """,
                                    (
                                        deal["current_price"],
                                        deal["original_price"],
                                        deal["discount_percent"],
                                        deal["savings"],
                                        deal["title"],
                                        deal.get("image_url", ""),
                                        deal.get("product_url", ""),
                                        deal.get("category"),
                                        deal.get("rating"),
                                        deal.get("review_count", 0),
                                        deal.get("recommendation", "good_deal"),
                                        deal["id"],
                                    ),
                                )
                                updated += 1
                            else:
                                # Price unchanged — just update last_seen_at
                                cur.execute(
                                    """
                                    UPDATE deals SET
                                        last_seen_at = NOW(),
                                        is_active = %s
                                    WHERE id = %s
                                    """,
                                    (deal.get("is_active", True), deal["id"]),
                                )
                                unchanged += 1

                    except Exception as e:
                        logger.error(f"[ERROR] Failed to upsert deal {deal.get('id')}: {e}")
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        continue

                conn.commit()
        except Exception as e:
            logger.error(f"[ERROR] Upsert transaction failed: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            self._put_db_conn(self.db_pool, conn)

        return {"inserted": inserted, "updated": updated, "unchanged": unchanged}

    def record_price_snapshots(self, deals: List[dict]) -> int:
        """Record price snapshots to TimescaleDB.

        Uses chunked batching with automatic reconnection on SSL/network drops.
        Each chunk of 10 snapshots gets its own connection attempt so a single
        dropped connection doesn't wipe out all 43+ inserts.
        """
        if not deals or not self.ts_pool:
            return 0

        _SQL = """
            INSERT INTO price_snapshots
                (deal_id, product_id, site, source,
                 price, original_price, discount_percent, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """

        def _row(d: dict) -> tuple:
            return (
                d["id"],
                d.get("product_id", ""),
                d["site"],
                d["site"],
                d["current_price"],
                d["original_price"],
                d["discount_percent"],
                d.get("currency", "EGP"),
            )

        count = 0
        # Process in chunks of 10 — if one chunk's connection dies, others survive
        chunk_size = 10
        for i in range(0, len(deals), chunk_size):
            chunk = deals[i : i + chunk_size]
            conn = self._get_db_conn(self.ts_pool)
            if conn is None:
                logger.warning("[WARN] No TimescaleDB connection for snapshot chunk")
                break
            try:
                with conn.cursor() as cur:
                    for deal in chunk:
                        cur.execute(_SQL, _row(deal))
                        count += 1
                conn.commit()
            except Exception as e:
                logger.warning(f"[WARN] Snapshot chunk {i}-{i+chunk_size} failed: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                self._put_db_conn(self.ts_pool, conn)

        logger.info(f"[OK] Recorded {count}/{len(deals)} price snapshots")
        return count

    def detect_price_changes(self) -> List[dict]:
        """Compare current prices with last snapshot.

        Find deals where current price differs from last snapshot by >5%.
        Insert price_change_events. Return list of changes.
        """
        if not self.ts_pool or not self.db_pool:
            return []

        changes: List[dict] = []
        conn = self._get_db_conn(self.ts_pool)
        if conn is None:
            return []

        try:
            with conn.cursor() as cur:
                # Find deals with significant price changes
                cur.execute(
                    """
                    WITH latest_snapshots AS (
                        SELECT DISTINCT ON (deal_id)
                            deal_id, price, timestamp
                        FROM price_snapshots
                        ORDER BY deal_id, timestamp DESC
                    ),
                    previous_snapshots AS (
                        SELECT DISTINCT ON (deal_id)
                            deal_id, price, timestamp
                        FROM price_snapshots ps
                        WHERE timestamp < (
                            SELECT MAX(timestamp) FROM price_snapshots ps2
                            WHERE ps2.deal_id = ps.deal_id
                        )
                        ORDER BY deal_id, timestamp DESC
                    )
                    SELECT
                        ls.deal_id,
                        ls.price as current_price,
                        COALESCE(ps.price, ls.price) as previous_price,
                        d.site,
                        d.title,
                        d.product_url
                    FROM latest_snapshots ls
                    LEFT JOIN previous_snapshots ps ON ls.deal_id = ps.deal_id
                    JOIN deals d ON ls.deal_id = d.id
                    WHERE ps.price IS NOT NULL
                        AND ABS(ls.price - ps.price) / NULLIF(ps.price, 0) > 0.05
                    ORDER BY ABS(ls.price - ps.price) / NULLIF(ps.price, 0) DESC
                    LIMIT 100
                    """
                )
                rows = cur.fetchall()

                for row in rows:
                    deal_id, current_price, previous_price, site, title, url = row
                    if previous_price and previous_price > 0:
                        change_pct = round(
                            ((current_price - previous_price) / previous_price) * 100,
                            1,
                        )
                    else:
                        change_pct = 0.0

                    change = {
                        "deal_id": deal_id,
                        "old_price": float(previous_price),
                        "new_price": float(current_price),
                        "change_percent": change_pct,
                        "source": site,
                        "title": title,
                        "url": url,
                    }
                    changes.append(change)

                # Insert price change events
                for change in changes:
                    try:
                        cur.execute(
                            """
                            INSERT INTO price_change_events
                                (deal_id, old_price, new_price, change_percent, source, timestamp)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                            """,
                            (
                                change["deal_id"],
                                change["old_price"],
                                change["new_price"],
                                change["change_percent"],
                                change["source"],
                            ),
                        )
                    except Exception as e:
                        logger.debug(f"[DEBUG] Failed to insert price change event: {e}")
                        continue

                conn.commit()
        except Exception as e:
            logger.error(f"[ERROR] Price change detection failed: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            self._put_db_conn(self.ts_pool, conn)

        logger.info(f"[OK] Detected {len(changes)} significant price changes")
        return changes

    # ═══════════════════════════════════════════════════════════════
    # STATE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def _get_state(self, key: str) -> Optional[float]:
        """Get a timestamp state value from Supabase."""
        if not self.db_pool:
            return None
        conn = self._get_db_conn(self.db_pool)
        if conn is None:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scraper_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    "SELECT value FROM scraper_state WHERE key = %s",
                    (key,),
                )
                row = cur.fetchone()
                conn.commit()
                if row and row[0]:
                    try:
                        return float(row[0])
                    except (ValueError, TypeError):
                        return None
                return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to get state {key}: {e}")
            return None
        finally:
            self._put_db_conn(self.db_pool, conn)

    def _set_state(self, key: str, value: float):
        """Set a timestamp state value in Supabase."""
        if not self.db_pool:
            return
        conn = self._get_db_conn(self.db_pool)
        if conn is None:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scraper_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO scraper_state (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (key, str(value)),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"[ERROR] Failed to set state {key}: {e}")
        finally:
            self._put_db_conn(self.db_pool, conn)

    def should_run_discovery(self) -> bool:
        """Return True only every 4 hours to save proxy credits."""
        last = self._get_state("last_discovery")
        now = time.time()
        if not last or (now - last) > (4 * 3600):
            self._set_state("last_discovery", now)
            return True
        return False

    # ═══════════════════════════════════════════════════════════════
    # MAIN ORCHESTRATOR
    # ═══════════════════════════════════════════════════════════════

    def run_cycle(self) -> dict:
        """Run a full scraper cycle across all platforms.

        Returns summary dict with counts.
        """
        start_time = time.time()
        logger.info("[OK] === Starting DealHunter scraper cycle ===")

        all_deals: List[dict] = []
        source_counts: Dict[str, int] = {}

        # ── Scrape all platforms ──
        scrapers = [
            ("amazon_eg", self.scrape_amazon_eg),
            ("amazon_ae", self.scrape_amazon_ae),
            ("amazon_sa", self.scrape_amazon_sa),
            ("noon_eg", self.scrape_noon_eg),
            ("noon_ae", self.scrape_noon_ae),
            ("noon_sa", self.scrape_noon_sa),
            ("jumia_eg", self.scrape_jumia_eg),
        ]

        for source_name, scraper_func in scrapers:
            try:
                deals = scraper_func()
                source_counts[source_name] = len(deals)
                all_deals.extend(deals)
            except Exception as e:
                logger.error(f"[ERROR] Scraper {source_name} crashed: {e}")
                source_counts[source_name] = 0

        total_found = len(all_deals)
        logger.info(
            f"[OK] Scraping complete: {total_found} total deals found "
            f"from {len([c for c in source_counts.values() if c > 0])} sources"
        )

        # Print per-source breakdown
        for source, count in source_counts.items():
            status = "OK" if count > 0 else "WARN"
            logger.info(f"  [{status}] {source}: {count} deals")

        # ── Upsert to Supabase ──
        if all_deals and self.db_pool:
            upsert_result = self.upsert_deals(all_deals)
            logger.info(
                f"[OK] Upserted: {upsert_result['inserted']} inserted, "
                f"{upsert_result['updated']} updated, "
                f"{upsert_result['unchanged']} unchanged"
            )
        else:
            upsert_result = {"inserted": 0, "updated": 0, "unchanged": 0}
            if not self.db_pool:
                logger.warning("[WARN] No database — deals not persisted")

        # ── Record price snapshots ──
        snapshots = 0
        if all_deals and self.ts_pool:
            snapshots = self.record_price_snapshots(all_deals)
            logger.info(
                f"[OK] Recorded {snapshots} price snapshots to TimescaleDB"
            )

        # ── Detect price changes ──
        price_changes = []
        if self.ts_pool and self.db_pool:
            try:
                price_changes = self.detect_price_changes()
            except Exception as e:
                logger.error(f"[ERROR] Price change detection failed: {e}")

        # ── Print summary ──
        elapsed = round(time.time() - start_time, 1)
        result = {
            "deals_found": total_found,
            "inserted": upsert_result["inserted"],
            "updated": upsert_result["updated"],
            "unchanged": upsert_result["unchanged"],
            "snapshots": snapshots,
            "price_changes": len(price_changes),
            "sources": source_counts,
            "elapsed_seconds": elapsed,
        }

        logger.info(
            f"[OK] === Cycle complete in {elapsed}s: "
            f"{total_found} found, {upsert_result['inserted']} inserted, "
            f"{upsert_result['updated']} updated, {snapshots} snapshots ==="
        )

        return result


# ──────────────────────────── CLI Entry Point ────────────────────────────

if __name__ == "__main__":
    scraper = DealHunterScraper()
    result = scraper.run_cycle()
    print(json.dumps(result, indent=2, default=str))

