from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
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

def serialize_deal(doc_id: str, deal_data: dict) -> dict:
    """Convert Firestore deal doc to API response dict"""
    return {
        # Basic fields
        "id": doc_id,
        "title": deal_data.get("title", ""),
        "store": deal_data.get("site_display", deal_data.get("source", "")),
        "source": deal_data.get("source", ""),
        
        # Pricing
        "current_price": float(deal_data.get("current_price", 0)),
        "original_price": float(deal_data.get("original_price", 0)),
        "discount_percent": int(deal_data.get("discount_percent", 0)),
        "currency": "EGP",
        
        # Images & URLs
        "image_url": deal_data.get("image_url", ""),
        "product_url": deal_data.get("product_url", ""),
        
        # Category & ratings
        "category": deal_data.get("category", ""),
        "rating": float(deal_data.get("rating", 0)) if deal_data.get("rating") else 0.0,
        
        # ✅ KANBKAM/SAFQA VERDICT FIELDS (these were missing!)
        "verdict": deal_data.get("fake_verdict", "UNVERIFIED"),
        "verdict_ar": deal_data.get("fake_verdict_ar", ""),
        "fake_emoji": deal_data.get("fake_emoji", "❓"),
        "fake_score": int(deal_data.get("fake_score", 50)),
        
        # ✅ PRICE HISTORY FIELDS
        "lowest_price": float(deal_data.get("lowest_price_ever", 0)),
        "highest_price": float(deal_data.get("highest_price_ever", 0)),
        "suggested_wait_price": float(deal_data.get("suggested_wait_price", 0)),
        
        # Additional metadata
        "rule_a_triggered": deal_data.get("rule_a", False),
        "rule_b_triggered": deal_data.get("rule_b", False),
        "source_used": deal_data.get("source_used", ""),
    }

# ─────────────────────────────────────────────────────
# PUBLIC API ENDPOINTS
# ─────────────────────────────────────────────────────

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
        
        return jsonify({
            "success": True,
            "deal": deal,
            "timestamp": now_iso()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
    """Search deals by query (client-side filtering)"""
    query = request.args.get('q', '').lower()
    limit = request.args.get('limit', 50, type=int)
    
    if not query or len(query) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400
    
    try:
        docs = db.collection('deals').limit(limit * 2).stream()  # Get more, filter in Python
        deals = []
        
        for doc in docs:
            deal_data = doc.to_dict()
            title = deal_data.get('title', '').lower()
            store = deal_data.get('site_display', '').lower()
            category = deal_data.get('category', '').lower()
            
            # Match query in any field
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
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "dealhunter-api"}), 200

# ─────────────────────────────────────────────────────
# ERROR HANDLERS
# ─────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
