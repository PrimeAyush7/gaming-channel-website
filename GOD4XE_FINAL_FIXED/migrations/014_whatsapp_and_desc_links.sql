-- Migration 014: WhatsApp Integration & Website Description Links
INSERT INTO site_settings (key, value) VALUES
    ('notify_whatsapp_enabled', 'false'),
    ('whatsapp_webhook_url', ''),
    ('desc_link_1_title', ''),
    ('desc_link_1_url', ''),
    ('desc_link_2_title', ''),
    ('desc_link_2_url', ''),
    ('desc_link_3_title', ''),
    ('desc_link_3_url', ''),
    ('desc_link_4_title', ''),
    ('desc_link_4_url', ''),
    ('desc_link_5_title', ''),
    ('desc_link_5_url', ''),
    ('desc_link_6_title', ''),
    ('desc_link_6_url', '')
ON CONFLICT (key) DO NOTHING;
