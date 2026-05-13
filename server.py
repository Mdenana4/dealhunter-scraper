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
        site = request.args.get("site", "")

        query = db.collection("deals").order_by("timestamp", direction="DESCENDING").limit(limit)
        docs = query.stream()

        deals = []
        for doc in docs:
            d = doc.to_dict()
            if cat and d.get("category", "").lower() != cat.lower():
                continue
            if site and site not in d.get("site", ""):
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[server] Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
