-- =============================================================================
-- DEALHUNTER EGYPT — SUPABASE PRO POSTGRESQL SCHEMA
-- =============================================================================
-- Database: PostgreSQL 15+ (Supabase Pro)
-- Purpose: Main application database for DealHunter Flutter app
-- Tables: deals, users, devices, membership_tiers, payments, scraper_logs
-- Features: Full-text search, RLS, triggers, functions, indexes
-- =============================================================================

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

DO $$ BEGIN
    CREATE TYPE site_enum AS ENUM (
        'amazon_eg', 'noon_eg', 'jumia_eg', 
        'amazon_ae', 'noon_ae', 'noon_sa'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE category_enum AS ENUM (
        'electronics', 'fashion', 'home', 'sports', 'grocery', 'general'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE verdict_enum AS ENUM (
        'GENUINE', 'SUSPICIOUS', 'FAKE', 'UNVERIFIED'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE tier_enum AS ENUM (
        'free', 'trial', 'premium', 'vip', 'elite'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE device_platform_enum AS ENUM (
        'android', 'ios', 'web'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE platform_enum AS ENUM (
        'android', 'ios', 'web', 'unknown'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE payment_provider_enum AS ENUM (
        'paymob', 'tap'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE payment_status_enum AS ENUM (
        'pending', 'completed', 'failed', 'refunded'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE recommendation_enum AS ENUM (
        'buy_now', 'wait', 'normal', 'avoid', 'check_back_later'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- =============================================================================
-- TABLE: deals — Main deals/products table
-- =============================================================================

CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    site site_enum NOT NULL,
    title TEXT NOT NULL,
    image_url TEXT,
    product_url TEXT NOT NULL,
    category category_enum DEFAULT 'general',
    original_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    current_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    discount_percent DECIMAL(5,2) NOT NULL DEFAULT 0,
    savings DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency TEXT DEFAULT 'EGP' CHECK (currency IN ('EGP', 'AED', 'SAR', 'USD')),
    verdict verdict_enum DEFAULT 'UNVERIFIED',
    fake_score DECIMAL(5,2) DEFAULT 0 CHECK (fake_score >= 0 AND fake_score <= 100),
    recommendation recommendation_enum DEFAULT 'normal',
    confidence DECIMAL(3,2) DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    fraud_reasons TEXT[] DEFAULT '{}',
    rating DECIMAL(3,2) CHECK (rating >= 0 AND rating <= 5),
    review_count INTEGER DEFAULT 0 CHECK (review_count >= 0),
    marketplace_country TEXT DEFAULT 'egypt' CHECK (marketplace_country IN ('egypt', 'uae', 'saudi')),
    is_active BOOLEAN DEFAULT TRUE,
    is_featured BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    scraped_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Comments
COMMENT ON TABLE deals IS 'Main deals table storing scraped product deals across all marketplaces';
COMMENT ON COLUMN deals.id IS 'MD5 hash of site || url || price for idempotency';
COMMENT ON COLUMN deals.product_id IS 'Marketplace-specific product identifier (ASIN/SKU)';
COMMENT ON COLUMN deals.fake_score IS '0-100 score indicating likelihood of fake discount';
COMMENT ON COLUMN deals.confidence IS '0.00-1.00 confidence level in the verdict';
COMMENT ON COLUMN deals.fraud_reasons IS 'Array of reasons for fraud suspicion';
COMMENT ON COLUMN deals.metadata IS 'Flexible JSONB for marketplace-specific data';

-- =============================================================================
-- TABLE: users — App users linked to Firebase Auth
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid TEXT UNIQUE,
    email TEXT,
    phone TEXT,
    display_name TEXT,
    avatar_url TEXT,
    tier tier_enum DEFAULT 'free',
    tier_expires_at TIMESTAMPTZ,
    fcm_token TEXT,
    device_platform device_platform_enum,
    country TEXT DEFAULT 'egypt' CHECK (country IN ('egypt', 'uae', 'saudi')),
    timezone TEXT DEFAULT 'Africa/Cairo',
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT valid_email CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

COMMENT ON TABLE users IS 'Application users synchronized from Firebase Auth';
COMMENT ON COLUMN users.firebase_uid IS 'Firebase Authentication user ID for cross-system identity';
COMMENT ON COLUMN users.tier_expires_at IS 'When the current membership tier expires, NULL for free';

-- =============================================================================
-- TABLE: devices — Device tokens for push notifications
-- =============================================================================

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    fcm_token TEXT NOT NULL UNIQUE,
    device_id TEXT,
    device_model TEXT,
    os_version TEXT,
    app_version TEXT,
    platform platform_enum DEFAULT 'unknown',
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tier tier_enum DEFAULT 'free',
    country TEXT DEFAULT 'egypt',
    is_active BOOLEAN DEFAULT TRUE,
    badge_count INTEGER DEFAULT 0,
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW(),
    last_notified_at TIMESTAMPTZ
);

COMMENT ON TABLE devices IS 'Registered devices for push notification delivery via Firebase Cloud Messaging';
COMMENT ON COLUMN devices.id IS 'First 50 characters of the FCM token';

-- =============================================================================
-- TABLE: membership_tiers — Membership tier configuration
-- =============================================================================

CREATE TABLE IF NOT EXISTS membership_tiers (
    id TEXT PRIMARY KEY CHECK (id IN ('free', 'trial', 'premium', 'vip', 'elite')),
    name TEXT NOT NULL,
    price_egp DECIMAL(10,2) NOT NULL DEFAULT 0,
    price_aed DECIMAL(10,2) DEFAULT 0,
    price_sar DECIMAL(10,2) DEFAULT 0,
    features TEXT[] NOT NULL DEFAULT '{}',
    daily_alert_limit INTEGER DEFAULT 0,
    max_alerts INTEGER DEFAULT 0,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE membership_tiers IS 'Membership tier definitions and pricing for all supported countries';

-- =============================================================================
-- TABLE: payments — Payment records for membership subscriptions
-- =============================================================================

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tier tier_enum NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency TEXT DEFAULT 'EGP' CHECK (currency IN ('EGP', 'AED', 'SAR', 'USD')),
    provider payment_provider_enum NOT NULL,
    provider_order_id TEXT,
    provider_transaction_id TEXT,
    status payment_status_enum DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    paid_at TIMESTAMPTZ,
    refunded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE payments IS 'Payment transactions processed through Paymob, Tap, or other providers';

-- =============================================================================
-- TABLE: scraper_logs — Scraper execution audit logs
-- =============================================================================

CREATE TABLE IF NOT EXISTS scraper_logs (
    id BIGSERIAL PRIMARY KEY,
    source site_enum NOT NULL,
    source_url TEXT,
    scraper_version TEXT DEFAULT '1.0.0',
    deals_found INTEGER DEFAULT 0 CHECK (deals_found >= 0),
    deals_inserted INTEGER DEFAULT 0 CHECK (deals_inserted >= 0),
    deals_updated INTEGER DEFAULT 0 CHECK (deals_updated >= 0),
    deals_skipped INTEGER DEFAULT 0 CHECK (deals_skipped >= 0),
    deals_expired INTEGER DEFAULT 0 CHECK (deals_expired >= 0),
    errors TEXT[] DEFAULT '{}',
    warnings TEXT[] DEFAULT '{}',
    duration_ms INTEGER CHECK (duration_ms >= 0),
    memory_mb DECIMAL(10,2),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT valid_completion CHECK (completed_at IS NULL OR completed_at >= started_at)
);

COMMENT ON TABLE scraper_logs IS 'Audit trail for every scraper execution run across all marketplaces';

-- =============================================================================
-- TABLE: user_favorites — User-deal favorites/watchlist
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_favorites (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    deal_id TEXT NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    favorited_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, deal_id)
);

COMMENT ON TABLE user_favorites IS 'User saved/watched deals for quick access and price tracking';

-- =============================================================================
-- TABLE: alert_rules — User-configured price alert rules
-- =============================================================================

CREATE TABLE IF NOT EXISTS alert_rules (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    site site_enum NOT NULL,
    alert_type TEXT DEFAULT 'price_drop' CHECK (alert_type IN ('price_drop', 'target_price', 'back_in_stock', 'discount_available')),
    target_price DECIMAL(12,2),
    discount_threshold DECIMAL(5,2) DEFAULT 10.00,
    is_active BOOLEAN DEFAULT TRUE,
    trigger_count INTEGER DEFAULT 0,
    last_triggered_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE alert_rules IS 'User-configured price drop and availability alert rules';

-- =============================================================================
-- TABLE: notifications — Push notification history
-- =============================================================================

CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    device_id TEXT REFERENCES devices(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    notification_type TEXT DEFAULT 'price_drop' CHECK (notification_type IN ('price_drop', 'deal_expired', 'membership_expiring', 'system', 'welcome', 'alert_triggered')),
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    fcm_response TEXT
);

COMMENT ON TABLE notifications IS 'Audit trail of all push notifications sent to users';

-- =============================================================================
-- TABLE: deal_price_history — Quick price history (within main DB)
-- =============================================================================

CREATE TABLE IF NOT EXISTS deal_price_history (
    id BIGSERIAL PRIMARY KEY,
    deal_id TEXT NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    site site_enum NOT NULL,
    price DECIMAL(12,2) NOT NULL,
    original_price DECIMAL(12,2),
    discount_percent DECIMAL(5,2) DEFAULT 0,
    currency TEXT DEFAULT 'EGP',
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE deal_price_history IS 'Lightweight price history stored in main DB for quick lookups; full history in TimescaleDB';

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Deals indexes
CREATE INDEX IF NOT EXISTS idx_deals_site ON deals(site);
CREATE INDEX IF NOT EXISTS idx_deals_category ON deals(category);
CREATE INDEX IF NOT EXISTS idx_deals_verdict ON deals(verdict);
CREATE INDEX IF NOT EXISTS idx_deals_discount ON deals(discount_percent DESC);
CREATE INDEX IF NOT EXISTS idx_deals_active ON deals(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_deals_product_id ON deals(product_id);
CREATE INDEX IF NOT EXISTS idx_deals_featured ON deals(is_featured) WHERE is_featured = TRUE AND is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_deals_created ON deals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_marketplace_country ON deals(marketplace_country);

-- Full-text search on deals (title + category)
CREATE INDEX IF NOT EXISTS idx_deals_search 
    ON deals USING gin(to_tsvector('english', title || ' ' || COALESCE(category::TEXT, '')));

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_firebase ON users(firebase_uid) WHERE firebase_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_tier ON users(tier);
CREATE INDEX IF NOT EXISTS idx_users_fcm ON users(fcm_token) WHERE fcm_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = TRUE;

-- Devices indexes
CREATE INDEX IF NOT EXISTS idx_devices_user ON devices(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_devices_platform ON devices(platform);
CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_devices_last_active ON devices(last_active DESC);

-- Payments indexes
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_provider ON payments(provider);
CREATE INDEX IF NOT EXISTS idx_payments_created ON payments(created_at DESC);

-- Scraper logs indexes
CREATE INDEX IF NOT EXISTS idx_scraper_logs_source ON scraper_logs(source);
CREATE INDEX IF NOT EXISTS idx_scraper_logs_started ON scraper_logs(started_at DESC);

-- User favorites indexes
CREATE INDEX IF NOT EXISTS idx_favorites_user ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_deal ON user_favorites(deal_id);

-- Alert rules indexes
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alert_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_product ON alert_rules(product_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alert_rules(is_active) WHERE is_active = TRUE;

-- Notifications indexes
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_sent ON notifications(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;

-- Deal price history indexes
CREATE INDEX IF NOT EXISTS idx_price_history_deal ON deal_price_history(deal_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_history_product ON deal_price_history(product_id, recorded_at DESC);

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Auto-update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at_column() IS 'Automatically sets updated_at to current timestamp on row update';

-- =============================================================================
-- TRIGGERS — Apply auto-update to all tables with updated_at
-- =============================================================================

DO $$ BEGIN
    CREATE TRIGGER update_deals_updated_at
        BEFORE UPDATE ON deals
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_payments_updated_at
        BEFORE UPDATE ON payments
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_alert_rules_updated_at
        BEFORE UPDATE ON alert_rules
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- =============================================================================
-- DEAL VERIFICATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION get_deal_verdict(
    p_product_id TEXT,
    p_marketplace TEXT DEFAULT 'amazon_eg'
)
RETURNS TABLE (
    verdict TEXT,
    confidence DECIMAL,
    explanation TEXT,
    red_flags TEXT[],
    recommendation TEXT,
    historical_high DECIMAL,
    historical_low DECIMAL,
    data_found BOOLEAN
) AS $$
DECLARE
    v_found BOOLEAN := FALSE;
BEGIN
    RETURN QUERY
    SELECT 
        d.verdict::TEXT,
        d.confidence,
        CASE d.verdict
            WHEN 'FAKE' THEN 'This deal shows clear signs of an inflated discount. The seller may have raised the original price before applying the discount.'
            WHEN 'GENUINE' THEN 'This appears to be a genuine discount based on historical price data analysis.'
            WHEN 'SUSPICIOUS' THEN 'This deal has suspicious indicators. The discount pattern or pricing history raises concerns.'
            ELSE 'Insufficient price history data to make a definitive determination. Check back later for more data.'
        END::TEXT,
        COALESCE(d.fraud_reasons, ARRAY[]::TEXT[]),
        d.recommendation::TEXT,
        d.original_price,
        d.current_price,
        TRUE
    FROM deals d
    WHERE d.product_id = p_product_id AND d.site::TEXT = p_marketplace
    LIMIT 1;

    GET DIAGNOSTICS v_found = ROW_COUNT;

    IF NOT v_found OR v_found = 0 THEN
        RETURN QUERY SELECT 
            'uncertain'::TEXT, 
            0::DECIMAL, 
            'No price history data available for this product.'::TEXT,
            ARRAY[]::TEXT[],
            'check_back_later'::TEXT,
            NULL::DECIMAL, 
            NULL::DECIMAL, 
            FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_deal_verdict(TEXT, TEXT) IS 'Analyzes a product deal and returns fraud detection verdict with explanation';

-- =============================================================================
-- FULL-TEXT SEARCH FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION search_deals(
    search_query TEXT,
    p_site site_enum DEFAULT NULL,
    p_category category_enum DEFAULT NULL,
    p_min_discount DECIMAL DEFAULT 0,
    result_limit INTEGER DEFAULT 20,
    result_offset INTEGER DEFAULT 0
)
RETURNS SETOF deals AS $$
DECLARE
    v_tsquery tsquery;
BEGIN
    v_tsquery := plainto_tsquery('english', search_query);
    
    RETURN QUERY
    SELECT d.* FROM deals d
    WHERE to_tsvector('english', d.title || ' ' || COALESCE(d.category::TEXT, '')) @@ v_tsquery
        AND d.is_active = TRUE
        AND (p_site IS NULL OR d.site = p_site)
        AND (p_category IS NULL OR d.category = p_category)
        AND d.discount_percent >= p_min_discount
    ORDER BY d.discount_percent DESC, d.rating DESC NULLS LAST, d.review_count DESC NULLS LAST
    LIMIT result_limit OFFSET result_offset;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION search_deals(TEXT, site_enum, category_enum, DECIMAL, INTEGER, INTEGER) IS 'Full-text search across deal titles and categories with optional filtering';

-- =============================================================================
-- DISCOUNT CALCULATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION calculate_discount(
    p_original_price DECIMAL,
    p_current_price DECIMAL
)
RETURNS TABLE (
    discount_percent DECIMAL,
    savings DECIMAL,
    is_valid BOOLEAN
) AS $$
DECLARE
    v_discount DECIMAL;
    v_savings DECIMAL;
BEGIN
    IF p_original_price IS NULL OR p_current_price IS NULL OR p_original_price <= 0 THEN
        RETURN QUERY SELECT 0::DECIMAL, 0::DECIMAL, FALSE;
        RETURN;
    END IF;
    
    v_savings := p_original_price - p_current_price;
    
    IF v_savings <= 0 THEN
        RETURN QUERY SELECT 0::DECIMAL, 0::DECIMAL, FALSE;
        RETURN;
    END IF;
    
    v_discount := ROUND((v_savings / p_original_price) * 100, 2);
    
    RETURN QUERY SELECT v_discount, v_savings, TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION calculate_discount(DECIMAL, DECIMAL) IS 'Calculates discount percentage and savings from original and current price';

-- =============================================================================
-- GET DEALS BY SITE WITH PAGINATION
-- =============================================================================

CREATE OR REPLACE FUNCTION get_deals_by_site(
    p_site site_enum,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0,
    p_min_discount DECIMAL DEFAULT 0
)
RETURNS SETOF deals AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM deals
    WHERE site = p_site
        AND is_active = TRUE
        AND discount_percent >= p_min_discount
    ORDER BY discount_percent DESC, created_at DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_deals_by_site(site_enum, INTEGER, INTEGER, DECIMAL) IS 'Returns paginated active deals for a specific marketplace';

-- =============================================================================
-- GET DEALS BY CATEGORY
-- =============================================================================

CREATE OR REPLACE FUNCTION get_deals_by_category(
    p_category category_enum,
    p_limit INTEGER DEFAULT 20,
    p_offset INTEGER DEFAULT 0,
    p_min_discount DECIMAL DEFAULT 0
)
RETURNS SETOF deals AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM deals
    WHERE category = p_category
        AND is_active = TRUE
        AND discount_percent >= p_min_discount
    ORDER BY discount_percent DESC, created_at DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_deals_by_category(category_enum, INTEGER, INTEGER, DECIMAL) IS 'Returns paginated active deals filtered by category';

-- =============================================================================
-- UPSERT DEAL FUNCTION (idempotent insert/update for scrapers)
-- =============================================================================

CREATE OR REPLACE FUNCTION upsert_deal(
    p_id TEXT,
    p_product_id TEXT,
    p_site site_enum,
    p_title TEXT,
    p_image_url TEXT,
    p_product_url TEXT,
    p_category category_enum,
    p_original_price DECIMAL,
    p_current_price DECIMAL,
    p_discount_percent DECIMAL,
    p_savings DECIMAL,
    p_currency TEXT,
    p_rating DECIMAL,
    p_review_count INTEGER,
    p_marketplace_country TEXT,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS TABLE (
    deal_id TEXT,
    operation TEXT,
    old_discount DECIMAL,
    new_discount DECIMAL
) AS $$
DECLARE
    v_old_discount DECIMAL;
    v_operation TEXT;
BEGIN
    SELECT discount_percent INTO v_old_discount
    FROM deals WHERE deals.id = p_id;

    IF FOUND THEN
        v_operation := 'updated';
        UPDATE deals SET
            title = p_title,
            image_url = p_image_url,
            product_url = p_product_url,
            category = p_category,
            original_price = p_original_price,
            current_price = p_current_price,
            discount_percent = p_discount_percent,
            savings = p_savings,
            currency = p_currency,
            rating = p_rating,
            review_count = p_review_count,
            marketplace_country = p_marketplace_country,
            is_active = TRUE,
            scraped_at = NOW(),
            metadata = deals.metadata || p_metadata
        WHERE deals.id = p_id;
    ELSE
        v_operation := 'inserted';
        INSERT INTO deals (
            id, product_id, site, title, image_url, product_url, category,
            original_price, current_price, discount_percent, savings, currency,
            rating, review_count, marketplace_country, scraped_at, metadata
        ) VALUES (
            p_id, p_product_id, p_site, p_title, p_image_url, p_product_url, p_category,
            p_original_price, p_current_price, p_discount_percent, p_savings, p_currency,
            p_rating, p_review_count, p_marketplace_country, NOW(), p_metadata
        );
    END IF;

    RETURN QUERY SELECT p_id, v_operation, v_old_discount, p_discount_percent;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION upsert_deal(TEXT, TEXT, site_enum, TEXT, TEXT, TEXT, category_enum, DECIMAL, DECIMAL, DECIMAL, DECIMAL, TEXT, DECIMAL, INTEGER, TEXT, JSONB) IS 'Idempotent deal insert/update for scraper pipelines with conflict detection';

-- =============================================================================
-- LOG SCRAPER RUN FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION log_scraper_run(
    p_source site_enum,
    p_source_url TEXT DEFAULT NULL,
    p_scraper_version TEXT DEFAULT '1.0.0'
)
RETURNS BIGINT AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO scraper_logs (source, source_url, scraper_version, started_at)
    VALUES (p_source, p_source_url, p_scraper_version, NOW())
    RETURNING scraper_logs.id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_scraper_run(site_enum, TEXT, TEXT) IS 'Starts a new scraper run and returns the log ID for completion logging';

-- =============================================================================
-- COMPLETE SCRAPER RUN FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION complete_scraper_run(
    p_log_id BIGINT,
    p_deals_found INTEGER,
    p_deals_inserted INTEGER,
    p_deals_updated INTEGER,
    p_deals_skipped INTEGER DEFAULT 0,
    p_errors TEXT[] DEFAULT '{}',
    p_warnings TEXT[] DEFAULT '{}',
    p_duration_ms INTEGER DEFAULT NULL,
    p_memory_mb DECIMAL DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE scraper_logs SET
        deals_found = p_deals_found,
        deals_inserted = p_deals_inserted,
        deals_updated = p_deals_updated,
        deals_skipped = p_deals_skipped,
        errors = p_errors,
        warnings = p_warnings,
        duration_ms = p_duration_ms,
        memory_mb = p_memory_mb,
        completed_at = NOW()
    WHERE id = p_log_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION complete_scraper_run(BIGINT, INTEGER, INTEGER, INTEGER, INTEGER, TEXT[], TEXT[], INTEGER, DECIMAL) IS 'Completes a scraper run with full statistics';

-- =============================================================================
-- CLEANUP EXPIRED DEALS FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION cleanup_expired_deals(
    p_max_age_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    deactivated_count INTEGER,
    deleted_count INTEGER
) AS $$
DECLARE
    v_deactivated INTEGER;
    v_deleted INTEGER;
BEGIN
    UPDATE deals
    SET is_active = FALSE
    WHERE created_at < NOW() - (p_max_age_days || ' days')::INTERVAL
        AND is_active = TRUE;
    GET DIAGNOSTICS v_deactivated = ROW_COUNT;

    DELETE FROM deals
    WHERE is_active = FALSE
        AND created_at < NOW() - ((p_max_age_days + 30) || ' days')::INTERVAL;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    RETURN QUERY SELECT v_deactivated, v_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_deals(INTEGER) IS 'Deactivates old deals and permanently deletes very old inactive deals';

-- =============================================================================
-- GET USER STATISTICS FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION get_user_statistics(p_user_id UUID)
RETURNS TABLE (
    total_favorites BIGINT,
    total_alerts BIGINT,
    active_alerts BIGINT,
    notifications_sent BIGINT,
    unread_notifications BIGINT,
    current_tier TEXT,
    tier_expires_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM user_favorites WHERE user_id = p_user_id),
        (SELECT COUNT(*) FROM alert_rules WHERE user_id = p_user_id),
        (SELECT COUNT(*) FROM alert_rules WHERE user_id = p_user_id AND is_active = TRUE),
        (SELECT COUNT(*) FROM notifications WHERE user_id = p_user_id),
        (SELECT COUNT(*) FROM notifications WHERE user_id = p_user_id AND read_at IS NULL),
        (SELECT tier::TEXT FROM users WHERE id = p_user_id),
        (SELECT users.tier_expires_at FROM users WHERE id = p_user_id);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_user_statistics(UUID) IS 'Returns aggregated statistics for a user dashboard';

-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership_tiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE deal_price_history ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- RLS POLICIES: deals
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Deals are viewable by everyone" 
    ON deals FOR SELECT 
    USING (is_active = TRUE);

CREATE POLICY IF NOT EXISTS "Only service role can insert deals" 
    ON deals FOR INSERT 
    WITH CHECK (FALSE);

CREATE POLICY IF NOT EXISTS "Only service role can update deals" 
    ON deals FOR UPDATE 
    USING (FALSE);

CREATE POLICY IF NOT EXISTS "Only service role can delete deals" 
    ON deals FOR DELETE 
    USING (FALSE);

-- =============================================================================
-- RLS POLICIES: users
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Users can view own record" 
    ON users FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY IF NOT EXISTS "Users can update own record" 
    ON users FOR UPDATE 
    USING (auth.uid() = id);

CREATE POLICY IF NOT EXISTS "Service role can insert users" 
    ON users FOR INSERT 
    WITH CHECK (TRUE);

-- =============================================================================
-- RLS POLICIES: devices
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Users can view own devices" 
    ON devices FOR SELECT 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can insert own devices" 
    ON devices FOR INSERT 
    WITH CHECK (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can update own devices" 
    ON devices FOR UPDATE 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can delete own devices" 
    ON devices FOR DELETE 
    USING (user_id = auth.uid());

-- =============================================================================
-- RLS POLICIES: membership_tiers
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Tiers are viewable by everyone" 
    ON membership_tiers FOR SELECT 
    USING (is_active = TRUE);

CREATE POLICY IF NOT EXISTS "Only service role can modify tiers" 
    ON membership_tiers FOR ALL 
    USING (FALSE);

-- =============================================================================
-- RLS POLICIES: payments
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Users can view own payments" 
    ON payments FOR SELECT 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Service role can create payments" 
    ON payments FOR INSERT 
    WITH CHECK (TRUE);

CREATE POLICY IF NOT EXISTS "Users can update own pending payments" 
    ON payments FOR UPDATE 
    USING (user_id = auth.uid() AND status = 'pending');

-- =============================================================================
-- RLS POLICIES: scraper_logs
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Scraper logs only viewable by service role" 
    ON scraper_logs FOR SELECT 
    USING (FALSE);

CREATE POLICY IF NOT EXISTS "Only service role can manage scraper logs" 
    ON scraper_logs FOR ALL 
    USING (FALSE);

-- =============================================================================
-- RLS POLICIES: user_favorites
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Users can view own favorites" 
    ON user_favorites FOR SELECT 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can add own favorites" 
    ON user_favorites FOR INSERT 
    WITH CHECK (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can remove own favorites" 
    ON user_favorites FOR DELETE 
    USING (user_id = auth.uid());

-- =============================================================================
-- RLS POLICIES: alert_rules
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Users can view own alerts" 
    ON alert_rules FOR SELECT 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can create own alerts" 
    ON alert_rules FOR INSERT 
    WITH CHECK (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can update own alerts" 
    ON alert_rules FOR UPDATE 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can delete own alerts" 
    ON alert_rules FOR DELETE 
    USING (user_id = auth.uid());

-- =============================================================================
-- RLS POLICIES: notifications
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Users can view own notifications" 
    ON notifications FOR SELECT 
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Service role can create notifications" 
    ON notifications FOR INSERT 
    WITH CHECK (TRUE);

CREATE POLICY IF NOT EXISTS "Users can mark own notifications read" 
    ON notifications FOR UPDATE 
    USING (user_id = auth.uid());

-- =============================================================================
-- RLS POLICIES: deal_price_history
-- =============================================================================

CREATE POLICY IF NOT EXISTS "Price history viewable by everyone" 
    ON deal_price_history FOR SELECT 
    USING (TRUE);

CREATE POLICY IF NOT EXISTS "Only service role can insert price history" 
    ON deal_price_history FOR INSERT 
    WITH CHECK (FALSE);

-- =============================================================================
-- GRANT PERMISSIONS FOR ANON/AUTHENTICATED ROLES
-- =============================================================================

GRANT USAGE ON SCHEMA public TO anon, authenticated;

GRANT SELECT ON deals TO anon, authenticated;
GRANT SELECT ON membership_tiers TO anon, authenticated;
GRANT SELECT ON deal_price_history TO anon, authenticated;

GRANT SELECT, UPDATE ON users TO authenticated;
GRANT SELECT, INSERT, DELETE, UPDATE ON devices TO authenticated;
GRANT SELECT ON payments TO authenticated;
GRANT SELECT, INSERT, DELETE ON user_favorites TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON alert_rules TO authenticated;
GRANT SELECT, UPDATE ON notifications TO authenticated;

GRANT USAGE ON SEQUENCE scraper_logs_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE user_favorites_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE alert_rules_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE notifications_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE deal_price_history_id_seq TO authenticated;

-- =============================================================================
-- SCHEMA COMPLETE
-- =============================================================================
-- Total tables: 10
-- Total indexes: 30+
-- Total functions: 10
-- Total triggers: 4
-- Total RLS policies: 30
-- =============================================================================
