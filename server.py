from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, messaging, auth as fb_auth
import json, os, re, requests, hashlib, hmac, base64, time, traceback, math
from datetime import datetime, timezone, timedelta
from functools import wraps
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.backends import default_backend

app = Flask(__name__)
_cors_origins = os.getenv('CORS_ORIGINS', 'https://dealhunter-scraper.onrender.com')
CORS(app, origins=_cors_origins.split(','))

firebase_key_json = (os.getenv("FIREBASE_KEY_JSON") or
                     os.getenv("FIREBASE_CREDENTIALS_JSON") or
                     os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON"))
if firebase_key_json:
    cred = credentials.Certificate(json.loads(firebase_key_json))
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized")
else:
    raise RuntimeError("Firebase credentials not found — set FIREBASE_KEY_JSON env var")

db = firestore.client()

def _sanitize_json(obj):
    """
    Recursively replace NaN/Infinity float values with 0 so Flask's jsonify
    never emits the literal token 'NaN' (invalid JSON).

    Root cause: Firestore can store NaN via Python's float('nan').  When that
    value is returned through jsonify it produces  "price":NaN  which the
    browser's JSON.parse rejects with
    'Unexpected token N … is not valid JSON'.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return 0
    return obj

# ── In-memory admin cache (loaded once at startup, refreshed hourly) ────────
# Eliminates Firestore reads on every login — critical to stay under quota.
_admin_cache: dict = {}
_admin_cache_ts: float = 0.0

def _reload_admin_cache(force: bool = False) -> None:
    global _admin_cache, _admin_cache_ts
    now = time.time()
    if not force and now - _admin_cache_ts < 3600:
        return
    try:
        docs = list(db.collection('admin_users').stream())
        _admin_cache = {d.id: (d.to_dict() or {}) for d in docs}
        _admin_cache_ts = now
        print(f'[admin-cache] loaded {len(_admin_cache)} admins')
    except Exception as exc:
        print(f'[admin-cache] load failed: {exc}')

def _get_admin_data(uid: str, email: str) -> dict | None:
    _reload_admin_cache()
    return _admin_cache.get(uid) or _admin_cache.get(email) or None

# Load at startup (best-effort; quota errors are caught above)
_reload_admin_cache(force=True)

# ── Stats result cache (5-minute TTL) ───────────────────────────────────────
_stats_cache: dict = {'data': None, 'at': 0.0}
_STATS_TTL = 300  # seconds

# ── Firebase token: local JWT decode (no API call, no quota) ───────────────
# Security gate is the in-memory admin cache above — UID/email must be present.
def _uid_email_from_token(token):
    """Decode Firebase ID token locally. Checks format and expiry; no network call."""
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError('Malformed token')
    pad     = 4 - len(parts[1]) % 4
    padded  = parts[1] + '=' * (pad % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    if time.time() > payload.get('exp', 0):
        raise ValueError('Token expired')
    uid   = payload.get('user_id') or payload.get('sub', '')
    email = payload.get('email', '')
    if not uid:
        raise ValueError('No uid in token')
    return uid, email

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

# ── Structured event logger ─────────────────────────────────────────────────
_logging_in_progress = False  # guard against recursive log calls

def _log_event(level, category, message, details=None):
    """Write a structured log entry to admin_logs collection (never crashes the app)."""
    global _logging_in_progress
    if _logging_in_progress:
        return
    _logging_in_progress = True
    try:
        db.collection('admin_logs').add({
            'level':     level,       # error | warn | info
            'category':  category,    # scraper | auth | db | api | system
            'message':   message,
            'details':   details or {},
            'path':      request.path if request else '',
            'method':    request.method if request else '',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
    finally:
        _logging_in_progress = False

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


@app.route('/api/debug/amazon-test')
def debug_amazon_test():
    """
    Test ALL 5 RapidAPI Amazon integrations with one request.
    Visit: /api/debug/amazon-test
    """
    KEY = (os.getenv("RAPIDAPI_KEY") or os.getenv("RAPID_API_KEY") or "")
    if not KEY:
        return jsonify({"error": "RAPIDAPI_KEY not set in Railway Variables"}), 400

    hdrs = lambda host: {"x-rapidapi-host": host, "x-rapidapi-key": KEY}
    results = {}

    # 1 — real-time-amazon-data: search EG
    try:
        r = requests.get("https://real-time-amazon-data.p.rapidapi.com/search",
            headers=hdrs("real-time-amazon-data.p.rapidapi.com"),
            params={"query": "laptop", "page": "1", "country": "EG"}, timeout=15)
        prods = (r.json().get("data") or {}).get("products") or []
        results["1_real_time_search_EG"] = {
            "http": r.status_code, "products": len(prods),
            "sample": (prods[0].get("product_title","")[:50] if prods else None)}
    except Exception as e:
        results["1_real_time_search_EG"] = {"error": str(e)}

    # 2 — real-time-amazon-data: search US (free tier baseline)
    try:
        r = requests.get("https://real-time-amazon-data.p.rapidapi.com/search",
            headers=hdrs("real-time-amazon-data.p.rapidapi.com"),
            params={"query": "laptop", "page": "1", "country": "US"}, timeout=15)
        prods = (r.json().get("data") or {}).get("products") or []
        results["2_real_time_search_US"] = {
            "http": r.status_code, "products": len(prods),
            "sample": (prods[0].get("product_title","")[:50] if prods else None)}
    except Exception as e:
        results["2_real_time_search_US"] = {"error": str(e)}

    # 3 — amazon-product-info2: search via direct Amazon.eg URL
    try:
        r = requests.get("https://amazon-product-info2.p.rapidapi.com/Amazon/details",
            headers=hdrs("amazon-product-info2.p.rapidapi.com"),
            params={"url": "https://www.amazon.eg/s?k=laptop"}, timeout=15)
        body = r.json()
        prods = body.get("products") or body.get("data") or body.get("results") or []
        if isinstance(prods, dict):
            prods = list(prods.values())[:5]
        results["3_product_info2_EG_URL"] = {
            "http": r.status_code, "top_keys": list(body.keys())[:8],
            "items": len(prods) if isinstance(prods, list) else "not a list",
            "raw_snippet": str(body)[:300]}
    except Exception as e:
        results["3_product_info2_EG_URL"] = {"error": str(e)}

    # 4 — amazon-pricing-and-product-info: domain=eg with known ASIN
    try:
        r = requests.get("https://amazon-pricing-and-product-info.p.rapidapi.com/",
            headers=hdrs("amazon-pricing-and-product-info.p.rapidapi.com"),
            params={"asin": "B07GR5MSKD", "domain": "eg"}, timeout=15)
        body = r.json()
        results["4_pricing_domain_eg"] = {
            "http": r.status_code, "top_keys": list(body.keys())[:8],
            "raw_snippet": str(body)[:300]}
    except Exception as e:
        results["4_pricing_domain_eg"] = {"error": str(e)}

    # 5 — realtime-amazon-data: best-sellers
    try:
        r = requests.get("https://realtime-amazon-data.p.rapidapi.com/best-sellers",
            headers=hdrs("realtime-amazon-data.p.rapidapi.com"),
            params={"category": "electronics", "country": "us", "page": "1"}, timeout=15)
        body = r.json()
        prods = body.get("best_sellers") or body.get("products") or body.get("data") or []
        results["5_realtime_bestsellers"] = {
            "http": r.status_code, "top_keys": list(body.keys())[:8],
            "items": len(prods) if isinstance(prods, list) else "not a list",
            "sample": (prods[0].get("product_title","")[:50] if isinstance(prods,list) and prods else None)}
    except Exception as e:
        results["5_realtime_bestsellers"] = {"error": str(e)}

    return jsonify({"key_used": KEY[:8] + "...", "results": results})


@app.route('/api/debug/sites')
def debug_sites():
    """
    Test B.Tech and Carrefour directly — shows HTTP status and what HTML/JSON they return.
    Visit: /api/debug/sites
    """
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    result = {}

    # B.Tech
    try:
        r = requests.get("https://btech.com/en/sale.html?pageSize=24", headers=hdrs, timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.content, "lxml")
        products = (
            soup.find_all("li",  class_=lambda c: c and "product-item" in str(c)) or
            soup.find_all("div", class_=lambda c: c and "product-item" in str(c)) or
            soup.find_all("div", class_=lambda c: c and "product-card" in str(c))
        )
        sample_title = ""
        if products:
            el = (products[0].find("a", class_="product-item-link") or
                  products[0].find("a") or products[0].find("h2") or products[0].find("h3"))
            sample_title = el.get_text(strip=True)[:60] if el else "(found product but no title)"
        result["btech"] = {
            "http": r.status_code,
            "body_len": len(r.text),
            "products_found": len(products),
            "sample_title": sample_title,
            "body_snippet": r.text[:400],
        }
    except Exception as e:
        result["btech"] = {"error": str(e)}

    # Carrefour — try multiple API versions
    carrefour_result = {}
    api_versions = ["v9", "v8", "v7", "v6", "v5", "v4"]
    for v in api_versions:
        try:
            url = f"https://www.carrefouregypt.com/api/{v}/page?url=/mafegy/en/c/electronics&page=0&pageSize=10&sortBy=discountPercentage&sortOrder=desc"
            r = requests.get(url, headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.carrefouregypt.com/",
                "lang": "en", "country": "EG",
            }, timeout=12)
            body_str = r.text[:500]
            try:
                body = r.json()
                has_products = bool(
                    body.get("data", {}).get("products", {}).get("results") or
                    body.get("products", {}).get("results") or
                    body.get("results")
                )
                carrefour_result[v] = {"http": r.status_code, "has_products": has_products, "keys": list(body.keys())[:6]}
            except Exception:
                carrefour_result[v] = {"http": r.status_code, "raw": body_str}
            if r.status_code == 200:
                break
        except Exception as e:
            carrefour_result[v] = {"error": str(e)}
    result["carrefour_api_versions"] = carrefour_result

    # Carrefour HTML fallback test
    try:
        r = requests.get(
            "https://www.carrefouregypt.com/mafegy/en/c/electronics?pageSize=10&sortBy=discountPercentage",
            headers=hdrs, timeout=15)
        result["carrefour_html"] = {
            "http": r.status_code,
            "body_len": len(r.text),
            "has_next_data": "__NEXT_DATA__" in r.text,
        }
    except Exception as e:
        result["carrefour_html"] = {"error": str(e)}

    return jsonify(result)


@app.route('/api/debug/scraper-status')
def debug_scraper_status():
    """
    Show scraper health from last cycle + last 20 lines of scraper.log.
    Visit: /api/debug/scraper-status
    """
    result = {"scraper_log_tail": None, "last_health": None}

    # Read scraper log tail
    try:
        with open("/tmp/scraper.log", "r") as f:
            lines = f.readlines()
        result["scraper_log_tail"] = "".join(lines[-40:])
        result["log_total_lines"]  = len(lines)
    except FileNotFoundError:
        result["scraper_log_tail"] = "FILE NOT FOUND — scraper process has not started"
    except Exception as e:
        result["scraper_log_tail"] = f"Error reading log: {e}"

    # Read last health from Firestore
    try:
        doc = db.collection("scraper_health").document("latest").get()
        if doc.exists:
            d = doc.to_dict() or {}
            # Convert Firestore timestamps to strings
            ts = d.get("timestamp")
            result["last_health"] = {
                "timestamp": str(ts) if ts else None,
                "cycle":     d.get("cycle", {}),
                "has_alerts": d.get("has_alerts", False),
                "broken":    d.get("broken_scrapers", []),
            }
        else:
            result["last_health"] = "No scraper_health/latest document — scraper has never completed a cycle"
    except Exception as e:
        result["last_health"] = f"Firestore error: {e}"

    # Read last deal timestamp
    try:
        docs = list(db.collection("deals").order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        ).limit(1).stream())
        if docs:
            d = docs[0].to_dict() or {}
            result["newest_deal_timestamp"] = d.get("timestamp")
            result["newest_deal_site"]      = d.get("site")
            result["newest_deal_title"]     = (d.get("title") or "")[:60]
        else:
            result["newest_deal_timestamp"] = "No deals in database"
    except Exception as e:
        result["newest_deal_timestamp"] = f"Error: {e}"

    return jsonify(result)


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


@app.route('/api/debug/fcm-test')
def debug_fcm_test():
    """
    Diagnose FCM configuration. Sends two test messages and reports results.
    No auth required — Railway internal use only.

    Visit: /api/debug/fcm-test

    What to look for:
      topic_test.status = 'success'  → FCM works, service account has correct permissions
      topic_test.status = 'error'    → See topic_test.error + topic_test.cause for fix
      all_users_test.status = 'success' → Users subscribed to all_users will receive pushes

    Common errors and fixes:
      'SERVICE_UNAVAILABLE'  → Transient Firebase outage; retry later
      'INVALID_ARGUMENT'     → Message format bug; check data fields are all strings
      '403 Forbidden' / 'Caller does not have permission'
          → Firebase service account is missing 'Firebase Cloud Messaging Admin' role.
             Fix: Google Cloud Console → IAM → find your service account → Add role →
             'Firebase Cloud Messaging Admin'  (or 'Firebase Admin SDK Administrator Service Agent')
      'App not initialized'  → FIREBASE_KEY_JSON env var missing or malformed
    """
    results = {}
    timestamp = datetime.now(timezone.utc).isoformat()

    # Test 1 — send to a throwaway debug topic (no real users affected)
    try:
        msg_id = messaging.send(messaging.Message(
            topic="fcm_debug_test",
            notification=messaging.Notification(
                title="FCM Connectivity Test",
                body=f"Backend FCM test at {timestamp}",
            ),
            data={"type": "debug_test", "ts": timestamp},
        ))
        results['topic_test'] = {
            'status': 'success',
            'message_id': msg_id,
            'meaning': 'FCM is working. Service account has correct permissions.',
        }
    except Exception as e:
        results['topic_test'] = {
            'status': 'error',
            'error': str(e),
            'type': type(e).__name__,
            'cause': (
                'Service account missing FCM permissions'
                if 'permission' in str(e).lower() or '403' in str(e)
                else 'Check error message above for root cause'
            ),
        }

    # Test 2 — send to all_users topic (real users will receive this if subscribed)
    try:
        msg_id = messaging.send(messaging.Message(
            topic="all_users",
            notification=messaging.Notification(
                title="🔔 DealHunter Test Notification",
                body="If you see this, push notifications are working correctly!",
            ),
            data={"type": "test", "ts": timestamp},
            android=messaging.AndroidConfig(priority="high"),
        ))
        results['all_users_test'] = {
            'status': 'success',
            'message_id': msg_id,
            'meaning': 'Sent to all_users topic. Users subscribed will receive this push.',
        }
    except Exception as e:
        results['all_users_test'] = {
            'status': 'error',
            'error': str(e),
            'type': type(e).__name__,
        }

    # Test 3 — check Firebase app is initialized
    try:
        _ = firebase_admin.get_app()
        results['firebase_init'] = {'status': 'ok', 'app_name': firebase_admin.get_app().name}
    except Exception as e:
        results['firebase_init'] = {'status': 'error', 'error': str(e)}

    overall_ok = all(v.get('status') in ('success', 'ok') for v in results.values())
    return jsonify({
        'overall': 'ALL OK — notifications should be working' if overall_ok else 'ERRORS FOUND — see results',
        'timestamp': timestamp,
        'results': results,
        'next_step': (
            'FCM is healthy. If users still do not receive notifications, check '
            'that the Flutter app subscribes to the correct FCM topic on login '
            '(all_users, tier_vip, tier_premium, or tier_free).'
            if overall_ok else
            'Fix the errors shown in results.topic_test.error above, then reload this page.'
        ),
    })


@app.route('/api/v1/admin/check-auth')
def admin_check_auth():
    """Verify Firebase token and confirm the user is in admin_users (by UID or email)."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'is_admin': False, 'error': 'Missing token'}), 401
    token = auth_header[7:]
    try:
        uid, email = _uid_email_from_token(token)
        data = _get_admin_data(uid, email)
        if not data:
            return jsonify({'is_admin': False, 'error': 'Not an admin'}), 401
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
    source      = request.args.get('source')
    source_type = request.args.get('source_type', 'site')  # 'site' or 'source'
    category    = request.args.get('category')
    limit       = min(int(request.args.get('limit', 50)), 500)
    try:
        # Fetch top deals ordered by timestamp, filter in Python to avoid
        # Firestore composite index requirements (order_by + where per field)
        fetch_limit = min(limit * 5, 500) if (source or category) else limit
        docs = list(db.collection('deals')
                    .order_by('timestamp', direction=firestore.Query.DESCENDING)
                    .limit(fetch_limit).stream())
        deals = []
        for d in docs:
            data = d.to_dict() or {}
            if source and data.get(source_type) != source:
                continue
            if category and data.get('category') != category:
                continue
            ts = data.get('timestamp')
            if hasattr(ts, 'isoformat'):
                data['timestamp'] = ts.isoformat()
            deals.append({'id': d.id, **data})
            if len(deals) >= limit:
                break
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


def _ts(val):
    return val.isoformat() if hasattr(val, 'isoformat') else val


@app.route('/api/v1/admin/stats')
def admin_stats():
    """Monitor stats: deals, users, per-source breakdown, latest deals."""
    now = time.time()
    if _stats_cache['data'] and now - _stats_cache['at'] < _STATS_TTL:
        return jsonify(_stats_cache['data'])
    try:
        deal_docs = list(db.collection('deals').stream())
        deals = []
        for d in deal_docs:
            row = d.to_dict() or {}
            row['_doc_id'] = d.id
            deals.append(row)

        clicks = sum(int(d.get('click_count') or 0) for d in deals)
        buys   = sum(int(d.get('buy_click_count') or 0) for d in deals)

        site_counts, site_last, site_fake, cat_counts = {}, {}, {}, {}
        for d in deals:
            s = d.get('site', 'unknown')
            site_counts[s] = site_counts.get(s, 0) + 1
            ts = _ts(d.get('timestamp'))
            if ts and (s not in site_last or ts > site_last[s]):
                site_last[s] = ts
            if d.get('fake_verdict') in ('SUSPICIOUS', 'FAKE'):
                site_fake[s] = site_fake.get(s, 0) + 1
            c = d.get('category', 'general')
            cat_counts[c] = cat_counts.get(c, 0) + 1

        user_docs = list(db.collection('users').stream())
        custom_docs = list(db.collection('admin').stream())
        custom_sources = [{'id': d.id, **d.to_dict()} for d in custom_docs]

        raw_latest = sorted(deals, key=lambda x: str(x.get('timestamp') or ''), reverse=True)[:10]
        latest = []
        for d in raw_latest:
            clean = {k: _ts(v) if hasattr(v, 'isoformat') else v
                     for k, v in d.items() if k != '_doc_id'}
            clean['id'] = d['_doc_id']
            latest.append(clean)

        result = {
            'success': True,
            'total_deals': len(deals),
            'total_users': len(user_docs),
            'clicks': clicks, 'buys': buys,
            'site_counts': site_counts,
            'site_last': site_last,
            'site_fake': site_fake,
            'cat_counts': cat_counts,
            'custom_sources': custom_sources,
            'latest_deals': latest,
        }
        _stats_cache.update({'data': result, 'at': time.time()})
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/users')
def admin_users():
    """Admin: list all app users."""
    try:
        docs = list(db.collection('users').stream())
        users = []
        for d in docs:
            data = d.to_dict() or {}
            for k in ('created_at', 'last_login', 'tier_upgraded_at'):
                data[k] = _ts(data.get(k))
            users.append({'id': d.id, **data})
        return jsonify({'success': True, 'users': users, 'count': len(users)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/users/<user_id>', methods=['PATCH'])
def admin_update_user(user_id):
    """Admin: update a user document (tier, daily_deal_limit, etc.)."""
    try:
        data = request.get_json() or {}
        for k in ('created_at', 'last_login', 'tier_upgraded_at'):
            data.pop(k, None)
        db.collection('users').document(user_id).update(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/team')
def admin_team():
    """Admin: list all admin_users."""
    try:
        docs = list(db.collection('admin_users').stream())
        team = []
        for d in docs:
            data = d.to_dict() or {}
            data['last_login'] = _ts(data.get('last_login'))
            team.append({'id': d.id, 'email': data.get('email', d.id), **data})
        return jsonify({'success': True, 'team': team})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/notifications')
def admin_notifications():
    """Admin: list sent notifications."""
    try:
        try:
            docs = list(db.collection('notifications')
                        .order_by('sent_at', direction=firestore.Query.DESCENDING)
                        .limit(100).stream())
        except Exception:
            docs = list(db.collection('notifications').limit(100).stream())
        notifs = []
        for d in docs:
            data = d.to_dict() or {}
            data['sent_at'] = _ts(data.get('sent_at'))
            notifs.append({'id': d.id, **data})
        return jsonify({'success': True, 'notifications': notifs})
    except Exception as e:
        return jsonify({'success': True, 'notifications': []})


# ── Generic Firestore proxy (admin panel only) ──────────────────────────────
_PROXY_COLLECTIONS = {
    'deals', 'users', 'admin', 'admin_users', 'notifications',
    'user_groups', 'special_offers', 'tier_config', 'tier_history',
    'fake_checks', 'scraper_health', 'admin_logs', 'country_pricing',
    'ab_tests', 'fraud_flags',
}


@app.route('/api/v1/admin/db/<collection>', methods=['GET', 'POST'])
@app.route('/api/v1/admin/db/<collection>/<doc_id>', methods=['GET', 'PATCH', 'PUT', 'DELETE'])
def admin_db_proxy(collection, doc_id=None):
    """Generic Firestore CRUD proxy for the admin panel."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': 'Invalid token: ' + str(e)}), 401

    if collection not in _PROXY_COLLECTIONS:
        return jsonify({'success': False, 'error': 'Collection not allowed'}), 403
    try:
        cref = db.collection(collection)
        if request.method == 'GET':
            if doc_id:
                doc = cref.document(doc_id).get()
                if not doc.exists:
                    return jsonify({'success': False, 'error': 'Not found'}), 404
                data = {k: _ts(v) for k, v in (doc.to_dict() or {}).items()}
                return jsonify({'success': True, 'id': doc.id, **data})
            else:
                q = cref
                where_f = request.args.get('where_field')
                where_v = request.args.get('where_value')
                order_by = request.args.get('order_by')
                order_dir = request.args.get('order_dir', 'asc')
                lim = int(request.args.get('limit', 100))
                if where_f and where_v:
                    q = q.where(where_f, '==', where_v)
                if order_by:
                    direction = (firestore.Query.DESCENDING if order_dir == 'desc'
                                 else firestore.Query.ASCENDING)
                    q = q.order_by(order_by, direction=direction)
                items = [{'id': d.id, **{k: _ts(v) for k, v in (d.to_dict() or {}).items()}}
                         for d in q.limit(lim).stream()]
                return jsonify({'success': True, 'items': items})
        elif request.method == 'POST':
            data = request.get_json() or {}
            _, ref = cref.add(data)
            return jsonify({'success': True, 'id': ref.id})
        elif request.method == 'PATCH':
            if not doc_id:
                return jsonify({'success': False, 'error': 'doc_id required'}), 400
            # set(merge=True) creates the doc if it doesn't exist; update() would fail
            cref.document(doc_id).set(request.get_json() or {}, merge=True)
            return jsonify({'success': True})
        elif request.method == 'PUT':
            if not doc_id:
                return jsonify({'success': False, 'error': 'doc_id required'}), 400
            merge = request.args.get('merge', 'false').lower() == 'true'
            cref.document(doc_id).set(request.get_json() or {}, merge=merge)
            return jsonify({'success': True})
        elif request.method == 'DELETE':
            if not doc_id:
                return jsonify({'success': False, 'error': 'doc_id required'}), 400
            cref.document(doc_id).delete()
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Convenience aliases used by existing admin.html code
@app.route('/api/v1/user-groups', methods=['POST'])
def create_user_group():
    data = request.get_json() or {}
    data.setdefault('created_at', datetime.now(timezone.utc).isoformat())
    _, ref = db.collection('user_groups').add(data)
    return jsonify({'success': True, 'id': ref.id})


@app.route('/api/v1/special-offers', methods=['POST'])
def create_special_offer():
    data = request.get_json() or {}
    data.setdefault('created_at', datetime.now(timezone.utc).isoformat())
    data.setdefault('is_active', True)
    data.setdefault('used_count', 0)
    _, ref = db.collection('special_offers').add(data)
    return jsonify({'success': True, 'id': ref.id})


@app.route('/api/v1/users/<user_id>/daily-limit', methods=['PUT'])
def update_user_daily_limit(user_id):
    data = request.get_json() or {}
    limit = data.get('daily_deal_limit')
    if not limit:
        return jsonify({'success': False, 'error': 'daily_deal_limit required'}), 400
    db.collection('users').document(user_id).update({
        'daily_deal_limit': int(limit), 'custom_daily_limit': True,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    })
    return jsonify({'success': True})


@app.route('/api/v1/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        fb_auth.delete_user(user_id)
    except Exception:
        pass
    db.collection('users').document(user_id).delete()
    return jsonify({'success': True})


@app.route('/api/v1/admin/sources')
def admin_sources():
    """Admin: custom scraper sources from 'admin' collection."""
    try:
        docs = list(db.collection('admin').stream())
        sources = [{'id': d.id, **d.to_dict()} for d in docs]
        return jsonify({'success': True, 'sources': sources})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/admin/tier-history')
def admin_tier_history():
    """Admin: tier change log."""
    try:
        docs = list(db.collection('tier_history')
                    .order_by('changed_at', direction=firestore.Query.DESCENDING)
                    .limit(50).stream())
        history = []
        for d in docs:
            data = d.to_dict() or {}
            data['changed_at'] = _ts(data.get('changed_at'))
            history.append({'id': d.id, **data})
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': True, 'history': []})


@app.route('/api/v1/admin/deals/<deal_id>', methods=['PATCH', 'DELETE'])
def admin_deal(deal_id):
    """Admin: update or delete a deal."""
    try:
        if request.method == 'DELETE':
            db.collection('deals').document(deal_id).delete()
            return jsonify({'success': True})
        data = request.get_json() or {}
        db.collection('deals').document(deal_id).update(data)
        return jsonify({'success': True})
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
        # tier_config is written by the admin panel; fall back to tiers, then defaults
        docs = list(db.collection('tier_config').stream())
        if not docs:
            docs = list(db.collection('tiers').stream())
        if docs:
            # _sanitize_json converts any NaN/Infinity floats → 0 so the
            # browser's JSON.parse never sees the invalid token 'NaN'.
            tiers = [_sanitize_json({'name': d.id, **d.to_dict()}) for d in docs]
        else:
            tiers = defaults
        return jsonify({'success': True, 'tiers': tiers})
    except Exception as e:
        print(f"[ERROR] admin_tiers: {e}")
        return jsonify({'success': True, 'tiers': defaults})


@app.route('/api/v1/notifications/send', methods=['POST'])
def send_notification():
    """Send push notification via Firebase Cloud Messaging."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        uid, email = _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

    data    = request.get_json() or {}
    title   = data.get('title', '')
    title_ar = data.get('title_ar', '')
    message  = data.get('message', '')
    message_ar = data.get('message_ar', '')
    target   = data.get('target', 'tier:all')
    channel  = data.get('channel', 'in_app')
    group_id = data.get('group_id', '')
    specific_user = data.get('specific_user', '')

    if not (title or title_ar):
        return jsonify({'success': False, 'error': 'Title required'}), 400
    if not (message or message_ar):
        return jsonify({'success': False, 'error': 'Message required'}), 400

    recipients = 0
    fcm_error  = None

    try:
        topic_map = {
            'tier:all': 'all_users', 'tier:vip': 'tier_vip',
            'tier:premium': 'tier_premium', 'tier:free': 'tier_free',
        }
        notif_obj = messaging.Notification(
            title=title or title_ar, body=message or message_ar)
        extra = {'title_ar': title_ar, 'message_ar': message_ar, 'channel': channel}

        if target in topic_map:
            topic = topic_map[target]
            msg = messaging.Message(notification=notif_obj, data=extra, topic=topic)
            try:
                msg_id = messaging.send(msg)
                recipients = -1   # topic — unknown count
                print(f"[NOTIFY] ✓ FCM topic={topic} msg_id={msg_id} by={email}")
            except Exception as e:
                fcm_error = str(e)
                print(
                    f"[NOTIFY] ✗ FCM FAILED topic={topic} error={e}\n"
                    f"          type={type(e).__name__} — see /api/debug/fcm-test for diagnosis"
                )
        elif target == 'group' and group_id:
            gdoc = db.collection('user_groups').document(group_id).get()
            members = (gdoc.to_dict() or {}).get('members', []) if gdoc.exists else []
            for m in members:
                user_docs = list(db.collection('users')
                                 .where('email', '==', m.get('email', ''))
                                 .limit(1).stream())
                for u in user_docs:
                    tok = (u.to_dict() or {}).get('fcm_token')
                    if tok:
                        try:
                            messaging.send(messaging.Message(
                                notification=notif_obj, data=extra, token=tok))
                            recipients += 1
                        except Exception as te:
                            fcm_error = str(te)
                            print(f"[NOTIFY] ✗ FCM token send error: {te}")
        elif target == 'user' and specific_user:
            for field in ('email', 'phone'):
                if recipients:
                    break
                for u in db.collection('users').where(field, '==', specific_user).limit(1).stream():
                    tok = (u.to_dict() or {}).get('fcm_token')
                    if tok:
                        try:
                            messaging.send(messaging.Message(
                                notification=notif_obj, data=extra, token=tok))
                            recipients += 1
                        except Exception as ue:
                            fcm_error = str(ue)
                            print(f"[NOTIFY] ✗ FCM user token error: {ue}")
    except Exception as e:
        fcm_error = str(e)
        print(f"[NOTIFY] ✗ Unexpected error: {e} — type={type(e).__name__}")

    # Save to Firestore regardless of FCM outcome
    db.collection('notifications').add({
        'title': title, 'title_ar': title_ar,
        'message': message, 'message_ar': message_ar,
        'target': target, 'channel': channel,
        'type': 'manual_push',
        'sent_at': datetime.now(timezone.utc).isoformat(),
        'sent_by': email,
        'recipients': recipients,
        'fcm_error': fcm_error,
    })

    if fcm_error:
        # Return the full error so admin.html can display the root cause
        return jsonify({
            'success': False,
            'error': f'FCM error: {fcm_error}',
            'hint': 'Visit /api/debug/fcm-test in your browser for a full diagnosis.',
            'recipients': recipients,
        }), 500
    cnt = 'all subscribers' if recipients == -1 else str(recipients)
    return jsonify({'success': True,
                    'message': f'Notification sent to {cnt}',
                    'recipients': recipients})


# ── Admin Logs ──────────────────────────────────────────────────────────────
@app.route('/api/v1/admin/logs')
def admin_logs():
    """Return recent structured log entries with optional level filter."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

    level    = request.args.get('level')
    category = request.args.get('category')
    limit    = min(int(request.args.get('limit', 100)), 500)
    try:
        # Try ordered fetch; fall back to unordered if index not ready
        try:
            docs = list(db.collection('admin_logs')
                        .order_by('timestamp', direction=firestore.Query.DESCENDING)
                        .limit(500).stream())
        except Exception:
            docs = list(db.collection('admin_logs').limit(500).stream())

        logs = []
        for d in docs:
            data = d.to_dict() or {}
            if level and data.get('level') != level:
                continue
            if category and data.get('category') != category:
                continue
            data['id'] = d.id
            logs.append(data)
            if len(logs) >= limit:
                break
        return jsonify({'success': True, 'logs': logs, 'count': len(logs)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Alarms ──────────────────────────────────────────────────────────────────
@app.route('/api/v1/admin/alarms')
def admin_alarms():
    """Compute real-time alarms: scraper health, error rate, database health."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

    alarms = []
    now    = datetime.now(timezone.utc)

    # ── Scraper health: last deal per source ──────────────────────────
    _EXPECTED_SOURCES = [
        'amazon_eg', 'noon_eg', 'jumia_eg', 'btech_eg',
        'carrefour_eg', 'sharaf_dg_eg', 'hyperone_eg', 'sahla_eg',
    ]
    try:
        deal_docs = list(db.collection('deals')
                         .order_by('timestamp', direction=firestore.Query.DESCENDING)
                         .limit(500).stream())
        site_last = {}
        for d in deal_docs:
            row = d.to_dict() or {}
            s   = row.get('site')
            ts  = row.get('timestamp')
            if s and ts and s not in site_last:
                site_last[s] = ts

        for src in _EXPECTED_SOURCES:
            last = site_last.get(src)
            if last is None:
                alarms.append({'level': 'warn', 'category': 'scraper',
                                'source': src,
                                'message': f'No deals ever collected from {src}',
                                'last_deal': None})
            else:
                try:
                    last_dt = last if hasattr(last, 'tzinfo') else None
                    if last_dt:
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        age_min = (now - last_dt).total_seconds() / 60
                        if age_min > 120:
                            alarms.append({'level': 'error', 'category': 'scraper',
                                           'source': src,
                                           'message': f'{src} — no new deals for {int(age_min)} minutes',
                                           'last_deal': _ts(last)})
                        elif age_min > 30:
                            alarms.append({'level': 'warn', 'category': 'scraper',
                                           'source': src,
                                           'message': f'{src} — no new deals for {int(age_min)} minutes',
                                           'last_deal': _ts(last)})
                except Exception:
                    pass
    except Exception as e:
        alarms.append({'level': 'error', 'category': 'database',
                       'message': f'Cannot read deals collection: {str(e)}'})

    # ── Recent error count ────────────────────────────────────────────
    try:
        recent_errors = list(db.collection('admin_logs')
                             .where('level', '==', 'error')
                             .order_by('timestamp', direction=firestore.Query.DESCENDING)
                             .limit(20).stream())
        err_count = len(recent_errors)
        if err_count >= 10:
            alarms.append({'level': 'error', 'category': 'system',
                           'message': f'{err_count} recent server errors — investigate logs immediately'})
        elif err_count >= 3:
            alarms.append({'level': 'warn', 'category': 'system',
                           'message': f'{err_count} recent server errors detected'})
    except Exception:
        pass  # logs collection might not exist yet

    # ── Database connectivity (already got here = ok) ─────────────────
    alarms.append({'level': 'info', 'category': 'database',
                   'message': 'Firestore connection: OK',
                   'checked_at': now.isoformat()})

    error_count = sum(1 for a in alarms if a['level'] == 'error')
    warn_count  = sum(1 for a in alarms if a['level'] == 'warn')

    return jsonify({
        'success': True,
        'alarms': alarms,
        'summary': {'errors': error_count, 'warnings': warn_count},
        'checked_at': now.isoformat(),
    })


# ── Revenue / Financial ──────────────────────────────────────────────────────
@app.route('/api/v1/admin/revenue')
def admin_revenue():
    """Financial dashboard: MRR estimate, tier breakdown, recent tier changes."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

    try:
        users = [d.to_dict() or {} for d in db.collection('users').stream()]

        # Tier pricing (USD default)
        tier_prices_usd = {'free': 0, 'trial': 0, 'premium': 5, 'vip': 10}
        try:
            for d in db.collection('tier_config').stream():
                data = d.to_dict() or {}
                tier_prices_usd[d.id] = float(data.get('price', 0))
        except Exception:
            pass

        # Country pricing
        country_prices = {}
        try:
            for d in db.collection('country_pricing').stream():
                country_prices[d.id] = d.to_dict() or {}
        except Exception:
            pass

        # Compute tier counts and MRR
        tier_counts = {}
        country_counts = {}
        for u in users:
            tier = u.get('tier', 'free')
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            country = u.get('country', 'eg')
            country_counts[country] = country_counts.get(country, 0) + 1

        mrr_by_tier = {}
        total_mrr   = 0.0
        for tier, count in tier_counts.items():
            price = tier_prices_usd.get(tier, 0)
            mrr   = round(count * price, 2)
            mrr_by_tier[tier] = {'count': count, 'price_usd': price, 'mrr_usd': mrr}
            total_mrr += mrr

        # Recent tier changes
        tier_changes = []
        try:
            for d in (db.collection('tier_history')
                      .order_by('changed_at', direction=firestore.Query.DESCENDING)
                      .limit(20).stream()):
                row = d.to_dict() or {}
                tier_changes.append({
                    'user_id':    (row.get('user_id') or '')[:14],
                    'from_tier':  row.get('from_tier', ''),
                    'to_tier':    row.get('to_tier', ''),
                    'changed_at': _ts(row.get('changed_at')),
                    'method':     row.get('method', ''),
                })
        except Exception:
            pass

        # Upgrade vs downgrade counts — safe lookup avoids ValueError on unknown tier names
        _TIER_ORDER = ['free', 'trial', 'premium', 'vip']
        def _tier_rank(t):
            try:
                return _TIER_ORDER.index(t or 'free')
            except ValueError:
                return 0
        upgrades   = sum(1 for c in tier_changes
                         if _tier_rank(c['to_tier']) > _tier_rank(c['from_tier']))
        downgrades = len(tier_changes) - upgrades

        return jsonify({
            'success':       True,
            'total_users':   len(users),
            'tier_counts':   tier_counts,
            'mrr_by_tier':   mrr_by_tier,
            'total_mrr_usd': round(total_mrr, 2),
            'country_counts': country_counts,
            'country_prices': country_prices,
            'tier_changes':  tier_changes,
            'upgrades':      upgrades,
            'downgrades':    downgrades,
        })
    except Exception as e:
        _log_event('error', 'api', f'Revenue endpoint error: {str(e)}',
                   {'traceback': traceback.format_exc()[:1000]})
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Country pricing CRUD ─────────────────────────────────────────────────────
@app.route('/api/v1/admin/country-pricing', methods=['GET'])
def get_country_pricing():
    """List per-country tier prices."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

    defaults = {
        'eg': {'currency': 'EGP', 'symbol': 'ج.م', 'free': 0, 'trial': 0, 'premium': 99,  'vip': 199},
        'sa': {'currency': 'SAR', 'symbol': 'ر.س', 'free': 0, 'trial': 0, 'premium': 39,  'vip': 79},
        'ae': {'currency': 'AED', 'symbol': 'د.إ', 'free': 0, 'trial': 0, 'premium': 39,  'vip': 79},
        'kw': {'currency': 'KWD', 'symbol': 'د.ك', 'free': 0, 'trial': 0, 'premium': 2.9, 'vip': 5.9},
        'qa': {'currency': 'QAR', 'symbol': 'ر.ق', 'free': 0, 'trial': 0, 'premium': 39,  'vip': 79},
    }
    try:
        docs = list(db.collection('country_pricing').stream())
        pricing = {d.id: d.to_dict() for d in docs}
        # fill missing countries with defaults
        for cc, vals in defaults.items():
            if cc not in pricing:
                pricing[cc] = vals
        return jsonify({'success': True, 'pricing': pricing})
    except Exception as e:
        return jsonify({'success': True, 'pricing': defaults})


@app.route('/api/v1/admin/country-pricing/<country_code>', methods=['PUT'])
def set_country_pricing(country_code):
    """Set per-country tier prices."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        _uid_email_from_token(auth_header[7:])
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 401

    data = request.get_json() or {}
    db.collection('country_pricing').document(country_code).set(data, merge=True)
    return jsonify({'success': True})


@app.route('/admin')
@app.route('/admin.html')
def serve_admin():
    resp = send_from_directory('.', 'admin.html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    _log_event('error', 'server', str(e), {
        'traceback': tb[:2000],
        'path': request.path,
        'method': request.method,
    })
    return jsonify({"success": False, "error": "Server error: " + str(e)}), 500

@app.after_request
def log_slow_requests(response):
    # Log any 5xx from route handlers that returned error JSON
    if response.status_code >= 500:
        _log_event('error', 'api', f'HTTP {response.status_code} on {request.method} {request.path}')
    return response

print("Starting...")
_load_shops()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
