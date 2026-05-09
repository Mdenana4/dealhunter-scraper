#!/usr/bin/env python3
"""
Safqa Browser — Headless Chromium Price Checker v8 SEARCH-FIRST
===============================================================
Key fix: Actually USE the product title for search-first approach.

Changes from v7:
1. SEARCH-FIRST: If title provided, try /search?q={title} before direct /product/{asin}
2. Timeout: 30s → 45s page load, 8s → 12s React render wait
3. Search result click-through: On search page, click first product link
4. More DOM selectors: class*=price, Tailwind .text-green-600, .text-primary
5. Full-page EGP text scan as final fallback
6. Better debug logging at every step
7. networkidle timeout handling — no longer hard-fails on slow networks

API (unchanged — fake_checker.py compatible):
    from safqa_browser import check_safqa, shutdown_browser
    result = check_safqa(asin="B0DHTYW7P8", title="Apple iPhone 16")
    # Returns: {"found", "lowest_price", "highest_price", "price_samples", "coupon_codes"}
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("safqa_browser")

# ─── Lazy Import ───
_playwright = None
_sync_playwright = None


def _ensure_imports() -> None:
    """Lazy-load Playwright to avoid import cost when Safqa is not checked."""
    global _sync_playwright
    if _sync_playwright is None:
        try:
            from playwright.sync_api import sync_playwright
            _sync_playwright = sync_playwright
        except ImportError as exc:
            raise ImportError(
                "Playwright not installed. Run:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            ) from exc


@dataclass
class SafqaResult:
    """Structured result from a Safqa price check."""
    found: bool = False
    lowest_price: float = 0.0
    highest_price: float = 0.0
    price_samples: list[float] = field(default_factory=list)
    coupon_codes: list[str] = field(default_factory=list)
    source_url: str = ""
    method: str = ""  # Which extraction method succeeded

    def to_legacy_dict(self) -> dict:
        """Convert to the dict format expected by fake_checker.py."""
        return {
            "found": self.found,
            "lowest_price": self.lowest_price,
            "highest_price": self.highest_price,
            "price_samples": self.price_samples,
            "coupon_codes": self.coupon_codes,
        }


class SafqaBrowser:
    """
    Headless Chromium browser for scraping Safqa.

    Lifecycle:
        browser = SafqaBrowser()
        browser.start()      # Launch Chromium (~3s one-time cost)
        browser.check_product("B08N5WRWNW", title="Product Name")  # Fast
        browser.stop()       # Cleanup

    v8: Search-first — if title is provided, searches by title before trying ASIN URL.
    """

    SAFQA_BASE = "https://joinsafqa.com"

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 45_000,       # v8: was 30_000
        render_wait_ms: int = 12_000,   # v8: was 8_000
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.render_wait_ms = render_wait_ms

        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._started = False

    # ── Lifecycle ──

    def start(self) -> None:
        """Launch Chromium browser. Call once at scraper startup."""
        if self._started:
            return

        _ensure_imports()
        print("    [SAFQA-BROWSER] Starting Chromium...")
        t0 = time.time()

        self._pw = _sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1920,1080",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            java_script_enabled=True,
        )
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)
        self._page = self._context.new_page()
        self._started = True
        print(f"    [SAFQA-BROWSER] Chromium ready in {time.time()-t0:.1f}s")

    def stop(self) -> None:
        """Close browser. Call at scraper shutdown."""
        print("    [SAFQA-BROWSER] Stopping Chromium...")
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            logger.warning(f"[SAFQA-BROWSER] Cleanup error: {exc}")
        finally:
            self._started = False
            self._page = None

    # ── Public API ──

    def check_product(
        self,
        asin: Optional[str] = None,
        product_url: Optional[str] = None,
        title: str = "",
    ) -> SafqaResult:
        print(f"    [SAFQA-BROWSER] check_product() called, asin={asin}, _started={self._started}")

        if not self._started:
            self.start()

        result = SafqaResult()
        if not asin:
            return result

        # ─── v8: SEARCH-FIRST STRATEGY ───
        # If we have a title, search by title FIRST before trying direct ASIN URLs
        if title and title.strip():
            search_result = self._try_search_first(asin, title.strip())
            if search_result.found:
                return search_result
            # If search found the page but no price, fall through to direct URLs

        # ─── FALLBACK: Direct product URLs ───
        urls = self._build_urls(asin, product_url)
        logger.info(f"[SAFQA-BROWSER] Checking ASIN {asin} — {len(urls)} direct URLs")

        for url in urls:
            try:
                result.source_url = url
                self._navigate(url)

                prices = self._run_extractors(asin)
                if prices:
                    result.found = True
                    result.lowest_price = min(prices)
                    result.highest_price = max(prices)
                    result.price_samples = prices
                    result.method = "direct-url"
                    logger.info(
                        f"[SAFQA-BROWSER] ASIN {asin} via direct URL: "
                        f"low={result.lowest_price:,.0f}"
                    )
                    return result

            except Exception as exc:
                print(f"    [SAFQA-BROWSER] URL failed {url[:50]}: {exc}")
                continue

        print(f"    [SAFQA-BROWSER] ASIN {asin}: not found on Safqa")
        return result

    # ── v8: Search-First Implementation ──

    def _try_search_first(self, asin: str, title: str) -> SafqaResult:
        """
        v8: Search by product title first.
        1. Go to /search?q={title}
        2. Wait for results
        3. Try to find product card matching our ASIN
        4. Click first result if no ASIN match
        5. Extract prices from resulting page
        """
        result = SafqaResult()
        # Truncate very long titles
        search_title = title[:70]
        encoded = urllib.parse.quote(search_title)

        search_urls = [
            f"{self.SAFQA_BASE}/ar/search?q={encoded}",
            f"{self.SAFQA_BASE}/en/search?q={encoded}",
            f"{self.SAFQA_BASE}/search?q={encoded}",
        ]

        for search_url in search_urls:
            try:
                print(f"      [SAFQA-BROWSER] Search-first: {search_url[:80]}...")
                self._navigate(search_url)

                # Strategy A: Look for our ASIN in search results
                try:
                    asin_link = self._page.query_selector(f'a[href*="{asin}"]')
                    if asin_link:
                        print(f"      [SAFQA-BROWSER] Found ASIN {asin} in search results, clicking...")
                        asin_link.click()
                        self._page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                        self._page.wait_for_timeout(self.render_wait_ms)

                        prices = self._run_extractors(asin)
                        if prices:
                            result.found = True
                            result.lowest_price = min(prices)
                            result.highest_price = max(prices)
                            result.price_samples = prices
                            result.source_url = self._page.url
                            result.method = "search-asin-click"
                            print(f"      [SAFQA-BROWSER] Price found after ASIN click: {result.lowest_price:,.0f} EGP")
                            return result
                except Exception as e:
                    print(f"      [SAFQA-BROWSER] ASIN click failed: {e}")

                # Strategy B: Extract price directly from search results page
                prices = self._run_extractors(asin)
                if prices:
                    result.found = True
                    result.lowest_price = min(prices)
                    result.highest_price = max(prices)
                    result.price_samples = prices
                    result.source_url = search_url
                    result.method = "search-page-direct"
                    print(f"      [SAFQA-BROWSER] Price found on search page: {result.lowest_price:,.0f} EGP")
                    return result

                # Strategy C: Click first product result, then extract
                try:
                    first_link = self._page.query_selector(
                        "a[href*='/product/'], a[href*='/products/'], a[href*='/p/']"
                    )
                    if first_link:
                        href = first_link.get_attribute("href")
                        if href:
                            click_url = href if href.startswith("http") else f"{self.SAFQA_BASE}{href}"
                            print(f"      [SAFQA-BROWSER] Clicking first result: {click_url[:60]}...")
                            self._navigate(click_url)

                            prices = self._run_extractors(asin)
                            if prices:
                                result.found = True
                                result.lowest_price = min(prices)
                                result.highest_price = max(prices)
                                result.price_samples = prices
                                result.source_url = click_url
                                result.method = "search-first-result"
                                print(f"      [SAFQA-BROWSER] Price from first result: {result.lowest_price:,.0f} EGP")
                                return result
                except Exception as e:
                    print(f"      [SAFQA-BROWSER] First result click failed: {e}")

                print(f"      [SAFQA-BROWSER] Search URL {search_url[:50]}... no prices found")

            except Exception as e:
                print(f"      [SAFQA-BROWSER] Search approach failed: {type(e).__name__}: {str(e)[:80]}")
                continue

        print(f"      [SAFQA-BROWSER] Search-first found nothing, falling back to direct URLs")
        return result

    # ── Internal ──

    def _build_urls(self, asin: str, product_url: Optional[str]) -> list[str]:
        """Build list of URLs to try."""
        urls = []
        if product_url and "joinsafqa.com" in product_url:
            urls.append(product_url)
        # v8: locale-specific product URLs first
        urls.extend([
            f"{self.SAFQA_BASE}/en/product/{asin}",
            f"{self.SAFQA_BASE}/ar/product/{asin}",
            f"{self.SAFQA_BASE}/product/{asin}",
            f"{self.SAFQA_BASE}/p/{asin}",
            f"{self.SAFQA_BASE}/en/p/{asin}",
            f"{self.SAFQA_BASE}/ar/p/{asin}",
        ])
        return urls

    def _navigate(self, url: str) -> None:
        """Navigate to URL and wait for React to render."""
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        # v8: networkidle is best effort — don't hard-fail if it times out
        try:
            self._page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass  # domcontentloaded is enough; React may still be rendering
        # v8: Longer wait for React to render price elements
        self._page.wait_for_timeout(self.render_wait_ms)
        # DEBUG
        try:
            t = self._page.title()
            c = self._page.content()
            has_egp = "EGP" in c
            has_price = "price" in c.lower()
            print(f"      [SAFQA-BROWSER] Page: title={t[:50]} has_EGP={has_egp} has_price={has_price} url={self._page.url[:60]}")
        except Exception as e:
            print(f"      [SAFQA-BROWSER] Page info error: {e}")

    def _run_extractors(self, asin: str) -> Optional[list[float]]:
        """Run all price extraction methods, return first successful list."""
        extractors = [
            ("json-ld", self._extract_json_ld),
            ("next-data", self._extract_next_data),
            ("initial-state", self._extract_initial_state),
            ("dom-price", self._extract_dom_price),
            ("dom-tailwind", self._extract_tailwind_price),
            ("text-scan", self._extract_text_scan),
        ]

        all_prices = []
        for method_name, extractor in extractors:
            try:
                prices = extractor()
                if prices:
                    print(f"      [SAFQA-BROWSER] Extracted via {method_name}: {prices}")
                    all_prices.extend(prices)
            except Exception as e:
                logger.debug(f"Extractor {method_name} failed: {e}")

        return all_prices if all_prices else None

    # ── Extraction Methods ──

    def _extract_json_ld(self) -> Optional[list[float]]:
        """Extract prices from JSON-LD structured data."""
        scripts = self._page.query_selector_all('script[type="application/ld+json"]')
        prices = []
        for script in scripts:
            try:
                data = json.loads(script.inner_text())
                if isinstance(data, dict) and data.get("@type") == "Product":
                    offers = data.get("offers", {})
                    if isinstance(offers, dict):
                        p = self._to_float(offers.get("price"))
                        if p > 0:
                            prices.append(p)
                    p = self._to_float(data.get("price"))
                    if p > 0:
                        prices.append(p)
                # Also handle @graph arrays
                graph = data.get("@graph", []) if isinstance(data, dict) else []
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            p = self._to_float(offers.get("price"))
                            if p > 0:
                                prices.append(p)
            except (json.JSONDecodeError, AttributeError):
                continue
        return prices if prices else None

    def _extract_next_data(self) -> Optional[list[float]]:
        """Extract prices from Next.js __NEXT_DATA__ script."""
        el = self._page.query_selector("script#__NEXT_DATA__")
        if not el:
            return None
        try:
            data = json.loads(el.inner_text())
            return self._find_prices_recursive(data)
        except (json.JSONDecodeError, AttributeError):
            return None

    def _extract_initial_state(self) -> Optional[list[float]]:
        """Extract prices from window.__INITIAL_STATE__ or __DATA__."""
        state_json = self._page.evaluate("""
            () => {
                if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                if (window.__DATA__) return JSON.stringify(window.__DATA__);
                if (window.__PRELOADED_STATE__) return JSON.stringify(window.__PRELOADED_STATE__);
                if (window.__APP_DATA__) return JSON.stringify(window.__APP_DATA__);
                return null;
            }
        """)
        if not state_json:
            return None
        try:
            data = json.loads(state_json)
            return self._find_prices_recursive(data)
        except (json.JSONDecodeError, AttributeError):
            return None

    def _extract_dom_price(self) -> Optional[list[float]]:
        """Extract prices from rendered DOM elements — v8: expanded selectors."""
        selectors = [
            "[data-testid='product-price']",
            "[data-testid='current-price']",
            "[data-testid='price']",
            ".product-price .current",
            ".price-current",
            ".sale-price",
            ".current-price",
            ".product-price",
            "[class*='price']",
            "[class*='Price']",
        ]
        prices = []
        for sel in selectors:
            try:
                els = self._page.query_selector_all(sel)
                for el in els:
                    text = el.inner_text().strip()
                    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                    if match:
                        p = float(match.group())
                        if 10 <= p <= 500_000:
                            prices.append(p)
            except Exception:
                continue
        return prices if prices else None

    def _extract_tailwind_price(self) -> Optional[list[float]]:
        """v8: Extract from common Tailwind CSS price classes."""
        selectors = [
            ".text-green-600",
            ".text-green-500",
            ".text-primary",
            ".text-blue-600",
            ".font-bold.text-lg",
            ".font-bold.text-xl",
        ]
        prices = []
        for sel in selectors:
            try:
                els = self._page.query_selector_all(sel)
                for el in els:
                    text = el.inner_text().strip()
                    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                    if match:
                        p = float(match.group())
                        if 10 <= p <= 500_000:
                            prices.append(p)
            except Exception:
                continue
        return prices if prices else None

    def _extract_text_scan(self) -> Optional[list[float]]:
        """v8: Full-page text scan for EGP price patterns — final fallback."""
        try:
            text = self._page.content()
        except Exception:
            return None

        # Pattern: "1,234 EGP" or "EGP 1,234" or "ج.م ١٢٣٤"
        price_matches = re.findall(
            r'([\d,]+\.?\d*)\s*(?:EGP|ج\.م|جنيه)|(?:EGP|ج\.م|جنيه)\s*([\d,]+\.?\d*)',
            text
        )
        prices = []
        for m in price_matches:
            num_str = (m[0] or m[1]).replace(",", "")
            try:
                p = float(num_str)
                if 10 <= p <= 500_000:
                    prices.append(p)
            except ValueError:
                continue

        # Also look for standalone numbers near price indicators
        if not prices:
            matches = re.findall(r'[\d,]+\.?\d*', text)
            for m in matches:
                try:
                    p = float(m.replace(",", ""))
                    if 50 <= p <= 500_000:
                        prices.append(p)
                except ValueError:
                    continue

        return prices if prices else None

    # ── Helpers ──

    @staticmethod
    def _to_float(val) -> float:
        """Safely convert a value to float."""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("EGP", "").replace("SAR", "").replace("AED", "").replace("ج.م", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    @classmethod
    def _find_prices_recursive(cls, obj, depth: int = 0) -> Optional[list[float]]:
        """Recursively find all numeric prices in a nested dict/list."""
        if depth > 12 or obj is None:
            return None
        prices = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if kl in {"price", "sale_price", "current_price", "offer_price", "discounted_price", "low_price", "min_price"}:
                    p = cls._to_float(v)
                    if p > 0:
                        prices.append(p)
                elif kl in {"prices", "price_list", "offers"} and isinstance(v, list):
                    for item in v:
                        if isinstance(item, (int, float)):
                            prices.append(float(item))
                        elif isinstance(item, dict):
                            for pk, pv in item.items():
                                if "price" in pk.lower():
                                    p = cls._to_float(pv)
                                    if p > 0:
                                        prices.append(p)
                elif isinstance(v, (dict, list)):
                    found = cls._find_prices_recursive(v, depth + 1)
                    if found:
                        prices.extend(found)
        elif isinstance(obj, list):
            for item in obj:
                found = cls._find_prices_recursive(item, depth + 1)
                if found:
                    prices.extend(found)
        return prices if prices else None


# ─── Legacy API (drop-in for fake_checker.py) ───

_browser_instance: Optional[SafqaBrowser] = None


def check_safqa(asin: Optional[str] = None, product_url: Optional[str] = None, title: str = "") -> dict:
    """
    Legacy-compatible wrapper for fake_checker.py.
    v8: Now actually uses the title parameter for search-first!
    """
    global _browser_instance

    try:
        if _browser_instance is None or not _browser_instance._started:
            _browser_instance = SafqaBrowser()
            _browser_instance.start()

        result = _browser_instance.check_product(asin=asin, product_url=product_url, title=title)
        return result.to_legacy_dict()

    except ImportError as exc:
        print(f"    [SAFQA-BROWSER] Playwright not installed: {exc}")
        print("    Fix: apt-get install -y libnss3 libatk1.0 libxss1 && pip install playwright && playwright install chromium")
        return {"found": False, "lowest_price": 0, "highest_price": 0, "price_samples": [], "coupon_codes": []}
    except Exception as exc:
        print(f"    [SAFQA-BROWSER] Error: {exc}")
        return {"found": False, "lowest_price": 0, "highest_price": 0, "price_samples": [], "coupon_codes": []}


def shutdown_browser() -> None:
    """Call this when the scraper process exits."""
    global _browser_instance
    if _browser_instance:
        _browser_instance.stop()
        _browser_instance = None


# ─── Self-test ───
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=" * 60)
    print("SAFQA BROWSER v8 SEARCH-FIRST — Self Test")
    print("=" * 60)

    # Test cases: (asin, title, should_find)
    test_cases = [
        ("B0DHTYW7P8", "Apple iPhone 16", None),       # Electronics — should find
        ("B0CHX1W1XY", "Samsung Galaxy S24", None),     # Electronics — should find
        ("0761562850", "Iphone Apps Book Vol 1", False), # Book — should NOT find
    ]

    browser = SafqaBrowser()
    try:
        browser.start()
        for asin, title, expected in test_cases:
            print(f"\n{'='*50}")
            print(f"Test: ASIN={asin} | Title={title[:40]}")
            print(f"Expected: {'SHOULD FIND' if expected is None else 'NOT FOUND'}")
            print("=" * 50)
            result = browser.check_product(asin=asin, title=title)
            status = "FOUND" if result.found else "NOT FOUND"
            print(f"Result: {status}")
            if result.found:
                print(f"  Price: EGP {result.lowest_price:,.0f} ~ {result.highest_price:,.0f}")
                print(f"  Method: {result.method}")
                print(f"  URL: {result.source_url[:60]}...")
    finally:
        browser.stop()

    print("\n" + "=" * 60)
    print("Self-test complete")
    print("=" * 60)
