-- Migration 012: Team & Squad Registration Support
ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS team_name VARCHAR(100);
ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS team_role VARCHAR(20) DEFAULT 'CAPTAIN';
ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS teammates_json TEXT;
