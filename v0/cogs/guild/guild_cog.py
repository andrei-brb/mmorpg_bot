"""
╔══════════════════════════════════════════════════════════════════════════════╗
║            cogs/guild/guild_cog.py — /guild commands                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from services.character.character_service import CharacterService

log = logging.getLogger("cog.guild")

class GuildCog(commands.Cog, name="Guild"):
    def __init__(self, bot): self.bot = bot; self.svc: CharacterService = None
    async def cog_load(self): self.svc = CharacterService(self.bot.db)

    g = app_commands.Group(name="guild", description="Guild management")

    @g.command(name="create", description="Found a new guild")
    @app_commands.describe(name="Guild name", tag="2–8 uppercase letters/numbers")
    async def create(self, interaction: discord.Interaction, name: str, tag: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "guild"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ You need a character first.")
        if char["guild_id"]: return await interaction.followup.send("❌ You're already in a guild.")

        tag = tag.upper()
        if not (2 <= len(tag) <= 8) or not tag.isalnum():
            return await interaction.followup.send("❌ Tag must be 2–8 alphanumeric characters.")
        if not (3 <= len(name) <= 64):
            return await interaction.followup.send("❌ Guild name must be 3–64 characters.")

        exists = await self.bot.db.fetchrow("SELECT id FROM guilds WHERE name ILIKE $1 OR tag=$2", name, tag)
        if exists: return await interaction.followup.send("❌ That name or tag is already taken.")

        guild = await self.bot.db.fetchrow(
            "INSERT INTO guilds(name,tag,guildmaster_id,server_id) VALUES($1,$2,$3,$4) RETURNING *",
            name, tag, char["id"], interaction.guild_id,
        )
        await self.bot.db.execute(
            "UPDATE characters SET guild_id=$2, guild_rank='guildmaster' WHERE id=$1", char["id"], guild["id"]
        )
        
        # Check guild create achievement
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        await ach_svc.check_and_award(char["id"], "guild_create", {})
        
        embed = discord.Embed(title=f"🏰 [{tag}] {name} — Founded!", description=f"**{char['name']}** has founded a new guild!", color=0xFFD700)
        embed.add_field(name="Guildmaster", value=char["name"], inline=True)
        embed.add_field(name="Members", value="1", inline=True)
        embed.set_footer(text="Use /guild invite to recruit members")
        await interaction.followup.send(embed=embed)

    async def _sync_member_count(self, guild_id):
        """Sync member_count with actual member count."""
        actual_count = await self.bot.db.fetchval(
            "SELECT COUNT(*) FROM characters WHERE guild_id=$1",
            guild_id
        )
        await self.bot.db.execute(
            "UPDATE guilds SET member_count=$1 WHERE id=$2",
            actual_count or 0, guild_id
        )
        return actual_count or 0

    @g.command(name="info", description="View guild information")
    @app_commands.describe(name="Guild name (defaults to yours)")
    async def info(self, interaction: discord.Interaction, name: Optional[str] = None):
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)

        if name:
            guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE name ILIKE $1", name)
        elif char and char["guild_id"]:
            guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE id=$1", char["guild_id"])
        else:
            return await interaction.followup.send("❌ You're not in a guild. Specify a guild name.")

        if not guild: return await interaction.followup.send("❌ Guild not found.")

        # Sync member count
        actual_count = await self._sync_member_count(guild["id"])

        gm = await self.bot.db.fetchrow("SELECT name FROM characters WHERE id=$1", guild["guildmaster_id"])
        # Get all members - don't filter by is_active since that might exclude valid members
        members = await self.bot.db.fetch(
            "SELECT name, level, class, guild_rank FROM characters WHERE guild_id=$1 ORDER BY guild_rank DESC, level DESC",
            guild["id"]
        )
        embed = discord.Embed(title=f"🏰 [{guild['tag']}] {guild['name']}", description=guild["motd"] or "*No MOTD set.*", color=0xFFD700)
        embed.add_field(name="Guildmaster", value=gm["name"] if gm else "Unknown", inline=True)
        embed.add_field(name="Level", value=str(guild["guild_level"]), inline=True)
        embed.add_field(name="Members", value=f"{actual_count}/{guild['max_members']}", inline=True)
        
        # Show all members, grouped by rank
        roster_parts = []
        for rank in ["guildmaster", "officer", "veteran", "member"]:
            rank_members = [m for m in members if m["guild_rank"] == rank]
            if rank_members:
                rank_display = rank.title() + "s" if rank != "guildmaster" else "Guildmaster"
                rank_list = "\n".join(f"• **{m['name']}** Lv{m['level']} ({m['class'].title()})" for m in rank_members)
                roster_parts.append(f"**{rank_display}:**\n{rank_list}")
        
        roster = "\n\n".join(roster_parts) if roster_parts else "Empty"
        embed.add_field(name="🏆 Roster", value=roster, inline=False)
        if guild["is_premium"]: embed.add_field(name="✨", value="Premium Guild", inline=True)
        await interaction.followup.send(embed=embed)

    @g.command(name="invite", description="Invite a player to your guild")
    @app_commands.describe(member="Player to invite")
    async def invite(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char or not char["guild_id"]:
            return await interaction.followup.send("❌ You're not in a guild.")
        
        # Check permissions (guildmaster or officer)
        if char["guild_rank"] not in ("guildmaster", "officer"):
            return await interaction.followup.send("❌ Only guildmasters and officers can invite members.")
        
        target_char = await self.svc.get_character(member.id)
        if not target_char:
            return await interaction.followup.send(f"❌ {member.display_name} doesn't have a character.")
        
        if target_char["guild_id"]:
            return await interaction.followup.send(f"❌ {target_char['name']} is already in a guild.")
        
        guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE id=$1", char["guild_id"])
        if guild["member_count"] >= guild["max_members"]:
            return await interaction.followup.send("❌ Guild is full.")
        
        # Create invite (could be stored in DB, but for now just notify)
        embed = discord.Embed(
            title=f"🏰 Guild Invitation",
            description=f"**{char['name']}** has invited you to join **[{guild['tag']}] {guild['name']}**!",
            color=0xFFD700,
        )
        embed.add_field(name="Guildmaster", value=guild.get("guildmaster_name", "Unknown"), inline=True)
        embed.add_field(name="Members", value=f"{guild['member_count']}/{guild['max_members']}", inline=True)
        
        class InviteView(discord.ui.View):
            def __init__(self, guild_id, inviter_char):
                super().__init__(timeout=300)  # 5 minutes
                self.guild_id = guild_id
                self.inviter_char = inviter_char
            
            @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
            async def accept(self, interaction: discord.Interaction, _):
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                target = await self.svc.get_character(interaction.user.id)
                if not target:
                    return await interaction.followup.send("❌ No character found.")
                if target["guild_id"]:
                    return await interaction.followup.send("❌ You're already in a guild.")
                
                guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE id=$1", self.guild_id)
                if guild["member_count"] >= guild["max_members"]:
                    return await interaction.followup.send("❌ Guild is now full.")
                
                await self.bot.db.execute(
                    "UPDATE characters SET guild_id=$1, guild_rank='member' WHERE id=$2",
                    self.guild_id, target["id"]
                )
                # Sync member count
                await self.bot.db.execute(
                    """
                    UPDATE guilds SET member_count=(
                        SELECT COUNT(*) FROM characters WHERE guild_id=$1
                    ) WHERE id=$1
                    """,
                    self.guild_id
                )
                await interaction.followup.send(f"✅ You joined **[{guild['tag']}] {guild['name']}**!")
                self.stop()
            
            @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
            async def decline(self, interaction: discord.Interaction, _):
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                await interaction.followup.send("❌ Invitation declined.")
                self.stop()
        
        view = InviteView(guild["id"], char)
        view.svc = self.svc
        view.bot = self.bot
        
        try:
            await member.send(embed=embed, view=view)
            await interaction.followup.send(f"✅ Invited **{target_char['name']}** to your guild!")
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Couldn't DM {member.display_name}. They may have DMs disabled.")

    @g.command(name="join", description="Join a guild by name")
    @app_commands.describe(name="Guild name to join")
    async def join(self, interaction: discord.Interaction, name: str):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character found.")
        if char["guild_id"]:
            return await interaction.followup.send("❌ You're already in a guild.")
        
        guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE name ILIKE $1", name)
        if not guild:
            return await interaction.followup.send("❌ Guild not found.")
        
        if guild["member_count"] >= guild["max_members"]:
            return await interaction.followup.send("❌ Guild is full.")
        
        await self.bot.db.execute(
            "UPDATE characters SET guild_id=$1, guild_rank='member' WHERE id=$2",
            guild["id"], char["id"]
        )
        # Sync member count
        await self.bot.db.execute(
            """
            UPDATE guilds SET member_count=(
                SELECT COUNT(*) FROM characters WHERE guild_id=$1
            ) WHERE id=$1
            """,
            guild["id"]
        )
        
        # Check guild join achievement
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        await ach_svc.check_and_award(char["id"], "guild_join", {})
        
        await interaction.followup.send(f"✅ You joined **[{guild['tag']}] {guild['name']}**!")

    @g.command(name="leave", description="Leave your current guild")
    async def leave(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char or not char["guild_id"]: return await interaction.followup.send("❌ You're not in a guild.")
        if char["guild_rank"] == "guildmaster": return await interaction.followup.send("❌ Transfer leadership first.")
        guild_id = char["guild_id"]
        await self.bot.db.execute("UPDATE characters SET guild_id=NULL, guild_rank=NULL WHERE id=$1", char["id"])
        # Sync member count
        await self.bot.db.execute(
            """
            UPDATE guilds SET member_count=(
                SELECT COUNT(*) FROM characters WHERE guild_id=$1
            ) WHERE id=$1
            """,
            guild_id
        )
        await interaction.followup.send(f"✅ **{char['name']}** has left the guild.")

    @g.command(name="roster", description="View full guild roster")
    async def roster(self, interaction: discord.Interaction):
        """Debug command to see all guild members."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char or not char["guild_id"]:
            return await interaction.followup.send("❌ You're not in a guild.")
        
        guild = await self.bot.db.fetchrow("SELECT * FROM guilds WHERE id=$1", char["guild_id"])
        if not guild:
            return await interaction.followup.send("❌ Guild not found.")
        
        # Get all characters with this guild_id
        all_members = await self.bot.db.fetch(
            "SELECT id, name, level, class, guild_rank, is_active, guild_id FROM characters WHERE guild_id=$1 ORDER BY guild_rank DESC, level DESC",
            guild["id"]
        )
        
        # Also check what the guild thinks its member count is
        embed = discord.Embed(
            title=f"🔍 Debug: [{guild['tag']}] {guild['name']}",
            description=f"**Stored member_count:** {guild['member_count']}\n**Actual members found:** {len(all_members)}",
            color=0x00FF00,
        )
        
        member_list = []
        for m in all_members:
            status = "✅" if m["is_active"] else "❌"
            member_list.append(
                f"{status} **{m['name']}** Lv{m['level']} ({m['class']}) — {m['guild_rank']}\n"
                f"   ID: {str(m['id'])[:8]}... | guild_id: {str(m['guild_id'])[:8] if m['guild_id'] else 'NULL'}..."
            )
        
        embed.add_field(
            name="👥 All Members",
            value="\n".join(member_list) if member_list else "No members found",
            inline=False,
        )
        
        await interaction.followup.send(embed=embed)

    @g.command(name="disband", description="Disband your guild (guildmaster only)")
    async def disband(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char or char["guild_rank"] != "guildmaster":
            return await interaction.followup.send("❌ Only the guildmaster can disband the guild.")

        class Confirm(discord.ui.View):
            def __init__(self): super().__init__(timeout=30); self.ok = False
            @discord.ui.button(label="Disband Forever", style=discord.ButtonStyle.danger)
            async def yes(self, i, _): self.ok = True; self.stop(); await i.response.defer()
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
            async def no(self, i, _): self.stop(); await i.response.defer()

        view = Confirm()
        await interaction.followup.send("⚠️ Permanently disband your guild?", view=view)
        await view.wait()
        if view.ok:
            await self.bot.db.execute("UPDATE characters SET guild_id=NULL, guild_rank=NULL WHERE guild_id=$1", char["guild_id"])
            await self.bot.db.execute("DELETE FROM guilds WHERE id=$1", char["guild_id"])
            await interaction.edit_original_response(content="💀 Guild disbanded.", view=None)

async def setup(bot): await bot.add_cog(GuildCog(bot))
