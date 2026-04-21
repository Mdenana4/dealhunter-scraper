from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

# ─── FIREBASE INIT ───
firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    try:
        key_dict = json.loads(firebase_key_json)
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized from env var")
    except Exception as e:
        print(f"❌ Firebase init failed: {e}")
        raise
else:
    raise RuntimeError("FIREBASE_KEY_JSON not set!")

db = firestore.client()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ─────────────────────────────────────────────────────────────
# ✅ FRAUD DETECTION ENGINE
# ─────────────────────────────────────────────────────────────

def detect_fake_discount(deal_data: dict) -> dict:
    """
    Analyze a deal for fake/suspicious discount patterns.
    Returns: {
        verdict: "GENUINE" | "FAKE" | "SUSPICIOUS",
        fake_score: 0-100,  # Higher = more suspicious
        reasons: [...]
    }
    """
    reasons = []
    score = 0

    original = float(deal_data.get("original_price", 0))
    current = float(deal_data.get("current_price", 0))
    discount_pct = int(deal_data.get("discount_percent", 0))

    # ── Rule 1: Inflated original price ──
    # If original price is 200%+ higher than current, it's suspicious
    if original > 0 and current > 0:
        inflation_ratio = original / current
        if inflation_ratio > 2.0:
            reasons.append(f"Original price inflated: {inflation_ratio:.1f}x the sale price")
            score += 35

    # ── Rule 2: Discount math doesn't match ──
    # Calculate what discount % should be
    if original > 0 and current > 0:
        real_discount = ((original - current) / original) * 100
        if abs(real_discount - discount_pct) > 5:
            reasons.append(f"Discount mismatch: claimed {discount_pct}% but math shows {real_discount:.0f}%")
            score += 25

    # ── Rule 3: Suspiciously high discount ──
    # Discounts over 60% are rare and often fake
    if discount_pct > 60:
        reasons.append(f"Unusually high discount: {discount_pct}% (real deals rarely exceed 50%)")
        score += 20

    # ── Rule 4: No price history available ──
    # If we can't verify with Safqa/Kanbkam, we can't confirm it's real
    # (This is less critical but adds uncertainty)
    has_history = deal_data.get("source_used") and deal_data.get("source_used") != ""
    if not has_history:
        reasons.append("No price history available to verify discount authenticity")
        score += 15

    # ── Rule 5: Price change in last 24 hours ──
    # Sudden price drops with huge discounts are often flash sale traps
    last_updated = deal_data.get("last_updated", "")
    if last_updated:
        try:
            updated_date = datetime.fromisoformat(last_updated.replace('Z', '+00:00')).date()
            today = datetime.now(timezone.utc).date()
            if (today - updated_date).days <= 1 and discount_pct > 30:
                reasons.append("Recent price drop with high discount (classic flash sale trap)")
                score += 10
        except:
            pass

    # ── Determine verdict ──
    if score >= 50:
        verdict = "FAKE"
        verdict_ar = "❌ مزيف - سعر مرتفع وهمي"
        emoji = "❌"
    elif score >= 30:
        verdict = "SUSPICIOUS"
        verdict_ar = "⚠️ مريب - احذر"
        emoji = "⚠️"
    else:
        verdict = "GENUINE"
        verdict_ar = "✅ حقيقي"
        emoji = "✅"

    return {
        "verdict": verdict,
        "verdict_ar": verdict_ar,
        "fake_emoji": emoji,
        "fake_score": score,
        "fraud_reasons": reasons
    }

def enrich_deal(doc_id: str, deal_data: dict) -> dict:
    """
    Add fraud detection and analysis to a deal before returning to API.
    """
    # Run fraud detection
    fraud_analysis = detect_fake_discount(deal_data)
    
    # Merge into deal data
    deal_data.update(fraud_analysis)
    
    return deal_data

def serialize_deal(doc_id: str, deal_data: dict) -> dict:
    """Convert Firestore deal doc to API response dict"""
    enriched = enrich_deal(doc_id, deal_data.copy())
    
    return {
        "id": doc_id,
        "title": enriched.get("title", ""),
        "store": enriched.get("site_display", enriched.get("source", "")),
        "source": enriched.get("source", ""),
        "current_price": float(enriched.get("current_price", 0)),
        "original_price": float(enriched.get("original_price", 0)),
        "discount_percent": int(enriched.get("discount_percent", 0)),
        "currency": "EGP",
        "image_url": enriched.get("image_url", ""),
        "product_url": enriched.get("product_url", ""),
        "category": enriched.get("category", ""),
        "rating": float(enriched.get("rating", 0)) if enriched.get("rating") else 0.0,
        # ✅ Fraud detection fields
        "verdict": enriched.get("verdict", "UNVERIFIED"),
        "verdict_ar": enriched.get("verdict_ar", ""),
        "fake_emoji": enriched.get("fake_emoji", "❓"),
        "fake_score": enriched.get("fake_score", 50),
        "fraud_reasons": enriched.get("fraud_reasons", []),
        "lowest_price": float(enriched.get("lowest_price_ever", 0)),
        "highest_price": float(enriched.get("highest_price_ever", 0)),
        "suggested_wait_price": float(enriched.get("suggested_wait_price", 0)),
        "rule_a_triggered": enriched.get("rule_a", False),
        "rule_b_triggered": enriched.get("rule_b", False),
        "source_used": enriched.get("source_used", ""),
    }

# ─────────────────────────────────────────────────────────────
# PUBLIC API ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    """Get all deals with optional filtering"""
    limit = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)

    try:
        query = db.collection('deals')
        if category:
            query = query.where('category', '==', category.lower())
        docs = query.limit(limit).stream()
        deals = [serialize_deal(doc.id, doc.to_dict()) for doc in docs]

        return jsonify({
            "success": True,
            "count": len(deals),
            "deals": deals,
            "timestamp": now_iso()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/deals/<deal_id>', methods=['GET'])
def get_deal_by_id(deal_id):
    """Get single deal by ID"""
    try:
        doc = db.collection('deals').document(deal_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Deal not found"}), 404
        deal = serialize_deal(doc.id, doc.to_dict())
        return jsonify({"success": True, "deal": deal, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
    """Search deals by query"""
    query = request.args.get('q', '').lower()
    limit = request.args.get('limit', 50, type=int)

    if not query or len(query) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400

    try:
        docs = db.collection('deals').limit(limit * 2).stream()
        deals = []
        for doc in docs:
            deal_data = doc.to_dict()
            title = deal_data.get('title', '').lower()
            store = deal_data.get('site_display', '').lower()
            category = deal_data.get('category', '').lower()
            if query in title or query in store or query in category:
                deals.append(serialize_deal(doc.id, deal_data))
                if len(deals) >= limit:
                    break

        return jsonify({
            "success": True,
            "count": len(deals),
            "deals": deals,
            "query": query,
            "timestamp": now_iso()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/categories', methods=['GET'])
def get_categories():
    """Get all available categories"""
    try:
        categories = set()
        for doc in db.collection('deals').stream():
            cat = doc.to_dict().get('category', 'general')
            if cat:
                categories.add(cat)
        return jsonify({
            "success": True,
            "categories": sorted(list(categories)),
            "timestamp": now_iso()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "dealhunter-api"}), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
