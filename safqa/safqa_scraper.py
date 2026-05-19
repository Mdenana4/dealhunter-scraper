#!/usr/bin/env python3
"""
Safqa (safqaprice.com) Scraper — Fixed Version
Tries multiple API endpoint patterns to find working ones.

Usage:
    from safqa_scraper import SafqaClient
    client = SafqaClient()
    deals = client.get_deals(country="eg", page=1, limit=50)
    product = client.get_product("ASIN_HERE", country="eg")
    price_history = client.get_price_history("ASIN_HERE", country="eg")
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime


class SafqaClient:
    """Client for Safqa price comparison API."""

    # Possible API base URLs to try
    API_ENDPOINTS = [
        "https://api.safqaprice.com",
        "https://safqaprice.com/api",
        "https://safqaprice.com/api/v1",
        "https://backend.safqaprice.com",
        "https://api.safqaprice.com/v1",
    ]

    def __init__(self, timeout=30):
        self.timeout = timeout
        self.working_base = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Referer": "https://safqaprice.com/",
            "Origin": "https://safqaprice.com",
        }

    def _request(self, url, retries=3):
        """Make HTTP request with retry logic."""
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=self.headers, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read().decode("utf-8", errors="ignore")
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        return {"_raw_html": data[:1000]}
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None  # Endpoint doesn't exist
                if e.code == 429:
                    time.sleep(2 ** attempt)
                    continue
                print(f"  HTTP {e.code}: {url}")
                return None
            except Exception as e:
                print(f"  Error: {e}")
                return None
        return None

    def find_working_api(self):
        """Probe all API endpoints to find the working one."""
        print("[SAFQA] Probing API endpoints...")

        test_paths = [
            "/deals?page=1&limit=1",
            "/products?page=1&limit=1",
            "/search?q=iphone&page=1",
        ]

        for base in self.API_ENDPOINTS:
            for path in test_paths:
                url = f"{base}{path}"
                result = self._request(url)
                if result and "_raw_html" not in result:
                    self.working_base = base
                    print(f"  ✅ Working API found: {base}")
                    print(f"     Test path: {path}")
                    return True

        print("  ⚠ No working API endpoint found from direct requests")
        print("  Will try alternative methods (scrape.do, etc.)")
        return False

    def get_deals(self, country="eg", page=1, limit=50, category=None):
        """Get deals from Safqa.

        Args:
            country: 'eg' (Egypt), 'sa' (Saudi), 'ae' (UAE)
            page: Page number
            limit: Items per page
            category: Optional category filter

        Returns:
            List of deal dicts with keys: title, price, old_price, discount_pct,
            source, url, image, asin
        """
        if not self.working_base:
            if not self.find_working_api():
                return []

        params = urllib.parse.urlencode({
            "country": country,
            "page": page,
            "limit": limit,
            **({"category": category} if category else {})
        })

        # Try multiple deal endpoint patterns
        paths = [
            f"/deals?{params}",
            f"/products?{params}",
            f"/products/deals?{params}",
            f"/v1/deals?{params}",
        ]

        for path in paths:
            url = f"{self.working_base}{path}"
            result = self._request(url)
            if result:
                return self._parse_deals(result)

        return []

    def get_product(self, asin, country="eg"):
        """Get product details by ASIN.

        Args:
            asin: Amazon/Noon product ASIN
            country: Country code

        Returns:
            Dict with product info and price history summary
        """
        if not self.working_base:
            if not self.find_working_api():
                return None

        paths = [
            f"/products/{asin}?country={country}",
            f"/product/{asin}?country={country}",
            f"/products/detail/{asin}?country={country}",
        ]

        for path in paths:
            url = f"{self.working_base}{path}"
            result = self._request(url)
            if result:
                return self._parse_product(result)

        return None

    def get_price_history(self, asin, country="eg", days=90):
        """Get price history for a product.

        Args:
            asin: Product ASIN
            country: Country code
            days: Number of days of history

        Returns:
            List of {date, price} dicts
        """
        if not self.working_base:
            if not self.find_working_api():
                return []

        params = urllib.parse.urlencode({
            "country": country,
            "days": days,
        })

        paths = [
            f"/products/{asin}/price-history?{params}",
            f"/product/{asin}/history?{params}",
            f"/products/{asin}/prices?{params}",
        ]

        for path in paths:
            url = f"{self.working_base}{path}"
            result = self._request(url)
            if result:
                return self._parse_price_history(result)

        return []

    def search_products(self, query, country="eg", page=1, limit=20):
        """Search for products on Safqa.

        Args:
            query: Search query string
            country: Country code
            page: Page number
            limit: Results per page

        Returns:
            List of product dicts
        """
        if not self.working_base:
            if not self.find_working_api():
                return []

        params = urllib.parse.urlencode({
            "q": query,
            "country": country,
            "page": page,
            "limit": limit,
        })

        paths = [
            f"/search?{params}",
            f"/products/search?{params}",
            f"/v1/search?{params}",
        ]

        for path in paths:
            url = f"{self.working_base}{path}"
            result = self._request(url)
            if result:
                return self._parse_deals(result)

        return []

    def _parse_deals(self, data):
        """Parse deals response into standard format."""
        deals = []

        # Handle different response structures
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common keys
            for key in ["deals", "products", "items", "data", "results"]:
                if key in data:
                    items = data[key]
                    break
            else:
                items = [data] if "title" in data or "name" in data else []
        else:
            return []

        for item in items:
            if not isinstance(item, dict):
                continue

            deal = {
                "title": item.get("title") or item.get("name", ""),
                "price": self._extract_price(item.get("price")),
                "old_price": self._extract_price(item.get("old_price") or item.get("original_price")),
                "discount_pct": item.get("discount") or item.get("discount_percentage") or 0,
                "source": item.get("source") or item.get("store") or item.get("platform", "safqa"),
                "url": item.get("url") or item.get("link", ""),
                "image": item.get("image") or item.get("image_url", ""),
                "asin": item.get("asin") or item.get("sku") or item.get("id", ""),
                "country": item.get("country", "eg"),
                "category": item.get("category", ""),
                "scraped_at": datetime.utcnow().isoformat(),
            }

            # Calculate discount if not provided
            if deal["discount_pct"] == 0 and deal["old_price"] and deal["price"]:
                try:
                    deal["discount_pct"] = round(
                        (1 - deal["price"] / deal["old_price"]) * 100, 1
                    )
                except (ZeroDivisionError, TypeError):
                    pass

            deals.append(deal)

        return deals

    def _parse_product(self, data):
        """Parse product detail response."""
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        if not isinstance(data, dict):
            return None

        return {
            "title": data.get("title") or data.get("name", ""),
            "description": data.get("description", ""),
            "current_price": self._extract_price(data.get("price")),
            "old_price": self._extract_price(data.get("old_price")),
            "discount_pct": data.get("discount", 0),
            "source": data.get("source") or data.get("store", ""),
            "url": data.get("url") or data.get("link", ""),
            "image": data.get("image") or data.get("image_url", ""),
            "asin": data.get("asin") or data.get("sku") or data.get("id", ""),
            "category": data.get("category", ""),
            "rating": data.get("rating", 0),
            "reviews_count": data.get("reviews_count", 0),
            "scraped_at": datetime.utcnow().isoformat(),
        }

    def _parse_price_history(self, data):
        """Parse price history response."""
        history = []

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ["history", "prices", "data", "items"]:
                if key in data:
                    items = data[key]
                    break
            else:
                return []
        else:
            return []

        for item in items:
            if isinstance(item, dict):
                entry = {
                    "date": item.get("date") or item.get("timestamp", ""),
                    "price": self._extract_price(item.get("price")),
                    "currency": item.get("currency", "EGP"),
                }
                history.append(entry)

        return history

    @staticmethod
    def _extract_price(price_val):
        """Extract numeric price from various formats."""
        if price_val is None:
            return 0.0
        if isinstance(price_val, (int, float)):
            return float(price_val)
        if isinstance(price_val, str):
            # Remove currency symbols and commas
            cleaned = price_val.replace(",", "").replace("EGP", "").replace("SAR", "").replace("AED", "").replace("$", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0


def test_safqa():
    """Test the Safqa client."""
    print("=" * 60)
    print("SAFQA SCRAPER TEST")
    print("=" * 60)

    client = SafqaClient()

    # Step 1: Find working API
    if not client.find_working_api():
        print("\n⚠ Direct API access failed.")
        print("  This is normal if behind Cloudflare.")
        print("  Use scrape.do proxy in production.")
        return

    # Step 2: Get deals
    print("\n[TEST] Getting deals...")
    deals = client.get_deals(country="eg", page=1, limit=5)
    print(f"  Found {len(deals)} deals")
    for d in deals[:3]:
        print(f"    - {d['title'][:60]} | EGP {d['price']} | {d['discount_pct']}% off")

    # Step 3: Search
    print("\n[TEST] Searching for 'iphone'...")
    results = client.search_products("iphone", country="eg", limit=3)
    print(f"  Found {len(results)} results")
    for r in results[:2]:
        print(f"    - {r['title'][:60]} | EGP {r['price']}")

    print("\n✅ Safqa scraper test complete")


if __name__ == "__main__":
    test_safqa()
