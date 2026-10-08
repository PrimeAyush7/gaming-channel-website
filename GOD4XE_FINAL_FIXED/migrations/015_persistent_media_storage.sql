-- Migration 015: Persistent Media Storage
-- Stores raw image binary (BYTEA) directly in PostgreSQL to ensure uploaded images
-- persist permanently across Render dyno restarts, deploys, and idle spin-downs.

ALTER TABLE media ADD COLUMN IF NOT EXISTS file_data BYTEA;
