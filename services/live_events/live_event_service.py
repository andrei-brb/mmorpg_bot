"""
Per-guild scheduled live events (double XP, gold, boss hunt, etc.).

Configs are stored in `guild_live_events.config` JSON, e.g.:
  {"xp_multiplier": 2.0, "gold_multiplier": 1.0, "explore_boss_chance_add": 0.08}
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger("live_events")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}$")


def _parse_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


class LiveEventService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def validate_slug(slug: str) -> bool:
        return bool(slug and _SLUG_RE.match(slug))

    async def get_reward_multipliers(self, guild_id: int) -> Dict[str, float]:
        """Active events multiply together. boss_chance_add sums then caps."""
        rows = await self.db.fetch(
            """SELECT config FROM guild_live_events
               WHERE guild_id=$1 AND enabled=TRUE
                 AND starts_at <= NOW() AND ends_at > NOW()""",
            guild_id,
        )
        xp = 1.0
        gold = 1.0
        boss_add = 0.0
        for r in rows:
            c = _parse_config(r["config"])
            try:
                xp *= float(c.get("xp_multiplier") or 1.0)
                gold *= float(c.get("gold_multiplier") or 1.0)
                boss_add += float(c.get("explore_boss_chance_add") or 0.0)
            except (TypeError, ValueError):
                continue
        boss_add = min(max(boss_add, 0.0), 0.15)
        return {
            "xp_multiplier": xp,
            "gold_multiplier": gold,
            "explore_boss_chance_add": boss_add,
        }

    async def list_active_public(self, guild_id: int) -> List[dict]:
        """Active events for Activity / API (no secrets)."""
        rows = await self.db.fetch(
            """SELECT slug, title, description, config, starts_at, ends_at
               FROM guild_live_events
               WHERE guild_id=$1 AND enabled=TRUE
                 AND starts_at <= NOW() AND ends_at > NOW()
               ORDER BY ends_at ASC""",
            guild_id,
        )
        return [dict(r) for r in rows]

    async def list_all(self, guild_id: int) -> List[dict]:
        rows = await self.db.fetch(
            """SELECT * FROM guild_live_events
               WHERE guild_id=$1
               ORDER BY starts_at DESC
               LIMIT 50""",
            guild_id,
        )
        return [dict(r) for r in rows]

    async def create_event(
        self,
        guild_id: int,
        slug: str,
        title: str,
        *,
        description: str = "",
        starts_at: datetime,
        ends_at: datetime,
        config: Dict[str, Any],
        announce_on_start: bool = True,
        announce_on_end: bool = False,
        announce_channel_id: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> None:
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        await self.db.execute(
            """INSERT INTO guild_live_events (
                 guild_id, slug, title, description, config,
                 starts_at, ends_at, enabled,
                 announce_on_start, announce_on_end, announce_channel_id,
                 announce_start_sent, announce_end_sent,
                 created_by
               )
               VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,TRUE,$8,$9,$10,FALSE,FALSE,$11)
               ON CONFLICT (guild_id, slug) DO UPDATE SET
                 title=EXCLUDED.title,
                 description=EXCLUDED.description,
                 config=EXCLUDED.config,
                 starts_at=EXCLUDED.starts_at,
                 ends_at=EXCLUDED.ends_at,
                 enabled=TRUE,
                 announce_on_start=EXCLUDED.announce_on_start,
                 announce_on_end=EXCLUDED.announce_on_end,
                 announce_channel_id=EXCLUDED.announce_channel_id,
                 announce_start_sent=FALSE,
                 announce_end_sent=FALSE,
                 created_by=EXCLUDED.created_by
            """,
            guild_id,
            slug,
            title,
            description,
            json.dumps(config),
            starts_at,
            ends_at,
            announce_on_start,
            announce_on_end,
            announce_channel_id,
            created_by,
        )

    async def delete_event(self, guild_id: int, slug: str) -> bool:
        r = await self.db.execute(
            "DELETE FROM guild_live_events WHERE guild_id=$1 AND slug=$2",
            guild_id,
            slug,
        )
        return "DELETE 1" in r

    async def disable_event(self, guild_id: int, slug: str) -> bool:
        r = await self.db.execute(
            "UPDATE guild_live_events SET enabled=FALSE WHERE guild_id=$1 AND slug=$2",
            guild_id,
            slug,
        )
        return "UPDATE 1" in r
