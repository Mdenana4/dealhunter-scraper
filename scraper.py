# DealHunter Egypt - Scraper v3
# Uses Amazon RSS feeds (no blocking) + direct HTML with better selectors

import requests
import schedule
import time
import json
import hashlib
import os
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

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
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

def detect_category(title):
    t = title.lower()
    if any(k in t for k in ["phone","mobile","iphone","samsung","xiaomi","laptop","tablet","ipad","pc","computer","monitor","keyboard","mouse","headphone","earphone","earbuds","speaker","camera","tv ","television","gaming","playstation","xbox","console","router","charger","cable","battery","power bank","smartwatch","smart watch"]):
        return "electronics"
    elif any(k in t for k in ["dress","shirt","shoes","bag","watch","perfume","jeans","jacket","sneaker","sandal","handbag","wallet","belt","hat","cap","suit","blouse","skirt","coat","boots","heel","loafer","polo","tshirt","t-shirt"]):
        return "fashion"
    elif any(k in t for k in ["sofa","chair","bed","table","lamp","kitchen","blender","cookware","vacuum","air condition","refrigerator","washing machine","oven","microwave","curtain","pillow","mattress","shelf","cabinet"]):
        return "home"
    elif any(k in t for k in ["cream","serum","shampoo","makeup","skincare","moisturizer","lotion","vitamin","supplement","face wash","hair","nail","lipstick","foundation","perfume","cologne","body wash","deodorant"]):
        return "beauty"
    elif any(k in t for k in ["gym","sport","fitness","yoga","bicycle","bike","football","tennis","treadmill","dumbbell","resistance band","protein","swimming"]):
        return "sports"
    return "general"

# ─────────────────────────────────────────
# METHOD 1: AMAZON EGYPT RSS DEALS FEED
# These are official Amazon XML feeds — never blocked
# ─────────────────────────────────────────

def scrape_amazon_rss():
    print("\n[AMAZON RSS] Checking official deal feeds...")

    # Amazon Egypt official RSS/deal feeds
    rss_urls = [
        "https://www.amazon.eg/gp/rss/bestsellers/electronics/ref=zg_bs_electronics_rss?ie=UTF8&exportformat=rss",
        "https://www.amazon.eg/gp/rss/bestsellers/computers/ref=zg_bs_computers_rss?ie=UTF8&exportformat=rss",
        "https://www.amazon.eg/gp/rss/bestsellers/mobile/ref=zg_bs_mobile_rss?ie=UTF8&exportformat=rss",
        "https://www.amazon.eg/gp/rss/bestsellers/fashion/ref=zg_bs_fashion_rss?ie=UTF8&exportformat=rss",
        "https://www.amazon.eg/gp/rss/bestsellers/home/ref=zg_bs_home_rss?ie=UTF8&exportformat=rss",
        "https://www.amazon.eg/gp/rss/bestsellers/beauty/ref=zg_bs_beauty_rss?ie=UTF8&exportformat=rss",
    ]

    total = 0

    for url in rss_urls:
        try:
            print(f"  Fetching RSS: {url[:70]}...")
            resp = requests.get(url, headers=get_headers(), timeout=15)

            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} — skipping")
                continue

            # Parse XML
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            print(f"  Found {len(items)} RSS items")

            for item in items:
                try:
                    title = item.findtext("title", "").strip()
                    link = item.findtext("link", "").strip()
                    description = item.findtext("description", "")

                    if not title or not link:
                        continue

                    # Parse price from description HTML
                    desc_soup = BeautifulSoup(description, "lxml")
                    desc_text = desc_soup.get_text()

                    # Look for price patterns like "EGP 1,299" or "1299"
                    import re
                    prices = re.findall(r'[\d,]+\.?\d*', desc_text.replace(",",""))
                    prices = [float(p) for p in prices if float(p) > 100]

                    if not prices:
                        continue

                    current_price = min(prices)  # Usually the sale price is shown first

                    # Get image from description
                    img_el = desc_soup.find("img")
                    image_url = img_el.get("src", "") if img_el else ""

                    category = detect_category(title)

                    # RSS feeds do not have original price, so we estimate
                    # We save these as "best sellers" deals
                    deal = {
                        "deal_id": generate_deal_id("amazon_eg", link, current_price),
                        "title": title,
                        "site": "amazon_eg",
                        "site_display": "Amazon Egypt",
                        "category": category,
                        "current_price": current_price,
                        "original_price": current_price,
                        "discount_percent": 0,
                        "currency": "EGP",
                        "image_url": image_url,
                        "product_url": link,
                        "availability": "in_stock",
                        "timestamp": datetime.utcnow().isoformat(),
                        "rating": 0.0,
                        "verified": False,
                        "hidden": False,
                        "featured": False,
                        "source": "rss"
                    }

                    save_deal(deal)
                    total += 1

                except Exception as e:
                    print(f"  RSS item error: {e}")
                    continue

            time.sleep(2)

        except Exception as e:
            print(f"  RSS feed error: {e}")
            continue

    print(f"[AMAZON RSS] Done. {total} items saved.")
    return total

# ─────────────────────────────────────────
# METHOD 2: AMAZON EGYPT — SIMPLE SEARCH PAGES
# These simpler URLs are less likely to be blocked
# ─────────────────────────────────────────

def scrape_amazon_simple():
    print("\n[AMAZON] Scraping simple search pages...")

    # Simple straightforward URLs — no complex filter parameters
    pages = [
        {"url": "https://www.amazon.eg/s?k=samsung+galaxy&language=en_AE", "category": "electronics"},
        {"url": "https://www.amazon.eg/s?k=iphone&language=en_AE", "category": "electronics"},
        {"url": "https://www.amazon.eg/s?k=laptop+sale&language=en_AE", "category": "electronics"},
        {"url": "https://www.amazon.eg/s?k=nike+shoes&language=en_AE", "category": "fashion"},
        {"url": "https://www.amazon.eg/s?k=adidas&language=en_AE", "category": "fashion"},
        {"url": "https://www.amazon.eg/s?k=headphones&language=en_AE", "category": "electronics"},
        {"url": "https://www.amazon.eg/s?k=smart+watch&language=en_AE", "category": "electronics"},
        {"url": "https://www.amazon.eg/s?k=air+conditioner&language=en_AE", "category": "home"},
        {"url": "https://www.amazon.eg/s?k=perfume&language=en_AE", "category": "beauty"},
        {"url": "https://www.amazon.eg/s?k=tablet&language=en_AE", "category": "electronics"},
    ]

    total = 0

    for page in pages:
        url = page["url"]
        category = page["category"]

        try:
            print(f"  Fetching: {url[:70]}...")

            # Add a small random delay to look more human
            time.sleep(2)

            resp = requests.get(url, headers=get_headers(), timeout=20)

            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} — skipping")
                continue

            soup = BeautifulSoup(resp.content, "lxml")

            # Find products by data-asin attribute — most reliable selector
            products = soup.find_all("div", attrs={"data-asin": True})
            # Remove empty ASIN items
            products = [p for p in products if p.get("data-asin","").strip()]

            print(f"  {len(products)} products with ASIN found")

            for product in products:
                try:
                    asin = product.get("data-asin","")
                    if not asin:
                        continue

                    # Skip ads
                    if product.get("data-component-type") == "sp-sponsored-result":
                        continue

                    # Title — try multiple selectors
                    title_el = (
                        product.find("h2") or
                        product.find("span", class_="a-size-medium") or
                        product.find("span", class_="a-size-base-plus") or
                        product.find("span", class_="a-size-large") or
                        product.find("span", class_="a-color-base")
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 8:
                        continue

                    # Current price
                    price_el = product.find("span", class_="a-price-whole")
                    if not price_el:
                        continue

                    price_text = price_el.get_text(strip=True)
                    price_text = price_text.replace(",","").replace(".","").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue

                    # Skip very cheap items — not real deals
                    if current_price < 200:
                        continue

                    # Original price
                    original_price = current_price
                    orig_block = product.find("span", class_="a-price a-text-price")
                    if orig_block:
                        orig_el = orig_block.find("span", class_="a-offscreen")
                        if orig_el:
                            orig_text = orig_el.get_text(strip=True)
                            orig_text = orig_text.replace(",","").replace("EGP","").replace("ج.م","").strip()
                            try:
                                original_price = float(orig_text)
                            except:
                                original_price = current_price

                    # Check badge for discount
                    discount = calculate_discount(original_price, current_price)

                    badge_el = product.find("span", class_="a-badge-text")
                    if badge_el and discount == 0:
                        badge_text = badge_el.get_text(strip=True)
                        if "%" in badge_text:
                            try:
                                import re
                                nums = re.findall(r'\d+', badge_text)
                                if nums:
                                    badge_discount = int(nums[0])
                                    if badge_discount >= MIN_DISCOUNT:
                                        discount = badge_discount
                                        original_price = round(current_price / (1 - badge_discount/100))
                            except:
                                pass

                    if discount < MIN_DISCOUNT:
                        continue

                    # Image
                    img_el = product.find("img", class_="s-image")
                    image_url = img_el.get("src","") if img_el else ""

                    # Rating
                    rating = 0.0
                    rating_el = product.find("span", class_="a-icon-alt")
                    if rating_el:
                        try:
                            rating = float(rating_el.get_text(strip=True).split(" ")[0])
                        except:
                            pass

                    product_url = f"https://www.amazon.eg/dp/{asin}?language=en_AE"
                    detected_cat = detect_category(title) if detect_category(title) != "general" else category

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
                        "source": "search"
                    }

                    save_deal(deal)
                    total += 1

                except Exception as e:
                    print(f"  Product error: {e}")
                    continue

        except Exception as e:
            print(f"  Page error: {e}")
            continue

    print(f"[AMAZON] Simple search done. {total} deals saved.")
    return total

# ─────────────────────────────────────────
# METHOD 3: ADD DEALS MANUALLY FROM ADMIN
# This is a fallback — admin can add deals directly
# through the admin dashboard
# ─────────────────────────────────────────

def check_manual_deals():
    """Check Firebase for any manually added deals from admin dashboard"""
    print("\n[MANUAL] Checking for admin-added deals...")
    try:
        snap = db.collection("manual_deals").stream()
        count = 0
        for doc in snap:
            data = doc.to_dict()
            if not data.get("processed", False):
                # Move to main deals collection
                deal = {
                    "deal_id": generate_deal_id("manual", data.get("product_url",""), data.get("current_price",0)),
                    "title": data.get("title","Manual Deal"),
                    "site": data.get("site","manual"),
                    "site_display": data.get("site_display","Manual"),
                    "category": data.get("category","general"),
                    "current_price": float(data.get("current_price",0)),
                    "original_price": float(data.get("original_price",0)),
                    "discount_percent": int(data.get("discount_percent",0)),
                    "currency": "EGP",
                    "image_url": data.get("image_url",""),
                    "product_url": data.get("product_url",""),
                    "availability": "in_stock",
                    "timestamp": datetime.utcnow().isoformat(),
                    "rating": 0.0,
                    "verified": True,
                    "hidden": False,
                    "featured": True,
                    "source": "manual"
                }
                save_deal(deal)
                # Mark as processed
                db.collection("manual_deals").document(doc.id).update({"processed": True})
                count += 1
        print(f"[MANUAL] {count} manual deals processed.")
        return count
    except Exception as e:
        print(f"[MANUAL] Error: {e}")
        return 0

# ─────────────────────────────────────────
# MAIN CYCLE
# ─────────────────────────────────────────

def run_scraper():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*55}")
    print(f"  SCRAPE CYCLE: {now}")
    print(f"{'='*55}")

    total = 0
    total += scrape_amazon_rss()
    total += scrape_amazon_simple()
    total += check_manual_deals()

    print(f"\n  TOTAL THIS CYCLE: {total} items")
    print(f"  Next run in {INTERVAL} minutes")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    print("DealHunter Egypt Scraper v3")
    print(f"Min discount: {MIN_DISCOUNT}% | Interval: {INTERVAL} min\n")
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)