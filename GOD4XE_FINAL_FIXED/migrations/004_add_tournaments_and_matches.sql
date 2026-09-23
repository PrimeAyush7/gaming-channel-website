-- Migration 004: Tournament and Match System
CREATE TABLE IF NOT EXISTS tournaments (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    banner_url TEXT,
    description TEXT,
    game VARCHAR(100) DEFAULT 'FREE_FIRE',
    mode VARCHAR(50) DEFAULT 'SOLO',
    format VARCHAR(50) DEFAULT 'BATTLE_ROYALE',
    entry_type VARCHAR(20) NOT NULL CHECK (entry_type IN ('FREE', 'DIAMONDS')),
    entry_fee_diamonds INTEGER NOT NULL DEFAULT 0,
    prize_type VARCHAR(50) NOT NULL DEFAULT 'DIAMONDS',
    prize_amount_diamonds INTEGER NOT NULL DEFAULT 0,
    prize_distribution TEXT,
    max_slots INTEGER NOT NULL DEFAULT 48,
    joined_players INTEGER NOT NULL DEFAULT 0,
    rules TEXT,
    map_name VARCHAR(100) DEFAULT 'BERMUDA',
    room_id VARCHAR(100),
    room_password VARCHAR(100),
    room_instructions TEXT,
    start_time TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'UPCOMING',
    is_registration_open INTEGER DEFAULT 1,
    is_featured INTEGER DEFAULT 0,
    is_published INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tournament_participants (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    slot_number INTEGER NOT NULL,
    ff_uid VARCHAR(50) NOT NULL,
    ff_ign VARCHAR(100) NOT NULL,
    payment_status VARCHAR(50) DEFAULT 'PAID',
    diamonds_paid INTEGER DEFAULT 0,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tournament_id, user_id),
    UNIQUE(tournament_id, slot_number)
);

CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    match_number INTEGER DEFAULT 1,
    title VARCHAR(255),
    status VARCHAR(50) DEFAULT 'SCHEDULED',
    room_id VARCHAR(100),
    room_password VARCHAR(100),
    scheduled_time TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_results (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    ff_uid VARCHAR(50),
    ff_ign VARCHAR(100),
    placement INTEGER NOT NULL,
    kills INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    diamonds_awarded INTEGER NOT NULL DEFAULT 0,
    is_verified INTEGER DEFAULT 0,
    admin_verified_by INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, user_id)
);

CREATE TABLE IF NOT EXISTS match_disputes (
    id SERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    reporter_user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    reported_user_id INTEGER REFERENCES app_users(id) ON DELETE SET NULL,
    reason VARCHAR(100) NOT NULL,
    proof_url TEXT,
    description TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    public_notice TEXT,
    resolution_notes TEXT,
    resolved_by_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status, start_time);
CREATE INDEX IF NOT EXISTS idx_tournaments_featured ON tournaments(is_featured, is_published);
CREATE INDEX IF NOT EXISTS idx_participants_tourn ON tournament_participants(tournament_id);
CREATE INDEX IF NOT EXISTS idx_participants_user ON tournament_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_match_results_user ON match_results(user_id);
