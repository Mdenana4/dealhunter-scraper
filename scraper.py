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
INTERVAL        = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 60))
SCRAPER_API_KEY = (
    os.getenv("SCRAPER_API_KEY") or
    os.getenv("SCRAPERAPI_KEY") or
    os.getenv("SCRAPER_KEY") or
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
    if re.search(r'dress|shirt|shoes|bag|perfume|jeans|jacket|sneaker|sandal|handbag|wallet|belt|hat|cap|suit|blouse|skirt|coat|boots|polo|t-shirt|tshirt|underwear|socks|scarf|glasses|sunglasses|leggings|hoodie|sweatshirt|bra|swimsuit', t):
        return "fashion"
    if re.search(r'sofa|chair|bed|table|lamp|kitchen|blender|cookware|vacuum|air.?condition|refrigerator|washing.?machine|oven|microwave|curtain|pillow|mattress|shelf|cabinet|wardrobe|fan|heater|iron|kettle|toaster|coffee.?maker|air.?fryer|pressure.?cooker|dishwasher|water.?filter', t):
        return "home"
    if re.search(r'cream|serum|shampoo|makeup|skincare|moisturizer|lotion|vitamin|supplement|face.?wash|nail|lipstick|foundation|mascara|toner|sunscreen|body.?wash|deodorant|cologne|hair.?dryer|straightener|razor|trimmer', t):
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
    return "general"


# ─────────────────────────────────────────────────────
# SCRAPERAPI
# ─────────────────────────────────────────────────────
def extract_next_data(html_text):
    """Extract __NEXT_DATA__ JSON embedded in Next.js pages."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>\s*({.+?})\s*</script>', html_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


_SCRAPERAPI_EXHAUSTED = False  # set True when monthly quota gone


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


def fetch_with_scraperapi(url, render_js=True, country="eg"):
    global _SCRAPERAPI_EXHAUSTED
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
    try:
        resp = requests.get(
            f"https://{_RAPIDAPI_AMAZON_HOST}/search",
            headers=_RAPIDAPI_HEADERS,
            params={
                "query":        query,
                "page":         page,
                "country":      country,
                "sort_by":           "RELEVANCE",
                "discount_only":     "true",
                "product_condition": "ALL",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"    RapidAPI [{country}] '{query}': HTTP {resp.status_code}")
            return 0

        data = resp.json()
        products = (data.get("data") or {}).get("products") or []
        saved = 0

        for p in products:
            try:
                title = (p.get("product_title") or "").strip()
                if not title or len(title) < 5:
                    continue

                asin = p.get("asin", "")
                product_url = p.get("product_url") or (
                    f"https://www.amazon.{country.lower()}/dp/{asin}" if asin else ""
                )
                if not product_url:
                    continue

                # Price — API returns strings like "EGP 15,999" or "15,999.00"
                current_price  = clean_price(str(p.get("product_price") or 0))
                original_price = clean_price(str(p.get("product_original_price") or 0))
                if current_price < 1:
                    continue
                if original_price < current_price:
                    original_price = current_price

                # Discount — API returns "-43%" / "43%" / "43" / integer
                disc_raw = (
                    p.get("discount_percent") or
                    p.get("product_discount") or
                    p.get("savings_percent") or
                    ""
                )
                if disc_raw:
                    try:
                        discount = int(re.sub(r"[^\d]", "", str(disc_raw)))
                    except Exception:
                        discount = calculate_discount(original_price, current_price)
                else:
                    discount = calculate_discount(original_price, current_price)

                # Back-calculate original price from badge discount if missing
                if discount >= MIN_DISCOUNT and original_price <= current_price:
                    original_price = round(current_price / (1 - discount / 100))
                # If still no discount signal, skip (discount_only=true should prevent this)
                if discount < MIN_DISCOUNT:
                    continue

                if currency == "EGP" and not price_in_range(current_price):
                    continue

                image_url = (
                    p.get("product_photo") or
                    p.get("thumbnail") or
                    p.get("product_image") or ""
                )
                try:
                    rating = float(p.get("product_star_rating") or 0)
                except Exception:
                    rating = 0.0
                rc_raw = p.get("product_num_ratings") or p.get("product_num_offers")
                try:
                    review_count = int(str(rc_raw).replace(",", "")) if rc_raw else None
                except Exception:
                    review_count = None

                cat = detect_category(title) or default_cat

                print(f"    [API/{country}] [{discount}%] {title[:40]}...")
                kb = check_price_history(
                    asin=asin,
                    product_url=product_url,
                    current_price=current_price,
                    original_price=original_price,
                    title=title,
                    site=marketplace_country,
                )
                time.sleep(0.3)

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
                save_deal(deal)
                saved += 1
            except Exception:
                continue

        return saved

    except Exception as e:
        print(f"    RapidAPI [{country}] '{query}' error: {e}")
        return 0


def _rapidapi_amazon_deals(country, marketplace_country, site_display, currency):
    """Fetch the Amazon Deals page via RapidAPI. Returns count."""
    total = 0
    try:
        for offset in (0, 50):
            resp = requests.get(
                f"https://{_RAPIDAPI_AMAZON_HOST}/deals-and-offers",
                headers=_RAPIDAPI_HEADERS,
                params={"country": country, "offset": offset, "limit": 50},
                timeout=30,
            )
            if resp.status_code != 200:
                break
            data  = resp.json()
            deals = (
                (data.get("data") or {}).get("deals") or
                (data.get("data") or {}).get("products") or
                data.get("deals") or []
            )
            if not deals:
                break

        for p in deals:
            try:
                title = (
                    p.get("deal_title") or p.get("product_title") or
                    p.get("title") or ""
                ).strip()
                if not title or len(title) < 5:
                    continue

                current_price  = clean_price(str(p.get("deal_price") or p.get("product_price") or 0))
                original_price = clean_price(str(p.get("original_price") or p.get("list_price") or 0))
                if current_price < 1:
                    continue
                if original_price < current_price:
                    original_price = current_price

                discount = calculate_discount(original_price, current_price)
                disc_raw = p.get("discount_percent") or p.get("savings_percent") or ""
                if disc_raw:
                    try:
                        discount = int(re.sub(r"[^\d]", "", str(disc_raw)))
                    except Exception:
                        pass
                if discount < MIN_DISCOUNT:
                    continue

                if currency == "EGP" and not price_in_range(current_price):
                    continue

                asin        = p.get("asin", "")
                product_url = p.get("product_url") or p.get("deal_url") or (
                    f"https://www.amazon.{country.lower()}/dp/{asin}" if asin else ""
                )
                image_url   = p.get("product_photo") or p.get("deal_image") or ""
                cat         = detect_category(title)

                print(f"    [DEALS/{country}] [{discount}%] {title[:40]}...")
                kb = check_price_history(
                    asin=asin, product_url=product_url,
                    current_price=current_price, original_price=original_price,
                    title=title, site=marketplace_country,
                )
                deal = build_deal(
                    title=title, site=marketplace_country, site_display=site_display,
                    category=cat, current_price=current_price, original_price=original_price,
                    discount=discount, image_url=image_url, product_url=product_url,
                    asin=asin, kanbkam_result=kb, currency=currency,
                )
                save_deal(deal)
                total += 1
                time.sleep(0.3)
            except Exception:
                continue

    except Exception as e:
        print(f"    RapidAPI deals [{country}] error: {e}")
    return total


def _rapidapi_amazon_category(country, category_id, default_cat,
                               marketplace_country, site_display, currency):
    """Fetch best-sellers/sale for a category, filter for MIN_DISCOUNT. Returns count."""
    total = 0
    for page in (1, 2):
        try:
            resp = requests.get(
                f"https://{_RAPIDAPI_AMAZON_HOST}/search",
                headers=_RAPIDAPI_HEADERS,
                params={
                    "query":         f"discount sale {default_cat}",
                    "page":          page,
                    "country":       country,
                    "category_id":   category_id,
                    "sort_by":       "RELEVANCE",
                    "discount_only": "true",
                },
                timeout=30,
            )
            if resp.status_code != 200:
                break
            products = (resp.json().get("data") or {}).get("products") or []
            for p in products:
                try:
                    title = (p.get("product_title") or "").strip()
                    if not title or len(title) < 5:
                        continue
                    asin        = p.get("asin", "")
                    product_url = p.get("product_url") or (
                        f"https://www.amazon.{country.lower()}/dp/{asin}" if asin else "")
                    if not product_url:
                        continue
                    cp = clean_price(str(p.get("product_price") or 0))
                    op = clean_price(str(p.get("product_original_price") or 0))
                    if cp < 1:
                        continue
                    if op < cp:
                        op = cp
                    disc_raw = (p.get("discount_percent") or p.get("savings_percent") or "")
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
                    cat = detect_category(title) or default_cat
                    image_url = p.get("product_photo") or p.get("thumbnail") or ""
                    try:
                        rating = float(p.get("product_star_rating") or 0)
                    except Exception:
                        rating = 0.0
                    print(f"    [CAT/{country}/{category_id}] [{disc}%] {title[:38]}...")
                    kb = check_price_history(
                        asin=asin, product_url=product_url,
                        current_price=cp, original_price=op,
                        title=title, site=marketplace_country,
                    )
                    time.sleep(0.3)
                    deal = build_deal(
                        title=title, site=marketplace_country, site_display=site_display,
                        category=cat, current_price=cp, original_price=op,
                        discount=disc, image_url=image_url, product_url=product_url,
                        rating=rating, asin=asin, kanbkam_result=kb, currency=currency,
                    )
                    save_deal(deal)
                    total += 1
                except Exception:
                    continue
            time.sleep(2)
        except Exception as e:
            print(f"    [CAT/{country}] {category_id} page {page} error: {e}")
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
    print(f"  Deals endpoint: {n} deals")
    total += n
    time.sleep(3)

    # Phase 2: keyword search (discount_only=true, 2 pages each)
    for term, default_cat in _AMAZON_SEARCH_TERMS:
        for page in (1, 2):
            n = _rapidapi_amazon_search(
                term, country, default_cat,
                marketplace_country, site_display, currency, page=page,
            )
            total += n
            time.sleep(2)

    # Phase 3: broad category search with discount filter
    for cat_id, default_cat in _AMAZON_CATEGORIES:
        n = _rapidapi_amazon_category(
            country, cat_id, default_cat,
            marketplace_country, site_display, currency,
        )
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
    """Scrape the Amazon deals page directly (40-80% off filter). Returns deal count."""
    # URL with 40-80% discount filter — same as the link the user provided
    deals_url = (
        f"https://www.{base_domain}/-/en/deals?"
        "discounts-widget=%22%7B%22state%22%3A%7B%22rangeRefinementFilters%22%3A"
        "%7B%22percentOff%22%3A%7B%22min%22%3A40%2C%22max%22%3A80%7D%7D%7D%2C"
        "%22version%22%3A1%7D%22"
    )
    print(f"\n[AMAZON/{country_code.upper()}] Scraping deals page...")
    total = 0

    for page_num in range(1, 4):  # pages 1–3
        try:
            url = deals_url if page_num == 1 else f"{deals_url}&page={page_num}"
            resp = fetch_with_scraperapi(url, render_js=False, country=country_code)
            if is_blocked_response(resp, min_length=5000):
                print(f"  Deals page {page_num}: blocked/empty (HTTP {resp.status_code if resp else 'no response'}) — skipping")
                _log_scraper_error(f"amazon_{country_code}", url, "Blocked/CAPTCHA response on deals page")
                break

            soup = BeautifulSoup(resp.content, "lxml")
            products = [
                p for p in soup.find_all("div", attrs={"data-asin": True})
                if p.get("data-asin", "").strip()
            ]
            if not products:
                print(f"  Deals page {page_num}: 0 products found — HTML structure may have changed")
                _log_scraper_error(f"amazon_{country_code}", url, "0 products parsed — selector may be broken")
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
                    if not title or len(title) < 6:
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

    for item in AMAZON_KEYWORDS:
        try:
            url = f"https://www.{base_domain}/s?k={item['k'].replace(' ', '+')}&language=en_AE"
            resp = fetch_with_scraperapi(url, render_js=False, country=country_code)
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
                    if not title or len(title) < 6:
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
                    save_deal(deal)
                    total += 1
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
    """Amazon Egypt — RapidAPI primary, HTML fallback."""
    if RAPIDAPI_KEY:
        return _scrape_amazon_via_api("EG", "amazon_eg", "Amazon Egypt", "EGP")
    print("\n[AMAZON/EG] No RAPIDAPI_KEY — falling back to HTML scraper (may be blocked)")
    total = _scrape_amazon_deals_page()
    total += _scrape_amazon_region()
    return total

def scrape_amazon_ae():
    """Amazon UAE — RapidAPI primary, HTML fallback."""
    if RAPIDAPI_KEY:
        return _scrape_amazon_via_api("AE", "amazon_ae", "Amazon UAE", "AED")
    print("\n[AMAZON/AE] No RAPIDAPI_KEY — falling back to HTML scraper (may be blocked)")
    total = _scrape_amazon_deals_page("amazon.ae", "amazon_ae", "Amazon UAE", "AED", "ae")
    total += _scrape_amazon_region("amazon.ae", "amazon_ae", "Amazon UAE", "AED", "ae")
    return total

def scrape_amazon_sa():
    """Amazon Saudi Arabia — RapidAPI primary, HTML fallback."""
    if RAPIDAPI_KEY:
        return _scrape_amazon_via_api("SA", "amazon_sa", "Amazon Saudi Arabia", "SAR")
    print("\n[AMAZON/SA] No RAPIDAPI_KEY — falling back to HTML scraper (may be blocked)")
    total = _scrape_amazon_deals_page("amazon.sa", "amazon_sa", "Amazon Saudi Arabia", "SAR", "sa")
    total += _scrape_amazon_region("amazon.sa", "amazon_sa", "Amazon Saudi Arabia", "SAR", "sa")
    return total


# ─────────────────────────────────────────────────────
# JUMIA EGYPT — Static HTML
# ─────────────────────────────────────────────────────
def scrape_jumia():
    print("\n[JUMIA] Starting...")
    total = 0
    pages = [
        ("https://www.jumia.com.eg/mlp-flash-sales/", "general"),
        ("https://www.jumia.com.eg/phones-tablets/?sort=discountPercent&type=lowest-price#catalog-listing", "electronics"),
        ("https://www.jumia.com.eg/electronics/?sort=discountPercent&type=lowest-price#catalog-listing", "electronics"),
        ("https://www.jumia.com.eg/fashion/?sort=discountPercent#catalog-listing", "fashion"),
        ("https://www.jumia.com.eg/home-office/?sort=discountPercent#catalog-listing", "home"),
        ("https://www.jumia.com.eg/sporting-goods/?sort=discountPercent#catalog-listing", "sports"),
        ("https://www.jumia.com.eg/beauty-perfumes/?sort=discountPercent#catalog-listing", "beauty"),
        ("https://www.jumia.com.eg/baby-products/?sort=discountPercent#catalog-listing", "toys"),
    ]

    for url, default_cat in pages:
        try:
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
                         site_display, country_code):
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
        soup.find_all("div", attrs={"data-testid": "product-block"}) or
        soup.find_all("div", class_=lambda c: c and any(
            k in str(c) for k in ("productContainer", "ProductCard", "product-card"))) or
        soup.find_all("article", class_=lambda c: c and "product" in str(c).lower())
    )
    for p in blocks:
        try:
            title_el = (p.find(attrs={"data-qa": "product-name"}) or
                        p.find(class_=lambda c: c and "name" in str(c).lower()) or
                        p.find("h2") or p.find("p"))
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            price_el = (p.find(attrs={"data-qa": "price-now"}) or
                        p.find(class_=lambda c: c and "price" in str(c).lower()))
            if not price_el:
                continue
            cp = clean_price(price_el.get_text())
            if cp < 50:
                continue
            orig_el = (p.find(attrs={"data-qa": "price-was"}) or
                       p.find("del") or
                       p.find(class_=lambda c: c and "was" in str(c).lower()))
            op = clean_price(orig_el.get_text()) if orig_el else cp
            if op < cp:
                op = cp
            disc = calculate_discount(op, cp)
            if disc < MIN_DISCOUNT:
                continue
            link_el = p.find("a", href=True)
            href = link_el["href"] if link_el else ""
            purl = ("https://www.noon.com" + href
                    if href.startswith("/") else href)
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

    def _noon_fetch(url):
        """Try direct first (free), fall back to ScraperAPI only if needed."""
        resp = fetch_noon_direct(url, country_code)
        if resp and resp.status_code == 200 and len(resp.text) > 5000:
            return resp
        return fetch_with_scraperapi(url, render_js=False, country=country_code)

    # ── Phase 1: Deals / sale pages (server-side rendered, most reliable) ──
    deals_pages = [
        f"https://www.noon.com/{region_path}/deals/?limit=48&sort%5Bby%5D=discount_percent&sort%5Bdir%5D=desc",
        f"https://www.noon.com/{region_path}/flash-sale/?limit=48",
        f"https://www.noon.com/{region_path}/sale/?limit=48&sort%5Bby%5D=discount_percent",
    ]
    for dp_url in deals_pages:
        try:
            resp = _noon_fetch(dp_url)
            if is_blocked_response(resp, min_length=3000):
                print(f"  [NOON/{country_code.upper()}] Deals page blocked — trying JS render")
                resp = fetch_with_scraperapi(dp_url, render_js=True, country=country_code)
            if resp and resp.status_code == 200:
                n = _parse_noon_products(resp.text, "general", region_path, currency,
                                         marketplace_country, site_display, country_code)
                if n == 0:
                    # Last resort: JS render
                    resp2 = fetch_with_scraperapi(dp_url, render_js=True, country=country_code)
                    if resp2 and resp2.status_code == 200:
                        n = _parse_noon_products(resp2.text, "general", region_path, currency,
                                                 marketplace_country, site_display, country_code)
                if n == 0:
                    _log_scraper_error(marketplace_country, dp_url, "0 products on deals page — selector may be broken")
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

            # Try direct first (free), then ScraperAPI, then JS render
            resp = _noon_fetch(url)
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue
            n = _parse_noon_products(resp.text, default_cat, region_path, currency,
                                     marketplace_country, site_display, country_code)
            if n == 0:
                resp2 = fetch_with_scraperapi(url, render_js=True, country=country_code)
                if resp2 and resp2.status_code == 200:
                    n = _parse_noon_products(resp2.text, default_cat, region_path, currency,
                                             marketplace_country, site_display, country_code)
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
                resp = fetch_with_scraperapi(url, render_js=True, country="eg")
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
                resp = fetch_with_scraperapi(url, render_js=True, country="eg")
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
                    resp = fetch_with_scraperapi(site_url, render_js=True, country="eg")
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
def run_scraper():
    if not check_scraper_control():
        return

    print(f"\n{'=' * 62}")
    print(f"  SCRAPE CYCLE: {now_str()}")
    if RAPIDAPI_KEY:
        print(f"  RapidAPI Amazon: ACTIVE (zero-block API mode for EG/AE/SA)")
    else:
        print(f"  RapidAPI Amazon: NOT SET — add RAPIDAPI_KEY in Railway Variables")
    if SCRAPER_API_KEY:
        print(f"  ScraperAPI: ACTIVE (JS rendering for Noon/HyperOne/Sahla)")
    else:
        print(f"  ScraperAPI: NOT SET — Noon may return 0 deals")
    if MIN_PRICE > 0 or MAX_PRICE < 9999999:
        print(f"  Price filter: EGP {MIN_PRICE:,.0f} – EGP {MAX_PRICE:,.0f}")
    print(f"{'=' * 62}")

    total = 0

    # ── Egypt ────────────────────────────────────────────────────────────────
    n = scrape_amazon();       _health.record("amazon_eg", n); total += n
    n = scrape_jumia();        _health.record("jumia_eg",  n); total += n
    n = scrape_btech();        _health.record("btech_eg",  n); total += n
    n = scrape_carrefour();    _health.record("carrefour_eg", n); total += n
    n = scrape_sharaf_dg();    _health.record("sharaf_dg_eg", n); total += n
    n = scrape_hyperone();     _health.record("hyperone_eg", n); total += n
    n = scrape_sahla();        _health.record("sahla_eg",  n); total += n

    # ── Noon Egypt (wrapped separately for safety) ───────────────────────────
    try:
        n = scrape_noon()
        _health.record("noon_eg", n)
        total += n
    except Exception as e:
        print(f"\n❌ [NOON/EG] CRITICAL ERROR: {e}", flush=True)
        import traceback; traceback.print_exc()
        _health.record("noon_eg", 0)

    # ── UAE ──────────────────────────────────────────────────────────────────
    try:
        n = scrape_amazon_ae(); _health.record("amazon_ae", n); total += n
    except Exception as e:
        print(f"❌ [AMAZON/AE]: {e}"); _health.record("amazon_ae", 0)
    try:
        n = scrape_noon_ae();   _health.record("noon_ae",   n); total += n
    except Exception as e:
        print(f"❌ [NOON/AE]: {e}");   _health.record("noon_ae", 0)

    # ── Saudi Arabia ─────────────────────────────────────────────────────────
    try:
        n = scrape_amazon_sa(); _health.record("amazon_sa", n); total += n
    except Exception as e:
        print(f"❌ [AMAZON/SA]: {e}"); _health.record("amazon_sa", 0)
    try:
        n = scrape_noon_sa();   _health.record("noon_sa",   n); total += n
    except Exception as e:
        print(f"❌ [NOON/SA]: {e}");   _health.record("noon_sa", 0)

    # ── Custom & analytics ───────────────────────────────────────────────────
    n = scrape_custom_sources(); total += n

    update_analytics()
    _health.flush()   # write health summary + send FCM alert if anything broke
    print(f"\n  TOTAL: {total} deals | Next in: {INTERVAL} min")
    print(f"{'=' * 62}\n")


if __name__ == "__main__":
    print("DealHunter Egypt Scraper v7 FIXED")
    print(f"Stores: Amazon EG/AE/SA + Noon EG/AE/SA + Jumia + B.Tech + Carrefour + Sharaf DG + HyperOne + Sahla")
    print(f"Fake check: Kanbkam (fixed URL) + Safqa (rebuilt)")
    print(f"Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min")
    if MIN_PRICE > 0 or MAX_PRICE < 9999999:
        print(f"Price filter: EGP {MIN_PRICE:,.0f} – EGP {MAX_PRICE:,.0f}")
    print()
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)
