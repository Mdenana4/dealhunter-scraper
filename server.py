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
        result = {"sources": {}, "total_products": total_products, "total_snapshots": total_snapshots}
        for mc, data in sorted(sources.items()):
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
            deals.append({
                "id": doc.id,
                "title": d.get("title", ""),
                "site": d.get("site", ""),
                "current_price": d.get("current_price"),
                "original_price": d.get("original_price"),
                "discount": d.get("discount"),
                "category": d.get("category", ""),
                "timestamp": str(d.get("timestamp")) if d.get("timestamp") else None,
                "product_url": d.get("product_url", ""),
                "image_url": d.get("image_url", "")
            })

        return jsonify({"deals": deals, "count": len(deals)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[server] Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
