# DealHunter Egypt - Main Scraper
# Reads Firebase credentials from environment variable (for Render)

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

# Load .env file if running locally on your PC
load_dotenv()

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", 40))
INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 3))

# ─────────────────────────────────────────
# CONNECT TO FIREBASE
# Works both locally (file) and on Render (environment variable)
# ─────────────────────────────────────────

print("Connecting to Firebase...")

firebase_key_json = os.getenv("FIREBASE_KEY_JSON")

if firebase_key_json:
    # Running on Render — read key from environment variable
    try:
        key_dict = json.loads(firebase_key_json)
        cred = credentials.Certificate(key_dict)
        print("Firebase key loaded from environment variable.")
    except Exception as e:
        print(f"ERROR reading FIREBASE_KEY_JSON: {e}")
        raise
elif os.path.exists("firebase-key.json"):
    # Running locally on your PC — read key from file
    cred = credentials.Certificate("firebase-key.json")
    print("Firebase key loaded from firebase-key.json file.")
else:
    raise Exception("No Firebase key found. Set FIREBASE_KEY_JSON or add firebase-key.json file.")

firebase_admin.initialize_app(cred)
db = firestore.client()
print("Connected to Firebase successfully!")

# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

def calculate_discount(original, current):
    """Calculate discount percentage"""
    if original <= 0 or current <= 0:
        return 0
    if current >= original:
        return 0
    return round(((original - current) / original) * 100)

def generate_deal_id(site, url, price):
    """Create a unique ID for each deal"""
    raw = f"{site}_{url}_{price}"
    return hashlib.md5(raw.encode()).hexdigest()

def save_deal_to_firebase(deal):
    """Save or update a deal in Firebase"""
    deal_id = deal["deal_id"]
    deal_ref = db.collection("deals").document(deal_id)

    try:
        existing = deal_ref.get()

        if existing.exists:
            existing_data = existing.to_dict()
            old_price = existing_data.get("current_price", 0)
            new_price = deal["current_price"]

            if old_price != new_price:
                # Price changed — update deal
                deal_ref.update({
                    "current_price": new_price,
                    "discount_percent": deal["discount_percent"],
                    "timestamp": deal["timestamp"]
                })
                # Save to price history for Safqa feature
                history_ref = deal_ref.collection("price_history").document()
                history_ref.set({
                    "price": new_price,
                    "timestamp": deal["timestamp"]
                })
                print(f"  UPDATED: {deal['title'][:45]} | {old_price} → {new_price} EGP")
            else:
                print(f"  SAME:    {deal['title'][:45]} | No change")
        else:
            # Brand new deal — save it
            deal_ref.set(deal)
            # Save first price history entry
            history_ref = deal_ref.collection("price_history").document()
            history_ref.set({
                "price": deal["current_price"],
                "timestamp": deal["timestamp"]
            })
            print(f"  NEW:     {deal['title'][:45]} | {deal['discount_percent']}% OFF | EGP {deal['current_price']}")

    except Exception as e:
        print(f"  ERROR saving deal: {e}")

def get_headers():
    """Browser-like headers to avoid being blocked"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

# ─────────────────────────────────────────
# AMAZON EGYPT SCRAPER
# ─────────────────────────────────────────

def scrape_amazon_egypt():
    """Scrape deals from Amazon Egypt"""
    print("\n[AMAZON] Starting scrape...")

    urls = [
        "https://www.amazon.eg/s?i=electronics&rh=n%3A21419864031&s=price-asc-rank&language=en_AE",
        "https://www.amazon.eg/s?i=fashion&rh=n%3A21419911031&language=en_AE",
        "https://www.amazon.eg/gp/goldbox?language=en_AE",
    ]

    deals_found = 0

    for url in urls:
        try:
            print(f"  Fetching: {url[:60]}...")
            response = requests.get(url, headers=get_headers(), timeout=20)

            if response.status_code != 200:
                print(f"  [AMAZON] HTTP {response.status_code} — skipping this page")
                continue

            soup = BeautifulSoup(response.content, "lxml")

            # Try multiple ways to find products
            products = soup.find_all("div", {"data-component-type": "s-search-result"})
            if not products:
                products = soup.find_all("div", class_="s-result-item")
            if not products:
                products = soup.find_all("div", attrs={"data-asin": True})

            print(f"  [AMAZON] {len(products)} products found on this page")

            for product in products:
                try:
                    # Skip sponsored/ad items
                    if product.get("data-component-type") == "sp-sponsored-result":
                        continue

                    # Get title
                    title_elem = (
                        product.find("span", class_="a-size-medium") or
                        product.find("span", class_="a-size-base-plus") or
                        product.find("span", class_="a-size-large") or
                        product.find("h2")
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # Get product link
                    link_elem = product.find("a", class_="a-link-normal")
                    if not link_elem:
                        continue
                    href = link_elem.get("href", "")
                    if not href:
                        continue
                    product_url = "https://www.amazon.eg" + href if href.startswith("/") else href

                    # Get current price
                    price_whole = product.find("span", class_="a-price-whole")
                    if not price_whole:
                        continue
                    price_text = price_whole.get_text(strip=True).replace(",", "").replace(".", "").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue
                    if current_price <= 0:
                        continue

                    # Get original (strikethrough) price
                    orig_price_block = product.find("span", class_="a-price a-text-price")
                    original_price = current_price
                    if orig_price_block:
                        orig_offscreen = orig_price_block.find("span", class_="a-offscreen")
                        if orig_offscreen:
                            orig_text = orig_offscreen.get_text(strip=True)
                            orig_text = orig_text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
                            try:
                                original_price = float(orig_text)
                            except:
                                original_price = current_price

                    # Calculate and filter by discount
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    # Get image URL
                    img_elem = product.find("img", class_="s-image")
                    image_url = img_elem.get("src", "") if img_elem else ""

                    # Get rating
                    rating = 0.0
                    rating_elem = product.find("span", class_="a-icon-alt")
                    if rating_elem:
                        try:
                            rating = float(rating_elem.get_text(strip=True).split(" ")[0])
                        except:
                            rating = 0.0

                    # Detect category
                    if "electronics" in url:
                        category = "electronics"
                    elif "fashion" in url:
                        category = "fashion"
                    else:
                        category = "general"

                    deal = {
                        "deal_id": generate_deal_id("amazon_eg", product_url, current_price),
                        "title": title,
                        "site": "amazon_eg",
                        "site_display": "Amazon Egypt",
                        "category": category,
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
                    }

                    save_deal_to_firebase(deal)
                    deals_found += 1

                except Exception as e:
                    print(f"  [AMAZON] Product parse error: {e}")
                    continue

            # Be polite — wait 2 seconds between pages
            time.sleep(2)

        except Exception as e:
            print(f"  [AMAZON] Page fetch error: {e}")
            continue

    print(f"[AMAZON] Finished. {deals_found} deals saved this cycle.")
    return deals_found

# ─────────────────────────────────────────
# NOON EGYPT SCRAPER
# ─────────────────────────────────────────

def scrape_noon_egypt():
    """Scrape deals from Noon Egypt"""
    print("\n[NOON] Starting scrape...")

    urls = [
        "https://www.noon.com/egypt-en/electronics/",
        "https://www.noon.com/egypt-en/fashion/",
        "https://www.noon.com/egypt-en/home/",
        "https://www.noon.com/egypt-en/beauty/",
        "https://www.noon.com/egypt-en/sports/",
    ]

    deals_found = 0

    for url in urls:
        try:
            print(f"  Fetching: {url[:60]}...")
            response = requests.get(url, headers=get_headers(), timeout=20)

            if response.status_code != 200:
                print(f"  [NOON] HTTP {response.status_code} — skipping this page")
                continue

            soup = BeautifulSoup(response.content, "lxml")

            # Try multiple selectors for Noon products
            products = (
                soup.find_all("div", class_="productContainer") or
                soup.find_all("div", attrs={"data-qa": "product-block"}) or
                soup.find_all("div", class_="sc-eBMEer") or
                soup.find_all("article") or
                soup.find_all("div", class_="grid-item")
            )

            print(f"  [NOON] {len(products)} products found on this page")

            for product in products:
                try:
                    # Get title
                    title_elem = (
                        product.find("div", class_="name") or
                        product.find("p", class_="name") or
                        product.find("h2") or
                        product.find("span", class_="name")
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # Get link
                    link_elem = product.find("a")
                    if not link_elem:
                        continue
                    href = link_elem.get("href", "")
                    product_url = "https://www.noon.com" + href if href.startswith("/") else href
                    if not product_url:
                        continue

                    # Get current price
                    price_elem = (
                        product.find("strong", class_="price") or
                        product.find("span", class_="price") or
                        product.find("div", class_="price")
                    )
                    if not price_elem:
                        continue
                    price_text = price_elem.get_text(strip=True)
                    price_text = price_text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue
                    if current_price <= 0:
                        continue

                    # Get original price
                    orig_elem = (
                        product.find("span", class_="was-price") or
                        product.find("del") or
                        product.find("span", class_="oldPrice")
                    )
                    original_price = current_price
                    if orig_elem:
                        orig_text = orig_elem.get_text(strip=True)
                        orig_text = orig_text.replace(",", "").replace("EGP", "").replace("ج.م", "").strip()
                        try:
                            original_price = float(orig_text)
                        except:
                            original_price = current_price

                    # Filter by discount
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    # Get image
                    img_elem = product.find("img")
                    image_url = img_elem.get("src", "") if img_elem else ""

                    # Detect category from URL
                    if "electronics" in url:
                        category = "electronics"
                    elif "fashion" in url:
                        category = "fashion"
                    elif "home" in url:
                        category = "home"
                    elif "beauty" in url:
                        category = "beauty"
                    elif "sports" in url:
                        category = "sports"
                    else:
                        category = "general"

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
                    }

                    save_deal_to_firebase(deal)
                    deals_found += 1

                except Exception as e:
                    print(f"  [NOON] Product parse error: {e}")
                    continue

            time.sleep(2)

        except Exception as e:
            print(f"  [NOON] Page fetch error: {e}")
            continue

    print(f"[NOON] Finished. {deals_found} deals saved this cycle.")
    return deals_found

# ─────────────────────────────────────────
# MAIN SCRAPE CYCLE
# ─────────────────────────────────────────

def run_scraper():
    """Run one complete scrape of all sites"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*55}")
    print(f"  SCRAPE CYCLE: {now}")
    print(f"{'='*55}")

    total = 0
    total += scrape_amazon_egypt()
    total += scrape_noon_egypt()

    print(f"\n  TOTAL THIS CYCLE: {total} deals saved")
    print(f"  Next run in {INTERVAL} minutes")
    print(f"{'='*55}\n")

# ─────────────────────────────────────────
# START — only runs when called directly
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("DealHunter Egypt Scraper")
    print(f"Min discount: {MIN_DISCOUNT}%")
    print(f"Interval: every {INTERVAL} minutes")
    print("Press CTRL+C to stop\n")

    run_scraper()

    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)