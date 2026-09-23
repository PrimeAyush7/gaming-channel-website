-- Migration 003: App Users, Profiles, and Mobile Authentication
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255),
    salt VARCHAR(255),
    google_id VARCHAR(255) UNIQUE,
    auth_provider VARCHAR(50) DEFAULT 'PASSWORD',
    referral_code VARCHAR(30) UNIQUE NOT NULL,
    referred_by_code VARCHAR(30),
    is_active INTEGER DEFAULT 1,
    is_verified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    avatar_url TEXT DEFAULT '/static/images/default-avatar.png',
    ff_uid VARCHAR(50),
    ff_ign VARCHAR(100),
    total_matches INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    kills INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    rank_tier VARCHAR(50) DEFAULT 'Bronze',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    device_info TEXT,
    ip_address VARCHAR(100),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS otp_verifications (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) NOT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    attempts INTEGER DEFAULT 0,
    is_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email);
CREATE INDEX IF NOT EXISTS idx_app_users_phone ON app_users(phone);
CREATE INDEX IF NOT EXISTS idx_app_users_google ON app_users(google_id);
CREATE INDEX IF NOT EXISTS idx_app_users_referral ON app_users(referral_code);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
