#!/usr/bin/env python3
"""
Safqa Scraper — With Scrape.do Proxy Support
For use on Railway where scrape.do token is available.

Environment:
    SCRAPEDO_TOKEN=your_token_here

Usage:
    from safqa_scraper_proxied import SafqaScraper
    scraper = SafqaScraper()
    deals = scraper.scrape_deals(country="eg", max_pages=3)
"""

import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime


class SafqaScraper:
    """Safqa scraper with automatic proxy fallback."""

    def __init__(self):
        self.scrapedo_token = os.environ.get("SCRAPEDO_TOKEN", "")
        self.base_url = "https://safqaprice.com"
        self.api_base = None  # Discovered at runtime
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Referer": "https://safqaprice.com/",
        }

    def _fetch(self, url, use_proxy=True):
        """Fetch URL directly or via scrape.do proxy."""
        # Try direct first, then proxy
        methods = []

        if not use_proxy:
            methods.append(("direct", url))
        else:
            # Try direct
            methods.append(("direct", url))
            # Try scrape.do
            if self.scrapedo_token:
                encoded_url = urllib.parse.quote(url, safe="")
                proxy_url = f"https://api.scrape.do/?token={self.scrapedo_token}&url={encoded_url}&render=true"
                methods.append(("scrape.do", proxy_url))
            # Try ScraperAPI fallback
            scraper_api_key = os.environ.get("SCRAPER_API_KEY", "")
            if scraper_api_key:
                encoded_url = urllib.parse.quote(url, safe="")
                proxy_url = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={encoded_url}"
                methods.append(("scraperapi", proxy_url))

        for method_name, fetch_url in methods:
            try:
                req = urllib.request.Request(fetch_url, headers=self.headers, method="GET")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read().decode("utf-8", errors="ignore")

                    # Try to parse as JSON
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        # Return raw HTML for parsing
                        return {"_html": data}

            except urllib.error.HTTPError as e:
                if e.code in (404, 410):
                    return None
                print(f"  [{method_name}] HTTP {e.code} for {url[:80]}")
                continue
            except Exception as e:
                print(f"  [{method_name}] Error: {str(e)[:100]}")
                continue

        return None

    def discover_api(self):
        """Discover Safqa's API endpoints by analyzing the HTML/JS."""
        print("[SAFQA] Discovering API endpoints...")

        # Fetch the main page
        result = self._fetch(self.base_url)
        if not result:
            print("  ❌ Cannot access safqaprice.com")
            return False

        html = result.get("_html", "")

        # Look for API base URL in HTML
        import re

        # Pattern 1: apiBase or API_BASE in inline scripts
        api_patterns = [
            r'apiBase["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'API_BASE["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'api_url["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'baseURL["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'"(/api/[^"\']+)"',
            r'"(https://api\.[^"\']+)"',
        ]

        for pattern in api_patterns:
            matches = re.findall(pattern, html)
            if matches:
                for match in set(matches):
                    print(f"  🔍 Found API hint: {match}")
                    if match.startswith("http"):
                        self.api_base = match
                        print(f"  ✅ API base set: {self.api_base}")
                        return True
                    elif match.startswith("/api"):
                        self.api_base = f"{self.base_url}{match}"
                        print(f"  ✅ API base set: {self.api_base}")
                        return True

        # Pattern 2: Look for fetch() or axios calls in inline scripts
        fetch_patterns = [
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.[get|post]+\(["\']([^"\']+)["\']',
            r'"/api/(v?\d+/)?([^"\']+)"',
        ]

        for pattern in fetch_patterns:
            matches = re.findall(pattern, html)
            if matches:
                print(f"  🔍 Found fetch patterns: {matches[:5]}")

        # Pattern 3: Try to get JS bundle and analyze it
        js_pattern = r'/assets/index-[^"\']+\.js'
        js_matches = re.findall(js_pattern, html)
        if js_matches:
            js_url = f"{self.base_url}{js_matches[0]}"
            print(f"  🔍 Found JS bundle: {js_url}")
            self._analyze_js_bundle(js_url)

        # If still no API base, try common patterns
        if not self.api_base:
            print("  ⚠ No API found in HTML, trying common endpoints...")
            self.api_base = self.base_url  # Will try relative paths

        return True

    def _analyze_js_bundle(self, js_url):
        """Analyze JS bundle for API endpoints."""
        import re

        result = self._fetch(js_url, use_proxy=True)
        if not result or "_html" not in result:
            return

        js_code = result["_html"]
        print(f"  📦 JS bundle size: {len(js_code)} bytes")

        # Look for API endpoint patterns in JS
        patterns = [
            r'["\'](/api/[^"\']+)["\']',
            r'["\'](https://api\.[^"\']+)["\']',
            r'baseURL\s*[:=]\s*["\']([^"\']+)["\']',
            r'path\s*[:=]\s*["\'](/[^"\']+)["\']',
        ]

        found_endpoints = set()
        for pattern in patterns:
            matches = re.findall(pattern, js_code)
            for m in matches:
                if "api" in m.lower() or "/v" in m:
                    found_endpoints.add(m)

        if found_endpoints:
            print(f"  🔍 Found {len(found_endpoints)} API endpoints in JS:")
            for ep in sorted(found_endpoints)[:20]:
                print(f"     {ep}")

    def scrape_deals(self, country="eg", max_pages=3, min_discount=40):
        """Scrape deals from Safqa.

        Args:
            country: 'eg', 'sa', or 'ae'
            max_pages: Max pages to scrape
            min_discount: Minimum discount percentage

        Returns:
            List of deal dicts
        """
        if not self.api_base:
            if not self.discover_api():
                return []

        all_deals = []

        for page in range(1, max_pages + 1):
            print(f"[SAFQA] Fetching page {page}...")

            # Try multiple endpoint patterns
            endpoints = [
                f"{self.api_base}/api/deals?country={country}&page={page}",
                f"{self.api_base}/api/products?country={country}&page={page}&deals=true",
                f"{self.api_base}/api/v1/deals?country={country}&page={page}",
                f"{self.base_url}/api/deals?country={country}&page={page}",
            ]

            page_deals = []
            for url in endpoints:
                result = self._fetch(url)
                if result and "_html" not in result:
                    page_deals = self._parse_response(result)
                    if page_deals:
                        print(f"  ✅ Found {len(page_deals)} deals via {url[:80]}")
                        break

            if not page_deals:
                print(f"  ⚠ No deals on page {page}, stopping")
                break

            # Filter by discount
            for deal in page_deals:
                if deal.get("discount_pct", 0) >= min_discount:
                    all_deals.append(deal)

            time.sleep(1)  # Be polite

        print(f"[SAFQA] Total deals found: {len(all_deals)}")
        return all_deals

    def verify_price(self, asin, country="eg"):
        """Verify a product's price history on Safqa.

        Args:
            asin: Product ASIN
            country: Country code

        Returns:
            Dict with price info or None
        """
        if not self.api_base:
            self.discover_api()

        endpoints = [
            f"{self.api_base}/api/products/{asin}?country={country}",
            f"{self.api_base}/api/product/{asin}?country={country}",
            f"{self.base_url}/api/products/{asin}?country={country}",
        ]

        for url in endpoints:
            result = self._fetch(url)
            if result and "_html" not in result:
                return self._parse_product(result)

        return None

    def _parse_response(self, data):
        """Parse API response into deal list."""
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ["deals", "products", "items", "data", "results"]:
                if key in data:
                    items = data[key]
                    break
            else:
                items = []
        else:
            items = []

        deals = []
        for item in items:
            if not isinstance(item, dict):
                continue

            deal = {
                "title": item.get("title") or item.get("name", ""),
                "price": self._to_float(item.get("price")),
                "old_price": self._to_float(item.get("old_price") or item.get("original_price")),
                "discount_pct": item.get("discount", 0) or item.get("discount_percentage", 0),
                "source": "safqa",
                "platform": item.get("platform") or item.get("store", ""),
                "url": item.get("url") or item.get("link", ""),
                "image": item.get("image") or item.get("image_url", ""),
                "asin": item.get("asin") or item.get("sku") or item.get("id", ""),
                "country": item.get("country", "eg"),
                "scraped_at": datetime.utcnow().isoformat(),
            }

            # Calculate discount
            if deal["discount_pct"] == 0 and deal["old_price"] > 0 and deal["price"] > 0:
                deal["discount_pct"] = round((1 - deal["price"] / deal["old_price"]) * 100, 1)

            deals.append(deal)

        return deals

    def _parse_product(self, data):
        """Parse single product response."""
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return None

        return {
            "title": data.get("title") or data.get("name", ""),
            "current_price": self._to_float(data.get("price")),
            "old_price": self._to_float(data.get("old_price")),
            "discount_pct": data.get("discount", 0),
            "platform": data.get("platform") or data.get("store", ""),
            "url": data.get("url", ""),
            "image": data.get("image", ""),
            "asin": data.get("asin") or data.get("sku", ""),
            "in_stock": data.get("in_stock", True),
            "scraped_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _to_float(val):
        """Convert price to float."""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("EGP", "").replace("SAR", "").replace("AED", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0


def main():
    """Run Safqa scraper test."""
    print("=" * 60)
    print("SAFQA SCRAPER — PROXIED VERSION")
    print("=" * 60)

    scraper = SafqaScraper()

    # Discover API
    if not scraper.discover_api():
        print("\n❌ Cannot access Safqa. Check SCRAPEDO_TOKEN.")
        return

    # Scrape deals
    deals = scraper.scrape_deals(country="eg", max_pages=2, min_discount=40)

    # Show results
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(deals)} deals with 40%+ discount")
    print(f"{'='*60}")

    for d in deals[:10]:
        print(f"\n  📦 {d['title'][:70]}")
        print(f"     💰 EGP {d['price']:,.0f} ~~{d['old_price']:,.0f}~~ ({d['discount_pct']}% off)")
        print(f"     🔗 {d['url'][:60]}")


if __name__ == "__main__":
    main()
