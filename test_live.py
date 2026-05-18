#!/usr/bin/env python3
"""
DealHunter — Live scraper test (no database, no Cloud Run needed).
Tests each source individually and reports deal counts + samples.

Usage:  python3 test_live.py
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────
SCRAPEDO_TOKEN = os.environ.get(
    "SCRAPEDO_TOKEN", "3041e7da00be45828a61c399c063750ba0cb05219d0"
)
MIN_DISCOUNT  = 40
MIN_PRICE     = 100

# ── Helpers ─────────────────────────────────────────────────────────────────

def clean_price(text) -> float:
    if not text:
        return 0.0
    text = re.sub(r"[A-Z]{2,3}\s*", "", str(text), flags=re.IGNORECASE).strip()
    m = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not m:
        return 0.0
    n = m.group().replace(",", "")
    try:
        return float(n)
    except ValueError:
        return 0.0

def discount_pct(original: float, current: float) -> float:
    if original <= 0 or current <= 0 or original <= current:
        return 0.0
    return round((1 - current / original) * 100, 1)

def make_id(site, url, price) -> str:
    return hashlib.md5(f"{site}:{url}:{price}".encode()).hexdigest()[:12]

def ok(n):  return "✓" if n else "✗"

# ── Amazon Egypt ─────────────────────────────────────────────────────────────

def test_amazon_eg():
    print("\n" + "="*60)
    print("AMAZON EGYPT")
    print("="*60)

    urls = [
        "https://www.amazon.eg/-/en/gp/goldbox",
        "https://www.amazon.eg/s?k=deals",
    ]

    deals = []
    for url in urls:
        try:
            encoded = urllib.parse.quote(url, safe="")
            proxy = (
                f"https://api.scrape.do/?token={SCRAPEDO_TOKEN}"
                f"&url={encoded}&render=false"
            )
            resp = requests.get(proxy, timeout=60)
            print(f"  HTTP {resp.status_code} for {url}")
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div[data-component-type='s-search-result']")
            print(f"  → {len(cards)} product cards found")

            for card in cards:
                try:
                    title_el = card.select_one("h2 a span") or card.select_one("h2 span")
                    title = title_el.get_text(strip=True) if title_el else ""
                    if not title:
                        continue

                    link_el = card.select_one("h2 a") or card.select_one("a[href*='/dp/']")
                    href = link_el.get("href", "") if link_el else ""
                    asin = card.get("data-asin", "")
                    product_url = (
                        f"https://www.amazon.eg/dp/{asin}" if asin
                        else f"https://www.amazon.eg{href}" if href.startswith("/")
                        else href
                    )
                    if "/dp/" not in product_url:
                        continue

                    whole = card.select_one("span.a-price-whole")
                    frac  = card.select_one("span.a-price-fraction")
                    if whole:
                        cp_str = whole.get_text(strip=True).replace(",", "")
                        cp_str += "." + (frac.get_text(strip=True) if frac else "00")
                    else:
                        off = card.select_one("span.a-price span.a-offscreen")
                        cp_str = off.get_text(strip=True) if off else ""

                    cp = clean_price(cp_str)
                    if cp < MIN_PRICE:
                        continue

                    op_el = (
                        card.select_one("span.a-text-price span.a-offscreen")
                        or card.select_one("span.a-price.a-text-price span.a-offscreen")
                    )
                    op = clean_price(op_el.get_text(strip=True)) if op_el else cp

                    disc = discount_pct(op, cp)
                    if disc < MIN_DISCOUNT:
                        continue

                    img = card.select_one("img")
                    img_url = img.get("src", "") if img else ""

                    deals.append({
                        "id": make_id("amazon_eg", product_url, cp),
                        "site": "amazon_eg",
                        "title": title[:80],
                        "current_price": cp,
                        "original_price": op,
                        "discount_pct": disc,
                        "url": product_url,
                        "image": img_url[:60] + "..." if len(img_url) > 60 else img_url,
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n  RESULT: {len(deals)} deals found from Amazon EG")
    for d in deals[:3]:
        print(f"    [{d['discount_pct']:.0f}%] {d['title'][:60]}")
        print(f"           EGP {d['current_price']:.0f}  (was {d['original_price']:.0f})")
    return deals

# ── Noon Egypt ───────────────────────────────────────────────────────────────

def test_noon_eg():
    print("\n" + "="*60)
    print("NOON EGYPT")
    print("="*60)

    urls = [
        "https://www.noon.com/egypt-en/sale-electronics/",
        "https://www.noon.com/egypt-en/sale-fashion/",
    ]

    deals = []
    for url in urls:
        print(f"\n  Testing: {url}")

        # Primary: scrape.do rendered
        html = None
        try:
            encoded = urllib.parse.quote(url, safe="")
            sd_url = (
                f"https://api.scrape.do/?token={SCRAPEDO_TOKEN}"
                f"&url={encoded}&render=true&wait=6000"
            )
            print(f"  → Requesting via scrape.do rendered...", end=" ", flush=True)
            resp = requests.get(sd_url, timeout=90)
            print(f"HTTP {resp.status_code}  ({len(resp.text):,} chars)")
            if resp.status_code == 200:
                html = resp.text
        except Exception as e:
            print(f"ERROR: {e}")

        if not html:
            print("  ✗ No HTML received")
            continue

        soup = BeautifulSoup(html, "lxml")

        # Check what we got
        products = soup.select('[data-qa="plp-product-box"]')
        print(f"  → data-qa=plp-product-box: {len(products)} found")

        # Also check __NEXT_DATA__
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        next_data_products = 0
        if script and script.string:
            try:
                data = json.loads(script.string)
                pp = data.get("props", {}).get("pageProps", {})
                for path in [["catalog","hits"], ["initialData","hits"],
                              ["initialData","data","products"], ["products"]]:
                    obj = pp
                    for k in path:
                        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
                    if isinstance(obj, list) and obj:
                        next_data_products = len(obj)
                        print(f"  → __NEXT_DATA__ path {path}: {next_data_products} products")
                        break
            except Exception as e:
                print(f"  → __NEXT_DATA__ parse error: {e}")

        if not products and not next_data_products:
            # Show what selectors ARE present to help debug
            body_text = soup.get_text()[:200].replace("\n", " ")
            print(f"  ✗ No products. Page text preview: {body_text}")
            continue

        # Parse products
        country = "egypt-en"
        for product in (products or []):
            try:
                name_el = product.select_one('[data-qa="plp-product-box-name"]')
                price_el = product.select_one('[data-qa="plp-product-box-price"]')
                old_el   = product.select_one('[data-qa="plp-product-box-old-price"]')
                disc_el  = product.select_one('[data-qa="plp-product-box-discount"]')
                link_el  = product.select_one("a[href]")

                if not name_el or not price_el or not link_el:
                    continue

                name = name_el.get_text(strip=True)
                cp   = clean_price(price_el.get_text(strip=True))
                if cp < MIN_PRICE:
                    continue

                op = clean_price(old_el.get_text(strip=True)) if old_el else cp
                if op <= cp:
                    if disc_el:
                        m = re.search(r"(\d+)", disc_el.get_text(strip=True))
                        if m:
                            pct = int(m.group(1))
                            op = round(cp / (1 - pct / 100), 2) if 0 < pct < 100 else cp

                disc = discount_pct(op, cp)
                if disc < MIN_DISCOUNT:
                    continue

                href = link_el.get("href", "")
                purl = f"https://www.noon.com{href}" if href.startswith("/") else href
                if "/p/" not in purl:
                    continue

                deals.append({
                    "id": make_id("noon_eg", purl, cp),
                    "site": "noon_eg",
                    "title": name[:80],
                    "current_price": cp,
                    "original_price": op,
                    "discount_pct": disc,
                    "url": purl,
                })
            except Exception:
                continue

        # Also parse from __NEXT_DATA__ if DOM had no results
        if not products and script and script.string:
            try:
                data = json.loads(script.string)
                pp = data.get("props", {}).get("pageProps", {})
                hits = []
                for path in [["catalog","hits"], ["initialData","hits"],
                              ["initialData","data","products"]]:
                    obj = pp
                    for k in path:
                        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
                    if isinstance(obj, list) and obj:
                        hits = obj
                        break

                for hit in hits:
                    try:
                        name = hit.get("name","") or hit.get("title","")
                        if not name:
                            continue
                        pr = hit.get("price", {}) or {}
                        cp = float(pr.get("salePrice",0) or pr.get("price",0) or 0)
                        op = float(pr.get("oldPrice",0) or cp)
                        if op < cp:
                            op = cp
                        disc = discount_pct(op, cp)
                        if disc < MIN_DISCOUNT:
                            continue
                        sku = hit.get("sku","")
                        purl = f"https://www.noon.com/egypt-en/product/{sku}/" if sku else ""
                        if not purl:
                            continue
                        deals.append({
                            "id": make_id("noon_eg", purl, cp),
                            "site": "noon_eg",
                            "title": name[:80],
                            "current_price": cp,
                            "original_price": op,
                            "discount_pct": disc,
                            "url": purl,
                            "source": "__NEXT_DATA__"
                        })
                    except Exception:
                        continue
            except Exception:
                pass

        time.sleep(2)

    print(f"\n  RESULT: {len(deals)} deals found from Noon EG")
    for d in deals[:3]:
        src = d.get("source","DOM")
        print(f"    [{d['discount_pct']:.0f}% via {src}] {d['title'][:60]}")
        print(f"           EGP {d['current_price']:.0f}  (was {d['original_price']:.0f})")
    return deals

# ── Jumia Egypt ──────────────────────────────────────────────────────────────

def test_jumia_eg():
    print("\n" + "="*60)
    print("JUMIA EGYPT")
    print("="*60)

    urls = [
        "https://www.jumia.com.eg/deals-of-the-day/",
        "https://www.jumia.com.eg/catalog/?f%5Bn_special_price%5D=1",
    ]

    deals = []
    for url in urls:
        print(f"\n  Testing: {url}")
        html = None

        # Strategy 1: curl_cffi
        try:
            from curl_cffi import requests as cf_req
            print("  → curl_cffi Chrome impersonation...", end=" ", flush=True)
            r = cf_req.get(
                url,
                impersonate="chrome120",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
                    "Referer": "https://www.jumia.com.eg/",
                },
                timeout=35,
                allow_redirects=True,
            )
            print(f"HTTP {r.status_code}  ({len(r.text):,} chars)")
            if r.status_code == 200:
                html = r.text
        except ImportError:
            print("(curl_cffi not installed)")
        except Exception as e:
            print(f"ERROR: {e}")

        # Strategy 2: scrape.do super
        if not html:
            try:
                encoded = urllib.parse.quote(url, safe="")
                sd_url = (
                    f"https://api.scrape.do/?token={SCRAPEDO_TOKEN}"
                    f"&url={encoded}&super=true&render=false&geoCode=eg"
                )
                print("  → scrape.do super proxy...", end=" ", flush=True)
                r = requests.get(sd_url, timeout=65)
                print(f"HTTP {r.status_code}  ({len(r.text):,} chars)")
                if r.status_code == 200:
                    html = r.text
            except Exception as e:
                print(f"ERROR: {e}")

        # Strategy 3: direct
        if not html:
            try:
                print("  → Direct HTTP...", end=" ", flush=True)
                r = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                           "AppleWebKit/537.36 Chrome/120 Safari/537.36",
                             "Accept": "text/html"},
                    timeout=30,
                )
                print(f"HTTP {r.status_code}")
                if r.status_code == 200:
                    html = r.text
            except Exception as e:
                print(f"ERROR: {e}")

        if not html:
            print("  ✗ All strategies failed")
            continue

        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("article.prd")
        if not cards:
            cards = soup.select("div[data-brand]")
        print(f"  → {len(cards)} product cards found")

        if not cards:
            body = soup.get_text()[:300].replace("\n", " ")
            print(f"  Page text: {body}")
            continue

        for card in cards:
            try:
                name_el = (
                    card.select_one("h3.name") or card.select_one("div.name")
                )
                name = name_el.get_text(strip=True) if name_el else ""
                if not name:
                    continue

                link_el = (
                    card.select_one("a.core") or card.select_one("a[href*='.html']")
                )
                href = link_el.get("href","") if link_el else ""
                purl = f"https://www.jumia.com.eg{href}" if href.startswith("/") else href
                if not purl:
                    continue

                price_el = card.select_one("div.prc") or card.select_one("span.prc")
                cp = clean_price(price_el.get_text(strip=True)) if price_el else 0
                if cp < MIN_PRICE:
                    continue

                old_el = card.select_one("div.old") or card.select_one("span.old")
                op = clean_price(old_el.get_text(strip=True)) if old_el else cp

                if op <= cp:
                    badge = (
                        card.select_one("span.bdg._dsct")
                        or card.select_one("span[class*='dsct']")
                    )
                    if badge:
                        m = re.search(r"(\d+)", badge.get_text(strip=True))
                        if m:
                            pct = int(m.group(1))
                            op = round(cp / (1 - pct / 100), 2) if 0 < pct < 100 else cp

                disc = discount_pct(op, cp)
                if disc < MIN_DISCOUNT:
                    continue

                deals.append({
                    "id": make_id("jumia_eg", purl, cp),
                    "site": "jumia_eg",
                    "title": name[:80],
                    "current_price": cp,
                    "original_price": op,
                    "discount_pct": disc,
                    "url": purl,
                })
            except Exception:
                continue

        time.sleep(2)

    print(f"\n  RESULT: {len(deals)} deals found from Jumia EG")
    for d in deals[:3]:
        print(f"    [{d['discount_pct']:.0f}%] {d['title'][:60]}")
        print(f"           EGP {d['current_price']:.0f}  (was {d['original_price']:.0f})")
    return deals

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("DEALHUNTER LIVE SCRAPER TEST")
    print("No database required — testing real sites directly")
    print("="*60)

    results = {}

    start = time.time()
    results["amazon_eg"] = test_amazon_eg()
    results["noon_eg"]   = test_noon_eg()
    results["jumia_eg"]  = test_jumia_eg()
    elapsed = time.time() - start

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    total = sum(len(v) for v in results.values())
    for source, deals in results.items():
        status = "OK" if deals else "FAIL"
        print(f"  [{status}] {source}: {len(deals)} deals")
    print(f"\n  TOTAL: {total} deals in {elapsed:.0f}s")

    if results["noon_eg"]:
        print("\n  [OK] Noon is WORKING")
    else:
        print("\n  [!!] Noon returned 0 deals — check scrape.do token / URL")

    if results["jumia_eg"]:
        print("  [OK] Jumia is WORKING")
    else:
        print("  [!!] Jumia returned 0 deals — check curl_cffi / network")

    if total >= 30:
        print("\n  READY TO DEPLOY")
    else:
        print(f"\n  Only {total} deals — investigate before deploying")


if __name__ == "__main__":
    main()
