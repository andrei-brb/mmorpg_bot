"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      cogs/events/events_cog.py — World events, daily quests, timers        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging, random
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config.settings import Settings, ZONES
from services.character.character_service import CharacterService

log = logging.getLogger("cog.events")

# World event templates
WORLD_EVENTS = {
    "demon_invasion": {
        "name": "Demon Invasion",
        "description": "A demonic rift has opened! Demons pour into the land. Extra XP and loot for all kills!",
        "emoji": "😈",
        "duration_hours": 2,
        "xp_bonus": 0.5,
        "gold_bonus": 0.25,
    },
    "merchants_festival": {
        "name": "Merchant's Festival",
        "description": "Travelling merchants have set up shop! Vendor prices reduced and rare items available.",
        "emoji": "🎪",
        "duration_hours": 4,
        "xp_bonus": 0.0,
        "gold_bonus": 0.5,
    },
    "ancient_curse": {
        "name": "Ancient Curse",
        "description": "An ancient curse grips the land. Enemies are stronger but rewards are doubled!",
        "emoji": "💀",
        "duration_hours": 3,
        "xp_bonus": 1.0,
        "gold_bonus": 1.0,
    },
    "blessing_of_light": {
        "name": "Blessing of the Light",
        "description": "A divine blessing bathes the realm! All healing is 50% more effective.",
        "emoji": "✨",
        "duration_hours": 2,
        "xp_bonus": 0.25,
        "gold_bonus": 0.0,
    },
}

class EventsCog(commands.Cog, name="Events"):
    def __init__(self, bot):
        self.bot = bot
        self.svc: CharacterService = None
        self.active_event: dict = None

    async def cog_load(self):
        self.svc = CharacterService(self.bot.db)
        self.world_event_loop.start()
        self.boss_respawn_loop.start()
        self.daily_reset_loop.start()
        log.info("Event loops started.")

    def cog_unload(self):
        self.world_event_loop.cancel()
        self.boss_respawn_loop.cancel()
        self.daily_reset_loop.cancel()

    # ── Tasks ─────────────────────────────────────────────────────────────────

    @tasks.loop(hours=6)
    async def world_event_loop(self):
        """Start a random world event every 6 hours."""
        key = random.choice(list(WORLD_EVENTS.keys()))
        event = WORLD_EVENTS[key]
        ends_at = datetime.now(timezone.utc) + timedelta(hours=event["duration_hours"])

        await self.bot.db.execute(
            "INSERT INTO world_events(event_key,name,description,is_active,ends_at) VALUES($1,$2,$3,TRUE,$4)",
            key, event["name"], event["description"], ends_at,
        )
        self.active_event = {**event, "key": key, "ends_at": ends_at}
        log.info(f"World event started: {event['name']}")

        # Announce to all servers that have an announcement channel
        servers = await self.bot.db.fetch("SELECT announce_channel_id FROM server_config WHERE announce_channel_id IS NOT NULL")
        for srv in servers:
            try:
                ch = self.bot.get_channel(srv["announce_channel_id"])
                if ch:
                    embed = discord.Embed(
                        title=f"{event['emoji']} World Event: {event['name']}",
                        description=event["description"],
                        color=0xFF8C00,
                    )
                    embed.add_field(name="Duration", value=f"{event['duration_hours']} hours")
                    if event["xp_bonus"]:  embed.add_field(name="⚡ XP Bonus",  value=f"+{int(event['xp_bonus']*100)}%")
                    if event["gold_bonus"]: embed.add_field(name="🪙 Gold Bonus", value=f"+{int(event['gold_bonus']*100)}%")
                    await ch.send(embed=embed)
            except Exception as e:
                log.warning(f"Could not announce to channel: {e}")

    @tasks.loop(hours=1)
    async def boss_respawn_loop(self):
        """Respawn bosses in zones where they've been killed."""
        await self.bot.db.execute(
            """UPDATE zone_state SET boss_alive=TRUE
               WHERE boss_alive=FALSE AND (boss_next_spawn IS NULL OR boss_next_spawn <= NOW())"""
        )

    @tasks.loop(hours=24)
    async def daily_reset_loop(self):
        """Reset daily quests and zone kill counts."""
        await self.bot.db.execute("UPDATE zone_state SET kills_today=0")
        await self.bot.db.execute(
            "UPDATE character_quests SET is_complete=FALSE, progress='{}', completed_at=NULL "
            "WHERE quest_id IN (SELECT id FROM quest_templates WHERE quest_type='daily')"
        )
        log.info("Daily reset complete.")

    @world_event_loop.before_loop
    @boss_respawn_loop.before_loop
    @daily_reset_loop.before_loop
    async def wait_ready(self): await self.bot.wait_until_ready()

    # ── Commands ──────────────────────────────────────────────────────────────

    @app_commands.command(name="events", description="View active world events")
    async def events(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        active = await self.bot.db.fetch(
            "SELECT * FROM world_events WHERE is_active=TRUE AND ends_at>NOW() ORDER BY started_at DESC LIMIT 5"
        )
        if not active:
            embed = discord.Embed(title="📅 World Events", description="No active events. Check back later!", color=0x2F3136)
            return await interaction.followup.send(embed=embed)

        embed = discord.Embed(title="📅 Active World Events", color=0xFF8C00)
        for ev in active:
            key = ev["event_key"]
            tmpl = WORLD_EVENTS.get(key, {})
            emoji = tmpl.get("emoji", "🌍")
            remaining = ev["ends_at"] - datetime.now(timezone.utc)
            hours = int(remaining.total_seconds() // 3600)
            mins  = int((remaining.total_seconds() % 3600) // 60)
            embed.add_field(
                name=f"{emoji} {ev['name']}",
                value=f"{ev['description']}\n⏰ Ends in **{hours}h {mins}m**",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="daily", description="View and claim your daily quest")
    async def daily(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")

        # Check/create a daily quest for this character
        quest = await self.bot.db.fetchrow(
            """SELECT cq.*, qt.name, qt.description, qt.objectives, qt.rewards
               FROM character_quests cq JOIN quest_templates qt ON cq.quest_id=qt.id
               WHERE cq.character_id=$1 AND qt.quest_type='daily'
               AND cq.started_at::date = CURRENT_DATE
               LIMIT 1""", char["id"]
        )
        if not quest:
            embed = discord.Embed(
                title="📋 Daily Quest",
                description="No daily quest assigned yet. Explore to receive daily quests!",
                color=0x2F3136,
            )
        elif quest["is_complete"]:
            embed = discord.Embed(
                title="📋 Daily Quest — ✅ Complete!",
                description=f"**{quest['name']}** — Already completed today!\nReturns tomorrow at midnight UTC.",
                color=0x00FF7F,
            )
        else:
            embed = discord.Embed(
                title=f"📋 Daily Quest: {quest['name']}",
                description=quest["description"],
                color=0xFFD700,
            )
            import json
            objectives = quest["objectives"] if isinstance(quest["objectives"], list) else json.loads(quest["objectives"])
            progress   = quest["progress"]   if isinstance(quest["progress"], dict) else json.loads(quest["progress"])
            obj_text = "\n".join(
                f"• {obj.get('description','?')} — {progress.get(obj.get('id',''), 0)}/{obj.get('count',1)}"
                for obj in objectives
            )
            embed.add_field(name="Objectives", value=obj_text or "None", inline=False)
            rewards = quest["rewards"] if isinstance(quest["rewards"], dict) else json.loads(quest["rewards"])
            embed.add_field(name="Rewards", value=f"+{rewards.get('xp',0)} XP | +{rewards.get('gold',0)}🪙", inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="login", description="Claim your daily login reward")
    async def daily_login(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character — use `/character create`.", ephemeral=True)

        from services.daily.daily_login_service import DailyLoginService
        login_svc = DailyLoginService(self.bot.db)
        
        result = await login_svc.claim_daily_reward(char["id"])
        
        if not result["claimed"]:
            embed = discord.Embed(
                title="🎁 Daily Login",
                description=result["message"],
                color=0xFFD700,
            )
            if result.get("next_claim"):
                embed.set_footer(text=f"Next claim: {result['next_claim']}")
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Award rewards
        await self.svc.award_xp(char["id"], result["xp"])
        await self.svc.add_gold(char["id"], result["gold"], "daily_login")
        
        # Build embed
        streak_emoji = "🔥" if result["current_streak"] >= 7 else "⭐" if result["current_streak"] >= 3 else "✨"
        streak_text = f"{streak_emoji} {result['current_streak']} day streak!"
        if not result["streak_maintained"]:
            streak_text = f"✨ New streak started! {streak_text}"
        
        embed = discord.Embed(
            title="🎁 Daily Login Reward Claimed!",
            description=streak_text,
            color=0xFFD700,
        )
        
        embed.add_field(
            name="💰 Rewards",
            value=f"**{result['gold']:,}**🪙 gold\n**{result['xp']:,}**⭐ XP",
            inline=True,
        )
        
        embed.add_field(
            name="📊 Streak Stats",
            value=f"Current: **{result['current_streak']}** days\nLongest: **{result['longest_streak']}** days",
            inline=True,
        )
        
        # Show milestone bonuses
        bonuses = []
        if result["current_streak"] % 7 == 0:
            bonuses.append("🎉 **7-Day Milestone Bonus!**")
        if result["current_streak"] % 30 == 0:
            bonuses.append("🏆 **30-Day Milestone Bonus!**")
        if bonuses:
            embed.add_field(name="✨ Milestones", value="\n".join(bonuses), inline=False)
        
        embed.set_footer(text=f"Next claim: {result['next_claim']}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="streak", description="View your login streak")
    async def streak(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character — use `/character create`.", ephemeral=True)

        from services.daily.daily_login_service import DailyLoginService
        login_svc = DailyLoginService(self.bot.db)
        
        streak_data = await login_svc.get_streak(char["id"])
        
        embed = discord.Embed(
            title="🔥 Login Streak",
            description=f"**{char['name']}**'s login statistics",
            color=0xFFD700,
        )
        
        embed.add_field(
            name="Current Streak",
            value=f"🔥 **{streak_data['current_streak']}** days",
            inline=True,
        )
        
        embed.add_field(
            name="Longest Streak",
            value=f"🏆 **{streak_data['longest_streak']}** days",
            inline=True,
        )
        
        embed.add_field(
            name="Total Logins",
            value=f"📊 **{streak_data.get('total_logins', 0)}** days",
            inline=True,
        )
        
        if streak_data.get("last_login"):
            last_login = streak_data["last_login"]
            if isinstance(last_login, str):
                from datetime import datetime
                last_login = datetime.fromisoformat(last_login.replace('Z', '+00:00'))
            embed.add_field(
                name="Last Login",
                value=f"🕐 {last_login.strftime('%Y-%m-%d %H:%M')}",
                inline=False,
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot): await bot.add_cog(EventsCog(bot))
