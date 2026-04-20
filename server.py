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

# ─── SHARED HEADERS ───
SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def serialize_deal(doc_id: str, deal_data: dict) -> dict:
    """Convert Firestore deal doc to API response dict"""
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
        "verdict": deal_data.get("fake_verdict", "UNVERIFIED"),
        "verdict_ar": deal_data.get("fake_verdict_ar", ""),
        "fake_emoji": deal_data.get("fake_emoji", "❓"),
        "fake_score": int(deal_data.get("fake_score", 50)),
        "lowest_price": float(deal_data.get("lowest_price_ever", 0)),
        "highest_price": float(deal_data.get("highest_price_ever", 0)),
        "suggested_wait_price": float(deal_data.get("suggested_wait_price", 0)),
        "rule_a_triggered": deal_data.get("rule_a", False),
        "rule_b_triggered": deal_data.get("rule_b", False),
        "source_used": deal_data.get("source_used", ""),
    }


# ─────────────────────────────────────────────────────
# PRICE HISTORY HELPERS
# ─────────────────────────────────────────────────────

def extract_asin(url: str) -> str:
    """Extract Amazon ASIN from product URL"""
    match = re.search(r'/dp/([A-Z0-9]{10})', url)
    if match:
        return match.group(1)
    match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
    if match:
        return match.group(1)
    return ""

def is_future_date(date_str: str) -> bool:
    """Check if a date string is in the future"""
    try:
        today = datetime.now(timezone.utc).date()
        # Support formats: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                return parsed > today
            except ValueError:
                continue
    except Exception:
        pass
    return False

def flag_suspicious(history: list) -> dict:
    """
    Detect suspicious patterns in price history.
    Returns a dict with is_suspicious flag and reasons list.
    """
    reasons = []

    if not history:
        return {"is_suspicious": False, "reasons": []}

    # Check for future dates
    future_entries = [e for e in history if is_future_date(e.get("date", ""))]
    if future_entries:
        reasons.append(f"Contains {len(future_entries)} future date(s) — data may be fabricated")

    # Only 1 data point — can't call it a trend
    if len(history) == 1:
        reasons.append("Only one price point found — insufficient history to verify discount")

    # Impossible price spikes (>300% increase in one step)
    for i in range(1, len(history)):
        prev = history[i - 1].get("price", 0)
        curr = history[i].get("price", 0)
        if prev > 0 and curr > 0:
            change_pct = abs((curr - prev) / prev) * 100
            if change_pct > 300:
                reasons.append(
                    f"Suspicious price jump: {prev} → {curr} "
                    f"({change_pct:.0f}% change on {history[i].get('date', '?')})"
                )

    return {
        "is_suspicious": len(reasons) > 0,
        "reasons": reasons
    }

def get_safqa_price_history(product_url: str) -> dict:
    """
    Fetch price history from Safqa.com for a given Amazon Egypt product URL.
    Returns: { found: bool, history: [...], source_url: str }
    """
    asin = extract_asin(product_url)
    if not asin:
        return {"found": False, "history": [], "source_url": ""}

    # Safqa search URL
    search_url = f"https://www.safqa.com/search?q={asin}&country=eg"
    source_url = search_url

    try:
        resp = requests.get(search_url, headers=SCRAPE_HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"found": False, "history": [], "source_url": source_url}

        soup = BeautifulSoup(resp.text, "lxml")

        # Find the product link that matches the ASIN
        product_link = None
        for a in soup.find_all("a", href=True):
            if asin in a["href"]:
                product_link = a["href"]
                break

        if not product_link:
            return {"found": False, "history": [], "source_url": source_url}

        # Ensure absolute URL
        if product_link.startswith("/"):
            product_link = "https://www.safqa.com" + product_link

        source_url = product_link

        # Fetch the product detail page on Safqa
        detail_resp = requests.get(product_link, headers=SCRAPE_HEADERS, timeout=10)
        if detail_resp.status_code != 200:
            return {"found": False, "history": [], "source_url": source_url}

        detail_soup = BeautifulSoup(detail_resp.text, "lxml")

        # Parse price history table/chart data
        history = []

        # Look for price history rows (adjust selectors to match Safqa's actual HTML)
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

        return {
            "found": len(history) > 0,
            "history": history,
            "source_url": source_url
        }

    except requests.exceptions.Timeout:
        print("⏱️ Safqa request timed out")
        return {"found": False, "history": [], "source_url": source_url}
    except Exception as e:
        print(f"❌ Safqa scrape error: {e}")
        return {"found": False, "history": [], "source_url": source_url}

def get_kanbkam_price_history(product_url: str) -> dict:
    """
    Fetch price history from Kanbkam.com for a given Amazon Egypt product URL.
    Returns: { found: bool, history: [...], source_url: str }
    """
    asin = extract_asin(product_url)
    if not asin:
        return {"found": False, "history": [], "source_url": ""}

    # Kanbkam product URL format for Egypt
    kanbkam_url = f"https://www.kanbkam.com/eg/en/search?q={asin}"
    source_url = kanbkam_url

    try:
        resp = requests.get(kanbkam_url, headers=SCRAPE_HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"found": False, "history": [], "source_url": source_url}

        soup = BeautifulSoup(resp.text, "lxml")

        # Find the product link that matches our ASIN
        product_link = None
        for a in soup.find_all("a", href=True):
            if asin in a["href"]:
                product_link = a["href"]
                break

        if not product_link:
            return {"found": False, "history": [], "source_url": source_url}

        if product_link.startswith("/"):
            product_link = "https://www.kanbkam.com" + product_link

        source_url = product_link

        # Fetch product detail page
        detail_resp = requests.get(product_link, headers=SCRAPE_HEADERS, timeout=10)
        if detail_resp.status_code != 200:
            return {"found": False, "history": [], "source_url": source_url}

        detail_soup = BeautifulSoup(detail_resp.text, "lxml")

        # Try to extract chart data from inline JSON (Kanbkam often embeds it)
        history = []
        scripts = detail_soup.find_all("script")
        for script in scripts:
            script_text = script.string or ""
            # Look for arrays of [timestamp, price] pairs
            json_match = re.search(
                r'"priceHistory"\s*:\s*(\[.*?\])', script_text, re.DOTALL
            )
            if not json_match:
                json_match = re.search(
                    r'data\s*:\s*(\[\s*\[\d+,[\d.]+\].*?\])', script_text, re.DOTALL
                )
            if json_match:
                try:
                    raw = json.loads(json_match.group(1))
                    for entry in raw:
                        # Entry can be [unix_timestamp, price] or {"date": ..., "price": ...}
                        if isinstance(entry, list) and len(entry) == 2:
                            ts, price = entry
                            date_str = datetime.utcfromtimestamp(ts / 1000).strftime("%d-%m-%Y")
                            history.append({"date": date_str, "price": float(price)})
                        elif isinstance(entry, dict):
                            history.append({
                                "date": entry.get("date", ""),
                                "price": float(entry.get("price", 0))
                            })
                    if history:
                        break
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

        # Fallback: parse HTML table if no JSON found
        if not history:
            rows = detail_soup.select(
                "table tr, .price-table tr, .history-row, [class*='price-row']"
            )
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

        return {
            "found": len(history) > 0,
            "history": history,
            "source_url": source_url
        }

    except requests.exceptions.Timeout:
        print("⏱️ Kanbkam request timed out")
        return {"found": False, "history": [], "source_url": source_url}
    except Exception as e:
        print(f"❌ Kanbkam scrape error: {e}")
        return {"found": False, "history": [], "source_url": source_url}

def build_price_history_summary(history: list) -> dict:
    """
    From a list of {date, price} entries, compute:
    lowest, highest, current (last), and full change timeline.
    """
    if not history:
        return {}

    prices = [e["price"] for e in history]
    lowest = min(prices)
    highest = max(prices)
    current = history[-1]["price"]

    # Build human-readable change log
    changes = []
    for i in range(1, len(history)):
        prev = history[i - 1]
        curr = history[i]
        direction = "📈 increased" if curr["price"] > prev["price"] else "📉 dropped"
        changes.append({
            "from_date": prev["date"],
            "to_date": curr["date"],
            "from_price": prev["price"],
            "to_price": curr["price"],
            "direction": direction,
        })

    return {
        "lowest_ever": lowest,
        "highest_ever": highest,
        "current_price": current,
        "total_data_points": len(history),
        "changes": changes,
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


# ─────────────────────────────────────────────────────
# ✅ NEW: PRICE HISTORY ENDPOINT
# ─────────────────────────────────────────────────────

@app.route('/api/v1/price-history', methods=['GET'])
def get_price_history():
    """
    Fetch price history for a product URL.
    Priority: Safqa first → Kanbkam fallback → No data.

    Query params:
      - url: Amazon Egypt product URL (required)

    Response:
      {
        success: true,
        source: "safqa" | "kanbkam" | "none",
        source_url: "https://...",
        found: true | false,
        is_suspicious: false,
        suspicious_reasons: [],
        summary: { lowest_ever, highest_ever, current_price, changes: [...] },
        history: [ { date, price }, ... ],
        message: "No price history available" (only when found=false)
      }
    """
    product_url = request.args.get('url', '').strip()

    if not product_url:
        return jsonify({"success": False, "error": "Missing 'url' parameter"}), 400

    asin = extract_asin(product_url)
    if not asin:
        return jsonify({
            "success": False,
            "error": "Could not extract ASIN from URL. Make sure it's a valid Amazon product URL."
        }), 400

    # ── Step 1: Try Safqa ──
    print(f"🔍 Checking Safqa for ASIN: {asin}")
    safqa_result = get_safqa_price_history(product_url)

    if safqa_result["found"]:
        history = safqa_result["history"]
        suspicion = flag_suspicious(history)
        summary = build_price_history_summary(history)
        print(f"✅ Safqa returned {len(history)} data points")
        return jsonify({
            "success": True,
            "source": "safqa",
            "source_url": safqa_result["source_url"],
            "found": True,
            "is_suspicious": suspicion["is_suspicious"],
            "suspicious_reasons": suspicion["reasons"],
            "summary": summary,
            "history": history,
            "timestamp": now_iso()
        })

    # ── Step 2: Try Kanbkam ──
    print(f"⚠️ Safqa has no data — trying Kanbkam for ASIN: {asin}")
    kanbkam_result = get_kanbkam_price_history(product_url)

    if kanbkam_result["found"]:
        history = kanbkam_result["history"]
        suspicion = flag_suspicious(history)
        summary = build_price_history_summary(history)
        print(f"✅ Kanbkam returned {len(history)} data points")
        return jsonify({
            "success": True,
            "source": "kanbkam",
            "source_url": kanbkam_result["source_url"],
            "found": True,
            "is_suspicious": suspicion["is_suspicious"],
            "suspicious_reasons": suspicion["reasons"],
            "summary": summary,
            "history": history,
            "timestamp": now_iso()
        })

    # ── Step 3: Neither source has data ──
    print(f"❌ No price history found on either source for ASIN: {asin}")
    return jsonify({
        "success": True,
        "source": "none",
        "source_url": "",
        "found": False,
        "is_suspicious": False,
        "suspicious_reasons": [],
        "summary": {},
        "history": [],
        "message": "No price history available for this product on Safqa or Kanbkam.",
        "timestamp": now_iso()
    })


@app.route('/health', methods=['GET'])
def health():
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
    
