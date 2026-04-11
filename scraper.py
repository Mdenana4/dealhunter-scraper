# DealHunter Egypt - Scraper v2
# Fixed URLs for better deal quality + improved Noon scraping

import requests
import schedule
import time
import json
import hashlib
import os
from bs4 import BeautifulSoup
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", 40))
INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 3))

# ─────────────────────────────────────────
# CONNECT TO FIREBASE
# ─────────────────────────────────────────
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
    print("Firebase key loaded from firebase-key.json file.")
else:
    raise Exception("No Firebase key found.")

firebase_admin.initialize_app(cred)
db = firestore.client()
print("Connected to Firebase successfully!")

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def calculate_discount(original, current):
    if original <= 0 or current <= 0 or current >= original:
        return 0
    return round(((original - current) / original) * 100)

def generate_deal_id(site, url, price):
    raw = f"{site}_{url}_{price}"
    return hashlib.md5(raw.encode()).hexdigest()

def save_deal(deal):
    deal_id = deal["deal_id"]
    ref = db.collection("deals").document(deal_id)
    try:
        existing = ref.get()
        if existing.exists:
            old_price = existing.to_dict().get("current_price", 0)
            if old_price != deal["current_price"]:
                ref.update({
                    "current_price": deal["current_price"],
                    "discount_percent": deal["discount_percent"],
                    "timestamp": deal["timestamp"]
                })
                ref.collection("price_history").document().set({
                    "price": deal["current_price"],
                    "timestamp": deal["timestamp"]
                })
                print(f"  UPDATED: {deal['title'][:50]} | EGP {old_price} → {deal['current_price']}")
            else:
                print(f"  SAME:    {deal['title'][:50]}")
        else:
            ref.set(deal)
            ref.collection("price_history").document().set({
                "price": deal["current_price"],
                "timestamp": deal["timestamp"]
            })
            print(f"  NEW:     {deal['title'][:50]} | {deal['discount_percent']}% OFF | EGP {deal['current_price']}")
    except Exception as e:
        print(f"  ERROR:   {e}")

def get_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

# ─────────────────────────────────────────
# AMAZON EGYPT — REAL DEAL PAGES
# ─────────────────────────────────────────

def scrape_amazon_egypt():
    print("\n[AMAZON] Starting scrape...")

    # These are Amazon Egypt's actual deals and discount pages
    pages = [
        {
            "url": "https://www.amazon.eg/gp/goldbox?language=en_AE",
            "category": "general"
        },
        {
            "url": "https://www.amazon.eg/s?i=electronics&rh=p_n_pct-off-with-tax%3A2493781031%7C2493782031%7C2493783031&language=en_AE&s=price-desc-rank",
            "category": "electronics"
        },
        {
            "url": "https://www.amazon.eg/s?i=fashion-womens-intl-ship&rh=p_n_pct-off-with-tax%3A2493782031%7C2493783031&language=en_AE",
            "category": "fashion"
        },
        {
            "url": "https://www.amazon.eg/s?i=computers&rh=p_n_pct-off-with-tax%3A2493781031%7C2493782031%7C2493783031&language=en_AE&s=price-desc-rank",
            "category": "electronics"
        },
        {
            "url": "https://www.amazon.eg/s?i=mobile&rh=p_n_pct-off-with-tax%3A2493781031%7C2493782031%7C2493783031&language=en_AE&s=price-desc-rank",
            "category": "electronics"
        },
    ]

    total = 0

    for page in pages:
        url = page["url"]
        category = page["category"]

        try:
            print(f"  Fetching: {url[:70]}...")
            resp = requests.get(url, headers=get_headers(), timeout=20)

            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} — skipping")
                continue

            soup = BeautifulSoup(resp.content, "lxml")

            # Find products
            products = (
                soup.find_all("div", {"data-component-type": "s-search-result"}) or
                soup.find_all("div", attrs={"data-asin": True})
            )

            # Remove products with no ASIN
            products = [p for p in products if p.get("data-asin", "").strip()]

            print(f"  Found {len(products)} products")

            for product in products:
                try:
                    # Skip ads
                    if "AdHolder" in product.get("class", []):
                        continue
                    if product.get("data-component-type") == "sp-sponsored-result":
                        continue

                    # ASIN — unique product ID on Amazon
                    asin = product.get("data-asin", "")
                    if not asin:
                        continue

                    # Title
                    title_el = (
                        product.find("span", class_="a-size-medium") or
                        product.find("span", class_="a-size-base-plus") or
                        product.find("span", class_="a-size-large") or
                        product.find("h2")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 8:
                        continue

                    # Current price — must exist
                    price_el = product.find("span", class_="a-price-whole")
                    if not price_el:
                        continue
                    price_text = price_el.get_text(strip=True).replace(",", "").replace(".", "").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue

                    # Skip products under EGP 100 — these are accessories/parts not real deals
                    if current_price < 100:
                        continue

                    # Original price (strikethrough)
                    orig_price_block = product.find("span", class_="a-price a-text-price")
                    original_price = current_price
                    if orig_price_block:
                        orig_el = orig_price_block.find("span", class_="a-offscreen")
                        if orig_el:
                            orig_text = orig_el.get_text(strip=True)
                            orig_text = orig_text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
                            try:
                                original_price = float(orig_text)
                            except:
                                original_price = current_price

                    # Also check the badge text for discount %
                    badge_el = product.find("span", class_="a-badge-text")
                    badge_discount = 0
                    if badge_el:
                        badge_text = badge_el.get_text(strip=True)
                        if "%" in badge_text:
                            try:
                                badge_discount = int(badge_text.replace("%", "").replace("-", "").strip())
                            except:
                                badge_discount = 0

                    # Calculate discount
                    discount = calculate_discount(original_price, current_price)

                    # If we have a badge discount and calculated discount is 0, use badge
                    if discount == 0 and badge_discount >= MIN_DISCOUNT:
                        discount = badge_discount
                        # Estimate original from badge
                        if badge_discount > 0:
                            original_price = round(current_price / (1 - badge_discount/100))

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

                    # Product URL — use ASIN for clean URL
                    product_url = f"https://www.amazon.eg/dp/{asin}?language=en_AE"

                    # Auto-detect category from title keywords
                    title_lower = title.lower()
                    if any(k in title_lower for k in ["phone","mobile","iphone","samsung","xiaomi","laptop","tablet","ipad","computer","monitor","keyboard","mouse","headphone","earphone","speaker","camera","tv","television","gaming","playstation","xbox"]):
                        detected_cat = "electronics"
                    elif any(k in title_lower for k in ["dress","shirt","shoes","bag","watch","perfume","jeans","jacket","sneaker","sandal","handbag","wallet"]):
                        detected_cat = "fashion"
                    elif any(k in title_lower for k in ["sofa","chair","bed","kitchen","blender","cookware","vacuum","air conditioner","refrigerator","washing"]):
                        detected_cat = "home"
                    elif any(k in title_lower for k in ["cream","serum","shampoo","makeup","skincare","moisturizer","lotion","vitamin"]):
                        detected_cat = "beauty"
                    elif any(k in title_lower for k in ["gym","sport","fitness","yoga","bicycle","football","tennis"]):
                        detected_cat = "sports"
                    else:
                        detected_cat = category

                    deal = {
                        "deal_id": generate_deal_id("amazon_eg", product_url, current_price),
                        "title": title,
                        "site": "amazon_eg",
                        "site_display": "Amazon Egypt",
                        "category": detected_cat,
                        "current_price": current_price,
                        "original_price": original_price,
                        "discount_percent": discount,
                        "currency": "EGP",
                        "image_url": image_url,
                        "product_url": product_url,
                        "availability": "in_stock",
                        "timestamp": datetime.utcnow().isoformat(),
                        "rating": rating,
                        "verified": False,
                        "hidden": False,
                        "featured": False,
                    }

                    save_deal(deal)
                    total += 1

                except Exception as e:
                    print(f"  Product error: {e}")
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  Page error: {e}")
            continue

    print(f"[AMAZON] Done. {total} deals saved.")
    return total

# ─────────────────────────────────────────
# NOON EGYPT — FIXED SCRAPER
# ─────────────────────────────────────────

def scrape_noon_egypt():
    print("\n[NOON] Starting scrape...")

    # Noon Egypt sale pages
    pages = [
        {"url": "https://www.noon.com/egypt-en/sale/", "category": "general"},
        {"url": "https://www.noon.com/egypt-en/electronics/?limit=50&sort%5Bby%5D=discount&sort%5Bdir%5D=desc", "category": "electronics"},
        {"url": "https://www.noon.com/egypt-en/fashion/?limit=50&sort%5Bby%5D=discount&sort%5Bdir%5D=desc", "category": "fashion"},
        {"url": "https://www.noon.com/egypt-en/home/?limit=50&sort%5Bby%5D=discount&sort%5Bdir%5D=desc", "category": "home"},
        {"url": "https://www.noon.com/egypt-en/beauty/?limit=50&sort%5Bby%5D=discount&sort%5Bdir%5D=desc", "category": "beauty"},
    ]

    total = 0

    for page in pages:
        url = page["url"]
        category = page["category"]

        try:
            print(f"  Fetching: {url[:70]}...")

            # Noon needs slightly different headers
            headers = get_headers()
            headers["Referer"] = "https://www.noon.com/"

            resp = requests.get(url, headers=headers, timeout=20)

            if resp.status_code == 403:
                print(f"  [NOON] Blocked (403) — Noon uses heavy bot protection")
                print(f"  [NOON] This is normal — will retry next cycle")
                continue

            if resp.status_code != 200:
                print(f"  [NOON] HTTP {resp.status_code} — skipping")
                continue

            soup = BeautifulSoup(resp.content, "lxml")

            # Noon loads products via JavaScript, so HTML scraping may find 0
            # Try multiple selectors
            products = (
                soup.find_all("div", class_=lambda c: c and "productContainer" in c) or
                soup.find_all("div", attrs={"data-qa": "product-block"}) or
                soup.find_all("div", class_=lambda c: c and "sc-" in str(c) and "product" in str(c).lower()) or
                soup.find_all("article") or
                soup.find_all("div", class_="grid-item")
            )

            print(f"  Found {len(products)} products")

            if len(products) == 0:
                print(f"  [NOON] No products found — Noon uses React/JS rendering")
                print(f"  [NOON] Static scraping cannot read JS-rendered content")
                continue

            for product in products:
                try:
                    title_el = (
                        product.find("div", class_="name") or
                        product.find("p", class_="name") or
                        product.find("h2") or
                        product.find("span", class_="name")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link_el = product.find("a")
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    product_url = "https://www.noon.com" + href if href.startswith("/") else href

                    price_el = (
                        product.find("strong", class_="price") or
                        product.find("span", class_="price") or
                        product.find("div", class_="price")
                    )
                    if not price_el:
                        continue
                    price_text = price_el.get_text(strip=True).replace(",","").replace("EGP","").replace("ج.م","").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue
                    if current_price < 100:
                        continue

                    orig_el = (
                        product.find("span", class_="was-price") or
                        product.find("del") or
                        product.find("span", class_="oldPrice")
                    )
                    original_price = current_price
                    if orig_el:
                        orig_text = orig_el.get_text(strip=True).replace(",","").replace("EGP","").replace("ج.م","").strip()
                        try:
                            original_price = float(orig_text)
                        except:
                            original_price = current_price

                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    img_el = product.find("img")
                    image_url = img_el.get("src","") if img_el else ""

                    deal = {
                        "deal_id": generate_deal_id("noon_eg", product_url, current_price),
                        "title": title,
                        "site": "noon_eg",
                        "site_display": "Noon Egypt",
                        "category": category,
                        "current_price": current_price,
                        "original_price": original_price,
                        "discount_percent": discount,
                        "currency": "EGP",
                        "image_url": image_url,
                        "product_url": product_url,
                        "availability": "in_stock",
                        "timestamp": datetime.utcnow().isoformat(),
                        "rating": 0.0,
                        "verified": False,
                        "hidden": False,
                        "featured": False,
                    }

                    save_deal(deal)
                    total += 1

                except Exception as e:
                    print(f"  Product error: {e}")
                    continue

            time.sleep(3)

        except Exception as e:
            print(f"  Page error: {e}")
            continue

    print(f"[NOON] Done. {total} deals saved.")
    return total

# ─────────────────────────────────────────
# MAIN CYCLE
# ─────────────────────────────────────────

def run_scraper():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*55}")
    print(f"  SCRAPE CYCLE: {now}")
    print(f"{'='*55}")

    total = 0
    total += scrape_amazon_egypt()
    total += scrape_noon_egypt()

    print(f"\n  TOTAL THIS CYCLE: {total} deals")
    print(f"  Next run in {INTERVAL} minutes")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    print("DealHunter Egypt Scraper v2")
    print(f"Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min\n")
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)
