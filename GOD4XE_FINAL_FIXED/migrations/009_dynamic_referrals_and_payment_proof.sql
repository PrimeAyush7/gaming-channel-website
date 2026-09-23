-- Migration 009: Dynamic Referral Ranks, Audit Extensions, and UPI QR Settings

-- 1. Extend referrals table for administrative invalidation & audit tracking
ALTER TABLE referrals ADD COLUMN IF NOT EXISTS invalidation_reason VARCHAR(255);
ALTER TABLE referrals ADD COLUMN IF NOT EXISTS invalidated_at TIMESTAMP;
ALTER TABLE referrals ADD COLUMN IF NOT EXISTS invalidated_by_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL;

-- Ensure indexes for high-performance referral lookups and live leaderboards
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_status ON referrals(referrer_id, status);
CREATE INDEX IF NOT EXISTS idx_referrals_referee ON referrals(referee_id);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status);

-- 2. Create referral_ranks table for centralized, admin-configurable rank thresholds
CREATE TABLE IF NOT EXISTS referral_ranks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    min_referrals INTEGER NOT NULL,
    max_referrals INTEGER, -- NULL denotes top tier with no upper limit
    display_order INTEGER NOT NULL DEFAULT 0,
    badge_color VARCHAR(30) DEFAULT '#a855f7',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed authoritative default rank tiers
INSERT INTO referral_ranks (name, min_referrals, max_referrals, display_order, badge_color, is_active)
VALUES
    ('ROOKIE', 0, 9, 1, '#94a3b8', TRUE),
    ('PRO', 10, 24, 2, '#38bdf8', TRUE),
    ('ELITE', 25, 49, 3, '#a855f7', TRUE),
    ('MASTER', 50, 99, 4, '#f59e0b', TRUE),
    ('LEGEND', 100, NULL, 5, '#ef4444', TRUE)
ON CONFLICT (name) DO NOTHING;

-- 3. Ensure site_settings contains UPI QR code storage
INSERT INTO site_settings (key, value)
VALUES ('upi_qr_image_url', '')
ON CONFLICT (key) DO NOTHING;

INSERT INTO site_settings (key, value)
VALUES ('google_client_id', '')
ON CONFLICT (key) DO NOTHING;
