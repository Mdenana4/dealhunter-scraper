from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, messaging, auth as fb_auth
import json, os, re, requests, hashlib, hmac, base64, time
from datetime import datetime, timezone, timedelta
from functools import wraps
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.backends import default_backend

app = Flask(__name__)
_cors_origins = os.getenv('CORS_ORIGINS', 'https://dealhunter-scraper.onrender.com')
CORS(app, origins=_cors_origins.split(','))

firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    cred = credentials.Certificate(json.loads(firebase_key_json))
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized")
else:
    raise RuntimeError("FIREBASE_KEY_JSON not set!")

db = firestore.client()

SAFQA_BASE    = "https://api.sfq.app/v1"
SAFQA_AES_KEY = os.getenv("SAFQA_AES_KEY", "ee6uFer3jc6WuzbUGrhV")
SAFQA_HEADERS = {
    "X-joinsafqa": "joinsafqa-0.1.105",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

_session    = requests.Session()
_shop_cache = {}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ── AES ────────────────────────────────────────────────────
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

# ── Token: read from env var directly ─────────────────────
# User sets SAFQA_ACCESS_TOKEN in Render env
# When it expires, get a new one from browser DevTools
def get_token() -> str:
    return os.getenv("SAFQA_ACCESS_TOKEN", "")

def auth_headers() -> dict:
    h = {**SAFQA_HEADERS}
    t = get_token()
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h

# ── Shop list ───────────────────────────────────────────────
def _load_shops():
    global _shop_cache
    try:
        r = _session.get(f"{SAFQA_BASE}/shop/shop-list",
                         headers=auth_headers(), timeout=12,
                         allow_redirects=False)
        print(f"Shop list → {r.status_code}")
        if r.status_code == 200:
            for s in (r.json().get("data") or []):
                k, p = s.get("shopKey",""), s.get("regex_shop","")
                if k and p:
                    _shop_cache[p] = k
            print(f"✅ {len(_shop_cache)} shops")
    except Exception as e:
        print(f"Shop load: {e}")

def get_shop_key(url: str) -> str:
    if not _shop_cache:
        _load_shops()
    for pat, key in _shop_cache.items():
        try:
            if re.search(pat, url): return key
        except: pass
    return "amazon.eg" if "amazon.eg" in url else ""

# ── Safqa price history ─────────────────────────────────────
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
    try:
        r = _session.post(f"{SAFQA_BASE}/product/ssearch",
                          json={"d": enc},
                          headers=auth_headers(),
                          timeout=15,
                          allow_redirects=False)
        print(f"ssearch {asin} → {r.status_code}")
        if r.status_code == 200:
            prices = (r.json().get("data") or {}).get("prices") or []
            vals   = [float(p["price"]) for p in prices
                      if p.get("price") and float(p["price"]) > 0]
            if vals:
                return {"found": True, "lowest": min(vals),
                        "highest": max(vals), "source": "Safqa"}
        else:
            print(f"ssearch body: {r.text[:200]}")
    except Exception as e:
        print(f"ssearch error: {e}")
    return {"found": False}

# ── Fraud detection ─────────────────────────────────────────
def detect_fraud_safqa(orig, curr, pct, low, high) -> dict:
    reasons, score = [], 0
    if high > 0 and orig > high * 1.10:
        inf = round((orig-high)/high*100)
        reasons.append(f"Original EGP {orig:.0f} was NEVER the real price — all-time high EGP {high:.0f} ({inf}% inflated)")
        score += 55
    if high > 0 and curr >= high * 0.95:
        reasons.append(f"No real discount — current EGP {curr:.0f} equals all-time high EGP {high:.0f}")
        score += 45
    if high > 0 and curr > 0:
        real = round((high-curr)/high*100)
        if pct - real > 10:
            reasons.append(f"Discount exaggerated: claimed {pct}% but real saving is {real}%")
            score += 30
    if orig > 0:
        calc = round((orig-curr)/orig*100)
        if abs(pct-calc) > 10:
            reasons.append(f"Math mismatch: claimed {pct}% calculated {calc}%"); score += 35
    verdict = "FAKE" if score>=60 else "SUSPICIOUS" if score>=35 else "GENUINE"
    return {"verdict": verdict, "score": score, "confidence": 92, "reasons": reasons}

def detect_fraud_basic(orig, curr, pct) -> dict:
    reasons, score, conf = [], 0, 65
    # Reconstruct original price from claimed discount when it's missing in storage.
    # e.g. curr=89, pct=77  →  orig ≈ 387. Allows ratio check to run.
    if orig == 0 and curr > 0 and 0 < pct < 100:
        orig = round(curr / (1 - pct / 100), 2)
        reasons.append(f"Original price not stored — reconstructed as {orig:.0f} from {pct}% claim")
    if orig > 0 and curr > 0:
        ratio = orig / curr
        calc  = round((orig - curr) / orig * 100)
        if abs(pct - calc) > 10:
            reasons.append(f"Math mismatch: claimed {pct}% but calculated {calc}%"); score += 40
        if ratio > 3.5 and pct > 65:
            reasons.append(f"Extreme {ratio:.1f}x ratio with {pct}% claimed — 'was' price likely inflated")
            score += 65; conf -= 15
        elif ratio > 3.0:
            reasons.append(f"Very high {ratio:.1f}x ratio"); score += 45; conf -= 10
        elif ratio > 2.0:
            reasons.append(f"High {ratio:.1f}x ratio"); score += 20
    if pct > 75: reasons.append(f"Very high {pct}% claimed discount"); score += 20
    verdict = "FAKE" if score >= 60 else "SUSPICIOUS" if score >= 35 else "GENUINE"
    return {"verdict": verdict, "score": score, "confidence": max(20, min(100, conf)), "reasons": reasons}

def serialize_deal(doc_id, d) -> dict:
    orig = float(d.get("original_price") or 0)
    curr = float(d.get("current_price") or 0)
    disc = int(d.get("discount_percent") or 0)

    # Prefer the real Kanbkam+Safqa verdict stored by the scraper.
    # Fall back to the basic math check only when no scraper verdict exists.
    kb = d.get("kanbkam") or {}
    kb_verdict = kb.get("verdict", "")
    _rank = {"FAKE": 4, "SUSPICIOUS": 3, "WAIT": 2, "GENUINE": 1, "UNVERIFIED": 0}

    if kb_verdict in ("GENUINE", "FAKE", "SUSPICIOUS", "WAIT"):
        verdict    = "SUSPICIOUS" if kb_verdict == "WAIT" else kb_verdict
        fake_score = float(kb.get("fake_score", 50))
        confidence = float(kb.get("confidence", 65) if "confidence" in kb else (
            10 if kb_verdict == "GENUINE" else 90 if kb_verdict == "FAKE" else 65))
        fraud_reasons = ([kb["reason"]] if kb.get("reason") else []) + (
            ["Rule A: original price inflated"] if kb.get("rule_a_triggered") else []) + (
            ["Rule B: price never changed"] if kb.get("rule_b_triggered") else [])
        # Even with a stored verdict, cross-check with basic ratio analysis.
        # If the ratio-based check is MORE suspicious, upgrade the verdict.
        f = detect_fraud_basic(orig, curr, disc)
        if _rank.get(f["verdict"], 0) > _rank.get(verdict, 0):
            verdict       = f["verdict"]
            fake_score    = max(fake_score, float(f["score"]))
            confidence    = f["confidence"]
            fraud_reasons = f["reasons"] + fraud_reasons
    else:
        # No price history stored (UNVERIFIED or missing) — use ratio analysis only
        f = detect_fraud_basic(orig, curr, disc)
        verdict, fake_score, confidence, fraud_reasons = (
            f["verdict"], f["score"], f["confidence"], f["reasons"])

    marketplace = d.get("site") or d.get("marketplace_country") or d.get("source", "")
    return {
        "id": doc_id, "title": d.get("title", ""),
        "store": d.get("site_display", marketplace),
        "source": marketplace,
        "marketplace_country": marketplace,
        "product_id": d.get("asin") or d.get("product_id") or doc_id,
        "current_price": curr, "original_price": orig,
        "discount_percent": disc,
        "currency": d.get("currency", "EGP"),
        "image_url": d.get("image_url", ""), "product_url": d.get("product_url", ""),
        "category": d.get("category", ""),
        "rating": float(d.get("rating") or 0),
        "verdict": verdict, "fake_score": fake_score,
        "confidence": confidence, "fraud_reasons": fraud_reasons,
        "lowest_price": float(kb.get("lowest_price") or 0),
        "highest_price": float(kb.get("highest_price") or 0),
        "verdict_ar": kb.get("verdict_ar", ""),
        "reason_ar": kb.get("reason_ar", ""),
        "coupon_codes": kb.get("coupon_codes", []),
    }

# ── Routes ──────────────────────────────────────────────────
@app.route('/health')
def health():
    token = get_token()
    return jsonify({
        "status": "ok",
        "safqa_token_set": bool(token),
        "safqa_token_preview": token[:20]+"..." if token else "NOT SET",
    }), 200

@app.route('/test-safqa')
def test_safqa():
    """Test ssearch with BaByliss to confirm Safqa works."""
    token = get_token()
    if not token:
        return jsonify({"error": "SAFQA_ACCESS_TOKEN not set in Render env vars"}), 400
    enc = cryptojs_encrypt(json.dumps({
        "ssin": "B09B81NKPF", "offerCode": "",
        "url": "https://www.amazon.eg/dp/B09B81NKPF",
        "shopId": "amazon.eg", "currentPrice": 1500.0,
    }))
    try:
        r = _session.post(f"{SAFQA_BASE}/product/ssearch",
                          json={"d": enc},
                          headers=auth_headers(),
                          timeout=15,
                          allow_redirects=False)
        return jsonify({
            "status_code": r.status_code,
            "response": r.json() if "json" in r.headers.get("Content-Type","") else r.text[:500],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/deals')
def get_deals():
    limit,category = request.args.get('limit',50,type=int),request.args.get('category')
    try:
        q = db.collection('deals')
        if category and category!="all":
            q = q.where('category','==',category.lower())
        deals=[serialize_deal(d.id,d.to_dict()) for d in q.limit(limit).stream()]
        return jsonify({"success":True,"count":len(deals),"deals":deals,"timestamp":now_iso()})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),500

@app.route('/api/v1/deals/search')
def search_deals():
    q_str,category,limit=request.args.get('q','').lower().strip(),request.args.get('category'),request.args.get('limit',50,type=int)
    if len(q_str)<2: return jsonify({"success":False,"error":"Query too short"}),400
    try:
        deals=[]
        for doc in db.collection('deals').limit(limit*3).stream():
            d=doc.to_dict()
            if q_str not in d.get('title','').lower() and q_str not in d.get('site_display','').lower(): continue
            if category and category!="all" and d.get('category','')!=category.lower(): continue
            deals.append(serialize_deal(doc.id,d))
            if len(deals)>=limit: break
        return jsonify({"success":True,"count":len(deals),"deals":deals})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),500

@app.route('/api/v1/categories')
def get_categories():
    try:
        cats={d.to_dict().get('category','') for d in db.collection('deals').stream()}
        return jsonify({"success":True,"categories":sorted(c for c in cats if c)})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),500

@app.route('/api/v1/price-history')
def price_history():
    url=request.args.get('url','').strip()
    orig=request.args.get('original',0,type=float)
    curr=request.args.get('current',0,type=float)
    pct=request.args.get('discount',0,type=int)
    if not url: return jsonify({"success":False,"error":"Missing URL"}),400
    hist=get_safqa_history(url,curr)
    fraud=detect_fraud_safqa(orig,curr,pct,hist.get("lowest",0),hist.get("highest",0)) \
          if hist.get("found") and orig>0 else None
    resp={"success":True,"found":hist.get("found",False),
          "lowest":hist.get("lowest",0),"highest":hist.get("highest",0),
          "source":hist.get("source",""),"timestamp":now_iso()}
    if fraud:
        resp.update({"enhanced_verdict":fraud["verdict"],"enhanced_score":fraud["score"],
                     "enhanced_confidence":fraud["confidence"],"enhanced_reasons":fraud["reasons"]})
    return jsonify(resp)

# ── Price-tracker routes ────────────────────────────────────────────────────
# These endpoints expose the price_tracker.py service to the frontend / apps.
# All accept marketplace_country values: amazon_eg, amazon_ae, amazon_sa,
#   noon_eg, noon_ae, noon_sa, jumia_eg

from price_tracker import (
    record_price as pt_record,
    get_price_history as pt_history,
    get_price_changes_only as pt_changes,
    get_product_summary as pt_summary,
    get_recent_price_changes as pt_recent,
    get_top_price_drops as pt_drops,
    get_historical_low as pt_low,
    create_price_alert as pt_create_alert,
    get_user_alerts as pt_user_alerts,
    delete_alert as pt_delete_alert,
)

def _pt_error(msg, code=400):
    return jsonify({"success": False, "error": msg}), code

def _serialize_ts(obj):
    """Recursively convert Firestore Timestamps to ISO strings for JSON."""
    if isinstance(obj, list):
        return [_serialize_ts(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize_ts(v) for k, v in obj.items()}
    if hasattr(obj, "isoformat"):   # datetime / Timestamp
        return obj.isoformat()
    return obj


@app.route("/api/v1/tracker/record", methods=["POST"])
def tracker_record():
    """
    Internal endpoint called by the scraper to store a price snapshot.

    Required JSON body fields:
      marketplace_country, product_id, name, url, price

    Optional:
      original_price, currency, in_stock, image_url, category, brand
    """
    body = request.get_json(silent=True) or {}
    required = ("marketplace_country", "product_id", "name", "url", "price")
    missing  = [f for f in required if not body.get(f)]
    if missing:
        return _pt_error(f"Missing fields: {missing}")

    try:
        result = pt_record(
            marketplace_country = body["marketplace_country"],
            product_id          = body["product_id"],
            name                = body["name"],
            url                 = body["url"],
            price               = float(body["price"]),
            original_price      = float(body["original_price"]) if body.get("original_price") else None,
            currency            = body.get("currency"),
            in_stock            = bool(body.get("in_stock", True)),
            image_url           = body.get("image_url"),
            category            = body.get("category"),
            brand               = body.get("brand"),
        )
        return jsonify({"success": True, **result})
    except ValueError as e:
        return _pt_error(str(e))
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/history")
def tracker_history():
    """
    Full chronological price history for one product.

    Query params:
      marketplace_country  e.g. amazon_eg
      product_id           e.g. B08N5WRWNW
      days                 int, default 90
      changes_only         bool (1/true) — return only snapshots where price changed
    """
    mc  = request.args.get("marketplace_country", "").strip()
    pid = request.args.get("product_id", "").strip()
    if not mc or not pid:
        return _pt_error("marketplace_country and product_id are required")
    # Strip marketplace prefix if the app passed the full Firestore doc_id
    if pid.startswith(mc + "_"):
        pid = pid[len(mc) + 1:]

    days         = request.args.get("days", 90, type=int)
    changes_only = request.args.get("changes_only", "").lower() in ("1", "true", "yes")

    try:
        if changes_only:
            data = pt_changes(mc, pid, days=days)
        else:
            data = pt_history(mc, pid, days=days)
        return jsonify({
            "success": True,
            "marketplace_country": mc,
            "product_id": pid,
            "days": days,
            "count": len(data),
            "history": _serialize_ts(data),
        })
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/product")
def tracker_product():
    """
    Product document + statistics (lowest, highest, average, trend).

    Query params:
      marketplace_country  e.g. noon_ae
      product_id           product's SKU / ASIN
      days                 int, window for stats, default 90
    """
    mc  = request.args.get("marketplace_country", "").strip()
    pid = request.args.get("product_id", "").strip()
    if not mc or not pid:
        return _pt_error("marketplace_country and product_id are required")
    if pid.startswith(mc + "_"):
        pid = pid[len(mc) + 1:]

    days = request.args.get("days", 90, type=int)
    try:
        summary = pt_summary(mc, pid, history_days=days)
        if not summary:
            return jsonify({"success": False, "error": "Product not found"}), 404
        return jsonify({"success": True, "product": _serialize_ts(summary)})
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/recent-changes")
def tracker_recent_changes():
    """
    Recent price change events across all tracked products.

    Query params (all optional, use one filter at a time):
      marketplace_country  e.g. jumia_eg
      marketplace          e.g. amazon
      country              e.g. sa
      hours                int, look-back window, default 24
      limit                int, max results, default 50
    """
    mc          = request.args.get("marketplace_country", "").strip() or None
    marketplace = request.args.get("marketplace", "").strip() or None
    country     = request.args.get("country", "").strip() or None
    hours       = request.args.get("hours", 24, type=int)
    limit       = request.args.get("limit", 50, type=int)

    try:
        events = pt_recent(
            marketplace_country = mc,
            marketplace         = marketplace,
            country             = country,
            hours               = hours,
            limit               = limit,
        )
        return jsonify({
            "success": True,
            "hours": hours,
            "count": len(events),
            "events": _serialize_ts(events),
        })
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/top-drops")
def tracker_top_drops():
    """
    Products with the largest percentage price drops in the last N hours.

    Query params:
      marketplace_country  optional filter
      hours                int, default 24
      limit                int, default 20
      min_drop_pct         float, minimum drop to include, default 5.0
    """
    mc           = request.args.get("marketplace_country", "").strip() or None
    hours        = request.args.get("hours", 24, type=int)
    limit        = request.args.get("limit", 20, type=int)
    min_drop_pct = request.args.get("min_drop_pct", 5.0, type=float)

    try:
        drops = pt_drops(
            marketplace_country = mc,
            hours               = hours,
            limit               = limit,
            min_drop_pct        = min_drop_pct,
        )
        return jsonify({
            "success": True,
            "hours": hours,
            "min_drop_pct": min_drop_pct,
            "count": len(drops),
            "drops": _serialize_ts(drops),
        })
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/alert", methods=["POST"])
def tracker_create_alert():
    """
    Create a price alert for a user.

    Required JSON body:
      user_id, marketplace_country, product_id

    Provide at least one of:
      target_price         — alert when price drops to or below this value
      alert_threshold_pct  — alert on any drop >= this percentage (e.g. 10)

    Optional:
      notification_channels  array, default ["push", "email"]
    """
    body = request.get_json(silent=True) or {}
    required = ("user_id", "marketplace_country", "product_id")
    missing  = [f for f in required if not body.get(f)]
    if missing:
        return _pt_error(f"Missing fields: {missing}")

    if not body.get("target_price") and not body.get("alert_threshold_pct"):
        return _pt_error("Provide target_price or alert_threshold_pct")

    try:
        alert_id = pt_create_alert(
            user_id              = body["user_id"],
            marketplace_country  = body["marketplace_country"],
            product_id           = body["product_id"],
            target_price         = float(body["target_price"]) if body.get("target_price") else None,
            alert_threshold_pct  = float(body["alert_threshold_pct"]) if body.get("alert_threshold_pct") else None,
            notification_channels = body.get("notification_channels"),
        )
        return jsonify({"success": True, "alert_id": alert_id})
    except ValueError as e:
        return _pt_error(str(e))
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/alert", methods=["GET"])
def tracker_list_alerts():
    """List active price alerts for a user. Requires ?user_id= or Firebase token."""
    # Try token first, fall back to query param
    decoded = _verify_firebase_token(required=False)
    user_id = decoded["uid"] if decoded else request.args.get("user_id", "")
    if not user_id:
        return _pt_error("user_id required", 401)
    try:
        alerts = pt_user_alerts(user_id)
        return jsonify({"success": True, "alerts": alerts})
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route("/api/v1/tracker/alert/<alert_id>", methods=["DELETE"])
def tracker_delete_alert(alert_id):
    """Deactivate (soft-delete) a price alert owned by the caller."""
    decoded = _verify_firebase_token(required=False)
    body    = request.get_json(silent=True) or {}
    user_id = (decoded["uid"] if decoded else None) or body.get("user_id", "")
    if not user_id:
        return _pt_error("user_id required", 401)
    try:
        ok = pt_delete_alert(alert_id, user_id)
        if not ok:
            return _pt_error("Alert not found or not owned by user", 404)
        return jsonify({"success": True})
    except Exception as e:
        return _pt_error(str(e), 500)


# ── Auth helpers ────────────────────────────────────────────────────────────

def _verify_firebase_token(required=True):
    """Return decoded Firebase token, or None if optional and missing."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ', 1)[1]
    try:
        return fb_auth.verify_id_token(token)
    except Exception:
        return None

def require_auth(f):
    """Decorator: reject if no valid Firebase JWT present."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _verify_firebase_token():
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

def require_admin(f):
    """Decorator: reject if caller is not in admin_users collection."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        decoded = _verify_firebase_token()
        if not decoded:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        uid = decoded.get('uid', '')
        admin_doc = db.collection('admin_users').document(uid).get()
        if not admin_doc.exists:
            return jsonify({"success": False, "error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


# ── Mobile App API ───────────────────────────────────────────────────────────
# Endpoints consumed by the Flutter user app (api_service.dart).

# Egypt prices in EGP (Paymob)
TIER_PRICES_EGP = {
    'basic':   {'monthly': 49,   '6months': 264.6,  'yearly': 441.0},
    'premium': {'monthly': 99,   '6months': 534.6,  'yearly': 891.0},
    'vip':     {'monthly': 199,  '6months': 1074.6, 'yearly': 1791.0},
}

# GCC prices in AED (Tap Payments) — UAE/SA/KW/BH/QA/OM
TIER_PRICES_AED = {
    'basic':   {'monthly': 14.99, '6months': 80.94,  'yearly': 134.91},
    'premium': {'monthly': 29.99, '6months': 161.94, 'yearly': 269.91},
    'vip':     {'monthly': 59.99, '6months': 323.94, 'yearly': 539.91},
}

TIER_PRICES = TIER_PRICES_EGP   # backwards compat alias

GCC_COUNTRIES = {'AE', 'SA', 'KW', 'BH', 'QA', 'OM'}


@app.route('/api/deals')
def mobile_get_deals():
    """
    Paginated deal feed consumed by the user app's DealsTab.

    Query params:
      category             optional string
      country              optional 2-letter code (eg, ae, sa) — filters by site suffix
      marketplace_country  optional string (amazon_eg, noon_eg, …) — exact match
      min_discount         float, default 0 (filter out low-discount items)
      limit                int, default 50
      page                 int, default 1 (1-based)
    """
    category   = request.args.get('category', '').strip().lower() or None
    country    = request.args.get('country', '').strip().lower() or None
    source     = request.args.get('source', '').strip().lower() or None   # amazon | noon | jumia
    mc         = request.args.get('marketplace_country', '').strip().lower() or None
    min_disc   = request.args.get('min_discount', 0.0, type=float)
    limit      = min(request.args.get('limit', 50, type=int), 200)
    page       = max(request.args.get('page', 1, type=int), 1)
    offset     = (page - 1) * limit

    try:
        q = db.collection('deals')
        if category:
            q = q.where('category', '==', category)
        if mc:
            q = q.where('site', '==', mc)   # scraper stores marketplace in 'site'

        # Cap at 1000 docs to prevent streaming an unbounded collection
        # (causes memory exhaustion / 60-second Firestore timeout).
        all_docs = list(q.limit(1000).stream())

        # Country filter: keep docs whose 'site' ends with _{country} (eg, ae, sa)
        if country:
            all_docs = [
                d for d in all_docs
                if d.to_dict().get('site', '').endswith(f'_{country}')
            ]

        # Source filter: amazon_ | noon_ | jumia_ prefix
        if source:
            all_docs = [
                d for d in all_docs
                if d.to_dict().get('site', '').startswith(f'{source}_')
            ]
        def _disc_sort_key(doc):
            try:
                return int(doc.to_dict().get('discount_percent') or 0)
            except Exception:
                return 0

        all_docs.sort(key=_disc_sort_key, reverse=True)

        # Drop deals not updated in the last N days.
        # timestamp can be a Firestore DatetimeWithNanoseconds OR an ISO string.
        def _cutoff_dt(days):
            return datetime.now(timezone.utc) - timedelta(days=days)

        def _doc_dt(doc):
            ts = doc.to_dict().get('timestamp')
            if ts is None:
                return None
            if hasattr(ts, 'tzinfo'):  # DatetimeWithNanoseconds / datetime
                if ts.tzinfo is None:
                    return ts.replace(tzinfo=timezone.utc)
                return ts
            if isinstance(ts, str) and ts:
                try:
                    return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except Exception:
                    pass
            return None

        _epoch = datetime.min.replace(tzinfo=timezone.utc)
        fresh = [d for d in all_docs if (_doc_dt(d) or _epoch) >= _cutoff_dt(7)]
        if not fresh:
            fresh = [d for d in all_docs if (_doc_dt(d) or _epoch) >= _cutoff_dt(30)]
        all_docs = fresh

        # Apply min_discount and paginate in memory (Firestore doesn't support !=)
        results = []
        skipped = 0
        for doc in all_docs:
            d = doc.to_dict()
            try:
                if int(d.get('discount_percent') or 0) < min_disc:
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                results.append(serialize_deal(doc.id, d))
                if len(results) >= limit:
                    break
            except Exception as doc_err:
                import traceback
                print(f"[WARN] Skipping bad deal doc {doc.id}: {doc_err}", flush=True)
                print(traceback.format_exc(), flush=True)
                continue

        return jsonify({
            "success": True,
            "count": len(results),
            "page": page,
            "deals": results,
            "timestamp": now_iso(),
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] /api/deals crashed: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        return _pt_error(str(e), 500)


@app.route('/api/deals/<string:deal_id>')
def mobile_get_deal_detail(deal_id):
    """Single deal by Firestore document ID."""
    try:
        doc = db.collection('deals').document(deal_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Deal not found"}), 404
        return jsonify({"success": True, "deal": serialize_deal(doc.id, doc.to_dict())})
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route('/api/search')
def mobile_search():
    """
    Full-text search with optional brand / size / marketplace filters.

    Query params: q, category, brand, size, marketplace_country, limit
    """
    q_str = request.args.get('q', '').strip().lower()
    if len(q_str) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400

    category = request.args.get('category', '').strip().lower() or None
    brand    = request.args.get('brand', '').strip().lower() or None
    size     = request.args.get('size', '').strip().lower() or None
    mc       = request.args.get('marketplace_country', '').strip().lower() or None
    limit    = min(request.args.get('limit', 30, type=int), 100)

    try:
        results = []
        for doc in db.collection('deals').limit(limit * 5).stream():
            d = doc.to_dict()
            title   = d.get('title', '').lower()
            site    = d.get('site', d.get('source', '')).lower()
            d_brand = d.get('brand', '').lower()
            d_size  = d.get('size', '').lower()
            d_cat   = d.get('category', '').lower()

            if q_str not in title and q_str not in site:
                continue
            if category and d_cat != category:
                continue
            if brand and brand not in d_brand:
                continue
            if size and size not in d_size:
                continue
            if mc and site != mc:
                continue

            results.append(serialize_deal(doc.id, d))
            if len(results) >= limit:
                break

        return jsonify({"success": True, "count": len(results), "results": results})
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route('/api/verify')
def mobile_verify():
    """
    On-demand fake-discount verification.

    Strategy (in order):
      1. Our own price_tracker database (grows every scrape cycle)
      2. Safqa ssearch (requires valid SAFQA_ACCESS_TOKEN in Render env)
      3. Kanbkam via ScraperAPI proxy (Amazon EG, avoids IP blocks on Render)
      4. Ratio analysis — always runs. When no external data found,
         returns 'unverified' instead of 'genuine' to be honest.
    """
    mc   = request.args.get('marketplace_country', '').strip()
    pid  = request.args.get('product_id', '').strip()
    url  = request.args.get('product_url', '').strip()
    orig = request.args.get('original_price', 0, type=float)
    curr = request.args.get('current_price',  0, type=float)
    disc = request.args.get('discount_percent', 0, type=int)

    if not mc or not pid:
        return jsonify({"success": False,
                        "error": "marketplace_country and product_id required"}), 400
    if pid.startswith(mc + "_"):
        pid = pid[len(mc) + 1:]

    # Fill missing prices from deals collection
    if not orig or not curr:
        try:
            matches = list(db.collection('deals').where('asin', '==', pid).limit(1).stream())
            if not matches:
                doc = db.collection('deals').document(pid).get()
                if doc.exists:
                    matches = [doc]
            if matches:
                d    = matches[0].to_dict()
                orig = orig or float(d.get('original_price') or 0)
                curr = curr or float(d.get('current_price')  or 0)
                disc = disc or int(d.get('discount_percent') or 0)
                url  = url  or d.get('product_url', '')
        except Exception:
            pass

    try:
        data_found      = False
        historical_low  = 0.0
        historical_high = 0.0
        source_label    = ''
        currency = 'EGP' if 'eg' in mc else ('AED' if 'ae' in mc else 'SAR')

        # ── 1. Own price_tracker DB ─────────────────────────────────────────
        try:
            from price_tracker import make_product_doc_id, get_price_history
            doc_id  = make_product_doc_id(mc, pid)
            history = get_price_history(mc, pid, days=365)
            prices  = [h['price'] for h in history if h.get('price')]
            if len(prices) >= 3:
                historical_low  = min(prices)
                historical_high = max(prices)
                data_found      = True
                source_label    = 'DealHunter price database'
                print(f"[VERIFY] Own DB: {len(prices)} snapshots, "
                      f"low={historical_low}, high={historical_high}", flush=True)
        except Exception as db_err:
            print(f"[VERIFY] Own DB error: {db_err}", flush=True)

        # ── 2. Safqa ssearch ────────────────────────────────────────────────
        if not data_found and url and curr > 0:
            try:
                hist = get_safqa_history(url, curr)
                if hist.get('found'):
                    historical_low  = hist.get('lowest',  0)
                    historical_high = hist.get('highest', 0)
                    data_found      = True
                    source_label    = 'price history database'
                    print(f"[VERIFY] Safqa: low={historical_low}, high={historical_high}", flush=True)
            except Exception as sq_err:
                print(f"[VERIFY] Safqa error: {sq_err}", flush=True)

        # ── 3. Kanbkam via ScraperAPI (Amazon EG, avoids server IP blocks) ──
        if not data_found and mc == 'amazon_eg' and re.match(r'^[A-Z0-9]{10}$', pid):
            try:
                scraper_key = os.getenv('SCRAPER_API_KEY', '')
                for kb_url in [
                    f"https://www.kanbkam.com/eg/ar/dp/{pid}",
                    f"https://www.kanbkam.com/eg/en/dp/{pid}",
                ]:
                    params = {"api_key": scraper_key, "url": kb_url,
                              "render": "false", "country_code": "eg"}
                    r = _session.get("http://api.scraperapi.com",
                                     params=params, timeout=30)
                    if r.status_code != 200 or len(r.text) < 500:
                        continue
                    lm = re.search(r'"lowestPrice"\s*:\s*([\d.]+)', r.text)
                    hm = re.search(r'"highestPrice"\s*:\s*([\d.]+)', r.text)
                    if not lm:
                        lm = re.search(r'أقل\s*سعر[^\d]*([\d,]+)', r.text)
                        hm = re.search(r'أعلى\s*سعر[^\d]*([\d,]+)', r.text)
                    if lm:
                        historical_low  = float(lm.group(1).replace(',', ''))
                        historical_high = float(hm.group(1).replace(',', '')) if hm else historical_low
                        data_found      = True
                        source_label    = 'price history database'
                        print(f"[VERIFY] Kanbkam: low={historical_low}, high={historical_high}", flush=True)
                        break
            except Exception as kb_err:
                print(f"[VERIFY] Kanbkam error: {kb_err}", flush=True)

        # ── 4. Compute verdict ───────────────────────────────────────────────
        if data_found and orig > 0:
            fraud = detect_fraud_safqa(orig, curr, disc, historical_low, historical_high)
        else:
            fraud = detect_fraud_basic(orig, curr, disc)

        # When no external data found, never claim "genuine" — we simply can't verify
        has_external = data_found
        if not has_external and fraud['verdict'] == 'GENUINE':
            verdict      = 'unverified'
            confidence   = 30
            explanation  = (
                f"No price history found for this product. "
                f"We cannot verify whether the claimed 'was' price "
                f"({currency} {orig:.0f}) was ever real."
            )
            red_flags    = []
            recommendation = (
                "Price history unavailable. Check the product manually "
                "or wait a few weeks for our database to build history."
            )
        else:
            # Build red flags
            red_flags = list(fraud.get('reasons', []))
            if historical_high > 0 and orig > historical_high * 1.05:
                red_flags.insert(0,
                    f"'Was' price ({currency} {orig:.0f}) was NEVER real — "
                    f"highest price ever recorded was only {currency} {historical_high:.0f}.")
            if historical_high > 0:
                real_disc = round((historical_high - curr) / historical_high * 100)
                if disc - real_disc > 10:
                    red_flags.append(
                        f"Real saving vs true highest price: {real_disc}% "
                        f"(not the claimed {disc}%).")

            verdict_map = {'GENUINE': 'genuine', 'FAKE': 'fake',
                           'SUSPICIOUS': 'uncertain', 'WAIT': 'uncertain'}
            verdict     = verdict_map.get(fraud['verdict'], 'uncertain')
            confidence  = fraud['confidence']

            if historical_high > 0:
                explanation = (
                    f"Verified against {source_label}. "
                    f"Highest price ever: {currency} {historical_high:.0f} · "
                    f"Claimed 'was': {currency} {orig:.0f} · "
                    f"Now: {currency} {curr:.0f}."
                )
            else:
                explanation = (
                    f"Checked using price ratio analysis. "
                    f"Claimed 'was': {currency} {orig:.0f} · "
                    f"Now: {currency} {curr:.0f} · {disc}% off."
                )

            recommendation = (
                "This looks like a genuine deal — good time to buy!"
                if verdict == 'genuine' else
                "Price manipulation detected — the 'was' price was likely never real."
                if verdict == 'fake' else
                "Suspicious signals detected — verify before buying."
            )

        return jsonify({
            "success":         True,
            "verdict":         verdict,
            "confidence":      confidence,
            "explanation":     explanation,
            "red_flags":       red_flags,
            "recommendation":  recommendation,
            "historical_high": historical_high,
            "historical_low":  historical_low,
            "data_found":      data_found,
            "source_used":     source_label,
            "checked_at":      now_iso(),
        })
    except Exception as e:
        import traceback
        print(f"[VERIFY] Error: {e}\n{traceback.format_exc()}", flush=True)
        return _pt_error(str(e), 500)


@app.route('/api/analytics/event', methods=['POST'])
def mobile_log_event():
    """
    Fire-and-forget analytics event from the user app.
    Body: { event, data, timestamp }
    """
    body = request.get_json(silent=True) or {}
    event = body.get('event', '').strip()
    if not event:
        return jsonify({"success": False, "error": "event required"}), 400

    # Enrich with server-side uid if auth header present
    decoded = _verify_firebase_token(required=False)
    uid     = decoded.get('uid') if decoded else None

    try:
        db.collection('analytics_events').add({
            'event':     event,
            'data':      body.get('data', {}),
            'uid':       uid,
            'timestamp': body.get('timestamp') or now_iso(),
            'server_ts': now_iso(),
        })
        return jsonify({"success": True})
    except Exception as e:
        return _pt_error(str(e), 500)


@app.route('/api/payment/create', methods=['POST'])
def mobile_create_payment():
    """
    Create a payment session — routes to Paymob (EG) or Tap Payments (GCC).

    Body: { user_id, tier, billing_cycle, country }
    country: ISO 3166-1 alpha-2 (EG → Paymob; AE/SA/KW/BH/QA/OM → Tap)
    billing_cycle: 'monthly' | '6months' | 'yearly'
    Returns: { payment_url, order_id, gateway, currency, amount }
    """
    body          = request.get_json(silent=True) or {}
    user_id       = body.get('user_id', '').strip()
    tier          = body.get('tier', '').strip().lower()
    billing_cycle = body.get('billing_cycle', 'monthly').strip().lower()
    country       = body.get('country', 'EG').strip().upper()

    if not user_id or tier not in TIER_PRICES_EGP:
        return jsonify({"success": False, "error": "user_id and valid tier required"}), 400

    user_doc = db.collection('users').document(user_id).get()
    u = user_doc.to_dict() if user_doc.exists else {}

    if country in GCC_COUNTRIES:
        return _create_tap_payment(user_id, u, tier, billing_cycle, country)
    return _create_paymob_payment(user_id, u, tier, billing_cycle)


def _create_paymob_payment(user_id, u, tier, billing_cycle):
    """Create a Paymob (Egypt) payment session. Returns Flask response."""
    amount_egp   = TIER_PRICES_EGP[tier].get(billing_cycle, TIER_PRICES_EGP[tier]['monthly'])
    amount_cents = int(amount_egp * 100)

    api_key        = os.getenv('PAYMOB_API_KEY', '')
    integration_id = os.getenv('PAYMOB_INTEGRATION_ID', '')
    iframe_id      = os.getenv('PAYMOB_IFRAME_ID', '')

    if not api_key:
        return jsonify({"success": False, "error": "Paymob not configured"}), 503

    sess = requests.Session()
    try:
        auth_resp = sess.post(
            'https://accept.paymob.com/api/auth/tokens',
            json={'api_key': api_key}, timeout=10,
        )
        auth_resp.raise_for_status()
        auth_token = auth_resp.json()['token']

        order_resp = sess.post(
            'https://accept.paymob.com/api/ecommerce/orders',
            json={
                'auth_token':      auth_token,
                'delivery_needed': False,
                'amount_cents':    amount_cents,
                'currency':        'EGP',
                'items': [{
                    'name':         f'DealHunter {tier.title()} ({billing_cycle})',
                    'amount_cents': amount_cents,
                    'description':  f'DealHunter {tier.title()} membership',
                    'quantity':     1,
                }],
            }, timeout=10,
        )
        order_resp.raise_for_status()
        order_id = order_resp.json()['id']

        key_resp = sess.post(
            'https://accept.paymob.com/api/acceptance/payment_keys',
            json={
                'auth_token':     auth_token,
                'amount_cents':   amount_cents,
                'expiration':     3600,
                'order_id':       order_id,
                'currency':       'EGP',
                'integration_id': int(integration_id),
                'billing_data': {
                    'first_name':      u.get('display_name', 'DealHunter').split()[0],
                    'last_name':       (u.get('display_name', 'User').split() + ['User'])[-1],
                    'email':           u.get('email', 'no-reply@dealhunter.app'),
                    'phone_number':    u.get('phone', '+20000000000'),
                    'apartment':       'NA', 'floor': 'NA', 'street': 'NA',
                    'building':        'NA', 'shipping_method': 'NA',
                    'postal_code':     'NA', 'city': 'NA',
                    'country':         'EG', 'state': 'NA',
                },
            }, timeout=10,
        )
        key_resp.raise_for_status()
        payment_key = key_resp.json()['token']
        payment_url = (
            f'https://accept.paymob.com/api/acceptance/iframes/{iframe_id}'
            f'?payment_token={payment_key}'
        )

        db.collection('payment_transactions').add({
            'user_id':       user_id,
            'tier':          tier,
            'billing_cycle': billing_cycle,
            'amount':        amount_egp,
            'currency':      'EGP',
            'gateway':       'paymob',
            'order_id':      str(order_id),
            'status':        'pending',
            'created_at':    now_iso(),
        })

        return jsonify({
            "success":     True,
            "gateway":     "paymob",
            "payment_url": payment_url,
            "order_id":    str(order_id),
            "currency":    "EGP",
            "amount":      amount_egp,
        })
    except Exception as e:
        return _pt_error(f'Paymob payment creation failed: {e}', 500)


def _create_tap_payment(user_id, u, tier, billing_cycle, country):
    """Create a Tap Payments (GCC) charge. Returns Flask response."""
    amount_aed = TIER_PRICES_AED[tier].get(billing_cycle, TIER_PRICES_AED[tier]['monthly'])

    tap_secret = os.getenv('TAP_SECRET_KEY', '')
    if not tap_secret:
        return jsonify({"success": False, "error": "Tap Payments not configured"}), 503

    display_name = u.get('display_name', 'DealHunter User')
    name_parts   = display_name.split(maxsplit=1)
    first_name   = name_parts[0]
    last_name    = name_parts[1] if len(name_parts) > 1 else 'User'

    try:
        resp = requests.post(
            'https://api.tap.company/v2/charges',
            headers={
                'Authorization': f'Bearer {tap_secret}',
                'Content-Type':  'application/json',
            },
            json={
                'amount':      amount_aed,
                'currency':    'AED',
                'customer_initiated': True,
                'threeDSecure': True,
                'save_card':    False,
                'description':  f'DealHunter {tier.title()} ({billing_cycle})',
                'metadata':     {
                    'user_id':       user_id,
                    'tier':          tier,
                    'billing_cycle': billing_cycle,
                },
                'reference':    {
                    'transaction': f'dh_{user_id[:8]}_{int(time.time())}',
                    'order':       f'dh_order_{int(time.time())}',
                },
                'receipt':      {'email': True, 'sms': False},
                'customer': {
                    'first_name': first_name,
                    'last_name':  last_name,
                    'email':      u.get('email', 'no-reply@dealhunter.app'),
                    'phone':      {
                        'country_code': '971',
                        'number':       u.get('phone', '500000000').lstrip('+'),
                    },
                },
                'source': {'id': 'src_all'},
                'post': {
                    'url': os.getenv(
                        'TAP_CALLBACK_URL',
                        'https://dealhunter-scraper.onrender.com/api/payment/tap-callback',
                    ),
                },
                'redirect': {
                    'url': os.getenv(
                        'APP_PAYMENT_RETURN_URL',
                        'https://dealhunter.app/payment/result',
                    ),
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        charge = resp.json()
        charge_id   = charge.get('id', '')
        payment_url = charge.get('transaction', {}).get('url', '')

        db.collection('payment_transactions').add({
            'user_id':       user_id,
            'tier':          tier,
            'billing_cycle': billing_cycle,
            'amount':        amount_aed,
            'currency':      'AED',
            'gateway':       'tap',
            'order_id':      charge_id,
            'status':        'pending',
            'created_at':    now_iso(),
        })

        return jsonify({
            "success":     True,
            "gateway":     "tap",
            "payment_url": payment_url,
            "order_id":    charge_id,
            "currency":    "AED",
            "amount":      amount_aed,
        })
    except Exception as e:
        return _pt_error(f'Tap payment creation failed: {e}', 500)


@app.route('/api/payment/tap-callback', methods=['POST'])
def tap_payment_callback():
    """
    Tap Payments POST webhook — called after the user completes (or fails) payment.
    Tap sends charge object as JSON body.
    """
    payload = request.get_json(silent=True) or {}
    charge_id = payload.get('id', '')
    status    = payload.get('status', '')      # CAPTURED | VOID | FAILED | …
    metadata  = payload.get('metadata') or {}

    user_id       = metadata.get('user_id', '')
    tier          = metadata.get('tier', '')
    billing_cycle = metadata.get('billing_cycle', 'monthly')

    if not charge_id:
        return jsonify({"success": False, "error": "Missing charge id"}), 400

    try:
        # Update the pending transaction record
        txn_query = (db.collection('payment_transactions')
                       .where('order_id', '==', charge_id)
                       .limit(1)
                       .stream())
        for txn in txn_query:
            txn.reference.update({
                'status':      status.lower(),
                'updated_at':  now_iso(),
                'raw_status':  status,
            })

        if status == 'CAPTURED' and user_id and tier:
            _activate_membership(user_id, tier, billing_cycle, gateway='tap',
                                 order_id=charge_id)

        return jsonify({"success": True})
    except Exception as e:
        return _pt_error(f'Tap callback error: {e}', 500)


@app.route('/api/payment/paymob-callback', methods=['POST'])
def paymob_payment_callback():
    """
    Paymob transaction callback — HMAC-verified POST from Paymob.
    Activates membership on successful payment.
    """
    payload = request.get_json(silent=True) or {}
    obj     = payload.get('obj', {})
    hmac_received = request.args.get('hmac', '')

    hmac_secret = os.getenv('PAYMOB_HMAC_SECRET', '')
    if hmac_secret:
        # Build the HMAC string in Paymob's documented field order
        hmac_fields = [
            str(obj.get('amount_cents', '')),
            str(obj.get('created_at', '')),
            str(obj.get('currency', '')),
            str(obj.get('error_occured', '')),
            str(obj.get('has_parent_transaction', '')),
            str(obj.get('id', '')),
            str(obj.get('integration_id', '')),
            str(obj.get('is_3d_secure', '')),
            str(obj.get('is_auth', '')),
            str(obj.get('is_capture', '')),
            str(obj.get('is_refunded', '')),
            str(obj.get('is_standalone_payment', '')),
            str(obj.get('is_voided', '')),
            str(obj.get('order', {}).get('id', '') if isinstance(obj.get('order'), dict) else obj.get('order', '')),
            str(obj.get('owner', '')),
            str(obj.get('pending', '')),
            str(obj.get('source_data.pan', '')),
            str(obj.get('source_data.sub_type', '')),
            str(obj.get('source_data.type', '')),
            str(obj.get('success', '')),
        ]
        hmac_string   = ''.join(hmac_fields)
        hmac_computed = hmac.new(
            hmac_secret.encode(), hmac_string.encode(), hashlib.sha512
        ).hexdigest()
        if not hmac_received or hmac_computed != hmac_received:
            return jsonify({"success": False, "error": "HMAC mismatch"}), 403

    success  = obj.get('success', False)
    order_id = str(obj.get('order', {}).get('id', '') if isinstance(obj.get('order'), dict) else obj.get('order', ''))

    try:
        txn_query = (db.collection('payment_transactions')
                       .where('order_id', '==', order_id)
                       .limit(1)
                       .stream())
        user_id = tier = billing_cycle = None
        for txn in txn_query:
            data = txn.to_dict()
            user_id, tier, billing_cycle = (
                data.get('user_id'), data.get('tier'), data.get('billing_cycle', 'monthly')
            )
            txn.reference.update({
                'status':     'completed' if success else 'failed',
                'updated_at': now_iso(),
            })

        if success and user_id and tier:
            _activate_membership(user_id, tier, billing_cycle, gateway='paymob',
                                 order_id=order_id)

        return jsonify({"success": True})
    except Exception as e:
        return _pt_error(f'Paymob callback error: {e}', 500)


def _activate_membership(user_id: str, tier: str, billing_cycle: str,
                          gateway: str, order_id: str):
    """Upgrade user's Firestore membership record after confirmed payment."""
    now = now_iso()
    db.collection('users').document(user_id).update({
        'membership.tier':          tier,
        'membership.billing_cycle': billing_cycle,
        'membership.gateway':       gateway,
        'membership.last_order_id': order_id,
        'membership.activated_at':  now,
        'last_updated_at':          now,
    })


@app.route('/api/referral/apply', methods=['POST'])
def mobile_apply_referral():
    """
    Validate and apply a referral code.
    Body: { user_id, referral_code }
    """
    body    = request.get_json(silent=True) or {}
    uid     = body.get('user_id', '').strip()
    code    = body.get('referral_code', '').strip().upper()
    if not uid or not code:
        return jsonify({"success": False, "error": "user_id and referral_code required"}), 400

    try:
        # Find the owner of this referral code
        matches = list(db.collection('users')
                         .where('referral_code', '==', code)
                         .limit(1)
                         .stream())
        if not matches:
            return jsonify({"success": False, "error": "Invalid referral code"}), 404

        referrer_uid = matches[0].id
        if referrer_uid == uid:
            return jsonify({"success": False, "error": "Cannot use your own referral code"}), 400

        # Check if this user already used a referral code
        user_doc = db.collection('users').document(uid).get()
        if user_doc.exists and user_doc.to_dict().get('referral_used_by'):
            return jsonify({"success": False, "error": "Referral code already applied"}), 409

        # Credit both parties in Firestore (reward logic handled by Cloud Function)
        db.collection('users').document(uid).update({
            'referral_used_by': referrer_uid,
            'referral_applied_at': now_iso(),
        })
        db.collection('referral_events').add({
            'referrer_uid':  referrer_uid,
            'referred_uid':  uid,
            'code':          code,
            'created_at':    now_iso(),
            'reward_status': 'pending',
        })

        return jsonify({"success": True, "message": "Referral applied. Reward pending."})
    except Exception as e:
        return _pt_error(str(e), 500)


# ── Admin API ────────────────────────────────────────────────────────────────

@app.route('/api/admin/notify', methods=['POST'])
@require_admin
def admin_send_notification():
    """
    Broadcast FCM push notification from the admin app.

    Body: {
      title, body, image_url?,
      target_type: 'all' | 'tier' | 'group' | 'user',
      target_id?:  tier name | group doc ID | user UID,
      data?:       { key: value, … }
    }
    """
    payload = request.get_json(silent=True) or {}
    title       = payload.get('title', '').strip()
    body_text   = payload.get('body', '').strip()
    image_url   = payload.get('image_url')
    target_type = payload.get('target_type', 'all')
    target_id   = payload.get('target_id')
    extra_data  = {str(k): str(v) for k, v in (payload.get('data') or {}).items()}

    if not title or not body_text:
        return jsonify({"success": False, "error": "title and body required"}), 400

    notification = messaging.Notification(
        title=title,
        body=body_text,
        image=image_url or None,
    )
    success_count = 0
    failure_count = 0

    try:
        if target_type in ('all', 'tier'):
            topic = 'all_users' if target_type == 'all' else f'tier_{target_id}'
            msg   = messaging.Message(
                notification=notification,
                data=extra_data,
                topic=topic,
            )
            messaging.send(msg)
            success_count = 1  # topic sends don't return per-device counts

        elif target_type == 'group':
            # Fetch member UIDs from user_groups
            group_doc = db.collection('user_groups').document(target_id).get()
            if not group_doc.exists:
                return jsonify({"success": False, "error": "Group not found"}), 404
            member_uids = (group_doc.to_dict().get('member_uids') or [])
            tokens      = _get_fcm_tokens(member_uids)
            s, f        = _send_multicast(tokens, notification, extra_data)
            success_count, failure_count = s, f

        elif target_type == 'user':
            tokens = _get_fcm_tokens([target_id])
            if tokens:
                msg = messaging.Message(
                    notification=notification,
                    data=extra_data,
                    token=tokens[0],
                )
                messaging.send(msg)
                success_count = 1
            else:
                failure_count = 1

        else:
            return jsonify({"success": False, "error": "Invalid target_type"}), 400

        return jsonify({
            "success":       True,
            "success_count": success_count,
            "failure_count": failure_count,
        })
    except Exception as e:
        return _pt_error(f'Notification failed: {e}', 500)


def _get_fcm_tokens(uids: list) -> list:
    """Fetch FCM tokens for a list of user UIDs from Firestore."""
    tokens = []
    for uid in uids:
        try:
            doc = db.collection('users').document(uid).get()
            if doc.exists:
                token = doc.to_dict().get('fcm_token')
                if token:
                    tokens.append(token)
        except Exception:
            pass
    return tokens


def _send_multicast(tokens: list, notification, data: dict) -> tuple:
    """Send FCM multicast in batches of 500. Returns (success, failure) counts."""
    if not tokens:
        return 0, 0
    success = failure = 0
    batch_size = 500
    for i in range(0, len(tokens), batch_size):
        batch = tokens[i:i + batch_size]
        msg   = messaging.MulticastMessage(
            notification=notification,
            data=data,
            tokens=batch,
        )
        resp = messaging.send_each_for_multicast(msg)
        success  += resp.success_count
        failure  += resp.failure_count
    return success, failure


@app.route('/api/debug/scraper-log')
def scraper_log():
    """Read the last N lines of the scraper log file."""
    lines = int(request.args.get("lines", 100))
    try:
        with open("/tmp/scraper.log", "r") as f:
            content = f.read()
        tail = content[-lines * 120:]  # ~120 chars per line estimate
        return jsonify({"log": tail, "total_bytes": len(content)})
    except FileNotFoundError:
        return jsonify({"error": "Scraper log not found — scraper may not have started yet"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/debug/noon')
def debug_noon():
    """Diagnostic: fetch a Noon page via direct + ScraperAPI and compare."""
    SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")
    region = request.args.get("region", "egypt-en")
    q      = request.args.get("q", "samsung")
    url = f"https://www.noon.com/{region}/search/?q={q}&limit=48&sort%5Bby%5D=discount&sort%5Bdir%5D=desc"

    def _analyse(r):
        if not r:
            return {"status": None, "body_len": 0, "has_next_data": False,
                    "page_props_keys": [], "body_snippet": ""}
        body = r.text
        nd_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>\s*({.+?})\s*</script>', body, re.DOTALL)
        nd_keys = []
        if nd_match:
            try:
                nd = json.loads(nd_match.group(1))
                nd_keys = list(nd.get("props", {}).get("pageProps", {}).keys())
            except Exception:
                pass
        return {"status": r.status_code, "body_len": len(body),
                "has_next_data": bool(nd_match), "page_props_keys": nd_keys,
                "body_snippet": body[:1500]}

    direct_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.noon.com/",
    }
    try:
        direct_r = requests.get(url, headers=direct_headers, timeout=20, allow_redirects=True)
    except Exception as e:
        direct_r = None

    scraper_r = None
    if SCRAPER_API_KEY:
        try:
            scraper_r = requests.get("http://api.scraperapi.com", params={
                "api_key": SCRAPER_API_KEY, "url": url,
                "render": "false", "country_code": region[:2], "premium": "false",
            }, timeout=60)
        except Exception:
            pass

    return jsonify({
        "url": url,
        "direct": _analyse(direct_r),
        "scraperapi": _analyse(scraper_r),
    })


@app.route('/api/v1/admin/check-auth')
def admin_check_auth():
    """Verify Firebase token and confirm the user is in admin_users (by UID or email)."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'is_admin': False, 'error': 'Missing token'}), 401
    token = auth_header[7:]
    try:
        decoded = fb_auth.verify_id_token(token)
        uid   = decoded['uid']
        email = decoded.get('email', '')

        # Check by UID first, then by email (support both doc ID conventions)
        doc = db.collection('admin_users').document(uid).get()
        if not doc.exists and email:
            doc = db.collection('admin_users').document(email).get()

        if not doc.exists:
            return jsonify({'is_admin': False})

        data = doc.to_dict() or {}
        return jsonify({
            'is_admin':    True,
            'uid':         uid,
            'email':       email,
            'role':        data.get('role', 'admin'),
            'permissions': data.get('permissions', []),
            'name':        data.get('name', ''),
        })
    except Exception as e:
        return jsonify({'is_admin': False, 'error': str(e)}), 401


@app.route('/api/v1/admin/offers')
def admin_offers():
    """Admin: paginated deal list with optional source/category filters."""
    source   = request.args.get('source')
    category = request.args.get('category')
    limit    = min(int(request.args.get('limit', 50)), 200)
    try:
        q = db.collection('deals').order_by('timestamp', direction=firestore.Query.DESCENDING)
        if source:   q = q.where('site',     '==', source)
        if category: q = q.where('category', '==', category)
        docs = list(q.limit(limit).stream())
        deals = []
        for d in docs:
            data = d.to_dict() or {}
            ts = data.get('timestamp')
            if hasattr(ts, 'isoformat'):
                data['timestamp'] = ts.isoformat()
            deals.append({'id': d.id, **data})
        return jsonify({'success': True, 'deals': deals, 'count': len(deals)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/groups')
def admin_groups():
    """Admin: list all user groups."""
    try:
        docs = list(db.collection('user_groups').stream())
        groups = [{'id': d.id, **d.to_dict()} for d in docs]
        return jsonify({'success': True, 'groups': groups})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/tiers')
def admin_tiers():
    """Admin: list tier configurations from Firestore (or return defaults)."""
    defaults = [
        {'name': 'free',    'daily_limit': 50,    'price': 0,  'features': ['View Deals']},
        {'name': 'trial',   'daily_limit': 100,   'price': 0,  'features': ['View Deals', 'Price History', 'Groups']},
        {'name': 'premium', 'daily_limit': 500,   'price': 5,  'features': ['View Deals', 'Price History', 'Groups', 'Gift Deals']},
        {'name': 'vip',     'daily_limit': 99999, 'price': 10, 'features': ['All Premium Features', 'Priority Support']},
    ]
    try:
        docs = list(db.collection('tiers').stream())
        if docs:
            tiers = [{'name': d.id, **d.to_dict()} for d in docs]
        else:
            tiers = defaults
        return jsonify({'success': True, 'tiers': tiers})
    except Exception as e:
        return jsonify({'success': True, 'tiers': defaults})


@app.route('/admin')
@app.route('/admin.html')
def serve_admin():
    resp = send_from_directory('.', 'admin.html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

@app.errorhandler(404)
def not_found(e): return jsonify({"success":False,"error":"Not found"}),404
@app.errorhandler(500)
def server_error(e): return jsonify({"success":False,"error":"Server error"}),500

print("Starting...")
_load_shops()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
