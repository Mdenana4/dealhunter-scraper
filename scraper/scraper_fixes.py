"""
================================================================================
DealHunter Egypt — Scraper Fixes Patch (v8)
================================================================================
This file contains ALL fixes for the issues in scraper.py v7.

Apply these changes by:
1. Copy the functions below into your scraper.py (replace existing ones)
2. Update the Jumia/Noon scraper sections as indicated
3. Add the new helpers at the top of the file (after the existing helpers)

ISSUES FIXED:
  [CRITICAL] 1. Rating counts read as prices ("592 Ratings" → 592 EGP)
  [CRITICAL] 2. Sales counts read as prices ("380+ sold recently" → 380 EGP)
  [CRITICAL] 3. Discount badges read as prices ("59% Off" → 59 EGP)
  [CRITICAL] 4. Product specs read as prices ("1400 RPM" → 1400 EGP)
  [CRITICAL] 5. RAM/storage read as prices ("128GB" → 128 EGP)
  [CRITICAL] 6. USD prices not converted ($71.83 stored as 71.83 EGP)
  [CRITICAL] 7. Monthly installment read as price (71.83/month → 71.83 EGP)
  [HIGH]     8. Stale deals persist after discount ends (Noon/Jumia)
  [HIGH]     9. Wrong categories on Jumia (search URL → breadcrumb)
  [HIGH]     10. Broken Jumia product URLs (homepage instead of product)
  [HIGH]     11. Wrong categories on Noon (keyword → product page)
  [MEDIUM]   12. "Noon Egypt do electronics" source label bug
  [MEDIUM]   13. Amazon only finds ~13 deals (selectors + 502 errors)
  [MEDIUM]   14. Jumia fashion/beauty return 0 products
================================================================================
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: DROP-IN REPLACEMENTS (paste these into scraper.py)
# ═══════════════════════════════════════════════════════════════════════════════

# ─── 1.1 Replace clean_price() ───────────────────────────────────────────────
# Location: ~line 88 in scraper.py
# OLD:
#   def clean_price(text):
#       if not text: return 0.0
#       text = str(text).replace(',','').replace('EGP','')...
#       text = re.sub(r'[^\d.]', '', text)
#       try: return float(text)
#       except: return 0.0

# NEW:
def clean_price(text):
    """
    Extract price from text. Returns 0.0 for non-price text.
    Rejects social-proof text (ratings, sold counts), specs (RPM, GB),
    discount badges (% Off), and installment text.
    """
    if not text:
        return 0.0

    text = str(text).strip()
    original = text
    lower = text.lower()

    # ── STEP 1: Reject obvious non-price text ─────────────────────────
    non_price_indicators = [
        # Social proof
        'rating', 'ratings', 'rated', 'review', 'reviews',
        'sold', 'bought', 'purchased', 'ordered',
        'customer', 'buyer', 'viewer',
        # Discount badges
        '% off', 'percent off', 'discount', 'save',
        # Specs
        'rpm', 'gb', 'tb', 'mb', 'mhz', 'ghz', 'watt', 'watts',
        'inch', '"', 'cm', 'mm', 'kg', 'grams', 'liter', 'l',
        'mah', 'pixel', 'mp', 'dpi', 'fps', 'hz',
        # Installment
        '/month', 'monthly', 'installment', 'installments',
        'per month', 'egp/month', '$/month',
        # Currency confusion
        '$', 'usd', 'dollar', 'dollars', 'eur', 'euro', 'aed', 'sar',
        # Generic non-price
        'off', 'up to', 'starting', 'from', 'as low as',
    ]

    for indicator in non_price_indicators:
        if indicator in lower:
            return 0.0

    # Reject if text is purely a number with % sign
    if re.match(r'^\d+%$', text):
        return 0.0

    # Reject if text looks like a spec (number + unit, e.g. "128GB", "1400 RPM")
    if re.match(r'^\d+\s*[a-zA-Z/]+$', text):
        return 0.0

    # ── STEP 2: Strip currency symbols and whitespace ─────────────────
    text = (text
            .replace(',', '')
            .replace('EGP', '')
            .replace('ج.م', '')
            .replace('جنيه', '')
            .replace('جنية', '')
            .replace('ج', '')
            .replace('~', '')
            .strip())

    # ── STEP 3: Extract numeric value ─────────────────────────────────
    # Look for a number pattern: optional digits, optional decimal, digits
    match = re.search(r'(\d+(?:\.\d{1,2})?)', text)
    if not match:
        return 0.0

    try:
        value = float(match.group(1))
    except Exception:
        return 0.0

    # ── STEP 4: Sanity checks ────────────────────────────────────────
    # Too cheap for real product (filters out most spec/RPM/GB false positives)
    if value < 10:
        return 0.0

    # Too cheap for electronics/fashion (128, 256, 512 are common RAM/GB specs)
    if 100 <= value <= 999:
        # Extra check: if the original text had GB, MB, RPM, etc.
        spec_units = ['gb', 'mb', 'tb', 'rpm', 'mah', 'mhz', 'ghz', 'w',
                      'mp', 'dpi', 'hz', 'kg', 'mm', 'cm', 'inch']
        for unit in spec_units:
            if unit in original.lower():
                return 0.0

    # Too expensive (likely a phone number or ID)
    if value > 500000:
        return 0.0

    return value


# ─── 1.2 Add new helper: is_social_proof_text() ──────────────────────────────
# Location: Add this right after clean_price()

def is_social_proof_text(text):
    """Return True if text is social proof (ratings, sold count) NOT a price."""
    if not text:
        return False
    lower = str(text).lower().strip()
    social_patterns = [
        r'\d+\s*rating', r'\d+\s*ratings',
        r'\d+\+?\s*sold', r'\d+\+?\s*bought',
        r'\d+\s*review', r'\d+\s*reviews',
        r'\d+\s*customer', r'\d+\s*buyer',
    ]
    return any(re.search(p, lower) for p in social_patterns)


def is_spec_text(text):
    """Return True if text is a product spec (RPM, GB, etc.) NOT a price."""
    if not text:
        return False
    text = str(text).strip()
    spec_patterns = [
        r'^\d+\s*rpm$', r'^\d+\s*gb$', r'^\d+\s*tb$', r'^\d+\s*mb$',
        r'^\d+\s*mah$', r'^\d+\s*mhz$', r'^\d+\s*ghz$',
        r'^\d+\s*watt?s?$', r'^\d+\s*mp$', r'^\d+\s*hz$',
        r'^\d+\s*kg$', r'^\d+\s*mm$', r'^\d+\s*cm$',
        r'^\d+\.?\d*\s*"$', r'^\d+\s*inch',
    ]
    return any(re.search(p, text, re.I) for p in spec_patterns)


def is_installment_text(text):
    """Return True if text describes a monthly installment, not a full price."""
    if not text:
        return False
    lower = str(text).lower()
    installment_indicators = [
        '/month', 'monthly', 'per month', 'installment',
        'قسط', 'شهري', '/شهر',
    ]
    return any(ind in lower for ind in installment_indicators)


def contains_dollar_sign(text):
    """Return True if text contains $ (indicating USD price on Amazon.eg)."""
    if not text:
        return False
    return '$' in str(text)


# ─── 1.3 Add USD→EGP conversion ──────────────────────────────────────────────
# Location: Add after the other helpers

# Exchange rate cache (refresh every 6 hours)
_usd_to_egp_rate = None
_usd_rate_cached_at = 0
_USD_CACHE_TTL = 6 * 3600  # 6 hours


def get_usd_to_egp():
    """Fetch current USD→EGP exchange rate. Returns 50.0 as fallback."""
    global _usd_to_egp_rate, _usd_rate_cached_at

    now = time.time()
    if _usd_to_egp_rate and (now - _usd_rate_cached_at) < _USD_CACHE_TTL:
        return _usd_to_egp_rate

    try:
        resp = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=10,
        )
        if resp.status_code == 200:
            rate = resp.json().get("rates", {}).get("EGP", 50.0)
            if rate and rate > 0:
                _usd_to_egp_rate = rate
                _usd_rate_cached_at = now
                print(f"    [FX] USD→EGP = {rate:.2f}")
                return rate
    except Exception as e:
        print(f"    [FX] Error fetching rate: {e}")

    # Fallback rates
    _usd_to_egp_rate = 50.0
    _usd_rate_cached_at = now
    return 50.0


def convert_usd_to_egp(usd_price):
    """Convert a USD price to EGP."""
    rate = get_usd_to_egp()
    return round(usd_price * rate, 2)


# ─── 1.4 Add stale deal purging ──────────────────────────────────────────────
# Location: Add after save_deal()

_STALE_DEAL_MAX_AGE_HOURS = 48  # Mark deals inactive after 48h of no re-check


def purge_stale_deals():
    """
    Mark deals as inactive if they haven't been re-checked in 48+ hours.
    Call this at the end of every scraper run.
    """
    if not db:
        return
    try:
        cutoff = datetime.now(timezone.utc).isoformat()
        # Find deals whose last_scraped is older than the threshold
        # We can't do date math in Firestore queries, so we fetch and filter
        stale_refs = []
        count = 0

        for site_key in ["amazon_eg", "noon_eg", "jumia_eg"]:
            docs = (db.collection("deals")
                    .where("site", "==", site_key)
                    .where("status", "==", "active")
                    .limit(500)
                    .stream())

            for doc in docs:
                data = doc.to_dict()
                last_scraped = data.get("last_scraped", "")
                if not last_scraped:
                    continue

                # Parse the timestamp
                try:
                    if isinstance(last_scraped, str):
                        from datetime import datetime as _dt
                        scraped_time = _dt.fromisoformat(last_scraped.replace('Z', '+00:00'))
                    else:
                        scraped_time = last_scraped

                    hours_old = (datetime.now(timezone.utc) - scraped_time).total_seconds() / 3600
                    if hours_old > _STALE_DEAL_MAX_AGE_HOURS:
                        doc.reference.update({
                            "status": "inactive",
                            "purged_at": now_iso(),
                            "purge_reason": f"Not re-checked in {hours_old:.0f} hours",
                        })
                        count += 1
                except Exception:
                    continue

        if count > 0:
            print(f"  [PURGE] Marked {count} stale deals as inactive (>{_STALE_DEAL_MAX_AGE_HOURS}h old)")
    except Exception as e:
        print(f"  [PURGE] Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: FIXES FOR JUMIA SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

# In your Jumia scraper function, replace the price extraction with:

"""
# INSIDE scrape_jumia() or scrape_jumia_category():

# OLD (broken — picks up wrong elements):
#   price_text = product.find("span", class_="prc").get_text()
#   current_price = clean_price(price_text)

# NEW (fixed — validates before extracting):
    price_el = product.find("span", class_="prc")
    if not price_el:
        continue
    price_text = price_el.get_text(strip=True)

    # Reject social proof / specs / installments
    if is_social_proof_text(price_text):
        print(f"    SKIP: social proof text '{price_text}'")
        continue
    if is_spec_text(price_text):
        print(f"    SKIP: spec text '{price_text}'")
        continue
    if is_installment_text(price_text):
        print(f"    SKIP: installment text '{price_text}'")
        continue

    current_price = clean_price(price_text)
    if current_price < 10:
        continue

# For original/old price:
    old_price_el = product.find("span", class_="old")
    if old_price_el:
        old_text = old_price_el.get_text(strip=True)
        if not is_social_proof_text(old_text) and not is_spec_text(old_text):
            original_price = clean_price(old_text) or current_price

# For discount percentage:
    discount_el = product.find("span", class_="bdg _dsct")
    if discount_el:
        discount_text = discount_el.get_text(strip=True)
        # Only accept if it contains %
        if '%' in discount_text:
            discount = clean_price(discount_text)
        else:
            discount = calculate_discount(original_price, current_price)
"""


# ─── 2.1 Jumia URL Fix ───────────────────────────────────────────────────────

"""
# OLD (broken — links to homepage):
#   product_url = "https://www.jumia.com.eg" + product.find("a")["href"]

# NEW (fixed — extracts proper product URL):
    link_el = product.find("a", href=True)
    if not link_el:
        continue
    href = link_el["href"]

    # Jumia product URLs should contain the product slug + ID
    # Pattern: /product-name-MP1234567.html or /product-name-EG123.html
    if not re.search(r'-([A-Z]{2}\d+|[A-Z]\w{4,})\.html', href, re.I):
        # Skip non-product links (category pages, etc.)
        continue

    if href.startswith("http"):
        product_url = href
    else:
        product_url = "https://www.jumia.com.eg" + href

    # Verify URL doesn't redirect to homepage
    product_url = product_url.replace("//www.jumia.com.eg//", "//www.jumia.com.eg/")
    if product_url.endswith("jumia.com.eg") or product_url.endswith("jumia.com.eg/"):
        continue
"""


# ─── 2.2 Jumia Category Fix ──────────────────────────────────────────────────

"""
# OLD (wrong — uses search URL category):
#   category = jumia_category_map.get(search_category, "unknown")

# NEW (fixed — detects from product title + breadcrumb when available):

    # First try: detect from product title
    category = detect_category(title)

    # Second try: look for breadcrumb data in the page
    if not category:
        breadcrumb_el = soup.find("nav", class_=re.compile(r"breadcrumbs?", re.I))
        if breadcrumb_el:
            breadcrumb_links = breadcrumb_el.find_all("a")
            for link in breadcrumb_links:
                bc_text = link.get_text(strip=True).lower()
                if any(k in bc_text for k in ["electronics", "phones", "computers"]):
                    category = "electronics"
                    break
                elif any(k in bc_text for k in ["fashion", "clothing", "shoes", "watches"]):
                    category = "fashion"
                    break
                elif any(k in bc_text for k in ["home", "kitchen", "appliances", "furniture"]):
                    category = "home"
                    break
                elif any(k in bc_text for k in ["beauty", "health", "perfume"]):
                    category = "beauty"
                    break
                elif any(k in bc_text for k in ["toys", "baby", "kids"]):
                    category = "toys"
                    break
                elif any(k in bc_text for k in ["sports", "fitness", "gym"]):
                    category = "sports"
                    break
                elif any(k in bc_text for k in ["supermarket", "grocery", "food"]):
                    category = "grocery"
                    break
                elif any(k in bc_text for k in ["automotive", "car", "auto"]):
                    category = "automotive"
                    break
                elif any(k in bc_text for k in ["books", "stationery", "office"]):
                    category = "books"
                    break

    # Final fallback: use search category mapping
    if not category:
        category = jumia_category_map.get(search_category, "unknown")
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: FIXES FOR NOON SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

# ─── 3.1 Noon Price Fix ──────────────────────────────────────────────────────

"""
# INSIDE scrape_noon() or scrape_noon_category():

# OLD (broken):
#   price_text = product.find("strong", class_="amount").get_text()
#   current_price = clean_price(price_text)

# NEW (fixed):
    price_el = product.find("strong", class_="amount")
    if not price_el:
        continue
    price_text = price_el.get_text(strip=True)

    # Reject non-price text
    if is_social_proof_text(price_text):
        continue
    if is_spec_text(price_text):
        continue
    if is_installment_text(price_text):
        continue

    current_price = clean_price(price_text)
    if current_price < 10:
        continue

    # Check for USD prices (rare but happens on Noon)
    if contains_dollar_sign(price_text):
        current_price = convert_usd_to_egp(current_price)
"""


# ─── 3.2 Noon Category Fix ───────────────────────────────────────────────────

"""
# OLD (wrong — appends keyword category to source):
#   category = noon_search_category  # from the search URL
#   site_display = f"Noon Egypt do {category}"  # BUG!

# NEW (fixed):
    # Detect from product title
    category = detect_category(title)

    # Verify from product page breadcrumb (fetch from __NEXT_DATA__)
    next_data = extract_next_data(resp.text)
    try:
        breadcrumbs = (next_data.get("props", {})
                       .get("pageProps", {})
                       .get("product", {})
                       .get("breadcrumbs", []))
        for crumb in breadcrumbs:
            crumb_name = str(crumb.get("name", "")).lower()
            mapped = None
            if any(k in crumb_name for k in ["electronics", "mobiles", "computers", "tv", "audio"]):
                mapped = "electronics"
            elif any(k in crumb_name for k in ["fashion", "men", "women", "kids", "shoes", "watches", "bags"]):
                mapped = "fashion"
            elif any(k in crumb_name for k in ["home", "kitchen", "appliances", "furniture", "decor", "tools"]):
                mapped = "home"
            elif any(k in crumb_name for k in ["beauty", "personal care", "health", "perfume", "makeup", "skincare"]):
                mapped = "beauty"
            elif any(k in crumb_name for k in ["baby", "toys", "kids"]):
                mapped = "toys"
            elif any(k in crumb_name for k in ["sports", "fitness", "outdoor", "nutrition"]):
                mapped = "sports"
            elif any(k in crumb_name for k in ["food", "grocery", "beverages"]):
                mapped = "grocery"
            elif any(k in crumb_name for k in ["automotive", "car care", "motorcycle"]):
                mapped = "automotive"
            elif any(k in crumb_name for k in ["books", "stationery", "school"]):
                mapped = "books"
            if mapped and (not category or mapped != category):
                category = mapped
                break
    except Exception:
        pass

    # Fix source display
    site_display = "Noon Egypt"  # Always "Noon Egypt", never "Noon Egypt do X"
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: FIXES FOR AMAZON SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════

# ─── 4.1 Amazon Price Fix (in _scrape_amazon_deals_page) ─────────────────────

"""
# In the _scrape_amazon_deals_page() function, replace the price extraction:

# OLD:
#   price_el = product.find("span", class_="a-price-whole")
#   if not price_el: continue
#   current_price = clean_price(price_el.get_text(strip=True))

# NEW:
    price_el = product.find("span", class_="a-price-whole")
    if not price_el:
        continue
    price_text = price_el.get_text(strip=True)

    # Reject non-price text that slipped into the price element
    if is_social_proof_text(price_text):
        continue
    if is_spec_text(price_text):
        continue
    if is_installment_text(price_text):
        continue

    current_price = clean_price(price_text)
    if current_price < 10:
        continue

    # Check for USD prices (Amazon.eg sometimes shows $ prices)
    if contains_dollar_sign(price_text):
        current_price = convert_usd_to_egp(current_price)
"""


# ─── 4.2 Amazon Deals Page URL Fix (502 errors) ──────────────────────────────

"""
# OLD:
#   deals_url = (
#       f"https://www.{base_domain}/s?"
#       f"rh=p_n_pct-off-with-tax%3A40-&s=discount-rank&language=en_AE"
#   )

# NEW (more reliable URL format):
    deals_url = (
        f"https://www.{base_domain}/gp/goldbox?"
        f"ref_=nav_cs_gb&language=en_AE"
    )
    # Fallback to search-filtered URL if goldbox fails
    fallback_url = (
        f"https://www.{base_domain}/s?"
        f"k=deals&rh=p_8%3A30-&s=exact-aware-popularity-rank&language=en_AE"
    )
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: CALL purge_stale_deals() AT END OF run_scraper()
# ═══════════════════════════════════════════════════════════════════════════════

"""
# At the end of run_scraper() function, add:

    # ── Purge stale deals ──────────────────────────────────────────────
    print("\n[MAINTENANCE] Checking for stale deals...")
    purge_stale_deals()

    # ── Send batch FCM notifications ───────────────────────────────────
    if _new_deals_this_run:
        _notify_new_deals(_new_deals_this_run)
        _new_deals_this_run.clear()

    print(f"\n[SCRAPER] Run complete at {now_str()}")
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: ENVIRONMENT VARIABLES TO ADD
# ═══════════════════════════════════════════════════════════════════════════════

"""
Add these to your Railway/Render environment variables:

# Stale deal purging (optional, defaults shown)
STALE_DEAL_MAX_AGE_HOURS=48   # Mark deals inactive after 48h

# Price validation (optional, defaults shown)
MIN_PRICE=10                  # Minimum valid price in EGP
MAX_PRICE=500000              # Maximum valid price in EGP

# USD conversion (optional)
USD_TO_EGP_FALLBACK=50.0      # Fallback rate if API fails
"""


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PATCH
# ═══════════════════════════════════════════════════════════════════════════════
print("scraper_fixes.py loaded — apply the changes above to your scraper.py")
