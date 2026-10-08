-- 016_ff_daily_redeem_codes.sql
CREATE TABLE IF NOT EXISTS ff_daily_redeem_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    reward_desc VARCHAR(255) NOT NULL DEFAULT 'Exclusive In-Game Reward / Voucher',
    server_region VARCHAR(50) NOT NULL DEFAULT 'India & Global',
    release_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expires_at TIMESTAMP NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    copy_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed active daily redeem codes
INSERT INTO ff_daily_redeem_codes (code, reward_desc, server_region, release_date, is_active, copy_count)
VALUES 
    ('FFBC-VHG9-JK89', 'Diamond Royale Voucher x2 + 50 Diamonds', 'India & Global', CURRENT_DATE, 1, 412),
    ('FF9M-J31C-XKRG', 'Dragon AK47 Skin Weapon Loot Crate', 'India Server', CURRENT_DATE, 1, 893),
    ('FFAC-2YXE-6RF2', 'Titan Scar Gun Skin Crate', 'Global (All Servers)', CURRENT_DATE, 1, 621),
    ('FFPL-NZUW-MALS', 'Gloo Wall - Cyber Power Skin', 'India Server', CURRENT_DATE, 1, 1045),
    ('FFIC-JGW9-NKYT', 'Emote: Booyah Winner Dance', 'India & Global', CURRENT_DATE, 1, 754),
    ('FF11-64XN-JZ2V', 'Weapon Royale Voucher x3', 'India Server', CURRENT_DATE, 1, 388),
    ('FF11-WFNP-P956', 'Pet Skin - Neon Beast Tig', 'Global Server', CURRENT_DATE, 1, 512),
    ('FF10-617K-GUF9', 'Universal Incubator Blueprint Voucher', 'India & Global', CURRENT_DATE, 1, 439),
    ('FF11-DAKX-4WHV', 'M1014 Green Flame Draco Crate', 'India Server', CURRENT_DATE, 1, 920),
    ('FFBB-CVQZ-4MWA', 'Free Fire MAX Exclusive Bundle Glitch Ticket', 'India & Global', CURRENT_DATE, 1, 670)
ON CONFLICT (code) DO NOTHING;
