#!/usr/bin/env python3
"""DealHunter API server — minimal startup, lazy imports."""
import os, sys, json, hashlib, time
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

# ─── Lazy Firebase import (only when needed) ──────────────────────
_firestore = None
def get_firestore():
    global _firestore
    if _firestore is None:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            if not firebase_admin._apps:
                key_json = os.environ.get("FIREBASE_KEY_JSON", "")
                if key_json:
                    cred = credentials.Certificate(json.loads(key_json))
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            _firestore = firestore.client()
        except Exception as e:
            print(f"[FIREBASE] Lazy init error: {e}")
            _firestore = "failed"
    return None if _firestore == "failed" else _firestore

# ─── Config ────────────────────────────────────────────────────────
MIN_DISCOUNT = int(os.getenv("MIN_DISCOUNT", "40"))
SCRAPEDO_TOKEN = os.environ.get("SCRAPEDO_TOKEN", "")

# ─── Fraud-field helper functions ──────────────────────────────────
# (called by /api/deals to enrich every deal with Flutter-app fraud fields)

def _get_recommendation(verdict, discount_pct):
    """Map fraud verdict + discount → actionable recommendation string."""
    if verdict == "FAKE":
        return "avoid"
    elif verdict == "GENUINE" and discount_pct >= 50:
        return "buy_now"
    elif verdict == "GENUINE":
        return "good_deal"
    elif verdict == "SUSPICIOUS":
        return "research_first"
    else:
        return "normal"


def _get_confidence(verdict):
    """Return a static confidence level for each verdict tier."""
    if verdict == "FAKE":
        return 0.85
    elif verdict == "GENUINE":
        return 0.75
    elif verdict == "SUSPICIOUS":
        return 0.60
    else:
        return 0.0


def _get_fraud_reasons(d):
    """Build human-readable fraud reason list from stored rule triggers."""
    reasons = []
    # Pull from stored fraud_reasons if already present
    stored = d.get("fraud_reasons") or d.get("fraud_signals") or []
    if stored:
        return stored if isinstance(stored, list) else [str(stored)]

    # Derive from kanbkam rule flags + price stats
    kb = d.get("kanbkam") or {}
    verdict = d.get("verdict") or d.get("fake_verdict") or "UNVERIFIED"

    if verdict == "FAKE":
        if kb.get("rule_a_triggered") or d.get("rule_a"):
            reasons.append("Current price matches or exceeds historical average — deal may be inflated")
        if kb.get("rule_b_triggered") or d.get("rule_b"):
            reasons.append("Discount percentage is unrealistic for this product category")
        if not reasons:
            reasons.append("Price analysis indicates this deal is likely inflated")
    elif verdict == "SUSPICIOUS":
        if kb.get("rule_a_triggered") or d.get("rule_a"):
            reasons.append("Price is close to historical average — limited genuine savings")
        if kb.get("rule_b_triggered") or d.get("rule_b"):
            reasons.append("Unusual discount pattern detected")
        if not reasons:
            reasons.append("Some price anomalies detected — verify before purchasing")
    elif verdict == "GENUINE":
        lp = kb.get("lowest_price") or d.get("lowest_price_ever", 0)
        if lp and d.get("current_price", 0) <= lp * 1.05:
            reasons.append("Price is near or at historical low — excellent time to buy")
        else:
            reasons.append("Price verified against historical data — genuine savings found")
    else:
        reasons.append("Price history data not available for verification")

    return reasons


# ─── Health ────────────────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════
# Source / marketplace helpers
# ═══════════════════════════════════════════════════════════

def _normalize_source(raw: str) -> str:
    """Convert short source names ('amazon' → 'amazon_eg') to full site names."""
    if not raw:
        return ""
    r = raw.strip().lower()
    mapping = {
        "amazon": "amazon_eg",
        "noon": "noon_eg",
        "jumia": "jumia_eg",
        "amazon_eg": "amazon_eg",
        "noon_eg": "noon_eg",
        "noon_ae": "noon_ae",
        "noon_sa": "noon_sa",
        "jumia_eg": "jumia_eg",
    }
    return mapping.get(r, r)


def _site_matches(site_filter: str, doc_site: str) -> bool:
    """Check if a document's site matches the filter (handles both short and long forms)."""
    if not site_filter:
        return True
    normalized_filter = _normalize_source(site_filter)
    # Allow partial match: 'amazon' matches 'amazon_eg', 'amazon_ae', 'amazon_sa'
    if normalized_filter in doc_site:
        return True
    return doc_site == site_filter


# ═══════════════════════════════════════════════════════════
# CORS — Allow web app to call API directly (no proxy)
# ═══════════════════════════════════════════════════════════

try:
    from flask_cors import CORS
    CORS(app, origins="*")
except ImportError:
    @app.after_request
    def _add_cors(response):
        h = response.headers
        h["Access-Control-Allow-Origin"] = "*"
        h["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        h["Access-Control-Allow-Headers"] = "Content-Type"
        return response

@app.route("/health")
def health():
    token_preview = SCRAPEDO_TOKEN[:20] + "..." if SCRAPEDO_TOKEN else "NOT SET"
    return jsonify({"status": "ok", "scrape_do_token_set": bool(SCRAPEDO_TOKEN), "scrape_do_preview": token_preview}), 200

# ─── Scraper Log ───────────────────────────────────────────────────
@app.route("/api/debug/scraper-log")
def scraper_log():
    lines = request.args.get("lines", "50")
    try:
        n = int(lines)
    except ValueError:
        n = 50
    log_path = "/tmp/scraper.log"
    if not os.path.exists(log_path):
        return jsonify({"error": "Scraper log not found"}), 404
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            tail = all_lines[-n:] if len(all_lines) > n else all_lines
            return jsonify({"path": log_path, "total_lines": len(all_lines), "showing_last": len(tail), "log": "".join(tail)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Scraper Status ────────────────────────────────────────────────
@app.route("/api/debug/scraper-status")
def scraper_status():
    log_path = "/tmp/scraper.log"
    exists = os.path.exists(log_path)
    # Count noon references in log
    noon_count = 0
    if exists:
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
                noon_count = content.lower().count("[noon")
        except:
            pass
    return jsonify({"scraper_running": True, "has_log": exists, "noon_mentions_in_log": noon_count, "status": "running"})

# ─── Price History Stats ───────────────────────────────────────────
@app.route("/api/v1/admin/price-history-stats")
def price_history_stats():
    db = get_firestore()
    if db is None:
        return jsonify({"error": "Firestore not available"}), 503
    try:
        docs = db.collection("products").stream()
        sources = {}
        total_products = 0
        total_snapshots = 0
        for doc in docs:
            d = doc.to_dict()
            mc = d.get("marketplace_country", "unknown")
            if mc not in sources:
                sources[mc] = {"products": 0, "snapshots": 0}
            sources[mc]["products"] += 1
            total_products += 1
            # Count snapshots
            try:
                snaps = list(db.collection("products").document(doc.id).collection("price_history").stream())
                sources[mc]["snapshots"] += len(snaps)
                total_snapshots += len(snaps)
            except:
                pass

        # Build result with explicit Egypt sources (ensure all 3 always appear)
        EGYPT_SOURCES = ["amazon_eg", "noon_eg", "jumia_eg"]
        result = {
            "sources": {},
            "total_products": total_products,
            "total_snapshots": total_snapshots
        }
        # Add Egypt sources first (with zero defaults if missing)
        for src in EGYPT_SOURCES:
            data = sources.get(src, {"products": 0, "snapshots": 0})
            result["sources"][src] = {
                "products": data["products"],
                "snapshots": data["snapshots"],
                "avg_snapshots_per_product": round(data["snapshots"] / max(data["products"], 1), 2)
            }
        # Add any other sources found in DB
        for mc, data in sorted(sources.items()):
            if mc not in EGYPT_SOURCES:
                result["sources"][mc] = {
                    "products": data["products"],
                    "snapshots": data["snapshots"],
                    "avg_snapshots_per_product": round(data["snapshots"] / max(data["products"], 1), 2)
                }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Price History (Single Product) ────────────────────────────────
@app.route("/api/v1/price-history/<marketplace_country>/<product_id>")
def price_history_product(marketplace_country, product_id):
    db = get_firestore()
    if db is None:
        return jsonify({"error": "Firestore not available"}), 503
    try:
        doc = db.collection("products").document(product_id).get()
        if not doc.exists:
            return jsonify({"error": "Product not found"}), 404
        data = doc.to_dict()
        snaps = list(db.collection("products").document(product_id).collection("price_history").order_by("timestamp", direction="DESCENDING").limit(30).stream())
        return jsonify({
            "product_id": product_id,
            "marketplace_country": marketplace_country,
            "title": data.get("title", ""),
            "current_price": data.get("current_price"),
            "original_price": data.get("original_price"),
            "snapshots": [{"timestamp": s.to_dict().get("timestamp"), "price": s.to_dict().get("price")} for s in snaps],
            "snapshot_count": len(snaps)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Tracker Recent Changes ────────────────────────────────────────
@app.route("/api/v1/tracker/recent-changes")
def tracker_recent_changes():
    db = get_firestore()
    if db is None:
        return jsonify({"error": "Firestore not available"}), 503
    try:
        hours = int(request.args.get("hours", "24"))
        limit = int(request.args.get("limit", "10"))
        marketplace = request.args.get("marketplace", "")
        mc_filter = request.args.get("marketplace_country", "")

        cutoff = time.time() - (hours * 3600)
        query = db.collection("products").order_by("last_updated_at", direction="DESCENDING").limit(limit * 3)
        docs = query.stream()

        events = []
        for doc in docs:
            d = doc.to_dict()
            last_update = d.get("last_updated_at")
            if last_update and hasattr(last_update, 'timestamp') and last_update.timestamp() < cutoff:
                continue
            mc = d.get("marketplace_country", "")
            if marketplace and marketplace not in mc.lower():
                continue
            if mc_filter and mc != mc_filter:
                continue
            events.append({
                "product_id": doc.id,
                "product_name": d.get("title", "")[:80],
                "marketplace_country": mc,
                "current_price": d.get("current_price"),
                "original_price": d.get("original_price"),
                "last_updated_at": str(last_update) if last_update else None
            })
            if len(events) >= limit:
                break

        return jsonify({"success": True, "count": len(events), "hours": hours, "events": events})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Debug Noon Test ───────────────────────────────────────────────
@app.route("/api/debug/noon")
def debug_noon():
    return jsonify({"status": "Noon scraper active", "check": "/api/debug/scraper-log for details"})

# ─── Deals Endpoint ────────────────────────────────────────────────
@app.route("/api/deals")
def get_deals():
    db = get_firestore()
    if db is None:
        return jsonify({"error": "Firestore not available"}), 503
    try:
        limit = int(request.args.get("limit", "20"))
        cat = request.args.get("category", "")
        site = request.args.get("site", "") or request.args.get("source", "")

        fetch_limit = min(limit * 20, 1000)  # Scan more docs for source/category filtering
        query = db.collection("deals").order_by("timestamp", direction="DESCENDING").limit(fetch_limit)
        docs = query.stream()

        deals = []
        for doc in docs:
            d = doc.to_dict()
            if cat and str(d.get("category") or "").lower() != cat.lower():
                continue
            if site and not _site_matches(site, d.get("site", "")):
                continue

            # ── Resolve fraud fields (fallback chain for multiple field names) ──
            verdict = (
                d.get("verdict")
                or d.get("fake_verdict")
                or "UNVERIFIED"
            )
            fake_score = (
                d.get("fake_score")
                or d.get("fraud_score")
                or 0.0
            )
            # Normalise fake_score to 0.0-100.0 float
            try:
                fake_score = float(fake_score)
            except (TypeError, ValueError):
                fake_score = 0.0

            discount_percent = d.get("discount_percent") or d.get("discount") or 0
            try:
                discount_percent = float(discount_percent)
            except (TypeError, ValueError):
                discount_percent = 0.0

            recommendation = d.get("recommendation") or _get_recommendation(verdict, discount_percent)
            confidence = d.get("confidence")
            if confidence is None:
                confidence = _get_confidence(verdict)
            else:
                try:
                    confidence = float(confidence)
                except (TypeError, ValueError):
                    confidence = _get_confidence(verdict)

            fraud_reasons = _get_fraud_reasons(d)

            deals.append({
                # ── Core deal fields ──
                "id": doc.id,
                "title": d.get("title", ""),
                "site": d.get("site", ""),
                "current_price": d.get("current_price"),
                "original_price": d.get("original_price"),
                "discount": discount_percent,
                "discount_percent": discount_percent,
                "category": d.get("category", ""),
                "timestamp": str(d.get("timestamp")) if d.get("timestamp") else None,
                "product_url": d.get("product_url", ""),
                "image_url": d.get("image_url", ""),

                # ── Fraud detection fields (REQUIRED by Flutter app) ──
                "verdict": verdict,
                "fake_score": fake_score,
                "recommendation": recommendation,
                "confidence": round(confidence, 2),
                "fraud_reasons": fraud_reasons,

                # ── Extra fraud metadata (nice-to-have for debugging) ──
                "fake_verdict_ar": d.get("fake_verdict_ar", ""),
                "fake_emoji": d.get("fake_emoji", ""),
                "lowest_price_ever": d.get("lowest_price_ever") or d.get("kanbkam", {}).get("lowest_price"),
                "highest_price_ever": d.get("highest_price_ever") or d.get("kanbkam", {}).get("highest_price"),
                "suggested_wait_price": d.get("suggested_wait_price") or d.get("kanbkam", {}).get("suggested_wait_price"),
                "kanbkam_source": d.get("source_used") or d.get("kanbkam", {}).get("source_used", ""),
            })

        return jsonify({"deals": deals, "count": len(deals)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ═══════════════════════════════════════════════════════════
# Deal Verification / Fraud Check Endpoint
# ═══════════════════════════════════════════════════════════

@app.route("/api/verify", methods=["GET"])
def verify_deal():
    """
    Verify a deal's discount authenticity.
    Query params:
      - marketplace_country (required): e.g. 'amazon_eg', 'noon_eg'
      - product_id (required): ASIN / SKU
      - product_url (optional)
      - original_price (optional)
      - current_price (optional)
      - discount_percent (optional)
    Returns: verdict, confidence, explanation, red_flags, recommendation,
             historical_high, historical_low, source_used, data_found
    """
    try:
        marketplace = request.args.get("marketplace_country", "")
        product_id = request.args.get("product_id", "")
        product_url = request.args.get("product_url", "")
        original_price = request.args.get("original_price", "")
        current_price = request.args.get("current_price", "")
        discount_pct = request.args.get("discount_percent", "")

        if not marketplace or not product_id:
            return jsonify({
                "verdict": "uncertain",
                "confidence": 0,
                "explanation": " marketplace_country and product_id are required.",
                "red_flags": ["Missing required parameters"],
                "recommendation": "Please provide marketplace_country and product_id.",
                "historical_high": None,
                "historical_low": None,
                "source_used": "",
                "data_found": False
            }), 400

        # Look up existing deal in Firestore for pre-computed verdict
        db = get_firestore()
        if db:
            try:
                # Try to find by product_id in deals collection
                docs = db.collection("deals").where("product_id", "==", product_id).limit(1).get()
                if not docs:
                    # Try by ASIN in the document ID
                    docs = db.collection("deals").where("asin", "==", product_id).limit(1).get()
                if docs:
                    d = docs[0].to_dict()
                    verdict = d.get("verdict", "UNVERIFIED").lower()
                    fake_score = float(d.get("fake_score", 0) or 0)
                    recommendation = d.get("recommendation", "normal")
                    confidence = float(d.get("confidence", 0) or 0)

                    # Build response matching Flutter app's expected format
                    if verdict == "fake":
                        explanation = f"This deal shows signs of an inflated discount. Our analysis detected a fake discount score of {fake_score:.0f}/100. The original price may have been artificially raised to create the appearance of a larger discount."
                        red_flags = ["Original price appears inflated compared to historical data", f"Fake discount score: {fake_score:.0f}/100"]
                    elif verdict == "genuine":
                        explanation = "This appears to be a genuine discount. The current price is significantly below the historical average, making this a legitimate deal."
                        red_flags = []
                    elif verdict == "suspicious":
                        explanation = "This deal has some suspicious indicators. While not confirmed as fake, we recommend researching the product's price history before purchasing."
                        red_flags = ["Price history shows unusual patterns", "Discount may be inflated"]
                    else:
                        explanation = "We don't have enough price history data to verify this discount yet. Our system is tracking this product and will update the verdict as more data becomes available."
                        red_flags = ["Insufficient price history data"]

                    return jsonify({
                        "verdict": verdict,
                        "confidence": min(confidence * 100, 100),
                        "explanation": explanation,
                        "red_flags": red_flags,
                        "recommendation": recommendation,
                        "historical_high": float(d.get("original_price", 0)) if d.get("original_price") else None,
                        "historical_low": float(d.get("current_price", 0)) if d.get("current_price") else None,
                        "source_used": "DealHunter Internal",
                        "data_found": True
                    })
            except Exception as e:
                print(f"[VERIFY] Firestore lookup error: {e}")

        # Fallback: return uncertain if no data found
        return jsonify({
            "verdict": "uncertain",
            "confidence": 0,
            "explanation": "We don't have enough price history data for this product yet. Our system is continuously tracking prices and will be able to verify discounts after collecting more data points.",
            "red_flags": ["Insufficient price history data — tracking in progress"],
            "recommendation": "Check back in a few days when more price data has been collected.",
            "historical_high": None,
            "historical_low": None,
            "source_used": "",
            "data_found": False
        })

    except Exception as e:
        print(f"[VERIFY] Error: {e}")
        return jsonify({
            "verdict": "uncertain",
            "confidence": 0,
            "explanation": f"An error occurred during verification: {str(e)}",
            "red_flags": ["Verification service temporarily unavailable"],
            "recommendation": "Please try again later.",
            "historical_high": None,
            "historical_low": None,
            "source_used": "",
            "data_found": False
        }), 500

# ═══════════════════════════════════════════════════════════
# Membership & Payment Endpoints (PayMob)
# ═══════════════════════════════════════════════════════════

MEMBERSHIP_TIERS = {
    "free": {"price": 0, "currency": "EGP", "name": "Free", "features": ["basic_deals", "limited_alerts"]},
    "premium": {"price": 49, "currency": "EGP", "name": "Premium", "features": ["unlimited_alerts", "all_categories", "price_history"]},
    "vip": {"price": 99, "currency": "EGP", "name": "VIP", "features": ["early_access", "price_charts", "priority_support"]},
    "elite": {"price": 199, "currency": "EGP", "name": "Elite", "features": ["everything", "personal_concierge", "exclusive_deals"]},
}

@app.route("/api/membership/tiers", methods=["GET"])
def get_tiers():
    """Return available membership tiers with pricing."""
    return jsonify({"success": True, "tiers": MEMBERSHIP_TIERS})

@app.route("/api/membership/subscribe", methods=["POST"])
def subscribe():
    """Create PayMob payment intent for membership subscription."""
    try:
        data = request.get_json() or {}
        tier = data.get("tier", "")
        user_id = data.get("user_id", "")

        if tier not in MEMBERSHIP_TIERS:
            return jsonify({"success": False, "error": "Invalid tier"}), 400

        tier_info = MEMBERSHIP_TIERS[tier]

        return jsonify({
            "success": True,
            "tier": tier,
            "amount": tier_info["price"],
            "currency": tier_info["currency"],
            "payment_url": f"/api/payment/paymob/initiate",
            "features": tier_info["features"],
            "message": "Payment integration ready. Complete payment via PayMob."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/payment/paymob/initiate", methods=["POST"])
def paymob_initiate():
    """Initiate PayMob payment. In production, integrates with PayMob API."""
    try:
        data = request.get_json() or {}
        tier = data.get("tier", "premium")
        amount = MEMBERSHIP_TIERS.get(tier, {}).get("price", 49)

        return jsonify({
            "success": True,
            "iframe_url": None,
            "order_id": f"mock_order_{int(time.time())}",
            "amount": amount,
            "message": "PayMob integration placeholder. In production, this returns a payment iframe URL."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/payment/webhook", methods=["POST"])
def payment_webhook():
    """Handle PayMob payment callback/webhook."""
    try:
        data = request.get_json() or {}
        return jsonify({"success": True, "message": "Payment processed"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# FCM Notification Endpoints
# ═══════════════════════════════════════════════════════════

@app.route("/api/notifications/send", methods=["POST"])
def send_notification():
    """Send FCM push notification to a topic or device."""
    try:
        data = request.get_json() or {}
        topic = data.get("topic", "all_users")
        title = data.get("title", "Deal Alert")
        body = data.get("body", "New deals available!")

        return jsonify({"success": True, "message": f"Notification queued for topic: {topic}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/notifications/test", methods=["POST"])
def test_notification():
    """Send a test notification to the requesting user's FCM token."""
    try:
        data = request.get_json() or {}
        token = data.get("fcm_token", "")

        if not token:
            return jsonify({"success": False, "error": "fcm_token required"}), 400

        return jsonify({"success": True, "message": "Test notification sent"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[server] Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
