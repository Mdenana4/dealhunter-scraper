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

firebase_key_json = os.getenv("FIREBASE_KEY_JSON")
if firebase_key_json:
    cred = credentials.Certificate(json.loads(firebase_key_json))
    firebase_admin.initialize_app(cred)
    print("✅ Firebase initialized")
else:
    raise RuntimeError("FIREBASE_KEY_JSON not set!")

db = firestore.client()

SAFQA_BASE    = "https://api.sfq.app/v1"
SAFQA_AES_KEY = "ee6uFer3jc6WuzbUGrhV"
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
    if orig > 0:
        calc = round((orig-curr)/orig*100)
        if abs(pct-calc)>10:
            reasons.append(f"Math mismatch: {pct}% vs {calc}%"); score+=40
    if curr > 0 and orig > 0:
        ratio = orig/curr
        if ratio > 3.0: reasons.append(f"Extreme {ratio:.1f}x"); score+=40; conf-=10
        elif ratio > 2.0: reasons.append(f"High {ratio:.1f}x"); score+=20
    if pct > 70: reasons.append(f"Very high {pct}%"); score+=20
    verdict = "FAKE" if score>=60 else "SUSPICIOUS" if score>=35 else "GENUINE"
    return {"verdict": verdict, "score": score, "confidence": max(20,min(100,conf)), "reasons": reasons}

def serialize_deal(doc_id, d) -> dict:
    orig,curr,disc = float(d.get("original_price",0)),float(d.get("current_price",0)),int(d.get("discount_percent",0))
    f = detect_fraud_basic(orig, curr, disc)
    return {
        "id":doc_id,"title":d.get("title",""),
        "store":d.get("site_display",d.get("source","")),
        "source":d.get("source",""),
        "current_price":curr,"original_price":orig,
        "discount_percent":disc,"currency":"EGP",
        "image_url":d.get("image_url",""),"product_url":d.get("product_url",""),
        "category":d.get("category",""),
        "rating":float(d.get("rating",0)) if d.get("rating") else 0.0,
        "verdict":f["verdict"],"fake_score":f["score"],
        "confidence":f["confidence"],"fraud_reasons":f["reasons"],
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


@app.errorhandler(404)
def not_found(e): return jsonify({"success":False,"error":"Not found"}),404
@app.errorhandler(500)
def server_error(e): return jsonify({"success":False,"error":"Server error"}),500

print("Starting...")
_load_shops()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
