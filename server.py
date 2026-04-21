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

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def extract_asin(url: str) -> str:
    match = re.search(r'/dp/([A-Z0-9]{10})', url or "")
    return match.group(1) if match else ""

# ═══════════════════════════════════════════════════
# FRAUD DETECTION — MATH ONLY, NO SCRAPING = FAST
# ═══════════════════════════════════════════════════

def detect_fraud(original: float, current: float, claimed_pct: int) -> dict:
    if current <= 0 or original <= 0:
        return {"verdict": "UNVERIFIED", "score": 0, "confidence": 20, "reasons": []}

    reasons = []
    score = 0
    confidence = 70  # base confidence

    # Rule 1 — Math check: does the claimed discount match the math?
    calculated_pct = round(((original - current) / original) * 100)
    diff = abs(claimed_pct - calculated_pct)
    if diff > 10:
        reasons.append(f"Math error: claimed {claimed_pct}% but calculated {calculated_pct}%")
        score += 40

    # Rule 2 — Original price inflated vs current
    ratio = original / current
    if ratio > 2.5:
        reasons.append(f"Original price inflated ({ratio:.1f}x the sale price)")
        score += 35
        confidence -= 10
    elif ratio > 2.0:
        reasons.append(f"Original price seems high ({ratio:.1f}x the sale price)")
        score += 20

    # Rule 3 — Discount too high
    if claimed_pct > 65:
        reasons.append(f"Very high discount: {claimed_pct}% (uncommon on Amazon Egypt)")
        score += 20

    # Rule 4 — No real discount (less than 5%)
    if claimed_pct < 5 and original != current:
        score += 10

    # Adjust confidence upward if data is consistent
    if diff <= 5:
        confidence += 10

    confidence = max(20, min(100, confidence))

    if score >= 60:
        verdict = "FAKE"
    elif score >= 35:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}


def serialize_deal(doc_id: str, d: dict) -> dict:
    original = float(d.get("original_price", 0))
    current = float(d.get("current_price", 0))
    discount = int(d.get("discount_percent", 0))
    fraud = detect_fraud(original, current, discount)

    return {
        "id": doc_id,
        "title": d.get("title", ""),
        "store": d.get("site_display", d.get("source", "")),
        "source": d.get("source", ""),
        "current_price": current,
        "original_price": original,
        "discount_percent": discount,
        "currency": "EGP",
        "image_url": d.get("image_url", ""),
        "product_url": d.get("product_url", ""),
        "category": d.get("category", ""),
        "rating": float(d.get("rating", 0)) if d.get("rating") else 0.0,
        "verdict": fraud["verdict"],
        "fake_score": fraud["score"],
        "confidence": fraud["confidence"],
        "fraud_reasons": fraud["reasons"],
    }


# ═══════════════════════════════════════════════════
# PRICE HISTORY — Safqa via ASIN
# ═══════════════════════════════════════════════════

def get_safqa_history(asin: str) -> dict:
    """Try to get Safqa price history for an Amazon ASIN."""
    if not asin:
        return {"found": False}
    try:
        # Safqa API endpoint (used by their browser extension)
        url = f"https://www.safqa.com/api/v2/products/{asin}?country=eg"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.amazon.eg/dp/{asin}",
            "Accept": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=8)

        if resp.status_code == 200:
            data = resp.json()
            prices_raw = data.get("prices", []) or data.get("price_history", [])
            prices = [float(p.get("price", 0) or p) for p in prices_raw if p]
            prices = [p for p in prices if p > 0]

            if prices:
                return {
                    "found": True,
                    "lowest": min(prices),
                    "highest": max(prices),
                    "source": "Safqa",
                }

        # Fallback: try Safqa search page scrape
        search_url = f"https://www.safqa.com/eg/product/{asin}"
        resp2 = requests.get(search_url, headers={"User-Agent": headers["User-Agent"]}, timeout=8)
        if resp2.status_code == 200:
            soup = BeautifulSoup(resp2.text, "html.parser")
            prices = []
            for el in soup.select("[data-price], .price-value, .chart-price"):
                try:
                    prices.append(float(el.get("data-price") or el.text.replace(",", "").strip()))
                except:
                    pass
            if prices:
                return {"found": True, "lowest": min(prices), "highest": max(prices), "source": "Safqa"}

    except Exception as e:
        print(f"Safqa error: {e}")

    return {"found": False}


def get_kanbkam_history(asin: str) -> dict:
    """Try Kanbkam as a fallback."""
    if not asin:
        return {"found": False}
    try:
        url = f"https://www.kanbkam.com/eg/en/api/products/{asin}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            prices = data.get("prices", [])
            if prices:
                vals = [float(p.get("price", 0)) for p in prices if p.get("price")]
                vals = [v for v in vals if v > 0]
                if vals:
                    return {"found": True, "lowest": min(vals), "highest": max(vals), "source": "Kanbkam"}
    except:
        pass
    return {"found": False}


# ═══════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    limit = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)
    try:
        query = db.collection('deals')
        if category and category != "all":
            query = query.where('category', '==', category.lower())
        docs = query.limit(limit).stream()
        deals = [serialize_deal(doc.id, doc.to_dict()) for doc in docs]
        return jsonify({"success": True, "count": len(deals), "deals": deals, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
    q = request.args.get('q', '').lower().strip()
    category = request.args.get('category', None)
    limit = request.args.get('limit', 50, type=int)
    if len(q) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400
    try:
        docs = db.collection('deals').limit(limit * 3).stream()
        deals = []
        for doc in docs:
            d = doc.to_dict()
            title = d.get('title', '').lower()
            store = d.get('site_display', d.get('source', '')).lower()
            cat = d.get('category', '').lower()
            if q not in title and q not in store:
                continue
            if category and category != "all" and cat != category.lower():
                continue
            deals.append(serialize_deal(doc.id, d))
            if len(deals) >= limit:
                break
        return jsonify({"success": True, "count": len(deals), "deals": deals, "query": q, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/categories', methods=['GET'])
def get_categories():
    try:
        cats = set()
        for doc in db.collection('deals').stream():
            c = doc.to_dict().get('category', '')
            if c:
                cats.add(c)
        return jsonify({"success": True, "categories": sorted(list(cats)), "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/price-history', methods=['GET'])
def price_history():
    """Lazy-loaded endpoint — only called from detail screen."""
    product_url = request.args.get('url', '').strip()
    if not product_url:
        return jsonify({"success": False, "found": False, "error": "Missing URL"}), 400

    asin = extract_asin(product_url)

    # Try Safqa first, then Kanbkam
    result = get_safqa_history(asin)
    if not result.get("found"):
        result = get_kanbkam_history(asin)

    return jsonify({
        "success": True,
        "found": result.get("found", False),
        "lowest": result.get("lowest", 0),
        "highest": result.get("highest", 0),
        "source": result.get("source", ""),
        "asin": asin,
        "timestamp": now_iso(),
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "Server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
