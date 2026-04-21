from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json, os, re, requests, time
from bs4 import BeautifulSoup
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    key_dict = json.loads(firebase_key_json)
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)
db = firestore.client()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def extract_asin(url: str) -> str:
    m = re.search(r'/dp/([A-Z0-9]{10})', url or "")
    return m.group(1) if m else ""

# ══════════════════════════════════════════════════════════════
# SAFQA PRICE HISTORY  (tries multiple endpoints + scrape)
# ══════════════════════════════════════════════════════════════
SAFQA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8",
    "Origin": "https://www.amazon.eg",
    "Referer": "https://www.amazon.eg/",
}

def _parse_prices_from_json(obj, depth=0) -> list:
    """Recursively extract all numbers that look like EGP prices."""
    prices = []
    if depth > 6:
        return prices
    if isinstance(obj, dict):
        for v in obj.values():
            prices += _parse_prices_from_json(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            prices += _parse_prices_from_json(item, depth + 1)
    elif isinstance(obj, (int, float)):
        v = float(obj)
        if 10 < v < 500_000:        # plausible EGP price
            prices.append(v)
    elif isinstance(obj, str):
        # extract numbers from strings like "1,500.00"
        for tok in re.findall(r'[\d,]+\.?\d*', obj):
            try:
                v = float(tok.replace(",", ""))
                if 10 < v < 500_000:
                    prices.append(v)
            except:
                pass
    return prices

def get_safqa_history(asin: str) -> dict:
    if not asin:
        return {"found": False, "lowest": 0, "highest": 0, "source": ""}

    endpoints = [
        f"https://www.safqa.com/api/v2/products/{asin}?country=eg",
        f"https://www.safqa.com/api/products/{asin}?country=eg",
        f"https://www.safqa.com/api/v1/history/{asin}?country=eg",
        f"https://www.safqa.com/product/{asin}?country=eg",
        f"https://api.safqa.com/products/{asin}?country=eg",
    ]

    for url in endpoints:
        try:
            r = requests.get(url, headers=SAFQA_HEADERS, timeout=8)
            if r.status_code == 200:
                ct = r.headers.get("Content-Type", "")
                if "json" in ct:
                    data = r.json()
                    prices = _parse_prices_from_json(data)
                    if prices:
                        return {
                            "found": True,
                            "lowest": min(prices),
                            "highest": max(prices),
                            "source": "Safqa",
                        }
        except:
            pass

    # Scrape Safqa page directly
    try:
        page_url = f"https://www.safqa.com/eg/product/{asin}"
        r = requests.get(page_url, headers=SAFQA_HEADERS, timeout=10)
        if r.status_code == 200:
            # Look for JSON blobs in script tags
            soup = BeautifulSoup(r.text, "html.parser")
            for script in soup.find_all("script"):
                txt = script.string or ""
                if "price" in txt.lower() and len(txt) < 100_000:
                    try:
                        # Extract JSON objects from script
                        for match in re.finditer(r'\{[^{}]{20,}\}', txt):
                            try:
                                obj = json.loads(match.group())
                                prices = _parse_prices_from_json(obj)
                                if len(prices) >= 2:
                                    return {
                                        "found": True,
                                        "lowest": min(prices),
                                        "highest": max(prices),
                                        "source": "Safqa",
                                    }
                            except:
                                pass
                    except:
                        pass

            # Look for visible price text elements
            prices = []
            for el in soup.select(".price, [data-price], .chart-value, .history-price, span[class*='price']"):
                txt = el.get("data-price") or el.text
                for tok in re.findall(r'[\d,]+\.?\d*', txt):
                    try:
                        v = float(tok.replace(",", ""))
                        if 10 < v < 500_000:
                            prices.append(v)
                    except:
                        pass
            if prices:
                return {"found": True, "lowest": min(prices), "highest": max(prices), "source": "Safqa"}
    except Exception as e:
        print(f"Safqa scrape error: {e}")

    return {"found": False, "lowest": 0, "highest": 0, "source": ""}


def get_kanbkam_history(asin: str) -> dict:
    if not asin:
        return {"found": False, "lowest": 0, "highest": 0, "source": ""}
    urls = [
        f"https://www.kanbkam.com/eg/en/api/products/{asin}",
        f"https://www.kanbkam.com/api/v1/products/{asin}?country=eg",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": SAFQA_HEADERS["User-Agent"]}, timeout=8)
            if r.status_code == 200:
                prices = _parse_prices_from_json(r.json())
                if prices:
                    return {"found": True, "lowest": min(prices), "highest": max(prices), "source": "Kanbkam"}
        except:
            pass
    return {"found": False, "lowest": 0, "highest": 0, "source": ""}


# ══════════════════════════════════════════════════════════════
# FRAUD DETECTION
# Two modes:
#   A) With Safqa data  — compare claimed original vs safqa highest
#   B) Without Safqa    — compare math only
# ══════════════════════════════════════════════════════════════

def detect_fraud_with_history(
    claimed_original: float, claimed_current: float, claimed_pct: int,
    safqa_lowest: float, safqa_highest: float
) -> dict:
    reasons = []
    score = 0
    confidence = 90   # high confidence when we have history

    if claimed_current <= 0:
        return {"verdict": "UNVERIFIED", "score": 0, "confidence": 20, "reasons": []}

    # ── Rule 1 (CRITICAL): Claimed original vs Safqa highest-ever
    if safqa_highest > 0 and claimed_original > safqa_highest * 1.15:
        inflation = round((claimed_original - safqa_highest) / safqa_highest * 100)
        reasons.append(
            f"Original price NEVER reached {claimed_original:.0f} EGP — "
            f"highest ever was {safqa_highest:.0f} EGP ({inflation}% inflated)"
        )
        score += 50

    # ── Rule 2: Real discount vs claimed discount (using Safqa highest as true original)
    if safqa_highest > 0 and claimed_current > 0:
        real_pct = round((safqa_highest - claimed_current) / safqa_highest * 100)
        diff = claimed_pct - real_pct
        if diff > 10:
            reasons.append(
                f"Discount exaggerated: claimed {claimed_pct}% but real discount is {real_pct}%"
            )
            score += 35

    # ── Rule 3: Current price is at or above safqa highest (no real discount)
    if safqa_highest > 0 and claimed_current >= safqa_highest * 0.95:
        reasons.append(
            f"No real discount: current price ({claimed_current:.0f}) equals the all-time high ({safqa_highest:.0f})"
        )
        score += 40

    # ── Rule 4: Math check (claimed_pct vs calculated)
    if claimed_original > 0:
        calc_pct = round((claimed_original - claimed_current) / claimed_original * 100)
        if abs(claimed_pct - calc_pct) > 10:
            reasons.append(f"Math mismatch: claimed {claimed_pct}% but calculated {calc_pct}%")
            score += 30

    if score >= 60:
        verdict = "FAKE"
    elif score >= 35:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}


def detect_fraud_basic(claimed_original: float, claimed_current: float, claimed_pct: int) -> dict:
    """Fallback when no Safqa data."""
    reasons = []
    score = 0
    confidence = 60

    if claimed_current <= 0 or claimed_original <= 0:
        return {"verdict": "UNVERIFIED", "score": 0, "confidence": 20, "reasons": []}

    calc_pct = round((claimed_original - claimed_current) / claimed_original * 100)
    if abs(claimed_pct - calc_pct) > 10:
        reasons.append(f"Math mismatch: claimed {claimed_pct}% but calculated {calc_pct}%")
        score += 40

    ratio = claimed_original / claimed_current
    if ratio > 2.5:
        reasons.append(f"Original price inflated: {ratio:.1f}× the sale price")
        score += 35
        confidence -= 10
    elif ratio > 2.0:
        reasons.append(f"Original price seems high: {ratio:.1f}× the sale price")
        score += 20

    if claimed_pct > 65:
        reasons.append(f"Very high discount: {claimed_pct}%")
        score += 20

    confidence = max(20, min(100, confidence))

    if score >= 60:
        verdict = "FAKE"
    elif score >= 35:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}


# ══════════════════════════════════════════════════════════════
# SERIALISE
# ══════════════════════════════════════════════════════════════

def serialize_deal_fast(doc_id: str, d: dict) -> dict:
    """Fast serialisation — no Safqa fetch. Used for /deals list."""
    original = float(d.get("original_price", 0))
    current  = float(d.get("current_price", 0))
    discount = int(d.get("discount_percent", 0))
    fraud    = detect_fraud_basic(original, current, discount)
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


# ══════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    limit    = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)
    try:
        q = db.collection('deals')
        if category and category != "all":
            q = q.where('category', '==', category.lower())
        docs  = q.limit(limit).stream()
        deals = [serialize_deal_fast(doc.id, doc.to_dict()) for doc in docs]
        return jsonify({"success": True, "count": len(deals), "deals": deals, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
    q_str    = request.args.get('q', '').lower().strip()
    category = request.args.get('category', None)
    limit    = request.args.get('limit', 50, type=int)
    if len(q_str) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400
    try:
        docs  = db.collection('deals').limit(limit * 3).stream()
        deals = []
        for doc in docs:
            d     = doc.to_dict()
            title = d.get('title', '').lower()
            store = d.get('site_display', d.get('source', '')).lower()
            cat   = d.get('category', '').lower()
            if q_str not in title and q_str not in store:
                continue
            if category and category != "all" and cat != category.lower():
                continue
            deals.append(serialize_deal_fast(doc.id, d))
            if len(deals) >= limit:
                break
        return jsonify({"success": True, "count": len(deals), "deals": deals, "query": q_str, "timestamp": now_iso()})
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
    """
    Called LAZILY from the detail screen.
    Returns Safqa/Kanbkam history AND enhanced fraud verdict.
    """
    product_url      = request.args.get('url', '').strip()
    claimed_original = request.args.get('original', 0, type=float)
    claimed_current  = request.args.get('current', 0, type=float)
    claimed_pct      = request.args.get('discount', 0, type=int)

    if not product_url:
        return jsonify({"success": False, "found": False, "error": "Missing URL"}), 400

    asin = extract_asin(product_url)

    # Try Safqa → then Kanbkam
    history = get_safqa_history(asin)
    if not history.get("found"):
        history = get_kanbkam_history(asin)

    # Enhanced fraud verdict if we have history
    if history.get("found") and claimed_original > 0:
        fraud = detect_fraud_with_history(
            claimed_original, claimed_current, claimed_pct,
            history["lowest"], history["highest"]
        )
    else:
        fraud = None   # app keeps the basic verdict

    resp = {
        "success": True,
        "found":   history.get("found", False),
        "lowest":  history.get("lowest", 0),
        "highest": history.get("highest", 0),
        "source":  history.get("source", ""),
        "asin":    asin,
        "timestamp": now_iso(),
    }
    if fraud:
        resp["enhanced_verdict"]   = fraud["verdict"]
        resp["enhanced_score"]     = fraud["score"]
        resp["enhanced_confidence"] = fraud["confidence"]
        resp["enhanced_reasons"]   = fraud["reasons"]

    return jsonify(resp)


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
