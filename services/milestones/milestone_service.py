"""
Server Milestones v1 service.

Tracks per-guild aggregate goals and grants temporary server buffs on tier unlock.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

log = logging.getLogger("milestones")


@dataclass(frozen=True)
class MilestoneTrack:
    key: str
    title: str
    thresholds: tuple[int, ...]
    unit: str


# v1 tracks
TRACKS: Dict[str, MilestoneTrack] = {
    "characters_created": MilestoneTrack("characters_created", "Population", (25, 50, 100, 250), "characters"),
    "levels_gained": MilestoneTrack("levels_gained", "Progression", (500, 1500, 5000), "levels"),
    "kills_total": MilestoneTrack("kills_total", "Combat: Kills", (1000, 5000, 20000), "kills"),
    "boss_kills": MilestoneTrack("boss_kills", "Combat: Boss Kills", (25, 100, 300), "boss kills"),
    "gold_earned": MilestoneTrack("gold_earned", "Economy", (100_000, 500_000, 2_000_000), "gold"),
    "quests_completed": MilestoneTrack("quests_completed", "Quests", (500, 2000, 10000), "quests"),
}


class MilestoneService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _tier_for_value(track: MilestoneTrack, value: int) -> int:
        return sum(1 for t in track.thresholds if value >= t)

    async def increment(
        self,
        guild_id: int,
        key: str,
        amount: int = 1,
        *,
        source: str = "system",
        actor_id: Optional[int] = None,
    ) -> List[dict]:
        """
        Increment a guild milestone key and return newly completed tiers.
        """
        if amount <= 0:
            return []
        track = TRACKS.get(key)
        if not track:
            return []

        row = await self.db.fetchrow(
            """INSERT INTO server_milestones(guild_id, key, value, tier_reached)
               VALUES($1, $2, 0, 0)
               ON CONFLICT (guild_id, key) DO UPDATE SET key=EXCLUDED.key
               RETURNING value, tier_reached""",
            guild_id, key,
        )
        old_value = int(row["value"] or 0)
        old_tier = int(row["tier_reached"] or 0)
        new_value = old_value + int(amount)
        new_tier = self._tier_for_value(track, new_value)

        await self.db.execute(
            """UPDATE server_milestones
               SET value=$3, tier_reached=$4, updated_at=NOW()
               WHERE guild_id=$1 AND key=$2""",
            guild_id, key, new_value, new_tier,
        )
        await self.db.execute(
            """INSERT INTO milestone_log(guild_id, key, amount, before_value, after_value, source, actor_id)
               VALUES($1,$2,$3,$4,$5,$6,$7)""",
            guild_id, key, amount, old_value, new_value, source, actor_id,
        )

        completions: List[dict] = []
        if new_tier <= old_tier:
            return completions

        for tier in range(old_tier + 1, new_tier + 1):
            target = track.thresholds[tier - 1]
            reward = await self._activate_reward(guild_id, track.key, tier)
            completions.append(
                {
                    "key": key,
                    "title": track.title,
                    "tier": tier,
                    "target": target,
                    "reward": reward,
                    "value": new_value,
                }
            )
        return completions

    async def _activate_reward(self, guild_id: int, key: str, tier: int) -> dict:
        """
        Tier reward pattern:
        1 -> +5% XP 12h
        2 -> +10% Gold 12h
        3 -> event unlock (announcement only)
        4 -> +10% XP 24h
        5 -> +15% Gold 24h
        """
        if tier == 1:
            return await self._grant_buff(guild_id, key, "xp_multiplier", 0.05, 12, "XP Surge +5% for 12h")
        if tier == 2:
            return await self._grant_buff(guild_id, key, "gold_multiplier", 0.10, 12, "Gold Rush +10% for 12h")
        if tier == 3:
            return {"type": "event_unlock", "label": "Special world event unlocked"}
        if tier == 4:
            return await self._grant_buff(guild_id, key, "xp_multiplier", 0.10, 24, "XP Surge +10% for 24h")
        return await self._grant_buff(guild_id, key, "gold_multiplier", 0.15, 24, "Gold Rush +15% for 24h")

    async def _grant_buff(self, guild_id: int, key: str, buff_type: str, buff_value: float, hours: int, label: str) -> dict:
        await self.db.execute(
            """INSERT INTO server_buffs(guild_id, buff_type, buff_value, expires_at, source_key)
               VALUES($1, $2, $3, NOW() + ($4 || ' hours')::INTERVAL, $5)""",
            guild_id, buff_type, buff_value, str(hours), key,
        )
        return {
            "type": "buff",
            "buff_type": buff_type,
            "buff_value": buff_value,
            "hours": hours,
            "label": label,
        }

    async def get_active_multipliers(self, guild_id: int) -> dict:
        row = await self.db.fetchrow(
            """SELECT
                 COALESCE(SUM(CASE WHEN buff_type='xp_multiplier' THEN buff_value ELSE 0 END), 0) AS xp_bonus,
                 COALESCE(SUM(CASE WHEN buff_type='gold_multiplier' THEN buff_value ELSE 0 END), 0) AS gold_bonus
               FROM server_buffs
               WHERE guild_id=$1 AND expires_at > NOW()""",
            guild_id,
        )
        xp_bonus = float(row["xp_bonus"] or 0.0)
        gold_bonus = float(row["gold_bonus"] or 0.0)
        return {
            "xp_multiplier": 1.0 + xp_bonus,
            "gold_multiplier": 1.0 + gold_bonus,
            "xp_bonus_pct": xp_bonus * 100.0,
            "gold_bonus_pct": gold_bonus * 100.0,
        }

    async def get_progress(self, guild_id: int) -> List[dict]:
        rows = await self.db.fetch(
            "SELECT key, value, tier_reached FROM server_milestones WHERE guild_id=$1",
            guild_id,
        )
        by_key = {r["key"]: r for r in rows}
        out: List[dict] = []
        for key, track in TRACKS.items():
            row = by_key.get(key)
            value = int((row["value"] if row else 0) or 0)
            tier = int((row["tier_reached"] if row else 0) or 0)
            next_target = None
            for t in track.thresholds:
                if value < t:
                    next_target = t
                    break
            out.append(
                {
                    "key": key,
                    "title": track.title,
                    "value": value,
                    "unit": track.unit,
                    "tier": tier,
                    "next_target": next_target,
                    "max_tier": len(track.thresholds),
                }
            )
        return out

    async def get_active_buffs(self, guild_id: int) -> List[dict]:
        rows = await self.db.fetch(
            """SELECT buff_type, buff_value, expires_at
               FROM server_buffs
               WHERE guild_id=$1 AND expires_at > NOW()
               ORDER BY expires_at ASC""",
            guild_id,
        )
        return [dict(r) for r in rows]

    @staticmethod
    async def announce_completions(bot, guild_id: int, completions: List[dict]) -> None:
        """Post milestone completion announcements to the server announce channel."""
        if not completions:
            return
        guild = bot.get_guild(guild_id)
        if not guild:
            return

        channel = None
        try:
            if hasattr(bot, "channels"):
                ch_id = bot.channels.get_channel_id(guild_id, "general")
                if ch_id:
                    channel = guild.get_channel(ch_id)
        except Exception:
            channel = None

        if channel is None:
            channel = guild.system_channel
        if channel is None:
            for ch in guild.text_channels:
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.embed_links:
                    channel = ch
                    break
        if channel is None:
            return

        for c in completions:
            reward = c.get("reward", {})
            reward_label = reward.get("label", reward.get("type", "reward"))
            embed = {
                "title": "🏁 Server Milestone Reached!",
                "description": (
                    f"**{c['title']}** reached **Tier {c['tier']}**\n"
                    f"Target: **{c['target']:,}** | Current: **{c['value']:,}**"
                ),
                "color": 0xF1C40F,
            }
            try:
                import discord

                msg = discord.Embed(
                    title=embed["title"],
                    description=embed["description"],
                    color=embed["color"],
                )
                msg.add_field(name="🎁 Reward", value=reward_label, inline=False)
                msg.set_footer(text="Server-wide bonus activated")
                await channel.send(embed=msg)
            except Exception:
                # Don't break gameplay flow due to announcement failures.
                continue
