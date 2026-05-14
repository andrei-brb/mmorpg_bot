-- Salvage / forge crafting (run once on existing DBs if not using full db.initialize_schema)
ALTER TABLE characters ADD COLUMN IF NOT EXISTS crafting_level SMALLINT DEFAULT 1;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS crafting_xp INT DEFAULT 0;

-- Tables match database/db.py _SCHEMA + initialize_schema

-- Forge Path A + unified jobs (run if initialize_schema is not used)
CREATE TABLE IF NOT EXISTS forge_rarity_rules (
    id                      VARCHAR(64) PRIMARY KEY,
    name                    VARCHAR(120) NOT NULL,
    from_rarity             item_rarity NOT NULL,
    to_rarity               item_rarity NOT NULL,
    applies_to              VARCHAR(32) NOT NULL,
    required_crafting_level SMALLINT NOT NULL DEFAULT 1,
    max_input_template_level SMALLINT,
    gold_cost               INT NOT NULL DEFAULT 0,
    costs                   JSONB NOT NULL DEFAULT '{}',
    craft_seconds           INT NOT NULL DEFAULT 10,
    success_chance          DOUBLE PRECISION NOT NULL DEFAULT 0.65
        CHECK (success_chance >= 0 AND success_chance <= 1),
    crafting_xp_reward      INT NOT NULL DEFAULT 5
);

CREATE TABLE IF NOT EXISTS forge_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    job_kind        VARCHAR(24) NOT NULL,
    success         BOOLEAN NOT NULL,
    rng_roll        DOUBLE PRECISION,
    recipe_id       VARCHAR(64),
    rarity_rule_id  VARCHAR(64),
    gold_spent      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE craft_recipes
    ADD COLUMN IF NOT EXISTS success_chance DOUBLE PRECISION DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS destroy_input_on_fail BOOLEAN DEFAULT TRUE;

ALTER TABLE craft_jobs
    ADD COLUMN IF NOT EXISTS job_kind VARCHAR(24) DEFAULT 'template_branch',
    ADD COLUMN IF NOT EXISTS rarity_rule_id VARCHAR(64) REFERENCES forge_rarity_rules(id);

UPDATE craft_jobs SET job_kind = 'template_branch' WHERE job_kind IS NULL AND recipe_id IS NOT NULL;
ALTER TABLE craft_jobs ALTER COLUMN recipe_id DROP NOT NULL;
