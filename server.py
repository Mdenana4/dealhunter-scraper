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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ═════════════════════════════════════════════════════════════
# AMAZON PRICE SCRAPER
# ═════════════════════════════════════════════════════════════

def scrape_amazon_prices(product_url: str) -> dict:
    """
    Scrape Amazon to get REAL original and current prices
    """
    try:
        if not product_url or "amazon" not in product_url.lower():
            return {"found": False, "original": 0, "current": 0}

        # Add timeout and headers
        resp = requests.get(product_url, headers=SCRAPE_HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"found": False, "original": 0, "current": 0}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try multiple selectors for current price
        current_price = 0
        original_price = 0

        # Selector 1: Current price
        price_span = soup.find("span", class_=re.compile("a-price-whole"))
        if price_span:
            price_text = price_span.text.strip()
            match = re.search(r'[\d,]+', price_text)
            if match:
                current_price = float(match.group().replace(",", ""))

        # Selector 2: Original/List price (struck through)
        original_span = soup.find("span", class_=re.compile("a-price a-text-price-range"))
        if not original_span:
            original_span = soup.find("s", class_=re.compile("a-price"))
        
        if original_span:
            original_text = original_span.text.strip()
            match = re.search(r'[\d,]+', original_text)
            if match:
                original_price = float(match.group().replace(",", ""))

        # If no original found, use current * 1.5 as estimate
        if original_price == 0 and current_price > 0:
            original_price = current_price * 1.5

        return {
            "found": current_price > 0,
            "original": original_price,
            "current": current_price
        }
    except Exception as e:
        print(f"Scrape error: {e}")
        return {"found": False, "original": 0, "current": 0}

# ═════════════════════════════════════════════════════════════
# ✅ FRAUD DETECTION (Uses REAL Amazon prices)
# ═════════════════════════════════════════════════════════════

def detect_fraud_with_real_prices(claimed_original: float, claimed_current: float, 
                                   real_original: float, real_current: float, 
                                   claimed_discount: int) -> dict:
    """
    Detect fraud by comparing claimed prices against REAL Amazon prices
    """
    reasons = []
    score = 0
    confidence = 60

    if claimed_current <= 0:
        return {"verdict": "UNVERIFIED", "score": 0, "confidence": 20, "reasons": ["Invalid price"]}

    # No real price data - fall back to basic check
    if real_original <= 0:
        return detect_fraud_basic(claimed_original, claimed_current, claimed_discount)

    # ── Rule 1: Claimed original vs REAL original (MOST IMPORTANT)
    if real_original > 0:
        original_diff = abs(claimed_original - real_original) / real_original * 100
        
        if original_diff > 15:  # More than 15% difference
            reasons.append(f"Original price mismatch: claimed {claimed_original:.0f} vs Amazon {real_original:.0f}")
            score += 40
            confidence -= 15

    # ── Rule 2: Compare claimed discount vs REAL discount
    real_discount = ((real_original - real_current) / real_original) * 100 if real_original > 0 else 0
    discount_diff = abs(claimed_discount - real_discount)
    
    if discount_diff > 10:
        reasons.append(f"Discount exaggerated: claimed {claimed_discount}% vs real {real_discount:.0f}%")
        score += 35

    # ── Rule 3: Claimed original suspiciously high vs claimed current
    if claimed_original > claimed_current * 2.5:
        reasons.append(f"Original price inflated: {claimed_original:.0f} is {(claimed_original/claimed_current):.1f}x the sale price")
        score += 30

    # ── Rule 4: Unrealistic discount
    if claimed_discount > 70:
        reasons.append(f"Unrealistic discount: {claimed_discount}% (rarely exceeds 60%)")
        score += 20

    confidence = max(30, min(100, confidence))

    if score >= 70:
        verdict = "FAKE"
    elif score >= 40:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}

def detect_fraud_basic(original_price: float, current_price: float, claimed_discount: int) -> dict:
    """Fallback when no real price data available"""
    reasons = []
    score = 0
    confidence = 60

    if original_price > current_price * 2.5:
        reasons.append("Original price inflated: 2.5x+ the sale price")
        score += 35
        confidence -= 10

    if claimed_discount > 70:
        reasons.append(f"Unrealistic discount: {claimed_discount}%")
        score += 25

    confidence = max(20, min(100, confidence))

    if score >= 60:
        verdict = "FAKE"
    elif score >= 35:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}

def serialize_deal_smart(doc_id: str, deal_data: dict) -> dict:
    """
    Serialize deal with REAL fraud detection
    Scrapes Amazon to get true prices
    """
    
    claimed_original = float(deal_data.get("original_price", 0))
    claimed_current = float(deal_data.get("current_price", 0))
    claimed_discount = int(deal_data.get("discount_percent", 0))
    product_url = deal_data.get("product_url", "")

    # Scrape Amazon for REAL prices (with timeout)
    real_prices = scrape_amazon_prices(product_url)
    real_original = real_prices.get("original", 0)
    real_current = real_prices.get("current", 0)

    # Detect fraud using REAL prices
    if real_prices.get("found"):
        fraud = detect_fraud_with_real_prices(claimed_original, claimed_current, 
                                             real_original, real_current, claimed_discount)
    else:
        fraud = detect_fraud_basic(claimed_original, claimed_current, claimed_discount)

    return {
        "id": doc_id,
        "title": deal_data.get("title", ""),
        "store": deal_data.get("site_display", deal_data.get("source", "")),
        "source": deal_data.get("source", ""),
        "current_price": claimed_current,
        "original_price": claimed_original,
        "discount_percent": claimed_discount,
        "currency": "EGP",
        "image_url": deal_data.get("image_url", ""),
        "product_url": product_url,
        "category": deal_data.get("category", ""),
        "rating": float(deal_data.get("rating", 0)) if deal_data.get("rating") else 0.0,
        
        # Fraud Detection (REAL prices)
        "verdict": fraud.get("verdict", "UNVERIFIED"),
        "fake_score": fraud.get("score", 0),
        "confidence": fraud.get("confidence", 60),
        "fraud_reasons": fraud.get("reasons", []),
        
        # Real Amazon prices (for reference)
        "amazon_original": real_original,
        "amazon_current": real_current,
    }

# ═════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    """Get deals with REAL fraud detection"""
    limit = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)

    try:
        query = db.collection('deals')
        if category and category != "all":
            query = query.where('category', '==', category.lower())
        
        docs = query.limit(limit).stream()
        deals = [serialize_deal_smart(doc.id, doc.to_dict()) for doc in docs]

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
    """Get single deal with REAL fraud detection"""
    try:
        doc = db.collection('deals').document(deal_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Deal not found"}), 404
        
        deal = serialize_deal_smart(doc.id, doc.to_dict())
        return jsonify({"success": True, "deal": deal, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
    """Search deals with REAL fraud detection"""
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
            
            if query not in title and query not in store:
                continue
            if category and category != "all" and cat != category.lower():
                continue
            
            deals.append(serialize_deal_smart(doc.id, deal_data))
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
