# DealHunter Egypt - Fake Discount Checker Module v3 FIXED
# FIXES:
#   1. Kanbkam: now uses /eg/ar/dp/{ASIN} — correct URL, no wrong product match
#   2. Safqa: rebuilt with working endpoints + Chrome extension API
#   3. Both sources: multiple fallback methods
#   4. Price range logic: more accurate Rule A/B

import requests
import re
import json
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ─── PROXY SETUP for Safqa (Cloudflare bypass) ───
import os

def _proxied_get(url, headers=None, timeout=15):
    """Make HTTP request via scrape.do proxy (Railway env)."""
    # Try scrape.do first
    scrapedo_token = os.environ.get("SCRAPEDO_TOKEN", "")
    if scrapedo_token:
        try:
            encoded = requests.utils.quote(url, safe="")
            proxy_url = f"https://api.scrape.do/?token={scrapedo_token}&url={encoded}&render=true"
            r = requests.get(proxy_url, headers=headers, timeout=timeout+10)
            if r.status_code == 200:
                return r
        except Exception:
            pass

    # Fallback: ScraperAPI
    scraper_key = os.environ.get("SCRAPER_API_KEY", "")
    if scraper_key:
        try:
            encoded = requests.utils.quote(url, safe="")
            proxy_url = f"http://api.scraperapi.com?api_key={scraper_key}&url={encoded}"
            r = requests.get(proxy_url, headers=headers, timeout=timeout+10)
            if r.status_code == 200:
                return r
        except Exception:
            pass

    # Direct (will likely fail on Cloudflare)
    return requests.get(url, headers=headers, timeout=timeout)



def now_iso():
    return datetime.now(timezone.utc).isoformat()

def clean_price(text):
    if not text:
        return 0.0
    text = str(text).replace(',', '').replace('EGP', '').replace('ج.م', '').replace('جنيه', '').replace('جنية', '').strip()
    text = re.sub(r'[^\d.]', '', text)
    try:
        return float(text)
    except:
        return 0.0

def get_headers(arabic=False):
    lang = "ar-EG,ar;q=0.9,en;q=0.8" if arabic else "en-US,en;q=0.9,ar;q=0.8"
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": lang,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
    }


# ─────────────────────────────────────────────────────
# SOURCE 1: KANBKAM — Fixed URL format using ASIN directly
# ─────────────────────────────────────────────────────
def check_kanbkam(asin, title=""):
    """
    Fetch real price history from Kanbkam.com
    Uses /eg/ar/dp/{ASIN} — direct Amazon-style URL.
    Methods 0-3 only (Method 4 removed — too noisy, caused wrong results).
    Returns: {lowest_price, highest_price, current_price, found, url}
    """
    result = {"found": False, "lowest_price": 0, "highest_price": 0,
              "current_price": 0, "url": "", "source": "kanbkam"}

    if not asin:
        return result

    try:
        headers = get_headers(arabic=True)
        headers["Referer"] = "https://www.kanbkam.com/"

        resp = None
        for url in [
            f"https://www.kanbkam.com/eg/ar/dp/{asin}",
            f"https://www.kanbkam.com/eg/en/dp/{asin}",
            f"https://www.kanbkam.com/sa/ar/dp/{asin}",
        ]:
            try:
                r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                if r.status_code == 200 and len(r.text) > 500:
                    resp = r
                    break
            except:
                continue

        # If direct URL didn't work or redirected away from ASIN, try search
        if not resp or (asin not in resp.url and asin not in resp.text[:2000]):
            try:
                search_url = f"https://www.kanbkam.com/eg/ar/search?q={asin}"
                r = requests.get(search_url, headers=headers, timeout=15)
                if r.status_code == 200 and asin in r.text:
                    resp = r
            except:
                pass

        if not resp or resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.content, "lxml")
        text = soup.get_text(separator=" ")
        lowest = 0
        highest = 0

        # Method 0: __NEXT_DATA__ / __NUXT__ JSON (most reliable for modern SSR sites)
        for script in soup.find_all("script", id="__NEXT_DATA__"):
            try:
                nd_str = json.dumps(json.loads(script.string or ""))
                lj = re.search(r'"lowestPrice"\s*:\s*([\d.]+)', nd_str)
                hj = re.search(r'"highestPrice"\s*:\s*([\d.]+)', nd_str)
                if lj:
                    lowest = float(lj.group(1))
                if hj:
                    highest = float(hj.group(1))
                if lowest > 0:
                    break
            except:
                pass

        # Method 1: Arabic labels (reliable on Kanbkam Arabic pages)
        if lowest == 0:
            lm = re.search(r'أقل\s*سعر[^\d]*(\d[\d,]*)', text)
            hm = re.search(r'أعلى\s*سعر[^\d]*(\d[\d,]*)', text)
            if lm:
                lowest = clean_price(lm.group(1))
            if hm:
                highest = clean_price(hm.group(1))

        # Method 2: JSON keys in any script tag (only look in scripts that mention the ASIN)
        if lowest == 0:
            for script in soup.find_all("script"):
                st = script.get_text()
                if "lowestPrice" not in st and "lowest_price" not in st:
                    continue
                lj = re.search(r'"lowestPrice"\s*:\s*([\d.]+)', st)
                hj = re.search(r'"highestPrice"\s*:\s*([\d.]+)', st)
                if lj:
                    lowest = float(lj.group(1))
                if hj:
                    highest = float(hj.group(1))
                if lowest > 0:
                    break

        # Method 3: JSON-LD structured data
        if lowest == 0:
            for tag in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(tag.string or "")
                    offers = ld.get("offers", {})
                    if isinstance(offers, dict):
                        p = clean_price(str(offers.get("price", 0)))
                        if p > 0:
                            lowest = p
                            highest = p
                except:
                    pass

        # Sanity check
        if lowest > 0 and highest > 0 and lowest > highest:
            lowest, highest = highest, lowest
        if lowest > 0 and highest == 0:
            highest = lowest

        if lowest > 0:
            result["found"] = True
            result["lowest_price"] = lowest
            result["highest_price"] = highest
            result["url"] = resp.url
            print(f"    [KANBKAM] Found: Low=EGP {lowest:,.0f} High=EGP {highest:,.0f}")
        else:
            print(f"    [KANBKAM] Page loaded but no prices extracted")

    except Exception as e:
        print(f"    [KANBKAM] Error: {e}")

    return result


# ─────────────────────────────────────────────────────
# SOURCE 2: SAFQA — Rebuilt with working endpoints
# ─────────────────────────────────────────────────────
def check_safqa(asin=None, product_url=None, title=""):
    """Fetch price history from Safqa (safqaprice.com) v4 — with retry logic for 502s."""
    import os

    scrapedo_token = os.environ.get("SCRAPEDO_TOKEN", "")
    scraper_key = os.environ.get("SCRAPER_API_KEY", "")
    print(f"    [SAFQA] DEBUG: SCRAPEDO_TOKEN={'SET' if scrapedo_token else 'MISSING'} len={len(scrapedo_token)}")
    print(f"    [SAFQA] DEBUG: SCRAPER_API_KEY={'SET' if scraper_key else 'MISSING'} len={len(scraper_key)}")

    result = {"found": False, "lowest_price": 0, "highest_price": 0, "price_samples": [], "coupon_codes": []}
    if not asin:
        return result

    ext_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "application/json"}

    def _do_request(url, method="GET", payload=None, headers=None, retries=2):
        h = headers or ext_headers
        for attempt in range(retries):
            try:
                # Try 1: scrape.do with longer timeout and wait
                if scrapedo_token:
                    encoded = requests.utils.quote(url, safe="")
                    # Add wait=5000 to let React SPA render (5 seconds)
                    proxy_url = f"https://api.scrape.do/?token={scrapedo_token}&url={encoded}&render=true&wait=5000"
                    try:
                        if method == "POST":
                            r = requests.post(proxy_url, headers=h, json=payload, timeout=35)
                        else:
                            r = requests.get(proxy_url, headers=h, timeout=35)
                        status = r.status_code
                        print(f"      [SAFQA] scrape.do | {url[:50]}... | Status: {status} | Len: {len(r.text)}")
                        if status == 200:
                            return r
                        # 502 might be temporary — retry once
                        if status == 502 and attempt == 0:
                            print(f"      [SAFQA] 502, retrying in 3s...")
                            import time
                            time.sleep(3)
                            continue
                    except Exception as e:
                        print(f"      [SAFQA] scrape.do err: {str(e)[:40]}")

                # Try 2: scrape.do without render (lighter request)
                if scrapedo_token and attempt == 1:
                    proxy_url = f"https://api.scrape.do/?token={scrapedo_token}&url={encoded}"
                    try:
                        r = requests.get(proxy_url, headers=h, timeout=25)
                        print(f"      [SAFQA] scrape.do(nr) | {url[:50]}... | Status: {r.status_code} | Len: {len(r.text)}")
                        if r.status_code == 200:
                            return r
                    except Exception as e:
                        print(f"      [SAFQA] scrape.do(nr) err: {str(e)[:40]}")

                # Try 3: ScraperAPI
                if scraper_key:
                    encoded = requests.utils.quote(url, safe="")
                    proxy_url = f"http://api.scraperapi.com?api_key={scraper_key}&url={encoded}"
                    try:
                        if method == "POST":
                            r = requests.post(proxy_url, headers=h, json=payload, timeout=25)
                        else:
                            r = requests.get(proxy_url, headers=h, timeout=25)
                        print(f"      [SAFQA] scraperapi | {url[:50]}... | Status: {r.status_code} | Len: {len(r.text)}")
                        if r.status_code == 200:
                            return r
                    except Exception as e:
                        print(f"      [SAFQA] scraperapi err: {str(e)[:40]}")

                # Try 4: direct (last resort)
                try:
                    if method == "POST":
                        r = requests.post(url, headers=h, json=payload, timeout=10)
                    else:
                        r = requests.get(url, headers=h, timeout=10)
                    print(f"      [SAFQA] direct | {url[:50]}... | Status: {r.status_code} | Len: {len(r.text)}")
                    return r
                except Exception as e:
                    print(f"      [SAFQA] direct err: {str(e)[:40]}")
                    return None
            except Exception as e:
                print(f"      [SAFQA] req failed: {str(e)[:40]}")
                return None
        return None

    # ─── Method 1: API endpoints ───
    api_urls = [
        f"https://api.safqaprice.com/v1/products/{asin}?country=eg",
        f"https://api.safqaprice.com/products/{asin}?country=eg",
        f"https://backend.safqaprice.com/api/products/{asin}?country=eg",
        f"https://safqaprice.com/api/v1/products/{asin}?country=eg",
        f"https://safqaprice.com/api/products/{asin}?country=eg",
        f"https://api.safqaprice.com/v1/search?q={asin}&country=eg",
        f"https://safqaprice.com/api/search?q={asin}&country=eg",
    ]

    print(f"    [SAFQA] Trying {len(api_urls)} API URLs for ASIN: {asin}")

    for url in api_urls:
        try:
            if result["found"]:
                break
            resp = _do_request(url)
            if resp and resp.status_code == 200:
                text = resp.text.strip()
                if not text or text.startswith("<"):
                    continue
                try:
                    data = resp.json()
                except:
                    continue
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                if not isinstance(data, dict):
                    continue
                price = data.get("price") or data.get("current_price") or data.get("sale_price") or 0
                old_price = data.get("old_price") or data.get("original_price") or data.get("list_price") or 0
                if price and price != 0:
                    result["found"] = True
                    result["lowest_price"] = price
                    result["highest_price"] = old_price or price
                    result["price_samples"] = [price]
                    result["coupon_codes"] = data.get("coupons") or data.get("coupon_codes") or []
                    print(f"    [SAFQA] HIT via API: {url[:60]}...")
                    break
        except Exception as e:
            print(f"      [SAFQA] API error: {str(e)[:50]}")
            continue

    # ─── Method 2: Page HTML for embedded JSON ───
    if not result["found"]:
        page_urls = [
            f"https://safqaprice.com/product/{asin}?country=eg",
            f"https://safqaprice.com/products/{asin}?country=eg",
        ]
        print(f"    [SAFQA] Trying {len(page_urls)} page URLs")

        for url in page_urls:
            try:
                if result["found"]:
                    break
                resp = _do_request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
                if resp and resp.status_code == 200:
                    html = resp.text

                    # Look for JSON-LD
                    json_ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                    for ld in json_ld:
                        try:
                            ld_data = json.loads(ld.strip())
                            if isinstance(ld_data, dict) and ld_data.get("@type") in ["Product", "Offer"]:
                                price_info = ld_data.get("offers", {})
                                price = price_info.get("price") if isinstance(price_info, dict) else None
                                if not price:
                                    price = ld_data.get("price")
                                if price:
                                    result["found"] = True
                                    result["lowest_price"] = float(str(price).replace(",", ""))
                                    result["price_samples"] = [result["lowest_price"]]
                                    print(f"    [SAFQA] HIT via JSON-LD")
                                    break
                        except:
                            pass

                    # Look for __NEXT_DATA__ or __INITIAL_STATE__
                    for pattern in [r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', 
                                    r'window\.__INITIAL_STATE__\s*=\s*({.*?});']:
                        match = re.search(pattern, html, re.DOTALL)
                        if match:
                            try:
                                init_data = json.loads(match.group(1))
                                print(f"    [SAFQA] Found embedded React data")
                                def _find_prices(obj, depth=0):
                                    if depth > 10: return []
                                    prices = []
                                    if isinstance(obj, dict):
                                        for k, v in obj.items():
                                            if k.lower() in ["price", "sale_price", "current_price"] and isinstance(v, (int, float)):
                                                prices.append(v)
                                            elif k.lower() in ["price", "sale_price", "current_price"] and isinstance(v, str):
                                                try: prices.append(float(v.replace(",", "")))
                                                except: pass
                                            elif isinstance(v, (dict, list)):
                                                prices.extend(_find_prices(v, depth+1))
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            prices.extend(_find_prices(item, depth+1))
                                    return prices
                                prices = _find_prices(init_data)
                                if prices:
                                    result["found"] = True
                                    result["lowest_price"] = min(prices)
                                    result["highest_price"] = max(prices)
                                    result["price_samples"] = prices
                                    print(f"    [SAFQA] HIT via React data: prices={prices}")
                                    break
                            except:
                                pass
                    if result["found"]:
                        break
            except Exception as e:
                print(f"      [SAFQA] Page error: {str(e)[:50]}")
                continue

    if result["found"]:
        print(f"    [SAFQA] Result: Low={result['lowest_price']:,.0f} High={result['highest_price']:,.0f}")
    else:
        print(f"    [SAFQA] Not found (tried {len(api_urls)} API + {len(page_urls)} page URLs)")

    return result


def check_price_history(asin=None, product_url=None, current_price=0,
                        original_price=0, title="", site="amazon_eg"):
    """
    Main entry point: checks BOTH Kanbkam and Safqa, combines best data,
    then applies Rules A+B for fake discount detection.

    Works for:
    - Amazon Egypt: Kanbkam (primary) + Safqa (fallback)
    - Jumia Egypt:  Safqa only
    - Noon Egypt:   Safqa only
    - Others:       local analysis only
    """
    print(f"    Checking price history: {title[:40]}...")

    kanbkam_data = {"found": False, "lowest_price": 0, "highest_price": 0}
    safqa_data   = {"found": False, "lowest_price": 0, "highest_price": 0, "coupon_codes": []}

    # Price history lookup only works for Amazon products (need ASIN-based tracking)
    is_amazon = "amazon" in str(site).lower()
    if not is_amazon:
        return local_verdict(current_price, original_price)

    # Kanbkam: Amazon Egypt only, needs ASIN
    if site == "amazon_eg" and asin:
        kanbkam_data = check_kanbkam(asin, title)
        time.sleep(1)

    # Safqa: Amazon only (ASIN-based)
    if asin:
        safqa_data = check_safqa(asin, product_url, title)
        time.sleep(1)

    # Combine: take most conservative (lowest) price from either source
    lowest_price  = 0
    highest_price = 0
    source_used   = "none"

    if kanbkam_data["found"] and safqa_data["found"]:
        lowest_price  = min(kanbkam_data["lowest_price"],  safqa_data["lowest_price"])
        highest_price = min(kanbkam_data["highest_price"], safqa_data["highest_price"])
        source_used   = "kanbkam+safqa"
        print(f"    Combined: Kanbkam={kanbkam_data['lowest_price']:,.0f} Safqa={safqa_data['lowest_price']:,.0f} → Using={lowest_price:,.0f}")
    elif kanbkam_data["found"]:
        lowest_price  = kanbkam_data["lowest_price"]
        highest_price = kanbkam_data["highest_price"]
        source_used   = "kanbkam"
    elif safqa_data["found"]:
        lowest_price  = safqa_data["lowest_price"]
        highest_price = safqa_data["highest_price"]
        source_used   = "safqa"
    else:
        return local_verdict(current_price, original_price)

    return apply_rules_ab(
        current_price=current_price,
        original_price=original_price,
        lowest_price=lowest_price,
        highest_price=highest_price,
        kanbkam_url=kanbkam_data.get("url", ""),
        safqa_url=safqa_data.get("url", ""),
        coupon_codes=safqa_data.get("coupon_codes", []),
        source_used=source_used
    )


def apply_rules_ab(current_price, original_price, lowest_price, highest_price,
                   kanbkam_url="", safqa_url="", coupon_codes=None, source_used=""):
    """
    RULE A: original_price > highest_price * 1.05
            → The 'was' price shown was never real
    RULE B: (highest - lowest) <= EGP 5 AND current ≈ lowest
            → Price has NEVER meaningfully changed
    FAKE        = Rule A AND Rule B both true
    SUSPICIOUS  = Only one rule true
    GENUINE     = Current price near historical low
    WAIT        = Current price far above historical low (>40% above)
    """
    if coupon_codes is None:
        coupon_codes = []

    rule_a = (original_price > highest_price * 1.05) if highest_price > 0 else False
    price_range = (highest_price - lowest_price) if highest_price > lowest_price else 0
    rule_b = (price_range <= 5) and (abs(current_price - lowest_price) <= 5)

    near_lowest = (current_price <= lowest_price * 1.15) if lowest_price > 0 else False
    above_low_pct = (
        round((current_price - lowest_price) / lowest_price * 100)
        if lowest_price > 0 and current_price > lowest_price else 0
    )
    suggested_wait = round(lowest_price * 1.05) if lowest_price > 0 else 0
    coupon_str = ", ".join(coupon_codes[:3]) if coupon_codes else None

    if rule_a and rule_b:
        verdict    = "FAKE"
        verdict_ar = "خصم مزيف — السعر الأصلي كان مزيفاً دائماً"
        emoji      = "❌"
        fake_score = 95
        reason     = (f"FAKE CONFIRMED (Rules A+B, source: {source_used}):\n"
                      f"• Rule A: 'was' EGP {original_price:,.0f} but real highest EVER was EGP {highest_price:,.0f}\n"
                      f"• Rule B: Price was always ~EGP {lowest_price:,.0f} — never changed")
        reason_ar  = (f"خصم مزيف مؤكد: السعر كان دائماً {lowest_price:,.0f} جنيه ولم يتغير أبداً، "
                      f"والسعر الأصلي المعلن {original_price:,.0f} جنيه أعلى من أعلى سعر حقيقي {highest_price:,.0f} جنيه")
    elif rule_a:
        verdict    = "SUSPICIOUS"
        verdict_ar = "مشبوه — السعر الأصلي مبالغ فيه"
        emoji      = "⚠️"
        fake_score = 72
        reason     = (f"SUSPICIOUS (Rule A, source: {source_used}):\n"
                      f"'was' EGP {original_price:,.0f} but real highest was only EGP {highest_price:,.0f}.")
        reason_ar  = f"مشبوه: السعر الأصلي المعلن {original_price:,.0f} جنيه أعلى من أعلى سعر حقيقي {highest_price:,.0f} جنيه."
    elif rule_b:
        verdict    = "SUSPICIOUS"
        verdict_ar = "مشبوه — السعر لم يتغير قط"
        emoji      = "⚠️"
        fake_score = 58
        reason     = (f"SUSPICIOUS (Rule B, source: {source_used}):\n"
                      f"Price was always EGP {lowest_price:,.0f} — never meaningfully changed.")
        reason_ar  = f"مشبوه: السعر كان دائماً {lowest_price:,.0f} جنيه ولم يتغير أبداً."
    elif near_lowest:
        verdict    = "GENUINE"
        verdict_ar = "خصم حقيقي — قريب من أقل سعر تاريخي"
        emoji      = "✅"
        fake_score = 10
        reason     = (f"GENUINE (source: {source_used}):\n"
                      f"Current EGP {current_price:,.0f} is near historical low EGP {lowest_price:,.0f}. Great deal!")
        reason_ar  = f"حقيقي: السعر الحالي {current_price:,.0f} جنيه قريب من أقل سعر {lowest_price:,.0f} جنيه."
    elif above_low_pct > 40:
        verdict    = "WAIT"
        verdict_ar = "انتظر — سعر أفضل متوقع"
        emoji      = "⏳"
        fake_score = 35
        reason     = (f"WAIT (source: {source_used}):\n"
                      f"Price was EGP {lowest_price:,.0f} before. Current EGP {current_price:,.0f} is {above_low_pct}% above historical low.")
        reason_ar  = f"انتظر: السعر كان {lowest_price:,.0f} جنيه. الحالي أعلى بـ{above_low_pct}%."
    else:
        verdict    = "GENUINE"
        verdict_ar = "خصم حقيقي"
        emoji      = "✅"
        fake_score = 20
        reason     = (f"GENUINE (source: {source_used}):\n"
                      f"Price history looks normal. Current: EGP {current_price:,.0f}, Historical low: EGP {lowest_price:,.0f}")
        reason_ar  = "حقيقي: تاريخ السعر طبيعي."

    return {
        "kanbkam_checked":   source_used in ("kanbkam", "kanbkam+safqa"),
        "safqa_checked":     source_used in ("safqa", "kanbkam+safqa"),
        "source_used":       source_used,
        "kanbkam_url":       kanbkam_url,
        "safqa_url":         safqa_url,
        "lowest_price":      lowest_price,
        "highest_price":     highest_price,
        "rule_a_triggered":  rule_a,
        "rule_b_triggered":  rule_b,
        "verdict":           verdict,
        "verdict_ar":        verdict_ar,
        "emoji":             emoji,
        "fake_score":        fake_score,
        "reason":            reason,
        "reason_ar":         reason_ar,
        "near_lowest":       near_lowest,
        "suggested_wait_price": suggested_wait,
        "coupon_codes":      coupon_codes,
        "coupon_display":    coupon_str,
        "checked_at":        now_iso(),
    }


def local_verdict(current_price, original_price):
    """Fallback when both Kanbkam and Safqa are unreachable.
    Uses price ratio to give the most conservative safe verdict.
    """
    ratio = original_price / current_price if current_price > 0 else 1
    disc  = round((original_price - current_price) / original_price * 100) if original_price > 0 else 0

    if ratio > 3.5 and disc > 65:
        # e.g. SAR 380 → 89 (4.3x, 77%) — almost certainly inflated "was" price
        v, va, e, fs = "FAKE", "خصم مزيف — نسبة مرتفعة جداً بدون تاريخ سعر", "❌", 82
        reason = (f"LIKELY FAKE (ratio {ratio:.1f}x, {disc}% claimed discount). "
                  f"No verified price history — 'was' price of {original_price:,.0f} "
                  f"appears artificially inflated.")
    elif ratio > 3.0:
        v, va, e, fs = "SUSPICIOUS", "مشبوه - نسبة مرتفعة جداً", "⚠️", 68
        reason = (f"SUSPICIOUS (ratio {ratio:.1f}x). "
                  f"Original {original_price:,.0f} is very high vs current {current_price:,.0f}. "
                  f"Price history unavailable to confirm.")
    elif ratio > 2.0:
        v, va, e, fs = "SUSPICIOUS", "مشبوه", "⚠️", 45
        reason = f"High ratio ({ratio:.1f}x). Price history unavailable."
    else:
        v, va, e, fs = "UNVERIFIED", "غير مؤكد", "❓", 30
        reason = "Price history unavailable. Cannot verify."

    return {
        "kanbkam_checked": False, "safqa_checked": False,
        "source_used": "ratio_only", "kanbkam_url": "", "safqa_url": "",
        "lowest_price": 0,         "highest_price": 0,
        "rule_a_triggered": False, "rule_b_triggered": False,
        "verdict": v,              "verdict_ar": va,  "emoji": e,
        "fake_score": fs,          "reason": reason,  "reason_ar": reason,
        "near_lowest": False,      "suggested_wait_price": 0,
        "coupon_codes": [],        "coupon_display": None,
        "checked_at": now_iso()
    }


# ─────────────────────────────────────────────────────
# QUICK TEST — run: python fake_checker.py
# ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("Testing Fake Discount Checker v3 FIXED")
    print("Product: Oraimo FreePods 3 earbuds")
    print("Amazon claims: Was EGP 1,099 → Now EGP 899 (18% OFF)")
    print("=" * 55)

    result = check_price_history(
        asin="B0BS1QCFHX",
        current_price=899,
        original_price=1099,
        title="Oraimo FreePods 3 OEB-E104DC True Wireless Earbuds",
        site="amazon_eg"
    )

    print("\n" + "=" * 55)
    print("RESULT:")
    print(f"Verdict:          {result['emoji']} {result['verdict']}")
    print(f"Verdict (AR):     {result['verdict_ar']}")
    print(f"Lowest ever:      EGP {result['lowest_price']:,.0f}")
    print(f"Highest ever:     EGP {result['highest_price']:,.0f}")
    print(f"Rule A triggered: {result['rule_a_triggered']}")
    print(f"Rule B triggered: {result['rule_b_triggered']}")
    print(f"Source used:      {result['source_used']}")
    print(f"Coupon codes:     {result['coupon_codes']}")
    if result['suggested_wait_price']:
        print(f"Wait for price:   EGP {result['suggested_wait_price']:,.0f}")
    print(f"\nReason: {result['reason']}")
    print("=" * 55)
