-- Migration 010: Add display_name, custom avatar and custom username tracking
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_custom_avatar INTEGER DEFAULT 0;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_custom_username INTEGER DEFAULT 0;

-- Backfill display_name from app_users.username where display_name is null
UPDATE user_profiles
SET display_name = (SELECT username FROM app_users WHERE app_users.id = user_profiles.user_id)
WHERE display_name IS NULL;
