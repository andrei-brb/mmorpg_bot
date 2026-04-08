"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         cogs/admin/admin_cog.py — /admin GM tools                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import Settings, RARITIES
from services.character.character_service import CharacterService

log = logging.getLogger("cog.admin")

# ── Dropdown Views ──────────────────────────────────────────────────────────────

class _GoldSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, member: discord.Member):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.member = member
        self.chosen = None
        self.add_item(_GoldSelect())

class _GoldSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="100 Gold", value="100", description="Small amount"),
            discord.SelectOption(label="500 Gold", value="500", description="Medium amount"),
            discord.SelectOption(label="1,000 Gold", value="1000", description="Large amount"),
            discord.SelectOption(label="5,000 Gold", value="5000", description="Very large amount"),
            discord.SelectOption(label="10,000 Gold", value="10000", description="Huge amount"),
            discord.SelectOption(label="50,000 Gold", value="50000", description="Massive amount"),
        ]
        super().__init__(placeholder="Select gold amount…", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _GoldSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
        
        view.chosen = int(self.values[0])
        view.stop()
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

class _XPSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, member: discord.Member):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.member = member
        self.chosen = None
        self.add_item(_XPSelect())

class _XPSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="100 XP", value="100", description="Small amount"),
            discord.SelectOption(label="500 XP", value="500", description="Medium amount"),
            discord.SelectOption(label="1,000 XP", value="1000", description="Large amount"),
            discord.SelectOption(label="5,000 XP", value="5000", description="Very large amount"),
            discord.SelectOption(label="10,000 XP", value="10000", description="Huge amount"),
            discord.SelectOption(label="50,000 XP", value="50000", description="Massive amount"),
        ]
        super().__init__(placeholder="Select XP amount…", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _XPSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
        
        view.chosen = int(self.values[0])
        view.stop()
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

class _ItemSelect(discord.ui.Select):
    def __init__(self, bot, items: List):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=item['name'],
                description=f"{item['item_type']} • {item['rarity']}",
                value=item['id']
            )
            for item in items[:25]  # Discord limit
        ]
        super().__init__(placeholder="Select an item…", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _ItemSelectView):
            return await interaction.response.send_message("❌ Internal error.", ephemeral=True)
        if interaction.user.id != view.owner_id:
            return await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
        
        view.chosen = self.values[0]
        view.stop()
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

class _ItemSelectView(discord.ui.View):
    def __init__(self, *, owner_id: int, member: discord.Member, rarity: str, bot, items: List):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.member = member
        self.rarity = rarity
        self.bot = bot
        self.chosen = None
        self.add_item(_ItemSelect(bot, items))

def is_admin():
    """Check: Discord admin OR configured admin role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        try:
            # Check Discord administrator permission
            if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
                return True
            
            # Check configured admin role
            if interaction.guild:
                cfg = await interaction.client.db.fetchrow(
                    "SELECT admin_role_id FROM server_config WHERE server_id=$1", interaction.guild_id
                )
                if cfg and cfg["admin_role_id"]:
                    role = interaction.guild.get_role(cfg["admin_role_id"])
                    if role and role in interaction.user.roles:
                        return True
        except Exception as e:
            log.error(f"Error checking admin permissions: {e}", exc_info=True)
        
        # If no permission, send helpful error
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ **Permission Denied**\n\n"
                    "You need one of the following:\n"
                    "• Discord **Administrator** permission\n"
                    "• An admin role set via `/admin setup admin_role:@role`\n\n"
                    "To set an admin role, ask a server administrator to run:\n"
                    "`/admin setup admin_role:@YourRole`",
                    ephemeral=True
                )
        except Exception:
            pass  # Already responded or error sending
        
        return False
    return app_commands.check(predicate)

class AdminCog(commands.Cog, name="Admin"):
    def __init__(self, bot): self.bot = bot; self.svc: CharacterService = None
    async def cog_load(self): self.svc = CharacterService(self.bot.db)

    admin = app_commands.Group(name="admin", description="Game master tools (admin only)")
    lore = app_commands.Group(
        name="lore",
        description="Lore deeds, boss gates & Obsidian Silence tracker",
        parent=admin,
    )

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Respond immediately then verify admin permissions. Returns True if admin."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        # Discord Administrator permission
        if hasattr(interaction.user, 'guild_permissions') and interaction.user.guild_permissions.administrator:
            return True
        # Configured admin role in DB
        if interaction.guild:
            try:
                cfg = await self.bot.db.fetchrow(
                    "SELECT admin_role_id FROM server_config WHERE server_id=$1", interaction.guild_id
                )
                if cfg and cfg["admin_role_id"]:
                    role = interaction.guild.get_role(cfg["admin_role_id"])
                    if role and role in interaction.user.roles:
                        return True
            except Exception as e:
                log.error(f"DB error checking admin: {e}")
        await interaction.followup.send(
            "❌ **Permission Denied**\n\n"
            "You need one of the following:\n"
            "• Discord **Administrator** permission\n"
            "• An admin role set via `/admin setup admin_role:@role`",
            ephemeral=True,
        )
        return False


    @admin.command(name="givegold", description="Give gold to a player")
    @app_commands.describe(member="Target player", amount="Gold amount (or use dropdown)")
    async def give_gold(self, interaction: discord.Interaction, member: discord.Member, amount: Optional[int] = None):
        """Give gold to a player - admin only."""
        if not await self._check_admin(interaction):
            return
        
        # If no amount provided, show dropdown
        if amount is None:
            view = _GoldSelectView(owner_id=interaction.user.id, member=member)
            await interaction.followup.send(
                f"**Select gold amount to give to {member.display_name}:**",
                view=view,
                ephemeral=True,
            )
            await view.wait()
            if not view.chosen:
                return
            amount = view.chosen
        
        char = await self.svc.get_character(member.id)
        if not char: return await interaction.followup.send(f"❌ {member.display_name} has no character.")
        await self.svc.add_gold(char["id"], amount, "admin grant")
        await interaction.followup.send(f"✅ Gave **{amount:,}**🪙 to **{char['name']}**.")

    @admin.command(name="givexp", description="Give XP to a player")
    @app_commands.describe(member="Target player", amount="XP amount (or use dropdown)")
    async def give_xp(self, interaction: discord.Interaction, member: discord.Member, amount: Optional[int] = None):
        if not await self._check_admin(interaction):
            return
        
        # If no amount provided, show dropdown
        if amount is None:
            view = _XPSelectView(owner_id=interaction.user.id, member=member)
            await interaction.followup.send(
                f"**Select XP amount to give to {member.display_name}:**",
                view=view,
                ephemeral=True,
            )
            await view.wait()
            if not view.chosen:
                return
            amount = view.chosen
        
        char = await self.svc.get_character(member.id)
        if not char: return await interaction.followup.send(f"❌ No character.")
        result = await self.svc.award_xp(char["id"], amount)
        msg = f"✅ Gave **{amount:,}** XP to **{char['name']}**."
        if result["leveled_up"]:
            msg += f" They leveled up to **{result['new_level']}**!"
        await interaction.followup.send(msg)

    @admin.command(name="givelevel", description="Set a player's level (admin)")
    @app_commands.describe(member="Target player", level="New level (1..MAX)")
    async def give_level(self, interaction: discord.Interaction, member: discord.Member, level: int):
        if not await self._check_admin(interaction):
            return
        char = await self.svc.get_character(member.id)
        if not char:
            return await interaction.followup.send(f"❌ {member.display_name} has no character.")
        res = await self.svc.set_level(char["id"], int(level))
        if not res.get("ok"):
            return await interaction.followup.send("❌ Could not set level.")
        await interaction.followup.send(
            f"✅ Set **{char['name']}** to level **{res['level']}** (HP refilled)."
        )

    @admin.command(name="giveitem", description="Give an item to a player")
    @app_commands.describe(member="Target player", item_id="Item template ID (use autocomplete)", rarity="Item rarity")
    @app_commands.choices(rarity=[
        app_commands.Choice(name=r.name, value=k)
        for k, r in RARITIES.items()
    ])
    async def give_item(self, interaction: discord.Interaction, member: discord.Member, item_id: Optional[str] = None, rarity: str = "common"):
        if not await self._check_admin(interaction):
            return
        
        # If no item_id provided, show dropdown
        if not item_id:
            # Fetch items from database
            items = await self.bot.db.fetch(
                "SELECT id, name, item_type, rarity FROM item_templates ORDER BY rarity DESC, name LIMIT 25"
            )
            view = _ItemSelectView(owner_id=interaction.user.id, member=member, rarity=rarity, bot=self.bot, items=items)
            msg = await interaction.followup.send(
                f"**Select an item to give to {member.display_name}:**",
                view=view,
                ephemeral=True,
            )
            await view.wait()
            if not view.chosen:
                return await msg.edit(content="❌ No item selected.", view=None)
            item_id = view.chosen
            await msg.edit(content=f"⚙️ Giving **{item_id}** to {member.display_name}...", view=None)
        
        char = await self.svc.get_character(member.id)
        if not char: return await interaction.followup.send("❌ No character.")
        from services.character.inventory_service import InventoryService
        inv = InventoryService(self.bot.db)
        ok, msg = await inv.add_item(char["id"], item_id, rarity, from_="admin")
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}")
    
    @give_item.autocomplete("item_id")
    async def give_item_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for item template IDs."""
        if not current:
            current = ""
        current = current.lower()
        
        items = await self.bot.db.fetch(
            "SELECT id, name, item_type, rarity FROM item_templates WHERE id ILIKE $1 OR name ILIKE $1 ORDER BY rarity DESC, name LIMIT 25",
            f"%{current}%"
        )
        return [
            app_commands.Choice(
                name=f"{item['name']} ({item['item_type']})",
                value=item['id']
            )
            for item in items
        ]

    @admin.command(name="setup", description="Configure this server")
    @app_commands.describe(
        announce_channel="Channel for world event announcements",
        admin_role="Role that can use admin commands",
        xp_multiplier="XP multiplier (e.g. 1.5 for 50% bonus)",
        gold_multiplier="Gold multiplier",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        announce_channel: Optional[discord.TextChannel] = None,
        admin_role: Optional[discord.Role] = None,
        xp_multiplier: Optional[float] = None,
        gold_multiplier: Optional[float] = None,
    ):
        if not await self._check_admin(interaction):
            return

        # Upsert server config
        updates = []
        values = [interaction.guild_id]
        idx = 2

        if announce_channel:
            updates.append(f"announce_channel_id=${idx}"); values.append(announce_channel.id); idx += 1
        if admin_role:
            updates.append(f"admin_role_id=${idx}"); values.append(admin_role.id); idx += 1
        if xp_multiplier is not None:
            updates.append(f"xp_multiplier=${idx}"); values.append(max(0.1, min(10.0, xp_multiplier))); idx += 1
        if gold_multiplier is not None:
            updates.append(f"gold_multiplier=${idx}"); values.append(max(0.1, min(10.0, gold_multiplier))); idx += 1

        if updates:
            await self.bot.db.execute(
                f"""INSERT INTO server_config(server_id) VALUES($1)
                    ON CONFLICT(server_id) DO UPDATE SET {', '.join(updates)}""",
                *values,
            )

        cfg = await self.bot.db.fetchrow("SELECT * FROM server_config WHERE server_id=$1", interaction.guild_id)
        embed = discord.Embed(title="⚙️ Server Configuration", color=0x4488FF)
        embed.add_field(name="XP Multiplier",   value=f"{cfg['xp_multiplier'] if cfg else 1.0:.1f}×", inline=True)
        embed.add_field(name="Gold Multiplier",  value=f"{cfg['gold_multiplier'] if cfg else 1.0:.1f}×", inline=True)
        embed.add_field(name="Premium",          value="✅ Yes" if (cfg and cfg["is_premium"]) else "❌ No", inline=True)
        embed.add_field(name="Announce Channel", value=f"<#{cfg['announce_channel_id']}>" if (cfg and cfg["announce_channel_id"]) else "Not set", inline=True)
        embed.add_field(name="Admin Role",       value=f"<@&{cfg['admin_role_id']}>" if (cfg and cfg["admin_role_id"]) else "Not set", inline=True)
        await interaction.followup.send(embed=embed)

    @lore.command(name="flags", description="List deed flags for a player's character")
    @app_commands.describe(member="Target player")
    async def lore_flags(self, interaction: discord.Interaction, member: discord.Member):
        if not await self._check_admin(interaction):
            return
        char = await self.svc.get_character(member.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        from services.lore.lore_gate_service import LoreGateService

        lg = LoreGateService(self.bot.db)
        flags = await lg.get_flags(char["id"])
        if not flags:
            return await interaction.followup.send(
                f"📜 **{char['name']}** — no deed flags stored yet.\n"
                f"`character_id`: `{char['id']}`",
                ephemeral=True,
            )
        body = "\n".join(f"• `{f}`" for f in flags[:50])
        extra = f"\n… +{len(flags) - 50} more" if len(flags) > 50 else ""
        await interaction.followup.send(
            f"📜 **{char['name']}** — **{len(flags)}** deed flag(s)\n{body}{extra}\n\n"
            f"`character_id`: `{char['id']}`",
            ephemeral=True,
        )

    @lore.command(name="grant_flag", description="Grant a deed flag to a player's character")
    @app_commands.describe(member="Target player", flag_key="Flag key (e.g. marcus_recommendation)")
    async def lore_grant_flag(
        self, interaction: discord.Interaction, member: discord.Member, flag_key: str
    ):
        if not await self._check_admin(interaction):
            return
        char = await self.svc.get_character(member.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        fk = (flag_key or "").strip()
        if not fk or len(fk) > 128:
            return await interaction.followup.send("❌ Invalid flag_key.")
        from services.lore.lore_gate_service import LoreGateService

        lg = LoreGateService(self.bot.db)
        await lg.grant_flag(char["id"], fk)
        await interaction.followup.send(
            f"✅ Granted flag `{fk}` to **{char['name']}**.",
            ephemeral=True,
        )

    @lore.command(name="revoke_flag", description="Remove a deed flag from a player's character")
    @app_commands.describe(member="Target player", flag_key="Flag key to remove")
    async def lore_revoke_flag(
        self, interaction: discord.Interaction, member: discord.Member, flag_key: str
    ):
        if not await self._check_admin(interaction):
            return
        char = await self.svc.get_character(member.id)
        if not char:
            return await interaction.followup.send("❌ No character.")
        fk = (flag_key or "").strip()
        from services.lore.lore_gate_service import LoreGateService

        lg = LoreGateService(self.bot.db)
        await lg.revoke_flag(char["id"], fk)
        await interaction.followup.send(
            f"✅ Revoked flag `{fk}` from **{char['name']}** (if it existed).",
            ephemeral=True,
        )

    @lore.command(name="gates", description="Show configured lore boss gates (enemy_key → flags/items)")
    async def lore_gates_cmd(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return
        from config.lore_gates import LORE_BOSS_GATES

        if not LORE_BOSS_GATES:
            return await interaction.followup.send(
                "📖 **LORE_BOSS_GATES** is empty — no story immunities active.\n"
                "Edit `config/lore_gates.py` to add `enemy_key` rules.",
                ephemeral=True,
            )
        lines = []
        for ek, cfg in LORE_BOSS_GATES.items():
            rf = ", ".join(cfg.get("required_flags") or []) or "—"
            ri = ", ".join(cfg.get("required_items") or []) or "—"
            hint = (cfg.get("hint") or "")[:200]
            lines.append(f"**{ek}**\nflags: `{rf}` | items: `{ri}`\n_{hint}_\n")
        await interaction.followup.send(
            "🪞 **Lore boss gates**\n\n" + "\n".join(lines)[:3900],
            ephemeral=True,
        )

    @admin.command(name="spawn_event", description="Manually trigger a world event")
    @app_commands.describe(event_key="Event key to spawn")
    @app_commands.choices(event_key=[
        app_commands.Choice(name="Demon Invasion",       value="demon_invasion"),
        app_commands.Choice(name="Merchant's Festival",  value="merchants_festival"),
        app_commands.Choice(name="Ancient Curse",        value="ancient_curse"),
        app_commands.Choice(name="Blessing of Light",    value="blessing_of_light"),
    ])
    async def spawn_event(self, interaction: discord.Interaction, event_key: str):
        if not await self._check_admin(interaction):
            return
        # Find events cog and trigger it
        events_cog = self.bot.cogs.get("Events")
        if events_cog:
            events_cog.world_event_loop.restart()
        await interaction.followup.send(f"✅ World event loop restarted — **{event_key}** queued.")

    @admin.command(name="stats", description="View server game statistics")
    async def stats(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return
        total_chars  = await self.bot.db.fetchval("SELECT COUNT(*) FROM characters WHERE is_active=TRUE")
        total_guilds = await self.bot.db.fetchval("SELECT COUNT(*) FROM guilds")
        top_level    = await self.bot.db.fetchval("SELECT MAX(level) FROM characters WHERE is_active=TRUE")
        total_gold   = await self.bot.db.fetchval("SELECT SUM(gold) FROM characters WHERE is_active=TRUE") or 0
        market_count = await self.bot.db.fetchval("SELECT COUNT(*) FROM market_listings WHERE is_active=TRUE")
        active_fights = await self.bot.db.fetchval("SELECT COUNT(*) FROM characters WHERE combat_status='in_combat'")

        embed = discord.Embed(title=f"📊 {interaction.guild.name} — Game Stats", color=0x4488FF)
        embed.add_field(name="👥 Active Characters", value=str(total_chars),    inline=True)
        embed.add_field(name="🏰 Guilds",            value=str(total_guilds),   inline=True)
        embed.add_field(name="🏆 Highest Level",     value=str(top_level or 0), inline=True)
        embed.add_field(name="🪙 Total Gold",         value=f"{total_gold:,}",   inline=True)
        embed.add_field(name="🏪 Market Listings",   value=str(market_count),   inline=True)
        embed.add_field(name="⚔️ Active Fights",     value=str(active_fights),  inline=True)
        await interaction.followup.send(embed=embed)

    @admin.command(name="characters", description="List characters on this server (debug)")
    async def characters(self, interaction: discord.Interaction):
        """Show a snapshot of characters (name, level, gold, owner)."""
        if not await self._check_admin(interaction):
            return

        rows = await self.bot.db.fetch(
            """
            SELECT c.name, c.level, c.gold, c.class, c.is_active,
                   c.player_id, p.username
            FROM characters c
            LEFT JOIN players p ON c.player_id = p.id
            ORDER BY COALESCE(c.last_combat, c.created_at) DESC
            LIMIT 20
            """
        )

        if not rows:
            return await interaction.followup.send(
                "📋 No characters found in the database yet.",
                ephemeral=True,
            )

        lines = []
        for r in rows:
            owner_mention = f"<@{r['player_id']}>" if r["player_id"] else "Unknown"
            owner_name = r["username"] or "Unknown"
            status = "✅ active" if r["is_active"] else "❌ inactive"
            lines.append(
                f"• **{r['name']}** (Lv {r['level']} {r['class']}) — "
                f"{r['gold']:,}🪙 — {status}\n"
                f"  Owner: {owner_mention} (`{owner_name}`)"
            )

        embed = discord.Embed(
            title="👥 Characters — Snapshot",
            description="\n".join(lines),
            color=0x00A86B,
        )
        embed.set_footer(text="Showing up to 20 most recently updated characters.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin.command(name="sync_commands", description="Force re-sync Discord commands (fixes duplicates)")
    async def sync_commands(self, interaction: discord.Interaction):
        """Force re-sync all commands and clear guild duplicates."""
        if not await self._check_admin(interaction):
            return
        try:
            # Sync global commands
            synced = await self.bot.tree.sync()
            cleared = 0
            # Clear guild-specific commands (prevents double/triple commands)
            for guild in self.bot.guilds:
                self.bot.tree.clear_commands(guild=guild)
                await self.bot.tree.sync(guild=guild)
                cleared += 1
            await interaction.followup.send(
                f"✅ **Commands re-synced!**\n{len(synced)} global commands.\n"
                f"Cleared guild commands in **{cleared}** server(s).\n\n"
                "Discord may take 1–2 minutes to update. Duplicates should disappear.",
                ephemeral=True
            )
        except Exception as e:
            err_str = str(e)
            # Handle Discord Activity Entry Point error (50240)
            if "50240" in err_str or "Entry Point" in err_str:
                await interaction.followup.send(
                    "⚠️ **Sync partially completed**\n\n"
                    "Discord's Activity Entry Point prevents full re-sync.\n\n"
                    "✅ Your new commands (including `/admin givelevel`) are registered!\n"
                    "⏳ Wait 1-2 minutes for Discord to update the command list.\n\n"
                    "*This is a Discord limitation with Activities, not a bot error.*",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(f"❌ Failed to sync commands: {e}", ephemeral=True)

    @admin.command(name="help", description="View all admin commands")
    async def admin_help(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return
        embed = discord.Embed(title="🛠️ Admin Commands", color=0xFF8C00)
        embed.add_field(name="/admin setup",         value="Configure server settings, multipliers, announce channel", inline=False)
        embed.add_field(name="/admin givegold",      value="Give gold to a player", inline=False)
        embed.add_field(name="/admin givexp",        value="Give XP to a player", inline=False)
        embed.add_field(name="/admin givelevel",     value="Set a player's level", inline=False)
        embed.add_field(name="/admin giveitem",      value="Give an item to a player", inline=False)
        embed.add_field(name="/admin spawn_event",   value="Manually trigger a world event", inline=False)
        embed.add_field(name="/admin stats",         value="View server game statistics", inline=False)
        embed.add_field(name="/admin sync_commands",  value="Force re-sync commands (fixes duplicates)", inline=False)
        embed.add_field(name="/admin version",       value="Show deployed version info", inline=False)
        embed.add_field(
            name="/admin lore …",
            value="`flags`, `grant_flag`, `revoke_flag`, `gates` — deed flags & boss gate tracker",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="version", description="Show deployed version info")
    async def version(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return
        import os

        git_sha = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_SHA") or "").strip() or "unknown"
        svc = (os.getenv("RAILWAY_SERVICE_NAME") or "").strip() or "unknown"
        env = (os.getenv("RAILWAY_ENVIRONMENT_NAME") or "").strip() or "unknown"
        pub = (os.getenv("ACTIVITY_PUBLIC_URL") or "").strip() or "(not set)"
        redir = (os.getenv("DISCORD_OAUTH_REDIRECT_URI") or "").strip() or "(not set)"
        has_secret = "yes" if (os.getenv("DISCORD_CLIENT_SECRET") or "").strip() else "no"
        await interaction.response.send_message(
            f"**Version**: `{git_sha}`\n"
            f"**Railway**: service `{svc}` env `{env}`\n"
            f"**ACTIVITY_PUBLIC_URL**: `{pub}`\n"
            f"**DISCORD_OAUTH_REDIRECT_URI**: `{redir}`\n"
            f"**DISCORD_CLIENT_SECRET set**: `{has_secret}`",
            ephemeral=True,
        )

async def setup(bot): await bot.add_cog(AdminCog(bot))
