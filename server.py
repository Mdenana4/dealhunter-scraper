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

@app.errorhandler(404)
def not_found(e): return jsonify({"success":False,"error":"Not found"}),404
@app.errorhandler(500)
def server_error(e): return jsonify({"success":False,"error":"Server error"}),500

print("Starting...")
_load_shops()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
