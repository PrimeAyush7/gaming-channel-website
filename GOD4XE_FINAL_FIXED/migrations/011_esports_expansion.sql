-- Migration 011: eSports Expansion - Categories, Guns, Updates, Communities, Moderation, Disputes, Tutorials, Achievements

-- 1. Tournament Categories & Subcategories
CREATE TABLE IF NOT EXISTS tournament_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    image_url TEXT,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tournament_subcategories (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES tournament_categories(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    image_url TEXT,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_id, slug)
);

-- Seed Default Categories
INSERT INTO tournament_categories (name, slug, description, image_url, display_order, is_active)
VALUES 
    ('Battle Royale', 'battle-royale', 'Classic full-map Free Fire survival combat', '/static/images/categories/battle_royale.png', 1, 1),
    ('Clash Squad', 'clash-squad', 'Intense round-based 4v4 team tactical battles', '/static/images/categories/clash_squad.png', 2, 1),
    ('Lone Wolf', 'lone-wolf', 'Pure 1v1 and 2v2 skill duels in Iron Cage', '/static/images/categories/lone_wolf.png', 3, 1),
    ('4v4 Custom', '4v4-custom', 'Custom room competitive 4v4 squad matches', '/static/images/categories/4v4_custom.png', 4, 1),
    ('Guns Only Custom', 'guns-only-custom', 'Custom tournaments locked to a specific weapon', '/static/images/categories/guns_only.png', 5, 1)
ON CONFLICT (slug) DO NOTHING;

-- Seed Subcategories for Battle Royale
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Solo', 'solo', 1 FROM tournament_categories WHERE slug = 'battle-royale'
ON CONFLICT (category_id, slug) DO NOTHING;
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Duo', 'duo', 2 FROM tournament_categories WHERE slug = 'battle-royale'
ON CONFLICT (category_id, slug) DO NOTHING;
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Squad', 'squad', 3 FROM tournament_categories WHERE slug = 'battle-royale'
ON CONFLICT (category_id, slug) DO NOTHING;

-- Seed Subcategories for Clash Squad
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Squad (4v4)', 'squad', 1 FROM tournament_categories WHERE slug = 'clash-squad'
ON CONFLICT (category_id, slug) DO NOTHING;
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Duo', 'duo', 2 FROM tournament_categories WHERE slug = 'clash-squad'
ON CONFLICT (category_id, slug) DO NOTHING;

-- Seed Subcategories for Lone Wolf
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, '1v1 Solo', '1v1', 1 FROM tournament_categories WHERE slug = 'lone-wolf'
ON CONFLICT (category_id, slug) DO NOTHING;
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, '2v2 Duo', '2v2', 2 FROM tournament_categories WHERE slug = 'lone-wolf'
ON CONFLICT (category_id, slug) DO NOTHING;

-- Seed Subcategories for 4v4 Custom
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Squad', 'squad', 1 FROM tournament_categories WHERE slug = '4v4-custom'
ON CONFLICT (category_id, slug) DO NOTHING;

-- Seed Subcategories for Guns Only
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Solo', 'solo', 1 FROM tournament_categories WHERE slug = 'guns-only-custom'
ON CONFLICT (category_id, slug) DO NOTHING;
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Duo', 'duo', 2 FROM tournament_categories WHERE slug = 'guns-only-custom'
ON CONFLICT (category_id, slug) DO NOTHING;
INSERT INTO tournament_subcategories (category_id, name, slug, display_order)
SELECT id, 'Squad', 'squad', 3 FROM tournament_categories WHERE slug = 'guns-only-custom'
ON CONFLICT (category_id, slug) DO NOTHING;

-- 2. Allowed Guns for Guns Only Tournaments
CREATE TABLE IF NOT EXISTS tournament_guns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    image_url TEXT,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tournament_guns (name, code, display_order)
VALUES 
    ('Desert Eagle Only', 'DESERT_EAGLE', 1),
    ('M1887 Only', 'M1887', 2),
    ('MP40 Only', 'MP40', 3),
    ('AWM Only', 'AWM', 4),
    ('UMP Only', 'UMP', 5),
    ('Woodpecker Only', 'WOODPECKER', 6),
    ('M1014 Only', 'M1014', 7)
ON CONFLICT (code) DO NOTHING;

-- 3. Extend Tournaments Table
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES tournament_categories(id) ON DELETE SET NULL;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS subcategory_id INTEGER REFERENCES tournament_subcategories(id) ON DELETE SET NULL;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS allowed_gun_id INTEGER REFERENCES tournament_guns(id) ON DELETE SET NULL;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS allowed_weapon VARCHAR(100);
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS per_kill_diamonds INTEGER DEFAULT 0;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS is_manually_completed INTEGER DEFAULT 0;
ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS match_proof_url TEXT;

-- 4. User Avatar Moderation
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS avatar_upload_disabled INTEGER DEFAULT 0;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS avatar_moderation_status VARCHAR(50) DEFAULT 'APPROVED';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS avatar_rejection_reason TEXT;

CREATE TABLE IF NOT EXISTS avatar_moderation_queue (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    avatar_url TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    rejection_reason TEXT,
    reviewed_by_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

-- 5. Tournament Favorites
CREATE TABLE IF NOT EXISTS tournament_favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tournament_id)
);

-- 6. Latest Updates (Home Screen Content)
CREATE TABLE IF NOT EXISTS latest_updates (
    id SERIAL PRIMARY KEY,
    heading VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    cover_image_url TEXT,
    youtube_video_url TEXT,
    button_text VARCHAR(100),
    button_url TEXT,
    display_order INTEGER DEFAULT 0,
    is_published INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO latest_updates (heading, description, button_text, button_url, display_order, is_published)
VALUES 
    ('GOD4XE Championship Season 1', 'Compete in our grand Free Fire tournament league with ₹50,000 in diamond prize pools!', 'Join Arena', '/tournaments', 1, 1),
    ('Guns Only Custom Matches Live', 'Prove your raw aim in Desert Eagle, M1887, and AWM only custom battles.', 'View Battles', '/tournaments?category=guns-only-custom', 2, 1)
ON CONFLICT DO NOTHING;

-- 7. Announcements & Arena Notice
CREATE TABLE IF NOT EXISTS announcements (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    banner_url TEXT,
    type VARCHAR(50) DEFAULT 'INFO',
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO announcements (title, message, type, is_active)
VALUES ('Season Kickoff', 'Welcome to GOD4XE eSports! Make sure your Free Fire UID and IGN are updated before matches.', 'INFO', 1)
ON CONFLICT DO NOTHING;

-- 8. Communities (Social / Official Channels)
CREATE TABLE IF NOT EXISTS communities (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    url TEXT NOT NULL,
    logo_url TEXT,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO communities (platform, name, url, display_order, is_active)
VALUES 
    ('Instagram', 'GOD4XE Official Instagram', 'https://instagram.com/god4xe', 1, 1),
    ('Discord', 'GOD4XE eSports Discord Server', 'https://discord.gg/god4xe', 2, 1),
    ('WhatsApp', 'GOD4XE Free Fire Community', 'https://chat.whatsapp.com/god4xe', 3, 1),
    ('Telegram', 'GOD4XE Official Channel', 'https://t.me/god4xe', 4, 1),
    ('YouTube', 'GOD4XE Gaming YouTube', 'https://youtube.com/@god4xe', 5, 1)
ON CONFLICT DO NOTHING;

-- 9. Tutorials / How to Play
CREATE TABLE IF NOT EXISTS tutorials (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    image_url TEXT,
    video_url TEXT,
    display_order INTEGER DEFAULT 0,
    is_published INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tutorials (title, slug, category, content, display_order, is_published)
VALUES 
    ('How to Setup Free Fire UID & IGN', 'how-to-setup-ff-uid-ign', 'PROFILE', 'Go to your Profile screen, tap Edit Profile, enter your exact in-game numeric UID and in-game name (IGN). This is required for room invitations and prize distributions.', 1, 1),
    ('How to Join a Tournament', 'how-to-join-a-tournament', 'TOURNAMENTS', 'Browse the Arena, pick your category (Battle Royale, Clash Squad, Guns Only), ensure you have enough Diamonds, tap Join, confirm your slot and credentials.', 2, 1),
    ('How Room ID and Password Works', 'how-room-id-and-password-works', 'MATCHES', 'When a tournament is scheduled, room ID and password are disclosed 15 minutes before the match start time in the Match Center. Copy them and enter in Free Fire Custom Room search.', 3, 1),
    ('How to Deposit Diamonds', 'how-to-deposit-diamonds', 'WALLET', 'In the Diamonds tab, enter the amount you wish to add, scan the official UPI QR code or pay via any UPI app, enter your 12-digit UTR reference, and upload your payment screenshot. Diamonds are credited upon admin verification.', 4, 1),
    ('How to Withdraw Winnings', 'how-to-withdraw-winnings', 'WALLET', 'Go to Diamonds -> Withdraw, enter your UPI ID, and submit. The payout request is verified and processed within 24 hours.', 5, 1),
    ('Fair Play & Anti-Cheat Rules', 'fair-play-anti-cheat-rules', 'RULES', 'Hacking, teaming in solo matches, or using modified game clients results in immediate disqualification and permanent platform ban.', 6, 1)
ON CONFLICT (slug) DO NOTHING;

-- 10. Achievements System
CREATE TABLE IF NOT EXISTS achievements (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    badge_icon VARCHAR(50) DEFAULT '🏆',
    required_metric VARCHAR(50) NOT NULL,
    threshold INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_achievements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    achievement_id INTEGER NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, achievement_id)
);

INSERT INTO achievements (code, title, description, badge_icon, required_metric, threshold)
VALUES 
    ('FIRST_TOURNAMENT', 'Rookie Combatant', 'Joined your first Free Fire tournament', '🎮', 'total_matches', 1),
    ('FIRST_WIN', 'Booyah Master', 'Won your first Free Fire match', '🏆', 'wins', 1),
    ('TEN_WINS', 'Deca Champion', 'Secured 10 Booyah victories', '🥇', 'wins', 10),
    ('HUNDRED_KILLS', 'Century Predator', 'Accumulated 100 tournament eliminations', '🎯', 'kills', 100),
    ('FIFTY_MATCHES', 'Veteran Gladiator', 'Competed in 50 tournaments', '⚔️', 'total_matches', 50)
ON CONFLICT (code) DO NOTHING;

-- 11. Tournament Disputes / Reports Table
CREATE TABLE IF NOT EXISTS tournament_disputes (
    id SERIAL PRIMARY KEY,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    dispute_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    proof_url TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    admin_response TEXT,
    resolved_by_admin_id INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Seed Default Settings
INSERT INTO site_settings (key, value)
VALUES 
    ('deposit_diamonds_per_inr', '1'),
    ('deposit_min_diamonds', '10'),
    ('deposit_multiples', '10'),
    ('withdraw_diamonds_per_inr', '0.8'),
    ('withdraw_min_diamonds', '50'),
    ('withdraw_multiples', '10'),
    ('withdrawals_enabled', 'true'),
    ('arena_notice_marquee', 'Please be ready before match starts')
ON CONFLICT (key) DO NOTHING;
