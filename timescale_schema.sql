-- =============================================================================
-- DEALHUNTER EGYPT — TIMESCALEDB CLOUD SCHEMA
-- =============================================================================
-- Database: TimescaleDB Cloud (PostgreSQL 15+ with TimescaleDB extension)
-- Purpose: Time-series storage for price history and price change events
-- Tables: price_snapshots, price_change_events
-- Features: Hypertables, continuous aggregates, retention policies, compression
-- =============================================================================

-- =============================================================================
-- PRE-FLIGHT: Verify TimescaleDB extension is available
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        RAISE EXCEPTION 'TimescaleDB extension is not installed. Please install TimescaleDB first.';
    END IF;
END $$;

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TABLE: price_snapshots — Raw time-series price data
-- =============================================================================
-- Stores every price observation collected by scrapers
-- Partitioned by time (7 day chunks) for efficient queries and compression

CREATE TABLE IF NOT EXISTS price_snapshots (
    time TIMESTAMPTZ NOT NULL,
    deal_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    site TEXT NOT NULL CHECK (site IN ('amazon_eg', 'noon_eg', 'jumia_eg', 'amazon_ae', 'noon_ae', 'noon_sa')),
    price DECIMAL(12,2) NOT NULL,
    original_price DECIMAL(12,2),
    discount_percent DECIMAL(5,2) DEFAULT 0,
    currency TEXT DEFAULT 'EGP' CHECK (currency IN ('EGP', 'AED', 'SAR', 'USD')),
    in_stock BOOLEAN DEFAULT TRUE,
    scraped_by TEXT DEFAULT 'system',
    metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE price_snapshots IS 'Time-series price observations collected by scrapers. Converted to hypertable for automatic partitioning.';
COMMENT ON COLUMN price_snapshots.time IS 'Timestamp of the price observation (UTC)';
COMMENT ON COLUMN price_snapshots.deal_id IS 'Reference to the deals table in the main Supabase database';
COMMENT ON COLUMN price_snapshots.product_id IS 'Marketplace-specific product identifier (ASIN/SKU)';
COMMENT ON COLUMN price_snapshots.metadata IS 'Additional scraped data (availability, shipping info, seller)';

-- =============================================================================
-- CONVERT price_snapshots TO HYPERTABLE
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'price_snapshots'
    ) THEN
        PERFORM create_hypertable(
            'price_snapshots', 
            'time', 
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- =============================================================================
-- INDEXES: price_snapshots
-- =============================================================================

-- Already indexed by time via hypertable, add compound indexes for common queries
CREATE INDEX IF NOT EXISTS idx_snapshots_deal 
    ON price_snapshots (deal_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_product 
    ON price_snapshots (product_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_site 
    ON price_snapshots (site, time DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_product_site 
    ON price_snapshots (product_id, site, time DESC);

-- Partial index for in-stock items only
CREATE INDEX IF NOT EXISTS idx_snapshots_in_stock 
    ON price_snapshots (product_id, time DESC) 
    WHERE in_stock = TRUE;

-- =============================================================================
-- TABLE: price_change_events — Significant price changes detected
-- =============================================================================
-- Stores only meaningful price changes to reduce noise

CREATE TABLE IF NOT EXISTS price_change_events (
    time TIMESTAMPTZ NOT NULL,
    deal_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    site TEXT NOT NULL CHECK (site IN ('amazon_eg', 'noon_eg', 'jumia_eg', 'amazon_ae', 'noon_ae', 'noon_sa')),
    old_price DECIMAL(12,2) NOT NULL,
    new_price DECIMAL(12,2) NOT NULL,
    price_change_percent DECIMAL(5,2) NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN ('drop', 'increase', 'new', 'restocked')),
    currency TEXT DEFAULT 'EGP' CHECK (currency IN ('EGP', 'AED', 'SAR', 'USD')),
    triggered_alert BOOLEAN DEFAULT FALSE,
    alerted_users INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE price_change_events IS 'Significant price changes that triggered user alerts or exceeded thresholds';
COMMENT ON COLUMN price_change_events.change_type IS 'Type of change: drop (price decrease), increase (price up), new (first seen), restocked (back in stock)';
COMMENT ON COLUMN price_change_events.triggered_alert IS 'Whether this change triggered any user alert rules';

-- =============================================================================
-- CONVERT price_change_events TO HYPERTABLE
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'price_change_events'
    ) THEN
        PERFORM create_hypertable(
            'price_change_events', 
            'time', 
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- =============================================================================
-- INDEXES: price_change_events
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_price_changes_deal 
    ON price_change_events (deal_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_price_changes_product 
    ON price_change_events (product_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_price_changes_type 
    ON price_change_events (change_type, time DESC);

CREATE INDEX IF NOT EXISTS idx_price_changes_alerted 
    ON price_change_events (triggered_alert, time DESC) 
    WHERE triggered_alert = TRUE;

-- =============================================================================
-- TABLE: deal_metrics — Aggregated daily deal performance metrics
-- =============================================================================

CREATE TABLE IF NOT EXISTS deal_metrics (
    time TIMESTAMPTZ NOT NULL,
    site TEXT NOT NULL CHECK (site IN ('amazon_eg', 'noon_eg', 'jumia_eg', 'amazon_ae', 'noon_ae', 'noon_sa')),
    category TEXT DEFAULT 'general',
    total_deals INTEGER DEFAULT 0,
    avg_discount DECIMAL(5,2) DEFAULT 0,
    max_discount DECIMAL(5,2) DEFAULT 0,
    min_discount DECIMAL(5,2) DEFAULT 0,
    avg_price DECIMAL(12,2) DEFAULT 0,
    deals_verified INTEGER DEFAULT 0,
    deals_suspicious INTEGER DEFAULT 0,
    deals_fake INTEGER DEFAULT 0,
    new_deals INTEGER DEFAULT 0,
    expired_deals INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = 'deal_metrics'
    ) THEN
        PERFORM create_hypertable(
            'deal_metrics', 
            'time', 
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_deal_metrics_site 
    ON deal_metrics (site, time DESC);

CREATE INDEX IF NOT EXISTS idx_deal_metrics_category 
    ON deal_metrics (category, time DESC);

-- =============================================================================
-- CONTINUOUS AGGREGATES
-- =============================================================================

-- Daily price statistics per deal
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_price_stats
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS day,
    deal_id,
    site,
    AVG(price) AS avg_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    AVG(discount_percent) AS avg_discount,
    MAX(discount_percent) AS max_discount,
    MIN(discount_percent) AS min_discount,
    COUNT(*) AS snapshot_count,
    COUNT(*) FILTER (WHERE in_stock = TRUE) AS in_stock_count,
    COUNT(*) FILTER (WHERE in_stock = FALSE) AS out_of_stock_count
FROM price_snapshots
GROUP BY time_bucket('1 day', time), deal_id, site;

COMMENT ON MATERIALIZED VIEW daily_price_stats IS 'Continuous aggregate of daily price statistics per deal for fast dashboard queries';

-- Hourly price statistics per product (for real-time monitoring)
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_price_stats
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS hour,
    product_id,
    site,
    AVG(price) AS avg_price,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    FIRST(price, time) AS open_price,
    LAST(price, time) AS close_price,
    COUNT(*) AS snapshot_count
FROM price_snapshots
GROUP BY time_bucket('1 hour', time), product_id, site;

COMMENT ON MATERIALIZED VIEW hourly_price_stats IS 'Continuous aggregate of hourly price stats for real-time monitoring dashboards';

-- Daily price change event summary
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_price_change_summary
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS day,
    site,
    change_type,
    COUNT(*) AS event_count,
    AVG(ABS(price_change_percent)) AS avg_change_magnitude,
    MAX(ABS(price_change_percent)) AS max_change_magnitude,
    SUM(CASE WHEN triggered_alert THEN 1 ELSE 0 END) AS alerts_triggered
FROM price_change_events
GROUP BY time_bucket('1 day', time), site, change_type;

COMMENT ON MATERIALIZED VIEW daily_price_change_summary IS 'Daily summary of price change events for trend analysis';

-- =============================================================================
-- CONTINUOUS AGGREGATE REFRESH POLICIES
-- =============================================================================

-- Refresh daily stats every hour
DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy('daily_price_stats',
        start_offset => INTERVAL '30 days',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- Refresh hourly stats every 15 minutes
DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy('hourly_price_stats',
        start_offset => INTERVAL '7 days',
        end_offset => INTERVAL '15 minutes',
        schedule_interval => INTERVAL '15 minutes'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- Refresh daily change summary every hour
DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy('daily_price_change_summary',
        start_offset => INTERVAL '30 days',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour'
    );
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- =============================================================================
-- RETENTION POLICIES — Auto-delete old data
-- =============================================================================

-- Keep raw snapshots for 90 days
DO $$
BEGIN
    PERFORM add_retention_policy('price_snapshots', INTERVAL '90 days');
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- Keep change events for 180 days
DO $$BEGIN
    PERFORM add_retention_policy('price_change_events', INTERVAL '180 days');
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- Keep deal metrics for 365 days
DO $$BEGIN
    PERFORM add_retention_policy('deal_metrics', INTERVAL '365 days');
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- =============================================================================
-- COMPRESSION POLICIES — Compress older chunks to save storage
-- =============================================================================

-- Compress snapshots older than 14 days
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        ALTER TABLE price_snapshots SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'deal_id, product_id, site',
            timescaledb.compress_orderby = 'time DESC'
        );
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not set compression on price_snapshots: %', SQLERRM;
END $$;

DO $$
BEGIN
    PERFORM add_compression_policy('price_snapshots', INTERVAL '14 days');
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- Compress change events older than 30 days
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        ALTER TABLE price_change_events SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'deal_id, product_id, site',
            timescaledb.compress_orderby = 'time DESC'
        );
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not set compression on price_change_events: %', SQLERRM;
END $$;

DO $$
BEGIN
    PERFORM add_compression_policy('price_change_events', INTERVAL '30 days');
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Get price history for a specific product
CREATE OR REPLACE FUNCTION get_product_price_history(
    p_product_id TEXT,
    p_site TEXT DEFAULT NULL,
    p_since TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days',
    p_limit INTEGER DEFAULT 1000
)
RETURNS TABLE (
    observation_time TIMESTAMPTZ,
    deal_id TEXT,
    price DECIMAL,
    original_price DECIMAL,
    discount_percent DECIMAL,
    currency TEXT,
    in_stock BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ps.time AS observation_time,
        ps.deal_id,
        ps.price,
        ps.original_price,
        ps.discount_percent,
        ps.currency,
        ps.in_stock
    FROM price_snapshots ps
    WHERE ps.product_id = p_product_id
        AND ps.time >= p_since
        AND (p_site IS NULL OR ps.site = p_site)
    ORDER BY ps.time DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_product_price_history(TEXT, TEXT, TIMESTAMPTZ, INTEGER) IS 'Returns price history for a specific product, optionally filtered by site';

-- Get price range statistics for a product
CREATE OR REPLACE FUNCTION get_product_price_stats(
    p_product_id TEXT,
    p_site TEXT DEFAULT NULL,
    p_since TIMESTAMPTZ DEFAULT NOW() - INTERVAL '30 days'
)
RETURNS TABLE (
    avg_price DECIMAL,
    min_price DECIMAL,
    max_price DECIMAL,
    avg_discount DECIMAL,
    max_discount DECIMAL,
    min_discount DECIMAL,
    observation_count BIGINT,
    price_volatility DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        AVG(ps.price)::DECIMAL,
        MIN(ps.price)::DECIMAL,
        MAX(ps.price)::DECIMAL,
        AVG(ps.discount_percent)::DECIMAL,
        MAX(ps.discount_percent)::DECIMAL,
        MIN(ps.discount_percent)::DECIMAL,
        COUNT(*)::BIGINT,
        STDDEV(ps.price)::DECIMAL AS price_volatility
    FROM price_snapshots ps
    WHERE ps.product_id = p_product_id
        AND ps.time >= p_since
        AND (p_site IS NULL OR ps.site = p_site);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_product_price_stats(TEXT, TEXT, TIMESTAMPTZ) IS 'Returns statistical analysis of a product price history';

-- Detect significant price drop and create event
CREATE OR REPLACE FUNCTION detect_price_change(
    p_product_id TEXT,
    p_deal_id TEXT,
    p_site TEXT,
    p_new_price DECIMAL,
    p_old_price DECIMAL,
    p_currency TEXT DEFAULT 'EGP',
    p_in_stock BOOLEAN DEFAULT TRUE,
    p_change_threshold DECIMAL DEFAULT 5.0
)
RETURNS TABLE (
    change_detected BOOLEAN,
    change_type TEXT,
    change_percent DECIMAL,
    is_significant BOOLEAN
) AS $$
DECLARE
    v_change_percent DECIMAL;
    v_change_type TEXT;
    v_is_significant BOOLEAN;
    v_old_exists BOOLEAN;
BEGIN
    SELECT EXISTS(SELECT 1 FROM price_snapshots WHERE product_id = p_product_id LIMIT 1) INTO v_old_exists;

    IF NOT v_old_exists OR p_old_price IS NULL OR p_old_price = 0 THEN
        v_change_type := 'new';
        v_change_percent := 0;
        v_is_significant := TRUE;
    ELSE
        v_change_percent := ROUND(((p_new_price - p_old_price) / p_old_price) * 100, 2);
        
        IF p_new_price < p_old_price THEN
            v_change_type := 'drop';
            v_is_significant := ABS(v_change_percent) >= p_change_threshold;
        ELSIF p_new_price > p_old_price THEN
            v_change_type := 'increase';
            v_is_significant := ABS(v_change_percent) >= p_change_threshold;
        ELSE
            v_change_type := NULL;
            v_is_significant := FALSE;
        END IF;
    END IF;

    IF v_change_type IS NOT NULL THEN
        INSERT INTO price_change_events (
            time, deal_id, product_id, site, old_price, new_price,
            price_change_percent, change_type, currency
        ) VALUES (
            NOW(), p_deal_id, p_product_id, p_site, COALESCE(p_old_price, p_new_price),
            p_new_price, COALESCE(v_change_percent, 0), v_change_type, p_currency
        );
    END IF;

    RETURN QUERY SELECT TRUE, v_change_type, v_change_percent, v_is_significant;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_price_change(TEXT, TEXT, TEXT, DECIMAL, DECIMAL, TEXT, BOOLEAN, DECIMAL) IS 'Detects significant price changes and records events. Returns change details.';

-- Insert price snapshot with automatic change detection
CREATE OR REPLACE FUNCTION insert_price_snapshot(
    p_deal_id TEXT,
    p_product_id TEXT,
    p_site TEXT,
    p_price DECIMAL,
    p_original_price DECIMAL,
    p_discount_percent DECIMAL DEFAULT 0,
    p_currency TEXT DEFAULT 'EGP',
    p_in_stock BOOLEAN DEFAULT TRUE,
    p_scraped_by TEXT DEFAULT 'system',
    p_metadata JSONB DEFAULT '{}'
)
RETURNS TABLE (
    snapshot_inserted BOOLEAN,
    change_detected BOOLEAN,
    change_type TEXT,
    change_percent DECIMAL
) AS $$
DECLARE
    v_old_price DECIMAL;
    v_change_result RECORD;
BEGIN
    -- Get the most recent price for change detection
    SELECT price INTO v_old_price
    FROM price_snapshots
    WHERE product_id = p_product_id AND site = p_site
    ORDER BY time DESC
    LIMIT 1;

    -- Insert the snapshot
    INSERT INTO price_snapshots (
        time, deal_id, product_id, site, price, original_price,
        discount_percent, currency, in_stock, scraped_by, metadata
    ) VALUES (
        NOW(), p_deal_id, p_product_id, p_site, p_price, p_original_price,
        p_discount_percent, p_currency, p_in_stock, p_scraped_by, p_metadata
    );

    -- Detect and record any price change
    SELECT * INTO v_change_result
    FROM detect_price_change(
        p_product_id, p_deal_id, p_site, p_price, v_old_price, p_currency, p_in_stock
    );

    RETURN QUERY SELECT TRUE, v_change_result.change_detected, v_change_result.change_type, v_change_result.change_percent;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION insert_price_snapshot(TEXT, TEXT, TEXT, DECIMAL, DECIMAL, DECIMAL, TEXT, BOOLEAN, TEXT, JSONB) IS 'Inserts a price snapshot and automatically detects/records price changes';

-- Get deals with biggest price drops in a time period
CREATE OR REPLACE FUNCTION get_biggest_price_drops(
    p_site TEXT DEFAULT NULL,
    p_since TIMESTAMPTZ DEFAULT NOW() - INTERVAL '24 hours',
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    deal_id TEXT,
    product_id TEXT,
    site TEXT,
    old_price DECIMAL,
    new_price DECIMAL,
    drop_percent DECIMAL,
    drop_amount DECIMAL,
    change_time TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pce.deal_id,
        pce.product_id,
        pce.site,
        pce.old_price,
        pce.new_price,
        pce.price_change_percent AS drop_percent,
        (pce.old_price - pce.new_price)::DECIMAL AS drop_amount,
        pce.time AS change_time
    FROM price_change_events pce
    WHERE pce.change_type = 'drop'
        AND pce.time >= p_since
        AND (p_site IS NULL OR pce.site = p_site)
    ORDER BY ABS(pce.price_change_percent) DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_biggest_price_drops(TEXT, TIMESTAMPTZ, INTEGER) IS 'Returns deals with the biggest price drops in the given time period';

-- Get price trend for a product (increasing, decreasing, stable)
CREATE OR REPLACE FUNCTION get_price_trend(
    p_product_id TEXT,
    p_site TEXT,
    p_period TEXT DEFAULT '7 days'
)
RETURNS TABLE (
    trend TEXT,
    trend_strength DECIMAL,
    price_change_percent DECIMAL,
    start_price DECIMAL,
    end_price DECIMAL,
    data_points BIGINT
) AS $$
DECLARE
    v_start_price DECIMAL;
    v_end_price DECIMAL;
    v_data_points BIGINT;
    v_change_percent DECIMAL;
    v_trend TEXT;
    v_strength DECIMAL;
    v_slope DECIMAL;
BEGIN
    SELECT 
        FIRST(price, time),
        LAST(price, time),
        COUNT(*)
    INTO v_start_price, v_end_price, v_data_points
    FROM price_snapshots
    WHERE product_id = p_product_id 
        AND site = p_site
        AND time >= NOW() - p_period::INTERVAL;

    IF v_data_points < 2 OR v_start_price IS NULL OR v_start_price = 0 THEN
        RETURN QUERY SELECT 'insufficient_data'::TEXT, 0::DECIMAL, 0::DECIMAL, v_start_price, v_end_price, v_data_points;
        RETURN;
    END IF;

    v_change_percent := ROUND(((v_end_price - v_start_price) / v_start_price) * 100, 2);

    IF v_change_percent < -10 THEN
        v_trend := 'strongly_decreasing';
        v_strength := ABS(v_change_percent);
    ELSIF v_change_percent < -3 THEN
        v_trend := 'decreasing';
        v_strength := ABS(v_change_percent);
    ELSIF v_change_percent > 10 THEN
        v_trend := 'strongly_increasing';
        v_strength := ABS(v_change_percent);
    ELSIF v_change_percent > 3 THEN
        v_trend := 'increasing';
        v_strength := ABS(v_change_percent);
    ELSE
        v_trend := 'stable';
        v_strength := 0;
    END IF;

    RETURN QUERY SELECT v_trend, v_strength, v_change_percent, v_start_price, v_end_price, v_data_points;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION get_price_trend(TEXT, TEXT, TEXT) IS 'Analyzes price trend for a product over a given period';

-- =============================================================================
-- GRANTS
-- =============================================================================

GRANT SELECT ON price_snapshots TO anon, authenticated;
GRANT SELECT ON price_change_events TO anon, authenticated;
GRANT SELECT ON deal_metrics TO anon, authenticated;
GRANT SELECT ON daily_price_stats TO anon, authenticated;
GRANT SELECT ON hourly_price_stats TO anon, authenticated;
GRANT SELECT ON daily_price_change_summary TO anon, authenticated;

-- =============================================================================
-- SCHEMA COMPLETE
-- =============================================================================
-- Hypertables: 3 (price_snapshots, price_change_events, deal_metrics)
-- Continuous aggregates: 3 (daily_price_stats, hourly_price_stats, daily_price_change_summary)
-- Retention policies: 3
-- Compression policies: 2
-- Functions: 7
-- =============================================================================
