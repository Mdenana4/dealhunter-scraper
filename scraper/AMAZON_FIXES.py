"""
================================================================================
DealHunter Egypt — Amazon Scraper Fixes (REAL BOTTLENECKS)
================================================================================
After analyzing the full 3,537-line scraper.py, here are the ACTUAL reasons
Amazon only finds ~12 deals per cycle, and the targeted fixes.

ROOT CAUSE ANALYSIS
================================================================================

BOTTLENECK 1: Keyword search is DISABLED by default (line 29)
  AMAZON_KEYWORD_ENABLED defaults to "false"
  → _scrape_amazon_region() ONLY runs if deals page returns 0
  → Normally only the deals page runs (~12 deals)
  → 48 keywords × up to 6 deals = 288 potential deals NEVER RUN

BOTTLENECK 2: Deals page burns 30 credits per run (line 1215)
  super_proxy=True = 10 credits/page × 3 pages = 30 credits
  → When scrape.do is rate-limited, falls back to direct (blocked)
  → Gets ~12 products from 3 pages before proxy dies

BOTTLENECK 3: 6-deal cap per keyword (lines 1389, 1463)
  if saved_this_keyword >= 6: break
  → Even when keyword search IS enabled, hard cap of 6 per keyword
  → 48 keywords × 6 = 288 max, but with blocking it's more like 48 × 2-3

BOTTLENECK 4: Strategy A (structured API) skips Egypt (line 441)
  _AMAZON_API_GEOCODES has no "eg" entry
  → fetch_amazon_structured_search() returns None for Egypt
  → Falls through to Strategy B (HTML scraping) which is slower

BOTTLENECK 5: 5+ minutes of dead time from sleep() calls
  time.sleep(1) per product × ~30 products = 30s
  time.sleep(3) between pages × 3 = 9s
  time.sleep(2) between keywords × 48 = 96s
  time.sleep(0.5) between saves × ~30 = 15s
  → ~2.5 minutes of sleep in a cycle that should take 30 seconds

BOTTLENECK 6: Wrong language parameter in URL (line 1205)
  language=en_AE (UAE) instead of en_EG (Egypt)
  → May cause Amazon to serve wrong regional content

FIXES — Only 8 changes needed
================================================================================
"""


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 1: Enable keyword search by default (1 line change in scraper.py)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Line 29
# OLD:
#     AMAZON_KEYWORD_ENABLED = os.getenv("AMAZON_KEYWORD_ENABLED", "false").lower() == "true"
# NEW:
AMAZON_KEYWORD_ENABLED = os.getenv("AMAZON_KEYWORD_ENABLED", "true").lower() == "true"
#                     #                                 ^^^^^^ changed from "false"
# Impact: Enables _scrape_amazon_region() to run every cycle, not just when deals page fails


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 2: Remove super_proxy from deals page (1 line change in scraper.py)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Line 1215
# OLD:
#     resp = fetch_with_scrapedo(url, render_js=True, country=country_code, super_proxy=True)
# NEW:
#     resp = fetch_with_scrapedo(url, render_js=True, country=country_code)
#                                                     # removed: super_proxy=True
# Impact: Saves 9 credits/page (1 credit instead of 10). 3 pages = 3 credits instead of 30.
# If scrape.do datacenter IPs are blocked, the fallback chain already handles it.


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 3: Fix language parameter (1 line change in scraper.py)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Line 1205
# OLD:
#     deals_url = (
#         f"https://www.{base_domain}/s?"
#         f"rh=p_n_pct-off-with-tax%3A40-&s=discount-rank&language=en_AE"
#     )
# NEW:
#     deals_url = (
#         f"https://www.{base_domain}/s?"
#         f"rh=p_n_pct-off-with-tax%3A40-&s=discount-rank&language=en_EG"
#     )
#     # ^^^ changed en_AE to en_EG for Egypt region
# Same fix needed for the keyword search URL in _scrape_amazon_region() around line 1480:
# OLD: url = f"https://www.{base_domain}/s?k={item['k'].replace(' ', '+')}&language=en_AE"
# NEW: url = f"https://www.{base_domain}/s?k={item['k'].replace(' ', '+')}&language=en_EG"


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 4: Raise the per-keyword cap from 6 to 12 (2 line changes in scraper.py)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Lines 1389 and 1463
# OLD (both locations):
#     if saved_this_keyword >= 6:
#         break
# NEW (both locations):
#     if saved_this_keyword >= 12:
#         break
# Impact: Doubles the max deals per keyword. With 48 keywords, max goes from 288 to 576.
# In practice with blocking, expect ~200-300 instead of ~100-150.


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 5: Reduce sleep times for Amazon scraper (4 line changes in scraper.py)
# ═══════════════════════════════════════════════════════════════════════════════

# Location: Line 1324 (in _scrape_amazon_deals_page)
# OLD: time.sleep(1)    # after price history check
# NEW: time.sleep(0.3)

# Location: Line 1345 (in _scrape_amazon_deals_page)
# OLD: time.sleep(0.5)  # between saves
# NEW: time.sleep(0.2)

# Location: Line 1350 (in _scrape_amazon_deals_page)
# OLD: time.sleep(3)    # between pages
# NEW: time.sleep(1)

# Location: Line 1440 (in _scrape_amazon_region, Strategy A loop)
# OLD: time.sleep(2)    # between keywords
# NEW: time.sleep(0.5)

# Location: Line 1580 (in _scrape_amazon_region, Strategy B loop)
# OLD: time.sleep(3)    # between keywords
# NEW: time.sleep(1)

# Impact: Cuts ~2 minutes of dead time per cycle


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 6: Add retry with backoff for blocked requests (NEW function to add)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Add after fetch_with_scrapedo()

def fetch_with_retry(url, fetch_fn, max_retries=3, backoff=2):
    """Retry a fetch with exponential backoff. Returns response or None."""
    for attempt in range(max_retries):
        resp = fetch_fn(url)
        if resp and not is_blocked_response(resp, min_length=2000):
            return resp
        wait = backoff * (2 ** attempt)  # 2s, 4s, 8s
        print(f"    [retry] Attempt {attempt+1}/{max_retries} failed, waiting {wait}s...")
        time.sleep(wait)
    return None

# Usage in _scrape_amazon_deals_page (replace the fetch chain):
# OLD:
#     resp = fetch_with_scrapedo(url, render_js=True, country=country_code)
#     if not resp or is_blocked_response(resp, min_length=3000):
#         resp = fetch_with_scraperapi(url, render_js=True, country=country_code, _skip_scrapedo=True, premium=True)
#     if is_blocked_response(resp, min_length=3000):
#         resp = fetch_direct(url)
# NEW:
#     resp = fetch_with_retry(url, lambda u: fetch_with_scrapedo(u, render_js=True, country=country_code))
#     if not resp:
#         resp = fetch_with_retry(url, lambda u: fetch_with_scraperapi(u, render_js=True, country=country_code, _skip_scrapedo=True, premium=True), max_retries=2)
#     if not resp:
#         resp = fetch_with_retry(url, fetch_direct, max_retries=1)


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 7: Use concurrent requests for keyword batches (NEW function to add)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Add after the other helpers

from concurrent.futures import ThreadPoolExecutor, as_completed

def scrape_amazon_keywords_parallel(keywords, scrape_fn, max_workers=4):
    """
    Scrape multiple keywords in parallel using thread pool.
    scrape_fn: function(keyword_dict) -> count
    Returns total deals found.
    """
    total = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_fn, kw): kw for kw in keywords}
        for future in as_completed(futures):
            kw = futures[future]
            try:
                count = future.result(timeout=30)
                total += count
            except Exception as e:
                print(f"    [parallel] Keyword '{kw.get('k', '?')}': {e}")
    return total

# Usage in _scrape_amazon_region:
# Replace the sequential keyword loop with parallel batches.
# Process keywords in batches of 8 to avoid overwhelming the proxy.


# ═══════════════════════════════════════════════════════════════════════════════
# FIX 8: Add more high-value keywords (add to AMAZON_KEYWORDS list)
# ═══════════════════════════════════════════════════════════════════════════════
# Location: Line 1135 (AMAZON_KEYWORDS list)
# Add these high-value, high-discount categories:

ADDITIONAL_KEYWORDS = [
    {"k": "realme phone",      "cat": "electronics"},
    {"k": "infinix phone",     "cat": "electronics"},
    {"k": "tecno phone",       "cat": "electronics"},
    {"k": "honor phone",       "cat": "electronics"},
    {"k": "nokia phone",       "cat": "electronics"},
    {"k": "smart watch",       "cat": "electronics"},
    {"k": "wireless earbuds",  "cat": "electronics"},
    {"k": "smart tv 43",       "cat": "electronics"},
    {"k": "smart tv 55",       "cat": "electronics"},
    {"k": "soundbar",          "cat": "electronics"},
    {"k": "men running shoes", "cat": "fashion"},
    {"k": "women sandals",     "cat": "fashion"},
    {"k": "casio watch",       "cat": "fashion"},
    {"k": "backpack laptop",   "cat": "fashion"},
    {"k": "skechers shoes",    "cat": "fashion"},
    {"k": "kitchen organizer", "cat": "home"},
    {"k": "food processor",    "cat": "home"},
    {"k": "rice cooker",       "cat": "home"},
    {"k": "stand mixer",       "cat": "home"},
    {"k": "water dispenser",   "cat": "home"},
    {"k": "face serum",        "cat": "beauty"},
    {"k": "hair oil",          "cat": "beauty"},
    {"k": "body lotion",       "cat": "beauty"},
    {"k": "men perfume",       "cat": "beauty"},
    {"k": "women perfume",     "cat": "beauty"},
    {"k": "whey protein",      "cat": "sports"},
    {"k": "dumbbell set",      "cat": "sports"},
    {"k": "exercise bike",     "cat": "sports"},
    {"k": "massage gun",       "cat": "sports"},
]
# Append these to the existing AMAZON_KEYWORDS list (line ~1135)
# This adds 29 more keywords to the existing 48, bringing total to 77.


"""
================================================================================
EXPECTED RESULTS AFTER FIXES
================================================================================

Before fixes:
  - Deals page only: ~12 deals/cycle
  - Keyword search: disabled (never runs)
  - Total: ~12 deals

After fixes:
  - Deals page: ~12 deals (with retry, maybe 15-20)
  - Keyword search: 77 keywords × ~4 deals (with blocking) = ~300 deals
  - With 12-deal cap: 77 × 8 = ~616 max, realistically ~200-400
  - With parallel requests + reduced sleep: completes in ~1-2 minutes
  - Total: ~200-400 deals per cycle (vs ~12 before)

PROXY CREDIT ESTIMATE:
  - Deals page: 3 pages × 1 credit = 3 credits
  - Keyword search: 77 keywords × 1 credit = 77 credits
  - Total: ~80 credits per cycle (vs 30 credits for 12 deals before)
  - If scrape.do gives 10,000 credits/month: ~125 cycles = 5 cycles/day

DEPLOYMENT STEPS:
  1. Make the 8 code changes in scraper.py
  2. Add the 2 new functions (fetch_with_retry, scrape_amazon_keywords_parallel)
  3. Add the 29 new keywords
  4. Deploy to Railway
  5. Monitor first 3 cycles for credit burn rate
  6. Adjust max_workers (4 → 3) if proxies are rate-limited
================================================================================
"""
