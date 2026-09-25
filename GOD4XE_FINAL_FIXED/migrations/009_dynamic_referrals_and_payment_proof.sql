-- Migration 009: Dynamic Referrals & Payment Proof
ALTER TABLE deposit_requests ADD COLUMN IF NOT EXISTS payment_proof_url TEXT;

CREATE TABLE IF NOT EXISTS referral_ranks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    min_referrals INTEGER NOT NULL,
    bonus_multiplier NUMERIC(4,2) DEFAULT 1.00,
    badge_icon VARCHAR(50) DEFAULT '🏅',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO referral_ranks (name, min_referrals, bonus_multiplier, badge_icon)
VALUES 
    ('Bronze Scout', 0, 1.00, '🥉'),
    ('Silver Vanguard', 5, 1.10, '🥈'),
    ('Gold Champion', 15, 1.25, '🥇'),
    ('Diamond Legend', 30, 1.50, '💎')
ON CONFLICT DO NOTHING;
