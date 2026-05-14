-- =============================================================================
-- DEALHUNTER EGYPT — SUPABASE SEED DATA
-- =============================================================================
-- Purpose: Initial seed data for membership tiers, categories, and sample data
-- Run after: supabase_schema.sql
-- Idempotent: Uses DO blocks to skip if data already exists
-- =============================================================================

BEGIN;

-- =============================================================================
-- SEED: Membership Tiers
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM membership_tiers WHERE id = 'free') THEN
        INSERT INTO membership_tiers (id, name, price_egp, price_aed, price_sar, features, daily_alert_limit, max_alerts, description, sort_order, is_active)
        VALUES (
            'free', 
            'Free', 
            0, 0, 0,
            ARRAY['basic_deals', 'limited_alerts', 'browse_all', 'basic_search'],
            3,
            5,
            'Basic deal access with limited features. Browse all deals and set up to 3 daily price alerts.',
            1,
            TRUE
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM membership_tiers WHERE id = 'trial') THEN
        INSERT INTO membership_tiers (id, name, price_egp, price_aed, price_sar, features, daily_alert_limit, max_alerts, description, sort_order, is_active)
        VALUES (
            'trial', 
            '7-Day Trial', 
            0, 0, 0,
            ARRAY['unlimited_alerts', 'all_categories', 'price_history_30d', 'advanced_search', 'favorites', 'deal_verdict'],
            999,
            50,
            'Full access for 7 days after signup. Experience all premium features before committing.',
            2,
            TRUE
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM membership_tiers WHERE id = 'premium') THEN
        INSERT INTO membership_tiers (id, name, price_egp, price_aed, price_sar, features, daily_alert_limit, max_alerts, description, sort_order, is_active)
        VALUES (
            'premium', 
            'Premium', 
            49, 9, 12,
            ARRAY['unlimited_alerts', 'all_categories', 'price_history_90d', 'advanced_search', 'favorites', 'deal_verdict', 'discount_40plus', 'priority_support'],
            999,
            100,
            'Full access to all deals and features. Unlimited alerts, 90-day price history, and priority support.',
            3,
            TRUE
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM membership_tiers WHERE id = 'vip') THEN
        INSERT INTO membership_tiers (id, name, price_egp, price_aed, price_sar, features, daily_alert_limit, max_alerts, description, sort_order, is_active)
        VALUES (
            'vip', 
            'VIP', 
            99, 19, 25,
            ARRAY['early_access', 'price_charts', 'priority_support', 'exclusive_deals', 'price_history_180d', 'personal_dashboard', 'export_data', 'deal_predictions'],
            999,
            200,
            'Everything plus early access to best deals. Get 4-hour head start on hot deals before free users.',
            4,
            TRUE
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM membership_tiers WHERE id = 'elite') THEN
        INSERT INTO membership_tiers (id, name, price_egp, price_aed, price_sar, features, daily_alert_limit, max_alerts, description, sort_order, is_active)
        VALUES (
            'elite', 
            'Elite', 
            199, 39, 49,
            ARRAY['everything', 'personal_concierge', 'exclusive_deals', 'vip_support', 'price_history_unlimited', 'api_access', 'custom_alerts', 'family_sharing', 'ai_recommendations'],
            999,
            999,
            'Ultimate experience with personal service. Unlimited everything, AI recommendations, and dedicated support.',
            5,
            TRUE
        );
    END IF;
END $$;

-- =============================================================================
-- SEED: Sample Deals (for testing/demo purposes)
-- =============================================================================

DO $$
BEGIN
    -- Only insert sample deals if the table is empty
    IF NOT EXISTS (SELECT 1 FROM deals LIMIT 1) THEN
        
        -- Amazon.EG Electronics
        INSERT INTO deals (id, product_id, site, title, image_url, product_url, category, original_price, current_price, discount_percent, savings, currency, verdict, fake_score, recommendation, confidence, fraud_reasons, rating, review_count, marketplace_country, is_active, is_featured, metadata)
        VALUES 
        (
            'sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 
            'Samsung Galaxy A54 5G 128GB Awesome Black',
            'https://m.media-amazon.com/images/I/71LPr-x3YnL._AC_SL1500_.jpg',
            'https://www.amazon.eg/Samsung-Galaxy-A54-128GB-Black/dp/B08N5WRWNW',
            'electronics', 12999.00, 7499.00, 42.31, 5500.00, 'EGP',
            'GENUINE', 5.0, 'buy_now', 0.92, ARRAY[]::TEXT[], 4.4, 2847,
            'egypt', TRUE, TRUE,
            '{"brand": "Samsung", "model": "Galaxy A54", "storage": "128GB", "color": "Black"}'::JSONB
        ),
        (
            'sample_amz_002', 'B0B3FVS9KG', 'amazon_eg',
            'Xiaomi Redmi Note 12 Pro 5G 256GB Midnight Black',
            'https://m.media-amazon.com/images/I/61QRgOgBx0L._AC_SL1500_.jpg',
            'https://www.amazon.eg/Xiaomi-Redmi-Note-12-Pro/dp/B0B3FVS9KG',
            'electronics', 9999.00, 6499.00, 35.00, 3500.00, 'EGP',
            'GENUINE', 8.0, 'buy_now', 0.88, ARRAY[]::TEXT[], 4.3, 1523,
            'egypt', TRUE, TRUE,
            '{"brand": "Xiaomi", "model": "Redmi Note 12 Pro", "storage": "256GB", "color": "Black"}'::JSONB
        ),
        (
            'sample_amz_003', 'B09V3KXJPB', 'amazon_eg',
            'Apple iPhone 14 128GB Midnight',
            'https://m.media-amazon.com/images/I/61bK6PMOC3L._AC_SL1500_.jpg',
            'https://www.amazon.eg/Apple-iPhone-14-128GB-Midnight/dp/B09V3KXJPB',
            'electronics', 36999.00, 28999.00, 21.62, 8000.00, 'EGP',
            'GENUINE', 3.0, 'normal', 0.85, ARRAY[]::TEXT[], 4.6, 5129,
            'egypt', TRUE, FALSE,
            '{"brand": "Apple", "model": "iPhone 14", "storage": "128GB", "color": "Midnight"}'::JSONB
        );

        -- Noon.EG Fashion
        INSERT INTO deals (id, product_id, site, title, image_url, product_url, category, original_price, current_price, discount_percent, savings, currency, verdict, fake_score, recommendation, confidence, fraud_reasons, rating, review_count, marketplace_country, is_active, is_featured, metadata)
        VALUES
        (
            'sample_noon_001', 'N35932947A', 'noon_eg',
            'Nike Air Force 1 ''07 Men White Sneakers',
            'https://f.nooncdn.com/products/tr:n-t_240/v1668529826/N35932947A_1.jpg',
            'https://www.noon.com/egypt-en/nike-air-force-1-07-men-white-sneakers/N35932947A/p/',
            'fashion', 3899.00, 2299.00, 40.98, 1600.00, 'EGP',
            'GENUINE', 4.0, 'buy_now', 0.90, ARRAY[]::TEXT[], 4.5, 892,
            'egypt', TRUE, TRUE,
            '{"brand": "Nike", "model": "Air Force 1", "gender": "men", "color": "White"}'::JSONB
        ),
        (
            'sample_noon_002', 'N43287654A', 'noon_eg',
            'Adidas Ultraboost 22 Men Running Shoes Black',
            'https://f.nooncdn.com/products/tr:n-t_240/v1672345678/N43287654A_1.jpg',
            'https://www.noon.com/egypt-en/adidas-ultraboost-22-men-running-shoes-black/N43287654A/p/',
            'fashion', 5499.00, 3299.00, 40.01, 2200.00, 'EGP',
            'SUSPICIOUS', 45.0, 'wait', 0.55, ARRAY['price_volatility_high', 'recent_price_increase_before_discount'],
            4.3, 445,
            'egypt', TRUE, FALSE,
            '{"brand": "Adidas", "model": "Ultraboost 22", "gender": "men", "color": "Black"}'::JSONB
        );

        -- Jumia.EG Home
        INSERT INTO deals (id, product_id, site, title, image_url, product_url, category, original_price, current_price, discount_percent, savings, currency, verdict, fake_score, recommendation, confidence, fraud_reasons, rating, review_count, marketplace_country, is_active, is_featured, metadata)
        VALUES
        (
            'sample_jum_001', 'GE810HA0AABCDEF', 'jumia_eg',
            'Tornado Automatic Vacuum Cleaner 2000W Black - TVC-2000',
            'https://eg.jumia.is/unsafe/fit-in/500x500/filters:fill(white)/product/81/012345/1.jpg',
            'https://www.jumia.com.eg/tornado-automatic-vacuum-cleaner-2000w-black-tvc-2000-GE810HA0AABCDEF.html',
            'home', 2499.00, 1399.00, 44.02, 1100.00, 'EGP',
            'GENUINE', 2.0, 'buy_now', 0.95, ARRAY[]::TEXT[], 4.2, 2134,
            'egypt', TRUE, TRUE,
            '{"brand": "Tornado", "model": "TVC-2000", "power": "2000W", "color": "Black", "type": "vacuum_cleaner"}'::JSONB
        ),
        (
            'sample_jum_002', 'GE810EL0XYZ1234', 'jumia_eg',
            'Fresh Electric Kettle 1.7L 1850-2200W - FK-1718',
            'https://eg.jumia.is/unsafe/fit-in/500x500/filters:fill(white)/product/81/098765/1.jpg',
            'https://www.jumia.com.eg/fresh-electric-kettle-1.7l-1850-2200w-fk-1718-GE810EL0XYZ1234.html',
            'home', 899.00, 449.00, 50.06, 450.00, 'EGP',
            'FAKE', 78.0, 'avoid', 0.82, ARRAY['inflated_original_price', 'no_price_history', 'seller_reputation_low'],
            3.1, 89,
            'egypt', TRUE, FALSE,
            '{"brand": "Fresh", "model": "FK-1718", "capacity": "1.7L", "power": "1850-2200W", "type": "electric_kettle"}'::JSONB
        );

        -- Amazon.AE (UAE) Electronics
        INSERT INTO deals (id, product_id, site, title, image_url, product_url, category, original_price, current_price, discount_percent, savings, currency, verdict, fake_score, recommendation, confidence, fraud_reasons, rating, review_count, marketplace_country, is_active, is_featured, metadata)
        VALUES
        (
            'sample_amzae_001', 'B0CJX2Z1GL', 'amazon_ae',
            'Sony WH-1000XM5 Wireless Noise Cancelling Headphones Black',
            'https://m.media-amazon.com/images/I/61+btxzpfDL._AC_SL1500_.jpg',
            'https://www.amazon.ae/Sony-WH-1000XM5-Wireless-Cancelling-Headphones/dp/B0CJX2Z1GL',
            'electronics', 1499.00, 899.00, 40.03, 600.00, 'AED',
            'GENUINE', 6.0, 'buy_now', 0.89, ARRAY[]::TEXT[], 4.5, 3421,
            'uae', TRUE, TRUE,
            '{"brand": "Sony", "model": "WH-1000XM5", "color": "Black", "type": "headphones"}'::JSONB
        );

        -- Noon.SA (Saudi) Sports
        INSERT INTO deals (id, product_id, site, title, image_url, product_url, category, original_price, current_price, discount_percent, savings, currency, verdict, fake_score, recommendation, confidence, fraud_reasons, rating, review_count, marketplace_country, is_active, is_featured, metadata)
        VALUES
        (
            'sample_noonsa_001', 'N52345678A', 'noon_sa',
            'Yoga Mat Non-Slip 6mm Thick with Carrying Strap - Purple',
            'https://f.nooncdn.com/products/tr:n-t_240/v1682345678/N52345678A_1.jpg',
            'https://www.noon.com/saudi-en/yoga-mat-non-slip-6mm-thick-with-carrying-strap-purple/N52345678A/p/',
            'sports', 189.00, 79.00, 58.20, 110.00, 'SAR',
            'GENUINE', 10.0, 'buy_now', 0.91, ARRAY[]::TEXT[], 4.4, 567,
            'saudi', TRUE, TRUE,
            '{"brand": "Generic", "thickness": "6mm", "color": "Purple", "type": "yoga_mat"}'::JSONB
        );

    END IF;
END $$;

-- =============================================================================
-- SEED: Sample Users (for testing)
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE email = 'demo@dealhunter.app') THEN
        INSERT INTO users (id, firebase_uid, email, display_name, tier, device_platform, country, is_active, created_at)
        VALUES 
        (
            'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
            'firebase_demo_001',
            'demo@dealhunter.app',
            'Demo User',
            'premium',
            'android',
            'egypt',
            TRUE,
            NOW() - INTERVAL '30 days'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM users WHERE email = 'test@dealhunter.app') THEN
        INSERT INTO users (id, firebase_uid, email, display_name, tier, device_platform, country, is_active, created_at)
        VALUES 
        (
            'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12',
            'firebase_demo_002',
            'test@dealhunter.app',
            'Test User',
            'trial',
            'ios',
            'uae',
            TRUE,
            NOW() - INTERVAL '2 days'
        );
    END IF;
END $$;

-- =============================================================================
-- SEED: Sample Devices
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM devices WHERE id = 'fcm_demo_001_token_prefix_sample_xyz123456789') THEN
        INSERT INTO devices (id, fcm_token, device_id, device_model, platform, user_id, tier, country, is_active, registered_at, last_active)
        VALUES 
        (
            'fcm_demo_001_token_prefix_sample_xyz123456789',
            'fcm_demo_001_token_prefix_sample_xyz123456789abcdefghijklmnopqrs',
            'device_android_demo_001',
            'Samsung Galaxy S23',
            'android',
            'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
            'premium',
            'egypt',
            TRUE,
            NOW() - INTERVAL '30 days',
            NOW() - INTERVAL '2 hours'
        );
    END IF;
END $$;

-- =============================================================================
-- SEED: Sample Favorites
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM user_favorites WHERE user_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11') THEN
        INSERT INTO user_favorites (user_id, deal_id, favorited_at)
        VALUES 
        ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'sample_amz_001', NOW() - INTERVAL '5 days'),
        ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'sample_noon_001', NOW() - INTERVAL '3 days'),
        ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'sample_jum_001', NOW() - INTERVAL '1 day');
    END IF;
END $$;

-- =============================================================================
-- SEED: Sample Alert Rules
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM alert_rules WHERE user_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11') THEN
        INSERT INTO alert_rules (user_id, product_id, site, alert_type, target_price, discount_threshold, is_active, created_at)
        VALUES 
        (
            'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
            'B08N5WRWNW',
            'amazon_eg',
            'target_price',
            6999.00,
            5.0,
            TRUE,
            NOW() - INTERVAL '7 days'
        ),
        (
            'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
            'N35932947A',
            'noon_eg',
            'price_drop',
            NULL,
            15.0,
            TRUE,
            NOW() - INTERVAL '5 days'
        );
    END IF;
END $$;

-- =============================================================================
-- SEED: Sample Price History (Lightweight — full history goes to TimescaleDB)
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM deal_price_history LIMIT 1) THEN
        INSERT INTO deal_price_history (deal_id, product_id, site, price, original_price, discount_percent, currency, recorded_at)
        VALUES
        -- Samsung Galaxy A54 history
        ('sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 12999.00, 12999.00, 0, 'EGP', NOW() - INTERVAL '30 days'),
        ('sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 11999.00, 12999.00, 7.69, 'EGP', NOW() - INTERVAL '20 days'),
        ('sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 10999.00, 12999.00, 15.39, 'EGP', NOW() - INTERVAL '15 days'),
        ('sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 9499.00, 12999.00, 26.93, 'EGP', NOW() - INTERVAL '10 days'),
        ('sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 8499.00, 12999.00, 34.62, 'EGP', NOW() - INTERVAL '5 days'),
        ('sample_amz_001', 'B08N5WRWNW', 'amazon_eg', 7499.00, 12999.00, 42.31, 'EGP', NOW() - INTERVAL '1 day'),

        -- Nike Air Force history
        ('sample_noon_001', 'N35932947A', 'noon_eg', 3899.00, 3899.00, 0, 'EGP', NOW() - INTERVAL '25 days'),
        ('sample_noon_001', 'N35932947A', 'noon_eg', 3499.00, 3899.00, 10.26, 'EGP', NOW() - INTERVAL '18 days'),
        ('sample_noon_001', 'N35932947A', 'noon_eg', 2999.00, 3899.00, 23.08, 'EGP', NOW() - INTERVAL '12 days'),
        ('sample_noon_001', 'N35932947A', 'noon_eg', 2699.00, 3899.00, 30.78, 'EGP', NOW() - INTERVAL '7 days'),
        ('sample_noon_001', 'N35932947A', 'noon_eg', 2299.00, 3899.00, 40.98, 'EGP', NOW() - INTERVAL '2 days'),

        -- Suspicious Adidas deal history (shows price manipulation)
        ('sample_noon_002', 'N43287654A', 'noon_eg', 4299.00, 4299.00, 0, 'EGP', NOW() - INTERVAL '20 days'),
        ('sample_noon_002', 'N43287654A', 'noon_eg', 3999.00, 4299.00, 6.98, 'EGP', NOW() - INTERVAL '15 days'),
        ('sample_noon_002', 'N43287654A', 'noon_eg', 5499.00, 5499.00, 0, 'EGP', NOW() - INTERVAL '10 days'),  -- Price hike!
        ('sample_noon_002', 'N43287654A', 'noon_eg', 5499.00, 7499.00, 26.68, 'EGP', NOW() - INTERVAL '7 days'),  -- Fake original price
        ('sample_noon_002', 'N43287654A', 'noon_eg', 3299.00, 5499.00, 40.01, 'EGP', NOW() - INTERVAL '3 days'),

        -- Fake Fresh Kettle history (shows manipulation pattern)
        ('sample_jum_002', 'GE810EL0XYZ1234', 'jumia_eg', 599.00, 599.00, 0, 'EGP', NOW() - INTERVAL '21 days'),
        ('sample_jum_002', 'GE810EL0XYZ1234', 'jumia_eg', 549.00, 599.00, 8.35, 'EGP', NOW() - INTERVAL '14 days'),
        ('sample_jum_002', 'GE810EL0XYZ1234', 'jumia_eg', 899.00, 1999.00, 55.03, 'EGP', NOW() - INTERVAL '10 days'),  -- Huge fake discount
        ('sample_jum_002', 'GE810EL0XYZ1234', 'jumia_eg', 899.00, 1799.00, 50.03, 'EGP', NOW() - INTERVAL '7 days'),
        ('sample_jum_002', 'GE810EL0XYZ1234', 'jumia_eg', 449.00, 899.00, 50.06, 'EGP', NOW() - INTERVAL '2 days');
    END IF;
END $$;

-- =============================================================================
-- SEED COMPLETE
-- =============================================================================
-- Membership tiers: 5
-- Sample deals: 8 (across 5 sites, 5 categories)
-- Sample users: 2
-- Sample devices: 1
-- Sample favorites: 3
-- Sample alerts: 2
-- Sample price history: 16 records
-- =============================================================================

COMMIT;
