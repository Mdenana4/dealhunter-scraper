#!/usr/bin/env python3
"""
price_history_system.py — System 1
Independent price-history database and fake-discount detection for DealHunter.
Runs in a background daemon thread. 24-hour cycle: discovery → snapshots → analytics.

Usage:
    from price_history_system import start_price_history_system
    start_price_history_system()   # called once from scraper.py main()
"""
from __future__ import annotations
import re, threading, time
from datetime import datetime, timezone
from typing import Any
from bs4 import BeautifulSoup
from firebase_admin import firestore
from scraper import fetch_with_scraperapi

db = firestore.client()

def _log(msg: str) -> None:
    print(f"[PRICE-HISTORY] {msg}", flush=True)

# ─── 1. CONFIGURATION ────────────────────────────────────────────────────────

SOURCES: dict[str, dict[str, str]] = {
    "amazon_eg": {"name": "Amazon Egypt", "domain": "amazon.eg", "currency": "EGP", "lang": "en_US"},
    "amazon_ae": {"name": "Amazon UAE", "domain": "amazon.ae", "currency": "AED", "lang": "en_AE"},
    "amazon_sa": {"name": "Amazon Saudi", "domain": "amazon.sa", "currency": "SAR", "lang": "en_SA"},
    "noon_eg":   {"name": "Noon Egypt", "domain": "noon.com/egypt-en", "currency": "EGP"},
    "noon_ae":   {"name": "Noon UAE", "domain": "noon.com/uae-en", "currency": "AED"},
    "noon_sa":   {"name": "Noon Saudi", "domain": "noon.com/saudi-en", "currency": "SAR"},
    "jumia_eg":  {"name": "Jumia Egypt", "domain": "jumia.com.eg", "currency": "EGP"},
}

DEAL_CATEGORIES: dict[str, dict[str, str]] = {
    "electronics": {"amazon": "electronics", "noon": "electronics", "jumia": "electronics"},
    "smartphones": {"amazon": "smartphone", "noon": "smartphone", "jumia": "smartphone"},
    "laptops": {"amazon": "laptop", "noon": "laptop", "jumia": "laptop"},
    "headphones": {"amazon": "headphones", "noon": "headphones", "jumia": "headphones"},
    "tvs": {"amazon": "television", "noon": "television", "jumia": "television"},
    "cameras": {"amazon": "camera", "noon": "camera", "jumia": "camera"},
    "gaming": {"amazon": "gaming", "noon": "gaming", "jumia": "gaming"},
    "mens_fashion": {"amazon": "men+clothing", "noon": "men-clothing", "jumia": "men-clothing"},
    "womens_fashion": {"amazon": "women+clothing", "noon": "women-clothing", "jumia": "women-clothing"},
    "shoes": {"amazon": "shoes", "noon": "shoes", "jumia": "shoes"},
    "watches": {"amazon": "watch", "noon": "watches", "jumia": "watches"},
    "bags": {"amazon": "bag", "noon": "bags", "jumia": "bags"},
    "home_kitchen": {"amazon": "home+kitchen", "noon": "home-kitchen", "jumia": "home-kitchen"},
    "furniture": {"amazon": "furniture", "noon": "furniture", "jumia": "furniture"},
    "beauty": {"amazon": "beauty", "noon": "beauty", "jumia": "beauty"},
    "skincare": {"amazon": "skincare", "noon": "skincare", "jumia": "skincare"},
    "perfume": {"amazon": "perfume", "noon": "perfume", "jumia": "perfume"},
    "sports": {"amazon": "sports", "noon": "sports", "jumia": "sports"},
    "baby": {"amazon": "baby", "noon": "baby", "jumia": "baby-products"},
    "books": {"amazon": "books", "noon": "books", "jumia": "books"},
    "automotive": {"amazon": "car+accessories", "noon": "automotive", "jumia": "automotive"},
    "pet_supplies": {"amazon": "pet+supplies", "noon": "pet-supplies", "jumia": "pet-supplies"},
    "grocery": {"amazon": "grocery", "noon": "grocery", "jumia": "grocery"},
}

BESTSELLER_CATEGORIES: dict[str, dict[str, str]] = {
    "electronics": {"amazon": "/gp/bestsellers/electronics"}, "fashion": {"amazon": "/gp/bestsellers/fashion"},
    "beauty": {"amazon": "/gp/bestsellers/beauty"}, "home_kitchen": {"amazon": "/gp/bestsellers/home"},
    "books": {"amazon": "/gp/bestsellers/books"}, "toys": {"amazon": "/gp/bestsellers/toys"},
    "automotive": {"amazon": "/gp/bestsellers/automotive"}, "pet_supplies": {"amazon": "/gp/bestsellers/pet-supplies"},
    "grocery": {"amazon": "/gp/bestsellers/grocery"},
}

# ─── 2. MASTER PRODUCT LIST ──────────────────────────────────────────────────

class MasterProductList:
    """Central registry of all products being tracked."""

    @staticmethod
    def _doc_id(source: str, asin: str) -> str:
        return f"{source}_{re.sub(r'[^A-Za-z0-9_-]', '_', asin.strip())[:80]}"

    @staticmethod
    def _extract_asins(html: str) -> list[str]:
        if not html or len(html) < 500:
            return []
        soup = BeautifulSoup(html, "html.parser")
        asins: list[str] = []
        for c in soup.find_all("div", attrs={"data-asin": True}):
            a = c.get("data-asin", "").strip().upper()
            if a and len(a) >= 8 and a not in asins:
                asins.append(a)
        for link in soup.find_all("a", href=re.compile(r"/dp/[A-Z0-9]{10}", re.I)):
            if (m := re.search(r"/dp/([A-Z0-9]{10})", link.get("href", ""), re.I)) and (a := m.group(1).upper()) not in asins:
                asins.append(a)
        return asins

    def _ref(self, source: str, asin: str):
        return db.collection("price_history").document(self._doc_id(source, asin))

    def discover_from_category_pages(self, source: str, category: str, html: str) -> list[str]:
        new = [a for a in self._extract_asins(html) if not self._ref(source, a).get().exists]
        _log(f"discover_cat: {source}/{category} new={len(new)}")
        return new

    def discover_from_bestseller_pages(self, source: str, category: str, html: str) -> list[str]:
        new = [a for a in self._extract_asins(html) if not self._ref(source, a).get().exists]
        _log(f"discover_best: {source}/{category} new={len(new)}")
        return new

    def add_product(self, source: str, asin: str, title: str, url: str, category: str, added_by: str) -> bool:
        ref = self._ref(source, asin)
        if ref.get().exists:
            return False
        ref.set({"source": source, "asin": asin, "title": title, "url": url, "category": category,
                 "first_seen": firestore.SERVER_TIMESTAMP, "last_updated": firestore.SERVER_TIMESTAMP,
                 "added_by": added_by, "is_active": True, "snapshots_count": 0, "thirty_day_avg": None,
                 "ninety_day_low": None, "ninety_day_high": None, "times_discounted_40plus": 0,
                 "latest_verdict": "UNVERIFIED", "latest_fake_score": 50.0, "latest_recommendation": "research_first"})
        _log(f"add: {source}_{asin} by={added_by}")
        return True

    def get_active_products(self, source: str | None = None) -> list[dict]:
        q = db.collection("price_history")
        if source:
            q = q.where(filter=firestore.FieldFilter("source", "==", source))
        return [d.to_dict() for d in q.where(filter=firestore.FieldFilter("is_active", "==", True)).stream()]

    def get_product(self, source: str, asin: str) -> dict | None:
        snap = self._ref(source, asin).get()
        return snap.to_dict() if snap.exists else None

    def request_tracking(self, source: str, asin: str, title: str, url: str, category: str) -> bool:
        return self.add_product(source, asin, title, url, category, "system_2_request")

# ─── 3. PRICE SNAPSHOT COLLECTOR ─────────────────────────────────────────────

class PriceSnapshotCollector:
    """Fetches product pages and saves price snapshots to Firestore."""

    @staticmethod
    def _country(source: str) -> str:
        return source.split("_")[-1]

    @staticmethod
    def _extract_amazon(html: str) -> dict[str, Any]:
        out: dict[str, Any] = {"current_price": 0.0, "list_price": 0.0, "discount_percent": 0, "seller": "", "fulfillment": "Merchant", "in_stock": True}
        if not html or len(html) < 1000:
            return out
        soup = BeautifulSoup(html, "html.parser")
        cp = 0.0
        if (pw := soup.find("span", class_="a-price-whole")) and (m := re.search(r"[\d,.]+", pw.get_text(strip=True).replace(",", ""))):
            try: cp = float(m.group().replace(",", ""))
            except ValueError: pass
        if cp <= 0 and (pb := soup.find("span", class_=re.compile(r"\ba-price\b"))) and (off := pb.find("span", class_="a-offscreen")) and (m := re.search(r"[\d,.]+", off.get_text(strip=True).replace(",", ""))):
            try: cp = float(m.group().replace(",", ""))
            except ValueError: pass
        lp = cp
        if (lb := soup.find("span", class_="a-price a-text-price")) and (lo := lb.find("span", class_="a-offscreen")) and (m := re.search(r"[\d,.]+", lo.get_text(strip=True).replace(",", ""))):
            try: lp = float(m.group().replace(",", ""))
            except ValueError: pass
        seller, ftype = "", "Merchant"
        if (mi := soup.find(id="merchant-info") or soup.find(id="shipsFromSoldByMessage_feature_div")):
            txt = mi.get_text(separator=" ", strip=True)
            if "Amazon" in txt: seller, ftype = "Amazon", "FBA"
            else:
                parts = txt.split("sold by")
                seller = parts[-1].split(".")[0].strip() if len(parts) > 1 else txt[:60]
        if soup.find(id=re.compile(r"fulfilled-by-amazon|fulfillment-feature", re.I)) or "Fulfilled by Amazon" in soup.get_text(): ftype = "FBA"
        out["in_stock"] = soup.find(id="outOfStock") is None and not soup.find(string=re.compile(r"currently unavailable", re.I))
        disc = int(((lp - cp) / lp) * 100) if lp > cp > 0 else 0
        return {**out, "current_price": round(cp, 2), "list_price": round(lp, 2), "discount_percent": disc, "seller": seller or "Unknown", "fulfillment": ftype}

    def collect_snapshot(self, source: str, asin: str) -> dict | None:
        meta = SOURCES.get(source)
        if not meta: return None
        domain = meta["domain"]
        if source.startswith("amazon"): url = f"https://{domain}/dp/{asin}"
        elif source.startswith("noon"): url = f"https://www.{domain}/product/{asin}"
        elif source.startswith("jumia"): url = f"https://{domain}/product/{asin}"
        else: url = f"https://{domain}/dp/{asin}"
        try:
            resp = fetch_with_scraperapi(url, render_js=True, country=self._country(source))
            if not resp or resp.status_code != 200 or len(resp.text) < 2000: return None
            if source.startswith("amazon"): ex = self._extract_amazon(resp.text)
            elif source.startswith("noon"): ex = self._extract_noon(resp.text)
            elif source.startswith("jumia"): ex = self._extract_jumia(resp.text)
            else: ex = self._extract_amazon(resp.text)
            if ex["current_price"] <= 0: return None
            snap = {"current_price": ex["current_price"], "list_price": ex["list_price"], "currency": meta["currency"],
                    "discount_percent": ex["discount_percent"], "seller": ex["seller"], "fulfillment": ex["fulfillment"],
                    "scraped_at": firestore.SERVER_TIMESTAMP, "is_deal": ex["discount_percent"] >= 40, "in_stock": ex["in_stock"]}
            pid = f"{source}_{asin}"
            db.collection("price_history").document(pid).collection("snapshots").document().set(snap)
            try: db.collection("price_history").document(pid).update({"snapshots_count": firestore.Increment(1), "last_updated": firestore.SERVER_TIMESTAMP})
            except Exception: pass
            return snap
        except Exception as e:
            _log(f"snap error {source}_{asin}: {e}")
            return None

    def collect_all_snapshots(self, source: str) -> dict[str, int]:
        prods = MasterProductList().get_active_products(source=source)
        ok = failed = 0
        for p in prods:
            if not (asin := p.get("asin", "")): continue
            if self.collect_snapshot(source, asin): ok += 1
            else: failed += 1
            time.sleep(0.5)
        _log(f"collect_all: {source} ok={ok} failed={failed}")
        return {"ok": ok, "failed": failed}

    @staticmethod
    def _extract_noon(_html: str) -> dict[str, Any]:
        """TODO: Implement Noon product-page price extraction."""
        return {"current_price": 0.0, "list_price": 0.0, "discount_percent": 0, "seller": "", "fulfillment": "", "in_stock": True}

    @staticmethod
    def _extract_jumia(_html: str) -> dict[str, Any]:
        """TODO: Implement Jumia product-page price extraction."""
        return {"current_price": 0.0, "list_price": 0.0, "discount_percent": 0, "seller": "", "fulfillment": "", "in_stock": True}

# ─── 4. FAKE-DISCOUNT ANALYZER ───────────────────────────────────────────────

class FakeDiscountAnalyzer:
    """Reads all snapshots for a product and produces fraud analysis."""

    @staticmethod
    def _thirty_day_avg(prices: list[float]) -> float:
        recent = prices[-30:] if len(prices) >= 30 else prices
        return round(sum(recent) / len(recent), 2) if recent else 0.0

    @staticmethod
    def _ninety_day_low(prices: list[float]) -> float: return min(prices[-90:]) if prices else 0.0

    @staticmethod
    def _ninety_day_high(prices: list[float]) -> float: return max(prices[-90:]) if prices else 0.0

    @staticmethod
    def _trend(prices: list[float]) -> str:
        if len(prices) < 6: return "stable"
        mid = len(prices) // 2
        a, b = sum(prices[:mid]) / mid, sum(prices[mid:]) / (len(prices) - mid)
        if a == 0: return "stable"
        p = (b - a) / a * 100
        return "rising" if p > 3 else "falling" if p < -3 else "stable"

    def analyze_product(self, product_id: str) -> dict[str, Any]:
        try:
            snaps = (db.collection("price_history").document(product_id).collection("snapshots")
                     .order_by("scraped_at").stream())
            prices: list[float] = []
            deals40 = 0
            latest: dict | None = None
            for doc in snaps:
                d = doc.to_dict() or {}
                if (cp := d.get("current_price", 0)) and cp > 0: prices.append(cp)
                if d.get("is_deal"): deals40 += 1
                latest = d
            if len(prices) < 5:
                return {"verdict": "UNVERIFIED", "fake_score": 50.0, "recommendation": "research_first", "confidence": 0.0,
                        "reasons": ["Insufficient history (<5 snapshots)"], "thirty_day_avg": None, "ninety_day_low": None,
                        "ninety_day_high": None, "times_discounted_40plus": deals40, "trend": "stable"}
            tavg, nlow, nhigh = self._thirty_day_avg(prices), self._ninety_day_low(prices), self._ninety_day_high(prices)
            trend = self._trend(prices)
            cprice = latest.get("current_price", 0) if latest else 0
            lprice = latest.get("list_price", 0) if latest else 0
            r = self.detect_fake_discount(product_id, cprice, lprice, tavg, nlow, deals40)
            return {**r, "thirty_day_avg": tavg, "ninety_day_low": nlow, "ninety_day_high": nhigh, "times_discounted_40plus": deals40, "trend": trend}
        except Exception as e:
            _log(f"analyze error {product_id}: {e}")
            return {"verdict": "UNVERIFIED", "fake_score": 50.0, "recommendation": "research_first", "confidence": 0.0, "reasons": [f"Error: {e}"]}

    def detect_fake_discount(self, product_id: str, current_price: float, list_price: float,
                             thirty_day_avg: float | None = None, ninety_day_low: float | None = None,
                             times_discounted_40plus: int = 0) -> dict[str, Any]:
        reasons: list[str] = []
        if not thirty_day_avg:
            return {"verdict": "UNVERIFIED", "fake_score": 50.0, "recommendation": "research_first", "confidence": 0.0, "reasons": ["No price history"]}
        if list_price > thirty_day_avg * 1.5:
            score = min(100.0, 85.0 + (list_price / thirty_day_avg - 1.5) * 10)
            reasons.append(f"List {list_price} is {list_price/thirty_day_avg:.1f}x 30d avg ({thirty_day_avg})")
            return {"verdict": "FAKE", "fake_score": round(score, 1), "recommendation": "avoid", "confidence": 0.85, "reasons": reasons}
        if ninety_day_low and current_price <= ninety_day_low * 1.05:
            reasons.append(f"Price {current_price} near 90d low ({ninety_day_low})")
            return {"verdict": "GENUINE", "fake_score": 10.0, "recommendation": "buy_now" if current_price <= ninety_day_low else "good_deal", "confidence": 0.90, "reasons": reasons}
        if times_discounted_40plus > 5:
            reasons.append(f"40%+ off {times_discounted_40plus}x — fake urgency")
            return {"verdict": "SUSPICIOUS", "fake_score": 65.0, "recommendation": "wait", "confidence": 0.60, "reasons": reasons}
        if list_price > thirty_day_avg * 1.2:
            reasons.append(f"List {list_price} mildly inflated vs 30d avg ({thirty_day_avg})")
            return {"verdict": "SUSPICIOUS", "fake_score": 55.0, "recommendation": "research_first", "confidence": 0.50, "reasons": reasons}
        reasons.append("Neutral — insufficient signals")
        return {"verdict": "UNVERIFIED", "fake_score": 50.0, "recommendation": "research_first", "confidence": 0.30, "reasons": reasons}

# ─── 5. PRICE HISTORY SCHEDULER ──────────────────────────────────────────────

class PriceHistoryScheduler:
    """Main scheduler — runs the 24-hour cycle in a background daemon thread."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._running = False
        self._mpl = MasterProductList()
        self._collector = PriceSnapshotCollector()
        self._analyzer = FakeDiscountAnalyzer()

    def start(self) -> None:
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="PriceHistorySys1", daemon=True)
        self._thread.start()
        _log("Scheduler started")

    def stop(self) -> None: self._running = False

    def _run_loop(self) -> None:
        _log("Loop running")
        while self._running:
            try: self._run_cycle()
            except Exception as e: _log(f"CYCLE ERROR (recovering): {e}")
            for _ in range(24 * 60):
                if not self._running: break
                time.sleep(60)
        _log("Loop exited")

    def _run_cycle(self) -> None:
        t0 = datetime.now(timezone.utc)
        _log(f"=== Cycle start {t0.isoformat()} ===")
        total_new = 0
        for src in SOURCES:
            try: total_new += self._discovery_crawl(src)
            except Exception as e: _log(f"discovery error {src}: {e}")
        for src in SOURCES:
            try: self._collector.collect_all_snapshots(src)
            except Exception as e: _log(f"snapshot error {src}: {e}")
        analyzed = 0
        try:
            for prod in self._mpl.get_active_products():
                try:
                    pid = f"{prod['source']}_{prod['asin']}"
                    r = self._analyzer.analyze_product(pid)
                    db.collection("price_history").document(pid).update({
                        "thirty_day_avg": r.get("thirty_day_avg"), "ninety_day_low": r.get("ninety_day_low"),
                        "ninety_day_high": r.get("ninety_day_high"), "times_discounted_40plus": r.get("times_discounted_40plus", 0),
                        "latest_verdict": r["verdict"], "latest_fake_score": r["fake_score"],
                        "latest_recommendation": r["recommendation"], "last_updated": firestore.SERVER_TIMESTAMP})
                    analyzed += 1
                except Exception as e: _log(f"analytics error {prod.get('asin', '?')}: {e}")
        except Exception as e: _log(f"analytics cycle error: {e}")
        self._set_last_run()
        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        _log(f"=== Cycle done in {elapsed/60:.1f}min | new={total_new} analyzed={analyzed} ===")

    def _discovery_crawl(self, source: str) -> int:
        if not source.startswith("amazon"): return 0
        new_all: list[str] = []
        domain = SOURCES[source]["domain"]
        cc = source.split("_")[-1]
        for cat, cmap in DEAL_CATEGORIES.items():
            kw = cmap.get("amazon", "")
            if not kw: continue
            try:
                resp = fetch_with_scraperapi(f"https://{domain}/s?k={kw}&s=price-desc-rank", render_js=True, country=cc)
                if resp and resp.status_code == 200: new_all += [a for a in self._mpl.discover_from_category_pages(source, cat, resp.text) if a not in new_all]
                time.sleep(1)
            except Exception as e: _log(f"cat crawl error {source}/{cat}: {e}")
        for cat, cmap in BESTSELLER_CATEGORIES.items():
            path = cmap.get("amazon", "")
            if not path: continue
            try:
                resp = fetch_with_scraperapi(f"https://{domain}{path}", render_js=True, country=cc)
                if resp and resp.status_code == 200: new_all += [a for a in self._mpl.discover_from_bestseller_pages(source, cat, resp.text) if a not in new_all]
                time.sleep(1)
            except Exception as e: _log(f"best crawl error {source}/{cat}: {e}")
        added = 0
        for asin in new_all:
            try:
                if self._mpl.add_product(source, asin, "", f"https://{domain}/dp/{asin}", "unknown", "discovery_crawl"): added += 1
            except Exception as e: _log(f"add error {source}_{asin}: {e}")
        return added

    def is_due(self) -> bool:
        last = self._get_last_run()
        return True if last is None else (datetime.now(timezone.utc) - last).total_seconds() >= 86400

    def _get_last_run(self) -> datetime | None:
        try:
            snap = db.collection("price_history").document("__system").get()
            if snap.exists and (ts := (snap.to_dict() or {}).get("last_run")):
                return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        except Exception: pass
        return None

    def _set_last_run(self) -> None:
        try: db.collection("price_history").document("__system").set({"last_run": firestore.SERVER_TIMESTAMP, "updated_by": "price_history_system"}, merge=True)
        except Exception as e: _log(f"set_last_run error: {e}")

# ─── 6. MODULE-LEVEL CONVENIENCE ─────────────────────────────────────────────

_price_history_system: PriceHistoryScheduler | None = None

def get_price_history_system() -> PriceHistoryScheduler:
    global _price_history_system
    if _price_history_system is None: _price_history_system = PriceHistoryScheduler()
    return _price_history_system

def start_price_history_system() -> None:
    get_price_history_system().start()
    _log("System 1 started — 24h cycle background thread launched")
