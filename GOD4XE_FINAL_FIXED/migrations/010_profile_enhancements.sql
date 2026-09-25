-- Migration 010: Profile Enhancements (display_name, custom avatar and username flags)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_custom_avatar INTEGER DEFAULT 0;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_custom_username INTEGER DEFAULT 0;

UPDATE user_profiles
SET display_name = (SELECT username FROM app_users WHERE app_users.id = user_profiles.user_id)
WHERE display_name IS NULL;
