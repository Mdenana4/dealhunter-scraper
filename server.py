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

# Firebase initialization
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ═════════════════════════════════════════════════════════════
# ✅ IMPROVED FRAUD DETECTION WITH PRICE HISTORY INTEGRATION
# ═════════════════════════════════════════════════════════════

def detect_fake_discount(deal_data: dict, price_history: dict) -> dict:
    """
    Detect fake discounts using:
    1. Price inflation analysis
    2. Discount math verification
    3. Historical price comparison
    """
    reasons = []
    score = 0

    original = float(deal_data.get("original_price", 0))
    current = float(deal_data.get("current_price", 0))
    claimed_discount = int(deal_data.get("discount_percent", 0))

    # ── Get price history data
    lowest_ever = float(price_history.get("lowest_ever", 0))
    highest_ever = float(price_history.get("highest_ever", 0))
    has_history = lowest_ever > 0 or highest_ever > 0

    # ── Rule 1: Original price inflated above historical max
    if has_history and original > 0 and highest_ever > 0:
        inflation_ratio = original / highest_ever
        if inflation_ratio > 1.1:  # >10% above historical high
            reasons.append(
                f"Original price inflated: EGP {original:.0f} vs historical max EGP {highest_ever:.0f}"
            )
            score += 40

    # ── Rule 2: Calculate real discount vs claimed discount
    if has_history and highest_ever > 0 and current > 0:
        real_discount = ((highest_ever - current) / highest_ever) * 100
        if claimed_discount > real_discount + 10:  # Claimed is 10%+ higher than real
            reasons.append(
                f"Discount exaggerated: Claimed {claimed_discount}% but real savings only {real_discount:.0f}%"
            )
            score += 35

    # ── Rule 3: Discount math check (if no history)
    if not has_history and original > 0 and current > 0:
        calc_discount = ((original - current) / original) * 100
        if abs(calc_discount - claimed_discount) > 5:
            reasons.append(
                f"Math error: Claimed {claimed_discount}% but {calc_discount:.0f}% based on prices"
            )
            score += 25

    # ── Rule 4: Suspiciously high discount (>60%)
    if claimed_discount > 60:
        reasons.append(
            f"Unrealistic discount: {claimed_discount}% (real discounts rarely exceed 50%)"
        )
        score += 20

    # ── Rule 5: No price history = low confidence
    if not has_history:
        reasons.append("No price history available to verify authenticity")
        score += 15

    # ── Rule 6: Current price below historical low is suspicious
    if has_history and lowest_ever > 0 and current < lowest_ever * 0.95:
        reasons.append(
            f"Price unusually low: EGP {current:.0f} vs historical low EGP {lowest_ever:.0f}"
        )
        score += 15

    # ── Determine verdict based on score
    if score >= 60:
        verdict = "FAKE"
    elif score >= 35:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    # ── Calculate confidence (inverse of missing data)
    confidence = 50  # Base confidence
    if has_history:
        confidence += 40  # +40 if we have history
    if claimed_discount <= 40:
        confidence += 10  # +10 if discount is reasonable

    confidence = min(confidence, 100)
    confidence = max(confidence, 0)

    return {
        "verdict": verdict,
        "fake_score": score,
        "fraud_reasons": reasons,
        "confidence": confidence
    }

def serialize_deal_with_history(doc_id: str, deal_data: dict, price_history: dict) -> dict:
    """Serialize deal with fraud detection and price history"""
    
    fraud_analysis = detect_fake_discount(deal_data, price_history)

    return {
        "id": doc_id,
        "title": deal_data.get("title", ""),
        "store": deal_data.get("site_display", deal_data.get("source", "")),
        "source": deal_data.get("source", ""),
        "current_price": float(deal_data.get("current_price", 0)),
        "original_price": float(deal_data.get("original_price", 0)),
        "discount_percent": int(deal_data.get("discount_percent", 0)),
        "currency": "EGP",
        "image_url": deal_data.get("image_url", ""),
        "product_url": deal_data.get("product_url", ""),
        "category": deal_data.get("category", ""),
        "rating": float(deal_data.get("rating", 0)) if deal_data.get("rating") else 0.0,
        
        # ✅ Fraud Detection
        "verdict": fraud_analysis.get("verdict", "UNVERIFIED"),
        "fake_score": fraud_analysis.get("fake_score", 50),
        "confidence": fraud_analysis.get("confidence", 0),
        "fraud_reasons": fraud_analysis.get("fraud_reasons", []),
        
        # ✅ Price History
        "lowest_price": float(price_history.get("lowest_ever", 0)),
        "highest_price": float(price_history.get("highest_ever", 0)),
        "suggested_wait_price": float(price_history.get("suggested_wait_price", 0)),
        "source_used": price_history.get("source_used", ""),
    }

# ═════════════════════════════════════════════════════════════
# PRICE HISTORY HELPERS
# ═════════════════════════════════════════════════════════════

def extract_asin(url: str) -> str:
    match = re.search(r'/dp/([A-Z0-9]{10})', url)
    if match:
        return match.group(1)
    match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
    if match:
        return match.group(1)
    return ""

def is_future_date(date_str: str) -> bool:
    try:
        today = datetime.now(timezone.utc).date()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                return parsed > today
            except ValueError:
                continue
    except:
        pass
    return False

def flag_suspicious(history: list) -> dict:
    reasons = []
    if not history:
        return {"is_suspicious": False, "reasons": []}

    future_entries = [e for e in history if is_future_date(e.get("date", ""))]
    if future_entries:
        reasons.append(f"Contains {len(future_entries)} future dates")

    if len(history) == 1:
        reasons.append("Only one data point - insufficient history")

    for i in range(1, len(history)):
        prev = history[i - 1].get("price", 0)
        curr = history[i].get("price", 0)
        if prev > 0 and curr > 0:
            change_pct = abs((curr - prev) / prev) * 100
            if change_pct > 300:
                reasons.append(f"Suspicious price jump: {change_pct:.0f}% on {history[i].get('date')}")

    return {"is_suspicious": len(reasons) > 0, "reasons": reasons}

def get_safqa_price_history(product_url: str) -> dict:
    asin = extract_asin(product_url)
    if not asin:
        return {"found": False, "history": [], "source_url": ""}

    try:
        search_url = f"https://www.safqa.com/search?q={asin}&country=eg"
        resp = requests.get(search_url, headers=SCRAPE_HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"found": False, "history": [], "source_url": search_url}

        soup = BeautifulSoup(resp.text, "lxml")
        product_link = None
        for a in soup.find_all("a", href=True):
            if asin in a["href"]:
                product_link = a["href"]
                break

        if not product_link:
            return {"found": False, "history": [], "source_url": search_url}

        if product_link.startswith("/"):
            product_link = "https://www.safqa.com" + product_link

        detail_resp = requests.get(product_link, headers=SCRAPE_HEADERS, timeout=10)
        if detail_resp.status_code != 200:
            return {"found": False, "history": [], "source_url": product_link}

        detail_soup = BeautifulSoup(detail_resp.text, "lxml")
        history = []
        rows = detail_soup.select("table.price-history tr, .price-history-row, [data-date]")

        for row in rows:
            date_el = row.select_one("[data-date], .date, td:first-child")
            price_el = row.select_one("[data-price], .price, td:last-child")
            if date_el and price_el:
                date_text = date_el.get_text(strip=True)
                price_text = re.sub(r"[^\d.]", "", price_el.get_text(strip=True))
                try:
                    price = float(price_text)
                    if price > 0 and date_text:
                        history.append({"date": date_text, "price": price})
                except ValueError:
                    continue

        return {"found": len(history) > 0, "history": history, "source_url": product_link}
    except:
        return {"found": False, "history": [], "source_url": ""}

def get_kanbkam_price_history(product_url: str) -> dict:
    asin = extract_asin(product_url)
    if not asin:
        return {"found": False, "history": [], "source_url": ""}

    try:
        kanbkam_url = f"https://www.kanbkam.com/eg/en/search?q={asin}"
        resp = requests.get(kanbkam_url, headers=SCRAPE_HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"found": False, "history": [], "source_url": kanbkam_url}

        soup = BeautifulSoup(resp.text, "lxml")
        product_link = None
        for a in soup.find_all("a", href=True):
            if asin in a["href"]:
                product_link = a["href"]
                break

        if not product_link:
            return {"found": False, "history": [], "source_url": kanbkam_url}

        if product_link.startswith("/"):
            product_link = "https://www.kanbkam.com" + product_link

        detail_resp = requests.get(product_link, headers=SCRAPE_HEADERS, timeout=10)
        if detail_resp.status_code != 200:
            return {"found": False, "history": [], "source_url": product_link}

        detail_soup = BeautifulSoup(detail_resp.text, "lxml")
        history = []
        rows = detail_soup.select("table tr, .price-table tr, .history-row")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                date_text = cells[0].get_text(strip=True)
                price_text = re.sub(r"[^\d.]", "", cells[1].get_text(strip=True))
                try:
                    price = float(price_text)
                    if price > 0 and date_text:
                        history.append({"date": date_text, "price": price})
                except ValueError:
                    continue

        return {"found": len(history) > 0, "history": history, "source_url": product_link}
    except:
        return {"found": False, "history": [], "source_url": ""}

def build_price_history_summary(history: list) -> dict:
    if not history:
        return {"lowest_ever": 0, "highest_ever": 0, "current_price": 0, "total_data_points": 0}

    prices = [e["price"] for e in history]
    return {
        "lowest_ever": min(prices),
        "highest_ever": max(prices),
        "current_price": history[-1]["price"],
        "total_data_points": len(history),
    }

# ═════════════════════════════════════════════════════════════
# PUBLIC API ENDPOINTS
# ═════════════════════════════════════════════════════════════

@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    limit = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)

    try:
        query = db.collection('deals')
        if category:
            query = query.where('category', '==', category.lower())
        docs = query.limit(limit).stream()
        deals = []
        
        for doc in docs:
            deal_data = doc.to_dict()
            # Get price history for this deal
            product_url = deal_data.get("product_url", "")
            
            price_history = {"lowest_ever": 0, "highest_ever": 0, "source_used": ""}
            
            if product_url:
                safqa_result = get_safqa_price_history(product_url)
                if safqa_result["found"]:
                    summary = build_price_history_summary(safqa_result["history"])
                    price_history = {**summary, "source_used": "Safqa"}
                else:
                    kanbkam_result = get_kanbkam_price_history(product_url)
                    if kanbkam_result["found"]:
                        summary = build_price_history_summary(kanbkam_result["history"])
                        price_history = {**summary, "source_used": "Kanbkam"}
            
            deal = serialize_deal_with_history(doc.id, deal_data, price_history)
            deals.append(deal)

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
    try:
        doc = db.collection('deals').document(deal_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Deal not found"}), 404
        
        deal_data = doc.to_dict()
        product_url = deal_data.get("product_url", "")
        price_history = {"lowest_ever": 0, "highest_ever": 0, "source_used": ""}
        
        if product_url:
            safqa_result = get_safqa_price_history(product_url)
            if safqa_result["found"]:
                summary = build_price_history_summary(safqa_result["history"])
                price_history = {**summary, "source_used": "Safqa"}
            else:
                kanbkam_result = get_kanbkam_price_history(product_url)
                if kanbkam_result["found"]:
                    summary = build_price_history_summary(kanbkam_result["history"])
                    price_history = {**summary, "source_used": "Kanbkam"}
        
        deal = serialize_deal_with_history(doc.id, deal_data, price_history)
        return jsonify({"success": True, "deal": deal, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/v1/deals/search', methods=['GET'])
def search_deals():
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
                product_url = deal_data.get("product_url", "")
                price_history = {"lowest_ever": 0, "highest_ever": 0, "source_used": ""}
                
                if product_url:
                    safqa_result = get_safqa_price_history(product_url)
                    if safqa_result["found"]:
                        summary = build_price_history_summary(safqa_result["history"])
                        price_history = {**summary, "source_used": "Safqa"}
                    else:
                        kanbkam_result = get_kanbkam_price_history(product_url)
                        if kanbkam_result["found"]:
                            summary = build_price_history_summary(kanbkam_result["history"])
                            price_history = {**summary, "source_used": "Kanbkam"}
                
                deal = serialize_deal_with_history(doc.id, deal_data, price_history)
                deals.append(deal)
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
    
