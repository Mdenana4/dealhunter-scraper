#!/usr/bin/env python3
"""
===============================================================================
DEALHUNTER EGYPT — Firestore → PostgreSQL Migration Script
===============================================================================
Purpose: Migrate existing data from Firebase Firestore to Supabase PostgreSQL
         and TimescaleDB Cloud.

Prerequisites:
    - pip install firebase-admin psycopg2-binary python-dotenv tqdm
    - Firebase service account key JSON file
    - Supabase PostgreSQL connection string (with admin privileges)
    - TimescaleDB connection string (with write privileges)
    - Both database schemas must be created before running

Usage:
    # Set environment variables
    export FIREBASE_CREDENTIALS_PATH="/path/to/service-account.json"
    export SUPABASE_URL="postgresql://postgres:password@db.xxx.supabase.co:5432/postgres"
    export TIMESCALE_URL="postgresql://tsdbadmin:password@xxx.tsdb.cloud.timescale.com:5432/tsdb"

    # Run full migration
    python migration_data.py --all --batch-size 500

    # Migrate specific collections
    python migration_data.py --deals --batch-size 500
    python migration_data.py --users --batch-size 200
    python migration_data.py --price-history --batch-size 1000

    # Dry run (no writes)
    python migration_data.py --all --dry-run

    # With verbose logging
    python migration_data.py --all -v
===============================================================================
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

# Optional dependencies - fail gracefully with instructions
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("ERROR: firebase-admin is required. Install with: pip install firebase-admin")
    sys.exit(1)

try:
    import psycopg2
    from psycopg2.extras import execute_values, RealDictCursor
except ImportError:
    print("ERROR: psycopg2-binary is required. Install with: pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm not available
    def tqdm(iterable, **kwargs):
        return iterable


# =============================================================================
# CONFIGURATION
# =============================================================================

# Valid site mappings from Firestore → PostgreSQL enum
SITE_MAPPING = {
    "amazon_eg": "amazon_eg",
    "noon_eg": "noon_eg",
    "jumia_eg": "jumia_eg",
    "amazon": "amazon_eg",
    "noon": "noon_eg",
    "jumia": "jumia_eg",
    "amazon_ae": "amazon_ae",
    "noon_ae": "noon_ae",
    "noon_sa": "noon_sa",
    "amazon.sa": "noon_sa",
}

# Valid category mappings
CATEGORY_MAPPING = {
    "electronics": "electronics",
    "fashion": "fashion",
    "home": "home",
    "sports": "sports",
    "grocery": "grocery",
    "general": "general",
    "kitchen": "home",
    "appliances": "electronics",
    "phones": "electronics",
    "laptops": "electronics",
    "clothing": "fashion",
    "shoes": "fashion",
    "fitness": "sports",
}

# Valid verdict mappings
VERDICT_MAPPING = {
    "GENUINE": "GENUINE",
    "SUSPICIOUS": "SUSPICIOUS",
    "FAKE": "FAKE",
    "UNVERIFIED": "UNVERIFIED",
    "genuine": "GENUINE",
    "suspicious": "SUSPICIOUS",
    "fake": "FAKE",
    "unverified": "UNVERIFIED",
    "verified": "GENUINE",
    "fraud": "FAKE",
}

# Valid tier mappings
TIER_MAPPING = {
    "free": "free",
    "trial": "trial",
    "premium": "premium",
    "vip": "vip",
    "elite": "elite",
}

# Valid currency mappings
CURRENCY_MAPPING = {
    "EGP": "EGP",
    "AED": "AED",
    "SAR": "SAR",
    "USD": "USD",
    "egp": "EGP",
    "aed": "AED",
    "sar": "SAR",
    "usd": "USD",
    "£": "EGP",
    "dh": "AED",
}

# Firebase collection names
FIRESTORE_COLLECTIONS = {
    "deals": "deals",
    "users": "users",
    "devices": "devices",
    "favorites": "user_favorites",
    "alert_rules": "alert_rules",
    "price_history": "price_history",
    "notifications": "notifications",
    "scraper_logs": "scraper_logs",
}


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging with colored output."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("dealhunter_migration")
    
    # Suppress noisy third-party logs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    
    return logger


# =============================================================================
# MIGRATION STATISTICS
# =============================================================================

class MigrationStats:
    """Track migration progress and statistics."""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.collections: Dict[str, Dict[str, Any]] = {}
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
    
    def start(self):
        self.start_time = datetime.now(timezone.utc)
    
    def finish(self):
        self.end_time = datetime.now(timezone.utc)
    
    def add_collection(self, name: str):
        self.collections[name] = {
            "total_firestore_docs": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "batches": 0,
            "start_time": None,
            "end_time": None,
        }
    
    def record_batch(self, collection: str, inserted: int = 0, updated: int = 0, 
                     skipped: int = 0, failed: int = 0):
        if collection not in self.collections:
            self.add_collection(collection)
        stats = self.collections[collection]
        stats["inserted"] += inserted
        stats["updated"] += updated
        stats["skipped"] += skipped
        stats["failed"] += failed
        stats["batches"] += 1
    
    def add_error(self, collection: str, doc_id: str, error: str):
        self.errors.append({
            "collection": collection,
            "document_id": doc_id,
            "error": str(error),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if collection in self.collections:
            self.collections[collection]["failed"] += 1
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    def print_summary(self, logger: logging.Logger):
        logger.info("=" * 70)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Duration: {self.duration_seconds:.1f}s")
        logger.info(f"Total errors: {len(self.errors)}")
        logger.info(f"Total warnings: {len(self.warnings)}")
        logger.info("")
        
        for name, stats in self.collections.items():
            logger.info(f"  [{name}]")
            logger.info(f"    Firestore docs: {stats['total_firestore_docs']}")
            logger.info(f"    Inserted:       {stats['inserted']}")
            logger.info(f"    Updated:        {stats['updated']}")
            logger.info(f"    Skipped:        {stats['skipped']}")
            logger.info(f"    Failed:         {stats['failed']}")
            logger.info(f"    Batches:        {stats['batches']}")
            logger.info("")
        
        if self.errors:
            logger.info("--- First 10 Errors ---")
            for err in self.errors[:10]:
                logger.error(f"  [{err['collection']}] {err['document_id']}: {err['error']}")
        
        logger.info("=" * 70)


# =============================================================================
# DATABASE CONNECTION MANAGER
# =============================================================================

class DatabaseManager:
    """Manages PostgreSQL/TimescaleDB connections with retry logic."""
    
    def __init__(self, connection_url: str, logger: logging.Logger, 
                 max_retries: int = 3, retry_delay: float = 2.0):
        self.connection_url = connection_url
        self.logger = logger
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._conn = None
        self._cursor = None
    
    def connect(self) -> psycopg2.extensions.connection:
        """Connect to PostgreSQL with retry logic."""
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"Connecting to database (attempt {attempt}/{self.max_retries})...")
                self._conn = psycopg2.connect(self.connection_url, connect_timeout=10)
                self._conn.autocommit = False
                self.logger.debug("Connected successfully.")
                return self._conn
            except psycopg2.Error as e:
                self.logger.warning(f"Connection attempt {attempt} failed: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * attempt)
                else:
                    raise
        raise ConnectionError("Failed to connect to database after all retries")
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        if not self._conn or self._conn.closed:
            self.connect()
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
    
    def execute(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Execute a query and return results."""
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            return []
    
    def execute_many(self, query: str, params_list: List[Tuple]):
        """Execute a query with multiple parameter sets."""
        with self._conn.cursor() as cur:
            execute_values(cur, query, params_list, page_size=1000)
    
    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()
            self.logger.debug("Database connection closed.")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =============================================================================
# FIRESTORE MANAGER
# =============================================================================

class FirestoreManager:
    """Manages Firestore connection and document streaming."""
    
    def __init__(self, credentials_path: str, logger: logging.Logger):
        self.credentials_path = credentials_path
        self.logger = logger
        self._db = None
    
    def connect(self) -> firestore.Client:
        """Initialize Firebase Admin and return Firestore client."""
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.credentials_path)
            firebase_admin.initialize_app(cred)
        self._db = firestore.client()
        self.logger.info("Connected to Firestore.")
        return self._db
    
    def stream_collection(self, collection_name: str, 
                          batch_size: int = 500) -> Generator[firestore.DocumentSnapshot, None, None]:
        """Stream documents from a Firestore collection in batches."""
        if not self._db:
            raise RuntimeError("Firestore not connected. Call connect() first.")
        
        collection = self._db.collection(collection_name)
        docs = collection.stream()
        
        count = 0
        for doc in docs:
            yield doc
            count += 1
            if count % batch_size == 0:
                self.logger.debug(f"Streamed {count} documents from '{collection_name}'...")
        
        self.logger.info(f"Total documents in '{collection_name}': {count}")
    
    def get_document(self, collection: str, doc_id: str) -> Optional[Dict]:
        """Get a single document by ID."""
        if not self._db:
            raise RuntimeError("Firestore not connected.")
        doc = self._db.collection(collection).document(doc_id).get()
        return doc.to_dict() if doc.exists else None
    
    def get_subcollection(self, parent_collection: str, parent_id: str, 
                          subcollection: str) -> Generator[firestore.DocumentSnapshot, None, None]:
        """Stream documents from a subcollection."""
        if not self._db:
            raise RuntimeError("Firestore not connected.")
        
        subcol = self._db.collection(parent_collection).document(parent_id).collection(subcollection)
        for doc in subcol.stream():
            yield doc


# =============================================================================
# DATA TRANSFORMERS
# =============================================================================

class DataTransformer:
    """Transforms Firestore documents into PostgreSQL-compatible rows."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    @staticmethod
    def to_timestamp(dt: Any) -> Optional[datetime]:
        """Convert Firestore datetime to Python datetime."""
        if dt is None:
            return None
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        if hasattr(dt, 'timestamp'):  # Firestore Timestamp
            return datetime.fromtimestamp(dt.timestamp(), tz=timezone.utc)
        return None
    
    @staticmethod
    def safe_decimal(value: Any, default: float = 0.0) -> float:
        """Safely convert a value to float/decimal."""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """Safely convert a value to int."""
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    
    @staticmethod
    def safe_text(value: Any, max_length: int = 1000) -> Optional[str]:
        """Safely convert to text, truncating if needed."""
        if value is None:
            return None
        text = str(value).strip()
        if len(text) > max_length:
            text = text[:max_length]
        return text if text else None
    
    @staticmethod
    def compute_deal_id(site: str, url: str, price: float) -> str:
        """Compute a deterministic deal ID from site, URL, and price."""
        key = f"{site}:{url}:{price}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()
    
    def transform_deal(self, doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a Firestore deal document into PostgreSQL row data."""
        try:
            # Extract fields with defaults
            site_raw = data.get("site", data.get("marketplace", "amazon_eg"))
            site = SITE_MAPPING.get(str(site_raw).lower().strip(), "amazon_eg")
            
            category_raw = data.get("category", data.get("productCategory", "general"))
            category = CATEGORY_MAPPING.get(str(category_raw).lower().strip(), "general")
            
            verdict_raw = data.get("verdict", data.get("status", "UNVERIFIED"))
            verdict = VERDICT_MAPPING.get(str(verdict_raw).upper().strip(), "UNVERIFIED")
            
            currency_raw = data.get("currency", "EGP")
            currency = CURRENCY_MAPPING.get(str(currency_raw).upper().strip(), "EGP")
            
            product_url = str(data.get("productUrl", data.get("url", data.get("link", ""))))
            product_id = str(data.get("productId", data.get("asin", data.get("sku", doc_id))))
            current_price = self.safe_decimal(data.get("currentPrice", data.get("price", 0)))
            original_price = self.safe_decimal(data.get("originalPrice", data.get("listPrice", current_price)))
            
            # Compute discount
            if original_price > 0:
                discount_percent = round(((original_price - current_price) / original_price) * 100, 2)
                savings = round(original_price - current_price, 2)
            else:
                discount_percent = 0.0
                savings = 0.0
            
            # Compute or use existing deal ID
            deal_id = data.get("dealId", data.get("id", ""))
            if not deal_id:
                deal_id = self.compute_deal_id(site, product_url, current_price)
            
            # Handle fraud reasons
            fraud_reasons = data.get("fraudReasons", [])
            if isinstance(fraud_reasons, str):
                fraud_reasons = [fraud_reasons] if fraud_reasons else []
            elif not isinstance(fraud_reasons, list):
                fraud_reasons = []
            
            # Parse metadata
            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            
            # Parse recommendation
            recommendation = data.get("recommendation", "normal")
            valid_recommendations = {"buy_now", "wait", "normal", "avoid", "check_back_later"}
            if recommendation not in valid_recommendations:
                if verdict == "FAKE":
                    recommendation = "avoid"
                elif verdict == "GENUINE" and discount_percent > 30:
                    recommendation = "buy_now"
                else:
                    recommendation = "normal"
            
            return {
                "id": deal_id,
                "product_id": product_id[:100],
                "site": site,
                "title": self.safe_text(data.get("title", data.get("name", "Unknown Product")), 500),
                "image_url": self.safe_text(data.get("imageUrl", data.get("image", None)), 1000),
                "product_url": product_url[:2000],
                "category": category,
                "original_price": max(0, original_price),
                "current_price": max(0, current_price),
                "discount_percent": max(0, discount_percent),
                "savings": max(0, savings),
                "currency": currency,
                "verdict": verdict,
                "fake_score": min(100, max(0, self.safe_decimal(data.get("fakeScore", data.get("fraudScore", 0))))),
                "recommendation": recommendation,
                "confidence": min(1.0, max(0, self.safe_decimal(data.get("confidence", 0)))),
                "fraud_reasons": fraud_reasons,
                "rating": data.get("rating") if data.get("rating") is not None else None,
                "review_count": self.safe_int(data.get("reviewCount", data.get("reviews", 0))),
                "marketplace_country": data.get("marketplaceCountry", "egypt"),
                "is_active": bool(data.get("isActive", True)),
                "is_featured": bool(data.get("isFeatured", False)),
                "created_at": self.to_timestamp(data.get("createdAt", data.get("created_at"))),
                "scraped_at": self.to_timestamp(data.get("scrapedAt", data.get("scraped_at"))),
                "metadata": json.dumps(metadata) if metadata else "{}",
            }
        except Exception as e:
            self.logger.error(f"Error transforming deal {doc_id}: {e}")
            return None
    
    def transform_user(self, doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a Firestore user document into PostgreSQL row data."""
        try:
            tier_raw = data.get("tier", data.get("membership", "free"))
            tier = TIER_MAPPING.get(str(tier_raw).lower().strip(), "free")
            
            device_platform = data.get("devicePlatform", data.get("platform"))
            if device_platform:
                device_platform = str(device_platform).lower()
                if device_platform not in {"android", "ios", "web"}:
                    device_platform = None
            
            country = data.get("country", "egypt")
            if country not in {"egypt", "uae", "saudi"}:
                country = "egypt"
            
            preferences = data.get("preferences", {})
            if not isinstance(preferences, dict):
                preferences = {}
            
            # Parse tier_expires_at
            tier_expires = self.to_timestamp(data.get("tierExpiresAt", data.get("membershipExpiry")))
            
            return {
                "id": data.get("id", doc_id),
                "firebase_uid": str(data.get("firebaseUid", data.get("uid", doc_id))),
                "email": self.safe_text(data.get("email"), 255),
                "phone": self.safe_text(data.get("phone"), 50),
                "display_name": self.safe_text(data.get("displayName", data.get("name", "")), 100),
                "avatar_url": self.safe_text(data.get("avatarUrl", data.get("photoURL")), 1000),
                "tier": tier,
                "tier_expires_at": tier_expires,
                "fcm_token": self.safe_text(data.get("fcmToken", data.get("deviceToken")), 500),
                "device_platform": device_platform,
                "country": country,
                "timezone": self.safe_text(data.get("timezone", "Africa/Cairo"), 50),
                "preferences": json.dumps(preferences) if preferences else "{}",
                "is_active": bool(data.get("isActive", True)),
                "last_login_at": self.to_timestamp(data.get("lastLoginAt", data.get("lastActive"))),
                "created_at": self.to_timestamp(data.get("createdAt", data.get("created_at"))),
            }
        except Exception as e:
            self.logger.error(f"Error transforming user {doc_id}: {e}")
            return None
    
    def transform_device(self, doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a Firestore device document into PostgreSQL row data."""
        try:
            fcm_token = str(data.get("fcmToken", data.get("token", doc_id)))
            device_id = fcm_token[:50] if len(fcm_token) > 50 else fcm_token
            
            platform = str(data.get("platform", "unknown")).lower()
            if platform not in {"android", "ios", "web", "unknown"}:
                platform = "unknown"
            
            tier_raw = data.get("tier", "free")
            tier = TIER_MAPPING.get(str(tier_raw).lower().strip(), "free")
            
            return {
                "id": device_id,
                "fcm_token": fcm_token[:500],
                "device_id": self.safe_text(data.get("deviceId", data.get("device_id", "")), 200),
                "device_model": self.safe_text(data.get("deviceModel", data.get("model", "")), 100),
                "os_version": self.safe_text(data.get("osVersion", data.get("os", "")), 50),
                "app_version": self.safe_text(data.get("appVersion", "1.0.0"), 20),
                "platform": platform,
                "user_id": data.get("userId"),
                "tier": tier,
                "country": data.get("country", "egypt"),
                "is_active": bool(data.get("isActive", True)),
                "registered_at": self.to_timestamp(data.get("registeredAt", data.get("createdAt"))),
                "last_active": self.to_timestamp(data.get("lastActive", data.get("updatedAt"))),
            }
        except Exception as e:
            self.logger.error(f"Error transforming device {doc_id}: {e}")
            return None
    
    def transform_price_snapshot(self, doc_id: str, data: Dict[str, Any],
                                  parent_product_id: str = "", 
                                  parent_site: str = "amazon_eg") -> Optional[Dict[str, Any]]:
        """Transform a Firestore price history document into TimescaleDB row."""
        try:
            site = SITE_MAPPING.get(str(data.get("site", parent_site)).lower().strip(), "amazon_eg")
            product_id = str(data.get("productId", parent_product_id or doc_id))
            deal_id = data.get("dealId", self.compute_deal_id(site, product_id, 0))
            
            currency_raw = data.get("currency", "EGP")
            currency = CURRENCY_MAPPING.get(str(currency_raw).upper().strip(), "EGP")
            
            price = self.safe_decimal(data.get("price", 0))
            original_price = self.safe_decimal(data.get("originalPrice", data.get("original_price")))
            
            if original_price and original_price > 0 and price > 0:
                discount_percent = round(((original_price - price) / original_price) * 100, 2)
            else:
                discount_percent = self.safe_decimal(data.get("discountPercent", 0))
            
            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            
            return {
                "time": self.to_timestamp(data.get("timestamp", data.get("time", data.get("recordedAt", datetime.now(timezone.utc))))),
                "deal_id": deal_id,
                "product_id": product_id[:100],
                "site": site,
                "price": max(0, price),
                "original_price": original_price if original_price and original_price > 0 else None,
                "discount_percent": max(0, discount_percent),
                "currency": currency,
                "in_stock": bool(data.get("inStock", data.get("in_stock", True))),
                "scraped_by": self.safe_text(data.get("scrapedBy", "migration"), 100),
                "metadata": json.dumps(metadata) if metadata else "{}",
            }
        except Exception as e:
            self.logger.error(f"Error transforming price snapshot {doc_id}: {e}")
            return None
    
    def transform_favorite(self, doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a Firestore favorite document into PostgreSQL row."""
        try:
            return {
                "user_id": str(data.get("userId", data.get("user_id", doc_id.split("_")[0] if "_" in doc_id else ""))),
                "deal_id": str(data.get("dealId", data.get("deal_id", ""))),
                "favorited_at": self.to_timestamp(data.get("favoritedAt", data.get("createdAt", datetime.now(timezone.utc)))),
            }
        except Exception as e:
            self.logger.error(f"Error transforming favorite {doc_id}: {e}")
            return None
    
    def transform_alert_rule(self, doc_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform a Firestore alert rule into PostgreSQL row."""
        try:
            site_raw = data.get("site", "amazon_eg")
            site = SITE_MAPPING.get(str(site_raw).lower().strip(), "amazon_eg")
            
            alert_type = str(data.get("alertType", "price_drop")).lower()
            if alert_type not in {"price_drop", "target_price", "back_in_stock", "discount_available"}:
                alert_type = "price_drop"
            
            return {
                "user_id": str(data.get("userId", data.get("user_id", ""))),
                "product_id": str(data.get("productId", data.get("product_id", ""))),
                "site": site,
                "alert_type": alert_type,
                "target_price": self.safe_decimal(data.get("targetPrice")) if data.get("targetPrice") else None,
                "discount_threshold": self.safe_decimal(data.get("discountThreshold", 10.0)),
                "is_active": bool(data.get("isActive", True)),
                "trigger_count": self.safe_int(data.get("triggerCount", 0)),
                "last_triggered_at": self.to_timestamp(data.get("lastTriggeredAt")),
                "expires_at": self.to_timestamp(data.get("expiresAt")),
                "created_at": self.to_timestamp(data.get("createdAt", datetime.now(timezone.utc))),
            }
        except Exception as e:
            self.logger.error(f"Error transforming alert rule {doc_id}: {e}")
            return None


# =============================================================================
# MIGRATION ENGINE
# =============================================================================

class MigrationEngine:
    """Orchestrates the Firestore to PostgreSQL migration."""
    
    def __init__(self, firestore_mgr: FirestoreManager, 
                 supabase_db: DatabaseManager,
                 timescale_db: DatabaseManager,
                 transformer: DataTransformer,
                 stats: MigrationStats,
                 logger: logging.Logger,
                 dry_run: bool = False):
        self.firestore = firestore_mgr
        self.supabase = supabase_db
        self.timescale = timescale_db
        self.transformer = transformer
        self.stats = stats
        self.logger = logger
        self.dry_run = dry_run
    
    def _batch_insert(self, db: DatabaseManager, table: str, columns: List[str],
                      rows: List[Dict], conflict_column: str = "id",
                      update_columns: Optional[List[str]] = None) -> Tuple[int, int, int]:
        """Perform a batched INSERT ... ON CONFLICT DO UPDATE."""
        if not rows:
            return 0, 0, 0
        
        if self.dry_run:
            self.logger.debug(f"[DRY-RUN] Would insert {len(rows)} rows into {table}")
            return len(rows), 0, 0
        
        # Build the INSERT query
        col_str = ", ".join(columns)
        placeholders = ", ".join([f"%s"] * len(columns))
        
        if update_columns:
            update_str = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_columns])
            query = f"""
                INSERT INTO {table} ({col_str})
                VALUES %s
                ON CONFLICT ({conflict_column})
                DO UPDATE SET {update_str}
            """
        else:
            query = f"""
                INSERT INTO {table} ({col_str})
                VALUES %s
                ON CONFLICT ({conflict_column})
                DO NOTHING
            """
        
        # Extract values in column order
        values = []
        for row in rows:
            row_values = []
            for col in columns:
                val = row.get(col)
                if isinstance(val, list):
                    row_values.append(val)
                elif val is None:
                    row_values.append(None)
                else:
                    row_values.append(val)
            values.append(tuple(row_values))
        
        try:
            with db.transaction():
                with db._conn.cursor() as cur:
                    execute_values(cur, query, values, page_size=1000)
                    
                    # Estimate results
                    inserted = cur.rowcount if cur.rowcount > 0 else 0
                    if update_columns:
                        updated = max(0, len(rows) - inserted)
                        return inserted, updated, 0
                    else:
                        skipped = max(0, len(rows) - inserted)
                        return inserted, 0, skipped
        except Exception as e:
            self.logger.error(f"Batch insert failed for {table}: {e}")
            # Fall back to individual inserts for error isolation
            inserted = 0
            updated = 0
            skipped = 0
            for row in rows:
                try:
                    with db.transaction():
                        single_values = [[row.get(col) for col in columns]]
                        with db._conn.cursor() as cur:
                            execute_values(cur, query, single_values, page_size=1)
                            if cur.rowcount > 0:
                                inserted += 1
                            else:
                                skipped += 1
                except Exception as e2:
                    self.logger.debug(f"Row insert failed: {e2}")
                    skipped += 1
            return inserted, updated, skipped
    
    def migrate_deals(self, batch_size: int = 500) -> None:
        """Migrate deals from Firestore to Supabase PostgreSQL."""
        collection = "deals"
        self.logger.info(f"Starting migration of '{collection}' collection...")
        self.stats.add_collection(collection)
        self.stats.collections[collection]["start_time"] = datetime.now(timezone.utc)
        
        columns = [
            "id", "product_id", "site", "title", "image_url", "product_url",
            "category", "original_price", "current_price", "discount_percent",
            "savings", "currency", "verdict", "fake_score", "recommendation",
            "confidence", "fraud_reasons", "rating", "review_count",
            "marketplace_country", "is_active", "is_featured", "created_at",
            "scraped_at", "metadata"
        ]
        
        update_columns = [
            "title", "image_url", "current_price", "original_price",
            "discount_percent", "savings", "verdict", "fake_score",
            "recommendation", "confidence", "fraud_reasons", "rating",
            "review_count", "is_active", "scraped_at", "metadata"
        ]
        
        batch = []
        total_docs = 0
        
        try:
            for doc in tqdm(self.firestore.stream_collection(collection, batch_size),
                           desc="Migrating deals", unit="docs"):
                total_docs += 1
                data = doc.to_dict()
                if not data:
                    self.stats.record_batch(collection, skipped=1)
                    continue
                
                row = self.transformer.transform_deal(doc.id, data)
                if row:
                    batch.append(row)
                else:
                    self.stats.record_batch(collection, skipped=1)
                
                if len(batch) >= batch_size:
                    ins, upd, skp = self._batch_insert(
                        self.supabase, "deals", columns, batch,
                        conflict_column="id", update_columns=update_columns
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
                    self.logger.debug(f"Batch: {ins} inserted, {upd} updated, {skp} skipped")
                    batch = []
            
            # Final batch
            if batch:
                ins, upd, skp = self._batch_insert(
                    self.supabase, "deals", columns, batch,
                    conflict_column="id", update_columns=update_columns
                )
                self.stats.record_batch(collection, ins, upd, skp)
        
        except Exception as e:
            self.logger.error(f"Fatal error migrating deals: {e}")
            self.stats.add_error(collection, "batch", str(e))
        
        self.stats.collections[collection]["total_firestore_docs"] = total_docs
        self.stats.collections[collection]["end_time"] = datetime.now(timezone.utc)
        
        stats = self.stats.collections[collection]
        self.logger.info(
            f"Deals migration complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped, "
            f"{stats['failed']} failed"
        )
    
    def migrate_users(self, batch_size: int = 200) -> None:
        """Migrate users from Firestore to Supabase PostgreSQL."""
        collection = "users"
        self.logger.info(f"Starting migration of '{collection}' collection...")
        self.stats.add_collection(collection)
        self.stats.collections[collection]["start_time"] = datetime.now(timezone.utc)
        
        columns = [
            "id", "firebase_uid", "email", "phone", "display_name",
            "avatar_url", "tier", "tier_expires_at", "fcm_token",
            "device_platform", "country", "timezone", "preferences",
            "is_active", "last_login_at", "created_at"
        ]
        
        update_columns = [
            "display_name", "email", "phone", "tier", "tier_expires_at",
            "fcm_token", "device_platform", "is_active", "last_login_at",
            "preferences"
        ]
        
        batch = []
        total_docs = 0
        
        try:
            for doc in tqdm(self.firestore.stream_collection(collection, batch_size),
                           desc="Migrating users", unit="docs"):
                total_docs += 1
                data = doc.to_dict()
                if not data:
                    self.stats.record_batch(collection, skipped=1)
                    continue
                
                row = self.transformer.transform_user(doc.id, data)
                if row:
                    batch.append(row)
                else:
                    self.stats.record_batch(collection, skipped=1)
                
                if len(batch) >= batch_size:
                    ins, upd, skp = self._batch_insert(
                        self.supabase, "users", columns, batch,
                        conflict_column="firebase_uid", update_columns=update_columns
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
                    batch = []
            
            if batch:
                ins, upd, skp = self._batch_insert(
                    self.supabase, "users", columns, batch,
                    conflict_column="firebase_uid", update_columns=update_columns
                )
                self.stats.record_batch(collection, ins, upd, skp)
        
        except Exception as e:
            self.logger.error(f"Fatal error migrating users: {e}")
            self.stats.add_error(collection, "batch", str(e))
        
        self.stats.collections[collection]["total_firestore_docs"] = total_docs
        self.stats.collections[collection]["end_time"] = datetime.now(timezone.utc)
        
        stats = self.stats.collections[collection]
        self.logger.info(
            f"Users migration complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped"
        )
    
    def migrate_devices(self, batch_size: int = 300) -> None:
        """Migrate device tokens from Firestore to Supabase PostgreSQL."""
        collection = "devices"
        self.logger.info(f"Starting migration of '{collection}' collection...")
        self.stats.add_collection(collection)
        self.stats.collections[collection]["start_time"] = datetime.now(timezone.utc)
        
        columns = [
            "id", "fcm_token", "device_id", "device_model", "os_version",
            "app_version", "platform", "user_id", "tier", "country",
            "is_active", "registered_at", "last_active"
        ]
        
        batch = []
        total_docs = 0
        
        try:
            for doc in tqdm(self.firestore.stream_collection(collection, batch_size),
                           desc="Migrating devices", unit="docs"):
                total_docs += 1
                data = doc.to_dict()
                if not data:
                    self.stats.record_batch(collection, skipped=1)
                    continue
                
                row = self.transformer.transform_device(doc.id, data)
                if row:
                    batch.append(row)
                else:
                    self.stats.record_batch(collection, skipped=1)
                
                if len(batch) >= batch_size:
                    ins, upd, skp = self._batch_insert(
                        self.supabase, "devices", columns, batch,
                        conflict_column="id"
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
                    batch = []
            
            if batch:
                ins, upd, skp = self._batch_insert(
                    self.supabase, "devices", columns, batch,
                    conflict_column="id"
                )
                self.stats.record_batch(collection, ins, upd, skp)
        
        except Exception as e:
            self.logger.error(f"Fatal error migrating devices: {e}")
            self.stats.add_error(collection, "batch", str(e))
        
        self.stats.collections[collection]["total_firestore_docs"] = total_docs
        self.stats.collections[collection]["end_time"] = datetime.now(timezone.utc)
        
        stats = self.stats.collections[collection]
        self.logger.info(
            f"Devices migration complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped"
        )
    
    def migrate_favorites(self, batch_size: int = 300) -> None:
        """Migrate user favorites from Firestore to Supabase PostgreSQL."""
        collection = "favorites"
        self.logger.info(f"Starting migration of '{collection}' collection...")
        self.stats.add_collection(collection)
        self.stats.collections[collection]["start_time"] = datetime.now(timezone.utc)
        
        columns = ["user_id", "deal_id", "favorited_at"]
        
        batch = []
        total_docs = 0
        
        try:
            for doc in tqdm(self.firestore.stream_collection(
                    FIRESTORE_COLLECTIONS.get("favorites", "user_favorites"), batch_size),
                           desc="Migrating favorites", unit="docs"):
                total_docs += 1
                data = doc.to_dict()
                if not data:
                    self.stats.record_batch(collection, skipped=1)
                    continue
                
                row = self.transformer.transform_favorite(doc.id, data)
                if row:
                    batch.append(row)
                else:
                    self.stats.record_batch(collection, skipped=1)
                
                if len(batch) >= batch_size:
                    ins, upd, skp = self._batch_insert(
                        self.supabase, "user_favorites", columns, batch,
                        conflict_column=None  # Let it auto-generate IDs
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
                    batch = []
            
            if batch:
                ins, upd, skp = self._batch_insert(
                    self.supabase, "user_favorites", columns, batch
                )
                self.stats.record_batch(collection, ins, upd, skp)
        
        except Exception as e:
            self.logger.error(f"Fatal error migrating favorites: {e}")
            self.stats.add_error(collection, "batch", str(e))
        
        self.stats.collections[collection]["total_firestore_docs"] = total_docs
        self.stats.collections[collection]["end_time"] = datetime.now(timezone.utc)
        
        stats = self.stats.collections[collection]
        self.logger.info(
            f"Favorites migration complete: {stats['inserted']} inserted, "
            f"{stats['skipped']} skipped"
        )
    
    def migrate_alert_rules(self, batch_size: int = 200) -> None:
        """Migrate alert rules from Firestore to Supabase PostgreSQL."""
        collection = "alert_rules"
        self.logger.info(f"Starting migration of '{collection}' collection...")
        self.stats.add_collection(collection)
        self.stats.collections[collection]["start_time"] = datetime.now(timezone.utc)
        
        columns = [
            "user_id", "product_id", "site", "alert_type", "target_price",
            "discount_threshold", "is_active", "trigger_count",
            "last_triggered_at", "expires_at", "created_at"
        ]
        
        batch = []
        total_docs = 0
        
        try:
            for doc in tqdm(self.firestore.stream_collection(
                    FIRESTORE_COLLECTIONS.get("alert_rules", "alert_rules"), batch_size),
                           desc="Migrating alert rules", unit="docs"):
                total_docs += 1
                data = doc.to_dict()
                if not data:
                    self.stats.record_batch(collection, skipped=1)
                    continue
                
                row = self.transformer.transform_alert_rule(doc.id, data)
                if row:
                    batch.append(row)
                else:
                    self.stats.record_batch(collection, skipped=1)
                
                if len(batch) >= batch_size:
                    ins, upd, skp = self._batch_insert(
                        self.supabase, "alert_rules", columns, batch
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
                    batch = []
            
            if batch:
                ins, upd, skp = self._batch_insert(
                    self.supabase, "alert_rules", columns, batch
                )
                self.stats.record_batch(collection, ins, upd, skp)
        
        except Exception as e:
            self.logger.error(f"Fatal error migrating alert rules: {e}")
            self.stats.add_error(collection, "batch", str(e))
        
        self.stats.collections[collection]["total_firestore_docs"] = total_docs
        self.stats.collections[collection]["end_time"] = datetime.now(timezone.utc)
        
        stats = self.stats.collections[collection]
        self.logger.info(
            f"Alert rules migration complete: {stats['inserted']} inserted, "
            f"{stats['skipped']} skipped"
        )
    
    def migrate_price_history(self, batch_size: int = 1000) -> None:
        """Migrate price history from Firestore to TimescaleDB."""
        collection = "price_history"
        self.logger.info(f"Starting migration of price history to TimescaleDB...")
        self.stats.add_collection(collection)
        self.stats.collections[collection]["start_time"] = datetime.now(timezone.utc)
        
        columns = [
            "time", "deal_id", "product_id", "site", "price",
            "original_price", "discount_percent", "currency",
            "in_stock", "scraped_by", "metadata"
        ]
        
        batch = []
        total_docs = 0
        
        # Strategy 1: Try subcollection pattern: products/{id}/price_history
        # Strategy 2: Try flat collection: price_history
        
        try:
            # First try flat collection
            logger.info("Checking for flat 'price_history' collection...")
            price_docs = list(self.firestore.stream_collection("price_history", 1))
            
            if price_docs:
                logger.info("Found flat price_history collection, migrating...")
                for doc in tqdm(self.firestore.stream_collection("price_history", batch_size),
                               desc="Migrating price history (flat)", unit="docs"):
                    total_docs += 1
                    data = doc.to_dict()
                    if not data:
                        self.stats.record_batch(collection, skipped=1)
                        continue
                    
                    row = self.transformer.transform_price_snapshot(doc.id, data)
                    if row:
                        batch.append(row)
                    else:
                        self.stats.record_batch(collection, skipped=1)
                    
                    if len(batch) >= batch_size:
                        ins, upd, skp = self._batch_insert(
                            self.timescale, "price_snapshots", columns, batch
                        )
                        self.stats.record_batch(collection, ins, upd, skp)
                        batch = []
                
                if batch:
                    ins, upd, skp = self._batch_insert(
                        self.timescale, "price_snapshots", columns, batch
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
            
            else:
                # Try subcollection pattern
                logger.info("Trying subcollection pattern: products/{id}/price_history")
                product_count = 0
                
                for product_doc in tqdm(self.firestore.stream_collection("products", 100),
                                       desc="Scanning products for price history", unit="products"):
                    product_count += 1
                    product_data = product_doc.to_dict() or {}
                    product_id = product_data.get("productId", product_doc.id)
                    site = SITE_MAPPING.get(
                        str(product_data.get("site", "amazon_eg")).lower().strip(), 
                        "amazon_eg"
                    )
                    
                    for price_doc in self.firestore.get_subcollection(
                            "products", product_doc.id, "price_history"):
                        total_docs += 1
                        price_data = price_doc.to_dict()
                        if not price_data:
                            self.stats.record_batch(collection, skipped=1)
                            continue
                        
                        row = self.transformer.transform_price_snapshot(
                            price_doc.id, price_data, parent_product_id=product_id, parent_site=site
                        )
                        if row:
                            batch.append(row)
                        else:
                            self.stats.record_batch(collection, skipped=1)
                        
                        if len(batch) >= batch_size:
                            ins, upd, skp = self._batch_insert(
                                self.timescale, "price_snapshots", columns, batch
                            )
                            self.stats.record_batch(collection, ins, upd, skp)
                            batch = []
                
                if batch:
                    ins, upd, skp = self._batch_insert(
                        self.timescale, "price_snapshots", columns, batch
                    )
                    self.stats.record_batch(collection, ins, upd, skp)
                
                logger.info(f"Scanned {product_count} products for price history subcollections")
        
        except Exception as e:
            self.logger.error(f"Fatal error migrating price history: {e}")
            self.stats.add_error(collection, "batch", str(e))
        
        self.stats.collections[collection]["total_firestore_docs"] = total_docs
        self.stats.collections[collection]["end_time"] = datetime.now(timezone.utc)
        
        stats = self.stats.collections[collection]
        self.logger.info(
            f"Price history migration complete: {stats['inserted']} inserted, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )
    
    def run_all(self, batch_size: int = 500) -> None:
        """Run the complete migration pipeline."""
        self.logger.info("=" * 70)
        self.logger.info("DEALHUNTER FIRESTORE → POSTGRESQL MIGRATION")
        self.logger.info("=" * 70)
        self.logger.info(f"Dry run: {self.dry_run}")
        self.logger.info(f"Batch size: {batch_size}")
        self.logger.info("")
        
        self.stats.start()
        
        try:
            # Migration order: users first (devices/favorites reference them)
            self.migrate_users(batch_size=min(batch_size, 200))
            self.migrate_devices(batch_size=min(batch_size, 300))
            self.migrate_deals(batch_size=batch_size)
            self.migrate_favorites(batch_size=min(batch_size, 300))
            self.migrate_alert_rules(batch_size=min(batch_size, 200))
            self.migrate_price_history(batch_size=max(batch_size, 1000))
        
        except KeyboardInterrupt:
            self.logger.warning("Migration interrupted by user.")
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            raise
        finally:
            self.stats.finish()
            self.stats.print_summary(self.logger)
        
        self.logger.info("Migration complete!")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DealHunter Firestore to PostgreSQL Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full migration
    python migration_data.py --all

    # Migrate specific collections
    python migration_data.py --deals --batch-size 500
    python migration_data.py --users --batch-size 200
    python migration_data.py --price-history --batch-size 1000

    # Dry run (validate without writing)
    python migration_data.py --all --dry-run

    # Verbose logging
    python migration_data.py --all -v
        """
    )
    
    # Migration scope
    parser.add_argument("--all", action="store_true", help="Migrate all collections")
    parser.add_argument("--deals", action="store_true", help="Migrate deals collection")
    parser.add_argument("--users", action="store_true", help="Migrate users collection")
    parser.add_argument("--devices", action="store_true", help="Migrate devices collection")
    parser.add_argument("--favorites", action="store_true", help="Migrate favorites collection")
    parser.add_argument("--alert-rules", action="store_true", help="Migrate alert rules")
    parser.add_argument("--price-history", action="store_true", help="Migrate price history to TimescaleDB")
    
    # Configuration
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for inserts (default: 500)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing to PostgreSQL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug logging")
    
    # Connection strings (can also use env vars)
    parser.add_argument("--firebase-creds", default=None, help="Path to Firebase service account JSON")
    parser.add_argument("--supabase-url", default=None, help="Supabase PostgreSQL connection string")
    parser.add_argument("--timescale-url", default=None, help="TimescaleDB connection string")
    
    return parser.parse_args()


def get_connection_url(env_var: str, arg_value: Optional[str], display_name: str) -> str:
    """Get connection URL from argument or environment variable."""
    url = arg_value or os.environ.get(env_var)
    if not url:
        print(f"ERROR: {display_name} connection URL required.")
        print(f"Set via --{env_var.lower().replace('_', '-')} or {env_var} environment variable.")
        sys.exit(1)
    return url


def main():
    args = parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    # Determine which collections to migrate
    migrations = {
        "users": args.users,
        "devices": args.devices,
        "deals": args.deals,
        "favorites": args.favorites,
        "alert_rules": args.alert_rules,
        "price_history": args.price_history,
    }
    
    if args.all:
        for key in migrations:
            migrations[key] = True
    
    if not any(migrations.values()):
        print("ERROR: No migration scope specified. Use --all or specific collection flags.")
        sys.exit(1)
    
    # Resolve connection details
    firebase_creds = args.firebase_creds or os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
    if not firebase_creds or not os.path.exists(firebase_creds):
        print("ERROR: Firebase credentials file not found.")
        print("Set via --firebase-creds or FIREBASE_CREDENTIALS_PATH environment variable.")
        sys.exit(1)
    
    supabase_url = get_connection_url("SUPABASE_URL", args.supabase_url, "Supabase")
    timescale_url = get_connection_url("TIMESCALE_URL", args.timescale_url, "TimescaleDB")
    
    # Initialize components
    logger.info("Initializing Firestore connection...")
    firestore_mgr = FirestoreManager(firebase_creds, logger)
    firestore_mgr.connect()
    
    logger.info("Initializing database connections...")
    supabase_db = DatabaseManager(supabase_url, logger)
    timescale_db = DatabaseManager(timescale_url, logger)
    
    transformer = DataTransformer(logger)
    stats = MigrationStats()
    
    # Verify database connections
    try:
        with supabase_db:
            result = supabase_db.execute("SELECT version();")
            logger.info(f"Supabase connected: {result[0]['version'][:50]}...")
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        sys.exit(1)
    
    try:
        with timescale_db:
            result = timescale_db.execute("SELECT version();")
            logger.info(f"TimescaleDB connected: {result[0]['version'][:50]}...")
    except Exception as e:
        logger.error(f"Failed to connect to TimescaleDB: {e}")
        sys.exit(1)
    
    # Create engine and run migrations
    engine = MigrationEngine(
        firestore_mgr=firestore_mgr,
        supabase_db=supabase_db,
        timescale_db=timescale_db,
        transformer=transformer,
        stats=stats,
        logger=logger,
        dry_run=args.dry_run
    )
    
    if args.all:
        engine.run_all(batch_size=args.batch_size)
    else:
        stats.start()
        try:
            if migrations["users"]:
                engine.migrate_users(batch_size=min(args.batch_size, 200))
            if migrations["devices"]:
                engine.migrate_devices(batch_size=min(args.batch_size, 300))
            if migrations["deals"]:
                engine.migrate_deals(batch_size=args.batch_size)
            if migrations["favorites"]:
                engine.migrate_favorites(batch_size=min(args.batch_size, 300))
            if migrations["alert_rules"]:
                engine.migrate_alert_rules(batch_size=min(args.batch_size, 200))
            if migrations["price_history"]:
                engine.migrate_price_history(batch_size=max(args.batch_size, 1000))
        finally:
            stats.finish()
            stats.print_summary(logger)
    
    # Cleanup
    firestore_mgr._db = None
    supabase_db.close()
    timescale_db.close()
    
    logger.info("Migration process completed.")
    return 0 if len(stats.errors) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
