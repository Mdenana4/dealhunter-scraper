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
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from fake_checker import check_price_history

load_dotenv()

MIN_DISCOUNT    = int(os.getenv("MIN_DISCOUNT", 40))
INTERVAL        = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 3))
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")

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
firebase_key_json = os.getenv("FIREBASE_KEY_JSON")

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
    raise Exception("No Firebase key found.")

firebase_admin.initialize_app(cred)
db = firestore.client()
print("Connected to Firebase successfully!")


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
def fetch_with_scraperapi(url, render_js=True, country="eg"):
    if not SCRAPER_API_KEY:
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

    except Exception as e:
        print(f"  SAVE ERROR: {e}")


def build_deal(title, site, site_display, category, current_price, original_price,
               discount, image_url, product_url, rating=0.0, review_count=None,
               asin=None, kanbkam_result=None, coupon_codes=None):
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
        "currency":             "EGP",
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
# AMAZON EGYPT
# ─────────────────────────────────────────────────────
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


def scrape_amazon():
    print("\n[AMAZON] Starting — with Kanbkam+Safqa check...")
    total = 0

    for item in AMAZON_KEYWORDS:
        try:
            url = f"https://www.amazon.eg/s?k={item['k'].replace(' ', '+')}&language=en_AE"
            resp = fetch_direct(url)
            if not resp or resp.status_code != 200:
                time.sleep(2)
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

                    # ✅ FIX: Apply MIN_PRICE / MAX_PRICE filter
                    if not price_in_range(current_price):
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

                    product_url = f"https://www.amazon.eg/dp/{asin}?language=en_AE"
                    cat = detect_category(title)
                    if cat == "general":
                        cat = item["cat"]

                    print(f"    Checking: {title[:35]}...")
                    kb = check_price_history(
                        asin=asin,
                        product_url=product_url,
                        current_price=current_price,
                        original_price=original_price,
                        title=title,
                        site="amazon_eg"
                    )
                    time.sleep(1)

                    deal = build_deal(
                        title=title,
                        site="amazon_eg",
                        site_display="Amazon Egypt",
                        category=cat,
                        current_price=current_price,
                        original_price=original_price,
                        discount=discount,
                        image_url=image_url,
                        product_url=product_url,
                        rating=rating,
                        review_count=review_count,
                        asin=asin,
                        kanbkam_result=kb
                    )
                    save_deal(deal)
                    total += 1
                    time.sleep(0.5)

                except Exception:
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  Amazon keyword error '{item['k']}': {e}")
            time.sleep(5)

    print(f"[AMAZON] Done. {total} deals.")
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
        ("https://btech.com/en/mobiles-and-tablets.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/laptops-and-computers.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/tv-and-audio.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "electronics"),
        ("https://btech.com/en/home-appliances.html?pageSize=48&product_list_order=discount_percent&product_list_dir=desc", "home"),
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
        # ✅ FIX: Try multiple Carrefour API URL formats (they change periodically)
        api_urls = [
            f"https://www.carrefouregypt.com/api/v7/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc",
            f"https://www.carrefouregypt.com/mafegy/en/c/{cat_id}?pageSize=48&sortBy=discountPercentage&sortOrder=desc&format=json",
            f"https://www.carrefouregypt.com/api/v6/page?url=/mafegy/en/c/{cat_id}&page=0&pageSize=48&sortBy=discountPercentage&sortOrder=desc",
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
    pages = [
        ("https://www.sharafdg.com/en/eg/deals",             "electronics"),
        ("https://www.sharafdg.com/en/eg/mobiles-tablets",   "electronics"),
        ("https://www.sharafdg.com/en/eg/computers-laptops",  "electronics"),
        ("https://www.sharafdg.com/en/eg/tv-video-audio",    "electronics"),
        ("https://www.sharafdg.com/en/eg/home-appliances",   "home"),
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
                soup.find_all("li",  class_=lambda c: c and "item" in str(c) and "product" in str(c)) or
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
def scrape_noon():
    print("\n[NOON] Starting — ScraperAPI JS rendering...")
    total = 0
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
            url = f"https://www.noon.com/egypt-en/search/?q={term.replace(' ', '+')}&limit=48&sort%5Bby%5D=discount&sort%5Bdir%5D=desc"
            resp = fetch_with_scraperapi(url, render_js=True, country="eg")
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue

            content = resp.text
            products_found = 0

            # Try JSON extraction first
            json_patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});\s*(?:window|</script>)',
                r'"products"\s*:\s*(\[.+?\])',
                r'"hits"\s*:\s*\{"hits"\s*:\s*(\[.+?\])',
            ]

            for pattern in json_patterns:
                match = re.search(pattern, content, re.DOTALL)
                if not match:
                    continue
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
                            src   = item.get("_source", item)
                            title = src.get("name", "") or src.get("title", "")
                            if not title:
                                continue
                            cp = clean_price(str(
                                src.get("price", {}).get("value", 0) or
                                src.get("sale_price", 0) or
                                src.get("price", 0)
                            ))
                            op = clean_price(str(
                                src.get("price", {}).get("was", cp) or
                                src.get("was_price", cp) or
                                src.get("original_price", cp) or cp
                            ))
                            if cp < 50:
                                continue
                            if not price_in_range(cp):
                                continue
                            if op < cp:
                                op = cp
                            disc = calculate_discount(op, cp)
                            if disc < MIN_DISCOUNT:
                                continue

                            img_keys = src.get("image_keys", [])
                            img  = f"https://f.nooncdn.com/p/{img_keys[0]}.jpg" if img_keys else (src.get("image", "") or "")
                            sku  = src.get("sku", "") or src.get("id", "")
                            purl = f"https://www.noon.com/egypt-en/{sku}/" if sku else ""
                            rating = float(src.get("rating", {}).get("value", 0) or src.get("rating", 0) or 0)
                            rc     = int(src.get("rating", {}).get("count", 0) or src.get("review_count", 0) or 0) or None
                            cat    = detect_category(title) or default_cat

                            kb = check_price_history(
                                product_url=purl, current_price=cp,
                                original_price=op, title=title, site="noon_eg"
                            )

                            deal = build_deal(
                                title=title, site="noon_eg", site_display="Noon Egypt",
                                category=cat, current_price=cp, original_price=op,
                                discount=disc, image_url=img, product_url=purl,
                                rating=rating, review_count=rc, kanbkam_result=kb
                            )
                            save_deal(deal)
                            total += 1
                            products_found += 1
                        except Exception:
                            continue

                    if products_found > 0:
                        break
                except Exception:
                    continue

            # HTML fallback
            if products_found == 0:
                soup = BeautifulSoup(content, "lxml")
                product_blocks = (
                    soup.find_all("div", attrs={"data-qa": "product-block"}) or
                    soup.find_all("div", class_=lambda c: c and "productContainer" in str(c)) or
                    soup.find_all("article")
                )
                for p in product_blocks:
                    try:
                        title_el = (
                            p.find(class_=lambda c: c and "name" in str(c)) or
                            p.find("h2") or
                            p.find("p", class_=lambda c: c and "name" in str(c))
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        price_el = (
                            p.find("strong", class_=lambda c: c and "price" in str(c)) or
                            p.find("span",   class_=lambda c: c and "price" in str(c)) or
                            p.find(class_="price")
                        )
                        if not price_el:
                            continue
                        cp = clean_price(price_el.get_text())
                        if cp < 50 or not price_in_range(cp):
                            continue

                        orig_el = (
                            p.find("span", class_=lambda c: c and ("was" in str(c) or "old" in str(c))) or
                            p.find("del")
                        )
                        op = clean_price(orig_el.get_text()) if orig_el else cp
                        if op < cp:
                            op = cp
                        disc = calculate_discount(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue

                        link_el = p.find("a", href=True)
                        href    = link_el["href"] if link_el else ""
                        purl    = "https://www.noon.com" + href if href.startswith("/") else href

                        img_el = p.find("img")
                        img    = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                        cat    = detect_category(title) or default_cat

                        kb = check_price_history(
                            product_url=purl, current_price=cp,
                            original_price=op, title=title, site="noon_eg"
                        )

                        deal = build_deal(
                            title=title, site="noon_eg", site_display="Noon Egypt",
                            category=cat, current_price=cp, original_price=op,
                            discount=disc, image_url=img, product_url=purl, kanbkam_result=kb
                        )
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
# HYPERONE — ScraperAPI + HTML fallback
# ─────────────────────────────────────────────────────
def scrape_hyperone():
    print("\n[HYPERONE] Starting...")
    total = 0
    pages = [
        ("https://www.hyperone.com.eg/offers/",                          "general"),
        ("https://www.hyperone.com.eg/electronics/",                     "electronics"),
        ("https://www.hyperone.com.eg/home-appliances/",                 "home"),
        ("https://www.hyperone.com.eg/mobiles-and-accessories/",         "electronics"),
    ]

    for url, default_cat in pages:
        try:
            resp = fetch_with_scraperapi(url, render_js=True, country="eg")
            if not resp or resp.status_code != 200:
                resp = fetch_direct(url)
            if not resp or resp.status_code != 200:
                time.sleep(2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            products = (
                soup.find_all("li",      class_=lambda c: c and "product" in str(c)) or
                soup.find_all("div",     class_=lambda c: c and "product" in str(c) and "item" in str(c)) or
                soup.find_all("article") or
                soup.find_all("div",     class_=lambda c: c and "product-card" in str(c))
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
    api_base    = "https://sahlaapp.com/api/v2"
    api_headers = {
        "Accept":       "application/json",
        "User-Agent":   "Sahla/2.0 (com.sahla.app; iOS 16.0)",
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
                    data  = resp.json()
                    items = data.get("data", data.get("products", data.get("offers", data.get("items", []))))
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
                            purl = f"https://sahlaapp.com/product/{pid}"
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
                    continue
                except Exception:
                    pass
        except Exception as e:
            print(f"  [SAHLA] API error: {e}")

    # ScraperAPI HTML fallback
    if total == 0:
        try:
            url  = "https://sahlaapp.com/products?sort=discount"
            resp = fetch_with_scraperapi(url, render_js=True, country="eg")
            if resp and resp.status_code == 200:
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
        except Exception as e:
            print(f"  [SAHLA] ScraperAPI error: {e}")

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
    try:
        deals       = [d.to_dict() for d in db.collection("deals").get()]
        users       = list(db.collection("users").get())
        site_counts = {}
        cat_counts  = {}
        verdict_counts = {}
        clicks      = 0
        buys        = 0
        fake_count  = 0

        for d in deals:
            s = d.get("site", "?")
            c = d.get("category", "general")
            v = d.get("fake_verdict", "UNVERIFIED")
            site_counts[s]    = site_counts.get(s, 0) + 1
            cat_counts[c]     = cat_counts.get(c, 0) + 1
            verdict_counts[v] = verdict_counts.get(v, 0) + 1
            clicks     += d.get("click_count", 0)
            buys       += d.get("buy_click_count", 0)
            if v == "FAKE":
                fake_count += 1

        db.collection("analytics").document("summary").set({
            "total_deals":    len(deals),
            "total_users":    len(users),
            "site_counts":    site_counts,
            "category_counts": cat_counts,
            "verdict_counts": verdict_counts,
            "total_clicks":   clicks,
            "total_buy_clicks": buys,
            "fake_deals_count": fake_count,
            "last_updated":   now_iso()
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

    print(f"\n{'=' * 62}")
    print(f"  SCRAPE CYCLE: {now_str()}")
    if SCRAPER_API_KEY:
        print(f"  ScraperAPI: ACTIVE (JS rendering for Noon/HyperOne/Sahla)")
    else:
        print(f"  ScraperAPI: NOT SET — get free key at scraperapi.com")
    if MIN_PRICE > 0 or MAX_PRICE < 9999999:
        print(f"  Price filter: EGP {MIN_PRICE:,.0f} – EGP {MAX_PRICE:,.0f}")
    print(f"{'=' * 62}")

    total = 0
    total += scrape_amazon()
    total += scrape_jumia()
    total += scrape_btech()
    total += scrape_carrefour()
    total += scrape_sharaf_dg()
    total += scrape_noon()
    total += scrape_hyperone()
    total += scrape_sahla()
    total += scrape_custom_sources()

    update_analytics()
    print(f"\n  TOTAL: {total} deals | Next in: {INTERVAL} min")
    print(f"{'=' * 62}\n")


if __name__ == "__main__":
    print("DealHunter Egypt Scraper v7 FIXED")
    print(f"Stores: Amazon + Jumia + B.Tech + Carrefour + Sharaf DG + Noon + HyperOne + Sahla")
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
