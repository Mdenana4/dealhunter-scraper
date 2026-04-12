# DealHunter Egypt - Scraper v6
# Phase 1: Correct Rules A+B fake detection
# Phase 2: Jumia, B.Tech, Carrefour, Sharaf DG (static HTML)
# Phase 3: Noon, HyperOne, Sahla via ScraperAPI (JavaScript rendering)
# Universal: Any future site automatically tries ScraperAPI if standard fails
# Never changes existing working logic

import requests
import schedule
import time
import json
import hashlib
import os
import re
from dotenv import load_dotenv
from fake_checker import check_price_history
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", 40))
INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 3))
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")  # Free at scraperapi.com

# ─────────────────────────────────────────────────────
# FIREBASE (unchanged)
# ─────────────────────────────────────────────────────
print("Connecting to Firebase...")
firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    try:
        key_dict = json.loads(firebase_key_json)
        cred = credentials.Certificate(key_dict)
        print("Firebase key loaded from environment variable.")
    except Exception as e:
        print(f"ERROR: {e}")
        raise
elif os.path.exists("firebase-key.json"):
    cred = credentials.Certificate("firebase-key.json")
    print("Firebase key loaded from file.")
else:
    raise Exception("No Firebase key found.")

firebase_admin.initialize_app(cred)
db = firestore.client()
print("Connected to Firebase successfully!")

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
    """Extract float from any price string"""
    if not text:
        return 0.0
    text = str(text).replace(',', '').replace('EGP', '').replace('ج.م', '').replace('جنيه', '').replace('جنية', '').strip()
    text = re.sub(r'[^\d.]', '', text)
    try:
        return float(text)
    except:
        return 0.0

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
    elif re.search(r'dress|shirt|shoes|bag|perfume|jeans|jacket|sneaker|sandal|handbag|wallet|belt|hat|cap|suit|blouse|skirt|coat|boots|polo|t-shirt|tshirt|underwear|socks|scarf|glasses|sunglasses|leggings|hoodie|sweatshirt|bra|swimsuit', t):
        return "fashion"
    elif re.search(r'sofa|chair|bed|table|lamp|kitchen|blender|cookware|vacuum|air.?condition|refrigerator|washing.?machine|oven|microwave|curtain|pillow|mattress|shelf|cabinet|wardrobe|fan|heater|iron|kettle|toaster|coffee.?maker|air.?fryer|pressure.?cooker|dishwasher|water.?filter', t):
        return "home"
    elif re.search(r'cream|serum|shampoo|makeup|skincare|moisturizer|lotion|vitamin|supplement|face.?wash|nail|lipstick|foundation|mascara|toner|sunscreen|body.?wash|deodorant|cologne|hair.?dryer|straightener|razor|trimmer', t):
        return "beauty"
    elif re.search(r'gym|sport|fitness|yoga|bicycle|bike|football|tennis|treadmill|dumbbell|resistance.?band|protein|swimming|basketball|volleyball|badminton|weights|barbell|boxing', t):
        return "sports"
    elif re.search(r'toy|baby|kids|children|doll|lego|puzzle|infant|toddler|stroller|diaper|feeding|educational|board.?game|action.?figure', t):
        return "toys"
    elif re.search(r'car|auto|vehicle|tire|wheel|motor.?oil|engine|spare.?part|seat.?cover|dashboard|steering|wiper|exhaust', t):
        return "automotive"
    elif re.search(r'food|grocery|snack|drink|juice|rice|pasta|oil|sugar|coffee|tea|chocolate|biscuit|chips|sauce|spice|flour|bread|milk|cheese|yogurt|honey|jam|cereal|protein.?bar', t):
        return "grocery"
    elif re.search(r'book|novel|textbook|stationery|pen|notebook|pencil|magazine|dictionary|academic|study', t):
        return "books"
    return "general"

# ─────────────────────────────────────────────────────
# PHASE 3: SCRAPERAPI — Universal JS Rendering Solution
# Free tier: 5,000 requests/month at scraperapi.com
# Handles JavaScript, CAPTCHAs, and bot detection
# ─────────────────────────────────────────────────────
def fetch_with_scraperapi(url, render_js=True, country="eg"):
    """
    Fetch any URL through ScraperAPI.
    render_js=True runs a real browser and executes JavaScript.
    Falls back to direct fetch if no API key configured.
    """
    if not SCRAPER_API_KEY:
        # No API key — try direct fetch
        return fetch_direct(url)
    
    try:
        api_url = "http://api.scraperapi.com"
        params = {
            "api_key": SCRAPER_API_KEY,
            "url": url,
            "render": "true" if render_js else "false",
            "country_code": country,
            "premium": "false",
        }
        resp = requests.get(api_url, params=params, timeout=60)
        if resp.status_code == 200:
            return resp
        else:
            print(f"    ScraperAPI returned {resp.status_code} — trying direct fetch")
            return fetch_direct(url)
    except Exception as e:
        print(f"    ScraperAPI error: {e} — trying direct fetch")
        return fetch_direct(url)


def fetch_direct(url, mobile=False):
    """Standard direct HTTP fetch"""
    try:
        resp = requests.get(url, headers=get_headers(mobile=mobile), timeout=20)
        return resp
    except Exception as e:
        print(f"    Direct fetch error: {e}")
        return None

# ─────────────────────────────────────────────────────
# SCRAPER CONTROL (kill switch from admin dashboard)
# ─────────────────────────────────────────────────────
def check_scraper_control():
    try:
        doc = db.collection("scraper_control").document("status").get()
        if doc.exists:
            d = doc.to_dict()
            if d.get("status") == "paused":
                print(f"  ⏸️ Paused by admin. Resume: {d.get('resume_at','not set')}")
                return False
        return True
    except:
        return True

# ─────────────────────────────────────────────────────
# PHASE 1: KANBKAM — Rules A+B Fake Detection
# Rule A: Amazon "Was" > Kanbkam highest EVER → fake original price
# Rule B: Kanbkam lowest = highest = current → price never changed
# FAKE only when BOTH rules are true
# ─────────────────────────────────────────────────────
def check_kanbkam(asin, current_price, original_price, title):
    """
    Checks real price history on Kanbkam.com for any Amazon product.
    Applies Rules A+B correctly.
    """
    if not asin:
        return local_verdict(current_price, original_price)
    
    try:
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:50].strip('-')
        url = f"https://www.kanbkam.com/eg/ar/{slug}-{asin}"
        
        headers = get_headers()
        headers["Accept-Language"] = "ar-EG,ar;q=0.9"
        headers["Referer"] = "https://www.kanbkam.com/"
        
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            # Fallback to search
            resp = requests.get(
                f"https://www.kanbkam.com/eg/ar/search?q={asin}",
                headers=headers, timeout=15
            )
            if resp.status_code != 200:
                return local_verdict(current_price, original_price)

        soup = BeautifulSoup(resp.content, "lxml")
        text = soup.get_text(separator=" ")

        lowest_price = 0
        highest_price = 0

        # Try Arabic labels first
        lm = re.search(r'أقل\s*سعر[^\d]*(\d[\d,]*)', text)
        hm = re.search(r'أعلى\s*سعر[^\d]*(\d[\d,]*)', text)
        if lm:
            lowest_price = clean_price(lm.group(1))
        if hm:
            highest_price = clean_price(hm.group(1))

        # Fallback: extract all EGP prices from page
        if lowest_price == 0:
            prices = []
            for m in re.finditer(r'(\d[\d,]*)\s*(?:جنية|جنيه|EGP|ج\.م)', text):
                v = clean_price(m.group(1))
                if 10 < v < 500000:
                    prices.append(v)
            if prices:
                prices = sorted(set(prices))
                lowest_price = prices[0]
                highest_price = prices[-1]

        if lowest_price > 0 and highest_price > 0:
            return apply_rules_ab(current_price, original_price, lowest_price, highest_price, url)
        else:
            return local_verdict(current_price, original_price)

    except Exception as e:
        print(f"  [KANBKAM] Error: {e}")
        return local_verdict(current_price, original_price)


def apply_rules_ab(current_price, original_price, lowest_price, highest_price, kanbkam_url=""):
    """
    RULE A: original_price > highest_price * 1.05
            → The 'was' price was never real
    RULE B: price_range <= EGP 5 AND current near lowest
            → Price has NEVER changed, no real discount
    FAKE = Rule A AND Rule B BOTH true
    """
    # Allow small tolerance
    rule_a = original_price > (highest_price * 1.05)
    price_range = highest_price - lowest_price
    rule_b = (price_range <= 5) and (abs(current_price - lowest_price) <= 5)
    
    near_lowest = current_price <= (lowest_price * 1.15)
    price_above_low = round((current_price - lowest_price) / lowest_price * 100) if lowest_price > 0 else 0
    suggested_wait = round(lowest_price * 1.05) if lowest_price > 0 else 0

    if rule_a and rule_b:
        # CONFIRMED FAKE — both rules triggered
        return {
            "kanbkam_checked": True,
            "kanbkam_url": kanbkam_url,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "rule_a_triggered": True,
            "rule_b_triggered": True,
            "verdict": "FAKE",
            "verdict_ar": "خصم مزيف",
            "emoji": "❌",
            "fake_score": 95,
            "reason": f"FAKE CONFIRMED — Rule A: Amazon 'was' EGP {original_price:,.0f} but Kanbkam highest EVER was EGP {highest_price:,.0f}. Rule B: Price was ALWAYS EGP {lowest_price:,.0f} — never changed.",
            "reason_ar": f"خصم مزيف — قاعدة أ: سعر أمازون الأصلي {original_price:,.0f} جنيه لكن أعلى سعر في كنبكام كان {highest_price:,.0f} جنيه فقط. قاعدة ب: السعر كان دائماً {lowest_price:,.0f} جنيه ولم يتغير أبداً.",
            "near_lowest": near_lowest,
            "suggested_wait_price": 0,  # No point waiting — deal is fake
            "checked_at": now_iso(),
        }
    elif rule_a:
        # Rule A only — original price inflated but price did vary
        return {
            "kanbkam_checked": True,
            "kanbkam_url": kanbkam_url,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "rule_a_triggered": True,
            "rule_b_triggered": False,
            "verdict": "SUSPICIOUS",
            "verdict_ar": "مشبوه — السعر الأصلي مبالغ فيه",
            "emoji": "⚠️",
            "fake_score": 72,
            "reason": f"SUSPICIOUS — Rule A: Amazon 'was' EGP {original_price:,.0f} exceeds Kanbkam highest EGP {highest_price:,.0f}. Original price appears inflated, but price did change historically.",
            "reason_ar": f"مشبوه — سعر أمازون الأصلي {original_price:,.0f} جنيه أعلى من أعلى سعر في كنبكام {highest_price:,.0f} جنيه.",
            "near_lowest": near_lowest,
            "suggested_wait_price": suggested_wait,
            "checked_at": now_iso(),
        }
    elif rule_b:
        # Rule B only — price never changed, discount claim suspicious
        return {
            "kanbkam_checked": True,
            "kanbkam_url": kanbkam_url,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "rule_a_triggered": False,
            "rule_b_triggered": True,
            "verdict": "SUSPICIOUS",
            "verdict_ar": "مشبوه — السعر لم يتغير أبداً",
            "emoji": "⚠️",
            "fake_score": 58,
            "reason": f"SUSPICIOUS — Rule B: Kanbkam shows price was always EGP {lowest_price:,.0f}. It never changed, making the claimed discount questionable.",
            "reason_ar": f"مشبوه — السعر كان دائماً {lowest_price:,.0f} جنيه ولم يتغير أبداً.",
            "near_lowest": near_lowest,
            "suggested_wait_price": suggested_wait,
            "checked_at": now_iso(),
        }
    elif near_lowest:
        return {
            "kanbkam_checked": True,
            "kanbkam_url": kanbkam_url,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "rule_a_triggered": False,
            "rule_b_triggered": False,
            "verdict": "GENUINE",
            "verdict_ar": "خصم حقيقي — قريب من أقل سعر تاريخي",
            "emoji": "✅",
            "fake_score": 10,
            "reason": f"GENUINE — Current EGP {current_price:,.0f} is near historical low EGP {lowest_price:,.0f}. Great deal!",
            "reason_ar": f"حقيقي — السعر الحالي {current_price:,.0f} جنيه قريب من أقل سعر تاريخي {lowest_price:,.0f} جنيه. صفقة رائعة!",
            "near_lowest": True,
            "suggested_wait_price": 0,
            "checked_at": now_iso(),
        }
    elif price_above_low > 40:
        return {
            "kanbkam_checked": True,
            "kanbkam_url": kanbkam_url,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "rule_a_triggered": False,
            "rule_b_triggered": False,
            "verdict": "WAIT",
            "verdict_ar": "انتظر — سعر أفضل متاح",
            "emoji": "⏳",
            "fake_score": 35,
            "reason": f"WAIT — Price was EGP {lowest_price:,.0f} before. Current EGP {current_price:,.0f} is {price_above_low}% above historical low. Wait for better price.",
            "reason_ar": f"انتظر — السعر كان {lowest_price:,.0f} جنيه. الحالي {current_price:,.0f} جنيه أعلى بـ{price_above_low}% من أقل سعر.",
            "near_lowest": False,
            "suggested_wait_price": suggested_wait,
            "checked_at": now_iso(),
        }
    else:
        return {
            "kanbkam_checked": True,
            "kanbkam_url": kanbkam_url,
            "lowest_price": lowest_price,
            "highest_price": highest_price,
            "rule_a_triggered": False,
            "rule_b_triggered": False,
            "verdict": "GENUINE",
            "verdict_ar": "خصم حقيقي",
            "emoji": "✅",
            "fake_score": 20,
            "reason": f"GENUINE — Price history looks normal. Current EGP {current_price:,.0f}, Historical low EGP {lowest_price:,.0f}.",
            "reason_ar": f"حقيقي — تاريخ السعر طبيعي. الحالي {current_price:,.0f} جنيه.",
            "near_lowest": near_lowest,
            "suggested_wait_price": suggested_wait,
            "checked_at": now_iso(),
        }


def local_verdict(current_price, original_price):
    """Fallback verdict when Kanbkam is unreachable"""
    ratio = original_price / current_price if current_price > 0 else 1
    if ratio > 3:
        v, va, e, fs = "SUSPICIOUS", "مشبوه", "⚠️", 65
        reason = f"Original EGP {original_price:,.0f} is {ratio:.1f}x current. Kanbkam unavailable to verify."
    elif ratio > 2:
        v, va, e, fs = "SUSPICIOUS", "مشبوه", "⚠️", 45
        reason = f"High ratio ({ratio:.1f}x). Cannot verify without Kanbkam."
    else:
        v, va, e, fs = "UNVERIFIED", "غير مؤكد", "❓", 30
        reason = "Kanbkam unavailable. Cannot verify price history."
    return {"kanbkam_checked": False, "kanbkam_url": "", "lowest_price": 0, "highest_price": 0,
            "rule_a_triggered": False, "rule_b_triggered": False,
            "verdict": v, "verdict_ar": va, "emoji": e, "fake_score": fs,
            "reason": reason, "reason_ar": reason, "near_lowest": False,
            "suggested_wait_price": 0, "checked_at": now_iso()}

# ─────────────────────────────────────────────────────
# SAVE DEAL — Always update, never skip
# ─────────────────────────────────────────────────────
def save_deal(deal):
    deal_id = deal["deal_id"]
    ref = db.collection("deals").document(deal_id)
    try:
        existing = ref.get()
        # Fix: never store 0 reviews — use None (shows as ---)
        if deal.get("review_count", 0) == 0:
            deal["review_count"] = None

        if existing.exists:
            old = existing.to_dict()
            old_price = old.get("current_price", 0)
            new_price = deal["current_price"]
            update = {
                "current_price": new_price,
                "discount_percent": deal["discount_percent"],
                "timestamp": deal["timestamp"],
            }
            if deal.get("image_url"):
                update["image_url"] = deal["image_url"]
            if deal.get("rating", 0) > 0:
                update["rating"] = deal["rating"]
            if deal.get("review_count") is not None:
                update["review_count"] = deal["review_count"]
            kb = deal.get("kanbkam", {})
            if kb:
                update.update({
                    "kanbkam": kb,
                    "fake_verdict": kb.get("verdict", "UNVERIFIED"),
                    "fake_verdict_ar": kb.get("verdict_ar", ""),
                    "fake_emoji": kb.get("emoji", ""),
                    "rule_a": kb.get("rule_a_triggered", False),
                    "rule_b": kb.get("rule_b_triggered", False),
                    "lowest_price_ever": kb.get("lowest_price", 0),
                    "highest_price_ever": kb.get("highest_price", 0),
                    "suggested_wait_price": kb.get("suggested_wait_price", 0),
                })
            ref.update(update)
            if old_price != new_price:
                ref.collection("price_history").document().set({"price": new_price, "old_price": old_price, "timestamp": deal["timestamp"]})
                print(f"  UPDATED: {deal['title'][:45]} | EGP {old_price:,.0f}→{new_price:,.0f} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
            else:
                print(f"  REFRESH: {deal['title'][:45]} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
        else:
            ref.set(deal)
            ref.collection("price_history").document().set({"price": deal["current_price"], "timestamp": deal["timestamp"]})
            print(f"  NEW:     {deal['title'][:45]} | {deal['discount_percent']}% OFF | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
    except Exception as e:
        print(f"  ERROR: {e}")


def build_deal(title, site, site_display, category, current_price, original_price,
               discount, image_url, product_url, rating=0.0, review_count=None,
               asin=None, kanbkam_result=None, coupon_code=None):
    if not kanbkam_result:
        kanbkam_result = local_verdict(current_price, original_price)
    if review_count == 0:
        review_count = None
    return {
        "deal_id": generate_deal_id(site, product_url, current_price),
        "title": title, "title_ar": "",
        "site": site, "site_display": site_display,
        "category": category,
        "current_price": current_price, "original_price": original_price,
        "discount_percent": discount, "currency": "EGP",
        "image_url": image_url, "product_url": product_url,
        "asin": asin or "", "availability": "in_stock",
        "timestamp": now_iso(),
        "rating": rating, "review_count": review_count,
        "coupon_code": coupon_code,
        "verified": True, "hidden": False, "featured": False, "source": "scraper",
        "kanbkam": kanbkam_result,
        "fake_verdict": kanbkam_result.get("verdict", "UNVERIFIED"),
        "fake_verdict_ar": kanbkam_result.get("verdict_ar", ""),
        "fake_emoji": kanbkam_result.get("emoji", "❓"),
        "fake_score": kanbkam_result.get("fake_score", 50),
        "rule_a": kanbkam_result.get("rule_a_triggered", False),
        "rule_b": kanbkam_result.get("rule_b_triggered", False),
        "lowest_price_ever": kanbkam_result.get("lowest_price", 0),
        "highest_price_ever": kanbkam_result.get("highest_price", 0),
        "suggested_wait_price": kanbkam_result.get("suggested_wait_price", 0),
        "click_count": 0, "buy_click_count": 0,
    }

# ─────────────────────────────────────────────────────
# AMAZON EGYPT — Unchanged working scraper
# ─────────────────────────────────────────────────────
AMAZON_KEYWORDS = [
    {"k": "samsung galaxy", "cat": "electronics"},
    {"k": "iphone", "cat": "electronics"},
    {"k": "xiaomi phone", "cat": "electronics"},
    {"k": "oppo phone", "cat": "electronics"},
    {"k": "laptop lenovo", "cat": "electronics"},
    {"k": "laptop dell", "cat": "electronics"},
    {"k": "laptop hp", "cat": "electronics"},
    {"k": "laptop asus", "cat": "electronics"},
    {"k": "tablet android", "cat": "electronics"},
    {"k": "ipad", "cat": "electronics"},
    {"k": "sony headphones", "cat": "electronics"},
    {"k": "jbl speaker", "cat": "electronics"},
    {"k": "earbuds bluetooth", "cat": "electronics"},
    {"k": "samsung watch", "cat": "electronics"},
    {"k": "samsung tv", "cat": "electronics"},
    {"k": "lg tv", "cat": "electronics"},
    {"k": "playstation", "cat": "electronics"},
    {"k": "power bank", "cat": "electronics"},
    {"k": "router wifi", "cat": "electronics"},
    {"k": "ssd", "cat": "electronics"},
    {"k": "gaming keyboard", "cat": "electronics"},
    {"k": "digital camera", "cat": "electronics"},
    {"k": "nike shoes", "cat": "fashion"},
    {"k": "adidas shoes", "cat": "fashion"},
    {"k": "puma shoes", "cat": "fashion"},
    {"k": "mens shirt", "cat": "fashion"},
    {"k": "womens dress", "cat": "fashion"},
    {"k": "handbag women", "cat": "fashion"},
    {"k": "sunglasses", "cat": "fashion"},
    {"k": "perfume men", "cat": "fashion"},
    {"k": "perfume women", "cat": "fashion"},
    {"k": "air conditioner", "cat": "home"},
    {"k": "refrigerator", "cat": "home"},
    {"k": "washing machine", "cat": "home"},
    {"k": "microwave oven", "cat": "home"},
    {"k": "air fryer", "cat": "home"},
    {"k": "blender", "cat": "home"},
    {"k": "coffee maker", "cat": "home"},
    {"k": "vacuum cleaner", "cat": "home"},
    {"k": "electric kettle", "cat": "home"},
    {"k": "face cream", "cat": "beauty"},
    {"k": "hair dryer", "cat": "beauty"},
    {"k": "vitamin supplement", "cat": "beauty"},
    {"k": "makeup kit", "cat": "beauty"},
    {"k": "shampoo", "cat": "beauty"},
    {"k": "gym equipment", "cat": "sports"},
    {"k": "protein powder", "cat": "sports"},
    {"k": "treadmill", "cat": "sports"},
    {"k": "yoga mat", "cat": "sports"},
    {"k": "lego", "cat": "toys"},
    {"k": "baby stroller", "cat": "toys"},
    {"k": "arabic novel", "cat": "books"},
    {"k": "protein bar", "cat": "grocery"},
    {"k": "organic honey", "cat": "grocery"},
]

def scrape_amazon():
    print("\n[AMAZON] Starting — direct scrape with Kanbkam check...")
    total = 0
    for item in AMAZON_KEYWORDS:
        try:
            url = f"https://www.amazon.eg/s?k={item['k'].replace(' ','+')}&language=en_AE"
            resp = fetch_direct(url)
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            products = [p for p in soup.find_all("div", attrs={"data-asin": True}) if p.get("data-asin", "").strip()]
            for product in products:
                try:
                    asin = product.get("data-asin", "").strip()
                    if not asin or product.get("data-component-type") == "sp-sponsored-result":
                        continue
                    title_el = product.find("h2") or product.find("span", class_="a-size-medium") or product.find("span", class_="a-size-base-plus")
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
                    img_el = product.find("img", class_="s-image")
                    image_url = img_el.get("src", "") if img_el else ""
                    rating = 0.0
                    rating_el = product.find("span", class_="a-icon-alt")
                    if rating_el:
                        try:
                            rating = float(rating_el.get_text(strip=True).split(" ")[0])
                        except:
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
                            except:
                                pass
                    product_url = f"https://www.amazon.eg/dp/{asin}?language=en_AE"
                    cat = detect_category(title)
                    if cat == "general":
                        cat = item["cat"]
                    print(f"    [AMAZON] Kanbkam check: {title[:30]}...")
                   kb = check_price_history(
    asin=asin,
    product_url=product_url,
    current_price=current_price,
    original_price=original_price,
    title=title,
    site="amazon_eg"
)
                    time.sleep(1)
                    deal = build_deal(title, "amazon_eg", "Amazon Egypt", cat,
                                      current_price, original_price, discount,
                                      image_url, product_url, rating, review_count, asin, kb)
                    save_deal(deal)
                    total += 1
                    time.sleep(0.5)
                except Exception:
                    continue
            time.sleep(3)
        except Exception as e:
            print(f"  Amazon keyword error: {e}")
            time.sleep(5)
    print(f"[AMAZON] Done. {total} deals.")
    return total

# ─────────────────────────────────────────────────────
# PHASE 2: JUMIA EGYPT — Static HTML
# ─────────────────────────────────────────────────────
def scrape_jumia():
    print("\n[JUMIA] Starting — static HTML scrape...")
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
        ("https://www.jumia.com.eg/car-motorbike/?sort=discountPercent#catalog-listing", "automotive"),
    ]
    for url, default_cat in pages:
        try:
            headers = get_headers()
            headers["Referer"] = "https://www.jumia.com.eg/"
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                time.sleep(2)
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("article", class_="prd") or
                soup.find_all("article", attrs={"data-id": True}) or
                soup.find_all("div", class_="prd")
            )
            print(f"  [JUMIA] {len(products)} products: {url[:55]}...")
            for p in products:
                try:
                    title_el = p.find("h3", class_="name") or p.find("p", class_="name") or p.find("h3")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    price_el = p.find("div", class_="prc") or p.find("span", class_="prc") or p.find(class_=lambda c: c and "prc" in str(c))
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50:
                        continue
                    orig_el = p.find("div", class_="old") or p.find("span", class_="old") or p.find("s") or p.find(class_=lambda c: c and "old" in str(c))
                    original_price = clean_price(orig_el.get_text()) if orig_el else current_price
                    if original_price < current_price:
                        original_price = current_price
                    discount = calculate_discount(original_price, current_price)
                    # Try discount badge
                    disc_el = p.find(class_=lambda c: c and "dsct" in str(c))
                    if disc_el and discount < MIN_DISCOUNT:
                        try:
                            bd = int(re.sub(r'[^\d]', '', disc_el.get_text()))
                            if bd >= MIN_DISCOUNT:
                                discount = bd
                                if original_price == current_price:
                                    original_price = round(current_price / (1 - bd/100))
                        except:
                            pass
                    if discount < MIN_DISCOUNT:
                        continue
                    link_el = p.find("a", href=True)
                    href = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://www.jumia.com.eg" + href
                    img_el = p.find("img")
                    image_url = (img_el.get("data-src") or img_el.get("src") or "") if img_el else ""
                    rating = 0.0
                    stars_el = p.find(class_=lambda c: c and "stars" in str(c))
                    if stars_el:
                        r_text = stars_el.get_text(strip=True)
                        try:
                            rating = float(re.search(r'[\d.]+', r_text).group())
                        except:
                            pass
                    review_count = None
                    rev_el = p.find(class_=lambda c: c and "rev" in str(c))
                    if rev_el:
                        try:
                            rc = int(re.sub(r'[^\d]', '', rev_el.get_text()))
                            if rc > 0:
                                review_count = rc
                        except:
                            pass
                    cat = detect_category(title)
                    if cat == "general":
                        cat = default_cat
                    deal = build_deal(title, "jumia_eg", "Jumia Egypt", cat, current_price, original_price, discount, image_url, product_url, rating, review_count)
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
# PHASE 2: B.TECH — Static HTML + JSON embedded
# ─────────────────────────────────────────────────────
def scrape_btech():
    print("\n[B.TECH] Starting...")
    total = 0
    pages = [
        ("https://btech.com/en/promotions.html?pageSize=48", "electronics"),
        ("https://btech.com/en/mobiles-and-tablets.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/laptops-and-computers.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/tv-and-audio.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/home-appliances.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "home"),
        ("https://btech.com/en/cameras.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
    ]
    for url, default_cat in pages:
        try:
            headers = get_headers()
            headers["Referer"] = "https://btech.com/"
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                time.sleep(2)
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            # B.Tech product selectors
            products = (
                soup.find_all("li", class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("div", class_="item product product-item") or
                soup.find_all("div", class_=lambda c: c and "product-item" in str(c))
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
                    # Special price first, then regular
                    special_el = p.find("span", class_="special-price")
                    price_el = special_el.find("span", class_="price") if special_el else p.find("span", class_="price")
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50:
                        continue
                    old_el = p.find("span", class_="old-price")
                    orig_text = old_el.find("span", class_="price").get_text() if old_el and old_el.find("span", class_="price") else ""
                    original_price = clean_price(orig_text) or current_price
                    if original_price < current_price:
                        original_price = current_price
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue
                    link_el = p.find("a", class_="product-item-link") or p.find("a", href=True)
                    href = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://btech.com" + href
                    img_el = p.find("img", class_=lambda c: c and "product" in str(c)) or p.find("img")
                    image_url = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                    rating = 0.0
                    stars_el = p.find("div", class_="rating-result")
                    if stars_el:
                        try:
                            style = stars_el.find("span", style=True)
                            if style:
                                pct = float(re.search(r'([\d.]+)%', style.get("style", "")).group(1))
                                rating = round(pct / 20, 1)
                        except:
                            pass
                    review_count = None
                    rev_el = p.find(class_=lambda c: c and "review" in str(c))
                    if rev_el:
                        try:
                            rc = int(re.sub(r'[^\d]', '', rev_el.get_text()))
                            if rc > 0:
                                review_count = rc
                        except:
                            pass
                    cat = detect_category(title) or default_cat
                    deal = build_deal(title, "btech_eg", "B.Tech Egypt", cat, current_price, original_price, discount, image_url, product_url, rating, review_count)
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
# PHASE 2: CARREFOUR EGYPT — JSON API
# ─────────────────────────────────────────────────────
def scrape_carrefour():
    print("\n[CARREFOUR] Starting — JSON API...")
    total = 0
    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.carrefouregypt.com/",
        "lang": "en",
        "x-api-key": "sVaMB6Zs6MkFdFMFwvvXLqQtRdwHQxQZ",
    }
    categories = [
        ("electronics", "electronics"),
        ("mobiles-tablets", "electronics"),
        ("computers", "electronics"),
        ("tv-video", "electronics"),
        ("kitchen-appliances", "home"),
        ("large-appliances", "home"),
        ("fashion", "fashion"),
        ("sports-outdoors", "sports"),
        ("beauty-health", "beauty"),
        ("baby-toys", "toys"),
    ]
    for cat_id, default_cat in categories:
        try:
            # Carrefour uses a Hybris-based API
            api_url = f"https://www.carrefouregypt.com/api/v7/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc"
            resp = requests.get(api_url, headers=api_headers, timeout=20)
            products_data = []
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    # Try multiple response structures
                    products_data = (
                        data.get("data", {}).get("products", {}).get("results", []) or
                        data.get("products", {}).get("results", []) or
                        data.get("results", []) or []
                    )
                except:
                    products_data = []
            if not products_data:
                # Try alternate API endpoint
                alt_url = f"https://www.carrefouregypt.com/api/v4/products?catalogId=mafegy&lang=en&query=%3AdiscountPercentage%3Acategory%3A{cat_id}&currentPage=0&pageSize=48"
                resp2 = requests.get(alt_url, headers=api_headers, timeout=20)
                if resp2.status_code == 200:
                    try:
                        data2 = resp2.json()
                        products_data = data2.get("products", []) or []
                    except:
                        products_data = []
            print(f"  [CARREFOUR] {len(products_data)} products: {cat_id}")
            for p in products_data:
                try:
                    title = p.get("name", "") or p.get("title", "")
                    if not title:
                        continue
                    price_info = p.get("price", {})
                    current_price = clean_price(str(price_info.get("value", 0) or price_info.get("discounted", 0) or p.get("price", 0)))
                    original_price = clean_price(str(price_info.get("formattedOriginalPrice", current_price) or price_info.get("original", current_price) or current_price))
                    if current_price < 50:
                        continue
                    if original_price < current_price:
                        original_price = current_price
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue
                    images = p.get("images", [{}])
                    image_url = (images[0].get("url", "") if images else "") or ""
                    if image_url and not image_url.startswith("http"):
                        image_url = "https://www.carrefouregypt.com" + image_url
                    code = p.get("code", "") or p.get("id", "")
                    product_url = f"https://www.carrefouregypt.com/mafegy/en/p/{code}"
                    rating = float(p.get("averageRating", 0) or 0)
                    review_count = int(p.get("numberOfReviews", 0) or 0) or None
                    cat = detect_category(title) or default_cat
                    deal = build_deal(title, "carrefour_eg", "Carrefour Egypt", cat, current_price, original_price, discount, image_url, product_url, rating, review_count)
                    save_deal(deal)
                    total += 1
                except Exception:
                    continue
            time.sleep(2)
        except Exception as e:
            print(f"  [CARREFOUR] Error: {e}")
            time.sleep(5)
    print(f"[CARREFOUR] Done. {total} deals.")
    return total

# ─────────────────────────────────────────────────────
# PHASE 2: SHARAF DG — Static HTML
# ─────────────────────────────────────────────────────
def scrape_sharaf_dg():
    print("\n[SHARAF DG] Starting...")
    total = 0
    pages = [
        ("https://www.sharafdg.com/en/eg/deals", "electronics"),
        ("https://www.sharafdg.com/en/eg/mobiles-tablets", "electronics"),
        ("https://www.sharafdg.com/en/eg/computers-laptops", "electronics"),
        ("https://www.sharafdg.com/en/eg/tv-video-audio", "electronics"),
        ("https://www.sharafdg.com/en/eg/home-appliances", "home"),
        ("https://www.sharafdg.com/en/eg/cameras", "electronics"),
    ]
    for url, default_cat in pages:
        try:
            headers = get_headers()
            headers["Referer"] = "https://www.sharafdg.com/"
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                time.sleep(2)
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("li", class_=lambda c: c and "item" in str(c) and "product" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "product-item" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "product-card" in str(c)) or
                soup.find_all("article", class_=lambda c: c and "product" in str(c))
            )
            print(f"  [SHARAF] {len(products)} products: {url[:55]}...")
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
                    price_el = (special_el.find("span", class_="price") if special_el else None) or p.find("span", class_="price") or p.find(class_=lambda c: c and "price" in str(c) and "old" not in str(c))
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50:
                        continue
                    old_el = p.find("span", class_=lambda c: c and "old" in str(c) and "price" in str(c)) or p.find("del") or p.find("s")
                    original_price = clean_price(old_el.get_text()) if old_el else current_price
                    if original_price < current_price:
                        original_price = current_price
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue
                    link_el = p.find("a", href=True)
                    href = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://www.sharafdg.com" + href
                    img_el = p.find("img")
                    image_url = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                    cat = detect_category(title) or default_cat
                    deal = build_deal(title, "sharaf_dg_eg", "Sharaf DG Egypt", cat, current_price, original_price, discount, image_url, product_url)
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
# PHASE 3: NOON EGYPT — ScraperAPI for JS rendering
# Falls back to API attempts if no ScraperAPI key
# ─────────────────────────────────────────────────────
def scrape_noon():
    print("\n[NOON] Starting — ScraperAPI JS rendering...")
    total = 0
    
    search_terms = [
        ("samsung galaxy", "electronics"), ("iphone", "electronics"),
        ("laptop", "electronics"), ("headphones", "electronics"),
        ("tv", "electronics"), ("tablet", "electronics"),
        ("nike shoes", "fashion"), ("dress", "fashion"),
        ("perfume", "fashion"), ("handbag", "fashion"),
        ("refrigerator", "home"), ("washing machine", "home"),
        ("air conditioner", "home"), ("microwave", "home"),
        ("skincare", "beauty"), ("makeup", "beauty"),
        ("hair dryer", "beauty"), ("vitamins", "beauty"),
        ("gym equipment", "sports"), ("protein", "sports"),
    ]
    
    for term, default_cat in search_terms:
        try:
            url = f"https://www.noon.com/egypt-en/search/?q={term.replace(' ','+')}&limit=48&sort%5Bby%5D=discount&sort%5Bdir%5D=desc"
            
            # Try ScraperAPI with JS rendering
            resp = fetch_with_scraperapi(url, render_js=True, country="eg")
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue
            
            # Try to extract embedded JSON first (faster than HTML parsing)
            content = resp.text
            products_found = 0
            
            # Method 1: Find JSON data in page (Noon embeds product data)
            json_patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});\s*(?:window|</script>)',
                r'"products"\s*:\s*(\[.+?\])',
                r'"hits"\s*:\s*\{"hits"\s*:\s*(\[.+?\])',
            ]
            
            for pattern in json_patterns:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    try:
                        raw = match.group(1)
                        if raw.startswith('{'):
                            data = json.loads(raw)
                            items = (
                                data.get("catalog", {}).get("hits", []) or
                                data.get("hits", {}).get("hits", []) or
                                data.get("products", []) or []
                            )
                        else:
                            items = json.loads(raw)
                        
                        for item in items:
                            try:
                                src = item.get("_source", item)
                                title = src.get("name", "") or src.get("title", "")
                                if not title:
                                    continue
                                cp = clean_price(str(src.get("price", {}).get("value", 0) or src.get("sale_price", 0) or src.get("price", 0)))
                                op = clean_price(str(src.get("price", {}).get("was", cp) or src.get("was_price", cp) or src.get("original_price", cp) or cp))
                                if cp < 50:
                                    continue
                                if op < cp:
                                    op = cp
                                disc = calculate_discount(op, cp)
                                if disc < MIN_DISCOUNT:
                                    continue
                                img_keys = src.get("image_keys", [])
                                img = f"https://f.nooncdn.com/p/{img_keys[0]}.jpg" if img_keys else (src.get("image", "") or "")
                                sku = src.get("sku", "") or src.get("id", "")
                                purl = f"https://www.noon.com/egypt-en/{sku}/" if sku else ""
                                rating = float(src.get("rating", {}).get("value", 0) or src.get("rating", 0) or 0)
                                rc = int(src.get("rating", {}).get("count", 0) or src.get("review_count", 0) or 0) or None
                                cat = detect_category(title) or default_cat
                                deal = build_deal(title, "noon_eg", "Noon Egypt", cat, cp, op, disc, img, purl, rating, rc)
kb = check_price_history(
    product_url=product_url,
    current_price=current_price,
    original_price=original_price,
    title=title,
    site="noon_eg"
)
deal["kanbkam"] = kb
deal["fake_verdict"] = kb.get("verdict","UNVERIFIED")
deal["fake_emoji"] = kb.get("emoji","❓")
deal["coupon_codes"] = kb.get("coupon_codes",[])
deal["coupon_display"] = kb.get("coupon_display","")
                                save_deal(deal)
                                total += 1
                                products_found += 1
                            except Exception:
                                continue
                        
                        if products_found > 0:
                            break
                    except Exception:
                        continue
            
            # Method 2: HTML parsing if JSON not found
            if products_found == 0:
                soup = BeautifulSoup(content, "lxml")
                product_blocks = (
                    soup.find_all("div", attrs={"data-qa": "product-block"}) or
                    soup.find_all("div", class_=lambda c: c and "productContainer" in str(c)) or
                    soup.find_all("div", class_=lambda c: c and "product" in str(c) and "grid" in str(c)) or
                    soup.find_all("article")
                )
                for p in product_blocks:
                    try:
                        title_el = p.find(class_=lambda c: c and "name" in str(c)) or p.find("h2") or p.find("p", class_=lambda c: c and "name" in str(c))
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue
                        price_el = p.find("strong", class_=lambda c: c and "price" in str(c)) or p.find("span", class_=lambda c: c and "price" in str(c)) or p.find(class_="price")
                        if not price_el:
                            continue
                        cp = clean_price(price_el.get_text())
                        if cp < 50:
                            continue
                        orig_el = p.find("span", class_=lambda c: c and ("was" in str(c) or "old" in str(c))) or p.find("del")
                        op = clean_price(orig_el.get_text()) if orig_el else cp
                        if op < cp:
                            op = cp
                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue
                        link_el = p.find("a", href=True)
                        href = link_el["href"] if link_el else ""
                        purl = "https://www.noon.com" + href if href.startswith("/") else href
                        img_el = p.find("img")
                        img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                        cat = detect_category(title) or default_cat
                        deal = build_deal(title, "noon_eg", "Noon Egypt", cat, cp, op, disc, img, purl)
                        save_deal(deal)
                        total += 1
                        products_found += 1
                    except Exception:
                        continue
            
            print(f"  [NOON] '{term}': {products_found} deals")
            time.sleep(2)
            
        except Exception as e:
            print(f"  [NOON] Error '{term}': {e}")
            time.sleep(3)
    
    print(f"[NOON] Done. {total} deals.")
    return total

# ─────────────────────────────────────────────────────
# PHASE 3: HYPERONE — ScraperAPI + HTML fallback
# ─────────────────────────────────────────────────────
def scrape_hyperone():
    print("\n[HYPERONE] Starting — ScraperAPI...")
    total = 0
    pages = [
        ("https://www.hyperone.com.eg/offers/", "general"),
        ("https://www.hyperone.com.eg/electronics/", "electronics"),
        ("https://www.hyperone.com.eg/home-appliances/", "home"),
        ("https://www.hyperone.com.eg/mobiles-and-accessories/", "electronics"),
        ("https://www.hyperone.com.eg/tablets-and-accessories/", "electronics"),
    ]
    for url, default_cat in pages:
        try:
            resp = fetch_with_scraperapi(url, render_js=True, country="eg")
            if not resp or resp.status_code != 200:
                # Try direct
                resp = fetch_direct(url)
                if not resp or resp.status_code != 200:
                    time.sleep(2)
                    continue
            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("li", class_=lambda c: c and "product" in str(c)) or
                soup.find_all("div", class_=lambda c: c and "product" in str(c) and "item" in str(c)) or
                soup.find_all("article") or
                soup.find_all("div", class_=lambda c: c and "product-card" in str(c))
            )
            print(f"  [HYPERONE] {len(products)} products: {url}")
            for p in products:
                try:
                    title_el = p.find("h2") or p.find("h3") or p.find(class_=lambda c: c and ("name" in str(c) or "title" in str(c)))
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue
                    special_el = p.find(class_=lambda c: c and "special" in str(c) and "price" in str(c))
                    price_el = (special_el.find("span", class_="price") if special_el else None) or p.find("span", class_="price") or p.find(class_=lambda c: c and "price" in str(c) and "old" not in str(c))
                    if not price_el:
                        continue
                    current_price = clean_price(price_el.get_text())
                    if current_price < 50:
                        continue
                    orig_el = p.find("span", class_=lambda c: c and "old" in str(c)) or p.find("del") or p.find("s")
                    original_price = clean_price(orig_el.get_text()) if orig_el else current_price
                    if original_price < current_price:
                        original_price = current_price
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue
                    link_el = p.find("a", href=True)
                    href = link_el["href"] if link_el else ""
                    product_url = href if href.startswith("http") else "https://www.hyperone.com.eg" + href
                    img_el = p.find("img")
                    image_url = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                    cat = detect_category(title) or default_cat
                    deal = build_deal(title, "hyperone_eg", "HyperOne Egypt", cat, current_price, original_price, discount, image_url, product_url)
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
# PHASE 3: SAHLA — API + ScraperAPI fallback
# ─────────────────────────────────────────────────────
def scrape_sahla():
    print("\n[SAHLA] Starting...")
    total = 0
    
    # Try Sahla's API first
    api_base = "https://sahlaapp.com/api/v2"
    api_headers = {
        "Accept": "application/json",
        "User-Agent": "Sahla/2.0 (com.sahla.app; iOS 16.0)",
        "x-app-version": "2.0",
        "Content-Type": "application/json",
    }
    
    endpoints = [
        f"{api_base}/products?page=1&per_page=50&sort_by=discount&sort_order=desc",
        f"{api_base}/categories/electronics/products?page=1&per_page=50&sort_by=discount",
        f"{api_base}/categories/fashion/products?page=1&per_page=50&sort_by=discount",
        f"{api_base}/offers?page=1&per_page=50",
    ]
    
    for endpoint in endpoints:
        try:
            resp = requests.get(endpoint, headers=api_headers, timeout=15)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    items = data.get("data", data.get("products", data.get("offers", data.get("items", []))))
                    for item in items:
                        try:
                            title = item.get("name", "") or item.get("title", "")
                            if not title:
                                continue
                            cp = clean_price(str(item.get("sale_price", item.get("price", item.get("discounted_price", 0)))))
                            op = clean_price(str(item.get("original_price", item.get("price", item.get("regular_price", cp)))))
                            if cp < 50:
                                continue
                            if op < cp:
                                op = cp
                            disc = calculate_discount(op, cp)
                            if disc < MIN_DISCOUNT:
                                continue
                            img = item.get("image", item.get("thumbnail", item.get("image_url", "")))
                            pid = item.get("id", item.get("slug", ""))
                            purl = f"https://sahlaapp.com/product/{pid}"
                            rating = float(item.get("rating", 0) or 0)
                            rc = int(item.get("reviews_count", item.get("review_count", 0)) or 0) or None
                            cat = detect_category(title)
                            deal = build_deal(title, "sahla_eg", "Sahla Egypt", cat, cp, op, disc, img or "", purl, rating, rc)
                            save_deal(deal)
                            total += 1
                        except Exception:
                            continue
                    continue
                except Exception:
                    pass
        except Exception as e:
            print(f"  [SAHLA] API error: {e}")
    
    # Fallback to ScraperAPI web scraping
    if total == 0:
        try:
            url = "https://sahlaapp.com/products?sort=discount"
            resp = fetch_with_scraperapi(url, render_js=True, country="eg")
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                products = soup.find_all(class_=lambda c: c and "product" in str(c).lower())
                for p in products:
                    try:
                        title_el = p.find("h2") or p.find("h3") or p.find(class_=lambda c: c and "name" in str(c).lower())
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue
                        price_el = p.find(class_=lambda c: c and "price" in str(c).lower() and "old" not in str(c).lower())
                        if not price_el:
                            continue
                        cp = clean_price(price_el.get_text())
                        if cp < 50:
                            continue
                        orig_el = p.find("del") or p.find(class_=lambda c: c and "old" in str(c).lower())
                        op = clean_price(orig_el.get_text()) if orig_el else cp
                        if op < cp:
                            op = cp
                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue
                        link_el = p.find("a", href=True)
                        href = link_el["href"] if link_el else ""
                        purl = href if href.startswith("http") else "https://sahlaapp.com" + href
                        img_el = p.find("img")
                        img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                        cat = detect_category(title)
                        deal = build_deal(title, "sahla_eg", "Sahla Egypt", cat, cp, op, disc, img, purl)
                        save_deal(deal)
                        total += 1
                    except Exception:
                        continue
        except Exception as e:
            print(f"  [SAHLA] ScraperAPI error: {e}")
    
    print(f"[SAHLA] Done. {total} deals.")
    return total

# ─────────────────────────────────────────────────────
# UNIVERSAL CUSTOM SOURCES SCRAPER
# For any site added via admin dashboard
# Auto-detects if JS rendering needed
# ─────────────────────────────────────────────────────
def scrape_custom_sources():
    print("\n[CUSTOM SOURCES] Checking admin-added sources...")
    total = 0
    try:
        sources = [doc.to_dict() for doc in db.collection("admin").stream()]
        active = [s for s in sources if s.get("status") == "active" and s.get("site_url")]
        known_defaults = {
            "amazon.eg", "noon.com", "jumia.com.eg", "btech.com",
            "carrefouregypt.com", "sharafdg.com", "hyperone.com.eg", "sahlaapp.com"
        }
        custom = [s for s in active if not any(d in s.get("site_url", "") for d in known_defaults)]
        
        if not custom:
            print("  No custom sources to scrape.")
            return 0
        
        for source in custom:
            site_name = source.get("site_name", "Unknown")
            site_url = source.get("site_url", "")
            site_id = source.get("id", site_name.lower().replace(" ", "_"))
            print(f"\n  Scraping custom source: {site_name} ({site_url})")
            
            # Try direct fetch first
            resp = fetch_direct(site_url)
            products_found = 0
            
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                products = (
                    soup.find_all("div", class_=lambda c: c and "product" in str(c).lower() and "item" in str(c).lower()) or
                    soup.find_all("article", class_=lambda c: c and "product" in str(c).lower()) or
                    soup.find_all("li", class_=lambda c: c and "product" in str(c).lower())
                )
                
                # If no products found, try ScraperAPI (site might use JS)
                if not products:
                    print(f"    No products in direct fetch — trying ScraperAPI JS rendering...")
                    resp = fetch_with_scraperapi(site_url, render_js=True, country="eg")
                    if resp and resp.status_code == 200:
                        soup = BeautifulSoup(resp.content, "lxml")
                        products = (
                            soup.find_all("div", class_=lambda c: c and "product" in str(c).lower()) or
                            soup.find_all("article") or
                            soup.find_all("li", class_=lambda c: c and "item" in str(c).lower())
                        )
                
                for product in products[:50]:
                    try:
                        title_el = product.find("h2") or product.find("h3") or product.find(class_=lambda c: c and ("name" in str(c) or "title" in str(c)))
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue
                        price_el = product.find(class_=lambda c: c and "price" in str(c) and "old" not in str(c))
                        if not price_el:
                            continue
                        cp = clean_price(price_el.get_text())
                        if cp < 50:
                            continue
                        orig_el = product.find("del") or product.find(class_=lambda c: c and "old" in str(c))
                        op = clean_price(orig_el.get_text()) if orig_el else cp
                        if op < cp:
                            op = cp
                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue
                        link_el = product.find("a", href=True)
                        href = link_el["href"] if link_el else ""
                        purl = href if href.startswith("http") else site_url.rstrip("/") + "/" + href.lstrip("/")
                        img_el = product.find("img")
                        img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                        cat = detect_category(title)
                        deal = build_deal(title, site_id, site_name, cat, cp, op, disc, img, purl)
                        save_deal(deal)
                        total += 1
                        products_found += 1
                    except Exception:
                        continue
            
            # Update last scraped
            try:
                docs = db.collection("admin").where("site_url", "==", site_url).limit(1).get()
                for doc in docs:
                    doc.reference.update({"last_scraped": now_iso(), "last_count": products_found})
            except:
                pass
            
            print(f"  {site_name}: {products_found} deals")
            time.sleep(3)
    
    except Exception as e:
        print(f"  Custom sources error: {e}")
    
    print(f"[CUSTOM SOURCES] Done. {total} deals.")
    return total

# ─────────────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────────────
def update_analytics():
    try:
        deals = [d.to_dict() for d in db.collection("deals").get()]
        users = db.collection("users").get()
        site_counts, cat_counts, verdict_counts = {}, {}, {}
        clicks = buys = fake_count = 0
        for d in deals:
            s, c, v = d.get("site","?"), d.get("category","general"), d.get("fake_verdict","UNVERIFIED")
            site_counts[s] = site_counts.get(s,0)+1
            cat_counts[c] = cat_counts.get(c,0)+1
            verdict_counts[v] = verdict_counts.get(v,0)+1
            clicks += d.get("click_count",0)
            buys += d.get("buy_click_count",0)
            if v == "FAKE": fake_count += 1
        db.collection("analytics").document("summary").set({
            "total_deals": len(deals), "total_users": len(users.docs if hasattr(users,'docs') else list(users)),
            "site_counts": site_counts, "category_counts": cat_counts,
            "verdict_counts": verdict_counts, "total_clicks": clicks,
            "total_buy_clicks": buys, "fake_deals_count": fake_count,
            "last_updated": now_iso()
        }, merge=True)
        print(f"  Analytics: {len(deals)} deals | {fake_count} FAKE | {clicks} clicks")
    except Exception as e:
        print(f"  Analytics error: {e}")

# ─────────────────────────────────────────────────────
# MAIN CYCLE
# ─────────────────────────────────────────────────────
def run_scraper():
    if not check_scraper_control():
        return

    print(f"\n{'='*62}")
    print(f"  SCRAPE CYCLE: {now_str()}")
    if SCRAPER_API_KEY:
        print(f"  ScraperAPI: CONFIGURED (JS rendering enabled for Noon/HyperOne/Sahla)")
    else:
        print(f"  ScraperAPI: NOT CONFIGURED (add SCRAPER_API_KEY to use JS rendering)")
        print(f"  Get free key at scraperapi.com — 5,000 requests/month free")
    print(f"{'='*62}")

    total = 0
    total += scrape_amazon()        # Phase 1+2: Amazon + Kanbkam
    total += scrape_jumia()         # Phase 2: Static HTML
    total += scrape_btech()         # Phase 2: Static HTML
    total += scrape_carrefour()     # Phase 2: JSON API
    total += scrape_sharaf_dg()     # Phase 2: Static HTML
    total += scrape_noon()          # Phase 3: ScraperAPI JS rendering
    total += scrape_hyperone()      # Phase 3: ScraperAPI JS rendering
    total += scrape_sahla()         # Phase 3: API + ScraperAPI fallback
    total += scrape_custom_sources()  # Universal: any site you add

    update_analytics()
    print(f"\n  TOTAL: {total} deals | Next: {INTERVAL} min")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    print("DealHunter Egypt Scraper v6")
    print(f"Stores: Amazon + Jumia + B.Tech + Carrefour + Sharaf DG + Noon + HyperOne + Sahla")
    print(f"Fake check: Rules A+B (BOTH must be true = FAKE confirmed)")
    print(f"JS rendering: {'ScraperAPI (' + SCRAPER_API_KEY[:8] + '...)' if SCRAPER_API_KEY else 'NOT configured — get free key at scraperapi.com'}")
    print(f"Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min\n")
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)