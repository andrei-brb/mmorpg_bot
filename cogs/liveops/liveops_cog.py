"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/liveops/liveops_cog.py — Per-guild configurable live events         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.channel_manager import interaction_user_is_guild_administrator
from services.live_events.live_event_service import LiveEventService

log = logging.getLogger("cog.liveops")


def _parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class LiveopsCog(commands.Cog, name="Liveops"):
    """Configurable server events (XP/gold multipliers, boss hunt, schedules)."""

    liveops_group = app_commands.Group(
        name="liveops",
        description="Configurable live events for this server (XP/gold/boss hunt, schedules)",
    )

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.live_event_tick.start()
        log.info("Live ops scheduler started.")

    def cog_unload(self):
        self.live_event_tick.cancel()

    async def _announce_channel(self, guild_id: int, override_id: Optional[int]) -> Optional[discord.TextChannel]:
        if override_id:
            ch = self.bot.get_channel(override_id)
            if isinstance(ch, discord.TextChannel):
                return ch
        row = await self.bot.db.fetchrow(
            "SELECT announce_channel_id FROM server_config WHERE server_id=$1",
            guild_id,
        )
        cid = row["announce_channel_id"] if row else None
        if cid:
            ch = self.bot.get_channel(int(cid))
            if isinstance(ch, discord.TextChannel):
                return ch
        return None

    @tasks.loop(minutes=1)
    async def live_event_tick(self):
        """Send start/end announcements and mark rows as sent."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            gid = guild.id
            try:
                # Start announcements
                rows = await self.bot.db.fetch(
                    """SELECT * FROM guild_live_events
                       WHERE guild_id=$1 AND enabled=TRUE
                         AND announce_on_start=TRUE AND announce_start_sent=FALSE
                         AND starts_at <= NOW() AND ends_at > NOW()""",
                    gid,
                )
                for ev in rows:
                    ch = await self._announce_channel(gid, ev["announce_channel_id"])
                    if ch:
                        cfg = ev["config"] if isinstance(ev["config"], dict) else {}
                        embed = discord.Embed(
                            title=f"🎉 Live Event: {ev['title']}",
                            description=ev["description"] or "",
                            color=0xFF8C00,
                        )
                        ts = int(ev["ends_at"].timestamp()) if ev.get("ends_at") else 0
                        if ts:
                            embed.add_field(name="Ends", value=f"<t:{ts}:R>", inline=True)
                        xp = float(cfg.get("xp_multiplier") or 1.0)
                        gd = float(cfg.get("gold_multiplier") or 1.0)
                        bc = float(cfg.get("explore_boss_chance_add") or 0.0)
                        if xp != 1.0:
                            embed.add_field(name="⚡ XP", value=f"×{xp:.2f}", inline=True)
                        if gd != 1.0:
                            embed.add_field(name="🪙 Gold", value=f"×{gd:.2f}", inline=True)
                        if bc > 0:
                            embed.add_field(name="💀 Explore", value=f"+{bc:.0%} boss chance", inline=True)
                        try:
                            await ch.send(embed=embed)
                        except Exception as e:
                            log.warning("live event start announce failed: %s", e)
                    await self.bot.db.execute(
                        "UPDATE guild_live_events SET announce_start_sent=TRUE WHERE id=$1",
                        ev["id"],
                    )

                # End announcements
                end_rows = await self.bot.db.fetch(
                    """SELECT * FROM guild_live_events
                       WHERE guild_id=$1 AND enabled=TRUE
                         AND announce_on_end=TRUE AND announce_end_sent=FALSE
                         AND ends_at <= NOW()""",
                    gid,
                )
                for ev in end_rows:
                    ch = await self._announce_channel(gid, ev["announce_channel_id"])
                    if ch:
                        embed = discord.Embed(
                            title=f"🏁 Event ended: {ev['title']}",
                            description="Thanks for playing!",
                            color=0x95A5A6,
                        )
                        try:
                            await ch.send(embed=embed)
                        except Exception as e:
                            log.warning("live event end announce failed: %s", e)
                    await self.bot.db.execute(
                        "UPDATE guild_live_events SET announce_end_sent=TRUE, enabled=FALSE WHERE id=$1",
                        ev["id"],
                    )
            except Exception as e:
                log.error("live_event_tick guild=%s: %s", gid, e, exc_info=True)

    @live_event_tick.before_loop
    async def _before_live_tick(self):
        await self.bot.wait_until_ready()

    @liveops_group.command(name="list", description="List configured live events")
    async def liveops_list(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        if not await interaction_user_is_guild_administrator(interaction):
            return await interaction.response.send_message("❌ **Administrator** permission required (or you must be the server owner).", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        svc = LiveEventService(self.bot.db)
        rows = await svc.list_all(interaction.guild_id)
        if not rows:
            return await interaction.followup.send("No events configured. Use `/liveops create`.", ephemeral=True)

        embed = discord.Embed(title="📅 Live events (this server)", color=0xFF8C00)
        for ev in rows[:15]:
            cfg = ev["config"] if isinstance(ev["config"], dict) else {}
            now = datetime.now(timezone.utc)
            st, en = ev["starts_at"], ev["ends_at"]
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            if en.tzinfo is None:
                en = en.replace(tzinfo=timezone.utc)
            active = ev["enabled"] and st <= now < en
            flag = "🟢" if active else ("⏳" if now < st else "⚪")
            bits = []
            if float(cfg.get("xp_multiplier") or 1) != 1:
                bits.append(f"XP×{float(cfg['xp_multiplier']):.2f}")
            if float(cfg.get("gold_multiplier") or 1) != 1:
                bits.append(f"Gold×{float(cfg['gold_multiplier']):.2f}")
            if float(cfg.get("explore_boss_chance_add") or 0) > 0:
                bits.append(f"Boss+{float(cfg['explore_boss_chance_add']):.0%}")
            embed.add_field(
                name=f"{flag} `{ev['slug']}` — {ev['title']}",
                value=(
                    f"{'**ACTIVE**' if active else ''}\n"
                    f"<t:{int(st.timestamp())}:f> → <t:{int(en.timestamp())}:f>\n"
                    f"{', '.join(bits) if bits else 'config'}\n"
                    f"enabled={ev['enabled']}"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @liveops_group.command(name="create", description="Create or replace a scheduled event by slug")
    @app_commands.describe(
        slug="Short id (lowercase, e.g. weekend_xp)",
        title="Display title",
        description="Optional description for announcements",
        duration_hours="How long the event runs",
        start_in_hours="Delay before start (0 = now)",
        xp_multiplier="XP multiplier (e.g. 2 for double XP)",
        gold_multiplier="Gold multiplier",
        boss_chance_add="Extra explore boss chance (0–0.15)",
        announce_channel="Optional channel override; else announce channel from server config",
    )
    async def liveops_create(
        self,
        interaction: discord.Interaction,
        slug: str,
        title: str,
        description: str = "",
        duration_hours: app_commands.Range[float, 0.5, 336.0] = 24.0,
        start_in_hours: app_commands.Range[float, 0.0, 720.0] = 0.0,
        xp_multiplier: float = 1.0,
        gold_multiplier: float = 1.0,
        boss_chance_add: app_commands.Range[float, 0.0, 0.15] = 0.0,
        announce_channel: Optional[discord.TextChannel] = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        if not await interaction_user_is_guild_administrator(interaction):
            return await interaction.response.send_message("❌ **Administrator** permission required (or you must be the server owner).", ephemeral=True)
        slug = slug.strip().lower()
        if not LiveEventService.validate_slug(slug):
            return await interaction.response.send_message(
                "❌ `slug` must be 2–63 chars: `a-z`, `0-9`, `_`, `-`",
                ephemeral=True,
            )
        if xp_multiplier <= 0 or gold_multiplier <= 0:
            return await interaction.response.send_message("❌ Multipliers must be > 0.", ephemeral=True)

        now = datetime.now(timezone.utc)
        starts = now + timedelta(hours=float(start_in_hours))
        ends = starts + timedelta(hours=float(duration_hours))
        cfg = {
            "xp_multiplier": float(xp_multiplier),
            "gold_multiplier": float(gold_multiplier),
            "explore_boss_chance_add": float(boss_chance_add),
        }
        svc = LiveEventService(self.bot.db)
        await svc.create_event(
            interaction.guild_id,
            slug,
            title,
            description=description,
            starts_at=starts,
            ends_at=ends,
            config=cfg,
            announce_on_start=True,
            announce_on_end=False,
            announce_channel_id=announce_channel.id if announce_channel else None,
            created_by=interaction.user.id,
        )
        await interaction.response.send_message(
            f"✅ Saved **`{slug}`** — active <t:{int(starts.timestamp())}:R> → <t:{int(ends.timestamp())}:R>.",
            ephemeral=True,
        )

    @liveops_group.command(name="schedule", description="Create/replace an event with explicit start/end (ISO 8601 UTC)")
    @app_commands.describe(
        slug="Short id",
        title="Display title",
        starts_at='Start time, e.g. 2026-03-30T18:00:00+00:00',
        ends_at='End time',
    )
    async def liveops_schedule(
        self,
        interaction: discord.Interaction,
        slug: str,
        title: str,
        starts_at: str,
        ends_at: str,
        description: str = "",
        xp_multiplier: float = 1.0,
        gold_multiplier: float = 1.0,
        boss_chance_add: app_commands.Range[float, 0.0, 0.15] = 0.0,
        announce_channel: Optional[discord.TextChannel] = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        if not await interaction_user_is_guild_administrator(interaction):
            return await interaction.response.send_message("❌ **Administrator** permission required (or you must be the server owner).", ephemeral=True)
        slug = slug.strip().lower()
        if not LiveEventService.validate_slug(slug):
            return await interaction.response.send_message("❌ Invalid `slug`.", ephemeral=True)
        try:
            st = _parse_iso(starts_at)
            en = _parse_iso(ends_at)
        except ValueError:
            return await interaction.response.send_message("❌ Could not parse datetimes. Use ISO 8601.", ephemeral=True)
        if en <= st:
            return await interaction.response.send_message("❌ `ends_at` must be after `starts_at`.", ephemeral=True)
        cfg = {
            "xp_multiplier": float(xp_multiplier),
            "gold_multiplier": float(gold_multiplier),
            "explore_boss_chance_add": float(boss_chance_add),
        }
        svc = LiveEventService(self.bot.db)
        await svc.create_event(
            interaction.guild_id,
            slug,
            title,
            description=description,
            starts_at=st,
            ends_at=en,
            config=cfg,
            announce_on_start=True,
            announce_on_end=True,
            announce_channel_id=announce_channel.id if announce_channel else None,
            created_by=interaction.user.id,
        )
        await interaction.response.send_message(f"✅ Scheduled **`{slug}`**.", ephemeral=True)

    @liveops_group.command(name="delete", description="Remove an event by slug")
    async def liveops_delete(self, interaction: discord.Interaction, slug: str):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        if not await interaction_user_is_guild_administrator(interaction):
            return await interaction.response.send_message("❌ **Administrator** permission required (or you must be the server owner).", ephemeral=True)
        svc = LiveEventService(self.bot.db)
        ok = await svc.delete_event(interaction.guild_id, slug.strip().lower())
        if ok:
            await interaction.response.send_message(f"🗑️ Deleted `{slug}`.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not found.", ephemeral=True)

    @liveops_group.command(name="disable", description="Disable an event without deleting")
    async def liveops_disable(self, interaction: discord.Interaction, slug: str):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        if not await interaction_user_is_guild_administrator(interaction):
            return await interaction.response.send_message("❌ **Administrator** permission required (or you must be the server owner).", ephemeral=True)
        svc = LiveEventService(self.bot.db)
        ok = await svc.disable_event(interaction.guild_id, slug.strip().lower())
        if ok:
            await interaction.response.send_message(f"⏹️ Disabled `{slug}`.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not found.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LiveopsCog(bot))
