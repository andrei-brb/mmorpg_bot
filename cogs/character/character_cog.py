"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          cogs/character/character_cog.py — /character commands             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import CLASSES, SPECIALIZATIONS, Settings, RARITIES, ZONES
from services.character.character_service import CharacterService

log = logging.getLogger("cog.character")


# ── UI Views ──────────────────────────────────────────────────────────────────

class ClassSelectView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=60)
        self.chosen = None
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=f"{cls.name} [{cls.role.upper()}]",
                value=key,
                description=cls.description[:80],
                emoji=cls.emoji,
            )
            for key, cls in CLASSES.items()
        ]
        select = discord.ui.Select(placeholder="Choose your class…", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        self.chosen = interaction.data["values"][0]
        self.stop()  # Stop FIRST
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, row=1)
    async def cancel(self, interaction: discord.Interaction, _):
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None, embed=None)


class SpecSelectView(discord.ui.View):
    def __init__(self, class_key: str, owner_id: int):
        super().__init__(timeout=60)
        self.chosen = None
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=f"{spec.name} [{spec.role.upper()}]",
                value=key,
                description=spec.description[:80],
                emoji=spec.emoji,
            )
            for key, spec in SPECIALIZATIONS.items()
            if spec.parent_class == class_key
        ]
        select = discord.ui.Select(placeholder="Choose your specialization…", options=options)
        select.callback = self._on_select
        self.add_item(select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        self.chosen = interaction.data["values"][0]
        self.stop()  # Stop FIRST
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass


# ── Cog ───────────────────────────────────────────────────────────────────────

class CharacterCog(commands.Cog, name="Character"):
    def __init__(self, bot):
        self.bot = bot
        self.svc: CharacterService = None
        self.inv_svc = None
        self._unified_generator = None

    async def cog_load(self):
        self.svc = CharacterService(self.bot.db)
        from services.character.inventory_service import InventoryService
        from cogs.character.unified_character_panel import UnifiedCharacterGenerator
        self.inv_svc = InventoryService(self.bot.db)
        self._unified_generator = UnifiedCharacterGenerator()

    char = app_commands.Group(name="character", description="Manage your character")

    # ── /character create ─────────────────────────────────────────────────────

    @char.command(name="create", description="Create your hero")
    @app_commands.describe(name="Character name (3–32 chars)")
    async def create(self, interaction: discord.Interaction, name: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "character"):
            return
        if not (3 <= len(name) <= 32):
            return await interaction.response.send_message(
                "❌ Name must be 3–32 characters.", ephemeral=True
            )

        await self.svc.ensure_player(interaction.user.id, interaction.user.display_name)

        embed = discord.Embed(
            title="⚔️ Choose Your Class",
            description="Select the class that will define your legend:",
            color=0x2F3136,
        )
        for key, cls in CLASSES.items():
            specs = " / ".join(
                f"{SPECIALIZATIONS[s].emoji}{SPECIALIZATIONS[s].name}"
                for s in cls.specializations if s in SPECIALIZATIONS
            )
            embed.add_field(
                name=f"{cls.emoji} **{cls.name}** — *{cls.role.upper()}*",
                value=f"{cls.description}\n"
                      f"Resource: **{cls.resource.title()}** | Specs: {specs}",
                inline=False,
            )

        view = ClassSelectView(owner_id=interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if not view.chosen:
            return

        ok, msg, char = await self.svc.create_character(interaction.user.id, name, view.chosen)
        cls = CLASSES[view.chosen]

        if not ok:
            return await interaction.edit_original_response(content=f"❌ {msg}", embed=None, view=None)

        embed = discord.Embed(
            title=f"🎉 Welcome to the world, **{name}**!",
            description=f"> *{cls.lore}*",
            color=0x00FF7F,
        )
        embed.add_field(name="Class",  value=f"{cls.emoji} {cls.name}", inline=True)
        embed.add_field(name="Role",   value=cls.role.title(),          inline=True)
        embed.add_field(name="Level",  value="1",                       inline=True)
        embed.add_field(name="HP",     value=str(char["max_hp"]),       inline=True)
        embed.add_field(name="Zone",   value="🌲 Elwynn Forest",        inline=True)
        embed.add_field(
            name="📋 Quick Start",
            value=f"• `/explore` — Enter the world\n"
                  f"• `/fight` — Battle enemies\n"
                  f"• `/character profile` — View your stats\n"
                  f"• Reach level **{Settings.SPEC_UNLOCK_LEVEL}** → choose a Specialization",
            inline=False,
        )
        await interaction.edit_original_response(embed=embed, view=None)

    # ── /character profile ────────────────────────────────────────────────────

    @char.command(name="profile", description="View your character profile")
    @app_commands.describe(member="View another player's profile")
    async def profile(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        if not interaction.response.is_done():
            if not interaction.response.is_done():
                await interaction.response.defer()
        target = member or interaction.user
        data = await self.svc.full_profile(target.id)

        if not data:
            who = "You don't" if not member else f"{target.display_name} doesn't"
            return await interaction.followup.send(f"❌ {who} have a character yet.", ephemeral=True)

        char = data["char"]
        stats = data["stats"]
        cls = CLASSES[char["class"]]
        spec = SPECIALIZATIONS.get(char["specialization"]) if char["specialization"] else None

        # ── Dynamic Colors by Class/Spec ──────────────────────────────────────────
        color_map = {
            # Mage specs
            "fire": 0xFF4500,      # Deep orange fire
            "frost": 0x00CED1,     # Cyan ice
            # Paladin specs  
            "retribution": 0xFF6347,   # Tomato red
            "holy_paladin": 0xFFD700,  # Gold
            # Priest specs
            "holy_priest": 0xFFFFE0,   # Light yellow
            "shadow": 0x8B008B,        # Dark magenta
            # Warrior specs
            "arms": 0xDC143C,          # Crimson
            "protection": 0x4682B4,    # Steel blue
            # Rogue specs
            "assassination": 0x8B0000, # Dark red
            "subtlety": 0x2F4F4F,      # Dark slate
            # Hunter specs
            "marksmanship": 0x228B22,  # Forest green
            "beast_mastery": 0x8B4513, # Saddle brown
        }
        
        # Default class colors if no spec
        class_colors = {
            "warrior": 0xC79C6E,
            "paladin": 0xF58CBA,
            "mage": 0x69CCF0,
            "rogue": 0xFFF569,
            "priest": 0xFFFFFF,
            "hunter": 0xABD473,
        }
        
        color = color_map.get(char["specialization"], class_colors.get(char["class"], 0x2F7F3F))

        # ── Build Embed ───────────────────────────────────────────────────────────
        
        # Title with class emoji and spec
        title_parts = [f"{cls.emoji} **{char['name']}**"]
        if spec:
            title_parts.append(f"{spec.emoji} {spec.name}")
        if char["prestige"] > 0:
            title_parts.append(f"✨ Prestige {char['prestige']}")
        
        embed = discord.Embed(
            title=" • ".join(title_parts),
            description=f"**Level {char['level']} {cls.name}**",
            color=color,
        )

        # ── XP Progress Bar ───────────────────────────────────────────────────────
        if char["level"] < Settings.MAX_LEVEL:
            pct = data["xp_pct"]
            bar_length = 20
            filled = int((pct / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            
            embed.add_field(
                name=f"⚡ Experience — {pct}%",
                value=f"`{bar}` {data['xp_current']:,} / {data['xp_needed']:,} XP",
                inline=False,
            )
        else:
            embed.add_field(
                name="⚡ Experience",
                value="```✨ MAX LEVEL ACHIEVED ✨```",
                inline=False,
            )

        # ── Health & Resources (Visual Bars) ──────────────────────────────────────
        hp_pct = int((char["current_hp"] / char["max_hp"]) * 100)
        hp_bar_len = 15
        hp_filled = int((hp_pct / 100) * hp_bar_len)
        hp_bar = "█" * hp_filled + "░" * (hp_bar_len - hp_filled)
        
        hp_text = f"```diff\n❤ HP  {hp_bar} {hp_pct}%\n{char['current_hp']:,}/{char['max_hp']:,}```"
        
        if char["max_res"] > 0:
            res_pct = int((char["current_res"] / char["max_res"]) * 100)
            res_filled = int((res_pct / 100) * hp_bar_len)
            res_bar = "█" * res_filled + "░" * (hp_bar_len - res_filled)
            
            res_emoji = {"mana": "💙", "energy": "⚡", "rage": "🔴"}.get(cls.resource, "🔋")
            res_name = cls.resource.title()
            
            hp_text += f"```ini\n{res_emoji} {res_name}  {res_bar} {res_pct}%\n{char['current_res']:,}/{char['max_res']:,}```"
        
        embed.add_field(name="━━━━━━━━━━━━━━━━━━━━", value=hp_text, inline=False)

        # ── Combat Stats (Two Columns) ────────────────────────────────────────────
        stats_left = (
            f"```yaml\n"
            f"STR: {stats['strength']}\n"
            f"AGI: {stats['agility']}\n"
            f"INT: {stats['intellect']}\n"
            f"SPI: {stats['spirit']}\n"
            f"STA: {stats['stamina']}\n"
            f"```"
        )
        
        stats_right = (
            f"```yaml\n"
            f"Attack:  {stats['attack_power']}\n"
            f"Spell:   {stats['spell_power']}\n"
            f"Armor:   {stats['armor']}\n"
            f"Crit:    {stats['crit_chance']:.1f}%\n"
            f"Dodge:   {stats['dodge_chance']:.1f}%\n"
            f"```"
        )
        
        embed.add_field(name="📊 Core Stats", value=stats_left, inline=True)
        embed.add_field(name="⚔️ Combat Stats", value=stats_right, inline=True)

        # ── Gold & Location ───────────────────────────────────────────────────────
        zone_name = char["current_zone"].replace("_", " ").title()
        zone_emoji = ZONES.get(char["current_zone"]).emoji if ZONES.get(char["current_zone"]) else "🗺️"
        
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━",
            value=f"🪙 **Gold:** {char['gold']:,}\n📍 **Location:** {zone_emoji} {zone_name}",
            inline=False,
        )

        # ── Guild Badge ───────────────────────────────────────────────────────────
        if char["guild_id"]:
            guild = await self.bot.db.fetchrow(
                "SELECT name, tag, guild_level FROM guilds WHERE id=$1", char["guild_id"]
            )
            if guild:
                embed.add_field(
                    name="🏰 Guild",
                    value=f"**[{guild['tag']}] {guild['name']}** (Lv {guild['guild_level']})",
                    inline=True,
                )

        # ── Equipped Gear Preview ─────────────────────────────────────────────────
        equipped = data["equipped"]
        if equipped:
            gear_slots = ["head", "chest", "main_hand"]
            gear_preview = []
            for slot in gear_slots:
                if slot in equipped:
                    item = equipped[slot]
                    rarity_emoji = RARITIES.get(item["rarity"]).emoji if item["rarity"] in RARITIES else "📦"
                    gear_preview.append(f"{rarity_emoji} {item['icon']} {item['name']}")
            
            if gear_preview:
                embed.add_field(
                    name="🎒 Key Equipment",
                    value="\n".join(gear_preview[:3]),  # Show top 3 pieces
                    inline=True,
                )
        
        # ── Achievements ──────────────────────────────────────────────────────────
        embed.add_field(
            name="🏆 Achievements",
            value=f"**{data['ach_count']}** earned",
            inline=True,
        )

        # ── Specialization Unlock Hint ────────────────────────────────────────────
        if not char["specialization"] and char["level"] >= Settings.SPEC_UNLOCK_LEVEL:
            embed.add_field(
                name="⚡ Specialization Available!",
                value="Use `/character specialize` to unlock your true power!",
                inline=False,
            )
        elif spec:
            embed.add_field(
                name=f"{spec.emoji} {spec.name} Specialization",
                value=f"*{spec.flavor}*\n**{spec.passive_name}:** {spec.passive_desc}",
                inline=False,
            )

        # ── Footer & Thumbnail ────────────────────────────────────────────────────
        embed.set_author(
            name=f"{target.display_name}'s Hero",
            icon_url=target.display_avatar.url
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(
            text=f"World of Discord v{Settings.VERSION} • {cls.role.title()} • {char['combat_status'].replace('_', ' ').title()}"
        )
        
        # Add timestamp
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed)

    # ── /character panel ──────────────────────────────────────────────────────

    @char.command(name="panel", description="Unified equipment + inventory panel (single message)")
    async def panel(self, interaction: discord.Interaction):
        """Single-message equipment/inventory panel with toggle buttons."""
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "character"):
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ You don't have a character yet. Use `/character create`.", ephemeral=True)

        from cogs.character.unified_character_panel import UnifiedCharacterView

        view = UnifiedCharacterView(
            owner_id=interaction.user.id,
            character_id=char["id"],
            generator=self._unified_generator,
            char_service=self.svc,
            inv_service=self.inv_svc,
        )

        # Force an initial render in equipment mode
        stats = await self.svc.total_stats(char["id"])
        equipped = await self.inv_svc.get_equipped(char["id"])
        bag = [i for i in (await self.inv_svc.get_all(char["id"])) if not i.get("is_equipped")]

        character_data = {
            "name": char.get("name", "Unknown"),
            "level": int(char.get("level", 1) or 1),
            "gold": int(char.get("gold", 0) or 0),
            "class": char.get("class", "warrior"),
            "stats": {
                "strength": int(stats.get("strength", 0) or 0),
                "agility": int(stats.get("agility", 0) or 0),
                "intellect": int(stats.get("intellect", 0) or 0),
                "stamina": int(stats.get("stamina", 0) or 0),
                "attack": int(stats.get("attack_power", 0) or 0),
                "armor": int(stats.get("armor", 0) or 0),
            },
        }

        equipment_data = {
            slot: {"id": str(it.get("id")), "name": it.get("name", "?"), "rarity": it.get("rarity", "common"), "icon": it.get("icon", "📦")}
            for slot, it in (equipped or {}).items()
        }
        inventory_items = []
        for item in bag[:112]:
            dmg_min = int(item.get("s_dmg_min", 0) or 0)
            dmg_max = int(item.get("s_dmg_max", 0) or 0)
            inventory_items.append(
                {
                    "id": str(item.get("id")),
                    "name": item.get("name", "?"),
                    "rarity": item.get("rarity", "common"),
                    "icon": item.get("icon", "📦"),
                    "template_id": item.get("template_id"),
                    "quantity": int(item.get("quantity", 1) or 1),
                    "enhancement_level": int(item.get("enhancement_level", 0) or 0),
                    "equip_slot": item.get("equip_slot"),
                    "is_equipped": bool(item.get("is_equipped", False)),
                    "s_str": int(item.get("s_str", 0) or 0),
                    "s_agi": int(item.get("s_agi", 0) or 0),
                    "damage": (dmg_min + dmg_max) // 2 if (dmg_min or dmg_max) else 0,
                }
            )

        # Prefer Vercel renderer for the *initial* panel render (avoids the "old image first" flash).
        image_bytes = None
        render_base = (os.getenv("RENDER_API_BASE_URL") or "").strip()
        if render_base:
            try:
                from services.render_api import post_png, icon_url_for_item_name, icon_url_for_template

                # Map bot equip slots -> renderer slot ids
                slot_map = {
                    "head": "head",
                    "neck": "neck",
                    "shoulders": "shoulder",
                    "chest": "chest",
                    "hands": "gloves",
                    "waist": "belt",
                    "legs": "legs",
                    "feet": "boots",
                    "main_hand": "mainhand",
                    "off_hand": "offhand",
                    "ring": "ring1",
                    "trinket": "trinket",
                }

                equipped_payload = {}
                for bot_slot, it in (equipped or {}).items():
                    renderer_slot = slot_map.get(str(bot_slot))
                    if not renderer_slot:
                        continue
                    item_name = it.get("name") or ""
                    icon_url = (
                        icon_url_for_item_name(item_name)
                        or icon_url_for_template(it.get("template_id") or "")
                        or ""
                    )
                    equipped_payload[renderer_slot] = {
                        "slot": renderer_slot,
                        "name": it.get("name", "?"),
                        "icon": icon_url,
                        "rarity": it.get("rarity", "common"),
                    }

                payload = {
                    "equipped": equipped_payload,
                    "stats": {
                        "attack": int(stats.get("attack_power", 0) or 0),
                        "defense": int(stats.get("armor", 0) or 0),
                        "hp": int(char.get("max_hp", 0) or 0),
                        "speed": int(stats.get("haste", 0) or 0),
                        "level": int(char.get("level", 1) or 1),
                        "class": (char.get("class") or "Adventurer").title(),
                        "name": char.get("name", "Adventurer"),
                    },
                }
                image_bytes = await post_png("/api/render-equipment", payload)
            except Exception:
                image_bytes = None

        if image_bytes is None:
            image_bytes = self._unified_generator.generate_view(
                view_mode="equipment",
                character_data=character_data,
                equipment_data=equipment_data,
                inventory_items=inventory_items,
                selected_item=None,
            )

        await interaction.followup.send(
            content=f"🧩 **{char['name']}'s Panel** — toggle views below. (This message updates in-place.)",
            file=discord.File(fp=image_bytes, filename="character.png"),
            view=view,
            ephemeral=True,
        )

    # ── /character overview ───────────────────────────────────────────────────
    @char.command(name="overview", description="See a full overview: stats, gold, quests, dungeon, daily, etc.")
    async def overview(self, interaction: discord.Interaction):
        """Compact debug-style overview of your character state."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # Core character
        data = await self.svc.full_profile(interaction.user.id)
        if not data:
            return await interaction.followup.send("❌ You don't have a character yet. Use `/character create`.", ephemeral=True)

        char = data["char"]
        stats = data["stats"]
        cls = CLASSES[char["class"]]

        # Import auxiliary services lazily
        from services.quest.npc_quest_service import NPCQuestService
        from services.dungeon.dungeon_service import DungeonService
        from services.daily.daily_login_service import DailyLoginService
        from services.achievement.achievement_service import AchievementService

        quest_svc = NPCQuestService(self.bot.db)
        dungeon_svc = DungeonService(self.bot.db)
        daily_svc = DailyLoginService(self.bot.db)
        ach_svc = AchievementService(self.bot.db)

        # Active / completed quests
        active_quests = await quest_svc.get_active_quests(char["id"])
        completed_quests = await quest_svc.get_completed_quests(char["id"])

        # Reputation summary
        factions = await quest_svc.get_all_reputation(char["id"])

        # Dungeon status
        active_run = await dungeon_svc.get_active_run(char["id"]) if char.get("in_dungeon") else None

        # Daily streak
        streak = await daily_svc.get_streak(char["id"])

        # Achievements
        ach_list = await ach_svc.get_character_achievements(char["id"])

        # Build overview embed
        embed = discord.Embed(
            title=f"📊 Overview — {char['name']}",
            description=f"**Level {char['level']} {cls.name}** — {cls.emoji}",
            color=0x2F3136,
        )

        # Core snapshot
        embed.add_field(
            name="👤 Character",
            value=(
                f"Class: **{cls.name}**\n"
                f"HP: **{char['current_hp']:,}/{char['max_hp']:,}**\n"
                f"Gold: **{char['gold']:,} 🪙**\n"
            ),
            inline=True,
        )

        embed.add_field(
            name="⚔️ Combat Snapshot",
            value=(
                f"ATK: **{stats['attack_power']}**\n"
                f"SP: **{stats['spell_power']}**\n"
                f"Armor: **{stats['armor']}**\n"
                f"Crit: **{stats['crit_chance']:.1f}%**\n"
            ),
            inline=True,
        )

        # Quests
        if active_quests:
            active_lines = [
                f"• {q['quest_name']} (step {q.get('current_step', 1)})"
                for q in active_quests[:5]
            ]
            more = f"\n…and {len(active_quests) - 5} more." if len(active_quests) > 5 else ""
            embed.add_field(
                name=f"📜 Active Quests ({len(active_quests)})",
                value=" \n".join(active_lines) + more,
                inline=False,
            )
        else:
            embed.add_field(
                name="📜 Active Quests",
                value="None — use `/explore` and `/interact` to pick some up.",
                inline=False,
            )

        if completed_quests:
            embed.add_field(
                name="✅ Completed Quests",
                value=f"Total completed: **{len(completed_quests)}**",
                inline=True,
            )

        # Reputation (top few)
        if factions:
            from services.quest.npc_quest_service import get_rep_level
            top_factions = sorted(factions, key=lambda f: f["reputation"], reverse=True)[:3]
            rep_lines = []
            for f in top_factions:
                lvl = get_rep_level(f["reputation"])
                rep_lines.append(
                    f"{lvl['emoji']} **{f['faction_name']}** — {f['reputation']} ({lvl['name']})"
                )
            embed.add_field(
                name="🤝 Reputation (Top 3)",
                value="\n".join(rep_lines),
                inline=False,
            )

        # Dungeon
        if active_run:
            embed.add_field(
                name="🏰 Dungeon",
                value=(
                    f"Active run: **{active_run['dungeon_key']}**\n"
                    f"Floor: **{active_run['current_floor']}/{active_run['total_floors']}**\n"
                    f"Difficulty: **{active_run['difficulty']}**"
                ),
                inline=True,
            )
        else:
            embed.add_field(
                name="🏰 Dungeon",
                value="Not currently in a dungeon.",
                inline=True,
            )

        # Daily login + Achievements
        embed.add_field(
            name="📅 Daily Login",
            value=(
                f"Current streak: **{streak.get('current_streak', 0)}**\n"
                f"Total logins: **{streak.get('total_logins', 0)}**"
            ),
            inline=True,
        )

        embed.add_field(
            name="🏆 Achievements",
            value=f"Total earned: **{len(ach_list)}**",
            inline=True,
        )

        # Location / status footer
        zone_name = char["current_zone"].replace("_", " ").title()
        zone_emoji = ZONES.get(char["current_zone"]).emoji if ZONES.get(char["current_zone"]) else "🗺️"
        embed.add_field(
            name="📍 World",
            value=f"{zone_emoji} **{zone_name}**",
            inline=False,
        )

        embed.set_footer(text=f"World of Discord v{Settings.VERSION} • Overview")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @char.command(name="card", description="Generate a visual profile card image")
    @app_commands.describe(member="View another player's profile card")
    async def card(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        if not interaction.response.is_done():
            if not interaction.response.is_done():
                await interaction.response.defer()
        target = member or interaction.user
        data = await self.svc.full_profile(target.id)

        if not data:
            who = "You don't" if not member else f"{target.display_name} doesn't"
            return await interaction.followup.send(
                f"❌ {who} have a character yet.", ephemeral=True
            )

        char = data["char"]
        stats = data["stats"]
        
        # Get guild info if in guild
        guild_info = {}
        if char.get("guild_id"):
            guild = await self.bot.db.fetchrow("SELECT name, tag, guild_level FROM guilds WHERE id=$1", char["guild_id"])
            if guild:
                guild_info = {"guild_name": guild["name"], "guild_tag": guild["tag"], "guild_level": guild["guild_level"]}
        
        # Get achievements
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        achievements = await ach_svc.get_character_achievements(char["id"])
        
        # Get equipped items
        equipped = {}
        for slot, item in data.get("equipped", {}).items():
            equipped[slot] = item
        
        # Prepare character data
        char_data = {
            **dict(char),
            **guild_info,
            "equipped": equipped,
            "avatar_url": getattr(target.display_avatar, "url", None),
            "res_type": CLASSES[char["class"]].resource,
            "xp_current": data.get("xp_current", 0),
            "xp_needed": data.get("xp_needed", 0),
            "xp_pct": data.get("xp_pct", 0),
        }
        
        # Generate card
        from services.profile.profile_card_generator import ProfileCardGenerator
        generator = ProfileCardGenerator(self.bot.db)
        
        try:
            card_bytes = await generator.generate_card(char["id"], char_data, stats, achievements)
            file = discord.File(card_bytes, filename=f"profile_{char['name']}.png")
            
            embed = discord.Embed(
                title=f"🖼️ Profile Card — {char['name']}",
                description=f"Level {char['level']} {char['class'].title()}",
                color=0xFFD700,
            )
            embed.set_image(url=f"attachment://profile_{char['name']}.png")
            embed.set_footer(text=f"World of Discord v{Settings.VERSION}")
            
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            log.error(f"Failed to generate profile card: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to generate profile card. Error: {str(e)}", ephemeral=True
            )

    # ── /character specialize ─────────────────────────────────────────────────

    @char.command(name="specialize", description=f"Choose your specialization (level {Settings.SPEC_UNLOCK_LEVEL}+)")
    async def specialize(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)

        if not char:
            return await interaction.followup.send("❌ No character — use `/character create`.")
        if char["level"] < Settings.SPEC_UNLOCK_LEVEL:
            return await interaction.followup.send(
                f"❌ Requires level **{Settings.SPEC_UNLOCK_LEVEL}**. You are level **{char['level']}**."
            )
        if char["specialization"]:
            spec = SPECIALIZATIONS.get(char["specialization"])
            return await interaction.followup.send(
                f"✅ You are already **{spec.emoji} {spec.name}**. Specialization is permanent."
            )

        cls = CLASSES[char["class"]]
        specs = {k: v for k, v in SPECIALIZATIONS.items() if v.parent_class == char["class"]}

        embed = discord.Embed(
            title="⚡ Choose Your Specialization",
            description=(
                f"As a **{cls.name}**, choose one path.\n"
                f"⚠️ **This choice is permanent.** Choose wisely.\n\u200b"
            ),
            color=0xFFD700,
        )
        for key, spec in specs.items():
            embed.add_field(
                name=f"{spec.emoji} {spec.name} — *{spec.role.upper()}*",
                value=f"{spec.description}\n"
                      f"**Passive:** {spec.passive_name} — *{spec.passive_desc}*\n"
                      f"**Flavor:** *{spec.flavor}*",
                inline=False,
            )

        view = SpecSelectView(char["class"], owner_id=interaction.user.id)
        await interaction.followup.send(embed=embed, view=view)
        await view.wait()

        if not view.chosen:
            return

        ok, msg = await self.svc.choose_spec(char["id"], view.chosen)
        spec = SPECIALIZATIONS[view.chosen]
        color = 0x00FF7F if ok else 0xFF0000
        result = discord.Embed(
            title=f"{spec.emoji} {spec.name}" if ok else "❌ Error",
            description=msg,
            color=color,
        )
        if ok:
            result.add_field(name="Passive", value=f"**{spec.passive_name}** — {spec.passive_desc}")
        await interaction.edit_original_response(embed=result, view=None)

    # ── /character delete ─────────────────────────────────────────────────────

    @char.command(name="delete", description="Permanently delete your character")
    async def delete(self, interaction: discord.Interaction):
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.response.send_message("❌ No character to delete.", ephemeral=True)

        # Check if character is a guildmaster
        guild = await self.bot.db.fetchrow(
            "SELECT id, name FROM guilds WHERE guildmaster_id=$1", char["id"]
        )
        if guild:
            return await interaction.response.send_message(
                f"❌ Cannot delete character: You are the guildmaster of **{guild['name']}**.\n"
                f"Transfer guildmaster to another member or disband the guild first.",
                ephemeral=True
            )

        class ConfirmView(discord.ui.View):
            def __init__(self): super().__init__(timeout=30); self.ok = False
            @discord.ui.button(label="Delete Forever", style=discord.ButtonStyle.danger)
            async def yes(self, i, _): self.ok = True; self.stop(); await i.response.defer()
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
            async def no(self, i, _): self.stop(); await i.response.defer()

        view = ConfirmView()
        await interaction.response.send_message(
            f"⚠️ Permanently delete **{char['name']}**? This cannot be undone.",
            view=view, ephemeral=True,
        )
        await view.wait()
        if view.ok:
            try:
                # Clean up references that don't have CASCADE
                # 1. Remove from guild if member (not guildmaster - already checked)
                if char.get("guild_id"):
                    await self.bot.db.execute(
                        "UPDATE characters SET guild_id=NULL, guild_rank=NULL WHERE id=$1",
                        char["id"]
                    )
                
                # 2. Cancel/remove active market listings
                await self.bot.db.execute(
                    "UPDATE market_listings SET is_active=FALSE WHERE seller_id=$1 AND is_active=TRUE",
                    char["id"]
                )
                
                # 3. Delete gold_log entries (historical data, safe to remove)
                await self.bot.db.execute(
                    "DELETE FROM gold_log WHERE character_id=$1",
                    char["id"]
                )
                
                # 4. Now delete the character (CASCADE will handle the rest)
                await self.bot.db.execute("DELETE FROM characters WHERE id=$1", char["id"])
                await interaction.edit_original_response(
                    content=f"💀 **{char['name']}** has been deleted.", view=None
                )
            except Exception as e:
                log.error(f"Error deleting character {char['id']}: {e}", exc_info=True)
                await interaction.edit_original_response(
                    content=f"❌ An error occurred while deleting your character: {str(e)[:100]}\nPlease try again or contact support.",
                    view=None
                )

    # ── /character classes ────────────────────────────────────────────────────

    @char.command(name="classes", description="Browse all playable classes")
    async def classes(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Classes of World of Discord",
            description="Six distinct paths await. Choose wisely.",
            color=0x2F3136,
        )
        for key, cls in CLASSES.items():
            specs = " / ".join(
                f"{SPECIALIZATIONS[s].emoji}{SPECIALIZATIONS[s].name}"
                for s in cls.specializations if s in SPECIALIZATIONS
            )
            embed.add_field(
                name=f"{cls.emoji} **{cls.name}** [{cls.role.upper()}]",
                value=(
                    f"{cls.description}\n"
                    f"Primary: **{cls.primary_stat.title()}** | Resource: **{cls.resource.title()}** | "
                    f"Base HP: **{cls.base_hp}**\n"
                    f"Specs: {specs}"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
