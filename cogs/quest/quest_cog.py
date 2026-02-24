"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       cogs/quest/quest_cog.py — NPC Interaction & Quest Commands           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Commands:
  /interact <npc>       — Talk to a discovered NPC (triggers DM)
  /quest log            — View active quests
  /quest completed      — View completed quests
  /quest abandon <id>   — Abandon an active quest
  /quest npcs           — See all discovered NPCs
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.quest.npc_quest_service import NPCQuestService, NPC_TEMPLATES

log = logging.getLogger("cog.quest")


# ═══════════════════════════════════════════════════════════════════════════════
#  UI — Quest Accept/Decline View (sent in DMs)
# ═══════════════════════════════════════════════════════════════════════════════

class QuestOfferView(discord.ui.View):
    """Buttons for accepting/declining a quest offer."""

    def __init__(self):
        super().__init__(timeout=300)
        self.choice: Optional[str] = None

    @discord.ui.button(label="✅ Accept Quest", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = "accept"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = "decline"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="ℹ️ More Info", style=discord.ButtonStyle.secondary)
    async def more_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.choice = "more_info"
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class QuestAbandonConfirm(discord.ui.View):
    """Confirm abandoning a quest."""

    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = False

    @discord.ui.button(label="Yes, Abandon", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


# ═══════════════════════════════════════════════════════════════════════════════
#  QUEST COG
# ═══════════════════════════════════════════════════════════════════════════════

class QuestCog(commands.Cog, name="Quests"):
    """NPC interactions and quest management."""

    def __init__(self, bot):
        self.bot = bot
        self.char_svc: CharacterService = None
        self.inv_svc: InventoryService = None
        self.quest_svc: NPCQuestService = None

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc = InventoryService(self.bot.db)
        self.quest_svc = NPCQuestService(self.bot.db)

    # ── /interact <npc> ─────────────────────────────────────────────────────

    @app_commands.command(name="interact", description="Talk to an NPC you discovered")
    @app_commands.describe(npc="NPC name (e.g., 'marcus', 'frostbeard', 'kira')")
    async def interact(self, interaction: discord.Interaction, npc: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character — use `/character create`.", ephemeral=True)

        # Find the NPC
        npc_id = self.quest_svc.find_npc_by_name(npc)
        if not npc_id:
            return await interaction.followup.send(
                f"❌ No NPC found matching **{npc}**.\n"
                "Use `/explore` to discover NPCs, or `/quest npcs` to see who you've met.",
                ephemeral=True,
            )

        # Check discovery
        state = await self.quest_svc.get_npc_state(char["id"], npc_id)
        if not state:
            return await interaction.followup.send(
                "❌ You haven't discovered this NPC yet! Use `/explore` to find them.",
                ephemeral=True,
            )

        npc_data = NPC_TEMPLATES[npc_id]

        # Check if talking to NPC completes a quest step
        talk_result = await self.quest_svc.check_talk_to_npc(char["id"], npc_id)

        if talk_result and talk_result["complete"]:
            # Quest is fully complete! Grant rewards
            quest_data = talk_result["quest_data"]
            rewards = await self.quest_svc.complete_quest(char["id"], talk_result["quest_id"])
            if rewards:
                await self._grant_rewards(char["id"], rewards)

            # Build completion embed
            dialogue = quest_data["dialogue"].get("completion", "Quest complete!")
            embed = discord.Embed(
                title=f"🎉 Quest Complete: {quest_data['name']}",
                description=dialogue,
                color=0x2ECC71,
            )

            reward_text = []
            if rewards.get("xp"):
                reward_text.append(f"⭐ **{rewards['xp']:,}** XP")
            if rewards.get("gold"):
                reward_text.append(f"🪙 **{rewards['gold']:,}** Gold")
            if rewards.get("items"):
                item_names = [i.replace("_", " ").title() for i in rewards["items"]]
                reward_text.append(f"🎁 {', '.join(item_names)}")

            embed.add_field(name="🏆 Rewards", value="\n".join(reward_text), inline=False)

            # Check if NPC has more quests
            completed_quest_ids = [
                q["quest_id"] for q in await self.quest_svc.get_completed_quests(char["id"])
            ]
            next_quest = self.quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids)
            if next_quest:
                embed.add_field(
                    name="💬 More Work Available",
                    value=f"*{npc_data['name']} has another task for you.\nUse `/interact {npc}` again to hear them out.*",
                    inline=False,
                )

            # Try DM, fallback to channel
            try:
                dm = await interaction.user.create_dm()
                await dm.send(embed=embed)
                await interaction.followup.send(
                    f"🎉 Quest **{quest_data['name']}** completed! Check your DMs for rewards.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await interaction.followup.send(embed=embed, ephemeral=True)
            return

        elif talk_result and not talk_result["complete"]:
            # Step advanced, show next objective
            quest_data = talk_result["quest_data"]
            next_step = talk_result["next_step"]
            embed = discord.Embed(
                title=f"📜 {quest_data['name']} — Step Updated!",
                description=quest_data["dialogue"].get(
                    f"progress_{talk_result.get('next_step', {}).get('step', 1) - 1}",
                    "\"Good progress! Keep going.\""
                ),
                color=0xF39C12,
            )
            embed.add_field(
                name="📍 Next Objective",
                value=f"{next_step['objective']}\n*{next_step['hint']}*",
                inline=False,
            )
            try:
                dm = await interaction.user.create_dm()
                await dm.send(embed=embed)
                await interaction.followup.send(f"💬 {npc_data['name']} sent you a message in DMs!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ── No quest step to complete — offer new quest or show intro ────────

        # Get player's completed quests to find next available
        completed_ids = [q["quest_id"] for q in await self.quest_svc.get_completed_quests(char["id"])]
        active_quests = await self.quest_svc.get_active_quests(char["id"])
        active_ids = [q["quest_id"] for q in active_quests]

        # Check if player already has a quest from this NPC
        for aq in active_quests:
            if aq["npc_id"] == npc_id:
                # Show current progress
                step_idx = aq["current_step"] - 1
                step = aq["steps"][step_idx] if step_idx < len(aq["steps"]) else None
                embed = discord.Embed(
                    title=f"{npc_data['title']} {npc_data['name']}",
                    description=f"*\"{self._get_progress_dialogue(aq, step_idx)}\"*",
                    color=0xF39C12,
                )
                if step:
                    embed.add_field(
                        name=f"📍 Current Objective (Step {aq['current_step']}/{aq['total_steps']})",
                        value=f"{step['objective']}\n*{step['hint']}*",
                        inline=False,
                    )
                try:
                    dm = await interaction.user.create_dm()
                    await dm.send(embed=embed)
                    await interaction.followup.send(f"💬 {npc_data['name']} reminded you of your quest. Check DMs!", ephemeral=True)
                except discord.Forbidden:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Find next available quest
        next_quest = self.quest_svc.get_next_quest_for_npc(npc_id, completed_ids)

        if not next_quest:
            # All quests done
            embed = discord.Embed(
                title=f"{npc_data['title']} {npc_data['name']}",
                description=(
                    f"*\"You've done everything I needed, adventurer. I owe you my gratitude.\n"
                    f"Safe travels!\"*"
                ),
                color=0x95A5A6,
            )
            try:
                dm = await interaction.user.create_dm()
                await dm.send(embed=embed)
                await interaction.followup.send(f"💬 {npc_data['name']} has no more quests. Check DMs.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check level requirement
        if char["level"] < next_quest.get("level_req", 1):
            embed = discord.Embed(
                title=f"{npc_data['title']} {npc_data['name']}",
                description=(
                    f"*\"You show promise, but you're not ready yet.\n"
                    f"Come back when you've reached level **{next_quest['level_req']}**.\"*"
                ),
                color=0xFF6B6B,
            )
            try:
                dm = await interaction.user.create_dm()
                await dm.send(embed=embed)
                await interaction.followup.send(f"💬 {npc_data['name']} says you need more experience. Check DMs.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ── Offer new quest via DM ───────────────────────────────────────────

        try:
            dm = await interaction.user.create_dm()
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I can't send you DMs! Please enable DMs from server members.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"{npc_data['title']} {npc_data['name']}",
            description=npc_data["introduction"]["text"],
            color=0x4A90E2,
        )

        embed.add_field(
            name="📜 Quest Available",
            value=f"**{next_quest['name']}**\n{next_quest['description']}",
            inline=False,
        )

        if next_quest.get("level_req", 1) > 1:
            embed.add_field(name="⚔️ Level Required", value=f"Level {next_quest['level_req']}", inline=True)

        # Reward preview
        rewards = next_quest["rewards"]
        reward_lines = []
        if rewards.get("xp"):
            reward_lines.append(f"⭐ {rewards['xp']:,} XP")
        if rewards.get("gold"):
            reward_lines.append(f"🪙 {rewards['gold']:,} Gold")
        if rewards.get("items"):
            reward_lines.append(f"🎁 Unique Item Reward")
        embed.add_field(name="🏆 Rewards", value="\n".join(reward_lines), inline=True)

        # Steps preview
        step_text = "\n".join(
            f"`{i+1}.` {s['objective']}" for i, s in enumerate(next_quest["steps"])
        )
        embed.add_field(name="📋 Objectives", value=step_text, inline=False)

        # Send with buttons
        view = QuestOfferView()
        dm_msg = await dm.send(embed=embed, view=view)

        await interaction.followup.send(
            f"💬 **{npc_data['name']}** is talking to you in DMs!",
            ephemeral=True,
        )

        # Update NPC state
        await self.quest_svc.update_npc_state(char["id"], npc_id, "quest_offered")

        # Wait for response
        await view.wait()

        if view.choice == "accept":
            await self.quest_svc.offer_quest(char["id"], npc_id, next_quest["id"])
            await self.quest_svc.accept_quest(char["id"], next_quest["id"])

            accept_embed = discord.Embed(
                title="✅ Quest Accepted!",
                description=next_quest["dialogue"]["accept"],
                color=0x2ECC71,
            )
            first_step = next_quest["steps"][0]
            accept_embed.add_field(
                name="📍 First Objective",
                value=f"{first_step['objective']}\n*{first_step['hint']}*",
                inline=False,
            )
            accept_embed.set_footer(text="Use /quest log to track your progress!")
            await dm_msg.edit(embed=accept_embed, view=None)

        elif view.choice == "decline":
            decline_embed = discord.Embed(
                title="Quest Declined",
                description=next_quest["dialogue"]["decline"],
                color=0x95A5A6,
            )
            decline_embed.set_footer(text="You can always come back and accept later.")
            await dm_msg.edit(embed=decline_embed, view=None)

        elif view.choice == "more_info":
            info_embed = discord.Embed(
                title=f"ℹ️ {next_quest['name']} — Details",
                description=next_quest["description"],
                color=0x3498DB,
            )
            for i, step in enumerate(next_quest["steps"]):
                info_embed.add_field(
                    name=f"Step {i+1}: {step['objective']}",
                    value=f"*{step['hint']}*",
                    inline=False,
                )
            info_embed.set_footer(text="Use /interact again to accept or decline.")
            await dm_msg.edit(embed=info_embed, view=None)

        else:
            # Timeout
            timeout_embed = discord.Embed(
                title="⏰ Quest Offer Expired",
                description="The NPC waits patiently. Use `/interact` again when you're ready.",
                color=0x95A5A6,
            )
            await dm_msg.edit(embed=timeout_embed, view=None)

    # ── /quest group ─────────────────────────────────────────────────────────

    quest_group = app_commands.Group(name="quest", description="Quest management commands")

    @quest_group.command(name="log", description="View your active quests")
    async def quest_log(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        active = await self.quest_svc.get_active_quests(char["id"])
        if not active:
            return await interaction.followup.send(
                "📋 No active quests. Use `/explore` to find NPCs and `/interact` to get quests!",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="📜 Quest Log",
            description=f"You have **{len(active)}** active quest(s).",
            color=0xF39C12,
        )

        for q in active:
            step_idx = q["current_step"] - 1
            step = q["steps"][step_idx] if step_idx < len(q["steps"]) else None
            status = "🟢 Active" if q["state"] == "active" else "🟡 Offered"

            value = f"{status} | Step {q['current_step']}/{q['total_steps']}"
            if step:
                value += f"\n📍 **{step['objective']}**\n*{step['hint']}*"

            # Show progress from metadata
            if step and q.get("metadata"):
                meta = q["metadata"] if isinstance(q["metadata"], dict) else {}
                check = step["completion_check"]
                if check["type"] in ("kill_enemy", "kill_any_zone", "kill_boss_zone"):
                    count = check.get("count", 1)
                    kill_key = None
                    if check["type"] == "kill_enemy":
                        kill_key = f"kills_{check['value']}"
                    elif check["type"] == "kill_any_zone":
                        kill_key = f"kills_zone_{check['value']}"
                    elif check["type"] == "kill_boss_zone":
                        kill_key = f"boss_kills_{check['value']}"
                    if kill_key:
                        current = meta.get(kill_key, 0)
                        value += f"\n📊 Progress: **{current}/{count}**"

            embed.add_field(
                name=f"📜 {q['quest_name']}",
                value=value,
                inline=False,
            )

        embed.set_footer(text="Use /interact <npc> to advance talk-to-NPC steps | /quest abandon <name> to drop a quest")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @quest_group.command(name="completed", description="View completed quests")
    async def quest_completed(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        completed = await self.quest_svc.get_completed_quests(char["id"])
        if not completed:
            return await interaction.followup.send("📋 No completed quests yet. Go explore!", ephemeral=True)

        embed = discord.Embed(
            title="🏆 Completed Quests",
            description=f"You have completed **{len(completed)}** quest(s).",
            color=0x2ECC71,
        )

        for q in completed:
            completed_at = q["completed_at"]
            ts = f"<t:{int(completed_at.timestamp())}:R>" if completed_at else "Unknown"
            embed.add_field(
                name=f"✅ {q['quest_name']}",
                value=f"Completed {ts}",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @quest_group.command(name="npcs", description="View NPCs you've discovered")
    async def quest_npcs(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        npcs = await self.quest_svc.get_discovered_npcs(char["id"])
        if not npcs:
            return await interaction.followup.send(
                "👤 No NPCs discovered yet. Use `/explore` to find them!",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="👥 Discovered NPCs",
            description=f"You've met **{len(npcs)}** NPC(s).",
            color=0x9B59B6,
        )

        from config.settings import ZONES
        for n in npcs:
            zone = ZONES.get(n["zone"], None)
            zone_name = zone.name if zone else n["zone"].replace("_", " ").title()
            state_emoji = {"discovered": "🔵", "introduced": "🟡", "quest_offered": "🟢"}.get(n["state"], "⚪")
            embed.add_field(
                name=f"{n['title']} {n['name']}",
                value=f"{state_emoji} {n['state'].replace('_', ' ').title()} | 📍 {zone_name}\n*Use `/interact {n['name'].split()[0].lower()}` to talk*",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @quest_group.command(name="abandon", description="Abandon an active quest")
    @app_commands.describe(quest_name="Name of the quest to abandon")
    async def quest_abandon(self, interaction: discord.Interaction, quest_name: str):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        active = await self.quest_svc.get_active_quests(char["id"])
        # Find quest by partial name match
        target = None
        for q in active:
            if quest_name.lower() in q["quest_name"].lower():
                target = q
                break

        if not target:
            quest_list = "\n".join(f"• {q['quest_name']}" for q in active) if active else "None"
            return await interaction.followup.send(
                f"❌ No active quest matching **{quest_name}**.\n\nActive quests:\n{quest_list}",
                ephemeral=True,
            )

        # Confirm
        embed = discord.Embed(
            title="⚠️ Abandon Quest?",
            description=(
                f"Are you sure you want to abandon **{target['quest_name']}**?\n\n"
                "All progress will be lost. You can accept the quest again later."
            ),
            color=0xFF6B6B,
        )
        view = QuestAbandonConfirm()
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.confirmed:
            await self.quest_svc.abandon_quest(char["id"], target["quest_id"])
            done_embed = discord.Embed(
                title="🗑️ Quest Abandoned",
                description=f"**{target['quest_name']}** has been abandoned.",
                color=0x95A5A6,
            )
            await msg.edit(embed=done_embed, view=None)
        else:
            keep_embed = discord.Embed(
                title="✅ Quest Kept",
                description=f"**{target['quest_name']}** is still active.",
                color=0x2ECC71,
            )
            await msg.edit(embed=keep_embed, view=None)

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _grant_rewards(self, char_id, rewards: dict):
        """Grant XP, gold, and items from quest rewards."""
        if rewards.get("xp"):
            await self.char_svc.award_xp(char_id, rewards["xp"])
        if rewards.get("gold"):
            await self.char_svc.add_gold(char_id, rewards["gold"], "quest_reward", "quest_reward")
        if rewards.get("items"):
            for template_id in rewards["items"]:
                # Get item rarity from template
                tmpl = await self.bot.db.fetchrow(
                    "SELECT rarity FROM item_templates WHERE id = $1", template_id
                )
                rarity = tmpl["rarity"] if tmpl else "common"
                await self.inv_svc.add_item(char_id, template_id, rarity=rarity)

    def _get_progress_dialogue(self, quest_data, step_idx):
        """Get the dialogue line for current progress."""
        dialogue = quest_data.get("dialogue", {}) if isinstance(quest_data, dict) else {}
        key = f"progress_{step_idx}"
        return dialogue.get(key, "Keep going! You're making good progress.")


async def setup(bot):
    await bot.add_cog(QuestCog(bot))
