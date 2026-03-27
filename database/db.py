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
    buyer_id    UUID REFERENCES characters(id)
);

CREATE INDEX IF NOT EXISTS idx_market_active ON market_listings(is_active, expires_at) WHERE is_active;

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
    -- Protection items for blacksmith
    ('protection_blessing_scroll','Blessing Scroll','Prevents item destruction. On fail, item loses 1 enhancement level instead.','consumable','rare',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 10000,5000,'🛡️'),
    ('protection_safety_charm','Safety Charm','Guarantees success for enhancements +1 through +5.','consumable','rare',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 5000,2500,'✨'),
    ('protection_enhancement_fragment','Enhancement Fragment','Increases success chance by 10%. Can stack up to 3 times (+30%).','consumable','uncommon',NULL,1,
     0,0,0,0,0,0,0,0, NULL,0,0, 2000,1000,'💎')
ON CONFLICT (id) DO UPDATE SET
    effect_type = EXCLUDED.effect_type,
    effect_value = EXCLUDED.effect_value,
    effect_duration = EXCLUDED.effect_duration;

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
