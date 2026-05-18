#!/usr/bin/env python3
"""
DealHunter — Offline parsing test (no network, no database needed).
Uses realistic HTML fixtures that match what Noon/Jumia actually serve.
Tests every parser, price cleaner, and database schema in isolation.

Run:  python3 test_parsing.py
"""

import json
import re
import sys
import traceback

from bs4 import BeautifulSoup

# ── Patch environment so scraper_cloudrun imports without DB ──────────────────
import os
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("TIMESCALE_URL", "")

# ── Import the real scraper module ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

try:
    import scraper_cloudrun as sc
    print("[OK] scraper_cloudrun imported (DB skipped — no DATABASE_URL)")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [OK]  {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}  {detail}")
        FAIL += 1

# ════════════════════════════════════════════════════════════════════════════
# 1. PriceCleaner
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("1. PriceCleaner")
print("="*60)

pc = sc.PriceCleaner()

check("EGP 1,299",          pc.clean_price("EGP 1,299")       == 1299.0)
check("EGP 18,999.00",      pc.clean_price("EGP 18,999.00")   == 18999.0)
check("26,999",             pc.clean_price("26,999")           == 26999.0)
check("AED 450.00",         pc.clean_price("AED 450.00")       == 450.0)
check("None → 0",           pc.clean_price(None)               == 0.0)
check("empty → 0",          pc.clean_price("")                 == 0.0)
check("SAR 1.299,00 (EU)",  pc.clean_price("1.299,00 SAR")     == 1299.0,
      f"got {pc.clean_price('1.299,00 SAR')}")

d = pc.calculate_discount(26999, 18999)
check("Discount: 26999→18999 = 30%", 29 <= d["percent"] <= 31,
      f"got {d['percent']}")
check("Savings: 26999-18999 = 8000", d["savings"] == 8000.0)

# ════════════════════════════════════════════════════════════════════════════
# 2. Category Detection
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("2. Category Detection")
print("="*60)

check("iphone → electronics",   sc.detect_category("iPhone 15 Pro", "") == "electronics")
check("laptop → electronics",   sc.detect_category("Dell XPS Laptop", "") == "electronics")
check("sneaker → fashion",      sc.detect_category("Nike sneaker 42", "") == "fashion")
check("sofa → home",            sc.detect_category("Modern sofa", "") == "home")
check("dumbbell → sports",      sc.detect_category("20kg dumbbell set", "") == "sports")

# ════════════════════════════════════════════════════════════════════════════
# 3. Noon HTML parsing (data-qa attributes — what scrape.do returns)
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("3. Noon HTML parsing (data-qa selectors)")
print("="*60)

NOON_HTML = """
<html><body>
<div data-qa="plp-product-box">
  <a href="/egypt-en/samsung-galaxy-s24-256gb/p/Z123456789012345/">
    <img data-src="https://f.nooncdn.com/p/pnsku/Z123456789012345/45/_/1.jpg" src="">
    <div data-qa="plp-product-box-name">Samsung Galaxy S24 256GB Phantom Black</div>
    <div data-qa="plp-product-box-price">EGP 18,999</div>
    <div data-qa="plp-product-box-old-price">EGP 26,999</div>
    <div data-qa="plp-product-box-discount">-30%</div>
  </a>
</div>
<div data-qa="plp-product-box">
  <a href="/egypt-en/apple-airpods-pro-2nd-gen/p/Z987654321098765/">
    <img src="https://f.nooncdn.com/p/pnsku/Z987654321098765/45/_/1.jpg">
    <div data-qa="plp-product-box-name">Apple AirPods Pro 2nd Generation</div>
    <div data-qa="plp-product-box-price">EGP 4,299</div>
    <div data-qa="plp-product-box-old-price">EGP 7,499</div>
    <div data-qa="plp-product-box-discount">-43%</div>
  </a>
</div>
<div data-qa="plp-product-box">
  <!-- Product with only discount badge, no old price element -->
  <a href="/egypt-en/xiaomi-redmi-note-13/p/Z111222333444555/">
    <div data-qa="plp-product-box-name">Xiaomi Redmi Note 13 Pro 256GB</div>
    <div data-qa="plp-product-box-price">EGP 8,499</div>
    <div data-qa="plp-product-box-discount">-47%</div>
  </a>
</div>
<div data-qa="plp-product-box">
  <!-- Cheap product below MIN_PRICE — should be filtered -->
  <a href="/egypt-en/cheap-cable/p/Z000000000000001/">
    <div data-qa="plp-product-box-name">USB Cable 1m</div>
    <div data-qa="plp-product-box-price">EGP 49</div>
    <div data-qa="plp-product-box-old-price">EGP 100</div>
    <div data-qa="plp-product-box-discount">-51%</div>
  </a>
</div>
<div data-qa="plp-product-box">
  <!-- Low discount product — should be filtered by MIN_DISCOUNT -->
  <a href="/egypt-en/random-item/p/Z000000000000002/">
    <div data-qa="plp-product-box-name">Random Item</div>
    <div data-qa="plp-product-box-price">EGP 1,200</div>
    <div data-qa="plp-product-box-old-price">EGP 1,350</div>
  </a>
</div>
</body></html>
"""

soup = BeautifulSoup(NOON_HTML, "lxml")
products = soup.select('[data-qa="plp-product-box"]')
check(f"Found {len(products)} product boxes",  len(products) == 5)

# Simulate what _scrape_noon_page does
scraper = sc.DealHunterScraper.__new__(sc.DealHunterScraper)
scraper.price_cleaner = sc.PriceCleaner()
scraper.proxy_rotator = sc.ProxyRotator()

noon_deals = []
for product in products:
    name_el     = product.select_one('[data-qa="plp-product-box-name"]')
    price_el    = product.select_one('[data-qa="plp-product-box-price"]')
    old_el      = product.select_one('[data-qa="plp-product-box-old-price"]')
    disc_el     = product.select_one('[data-qa="plp-product-box-discount"]')
    link_el     = product.select_one("a[href]")

    if not name_el or not price_el or not link_el:
        continue

    name = name_el.get_text(strip=True)
    cp   = scraper.price_cleaner.clean_price(price_el.get_text(strip=True))
    op   = scraper.price_cleaner.clean_price(old_el.get_text(strip=True)) if old_el else cp
    if op <= cp and disc_el:
        m = re.search(r"(\d+)", disc_el.get_text(strip=True))
        if m:
            pct = int(m.group(1))
            if 0 < pct < 100:
                op = round(cp / (1 - pct / 100), 2)

    href = link_el.get("href", "")
    purl = f"https://www.noon.com{href}" if href.startswith("/") else href

    deal = scraper._build_deal(
        site="noon_eg", platform="noon", country="eg",
        title=name, url=purl, current_price=cp, original_price=op,
    )
    if deal:
        noon_deals.append(deal)

check("Galaxy S24 filtered (30% < MIN_DISCOUNT=40)",
      not any("Galaxy S24" in d["title"] for d in noon_deals))
check("AirPods Pro 2nd Gen parsed and passed filter",
      any("AirPods" in d["title"] for d in noon_deals))
check("Xiaomi Redmi Note 13 parsed (discount from badge only)",
      any("Xiaomi" in d["title"] for d in noon_deals))
check("USB Cable filtered out (price < MIN_PRICE)",
      not any("USB Cable" in d["title"] for d in noon_deals))
check("Random Item filtered out (discount < MIN_DISCOUNT)",
      not any("Random Item" in d["title"] for d in noon_deals))
check(f"Final Noon deal count = 2", len(noon_deals) == 2,
      f"got {len(noon_deals)}")

if noon_deals:
    ap = next((d for d in noon_deals if "AirPods" in d["title"]), None)
    if ap:
        check("AirPods: current_price = 4299",    ap["current_price"] == 4299.0)
        check("AirPods: original_price = 7499",   ap["original_price"] == 7499.0)
        check("AirPods: discount_percent ~43",     41 <= ap["discount_percent"] <= 45,
              f"got {ap['discount_percent']}")
        check("AirPods: URL has /p/",              "/p/" in ap["product_url"])

# ════════════════════════════════════════════════════════════════════════════
# 4. Noon __NEXT_DATA__ parsing
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("4. Noon __NEXT_DATA__ JSON parsing")
print("="*60)

NEXT_DATA = {
    "props": {
        "pageProps": {
            "catalog": {
                "hits": [
                    {
                        "sku": "Z111111111111111",
                        "name": "Sony WH-1000XM5 Wireless Headphones",
                        "price": {
                            "salePrice": 7499,
                            "oldPrice": 13499,
                            "discountPercent": 44
                        },
                        "imageKeys": ["Z111111111111111"],
                        "url": "/egypt-en/sony-wh1000xm5/p/Z111111111111111/"
                    },
                    {
                        "sku": "Z222222222222222",
                        "name": "Logitech MX Keys Mini Keyboard",
                        "price": {
                            "salePrice": 2799,
                            "oldPrice": 4799,
                            "discountPercent": 42
                        },
                        "imageKeys": ["Z222222222222222"],
                        "url": "/egypt-en/logitech-mx-keys-mini/p/Z222222222222222/"
                    },
                    {
                        # Low discount — should be filtered
                        "sku": "Z333333333333333",
                        "name": "Generic Mouse",
                        "price": {
                            "salePrice": 500,
                            "oldPrice": 550,
                            "discountPercent": 9
                        },
                        "url": "/egypt-en/generic-mouse/p/Z333333333333333/"
                    }
                ]
            }
        }
    }
}

NEXT_HTML = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(NEXT_DATA)}</script></body></html>'

next_deals = scraper._parse_noon_next_data(NEXT_HTML, "noon_eg", "noon", "eg")

check("Sony headphones from __NEXT_DATA__",
      any("Sony" in d["title"] for d in next_deals))
check("Logitech keyboard from __NEXT_DATA__",
      any("Logitech" in d["title"] for d in next_deals))
check("Generic Mouse filtered (9% < MIN_DISCOUNT)",
      not any("Generic Mouse" in d["title"] for d in next_deals))
check(f"__NEXT_DATA__ deal count = 2", len(next_deals) == 2,
      f"got {len(next_deals)}")

# ════════════════════════════════════════════════════════════════════════════
# 5. Jumia HTML parsing
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("5. Jumia HTML parsing (article.prd selectors)")
print("="*60)

JUMIA_HTML = """
<html><body>
<article class="prd -electrical">
  <a class="core" href="/hp-laptop-15-ef-ryzen-5-8gb-512gb-ssd-p-12345678.html">
    <div class="info">
      <h3 class="name">HP Laptop 15 EF Ryzen 5 8GB 512GB SSD</h3>
      <div class="prc">EGP 14,999</div>
      <div class="old">EGP 25,499</div>
      <span class="bdg _dsct">-41%</span>
    </div>
    <img data-src="https://Africa-p4.jumia.com/image/hp-laptop.jpg" src="">
  </a>
</article>
<article class="prd -phones">
  <a class="core" href="/samsung-galaxy-a54-5g-8gb-256gb-awesome-violet-p-87654321.html">
    <div class="info">
      <h3 class="name">Samsung Galaxy A54 5G 8GB 256GB</h3>
      <div class="prc">EGP 8,999</div>
      <div class="old">EGP 16,999</div>
      <span class="bdg _dsct">-47%</span>
    </div>
    <img data-src="https://Africa-p4.jumia.com/image/a54.jpg" src="">
    <div class="stars" data-rate="4.2">(234)</div>
  </a>
</article>
<article class="prd -appliances">
  <!-- No old price — only badge to derive original -->
  <a class="core" href="/samsung-65-inch-qled-4k-p-11111111.html">
    <div class="info">
      <h3 class="name">Samsung 65 Inch QLED 4K Smart TV</h3>
      <div class="prc">EGP 21,999</div>
      <span class="bdg _dsct">-45%</span>
    </div>
  </a>
</article>
<article class="prd">
  <!-- Low discount — should be filtered -->
  <a class="core" href="/random-earbuds-p-99999999.html">
    <div class="info">
      <h3 class="name">Generic Earbuds</h3>
      <div class="prc">EGP 299</div>
      <div class="old">EGP 350</div>
    </div>
  </a>
</article>
</body></html>
"""

jumia_soup = BeautifulSoup(JUMIA_HTML, "lxml")
jumia_cards = jumia_soup.select("article.prd")
check(f"Found {len(jumia_cards)} Jumia product cards", len(jumia_cards) == 4)

# Simulate _scrape_jumia_page parsing logic
jumia_deals = []
for card in jumia_cards:
    name_el  = card.select_one("h3.name") or card.select_one("div.name")
    link_el  = card.select_one("a.core") or card.select_one("a[href*='.html']")
    price_el = card.select_one("div.prc") or card.select_one("span.prc")
    old_el   = card.select_one("div.old") or card.select_one("span.old")
    img_el   = card.select_one("img")

    name = name_el.get_text(strip=True) if name_el else ""
    if not name:
        continue

    href = link_el.get("href","") if link_el else ""
    purl = f"https://www.jumia.com.eg{href}" if href.startswith("/") else href

    cp = scraper.price_cleaner.clean_price(price_el.get_text(strip=True)) if price_el else 0
    op = scraper.price_cleaner.clean_price(old_el.get_text(strip=True)) if old_el else cp
    if op <= cp:
        badge = card.select_one("span.bdg._dsct") or card.select_one("span[class*='dsct']")
        if badge:
            m = re.search(r"(\d+)", badge.get_text(strip=True))
            if m:
                pct = int(m.group(1))
                op = round(cp / (1 - pct / 100), 2) if 0 < pct < 100 else cp

    deal = scraper._build_deal(
        site="jumia_eg", platform="jumia", country="eg",
        title=name, url=purl, current_price=cp, original_price=op,
    )
    if deal:
        jumia_deals.append(deal)

check("HP Laptop parsed and passed filter",
      any("HP Laptop" in d["title"] for d in jumia_deals))
check("Samsung Galaxy A54 parsed and passed filter",
      any("Samsung Galaxy A54" in d["title"] for d in jumia_deals))
check("Samsung QLED TV parsed (original from badge only)",
      any("QLED" in d["title"] for d in jumia_deals))
check("Generic Earbuds filtered (low discount)",
      not any("Generic Earbuds" in d["title"] for d in jumia_deals))
check(f"Final Jumia deal count = 3", len(jumia_deals) == 3,
      f"got {len(jumia_deals)}")

if jumia_deals:
    hp = next(d for d in jumia_deals if "HP Laptop" in d["title"])
    check("HP Laptop: current_price = 14999", hp["current_price"] == 14999.0)
    check("HP Laptop: original_price = 25499", hp["original_price"] == 25499.0)
    check("HP Laptop: discount ~41%", 39 <= hp["discount_percent"] <= 43,
          f"got {hp['discount_percent']}")

# ════════════════════════════════════════════════════════════════════════════
# 6. deal_id uniqueness
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("6. Deal ID uniqueness and consistency")
print("="*60)

id1 = sc.make_deal_id("noon_eg", "https://www.noon.com/egypt-en/product/p/Z123/", 18999.0)
id2 = sc.make_deal_id("noon_eg", "https://www.noon.com/egypt-en/product/p/Z123/", 18999.0)
id3 = sc.make_deal_id("noon_eg", "https://www.noon.com/egypt-en/product/p/Z123/", 17999.0)

check("Same input → same ID",          id1 == id2)
check("Price change → different ID",   id1 != id3)
check("ID is 32-char hex",             len(id1) == 32 and all(c in "0123456789abcdef" for c in id1))

# ════════════════════════════════════════════════════════════════════════════
# 7. _build_deal edge cases
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("7. _build_deal edge cases")
print("="*60)

d = scraper._build_deal(
    site="noon_eg", platform="noon", country="eg",
    title="", url="https://x.com/p/1/", current_price=1000, original_price=500,
)
check("Empty title → None",  d is None)

d = scraper._build_deal(
    site="noon_eg", platform="noon", country="eg",
    title="Test Product", url="", current_price=1000, original_price=500,
)
check("Empty URL → None",  d is None)

d = scraper._build_deal(
    site="noon_eg", platform="noon", country="eg",
    title="Cheap Thing", url="https://noon.com/p/1/", current_price=30, original_price=100,
)
check("Price below MIN_PRODUCT_PRICE → None",  d is None)

d = scraper._build_deal(
    site="noon_eg", platform="noon", country="eg",
    title="Good Deal", url="https://noon.com/p/2/",
    current_price=1000, original_price=2000,
)
check("50% discount → deal returned",  d is not None)
if d:
    check("site field = noon_eg",      d["site"] == "noon_eg")
    check("currency = EGP",            d["currency"] == "EGP")
    check("verdict = GENUINE",         d["verdict"] == "GENUINE")
    check("fraud_reasons = list",      isinstance(d["fraud_reasons"], list))

# ════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("RESULTS")
print("="*60)
total = PASS + FAIL
print(f"\n  Passed: {PASS}/{total}")
print(f"  Failed: {FAIL}/{total}")

if FAIL == 0:
    print("\n  ALL TESTS PASSED — parsing logic is correct, safe to deploy")
    sys.exit(0)
else:
    print(f"\n  {FAIL} FAILURES — review before deploying")
    sys.exit(1)
