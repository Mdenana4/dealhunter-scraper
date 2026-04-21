from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json, os, re, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

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
# AMAZON CURRENT PRICE SCRAPER
# Simple: only get the current price to detect expired deals
# ══════════════════════════════════════════════════════════════
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

def get_amazon_current_price(product_url: str) -> float:
    """Scrape current price from Amazon product page."""
    if not product_url or "amazon" not in product_url.lower():
        return 0.0
    try:
        resp = requests.get(product_url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return 0.0
        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 1: apexPriceToPay (most reliable)
        el = soup.find("span", {"id": "apexPriceToPay"})
        if not el:
            el = soup.find("span", {"id": "priceblock_ourprice"})
        if not el:
            el = soup.find("span", {"id": "priceblock_dealprice"})
        if not el:
            el = soup.find("span", class_=re.compile(r"a-price-whole"))

        if el:
            text = re.sub(r'[^\d,.]', '', el.text.replace("\u00a0", ""))
            # Handle formats like "1,500" or "1500"
            clean = text.replace(",", "")
            try:
                val = float(clean)
                if 10 < val < 500_000:
                    return val
            except:
                pass

        # Strategy 2: search all spans for price pattern
        for span in soup.find_all("span", class_=re.compile(r"a-price")):
            text = span.get_text(strip=True)
            m = re.search(r'EGP\s*([\d,]+)', text)
            if m:
                try:
                    val = float(m.group(1).replace(",", ""))
                    if 10 < val < 500_000:
                        return val
                except:
                    pass

        return 0.0
    except Exception as e:
        print(f"Amazon scrape error: {e}")
        return 0.0

# ══════════════════════════════════════════════════════════════
# FRAUD DETECTION — MATH BASED (fast, no network)
# ══════════════════════════════════════════════════════════════
def detect_fraud_math(original: float, current: float, claimed_pct: int) -> dict:
    if current <= 0 or original <= 0:
        return {"verdict": "UNVERIFIED", "score": 0, "confidence": 20, "reasons": []}

    reasons = []
    score   = 0
    confidence = 65

    # Rule 1: Math check
    calc_pct = round((original - current) / original * 100)
    diff = abs(claimed_pct - calc_pct)
    if diff > 10:
        reasons.append(f"Math error: claimed {claimed_pct}% but price math gives {calc_pct}%")
        score += 45

    # Rule 2: Ratio check
    ratio = original / current
    if ratio > 3.0:
        reasons.append(f"Extreme price inflation: original is {ratio:.1f}× the sale price")
        score += 40
        confidence -= 15
    elif ratio > 2.0:
        reasons.append(f"High ratio: original is {ratio:.1f}× the sale price")
        score += 25

    # Rule 3: Extreme discount
    if claimed_pct > 70:
        reasons.append(f"Extremely high discount: {claimed_pct}%")
        score += 20

    confidence = max(20, min(100, confidence))

    if score >= 60:
        verdict = "FAKE"
    elif score >= 30:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}


def deal_status(deal_data: dict) -> dict:
    """
    Check if a deal is still active based on:
    1. Created/updated timestamp in Firebase
    2. (On detail page) by comparing stored sale price vs live Amazon price
    """
    created_at = deal_data.get("created_at") or deal_data.get("timestamp") or ""
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                # Firestore timestamp
                dt = created_at.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days > 7:
                return {"stale": True, "age_days": age_days,
                        "warning": f"Deal added {age_days} days ago — price may have changed"}
        except:
            pass
    return {"stale": False, "age_days": 0, "warning": ""}


def serialize_deal(doc_id: str, d: dict) -> dict:
    original = float(d.get("original_price", 0))
    current  = float(d.get("current_price", 0))
    discount = int(d.get("discount_percent", 0))
    fraud    = detect_fraud_math(original, current, discount)
    status   = deal_status(d)

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
        # Stale deal warning
        "stale": status["stale"],
        "stale_warning": status["warning"],
    }


# ══════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    limit    = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)
    try:
        q    = db.collection('deals')
        if category and category != "all":
            q = q.where('category', '==', category.lower())
        docs  = q.limit(limit).stream()
        deals = [serialize_deal(doc.id, doc.to_dict()) for doc in docs]
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
            deals.append(serialize_deal(doc.id, d))
            if len(deals) >= limit:
                break
        return jsonify({"success": True, "count": len(deals), "deals": deals, "query": q_str})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/categories', methods=['GET'])
def get_categories():
    try:
        cats = set()
        for doc in db.collection('deals').stream():
            c = doc.to_dict().get('category', '')
            if c: cats.add(c)
        return jsonify({"success": True, "categories": sorted(list(cats))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/price-history', methods=['GET'])
def price_history():
    """
    Lazy-loaded on detail screen.
    1. Scrapes Amazon for CURRENT price → detect if deal expired
    2. Tries Keepa public data (no auth needed for basic info)
    """
    product_url      = request.args.get('url', '').strip()
    stored_sale      = request.args.get('current', 0, type=float)
    stored_original  = request.args.get('original', 0, type=float)
    claimed_discount = request.args.get('discount', 0, type=int)

    if not product_url:
        return jsonify({"success": False, "error": "Missing URL"}), 400

    asin = extract_asin(product_url)

    # Get current Amazon price
    amazon_current = get_amazon_current_price(product_url)

    deal_expired = False
    price_changed = False
    price_change_msg = ""

    if amazon_current > 0 and stored_sale > 0:
        diff_pct = abs(amazon_current - stored_sale) / stored_sale * 100
        if amazon_current > stored_sale * 1.10:
            deal_expired = True
            price_change_msg = (
                f"Price rose from EGP {stored_sale:.0f} → EGP {amazon_current:.0f}. "
                f"Deal appears to have EXPIRED."
            )
        elif amazon_current < stored_sale * 0.90:
            price_changed = True
            price_change_msg = (
                f"Price dropped further: EGP {stored_sale:.0f} → EGP {amazon_current:.0f}. "
                f"Better deal now!"
            )

    return jsonify({
        "success": True,
        "found": amazon_current > 0,
        "amazon_current": amazon_current,
        "stored_sale": stored_sale,
        "deal_expired": deal_expired,
        "price_changed": price_changed,
        "price_change_msg": price_change_msg,
        # No Safqa (requires private API) — honest about limitation
        "history_source": "Amazon (live)",
        "lowest": 0,    # would need Safqa/Keepa API
        "highest": 0,
        "source": "Amazon live price only",
        "note": "Full price history requires Safqa API access (browser extension only)",
        "timestamp": now_iso(),
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.errorhandler(404)
def not_found(e): return jsonify({"success": False, "error": "Not found"}), 404
@app.errorhandler(500)
def server_error(e): return jsonify({"success": False, "error": "Server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
