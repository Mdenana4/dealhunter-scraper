# DealHunter Egypt - Scraper v7 FIXED
# FIXES:
#   1. IndentationError at line 608 — corrected all indentation in scrape_amazon()
#   2. MIN_PRICE / MAX_PRICE filter added (set via .env or Render env vars)
#   3. site_display names made consistent with dashboard expectations
#   4. Jumia firebase save confirmed to use same 'deals' collection
#   5. Carrefour API URL updated to current working format
#   6. All scrapers: proper error handling so one failure doesn't crash others

import requests
import schedule
import time
import json
import hashlib
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from dotenv import load_dotenv
from fake_checker import check_price_history
from price_tracker import record_price as _pt_record, get_triggered_alerts as _pt_alerts
from scraper_health import health as _health

load_dotenv()

MIN_DISCOUNT    = int(os.getenv("MIN_DISCOUNT", 40))
AMAZON_KEYWORD_ENABLED = os.getenv("AMAZON_KEYWORD_ENABLED", "false").lower() == "true"
INTERVAL        = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 60))
SCRAPER_API_KEY = (
    os.getenv("SCRAPER_API_KEY") or
    os.getenv("SCRAPERAPI_KEY") or
    os.getenv("SCRAPER_KEY") or
    ""
)
SCRAPEDO_TOKEN = (
    os.getenv("SCRAPEDO_TOKEN") or
    os.getenv("SCRAPE_DO_TOKEN") or
    ""
)
RAPIDAPI_KEY = (
    os.getenv("RAPIDAPI_KEY") or
    os.getenv("RAPID_API_KEY") or
    ""
)

# ─── Price filter: skip products outside this EGP range ───────────────────────
# Set MIN_PRICE and MAX_PRICE in your .env file or Render environment variables.
# Example: MIN_PRICE=100  MAX_PRICE=50000
# Leave as 0 / 9999999 to disable the filter.
MIN_PRICE = float(os.getenv("MIN_PRICE", 0))
MAX_PRICE = float(os.getenv("MAX_PRICE", 9999999))


# ─────────────────────────────────────────────────────
# FIREBASE CONNECTION
# ─────────────────────────────────────────────────────
print("Connecting to Firebase...")
firebase_key_json = (
    os.getenv("FIREBASE_KEY_JSON") or
    os.getenv("FIREBASE_CREDENTIALS_JSON") or
    os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
)

if firebase_key_json:
    try:
        key_dict = json.loads(firebase_key_json)
        cred = credentials.Certificate(key_dict)
        print("Firebase key loaded from environment variable.")
    except Exception as e:
        print(f"ERROR reading FIREBASE_KEY_JSON: {e}")
        raise
elif os.path.exists("firebase-key.json"):
    cred = credentials.Certificate("firebase-key.json")
    print("Firebase key loaded from file.")
else:
    # Firebase will be initialized by server.py
    cred = None

# Don't initialize Firebase here - server.py handles it globally
# Just get the Firestore client from the already-initialized app
try:
    if cred:
        # If we loaded credentials, initialize only if not already initialized
        try:
            firebase_admin.get_app()
            # App already initialized, just get client
            db = firestore.client()
            print("Using already-initialized Firebase app")
        except ValueError:
            # App not initialized, initialize it
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("Connected to Firebase successfully!")
    else:
        # Server.py initialized Firebase, just get the client
        db = firestore.client()
        print("Connected to Firebase (initialized by server.py)")
except Exception as e:
    print(f"Firebase initialization/connection failed: {e}")
    db = None


# ─────────────────────────────────────────────────────
# PROXY STATUS LOG
# ─────────────────────────────────────────────────────
# Set to True when scrape.do returns 401/403 so we stop wasting requests
_scrapedo_dead = False

if SCRAPEDO_TOKEN:
    print(f"[PROXY] scrape.do active (token={SCRAPEDO_TOKEN[:6]}... len={len(SCRAPEDO_TOKEN)})")
else:
    _sd_env = os.getenv("SCRAPEDO_TOKEN","") or os.getenv("SCRAPE_DO_TOKEN","")
    print(f"[PROXY] scrape.do NOT set (SCRAPEDO_TOKEN={bool(os.getenv('SCRAPEDO_TOKEN'))} SCRAPE_DO_TOKEN={bool(os.getenv('SCRAPE_DO_TOKEN'))} raw_len={len(_sd_env)})")
if SCRAPER_API_KEY:
    print(f"[PROXY] ScraperAPI fallback active (key={SCRAPER_API_KEY[:6]}...)")
if not SCRAPEDO_TOKEN and not SCRAPER_API_KEY:
    print("[PROXY] ⚠️  NO PROXY CONFIGURED — direct requests only (sites will block us!)")
    print("[PROXY]    Fix: set SCRAPEDO_TOKEN in Railway environment variables")

# ─────────────────────────────────────────────────────
# SCRAPER CONTROL (kill switch from admin dashboard)
# ─────────────────────────────────────────────────────
def check_scraper_control():
    try:
        doc = db.collection("scraper_control").document("status").get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("status") == "paused":
                print(f"  Scraper paused by admin. Resume: {d.get('resume_at', 'not set')}")
                return False
        return True
    except Exception:
        return True


# Cache disabled sources for the duration of each cycle (re-read each cycle)
_disabled_sources: set = set()

def load_disabled_sources():
    """Read disabled source keys from Firestore scraper_control/disabled_sources."""
    global _disabled_sources
    try:
        doc = db.collection("scraper_control").document("disabled_sources").get()
        if doc.exists:
            data = doc.to_dict() or {}
            _disabled_sources = {k for k, v in data.items() if v is True or v == "removed"}
        else:
            _disabled_sources = set()
    except Exception:
        _disabled_sources = set()

def is_source_enabled(key: str) -> bool:
    return key not in _disabled_sources


# ─────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def calculate_discount(original, current):
    if original <= 0 or current <= 0 or current >= original:
        return 0
    return round(((original - current) / original) * 100)

def generate_deal_id(site, url, price):
    return hashlib.md5(f"{site}_{url}_{price}".encode()).hexdigest()

def clean_price(text):
    if not text:
        return 0.0
    text = (str(text)
            .replace(',', '').replace('EGP', '').replace('ج.م', '')
            .replace('جنيه', '').replace('جنية', '').strip())
    text = re.sub(r'[^\d.]', '', text)
    try:
        return float(text)
    except Exception:
        return 0.0

def price_in_range(price):
    """Return True if price passes the MIN_PRICE / MAX_PRICE filter."""
    return MIN_PRICE <= price <= MAX_PRICE


# ─── Price-tracker integration helpers ───────────────────────────────────────

# Sites whose price history we track in the products/price_history schema.
# Keys match the deal["site"] field; values are marketplace_country keys.
_SITE_TO_MC = {
    "amazon_eg": "amazon_eg",
    "amazon_ae": "amazon_ae",
    "amazon_sa": "amazon_sa",
    "noon_eg":   "noon_eg",
    "noon_ae":   "noon_ae",
    "noon_sa":   "noon_sa",
    "jumia_eg":  "jumia_eg",
}


def _tracker_id(deal: dict) -> str:
    """
    Return a stable product identifier suitable for price_tracker.record_price().
    - Amazon: use the ASIN (always present and unique).
    - Noon:   extract the SKU slug from the product URL.
    - Jumia:  extract the alphanumeric ID appended before .html.
    - Others: fall back to deal_id.
    """
    if deal.get("asin"):
        return deal["asin"]
    url = deal.get("product_url", "")
    # Noon URL pattern: noon.com/{region}/{sku}/
    noon_m = re.search(r'noon\.com/[^/]+/([^/?]+)', url)
    if noon_m:
        return noon_m.group(1)[:80]
    # Jumia URL pattern: /product-name-MP1234567.html
    jumia_m = re.search(r'-([A-Z0-9]{5,})\.html', url, re.IGNORECASE)
    if jumia_m:
        return jumia_m.group(1)
    return (deal.get("deal_id") or "unknown")[:80]


def _fire_price_alerts(tracker_result: dict) -> None:
    """
    After record_price() signals a price change, query active user alerts
    and send FCM push notifications to each matched user.
    Users receive notifications via the topic "user_{user_id}" which the
    mobile app subscribes to on login.
    """
    try:
        alerts = _pt_alerts({
            "product_doc_id": tracker_result["doc_id"],
            "new_price":      tracker_result["new_price"],
            "change_pct":     tracker_result.get("change_pct", 0),
        })
        for alert in alerts:
            user_id = alert.get("user_id", "")
            if not user_id:
                continue
            old_p = tracker_result.get("old_price") or 0
            new_p = tracker_result["new_price"]
            pct   = abs(tracker_result.get("change_pct", 0))
            cur   = tracker_result.get("currency", "EGP")
            try:
                messaging.send(messaging.Message(
                    topic=f"user_{user_id}",
                    notification=messaging.Notification(
                        title="💰 Price Drop Alert!",
                        body=f"Price dropped {pct:.1f}% → {new_p:,.0f} {cur}",
                    ),
                    data={
                        "type":            "price_alert",
                        "product_doc_id":  tracker_result["doc_id"],
                        "old_price":       str(old_p),
                        "new_price":       str(new_p),
                        "change_pct":      str(tracker_result.get("change_pct", 0)),
                        "alert_id":        alert.get("alert_id", ""),
                    },
                    android=messaging.AndroidConfig(priority="high"),
                ))
                # Stamp the alert so we don't re-fire it immediately
                if db:
                    db.collection("price_alerts").document(alert["alert_id"]).update({
                        "last_alerted_at": now_iso(),
                    })
                print(f"  [ALERT] Sent to user_{user_id} — {new_p:,.0f} {cur}")
            except Exception as _fe:
                print(f"  [ALERT] FCM error for user_{user_id}: {_fe}")
    except Exception as _e:
        print(f"  [ALERT] Error: {_e}")

def get_headers(mobile=False):
    if mobile:
        return {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

def detect_category(title):
    t = title.lower()
    if re.search(r'phone|mobile|iphone|samsung|xiaomi|oppo|vivo|realme|laptop|notebook|tablet|ipad|computer|monitor|keyboard|mouse|headphone|earphone|earbuds|airpods|speaker|camera|\btv\b|television|gaming|playstation|xbox|console|router|charger|cable|power.?bank|smartwatch|flash.?drive|usb|ssd|hard.?disk|printer|drone|ram|processor', t):
        return "electronics"
    if re.search(r'dress|shirt|shoes|bag|perfume|parfum|fragrance|eau.?de|attar|oud|jeans|jacket|sneaker|sandal|handbag|wallet|belt|hat|cap|suit|blouse|skirt|coat|boots|polo|t-shirt|tshirt|underwear|socks|scarf|glasses|sunglasses|leggings|hoodie|sweatshirt|bra|swimsuit', t):
        return "fashion"
    if re.search(r'sofa|chair|bed|table|lamp|kitchen|blender|cookware|vacuum|air.?condition|refrigerator|washing.?machine|oven|microwave|curtain|pillow|mattress|shelf|cabinet|wardrobe|fan|heater|iron|kettle|toaster|coffee.?maker|air.?fryer|pressure.?cooker|dishwasher|water.?filter', t):
        return "home"
    if re.search(r'cream|serum|shampoo|makeup|skincare|moisturizer|lotion|vitamin|supplement|omega|collagen|fish.?oil|probiotic|face.?wash|nail|lipstick|foundation|mascara|toner|sunscreen|body.?wash|deodorant|cologne|hair.?dryer|straightener|razor|trimmer', t):
        return "beauty"
    if re.search(r'gym|sport|fitness|yoga|bicycle|bike|football|tennis|treadmill|dumbbell|resistance.?band|protein|swimming|basketball|volleyball|badminton|weights|barbell|boxing', t):
        return "sports"
    if re.search(r'toy|baby|kids|children|doll|lego|puzzle|infant|toddler|stroller|diaper|feeding|educational|board.?game|action.?figure', t):
        return "toys"
    if re.search(r'car|auto|vehicle|tire|wheel|motor.?oil|engine|spare.?part|seat.?cover|dashboard|steering|wiper|exhaust', t):
        return "automotive"
    if re.search(r'food|grocery|snack|drink|juice|rice|pasta|oil|sugar|coffee|tea|chocolate|biscuit|chips|sauce|spice|flour|bread|milk|cheese|yogurt|honey|jam|cereal|protein.?bar', t):
        return "grocery"
    if re.search(r'book|novel|textbook|stationery|pen|notebook|pencil|magazine|dictionary|academic|study', t):
        return "books"
    return None


# ─────────────────────────────────────────────────────
# SCRAPERAPI
# ─────────────────────────────────────────────────────
def extract_next_data(html_text):
    """Extract __NEXT_DATA__ JSON embedded in Next.js pages."""
    # Use string slicing to avoid regex backtracking issues with large JSON
    tag_match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>', html_text)
    if tag_match:
        start = tag_match.end()
        end = html_text.find('</script>', start)
        if end != -1:
            raw = html_text[start:end].strip()
            try:
                return json.loads(raw)
            except Exception:
                pass
    # Fallback: original regex (handles reversed attribute order)
    m = re.search(r'<script[^>]*__NEXT_DATA__[^>]*>\s*({.+})\s*</script>', html_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


_SCRAPERAPI_EXHAUSTED = False  # set True when monthly quota gone

# Tracks new deals found in the current scraper run for batch FCM notification.
# Cleared at the end of each run_scraper() call.
_new_deals_this_run: list = []


def is_blocked_response(resp, min_length=2000):
    """Return True when the response looks like a CAPTCHA or bot-block page."""
    if not resp or resp.status_code != 200:
        return True
    text_lower = (resp.text or "")[:4000].lower()
    block_signals = [
        "robot check", "captcha", "automated access", "unusual traffic",
        "i'm not a robot", "access denied", "403 forbidden", "cloudflare",
        "just a moment", "security check", "verify you are human",
        "enable javascript", "please wait while we verify",
        "suspicious activity", "bot protection",
    ]
    for signal in block_signals:
        if signal in text_lower:
            return True
    # Very short response usually means redirect / empty block page
    if len(resp.text) < min_length:
        return True
    return False


def fetch_with_scrapedo(url, render_js=False, country="eg", super_proxy=False,
                        wait_until=None, wait_selector=None, custom_wait=None):
    """Fetch via scrape.do proxy. 1 credit (HTML), 5 (JS render), 10 (super residential)."""
    global _scrapedo_dead
    if not SCRAPEDO_TOKEN or _scrapedo_dead:
        return None
    import gzip as _gz
    try:
        params = {
            "token":   SCRAPEDO_TOKEN,
            "url":     url,
            "render":  "true" if (render_js or super_proxy) else "false",
            "geoCode": country.upper(),
        }
        if super_proxy:
            params["super"] = "true"
        if wait_until:
            params["waitUntil"] = wait_until
        if wait_selector:
            params["waitSelector"] = wait_selector
        if custom_wait:
            params["customWait"] = str(custom_wait)
        # stream=True lets us read raw bytes before decompression
        resp = requests.get(
            "https://api.scrape.do",
            params=params,
            timeout=60,
            headers={"Accept-Encoding": "gzip, deflate"},
            allow_redirects=True,
            stream=True,
        )
        if resp.status_code in (401, 403):
            print(f"    [scrape.do] HTTP {resp.status_code} — token invalid or credits exhausted, disabling for this session")
            _scrapedo_dead = True
            resp.close()
            return None
        if resp.status_code not in (200, 301, 302):
            print(f"    [scrape.do] HTTP {resp.status_code} for {url[:60]}")
            resp.close()
            return None
        # Read raw bytes without auto-decompression, then decompress manually
        raw = resp.raw.read(decode_content=False)
        resp.close()
        enc = resp.headers.get("Content-Encoding", "").lower()
        if "gzip" in enc or raw[:2] == b"\x1f\x8b":
            try:
                content = _gz.decompress(raw)
            except Exception:
                content = raw
        elif "deflate" in enc:
            import zlib as _zlib
            try:
                content = _zlib.decompress(raw)
            except Exception:
                try:
                    content = _zlib.decompress(raw, -15)
                except Exception:
                    content = raw
        else:
            content = raw
        if len(content) < 500:
            return None
        # Patch response so callers can use .content and .text normally
        resp._content = content
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp
    except Exception as e:
        print(f"    [scrape.do] error: {e}")
        return None


_AMAZON_API_GEOCODES = {
    # Egypt, UAE, Saudi Arabia are NOT supported by the scrape.do Amazon
    # structured API (returns HTTP 400). Only Western markets are supported.
    # Add a geocode here only after confirming it works.
    "us": "us", "uk": "uk", "de": "de", "fr": "fr",
    "it": "it", "es": "es", "ca": "ca", "au": "au",
    "jp": "jp", "in": "in", "br": "br", "mx": "mx",
}
_AMAZON_API_ZIPCODES = {
    "eg": "11311",  # Cairo
    "ae": "00000",
    "sa": "11564",  # Riyadh
    "us": "10001",
}


def fetch_amazon_structured_search(keyword, country_code):
    """
    Call scrape.do's Amazon Search API for clean JSON results.
    Returns list of product dicts (asin, title, price.amount, rating…) or None.
    1 credit per call — same cost as a basic scrape.do request.
    """
    if not SCRAPEDO_TOKEN or _scrapedo_dead:
        return None
    geocode = _AMAZON_API_GEOCODES.get(country_code)
    if not geocode:
        return None  # unsupported market — don't waste a credit
    zipcode = _AMAZON_API_ZIPCODES.get(country_code, "00000")
    try:
        resp = requests.get(
            "https://api.scrape.do/plugin/amazon/search",
            params={
                "token":    SCRAPEDO_TOKEN,
                "keyword":  keyword,
                "geocode":  geocode,
                "zipcode":  zipcode,
                "language": "EN",
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            products = data.get("products", [])
            print(f"    [amz-api] '{keyword}' geocode={geocode} → {len(products)} products")
            return products if products else None
        print(f"    [amz-api] HTTP {resp.status_code} for '{keyword}' geocode={geocode}")
        return None
    except Exception as e:
        print(f"    [amz-api] error: {e}")
        return None


def fetch_amazon_product_detail(asin, country_code):
    """
    Call scrape.do's Amazon PDP API to get price + list_price for one ASIN.
    Returns dict or None. 1 credit per call.
    """
    if not SCRAPEDO_TOKEN or _scrapedo_dead:
        return None
    geocode = _AMAZON_API_GEOCODES.get(country_code)
    if not geocode:
        return None
    zipcode = _AMAZON_API_ZIPCODES.get(country_code, "00000")
    try:
        resp = requests.get(
            "https://api.scrape.do/plugin/amazon/pdp",
            params={
                "token":    SCRAPEDO_TOKEN,
                "asin":     asin,
                "geocode":  geocode,
                "zipcode":  zipcode,
                "language": "EN",
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"    [amz-pdp] error: {e}")
        return None


def fetch_with_scraperapi(url, render_js=True, country="eg"):
    global _SCRAPERAPI_EXHAUSTED
    # Prefer scrape.do when token is set
    if SCRAPEDO_TOKEN:
        resp = fetch_with_scrapedo(url, render_js=render_js, country=country)
        if resp:
            return resp
        # scrape.do failed — fall through to ScraperAPI or direct
    if not SCRAPER_API_KEY or _SCRAPERAPI_EXHAUSTED:
        return fetch_direct(url)
    try:
        params = {
            "api_key": SCRAPER_API_KEY,
            "url": url,
            "render": "true" if render_js else "false",
            "country_code": country,
            "premium": "false",
        }
        resp = requests.get("http://api.scraperapi.com", params=params, timeout=60)
        if resp.status_code == 200:
            return resp
        if resp.status_code == 403 and "exhausted" in resp.text.lower():
            _SCRAPERAPI_EXHAUSTED = True
            print("⚠️  ScraperAPI credits exhausted — switching to direct fetch for this cycle")
        return fetch_direct(url)
    except Exception as e:
        print(f"    ScraperAPI error: {e}")
        return fetch_direct(url)

def fetch_direct(url, mobile=False):
    try:
        return requests.get(url, headers=get_headers(mobile=mobile), timeout=20)
    except Exception as e:
        print(f"    Direct fetch error: {e}")
        return None

def fetch_noon_direct(url, country_code="eg"):
    """Direct fetch for Noon with realistic browser headers. No proxy needed for most pages."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.noon.com/",
        "sec-ch-ua": '"Chromium";v="124","Google Chrome";v="124"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "max-age=0",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        return resp
    except Exception as e:
        print(f"    Noon direct error: {e}")
        return None


# ─────────────────────────────────────────────────────
# SCRAPER ERROR LOGGING
# ─────────────────────────────────────────────────────
def _log_scraper_error(scraper: str, url: str, message: str) -> None:
    """Persist a scraper error to Firestore admin_logs so it shows in the admin panel."""
    if not db:
        return
    try:
        db.collection("admin_logs").document().set({
            "level":     "error",
            "type":      "scraper_error",
            "scraper":   scraper,
            "url":       url[:500],
            "message":   message[:1000],
            "timestamp": now_iso(),
        })
    except Exception:
        pass  # never crash scraper because of logging


# ─────────────────────────────────────────────────────
# SAVE DEAL — Always update Firebase, never skip
# ─────────────────────────────────────────────────────
def save_deal(deal):
    deal_id = deal["deal_id"]
    ref = db.collection("deals").document(deal_id)
    try:
        if deal.get("review_count", 0) == 0:
            deal["review_count"] = None

        existing = ref.get()
        if existing.exists:
            old = existing.to_dict()
            old_price = old.get("current_price", 0)
            new_price  = deal["current_price"]

            update = {
                "current_price":   new_price,
                "discount_percent": deal["discount_percent"],
                "timestamp":       deal["timestamp"],
            }
            if deal.get("image_url"):
                update["image_url"] = deal["image_url"]
            if deal.get("rating", 0) > 0:
                update["rating"] = deal["rating"]
            if deal.get("review_count") is not None:
                update["review_count"] = deal["review_count"]
            if deal.get("coupon_codes"):
                update["coupon_codes"]   = deal["coupon_codes"]
                update["coupon_display"] = deal.get("coupon_display", "")

            kb = deal.get("kanbkam", {})
            if kb:
                update.update({
                    "kanbkam":              kb,
                    "fake_verdict":         kb.get("verdict", "UNVERIFIED"),
                    "fake_verdict_ar":      kb.get("verdict_ar", ""),
                    "fake_emoji":           kb.get("emoji", ""),
                    "rule_a":               kb.get("rule_a_triggered", False),
                    "rule_b":               kb.get("rule_b_triggered", False),
                    "lowest_price_ever":    kb.get("lowest_price", 0),
                    "highest_price_ever":   kb.get("highest_price", 0),
                    "suggested_wait_price": kb.get("suggested_wait_price", 0),
                    "source_used":          kb.get("source_used", ""),
                })

            ref.update(update)

            if old_price != new_price:
                ref.collection("price_history").document().set({
                    "price": new_price, "old_price": old_price, "timestamp": deal["timestamp"]
                })
                print(f"  UPDATED: {deal['title'][:45]} | EGP {old_price:,.0f}→{new_price:,.0f} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
            else:
                print(f"  REFRESH: {deal['title'][:45]} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
        else:
            ref.set(deal)
            ref.collection("price_history").document().set({
                "price": deal["current_price"], "timestamp": deal["timestamp"]
            })
            print(f"  NEW:     {deal['title'][:45]} | {deal['discount_percent']}% OFF | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
            # Queue for batch FCM notification at end of scraper run
            _new_deals_this_run.append({
                "title":            deal["title"],
                "discount_percent": deal.get("discount_percent", 0),
                "site":             deal.get("site", ""),
                "site_display":     deal.get("site_display", ""),
                "currency":         deal.get("currency", "EGP"),
                "current_price":    deal.get("current_price", 0),
                "deal_id":          deal.get("deal_id", ""),
            })

        # ── Record to price_tracker (builds the full price-history schema) ──
        mc = _SITE_TO_MC.get(deal.get("site", ""))
        if mc and db:
            try:
                _result = _pt_record(
                    marketplace_country = mc,
                    product_id          = _tracker_id(deal),
                    name                = deal["title"],
                    url                 = deal["product_url"],
                    price               = float(deal["current_price"]),
                    original_price      = float(deal["original_price"]) if deal.get("original_price") else None,
                    currency            = deal.get("currency", "EGP"),
                    in_stock            = deal.get("availability") != "out_of_stock",
                    image_url           = deal.get("image_url"),
                    category            = deal.get("category"),
                )
                if _result.get("price_changed"):
                    _fire_price_alerts(_result)
            except Exception as _te:
                print(f"  [TRACKER] {_te}")

    except Exception as e:
        print(f"  SAVE ERROR: {e}")


def _notify_new_deals(deals: list) -> None:
    """
    Send FCM push notifications to tier topics summarising newly found deals.

    Tier thresholds (minimum discount to be notified):
      tier_vip     → 40 %  (VIP users get everything)
      tier_premium → 50 %
      tier_free    → 60 %

    One FCM message is sent per tier — so at most 3 FCM calls per scraper run
    regardless of how many deals were found.  Each message picks the best deal
    as the headline and mentions the total count.

    Debug notes printed:
      [FCM-DEALS] Sent to <topic>: N deals, best XX% — <title>
      [FCM-DEALS] Error sending to <topic>: <error>   ← root cause visible in Railway logs
      [FCM-DEALS] No new deals this cycle — skipping notifications
    """
    if not deals:
        print("  [FCM-DEALS] No new deals this cycle — skipping notifications")
        return

    # Sort by discount descending so the best deal is always first
    sorted_deals = sorted(deals, key=lambda d: d.get("discount_percent", 0), reverse=True)

    tier_configs = [
        ("tier_vip",     40),
        ("tier_premium", 50),
        ("tier_free",    60),
    ]

    for topic, min_disc in tier_configs:
        qualifying = [d for d in sorted_deals if d.get("discount_percent", 0) >= min_disc]
        if not qualifying:
            print(f"  [FCM-DEALS] {topic}: no deals >= {min_disc}% — skipping")
            continue

        best   = qualifying[0]
        count  = len(qualifying)
        title_text = f"🔥 {count} New Deal{'s' if count > 1 else ''} — {best['site_display'] or best['site']}"
        if count == 1:
            body_text = f"{best['title'][:60]} — {best['discount_percent']}% OFF"
        else:
            body_text = (
                f"Best: {best['title'][:40]} {best['discount_percent']}% OFF"
                f" (+{count - 1} more)"
            )

        try:
            msg_id = messaging.send(messaging.Message(
                topic=topic,
                notification=messaging.Notification(
                    title=title_text,
                    body=body_text,
                ),
                data={
                    "type":           "new_deals",
                    "count":          str(count),
                    "best_discount":  str(best["discount_percent"]),
                    "best_deal_id":   str(best["deal_id"]),
                    "site":           str(best["site"]),
                },
                android=messaging.AndroidConfig(priority="high"),
            ))
            print(f"  [FCM-DEALS] ✓ Sent to {topic}: {count} deals, best {best['discount_percent']}% — msg_id={msg_id}")
        except Exception as fcm_err:
            # Log the full error so Railway logs show the root cause
            print(
                f"  [FCM-DEALS] ✗ Error sending to {topic}: {fcm_err}\n"
                f"             Root cause: {type(fcm_err).__name__} — check Firebase service account\n"
                f"             has 'Firebase Cloud Messaging Admin' role in Google Cloud IAM."
            )
            # Persist to Firestore so it appears in the admin Logs panel
            if db:
                try:
                    db.collection("admin_logs").document().set({
                        "level":     "error",
                        "type":      "fcm_error",
                        "topic":     topic,
                        "message":   str(fcm_err)[:800],
                        "timestamp": now_iso(),
                    })
                except Exception:
                    pass


def build_deal(title, site, site_display, category, current_price, original_price,
               discount, image_url, product_url, rating=0.0, review_count=None,
               asin=None, kanbkam_result=None, coupon_codes=None, currency="EGP"):
    if not kanbkam_result:
        from fake_checker import local_verdict
        kanbkam_result = local_verdict(current_price, original_price)
    if review_count == 0:
        review_count = None
    return {
        "deal_id":              generate_deal_id(site, product_url, current_price),
        "title":                title,
        "title_ar":             "",
        "site":                 site,
        "site_display":         site_display,
        "category":             category,
        "current_price":        current_price,
        "original_price":       original_price,
        "discount_percent":     discount,
        "currency":             currency,
        "image_url":            image_url,
        "product_url":          product_url,
        "asin":                 asin or "",
        "availability":         "in_stock",
        "timestamp":            now_iso(),
        "rating":               rating,
        "review_count":         review_count,
        "coupon_codes":         coupon_codes or kanbkam_result.get("coupon_codes", []),
        "coupon_display":       kanbkam_result.get("coupon_display", ""),
        "verified":             True,
        "hidden":               False,
        "featured":             False,
        "source":               "scraper",
        "kanbkam":              kanbkam_result,
        "fake_verdict":         kanbkam_result.get("verdict", "UNVERIFIED"),
        "fake_verdict_ar":      kanbkam_result.get("verdict_ar", ""),
        "fake_emoji":           kanbkam_result.get("emoji", "❓"),
        "fake_score":           kanbkam_result.get("fake_score", 50),
        "rule_a":               kanbkam_result.get("rule_a_triggered", False),
        "rule_b":               kanbkam_result.get("rule_b_triggered", False),
        "lowest_price_ever":    kanbkam_result.get("lowest_price", 0),
        "highest_price_ever":   kanbkam_result.get("highest_price", 0),
        "suggested_wait_price": kanbkam_result.get("suggested_wait_price", 0),
        "source_used":          kanbkam_result.get("source_used", ""),
        "click_count":          0,
        "buy_click_count":      0,
    }


# ─────────────────────────────────────────────────────
# AMAZON — RapidAPI (primary) + HTML scraper (fallback)
# ─────────────────────────────────────────────────────

_RAPIDAPI_AMAZON_HOST = "real-time-amazon-data.p.rapidapi.com"
_RAPIDAPI_HEADERS = {
    "x-rapidapi-host": _RAPIDAPI_AMAZON_HOST,
    "x-rapidapi-key":  RAPIDAPI_KEY,
    "Content-Type":    "application/json",
}
# Set to True once we receive a 403; prevents all subsequent API calls this process lifetime
_rapidapi_plan_blocked = False

_AMAZON_SEARCH_TERMS = [
    ("samsung galaxy",    "electronics"), ("iphone",          "electronics"),
    ("xiaomi phone",      "electronics"), ("oppo phone",       "electronics"),
    ("laptop lenovo",     "electronics"), ("laptop dell",      "electronics"),
    ("laptop hp",         "electronics"), ("laptop asus",      "electronics"),
    ("tablet android",    "electronics"), ("ipad",             "electronics"),
    ("sony headphones",   "electronics"), ("jbl speaker",      "electronics"),
    ("earbuds bluetooth", "electronics"), ("samsung watch",    "electronics"),
    ("samsung tv",        "electronics"), ("lg tv",            "electronics"),
    ("playstation",       "electronics"), ("power bank",       "electronics"),
    ("router wifi",       "electronics"), ("gaming keyboard",  "electronics"),
    ("digital camera",    "electronics"), ("ssd",              "electronics"),
    ("nike shoes",        "fashion"),     ("adidas shoes",     "fashion"),
    ("mens shirt",        "fashion"),     ("womens dress",     "fashion"),
    ("handbag women",     "fashion"),     ("perfume men",      "fashion"),
    ("air conditioner",   "home"),        ("refrigerator",     "home"),
    ("washing machine",   "home"),        ("microwave oven",   "home"),
    ("air fryer",         "home"),        ("blender",          "home"),
    ("face cream",        "beauty"),      ("hair dryer",       "beauty"),
    ("vitamin supplement","beauty"),      ("shampoo",          "beauty"),
    ("protein powder",    "sports"),      ("yoga mat",         "sports"),
    ("baby stroller",     "toys"),
]


def _rapidapi_amazon_search(query, country, default_cat,
                             marketplace_country, site_display, currency,
                             page=1):
    """Fetch one search page via RapidAPI and save qualifying deals. Returns count."""
    resp, ok = _rapidapi_get(
        "search",
        {
            "query":   query,
            "page":    page,
            "country": country,
            "sort_by": "RELEVANCE",
        },
        f"SEARCH/{country}",
    )
    if ok == "blocked":
        return -1  # signal caller to abort all remaining search calls
    if not ok or resp is None:
        return 0
    products = (resp.json().get("data") or {}).get("products") or []
    return _parse_and_save_rapidapi_products(
        products, country, marketplace_country, site_display, currency, "SEARCH")


def _rapidapi_get(endpoint, params, label="RapidAPI"):
    """
    Make one RapidAPI call.
    Returns (response, ok) where ok=False means caller should stop/skip.
    Returns (None, "blocked") specifically on 403 (plan does not cover this endpoint).
    """
    global _rapidapi_plan_blocked
    if _rapidapi_plan_blocked:
        return None, "blocked"
    try:
        resp = requests.get(
            f"https://{_RAPIDAPI_AMAZON_HOST}/{endpoint}",
            headers=_RAPIDAPI_HEADERS,
            params=params,
            timeout=30,
        )
        if resp.status_code == 429:
            print(f"    [{label}] Rate limit (429) — skipping (use HTML scraper)")
            return None, False
        if resp.status_code == 403:
            print(f"    [{label}] 403 Forbidden — plan blocked, disabling RapidAPI for this session")
            _rapidapi_plan_blocked = True
            return None, "blocked"
        if resp.status_code != 200:
            print(f"    [{label}] HTTP {resp.status_code}")
            return None, False
        return resp, True
    except Exception as e:
        print(f"    [{label}] request error: {e}")
        return None, False


def _parse_and_save_rapidapi_products(products, country, marketplace_country,
                                       site_display, currency, label="API"):
    """Parse product list from RapidAPI and save qualifying deals. Returns count."""
    saved = 0
    for p in products:
        try:
            title = (p.get("product_title") or p.get("deal_title") or p.get("title") or "").strip()
            if not title or len(title) < 5:
                continue

            asin = p.get("asin", "")
            product_url = p.get("product_url") or p.get("deal_url") or (
                f"https://www.amazon.{country.lower()}/dp/{asin}" if asin else "")
            if not product_url:
                continue

            cp = clean_price(str(
                p.get("product_price") or p.get("deal_price") or 0))
            op = clean_price(str(
                p.get("product_original_price") or p.get("original_price") or
                p.get("list_price") or 0))
            if cp < 1:
                continue
            if op < cp:
                op = cp

            disc_raw = (p.get("discount_percent") or p.get("savings_percent") or
                        p.get("product_discount") or "")
            try:
                disc = int(re.sub(r"[^\d]", "", str(disc_raw))) if disc_raw else 0
            except Exception:
                disc = 0
            if disc == 0:
                disc = calculate_discount(op, cp)
            if disc >= MIN_DISCOUNT and op <= cp:
                op = round(cp / (1 - disc / 100))
            if disc < MIN_DISCOUNT:
                continue
            if currency == "EGP" and not price_in_range(cp):
                continue

            image_url = (p.get("product_photo") or p.get("thumbnail") or
                         p.get("deal_image") or p.get("product_image") or "")
            try:
                rating = float(p.get("product_star_rating") or 0)
            except Exception:
                rating = 0.0
            rc_raw = p.get("product_num_ratings") or p.get("product_num_offers")
            try:
                review_count = int(str(rc_raw).replace(",", "")) if rc_raw else None
            except Exception:
                review_count = None

            cat = detect_category(title)
            print(f"    [{label}/{country}] [{disc}%] {title[:42]}...")
            kb = check_price_history(
                asin=asin, product_url=product_url, current_price=cp,
                original_price=op, title=title, site=marketplace_country,
            )
            time.sleep(0.5)
            deal = build_deal(
                title=title, site=marketplace_country, site_display=site_display,
                category=cat, current_price=cp, original_price=op,
                discount=disc, image_url=image_url, product_url=product_url,
                rating=rating, review_count=review_count, asin=asin,
                kanbkam_result=kb, currency=currency,
            )
            save_deal(deal)
            saved += 1
        except Exception:
            continue
    return saved


def _rapidapi_amazon_deals(country, marketplace_country, site_display, currency):
    """Fetch Amazon deals/offers via RapidAPI. Returns count, or -1 if plan blocked (403)."""
    total = 0
    all_deals = []
    try:
        for offset in (0, 50):
            resp, ok = _rapidapi_get(
                "deals-and-offers",
                {"country": country, "offset": offset, "limit": 50},
                f"DEALS/{country}",
            )
            if ok == "blocked":
                return -1  # signal to caller: abort all RapidAPI phases
            if not ok or resp is None:
                break
            data = resp.json()
            batch = (
                (data.get("data") or {}).get("deals") or
                (data.get("data") or {}).get("products") or
                data.get("deals") or []
            )
            if not batch:
                break
            all_deals.extend(batch)
            time.sleep(2)

        total = _parse_and_save_rapidapi_products(
            all_deals, country, marketplace_country, site_display, currency, "DEALS")
    except Exception as e:
        print(f"    RapidAPI deals [{country}] error: {e}")
    return total


def _rapidapi_amazon_category(country, category_id, default_cat,
                               marketplace_country, site_display, currency):
    """Search a category on Amazon via RapidAPI. Returns count."""
    total = 0
    for page in (1, 2):
        resp, ok = _rapidapi_get(
            "search",
            {
                "query":       default_cat,
                "page":        page,
                "country":     country,
                "category_id": category_id,
                "sort_by":     "RELEVANCE",
            },
            f"CAT/{country}/{category_id}",
        )
        if ok == "blocked":
            return -1
        if not ok or resp is None:
            break
        products = (resp.json().get("data") or {}).get("products") or []
        total += _parse_and_save_rapidapi_products(
            products, country, marketplace_country, site_display, currency,
            f"CAT/{category_id}",
        )
        time.sleep(2)
    return total


# Amazon category IDs for broad category searches
_AMAZON_CATEGORIES = [
    ("electronics",         "electronics"),
    ("computers",           "electronics"),
    ("fashion",             "fashion"),
    ("home-garden",         "home"),
    ("beauty",              "beauty"),
    ("sporting-goods",      "sports"),
    ("toys-and-games",      "toys"),
    ("grocery",             "grocery"),
]


def _scrape_amazon_via_api(
    country="EG",
    marketplace_country="amazon_eg",
    site_display="Amazon Egypt",
    currency="EGP",
):
    """Scrape Amazon using RapidAPI — no proxy needed, no CAPTCHA."""
    print(f"\n[AMAZON/{country}] RapidAPI mode — {site_display}...")
    total = 0

    # Phase 1: dedicated deals/offers endpoint
    n = _rapidapi_amazon_deals(country, marketplace_country, site_display, currency)
    if n == -1:
        print(f"  Deals endpoint: 403 blocked — aborting RapidAPI for {country}, will use HTML scraper")
        return 0
    print(f"  Deals endpoint: {n} deals")
    total += n
    time.sleep(3)

    # Phase 2: keyword search (abort immediately if plan is blocked)
    _search_blocked = False
    for term, default_cat in _AMAZON_SEARCH_TERMS:
        if _search_blocked:
            break
        for page in (1, 2):
            n = _rapidapi_amazon_search(
                term, country, default_cat,
                marketplace_country, site_display, currency, page=page,
            )
            if n == -1:
                print(f"  Search endpoint: 403 blocked — aborting Phase 2+3 for {country}")
                _search_blocked = True
                break
            total += n
            time.sleep(2)

    # Phase 3: broad category search with discount filter
    if not _search_blocked:
        for cat_id, default_cat in _AMAZON_CATEGORIES:
            n = _rapidapi_amazon_category(
                country, cat_id, default_cat,
                marketplace_country, site_display, currency,
            )
            if n == -1:
                break
            total += n
            time.sleep(3)

    print(f"[AMAZON/{country}] RapidAPI done. {total} deals.")
    return total


# ── HTML-scraper fallback (used when RAPIDAPI_KEY is not set) ────────────────
AMAZON_KEYWORDS = [
    {"k": "samsung galaxy",   "cat": "electronics"},
    {"k": "iphone",           "cat": "electronics"},
    {"k": "xiaomi phone",     "cat": "electronics"},
    {"k": "oppo phone",       "cat": "electronics"},
    {"k": "laptop lenovo",    "cat": "electronics"},
    {"k": "laptop dell",      "cat": "electronics"},
    {"k": "laptop hp",        "cat": "electronics"},
    {"k": "laptop asus",      "cat": "electronics"},
    {"k": "tablet android",   "cat": "electronics"},
    {"k": "ipad",             "cat": "electronics"},
    {"k": "sony headphones",  "cat": "electronics"},
    {"k": "jbl speaker",      "cat": "electronics"},
    {"k": "earbuds bluetooth","cat": "electronics"},
    {"k": "samsung watch",    "cat": "electronics"},
    {"k": "samsung tv",       "cat": "electronics"},
    {"k": "lg tv",            "cat": "electronics"},
    {"k": "playstation",      "cat": "electronics"},
    {"k": "power bank",       "cat": "electronics"},
    {"k": "router wifi",      "cat": "electronics"},
    {"k": "ssd",              "cat": "electronics"},
    {"k": "gaming keyboard",  "cat": "electronics"},
    {"k": "digital camera",   "cat": "electronics"},
    {"k": "nike shoes",       "cat": "fashion"},
    {"k": "adidas shoes",     "cat": "fashion"},
    {"k": "puma shoes",       "cat": "fashion"},
    {"k": "mens shirt",       "cat": "fashion"},
    {"k": "womens dress",     "cat": "fashion"},
    {"k": "handbag women",    "cat": "fashion"},
    {"k": "sunglasses",       "cat": "fashion"},
    {"k": "perfume men",      "cat": "fashion"},
    {"k": "perfume women",    "cat": "fashion"},
    {"k": "air conditioner",  "cat": "home"},
    {"k": "refrigerator",     "cat": "home"},
    {"k": "washing machine",  "cat": "home"},
    {"k": "microwave oven",   "cat": "home"},
    {"k": "air fryer",        "cat": "home"},
    {"k": "blender",          "cat": "home"},
    {"k": "coffee maker",     "cat": "home"},
    {"k": "vacuum cleaner",   "cat": "home"},
    {"k": "electric kettle",  "cat": "home"},
    {"k": "face cream",       "cat": "beauty"},
    {"k": "hair dryer",       "cat": "beauty"},
    {"k": "vitamin supplement","cat": "beauty"},
    {"k": "makeup kit",       "cat": "beauty"},
    {"k": "shampoo",          "cat": "beauty"},
    {"k": "gym equipment",    "cat": "sports"},
    {"k": "protein powder",   "cat": "sports"},
    {"k": "treadmill",        "cat": "sports"},
    {"k": "yoga mat",         "cat": "sports"},
    {"k": "lego",             "cat": "toys"},
    {"k": "baby stroller",    "cat": "toys"},
    {"k": "arabic novel",     "cat": "books"},
    {"k": "protein bar",      "cat": "grocery"},
    {"k": "organic honey",    "cat": "grocery"},
]


def _scrape_amazon_deals_page(
    base_domain="amazon.eg",
    marketplace_country="amazon_eg",
    site_display="Amazon Egypt",
    currency="EGP",
    country_code="eg",
):
    """Scrape Amazon discount-sorted search page (SSR, works without JS). Returns deal count."""
    # Amazon's discount-filtered search is server-side rendered — no React hydration needed.
    # Filters: 40%+ off, sorted by discount rank. Works on EG, AE, SA.
    deals_url = (
        f"https://www.{base_domain}/s?"
        f"rh=p_n_pct-off-with-tax%3A40-&s=discount-rank&language=en_AE"
    )
    print(f"\n[AMAZON/{country_code.upper()}] Scraping deals page...")
    total = 0

    for page_num in range(1, 4):  # pages 1–3
        try:
            url = deals_url if page_num == 1 else f"{deals_url}&page={page_num}"
            resp = fetch_with_scrapedo(url, render_js=False, country=country_code)
            if not resp or is_blocked_response(resp, min_length=5000):
                resp = fetch_with_scraperapi(url, render_js=False, country=country_code)
            if is_blocked_response(resp, min_length=5000):
                print(f"  Deals page {page_num}: blocked/empty (HTTP {resp.status_code if resp else 'no response'}) — skipping")
                _log_scraper_error(f"amazon_{country_code}", url, "Blocked/CAPTCHA response on deals page")
                break

            soup = BeautifulSoup(resp.content, "lxml")
            # Amazon deals page uses several different card structures depending on locale/year.
            # Try each selector in order, use the first that yields results.
            products = (
                [p for p in soup.find_all("div", attrs={"data-asin": True}) if p.get("data-asin", "").strip()] or
                soup.find_all("div", attrs={"data-component-type": "s-search-result"}) or
                soup.find_all("div", attrs={"data-testid": "deal-card"}) or
                soup.find_all("li", class_=re.compile(r"GridItem|deal-card|s-result-item", re.I)) or
                soup.find_all("div", class_=re.compile(r"DealCard|deal-card|dealCard", re.I))
            )
            if not products:
                # Log a snippet to help diagnose selector issues
                body_text = soup.get_text(" ", strip=True)[:200]
                print(f"  Deals page {page_num}: 0 products — selectors exhausted. Page preview: {body_text!r}")
                _log_scraper_error(f"amazon_{country_code}", url, "0 products parsed — all selectors failed")
                break

            print(f"  Deals page {page_num}: {len(products)} product divs")

            for product in products:
                try:
                    asin = product.get("data-asin", "").strip()
                    if not asin:
                        continue
                    if product.get("data-component-type") == "sp-sponsored-result":
                        continue

                    title_el = (
                        product.find("h2") or
                        product.find("span", class_="a-size-medium") or
                        product.find("span", class_="a-size-base-plus")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title.split()) < 3:
                        continue

                    price_el = product.find("span", class_="a-price-whole")
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text(strip=True))
                    if current_price < 1:
                        continue

                    original_price = current_price
                    orig_block = product.find("span", class_="a-price a-text-price")
                    if orig_block:
                        orig_el = orig_block.find("span", class_="a-offscreen")
                        if orig_el:
                            original_price = clean_price(orig_el.get_text(strip=True)) or current_price

                    # Try to get discount from badge first (most reliable on deals page)
                    discount = calculate_discount(original_price, current_price)
                    badge_el = product.find("span", class_="a-badge-text")
                    if badge_el:
                        badge_text = badge_el.get_text(strip=True)
                        nums = re.findall(r'\d+', badge_text)
                        if nums and int(nums[0]) >= MIN_DISCOUNT:
                            discount = int(nums[0])
                            if original_price <= current_price:
                                original_price = round(current_price / (1 - discount / 100))

                    if discount < MIN_DISCOUNT:
                        continue

                    img_el    = product.find("img", class_="s-image")
                    image_url = img_el.get("src", "") if img_el else ""

                    rating = 0.0
                    rating_el = product.find("span", class_="a-icon-alt")
                    if rating_el:
                        try:
                            rating = float(rating_el.get_text(strip=True).split(" ")[0])
                        except Exception:
                            pass

                    product_url = f"https://www.{base_domain}/dp/{asin}?language=en_AE"
                    cat = detect_category(title)

                    print(f"    [{discount}%] {title[:40]}...")
                    kb = check_price_history(
                        asin=asin,
                        product_url=product_url,
                        current_price=current_price,
                        original_price=original_price,
                        title=title,
                        site=marketplace_country,
                    )
                    time.sleep(1)

                    deal = build_deal(
                        title=title,
                        site=marketplace_country,
                        site_display=site_display,
                        category=cat,
                        current_price=current_price,
                        original_price=original_price,
                        discount=discount,
                        image_url=image_url,
                        product_url=product_url,
                        rating=rating,
                        review_count=None,
                        asin=asin,
                        kanbkam_result=kb,
                        currency=currency,
                    )
                    save_deal(deal)
                    total += 1
                    time.sleep(0.5)

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  Amazon/{country_code} deals page error (page {page_num}): {e}")
            break

    print(f"[AMAZON/{country_code.upper()}] Deals page done. {total} deals.")
    return total


def _scrape_amazon_region(
    base_domain="amazon.eg",
    marketplace_country="amazon_eg",
    site_display="Amazon Egypt",
    currency="EGP",
    country_code="eg",
):
    """Scrape any Amazon regional store. Called by the three wrappers below."""
    print(f"\n[AMAZON/{country_code.upper()}] Starting — {site_display}...")
    total = 0

    if not AMAZON_KEYWORD_ENABLED:
        print(f"  [AMAZON/{country_code.upper()}] keyword scan disabled (AMAZON_KEYWORD_ENABLED=false)")
        return 0

    seen_asins: set = set()  # deduplicate across all keywords (avoids 20+ adidas variants)

    for item in AMAZON_KEYWORDS:
        try:
            # ── Strategy A: scrape.do structured Amazon Search API ─────────
            # Returns clean JSON (asin, title, price) — no HTML parsing.
            # If the geocode isn't supported or the call fails, falls through
            # to Strategy B (HTML scraping).
            api_products = fetch_amazon_structured_search(item["k"], country_code)
            if api_products:
                saved_this_keyword = 0
                for p in api_products:
                    if saved_this_keyword >= 6:
                        break
                    asin  = (p.get("asin") or "").strip()
                    title = (p.get("title") or "").strip()
                    if not asin or not title or len(title.split()) < 3:
                        continue
                    if asin in seen_asins:
                        continue
                    if p.get("isSponsored"):
                        continue

                    # Get price + list_price from PDP (1 extra credit per product)
                    pdp = fetch_amazon_product_detail(asin, country_code)
                    if not pdp:
                        continue
                    cp = float(pdp.get("price") or 0)
                    op = float(pdp.get("list_price") or cp)
                    if cp < 50 or op < cp:
                        op = cp
                    discount = calculate_discount(op, cp)

                    # Also accept badge-stated discounts for products with no list_price
                    if discount < MIN_DISCOUNT:
                        continue
                    if currency == "EGP" and not price_in_range(cp):
                        continue

                    seen_asins.add(asin)
                    images = pdp.get("images") or []
                    img    = images[0].get("url", "") if images else ""
                    rating = float(pdp.get("rating") or 0)
                    rc     = int(pdp.get("total_ratings") or 0)
                    cat    = detect_category(title) or item["cat"]
                    product_url = f"https://www.{base_domain}/dp/{asin}?language=en_AE"

                    print(f"    [amz-api✓] {title[:40]} | {discount}% off")
                    kb = check_price_history(asin=asin, product_url=product_url,
                                             current_price=cp, original_price=op,
                                             title=title, site=marketplace_country)
                    deal = build_deal(title=title, site=marketplace_country,
                                      site_display=site_display, category=cat,
                                      current_price=cp, original_price=op,
                                      discount=discount, image_url=img,
                                      product_url=product_url, rating=rating,
                                      review_count=rc, asin=asin,
                                      kanbkam_result=kb, currency=currency)
                    save_deal(deal)
                    total += 1
                    saved_this_keyword += 1
                    time.sleep(1)

                time.sleep(2)
                continue  # structured API succeeded — skip HTML fallback

            # ── Strategy B: HTML keyword search (fallback) ─────────────────
            url = f"https://www.{base_domain}/s?k={item['k'].replace(' ', '+')}&language=en_AE"
            resp = fetch_with_scrapedo(url, render_js=True, country=country_code)
            if not resp or is_blocked_response(resp, min_length=5000):
                resp = fetch_with_scraperapi(url, render_js=True, country=country_code)
            if is_blocked_response(resp, min_length=5000):
                print(f"  [{item['k']}]: blocked/empty response — skipping")
                _log_scraper_error(f"amazon_{country_code}", url, f"Blocked response on keyword '{item['k']}'")
                time.sleep(5)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            products = [
                p for p in soup.find_all("div", attrs={"data-asin": True})
                if p.get("data-asin", "").strip()
            ]
            saved_this_keyword = 0

            for product in products:
                try:
                    if saved_this_keyword >= 6:
                        break  # cap at 6 deals per keyword to avoid 20+ adidas variants
                    asin = product.get("data-asin", "").strip()
                    if not asin:
                        continue
                    if asin in seen_asins:
                        continue  # skip duplicate (same product from another keyword)
                    seen_asins.add(asin)  # mark seen immediately to avoid re-checking variants
                    if product.get("data-component-type") == "sp-sponsored-result":
                        continue

                    title_el = (
                        product.find("h2") or
                        product.find("span", class_="a-size-medium") or
                        product.find("span", class_="a-size-base-plus")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    # Require at least 3 words: rejects bare brand names like
                    # "adidas", "Samsung", "Babacom" that Amazon renders in cards
                    # when the full title span hasn't hydrated.
                    if not title or len(title.split()) < 3:
                        continue

                    price_el = product.find("span", class_="a-price-whole")
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text(strip=True))
                    if current_price < 50:
                        continue

                    original_price = current_price
                    orig_block = product.find("span", class_="a-price a-text-price")
                    if orig_block:
                        orig_el = orig_block.find("span", class_="a-offscreen")
                        if orig_el:
                            original_price = clean_price(orig_el.get_text(strip=True)) or current_price

                    discount = calculate_discount(original_price, current_price)
                    badge_el = product.find("span", class_="a-badge-text")
                    if badge_el and discount < MIN_DISCOUNT:
                        nums = re.findall(r'\d+', badge_el.get_text())
                        if nums and int(nums[0]) >= MIN_DISCOUNT:
                            discount = int(nums[0])
                            original_price = round(current_price / (1 - discount / 100))
                    if discount < MIN_DISCOUNT:
                        continue

                    img_el    = product.find("img", class_="s-image")
                    image_url = img_el.get("src", "") if img_el else ""

                    rating = 0.0
                    rating_el = product.find("span", class_="a-icon-alt")
                    if rating_el:
                        try:
                            rating = float(rating_el.get_text(strip=True).split(" ")[0])
                        except Exception:
                            pass

                    review_count = None
                    for rel in product.find_all("span", {"aria-label": True}):
                        label = rel.get("aria-label", "")
                        if re.search(r'\d', label) and "star" not in label.lower():
                            try:
                                rc = int(re.sub(r'[^\d]', '', label))
                                if rc > 0:
                                    review_count = rc
                                    break
                            except Exception:
                                pass

                    product_url = f"https://www.{base_domain}/dp/{asin}?language=en_AE"
                    cat = detect_category(title)
                    if cat == "general":
                        cat = item["cat"]

                    # Skip EGP price-range filter for non-EGP markets
                    if currency == "EGP" and not price_in_range(current_price):
                        continue

                    print(f"    Checking: {title[:35]}...")
                    kb = check_price_history(
                        asin=asin,
                        product_url=product_url,
                        current_price=current_price,
                        original_price=original_price,
                        title=title,
                        site=marketplace_country,
                    )
                    time.sleep(1)

                    deal = build_deal(
                        title=title,
                        site=marketplace_country,
                        site_display=site_display,
                        category=cat,
                        current_price=current_price,
                        original_price=original_price,
                        discount=discount,
                        image_url=image_url,
                        product_url=product_url,
                        rating=rating,
                        review_count=review_count,
                        asin=asin,
                        kanbkam_result=kb,
                        currency=currency,
                    )
                    seen_asins.add(asin)
                    save_deal(deal)
                    total += 1
                    saved_this_keyword += 1
                    time.sleep(0.5)

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  Amazon/{country_code} keyword error '{item['k']}': {e}")
            time.sleep(5)

    print(f"[AMAZON/{country_code.upper()}] Done. {total} deals.")
    return total


def scrape_amazon():
    """Amazon Egypt — keyword HTML scraper via scrape.do."""
    print("\n[AMAZON/EG] Skipping RapidAPI (free plan 403) — going straight to HTML scraper")
    return _scrape_amazon_region()

def scrape_amazon_ae():
    """Amazon UAE — keyword HTML scraper via scrape.do."""
    print("\n[AMAZON/AE] Skipping RapidAPI — going straight to HTML scraper")
    return _scrape_amazon_region("amazon.ae", "amazon_ae", "Amazon UAE", "AED", "ae")

def scrape_amazon_sa():
    """Amazon Saudi Arabia — keyword HTML scraper via scrape.do."""
    print("\n[AMAZON/SA] Skipping RapidAPI — going straight to HTML scraper")
    return _scrape_amazon_region("amazon.sa", "amazon_sa", "Amazon Saudi Arabia", "SAR", "sa")


# ─────────────────────────────────────────────────────
# JUMIA EGYPT — Static HTML
# ─────────────────────────────────────────────────────
def scrape_jumia():
    print("\n[JUMIA] Starting...")
    total = 0
    pages = [
        ("https://www.jumia.com.eg/flash-sales/", "general"),
        ("https://www.jumia.com.eg/phones-tablets/?sort=discountPercent&type=lowest-price", "electronics"),
        ("https://www.jumia.com.eg/electronics/?sort=discountPercent&type=lowest-price", "electronics"),
        ("https://www.jumia.com.eg/fashion/?sort=discountPercent", "fashion"),
        ("https://www.jumia.com.eg/home-office/?sort=discountPercent", "home"),
        ("https://www.jumia.com.eg/sporting-goods/?sort=discountPercent", "sports"),
        ("https://www.jumia.com.eg/beauty-health/?sort=discountPercent", "beauty"),
        ("https://www.jumia.com.eg/baby-products/?sort=discountPercent", "toys"),
    ]

    for url, default_cat in pages:
        try:
            # scrape.do super proxy first (residential IP, JS rendering)
            resp = fetch_with_scrapedo(url, render_js=False, country="eg", super_proxy=True)
            if not resp or is_blocked_response(resp, min_length=3000):
                resp = fetch_with_scraperapi(url, render_js=False, country="eg")
            if is_blocked_response(resp, min_length=3000):
                print(f"  [JUMIA] blocked/empty: {url[:55]}...")
                _log_scraper_error("jumia_eg", url, "Blocked/empty response")
                time.sleep(5)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("article", class_="prd") or
                soup.find_all("article", attrs={"data-id": True}) or
                soup.find_all("div", class_="prd")
            )
            if not products:
                print(f"  [JUMIA] 0 products at {url[:55]}... — selector may be broken")
                _log_scraper_error("jumia_eg", url, "0 products — selector may be broken")
                continue
            print(f"  [JUMIA] {len(products)} products: {url[:55]}...")

            for p in products:
                try:
                    title_el = (
                        p.find("h3", class_="name") or
                        p.find("p", class_="name") or
                        p.find("h3")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    price_el = (
                        p.find("div", class_="prc") or
                        p.find("span", class_="prc") or
                        p.find(class_=lambda c: c and "prc" in str(c))
                    )
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50:
                        continue

                    # ✅ FIX: Apply MIN_PRICE / MAX_PRICE filter
                    if not price_in_range(current_price):
                        continue

                    orig_el = (
                        p.find("div", class_="old") or
                        p.find("span", class_="old") or
                        p.find("s") or
                        p.find(class_=lambda c: c and "old" in str(c))
                    )
                    original_price = clean_price(orig_el.get_text()) if orig_el else current_price
                    if original_price < current_price:
                        original_price = current_price

                    discount = calculate_discount(original_price, current_price)
                    disc_el = p.find(class_=lambda c: c and "dsct" in str(c))
                    if disc_el and discount < MIN_DISCOUNT:
                        try:
                            bd = int(re.sub(r'[^\d]', '', disc_el.get_text()))
                            if bd >= MIN_DISCOUNT:
                                discount = bd
                                if original_price == current_price:
                                    original_price = round(current_price / (1 - bd / 100))
                        except Exception:
                            pass
                    if discount < MIN_DISCOUNT:
                        continue

                    link_el = p.find("a", href=True)
                    href = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://www.jumia.com.eg" + href

                    img_el    = p.find("img")
                    image_url = (img_el.get("data-src") or img_el.get("src") or "") if img_el else ""

                    rating = 0.0
                    stars_el = p.find(class_=lambda c: c and "stars" in str(c))
                    if stars_el:
                        try:
                            m = re.search(r'[\d.]+', stars_el.get_text(strip=True))
                            if m:
                                rating = float(m.group())
                        except Exception:
                            pass

                    review_count = None
                    rev_el = p.find(class_=lambda c: c and "rev" in str(c))
                    if rev_el:
                        try:
                            rc = int(re.sub(r'[^\d]', '', rev_el.get_text()))
                            if rc > 0:
                                review_count = rc
                        except Exception:
                            pass

                    cat = detect_category(title)
                    if cat == "general":
                        cat = default_cat

                    kb = check_price_history(
                        product_url=product_url,
                        current_price=current_price,
                        original_price=original_price,
                        title=title,
                        site="jumia_eg"
                    )

                    deal = build_deal(
                        title=title,
                        site="jumia_eg",
                        site_display="Jumia Egypt",   # ✅ consistent name
                        category=cat,
                        current_price=current_price,
                        original_price=original_price,
                        discount=discount,
                        image_url=image_url,
                        product_url=product_url,
                        rating=rating,
                        review_count=review_count,
                        kanbkam_result=kb
                    )
                    save_deal(deal)
                    total += 1

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  [JUMIA] Error: {e}")
            time.sleep(5)

    print(f"[JUMIA] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# B.TECH — Static HTML
# ─────────────────────────────────────────────────────
def scrape_btech():
    print("\n[B.TECH] Starting...")
    total = 0
    pages = [
        ("https://btech.com/en/promotions.html?pageSize=48", "electronics"),
        ("https://btech.com/en/sale.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/mobiles-and-tablets.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/laptops-and-computers.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/tv-and-audio.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/home-appliances.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "home"),
    ]

    for url, default_cat in pages:
        try:
            headers = get_headers()
            headers["Referer"] = "https://btech.com/"
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            headers["Cache-Control"] = "no-cache"
            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code == 403:
                # Try mobile UA on 403
                resp = requests.get(url, headers=get_headers(mobile=True), timeout=25)
            if resp.status_code != 200:
                time.sleep(2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("li",  class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("div", class_="item product product-item") or
                soup.find_all("div", class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "product-card" in str(c)) or
                soup.find_all("article", class_=lambda c: c and "product" in str(c))
            )
            print(f"  [B.TECH] {len(products)} products: {url[:55]}...")

            for p in products:
                try:
                    title_el = (
                        p.find("a", class_="product-item-link") or
                        p.find("strong", class_="product-item-name") or
                        p.find("a", class_=lambda c: c and "product" in str(c) and "link" in str(c))
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    special_el = p.find("span", class_="special-price")
                    if special_el:
                        price_span = special_el.find("span", class_="price")
                    else:
                        price_span = p.find("span", class_="price")
                    if not price_span:
                        continue
                    current_price = clean_price(price_span.get_text())
                    if current_price < 50:
                        continue
                    if not price_in_range(current_price):
                        continue

                    old_el = p.find("span", class_="old-price")
                    if old_el:
                        old_price_span = old_el.find("span", class_="price")
                        original_price = clean_price(old_price_span.get_text()) if old_price_span else current_price
                    else:
                        original_price = current_price
                    if original_price < current_price:
                        original_price = current_price

                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    link_el = p.find("a", class_="product-item-link") or p.find("a", href=True)
                    href = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://btech.com" + href

                    img_el    = p.find("img")
                    image_url = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""

                    cat = detect_category(title) or default_cat

                    kb = check_price_history(
                        product_url=product_url,
                        current_price=current_price,
                        original_price=original_price,
                        title=title,
                        site="btech_eg"
                    )

                    deal = build_deal(
                        title=title,
                        site="btech_eg",
                        site_display="B.Tech Egypt",
                        category=cat,
                        current_price=current_price,
                        original_price=original_price,
                        discount=discount,
                        image_url=image_url,
                        product_url=product_url,
                        kanbkam_result=kb
                    )
                    save_deal(deal)
                    total += 1

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  [B.TECH] Error: {e}")
            time.sleep(5)

    print(f"[B.TECH] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# CARREFOUR EGYPT — JSON API (updated URL format)
# ─────────────────────────────────────────────────────
def scrape_carrefour():
    print("\n[CARREFOUR] Starting — JSON API...")
    total = 0
    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.carrefouregypt.com/",
        "lang": "en",
        "country": "EG",
    }
    categories = [
        ("electronics",        "electronics"),
        ("mobiles-tablets",    "electronics"),
        ("computers",          "electronics"),
        ("tv-video",           "electronics"),
        ("kitchen-appliances", "home"),
        ("large-appliances",   "home"),
        ("fashion",            "fashion"),
        ("sports-outdoors",    "sports"),
        ("beauty-health",      "beauty"),
    ]

    for cat_id, default_cat in categories:
        products_data = []
        # Try multiple Carrefour API URL formats — they update the version periodically
        api_urls = [
            f"https://www.carrefouregypt.com/api/v9/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc",
            f"https://www.carrefouregypt.com/api/v8/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc",
            f"https://www.carrefouregypt.com/api/v7/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc",
            f"https://www.carrefouregypt.com/api/v6/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc",
            f"https://www.carrefouregypt.com/mafegy/en/c/{cat_id}?pageSize=48&sortBy=discountPercentage&sortOrder=desc&format=json",
        ]
        for api_url in api_urls:
            try:
                resp = requests.get(api_url, headers=api_headers, timeout=20)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        products_data = (
                            data.get("data", {}).get("products", {}).get("results", []) or
                            data.get("products", {}).get("results", []) or
                            data.get("results", []) or []
                        )
                        if products_data:
                            break
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [CARREFOUR] API error {cat_id}: {e}")
                continue

        # HTML fallback: scrape category page directly if all APIs returned nothing
        if not products_data:
            try:
                page_url = f"https://www.carrefouregypt.com/mafegy/en/c/{cat_id}?pageSize=48&sortBy=discountPercentage&sortOrder=desc"
                resp = requests.get(page_url, headers=api_headers, timeout=20)
                if resp.status_code == 200:
                    nd = extract_next_data(resp.text)
                    nd_str = json.dumps(nd)
                    if nd_str and len(nd_str) > 100:
                        products_data = (
                            nd.get("props", {}).get("pageProps", {}).get("catalog", {}).get("products", {}).get("results", []) or
                            nd.get("props", {}).get("pageProps", {}).get("products", {}).get("results", []) or []
                        )
            except Exception as e:
                print(f"  [CARREFOUR] HTML fallback error {cat_id}: {e}")

        print(f"  [CARREFOUR] {len(products_data)} products: {cat_id}")

        for p in products_data:
            try:
                title = p.get("name", "") or p.get("title", "")
                if not title:
                    continue

                price_info    = p.get("price", {})
                current_price = clean_price(str(
                    price_info.get("value", 0) or
                    price_info.get("discounted", 0) or
                    p.get("price", 0)
                ))
                original_price = clean_price(str(
                    price_info.get("formattedOriginalPrice", current_price) or
                    price_info.get("original", current_price) or
                    current_price
                ))

                if current_price < 50:
                    continue
                if not price_in_range(current_price):
                    continue
                if original_price < current_price:
                    original_price = current_price

                discount = calculate_discount(original_price, current_price)
                if discount < MIN_DISCOUNT:
                    continue

                images    = p.get("images", [{}])
                image_url = (images[0].get("url", "") if images else "") or ""
                if image_url and not image_url.startswith("http"):
                    image_url = "https://www.carrefouregypt.com" + image_url

                code        = p.get("code", "") or p.get("id", "")
                product_url = f"https://www.carrefouregypt.com/mafegy/en/p/{code}"

                rating       = float(p.get("averageRating", 0) or 0)
                review_count = int(p.get("numberOfReviews", 0) or 0) or None

                cat = detect_category(title) or default_cat

                kb = check_price_history(
                    product_url=product_url,
                    current_price=current_price,
                    original_price=original_price,
                    title=title,
                    site="carrefour_eg"
                )

                deal = build_deal(
                    title=title,
                    site="carrefour_eg",
                    site_display="Carrefour Egypt",
                    category=cat,
                    current_price=current_price,
                    original_price=original_price,
                    discount=discount,
                    image_url=image_url,
                    product_url=product_url,
                    rating=rating,
                    review_count=review_count,
                    kanbkam_result=kb
                )
                save_deal(deal)
                total += 1

            except Exception:
                continue

        time.sleep(2)

    print(f"[CARREFOUR] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# SHARAF DG — Static HTML
# ─────────────────────────────────────────────────────
def scrape_sharaf_dg():
    print("\n[SHARAF DG] Starting...")
    total = 0
    # Try both URL formats — Sharaf DG occasionally restructures their paths
    pages = [
        ("https://www.sharafdg.com/en/eg/deals",                                     "electronics"),
        ("https://www.sharafdg.com/en/eg/sale",                                      "electronics"),
        ("https://www.sharafdg.com/en/eg/mobiles-tablets",                           "electronics"),
        ("https://www.sharafdg.com/en/eg/smartphones",                               "electronics"),
        ("https://www.sharafdg.com/en/eg/computers-laptops",                         "electronics"),
        ("https://www.sharafdg.com/en/eg/tv-video-audio",                            "electronics"),
        ("https://www.sharafdg.com/en/eg/home-appliances",                           "home"),
    ]

    for url, default_cat in pages:
        try:
            headers = get_headers()
            headers["Referer"] = "https://www.sharafdg.com/"
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code == 404:
                continue  # Skip wrong URL variant silently
            if resp.status_code != 200:
                time.sleep(2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")

            # Try __NEXT_DATA__ first (if they moved to Next.js)
            nd_products = []
            nd = extract_next_data(resp.text)
            if nd:
                nd_str = json.dumps(nd)
                if "price" in nd_str.lower():
                    # Products might be nested — just try known paths
                    nd_products = (
                        nd.get("props", {}).get("pageProps", {}).get("products", []) or
                        nd.get("props", {}).get("pageProps", {}).get("items", []) or []
                    )

            products = (
                soup.find_all("li",  class_=lambda c: c and "item" in str(c) and "product" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "product-card" in str(c)) or
                soup.find_all("article", class_=lambda c: c and "product" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "item-product" in str(c))
            )

            # Process Next.js products if found
            if nd_products and not products:
                for item in nd_products:
                    try:
                        title = item.get("name", item.get("title", ""))
                        if not title:
                            continue
                        cp = clean_price(str(item.get("salePrice", item.get("price", item.get("currentPrice", 0)))))
                        op = clean_price(str(item.get("originalPrice", item.get("regularPrice", cp))))
                        if cp < 50 or not price_in_range(cp):
                            continue
                        if op < cp:
                            op = cp
                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue
                        purl = item.get("url", item.get("productUrl", ""))
                        if purl and not purl.startswith("http"):
                            purl = "https://www.sharafdg.com" + purl
                        img = item.get("image", item.get("imageUrl", ""))
                        cat = detect_category(title) or default_cat
                        kb = check_price_history(product_url=purl, current_price=cp,
                                                 original_price=op, title=title, site="sharaf_dg_eg")
                        deal = build_deal(title=title, site="sharaf_dg_eg",
                                          site_display="Sharaf DG Egypt", category=cat,
                                          current_price=cp, original_price=op, discount=disc,
                                          image_url=img, product_url=purl, kanbkam_result=kb)
                        save_deal(deal)
                        total += 1
                    except Exception:
                        continue

            print(f"  [SHARAF] {len(products)} HTML products: {url[:55]}...")

            for p in products:
                try:
                    title_el = (
                        p.find("a", class_=lambda c: c and "product" in str(c) and "link" in str(c)) or
                        p.find("span", class_=lambda c: c and "product-name" in str(c)) or
                        p.find("h2") or p.find("h3") or
                        p.find("a", class_="product-item-link")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    special_el = p.find("span", class_=lambda c: c and "special" in str(c))
                    if special_el:
                        price_el = special_el.find("span", class_="price")
                    else:
                        price_el = (p.find("span", class_="price") or
                                    p.find(class_=lambda c: c and "price" in str(c) and "old" not in str(c)))
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50:
                        continue
                    if not price_in_range(current_price):
                        continue

                    old_el = (
                        p.find("span", class_=lambda c: c and "old" in str(c) and "price" in str(c)) or
                        p.find("del") or p.find("s")
                    )
                    original_price = clean_price(old_el.get_text()) if old_el else current_price
                    if original_price < current_price:
                        original_price = current_price

                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    link_el     = p.find("a", href=True)
                    href        = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://www.sharafdg.com" + href

                    img_el    = p.find("img")
                    image_url = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""

                    cat = detect_category(title) or default_cat

                    kb = check_price_history(
                        product_url=product_url,
                        current_price=current_price,
                        original_price=original_price,
                        title=title,
                        site="sharaf_dg_eg"
                    )

                    deal = build_deal(
                        title=title,
                        site="sharaf_dg_eg",
                        site_display="Sharaf DG Egypt",
                        category=cat,
                        current_price=current_price,
                        original_price=original_price,
                        discount=discount,
                        image_url=image_url,
                        product_url=product_url,
                        kanbkam_result=kb
                    )
                    save_deal(deal)
                    total += 1

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  [SHARAF] Error: {e}")
            time.sleep(5)

    print(f"[SHARAF DG] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# NOON EGYPT — ScraperAPI + JSON extraction
# ─────────────────────────────────────────────────────
def _process_noon_item(src, default_cat, region_path="egypt-en", currency="EGP"):
    """Parse a single Noon product dict. Returns tuple or None."""
    title = (src.get("name") or src.get("title") or src.get("productName") or "").strip()
    if not title:
        return None

    # Current price — try multiple known field shapes
    p = src.get("price")
    if isinstance(p, dict):
        cp_raw = p.get("now") or p.get("value") or p.get("sale_price") or p.get("current") or 0
        op_raw = p.get("before_price") or p.get("was") or p.get("before") or p.get("original") or cp_raw
        disc_stored = p.get("discount_percent") or p.get("discount") or 0
    else:
        cp_raw = src.get("sale_price") or src.get("current_price") or src.get("now_price") or p or 0
        op_raw = src.get("was_price") or src.get("original_price") or src.get("before_price") or cp_raw
        disc_stored = src.get("discount_percent") or src.get("discount") or 0

    cp = clean_price(str(cp_raw))
    op = clean_price(str(op_raw))

    if cp < 1:
        return None
    if op < cp:
        op = cp

    disc = calculate_discount(op, cp)
    # Accept if either our calculated disc OR the stored disc_percent meets MIN_DISCOUNT
    if disc < MIN_DISCOUNT and int(disc_stored or 0) < MIN_DISCOUNT:
        return None

    img_keys = src.get("image_keys") or []
    img = f"https://f.nooncdn.com/p/{img_keys[0]}.jpg" if img_keys else (
        src.get("image_key") and f"https://f.nooncdn.com/p/{src['image_key']}.jpg" or
        src.get("image") or src.get("thumbnail") or ""
    )
    sku  = src.get("sku") or src.get("product_id") or src.get("id") or ""
    purl = f"https://www.noon.com/{region_path}/{sku}/" if sku else src.get("url") or ""

    r = src.get("rating")
    rating = float(r.get("value") or r.get("average") or 0 if isinstance(r, dict) else r or 0)
    rc_raw = src.get("review_count") or src.get("reviews_count") or (
        r.get("count") or r.get("total") if isinstance(r, dict) else 0) or 0
    rc = int(rc_raw) or None
    cat = detect_category(title) or default_cat
    return title, cp, op, disc or int(disc_stored), img, purl, rating, rc, cat


def _parse_noon_products(content, default_cat, region_path, currency, marketplace_country,
                         site_display, country_code, seen_skus=None):
    """
    Try every known method to extract Noon products from HTML/JSON content.
    Returns count of deals saved.
    """
    saved = 0

    # ── Helper: walk any JSON tree for product-shaped objects ─────────────
    def _walk(obj, depth=0):
        if depth > 10 or not isinstance(obj, (dict, list)):
            return []
        if isinstance(obj, list):
            out = []
            for x in obj:
                out.extend(_walk(x, depth + 1))
            return out
        # Noon product: has sku/id AND name AND price
        has_id    = "sku" in obj or "product_id" in obj
        has_name  = "name" in obj or "title" in obj or "productName" in obj
        has_price = "price" in obj or "sale_price" in obj or "now" in obj
        if has_id and has_name and has_price:
            return [obj]
        out = []
        for v in obj.values():
            out.extend(_walk(v, depth + 1))
        return out

    def _save_items(items):
        count = 0
        for item in items:
            try:
                src = item.get("_source", item)
                parsed = _process_noon_item(src, default_cat, region_path, currency)
                if not parsed:
                    continue
                title, cp, op, disc, img, purl, rating, rc, cat = parsed
                kb = check_price_history(product_url=purl, current_price=cp,
                                         original_price=op, title=title,
                                         site=marketplace_country)
                deal = build_deal(title=title, site=marketplace_country,
                                  site_display=site_display, category=cat,
                                  current_price=cp, original_price=op,
                                  discount=disc, image_url=img, product_url=purl,
                                  rating=rating, review_count=rc,
                                  kanbkam_result=kb, currency=currency)
                save_deal(deal)
                count += 1
            except Exception:
                continue
        return count

    # Method 0: JSON-LD structured data probe (log presence for debugging)
    _ld_probe_soup = BeautifulSoup(content[:50000], "lxml")
    _ld_scripts = _ld_probe_soup.find_all("script", attrs={"type": "application/ld+json"})
    if _ld_scripts:
        try:
            _ld0 = json.loads(_ld_scripts[0].string or "{}")
            print(f"    [noon parse] JSON-LD found: {len(_ld_scripts)} scripts, "
                  f"type={_ld0.get('@type','?')} keys={list(_ld0.keys())[:5]}")
        except Exception:
            print(f"    [noon parse] JSON-LD found: {len(_ld_scripts)} scripts (parse failed)")
    else:
        print(f"    [noon parse] JSON-LD: none found")

    # Method A: __NEXT_DATA__
    nd = extract_next_data(content)
    print(f"    [noon parse] content={len(content)}B nd={'yes' if nd else 'no'}")
    if nd:
        pp = nd.get("props", {}).get("pageProps", {})
        hits = (
            pp.get("catalog", {}).get("hits", []) or
            pp.get("initialState", {}).get("catalog", {}).get("hits", []) or
            pp.get("hits", []) or
            pp.get("products", []) or
            pp.get("items", []) or
            nd.get("props", {}).get("initialState", {}).get("catalog", {}).get("hits", []) or
            _walk(nd)
        )
        print(f"    [noon parse] Method A hits={len(hits)}")
        if hits:
            saved += _save_items(hits)
            if saved:
                return saved

    # Method B: regex JSON patterns
    b_found = 0
    for pattern in [
        r'window\.__INITIAL_STATE__\s*=\s*({.+?});\s*(?:window|</script>)',
        r'"products"\s*:\s*(\[.+?\])',
        r'"hits"\s*:\s*\{"hits"\s*:\s*(\[.+?\])',
        r'"catalog"\s*:\s*\{[^}]*"hits"\s*:\s*(\[.+?\])',
    ]:
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            continue
        try:
            raw = m.group(1)
            data = json.loads(raw) if raw.startswith('{') else None
            items = (
                (data.get("catalog", {}).get("hits", []) or
                 data.get("hits", {}).get("hits", []) or
                 data.get("products", []))
                if data else json.loads(raw)
            )
            b_found = len(items) if items else 0
            if items:
                saved += _save_items(items)
                if saved:
                    return saved
        except Exception:
            continue
    print(f"    [noon parse] Method B items={b_found}")

    # Method C: HTML product cards (rendered DOM)
    soup = BeautifulSoup(content, "lxml")
    blocks = (
        soup.find_all("div", attrs={"data-qa": "product-block"}) or
        soup.find_all("div", attrs={"data-qa": "product-container"}) or
        soup.find_all("div", attrs={"data-testid": "product-block"}) or
        soup.find_all("div", attrs={"data-testid": "product-card"}) or
        soup.find_all("div", class_=lambda c: c and any(
            k in str(c) for k in ("productContainer", "ProductCard", "product-card", "grid_item"))) or
        soup.find_all("article", class_=lambda c: c and "product" in str(c).lower())
    )
    for p in blocks:
        try:
            title_el = (p.find(attrs={"data-qa": "product-name"}) or
                        p.find(attrs={"data-testid": "product-name"}) or
                        p.find(class_=lambda c: c and "name" in str(c).lower()) or
                        p.find("h2") or p.find("p"))
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            price_el = (p.find(attrs={"data-qa": "price-now"}) or
                        p.find(attrs={"data-testid": "price"}) or
                        p.find(class_=lambda c: c and "price" in str(c).lower()))
            if not price_el:
                continue
            cp = clean_price(price_el.get_text())
            if cp < 50:
                continue
            orig_el = (p.find(attrs={"data-qa": "price-was"}) or
                       p.find("del") or p.find("s") or
                       p.find(class_=lambda c: c and ("was" in str(c).lower() or "old" in str(c).lower())))
            op = clean_price(orig_el.get_text()) if orig_el else cp
            if op < cp:
                op = cp
            disc = calculate_discount(op, cp)
            if disc < MIN_DISCOUNT:
                continue
            link_el = p.find("a", href=True)
            href = link_el["href"] if link_el else ""
            purl = ("https://www.noon.com" + href if href.startswith("/") else href)
            img_el = p.find("img")
            img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
            cat = detect_category(title) or default_cat
            kb = check_price_history(product_url=purl, current_price=cp,
                                     original_price=op, title=title,
                                     site=marketplace_country)
            deal = build_deal(title=title, site=marketplace_country,
                              site_display=site_display, category=cat,
                              current_price=cp, original_price=op,
                              discount=disc, image_url=img, product_url=purl,
                              kanbkam_result=kb, currency=currency)
            save_deal(deal)
            saved += 1
        except Exception:
            continue

    if saved:
        return saved

    # Method D: product link scan
    # Noon URL pattern: /region-lang/product-slug/SKU/p/?o=...
    # The SKU sits BEFORE /p/, not after — fix the regex accordingly.
    import re as _re
    noon_sku_re = _re.compile(r'/[A-Za-z0-9]{5,}/p/', _re.IGNORECASE)
    all_a_tags = soup.find_all("a", href=True)
    p_hrefs = [a["href"] for a in all_a_tags if "/p/" in (a.get("href") or "")]
    matched_a_tags = [a for a in all_a_tags if noon_sku_re.search(a.get("href", ""))]
    print(f"    [noon parse] Method D: total_a={len(all_a_tags)} p_links={len(p_hrefs)} regex_matched={len(matched_a_tags)}")
    if p_hrefs:
        print(f"    [noon parse] Method D p_href samples={p_hrefs[:3]}")

    seen_urls: set = set()
    _d_debug_count = 0

    for a_tag in matched_a_tags:
        try:
            # Canonical URL: strip ?o= query param
            href = a_tag["href"].split("?")[0]
            if not href.endswith("/"):
                href += "/"
            purl = "https://www.noon.com" + href if href.startswith("/") else href
            if purl in seen_urls:
                continue
            seen_urls.add(purl)

            # Cross-keyword SKU dedup: extract SKU (segment before /p/) and skip
            # if already processed in a previous keyword page this cycle.
            _sku_m = noon_sku_re.search(href)
            if _sku_m:
                _sku = _sku_m.group(0).split("/p/")[0].strip("/")
                if seen_skus is not None:
                    if _sku in seen_skus:
                        continue
                    seen_skus.add(_sku)

            # Check the <a> tag itself first, then walk up 6 levels.
            # Noon cards wrap all content (title + prices) inside the <a>.
            containers_to_check = []
            node = a_tag
            for _ in range(7):
                if node and getattr(node, "name", None):
                    containers_to_check.append(node)
                    node = node.parent
                else:
                    break

            _link_saved = False
            for _lvl, container in enumerate(containers_to_check):

                # Guard: if this container holds more than one product link
                # we've walked too far up and would bleed prices/titles across
                # neighbouring cards. Stop immediately.
                if len(container.find_all("a", href=noon_sku_re)) > 1:
                    break

                # ── Price extraction (two-stage) ───────────────────────────
                # Stage 1: data-qa price elements (reliable when JS rendered them)
                _cp_el = (
                    container.find(attrs={"data-qa": "product-price"}) or
                    container.find(attrs={"data-qa": "price-now"}) or
                    container.find(attrs={"data-qa": "selling-price"}) or
                    container.find(attrs={"data-qa": "price"})
                )
                _op_el = (
                    container.find(attrs={"data-qa": "product-old-price"}) or
                    container.find(attrs={"data-qa": "price-was"}) or
                    container.find(attrs={"data-qa": "old-price"}) or
                    container.find(attrs={"data-qa": "original-price"})
                )

                # ── Stage 1: data-qa price elements ───────────────────────
                # Validate ratio [1.15, 8.0] so spec numbers that end up in
                # price elements (e.g. "1400 RPM" in product-price, "59%"
                # discount badge) are rejected rather than saved as prices.
                # If Stage 1 finds elements but values fail validation,
                # fall through to Stage 2 text scan instead of hard-skipping.
                cp = op = None
                if _cp_el and _op_el:
                    _cp_v = clean_price(_cp_el.get_text(strip=True))
                    _op_v = clean_price(_op_el.get_text(strip=True))
                    if (_cp_v and _op_v and _cp_v >= 200 and _op_v > _cp_v
                            and 1.15 <= _op_v / _cp_v <= 8.0):
                        cp, op = _cp_v, _op_v
                    else:
                        print(f"    [noon parse] S1-reject href={href[:45]} "
                              f"cp={_cp_v} op={_op_v}")

                # ── Stage 2: title-excluded text scan (fallback) ───────────
                if cp is None:
                    # Strip title text so spec numbers embedded in model names
                    # ("83" in "83JG0095ED", "5600" from "DDR5 5600",
                    # "1400" from "1400 RPM", "128" from "128GB") are removed
                    # before we scan for price candidates.
                    title_el_excl = (
                        container.find(attrs={"data-qa": "product-name"}) or
                        container.find(attrs={"data-qa": "product-title"}) or
                        container.find("h1") or container.find("h2") or
                        container.find("h3") or container.find("p")
                    )
                    _title_excl = title_el_excl.get_text(" ", strip=True) if title_el_excl else ""
                    full_text = container.get_text(" ", strip=True)
                    price_text = full_text.replace(_title_excl, " ") if _title_excl else full_text

                    # Standalone number regex: non-alphanumeric boundary on both
                    # sides excludes "83J" (model code), "16G" (RAM), "144Hz".
                    all_nums = []
                    for _m in _re.finditer(
                        r'(?<![A-Za-z\d])([\d,]+(?:\.\d+)?)(?![A-Za-z\d])', price_text
                    ):
                        try:
                            _n = float(_m.group(1).replace(",", ""))
                            if 200 <= _n <= 500_000:
                                all_nums.append(_n)
                        except ValueError:
                            continue
                    all_nums = sorted(set(all_nums), reverse=True)

                    if len(all_nums) < 2:
                        continue

                    # op = largest number; find cp where ratio in [1.15, 8.0]:
                    #   < 1.15 → < ~13% off — not worth alerting
                    #   > 8.0  → > 87.5% off — almost always a misidentified spec
                    op = all_nums[0]
                    for _candidate in all_nums[1:]:
                        _ratio = op / _candidate if _candidate > 0 else 0
                        if 1.15 <= _ratio <= 8.0:
                            cp = _candidate
                            break

                    if cp is None:
                        if _d_debug_count < 3:
                            _d_debug_count += 1
                            print(f"    [noon parse] D-miss href={href[:50]} "
                                  f"nums={all_nums[:5]}")
                        continue

                # ── Title extraction ───────────────────────────────────────
                title_el = (
                    container.find(attrs={"data-qa": "product-name"}) or
                    container.find(attrs={"data-qa": "product-title"}) or
                    container.find("h1") or container.find("h2") or container.find("h3") or
                    container.find("p")
                )
                title = title_el.get_text(strip=True) if title_el else ""
                if not title or len(title) < 5 or len(title) > 300:
                    continue

                disc = calculate_discount(op, cp)
                # Detect category early so electronics can use a lower threshold
                cat = detect_category(title) or default_cat
                # Electronics (phones, laptops, TVs) are high-value — notify at 15%+
                # even though general threshold is 40%. A 15% off a 60,000 EGP laptop
                # saves 9,000 EGP which is highly relevant.
                _eff_min_discount = 15 if cat == "electronics" else MIN_DISCOUNT

                if _d_debug_count < 8:
                    _nlinks = len(container.find_all("a", href=noon_sku_re))
                    print(f"    [noon parse] D-debug lvl={_lvl} links={_nlinks} cat={cat} "
                          f"href={href[:45]} op={op} cp={cp} disc={disc}")

                if disc < _eff_min_discount:
                    if _d_debug_count < 5:
                        _d_debug_count += 1
                    break
                if not price_in_range(cp):
                    break

                img_el = container.find("img")
                img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                kb = check_price_history(product_url=purl, current_price=cp,
                                         original_price=op, title=title,
                                         site=marketplace_country)
                deal = build_deal(title=title, site=marketplace_country,
                                  site_display=site_display, category=cat,
                                  current_price=cp, original_price=op,
                                  discount=disc, image_url=img, product_url=purl,
                                  kanbkam_result=kb, currency=currency)
                save_deal(deal)
                saved += 1
                _link_saved = True
                break

            if not _link_saved and _d_debug_count < 5:
                _d_debug_count += 1

        except Exception as _de:
            print(f"    [noon parse] Method D exc: {_de}")
            continue

    print(f"    [noon parse] Method D (link scan) saved={saved}")
    return saved


def _scrape_noon_region(
    region_path="egypt-en",
    marketplace_country="noon_eg",
    site_display="Noon Egypt",
    currency="EGP",
    country_code="eg",
):
    """Scrape any Noon regional store. Called by the three wrappers below."""
    print(f"\n[NOON/{country_code.upper()}] Starting — {site_display}...")
    total = 0
    _seen_noon_skus: set = set()  # shared across all keyword pages to prevent duplicate SKUs

    def _noon_fetch(url):
        """
        Fetch strategy for Noon pages (tried in order until one works):
        1. scrape.do super=true (residential proxy + JS render) — most reliable
        2. scrape.do render=true (datacenter + JS render) — fallback
        3. ScraperAPI render_js=True — last resort
        """
        # Try scrape.do with residential super proxy first.
        if SCRAPEDO_TOKEN and not _scrapedo_dead:
            resp = fetch_with_scrapedo(url, render_js=True, country=country_code,
                                       super_proxy=True)
            if resp and len(resp.text or "") > 3000:
                print(f"  [NOON/{country_code.upper()}] scrape.do super OK ({len(resp.text)}b)")
                return resp
            # Fall back to regular scrape.do render
            resp = fetch_with_scrapedo(url, render_js=True, country=country_code,
                                       super_proxy=False)
            if resp and len(resp.text or "") > 3000:
                print(f"  [NOON/{country_code.upper()}] scrape.do render OK ({len(resp.text)}b)")
                return resp
            print(f"  [NOON/{country_code.upper()}] scrape.do blocked → trying ScraperAPI")
        else:
            # No scrape.do — try direct first
            resp = fetch_noon_direct(url, country_code)
            if resp and resp.status_code == 200 and len(resp.text or "") > 5000:
                print(f"  [NOON/{country_code.upper()}] direct OK ({len(resp.text)}b)")
                return resp
            print(f"  [NOON/{country_code.upper()}] direct blocked ({resp.status_code if resp else 'no resp'}) → ScraperAPI")
        resp2 = fetch_with_scraperapi(url, render_js=True, country=country_code)
        if resp2 and resp2.status_code == 200 and len(resp2.text or "") > 3000:
            print(f"  [NOON/{country_code.upper()}] ScraperAPI OK ({len(resp2.text)}b)")
            return resp2
        print(f"  [NOON/{country_code.upper()}] all methods blocked — 0 products expected")
        return resp2  # caller handles empty result

    # ── Phase 1: Deals / sale pages (server-side rendered, most reliable) ──
    deals_pages = [
        f"https://www.noon.com/{region_path}/sale/?limit=48&sort%5Bby%5D=discount_percent&sort%5Bdir%5D=desc",
        f"https://www.noon.com/{region_path}/offers/?limit=48&sort%5Bby%5D=discount_percent",
        f"https://www.noon.com/{region_path}/category/deals/?limit=48",
    ]
    for dp_url in deals_pages:
        try:
            resp = _noon_fetch(dp_url)
            if resp and resp.status_code == 200:
                n = _parse_noon_products(resp.text, "general", region_path, currency,
                                         marketplace_country, site_display, country_code,
                                         seen_skus=_seen_noon_skus)
                if n == 0:
                    _log_scraper_error(marketplace_country, dp_url,
                                       "0 products on deals page — HTML selector may have changed")
                print(f"  [NOON/{country_code.upper()}] Deals page: {n} deals")
                total += n
                time.sleep(3)
        except Exception as e:
            print(f"  [NOON/{country_code.upper()}] Deals page error: {e}")
            _log_scraper_error(marketplace_country, dp_url, str(e))

    # ── Phase 2: Category search terms ─────────────────────────────────────
    search_terms = [
        ("samsung galaxy",  "electronics"), ("iphone",     "electronics"),
        ("laptop",          "electronics"), ("headphones", "electronics"),
        ("tv",              "electronics"), ("tablet",     "electronics"),
        ("nike shoes",      "fashion"),     ("dress",      "fashion"),
        ("perfume",         "fashion"),     ("handbag",    "fashion"),
        ("refrigerator",    "home"),        ("washing machine", "home"),
        ("air conditioner", "home"),        ("microwave",  "home"),
        ("skincare",        "beauty"),      ("makeup",     "beauty"),
        ("hair dryer",      "beauty"),      ("vitamins",   "beauty"),
        ("gym equipment",   "sports"),      ("protein",    "sports"),
    ]

    for term, default_cat in search_terms:
        try:
            url = f"https://www.noon.com/{region_path}/search/?q={term.replace(' ', '+')}&limit=48&sort%5Bby%5D=discount&sort%5Bdir%5D=desc"
            # _noon_fetch handles direct → ScraperAPI render_js=True cascade
            resp = _noon_fetch(url)
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue
            n = _parse_noon_products(resp.text, default_cat, region_path, currency,
                                     marketplace_country, site_display, country_code,
                                     seen_skus=_seen_noon_skus)
            print(f"  [NOON/{country_code.upper()}] '{term}': {n} deals")
            total += n
            time.sleep(2)

        except Exception as e:
            print(f"  [NOON/{country_code.upper()}] Error '{term}': {e}")
            time.sleep(3)

    print(f"[NOON/{country_code.upper()}] Done. {total} deals.")
    return total


def scrape_noon():
    """Noon Egypt (EGP)."""
    return _scrape_noon_region()

def scrape_noon_ae():
    """Noon UAE (AED)."""
    return _scrape_noon_region("uae-en", "noon_ae", "Noon UAE", "AED", "ae")

def scrape_noon_sa():
    """Noon Saudi Arabia (SAR)."""
    return _scrape_noon_region("saudi-en", "noon_sa", "Noon Saudi Arabia", "SAR", "sa")


# ─────────────────────────────────────────────────────
# HYPERONE — ScraperAPI + HTML fallback
# ─────────────────────────────────────────────────────
def scrape_hyperone():
    print("\n[HYPERONE] Starting...")
    total = 0
    pages = [
        ("https://www.hyperone.com.eg/offers/",                          "general"),
        ("https://www.hyperone.com.eg/specials/",                        "general"),
        ("https://www.hyperone.com.eg/sale/",                            "general"),
        ("https://www.hyperone.com.eg/electronics/",                     "electronics"),
        ("https://www.hyperone.com.eg/home-appliances/",                 "home"),
        ("https://www.hyperone.com.eg/mobiles-and-accessories/",         "electronics"),
        ("https://www.hyperone.com.eg/phones/",                          "electronics"),
    ]

    hyperone_headers = get_headers()
    hyperone_headers["Referer"] = "https://www.hyperone.com.eg/"
    hyperone_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"

    for url, default_cat in pages:
        try:
            resp = None
            # Try direct first (HyperOne is a simpler Magento site, often no JS needed)
            try:
                resp = requests.get(url, headers=hyperone_headers, timeout=20)
                if resp.status_code == 404:
                    continue  # URL doesn't exist, skip silently
            except Exception:
                pass

            if not resp or resp.status_code != 200:
                resp = fetch_with_scraperapi(url, render_js=False, country="eg")
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("li",      class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("li",      class_=lambda c: c and "product" in str(c)) or
                soup.find_all("div",     class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("div",     class_=lambda c: c and "product" in str(c) and "item" in str(c)) or
                soup.find_all("div",     class_=lambda c: c and "product-card" in str(c)) or
                soup.find_all("article")
            )
            print(f"  [HYPERONE] {len(products)} products: {url}")

            for p in products:
                try:
                    title_el = (
                        p.find("h2") or p.find("h3") or
                        p.find(class_=lambda c: c and ("name" in str(c) or "title" in str(c)))
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    special_el = p.find(class_=lambda c: c and "special" in str(c) and "price" in str(c))
                    if special_el:
                        price_el = special_el.find("span", class_="price")
                    else:
                        price_el = (p.find("span", class_="price") or
                                    p.find(class_=lambda c: c and "price" in str(c) and "old" not in str(c)))
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50 or not price_in_range(current_price):
                        continue

                    orig_el = (
                        p.find("span", class_=lambda c: c and "old" in str(c)) or
                        p.find("del") or p.find("s")
                    )
                    original_price = clean_price(orig_el.get_text()) if orig_el else current_price
                    if original_price < current_price:
                        original_price = current_price

                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    link_el     = p.find("a", href=True)
                    href        = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://www.hyperone.com.eg" + href

                    img_el    = p.find("img")
                    image_url = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                    cat       = detect_category(title) or default_cat

                    kb = check_price_history(
                        product_url=product_url, current_price=current_price,
                        original_price=original_price, title=title, site="hyperone_eg"
                    )

                    deal = build_deal(
                        title=title, site="hyperone_eg", site_display="HyperOne Egypt",
                        category=cat, current_price=current_price,
                        original_price=original_price, discount=discount,
                        image_url=image_url, product_url=product_url, kanbkam_result=kb
                    )
                    save_deal(deal)
                    total += 1

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  [HYPERONE] Error: {e}")
            time.sleep(5)

    print(f"[HYPERONE] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# SAHLA — API + ScraperAPI fallback
# ─────────────────────────────────────────────────────
def scrape_sahla():
    print("\n[SAHLA] Starting...")
    total = 0
    api_headers = {
        "Accept":       "application/json",
        "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }
    # Try multiple possible API base URLs for Sahla
    api_bases = [
        "https://sahlaapp.com/api/v2",
        "https://sahlaapp.com/api/v1",
        "https://api.sahlaapp.com/v1",
        "https://sahlaapp.com/api",
    ]
    endpoints_templates = [
        "/products?page=1&per_page=50&sort_by=discount&sort_order=desc",
        "/offers?page=1&per_page=50",
        "/deals?page=1&per_page=50",
    ]

    for base in api_bases:
        if total > 0:
            break
        for tmpl in endpoints_templates:
            endpoint = base + tmpl
            try:
                resp = requests.get(endpoint, headers=api_headers, timeout=12)
                if resp.status_code == 200:
                    try:
                        data  = resp.json()
                        items = data.get("data", data.get("products", data.get("offers", data.get("items", data.get("deals", [])))))
                        if not isinstance(items, list):
                            continue
                        for item in items:
                            try:
                                title = item.get("name", "") or item.get("title", "")
                                if not title:
                                    continue
                                cp = clean_price(str(item.get("sale_price", item.get("price", item.get("discounted_price", 0)))))
                                op = clean_price(str(item.get("original_price", item.get("price", item.get("regular_price", cp)))))
                                if cp < 50 or not price_in_range(cp):
                                    continue
                                if op < cp:
                                    op = cp
                                disc = calculate_discount(op, cp)
                                if disc < MIN_DISCOUNT:
                                    continue
                                img  = item.get("image", item.get("thumbnail", item.get("image_url", "")))
                                pid  = item.get("id", item.get("slug", ""))
                                purl = f"{base.split('/api')[0]}/product/{pid}"
                                rating = float(item.get("rating", 0) or 0)
                                rc     = int(item.get("reviews_count", item.get("review_count", 0)) or 0) or None
                                cat    = detect_category(title)

                                kb = check_price_history(
                                    product_url=purl, current_price=cp,
                                    original_price=op, title=title, site="sahla_eg"
                                )

                                deal = build_deal(
                                    title=title, site="sahla_eg", site_display="Sahla Egypt",
                                    category=cat, current_price=cp, original_price=op,
                                    discount=disc, image_url=img or "", product_url=purl,
                                    rating=rating, review_count=rc, kanbkam_result=kb
                                )
                                save_deal(deal)
                                total += 1
                            except Exception:
                                continue
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [SAHLA] API error {endpoint}: {e}")

    # HTML fallback — try direct web page scraping
    if total == 0:
        sahla_pages = [
            "https://sahlaapp.com/offers",
            "https://sahlaapp.com/deals",
            "https://sahlaapp.com/products?sort=discount",
        ]
        for url in sahla_pages:
            try:
                resp = fetch_with_scraperapi(url, render_js=False, country="eg")
                if not resp or resp.status_code != 200:
                    resp = fetch_direct(url)
                if not resp or resp.status_code != 200:
                    continue

                soup     = BeautifulSoup(resp.content, "lxml")
                products = soup.find_all(class_=lambda c: c and "product" in str(c).lower())
                for p in products:
                    try:
                        title_el = (
                            p.find("h2") or p.find("h3") or
                            p.find(class_=lambda c: c and "name" in str(c).lower())
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        price_el = p.find(class_=lambda c: c and "price" in str(c).lower() and "old" not in str(c).lower())
                        if not price_el:
                            continue
                        cp = clean_price(price_el.get_text())
                        if cp < 50 or not price_in_range(cp):
                            continue

                        orig_el = p.find("del") or p.find(class_=lambda c: c and "old" in str(c).lower())
                        op = clean_price(orig_el.get_text()) if orig_el else cp
                        if op < cp:
                            op = cp
                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue

                        link_el = p.find("a", href=True)
                        href    = link_el["href"] if link_el else ""
                        purl    = href if href.startswith("http") else "https://sahlaapp.com" + href

                        img_el = p.find("img")
                        img    = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                        cat    = detect_category(title)

                        kb = check_price_history(
                            product_url=purl, current_price=cp,
                            original_price=op, title=title, site="sahla_eg"
                        )

                        deal = build_deal(
                            title=title, site="sahla_eg", site_display="Sahla Egypt",
                            category=cat, current_price=cp, original_price=op,
                            discount=disc, image_url=img, product_url=purl, kanbkam_result=kb
                        )
                        save_deal(deal)
                        total += 1
                    except Exception:
                        continue

                if total > 0:
                    break  # Got results from this page, no need to try others
            except Exception as e:
                print(f"  [SAHLA] HTML error {url}: {e}")

    print(f"[SAHLA] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# CUSTOM SOURCES — Added via admin dashboard
# ─────────────────────────────────────────────────────
def scrape_custom_sources():
    print("\n[CUSTOM] Checking admin-added sources...")
    total = 0
    try:
        sources = [doc.to_dict() for doc in db.collection("admin").stream()]
        active  = [s for s in sources if s.get("status") == "active" and s.get("site_url")]
        known   = {"amazon.eg", "noon.com", "jumia.com.eg", "btech.com",
                   "carrefouregypt.com", "sharafdg.com", "hyperone.com.eg", "sahlaapp.com"}
        custom  = [s for s in active if not any(d in s.get("site_url", "") for d in known)]

        if not custom:
            print("  No custom sources to scrape.")
            return 0

        for source in custom:
            site_name = source.get("site_name", "Unknown")
            site_url  = source.get("site_url", "")
            site_id   = source.get("id", site_name.lower().replace(" ", "_"))
            print(f"\n  Scraping: {site_name} ({site_url})")

            resp = fetch_direct(site_url)
            products_found = 0

            if resp and resp.status_code == 200:
                soup     = BeautifulSoup(resp.content, "lxml")
                products = (
                    soup.find_all("div",     class_=lambda c: c and "product" in str(c).lower() and "item" in str(c).lower()) or
                    soup.find_all("article", class_=lambda c: c and "product" in str(c).lower()) or
                    soup.find_all("li",      class_=lambda c: c and "product" in str(c).lower())
                )

                if not products:
                    print(f"    No products in direct fetch — trying ScraperAPI...")
                    resp = fetch_with_scraperapi(site_url, render_js=False, country="eg")
                    if resp and resp.status_code == 200:
                        soup     = BeautifulSoup(resp.content, "lxml")
                        products = (
                            soup.find_all("div",     class_=lambda c: c and "product" in str(c).lower()) or
                            soup.find_all("article") or
                            soup.find_all("li",      class_=lambda c: c and "item" in str(c).lower())
                        )

                for product in products[:50]:
                    try:
                        title_el = (
                            product.find("h2") or product.find("h3") or
                            product.find(class_=lambda c: c and ("name" in str(c) or "title" in str(c)))
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        price_el = product.find(class_=lambda c: c and "price" in str(c) and "old" not in str(c))
                        if not price_el:
                            continue
                        cp = clean_price(price_el.get_text())
                        if cp < 50 or not price_in_range(cp):
                            continue

                        orig_el = product.find("del") or product.find(class_=lambda c: c and "old" in str(c))
                        op = clean_price(orig_el.get_text()) if orig_el else cp
                        if op < cp:
                            op = cp

                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue

                        link_el = product.find("a", href=True)
                        href    = link_el["href"] if link_el else ""
                        purl    = href if href.startswith("http") else site_url.rstrip("/") + "/" + href.lstrip("/")

                        img_el = product.find("img")
                        img    = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                        cat    = detect_category(title)

                        kb = check_price_history(
                            product_url=purl, current_price=cp,
                            original_price=op, title=title, site=site_id
                        )

                        deal = build_deal(
                            title=title, site=site_id, site_display=site_name,
                            category=cat, current_price=cp, original_price=op,
                            discount=disc, image_url=img, product_url=purl, kanbkam_result=kb
                        )
                        save_deal(deal)
                        total += 1
                        products_found += 1
                    except Exception:
                        continue

            try:
                docs = db.collection("admin").where("site_url", "==", site_url).limit(1).get()
                for doc in docs:
                    doc.reference.update({"last_scraped": now_iso(), "last_count": products_found})
            except Exception:
                pass

            print(f"  {site_name}: {products_found} deals")
            time.sleep(3)

    except Exception as e:
        print(f"  Custom sources error: {e}")

    print(f"[CUSTOM] Done. {total} deals.")
    return total


# ─────────────────────────────────────────────────────
# ANALYTICS UPDATE
# ─────────────────────────────────────────────────────
def update_analytics():
    """
    Write lightweight analytics using the scraper_health cycle totals.
    We deliberately avoid streaming the full deals/users collections here
    to prevent thousands of Firestore reads every scrape cycle.
    The admin dashboard stats endpoint (server.py) handles full stats with
    its own 5-minute cache.
    """
    try:
        health_doc = db.collection("scraper_health").document("latest").get()
        cycle = {}
        if health_doc.exists:
            cycle = health_doc.to_dict().get("cycle", {})
        cycle_total = sum(cycle.values())

        db.collection("analytics").document("summary").set({
            "last_scrape_cycle_deals": cycle_total,
            "last_scrape_site_counts": cycle,
            "last_updated": now_iso(),
        }, merge=True)

        print(f"  Analytics: cycle total {cycle_total} deals (lightweight write)")
    except Exception as e:
        print(f"  Analytics error: {e}")


# ─────────────────────────────────────────────────────
# MAIN CYCLE
# ─────────────────────────────────────────────────────
import threading as _threading
_scrape_lock = _threading.Lock()

def run_scraper():
    if not _scrape_lock.acquire(blocking=False):
        print("  [run_scraper] cycle already in progress — skipping duplicate trigger")
        return
    try:
        _run_scraper_inner()
    finally:
        _scrape_lock.release()


def _run_scraper_inner():
    if not check_scraper_control():
        return

    print(f"\n{'=' * 62}")
    print(f"  SCRAPE CYCLE: {now_str()}")
    print(f"  Amazon: HTML keyword scan via scrape.do (RapidAPI disabled — free plan 403)")
    if SCRAPER_API_KEY:
        print(f"  ScraperAPI: ACTIVE (fallback for Noon/Jumia)")
    else:
        print(f"  ScraperAPI: NOT SET")
    if MIN_PRICE > 0 or MAX_PRICE < 9999999:
        print(f"  Price filter: EGP {MIN_PRICE:,.0f} – EGP {MAX_PRICE:,.0f}")
    print(f"{'=' * 62}")

    total = 0
    load_disabled_sources()
    if _disabled_sources:
        print(f"  Disabled sources: {', '.join(sorted(_disabled_sources))}")

    def run(key, fn):
        nonlocal total
        if not is_source_enabled(key):
            print(f"\n[{key.upper()}] ⏸ disabled by admin — skipping")
            _health.record(key, 0)
            return
        try:
            n = fn()
            _health.record(key, n)
            total += n
        except Exception as e:
            print(f"❌ [{key.upper()}]: {e}")
            _health.record(key, 0)

    # ── Egypt ────────────────────────────────────────────────────────────────
    run("amazon_eg",     scrape_amazon)
    run("jumia_eg",      scrape_jumia)
    run("btech_eg",      scrape_btech)
    run("carrefour_eg",  scrape_carrefour)
    run("sharaf_dg_eg",  scrape_sharaf_dg)
    run("hyperone_eg",   scrape_hyperone)
    run("sahla_eg",      scrape_sahla)
    run("noon_eg",       scrape_noon)

    # ── UAE ──────────────────────────────────────────────────────────────────
    run("amazon_ae",     scrape_amazon_ae)
    run("noon_ae",       scrape_noon_ae)
    run("sharaf_dg_ae",  lambda: 0)   # placeholder — not yet implemented

    # ── Saudi Arabia ─────────────────────────────────────────────────────────
    run("amazon_sa",     scrape_amazon_sa)
    run("noon_sa",       scrape_noon_sa)

    # ── Custom & analytics ───────────────────────────────────────────────────
    n = scrape_custom_sources(); total += n

    update_analytics()
    _health.flush()   # write health summary + send FCM alert if anything broke

    # ── Purge deals that slipped through with wrong prices ────────────────────
    _purge_bad_deals()

    # ── Send deal notifications to users ─────────────────────────────────────
    # _new_deals_this_run was populated by save_deal() for every brand-new deal.
    print(f"\n  [FCM-DEALS] New deals this cycle: {len(_new_deals_this_run)}")
    _notify_new_deals(_new_deals_this_run)
    _new_deals_this_run.clear()  # reset for next cycle

    _cycle_end = now_str()
    print(f"\n{'=' * 62}")
    print(f"  CYCLE COMPLETE: {_cycle_end}")
    print(f"  TOTAL DEALS THIS CYCLE: {total}")
    print(f"  NEW DEALS NOTIFIED:     {len(_new_deals_this_run)}")
    print(f"  PROXY: scrape.do={'dead' if _scrapedo_dead else ('active' if SCRAPEDO_TOKEN else 'not set')}")
    print(f"  Next cycle in: {INTERVAL} min")
    print(f"{'=' * 62}\n")


def _purge_bad_deals():
    """
    Delete Firestore deals where the stored prices are clearly wrong:
    - current_price < 200 (spec number like "59" or "128" saved as price)
    - original_price / current_price > 8 (ratio above 8× — e.g. 1400 RPM case)
    - current_price > original_price (inverted prices)
    Runs at end of each scraper cycle to clean up any garbage that slipped through.
    """
    try:
        docs = list(db.collection("deals").stream())
        removed = 0
        for d in docs:
            data = d.to_dict() or {}
            cp = float(data.get("current_price") or 0)
            op = float(data.get("original_price") or 0)
            bad = False
            reason = ""
            if cp < 200:
                bad = True
                reason = f"cp={cp} below 200 floor"
            elif op > 0 and cp > 0 and op / cp > 8.0:
                bad = True
                reason = f"ratio={op/cp:.1f} (op={op} cp={cp}) exceeds 8×"
            elif cp > 0 and op > 0 and cp > op:
                bad = True
                reason = f"cp={cp} > op={op} (inverted)"
            if bad:
                print(f"  [PURGE] Deleting bad deal {d.id[:16]}… {reason}")
                db.collection("deals").document(d.id).delete()
                removed += 1
        if removed:
            print(f"  [PURGE] Removed {removed} bad deal(s)")
        else:
            print(f"  [PURGE] All {len(docs)} deals look clean")
    except Exception as e:
        print(f"  [PURGE] Error: {e}")


if __name__ == "__main__":
    print("DealHunter Egypt Scraper v7 FIXED")
    print(f"Stores: Amazon EG/AE/SA + Noon EG/AE/SA + Jumia + B.Tech + Carrefour + Sharaf DG + HyperOne + Sahla")
    print(f"Fake check: Kanbkam (fixed URL) + Safqa (rebuilt)")
    print(f"Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min")
    if MIN_PRICE > 0 or MAX_PRICE < 9999999:
        print(f"Price filter: EGP {MIN_PRICE:,.0f} – EGP {MAX_PRICE:,.0f}")
    print("Scraper started, waiting for first cycle...")
    print()
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)
