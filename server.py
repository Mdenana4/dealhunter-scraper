from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import json, os, re, requests, hashlib, base64, time
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.backends import default_backend

app = Flask(__name__)
CORS(app)

# ── Firebase ──────────────────────────────────────────────
firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    cred = credentials.Certificate(json.loads(firebase_key_json))
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized")
else:
    raise RuntimeError("FIREBASE_KEY_JSON not set!")

db = firestore.client()

# ── Safqa config ──────────────────────────────────────────
SAFQA_BASE    = "https://api.sfq.app/v1"
SAFQA_AES_KEY = "ee6uFer3jc6WuzbUGrhV"
SAFQA_HEADERS = {
    "X-joinsafqa": "joinsafqa-0.1.105",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

_session     = requests.Session()
_access_token = {"value": None, "expires_at": 0}
_shop_cache   = {}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ── AES encryption (CryptoJS compatible) ─────────────────
def _evp_bytes_to_key(password: bytes, salt: bytes):
    d, prev = b"", b""
    while len(d) < 48:
        prev = hashlib.md5(prev + password + salt).digest()
        d += prev
    return d[:32], d[32:48]

def cryptojs_encrypt(plaintext: str) -> str:
    salt    = os.urandom(8)
    key, iv = _evp_bytes_to_key(SAFQA_AES_KEY.encode(), salt)
    padder  = crypto_padding.PKCS7(128).padder()
    padded  = padder.update(plaintext.encode()) + padder.finalize()
    cipher  = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    enc     = cipher.encryptor()
    ct      = enc.update(padded) + enc.finalize()
    return base64.b64encode(b"Salted__" + salt + ct).decode()

# ── Auth using refresh token (bypasses login redirect) ────
def get_access_token() -> str | None:
    """
    Use the refresh token stored in SAFQA_REFRESH_TOKEN env var.
    The refresh endpoint accepts Bearer token directly — no cookies needed.
    Refresh token from user's browser expires April 2027.
    """
    # Return cached token if still valid
    if _access_token["value"] and time.time() < _access_token["expires_at"]:
        return _access_token["value"]

    refresh_token = os.getenv("SAFQA_REFRESH_TOKEN", "")
    if not refresh_token:
        print("❌ SAFQA_REFRESH_TOKEN env var not set")
        return None

    try:
        r = _session.post(
            f"{SAFQA_BASE}/auth/refresh",
            json={},
            headers={
                **SAFQA_HEADERS,
                "Authorization": f"Bearer {refresh_token}",
            },
            timeout=15,
            allow_redirects=False,
        )
        print(f"Refresh token → HTTP {r.status_code}")

        if r.status_code == 200:
            data   = r.json()
            tokens = (data.get("data") or {}).get("tokens") or {}
            access = tokens.get("accessToken")
            new_refresh = tokens.get("refreshToken")

            if access:
                _access_token["value"]      = access
                _access_token["expires_at"] = time.time() + 3000  # 50 min
                print("✅ Got new access token from refresh")

                # Update the refresh token if a new one was issued
                if new_refresh:
                    os.environ["SAFQA_REFRESH_TOKEN"] = new_refresh

                return access
            print(f"No access token in response: {data}")
        else:
            print(f"Refresh failed: {r.status_code} — {r.text[:300]}")
    except Exception as e:
        print(f"Refresh error: {e}")
    return None

def auth_headers() -> dict:
    token = get_access_token()
    h = {**SAFQA_HEADERS}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

# ── Shop list ─────────────────────────────────────────────
def _load_shops():
    global _shop_cache
    try:
        r = _session.get(f"{SAFQA_BASE}/shop/shop-list",
                         headers=auth_headers(), timeout=12)
        if r.status_code == 200:
            for s in (r.json().get("data") or []):
                k, p = s.get("shopKey", ""), s.get("regex_shop", "")
                if k and p:
                    _shop_cache[p] = k
            print(f"✅ {len(_shop_cache)} Safqa shops loaded")
        else:
            print(f"Shop list failed: {r.status_code}")
    except Exception as e:
        print(f"Shop load error: {e}")

def get_shop_key(url: str) -> str:
    if not _shop_cache:
        _load_shops()
    for pat, key in _shop_cache.items():
        try:
            if re.search(pat, url):
                return key
        except:
            pass
    return "amazon.eg" if "amazon.eg" in url else ""

# ── Safqa price history ───────────────────────────────────
def get_safqa_history(product_url: str, current_price: float) -> dict:
    m = re.search(r'/dp/([A-Z0-9]{10})', product_url or "")
    if not m:
        return {"found": False}

    asin = m.group(1)
    enc  = cryptojs_encrypt(json.dumps({
        "ssin": asin, "offerCode": "",
        "url": product_url,
        "shopId": get_shop_key(product_url),
        "currentPrice": current_price,
    }))

    for attempt in range(2):
        try:
            r = _session.post(
                f"{SAFQA_BASE}/product/ssearch",
                json={"d": enc},
                headers=auth_headers(),
                timeout=15,
                allow_redirects=False,
            )
            print(f"ssearch {asin} → HTTP {r.status_code}")

            if r.status_code == 401 and attempt == 0:
                # Clear cached token and retry
                _access_token["value"] = None
                _access_token["expires_at"] = 0
                continue

            if r.status_code == 200:
                prices = (r.json().get("data") or {}).get("prices") or []
                vals   = [float(p["price"]) for p in prices
                          if p.get("price") and float(p["price"]) > 0]
                if vals:
                    return {
                        "found":   True,
                        "lowest":  min(vals),
                        "highest": max(vals),
                        "source":  "Safqa",
                    }
                print("ssearch returned 200 but no prices")
            else:
                print(f"ssearch body: {r.text[:300]}")
            break
        except Exception as e:
            print(f"ssearch error: {e}")
            break
    return {"found": False}

# ── Fraud detection ───────────────────────────────────────
def detect_fraud_safqa(orig, curr, pct, lowest, highest) -> dict:
    reasons, score = [], 0

    if highest > 0 and orig > highest * 1.10:
        inf = round((orig - highest) / highest * 100)
        reasons.append(
            f"Original EGP {orig:.0f} was NEVER the real price — "
            f"all-time high was EGP {highest:.0f} ({inf}% inflated)"
        )
        score += 55

    if highest > 0 and curr >= highest * 0.95:
        reasons.append(
            f"No real discount — current price EGP {curr:.0f} "
            f"equals the all-time high EGP {highest:.0f}"
        )
        score += 45

    if highest > 0 and curr > 0:
        real_pct = round((highest - curr) / highest * 100)
        if pct - real_pct > 10:
            reasons.append(
                f"Discount exaggerated: claimed {pct}% "
                f"but real saving is only {real_pct}%"
            )
            score += 30

    if orig > 0:
        calc = round((orig - curr) / orig * 100)
        if abs(pct - calc) > 10:
            reasons.append(f"Math mismatch: claimed {pct}% but calculated {calc}%")
            score += 35

    verdict = "FAKE" if score >= 60 else "SUSPICIOUS" if score >= 35 else "GENUINE"
    return {"verdict": verdict, "score": score, "confidence": 92, "reasons": reasons}


def detect_fraud_basic(orig, curr, pct) -> dict:
    reasons, score, conf = [], 0, 65
    if orig > 0:
        calc = round((orig - curr) / orig * 100)
        if abs(pct - calc) > 10:
            reasons.append(f"Math mismatch: claimed {pct}% calculated {calc}%")
            score += 40
    if curr > 0 and orig > 0:
        ratio = orig / curr
        if ratio > 3.0:
            reasons.append(f"Extreme inflation: {ratio:.1f}×"); score += 40; conf -= 10
        elif ratio > 2.0:
            reasons.append(f"High ratio: {ratio:.1f}×"); score += 20
    if pct > 70:
        reasons.append(f"Very high discount: {pct}%"); score += 20
    verdict = "FAKE" if score >= 60 else "SUSPICIOUS" if score >= 35 else "GENUINE"
    return {"verdict": verdict, "score": score,
            "confidence": max(20, min(100, conf)), "reasons": reasons}


def serialize_deal(doc_id, d) -> dict:
    orig = float(d.get("original_price", 0))
    curr = float(d.get("current_price", 0))
    disc = int(d.get("discount_percent", 0))
    f    = detect_fraud_basic(orig, curr, disc)
    return {
        "id": doc_id, "title": d.get("title", ""),
        "store": d.get("site_display", d.get("source", "")),
        "source": d.get("source", ""),
        "current_price": curr, "original_price": orig,
        "discount_percent": disc, "currency": "EGP",
        "image_url": d.get("image_url", ""),
        "product_url": d.get("product_url", ""),
        "category": d.get("category", ""),
        "rating": float(d.get("rating", 0)) if d.get("rating") else 0.0,
        "verdict": f["verdict"], "fake_score": f["score"],
        "confidence": f["confidence"], "fraud_reasons": f["reasons"],
    }

# ── Routes ────────────────────────────────────────────────
@app.route('/health')
def health():
    token = get_access_token()
    return jsonify({
        "status": "ok",
        "safqa_logged_in": bool(token),
        "refresh_token_set": bool(os.getenv("SAFQA_REFRESH_TOKEN")),
    }), 200


@app.route('/debug-token')
def debug_token():
    """Test getting access token via refresh token."""
    refresh = os.getenv("SAFQA_REFRESH_TOKEN", "")
    if not refresh:
        return jsonify({"error": "SAFQA_REFRESH_TOKEN not set in Render env vars"}), 400
    try:
        r = requests.post(
            f"{SAFQA_BASE}/auth/refresh",
            json={},
            headers={**SAFQA_HEADERS, "Authorization": f"Bearer {refresh}"},
            timeout=15,
            allow_redirects=False,
        )
        return jsonify({
            "status_code": r.status_code,
            "success": r.status_code == 200,
            "response": r.json() if "json" in r.headers.get("Content-Type","") else r.text[:500],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/v1/deals')
def get_deals():
    limit    = request.args.get('limit', 50, type=int)
    category = request.args.get('category')
    try:
        q = db.collection('deals')
        if category and category != "all":
            q = q.where('category', '==', category.lower())
        deals = [serialize_deal(d.id, d.to_dict()) for d in q.limit(limit).stream()]
        return jsonify({"success": True, "count": len(deals),
                        "deals": deals, "timestamp": now_iso()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/deals/search')
def search_deals():
    q_str    = request.args.get('q', '').lower().strip()
    category = request.args.get('category')
    limit    = request.args.get('limit', 50, type=int)
    if len(q_str) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400
    try:
        deals = []
        for doc in db.collection('deals').limit(limit * 3).stream():
            d = doc.to_dict()
            if q_str not in d.get('title', '').lower() and \
               q_str not in d.get('site_display', '').lower():
                continue
            if category and category != "all" and \
               d.get('category', '') != category.lower():
                continue
            deals.append(serialize_deal(doc.id, d))
            if len(deals) >= limit:
                break
        return jsonify({"success": True, "count": len(deals), "deals": deals})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/categories')
def get_categories():
    try:
        cats = {d.to_dict().get('category', '')
                for d in db.collection('deals').stream()}
        return jsonify({"success": True,
                        "categories": sorted(c for c in cats if c)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/v1/price-history')
def price_history():
    url  = request.args.get('url', '').strip()
    orig = request.args.get('original', 0, type=float)
    curr = request.args.get('current',  0, type=float)
    pct  = request.args.get('discount', 0, type=int)

    if not url:
        return jsonify({"success": False, "error": "Missing URL"}), 400

    hist  = get_safqa_history(url, curr)
    fraud = detect_fraud_safqa(
        orig, curr, pct,
        hist.get("lowest", 0), hist.get("highest", 0)
    ) if hist.get("found") and orig > 0 else None

    resp = {
        "success":   True,
        "found":     hist.get("found", False),
        "lowest":    hist.get("lowest", 0),
        "highest":   hist.get("highest", 0),
        "source":    hist.get("source", ""),
        "timestamp": now_iso(),
    }
    if fraud:
        resp.update({
            "enhanced_verdict":    fraud["verdict"],
            "enhanced_score":      fraud["score"],
            "enhanced_confidence": fraud["confidence"],
            "enhanced_reasons":    fraud["reasons"],
        })
    return jsonify(resp)


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "Server error"}), 500


# ── Startup — get access token immediately ────────────────
print("Starting up — getting Safqa access token...")
token = get_access_token()
if token:
    print("✅ Safqa ready")
    _load_shops()
else:
    print("⚠️  Safqa token not available — set SAFQA_REFRESH_TOKEN env var")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
