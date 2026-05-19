#!/usr/bin/env python3
"""
Safqa Browser — Headless Chromium Price Checker v8.2 CLOUDFLARE-STEALTH
=======================================================================
Key fix: Fresh browser context per check to evade Cloudflare bot detection.

v8 → v8.1: Text-scan garbage fix, homepage detection, price sanity
v8.1 → v8.2: Cloudflare evasion — fresh context per check, CF detection, random delays

Changes in v8.2:
1. FRESH CONTEXT: New browser context for each check_product() call
2. CLOUDFLARE DETECT: Auto-detect "Just a moment..." challenge pages
3. RANDOM DELAYS: 2-5s between URL attempts to avoid rate limiting
4. BETTER STEALTH: Enhanced anti-detection scripts (permissions, webdriver, chrome)
5. COOKIE ISOLATION: Each check is independent — no cross-session tracking

API (unchanged — fake_checker.py compatible):
    from safqa_browser import check_safqa, shutdown_browser
    result = check_safqa(asin="B0DHTYW7P8", title="Apple iPhone 16")
    # Returns: {"found", "lowest_price", "highest_price", "price_samples", "coupon_codes"}
"""

from __future__ import annotations

import json
import logging
import random
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

    # v8.2: User agent rotation pool
    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.0",
    ]

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 45_000,
        render_wait_ms: int = 12_000,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.render_wait_ms = render_wait_ms

        self._pw = None
        self._browser = None
        self._started = False

    # ── Lifecycle ──

    def start(self) -> None:
        """Launch Chromium browser only (no context). Call once at scraper startup."""
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
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080",
                "--disable-web-security",
                "--disable-features=BlockInsecurePrivateNetworkRequests",
            ],
        )
        self._started = True
        print(f"    [SAFQA-BROWSER] Chromium ready in {time.time()-t0:.1f}s")

    def stop(self) -> None:
        """Close browser. Call at scraper shutdown."""
        print("    [SAFQA-BROWSER] Stopping Chromium...")
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            logger.warning(f"[SAFQA-BROWSER] Cleanup error: {exc}")
        finally:
            self._started = False

    # ── v8.2: Stealth Context (fresh per check) ──

    def _create_stealth_context(self):
        """Create a fresh browser context with anti-detection measures."""
        viewport = {"width": 1920, "height": 1080}
        user_agent = random.choice(self._USER_AGENTS)

        context = self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # v8.2: Enhanced anti-detection script
        context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

            // Fake chrome.runtime
            window.chrome = { runtime: {} };

            // Fake plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Fake permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ||
                parameters.name === 'clipboard-read' ||
                parameters.name === 'clipboard-write'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );

            // Remove Playwright-specific properties
            delete window.__playwright;
            delete window.__pw_manual;
            delete window.__PW_inspect;

            // Override iframe contentWindow to prevent detection
            const originalAttachShadow = Element.prototype.attachShadow;
            Element.prototype.attachShadow = function attachShadow(options) {
                return originalAttachShadow.call(this, options);
            };

            // Navigator.languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        return context

    @staticmethod
    def _is_cloudflare_challenge(page) -> bool:
        """Detect Cloudflare challenge/interstitial pages."""
        try:
            title = page.title().lower()
            content = page.content()[:500].lower()

            cf_markers = [
                "just a moment",
                "checking your browser",
                "verify you are human",
                "cf-browser-verification",
                "challenge-platform",
                "turnstile",
                "__cf_bm",
                "ray id",
            ]

            for marker in cf_markers:
                if marker in title or marker in content:
                    return True

            # Check for Cloudflare-specific elements
            cf_selectors = [
                "#cf-challenge-running",
                ".cf-browser-verification",
                "input[name='cf-turnstile-response']",
                "#turnstile-container",
            ]
            for sel in cf_selectors:
                try:
                    if page.query_selector(sel):
                        return True
                except Exception:
                    continue

            return False
        except Exception:
            return False

    @staticmethod
    def _random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
        """Sleep for a random duration to avoid bot detection patterns."""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    # ── Public API ──

    def check_product(
        self,
        asin: Optional[str] = None,
        product_url: Optional[str] = None,
        title: str = "",
    ) -> SafqaResult:
        """v8.2: Fresh stealth context per check to evade Cloudflare."""
        print(f"    [SAFQA-BROWSER] check_product() called, asin={asin}, _started={self._started}")

        if not self._started:
            self.start()

        result = SafqaResult()
        if not asin:
            return result

        # v8.2: Fresh context for each check (isolated cookies, fresh session)
        context = None
        page = None
        try:
            context = self._create_stealth_context()
            page = context.new_page()

            # ─── SEARCH-FIRST STRATEGY ───
            if title and title.strip():
                search_result = self._try_search_first(page, asin, title.strip())
                if search_result.found:
                    return search_result
                # v8.3: If search hit CF, skip direct URLs — same session, will also fail
                if self._is_cloudflare_challenge(page):
                    print(f"    [SAFQA-BROWSER] Cloudflare session flagged — skipping direct URLs")
                    return result

            # ─── FALLBACK: Direct product URLs ───
            self._random_delay(2, 4)
            urls = self._build_urls(asin, product_url)
            logger.info(f"[SAFQA-BROWSER] Checking ASIN {asin} — {len(urls)} direct URLs")

            for url in urls:
                try:
                    self._random_delay(2, 5)
                    result.source_url = url
                    self._navigate(page, url)

                    if self._is_cloudflare_challenge(page):
                        print(f"      [SAFQA-BROWSER] Cloudflare challenge detected, skipping")
                        continue

                    prices = self._run_extractors(page, asin)
                    if prices:
                        result.found = True
                        result.lowest_price = min(prices)
                        result.highest_price = max(prices)
                        result.price_samples = prices
                        result.method = "direct-url"
                        print(f"    [SAFQA-BROWSER] ASIN {asin} via direct URL: low={result.lowest_price:,.0f}")
                        return result

                except Exception as exc:
                    print(f"    [SAFQA-BROWSER] URL failed {url[:50]}: {exc}")
                    continue

            print(f"    [SAFQA-BROWSER] ASIN {asin}: not found on Safqa")
            return result

        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass
            if context:
                try:
                    context.close()
                except Exception:
                    pass

    # ── v8.2: Search-First with Fresh Context ──

    def _try_search_first(self, page, asin: str, title: str) -> SafqaResult:
        """v8.3: Search by product title — ONE attempt only, CF = stop.

        v8.3 fix: Multiple navigations in same context trigger CF.
        We try ONLY ONE search URL. If it returns homepage (no results),
        we go directly to product URLs. If CF hits, we stop entirely.
        """
        result = SafqaResult()
        search_title = title[:70]
        encoded = urllib.parse.quote(search_title)

        # v8.3: Only ONE search URL — multiple navigations trigger CF
        search_url = f"{self.SAFQA_BASE}/search?q={encoded}"

        try:
            print(f"      [SAFQA-BROWSER] Search-first: {search_url[:80]}...")
            self._navigate(page, search_url)

            # CF detected → session is flagged, stop ALL further attempts
            if self._is_cloudflare_challenge(page):
                print(f"      [SAFQA-BROWSER] Cloudflare challenge — stopping Safqa check entirely")
                return result  # Caller will see empty result = "not found"

            # Homepage redirect = product not in Safqa's DB
            current_url = page.url
            page_title = page.title()
            is_homepage = (
                "rfeeq altasawuq" in page_title.lower() or
                "رفيق التسوق" in page_title or
                ("/search" not in current_url and "/product" not in current_url)
            )
            if is_homepage:
                print(f"      [SAFQA-BROWSER] Search returned homepage — product not indexed")
                return result  # Fall through to direct URLs

            # Strategy A: Find ASIN match in search results
            try:
                asin_link = page.query_selector(f'a[href*="{asin}"]')
                if asin_link:
                    print(f"      [SAFQA-BROWSER] Found ASIN {asin} in results, clicking...")
                    asin_link.click()
                    page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
                    page.wait_for_timeout(self.render_wait_ms)

                    if self._is_cloudflare_challenge(page):
                        return result

                    prices = self._run_extractors(page, asin)
                    if prices:
                        result.found = True
                        result.lowest_price = min(prices)
                        result.highest_price = max(prices)
                        result.price_samples = prices
                        result.source_url = page.url
                        result.method = "search-asin-click"
                        return result
            except Exception as e:
                print(f"      [SAFQA-BROWSER] ASIN click failed: {e}")

            # Strategy B: Extract from search results page directly
            prices = self._run_extractors(page, asin)
            if prices:
                result.found = True
                result.lowest_price = min(prices)
                result.highest_price = max(prices)
                result.price_samples = prices
                result.source_url = search_url
                result.method = "search-page-direct"
                return result

            # Strategy C: Click first product link
            try:
                first_link = page.query_selector(
                    "a[href*='/product/'], a[href*='/products/'], a[href*='/p/']"
                )
                if first_link:
                    href = first_link.get_attribute("href")
                    if href:
                        click_url = href if href.startswith("http") else f"{self.SAFQA_BASE}{href}"
                        print(f"      [SAFQA-BROWSER] Clicking first result: {click_url[:60]}...")
                        self._navigate(page, click_url)

                        if self._is_cloudflare_challenge(page):
                            return result

                        prices = self._run_extractors(page, asin)
                        if prices:
                            result.found = True
                            result.lowest_price = min(prices)
                            result.highest_price = max(prices)
                            result.price_samples = prices
                            result.source_url = click_url
                            result.method = "search-first-result"
                            return result
            except Exception as e:
                print(f"      [SAFQA-BROWSER] First result click failed: {e}")

            print(f"      [SAFQA-BROWSER] Search page loaded but no prices found")

        except Exception as e:
            print(f"      [SAFQA-BROWSER] Search failed: {type(e).__name__}: {str(e)[:80]}")

        return result

    # ── Internal ──

    def _build_urls(self, asin: str, product_url: Optional[str]) -> list[str]:
        """Build list of URLs to try. v8.3: Only 2 — one with product_url, one locale."""
        urls = []
        if product_url and "joinsafqa.com" in product_url:
            urls.append(product_url)
        # v8.3: Only ONE locale URL — multiple navigations trigger CF
        urls.append(f"{self.SAFQA_BASE}/en/product/{asin}")
        return urls

    def _navigate(self, page, url: str) -> None:
        """Navigate to URL and wait for React to render. v8.2: accepts page param."""
        page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        page.wait_for_timeout(self.render_wait_ms)
        # DEBUG
        try:
            t = page.title()
            c = page.content()
            has_egp = "EGP" in c
            has_price = "price" in c.lower()
            print(f"      [SAFQA-BROWSER] Page: title={t[:50]} has_EGP={has_egp} has_price={has_price} url={page.url[:60]}")
        except Exception as e:
            print(f"      [SAFQA-BROWSER] Page info error: {e}")

    def _run_extractors(self, page, asin: str) -> Optional[list[float]]:
        """Run price extraction methods, return FIRST successful result."""
        extractors = [
            ("json-ld", self._extract_json_ld),
            ("next-data", self._extract_next_data),
            ("initial-state", self._extract_initial_state),
            ("dom-price", self._extract_dom_price),
            ("dom-tailwind", self._extract_tailwind_price),
            ("text-scan", self._extract_text_scan),
        ]

        for method_name, extractor in extractors:
            try:
                prices = extractor(page)
                if prices:
                    reasonable = [p for p in prices if 50 <= p <= 100_000]
                    if reasonable:
                        print(f"      [SAFQA-BROWSER] {method_name}: {reasonable[:5]}{'...' if len(reasonable) > 5 else ''}")
                        return reasonable
            except Exception as e:
                logger.debug(f"Extractor {method_name} failed: {e}")

        return None

    # ── Extraction Methods (v8.2: all accept page param) ──

    @staticmethod
    def _extract_json_ld(page) -> Optional[list[float]]:
        scripts = page.query_selector_all('script[type="application/ld+json"]')
        prices = []
        for script in scripts:
            try:
                data = json.loads(script.inner_text())
                if isinstance(data, dict) and data.get("@type") == "Product":
                    offers = data.get("offers", {})
                    if isinstance(offers, dict):
                        p = SafqaBrowser._to_float(offers.get("price"))
                        if p > 0:
                            prices.append(p)
                    p = SafqaBrowser._to_float(data.get("price"))
                    if p > 0:
                        prices.append(p)
                graph = data.get("@graph", []) if isinstance(data, dict) else []
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            p = SafqaBrowser._to_float(offers.get("price"))
                            if p > 0:
                                prices.append(p)
            except (json.JSONDecodeError, AttributeError):
                continue
        return prices if prices else None

    @staticmethod
    def _extract_next_data(page) -> Optional[list[float]]:
        el = page.query_selector("script#__NEXT_DATA__")
        if not el:
            return None
        try:
            data = json.loads(el.inner_text())
            return SafqaBrowser._find_prices_recursive(data)
        except (json.JSONDecodeError, AttributeError):
            return None

    @staticmethod
    def _extract_initial_state(page) -> Optional[list[float]]:
        state_json = page.evaluate("""
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
            return SafqaBrowser._find_prices_recursive(data)
        except (json.JSONDecodeError, AttributeError):
            return None

    @staticmethod
    def _extract_dom_price(page) -> Optional[list[float]]:
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
                els = page.query_selector_all(sel)
                for el in els:
                    text = el.inner_text().strip()
                    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                    if match:
                        p = float(match.group())
                        if 50 <= p <= 100_000:
                            prices.append(p)
            except Exception:
                continue
        return prices if prices else None

    @staticmethod
    def _extract_tailwind_price(page) -> Optional[list[float]]:
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
                els = page.query_selector_all(sel)
                for el in els:
                    text = el.inner_text().strip()
                    if not any(c in text for c in ("EGP", "ج.م", "جنيه")):
                        continue
                    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
                    if match:
                        p = float(match.group())
                        if 50 <= p <= 100_000:
                            prices.append(p)
            except Exception:
                continue
        return prices if prices else None

    @staticmethod
    def _extract_text_scan(page) -> Optional[list[float]]:
        """v8.1: ONLY matches numbers with EGP/ج.م currency markers."""
        try:
            text = page.content()
        except Exception:
            return None

        patterns = [
            r'([\d,]+\.?\d*)\s*(?:EGP|ج\.م|جنيه)',
            r'(?:EGP|ج\.م|جنيه)\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(?:L\.E|LE|ل\.إ)',
        ]
        prices = []
        for pat in patterns:
            for m in re.findall(pat, text):
                try:
                    p = float(m.replace(",", ""))
                    if 50 <= p <= 100_000:
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
