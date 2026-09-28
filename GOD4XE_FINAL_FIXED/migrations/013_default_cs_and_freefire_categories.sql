-- Migration 013: Default Clash Squad and Free Fire Categories & Settings Guarantee
INSERT INTO tournament_categories (name, slug, description, display_order, is_active)
VALUES 
    ('Clash Squad Ranked (CS)', 'cs-ranked', '4v4 Clash Squad Ranked and Hardcore aim matches', 1, 1),
    ('Lone Wolf (1v1 & 2v2)', 'lone-wolf', 'Intense 1v1 duels and 2v2 close-range battles', 2, 1),
    ('Battle Royale (Full Map)', 'battle-royale', 'Classic full map Bermuda, Purgatory, Kalahari matches', 3, 1),
    ('Guns Only Custom', 'guns-only', 'Custom rooms with restricted weapons and no grenades', 4, 1)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO site_settings (key, value) VALUES
    ('notify_telegram_enabled', 'false'),
    ('telegram_bot_token', ''),
    ('telegram_chat_id', ''),
    ('notify_discord_enabled', 'false'),
    ('discord_webhook_url', '')
ON CONFLICT (key) DO NOTHING;
