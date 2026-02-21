"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/exploration/exploration_cog.py — /explore /travel /map              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging, random
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import ZONES, Settings
from services.character.character_service import CharacterService

log = logging.getLogger("cog.exploration")

class ExplorationCog(commands.Cog, name="Exploration"):
    def __init__(self, bot): self.bot = bot; self.svc: CharacterService = None
    async def cog_load(self): self.svc = CharacterService(self.bot.db)

    @app_commands.command(name="explore", description="Explore your current zone")
    async def explore(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return  # Blocked - error message already sent
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character — use `/character create`.")
        if char["combat_status"] == "in_combat": return await interaction.followup.send("⚔️ Finish your fight first!")

        cd = await self.svc.on_cooldown(char["id"], "explore")
        if cd: return await interaction.followup.send(f"⏳ Explore again in **{int(cd)}s**.", ephemeral=True)

        zone = ZONES.get(char["current_zone"])
        if not zone: return await interaction.followup.send("❌ Unknown zone.")
        if char["level"] < zone.level_range[0]:
            return await interaction.followup.send(f"❌ Need level **{zone.level_range[0]}** for this zone.")

        await self.svc.set_cooldown(char["id"], "explore", Settings.EXPLORE_COOLDOWN)
        await self.bot.db.execute(
            "UPDATE zone_state SET active_players=active_players+1, kills_today=kills_today+1 WHERE zone_key=$1",
            char["current_zone"]
        )

        outcome = self._roll(char["level"], zone)
        embed = discord.Embed(title=f"{zone.emoji} Exploring {zone.name}", description=random.choice(zone.ambients), color=0x2F7F3F)

        if outcome["type"] == "enemy":
            embed.add_field(name="⚔️ Enemy Encountered!", value=f"A **{outcome['name']}** attacks!\nUse `/fight {outcome['key']}` to engage.", inline=False)
            embed.color = 0xFF4444
        elif outcome["type"] == "boss":
            embed.add_field(name="💀 BOSS NEARBY!", value=f"The fearsome **{outcome['name']}** lurks here!\nUse `/fight {outcome['key']}` to challenge it!", inline=False)
            embed.color = 0xFF0000
        elif outcome["type"] == "loot":
            xp, gold = random.randint(5, 15 + char["level"]), random.randint(1, 5 + char["level"] // 2)
            await self.svc.award_xp(char["id"], xp)
            await self.svc.add_gold(char["id"], gold, "exploration")
            embed.add_field(name="✨ Discovery!", value=f"You find hidden resources!\n+**{xp}** XP | +**{gold}**🪙", inline=False)
        else:
            xp = random.randint(3, 8)
            await self.svc.award_xp(char["id"], xp)
            embed.add_field(name="🌿 Quiet Journey", value=f"Nothing eventful, but the trek builds experience.\n+**{xp}** XP", inline=False)

        embed.set_footer(text=f"Cooldown: {Settings.EXPLORE_COOLDOWN}s | Use /travel to change zones")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Check exploration achievements
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        await ach_svc.check_and_award(char["id"], "explore", {})

    def _roll(self, level, zone) -> dict:
        r = random.random()
        if r < 0.40:
            key = random.choice(zone.enemies)
            return {"type": "enemy", "key": key, "name": key.replace("_", " ").title()}
        elif r < 0.55:
            key = random.choice(zone.bosses)
            return {"type": "boss", "key": key, "name": key.replace("_", " ").title()}
        elif r < 0.75:
            return {"type": "loot"}
        return {"type": "safe"}

    @app_commands.command(name="travel", description="Travel to a different zone")
    @app_commands.choices(zone=[
        app_commands.Choice(name=f"{z.emoji} {z.name} (Lv {z.level_range[0]}-{z.level_range[1]})", value=k)
        for k, z in ZONES.items()
    ])
    async def travel(self, interaction: discord.Interaction, zone: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return  # Blocked - error message already sent
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        if char["current_zone"] == zone: return await interaction.followup.send(f"You're already in **{ZONES[zone].name}**!")
        z = ZONES[zone]
        if char["level"] < z.level_range[0]:
            return await interaction.followup.send(f"❌ Need level **{z.level_range[0]}** for **{z.name}**. You are level **{char['level']}**.")

        await self.bot.db.execute(
            "UPDATE zone_state SET active_players=GREATEST(0,active_players-1) WHERE zone_key=$1", char["current_zone"]
        )
        await self.bot.db.execute("UPDATE characters SET current_zone=$2 WHERE id=$1", char["id"], zone)

        embed = discord.Embed(title=f"🗺️ Arrived in {z.emoji} {z.name}", description=z.description, color=0x4488FF)
        embed.add_field(name="Level Range", value=f"{z.level_range[0]}–{z.level_range[1]}", inline=True)
        embed.add_field(name="Faction", value=z.faction.title(), inline=True)
        embed.add_field(name="Known Enemies", value=", ".join(k.replace("_"," ").title() for k in z.enemies), inline=False)
        if z.bosses: embed.add_field(name="⚠️ Bosses", value=", ".join(b.replace("_"," ").title() for b in z.bosses), inline=False)
        embed.set_footer(text="Use /explore to begin your adventure here!")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="map", description="View the world map")
    async def world_map(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return  # Blocked - error message already sent
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        current = char["current_zone"] if char else None
        embed = discord.Embed(title="🗺️ World Map", description="All zones of the realm.", color=0x2F4F4F)
        for key, z in sorted(ZONES.items(), key=lambda x: x[1].level_range[0]):
            zs = await self.bot.db.fetchrow("SELECT active_players, boss_alive FROM zone_state WHERE zone_key=$1", key)
            players = zs["active_players"] if zs else 0
            boss = "⚠️ Boss alive" if (not zs or zs["boss_alive"]) else "✅ Boss defeated"
            marker = " 📍 **YOU**" if key == current else ""
            embed.add_field(
                name=f"{z.emoji} {z.name} [Lv {z.level_range[0]}-{z.level_range[1]}]{marker}",
                value=f"{z.description[:60]}…\n👥 {players} players | {boss} | {z.faction.title()}",
                inline=False,
            )
        embed.set_footer(text="Use /travel <zone> to move")
        await interaction.followup.send(embed=embed)

async def setup(bot): await bot.add_cog(ExplorationCog(bot))
