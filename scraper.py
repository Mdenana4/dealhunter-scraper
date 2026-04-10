# DealHunter Egypt - Main Scraper
# This script runs every 3 minutes and finds deals on Amazon.eg and Noon.com

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

# Load your secret keys from .env file
load_dotenv()

PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", 40))
INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", 3))

# Connect to Firebase
print("Connecting to Firebase...")
cred = credentials.Certificate("firebase-key.json")
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
    """Save a deal to Firebase database"""
    deal_id = deal["deal_id"]
    deal_ref = db.collection("deals").document(deal_id)
    existing = deal_ref.get()

    if existing.exists:
        existing_data = existing.to_dict()
        old_price = existing_data.get("current_price", 0)
        new_price = deal["current_price"]

        if old_price != new_price:
            # Price changed - update deal and log price history
            deal_ref.update({
                "current_price": new_price,
                "discount_percent": deal["discount_percent"],
                "timestamp": deal["timestamp"]
            })
            # Save price history for Safqa feature
            history_ref = deal_ref.collection("price_history").document()
            history_ref.set({
                "price": new_price,
                "timestamp": deal["timestamp"]
            })
            print(f"  UPDATED: {deal['title'][:40]} | Price changed {old_price} → {new_price} EGP")
        else:
            print(f"  SKIPPED: {deal['title'][:40]} | Same price")
    else:
        # New deal - save it and send notification
        deal_ref.set(deal)
        # Save initial price history
        history_ref = deal_ref.collection("price_history").document()
        history_ref.set({
            "price": deal["current_price"],
            "timestamp": deal["timestamp"]
        })
        print(f"  NEW DEAL: {deal['title'][:40]} | {deal['discount_percent']}% OFF | EGP {deal['current_price']}")

def get_headers():
    """Browser headers so websites don't block us"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

# ─────────────────────────────────────────
# AMAZON EGYPT SCRAPER
# ─────────────────────────────────────────

def scrape_amazon_egypt():
    """Scrape deals from Amazon Egypt"""
    print("\n[AMAZON] Starting scrape...")

    # Amazon Egypt deal pages to scrape
    urls = [
        "https://www.amazon.eg/s?i=electronics&rh=n%3A21419864031&s=price-asc-rank&dc&language=en_AE",
        "https://www.amazon.eg/s?i=fashion&rh=n%3A21419911031&s=price-asc-rank&language=en_AE",
        "https://www.amazon.eg/deals?language=en_AE",
    ]

    deals_found = 0

    for url in urls:
        try:
            response = requests.get(url, headers=get_headers(), timeout=15)
            if response.status_code != 200:
                print(f"  [AMAZON] Could not reach page: {url[:50]} | Status: {response.status_code}")
                continue

            soup = BeautifulSoup(response.content, "lxml")

            # Find all product containers on the page
            products = soup.find_all("div", {"data-component-type": "s-search-result"})

            if not products:
                # Try alternate product container
                products = soup.find_all("div", class_="s-result-item")

            print(f"  [AMAZON] Found {len(products)} products on page")

            for product in products:
                try:
                    # Get product title
                    title_elem = product.find("span", class_="a-size-medium") or \
                                 product.find("span", class_="a-size-base-plus") or \
                                 product.find("h2")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # Get product URL
                    link_elem = product.find("a", class_="a-link-normal")
                    if not link_elem:
                        continue
                    product_url = "https://www.amazon.eg" + link_elem.get("href", "")

                    # Get current price
                    price_elem = product.find("span", class_="a-price-whole")
                    if not price_elem:
                        continue
                    price_text = price_elem.get_text(strip=True).replace(",", "").replace(".", "")
                    try:
                        current_price = float(price_text)
                    except:
                        continue

                    # Get original price (strikethrough price)
                    orig_elem = product.find("span", class_="a-price a-text-price")
                    if orig_elem:
                        orig_text = orig_elem.find("span", class_="a-offscreen")
                        if orig_text:
                            orig_clean = orig_text.get_text(strip=True).replace(",", "").replace("EGP", "").strip()
                            try:
                                original_price = float(orig_clean)
                            except:
                                original_price = current_price
                        else:
                            original_price = current_price
                    else:
                        original_price = current_price

                    # Calculate discount
                    discount = calculate_discount(original_price, current_price)

                    # Only keep deals with 40%+ discount
                    if discount < MIN_DISCOUNT:
                        continue

                    # Get product image
                    img_elem = product.find("img", class_="s-image")
                    image_url = img_elem.get("src", "") if img_elem else ""

                    # Get rating
                    rating_elem = product.find("span", class_="a-icon-alt")
                    rating = 0.0
                    if rating_elem:
                        try:
                            rating = float(rating_elem.get_text(strip=True).split(" ")[0])
                        except:
                            rating = 0.0

                    # Detect category from URL
                    if "electronics" in url.lower() or "mobiles" in url.lower():
                        category = "electronics"
                    elif "fashion" in url.lower():
                        category = "fashion"
                    else:
                        category = "general"

                    # Build the deal object
                    deal = {
                        "deal_id": generate_deal_id("amazon_eg", product_url, current_price),
                        "title": title,
                        "site": "amazon_eg",
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
                    print(f"  [AMAZON] Error parsing product: {e}")
                    continue

        except Exception as e:
            print(f"  [AMAZON] Error fetching page: {e}")
            continue

    print(f"[AMAZON] Done. {deals_found} deals saved.")

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
            response = requests.get(url, headers=get_headers(), timeout=15)
            if response.status_code != 200:
                print(f"  [NOON] Could not reach page: {url[:50]} | Status: {response.status_code}")
                continue

            soup = BeautifulSoup(response.content, "lxml")

            # Noon product containers
            products = soup.find_all("div", class_="productContainer") or \
                       soup.find_all("div", attrs={"data-qa": "product-block"}) or \
                       soup.find_all("article")

            print(f"  [NOON] Found {len(products)} products on page")

            for product in products:
                try:
                    # Get title
                    title_elem = product.find("div", class_="name") or \
                                 product.find("h2") or \
                                 product.find("p", class_="name")
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
                    if href.startswith("/"):
                        product_url = "https://www.noon.com" + href
                    else:
                        product_url = href

                    # Get current price
                    price_elem = product.find("strong", class_="price") or \
                                 product.find("span", class_="price")
                    if not price_elem:
                        continue
                    price_text = price_elem.get_text(strip=True).replace(",", "").replace("EGP", "").strip()
                    try:
                        current_price = float(price_text)
                    except:
                        continue

                    # Get original price
                    orig_elem = product.find("span", class_="was-price") or \
                                product.find("del")
                    if orig_elem:
                        orig_text = orig_elem.get_text(strip=True).replace(",", "").replace("EGP", "").strip()
                        try:
                            original_price = float(orig_text)
                        except:
                            original_price = current_price
                    else:
                        original_price = current_price

                    # Calculate discount
                    discount = calculate_discount(original_price, current_price)
                    if discount < MIN_DISCOUNT:
                        continue

                    # Get image
                    img_elem = product.find("img")
                    image_url = img_elem.get("src", "") if img_elem else ""

                    # Detect category
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
                    print(f"  [NOON] Error parsing product: {e}")
                    continue

        except Exception as e:
            print(f"  [NOON] Error fetching page: {e}")
            continue

    print(f"[NOON] Done. {deals_found} deals saved.")

# ─────────────────────────────────────────
# MAIN SCRAPE CYCLE
# ─────────────────────────────────────────

def run_scraper():
    """Run one full scrape cycle"""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"SCRAPE CYCLE STARTED: {now}")
    print(f"{'='*50}")

    scrape_amazon_egypt()
    scrape_noon_egypt()

    print(f"\nCYCLE COMPLETE. Next run in {INTERVAL} minutes.")
    print(f"{'='*50}")

# ─────────────────────────────────────────
# START THE SCHEDULER
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("DealHunter Egypt Scraper Starting...")
    print(f"Will scrape every {INTERVAL} minutes")
    print(f"Minimum discount: {MIN_DISCOUNT}%")
    print("Press CTRL+C to stop\n")

    # Run immediately on start
    run_scraper()

    # Then run every X minutes
    schedule.every(INTERVAL).minutes.do(run_scraper)

    while True:
        schedule.run_pending()
        time.sleep(30)