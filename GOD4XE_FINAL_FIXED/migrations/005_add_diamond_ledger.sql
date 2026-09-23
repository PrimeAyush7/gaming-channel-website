-- Migration 005: Diamond Ledger & Financial Transactions
CREATE TABLE IF NOT EXISTS diamond_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0,
    locked_balance INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (balance >= 0),
    CHECK (locked_balance >= 0)
);

CREATE TABLE IF NOT EXISTS diamond_transactions (
    id SERIAL PRIMARY KEY,
    transaction_uuid VARCHAR(64) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    tx_type VARCHAR(50) NOT NULL,
    reference_id VARCHAR(100),
    admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deposit_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    utr_reference VARCHAR(100) UNIQUE NOT NULL,
    payment_proof_url TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    reviewed_by_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    upi_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    payout_reference VARCHAR(100),
    reviewed_by_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diamond_tx_user ON diamond_transactions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_diamond_tx_uuid ON diamond_transactions(transaction_uuid);
CREATE INDEX IF NOT EXISTS idx_deposit_requests_status ON deposit_requests(status, created_at);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status ON withdrawal_requests(status, created_at);
