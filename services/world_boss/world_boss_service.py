"""
Guild world boss windows: DB access, active lookups, trigger evaluation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.settings import Settings, ZONES
from config.world_boss_triggers import (
    WORLD_BOSS_TRIGGERS,
    MilestoneBossTrigger,
    PresenceBossTrigger,
    WorldBossTrigger,
)

log = logging.getLogger("world_boss")


class WorldBossService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    async def fetch_zone_patrol_boss_alive(db, zone_key: str) -> bool:
        row = await db.fetchrow("SELECT boss_alive FROM zone_state WHERE zone_key=$1", zone_key)
        if not row or row.get("boss_alive") is None:
            return True
        return bool(row["boss_alive"])

    @staticmethod
    async def mark_zone_patrol_boss_defeated(db, zone_key: str, enemy_key: str) -> None:
        """When a zone boss from the zone roster is killed in open world (not dungeon)."""
        zone = ZONES.get(zone_key)
        if not zone or enemy_key not in zone.bosses:
            return
        hours = float(getattr(Settings, "ZONE_PATROL_BOSS_RESPAWN_HOURS", 4) or 4)
        await db.execute(
            """
            UPDATE zone_state
            SET boss_alive=FALSE,
                boss_next_spawn=NOW() + ($2::double precision * INTERVAL '1 hour')
            WHERE zone_key=$1
            """,
            zone_key,
            hours,
        )

    async def list_active_windows(self, guild_id: int) -> List[Dict[str, Any]]:
        rows = await self.db.fetch(
            """
            SELECT zone_key, boss_key, ends_at, trigger_slug, trigger_kind
            FROM guild_world_boss_windows
            WHERE guild_id=$1 AND ends_at > NOW()
            ORDER BY ends_at ASC
            """,
            guild_id,
        )
        by_slug = {t.slug: t for t in WORLD_BOSS_TRIGGERS}
        out: List[Dict[str, Any]] = []
        for r in rows:
            slug = r["trigger_slug"]
            trig = by_slug.get(slug)
            title = trig.title if trig and hasattr(trig, "title") else slug.replace("_", " ").title()
            out.append(
                {
                    "zone_key": r["zone_key"],
                    "boss_key": r["boss_key"],
                    "ends_at": r["ends_at"].isoformat() if r["ends_at"] else None,
                    "trigger_slug": slug,
                    "trigger_kind": r["trigger_kind"],
                    "title": title,
                }
            )
        return out

    async def active_window_boss_for_zone(self, guild_id: Optional[int], zone_key: str) -> Optional[str]:
        """If a lore window is active for this guild+zone, return forced boss key (else None)."""
        if not guild_id:
            return None
        row = await self.db.fetchrow(
            """
            SELECT boss_key FROM guild_world_boss_windows
            WHERE guild_id=$1 AND zone_key=$2 AND ends_at > NOW()
            ORDER BY ends_at DESC
            LIMIT 1
            """,
            guild_id,
            zone_key,
        )
        if not row:
            return None
        return str(row["boss_key"])

    async def has_active_trigger_slug(self, guild_id: int, slug: str) -> bool:
        v = await self.db.fetchval(
            """
            SELECT 1 FROM guild_world_boss_windows
            WHERE guild_id=$1 AND trigger_slug=$2 AND ends_at > NOW()
            LIMIT 1
            """,
            guild_id,
            slug,
        )
        return v is not None

    async def last_window_ended_at(self, guild_id: int, slug: str) -> Optional[datetime]:
        ts = await self.db.fetchval(
            """
            SELECT MAX(ends_at) FROM guild_world_boss_windows
            WHERE guild_id=$1 AND trigger_slug=$2
            """,
            guild_id,
            slug,
        )
        return ts

    async def insert_window(
        self,
        guild_id: int,
        *,
        trigger_slug: str,
        zone_key: str,
        boss_key: str,
        duration_hours: float,
        trigger_kind: str,
        trigger_detail: Dict[str, Any],
    ) -> None:
        detail_json = json.dumps(trigger_detail or {})
        await self.db.execute(
            """
            INSERT INTO guild_world_boss_windows
                (guild_id, trigger_slug, zone_key, boss_key, starts_at, ends_at, trigger_kind, trigger_detail)
            VALUES ($1, $2, $3, $4, NOW(), NOW() + ($5::double precision * INTERVAL '1 hour'), $6, $7::jsonb)
            """,
            guild_id,
            trigger_slug,
            zone_key,
            boss_key,
            float(duration_hours),
            trigger_kind,
            detail_json,
        )

    async def set_window_announced(self, window_id: Any) -> None:
        await self.db.execute(
            "UPDATE guild_world_boss_windows SET announce_sent=TRUE WHERE id=$1",
            window_id,
        )

    async def latest_window_id(self, guild_id: int, trigger_slug: str) -> Any:
        return await self.db.fetchval(
            """
            SELECT id FROM guild_world_boss_windows
            WHERE guild_id=$1 AND trigger_slug=$2
            ORDER BY starts_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            guild_id,
            trigger_slug,
        )

    async def pending_announce_rows(self, guild_id: int) -> List[Dict[str, Any]]:
        return [
            dict(r)
            for r in await self.db.fetch(
                """
                SELECT id, trigger_slug, zone_key, boss_key, ends_at, trigger_kind
                FROM guild_world_boss_windows
                WHERE guild_id=$1 AND ends_at > NOW() AND announce_sent=FALSE
                ORDER BY starts_at ASC
                """,
                guild_id,
            )
        ]

    @staticmethod
    async def milestone_tier(db, guild_id: int, key: str) -> int:
        row = await db.fetchrow(
            "SELECT tier_reached FROM server_milestones WHERE guild_id=$1 AND key=$2",
            guild_id,
            key,
        )
        if not row:
            return 0
        return int(row["tier_reached"] or 0)

    @staticmethod
    async def count_guild_players_in_zone(db, guild_id: int, zone_key: str) -> int:
        n = await db.fetchval(
            """
            SELECT COUNT(*) FROM characters
            WHERE is_active=TRUE AND current_zone=$1 AND last_discord_guild_id=$2
            """,
            zone_key,
            guild_id,
        )
        return int(n or 0)

    @staticmethod
    async def distinct_activity_guild_ids(db) -> List[int]:
        rows = await self.db.fetch(
            """
            SELECT DISTINCT last_discord_guild_id AS gid
            FROM characters
            WHERE is_active=TRUE AND last_discord_guild_id IS NOT NULL
            """
        )
        return [int(r["gid"]) for r in rows if r["gid"] is not None]

    def cooldown_blocks(
        self,
        *,
        last_end: Optional[datetime],
        cooldown_hours: float,
    ) -> bool:
        if last_end is None:
            return False
        if last_end.tzinfo is None:
            last_end = last_end.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last_end
        return delta.total_seconds() < float(cooldown_hours) * 3600.0

    async def maybe_fire_trigger(self, guild_id: int, trig: WorldBossTrigger) -> bool:
        """Returns True if a new window was opened."""
        if await self.has_active_trigger_slug(guild_id, trig.slug):
            return False
        last_end = await self.last_window_ended_at(guild_id, trig.slug)
        if self.cooldown_blocks(last_end=last_end, cooldown_hours=trig.cooldown_hours):
            return False

        if isinstance(trig, MilestoneBossTrigger):
            tier = await self.milestone_tier(self.db, guild_id, trig.milestone_key)
            if tier < trig.min_tier:
                return False
        elif isinstance(trig, PresenceBossTrigger):
            n = await self.count_guild_players_in_zone(self.db, guild_id, trig.zone_key)
            if n < trig.min_players:
                return False
        else:
            return False

        detail: Dict[str, Any] = {"slug": trig.slug}
        if isinstance(trig, MilestoneBossTrigger):
            detail["milestone_key"] = trig.milestone_key
            detail["min_tier"] = trig.min_tier
        else:
            detail["min_players"] = trig.min_players

        await self.insert_window(
            guild_id,
            trigger_slug=trig.slug,
            zone_key=trig.zone_key,
            boss_key=trig.boss_key,
            duration_hours=trig.duration_hours,
            trigger_kind=trig.kind,
            trigger_detail=detail,
        )
        log.info("Opened world boss window guild=%s slug=%s zone=%s boss=%s", guild_id, trig.slug, trig.zone_key, trig.boss_key)
        return True

    async def evaluate_all_triggers_for_guild(self, guild_id: int) -> List[WorldBossTrigger]:
        """Evaluate configured triggers; return triggers that opened a new window this call."""
        opened: List[WorldBossTrigger] = []
        for trig in WORLD_BOSS_TRIGGERS:
            try:
                if await self.maybe_fire_trigger(guild_id, trig):
                    opened.append(trig)
            except Exception:
                log.exception("world boss trigger failed guild=%s slug=%s", guild_id, getattr(trig, "slug", "?"))
        return opened
