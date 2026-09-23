-- Migration 007: Starter Diamonds Bonus & Idempotency Guarantee
CREATE INDEX IF NOT EXISTS idx_diamond_tx_starter ON diamond_transactions(user_id, tx_type);
