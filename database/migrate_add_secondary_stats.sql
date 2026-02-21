-- Migration: Add secondary stats and set bonuses
-- Run this if you have an existing database

-- Add secondary stats to item_templates
ALTER TABLE item_templates 
ADD COLUMN IF NOT EXISTS s_haste SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS s_lifesteal SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS s_resistance SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS s_hit_rating SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS set_id VARCHAR(64);

-- Add secondary stats to inventory
ALTER TABLE inventory
ADD COLUMN IF NOT EXISTS r_haste SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS r_lifesteal SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS r_resistance SMALLINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS r_hit_rating SMALLINT DEFAULT 0;
