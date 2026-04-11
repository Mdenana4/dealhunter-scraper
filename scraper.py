# DealHunter Egypt - Scraper v4
# Fixed: RSS removed, datetime warning fixed, Kanbkam auto-check,
# always update deals, 80+ keywords, EGP 50 minimum, all categories

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

load_dotenv()

MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", 40))
INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 3))

# ─────────────────────────────────────────────────────
# CONNECT TO FIREBASE
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
# HELPERS
# ─────────────────────────────────────────────────────

def now_iso():
    """Fixed: use timezone-aware datetime instead of deprecated utcnow()"""
    return datetime.now(timezone.utc).isoformat()

def now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def calculate_discount(original, current):
    if original <= 0 or current <= 0 or current >= original:
        return 0
    return round(((original - current) / original) * 100)

def generate_deal_id(site, url, price):
    raw = f"{site}_{url}_{price}"
    return hashlib.md5(raw.encode()).hexdigest()

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

def detect_category(title):
    t = title.lower()
    if re.search(r'phone|mobile|iphone|samsung|xiaomi|oppo|vivo|realme|laptop|notebook|tablet|ipad|computer|monitor|keyboard|mouse|headphone|earphone|earbuds|airpods|speaker|camera|tv |television|gaming|playstation|xbox|console|router|charger|cable|battery|power.?bank|smartwatch|smart.?watch|flash.?drive|usb|ssd|hard.?disk|printer|projector|drone|gpu|processor|ram|motherboard', t):
        return "electronics"
    elif re.search(r'dress|shirt|shoes|bag|watch|perfume|jeans|jacket|sneaker|sandal|handbag|wallet|belt|hat|cap|suit|blouse|skirt|coat|boots|heel|polo|t-shirt|tshirt|underwear|socks|scarf|glasses|sunglasses|leggings|shorts|hoodie|sweatshirt|bra|bikini|swimsuit|tie|gloves', t):
        return "fashion"
    elif re.search(r'sofa|chair|bed|table|lamp|kitchen|blender|cookware|vacuum|air.?condition|refrigerator|washing.?machine|oven|microwave|curtain|pillow|mattress|shelf|cabinet|wardrobe|couch|fan|heater|iron|kettle|toaster|coffee.?maker|air.?fryer|pressure.?cooker|dish.?washer|water.?filter|humidifier', t):
        return "home"
    elif re.search(r'cream|serum|shampoo|makeup|skincare|moisturizer|lotion|vitamin|supplement|face.?wash|hair|nail|lipstick|foundation|mascara|eyeliner|blush|concealer|toner|sunscreen|body.?wash|deodorant|cologne|body.?lotion|hair.?dryer|straightener|curler|razor|trimmer', t):
        return "beauty"
    elif re.search(r'gym|sport|fitness|yoga|bicycle|bike|football|tennis|treadmill|dumbbell|resistance.?band|protein|swimming|running|cycling|basketball|volleyball|badminton|ping.?pong|soccer|weights|barbell|jump.?rope|boxing|martial', t):
        return "sports"
    elif re.search(r'toy|baby|kids|children|doll|lego|puzzle|infant|toddler|stroller|diaper|formula|feeding|play|educational|board.?game|action.?figure|remote.?control.?car', t):
        return "toys"
    elif re.search(r'car|auto|vehicle|tire|wheel|motor.?oil|engine|spare.?part|seat.?cover|dashboard|steering|battery.?car|wiper|horn|exhaust', t):
        return "automotive"
    elif re.search(r'food|grocery|snack|drink|juice|water|rice|pasta|oil|sugar|coffee|tea|chocolate|biscuit|chips|sauce|spice|flour|bread|milk|cheese|yogurt|egg|meat|fish|vegetable|fruit|organic|date|honey|jam|cereal|protein.?bar', t):
        return "grocery"
    elif re.search(r'book|novel|textbook|stationery|pen|notebook|pencil|magazine|dictionary|encyclopedia|academic|school|university|learning|study', t):
        return "books"
    return "general"

# ─────────────────────────────────────────────────────
# KANBKAM AUTO-CHECK
# Checks real price history for Amazon products
# ─────────────────────────────────────────────────────

def check_kanbkam(asin, current_price, original_price, title):
    """
    Automatically checks Kanbkam.com for real price history of an Amazon product.
    Returns dict with: lowest_price, highest_price, verdict, verdict_ar, fake_score
    """
    try:
        # Build Kanbkam URL from ASIN
        # Kanbkam uses product slug + ASIN format
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:60].strip('-')
        kanbkam_url = f"https://www.kanbkam.com/eg/ar/{slug}-{asin}"

        headers = get_headers()
        headers["Accept-Language"] = "ar,en;q=0.9"

        resp = requests.get(kanbkam_url, headers=headers, timeout=15)

        if resp.status_code != 200:
            # Try alternate URL format
            kanbkam_url = f"https://www.kanbkam.com/eg/ar/search?q={asin}"
            resp = requests.get(kanbkam_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return build_local_check(current_price, original_price)

        soup = BeautifulSoup(resp.content, "lxml")
        text = soup.get_text()

        # Extract prices from Kanbkam page
        # Kanbkam shows: أقل سعر (lowest), أعلى سعر (highest), سعر حاليا (current)
        lowest_price = 0
        highest_price = 0

        # Find price numbers on the page
        price_patterns = re.findall(r'(\d[\d,]*)\s*(?:جنية|جنيه|EGP|ج\.م)', text)
        prices = []
        for p in price_patterns:
            try:
                val = float(p.replace(',', ''))
                if 10 < val < 500000:
                    prices.append(val)
            except:
                pass

        # Also check for أقل سعر (lowest price) label
        lowest_match = re.search(r'أقل\s*سعر[\s\S]{0,50}?(\d[\d,]+)', text)
        highest_match = re.search(r'أعلى\s*سعر[\s\S]{0,50}?(\d[\d,]+)', text)

        if lowest_match:
            try:
                lowest_price = float(lowest_match.group(1).replace(',', ''))
            except:
                pass
        if highest_match:
            try:
                highest_price = float(highest_match.group(1).replace(',', ''))
            except:
                pass

        # If direct extraction failed, use price list
        if lowest_price == 0 and prices:
            prices_filtered = sorted([p for p in prices if p > 50])
            if prices_filtered:
                lowest_price = prices_filtered[0]
                highest_price = prices_filtered[-1]

        if lowest_price > 0 and highest_price > 0:
            return build_verdict(current_price, original_price, lowest_price, highest_price, kanbkam_url)
        else:
            # Kanbkam found but couldn't extract — use local analysis
            return build_local_check(current_price, original_price)

    except Exception as e:
        print(f"  [KANBKAM] Error: {e}")
        return build_local_check(current_price, original_price)


def build_verdict(current_price, original_price, lowest_price, highest_price, kanbkam_url=""):
    """Build verdict based on Kanbkam real price history"""

    # Real discount vs lowest price ever
    if lowest_price > 0 and current_price > 0:
        real_discount_vs_lowest = round((current_price - lowest_price) / lowest_price * 100)
    else:
        real_discount_vs_lowest = 0

    # Is current price near the lowest ever?
    near_lowest = current_price <= (lowest_price * 1.15)  # within 15% of lowest

    # Is original price inflated? (original > highest ever seen?)
    inflated_original = original_price > (highest_price * 1.1) if highest_price > 0 else False

    # Amazon's claimed discount
    claimed_discount = calculate_discount(original_price, current_price)

    # Verdict logic
    if inflated_original and near_lowest:
        verdict = "GENUINE"
        verdict_ar = "خصم حقيقي"
        fake_score = 15
        reason = f"Current price EGP {current_price:,.0f} is near the lowest ever (EGP {lowest_price:,.0f}). Good deal!"
        reason_ar = f"السعر الحالي {current_price:,.0f} جنيه قريب من أقل سعر ({lowest_price:,.0f} جنيه). صفقة جيدة!"
        emoji = "✅"
    elif near_lowest:
        verdict = "GENUINE"
        verdict_ar = "خصم حقيقي"
        fake_score = 20
        reason = f"Current price EGP {current_price:,.0f} is near its historical low of EGP {lowest_price:,.0f}."
        reason_ar = f"السعر الحالي قريب من أقل سعر تاريخي."
        emoji = "✅"
    elif inflated_original:
        verdict = "SUSPICIOUS"
        verdict_ar = "مشبوه"
        fake_score = 65
        reason = f"Amazon's 'original price' EGP {original_price:,.0f} seems inflated. Historical high was only EGP {highest_price:,.0f}."
        reason_ar = f"السعر الأصلي المعلن {original_price:,.0f} جنيه يبدو مبالغاً فيه. أعلى سعر تاريخي كان {highest_price:,.0f} جنيه فقط."
        emoji = "⚠️"
    elif current_price > (lowest_price * 1.4):
        verdict = "WAIT"
        verdict_ar = "انتظر"
        fake_score = 45
        reason = f"Price was EGP {lowest_price:,.0f} before. Current price EGP {current_price:,.0f} is {real_discount_vs_lowest}% above historical low. Wait for a better deal."
        reason_ar = f"السعر كان {lowest_price:,.0f} جنيه من قبل. انتظر حتى يصل إلى {lowest_price*1.1:,.0f} جنيه."
        emoji = "⏳"
    else:
        verdict = "GENUINE"
        verdict_ar = "خصم حقيقي"
        fake_score = 25
        reason = f"Price history looks normal. Current: EGP {current_price:,.0f}, Historical low: EGP {lowest_price:,.0f}."
        reason_ar = f"تاريخ السعر طبيعي. السعر الحالي {current_price:,.0f} جنيه."
        emoji = "✅"

    return {
        "kanbkam_checked": True,
        "kanbkam_url": kanbkam_url,
        "lowest_price": lowest_price,
        "highest_price": highest_price,
        "verdict": verdict,
        "verdict_ar": verdict_ar,
        "fake_score": fake_score,
        "reason": reason,
        "reason_ar": reason_ar,
        "emoji": emoji,
        "real_discount_vs_lowest": real_discount_vs_lowest,
        "near_lowest": near_lowest,
        "suggested_wait_price": round(lowest_price * 1.05) if lowest_price > 0 else 0,
        "checked_at": now_iso()
    }


def build_local_check(current_price, original_price):
    """Fallback: local analysis when Kanbkam is not reachable"""
    ratio = original_price / current_price if current_price > 0 else 1
    claimed_discount = calculate_discount(original_price, current_price)

    if ratio > 3:
        verdict = "SUSPICIOUS"
        verdict_ar = "مشبوه - السعر الأصلي مبالغ فيه"
        fake_score = 70
        reason = f"Original price ({original_price:,.0f}) is {ratio:.1f}x the current price. Likely inflated."
        reason_ar = f"السعر الأصلي {original_price:,.0f} جنيه يبدو مبالغاً فيه (نسبة {ratio:.1f}x)."
        emoji = "⚠️"
    elif ratio > 2:
        verdict = "SUSPICIOUS"
        verdict_ar = "مشبوه"
        fake_score = 50
        reason = f"High price ratio ({ratio:.1f}x). Verify price history independently."
        reason_ar = f"نسبة سعر مرتفعة ({ratio:.1f}x). تحقق من تاريخ السعر."
        emoji = "⚠️"
    else:
        verdict = "GENUINE"
        verdict_ar = "يبدو حقيقياً"
        fake_score = 20
        reason = f"Price ratio looks normal ({ratio:.1f}x). No Kanbkam data available."
        reason_ar = f"نسبة السعر تبدو طبيعية ({ratio:.1f}x)."
        emoji = "✅"

    return {
        "kanbkam_checked": False,
        "kanbkam_url": "",
        "lowest_price": 0,
        "highest_price": 0,
        "verdict": verdict,
        "verdict_ar": verdict_ar,
        "fake_score": fake_score,
        "reason": reason,
        "reason_ar": reason_ar,
        "emoji": emoji,
        "real_discount_vs_lowest": 0,
        "near_lowest": False,
        "suggested_wait_price": 0,
        "checked_at": now_iso()
    }

# ─────────────────────────────────────────────────────
# SAVE DEAL TO FIREBASE
# Always update — never skip existing deals
# ─────────────────────────────────────────────────────

def save_deal(deal):
    deal_id = deal["deal_id"]
    ref = db.collection("deals").document(deal_id)
    try:
        existing = ref.get()
        if existing.exists:
            # ALWAYS update — never skip
            # This ensures prices stay fresh every cycle
            old_data = existing.to_dict()
            old_price = old_data.get("current_price", 0)
            new_price = deal["current_price"]

            update_data = {
                "current_price": new_price,
                "discount_percent": deal["discount_percent"],
                "timestamp": deal["timestamp"],
                "image_url": deal.get("image_url", ""),
                "rating": deal.get("rating", 0),
            }

            # Add Kanbkam check data if available
            if deal.get("kanbkam"):
                update_data["kanbkam"] = deal["kanbkam"]
                update_data["fake_verdict"] = deal["kanbkam"].get("verdict", "UNKNOWN")
                update_data["fake_verdict_ar"] = deal["kanbkam"].get("verdict_ar", "")
                update_data["fake_emoji"] = deal["kanbkam"].get("emoji", "")

            ref.update(update_data)

            if old_price != new_price:
                # Log price change to history
                ref.collection("price_history").document().set({
                    "price": new_price,
                    "old_price": old_price,
                    "timestamp": deal["timestamp"]
                })
                print(f"  UPDATED: {deal['title'][:50]} | EGP {old_price:,.0f} → {new_price:,.0f} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
            else:
                print(f"  REFRESHED: {deal['title'][:50]} | EGP {new_price:,.0f} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")
        else:
            # Brand new deal
            ref.set(deal)
            ref.collection("price_history").document().set({
                "price": deal["current_price"],
                "timestamp": deal["timestamp"]
            })
            print(f"  NEW: {deal['title'][:50]} | {deal['discount_percent']}% OFF | EGP {deal['current_price']:,.0f} | {deal.get('fake_emoji','')} {deal.get('fake_verdict','')}")

        # Track click analytics
        analytics_ref = db.collection("analytics").document("summary")
        try:
            analytics_ref.set({"last_scrape": now_iso()}, merge=True)
        except:
            pass

    except Exception as e:
        print(f"  ERROR saving: {e}")

# ─────────────────────────────────────────────────────
# AMAZON EGYPT SCRAPER — 80+ KEYWORDS ALL CATEGORIES
# ─────────────────────────────────────────────────────

AMAZON_KEYWORDS = [
    # Electronics
    {"k": "samsung galaxy", "cat": "electronics"},
    {"k": "iphone", "cat": "electronics"},
    {"k": "xiaomi", "cat": "electronics"},
    {"k": "oppo", "cat": "electronics"},
    {"k": "realme phone", "cat": "electronics"},
    {"k": "laptop", "cat": "electronics"},
    {"k": "lenovo laptop", "cat": "electronics"},
    {"k": "dell laptop", "cat": "electronics"},
    {"k": "hp laptop", "cat": "electronics"},
    {"k": "asus laptop", "cat": "electronics"},
    {"k": "macbook", "cat": "electronics"},
    {"k": "tablet android", "cat": "electronics"},
    {"k": "ipad", "cat": "electronics"},
    {"k": "headphones wireless", "cat": "electronics"},
    {"k": "sony headphones", "cat": "electronics"},
    {"k": "jbl speaker", "cat": "electronics"},
    {"k": "earbuds bluetooth", "cat": "electronics"},
    {"k": "smart watch", "cat": "electronics"},
    {"k": "huawei watch", "cat": "electronics"},
    {"k": "samsung watch", "cat": "electronics"},
    {"k": "led tv", "cat": "electronics"},
    {"k": "samsung tv", "cat": "electronics"},
    {"k": "lg tv", "cat": "electronics"},
    {"k": "gaming monitor", "cat": "electronics"},
    {"k": "playstation", "cat": "electronics"},
    {"k": "xbox", "cat": "electronics"},
    {"k": "camera digital", "cat": "electronics"},
    {"k": "power bank", "cat": "electronics"},
    {"k": "router wifi", "cat": "electronics"},
    {"k": "ssd hard disk", "cat": "electronics"},
    {"k": "keyboard mouse", "cat": "electronics"},
    {"k": "graphics card", "cat": "electronics"},
    # Fashion
    {"k": "nike shoes", "cat": "fashion"},
    {"k": "adidas", "cat": "fashion"},
    {"k": "puma shoes", "cat": "fashion"},
    {"k": "reebok", "cat": "fashion"},
    {"k": "mens shirt", "cat": "fashion"},
    {"k": "womens dress", "cat": "fashion"},
    {"k": "handbag", "cat": "fashion"},
    {"k": "leather wallet", "cat": "fashion"},
    {"k": "sunglasses", "cat": "fashion"},
    {"k": "perfume men", "cat": "fashion"},
    {"k": "perfume women", "cat": "fashion"},
    {"k": "sneakers", "cat": "fashion"},
    {"k": "jeans", "cat": "fashion"},
    {"k": "jacket", "cat": "fashion"},
    # Home & Kitchen
    {"k": "air conditioner", "cat": "home"},
    {"k": "refrigerator", "cat": "home"},
    {"k": "washing machine", "cat": "home"},
    {"k": "microwave oven", "cat": "home"},
    {"k": "air fryer", "cat": "home"},
    {"k": "blender", "cat": "home"},
    {"k": "coffee maker", "cat": "home"},
    {"k": "vacuum cleaner", "cat": "home"},
    {"k": "electric kettle", "cat": "home"},
    {"k": "cookware set", "cat": "home"},
    {"k": "bedding set", "cat": "home"},
    {"k": "water filter", "cat": "home"},
    {"k": "electric fan", "cat": "home"},
    {"k": "heater electric", "cat": "home"},
    # Beauty & Health
    {"k": "face cream", "cat": "beauty"},
    {"k": "hair dryer", "cat": "beauty"},
    {"k": "electric shaver", "cat": "beauty"},
    {"k": "vitamin supplement", "cat": "beauty"},
    {"k": "makeup kit", "cat": "beauty"},
    {"k": "shampoo", "cat": "beauty"},
    {"k": "skincare set", "cat": "beauty"},
    {"k": "hair straightener", "cat": "beauty"},
    # Sports
    {"k": "gym equipment", "cat": "sports"},
    {"k": "protein powder", "cat": "sports"},
    {"k": "treadmill", "cat": "sports"},
    {"k": "bicycle", "cat": "sports"},
    {"k": "yoga mat", "cat": "sports"},
    {"k": "dumbbell set", "cat": "sports"},
    {"k": "football", "cat": "sports"},
    # Toys & Baby
    {"k": "lego", "cat": "toys"},
    {"k": "baby stroller", "cat": "toys"},
    {"k": "remote control car", "cat": "toys"},
    {"k": "educational toys", "cat": "toys"},
    # Grocery
    {"k": "protein bar", "cat": "grocery"},
    {"k": "organic honey", "cat": "grocery"},
    {"k": "coffee beans", "cat": "grocery"},
    # Books
    {"k": "arabic novel", "cat": "books"},
    {"k": "self help book", "cat": "books"},
]


def scrape_amazon_egypt():
    print("\n[AMAZON] Starting scrape — 80+ keywords across all categories...")
    total = 0

    for item in AMAZON_KEYWORDS:
        keyword = item["k"]
        default_cat = item["cat"]

        try:
            url = f"https://www.amazon.eg/s?k={keyword.replace(' ','+')}&language=en_AE"
            print(f"  [{default_cat.upper()}] Searching: {keyword}...")

            resp = requests.get(url, headers=get_headers(), timeout=20)
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} — skipping")
                time.sleep(2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")

            # Find all products with ASIN
            products = soup.find_all("div", attrs={"data-asin": True})
            products = [p for p in products if p.get("data-asin", "").strip()]

            found_deals = 0

            for product in products:
                try:
                    asin = product.get("data-asin", "").strip()
                    if not asin:
                        continue

                    # Skip sponsored ads
                    if product.get("data-component-type") == "sp-sponsored-result":
                        continue
                    if "AdHolder" in " ".join(product.get("class", [])):
                        continue

                    # Title
                    title_el = (
                        product.find("h2") or
                        product.find("span", class_="a-size-medium") or
                        product.find("span", class_="a-size-base-plus") or
                        product.find("span", class_="a-size-large")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 6:
                        continue

                    # Current price
                    price_el = product.find("span", class_="a-price-whole")
                    if not price_el:
                        continue
                    price_text = price_el.get_text(strip=True).replace(",", "").replace(".", "").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue

                    # Minimum EGP 50 (was 200, now 50 as requested)
                    if current_price < 50:
                        continue

                    # Original (strikethrough) price
                    original_price = current_price
                    orig_block = product.find("span", class_="a-price a-text-price")
                    if orig_block:
                        orig_el = orig_block.find("span", class_="a-offscreen")
                        if orig_el:
                            orig_text = orig_el.get_text(strip=True)
                            orig_text = orig_text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
                            try:
                                original_price = float(orig_text)
                            except:
                                original_price = current_price

                    # Check badge for discount % (Amazon sometimes shows badge even without strikethrough)
                    discount = calculate_discount(original_price, current_price)
                    badge_el = product.find("span", class_="a-badge-text")
                    if badge_el and discount < MIN_DISCOUNT:
                        badge_text = badge_el.get_text(strip=True)
                        if "%" in badge_text:
                            try:
                                nums = re.findall(r'\d+', badge_text)
                                if nums:
                                    badge_discount = int(nums[0])
                                    if badge_discount >= MIN_DISCOUNT:
                                        discount = badge_discount
                                        original_price = round(current_price / (1 - badge_discount / 100))
                            except:
                                pass

                    if discount < MIN_DISCOUNT:
                        continue

                    # Image
                    img_el = product.find("img", class_="s-image")
                    image_url = img_el.get("src", "") if img_el else ""

                    # Rating
                    rating = 0.0
                    rating_el = product.find("span", class_="a-icon-alt")
                    if rating_el:
                        try:
                            rating = float(rating_el.get_text(strip=True).split(" ")[0])
                        except:
                            pass

                    # Review count
                    review_count = 0
                    review_el = product.find("span", {"aria-label": True, "class": "a-size-base"})
                    if review_el:
                        try:
                            review_count = int(review_el.get_text(strip=True).replace(",", ""))
                        except:
                            pass

                    # Clean product URL
                    product_url = f"https://www.amazon.eg/dp/{asin}?language=en_AE"

                    # Auto-detect category from title
                    detected_cat = detect_category(title)
                    if detected_cat == "general":
                        detected_cat = default_cat

                    # ── KANBKAM AUTO-CHECK ──
                    print(f"    Checking Kanbkam for: {title[:40]}...")
                    kanbkam_result = check_kanbkam(asin, current_price, original_price, title)
                    time.sleep(1)  # Be polite to Kanbkam

                    deal = {
                        "deal_id": generate_deal_id("amazon_eg", product_url, current_price),
                        "title": title,
                        "title_ar": "",  # Will be filled by translation service in future
                        "site": "amazon_eg",
                        "site_display": "Amazon Egypt",
                        "site_display_ar": "أمازون مصر",
                        "category": detected_cat,
                        "current_price": current_price,
                        "original_price": original_price,
                        "discount_percent": discount,
                        "currency": "EGP",
                        "image_url": image_url,
                        "product_url": product_url,
                        "asin": asin,
                        "availability": "in_stock",
                        "timestamp": now_iso(),
                        "rating": rating,
                        "review_count": review_count,
                        "verified": True,
                        "hidden": False,
                        "featured": False,
                        "source": "scraper",
                        # Kanbkam fake check results
                        "kanbkam": kanbkam_result,
                        "fake_verdict": kanbkam_result.get("verdict", "UNKNOWN"),
                        "fake_verdict_ar": kanbkam_result.get("verdict_ar", ""),
                        "fake_emoji": kanbkam_result.get("emoji", ""),
                        "fake_score": kanbkam_result.get("fake_score", 50),
                        "lowest_price_ever": kanbkam_result.get("lowest_price", 0),
                        "highest_price_ever": kanbkam_result.get("highest_price", 0),
                        "suggested_wait_price": kanbkam_result.get("suggested_wait_price", 0),
                        # Analytics
                        "click_count": 0,
                        "buy_click_count": 0,
                    }

                    save_deal(deal)
                    found_deals += 1
                    total += 1

                    # Small delay between products to avoid detection
                    time.sleep(0.5)

                except Exception as e:
                    print(f"    Product error: {e}")
                    continue

            print(f"  [{default_cat.upper()}] {keyword}: {found_deals} new/updated deals")

            # Delay between keywords — be polite to Amazon
            time.sleep(3)

        except Exception as e:
            print(f"  Keyword '{keyword}' error: {e}")
            time.sleep(5)
            continue

    print(f"\n[AMAZON] Done. {total} deals saved/updated this cycle.")
    return total

# ─────────────────────────────────────────────────────
# DYNAMIC CUSTOM SOURCES SCRAPER
# Reads sources from Firebase admin collection
# and tries to scrape them automatically
# ─────────────────────────────────────────────────────

def scrape_custom_sources():
    """Scrape any custom sources the admin has added in the dashboard"""
    print("\n[CUSTOM SOURCES] Checking admin-added sources...")
    total = 0

    try:
        sources_snap = db.collection("admin").stream()
        sources = [doc.to_dict() for doc in sources_snap]
        active_sources = [s for s in sources if s.get("status") == "active" and s.get("site_url")]

        if not active_sources:
            print("  No custom active sources found.")
            return 0

        for source in active_sources:
            site_name = source.get("site_name", "Unknown")
            site_url = source.get("site_url", "")
            site_id = source.get("id", site_name.lower().replace(" ", "_"))

            # Skip the default sources — handled separately
            if site_url in ["https://www.amazon.eg", "https://www.noon.com/egypt-en"]:
                continue

            print(f"\n  Scraping: {site_name} ({site_url})...")

            try:
                resp = requests.get(site_url, headers=get_headers(), timeout=20)
                if resp.status_code != 200:
                    print(f"  HTTP {resp.status_code} for {site_name}")
                    # Update source status in Firebase
                    db.collection("admin").where("site_url", "==", site_url).limit(1)
                    continue

                soup = BeautifulSoup(resp.content, "lxml")

                # Generic product detection — works for most e-commerce sites
                # Try multiple common e-commerce HTML patterns
                products = (
                    soup.find_all("div", class_=lambda c: c and any(k in str(c).lower() for k in ["product", "item", "card"])) or
                    soup.find_all("article") or
                    soup.find_all("li", class_=lambda c: c and "product" in str(c).lower())
                )

                # Limit to first 50 to avoid processing too many
                products = products[:50]
                found = 0

                for product in products:
                    try:
                        # Generic title extraction
                        title_el = (
                            product.find("h1") or product.find("h2") or product.find("h3") or
                            product.find(class_=lambda c: c and "title" in str(c).lower() or "name" in str(c).lower())
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        # Generic price extraction
                        price_el = (
                            product.find(class_=lambda c: c and "price" in str(c).lower()) or
                            product.find("strong") or
                            product.find("span", class_=lambda c: c and "price" in str(c).lower())
                        )
                        if not price_el:
                            continue

                        price_text = price_el.get_text(strip=True)
                        price_text = re.sub(r'[^\d.]', '', price_text.replace(',', ''))
                        try:
                            current_price = float(price_text)
                        except:
                            continue
                        if current_price < 50:
                            continue

                        # Generic original price
                        orig_el = product.find("del") or product.find(class_=lambda c: c and ("old" in str(c).lower() or "was" in str(c).lower() or "original" in str(c).lower()))
                        original_price = current_price
                        if orig_el:
                            orig_text = re.sub(r'[^\d.]', '', orig_el.get_text(strip=True).replace(',', ''))
                            try:
                                original_price = float(orig_text)
                            except:
                                pass

                        discount = calculate_discount(original_price, current_price)
                        if discount < MIN_DISCOUNT:
                            continue

                        # Generic link
                        link_el = product.find("a")
                        product_url = ""
                        if link_el:
                            href = link_el.get("href", "")
                            product_url = href if href.startswith("http") else site_url.rstrip("/") + "/" + href.lstrip("/")

                        # Generic image
                        img_el = product.find("img")
                        image_url = img_el.get("src", "") if img_el else ""

                        category = detect_category(title)

                        deal = {
                            "deal_id": generate_deal_id(site_id, product_url or title, current_price),
                            "title": title,
                            "site": site_id,
                            "site_display": site_name,
                            "site_display_ar": site_name,
                            "category": category,
                            "current_price": current_price,
                            "original_price": original_price,
                            "discount_percent": discount,
                            "currency": "EGP",
                            "image_url": image_url,
                            "product_url": product_url,
                            "availability": "in_stock",
                            "timestamp": now_iso(),
                            "rating": 0.0,
                            "review_count": 0,
                            "verified": False,
                            "hidden": False,
                            "featured": False,
                            "source": "scraper_custom",
                            "kanbkam": {"verdict": "UNKNOWN", "kanbkam_checked": False},
                            "fake_verdict": "UNKNOWN",
                            "fake_emoji": "❓",
                            "fake_score": 50,
                            "click_count": 0,
                            "buy_click_count": 0,
                        }

                        save_deal(deal)
                        found += 1
                        total += 1

                    except Exception as e:
                        continue

                print(f"  {site_name}: {found} deals found")

                # Update last_scraped in Firebase
                try:
                    docs = db.collection("admin").where("site_url", "==", site_url).limit(1).get()
                    for doc in docs:
                        doc.reference.update({"last_scraped": now_iso(), "last_count": found})
                except:
                    pass

                time.sleep(3)

            except Exception as e:
                print(f"  Error scraping {site_name}: {e}")
                continue

    except Exception as e:
        print(f"  Custom sources error: {e}")

    print(f"[CUSTOM SOURCES] Done. {total} deals from custom sources.")
    return total

# ─────────────────────────────────────────────────────
# TRACK ANALYTICS
# ─────────────────────────────────────────────────────

def update_analytics():
    """Update overall analytics summary in Firebase"""
    try:
        deals_snap = db.collection("deals").get()
        users_snap = db.collection("users").get()
        deals_count = len(deals_snap.docs)
        users_count = len(users_snap.docs)

        # Count by site
        site_counts = {}
        cat_counts = {}
        click_total = 0
        buy_total = 0
        for doc in deals_snap.docs:
            d = doc.to_dict()
            site = d.get("site", "unknown")
            cat = d.get("category", "general")
            site_counts[site] = site_counts.get(site, 0) + 1
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            click_total += d.get("click_count", 0)
            buy_total += d.get("buy_click_count", 0)

        db.collection("analytics").document("summary").set({
            "total_deals": deals_count,
            "total_users": users_count,
            "site_counts": site_counts,
            "category_counts": cat_counts,
            "total_clicks": click_total,
            "total_buy_clicks": buy_total,
            "last_updated": now_iso()
        }, merge=True)

        print(f"  Analytics updated: {deals_count} deals, {users_count} users, {click_total} clicks, {buy_total} buys")
    except Exception as e:
        print(f"  Analytics error: {e}")

# ─────────────────────────────────────────────────────
# MAIN SCRAPE CYCLE
# ─────────────────────────────────────────────────────

def run_scraper():
    now = now_str()
    print(f"\n{'='*55}")
    print(f"  SCRAPE CYCLE: {now}")
    print(f"  Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min")
    print(f"{'='*55}")

    total = 0
    total += scrape_amazon_egypt()
    total += scrape_custom_sources()

    print(f"\n  Updating analytics...")
    update_analytics()

    print(f"\n  TOTAL THIS CYCLE: {total} deals saved/updated")
    print(f"  Next run in {INTERVAL} minutes")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    print("DealHunter Egypt Scraper v4")
    print(f"Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min")
    print(f"Keywords: {len(AMAZON_KEYWORDS)} across all categories")
    print(f"Features: Kanbkam auto-check, always update, custom sources\n")

    run_scraper()

    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)