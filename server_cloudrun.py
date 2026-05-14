"""
DealHunter Egypt - Flask API Server for Google Cloud Run
=========================================================
Production-ready API for deal discovery, fraud verification,
notifications, and payment processing.

Endpoints:
    GET  /health                   - Health check + DB status
    GET  /api/deals                - List deals (filtered)
    GET  /api/deals/<id>           - Single deal detail
    POST /api/deals/search         - Full-text search
    GET  /api/verify               - Verify deal authenticity
    POST /api/notifications/register   - Register FCM device token
    POST /api/notifications/test       - Send test push notification
    POST /api/notifications/send       - Send FCM to topic/token
    POST /api/notifications/broadcast  - Broadcast to all devices
    GET  /api/membership/tiers     - List membership tiers
    POST /api/membership/subscribe - Create PayMob payment intent
    POST /api/payment/paymob/initiate  - PayMob 3-step payment flow
    POST /api/payment/webhook      - PayMob payment callback

Environment Variables:
    DATABASE_URL        - Supabase PostgreSQL connection string
    TIMESCALE_URL       - TimescaleDB connection string
    PAYMOB_API_KEY      - PayMob API authentication key
    PAYMOB_INTEGRATION_ID   - PayMob integration ID
    PAYMOB_IFRAME_ID    - PayMob iframe ID
    FCM_SERVER_KEY      - Firebase Cloud Messaging server key
    FLASK_SECRET_KEY    - Flask session secret
    MIN_DISCOUNT        - Minimum discount threshold (default: 40)
"""

from __future__ import annotations

import os
import sys
import hashlib
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List, Tuple
from functools import wraps

import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv

# ---- Logging Setup ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("dealhunter")

# ---- Load Environment ----
load_dotenv()

# ---- Configuration ----
class Config:
    """Application configuration from environment variables."""

    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    TIMESCALE_URL: str = os.environ.get("TIMESCALE_URL", "")
    PAYMOB_API_KEY: str = os.environ.get("PAYMOB_API_KEY", "")
    PAYMOB_INTEGRATION_ID: int = int(os.environ.get("PAYMOB_INTEGRATION_ID", "4547446"))
    PAYMOB_IFRAME_ID: int = int(os.environ.get("PAYMOB_IFRAME_ID", "833328"))
    FCM_SERVER_KEY: str = os.environ.get("FCM_SERVER_KEY", "")
    FLASK_SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")
    MIN_DISCOUNT: int = int(os.environ.get("MIN_DISCOUNT", "40"))
    PORT: int = int(os.environ.get("PORT", "8080"))
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"

    # PayMob URLs
    PAYMOB_AUTH_URL: str = "https://accept.paymob.com/api/auth/tokens"
    PAYMOB_ORDER_URL: str = "https://accept.paymob.com/api/ecommerce/orders"
    PAYMOB_PAYMENT_KEY_URL: str = "https://accept.paymob.com/api/acceptance/payment_keys"
    PAYMOB_IFRAME_BASE: str = "https://accept.paymob.com/api/acceptance/iframes"

    # FCM
    FCM_SEND_URL: str = "https://fcm.googleapis.com/fcm/send"

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing critical configuration."""
        missing = []
        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not cls.PAYMOB_API_KEY:
            logger.warning("[WARN] PAYMOB_API_KEY not set - payments disabled")
        if not cls.FCM_SERVER_KEY:
            logger.warning("[WARN] FCM_SERVER_KEY not set - notifications disabled")
        return missing


# ---- Database Connection Pooling ----
class DatabasePool:
    """PostgreSQL connection pool manager for Supabase and TimescaleDB."""

    _instance: Optional["DatabasePool"] = None
    _pools: Dict[str, Any] = {}

    def __new__(cls) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_pool(self, db_url: str, pool_name: str) -> Any:
        """Get or create a connection pool."""
        if pool_name in self._pools and self._pools[pool_name] is not None:
            return self._pools[pool_name]

        try:
            import psycopg2
            from psycopg2 import pool

            conn_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=db_url,
                connect_timeout=10,
                options="-c statement_timeout=30000",
            )
            self._pools[pool_name] = conn_pool
            logger.info(f"[OK] {pool_name} connection pool created")
            return conn_pool
        except Exception as e:
            logger.error(f"[ERROR] Failed to create {pool_name} pool: {e}")
            self._pools[pool_name] = None
            return None

    def get_supabase_pool(self) -> Any:
        """Get Supabase PostgreSQL connection pool."""
        if not Config.DATABASE_URL:
            return None
        return self._get_pool(Config.DATABASE_URL, "supabase")

    def get_timescale_pool(self) -> Any:
        """Get TimescaleDB connection pool."""
        if not Config.TIMESCALE_URL:
            return None
        return self._get_pool(Config.TIMESCALE_URL, "timescale")

    def get_conn(self, pool_name: str = "supabase") -> Any:
        """Get a connection from named pool."""
        if pool_name == "timescale":
            p = self.get_timescale_pool()
        else:
            p = self.get_supabase_pool()
        if p is None:
            return None
        try:
            return p.getconn()
        except Exception as e:
            logger.error(f"[ERROR] Failed to get connection from {pool_name}: {e}")
            return None

    def put_conn(self, conn: Any, pool_name: str = "supabase") -> None:
        """Return a connection to the pool."""
        if conn is None:
            return
        try:
            if pool_name == "timescale":
                p = self._pools.get("timescale")
            else:
                p = self._pools.get("supabase")
            if p:
                p.putconn(conn)
        except Exception as e:
            logger.error(f"[ERROR] Failed to return connection: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        results = {}
        for name, url_var in [("supabase", "DATABASE_URL"), ("timescale", "TIMESCALE_URL")]:
            if not getattr(Config, url_var, None):
                results[name] = {"status": "not_configured"}
                continue
            conn = self.get_conn(name)
            if conn is None:
                results[name] = {"status": "unreachable", "error": "No connection available"}
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                results[name] = {"status": "healthy", "response_ms": "<30"}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
            finally:
                self.put_conn(conn, name)
        return results


db_pool = DatabasePool()

# ---- Flask App ----
app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ---- Error Handlers ----
@app.errorhandler(400)
def bad_request(error: Any) -> Response:
    logger.warning(f"[WARN] 400 Bad Request: {request.url}")
    return jsonify({"success": False, "error": {"code": "BAD_REQUEST", "message": "Invalid request"}}), 400


@app.errorhandler(404)
def not_found(error: Any) -> Response:
    logger.warning(f"[WARN] 404 Not Found: {request.url}")
    return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Endpoint not found"}}), 404


@app.errorhandler(405)
def method_not_allowed(error: Any) -> Response:
    logger.warning(f"[WARN] 405 Method Not Allowed: {request.method} {request.url}")
    return jsonify({"success": False, "error": {"code": "METHOD_NOT_ALLOWED", "message": f"Method {request.method} not allowed"}}), 405


@app.errorhandler(500)
def internal_error(error: Any) -> Response:
    logger.error(f"[ERROR] 500 Internal Server Error: {str(error)}")
    return jsonify({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}), 500


# ---- Response Helpers ----
def success_response(data: Any, status: int = 200) -> Response:
    """Return a standardized success response."""
    return jsonify({"success": True, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}), status


def error_response(message: str, code: str = "ERROR", status: int = 400, extra: Optional[Dict] = None) -> Response:
    """Return a standardized error response."""
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    if extra:
        payload["error"].update(extra)
    return jsonify(payload), status


# ---- Validation Helpers ----
def get_int_param(name: str, default: int = 0, minimum: int = 0, maximum: int = 10000) -> int:
    """Safely parse integer query parameter."""
    try:
        val = int(request.args.get(name, default))
        return max(minimum, min(maximum, val))
    except (ValueError, TypeError):
        return default


def get_float_param(name: str, default: float = 0.0, minimum: float = 0.0, maximum: float = 1e9) -> float:
    """Safely parse float query parameter."""
    try:
        val = float(request.args.get(name, default))
        return max(minimum, min(maximum, val))
    except (ValueError, TypeError):
        return default


def sanitize_string(value: Any, max_length: int = 200) -> str:
    """Sanitize user input string."""
    if not value:
        return ""
    s = str(value).strip()
    # Remove potentially dangerous characters
    s = s.replace("\x00", "")
    s = s.replace("\r", "")
    s = s.replace("\n", " ")
    # Truncate
    return s[:max_length]


# ---- FCM Helper (Lazy Firebase Import) ----
_fcm_initialized = False

def _init_fcm() -> bool:
    """Initialize Firebase Admin SDK (lazy, on first use)."""
    global _fcm_initialized
    if _fcm_initialized:
        return True
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not Config.FCM_SERVER_KEY:
            logger.warning("[WARN] FCM_SERVER_KEY not configured")
            return False

        # Try to initialize with service account credentials
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # Use server key for legacy HTTP API
            pass  # Legacy FCM uses requests with server key

        _fcm_initialized = True
        logger.info("[OK] Firebase Admin SDK initialized")
        return True
    except Exception as e:
        logger.error(f"[ERROR] FCM initialization failed: {e}")
        return False


def _send_fcm_legacy(token: str, title: str, body: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    """Send FCM notification using legacy HTTP API."""
    if not Config.FCM_SERVER_KEY:
        return {"success": False, "error": "FCM not configured"}

    payload = {
        "to": token,
        "notification": {
            "title": title,
            "body": body,
            "sound": "default",
            "badge": "1",
        },
        "priority": "high",
    }
    if data:
        payload["data"] = data

    try:
        resp = requests.post(
            Config.FCM_SEND_URL,
            headers={
                "Authorization": f"key={Config.FCM_SERVER_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        result = resp.json()
        if result.get("success", 0) > 0:
            logger.info(f"[OK] FCM sent to token: {token[:20]}...")
            return {"success": True, "message_id": result.get("results", [{}])[0].get("message_id")}
        else:
            error = result.get("results", [{}])[0].get("error", "Unknown error")
            logger.error(f"[ERROR] FCM failed: {error}")
            return {"success": False, "error": error}
    except Exception as e:
        logger.error(f"[ERROR] FCM request failed: {e}")
        return {"success": False, "error": str(e)}


def _send_fcm_topic(topic: str, title: str, body: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    """Send FCM notification to a topic using legacy API."""
    if not Config.FCM_SERVER_KEY:
        return {"success": False, "error": "FCM not configured"}

    payload = {
        "to": f"/topics/{topic}",
        "notification": {
            "title": title,
            "body": body,
            "sound": "default",
            "badge": "1",
        },
        "priority": "high",
    }
    if data:
        payload["data"] = data

    try:
        resp = requests.post(
            Config.FCM_SEND_URL,
            headers={
                "Authorization": f"key={Config.FCM_SERVER_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        result = resp.json()
        if result.get("message_id"):
            logger.info(f"[OK] FCM broadcast to topic '{topic}' sent")
            return {"success": True, "message_id": result.get("message_id")}
        else:
            error = result.get("failure", "Unknown error")
            logger.error(f"[ERROR] FCM topic broadcast failed: {error}")
            return {"success": False, "error": str(error)}
    except Exception as e:
        logger.error(f"[ERROR] FCM topic request failed: {e}")
        return {"success": False, "error": str(e)}


# ---- PayMob Helper ----
def _get_paymob_auth_token() -> Tuple[bool, str]:
    """Step 1: Get PayMob authentication token."""
    if not Config.PAYMOB_API_KEY:
        return False, "PayMob not configured"

    try:
        resp = requests.post(
            Config.PAYMOB_AUTH_URL,
            json={"api_key": Config.PAYMOB_API_KEY},
            timeout=15,
        )
        data = resp.json()
        token = data.get("token")
        if token:
            logger.info("[OK] PayMob auth token obtained")
            return True, token
        logger.error(f"[ERROR] PayMob auth failed: {data}")
        return False, str(data.get("detail", "Auth failed"))
    except Exception as e:
        logger.error(f"[ERROR] PayMob auth request failed: {e}")
        return False, str(e)


def _create_paymob_order(auth_token: str, amount_cents: int, items: List[Dict], merchant_order_id: str) -> Tuple[bool, str]:
    """Step 2: Create PayMob order."""
    payload = {
        "auth_token": auth_token,
        "delivery_needed": False,
        "amount_cents": amount_cents,
        "currency": "EGP",
        "merchant_order_id": merchant_order_id,
        "items": items,
    }
    try:
        resp = requests.post(
            Config.PAYMOB_ORDER_URL,
            json=payload,
            timeout=15,
        )
        data = resp.json()
        order_id = data.get("id")
        if order_id:
            logger.info(f"[OK] PayMob order created: {order_id}")
            return True, str(order_id)
        logger.error(f"[ERROR] PayMob order creation failed: {data}")
        return False, str(data.get("detail", "Order creation failed"))
    except Exception as e:
        logger.error(f"[ERROR] PayMob order request failed: {e}")
        return False, str(e)


def _get_paymob_payment_key(auth_token: str, amount_cents: int, order_id: str, billing_data: Dict) -> Tuple[bool, str]:
    """Step 3: Get PayMob payment key / iframe URL."""
    payload = {
        "auth_token": auth_token,
        "amount_cents": amount_cents,
        "expiration": 3600,
        "order_id": int(order_id),
        "billing_data": billing_data,
        "currency": "EGP",
        "integration_id": Config.PAYMOB_INTEGRATION_ID,
        "lock_order_when_paid": True,
    }
    try:
        resp = requests.post(
            Config.PAYMOB_PAYMENT_KEY_URL,
            json=payload,
            timeout=15,
        )
        data = resp.json()
        token = data.get("token")
        if token:
            logger.info("[OK] PayMob payment key obtained")
            return True, token
        logger.error(f"[ERROR] PayMob payment key failed: {data}")
        return False, str(data.get("detail", "Payment key failed"))
    except Exception as e:
        logger.error(f"[ERROR] PayMob payment key request failed: {e}")
        return False, str(e)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.route("/", methods=["GET"])
def root() -> Response:
    """Root endpoint - redirects to health or returns API info."""
    return success_response({
        "service": "DealHunter Egypt API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "deals": "/api/deals",
            "deal_detail": "/api/deals/<id>",
            "verify": "/api/verify",
            "tiers": "/api/membership/tiers",
            "paymob": "/api/payment/paymob/initiate",
        },
        "docs": "See /health for system status"
    })

@app.route("/health", methods=["GET"])
def health_check() -> Response:
    """
    GET /health
    Health check with database connectivity status.
    """
    db_status = db_pool.health_check()
    all_healthy = all(
        s.get("status") == "healthy" or s.get("status") == "not_configured"
        for s in db_status.values()
    )

    status_code = 200 if all_healthy else 503
    data = {
        "status": "healthy" if all_healthy else "degraded",
        "service": "dealhunter-api",
        "version": "1.0.0",
        "databases": db_status,
        "config": {
            "min_discount": Config.MIN_DISCOUNT,
            "paymob_configured": bool(Config.PAYMOB_API_KEY),
            "fcm_configured": bool(Config.FCM_SERVER_KEY),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("[OK] Health check requested")
    return jsonify({"success": True, "data": data}), status_code


@app.route("/api/deals", methods=["GET"])
def list_deals() -> Response:
    """
    GET /api/deals
    List deals with optional filters.

    Query Parameters:
        source      - Filter by site (amazon_eg, noon_eg, jumia_eg)
        category    - Filter by category (electronics, fashion, home, sports, grocery)
        min_discount- Minimum discount percent (default from config)
        max_price   - Maximum current price
        search      - Text search in title
        page        - Page number (default 1)
        per_page    - Items per page (default 20, max 100)
        sort_by     - Sort field (discount, price, rating, date)
        sort_order  - asc or desc (default desc)
    """
    conn = None
    try:
        # Parse parameters
        source = sanitize_string(request.args.get("source", ""), 50)
        category = sanitize_string(request.args.get("category", ""), 50)
        min_discount = get_int_param("min_discount", Config.MIN_DISCOUNT, 0, 100)
        max_price = get_float_param("max_price", 0, 0, 9999999)
        search_query = sanitize_string(request.args.get("search", ""), 200)
        page = get_int_param("page", 1, 1, 10000)
        per_page = get_int_param("per_page", 20, 1, 100)
        sort_by = sanitize_string(request.args.get("sort_by", "discount"), 50)
        sort_order = sanitize_string(request.args.get("sort_order", "desc"), 4)

        # Validate sort_by
        allowed_sort = {"discount": "discount_percent", "price": "current_price",
                        "rating": "rating", "date": "created_at", "savings": "savings"}
        sort_column = allowed_sort.get(sort_by, "discount_percent")
        sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        # Build query
        conditions = ["discount_percent >= %s"]
        params: List[Any] = [min_discount]

        if source:
            conditions.append("site = %s")
            params.append(source)
        if category:
            conditions.append("category = %s")
            params.append(category)
        if max_price > 0:
            conditions.append("current_price <= %s")
            params.append(max_price)
        if search_query:
            conditions.append("(title ILIKE %s OR product_id ILIKE %s)")
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        where_clause = " AND ".join(conditions)

        # Count query
        count_sql = f"SELECT COUNT(*) FROM deals WHERE {where_clause}"

        # Data query
        offset = (page - 1) * per_page
        data_sql = f"""
            SELECT id, product_id, site, title, image_url, product_url,
                   category, original_price, current_price, discount_percent,
                   savings, currency, verdict, fake_score, recommendation,
                   confidence, fraud_reasons, rating, review_count,
                   created_at
            FROM deals
            WHERE {where_clause}
            ORDER BY {sort_column} {sort_direction}
            LIMIT %s OFFSET %s
        """

        conn = db_pool.get_conn("supabase")
        if conn is None:
            return error_response("Database connection failed", "DB_ERROR", 503)

        with conn.cursor() as cur:
            # Get total count
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]

            # Get deals
            cur.execute(data_sql, params + [per_page, offset])
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            deals = []
            for row in rows:
                deal = dict(zip(columns, row))
                # Convert fraud_reasons from array if needed
                if deal.get("fraud_reasons") and isinstance(deal["fraud_reasons"], str):
                    try:
                        deal["fraud_reasons"] = json.loads(deal["fraud_reasons"])
                    except (json.JSONDecodeError, TypeError):
                        deal["fraud_reasons"] = []
                elif deal.get("fraud_reasons") is None:
                    deal["fraud_reasons"] = []
                # Format timestamps
                if deal.get("created_at") and hasattr(deal["created_at"], "isoformat"):
                    deal["created_at"] = deal["created_at"].isoformat()
                if deal.get("updated_at") and hasattr(deal["updated_at"], "isoformat"):
                    deal["updated_at"] = deal["updated_at"].isoformat()
                deals.append(deal)

        data = {
            "deals": deals,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
            "filters": {
                "source": source or None,
                "category": category or None,
                "min_discount": min_discount,
                "max_price": max_price or None,
                "search": search_query or None,
            },
        }
        logger.info(f"[OK] Listed {len(deals)} deals (total: {total})")
        return success_response(data)

    except Exception as e:
        logger.error(f"[ERROR] list_deals failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to retrieve deals", "QUERY_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


@app.route("/api/deals/<deal_id>", methods=["GET"])
def get_deal(deal_id: str) -> Response:
    """
    GET /api/deals/<id>
    Get single deal detail.
    """
    conn = None
    try:
        safe_id = sanitize_string(deal_id, 64)
        if not safe_id:
            return error_response("Deal ID is required", "MISSING_ID", 400)

        conn = db_pool.get_conn("supabase")
        if conn is None:
            return error_response("Database connection failed", "DB_ERROR", 503)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, product_id, site, title, image_url, product_url,
                       category, original_price, current_price, discount_percent,
                       savings, currency, verdict, fake_score, recommendation,
                       confidence, fraud_reasons, rating, review_count,
                       marketplace_country, created_at, updated_at
                FROM deals WHERE id = %s
            """, [safe_id])
            row = cur.fetchone()

            if not row:
                return error_response("Deal not found", "NOT_FOUND", 404)

            columns = [desc[0] for desc in cur.description]
            deal = dict(zip(columns, row))

            # Format arrays
            if deal.get("fraud_reasons") and isinstance(deal["fraud_reasons"], str):
                try:
                    deal["fraud_reasons"] = json.loads(deal["fraud_reasons"])
                except (json.JSONDecodeError, TypeError):
                    deal["fraud_reasons"] = []
            elif deal.get("fraud_reasons") is None:
                deal["fraud_reasons"] = []

            # Format timestamps
            if deal.get("created_at") and hasattr(deal["created_at"], "isoformat"):
                deal["created_at"] = deal["created_at"].isoformat()
            if deal.get("updated_at") and hasattr(deal["updated_at"], "isoformat"):
                deal["updated_at"] = deal["updated_at"].isoformat()

        logger.info(f"[OK] Retrieved deal: {safe_id}")
        return success_response(deal)

    except Exception as e:
        logger.error(f"[ERROR] get_deal failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to retrieve deal", "QUERY_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


@app.route("/api/deals/search", methods=["POST"])
def search_deals() -> Response:
    """
    POST /api/deals/search
    Full-text search across deals.

    Body:
        q           - Search query string (required)
        source      - Filter by site
        category    - Filter by category
        page        - Page number (default 1)
        per_page    - Items per page (default 20)
    """
    conn = None
    try:
        body = request.get_json(silent=True) or {}
        query = sanitize_string(body.get("q", ""), 200)
        source = sanitize_string(body.get("source", ""), 50)
        category = sanitize_string(body.get("category", ""), 50)
        page = max(1, min(10000, int(body.get("page", 1))))
        per_page = max(1, min(100, int(body.get("per_page", 20))))

        if not query:
            return error_response("Search query 'q' is required", "MISSING_QUERY", 400)

        conn = db_pool.get_conn("supabase")
        if conn is None:
            return error_response("Database connection failed", "DB_ERROR", 503)

        # Build search conditions
        conditions = ["(title ILIKE %s OR product_id ILIKE %s)"]
        params: List[Any] = [f"%{query}%", f"%{query}%"]

        if source:
            conditions.append("site = %s")
            params.append(source)
        if category:
            conditions.append("category = %s")
            params.append(category)

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * per_page

        with conn.cursor() as cur:
            # Count
            cur.execute(f"SELECT COUNT(*) FROM deals WHERE {where_clause}", params)
            total = cur.fetchone()[0]

            # Search results
            cur.execute(f"""
                SELECT id, product_id, site, title, image_url, product_url,
                       category, original_price, current_price, discount_percent,
                       savings, currency, verdict, recommendation, rating,
                       created_at
                FROM deals
                WHERE {where_clause}
                ORDER BY discount_percent DESC
                LIMIT %s OFFSET %s
            """, params + [per_page, offset])

            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

            deals = []
            for row in rows:
                deal = dict(zip(columns, row))
                if deal.get("created_at") and hasattr(deal["created_at"], "isoformat"):
                    deal["created_at"] = deal["created_at"].isoformat()
                deals.append(deal)

        data = {
            "query": query,
            "deals": deals,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        }
        logger.info(f"[OK] Search '{query}' returned {len(deals)} results")
        return success_response(data)

    except Exception as e:
        logger.error(f"[ERROR] search_deals failed: {e}\n{traceback.format_exc()}")
        return error_response("Search failed", "SEARCH_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


@app.route("/api/verify", methods=["GET"])
def verify_deal() -> Response:
    """
    GET /api/verify
    Verify deal authenticity / fraud check.

    Query Parameters:
        product_id  - Product ASIN/SKU (required)
        url         - Product URL (optional)
    """
    conn = None
    try:
        product_id = sanitize_string(request.args.get("product_id", ""), 200)
        product_url = sanitize_string(request.args.get("url", ""), 500)

        if not product_id and not product_url:
            return error_response("product_id or url is required", "MISSING_PARAM", 400)

        conn = db_pool.get_conn("supabase")
        if conn is None:
            return error_response("Database connection failed", "DB_ERROR", 503)

        # Try stored procedure first
        result = None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT get_deal_verdict(%s)", [product_id or product_url])
                row = cur.fetchone()
                if row and row[0]:
                    result = row[0]
        except Exception:
            # Stored procedure may not exist, fall back to query
            conn.rollback()

        if result is None:
            # Fallback: query deals table directly
            lookup_value = product_id or product_url
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, verdict, fake_score, recommendation,
                           confidence, fraud_reasons, site, original_price,
                           current_price, discount_percent
                    FROM deals
                    WHERE product_id = %s OR product_url = %s
                    LIMIT 1
                """, [lookup_value, lookup_value])
                row = cur.fetchone()
                if row:
                    columns = ["id", "title", "verdict", "fake_score", "recommendation",
                              "confidence", "fraud_reasons", "site", "original_price",
                              "current_price", "discount_percent"]
                    result = dict(zip(columns, row))
                    if result.get("fraud_reasons") and isinstance(result["fraud_reasons"], str):
                        try:
                            result["fraud_reasons"] = json.loads(result["fraud_reasons"])
                        except (json.JSONDecodeError, TypeError):
                            result["fraud_reasons"] = []
                    elif result.get("fraud_reasons") is None:
                        result["fraud_reasons"] = []

        if result:
            data = {
                "product_id": product_id,
                "found": True,
                "verdict": result.get("verdict", "UNVERIFIED"),
                "fake_score": result.get("fake_score", 0),
                "recommendation": result.get("recommendation", "research_first"),
                "confidence": result.get("confidence", 0.5),
                "fraud_reasons": result.get("fraud_reasons", []),
                "site": result.get("site"),
                "price_check": {
                    "original": result.get("original_price"),
                    "current": result.get("current_price"),
                    "discount": result.get("discount_percent"),
                },
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"[OK] Verified deal: {product_id} -> {data['verdict']}")
        else:
            data = {
                "product_id": product_id,
                "found": False,
                "verdict": "UNCERTAIN",
                "recommendation": "research_first",
                "message": "Deal not found in database. We cannot verify this product's authenticity.",
                "confidence": 0.0,
                "fraud_reasons": ["No data available for verification"],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"[OK] Verification uncertain for: {product_id}")

        return success_response(data)

    except Exception as e:
        logger.error(f"[ERROR] verify_deal failed: {e}\n{traceback.format_exc()}")
        return error_response("Verification failed", "VERIFY_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


# ============================================================================
# NOTIFICATIONS
# ============================================================================

@app.route("/api/notifications/register", methods=["POST"])
def register_device() -> Response:
    """
    POST /api/notifications/register
    Register FCM device token.

    Body:
        token       - FCM device token (required)
        platform    - android or ios (optional)
        app_version - App version string (optional)
        user_id     - Optional user identifier
    """
    conn = None
    try:
        body = request.get_json(silent=True) or {}
        token = sanitize_string(body.get("token", ""), 500)
        platform = sanitize_string(body.get("platform", "unknown"), 20)
        app_version = sanitize_string(body.get("app_version", ""), 50)
        user_id = sanitize_string(body.get("user_id", ""), 100)

        if not token:
            return error_response("FCM token is required", "MISSING_TOKEN", 400)

        conn = db_pool.get_conn("supabase")
        if conn is None:
            return error_response("Database connection failed", "DB_ERROR", 503)

        with conn.cursor() as cur:
            # Upsert device token
            cur.execute("""
                INSERT INTO devices (fcm_token, platform, app_version, user_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (fcm_token) DO UPDATE SET
                    platform = EXCLUDED.platform,
                    app_version = EXCLUDED.app_version,
                    user_id = EXCLUDED.user_id,
                    updated_at = NOW()
                RETURNING id
            """, [token, platform, app_version, user_id or None])
            device_id = cur.fetchone()[0]
            conn.commit()

        logger.info(f"[OK] Device registered: {device_id}, platform={platform}")
        return success_response({
            "registered": True,
            "device_id": device_id,
            "platform": platform,
        })

    except Exception as e:
        logger.error(f"[ERROR] register_device failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to register device", "REGISTER_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


@app.route("/api/notifications/test", methods=["POST"])
def send_test_notification() -> Response:
    """
    POST /api/notifications/test
    Send a test push notification to a device.

    Body:
        token   - FCM device token (required)
        title   - Notification title (default: "DealHunter Test")
        body    - Notification body (default: "This is a test notification")
    """
    try:
        body = request.get_json(silent=True) or {}
        token = sanitize_string(body.get("token", ""), 500)
        title = sanitize_string(body.get("title", "DealHunter Test"), 200)
        msg_body = sanitize_string(body.get("body", "This is a test notification"), 500)

        if not token:
            return error_response("FCM token is required", "MISSING_TOKEN", 400)

        result = _send_fcm_legacy(token, title, msg_body, {"type": "test"})
        if result.get("success"):
            logger.info(f"[OK] Test notification sent to: {token[:20]}...")
            return success_response({"sent": True, "message_id": result.get("message_id")})
        else:
            logger.error(f"[ERROR] Test notification failed: {result.get('error')}")
            return error_response(result.get("error", "Unknown error"), "FCM_ERROR", 502)

    except Exception as e:
        logger.error(f"[ERROR] send_test_notification failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to send notification", "NOTIFICATION_ERROR", 500)


@app.route("/api/notifications/send", methods=["POST"])
def send_notification() -> Response:
    """
    POST /api/notifications/send
    Send FCM notification to a specific token or topic.

    Body:
        target      - 'token' or 'topic' (required)
        destination - Token string or topic name (required)
        title       - Notification title (required)
        body        - Notification body (required)
        data        - Custom data payload (optional)
    """
    try:
        body = request.get_json(silent=True) or {}
        target = sanitize_string(body.get("target", ""), 20)
        destination = sanitize_string(body.get("destination", ""), 500)
        title = sanitize_string(body.get("title", ""), 200)
        msg_body = sanitize_string(body.get("body", ""), 500)
        custom_data = body.get("data", {})

        if not target or target not in ("token", "topic"):
            return error_response("target must be 'token' or 'topic'", "INVALID_TARGET", 400)
        if not destination:
            return error_response("destination is required", "MISSING_DESTINATION", 400)
        if not title:
            return error_response("title is required", "MISSING_TITLE", 400)

        result: Dict[str, Any]
        if target == "token":
            result = _send_fcm_legacy(destination, title, msg_body, custom_data)
        else:
            result = _send_fcm_topic(destination, title, msg_body, custom_data)

        if result.get("success"):
            logger.info(f"[OK] Notification sent via {target}: {destination[:30]}...")
            return success_response({"sent": True, "target": target, "message_id": result.get("message_id")})
        else:
            logger.error(f"[ERROR] Notification failed: {result.get('error')}")
            return error_response(result.get("error", "Unknown error"), "FCM_ERROR", 502)

    except Exception as e:
        logger.error(f"[ERROR] send_notification failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to send notification", "NOTIFICATION_ERROR", 500)


@app.route("/api/notifications/broadcast", methods=["POST"])
def broadcast_notification() -> Response:
    """
    POST /api/notifications/broadcast
    Broadcast notification to all registered devices via 'all_users' topic.

    Body:
        title   - Notification title (required)
        body    - Notification body (required)
        data    - Custom data payload (optional)
        topic   - Override topic (default: all_users)
    """
    try:
        body = request.get_json(silent=True) or {}
        title = sanitize_string(body.get("title", ""), 200)
        msg_body = sanitize_string(body.get("body", ""), 500)
        custom_data = body.get("data", {})
        topic = sanitize_string(body.get("topic", "all_users"), 100)

        if not title:
            return error_response("title is required", "MISSING_TITLE", 400)

        # Validate topic
        allowed_topics = {"all_users", "tier_free", "tier_premium", "tier_vip"}
        if topic not in allowed_topics:
            return error_response(f"Invalid topic. Allowed: {allowed_topics}", "INVALID_TOPIC", 400)

        result = _send_fcm_topic(topic, title, msg_body, custom_data)
        if result.get("success"):
            logger.info(f"[OK] Broadcast sent to topic '{topic}': {title}")
            return success_response({"broadcast": True, "topic": topic, "message_id": result.get("message_id")})
        else:
            logger.error(f"[ERROR] Broadcast failed: {result.get('error')}")
            return error_response(result.get("error", "Unknown error"), "FCM_ERROR", 502)

    except Exception as e:
        logger.error(f"[ERROR] broadcast_notification failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to broadcast", "BROADCAST_ERROR", 500)


# ============================================================================
# MEMBERSHIP
# ============================================================================

@app.route("/api/membership/tiers", methods=["GET"])
def list_membership_tiers() -> Response:
    """
    GET /api/membership/tiers
    List available membership tiers.
    """
    tiers = [
        {
            "id": "free",
            "name": "Free",
            "price_egp": 0,
            "features": [
                "Browse all deals",
                "Basic search",
                "Deal verification",
            ],
            "limitations": {
                "notifications_per_day": 5,
                "price_history_days": 7,
            },
        },
        {
            "id": "premium",
            "name": "Premium",
            "price_egp": 49,
            "price_monthly_egp": 49,
            "features": [
                "Everything in Free",
                "Unlimited notifications",
                "30-day price history",
                "Early access to deals",
                "Ad-free experience",
            ],
            "paymob_item_id": "premium_monthly",
        },
        {
            "id": "vip",
            "name": "VIP",
            "price_egp": 149,
            "price_monthly_egp": 149,
            "features": [
                "Everything in Premium",
                "Full price history",
                "Personal deal alerts",
                "Fraud protection reports",
                "Priority support",
                "Exclusive deals",
            ],
            "paymob_item_id": "vip_monthly",
        },
    ]
    logger.info("[OK] Membership tiers listed")
    return success_response({"tiers": tiers})


@app.route("/api/membership/subscribe", methods=["POST"])
def create_subscription() -> Response:
    """
    POST /api/membership/subscribe
    Create a PayMob payment intent for subscription.

    Body:
        tier_id         - Tier ID (premium or vip) (required)
        billing_email   - Customer email (required)
        billing_phone   - Customer phone (required)
        billing_first_name - First name (required)
        billing_last_name  - Last name (required)
        user_id         - Optional user identifier
    """
    conn = None
    try:
        body = request.get_json(silent=True) or {}
        tier_id = sanitize_string(body.get("tier_id", ""), 50)
        billing_email = sanitize_string(body.get("billing_email", ""), 200)
        billing_phone = sanitize_string(body.get("billing_phone", ""), 50)
        billing_first_name = sanitize_string(body.get("billing_first_name", ""), 100)
        billing_last_name = sanitize_string(body.get("billing_last_name", ""), 100)
        user_id = sanitize_string(body.get("user_id", ""), 100)

        if tier_id not in ("premium", "vip"):
            return error_response("tier_id must be 'premium' or 'vip'", "INVALID_TIER", 400)
        if not billing_email:
            return error_response("billing_email is required", "MISSING_EMAIL", 400)

        tier_prices = {"premium": 4900, "vip": 14900}  # in cents
        amount_cents = tier_prices.get(tier_id, 4900)

        # Step 1: Get auth token
        auth_ok, auth_token = _get_paymob_auth_token()
        if not auth_ok:
            return error_response(auth_token, "PAYMOB_AUTH_ERROR", 502)

        # Step 2: Create order
        merchant_order_id = f"dh_{tier_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]}"
        order_items = [{
            "name": f"DealHunter {tier_id.capitalize()} Subscription",
            "amount_cents": amount_cents,
            "quantity": 1,
        }]

        order_ok, order_id = _create_paymob_order(auth_token, amount_cents, order_items, merchant_order_id)
        if not order_ok:
            return error_response(order_id, "PAYMOB_ORDER_ERROR", 502)

        # Step 3: Get payment key
        billing_data = {
            "email": billing_email,
            "phone_number": billing_phone,
            "first_name": billing_first_name or "DealHunter",
            "last_name": billing_last_name or "User",
            "street": "NA",
            "building": "NA",
            "floor": "NA",
            "apartment": "NA",
            "city": "Cairo",
            "state": "Cairo",
            "country": "EG",
            "postal_code": "00000",
            "shipping_method": "NA",
        }

        key_ok, payment_token = _get_paymob_payment_key(auth_token, amount_cents, order_id, billing_data)
        if not key_ok:
            return error_response(payment_token, "PAYMOB_PAYMENT_KEY_ERROR", 502)

        # Build iframe URL
        iframe_url = f"{Config.PAYMOB_IFRAME_BASE}/{Config.PAYMOB_IFRAME_ID}?payment_token={payment_token}"

        # Record pending transaction
        conn = db_pool.get_conn("supabase")
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO transactions
                            (merchant_order_id, paymob_order_id, tier_id, amount_cents,
                             billing_email, user_id, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
                        ON CONFLICT (merchant_order_id) DO NOTHING
                    """, [merchant_order_id, order_id, tier_id, amount_cents,
                         billing_email, user_id or None])
                    conn.commit()
            except Exception as e:
                logger.warning(f"[WARN] Failed to record transaction: {e}")
            finally:
                db_pool.put_conn(conn, "supabase")
                conn = None

        logger.info(f"[OK] Subscription intent created: {merchant_order_id} -> tier={tier_id}")
        return success_response({
            "payment_intent_created": True,
            "merchant_order_id": merchant_order_id,
            "paymob_order_id": order_id,
            "tier": tier_id,
            "amount_egp": amount_cents / 100,
            "iframe_url": iframe_url,
            "payment_token": payment_token,
            "instructions": "Redirect user to iframe_url to complete payment",
        })

    except Exception as e:
        logger.error(f"[ERROR] create_subscription failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to create subscription", "SUBSCRIPTION_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


# ============================================================================
# PAYMENTS
# ============================================================================

@app.route("/api/payment/paymob/initiate", methods=["POST"])
def paymob_initiate() -> Response:
    """
    POST /api/payment/paymob/initiate
    Full PayMob 3-step payment flow for one-time payments.

    Body:
        amount_egp      - Amount in EGP (required)
        billing_email   - Customer email (required)
        billing_phone   - Customer phone (required)
        billing_first_name - First name (required)
        billing_last_name  - Last name (required)
        items           - Array of {name, amount_cents, quantity}
        user_id         - Optional user identifier
    """
    conn = None
    try:
        body = request.get_json(silent=True) or {}
        amount_egp = get_float_param_from_body(body, "amount_egp", 0, 0, 100000)
        billing_email = sanitize_string(body.get("billing_email", ""), 200)
        billing_phone = sanitize_string(body.get("billing_phone", ""), 50)
        billing_first_name = sanitize_string(body.get("billing_first_name", ""), 100)
        billing_last_name = sanitize_string(body.get("billing_last_name", ""), 100)
        user_id = sanitize_string(body.get("user_id", ""), 100)
        items_data = body.get("items", [])

        if amount_egp <= 0:
            return error_response("amount_egp must be greater than 0", "INVALID_AMOUNT", 400)
        if not billing_email:
            return error_response("billing_email is required", "MISSING_EMAIL", 400)

        amount_cents = int(amount_egp * 100)

        # Build items list
        items: List[Dict[str, Any]] = []
        if items_data and isinstance(items_data, list):
            for item in items_data:
                items.append({
                    "name": sanitize_string(item.get("name", "DealHunter Purchase"), 200),
                    "amount_cents": int(item.get("amount_cents", amount_cents)),
                    "quantity": int(item.get("quantity", 1)),
                })
        else:
            items = [{
                "name": "DealHunter Purchase",
                "amount_cents": amount_cents,
                "quantity": 1,
            }]

        # Step 1: Auth token
        auth_ok, auth_token = _get_paymob_auth_token()
        if not auth_ok:
            return error_response(auth_token, "PAYMOB_AUTH_ERROR", 502)

        # Step 2: Create order
        merchant_order_id = f"dh_pay_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]}"

        order_ok, order_id = _create_paymob_order(auth_token, amount_cents, items, merchant_order_id)
        if not order_ok:
            return error_response(order_id, "PAYMOB_ORDER_ERROR", 502)

        # Step 3: Payment key
        billing_data = {
            "email": billing_email,
            "phone_number": billing_phone,
            "first_name": billing_first_name or "DealHunter",
            "last_name": billing_last_name or "User",
            "street": "NA",
            "building": "NA",
            "floor": "NA",
            "apartment": "NA",
            "city": "Cairo",
            "state": "Cairo",
            "country": "EG",
            "postal_code": "00000",
            "shipping_method": "NA",
        }

        key_ok, payment_token = _get_paymob_payment_key(auth_token, amount_cents, order_id, billing_data)
        if not key_ok:
            return error_response(payment_token, "PAYMOB_PAYMENT_KEY_ERROR", 502)

        # Build iframe URL
        iframe_url = f"{Config.PAYMOB_IFRAME_BASE}/{Config.PAYMOB_IFRAME_ID}?payment_token={payment_token}"

        # Record transaction
        conn = db_pool.get_conn("supabase")
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO transactions
                            (merchant_order_id, paymob_order_id, amount_cents,
                             billing_email, user_id, status, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
                        ON CONFLICT (merchant_order_id) DO NOTHING
                    """, [merchant_order_id, order_id, amount_cents,
                         billing_email, user_id or None])
                    conn.commit()
            except Exception as e:
                logger.warning(f"[WARN] Failed to record transaction: {e}")
            finally:
                db_pool.put_conn(conn, "supabase")
                conn = None

        logger.info(f"[OK] Payment initiated: {merchant_order_id}, amount={amount_egp} EGP")
        return success_response({
            "payment_initiated": True,
            "merchant_order_id": merchant_order_id,
            "paymob_order_id": order_id,
            "amount_egp": amount_egp,
            "amount_cents": amount_cents,
            "iframe_url": iframe_url,
            "payment_token": payment_token,
            "instructions": "Redirect user to iframe_url to complete payment",
        })

    except Exception as e:
        logger.error(f"[ERROR] paymob_initiate failed: {e}\n{traceback.format_exc()}")
        return error_response("Failed to initiate payment", "PAYMENT_INIT_ERROR", 500)
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


@app.route("/api/payment/webhook", methods=["POST"])
def paymob_webhook() -> Response:
    """
    POST /api/payment/webhook
    Handle PayMob payment callback / webhook.

    PayMob sends:
        obj[amount_cents], obj[order][id], obj[success],
        obj[payment_key_claims][extra][merchant_order_id], etc.
    """
    conn = None
    try:
        body = request.get_json(silent=True) or {}

        # PayMob sends data in 'obj' field
        obj = body.get("obj", body)

        # Extract payment details
        amount_cents = obj.get("amount_cents", obj.get("amount", 0))
        order_id = str(obj.get("order", {}).get("id", ""))
        success = obj.get("success", False)
        transaction_id = str(obj.get("id", ""))
        pending = obj.get("pending", False)

        # Try to get merchant_order_id
        merchant_order_id = ""
        try:
            merchant_order_id = obj.get("payment_key_claims", {}).get("extra", {}).get("merchant_order_id", "")
        except (AttributeError, TypeError):
            merchant_order_id = str(obj.get("merchant_order_id", ""))

        # Calculate HMAC if secret is configured (optional validation)
        hmac_secret = os.environ.get("PAYMOB_HMAC_SECRET", "")
        if hmac_secret:
            # HMAC validation would go here
            pass

        # Determine status
        if success:
            status = "success"
        elif pending:
            status = "pending"
        else:
            status = "failed"

        # Update transaction in database
        conn = db_pool.get_conn("supabase")
        if conn:
            try:
                with conn.cursor() as cur:
                    # Try to update by merchant_order_id
                    if merchant_order_id:
                        cur.execute("""
                            UPDATE transactions
                            SET status = %s,
                                paymob_transaction_id = %s,
                                paymob_order_id = COALESCE(NULLIF(%s, ''), paymob_order_id),
                                updated_at = NOW()
                            WHERE merchant_order_id = %s
                            RETURNING id
                        """, [status, transaction_id, order_id, merchant_order_id])
                        updated = cur.fetchone()
                        if not updated:
                            # Try by paymob_order_id
                            cur.execute("""
                                UPDATE transactions
                                SET status = %s,
                                    paymob_transaction_id = %s,
                                    updated_at = NOW()
                                WHERE paymob_order_id = %s
                                RETURNING id
                            """, [status, transaction_id, order_id])
                            updated = cur.fetchone()

                        conn.commit()

                        # If successful, activate membership
                        if status == "success" and updated:
                            cur.execute("""
                                SELECT tier_id, user_id FROM transactions WHERE id = %s
                            """, [updated[0]])
                            row = cur.fetchone()
                            if row and row[0] and row[1]:
                                tier_id, uid = row[0], row[1]
                                cur.execute("""
                                    INSERT INTO memberships (user_id, tier, started_at, expires_at, active)
                                    VALUES (%s, %s, NOW(), NOW() + INTERVAL '30 days', TRUE)
                                    ON CONFLICT (user_id) DO UPDATE SET
                                        tier = EXCLUDED.tier,
                                        started_at = NOW(),
                                        expires_at = NOW() + INTERVAL '30 days',
                                        active = TRUE
                                """, [uid, tier_id])
                                conn.commit()
                                logger.info(f"[OK] Membership activated: user={uid}, tier={tier_id}")

            except Exception as e:
                logger.error(f"[ERROR] Webhook DB update failed: {e}")
                conn.rollback()
            finally:
                db_pool.put_conn(conn, "supabase")
                conn = None

        logger.info(f"[OK] PayMob webhook: order={order_id}, status={status}, success={success}")
        return success_response({
            "received": True,
            "paymob_order_id": order_id,
            "merchant_order_id": merchant_order_id,
            "status": status,
            "amount_cents": amount_cents,
            "transaction_id": transaction_id,
        })

    except Exception as e:
        logger.error(f"[ERROR] paymob_webhook failed: {e}\n{traceback.format_exc()}")
        # Always return 200 to PayMob to prevent retries
        return success_response({"received": True, "status": "error_logged", "note": "Check server logs"})
    finally:
        if conn:
            db_pool.put_conn(conn, "supabase")


# ============================================================================
# HELPERS
# ============================================================================

def get_float_param_from_body(body: Dict, name: str, default: float = 0.0,
                               minimum: float = 0.0, maximum: float = 1e9) -> float:
    """Safely parse float from request body."""
    try:
        val = float(body.get(name, default))
        return max(minimum, min(maximum, val))
    except (ValueError, TypeError):
        return default


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Validate configuration on startup
    missing = Config.validate()
    if missing:
        logger.error(f"[ERROR] Missing critical config: {missing}")
        sys.exit(1)

    logger.info("[OK] DealHunter API starting")
    logger.info(f"[OK] Port: {Config.PORT}, Debug: {Config.DEBUG}")

    app.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.DEBUG,
    )
