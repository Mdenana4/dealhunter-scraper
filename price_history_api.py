"""
price_history_api.py — System 1 API for System 2 integration

System 2 (deal scraper) uses these functions to:
- Query price-history verdicts for deals (replaces Kanbkam)
- Request new products be added to the price-history tracking list

Usage:
    from price_history_api import PriceHistoryAPI
    result = PriceHistoryAPI.query_verdict("amazon_eg", asin, price, list_price)
    PriceHistoryAPI.request_tracking("amazon_eg", asin, title, url, category)
"""

from typing import Any, Dict, Optional

from price_history_system import (
    FakeDiscountAnalyzer,
    MasterProductList,
    get_price_history_system,
)


class PriceHistoryAPI:
    """Static API: System 2 (scraper) → System 1 (price history DB)."""

    _product_list: Optional[MasterProductList] = None
    _analyzer: Optional[FakeDiscountAnalyzer] = None

    @classmethod
    def _init(cls) -> None:
        """Lazily initialize references to System 1 components."""
        if cls._product_list is None:
            system = get_price_history_system()
            cls._product_list = system._mpl
            cls._analyzer = system._analyzer

    @classmethod
    def query_verdict(
        cls, source: str, asin: str, current_price: float,
        list_price: float, title: str = "",
    ) -> Dict[str, Any]:
        """Query System 1 for a fraud verdict on a deal. Replaces Kanbkam.

        Returns dict with keys: verdict, fake_score, recommendation,
        confidence, trend, reasons. Verdict is one of "GENUINE", "FAKE",
        "SUSPICIOUS", or "UNVERIFIED".
        """
        cls._init()
        product_id = f"{source}_{asin}"
        product = cls._product_list.get_product(source, asin)
        snap_count = product.get("snapshots_count", 0) if product else 0

        if product is None or snap_count < 3:
            print(f"[PRICE-HISTORY-API] {product_id}: insufficient "
                  f"history ({snap_count} snapshots) — UNVERIFIED")
            return {"verdict": "UNVERIFIED", "fake_score": 50.0,
                    "recommendation": "research_first", "confidence": 0.0,
                    "trend": "stable",
                    "reasons": ["Insufficient price history (< 3 snapshots)"]}

        result = cls._analyzer.detect_fake_discount(
            product_id=product_id, current_price=current_price,
            list_price=list_price,
            thirty_day_avg=product.get("thirty_day_avg"),
            ninety_day_low=product.get("ninety_day_low"),
            times_discounted_40plus=product.get(
                "times_discounted_40plus", 0),
        )
        result["trend"] = product.get("trend", "stable")
        result.setdefault("verdict", "UNVERIFIED")
        result.setdefault("fake_score", 50.0)
        result.setdefault("recommendation", "research_first")
        result.setdefault("confidence", 0.0)
        result.setdefault("reasons", [])

        print(f"[PRICE-HISTORY-API] {product_id}: "
              f"verdict={result['verdict']}, "
              f"fake_score={result['fake_score']:.1f}, "
              f"recommendation={result['recommendation']}")
        return result

    @classmethod
    def request_tracking(
        cls, source: str, asin: str, title: str,
        url: str, category: str = "general",
    ) -> bool:
        """Request System 1 to start tracking a new product.

        Returns True if added (or already tracked), False on error.
        """
        cls._init()
        try:
            cls._product_list.request_tracking(
                source, asin, title, url, category)
            print(f"[PRICE-HISTORY-API] Requested tracking: "
                  f"{source}_{asin}")
            return True
        except Exception as e:
            print(f"[PRICE-HISTORY-API] Error requesting tracking "
                  f"for {source}_{asin}: {e}")
            return False

    @classmethod
    def get_product_stats(
        cls, source: str, asin: str,
    ) -> Optional[Dict[str, Any]]:
        """Get current analytics for a tracked product. None if not tracked."""
        cls._init()
        product = cls._product_list.get_product(source, asin)
        if not product:
            return None
        return {
            "thirty_day_avg": product.get("thirty_day_avg"),
            "ninety_day_low": product.get("ninety_day_low"),
            "ninety_day_high": product.get("ninety_day_high"),
            "times_discounted_40plus": product.get(
                "times_discounted_40plus", 0),
            "latest_verdict": product.get(
                "latest_verdict", "UNVERIFIED"),
            "latest_fake_score": product.get(
                "latest_fake_score", 50.0),
            "latest_recommendation": product.get(
                "latest_recommendation", "research_first"),
            "snapshots_count": product.get("snapshots_count", 0),
            "first_seen": product.get("first_seen"),
            "last_updated": product.get("last_updated"),
        }
