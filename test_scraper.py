#!/usr/bin/env python3
"""Minimal test scraper for Amazon.eg — diagnose HTML structure and proxy."""
import os, sys, re, hashlib, logging, json
from urllib.parse import urljoin, quote
import requests
from bs4 import BeautifulSoup
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger()

# Proxy config
PROXY_TOKEN = os.environ.get("SCRAPEDO_TOKEN", "")
USE_PROXY = bool(PROXY_TOKEN)

def fetch(url, max_retries=3):
    """Fetch URL via scrape.do proxy or direct."""
    for attempt in range(1, max_retries + 1):
        try:
            if USE_PROXY:
                proxy_url = f"http://api.scrape.do/?token={PROXY_TOKEN}&url={quote(url, safe='')}&geoCode=eg"
                log.info(f"[PROXY] Fetching (attempt {attempt}): {url[:60]}...")
                r = requests.get(proxy_url, timeout=60, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
            else:
                log.info(f"[DIRECT] Fetching (attempt {attempt}): {url[:60]}...")
                r = requests.get(url, timeout=30, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": "https://www.amazon.eg/"
                })
            
            log.info(f"[RESPONSE] Status: {r.status_code}, Size: {len(r.text)} bytes")
            
            if r.status_code == 200:
                return r.text
            elif r.status_code == 503:
                log.warning(f"[WARN] HTTP 503 (blocked), retrying...")
                continue
            else:
                log.warning(f"[WARN] HTTP {r.status_code}, retrying...")
                continue
                
        except requests.exceptions.Timeout:
            log.warning(f"[WARN] Timeout, attempt {attempt}/{max_retries}")
        except Exception as e:
            log.warning(f"[WARN] Error: {e}, attempt {attempt}/{max_retries}")
    
    return None

def clean_price(text):
    """Extract first number from price text."""
    if not text:
        return 0.0
    m = re.search(r"[\d,]+", str(text))
    return float(m.group().replace(",", "")) if m else 0.0

def make_deal_id(site, url, price):
    return hashlib.md5(f"{site}:{url}:{price}".encode()).hexdigest()

def parse_amazon_eg(html, page_url):
    """Parse Amazon.eg search results page."""
    soup = BeautifulSoup(html, "lxml")
    deals = []
    
    # Try multiple selectors for product cards
    selectors = [
        "div[data-component-type='s-search-result']",
        "div.s-result-item",
        "div[data-asin]",
        "div.sg-col-inner",
    ]
    
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            log.info(f"[SELECTOR] Found {len(cards)} cards with: {sel}")
            break
    
    if not cards:
        # Debug: show what containers exist
        log.warning("[DEBUG] No cards found. Sample div classes:")
        for div in soup.find_all("div", class_=True)[:10]:
            log.warning(f"  div class='{' '.join(div.get('class',[])[:3])}'")
        return []
    
    for card in cards[:20]:  # Limit to 20 per page
        try:
            asin = card.get("data-asin", "")
            if not asin:
                continue
            
            # Title
            title_el = card.select_one("h2 a span") or card.select_one("span.a-text-normal")
            title = title_el.get_text(strip=True) if title_el else "Unknown"
            
            # URL
            link_el = card.select_one("h2 a")
            product_url = urljoin("https://www.amazon.eg", link_el["href"]) if link_el and link_el.get("href") else page_url
            
            # Image
            img_el = card.select_one("img.s-image") or card.select_one("img")
            image_url = img_el.get("src", "") if img_el else ""
            
            # Price (current)
            price_whole = card.select_one("span.a-price-whole")
            price_fraction = card.select_one("span.a-price-fraction")
            if price_whole:
                whole = price_whole.get_text(strip=True).replace(",", "").replace(".", "")
                frac = price_fraction.get_text(strip=True) if price_fraction else "00"
                current_price = float(f"{whole}.{frac}")
            else:
                price_offscreen = card.select_one("span.a-price span.a-offscreen")
                current_price = clean_price(price_offscreen.get_text() if price_offscreen else "")
            
            # Original price (was price)
            original_price_el = card.select_one("span.a-price.a-text-price span.a-offscreen") or card.select_one("span.a-text-price span.a-offscreen")
            original_price = clean_price(original_price_el.get_text() if original_price_el else "")
            
            # Rating
            rating_el = card.select_one("span.a-icon-alt")
            rating = 0.0
            if rating_el:
                rm = re.search(r"([\d.]+)", rating_el.get_text())
                rating = float(rm.group(1)) if rm else 0.0
            
            # Reviews
            reviews_el = card.select_one("span.a-size-base")
            review_count = 0
            if reviews_el:
                rc = re.search(r"([\d,]+)", reviews_el.get_text())
                review_count = int(rc.group(1).replace(",", "")) if rc else 0
            
            if current_price <= 0:
                continue
            
            if not original_price or original_price <= current_price:
                original_price = current_price * 1.5  # Estimate
            
            savings = original_price - current_price
            discount_pct = min(round((savings / original_price) * 100, 1), 99) if original_price > 0 else 0
            
            if discount_pct < 5:
                continue
            
            deal = {
                "id": make_deal_id("amazon_eg", product_url, current_price),
                "product_id": asin,
                "site": "amazon_eg",
                "title": title[:200],
                "image_url": image_url,
                "product_url": product_url,
                "category": "electronics",
                "original_price": original_price,
                "current_price": current_price,
                "discount_percent": discount_pct,
                "savings": round(savings, 2),
                "currency": "EGP",
                "verdict": "UNVERIFIED",
                "fake_score": 0,
                "recommendation": "normal",
                "confidence": 0,
                "fraud_reasons": [],
                "rating": rating,
                "review_count": review_count,
            }
            deals.append(deal)
            
        except Exception as e:
            log.warning(f"[WARN] Parse error: {e}")
            continue
    
    return deals

def save_deals(deals):
    """Save deals to Supabase PostgreSQL."""
    if not deals:
        log.info("[OK] No deals to save")
        return
    
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        log.error("[ERROR] DATABASE_URL not set")
        return
    
    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()
    
    inserted = 0
    for deal in deals:
        try:
            cur.execute("""
                INSERT INTO deals (id, product_id, site, title, image_url, product_url, category,
                    original_price, current_price, discount_percent, savings, currency, verdict,
                    fake_score, recommendation, confidence, fraud_reasons, rating, review_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    current_price = EXCLUDED.current_price,
                    discount_percent = EXCLUDED.discount_percent,
                    savings = EXCLUDED.savings,
                    updated_at = NOW()
            """, (
                deal["id"], deal["product_id"], deal["site"], deal["title"],
                deal["image_url"], deal["product_url"], deal["category"],
                deal["original_price"], deal["current_price"], deal["discount_percent"],
                deal["savings"], deal["currency"], deal["verdict"],
                deal["fake_score"], deal["recommendation"], deal["confidence"],
                deal["fraud_reasons"], deal["rating"], deal["review_count"]
            ))
            inserted += 1
        except Exception as e:
            log.warning(f"[WARN] DB error: {e}")
    
    conn.commit()
    cur.close()
    conn.close()
    log.info(f"[OK] Saved {inserted}/{len(deals)} deals to database")

def main():
    log.info("=" * 60)
    log.info("DealHunter Test Scraper — Amazon.eg")
    log.info("=" * 60)
    log.info(f"Proxy: {'ENABLED' if USE_PROXY else 'DISABLED'}")
    
    urls = [
        "https://www.amazon.eg/s?k=deals",
        "https://www.amazon.eg/-/en/gp/goldbox",
    ]
    
    all_deals = []
    for url in urls:
        log.info(f"\n[URL] {url}")
        html = fetch(url)
        if html:
            deals = parse_amazon_eg(html, url)
            log.info(f"[RESULT] {len(deals)} deals from {url}")
            all_deals.extend(deals)
        else:
            log.error(f"[ERROR] Failed to fetch {url}")
    
    log.info(f"\n[TOTAL] {len(all_deals)} deals found across all URLs")
    
    if all_deals:
        for d in all_deals[:5]:
            log.info(f"  [{d['site']}] {d['title'][:50]} | {d['discount_percent']}% off | {d['current_price']} EGP")
        save_deals(all_deals)
    else:
        log.info("[DIAGNOSIS] No deals found. Possible causes:")
        log.info("  1. Amazon page structure changed")
        log.info("  2. Proxy returning cached/error page")
        log.info("  3. Page requires JavaScript rendering")
        log.info("  4. Amazon blocking the request")
    
    return 0 if all_deals else 1

if __name__ == "__main__":
    sys.exit(main())
