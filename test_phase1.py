"""
Phase 1 — scrape.do test script
Tests Amazon Egypt, Noon Egypt, and Jumia Egypt for deals >= 40% off.

Usage:
  SCRAPEDO_TOKEN=your_token python3 test_phase1.py

Without a token it falls back to direct HTTP (may be blocked by sites).
"""

import os, re, time, json, sys
import requests
from bs4 import BeautifulSoup

SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN", "")
MIN_DISCOUNT   = 40   # percent

# ──────────────────────────────────────────────────────────────────────────────
# Fetch helpers
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch(url, render_js=False, country="eg"):
    """
    Fetch `url` via scrape.do if token is set, otherwise direct request.
    Returns (html_text, method_used, elapsed_seconds) or (None, method, elapsed).
    """
    t0 = time.time()

    if SCRAPEDO_TOKEN:
        params = {
            "token":      SCRAPEDO_TOKEN,
            "url":        url,
            "render":     "true" if render_js else "false",
            "geoCode":    country.upper(),
            "super":      "false",
        }
        try:
            resp = requests.get("https://api.scrape.do", params=params, timeout=60)
            elapsed = round(time.time() - t0, 1)
            if resp.status_code == 200 and len(resp.text) > 1000:
                return resp.text, f"scrape.do ({'JS' if render_js else 'HTML'})", elapsed
            return None, f"scrape.do HTTP {resp.status_code}", elapsed
        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            return None, f"scrape.do error: {e}", elapsed

    # Direct fallback
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        elapsed = round(time.time() - t0, 1)
        if resp.status_code == 200 and len(resp.text) > 1000:
            return resp.text, "direct (no token)", elapsed
        return None, f"direct HTTP {resp.status_code}", elapsed
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        return None, f"direct error: {e}", elapsed


def clean_price(text):
    """Extract a numeric price from a string like 'EGP 1,299.00'."""
    text = re.sub(r"[^\d.,]", "", str(text)).replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", text)
    return float(m.group()) if m else 0.0


def discount(original, current):
    if original > current > 0:
        return round((original - current) / original * 100)
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Amazon Egypt parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_amazon(html):
    soup = BeautifulSoup(html, "lxml")
    deals = []

    # Deal cards on the Today's Deals page
    cards = (
        soup.find_all("div", attrs={"data-asin": True}) or
        soup.find_all("div", class_=lambda c: c and "DealCard" in str(c)) or
        soup.find_all("li", attrs={"data-asin": True})
    )

    for card in cards:
        try:
            asin = card.get("data-asin", "").strip()
            if not asin:
                continue

            title_el = (
                card.find("span", attrs={"data-a-size": True}) or
                card.find("h2") or
                card.find("span", class_=lambda c: c and "DealTitle" in str(c)) or
                card.find("span", class_="a-size-base-plus") or
                card.find("span", class_="a-size-medium")
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue

            price_el = card.find("span", class_="a-price-whole")
            if not price_el:
                price_el = card.find("span", class_=lambda c: c and "price" in str(c).lower())
            cp = clean_price(price_el.get_text()) if price_el else 0
            if cp < 1:
                continue

            orig_el = card.find("span", class_="a-price a-text-price")
            if not orig_el:
                orig_el = card.find("span", class_=lambda c: c and "was" in str(c).lower())
            op = clean_price(orig_el.get_text()) if orig_el else 0

            badge_el = card.find("span", class_="a-badge-text")
            stored_disc = 0
            if badge_el:
                m = re.search(r"(\d+)%", badge_el.get_text())
                stored_disc = int(m.group(1)) if m else 0

            if op < cp:
                if stored_disc > 0:
                    op = round(cp / (1 - stored_disc / 100))
                else:
                    op = cp

            disc = stored_disc or discount(op, cp)
            if disc < MIN_DISCOUNT:
                continue

            img_el = card.find("img")
            img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
            purl = f"https://www.amazon.eg/dp/{asin}"

            deals.append({
                "title":    title[:80],
                "current":  cp,
                "original": op,
                "discount": disc,
                "url":      purl,
                "image":    img,
            })
        except Exception:
            continue

    return deals


# ──────────────────────────────────────────────────────────────────────────────
# Noon Egypt parser  (handles __NEXT_DATA__ + HTML cards)
# ──────────────────────────────────────────────────────────────────────────────

def _noon_item_to_deal(src, region_path="egypt-en"):
    title = (src.get("name") or src.get("title") or "").strip()
    if not title or len(title) < 5:
        return None

    p = src.get("price", {})
    if isinstance(p, dict):
        cp = clean_price(str(p.get("now") or p.get("value") or p.get("sale_price") or 0))
        op = clean_price(str(p.get("was") or p.get("before_price") or p.get("before") or cp))
        stored_disc = int(p.get("discount_percent") or p.get("discount") or 0)
    else:
        cp = clean_price(str(src.get("sale_price") or src.get("now_price") or p or 0))
        op = clean_price(str(src.get("was_price") or src.get("original_price") or cp))
        stored_disc = int(src.get("discount_percent") or src.get("discount") or 0)

    if cp < 1:
        return None
    if op < cp:
        op = cp

    disc = stored_disc or discount(op, cp)
    if disc < MIN_DISCOUNT:
        return None

    img_keys = src.get("image_keys") or []
    img = (
        f"https://f.nooncdn.com/p/{img_keys[0]}.jpg" if img_keys else
        (f"https://f.nooncdn.com/p/{src['image_key']}.jpg" if src.get("image_key") else
         src.get("image") or src.get("thumbnail") or "")
    )
    sku  = src.get("sku") or src.get("id") or ""
    purl = f"https://www.noon.com/{region_path}/{sku}/" if sku else src.get("url") or ""

    return {"title": title[:80], "current": cp, "original": op,
            "discount": disc, "url": purl, "image": img}


def _walk_noon_json(obj, depth=0):
    """Recursively find objects that look like Noon products."""
    if depth > 12 or not isinstance(obj, (dict, list)):
        return []
    if isinstance(obj, list):
        if len(obj) >= 2 and all(isinstance(x, dict) for x in obj[:2]):
            sample = obj[0]
            has_id    = any(k in sample for k in ("sku", "product_id", "id"))
            has_name  = any(k in sample for k in ("name", "title", "productName"))
            has_price = any(k in sample for k in ("price", "sale_price", "now", "salePrice"))
            if has_id and has_name and has_price:
                return obj
        out = []
        for x in obj:
            out.extend(_walk_noon_json(x, depth + 1))
        return out
    # Dict: check if it IS a product
    has_id    = any(k in obj for k in ("sku", "product_id", "id"))
    has_name  = any(k in obj for k in ("name", "title", "productName"))
    has_price = any(k in obj for k in ("price", "sale_price", "now"))
    if has_id and has_name and has_price:
        return [obj]
    out = []
    for v in obj.values():
        if isinstance(v, (dict, list)):
            out.extend(_walk_noon_json(v, depth + 1))
    return out


def parse_noon(html, region_path="egypt-en"):
    deals = []

    # ── Method A: __NEXT_DATA__ ──────────────────────────────────────────────
    tag = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>', html)
    nd = {}
    if tag:
        end = html.find('</script>', tag.end())
        if end != -1:
            try:
                nd = json.loads(html[tag.end():end].strip())
            except Exception:
                pass

    if nd:
        pp = nd.get("props", {}).get("pageProps", {})
        hits = (
            pp.get("catalog", {}).get("hits", []) or
            pp.get("initialState", {}).get("catalog", {}).get("hits", []) or
            pp.get("initialReduxState", {}).get("catalog", {}).get("hits", []) or
            pp.get("hits", []) or
            pp.get("products", []) or
            pp.get("items", []) or
            nd.get("props", {}).get("initialState", {}).get("catalog", {}).get("hits", []) or
            []
        )
        # Fallback: deep walk
        if not hits:
            hits = _walk_noon_json(nd)

        print(f"    [noon] __NEXT_DATA__ found, hits={len(hits)}")
        for item in hits:
            src = item.get("_source", item)
            d = _noon_item_to_deal(src, region_path)
            if d:
                deals.append(d)

    # ── Method B: regex for embedded JSON arrays ─────────────────────────────
    if not deals:
        for pat in [
            r'"hits"\s*:\s*(\[.+?\])\s*,',
            r'"products"\s*:\s*(\[.+?\])\s*[,}]',
            r'"items"\s*:\s*(\[.+?\])\s*[,}]',
        ]:
            m = re.search(pat, html, re.DOTALL)
            if not m:
                continue
            try:
                items = json.loads(m.group(1))
                for item in items:
                    d = _noon_item_to_deal(item.get("_source", item), region_path)
                    if d:
                        deals.append(d)
                if deals:
                    break
            except Exception:
                continue

    # ── Method C: HTML product cards ─────────────────────────────────────────
    if not deals:
        soup = BeautifulSoup(html, "lxml")
        blocks = (
            soup.find_all("div", attrs={"data-qa": "product-block"}) or
            soup.find_all("div", attrs={"data-testid": "product-block"}) or
            soup.find_all("div", class_=lambda c: c and any(
                k in str(c) for k in ("productContainer", "ProductCard", "product-card")))
        )
        print(f"    [noon] HTML cards found: {len(blocks)}")
        for p in blocks:
            try:
                title_el = (
                    p.find(attrs={"data-qa": "product-name"}) or
                    p.find("h2") or
                    p.find(class_=lambda c: c and "name" in str(c).lower())
                )
                title = title_el.get_text(strip=True) if title_el else ""
                if not title or len(title) < 5:
                    continue
                price_el = (
                    p.find(attrs={"data-qa": "price-now"}) or
                    p.find(class_=lambda c: c and "price" in str(c).lower())
                )
                cp = clean_price(price_el.get_text()) if price_el else 0
                if cp < 50:
                    continue
                orig_el = (
                    p.find(attrs={"data-qa": "price-was"}) or
                    p.find("del") or
                    p.find(class_=lambda c: c and "was" in str(c).lower())
                )
                op = clean_price(orig_el.get_text()) if orig_el else cp
                if op < cp:
                    op = cp
                disc = discount(op, cp)
                if disc < MIN_DISCOUNT:
                    continue
                link_el = p.find("a", href=True)
                href = link_el["href"] if link_el else ""
                purl = ("https://www.noon.com" + href if href.startswith("/") else href)
                img_el = p.find("img")
                img = (img_el.get("src") or img_el.get("data-src") or "") if img_el else ""
                deals.append({"title": title[:80], "current": cp, "original": op,
                               "discount": disc, "url": purl, "image": img})
            except Exception:
                continue

    return deals


# ──────────────────────────────────────────────────────────────────────────────
# Jumia Egypt parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_jumia(html):
    soup = BeautifulSoup(html, "lxml")
    deals = []

    # Jumia product articles
    articles = (
        soup.find_all("article", class_="prd") or
        soup.find_all("article", attrs={"data-id": True}) or
        soup.find_all("div", class_=lambda c: c and "sku" in str(c).lower())
    )

    for art in articles:
        try:
            title_el = art.find("h3") or art.find("h2") or art.find(class_="name")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue

            price_el = art.find(class_="prc")
            if not price_el:
                price_el = art.find(class_=lambda c: c and "price" in str(c).lower())
            cp = clean_price(price_el.get_text()) if price_el else 0
            if cp < 1:
                continue

            orig_el = art.find(class_="old") or art.find("del")
            op = clean_price(orig_el.get_text()) if orig_el else cp
            if op < cp:
                op = cp

            disc_el = art.find(class_="bdg _dsct") or art.find(class_=lambda c: c and "disc" in str(c).lower() and "bdg" in str(c).lower())
            stored_disc = 0
            if disc_el:
                m = re.search(r"(\d+)%", disc_el.get_text())
                stored_disc = int(m.group(1)) if m else 0

            disc = stored_disc or discount(op, cp)
            if disc < MIN_DISCOUNT:
                continue

            link_el = art.find("a", href=True)
            href = link_el["href"] if link_el else ""
            purl = ("https://www.jumia.com.eg" + href
                    if href.startswith("/") else href)

            img_el = art.find("img")
            img = (img_el.get("data-src") or img_el.get("src") or "") if img_el else ""

            deals.append({
                "title":    title[:80],
                "current":  cp,
                "original": op,
                "discount": disc,
                "url":      purl,
                "image":    img,
            })
        except Exception:
            continue

    return deals


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

SITES = [
    {
        "name":      "Amazon Egypt",
        "url":       "https://www.amazon.eg/-/en/deals",
        "render_js": False,
        "country":   "EG",
        "parser":    parse_amazon,
        "currency":  "EGP",
    },
    {
        "name":      "Noon Egypt",
        "url":       "https://www.noon.com/egypt-en/sale/?sort%5Bby%5D=discount_percent&sort%5Bdir%5D=desc&limit=48",
        "render_js": True,
        "country":   "EG",
        "parser":    parse_noon,
        "currency":  "EGP",
    },
    {
        "name":      "Jumia Egypt",
        "url":       "https://www.jumia.com.eg/flash-sales/",
        "render_js": False,
        "country":   "EG",
        "parser":    parse_jumia,
        "currency":  "EGP",
    },
]


def run():
    if not SCRAPEDO_TOKEN:
        print("⚠️  SCRAPEDO_TOKEN not set — using direct requests (may be blocked by sites)")
        print("   Sign up free at https://scrape.do → copy your token → set SCRAPEDO_TOKEN=xxx\n")
    else:
        print(f"✅ scrape.do token found ({SCRAPEDO_TOKEN[:6]}...)\n")

    all_results = {}

    for site in SITES:
        print(f"{'═'*60}")
        print(f"🔍  {site['name']}  →  {site['url']}")
        html, method, elapsed = fetch(site["url"], site["render_js"], site["country"])
        status = "✅ OK" if html else "❌ BLOCKED"
        print(f"    Fetch: {status} via {method} in {elapsed}s")

        if not html:
            print(f"    0 deals found — page could not be fetched\n")
            all_results[site["name"]] = {"deals": [], "method": method, "elapsed": elapsed, "blocked": True}
            continue

        # Detect block signals even in 200-OK responses
        block_signals = [
            "captcha", "robot check", "just a moment", "enable javascript",
            "access denied", "verify you are human", "cloudflare",
        ]
        page_snippet = html[:5000].lower()
        is_blocked = any(s in page_snippet for s in block_signals) or len(html) < 3000

        if is_blocked:
            print(f"    ⚠️  Response looks like a bot-block page ({len(html)} bytes)")

        deals = site["parser"](html)
        deals.sort(key=lambda d: d["discount"], reverse=True)

        print(f"\n    📦 Deals ≥{MIN_DISCOUNT}% off: {len(deals)}")
        for i, d in enumerate(deals[:10]):
            curr = site["currency"]
            print(f"    #{i+1:02d}  [{d['discount']}%]  {d['title'][:55]}")
            print(f"          {curr} {d['current']:.0f}  (was {curr} {d['original']:.0f})  {d['url'][:60]}")

        if len(deals) > 10:
            print(f"    ... and {len(deals)-10} more deals not shown")

        all_results[site["name"]] = {
            "deals":   deals,
            "method":  method,
            "elapsed": elapsed,
            "blocked": is_blocked,
        }
        print()

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print("PHASE 1 SUMMARY")
    print(f"{'═'*60}")
    total = 0
    for name, r in all_results.items():
        n = len(r["deals"])
        total += n
        blocked_note = " (BLOCKED)" if r["blocked"] else ""
        print(f"  {name:<22} {n:>4} deals   {r['elapsed']}s   {r['method']}{blocked_note}")

    print(f"{'─'*60}")
    print(f"  {'TOTAL':<22} {total:>4} deals")
    print()

    if not SCRAPEDO_TOKEN:
        print("Next step: get your FREE scrape.do token:")
        print("  1. Go to https://scrape.do  →  Sign Up (no credit card)")
        print("  2. Copy your API token")
        print("  3. Re-run:  SCRAPEDO_TOKEN=xxx python3 test_phase1.py")
    elif total == 0:
        print("⚠️  0 deals found with scrape.do — check your token or try render_js=True for blocked sites")
    else:
        print(f"✅  Phase 1 PASSED — {total} deals found via scrape.do")

    return all_results


if __name__ == "__main__":
    run()
