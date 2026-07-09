"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         cogs/achievements/achievements_cog.py — /achievements command        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import Settings
from services.achievement.achievement_service import AchievementService
from services.character.character_service import CharacterService

log = logging.getLogger("cog.achievements")


class AchievementsCog(commands.Cog, name="Achievements"):
    def __init__(self, bot):
        self.bot = bot
        self.ach_svc: AchievementService = None
        self.char_svc: CharacterService = None

    async def cog_load(self):
        self.ach_svc = AchievementService(self.bot.db)
        self.char_svc = CharacterService(self.bot.db)

    @app_commands.command(name="achievements", description="View your achievements and badges")
    @app_commands.describe(category="Filter by category", member="View another player's achievements")
    @app_commands.choices(category=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Leveling", value="leveling"),
        app_commands.Choice(name="Combat", value="combat"),
        app_commands.Choice(name="Exploration", value="exploration"),
        app_commands.Choice(name="Economy", value="economy"),
        app_commands.Choice(name="Dungeon", value="dungeon"),
        app_commands.Choice(name="Items", value="items"),
        app_commands.Choice(name="Guild", value="guild"),
        app_commands.Choice(name="Secret", value="secret"),
    ])
    async def achievements(
        self,
        interaction: discord.Interaction,
        category: Optional[str] = "all",
        member: Optional[discord.Member] = None
    ):
        if not interaction.response.is_done():
            await interaction.response.defer()
        target = member or interaction.user
        char = await self.char_svc.get_character(target.id)
        if not char:
            return await interaction.followup.send("❌ No character found.", ephemeral=True)

        # Get earned achievements
        earned = await self.ach_svc.get_character_achievements(char["id"])
        earned_ids = {a["id"] for a in earned}
        
        # Get all achievements (filtered by category if specified)
        all_achievements = await self.ach_svc.get_all_achievements(
            category if category and category != "all" else None
        )
        
        # Calculate stats
        total_points = await self.ach_svc.get_total_points(char["id"])
        earned_count = len(earned)
        total_count = len(all_achievements)
        completion = int((earned_count / total_count * 100) if total_count > 0 else 0)
        
        # Build embed
        embed = discord.Embed(
            title=f"🏆 Achievements — {char['name']}",
            description=f"**{earned_count}/{total_count}** earned • **{total_points}** points • **{completion}%** complete",
            color=Settings.COLORS["reward"],
        )
        
        # Group by category
        categories = {}
        for ach in all_achievements:
            cat = ach.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(ach)
        
        # Display each category
        for cat_name, ach_list in sorted(categories.items()):
            lines = []
            for ach in sorted(ach_list, key=lambda x: x["points"], reverse=True):
                icon = ach.get("icon", "🏆")
                name = ach["name"]
                points = ach.get("points", 0)
                is_earned = ach["id"] in earned_ids
                is_secret = ach.get("secret", False) and not is_earned
                
                if is_secret:
                    lines.append(f"❓ **???** • {points} pts")
                elif is_earned:
                    earned_ach = next((e for e in earned if e["id"] == ach["id"]), None)
                    lines.append(f"{icon} ✅ **{name}** • {points} pts")
                else:
                    # Show progress
                    progress = await self.ach_svc.get_achievement_progress(char["id"], ach["id"])
                    if progress:
                        pct = progress.get("percent", 0)
                        current = progress.get("current", 0)
                        target = progress.get("target", 0)
                        lines.append(f"{icon} ⏳ **{name}** • {current}/{target} ({pct}%) • {points} pts")
                    else:
                        lines.append(f"{icon} ⬜ **{name}** • {points} pts")
            
            if lines:
                cat_display = cat_name.replace("_", " ").title()
                embed.add_field(
                    name=f"{cat_display} ({len([a for a in ach_list if a['id'] in earned_ids])}/{len(ach_list)})",
                    value="\n".join(lines[:10]),  # Limit to 10 per field
                    inline=False,
                )
        
        embed.set_footer(text=f"Use /achievements [category] to filter")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="badges", description="View your earned badges")
    async def badges(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        if not interaction.response.is_done():
            await interaction.response.defer()
        target = member or interaction.user
        char = await self.char_svc.get_character(target.id)
        if not char:
            return await interaction.followup.send("❌ No character found.", ephemeral=True)

        earned = await self.ach_svc.get_character_achievements(char["id"])
        
        if not earned:
            return await interaction.followup.send(
                f"❌ **{char['name']}** hasn't earned any badges yet!",
                ephemeral=True
            )
        
        # Sort by points (highest first)
        earned_sorted = sorted(earned, key=lambda x: x.get("points", 0), reverse=True)
        
        embed = discord.Embed(
            title=f"🎖️ Badges — {char['name']}",
            description=f"**{len(earned)}** badges earned",
            color=Settings.COLORS["reward"],
        )
        
        # Display badges in a grid (3 columns)
        badge_lines = []
        for ach in earned_sorted[:30]:  # Limit to 30 badges
            icon = ach.get("icon", "🏆")
            name = ach["name"]
            points = ach.get("points", 0)
            badge_lines.append(f"{icon} **{name}** ({points} pts)")
        
        # Split into chunks of 3 for inline display
        for i in range(0, len(badge_lines), 10):
            chunk = badge_lines[i:i+10]
            embed.add_field(
                name=f"Badges {i+1}-{min(i+10, len(badge_lines))}",
                value="\n".join(chunk),
                inline=False,
            )
        
        total_points = await self.ach_svc.get_total_points(char["id"])
        embed.set_footer(text=f"Total: {total_points} achievement points")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AchievementsCog(bot))
