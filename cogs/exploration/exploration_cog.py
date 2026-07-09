"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   cogs/exploration/exploration_cog.py — /explore /travel /map              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging, random
from uuid import UUID
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import ZONES, Settings
from services.character.character_service import CharacterService
from services.exploration.zone_explore import roll_explore_outcome
from services.reward_multipliers import get_combined_reward_multipliers

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
        if interaction.guild_id:
            await self.svc.set_last_discord_guild(char["id"], interaction.guild_id)
        
        # Auto-fix stuck combat status (no active fight but status says in_combat)
        if char["combat_status"] == "in_combat":
            from cogs.combat.combat_cog import ACTIVE
            channel_has_combat = interaction.channel_id in ACTIVE
            if not channel_has_combat:
                # Stuck in combat - clear it automatically
                await self.bot.db.execute(
                    "UPDATE characters SET combat_status='idle' WHERE id=$1",
                    char["id"],
                )
                # Refresh char data
                char = await self.svc.get_character(interaction.user.id)
            else:
                return await interaction.followup.send("⚔️ Finish your fight first!")

        cd = await self.svc.on_cooldown(char["id"], "explore")
        if cd: return await interaction.followup.send(f"⏳ Explore again in **{int(cd)}s**.", ephemeral=True)

        zone = ZONES.get(char["current_zone"])
        if not zone: return await interaction.followup.send("❌ Unknown zone.")
        if char["level"] < zone.level_range[0]:
            return await interaction.followup.send(f"❌ Need level **{zone.level_range[0]}** for this zone.")

        await self.bot.db.execute(
            "UPDATE zone_state SET active_players=active_players+1, kills_today=kills_today+1 WHERE zone_key=$1",
            char["current_zone"]
        )

        ig = UUID(str(char["guild_id"])) if char.get("guild_id") else None
        xp_mult, gold_mult, boss_add = await get_combined_reward_multipliers(
            self.bot.db, interaction.guild_id, ingame_guild_id=ig
        )
        from services.world_boss.world_boss_service import WorldBossService

        wbs = WorldBossService(self.bot.db)
        zone_patrol = await WorldBossService.fetch_zone_patrol_boss_alive(self.bot.db, char["current_zone"])
        world_key = await wbs.active_window_boss_for_zone(interaction.guild_id, char["current_zone"])
        if world_key:
            boss_add = min(boss_add + 0.08, 0.15)
        outcome = roll_explore_outcome(
            zone,
            boss_add,
            zone_patrol_boss_alive=zone_patrol,
            world_boss_key=world_key,
        )
        embed = discord.Embed(title=f"{zone.emoji} Exploring {zone.name}", description=random.choice(zone.ambients), color=0x2F7F3F)

        # Set cooldown based on outcome: 10s for rewards, 30s for encounters
        if outcome["type"] in ["enemy", "boss"]:
            cooldown = Settings.EXPLORE_COOLDOWN  # 30 seconds for encounters
        else:
            cooldown = 10  # 10 seconds for rewards only (loot/safe)
        
        await self.svc.set_cooldown(char["id"], "explore", cooldown)

        if outcome["type"] == "enemy":
            embed.add_field(name="⚔️ Enemy Encountered!", value=f"A **{outcome['name']}** attacks!\nUse `/fight` to engage.", inline=False)
            embed.color = 0xFF4444
        elif outcome["type"] == "boss":
            # Store the encountered boss so /fight can auto-start with it
            await self.bot.db.execute(
                "UPDATE characters SET pending_encounter=$2 WHERE id=$1",
                char["id"], outcome["key"]
            )
            embed.add_field(name="💀 BOSS NEARBY!", value=f"The fearsome **{outcome['name']}** lurks here!\nUse `/fight` to challenge it!", inline=False)
            embed.color = 0xFF0000
        elif outcome["type"] == "loot":
            xp0, g0 = random.randint(5, 15 + char["level"]), random.randint(1, 5 + char["level"] // 2)
            xp_result = await self.svc.award_xp(char["id"], xp0, xp_mult)
            gold = int(g0 * gold_mult)
            await self.svc.add_gold(char["id"], gold, "exploration")
            xp_eff = int(xp_result.get("xp_gained") or 0)
            scrap_line = ""
            # Gathering: crafting materials are farmable through exploration,
            # not only via salvaging gear drops.
            if random.random() < 0.35:
                from services.character.inventory_service import InventoryService
                scrap_tid = random.choice(("weapon_scrap", "armor_scrap", "accessory_scrap"))
                scrap_qty = random.randint(1, 2)
                inv_svc = InventoryService(self.bot.db)
                ok, _ = await inv_svc.add_item(
                    char["id"], scrap_tid, "common", quantity=scrap_qty, from_="gathering"
                )
                if ok:
                    scrap_name = scrap_tid.replace("_", " ").title()
                    scrap_line = f" | +**{scrap_qty}** 🔩 {scrap_name}"
            embed.add_field(
                name="✨ Discovery!",
                value=f"You find hidden resources!\n+**{xp_eff}** XP | +**{gold}**🪙{scrap_line}",
                inline=False,
            )
        else:
            xp0 = random.randint(3, 8)
            xp_result = await self.svc.award_xp(char["id"], xp0, xp_mult)
            xp_eff = int(xp_result.get("xp_gained") or 0)
            embed.add_field(
                name="🌿 Quiet Journey",
                value=f"Nothing eventful, but the trek builds experience.\n+**{xp_eff}** XP",
                inline=False,
            )

        # ── NPC Encounter Roll ────────────────────────────────────────────
        try:
            from services.quest.npc_quest_service import NPCQuestService
            npc_svc = NPCQuestService(self.bot.db)
            npc_encounter = await npc_svc.roll_npc_encounter(char["id"], char["current_zone"])

            if npc_encounter:
                npc_id = npc_encounter["npc_id"]
                npc_data = npc_encounter["npc_data"]
                already_met = npc_encounter["already_met"]

                if not already_met:
                    embed.add_field(
                        name="💬 Stranger Sighted!",
                        value=(
                            f"*{npc_data['discovery_hint']}*\n\n"
                            f"Use `/interact {npc_data['name'].split()[0].lower()}` to approach them."
                        ),
                        inline=False,
                    )
                    await npc_svc.discover_npc(char["id"], npc_id, char["current_zone"])
                else:
                    embed.add_field(
                        name=f"💬 {npc_data['name']}",
                        value=f"You see a familiar face.\nUse `/interact {npc_data['name'].split()[0].lower()}` to talk.",
                        inline=False,
                    )
        except Exception as e:
            log.warning(f"NPC encounter roll failed: {e}")

        # Daily quest progress (non-blocking)
        try:
            from services.quest.daily_quest_service import DailyQuestService
            daily_line = await DailyQuestService(self.bot.db).record_event(self.svc, char["id"], "explore")
            if daily_line:
                embed.add_field(name="📋 Daily Quest", value=daily_line, inline=False)
        except Exception:
            pass

        embed.set_footer(text=f"Cooldown: {cooldown}s | Use /travel to change zones")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Check exploration achievements
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        await ach_svc.check_and_award(char["id"], "explore", {})

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
        if interaction.guild_id:
            await self.svc.set_last_discord_guild(char["id"], interaction.guild_id)
        if char["current_zone"] == zone: return await interaction.followup.send(f"You're already in **{ZONES[zone].name}**!")
        z = ZONES[zone]
        if char["level"] < z.level_range[0]:
            return await interaction.followup.send(f"❌ Need level **{z.level_range[0]}** for **{z.name}**. You are level **{char['level']}**.")

        await self.bot.db.execute(
            "UPDATE zone_state SET active_players=GREATEST(0,active_players-1) WHERE zone_key=$1", char["current_zone"]
        )
        await self.bot.db.execute("UPDATE characters SET current_zone=$2 WHERE id=$1", char["id"], zone)

        embed = discord.Embed(title=f"🗺️ Arrived in {z.emoji} {z.name}", description=z.description, color=Settings.COLORS["info"])
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
            # Count actual characters currently in this zone
            players = await self.bot.db.fetchval(
                "SELECT COUNT(*) FROM characters WHERE current_zone=$1 AND is_active=TRUE",
                key
            ) or 0
            # Also get boss status
            zs = await self.bot.db.fetchrow("SELECT boss_alive FROM zone_state WHERE zone_key=$1", key)
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
