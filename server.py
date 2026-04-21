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
from functools import lru_cache
import threading

app = Flask(__name__)
CORS(app)

firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    try:
        key_dict = json.loads(firebase_key_json)
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized")
    except Exception as e:
        print(f"❌ Firebase init failed: {e}")
        raise
else:
    raise RuntimeError("FIREBASE_KEY_JSON not set!")

db = firestore.client()

SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ═════════════════════════════════════════════════════════════
# ✅ FRAUD DETECTION (Works WITHOUT price history)
# ═════════════════════════════════════════════════════════════

def detect_fraud_basic(original_price: float, current_price: float, claimed_discount: int) -> dict:
    """
    Detect fraud WITHOUT price history.
    Only uses: original_price, current_price, claimed_discount
    """
    reasons = []
    score = 0
    confidence = 60  # Base confidence

    if original_price <= 0 or current_price <= 0:
        return {
            "verdict": "UNVERIFIED",
            "score": 0,
            "confidence": 20,
            "reasons": ["Invalid price data"]
        }

    # ── Rule 1: Compare claimed discount with calculated discount
    calculated_discount = ((original_price - current_price) / original_price) * 100
    discount_diff = abs(claimed_discount - calculated_discount)

    if discount_diff > 10:
        reasons.append(f"Discount math error: claimed {claimed_discount}% but {calculated_discount:.0f}%")
        score += 30

    # ── Rule 2: Original price suspiciously high
    if original_price > current_price * 2.5:
        reasons.append("Original price inflated: 2.5x+ the sale price")
        score += 35
        confidence -= 10

    # ── Rule 3: Discount too high
    if claimed_discount > 70:
        reasons.append(f"Unrealistic discount: {claimed_discount}% (rarely exceeds 60%)")
        score += 25

    # ── Rule 4: No discount but prices differ
    if claimed_discount == 0 and original_price != current_price:
        reasons.append("Prices differ but no discount claimed")
        score += 15

    # Ensure confidence is in valid range
    confidence = max(20, min(100, confidence))

    if score >= 60:
        verdict = "FAKE"
    elif score >= 35:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {
        "verdict": verdict,
        "score": score,
        "confidence": confidence,
        "reasons": reasons
    }

def serialize_deal_fast(doc_id: str, deal_data: dict) -> dict:
    """Serialize deal with fraud detection (NO price history fetch)"""
    
    original = float(deal_data.get("original_price", 0))
    current = float(deal_data.get("current_price", 0))
    discount = int(deal_data.get("discount_percent", 0))
    
    fraud = detect_fraud_basic(original, current, discount)

    return {
        "id": doc_id,
        "title": deal_data.get("title", ""),
        "store": deal_data.get("site_display", deal_data.get("source", "")),
        "source": deal_data.get("source", ""),
        "current_price": current,
        "original_price": original,
        "discount_percent": discount,
        "currency": "EGP",
        "image_url": deal_data.get("image_url", ""),
        "product_url": deal_data.get("product_url", ""),
        "category": deal_data.get("category", ""),
        "rating": float(deal_data.get("rating", 0)) if deal_data.get("rating") else 0.0,
        
        # Fraud Detection (no history)
        "verdict": fraud.get("verdict", "UNVERIFIED"),
        "fake_score": fraud.get("score", 0),
        "confidence": fraud.get("confidence", 60),
        "fraud_reasons": fraud.get("reasons", []),
    }

# ═════════════════════════════════════════════════════════════
# PRICE HISTORY (Separate endpoint, with caching)
# ═════════════════════════════════════════════════════════════

price_history_cache = {}

def extract_asin(url: str) -> str:
    match = re.search(r'/dp/([A-Z0-9]{10})', url)
    if match:
        return match.group(1)
    return ""

def get_safqa_history(asin: str) -> dict:
    try:
        search_url = f"https://www.safqa.com/search?q={asin}&country=eg"
        resp = requests.get(search_url, headers=SCRAPE_HEADERS, timeout=8)
        if resp.status_code != 200:
            return {"found": False, "history": []}

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Try to find price chart data
        scripts = soup.find_all("script")
        history = []
        
        for script in scripts:
            text = script.string or ""
            if "price" in text.lower() and "date" in text.lower():
                try:
                    # Look for data patterns
                    matches = re.findall(r'"price"\s*:\s*([\d.]+)', text)
                    if matches:
                        history.append({"date": "recent", "price": float(matches[0])})
                        break
                except:
                    pass

        return {"found": len(history) > 0, "history": history}
    except:
        return {"found": False, "history": []}

def get_price_history_cached(product_url: str) -> dict:
    """Get price history with caching"""
    asin = extract_asin(product_url)
    if not asin:
        return {"found": False, "lowest": 0, "highest": 0, "source": ""}

    # Check cache
    if asin in price_history_cache:
        return price_history_cache[asin]

    # Try Safqa
    result = get_safqa_history(asin)
    
    if result["found"] and result["history"]:
        prices = [h["price"] for h in result["history"]]
        output = {
            "found": True,
            "lowest": min(prices),
            "highest": max(prices),
            "source": "Safqa"
        }
    else:
        output = {"found": False, "lowest": 0, "highest": 0, "source": ""}

    # Cache for 1 hour
    price_history_cache[asin] = output
    return output

# ═════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    """Fast endpoint - NO price history fetch"""
    limit = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)

    try:
        query = db.collection('deals')
        if category and category != "all":
            query = query.where('category', '==', category.lower())
        
        docs = query.limit(limit).stream()
        deals = [serialize_deal_fast(doc.id, doc.to_dict()) for doc in docs]

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
    """Get single deal (fast)"""
    try:
        doc = db.collection('deals').document(deal_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Deal not found"}), 404
        
        deal = serialize_deal_fast(doc.id, doc.to_dict())
        return jsonify({"success": True, "deal": deal, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
    """Search deals (fast)"""
    query = request.args.get('q', '').lower()
    category = request.args.get('category', None)
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
            cat = deal_data.get('category', '').lower()
            
            # Match query
            if query not in title and query not in store:
                continue
            
            # Match category if provided
            if category and category != "all" and cat != category.lower():
                continue
            
            deals.append(serialize_deal_fast(doc.id, deal_data))
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
    """Get all categories"""
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

@app.route('/api/v1/price-history', methods=['GET'])
def get_price_history():
    """Fetch price history for detail page (lazy load)"""
    product_url = request.args.get('url', '').strip()
    
    if not product_url:
        return jsonify({"success": False, "error": "Missing URL"}), 400

    history = get_price_history_cached(product_url)
    
    return jsonify({
        "success": True,
        "found": history.get("found", False),
        "lowest": history.get("lowest", 0),
        "highest": history.get("highest", 0),
        "source": history.get("source", ""),
        "timestamp": now_iso()
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404

@app.errorhandler(500)
def error(e):
    return jsonify({"success": False, "error": "Server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
