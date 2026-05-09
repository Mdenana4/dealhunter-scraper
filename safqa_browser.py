#!/usr/bin/env python3
"""
Safqa Browser — Headless Chromium Price Checker
================================================
Production-grade Playwright integration for Safqa price verification.

Architecture Decision:
    scrape.do and ScraperAPI are both dead (502/401). The ONLY way to
    access Safqa's React SPA is to render it in a real browser. This
    module provides that capability with zero external proxy dependencies.

    Browser is initialized ONCE per scraper lifecycle and reused across
    all Safqa checks. This avoids the ~3s Chromium launch overhead per
    product.

Usage:
    from safqa_browser import SafqaBrowser

    # Initialize once at scraper startup
    browser = SafqaBrowser()
    browser.start()

    # Check multiple products (browser reused)
    for asin in asin_list:
        result = browser.check_product(asin)
        print(result)

    # Shutdown at scraper exit
    browser.stop()

Railway Setup:
    apt-get update && apt-get install -y libnss3 libatk-bridge2.0-0 libxss1 libgtk-3-0
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("safqa_browser")

# ─── Lazy Import ───
# Playwright is heavy; only import when this module is actually used.
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
        browser.check_product("B08N5WRWNW")  # Fast, browser already open
        browser.check_product("B08N5M7S6K")  # Fast, same browser
        ...
        browser.stop()       # Cleanup

    Thread-safety:
        This class is NOT thread-safe. Use from a single thread
        (the scraper's main thread is fine).
    """

    SAFQA_BASE = "https://joinsafqa.com"

    # URL patterns to try, in order of likelihood
    _URL_PATTERNS = [
        "{base}/en/product/{asin}",
        "{base}/ar/product/{asin}",
        "{base}/product/{asin}",
        "{base}/search?q={asin}",
        "{base}/en/search?q={asin}",
        "{base}/p/{asin}",
    ]

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 30000,
        render_wait_ms: int = 8000,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.render_wait_ms = render_wait_ms

        # Playwright objects (initialized in start())
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
        # Inject anti-detection script before any navigation
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

        # DNS pre-check: skip if joinsafqa.com is blocked from this network
        import socket
        try:
            socket.gethostbyname("joinsafqa.com")
        except socket.gaierror:
            print(f"    [SAFQA-BROWSER] ⚠️  joinsafqa.com DNS blocked from this network — skipping")
            print(f"    [SAFQA-BROWSER]    (Use Egypt-based VPS or residential proxy)")
            return SafqaResult()
        """
        Check Safqa for price data on a product.

        Tries multiple URL patterns and extraction methods until
        one succeeds. Returns SafqaResult with found=True if data
        was extracted.
        """
        if not self._started:
            self.start()

        result = SafqaResult()
        if not asin:
            return result

        urls = self._build_urls(asin, product_url)
        logger.info(f"[SAFQA-BROWSER] Checking ASIN {asin} — {len(urls)} URLs")

        for url in urls:
            try:
                result.source_url = url
                self._navigate(url)

                # Try extraction methods in order of reliability
                extractors = [
                    ("json-ld", self._extract_json_ld),
                    ("next-data", self._extract_next_data),
                    ("initial-state", self._extract_initial_state),
                    ("dom-price", self._extract_dom_price),
                ]

                for method_name, extractor in extractors:
                    prices = extractor()
                    if prices:
                        result.found = True
                        result.lowest_price = min(prices)
                        result.highest_price = max(prices)
                        result.price_samples = prices
                        result.method = method_name
                        logger.info(
                            f"[SAFQA-BROWSER] ✅ ASIN {asin} via {method_name}: "
                            f"low={result.lowest_price:,.0f} high={result.highest_price:,.0f}"
                        )
                        return result

                # If search page, try clicking first result
                if "/search" in url:
                    product_url = self._click_first_search_result()
                    if product_url:
                        self._navigate(product_url)
                        # Re-run all extractors on product page
                        for method_name, extractor in extractors:
                            prices = extractor()
                            if prices:
                                result.found = True
                                result.lowest_price = min(prices)
                                result.highest_price = max(prices)
                                result.price_samples = prices
                                result.method = method_name
                                logger.info(
                                    f"[SAFQA-BROWSER] ✅ ASIN {asin} via {method_name} (from search): "
                                    f"low={result.lowest_price:,.0f}"
                                )
                                return result

            except Exception as exc:
                print(f"    [SAFQA-BROWSER] URL failed {url[:50]}: {exc}")
                continue

        print(f"    [SAFQA-BROWSER] ❌ ASIN {asin}: not found on Safqa")
        return result

    # ── Internal ──

    def _build_urls(self, asin: str, product_url: Optional[str]) -> list[str]:
        """Build list of URLs to try."""
        urls = []
        if product_url and "joinsafqa.com" in product_url:
            urls.append(product_url)
        for pattern in self._URL_PATTERNS:
            urls.append(pattern.format(base=self.SAFQA_BASE, asin=asin))
        return urls

    def _navigate(self, url: str) -> None:
        """Navigate to URL and wait for React to render."""
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        # Wait for network to settle (React loads data)
        self._page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        # Extra wait for React to render price elements
        self._page.wait_for_timeout(self.render_wait_ms)
        # DEBUG
        try:
            t = self._page.title()
            c = self._page.content()
            print(f"      [SAFQA-BROWSER] Page: title={t[:40]} has_EGP={'EGP' in c} has_price={'price' in c.lower()}")
        except Exception as e:
            print(f"      [SAFQA-BROWSER] Page info error: {e}")

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
                    # Also check direct price field
                    p = self._to_float(data.get("price"))
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
        """Extract prices from rendered DOM elements."""
        selectors = [
            "[data-testid='product-price']",
            "[data-testid='current-price']",
            ".product-price .current",
            ".price-current",
            ".sale-price",
            "span:has-text('EGP')",
            "div:has-text('EGP')",
            "span:has-text('ج.م')",
        ]
        prices = []
        for sel in selectors:
            try:
                el = self._page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                    if match:
                        p = float(match.group())
                        if p > 0:
                            prices.append(p)
            except Exception:
                continue
        return prices if prices else None

    def _click_first_search_result(self) -> Optional[str]:
        """On search page, click first product link and return its URL."""
        try:
            link = self._page.query_selector("a[href*='/product/'], a[href*='/products/'], a[href*='/p/']")
            if link:
                href = link.get_attribute("href")
                if href:
                    if href.startswith("http"):
                        return href
                    return f"{self.SAFQA_BASE}{href}"
        except Exception:
            pass
        return None

    # ── Helpers ──

    @staticmethod
    def _to_float(val) -> float:
        """Safely convert a value to float."""
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

    @classmethod
    def _find_prices_recursive(cls, obj, depth: int = 0) -> Optional[list[float]]:
        """Recursively find all numeric prices in a nested dict/list."""
        if depth > 12 or obj is None:
            return None
        prices = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if kl in {"price", "sale_price", "current_price", "offer_price", "discounted_price"}:
                    p = cls._to_float(v)
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

    Usage: Replace the old check_safqa() call with this function.
    The browser is lazily initialized on first call and kept alive.
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
    print("SAFQA BROWSER — Self Test")
    print("=" * 60)

    test_asins = ["B08N5WRWNW", "B0CHX1W1XY", "B0DHTYW7P8"]

    browser = SafqaBrowser()
    try:
        browser.start()
        for asin in test_asins:
            result = browser.check_product(asin=asin, title="Test")
            status = "✅ FOUND" if result.found else "❌ Not found"
            print(f"\n{status} | ASIN: {asin}")
            if result.found:
                print(f"  Price: EGP {result.lowest_price:,.0f} ~ {result.highest_price:,.0f}")
                print(f"  Method: {result.method}")
                print(f"  URL: {result.source_url[:60]}...")
    finally:
        browser.stop()
