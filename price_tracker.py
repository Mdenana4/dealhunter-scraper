# price_tracker.py
# Stores and queries per-product price history in Firestore.
#
# Firestore layout (see PRICE_TRACKING_SCHEMA.md for full explanation):
#
#   products/{doc_id}                   ← one document per product-marketplace pair
#     └── price_history/{auto_id}       ← one document per price snapshot
#
#   price_change_events/{auto_id}       ← flat log of every price change (fast global queries)
#
#   price_alerts/{auto_id}              ← user alert subscriptions
#
# Supported marketplace_country keys:
#   amazon_eg, amazon_ae, amazon_sa
#   noon_eg,   noon_ae,   noon_sa
#   jumia_eg
#
# Usage from scraper.py:
#   from price_tracker import record_price
#   record_price("amazon_eg", asin, title, url, current_price, original_price)

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from firebase_admin import firestore
from google.cloud.firestore import FieldFilter


# ─── Marketplace metadata ─────────────────────────────────────────────────────

MARKETPLACE_META: dict[str, dict] = {
    "amazon_eg": {"marketplace": "amazon", "country": "eg", "currency": "EGP"},
    "amazon_ae": {"marketplace": "amazon", "country": "ae", "currency": "AED"},
    "amazon_sa": {"marketplace": "amazon", "country": "sa", "currency": "SAR"},
    "noon_eg":   {"marketplace": "noon",   "country": "eg", "currency": "EGP"},
    "noon_ae":   {"marketplace": "noon",   "country": "ae", "currency": "AED"},
    "noon_sa":   {"marketplace": "noon",   "country": "sa", "currency": "SAR"},
    "jumia_eg":  {"marketplace": "jumia",  "country": "eg", "currency": "EGP"},
}

_PRICE_CHANGE_THRESHOLD = 0.01   # ignore floating-point noise below 1 piaster


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _db() -> firestore.Client:
    """Return the Firestore client (already initialised by server.py)."""
    return firestore.client()

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _calc_discount(original: Optional[float], current: float) -> Optional[float]:
    if not original or original <= 0 or current >= original:
        return None
    return round((original - current) / original * 100, 1)

def _calc_change_pct(old: Optional[float], new: float) -> float:
    if not old or old == 0:
        return 0.0
    return round((new - old) / old * 100, 2)

def _trend(prices: list[float]) -> str:
    """
    Compare the first-half average against the second-half average.
    Returns 'rising', 'falling', or 'stable'.
    Requires at least 6 data points.
    """
    if len(prices) < 6:
        return "stable"
    mid = len(prices) // 2
    avg_a = sum(prices[:mid]) / mid
    avg_b = sum(prices[mid:]) / (len(prices) - mid)
    if avg_a == 0:
        return "stable"
    pct = (avg_b - avg_a) / avg_a * 100
    if pct > 3:
        return "rising"
    if pct < -3:
        return "falling"
    return "stable"


def _detect_fake_discount(
    current_price: float,
    current_original: Optional[float],
    historical_prices: list[float],
) -> float:
    """
    Detect "fake discounts" where a store inflates the original/list
    price to make the discount look bigger.

    Returns a score from 0.0 (genuine discount) to 1.0 (definitely fake).

    Signals:
      1. current_original is much higher than historical average
      2. current_price is close to the historical median (not really discounted)
    """
    if not current_original or not historical_prices or len(historical_prices) < 5:
        return 0.0  # not enough data

    historical_avg = sum(historical_prices) / len(historical_prices)
    if historical_avg <= 0:
        return 0.0

    # Signal 1: original price inflated vs historical average
    inflation_ratio = current_original / historical_avg
    inflation_score = max(0.0, min(1.0, (inflation_ratio - 1.1) / 0.4))
    #  1.1x  → 0.0    (slight inflation = probably real)
    #  1.3x  → 0.5    (moderate inflation = suspicious)
    #  1.5x  → 1.0    (heavy inflation = definitely fake)

    # Signal 2: current price is close to historical average (not actually discounted)
    baseline_match = 1.0 - abs(current_price - historical_avg) / historical_avg
    baseline_score = max(0.0, min(1.0, baseline_match))
    #  same as average → 1.0  (not discounted at all)
    #  20% below avg  → 0.0  (genuine discount)

    # Combined: inflation matters more (60%), baseline match (40%)
    return round(inflation_score * 0.6 + baseline_score * 0.4, 2)


def _buy_recommendation(
    current_price: float,
    lowest_ever: Optional[float],
    avg_30d: Optional[float],
    trend: str,
    fake_discount_score: float,
) -> str:
    """
    Recommend whether to buy now, wait, or that it's a good deal.

    Returns one of: 'buy_now', 'good_deal', 'wait', 'normal'
    """
    # Near all-time low → BUY NOW
    if lowest_ever and current_price <= lowest_ever * 1.05:
        return "buy_now"

    # Significantly below average → GOOD DEAL
    if avg_30d and current_price <= avg_30d * 0.85:
        return "good_deal"

    # Price is falling → WAIT (might drop more)
    if trend == "falling" and fake_discount_score < 0.5:
        return "wait"

    # Fake discount detected → WAIT (real price is same as always)
    if fake_discount_score > 0.6:
        return "wait"

    return "normal"


def _update_product_analytics(
    marketplace_country: str,
    product_id: str,
    current_price: float,
    current_original: Optional[float],
) -> None:
    """
    Compute and save price analytics to the product document.
    Called automatically after every price record.

    This creates a Kanbkam-style analytics overlay:
      - lowest/highest/average prices
      - price trend
      - fake discount score
      - buy recommendation
    """
    db = _db()
    doc_id = make_product_doc_id(marketplace_country, product_id)

    # Get 30-day price history for analytics
    history = get_price_history(marketplace_country, product_id, days=30)
    prices = [h["price"] for h in history if h.get("price") is not None]

    if len(prices) < 3:
        return  # not enough data yet

    # Core stats
    lowest = min(prices)
    highest = max(prices)
    avg = round(sum(prices) / len(prices), 2)
    trend = _trend(prices)

    # Get all-time historical prices for fake discount detection
    all_history = get_price_history(marketplace_country, product_id, days=365)
    all_prices = [h["price"] for h in all_history if h.get("price") is not None]

    # Fake discount detection
    fake_score = _detect_fake_discount(current_price, current_original, all_prices)

    # Buy recommendation
    recommendation = _buy_recommendation(current_price, lowest, avg, trend, fake_score)

    # Save analytics to product document
    analytics = {
        "analytics": {
            "lowest_price_ever": lowest,
            "highest_price_ever": highest,
            "average_price_30d": avg,
            "price_trend": trend,
            "fake_discount_score": fake_score,
            "fake_discount_label": (
                "FAKE" if fake_score > 0.7 else
                "SUSPICIOUS" if fake_score > 0.4 else
                "GENUINE"
            ),
            "buy_recommendation": recommendation,
            "total_snapshots": len(prices),
            "last_analytics_update": _now(),
        }
    }

    db.collection("products").document(doc_id).update(analytics)
    # v9.9: [ANALYTICS] log moved to scraper.py _engine2_tracking() with real _compute_fake_score()
    # to avoid duplicate output. Firestore analytics update above still runs.


def make_product_doc_id(marketplace_country: str, product_id: str) -> str:
    """
    Build a stable, human-readable Firestore document ID for a product.

    Format: {marketplace_country}_{sanitised_product_id}
    Example: "amazon_eg_B08N5WRWNW"

    Firestore document IDs must be <= 1500 bytes and must not contain '/'.
    We cap the sanitised part at 80 characters.
    """
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", product_id.strip())[:80]
    return f"{marketplace_country}_{safe}"


# ─── Core write: record one price snapshot ────────────────────────────────────

def record_price(
    marketplace_country: str,
    product_id: str,
    name: str,
    url: str,
    price: float,
    original_price: Optional[float] = None,
    currency: Optional[str] = None,
    in_stock: bool = True,
    image_url: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
) -> dict:
    """
    Record one price capture for a product.

    What this does (all inside a single Firestore transaction):
      1. Reads the product document to get the previous price.
      2. Creates the product document if it doesn't exist yet.
      3. Updates the product document with the latest price + metadata.
      4. Appends a timestamped snapshot to the products/{id}/price_history
         subcollection, including the delta from the previous price.
      5. If the price actually changed (or this is the first snapshot), writes
         a mirrored document to the top-level price_change_events collection
         so that "what changed recently?" queries are fast and cheap.

    Returns a dict describing what happened:
      {
        "doc_id":        str,    # Firestore document ID of the product
        "is_new":        bool,   # True if the product was just created
        "price_changed": bool,   # True if the price differs from the last snapshot
        "old_price":     float | None,
        "new_price":     float,
        "change_amount": float,  # new - old  (negative = price dropped)
        "change_pct":    float,  # % change   (negative = price dropped)
      }
    """
    if marketplace_country not in MARKETPLACE_META:
        raise ValueError(
            f"Unknown marketplace_country '{marketplace_country}'. "
            f"Valid keys: {list(MARKETPLACE_META)}"
        )

    meta = MARKETPLACE_META[marketplace_country]
    currency = currency or meta["currency"]
    price = round(float(price), 2)
    if original_price is not None:
        original_price = round(float(original_price), 2)

    db = _db()
    doc_id      = make_product_doc_id(marketplace_country, product_id)
    product_ref = db.collection("products").document(doc_id)
    history_ref = product_ref.collection("price_history")
    events_col  = db.collection("price_change_events")

    # Pre-create document references so they can be used inside the transaction.
    new_history_ref = history_ref.document()          # auto-generated ID
    new_event_ref   = events_col.document()           # auto-generated ID

    now = _now()
    result: dict = {
        "doc_id": doc_id,
        "is_new": False,
        "price_changed": False,
        "old_price": None,
        "new_price": price,
        "change_amount": 0.0,
        "change_pct": 0.0,
    }

    @firestore.transactional
    def _run(transaction: firestore.Transaction) -> None:
        snap = product_ref.get(transaction=transaction)
        prev_price: Optional[float] = None

        if not snap.exists:
            # ── First time we see this product ──────────────────────────────
            result["is_new"] = True
            transaction.set(product_ref, {
                "product_id":          product_id,
                "marketplace":         meta["marketplace"],
                "country":             meta["country"],
                "marketplace_country": marketplace_country,
                "name":                name,
                "brand":               brand,
                "category":            category,
                "url":                 url,
                "image_url":           image_url,
                "currency":            currency,
                "current_price":       price,
                "original_price":      original_price,
                "current_discount_pct": _calc_discount(original_price, price),
                "in_stock":            in_stock,
                "first_seen_at":       now,
                "last_updated_at":     now,
                "scrape_priority":     "medium",
                "total_snapshots":     0,
            })
        else:
            # ── Subsequent visit: update the product document ───────────────
            prev_data  = snap.to_dict() or {}
            prev_price = prev_data.get("current_price")

            if prev_price is not None and abs(price - prev_price) > _PRICE_CHANGE_THRESHOLD:
                result["price_changed"] = True
                result["old_price"]     = prev_price
                result["change_amount"] = round(price - prev_price, 2)
                result["change_pct"]    = _calc_change_pct(prev_price, price)

            update_fields: dict = {
                "name":                name,
                "url":                 url,
                "current_price":       price,
                "original_price":      original_price,
                "current_discount_pct": _calc_discount(original_price, price),
                "in_stock":            in_stock,
                "last_updated_at":     now,
                "total_snapshots":     firestore.Increment(1),
            }
            # Only overwrite optional fields when the caller provides them
            if image_url:
                update_fields["image_url"] = image_url
            if category:
                update_fields["category"] = category
            if brand:
                update_fields["brand"] = brand
            transaction.update(product_ref, update_fields)

        # ── Write price_history snapshot (always) ───────────────────────────
        transaction.set(new_history_ref, {
            "price":          price,
            "original_price": original_price,
            "discount_pct":   _calc_discount(original_price, price),
            "currency":       currency,
            "in_stock":       in_stock,
            "timestamp":      now,
            # Delta fields — null for the very first snapshot
            "change_from":    prev_price,
            "change_amount":  round(price - prev_price, 2) if prev_price is not None else 0.0,
            "change_pct":     _calc_change_pct(prev_price, price) if prev_price is not None else 0.0,
        })

        # ── Write price_change_events (only when something changed) ─────────
        if result["is_new"] or result["price_changed"]:
            transaction.set(new_event_ref, {
                "product_doc_id":      doc_id,
                "product_name":        name,
                "marketplace":         meta["marketplace"],
                "country":             meta["country"],
                "marketplace_country": marketplace_country,
                "url":                 url,
                "image_url":           image_url,
                "category":            category,
                "old_price":           prev_price,
                "new_price":           price,
                "change_amount":       result["change_amount"],
                "change_pct":          result["change_pct"],
                "currency":            currency,
                "timestamp":           now,
                "is_new_product":      result["is_new"],
            })

    _run(db.transaction())

    # ── Update Kanbkam-style analytics (non-transactional, best-effort) ──
    try:
        _update_product_analytics(marketplace_country, product_id, price, original_price)
    except Exception as _ae:
        # Analytics are advisory — never let them break price recording
        print(f"  [ANALYTICS-SKIP] {_ae}")

    return result


# ─── Read helpers ─────────────────────────────────────────────────────────────

def get_price_history(
    marketplace_country: str,
    product_id: str,
    days: int = 90,
    limit: int = 1000,
) -> list[dict]:
    """
    Return every price snapshot for a product over the past `days` days,
    sorted oldest → newest.

    Each item contains:
      timestamp, price, original_price, discount_pct,
      change_from, change_amount, change_pct, in_stock, currency
    """
    db     = _db()
    doc_id = make_product_doc_id(marketplace_country, product_id)
    since  = _now() - timedelta(days=days)

    docs = (
        db.collection("products")
          .document(doc_id)
          .collection("price_history")
          .where(filter=FieldFilter("timestamp", ">=", since))
          .order_by("timestamp", direction=firestore.Query.ASCENDING)
          .limit(limit)
          .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def get_price_changes_only(
    marketplace_country: str,
    product_id: str,
    days: int = 90,
) -> list[dict]:
    """
    Return only the snapshots where the price actually changed.

    This gives a clean "price change log":
      "Apr 3 14:00 — went from EGP 2,500 to EGP 2,510 (+0.4 %)"
      "Apr 7 09:15 — went from EGP 2,510 to EGP 2,299 (-8.4 %)"

    The very first snapshot (change_from is None) is always included because
    it establishes the starting price when tracking began.
    """
    history = get_price_history(marketplace_country, product_id, days=days)
    return [
        h for h in history
        if h.get("change_from") is None          # first ever snapshot
        or abs(h.get("change_amount", 0)) > _PRICE_CHANGE_THRESHOLD
    ]


def get_product_summary(
    marketplace_country: str,
    product_id: str,
    history_days: int = 90,
) -> Optional[dict]:
    """
    Return the product document enriched with statistics computed from the
    last `history_days` days of price snapshots:

      lowest_price, highest_price, average_price, price_trend,
      total_snapshots_in_window, price_change_count
    """
    db     = _db()
    doc_id = make_product_doc_id(marketplace_country, product_id)
    snap   = db.collection("products").document(doc_id).get()

    if not snap.exists:
        return None

    product = snap.to_dict() or {}
    history = get_price_history(marketplace_country, product_id, days=history_days)
    prices  = [h["price"] for h in history if h.get("price") is not None]
    changes = [h for h in history if abs(h.get("change_amount", 0)) > _PRICE_CHANGE_THRESHOLD]

    stats: dict = {}
    if prices:
        stats = {
            "lowest_price":          min(prices),
            "highest_price":         max(prices),
            "average_price":         round(sum(prices) / len(prices), 2),
            "price_trend":           _trend(prices),
            "total_snapshots_in_window": len(prices),
            "price_change_count":    len(changes),
            "history_days":          history_days,
        }

    return {"doc_id": doc_id, **product, **stats}


def get_recent_price_changes(
    marketplace_country: Optional[str] = None,
    marketplace: Optional[str] = None,
    country: Optional[str] = None,
    hours: int = 24,
    limit: int = 50,
) -> list[dict]:
    """
    Query the flat price_change_events collection for recent changes.

    Filter precedence (use one):
      marketplace_country — e.g. "amazon_eg"  (most specific)
      marketplace         — e.g. "amazon"     (all countries)
      country             — e.g. "eg"         (all marketplaces)
      (none)              — all events

    Results are newest-first.
    """
    db    = _db()
    since = _now() - timedelta(hours=hours)
    q     = db.collection("price_change_events").where(filter=FieldFilter("timestamp", ">=", since))

    if marketplace_country:
        q = q.where(filter=FieldFilter("marketplace_country", "==", marketplace_country))
    elif marketplace:
        q = q.where(filter=FieldFilter("marketplace", "==", marketplace))
    elif country:
        q = q.where(filter=FieldFilter("country", "==", country))

    docs = (
        q.order_by("timestamp", direction=firestore.Query.DESCENDING)
         .limit(limit)
         .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]


def get_top_price_drops(
    marketplace_country: Optional[str] = None,
    hours: int = 24,
    limit: int = 20,
    min_drop_pct: float = 5.0,
) -> list[dict]:
    """
    Return products with the largest percentage price drops in the last `hours`.
    min_drop_pct is the minimum absolute drop (e.g. 5 = at least -5 %).
    Results are sorted biggest-drop-first.
    """
    # Fetch a wider set so we have enough after filtering
    candidates = get_recent_price_changes(
        marketplace_country=marketplace_country,
        hours=hours,
        limit=300,
    )
    drops = [
        c for c in candidates
        if c.get("change_pct", 0) <= -min_drop_pct
    ]
    drops.sort(key=lambda x: x.get("change_pct", 0))   # most negative first
    return drops[:limit]


def get_historical_low(marketplace_country: str, product_id: str) -> Optional[float]:
    """
    Return the lowest price ever recorded for a product across all history.
    Uses a large time window (10 years) to be effectively "all time".
    """
    history = get_price_history(marketplace_country, product_id, days=3650, limit=5000)
    prices  = [h["price"] for h in history if h.get("price") is not None]
    return min(prices) if prices else None


# ─── Alert helpers ────────────────────────────────────────────────────────────

def create_price_alert(
    user_id: str,
    marketplace_country: str,
    product_id: str,
    target_price: Optional[float] = None,
    alert_threshold_pct: Optional[float] = None,
    notification_channels: Optional[list] = None,
) -> str:
    """
    Create a price alert for a user.

    Either target_price (absolute) or alert_threshold_pct (relative) must be set.
    Returns the new alert document ID.
    """
    if target_price is None and alert_threshold_pct is None:
        raise ValueError("Provide target_price or alert_threshold_pct.")

    db     = _db()
    doc_id = make_product_doc_id(marketplace_country, product_id)
    ref    = db.collection("price_alerts").document()
    ref.set({
        "user_id":              user_id,
        "product_doc_id":       doc_id,
        "marketplace_country":  marketplace_country,
        "product_id":           product_id,
        "target_price":         target_price,
        "alert_threshold_pct":  alert_threshold_pct,
        "notification_channels": notification_channels or ["push", "email"],
        "is_active":            True,
        "created_at":           _now(),
        "last_alerted_at":      None,
    })
    return ref.id


def get_triggered_alerts(price_change_event: dict) -> list[dict]:
    """
    Given a price_change_event document, return all active alerts that should fire.
    Called after record_price() returns price_changed=True.
    """
    db            = _db()
    doc_id        = price_change_event["product_doc_id"]
    new_price     = price_change_event["new_price"]
    change_pct    = price_change_event.get("change_pct", 0)

    alerts = (
        db.collection("price_alerts")
          .where(filter=FieldFilter("product_doc_id", "==", doc_id))
          .where(filter=FieldFilter("is_active", "==", True))
          .stream()
    )

    triggered = []
    for a in alerts:
        data = a.to_dict() or {}
        target  = data.get("target_price")
        thr_pct = data.get("alert_threshold_pct")

        should_fire = False
        if target is not None and new_price <= target:
            should_fire = True
        if thr_pct is not None and change_pct <= -abs(thr_pct):
            should_fire = True

        if should_fire:
            triggered.append({"alert_id": a.id, **data})

    return triggered


def get_user_alerts(user_id: str) -> list[dict]:
    """Return all active alerts owned by user_id, newest first."""
    db = _db()
    docs = (
        db.collection("price_alerts")
          .where(filter=FieldFilter("user_id", "==", user_id))
          .where(filter=FieldFilter("is_active", "==", True))
          .order_by("created_at", direction="DESCENDING")
          .stream()
    )
    result = []
    for d in docs:
        data = d.to_dict() or {}
        data["alert_id"] = d.id
        # serialise datetime fields
        for k in ("created_at", "last_alerted_at"):
            v = data.get(k)
            if hasattr(v, "isoformat"):
                data[k] = v.isoformat()
        result.append(data)
    return result


def delete_alert(alert_id: str, user_id: str) -> bool:
    """
    Soft-delete (deactivate) an alert.
    Returns True if the alert was found and belonged to user_id, False otherwise.
    """
    db  = _db()
    ref = db.collection("price_alerts").document(alert_id)
    doc = ref.get()
    if not doc.exists:
        return False
    data = doc.to_dict() or {}
    if data.get("user_id") != user_id:
        return False
    ref.update({"is_active": False})
    return True
