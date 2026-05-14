#!/usr/bin/env python3
"""
DealHunter Scraper — Production Cloud Run Job
Scrapes Amazon.eg/ae/sa, Noon.com (eg/ae/sa), and Jumia.com.eg for deals.
Writes to Supabase PostgreSQL (deals) and TimescaleDB (price snapshots).

Author: DealHunter Engineering
"""

from __future__ import annotations

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
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "30"))
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
        "https://www.noon.com/egypt-en/electronics-and-mobiles/",
        "https://www.noon.com/egypt-en/fashion/",
        "https://www.noon.com/egypt-en/home-and-kitchen/",
    ],
    "noon_ae": [
        "https://www.noon.com/uae-en/electronics-and-mobiles/",
        "https://www.noon.com/uae-en/fashion/",
        "https://www.noon.com/uae-en/home-and-kitchen/",
    ],
    "noon_sa": [
        "https://www.noon.com/saudi-en/electronics-and-mobiles/",
        "https://www.noon.com/saudi-en/fashion/",
        "https://www.noon.com/saudi-en/home-and-kitchen/",
    ],
    "jumia_eg": [
        "https://www.jumia.com.eg/deals-of-the-day/",
        "https://www.jumia.com.eg/electronics/",
        "https://www.jumia.com.eg/fashion/",
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
        self.scrapedo_token = os.environ.get("SCRAPE_DO_TOKEN", "")
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
                f"&url={encoded_url}"
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
        """Ensure required tables exist in both databases."""
        # Supabase deals table
        if self.db_pool:
            try:
                conn = self.db_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS deals (
                            id TEXT PRIMARY KEY,
                            site VARCHAR(32) NOT NULL,
                            platform VARCHAR(32) NOT NULL,
                            country VARCHAR(8) NOT NULL,
                            title TEXT NOT NULL,
                            url TEXT NOT NULL,
                            image_url TEXT,
                            current_price DECIMAL(12,2) NOT NULL DEFAULT 0,
                            original_price DECIMAL(12,2) NOT NULL DEFAULT 0,
                            discount_percent DECIMAL(5,1) NOT NULL DEFAULT 0,
                            discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
                            category VARCHAR(32),
                            rating DECIMAL(3,1),
                            reviews INTEGER DEFAULT 0,
                            is_active BOOLEAN DEFAULT true,
                            is_grocery BOOLEAN DEFAULT false,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            updated_at TIMESTAMPTZ DEFAULT NOW(),
                            last_seen_at TIMESTAMPTZ DEFAULT NOW()
                        )
                        """
                    )
                    # Index for common queries
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_deals_site_active
                        ON deals(site, is_active)
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_deals_discount
                        ON deals(discount_percent DESC)
                        WHERE is_active = true
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_deals_category
                        ON deals(category)
                        WHERE is_active = true
                        """
                    )
                    conn.commit()
                self.db_pool.putconn(conn)
                logger.info("[OK] Supabase deals table ensured")
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
                            price DECIMAL(12,2) NOT NULL,
                            source VARCHAR(32) NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
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
            "site": site,
            "platform": platform,
            "country": country,
            "title": title.strip()[:500],
            "url": url.strip()[:2000],
            "image_url": (image_url or "")[:2000],
            "current_price": current,
            "original_price": original,
            "discount_percent": discount["percent"],
            "discount_amount": discount["savings"],
            "category": category,
            "rating": rating,
            "reviews": reviews,
            "is_active": True,
            "is_grocery": is_grocery,
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
            if d["url"] not in seen:
                seen.add(d["url"])
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
            if d["url"] not in seen:
                seen.add(d["url"])
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
            if d["url"] not in seen:
                seen.add(d["url"])
                unique_deals.append(d)

        logger.info(f"[OK] Amazon SA total: {len(unique_deals)} unique deals")
        return unique_deals

    # ── Noon Egypt ──

    def scrape_noon_eg(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Noon Egypt deals."""
        if not NOON_ENABLED:
            logger.info("[OK] Noon EG disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("noon_eg", [])

        for url in urls:
            try:
                deals = self._scrape_noon_page(url, "noon_eg", "noon", "eg", proxy)
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
            if d["url"] not in seen:
                seen.add(d["url"])
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
        """Scrape a single Noon page."""
        resp = self._fetch(url, proxy=proxy)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        deals: List[dict] = []

        # Noon product grid selectors
        selectors = [
            "div[data-qa='product-item']",
            "div.productPane",
            "div[data-id]",
            "div.sc-5e739f1b-0",  # Noon class patterns change frequently
            "div[class*='product']",
            "a[href*='/p/']",
        ]

        cards = []
        for selector in selectors:
            if selector.startswith("a["):
                cards = soup.select(selector)
            else:
                cards = soup.select(selector)
            if cards:
                break

        # Fallback: find all anchor tags with /p/ in href
        if not cards:
            all_links = soup.find_all("a", href=re.compile(r"/p/\d+"))
            # Group by parent to form cards
            card_parents = {}
            for link in all_links:
                parent = link.find_parent("div", recursive=True)
                if parent:
                    pid = id(parent)
                    if pid not in card_parents:
                        card_parents[pid] = parent
            cards = list(card_parents.values())

        if not cards:
            logger.warning(f"[WARN] No deal cards found on Noon {country}: {url}")
            return []

        for card in cards:
            try:
                # Title
                title_el = (
                    card.select_one("div[data-qa='product-name']")
                    or card.select_one("h2")
                    or card.select_one("p[class*='title']")
                    or card.select_one("span[class*='title']")
                    or card.select_one("div[class*='name']")
                    or card.find("a", href=re.compile(r"/p/\d+"))
                )
                title = ""
                if title_el:
                    title = title_el.get_text(strip=True)
                    if not title and title_el.get("title"):
                        title = title_el["title"]
                if not title:
                    continue

                # URL
                link_el = (
                    card.select_one("a[href*='/p/']")
                    or card.find("a", href=re.compile(r"/p/\d+"))
                )
                href = link_el.get("href", "") if link_el else ""
                product_url = resolve_url(href, f"https://www.noon.com/{country}-en")
                if not product_url or "/p/" not in product_url:
                    continue

                # Current price
                price_el = (
                    card.select_one("strong[class*='amount']")
                    or card.select_one("div[data-qa='product-price']")
                    or card.select_one("span[class*='price']")
                    or card.select_one("div[class*='price'] strong")
                    or card.select_one("div[class*='salePrice']")
                )
                current_price_str = (
                    price_el.get_text(strip=True) if price_el else ""
                )

                # Original price
                original_el = (
                    card.select_one("span[class*='oldPrice']")
                    or card.select_one("span[class*='was']")
                    or card.select_one("div[class*='original'] span")
                    or card.select_one("span[class*='crossed']")
                    or card.select_one("span[data-qa='product-old-price']")
                )
                original_price_str = (
                    original_el.get_text(strip=True) if original_el else ""
                )

                # Discount percentage (if shown)
                if not original_price_str and current_price_str:
                    discount_el = (
                        card.select_one("span[class*='discount']")
                        or card.select_one("div[class*='discountBadge']")
                    )
                    if discount_el:
                        discount_text = discount_el.get_text(strip=True)
                        m = re.search(r"(\d+)", discount_text)
                        if m:
                            pct = int(m.group(1))
                            current_f = self.price_cleaner.clean_price(
                                current_price_str
                            )
                            if current_f > 0 and 0 < pct < 100:
                                original_f = current_f / (1 - pct / 100)
                                original_price_str = str(round(original_f, 2))

                # Image - handle Noon's lazy-loaded images
                img = card.select_one("img")
                image_url = extract_image_url(img, f"https://www.noon.com/{country}-en")

                # Noon often uses placeholder SVGs — try data attributes
                if not image_url or "placeholder" in image_url.lower():
                    # Look for background image in style attr
                    div_with_bg = card.select_one("div[style*='background']")
                    if div_with_bg:
                        style = div_with_bg.get("style", "")
                        m = re.search(r'url\(["\']?(.*?)["\']?\)', style)
                        if m:
                            image_url = urllib.parse.urljoin(
                                f"https://www.noon.com/{country}-en",
                                m.group(1),
                            )

                # Rating
                rating_el = card.select_one("span[class*='rating']")
                rating = None
                if rating_el:
                    rating_text = rating_el.get_text(strip=True)
                    m = re.search(r"([\d.]+)", rating_text)
                    if m:
                        rating = float(m.group(1))

                # Reviews
                reviews_el = card.select_one("span[class*='review']")
                reviews = 0
                if reviews_el:
                    reviews_text = reviews_el.get_text(strip=True)
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
                logger.debug(f"[DEBUG] Error parsing Noon card: {e}")
                continue

        return deals

    # ── Noon UAE ──

    def scrape_noon_ae(self, proxy: Optional[str] = None) -> List[dict]:
        """Scrape Noon UAE deals."""
        if not NOON_ENABLED:
            logger.info("[OK] Noon AE disabled by kill switch")
            return []

        all_deals: List[dict] = []
        urls = _DEAL_URLS.get("noon_ae", [])

        for url in urls:
            try:
                deals = self._scrape_noon_page(url, "noon_ae", "noon", "ae", proxy)
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped noon_ae ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Noon AE scrape failed for {url}: {e}")

        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["url"] not in seen:
                seen.add(d["url"])
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
                deals = self._scrape_noon_page(url, "noon_sa", "noon", "sa", proxy)
                all_deals.extend(deals)
                logger.info(
                    f"[OK] Scraped noon_sa ({url}): {len(deals)} deals found"
                )
            except Exception as e:
                logger.error(f"[ERROR] Noon SA scrape failed for {url}: {e}")

        seen = set()
        unique_deals = []
        for d in all_deals:
            if d["url"] not in seen:
                seen.add(d["url"])
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
            if d["url"] not in seen:
                seen.add(d["url"])
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
        """Scrape a single Jumia deals page."""
        headers = get_headers(referer="https://www.jumia.com.eg/")
        resp = self._fetch(url, headers=headers, proxy=proxy)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        deals: List[dict] = []

        # Jumia product card selectors
        selectors = [
            "article.prd",
            "div[data-brand]",
            "a[href*='/product/']",
            "div.-paxs article",
            "div.card",
            "div.sku",
        ]

        cards = []
        for selector in selectors:
            if selector.startswith("a["):
                # Find parent containers of product links
                links = soup.select(selector)
                seen_parents = set()
                for link in links:
                    parent = link.find_parent("article") or link.find_parent("div", class_=re.compile(r"prd|card|sku"))
                    if parent:
                        pid = id(parent)
                        if pid not in seen_parents:
                            seen_parents.add(pid)
                            cards.append(parent)
                if cards:
                    break
            else:
                cards = soup.select(selector)
                if cards:
                    break

        # Fallback: find all product links
        if not cards:
            product_links = soup.find_all(
                "a", href=re.compile(r"/product/|/item/")
            )
            seen_parents = set()
            for link in product_links:
                parent = link.find_parent("div", recursive=True)
                if parent:
                    pid = id(parent)
                    if pid not in seen_parents:
                        seen_parents.add(pid)
                        cards.append(parent)

        if not cards:
            logger.warning(f"[WARN] No deal cards found on Jumia: {url}")
            return []

        for card in cards:
            try:
                # Title
                title_el = (
                    card.select_one("div.name")
                    or card.select_one("h3.name")
                    or card.select_one("div[class*='title']")
                    or card.select_one("span[class*='name']")
                    or card.select_one("h3")
                )
                title = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # URL
                link_el = (
                    card.select_one("a[href*='/product/']")
                    or card.select_one("a[href*='/item/']")
                    or card.select_one("a.core")
                    or card.select_one("a.link")
                )
                href = link_el.get("href", "") if link_el else ""
                product_url = resolve_url(href, "https://www.jumia.com.eg")
                if not product_url:
                    continue

                # Current price
                price_el = (
                    card.select_one("div.prc")
                    or card.select_one("span.prc")
                    or card.select_one("div[data-price]")
                    or card.select_one("span[class*='price']")
                    or card.select_one("div[class*='price']")
                )
                current_price_str = (
                    price_el.get_text(strip=True) if price_el else ""
                )

                # Original price
                original_el = (
                    card.select_one("div.old")
                    or card.select_one("span.old")
                    or card.select_one("div[class*='oldPrice']")
                    or card.select_one("span[class*='crossed']")
                    or card.select_one("div.s-prc-w")
                )
                original_price_str = (
                    original_el.get_text(strip=True) if original_el else ""
                )

                # Discount percentage badge
                if not original_price_str and current_price_str:
                    discount_el = (
                        card.select_one("div.bdg")
                        or card.select_one("span.bdg")
                        or card.select_one("span[class*='discount']")
                        or card.select_one("div[class*='discount']")
                    )
                    if discount_el:
                        discount_text = discount_el.get_text(strip=True)
                        m = re.search(r"(\d+)", discount_text)
                        if m:
                            pct = int(m.group(1))
                            current_f = self.price_cleaner.clean_price(
                                current_price_str
                            )
                            if current_f > 0 and 0 < pct < 100:
                                original_f = current_f / (1 - pct / 100)
                                original_price_str = str(round(original_f, 2))

                # Image
                img = card.select_one("img")
                image_url = extract_image_url(img, "https://www.jumia.com.eg")

                # Rating
                rating_el = card.select_one("div.stars")
                rating = None
                if rating_el:
                    # Jumia shows stars as a width percentage
                    rating_text = rating_el.get_text(strip=True)
                    m = re.search(r"([\d.]+)", rating_text)
                    if m:
                        rating = float(m.group(1))
                    else:
                        # Try data-rating attribute
                        rating_data = rating_el.get("data-rating", "")
                        if rating_data:
                            try:
                                rating = float(rating_data)
                            except (ValueError, TypeError):
                                pass

                # Reviews
                reviews_el = card.select_one("div.rev")
                reviews = 0
                if reviews_el:
                    reviews_text = reviews_el.get_text(strip=True)
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
                logger.debug(f"[DEBUG] Error parsing Jumia card: {e}")
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
                            # Insert new deal
                            cur.execute(
                                """
                                INSERT INTO deals (
                                    id, site, platform, country, title, url,
                                    image_url, current_price, original_price,
                                    discount_percent, discount_amount, category,
                                    rating, reviews, is_active, is_grocery,
                                    created_at, updated_at, last_seen_at
                                ) VALUES (
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW()
                                )
                                """,
                                (
                                    deal["id"],
                                    deal["site"],
                                    deal["platform"],
                                    deal["country"],
                                    deal["title"],
                                    deal["url"],
                                    deal.get("image_url", ""),
                                    deal["current_price"],
                                    deal["original_price"],
                                    deal["discount_percent"],
                                    deal["discount_amount"],
                                    deal.get("category"),
                                    deal.get("rating"),
                                    deal.get("reviews", 0),
                                    deal.get("is_active", True),
                                    deal.get("is_grocery", False),
                                ),
                            )
                            inserted += 1
                        else:
                            old_price = float(row[0])
                            new_price = float(deal["current_price"])

                            if abs(old_price - new_price) > 0.01:
                                # Price changed — update
                                cur.execute(
                                    """
                                    UPDATE deals SET
                                        current_price = %s,
                                        original_price = %s,
                                        discount_percent = %s,
                                        discount_amount = %s,
                                        title = %s,
                                        image_url = %s,
                                        category = %s,
                                        rating = %s,
                                        reviews = %s,
                                        is_active = %s,
                                        is_grocery = %s,
                                        updated_at = NOW(),
                                        last_seen_at = NOW()
                                    WHERE id = %s
                                    """,
                                    (
                                        deal["current_price"],
                                        deal["original_price"],
                                        deal["discount_percent"],
                                        deal["discount_amount"],
                                        deal["title"],
                                        deal.get("image_url", ""),
                                        deal.get("category"),
                                        deal.get("rating"),
                                        deal.get("reviews", 0),
                                        deal.get("is_active", True),
                                        deal.get("is_grocery", False),
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
        """Record price snapshots to TimescaleDB hypertable.

        Returns number of snapshots recorded.
        """
        if not deals or not self.ts_pool:
            return 0

        conn = self._get_db_conn(self.ts_pool)
        if conn is None:
            logger.error("[ERROR] No TimescaleDB connection for snapshots")
            return 0

        count = 0
        try:
            with conn.cursor() as cur:
                for deal in deals:
                    try:
                        cur.execute(
                            """
                            INSERT INTO price_snapshots
                                (deal_id, price, source, timestamp)
                            VALUES (%s, %s, %s, NOW())
                            """,
                            (
                                deal["id"],
                                deal["current_price"],
                                deal["site"],
                            ),
                        )
                        count += 1
                    except Exception as e:
                        logger.debug(
                            f"[DEBUG] Failed to record snapshot for {deal['id']}: {e}"
                        )
                        continue
                conn.commit()
        except Exception as e:
            logger.error(f"[ERROR] Snapshot batch failed: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            self._put_db_conn(self.ts_pool, conn)

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
                        d.url
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
