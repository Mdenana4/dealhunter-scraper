#!/usr/bin/env python3
"""
Safqa Scraper — Playwright Headless Browser Version
No proxy needed. Renders React SPA like a real browser.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    from safqa_playwright import SafqaPlaywright
    s = SafqaPlaywright()
    result = s.check_safqa("B08N5WRWNW")
    s.close()
"""

import json
import re
from playwright.sync_api import sync_playwright


class SafqaPlaywright:
    """Safqa scraper using headless Chromium — no proxy needed."""

    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        self.page = self.context.new_page()
        # Hide automation
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)

    def check_safqa(self, asin=None, product_url=None, title=""):
        """Check Safqa for price history using headless browser."""
        result = {
            "found": False,
            "lowest_price": 0,
            "highest_price": 0,
            "price_samples": [],
            "coupon_codes": [],
        }

        if not asin:
            return result

        urls_to_try = [
            f"https://safqaprice.com/product/{asin}?country=eg",
            f"https://safqaprice.com/products/{asin}?country=eg",
            f"https://safqaprice.com/search?q={asin}&country=eg",
        ]

        for url in urls_to_try:
            try:
                print(f"    [SAFQA-PLAYWRIGHT] Navigating: {url[:60]}...")
                self.page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for React to render (SPA loading)
                self.page.wait_for_timeout(5000)

                # Check if page loaded (not just loading spinner)
                html = self.page.content()

                # Method 1: Look for JSON-LD structured data
                json_ld_scripts = self.page.query_selector_all('script[type="application/ld+json"]')
                for script in json_ld_scripts:
                    try:
                        data = json.loads(script.inner_text())
                        if isinstance(data, dict) and data.get("@type") == "Product":
                            offers = data.get("offers", {})
                            if isinstance(offers, dict):
                                price = offers.get("price")
                                if price:
                                    result["found"] = True
                                    result["lowest_price"] = float(str(price).replace(",", ""))
                                    result["price_samples"] = [result["lowest_price"]]
                                    print(f"    [SAFQA-PLAYWRIGHT] Found JSON-LD: EGP {result['lowest_price']:,.0f}")
                                    return result
                    except:
                        pass

                # Method 2: Look for __NEXT_DATA__
                next_data = self.page.query_selector("script#__NEXT_DATA__")
                if next_data:
                    try:
                        data = json.loads(next_data.inner_text())
                        prices = self._extract_prices(data)
                        if prices:
                            result["found"] = True
                            result["lowest_price"] = min(prices)
                            result["highest_price"] = max(prices)
                            result["price_samples"] = prices
                            print(f"    [SAFQA-PLAYWRIGHT] Found __NEXT_DATA__: prices={prices}")
                            return result
                    except:
                        pass

                # Method 3: Look for window.__INITIAL_STATE__
                initial_state = self.page.evaluate("""
                    () => {
                        if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                        if (window.__DATA__) return JSON.stringify(window.__DATA__);
                        return null;
                    }
                """)
                if initial_state:
                    try:
                        data = json.loads(initial_state)
                        prices = self._extract_prices(data)
                        if prices:
                            result["found"] = True
                            result["lowest_price"] = min(prices)
                            result["highest_price"] = max(prices)
                            result["price_samples"] = prices
                            print(f"    [SAFQA-PLAYWRIGHT] Found __INITIAL_STATE__: prices={prices}")
                            return result
                    except:
                        pass

                # Method 4: DOM scraping — look for price elements
                price_selectors = [
                    "[data-testid='product-price']",
                    ".product-price",
                    ".price-current",
                    "span:has-text('EGP')",
                    "div:has-text('EGP')",
                ]
                for sel in price_selectors:
                    try:
                        el = self.page.query_selector(sel)
                        if el:
                            text = el.inner_text().strip()
                            price_match = re.search(r'[\d,]+\.?\d*', text.replace(",", ""))
                            if price_match:
                                price = float(price_match.group().replace(",", ""))
                                if price > 0:
                                    result["found"] = True
                                    result["lowest_price"] = price
                                    result["price_samples"] = [price]
                                    print(f"    [SAFQA-PLAYWRIGHT] Found DOM price: EGP {price:,.0f}")
                                    return result
                    except:
                        pass

                # Method 5: If search page, click first result
                if "/search" in url:
                    try:
                        first_link = self.page.query_selector("a[href*='/product/']")
                        if first_link:
                            href = first_link.get_attribute("href")
                            if href:
                                new_url = f"https://safqaprice.com{href}"
                                print(f"    [SAFQA-PLAYWRIGHT] Following search result: {new_url[:50]}...")
                                self.page.goto(new_url, wait_until="networkidle", timeout=30000)
                                self.page.wait_for_timeout(3000)
                                # Re-run extraction on product page
                                continue
                    except:
                        pass

                print(f"    [SAFQA-PLAYWRIGHT] No data on: {url[:50]}...")

            except Exception as e:
                print(f"    [SAFQA-PLAYWRIGHT] Error on {url[:50]}: {str(e)[:60]}")
                continue

        print(f"    [SAFQA-PLAYWRIGHT] Not found for ASIN: {asin}")
        return result

    def _extract_prices(self, obj, depth=0):
        """Recursively extract prices from nested dict/list."""
        if depth > 10:
            return []
        prices = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if kl in ["price", "sale_price", "current_price", "offer_price"] and isinstance(v, (int, float)):
                    if v > 0:
                        prices.append(v)
                elif kl in ["price", "sale_price", "current_price"] and isinstance(v, str):
                    try:
                        p = float(v.replace(",", ""))
                        if p > 0:
                            prices.append(p)
                    except:
                        pass
                elif isinstance(v, (dict, list)):
                    prices.extend(self._extract_prices(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                prices.extend(self._extract_prices(item, depth + 1))
        return prices

    def close(self):
        """Close browser."""
        try:
            self.context.close()
            self.browser.close()
            self.playwright.stop()
        except:
            pass

    def __del__(self):
        self.close()


def check_safqa_playwright(asin=None, product_url=None, title=""):
    """Drop-in replacement for check_safqa() in fake_checker.py."""
    scraper = None
    try:
        scraper = SafqaPlaywright()
        return scraper.check_safqa(asin, product_url, title)
    except ImportError:
        print("    [SAFQA-PLAYWRIGHT] Playwright not installed. Run: pip install playwright && playwright install chromium")
        return {"found": False, "lowest_price": 0, "highest_price": 0, "price_samples": [], "coupon_codes": []}
    except Exception as e:
        print(f"    [SAFQA-PLAYWRIGHT] Browser error: {str(e)[:80]}")
        return {"found": False, "lowest_price": 0, "highest_price": 0, "price_samples": [], "coupon_codes": []}
    finally:
        if scraper:
            scraper.close()


if __name__ == "__main__":
    # Test
    print("=" * 60)
    print("SAFQA PLAYWRIGHT TEST")
    print("=" * 60)

    result = check_safqa_playwright(asin="B08N5WRWNW", title="iPhone 15")
    print(f"\nResult: {'✅ FOUND' if result['found'] else '❌ Not found'}")
    if result["found"]:
        print(f"  Price: EGP {result['lowest_price']:,.0f}")
