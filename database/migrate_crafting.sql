-- Salvage / forge crafting (run once on existing DBs if not using full db.initialize_schema)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS crafting_level SMALLINT DEFAULT 1;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS crafting_xp INT DEFAULT 0;

-- Tables match database/db.py _SCHEMA + initialize_schema
