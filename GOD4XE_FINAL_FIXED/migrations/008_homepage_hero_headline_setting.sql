-- Migration 008: Homepage Hero Headline Setting
INSERT INTO site_settings (key, value) 
VALUES ('hero_headline', 'DOMINATE THE FREE FIRE ARENA')
ON CONFLICT (key) DO NOTHING;
