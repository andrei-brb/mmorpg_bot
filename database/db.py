"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               database/db.py — Async PostgreSQL Pool + Schema              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from typing import Any, List, Optional

import asyncpg

log = logging.getLogger("database")


async def _merge_stackable_inventory_rows(conn: asyncpg.Connection) -> None:
    """Merge duplicate inventory rows for stackable consumables/materials (post max_stack migration)."""
    try:
        rows = await conn.fetch(
            """
            SELECT i.character_id,
                   i.template_id,
                   COALESCE(i.rarity, t.rarity) AS eff_rarity,
                   t.max_stack,
                   array_agg(i.id ORDER BY i.obtained_at NULLS FIRST) AS ids,
                   SUM(i.quantity)::bigint AS total_qty
            FROM inventory i
            JOIN item_templates t ON t.id = i.template_id
            WHERE t.item_type IN ('consumable', 'material')
              AND t.equip_slot IS NULL
              AND t.max_stack > 1
            GROUP BY i.character_id, i.template_id, COALESCE(i.rarity, t.rarity), t.max_stack
            HAVING COUNT(*) > 1
            """
        )
        for r in rows:
            ids = list(r["ids"])
            total = int(r["total_qty"])
            max_stack = int(r["max_stack"] or 99)
            if max_stack <= 0:
                max_stack = 99
            remaining = total
            for oid in ids:
                if remaining <= 0:
                    await conn.execute("DELETE FROM inventory WHERE id=$1", oid)
                    continue
                q = min(remaining, max_stack)
                await conn.execute("UPDATE inventory SET quantity=$1 WHERE id=$2", q, oid)
                remaining -= q
            while remaining > 0:
                chunk = min(remaining, max_stack)
                await conn.execute(
                    """
                    INSERT INTO inventory (
                        character_id, template_id, quantity, durability,
                        r_str, r_agi, r_int, r_spi, r_sta,
                        r_haste, r_lifesteal, r_resistance, r_hit_rating,
                        is_equipped, equip_slot, enhancement_level, locked, obtained_from, rarity
                    )
                    SELECT character_id, template_id, $1::smallint, durability,
                        r_str, r_agi, r_int, r_spi, r_sta,
                        r_haste, r_lifesteal, r_resistance, r_hit_rating,
                        FALSE, NULL, COALESCE(enhancement_level, 0), locked, obtained_from, rarity
                    FROM inventory WHERE id=$2
                    """,
                    chunk,
                    ids[0],
                )
                remaining -= chunk
        if rows:
            log.info("Merged %s stackable inventory groups (duplicate rows combined).", len(rows))
    except Exception as e:
        log.warning("Stackable inventory merge skipped: %s", e)


class Database:
    """Thin wrapper around asyncpg pool with convenience methods."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.dsn, min_size=5, max_size=20, command_timeout=30
        )
        log.info("Database pool ready (min=5, max=20).")

    async def close(self):
        if self.pool:
            await self.pool.close()

    # ── Query helpers ─────────────────────────────────────────────────────────

    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        async with self.pool.acquire() as c:
            return await c.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        async with self.pool.acquire() as c:
            return await c.fetchrow(query, *args)

    async def fetchval(self, query: str, *args) -> Any:
        async with self.pool.acquire() as c:
            return await c.fetchval(query, *args)

    async def execute(self, query: str, *args) -> str:
        async with self.pool.acquire() as c:
            return await c.execute(query, *args)

    async def executemany(self, query: str, args_list: list) -> None:
        async with self.pool.acquire() as c:
            await c.executemany(query, args_list)

    # ── Schema ────────────────────────────────────────────────────────────────

    async def initialize_schema(self):
        async with self.pool.acquire() as c:
            # Run main schema
            await c.execute(_SCHEMA)
            
            # Add secondary stats columns if they don't exist (migration)
            await c.execute("""
                ALTER TABLE item_templates 
                ADD COLUMN IF NOT EXISTS s_haste SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS s_lifesteal SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS s_resistance SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS s_hit_rating SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS set_id VARCHAR(64);
            """)
            
            await c.execute("""
                ALTER TABLE inventory
                ADD COLUMN IF NOT EXISTS r_haste SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS r_lifesteal SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS r_resistance SMALLINT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS r_hit_rating SMALLINT DEFAULT 0;
            """)
            
            # Add pending_encounter for boss encounters from explore
            await c.execute("""
                ALTER TABLE characters
                ADD COLUMN IF NOT EXISTS pending_encounter VARCHAR(64);
            """)

            # Ensure only one active character per player (older installs may have multiple TRUE rows).
            # Keep the newest active and deactivate the rest.
            try:
                await c.execute("""
                    WITH ranked AS (
                        SELECT id,
                               player_id,
                               ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY created_at DESC) AS rn
                        FROM characters
                        WHERE is_active = TRUE
                    )
                    UPDATE characters c
                    SET is_active = FALSE
                    FROM ranked r
                    WHERE c.id = r.id AND r.rn > 1;
                """)
            except Exception as e:
                log.warning(f"Active character cleanup skipped: {e}")

            # Add uniqueness constraint if it wasn't present on older schemas.
            try:
                await c.execute("""
                    ALTER TABLE characters
                    ADD CONSTRAINT one_active_char UNIQUE (player_id, is_active);
                """)
            except Exception:
                # Constraint already exists or cannot be added (should be fine after cleanup).
                pass
            
            # Add rarity column to inventory (stores actual item rarity, not template rarity)
            await c.execute("""
                ALTER TABLE inventory
                ADD COLUMN IF NOT EXISTS rarity item_rarity;
            """)
            
            # Add enhancement_level to inventory
            await c.execute("""
                ALTER TABLE inventory
                ADD COLUMN IF NOT EXISTS enhancement_level SMALLINT DEFAULT 0 CHECK (enhancement_level BETWEEN 0 AND 10);
            """)
            
            # Add last_blessing_claim to characters
            await c.execute("""
                ALTER TABLE characters
                ADD COLUMN IF NOT EXISTS last_blessing_claim TIMESTAMPTZ;
            """)

            # Idle/offline reward accrual anchor (defaults to now so first deploy has no retro catch-up)
            await c.execute("""
                ALTER TABLE characters
                ADD COLUMN IF NOT EXISTS idle_last_claim_at TIMESTAMPTZ DEFAULT NOW();
            """)

            await c.execute("""
                ALTER TABLE characters
                ADD COLUMN IF NOT EXISTS crafting_level SMALLINT DEFAULT 1;
            """)
            await c.execute("""
                ALTER TABLE characters
                ADD COLUMN IF NOT EXISTS crafting_xp INT DEFAULT 0;
            """)

            # Crafting tables (older installs may predate _SCHEMA embed)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS craft_recipes (
                    id                      VARCHAR(64) PRIMARY KEY,
                    name                    VARCHAR(120) NOT NULL,
                    description             TEXT,
                    input_template_id       VARCHAR(64) NOT NULL REFERENCES item_templates(id),
                    output_template_id      VARCHAR(64) NOT NULL REFERENCES item_templates(id),
                    craft_seconds           INT NOT NULL DEFAULT 10,
                    required_crafting_level SMALLINT NOT NULL DEFAULT 1,
                    gold_cost               INT NOT NULL DEFAULT 0,
                    costs                   JSONB NOT NULL DEFAULT '{}',
                    crafting_xp_reward      INT NOT NULL DEFAULT 5
                );
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS craft_jobs (
                    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    character_id            UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    recipe_id               VARCHAR(64) NOT NULL REFERENCES craft_recipes(id),
                    payload                 JSONB NOT NULL DEFAULT '{}',
                    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completes_at            TIMESTAMPTZ NOT NULL,
                    status                  VARCHAR(16) NOT NULL DEFAULT 'active'
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_craft_recipes_input ON craft_recipes(input_template_id);
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_craft_jobs_char ON craft_jobs(character_id, status);
            """)
            await c.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_craft_jobs_one_inflight
                ON craft_jobs(character_id) WHERE (status IN ('active', 'ready'));
            """)

            # Seed / upsert forge recipes (idempotent)
            await c.execute("""
                INSERT INTO craft_recipes
                    (id, name, description, input_template_id, output_template_id, craft_seconds, required_crafting_level, gold_cost, costs, crafting_xp_reward)
                VALUES
                    ('upgrade_iron_to_steel_sword', 'Refined blade', 'Upgrade Iron Sword into a Steel Sword.', 'iron_sword', 'steel_sword', 5, 1, 50, '{"weapon_scrap": 3}'::jsonb, 15),
                    ('upgrade_leather_to_chain_coif', 'Reinforced hood', 'Upgrade Leather Cap into a Chain Coif.', 'leather_cap', 'chain_coif', 8, 1, 80, '{"armor_scrap": 4}'::jsonb, 20),
                    ('upgrade_bone_club_to_dwarven_axe', 'Ironforge pattern', 'Upgrade Bone Club into a Dwarven Axe.', 'bone_club', 'dwarven_axe', 30, 2, 200, '{"weapon_scrap": 6}'::jsonb, 35),
                    ('upgrade_raptor_to_jungle_chest', 'Stranglethorn weave', 'Upgrade Raptor Hide Vest into Jungle Leather Chest.', 'raptor_hide_vest', 'jungle_leather_chest', 45, 3, 350, '{"armor_scrap": 8}'::jsonb, 50),
                    ('upgrade_bracelet_t1_to_t2', 'Better wristwrap', 'Upgrade Woven Bracelet to a Carved Bracelet.', 'bracelet_t1', 'bracelet_t2', 6, 1, 60, '{"accessory_scrap": 3}'::jsonb, 12)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    input_template_id = EXCLUDED.input_template_id,
                    output_template_id = EXCLUDED.output_template_id,
                    craft_seconds = EXCLUDED.craft_seconds,
                    required_crafting_level = EXCLUDED.required_crafting_level,
                    gold_cost = EXCLUDED.gold_cost,
                    costs = EXCLUDED.costs,
                    crafting_xp_reward = EXCLUDED.crafting_xp_reward;
            """)

            # ── Forge: rarity rules, branch recipe columns, unified jobs, forge log ──
            await c.execute("""
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
            """)
            await c.execute("""
                INSERT INTO forge_rarity_rules
                    (id, name, from_rarity, to_rarity, applies_to, required_crafting_level,
                     max_input_template_level, gold_cost, costs, craft_seconds, success_chance, crafting_xp_reward)
                VALUES
                    ('forge_rarity_common_uncommon', 'Temper the metal',
                     'common', 'uncommon', 'all_equipment', 1, 35, 40,
                     '{"weapon_scrap": 2, "armor_scrap": 2, "accessory_scrap": 1}'::jsonb, 8, 0.68, 6),
                    ('forge_rarity_uncommon_rare', 'Draw out the gleam',
                     'uncommon', 'rare', 'all_equipment', 3, 35, 90,
                     '{"weapon_scrap": 4, "armor_scrap": 4, "accessory_scrap": 2}'::jsonb, 14, 0.55, 12)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    from_rarity = EXCLUDED.from_rarity,
                    to_rarity = EXCLUDED.to_rarity,
                    applies_to = EXCLUDED.applies_to,
                    required_crafting_level = EXCLUDED.required_crafting_level,
                    max_input_template_level = EXCLUDED.max_input_template_level,
                    gold_cost = EXCLUDED.gold_cost,
                    costs = EXCLUDED.costs,
                    craft_seconds = EXCLUDED.craft_seconds,
                    success_chance = EXCLUDED.success_chance,
                    crafting_xp_reward = EXCLUDED.crafting_xp_reward;
            """)
            await c.execute("""
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
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_forge_log_char ON forge_log(character_id, created_at DESC);
            """)
            await c.execute("""
                ALTER TABLE craft_recipes
                ADD COLUMN IF NOT EXISTS success_chance DOUBLE PRECISION DEFAULT 1.0,
                ADD COLUMN IF NOT EXISTS destroy_input_on_fail BOOLEAN DEFAULT TRUE;
            """)
            await c.execute("""
                UPDATE craft_recipes SET success_chance = 0.72, destroy_input_on_fail = TRUE
                WHERE id LIKE 'upgrade_%' AND (success_chance IS NULL OR success_chance >= 0.999);
            """)
            await c.execute("""
                ALTER TABLE craft_jobs
                ADD COLUMN IF NOT EXISTS job_kind VARCHAR(24) DEFAULT 'template_branch';
            """)
            await c.execute("""
                ALTER TABLE craft_jobs
                ADD COLUMN IF NOT EXISTS rarity_rule_id VARCHAR(64) REFERENCES forge_rarity_rules(id);
            """)
            await c.execute("""
                UPDATE craft_jobs SET job_kind = 'template_branch'
                WHERE job_kind IS NULL AND recipe_id IS NOT NULL;
            """)
            await c.execute("""
                ALTER TABLE craft_jobs ALTER COLUMN recipe_id DROP NOT NULL;
            """)
            try:
                await c.execute("""
                    ALTER TABLE craft_jobs ADD CONSTRAINT craft_jobs_forge_kind_chk CHECK (
                        (COALESCE(job_kind, 'template_branch') = 'template_branch'
                         AND recipe_id IS NOT NULL AND rarity_rule_id IS NULL)
                        OR (job_kind = 'rarity_forge' AND recipe_id IS NULL AND rarity_rule_id IS NOT NULL)
                    );
                """)
            except Exception as e:
                log.warning("craft_jobs_forge_kind_chk: %s", e)
            
            # Create enhancement_log table
            await c.execute("""
                CREATE TABLE IF NOT EXISTS enhancement_log (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    item_id         UUID,
                    item_name       VARCHAR(100) NOT NULL,
                    from_level      SMALLINT NOT NULL,
                    to_level        SMALLINT NOT NULL,
                    success         BOOLEAN NOT NULL,
                    gold_spent      INT NOT NULL,
                    protection_used VARCHAR(32),
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_enhancement_char 
                ON enhancement_log(character_id, created_at DESC);
            """)

            # ── NPC Quest System tables ──────────────────────────────────
            await c.execute("""
                CREATE TABLE IF NOT EXISTS npc_discoveries (
                    character_id    UUID REFERENCES characters(id) ON DELETE CASCADE,
                    npc_id          VARCHAR(64) NOT NULL,
                    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
                    state           VARCHAR(32) DEFAULT 'discovered',
                    zone_found      VARCHAR(64),
                    PRIMARY KEY (character_id, npc_id)
                );
            """)

            # Lore / Obsidian Silence deed flags (per character)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS character_deed_flags (
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    flag_key        VARCHAR(128) NOT NULL,
                    granted_at      TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (character_id, flag_key)
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_deed_flags_char
                ON character_deed_flags(character_id);
            """)

            await c.execute("""
                CREATE TABLE IF NOT EXISTS quest_progress (
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    quest_id        VARCHAR(64) NOT NULL,
                    npc_id          VARCHAR(64) NOT NULL,
                    current_step    INT DEFAULT 1,
                    state           VARCHAR(32) DEFAULT 'active',
                    started_at      TIMESTAMPTZ DEFAULT NOW(),
                    completed_at    TIMESTAMPTZ,
                    expires_at      TIMESTAMPTZ,
                    metadata        JSONB DEFAULT '{}',
                    PRIMARY KEY (character_id, quest_id)
                );
            """)

            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_quest_progress_char
                ON quest_progress(character_id, state);
            """)

            # Add expires_at column to existing quest_progress (migration)
            await c.execute("""
                ALTER TABLE quest_progress
                ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
            """)

            # ── Faction Reputation table ─────────────────────────────────
            await c.execute("""
                CREATE TABLE IF NOT EXISTS faction_reputation (
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    faction_id      VARCHAR(64) NOT NULL,
                    reputation      INT DEFAULT 0,
                    updated_at      TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (character_id, faction_id)
                );
            """)

            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_faction_rep_char
                ON faction_reputation(character_id);
            """)

            # ── Server Milestones v1 ──────────────────────────────────────
            await c.execute("""
                CREATE TABLE IF NOT EXISTS server_milestones (
                    guild_id        BIGINT NOT NULL,
                    key             VARCHAR(64) NOT NULL,
                    value           BIGINT DEFAULT 0,
                    tier_reached    SMALLINT DEFAULT 0,
                    updated_at      TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (guild_id, key)
                );
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS server_buffs (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id        BIGINT NOT NULL,
                    buff_type       VARCHAR(32) NOT NULL,   -- xp_multiplier | gold_multiplier
                    buff_value      DOUBLE PRECISION NOT NULL,
                    source_key      VARCHAR(64),
                    created_at      TIMESTAMPTZ DEFAULT NOW(),
                    expires_at      TIMESTAMPTZ NOT NULL
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_server_buffs_active
                ON server_buffs(guild_id, expires_at DESC);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS milestone_log (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id        BIGINT NOT NULL,
                    key             VARCHAR(64) NOT NULL,
                    amount          BIGINT NOT NULL,
                    before_value    BIGINT NOT NULL,
                    after_value     BIGINT NOT NULL,
                    source          VARCHAR(64) DEFAULT 'system',
                    actor_id        BIGINT,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_milestone_log_guild_created
                ON milestone_log(guild_id, created_at DESC);
            """)

            # ── Per-guild configurable live ops (scheduled XP/gold/boss hunt, etc.) ──
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_live_events (
                    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id                BIGINT NOT NULL,
                    slug                    VARCHAR(64) NOT NULL,
                    title                   VARCHAR(256) NOT NULL,
                    description             TEXT DEFAULT '',
                    config                  JSONB NOT NULL DEFAULT '{}',
                    starts_at               TIMESTAMPTZ NOT NULL,
                    ends_at                 TIMESTAMPTZ NOT NULL,
                    enabled                 BOOLEAN DEFAULT TRUE,
                    announce_on_start       BOOLEAN DEFAULT TRUE,
                    announce_on_end         BOOLEAN DEFAULT FALSE,
                    announce_channel_id     BIGINT,
                    announce_start_sent     BOOLEAN DEFAULT FALSE,
                    announce_end_sent       BOOLEAN DEFAULT FALSE,
                    created_at              TIMESTAMPTZ DEFAULT NOW(),
                    created_by              BIGINT,
                    UNIQUE (guild_id, slug)
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_live_events_window
                ON guild_live_events(guild_id, starts_at, ends_at);
            """)

            # Discord server context (Activity / slash commands) for guild-scoped world boss presence
            await c.execute("""
                ALTER TABLE characters
                ADD COLUMN IF NOT EXISTS last_discord_guild_id BIGINT;
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_char_discord_guild_zone
                ON characters(last_discord_guild_id, current_zone)
                WHERE is_active = TRUE AND last_discord_guild_id IS NOT NULL;
            """)

            # Scheduled lore/world boss windows per Discord guild
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_world_boss_windows (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id        BIGINT NOT NULL,
                    trigger_slug    VARCHAR(64) NOT NULL,
                    zone_key        VARCHAR(64) NOT NULL,
                    boss_key        VARCHAR(64) NOT NULL,
                    starts_at       TIMESTAMPTZ NOT NULL,
                    ends_at         TIMESTAMPTZ NOT NULL,
                    trigger_kind    VARCHAR(32) NOT NULL,
                    trigger_detail  JSONB NOT NULL DEFAULT '{}',
                    announce_sent   BOOLEAN DEFAULT FALSE,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_world_boss_windows_guild_active
                ON guild_world_boss_windows(guild_id, ends_at DESC);
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_world_boss_windows_zone_active
                ON guild_world_boss_windows(zone_key, ends_at DESC);
            """)

            # ── Activity PvP (Arena) ─────────────────────────────────────────────
            await c.execute("""
                CREATE TABLE IF NOT EXISTS pvp_stats (
                    character_id    UUID PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
                    rating          INT NOT NULL DEFAULT 1500,
                    wins            INT NOT NULL DEFAULT 0,
                    losses          INT NOT NULL DEFAULT 0,
                    draws           INT NOT NULL DEFAULT 0,
                    streak          INT NOT NULL DEFAULT 0,
                    updated_at      TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS pvp_match_history (
                    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    character_id            UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    opponent_character_id   UUID REFERENCES characters(id) ON DELETE SET NULL,
                    opponent_name           VARCHAR(100),
                    mode                    VARCHAR(16) NOT NULL,
                    result                  VARCHAR(16) NOT NULL,
                    rating_delta            INT,
                    damage_dealt            INT DEFAULT 0,
                    damage_taken            INT DEFAULT 0,
                    crits                   INT DEFAULT 0,
                    duration_seconds        INT DEFAULT 0,
                    created_at              TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_pvp_history_char
                ON pvp_match_history(character_id, created_at DESC);
            """)

            # ── In-game guild hub (UUID guilds) — bank, feed, boss, tech, raids ──
            await c.execute("""
                ALTER TABLE guilds
                ADD COLUMN IF NOT EXISTS announce_channel_id BIGINT;
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_bank_ledger (
                    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id            UUID NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                    character_id        UUID REFERENCES characters(id) ON DELETE SET NULL,
                    delta               BIGINT NOT NULL,
                    reason              VARCHAR(32) NOT NULL,
                    meta                JSONB NOT NULL DEFAULT '{}',
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_bank_ledger_guild
                ON guild_bank_ledger(guild_id, created_at DESC);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_feed_messages (
                    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id                UUID NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                    author_character_id     UUID REFERENCES characters(id) ON DELETE SET NULL,
                    body                    TEXT NOT NULL,
                    message_type            VARCHAR(32) NOT NULL DEFAULT 'chat',
                    meta                    JSONB NOT NULL DEFAULT '{}',
                    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_feed_guild
                ON guild_feed_messages(guild_id, created_at DESC);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_boss_encounters (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id        UUID NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                    boss_key        VARCHAR(64) NOT NULL,
                    hp_remaining    BIGINT NOT NULL,
                    hp_max          BIGINT NOT NULL,
                    status          VARCHAR(16) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','defeated','expired')),
                    opens_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    closes_at       TIMESTAMPTZ NOT NULL,
                    settled_at      TIMESTAMPTZ
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_boss_enc_guild
                ON guild_boss_encounters(guild_id, status, opens_at DESC);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_boss_hits (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    encounter_id    UUID NOT NULL REFERENCES guild_boss_encounters(id) ON DELETE CASCADE,
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    damage          INT NOT NULL CHECK (damage >= 0),
                    source          VARCHAR(32) NOT NULL DEFAULT 'simplified_roll',
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_boss_hits_enc
                ON guild_boss_hits(encounter_id, created_at DESC);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_tech_unlocks (
                    guild_id        UUID NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                    node_id         VARCHAR(64) NOT NULL,
                    unlocked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (guild_id, node_id)
                );
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_raid_runs (
                    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id                UUID NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                    template_key            VARCHAR(64) NOT NULL,
                    status                  VARCHAR(16) NOT NULL DEFAULT 'recruiting'
                        CHECK (status IN ('recruiting','active','completed','cancelled')),
                    leader_character_id     UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at              TIMESTAMPTZ,
                    completed_at            TIMESTAMPTZ
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_raid_runs_guild
                ON guild_raid_runs(guild_id, created_at DESC);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_raid_participants (
                    run_id          UUID NOT NULL REFERENCES guild_raid_runs(id) ON DELETE CASCADE,
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    role            VARCHAR(16) NOT NULL DEFAULT 'member',
                    PRIMARY KEY (run_id, character_id)
                );
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS guild_checkins (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    guild_id        UUID NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                    checkin_day     DATE NOT NULL,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (guild_id, character_id, checkin_day)
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_guild_checkins_guild_day
                ON guild_checkins(guild_id, checkin_day DESC);
            """)

            # Social (friends, ignore, whispers)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS player_friend_requests (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    from_player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    to_player_id    BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'declined')),
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    responded_at    TIMESTAMPTZ,
                    CHECK (from_player_id != to_player_id)
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_friend_requests_to
                ON player_friend_requests(to_player_id, status);
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_friend_requests_from
                ON player_friend_requests(from_player_id, status);
            """)
            await c.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_friend_requests_pending_pair
                ON player_friend_requests(from_player_id, to_player_id) WHERE (status = 'pending');
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS player_friendships (
                    player_a_id     BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    player_b_id     BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (player_a_id, player_b_id),
                    CHECK (player_a_id < player_b_id)
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_friendships_a ON player_friendships(player_a_id);
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_friendships_b ON player_friendships(player_b_id);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS player_ignores (
                    blocker_id      BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    blocked_id      BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (blocker_id, blocked_id),
                    CHECK (blocker_id != blocked_id)
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_player_ignores_blocked ON player_ignores(blocked_id);
            """)
            await c.execute("""
                CREATE TABLE IF NOT EXISTS player_whispers (
                    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    from_player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    to_player_id    BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                    body            VARCHAR(500) NOT NULL,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    read_at         TIMESTAMPTZ
                );
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_whispers_to
                ON player_whispers(to_player_id, created_at DESC);
            """)

            # Load additional items migration (500 items: 10 per rarity per slot)
            try:
                import os
                migration_path = os.path.join(os.path.dirname(__file__), "migrate_add_items.sql")
                if os.path.exists(migration_path):
                    with open(migration_path, "r") as f:
                        items_migration = f.read()
                        await c.execute(items_migration)
                        log.info("Loaded 500 additional items from migration.")
                else:
                    log.warning(f"migrate_add_items.sql not found at {migration_path}, skipping additional items.")
            except Exception as e:
                log.error(f"Error loading items migration: {e}")

            # Re-apply max_stack for any items added by migrate_add_items.sql (armor/weapons unchanged).
            await c.execute(
                """
                UPDATE item_templates SET max_stack = 99
                WHERE item_type IN ('consumable', 'material')
                  AND equip_slot IS NULL;
                """
            )
            await _merge_stackable_inventory_rows(c)

            # Warriors use rage (cap 100), not mana — fix legacy rows with max_res = 0.
            try:
                await c.execute(
                    """
                    UPDATE characters
                    SET max_res = 100,
                        current_res = LEAST(GREATEST(COALESCE(current_res, 0), 0), 100)
                    WHERE class = 'warrior' AND COALESCE(max_res, 0) < 100;
                    """
                )
            except Exception as e:
                log.warning("Warrior resource repair skipped: %s", e)

            # Player market: timed auctions share `market_listings` with fixed-price rows.
            await c.execute("""
                ALTER TABLE market_listings
                    ADD COLUMN IF NOT EXISTS listing_kind VARCHAR(16) NOT NULL DEFAULT 'fixed',
                    ADD COLUMN IF NOT EXISTS current_bid INT,
                    ADD COLUMN IF NOT EXISTS bid_count INT NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS current_bidder_id UUID REFERENCES characters(id),
                    ADD COLUMN IF NOT EXISTS buyout_price INT,
                    ADD COLUMN IF NOT EXISTS auction_ends_at TIMESTAMPTZ;
            """)
            await c.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_auction_end
                ON market_listings(auction_ends_at)
                WHERE is_active = TRUE AND COALESCE(listing_kind, 'fixed') = 'auction';
            """)

        log.info("Schema initialized.")


# ═════════════════════════════════════════════════════════════════════════════
#  FULL POSTGRESQL SCHEMA
#  All tables for the complete game. Run once; idempotent on restart.
# ═════════════════════════════════════════════════════════════════════════════

_SCHEMA = """
-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── Enums ────────────────────────────────────────────────────────────────────
DO $$ BEGIN CREATE TYPE item_rarity AS ENUM (
    'common','uncommon','rare','epic','legendary','artifact'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE item_type AS ENUM (
    'weapon','armor','accessory','consumable','material','quest','cosmetic'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE equip_slot AS ENUM (
    'head','chest','hands','legs','feet','main_hand','off_hand','neck','ring','trinket'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE combat_status AS ENUM (
    'idle','in_combat','dead','resting'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE guild_rank AS ENUM (
    'member','veteran','officer','guildmaster'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE gold_reason AS ENUM (
    'drop','purchase','sale','trade','quest_reward','dungeon_reward',
    'market_sale','market_fee','repair','admin'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- PLAYERS (Discord accounts)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS players (
    id                  BIGINT PRIMARY KEY,          -- Discord user ID
    username            VARCHAR(100) NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_seen           TIMESTAMPTZ DEFAULT NOW(),
    is_premium          BOOLEAN DEFAULT FALSE,
    premium_expires     TIMESTAMPTZ,
    stripe_customer_id  VARCHAR(120),
    total_playtime_sec  BIGINT DEFAULT 0,
    prestige_level      SMALLINT DEFAULT 0,
    settings            JSONB DEFAULT '{}'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- CHARACTERS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS characters (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id       BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    name            VARCHAR(32) NOT NULL UNIQUE,
    class           VARCHAR(32) NOT NULL,
    specialization  VARCHAR(32),                    -- NULL until level 10

    level           SMALLINT DEFAULT 1 CHECK (level BETWEEN 1 AND 60),
    xp              BIGINT DEFAULT 0,
    xp_rested       BIGINT DEFAULT 0,

    -- Base stats (before gear; apply spec multipliers in code)
    str             SMALLINT NOT NULL,
    agi             SMALLINT NOT NULL,
    int_            SMALLINT NOT NULL,
    spi             SMALLINT NOT NULL,
    sta             SMALLINT NOT NULL,

    -- Live HP/resource (persisted between sessions)
    current_hp      INT NOT NULL,
    max_hp          INT NOT NULL,
    current_res     INT DEFAULT 0,                  -- mana / energy / rage
    max_res         INT DEFAULT 0,

    -- State
    combat_status   combat_status DEFAULT 'idle',
    current_zone    VARCHAR(64) DEFAULT 'elwynn_forest',
    in_dungeon      BOOLEAN DEFAULT FALSE,

    -- Economy
    gold            BIGINT DEFAULT 0,
    bank_gold       BIGINT DEFAULT 0,

    -- Guild
    guild_id        UUID,
    guild_rank      guild_rank,

    -- Prestige (end-game)
    prestige        SMALLINT DEFAULT 0,

    -- Crafting / forge progression
    crafting_level  SMALLINT DEFAULT 1 CHECK (crafting_level BETWEEN 1 AND 99),
    crafting_xp     INT DEFAULT 0 CHECK (crafting_xp >= 0),

    -- Timestamps
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_combat     TIMESTAMPTZ,
    last_explore    TIMESTAMPTZ,
    last_rested     TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT one_active_char UNIQUE (player_id, is_active)
);

CREATE INDEX IF NOT EXISTS idx_char_player  ON characters(player_id);
CREATE INDEX IF NOT EXISTS idx_char_zone    ON characters(current_zone);
CREATE INDEX IF NOT EXISTS idx_char_guild   ON characters(guild_id);
CREATE INDEX IF NOT EXISTS idx_char_level   ON characters(level DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- ITEM TEMPLATES  (master catalogue — never instanced data)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS item_templates (
    id              VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    item_type       item_type NOT NULL,
    rarity          item_rarity DEFAULT 'common',
    equip_slot      equip_slot,
    level_req       SMALLINT DEFAULT 1,
    class_req       VARCHAR(32),

    -- Base stats
    s_str   SMALLINT DEFAULT 0,
    s_agi   SMALLINT DEFAULT 0,
    s_int   SMALLINT DEFAULT 0,
    s_spi   SMALLINT DEFAULT 0,
    s_sta   SMALLINT DEFAULT 0,
    s_armor SMALLINT DEFAULT 0,
    s_dmg_min SMALLINT DEFAULT 0,
    s_dmg_max SMALLINT DEFAULT 0,
    s_speed FLOAT DEFAULT 2.0,
    
    -- Secondary stats
    s_haste SMALLINT DEFAULT 0,        -- Attack speed bonus (%)
    s_lifesteal SMALLINT DEFAULT 0,    -- Lifesteal (%)
    s_resistance SMALLINT DEFAULT 0,   -- Elemental resistance
    s_hit_rating SMALLINT DEFAULT 0,    -- Accuracy bonus
    
    -- Set bonuses
    set_id VARCHAR(64),                 -- Set identifier (e.g., "warrior_set_1")

    -- Consumable
    effect_type     VARCHAR(32),
    effect_value    INT DEFAULT 0,
    effect_duration SMALLINT DEFAULT 0,

    -- Economy
    vendor_buy      INT DEFAULT 0,
    vendor_sell     INT DEFAULT 0,

    -- Flags
    max_stack       SMALLINT DEFAULT 1,
    max_durability  SMALLINT DEFAULT 100,
    tradeable       BOOLEAN DEFAULT TRUE,
    soulbound       BOOLEAN DEFAULT FALSE,
    icon            VARCHAR(10) DEFAULT '📦'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INVENTORY  (instanced items owned by characters)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inventory (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    template_id     VARCHAR(64) NOT NULL REFERENCES item_templates(id),
    quantity        SMALLINT DEFAULT 1 CHECK (quantity >= 0),
    durability      SMALLINT DEFAULT 100 CHECK (durability BETWEEN 0 AND 100),

    -- Random roll bonuses (on top of template stats)
    r_str   SMALLINT DEFAULT 0,
    r_agi   SMALLINT DEFAULT 0,
    r_int   SMALLINT DEFAULT 0,
    r_spi   SMALLINT DEFAULT 0,
    r_sta   SMALLINT DEFAULT 0,
    r_haste SMALLINT DEFAULT 0,
    r_lifesteal SMALLINT DEFAULT 0,
    r_resistance SMALLINT DEFAULT 0,
    r_hit_rating SMALLINT DEFAULT 0,

    -- Equipment state
    is_equipped     BOOLEAN DEFAULT FALSE,
    equip_slot      equip_slot,

    -- Enhancement
    enhancement_level SMALLINT DEFAULT 0 CHECK (enhancement_level BETWEEN 0 AND 10),

    -- Provenance
    locked          BOOLEAN DEFAULT FALSE,
    obtained_at     TIMESTAMPTZ DEFAULT NOW(),
    obtained_from   VARCHAR(32) DEFAULT 'drop'
);

CREATE INDEX IF NOT EXISTS idx_inv_char     ON inventory(character_id);
CREATE INDEX IF NOT EXISTS idx_inv_equipped ON inventory(character_id, is_equipped) WHERE is_equipped;

-- ─────────────────────────────────────────────────────────────────────────────
-- CRAFTING (timed upgrades + recipes)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS craft_recipes (
    id                      VARCHAR(64) PRIMARY KEY,
    name                    VARCHAR(120) NOT NULL,
    description             TEXT,
    input_template_id       VARCHAR(64) NOT NULL REFERENCES item_templates(id),
    output_template_id      VARCHAR(64) NOT NULL REFERENCES item_templates(id),
    craft_seconds           INT NOT NULL DEFAULT 10 CHECK (craft_seconds >= 1 AND craft_seconds <= 86400),
    required_crafting_level SMALLINT NOT NULL DEFAULT 1 CHECK (required_crafting_level BETWEEN 1 AND 99),
    gold_cost               INT NOT NULL DEFAULT 0 CHECK (gold_cost >= 0),
    costs                   JSONB NOT NULL DEFAULT '{}',
    crafting_xp_reward      INT NOT NULL DEFAULT 5 CHECK (crafting_xp_reward >= 0)
);

CREATE INDEX IF NOT EXISTS idx_craft_recipes_input ON craft_recipes(input_template_id);

CREATE TABLE IF NOT EXISTS craft_jobs (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id            UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    recipe_id               VARCHAR(64) NOT NULL REFERENCES craft_recipes(id),
    payload                 JSONB NOT NULL DEFAULT '{}',
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completes_at            TIMESTAMPTZ NOT NULL,
    status                  VARCHAR(16) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','ready','claimed','cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_craft_jobs_char ON craft_jobs(character_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_craft_jobs_one_inflight ON craft_jobs(character_id) WHERE (status IN ('active', 'ready'));

-- ─────────────────────────────────────────────────────────────────────────────
-- GUILDS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guilds (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(64) NOT NULL UNIQUE,
    tag             VARCHAR(8)  NOT NULL UNIQUE,
    description     TEXT,
    motd            TEXT,
    guildmaster_id  UUID NOT NULL REFERENCES characters(id),
    guild_level     SMALLINT DEFAULT 1,
    guild_xp        BIGINT DEFAULT 0,
    bank_gold       BIGINT DEFAULT 0,
    member_count    SMALLINT DEFAULT 1,
    max_members     SMALLINT DEFAULT 20,
    server_id       BIGINT,
    is_premium      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guilds_server ON guilds(server_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- COMBAT SESSIONS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS combat_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id      BIGINT NOT NULL,
    session_type    VARCHAR(16) DEFAULT 'solo',   -- solo|party|pvp|dungeon|raid
    zone            VARCHAR(64),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    outcome         VARCHAR(16),                  -- victory|defeat|fled|timeout
    turn_count      SMALLINT DEFAULT 0,
    state_snapshot  JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS combat_participants (
    session_id      UUID REFERENCES combat_sessions(id) ON DELETE CASCADE,
    character_id    UUID REFERENCES characters(id) ON DELETE CASCADE,
    is_player       BOOLEAN DEFAULT TRUE,
    hp_start        INT NOT NULL,
    hp_end          INT,
    dmg_dealt       INT DEFAULT 0,
    dmg_taken       INT DEFAULT 0,
    healing_done    INT DEFAULT 0,
    PRIMARY KEY (session_id, character_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DUNGEON RUNS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dungeon_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dungeon_key     VARCHAR(64) NOT NULL,
    thread_id       BIGINT,
    difficulty      SMALLINT DEFAULT 1,
    affixes         JSONB DEFAULT '[]',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    outcome         VARCHAR(16),
    current_floor   SMALLINT DEFAULT 1,
    total_floors    SMALLINT DEFAULT 3,
    timer_seconds   INT DEFAULT 1800
);

CREATE TABLE IF NOT EXISTS dungeon_participants (
    run_id          UUID REFERENCES dungeon_runs(id) ON DELETE CASCADE,
    character_id    UUID REFERENCES characters(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    PRIMARY KEY (run_id, character_id)
);

-- Dungeon party invites (pending invitations)
CREATE TABLE IF NOT EXISTS dungeon_party_invites (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id          UUID REFERENCES dungeon_runs(id) ON DELETE CASCADE,
    inviter_id      UUID REFERENCES characters(id) ON DELETE CASCADE,
    invitee_id      UUID REFERENCES characters(id) ON DELETE CASCADE,
    status          VARCHAR(16) DEFAULT 'pending',  -- pending, accepted, declined
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '15 minutes'),
    UNIQUE(run_id, invitee_id)
);
CREATE INDEX IF NOT EXISTS idx_dungeon_invites_invitee ON dungeon_party_invites(invitee_id, status);
CREATE INDEX IF NOT EXISTS idx_dungeon_invites_run ON dungeon_party_invites(run_id, status);

-- In-game social (friends, ignore, whispers)
CREATE TABLE IF NOT EXISTS player_friend_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    to_player_id    BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'declined')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at    TIMESTAMPTZ,
    CHECK (from_player_id != to_player_id)
);
CREATE INDEX IF NOT EXISTS idx_friend_requests_to ON player_friend_requests(to_player_id, status);
CREATE INDEX IF NOT EXISTS idx_friend_requests_from ON player_friend_requests(from_player_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_friend_requests_pending_pair
    ON player_friend_requests(from_player_id, to_player_id) WHERE (status = 'pending');

CREATE TABLE IF NOT EXISTS player_friendships (
    player_a_id     BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    player_b_id     BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_a_id, player_b_id),
    CHECK (player_a_id < player_b_id)
);
CREATE INDEX IF NOT EXISTS idx_friendships_a ON player_friendships(player_a_id);
CREATE INDEX IF NOT EXISTS idx_friendships_b ON player_friendships(player_b_id);

CREATE TABLE IF NOT EXISTS player_ignores (
    blocker_id      BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    blocked_id      BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id != blocked_id)
);
CREATE INDEX IF NOT EXISTS idx_player_ignores_blocked ON player_ignores(blocked_id);

CREATE TABLE IF NOT EXISTS player_whispers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    to_player_id    BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    body            VARCHAR(500) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_whispers_to ON player_whispers(to_player_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_whispers_thread ON player_whispers(
    LEAST(from_player_id, to_player_id), GREATEST(from_player_id, to_player_id), created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- QUESTS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quest_templates (
    id              VARCHAR(64) PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    quest_type      VARCHAR(16) DEFAULT 'daily',
    level_req       SMALLINT DEFAULT 1,
    zone            VARCHAR(64),
    objectives      JSONB NOT NULL DEFAULT '[]',
    rewards         JSONB NOT NULL DEFAULT '{}',
    repeatable      BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS character_quests (
    character_id    UUID REFERENCES characters(id) ON DELETE CASCADE,
    quest_id        VARCHAR(64) REFERENCES quest_templates(id),
    progress        JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    is_complete     BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (character_id, quest_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ECONOMY — Marketplace & Gold Log
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_listings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    seller_id   UUID NOT NULL REFERENCES characters(id),
    item_id     UUID REFERENCES inventory(id) ON DELETE SET NULL,
    price       INT NOT NULL CHECK (price > 0),
    quantity    SMALLINT DEFAULT 1,
    listed_at   TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '7 days',
    is_active   BOOLEAN DEFAULT TRUE,
    sold_at     TIMESTAMPTZ,
    buyer_id    UUID REFERENCES characters(id),
    listing_kind        VARCHAR(16) NOT NULL DEFAULT 'fixed',
    current_bid         INT,
    bid_count           INT NOT NULL DEFAULT 0,
    current_bidder_id   UUID REFERENCES characters(id),
    buyout_price        INT,
    auction_ends_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_market_active ON market_listings(is_active, expires_at) WHERE is_active;

-- Partial index on listing_kind belongs only in initialize_schema after ALTER migrations.
-- Putting it here breaks existing DBs: CREATE TABLE IF NOT EXISTS is skipped, but the index
-- still runs and references columns that do not exist yet.

CREATE TABLE IF NOT EXISTS gold_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id    UUID NOT NULL REFERENCES characters(id),
    amount          INT NOT NULL,
    balance_after   BIGINT NOT NULL,
    reason          VARCHAR(120),
    source          gold_reason,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gold_log_char ON gold_log(character_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- WORLD STATE
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zone_state (
    zone_key            VARCHAR(64) PRIMARY KEY,
    active_players      INT DEFAULT 0,
    kills_today         INT DEFAULT 0,
    boss_alive          BOOLEAN DEFAULT TRUE,
    boss_next_spawn     TIMESTAMPTZ,
    last_reset          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS world_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_key   VARCHAR(64) NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    zone        VARCHAR(64),
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    ends_at     TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT TRUE,
    state       JSONB DEFAULT '{}'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ACHIEVEMENTS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS achievement_templates (
    id          VARCHAR(64) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    category    VARCHAR(32),
    icon        VARCHAR(10) DEFAULT '🏆',
    points      SMALLINT DEFAULT 10,
    secret      BOOLEAN DEFAULT FALSE,
    criteria    JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS character_achievements (
    character_id    UUID REFERENCES characters(id) ON DELETE CASCADE,
    achievement_id  VARCHAR(64) REFERENCES achievement_templates(id),
    earned_at       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (character_id, achievement_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- COOLDOWNS  (persistent — survive bot restarts)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cooldowns (
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    action_key      VARCHAR(64) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (character_id, action_key)
);

CREATE INDEX IF NOT EXISTS idx_cd_expires ON cooldowns(expires_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- DAILY LOGIN STREAKS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS login_streaks (
    character_id    UUID PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    current_streak  SMALLINT DEFAULT 0,
    longest_streak  SMALLINT DEFAULT 0,
    last_login      TIMESTAMPTZ,
    total_logins    INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_login_streak ON login_streaks(current_streak DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- BATTLE PASS (seasonal progression + tier claims)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS battle_pass_seasons (
    id                  SERIAL PRIMARY KEY,
    key                 VARCHAR(64) NOT NULL UNIQUE,
    name                VARCHAR(120) NOT NULL,
    starts_at           TIMESTAMPTZ NOT NULL,
    ends_at             TIMESTAMPTZ NOT NULL,
    max_tier            SMALLINT NOT NULL DEFAULT 30,
    xp_per_tier         INT NOT NULL DEFAULT 100,
    weekend_multiplier  FLOAT NOT NULL DEFAULT 2.0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS battle_pass_tier_rewards (
    season_id           INT NOT NULL REFERENCES battle_pass_seasons(id) ON DELETE CASCADE,
    tier                SMALLINT NOT NULL,
    track               VARCHAR(16) NOT NULL DEFAULT 'free',
    reward              JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (season_id, tier, track)
);

CREATE TABLE IF NOT EXISTS character_battle_pass (
    character_id        UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    season_id           INT NOT NULL REFERENCES battle_pass_seasons(id) ON DELETE CASCADE,
    xp                  INT NOT NULL DEFAULT 0,
    premium_unlocked_at TIMESTAMPTZ,
    ladder_week_index   INT NOT NULL DEFAULT 0,
    playtime_minutes_today INT NOT NULL DEFAULT 0,
    playtime_day        DATE,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (character_id, season_id)
);

CREATE TABLE IF NOT EXISTS battle_pass_claims (
    character_id        UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    season_id           INT NOT NULL REFERENCES battle_pass_seasons(id) ON DELETE CASCADE,
    tier                SMALLINT NOT NULL,
    track               VARCHAR(16) NOT NULL DEFAULT 'free',
    claimed_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (character_id, season_id, tier, track)
);

CREATE TABLE IF NOT EXISTS battle_pass_xp_grants (
    id                  BIGSERIAL PRIMARY KEY,
    character_id        UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    season_id           INT NOT NULL REFERENCES battle_pass_seasons(id) ON DELETE CASCADE,
    event_key           VARCHAR(128) NOT NULL,
    xp_amount           INT NOT NULL,
    source              VARCHAR(64) NOT NULL,
    granted_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (character_id, season_id, event_key)
);

CREATE INDEX IF NOT EXISTS idx_bp_season_active ON battle_pass_seasons(is_active, starts_at, ends_at);
CREATE INDEX IF NOT EXISTS idx_bp_progress_char ON character_battle_pass(character_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- SERVER CONFIG  (per Discord server settings + premium)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS server_config (
    server_id               BIGINT PRIMARY KEY,
    is_premium              BOOLEAN DEFAULT FALSE,
    premium_expires         TIMESTAMPTZ,
    stripe_subscription_id  VARCHAR(120),
    admin_role_id           BIGINT,
    announce_channel_id     BIGINT,
    xp_multiplier           FLOAT DEFAULT 1.0,
    gold_multiplier         FLOAT DEFAULT 1.0,
    custom_items            JSONB DEFAULT '[]',
    max_guilds              SMALLINT DEFAULT 5,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    settings                JSONB DEFAULT '{}'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- MASTERY (class + ability)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS character_class_mastery (
    character_id    UUID PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    class_key       VARCHAR(32) NOT NULL,
    xp              BIGINT DEFAULT 0,
    level           INT DEFAULT 1,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS character_ability_mastery (
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    ability_key     VARCHAR(64) NOT NULL,
    xp              BIGINT DEFAULT 0,
    level           INT DEFAULT 1,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (character_id, ability_key)
);

CREATE INDEX IF NOT EXISTS idx_ability_mastery_char ON character_ability_mastery(character_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- TALENT TREES (spendable points + allocations)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS character_talent_meta (
    character_id        UUID PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    unspent_points      SMALLINT NOT NULL DEFAULT 0,
    respec_count        SMALLINT NOT NULL DEFAULT 0,
    foundation_locked   BOOLEAN NOT NULL DEFAULT FALSE,
    last_respec_at      TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS character_talent_allocations (
    character_id    UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    node_id         VARCHAR(96) NOT NULL,
    ranks           SMALLINT NOT NULL DEFAULT 1,
    PRIMARY KEY (character_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_talent_alloc_char ON character_talent_allocations(character_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- SEED DATA
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO zone_state (zone_key) VALUES
    ('elwynn_forest'),('dun_morogh'),('barrens'),
    ('stranglethorn'),('blackrock_depths')
ON CONFLICT DO NOTHING;

INSERT INTO item_templates
    (id, name, description, item_type, rarity, equip_slot, level_req,
     s_str, s_agi, s_int, s_spi, s_sta, s_armor, s_dmg_min, s_dmg_max,
     effect_type, effect_value, effect_duration,
     vendor_buy, vendor_sell, icon)
VALUES
    ('iron_sword','Iron Sword','A sturdy iron blade.','weapon','common','main_hand',1,
     4,2,0,0,2,0,8,14, NULL,0,0, 10,4,'⚔️'),
    ('steel_sword','Steel Sword','Refined from iron stock at the forge.','weapon','uncommon','main_hand',5,
     6,3,0,0,3,0,10,18, NULL,0,0, 40,16,'⚔️'),
    ('weapon_scrap','Weapon Scrap','Salvaged metal from broken arms.','material','common',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'⚙️'),
    ('armor_scrap','Armor Scrap','Straps, plates, and leather salvage.','material','common',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🛡️'),
    ('accessory_scrap','Accessory Scrap','Rings, cords, and charm fragments.','material','common',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'✨'),
    ('leather_cap','Leather Cap','Soft leather headgear.','armor','common','head',1,
     0,2,0,1,2,12,0,0, NULL,0,0, 8,3,'🪖'),
    ('health_potion','Health Potion','Restores 25% of max HP (min 80).','consumable','common',NULL,1,
     0,0,0,0,0,0,0,0, 'heal_hp',80,0, 5,2,'🧪'),
    ('dwarven_axe','Dwarven Axe','Forged in Ironforge.','weapon','uncommon','main_hand',5,
     7,2,0,0,3,0,12,20, NULL,0,0, 25,10,'🪓'),
    ('chain_coif','Chain Coif','Reliable chain headgear.','armor','uncommon','head',5,
     0,3,0,1,4,22,0,0, NULL,0,0, 20,8,'🪖'),
    ('frost_resist_potion','Frost Resist Potion','Grants +50 frost resistance for 10 minutes.','consumable','uncommon',NULL,5,
     0,0,0,0,0,0,0,0, 'boost_resistance',50,10, 12,5,'🔵'),
    ('stamina_draught','Stamina Draught','Boosts stamina by +5 for 10 minutes.','consumable','uncommon',NULL,10,
     0,0,0,0,0,0,0,0, 'boost_sta',5,10, 15,6,'🟤'),
    ('bone_club','Bone Club','Crude but effective.','weapon','common','main_hand',10,
     5,0,0,0,3,0,10,16, NULL,0,0, 12,5,'🦴'),
    ('raptor_hide_vest','Raptor Hide Vest','Tough and lightweight.','armor','uncommon','chest',15,
     0,6,0,2,4,30,0,0, NULL,0,0, 40,16,'🥋'),
    ('corsair_blade','Corsair Blade','Pirate-forged steel.','weapon','rare','main_hand',25,
     10,8,0,0,5,0,22,36, NULL,0,0, 80,32,'⚔️'),
    ('jungle_leather_chest','Jungle Leather Chest','Stranglethorn craft.','armor','rare','chest',25,
     0,10,0,4,7,55,0,0, NULL,0,0, 70,28,'🥋'),
    ('elixir_of_fortitude','Elixir of Fortitude','Increases max HP by +100 for 30 minutes.','consumable','rare',NULL,25,
     0,0,0,0,0,0,0,0, 'boost_max_hp',100,30, 50,20,'💪'),
    ('sulfuron_blade','Sulfuron Blade','Forged in living fire.','weapon','legendary','main_hand',55,
     28,15,10,5,12,0,55,90, NULL,0,0, 500,200,'🔥'),
    ('shadowforge_plate','Shadowforge Plate Chest','Dark iron mastery.','armor','legendary','chest',55,
     10,8,5,5,20,180,0,0, NULL,0,0, 450,180,'🖤'),
    ('flask_of_the_titans','Flask of the Titans','Increases max HP by +200 for 60 minutes.','consumable','epic',NULL,50,
     0,0,0,0,0,0,0,0, 'boost_max_hp',200,60, 200,80,'⚗️'),
    -- Tiered accessories (so every zone tier has usable rings/neck/trinkets)
    ('bracelet_t1','Woven Bracelet','Starter wristwrap that takes enchantment well.','accessory','common','trinket',3,
     0,0,0,0,1,0,0,0, NULL,0,0, 20,8,'🧵'),
    ('bracelet_t2','Carved Bracelet','Cold-weather carving with a steady pulse.','accessory','common','trinket',12,
     0,0,0,0,2,0,0,0, NULL,0,0, 45,18,'🪵'),
    ('bracelet_t3','Sun-Baked Bracelet','Desert-fired band that refuses to crack.','accessory','common','trinket',20,
     0,0,0,0,3,0,0,0, NULL,0,0, 80,32,'🌞'),
    ('bracelet_t4','Jungle-Laced Bracelet','Vine and bone braided into quick luck.','accessory','common','trinket',32,
     0,0,0,0,4,0,0,0, NULL,0,0, 140,56,'🌿'),
    ('bracelet_t5','Obsidian Bracelet','Heat-polished band that hums with force.','accessory','common','trinket',50,
     0,0,0,0,6,0,0,0, NULL,0,0, 260,105,'🪨'),

    ('ring_t1','Copper Ring','A simple ring with a warm sheen.','accessory','common','ring',3,
     0,0,0,0,1,0,0,0, NULL,0,0, 20,8,'💍'),
    ('ring_t2','Iron Ring','A sturdy iron band, slightly magnetic.','accessory','common','ring',12,
     0,0,0,0,2,0,0,0, NULL,0,0, 45,18,'💍'),
    ('ring_t3','Banded Ring','A broad ring scored with travel marks.','accessory','common','ring',20,
     0,0,0,0,3,0,0,0, NULL,0,0, 80,32,'💍'),
    ('ring_t4','Jade Ring','Green stone set in a careful clasp.','accessory','common','ring',32,
     0,0,0,0,4,0,0,0, NULL,0,0, 140,56,'💍'),
    ('ring_t5','Rune Ring','Runes bite softly against the skin.','accessory','common','ring',50,
     0,0,0,0,6,0,0,0, NULL,0,0, 260,105,'💍'),

    ('necklace_t1','Tin Necklace','A dull pendant on a thin cord.','accessory','common','neck',3,
     0,0,0,0,1,0,0,0, NULL,0,0, 20,8,'📿'),
    ('necklace_t2','Stone Necklace','A stone pendant that holds cold.','accessory','common','neck',12,
     0,0,0,0,2,0,0,0, NULL,0,0, 45,18,'📿'),
    ('necklace_t3','Bone Necklace','A travel charm of polished bone.','accessory','common','neck',20,
     0,0,0,0,3,0,0,0, NULL,0,0, 80,32,'📿'),
    ('necklace_t4','Coral Necklace','Salt-bright beads strung tight.','accessory','common','neck',32,
     0,0,0,0,4,0,0,0, NULL,0,0, 140,56,'📿'),
    ('necklace_t5','Obsidian Necklace','A heavy pendant cut from dark glass.','accessory','common','neck',50,
     0,0,0,0,6,0,0,0, NULL,0,0, 260,105,'📿'),

    ('trinket_t1','Lucky Pebble','A small stone that feels familiar.','accessory','common','trinket',3,
     0,0,0,0,1,0,0,0, NULL,0,0, 20,8,'💎'),
    ('trinket_t2','Frost Charm','A charm that chills the fingertip.','accessory','common','trinket',12,
     0,0,0,0,2,0,0,0, NULL,0,0, 45,18,'❄️'),
    ('trinket_t3','Sand Token','A token that carries heat like breath.','accessory','common','trinket',20,
     0,0,0,0,3,0,0,0, NULL,0,0, 80,32,'🌵'),
    ('trinket_t4','Tide Token','A token that smells faintly of salt.','accessory','common','trinket',32,
     0,0,0,0,4,0,0,0, NULL,0,0, 140,56,'🌊'),
    ('trinket_t5','Forge Sigil','A sigil that warms when danger nears.','accessory','common','trinket',50,
     0,0,0,0,6,0,0,0, NULL,0,0, 260,105,'🔥'),
    -- Protection items for blacksmith
    ('protection_blessing_scroll','Blessing Scroll','Prevents item destruction. On fail, item loses 1 enhancement level instead.','consumable','rare',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 10000,5000,'🛡️'),
    ('protection_safety_charm','Safety Charm','Guarantees success for enhancements +1 through +5.','consumable','rare',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 5000,2500,'✨'),
    ('protection_enhancement_fragment','Enhancement Fragment','Increases success chance by 10%. Can stack up to 3 times (+30%).','consumable','uncommon',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 2000,1000,'💎'),
    -- Obsidian Silence quest items & rewards
    ('shatter_tone_tuning_fork','Shatter-Tone Tuning Fork','Resonates against glass-stillness.','quest','uncommon',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🎵'),
    ('the_dull_shard','The Dull Shard','Glass that refuses to shine.','material','rare',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🪨'),
    ('gray_border_charm','Gray Border Charm','Ash line where the forest still argues.','accessory','uncommon','trinket',3,
     0,0,0,2,4,0,0,0, NULL,0,0, 150,75,'🔲'),
    ('seismic_trigger_kit','Seismic Trigger Kit','One punch through honest bedrock.','quest','rare',NULL,8,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'📳'),
    ('deep_rock_token','Deep Rock Token','Proof of a counted rescue.','quest','uncommon',NULL,6,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🪙'),
    ('glacial_fang','Glacial Fang','Ice that still remembers motion.','weapon','rare','main_hand',8,
     9,4,0,0,3,0,18,28, NULL,0,0, 120,50,'🗡️'),
    ('sun_scorched_scimitar','Sun-Scorched Scimitar','Barrens heat folded into a curve.','weapon','rare','main_hand',14,
     11,6,0,0,4,0,22,34, NULL,0,0, 200,85,'🌅'),
    ('salt_true_compass','Salt-True Compass','Points where the tide remembers truth.','accessory','rare','trinket',28,
     0,0,0,3,0,0,0,0, NULL,0,0, 220,95,'🧭'),
    ('tribal_seal_charm','Tribal Seal Charm','Memory of the sea in carved bone.','accessory','uncommon','trinket',30,
     0,0,0,2,5,0,0,0, NULL,0,0, 180,75,'🪶'),
    ('cipher_scroll','Cipher Scroll','Stranglethorn grammar for Blackrock doors.','quest','rare',NULL,38,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'📜'),
    ('tide_cutter','Tide-Cutter','Salt edge that refuses to rot.','weapon','rare','main_hand',38,
     14,9,0,0,5,0,28,38, NULL,0,0, 280,115,'⚔️'),
    ('ember_thread','Ember Thread','Heat braided into memory.','material','epic',NULL,50,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🧵'),
    ('blessed_oil_vial','Blessed Oil Vial','Mercy that moves.','consumable','uncommon',NULL,5,
     0,0,0,0,0,0,0,0, 'boost_resistance',15,30, 40,18,'🕯️'),
    ('rune_rubbing_kit','Rune Rubbing Kit','Impressions for arguing with stone.','quest','epic',NULL,54,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🖇️'),
    ('obsidian_breaker','Obsidian Breaker','Hit Vaelkor where grammar fails.','weapon','legendary','main_hand',55,
     26,14,10,6,14,0,58,92, NULL,0,0, 520,210,'🔨'),
    ('trisect_key','Trisect Key','Three proofs of motion.','quest','legendary',NULL,50,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🗝️'),
    ('the_eternal_frequency','The Eternal Frequency','A standing wave against silence.','weapon','artifact','main_hand',58,
     32,18,14,8,16,0,62,98, NULL,0,0, 2000,800,'〰️'),
    ('vance_blood_token','Vance Blood Token','Proof the blood-debt was answered in steel.','quest','rare',NULL,30,
     0,0,0,0,0,0,0,0, NULL,0,0, 0,0,'🩸')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    item_type = EXCLUDED.item_type,
    rarity = EXCLUDED.rarity,
    equip_slot = EXCLUDED.equip_slot,
    level_req = EXCLUDED.level_req,
    s_str = EXCLUDED.s_str,
    s_agi = EXCLUDED.s_agi,
    s_int = EXCLUDED.s_int,
    s_spi = EXCLUDED.s_spi,
    s_sta = EXCLUDED.s_sta,
    s_armor = EXCLUDED.s_armor,
    s_dmg_min = EXCLUDED.s_dmg_min,
    s_dmg_max = EXCLUDED.s_dmg_max,
    effect_type = EXCLUDED.effect_type,
    effect_value = EXCLUDED.effect_value,
    effect_duration = EXCLUDED.effect_duration,
    vendor_buy = EXCLUDED.vendor_buy,
    vendor_sell = EXCLUDED.vendor_sell,
    icon = EXCLUDED.icon;

INSERT INTO craft_recipes
    (id, name, description, input_template_id, output_template_id, craft_seconds, required_crafting_level, gold_cost, costs, crafting_xp_reward)
VALUES
    ('upgrade_iron_to_steel_sword', 'Refined blade', 'Upgrade Iron Sword into a Steel Sword.', 'iron_sword', 'steel_sword', 5, 1, 50, '{"weapon_scrap": 3}'::jsonb, 15),
    ('upgrade_leather_to_chain_coif', 'Reinforced hood', 'Upgrade Leather Cap into a Chain Coif.', 'leather_cap', 'chain_coif', 8, 1, 80, '{"armor_scrap": 4}'::jsonb, 20),
    ('upgrade_bone_club_to_dwarven_axe', 'Ironforge pattern', 'Upgrade Bone Club into a Dwarven Axe.', 'bone_club', 'dwarven_axe', 30, 2, 200, '{"weapon_scrap": 6}'::jsonb, 35),
    ('upgrade_raptor_to_jungle_chest', 'Stranglethorn weave', 'Upgrade Raptor Hide Vest into Jungle Leather Chest.', 'raptor_hide_vest', 'jungle_leather_chest', 45, 3, 350, '{"armor_scrap": 8}'::jsonb, 50),
    ('upgrade_bracelet_t1_to_t2', 'Better wristwrap', 'Upgrade Woven Bracelet to a Carved Bracelet.', 'bracelet_t1', 'bracelet_t2', 6, 1, 60, '{"accessory_scrap": 3}'::jsonb, 12)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    input_template_id = EXCLUDED.input_template_id,
    output_template_id = EXCLUDED.output_template_id,
    craft_seconds = EXCLUDED.craft_seconds,
    required_crafting_level = EXCLUDED.required_crafting_level,
    gold_cost = EXCLUDED.gold_cost,
    costs = EXCLUDED.costs,
    crafting_xp_reward = EXCLUDED.crafting_xp_reward;

-- ─────────────────────────────────────────────────────────────────────────────
-- ACHIEVEMENT TEMPLATES
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO achievement_templates (id, name, description, category, icon, points, secret, criteria) VALUES
-- Leveling Achievements
('level_10', 'First Steps', 'Reach level 10', 'leveling', '🌟', 10, FALSE, '{"type": "level", "target": 10, "trigger": "level_up"}'),
('level_20', 'Rising Star', 'Reach level 20', 'leveling', '⭐', 20, FALSE, '{"type": "level", "target": 20, "trigger": "level_up"}'),
('level_30', 'Veteran', 'Reach level 30', 'leveling', '✨', 30, FALSE, '{"type": "level", "target": 30, "trigger": "level_up"}'),
('level_40', 'Elite', 'Reach level 40', 'leveling', '💫', 40, FALSE, '{"type": "level", "target": 40, "trigger": "level_up"}'),
('level_50', 'Master', 'Reach level 50', 'leveling', '🔥', 50, FALSE, '{"type": "level", "target": 50, "trigger": "level_up"}'),
('level_60', 'Champion', 'Reach the maximum level', 'leveling', '👑', 100, FALSE, '{"type": "level", "target": 60, "trigger": "level_up"}'),

-- Combat Achievements
('kill_10', 'Novice Slayer', 'Defeat 10 enemies', 'combat', '⚔️', 10, FALSE, '{"type": "kill_count", "target": 10, "trigger": "kill"}'),
('kill_50', 'Warrior', 'Defeat 50 enemies', 'combat', '🗡️', 25, FALSE, '{"type": "kill_count", "target": 50, "trigger": "kill"}'),
('kill_100', 'Battle-Hardened', 'Defeat 100 enemies', 'combat', '⚔️', 50, FALSE, '{"type": "kill_count", "target": 100, "trigger": "kill"}'),
('kill_500', 'Slayer', 'Defeat 500 enemies', 'combat', '💀', 100, FALSE, '{"type": "kill_count", "target": 500, "trigger": "kill"}'),
('kill_1000', 'Destroyer', 'Defeat 1000 enemies', 'combat', '☠️', 200, FALSE, '{"type": "kill_count", "target": 1000, "trigger": "kill"}'),
('boss_1', 'Boss Slayer', 'Defeat your first boss', 'combat', '👹', 50, FALSE, '{"type": "boss_kill_count", "target": 1, "trigger": "kill"}'),
('boss_5', 'Boss Hunter', 'Defeat 5 bosses', 'combat', '👺', 100, FALSE, '{"type": "boss_kill_count", "target": 5, "trigger": "kill"}'),
('boss_10', 'Boss Master', 'Defeat 10 bosses', 'combat', '👑', 200, FALSE, '{"type": "boss_kill_count", "target": 10, "trigger": "kill"}'),

-- Exploration Achievements
('explore_10', 'Wanderer', 'Explore 10 times', 'exploration', '🚶', 10, FALSE, '{"type": "explore_count", "target": 10, "trigger": "explore"}'),
('explore_50', 'Explorer', 'Explore 50 times', 'exploration', '🗺️', 25, FALSE, '{"type": "explore_count", "target": 50, "trigger": "explore"}'),
('explore_100', 'Adventurer', 'Explore 100 times', 'exploration', '🧭', 50, FALSE, '{"type": "explore_count", "target": 100, "trigger": "explore"}'),
('visit_all_zones', 'World Traveler', 'Visit all zones', 'exploration', '🌍', 100, FALSE, '{"type": "zone_visit", "zones": ["elwynn_forest", "dun_morogh", "barrens", "stranglethorn", "blackrock_depths"], "trigger": "zone_visit"}'),

-- Economy Achievements
('gold_1000', 'Wealthy', 'Earn 1,000 gold', 'economy', '💰', 20, FALSE, '{"type": "gold_earned", "target": 1000, "trigger": "gold_earned"}'),
('gold_10000', 'Rich', 'Earn 10,000 gold', 'economy', '💎', 50, FALSE, '{"type": "gold_earned", "target": 10000, "trigger": "gold_earned"}'),
('gold_100000', 'Millionaire', 'Earn 100,000 gold', 'economy', '💍', 150, FALSE, '{"type": "gold_earned", "target": 100000, "trigger": "gold_earned"}'),
('market_seller', 'Merchant', 'Sell an item on the marketplace', 'economy', '🏪', 15, FALSE, '{"type": "market_sell", "target": 1, "trigger": "market_sell"}'),
('market_buyer', 'Collector', 'Buy an item from the marketplace', 'economy', '🛒', 15, FALSE, '{"type": "market_buy", "target": 1, "trigger": "market_buy"}'),

-- Dungeon Achievements
('dungeon_first', 'Dungeon Delver', 'Complete your first dungeon', 'dungeon', '🏰', 50, FALSE, '{"type": "dungeon_complete", "target": 1, "trigger": "dungeon_complete"}'),
('dungeon_5', 'Dungeon Master', 'Complete 5 dungeons', 'dungeon', '🏛️', 100, FALSE, '{"type": "dungeon_complete", "target": 5, "trigger": "dungeon_complete"}'),
('dungeon_10', 'Dungeon Legend', 'Complete 10 dungeons', 'dungeon', '🏯', 200, FALSE, '{"type": "dungeon_complete", "target": 10, "trigger": "dungeon_complete"}'),
('dungeon_solo', 'Lone Wolf', 'Complete a dungeon solo', 'dungeon', '🐺', 150, FALSE, '{"type": "dungeon_solo", "target": 1, "trigger": "dungeon_complete"}'),

-- Item Achievements
('item_10', 'Collector', 'Collect 10 unique items', 'items', '📦', 15, FALSE, '{"type": "item_collect", "target": 10, "trigger": "item_collect"}'),
('item_50', 'Hoarder', 'Collect 50 unique items', 'items', '📚', 40, FALSE, '{"type": "item_collect", "target": 50, "trigger": "item_collect"}'),
('item_100', 'Curator', 'Collect 100 unique items', 'items', '🏛️', 100, FALSE, '{"type": "item_collect", "target": 100, "trigger": "item_collect"}'),
('legendary_item', 'Legendary', 'Equip a legendary item', 'items', '💎', 200, FALSE, '{"type": "legendary_equip", "target": 1, "trigger": "item_equip"}'),

-- Guild Achievements
('guild_join', 'Guild Member', 'Join a guild', 'guild', '🤝', 10, FALSE, '{"type": "guild_join", "target": 1, "trigger": "guild_join"}'),
('guild_create', 'Guildmaster', 'Create a guild', 'guild', '👑', 50, FALSE, '{"type": "guild_create", "target": 1, "trigger": "guild_create"}'),

-- Secret Achievements
('first_death', 'First Blood', 'Die in combat', 'secret', '💀', 25, TRUE, '{"type": "death", "target": 1, "trigger": "death"}'),
('flee_master', 'Coward', 'Flee from combat 10 times', 'secret', '🏃', 10, TRUE, '{"type": "flee_count", "target": 10, "trigger": "flee"}')
ON CONFLICT DO NOTHING;
"""
