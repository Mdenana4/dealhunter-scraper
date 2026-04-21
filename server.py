from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json, os, re, requests, hashlib, base64, time
from datetime import datetime, timezone
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════
# FIREBASE
# ═══════════════════════════════════════════
firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    cred = credentials.Certificate(json.loads(firebase_key_json))
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized")
else:
    raise RuntimeError("FIREBASE_KEY_JSON not set!")

db = firestore.client()

# ═══════════════════════════════════════════
# SAFQA CONFIG  (from background.js)
# ═══════════════════════════════════════════
SAFQA_BASE   = "https://api.sfq.app/v1"
SAFQA_AES_KEY = "ee6uFer3jc6WuzbUGrhV"          # hardcoded in extension
SAFQA_HEADERS = {
    "X-joinsafqa": "joinsafqa-0.1.105",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# In-memory token store
_token = {"access": None, "refresh": None, "expires_at": 0}
# Shop key cache  { regex_pattern -> shopKey }
_shop_cache = {}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ═══════════════════════════════════════════
# AES  — CryptoJS.AES.encrypt(text, key) clone
# ═══════════════════════════════════════════
def _evp_bytes_to_key(password: bytes, salt: bytes, key_len: int, iv_len: int):
    """OpenSSL EVP_BytesToKey with MD5 (what CryptoJS uses)."""
    d, d_i = b"", b""
    while len(d) < key_len + iv_len:
        d_i = hashlib.md5(d_i + password + salt).digest()
        d += d_i
    return d[:key_len], d[key_len:key_len + iv_len]


def cryptojs_encrypt(plaintext: str) -> str:
    """
    Replicates:  CryptoJS.AES.encrypt(plaintext, SAFQA_AES_KEY).toString()
    Output is a Base64 string with the 'Salted__' OpenSSL header.
    """
    salt       = os.urandom(8)
    key, iv    = _evp_bytes_to_key(SAFQA_AES_KEY.encode(), salt, 32, 16)
    cipher     = AES.new(key, AES.MODE_CBC, iv)
    ct         = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(b"Salted__" + salt + ct).decode()

# ═══════════════════════════════════════════
# SAFQA AUTH
# ═══════════════════════════════════════════
def safqa_login() -> bool:
    email    = os.getenv("SAFQA_EMAIL", "")
    password = os.getenv("SAFQA_PASSWORD", "")
    if not email or not password:
        print("❌ SAFQA_EMAIL or SAFQA_PASSWORD not set")
        return False
    try:
        r = requests.post(
            f"{SAFQA_BASE}/auth/login",
            json={"email": email, "password": password},
            headers=SAFQA_HEADERS, timeout=12
        )
        print(f"Safqa login status: {r.status_code}")
        if r.status_code == 200:
            data   = r.json()
            tokens = (data.get("data") or {}).get("tokens") or {}
            _token["access"]     = tokens.get("accessToken")
            _token["refresh"]    = tokens.get("refreshToken")
            _token["expires_at"] = time.time() + 3000   # ~50 min
            print("✅ Safqa logged in")
            return True
        print(f"Safqa login failed: {r.text[:200]}")
    except Exception as e:
        print(f"Safqa login error: {e}")
    return False


def safqa_refresh() -> bool:
    if not _token["refresh"]:
        return safqa_login()
    try:
        r = requests.post(
            f"{SAFQA_BASE}/auth/refresh",
            headers={**SAFQA_HEADERS, "Authorization": f"Bearer {_token['refresh']}"},
            timeout=10
        )
        if r.status_code == 200:
            tokens = (r.json().get("data") or {}).get("tokens") or {}
            _token["access"]     = tokens.get("accessToken")
            _token["refresh"]    = tokens.get("refreshToken")
            _token["expires_at"] = time.time() + 3000
            return True
    except Exception as e:
        print(f"Safqa refresh error: {e}")
    return safqa_login()


def auth_headers() -> dict:
    """Return headers with a valid access token."""
    if not _token["access"] or time.time() > _token["expires_at"]:
        safqa_refresh()
    return {**SAFQA_HEADERS, "Authorization": f"Bearer {_token['access']}"}

# ═══════════════════════════════════════════
# SAFQA SHOP LIST  (find shopKey by URL)
# ═══════════════════════════════════════════
def _load_shops():
    global _shop_cache
    try:
        r = requests.get(f"{SAFQA_BASE}/shop/shop-list",
                         headers=auth_headers(), timeout=12)
        if r.status_code == 200:
            shops = r.json().get("data") or []
            for s in shops:
                key     = s.get("shopKey") or s.get("id") or ""
                pattern = s.get("regex_shop") or ""
                if key and pattern:
                    _shop_cache[pattern] = key
            print(f"✅ Loaded {len(_shop_cache)} Safqa shops")
    except Exception as e:
        print(f"Shop load error: {e}")


def get_shop_key(url: str) -> str:
    if not _shop_cache:
        _load_shops()
    for pattern, key in _shop_cache.items():
        try:
            if re.search(pattern, url):
                return key
        except:
            pass
    # Hard-coded fallback for Amazon Egypt
    if "amazon.eg" in url:
        return "amazon.eg"
    return ""

# ═══════════════════════════════════════════
# SAFQA PRICE HISTORY
# ═══════════════════════════════════════════
def get_safqa_history(product_url: str, current_price: float) -> dict:
    """
    Call /product/ssearch with encrypted payload.
    Returns { found, lowest, highest, prices[], source }
    """
    # Extract ASIN (Amazon) or product identifier
    asin_m = re.search(r'/dp/([A-Z0-9]{10})', product_url or "")
    if not asin_m:
        return {"found": False}

    asin      = asin_m.group(1)
    shop_key  = get_shop_key(product_url)
    offer_code = ""
    # Some Amazon URLs have offer codes after /ref=
    oc_m = re.search(r'[?&]th=(\w+)', product_url)
    if oc_m:
        offer_code = oc_m.group(1)

    payload_dict = {
        "ssin":         asin,
        "offerCode":    offer_code,
        "url":          product_url,
        "shopId":       shop_key,
        "currentPrice": current_price,
    }
    encrypted_d = cryptojs_encrypt(json.dumps(payload_dict))

    try:
        r = requests.post(
            f"{SAFQA_BASE}/product/ssearch",
            json={"d": encrypted_d},
            headers=auth_headers(),
            timeout=15
        )
        print(f"Safqa ssearch status: {r.status_code}  asin={asin}")

        if r.status_code == 401:
            # Token expired mid-request — refresh and retry once
            safqa_refresh()
            r = requests.post(
                f"{SAFQA_BASE}/product/ssearch",
                json={"d": encrypted_d},
                headers=auth_headers(),
                timeout=15
            )

        if r.status_code == 200:
            data   = r.json().get("data") or {}
            prices = data.get("prices") or []
            if prices:
                vals = [float(p.get("price", 0)) for p in prices if p.get("price")]
                vals = [v for v in vals if v > 0]
                if vals:
                    return {
                        "found":   True,
                        "lowest":  min(vals),
                        "highest": max(vals),
                        "prices":  prices,
                        "source":  "Safqa",
                    }
        else:
            print(f"Safqa ssearch error body: {r.text[:300]}")
    except Exception as e:
        print(f"Safqa ssearch exception: {e}")

    return {"found": False}

# ═══════════════════════════════════════════
# FRAUD DETECTION
# ═══════════════════════════════════════════
def detect_fraud_with_safqa(
    claimed_original: float,
    claimed_current: float,
    claimed_pct: int,
    safqa_lowest: float,
    safqa_highest: float,
) -> dict:
    reasons, score = [], 0
    confidence     = 92   # high — we have real history

    # Rule 1 ─ Claimed original NEVER reached in history
    if safqa_highest > 0 and claimed_original > safqa_highest * 1.10:
        inflation = round((claimed_original - safqa_highest) / safqa_highest * 100)
        reasons.append(
            f"Original price NEVER reached EGP {claimed_original:.0f} — "
            f"all-time high was EGP {safqa_highest:.0f} ({inflation}% inflated)"
        )
        score += 55

    # Rule 2 ─ No real discount (current ≥ highest)
    if safqa_highest > 0 and claimed_current >= safqa_highest * 0.95:
        reasons.append(
            f"No real discount — current price EGP {claimed_current:.0f} "
            f"equals the all-time high (EGP {safqa_highest:.0f})"
        )
        score += 45

    # Rule 3 ─ Exaggerated discount %
    if safqa_highest > 0 and claimed_current > 0:
        real_pct = round((safqa_highest - claimed_current) / safqa_highest * 100)
        diff     = claimed_pct - real_pct
        if diff > 10:
            reasons.append(
                f"Discount exaggerated: claimed {claimed_pct}% but real saving "
                f"vs history is {real_pct}%"
            )
            score += 30

    # Rule 4 ─ Price math check (no history needed)
    if claimed_original > 0:
        calc_pct = round((claimed_original - claimed_current) / claimed_original * 100)
        if abs(claimed_pct - calc_pct) > 10:
            reasons.append(
                f"Math mismatch: claimed {claimed_pct}% but price math gives {calc_pct}%"
            )
            score += 35

    if   score >= 60: verdict = "FAKE"
    elif score >= 35: verdict = "SUSPICIOUS"
    else:             verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}


def detect_fraud_basic(original: float, current: float, claimed_pct: int) -> dict:
    """Fallback when Safqa returns no data."""
    reasons, score = [], 0
    confidence     = 65

    if original > 0:
        calc_pct = round((original - current) / original * 100)
        if abs(claimed_pct - calc_pct) > 10:
            reasons.append(f"Math mismatch: claimed {claimed_pct}% but calculated {calc_pct}%")
            score += 40

    if current > 0 and original > 0:
        ratio = original / current
        if ratio > 3.0:
            reasons.append(f"Extreme inflation: original is {ratio:.1f}× the sale price")
            score += 40
            confidence -= 10
        elif ratio > 2.0:
            reasons.append(f"High ratio: original is {ratio:.1f}× the sale price")
            score += 20

    if claimed_pct > 70:
        reasons.append(f"Very high discount: {claimed_pct}%")
        score += 20

    confidence = max(20, min(100, confidence))

    if   score >= 60: verdict = "FAKE"
    elif score >= 35: verdict = "SUSPICIOUS"
    else:             verdict = "GENUINE"

    return {"verdict": verdict, "score": score, "confidence": confidence, "reasons": reasons}

# ═══════════════════════════════════════════
# SERIALISE DEAL  (fast — no Safqa call)
# ═══════════════════════════════════════════
def serialize_deal_fast(doc_id: str, d: dict) -> dict:
    original = float(d.get("original_price", 0))
    current  = float(d.get("current_price", 0))
    discount = int(d.get("discount_percent", 0))
    fraud    = detect_fraud_basic(original, current, discount)

    return {
        "id":               doc_id,
        "title":            d.get("title", ""),
        "store":            d.get("site_display", d.get("source", "")),
        "source":           d.get("source", ""),
        "current_price":    current,
        "original_price":   original,
        "discount_percent": discount,
        "currency":         "EGP",
        "image_url":        d.get("image_url", ""),
        "product_url":      d.get("product_url", ""),
        "category":         d.get("category", ""),
        "rating":           float(d.get("rating", 0)) if d.get("rating") else 0.0,
        "verdict":          fraud["verdict"],
        "fake_score":       fraud["score"],
        "confidence":       fraud["confidence"],
        "fraud_reasons":    fraud["reasons"],
        "stale":            False,
        "stale_warning":    "",
    }

# ═══════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════
@app.route('/api/v1/deals', methods=['GET'])
def get_deals():
    limit    = request.args.get('limit', 50, type=int)
    category = request.args.get('category', None)
    try:
        q    = db.collection('deals')
        if category and category != "all":
            q = q.where('category', '==', category.lower())
        docs  = q.limit(limit).stream()
        deals = [serialize_deal_fast(doc.id, doc.to_dict()) for doc in docs]
        return jsonify({"success": True, "count": len(deals),
                        "deals": deals, "timestamp": now_iso()})
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
        return jsonify({"success": True, "count": len(deals),
                        "deals": deals, "query": q_str})
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
        return jsonify({"success": True, "categories": sorted(list(cats))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/price-history', methods=['GET'])
def price_history():
    """
    Lazily called from the detail screen.
    Hits Safqa /product/ssearch with AES-encrypted payload.
    Returns Safqa history + enhanced fraud verdict.
    """
    product_url      = request.args.get('url', '').strip()
    claimed_original = request.args.get('original', 0, type=float)
    claimed_current  = request.args.get('current', 0, type=float)
    claimed_pct      = request.args.get('discount', 0, type=int)

    if not product_url:
        return jsonify({"success": False, "error": "Missing URL"}), 400

    # ── Safqa call ──────────────────────────────
    history = get_safqa_history(product_url, claimed_current)

    # ── Enhanced fraud verdict ──────────────────
    if history.get("found") and claimed_original > 0:
        fraud = detect_fraud_with_safqa(
            claimed_original, claimed_current, claimed_pct,
            history["lowest"], history["highest"]
        )
    else:
        fraud = None   # keep the basic verdict from /deals

    resp = {
        "success":         True,
        "found":           history.get("found", False),
        "lowest":          history.get("lowest", 0),
        "highest":         history.get("highest", 0),
        "source":          history.get("source", ""),
        "timestamp":       now_iso(),
    }
    if fraud:
        resp["enhanced_verdict"]    = fraud["verdict"]
        resp["enhanced_score"]      = fraud["score"]
        resp["enhanced_confidence"] = fraud["confidence"]
        resp["enhanced_reasons"]    = fraud["reasons"]

    return jsonify(resp)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "safqa_logged_in": bool(_token["access"])}), 200


@app.errorhandler(404)
def not_found(e): return jsonify({"success": False, "error": "Not found"}), 404
@app.errorhandler(500)
def server_error(e): return jsonify({"success": False, "error": "Server error"}), 500


# ── Login on startup ────────────────────────
safqa_login()
_load_shops()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)


# ── Debug endpoint (remove after testing) ──────────────
@app.route('/debug-login', methods=['GET'])
def debug_login():
    """Test Safqa login and show full response."""
    email    = os.getenv("SAFQA_EMAIL", "NOT_SET")
    password = os.getenv("SAFQA_PASSWORD", "NOT_SET")

    if email == "NOT_SET" or password == "NOT_SET":
        return jsonify({
            "error": "Environment variables not set",
            "SAFQA_EMAIL_set":    email != "NOT_SET",
            "SAFQA_PASSWORD_set": password != "NOT_SET",
        }), 400

    try:
        r = requests.post(
            f"{SAFQA_BASE}/auth/login",
            json={"email": email, "password": password},
            headers=SAFQA_HEADERS, timeout=12
        )
        return jsonify({
            "status_code": r.status_code,
            "email_used":  email,
            "response":    r.json() if "json" in r.headers.get("Content-Type","") else r.text[:500],
            "login_ok":    r.status_code == 200,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
