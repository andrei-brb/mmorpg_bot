"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       cogs/quest/quest_cog.py — NPC Interaction & Quest Commands           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Commands:
  /interact <npc>       — Talk to a discovered NPC (triggers DM)
  /quest log            — View active quests (with timers)
  /quest completed      — View completed quests
  /quest abandon <id>   — Abandon an active quest
  /quest npcs           — See all discovered NPCs
  /reputation           — View faction standings
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import Settings
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.lore.lore_gate_service import LoreGateService
from services.quest.npc_quest_service import (
    NPCQuestService, NPC_TEMPLATES, FACTIONS,
    get_rep_level, get_dynamic_intro,
    is_main_story_quest,
)

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
        self.lore_gate: LoreGateService = None

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc = InventoryService(self.bot.db)
        self.quest_svc = NPCQuestService(self.bot.db)
        self.lore_gate = LoreGateService(self.bot.db)

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
            reward_items = list(((quest_data or {}).get("rewards") or {}).get("items") or [])
            if reward_items:
                can_add, add_msg = await self.inv_svc.can_add_reward_items(char["id"], reward_items)
                if not can_add:
                    return await interaction.followup.send(
                        f"❌ Cannot complete quest yet: {add_msg}",
                        ephemeral=True,
                    )
            rewards = await self.quest_svc.complete_quest(char["id"], talk_result["quest_id"])
            grant_report = {"granted_items": [], "failed_items": []}
            if rewards:
                grant_report = await self._grant_rewards(
                    char["id"],
                    rewards,
                    quest_id=str(talk_result.get("quest_id") or ""),
                    char=dict(char),
                )

            dialogue = quest_data["dialogue"].get("completion", "Quest complete!")
            embed = discord.Embed(
                title=f"🎉 Quest Complete: {quest_data['name']}",
                description=dialogue,
                color=Settings.COLORS["success"],
            )

            reward_text = []
            if rewards.get("xp"):
                reward_text.append(f"⭐ **{rewards['xp']:,}** XP")
            if rewards.get("gold"):
                reward_text.append(f"🪙 **{rewards['gold']:,}** Gold")
            if grant_report.get("granted_items"):
                item_names = [str(i).replace("_", " ").title() for i in grant_report["granted_items"]]
                reward_text.append(f"🎁 {', '.join(item_names)}")
            if grant_report.get("failed_items"):
                failed = grant_report["failed_items"]
                first = failed[0] if failed else {}
                reward_text.append(
                    "⚠ Reward delivery issue: "
                    + str(first.get("template_id", "item")).replace("_", " ").title()
                    + f" ({first.get('reason', 'could not add')})"
                )

            # Show reputation gain
            rep_results = []
            if rewards.get("reputation"):
                for faction_id, amount in rewards["reputation"].items():
                    rep_info = await self.quest_svc.add_reputation(char["id"], faction_id, amount)
                    faction = FACTIONS.get(faction_id, {})
                    rep_text = f"{faction.get('emoji', '⭐')} **+{amount}** {faction.get('name', faction_id)}"
                    if rep_info.get("leveled_up"):
                        rep_text += f" — 🎊 **{rep_info['level']['name']}** reached!"
                    rep_results.append(rep_text)
                    reward_text.append(rep_text)

            embed.add_field(name="🏆 Rewards", value="\n".join(reward_text), inline=False)

            # Server milestone hook: quest completion (+ optional reward-side progress).
            if interaction.guild_id:
                try:
                    from services.milestones.milestone_service import MilestoneService
                    ms = MilestoneService(self.bot.db)
                    completed = []
                    completed.extend(
                        await ms.increment(
                            interaction.guild_id,
                            "quests_completed",
                            1,
                            source="quest_complete",
                            actor_id=interaction.user.id,
                        )
                    )
                    if rewards.get("gold", 0) > 0:
                        completed.extend(
                            await ms.increment(
                                interaction.guild_id,
                                "gold_earned",
                                int(rewards["gold"]),
                                source="quest_gold",
                                actor_id=interaction.user.id,
                            )
                        )
                    if completed:
                        lines = []
                        for c in completed:
                            reward = c.get("reward", {})
                            reward_label = reward.get("label", reward.get("type", "reward"))
                            lines.append(
                                f"• **{c['title']}** Tier {c['tier']} reached ({c['target']:,}) — {reward_label}"
                            )
                        embed.add_field(name="🏁 Server Milestones", value="\n".join(lines[:3]), inline=False)
                        await ms.announce_completions(self.bot, interaction.guild_id, completed)
                except Exception:
                    pass

            # Check if NPC has more quests
            completed_quest_ids = [
                q["quest_id"] for q in await self.quest_svc.get_completed_quests(char["id"])
            ]
            deed_set = set(await self.lore_gate.get_flags(char["id"]))
            next_quest = self.quest_svc.get_next_quest_for_npc(npc_id, completed_quest_ids, deed_set)
            if next_quest:
                embed.add_field(
                    name="💬 More Work Available",
                    value=f"*{npc_data['name']} has another task for you.\nUse `/interact {npc}` again to hear them out.*",
                    inline=False,
                )

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

        completed_ids = [q["quest_id"] for q in await self.quest_svc.get_completed_quests(char["id"])]
        active_quests = await self.quest_svc.get_active_quests(char["id"])
        active_ids = [q["quest_id"] for q in active_quests]

        # Check if player already has a quest from this NPC
        for aq in active_quests:
            if aq["npc_id"] == npc_id:
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

                # Show timer if timed quest
                if aq.get("expires_at"):
                    expires_at = aq["expires_at"]
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    ts = int(expires_at.timestamp())
                    embed.add_field(
                        name="⏰ Time Remaining",
                        value=f"Expires <t:{ts}:R>",
                        inline=True,
                    )

                try:
                    dm = await interaction.user.create_dm()
                    await dm.send(embed=embed)
                    await interaction.followup.send(f"💬 {npc_data['name']} reminded you of your quest. Check DMs!", ephemeral=True)
                except discord.Forbidden:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # Find next available quest
        deed_set = set(await self.lore_gate.get_flags(char["id"]))
        next_quest = self.quest_svc.get_next_quest_for_npc(npc_id, completed_ids, deed_set)

        if not next_quest:
            # Show which quests were completed from this NPC
            npc_completed = [q for q in await self.quest_svc.get_completed_quests(char["id"]) 
                           if q.get("npc_id") == npc_id]
            
            embed = discord.Embed(
                title=f"{npc_data['title']} {npc_data['name']}",
                description=(
                    f"*\"You've done everything I needed, adventurer. I owe you my gratitude.\n"
                    f"Safe travels!\"*"
                ),
                color=0x95A5A6,
            )
            
            if npc_completed:
                quest_names = []
                for q in npc_completed:
                    quest_template = self.quest_svc._find_quest_template(q["quest_id"])
                    if quest_template:
                        quest_names.append(f"✅ **{quest_template['name']}**")
                
                if quest_names:
                    embed.add_field(
                        name="📜 Completed Quests",
                        value="\n".join(quest_names),
                        inline=False,
                    )
            
            embed.add_field(
                name="💡 Tip",
                value="Explore other zones to discover new NPCs with quests! Use `/map` to see available zones.",
                inline=False,
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

        # ── Offer new quest via DM (with dynamic dialogue) ───────────────────

        try:
            dm = await interaction.user.create_dm()
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I can't send you DMs! Please enable DMs from server members.",
                ephemeral=True,
            )

        # Dynamic intro based on class/level
        char_class = char.get("class", "warrior")
        char_level = char.get("level", 1)
        intro_text = get_dynamic_intro(npc_id, npc_data, char_class, char_level)

        embed = discord.Embed(
            title=f"{npc_data['title']} {npc_data['name']}",
            description=intro_text,
            color=0x4A90E2,
        )

        embed.add_field(
            name="📜 Quest Available",
            value=f"**{next_quest['name']}**\n{next_quest['description']}",
            inline=False,
        )

        if next_quest.get("level_req", 1) > 1:
            embed.add_field(name="⚔️ Level Required", value=f"Level {next_quest['level_req']}", inline=True)

        # Show time limit if timed quest
        if next_quest.get("time_limit_hours"):
            hours = next_quest["time_limit_hours"]
            if hours >= 24:
                time_str = f"{hours // 24} day{'s' if hours >= 48 else ''}"
            else:
                time_str = f"{hours} hour{'s' if hours > 1 else ''}"
            embed.add_field(name="⏰ Time Limit", value=f"{time_str} to complete", inline=True)

        # Reward preview
        rewards = next_quest["rewards"]
        reward_lines = []
        if rewards.get("xp"):
            reward_lines.append(f"⭐ {rewards['xp']:,} XP")
        if rewards.get("gold"):
            reward_lines.append(f"🪙 {rewards['gold']:,} Gold")
        if rewards.get("items"):
            reward_lines.append(f"🎁 Unique Item Reward")
        if rewards.get("reputation"):
            for fid, amt in rewards["reputation"].items():
                faction = FACTIONS.get(fid, {})
                reward_lines.append(f"{faction.get('emoji', '⭐')} +{amt} {faction.get('name', fid)} Rep")
        embed.add_field(name="🏆 Rewards", value="\n".join(reward_lines), inline=True)

        # Steps preview
        step_text = "\n".join(
            f"`{i+1}.` {s['objective']}" for i, s in enumerate(next_quest["steps"])
        )
        embed.add_field(name="📋 Objectives", value=step_text, inline=False)

        # Show faction info
        faction_id = npc_data.get("faction")
        if faction_id:
            faction = FACTIONS.get(faction_id)
            if faction:
                current_rep = await self.quest_svc.get_reputation(char["id"], faction_id)
                level = get_rep_level(current_rep)
                embed.set_footer(
                    text=f"{faction['emoji']} {faction['name']}: {level['emoji']} {level['name']} ({current_rep:,} rep)"
                )

        # Send with buttons
        view = QuestOfferView()
        dm_msg = await dm.send(embed=embed, view=view)

        await interaction.followup.send(
            f"💬 **{npc_data['name']}** is talking to you in DMs!",
            ephemeral=True,
        )

        await self.quest_svc.update_npc_state(char["id"], npc_id, "quest_offered")
        await view.wait()

        if view.choice == "accept":
            await self.quest_svc.offer_quest(char["id"], npc_id, next_quest["id"])
            await self.quest_svc.accept_quest(char["id"], next_quest["id"])

            accept_embed = discord.Embed(
                title="✅ Quest Accepted!",
                description=next_quest["dialogue"]["accept"],
                color=Settings.COLORS["success"],
            )
            first_step = next_quest["steps"][0]
            accept_embed.add_field(
                name="📍 First Objective",
                value=f"{first_step['objective']}\n*{first_step['hint']}*",
                inline=False,
            )
            if next_quest.get("time_limit_hours"):
                accept_embed.add_field(
                    name="⏰ Timer Started!",
                    value=f"You have **{next_quest['time_limit_hours']} hours** to complete this quest!",
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
                color=Settings.COLORS["info"],
            )
            for i, step in enumerate(next_quest["steps"]):
                info_embed.add_field(
                    name=f"Step {i+1}: {step['objective']}",
                    value=f"*{step['hint']}*",
                    inline=False,
                )
            if next_quest.get("time_limit_hours"):
                info_embed.add_field(
                    name="⏰ Time Limit",
                    value=f"**{next_quest['time_limit_hours']} hours** from acceptance",
                    inline=False,
                )
            info_embed.set_footer(text="Use /interact again to accept or decline.")
            await dm_msg.edit(embed=info_embed, view=None)

        else:
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

            # Show timer for timed quests
            if q.get("expires_at"):
                expires_at = q["expires_at"]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                ts = int(expires_at.timestamp())
                value += f"\n⏰ Expires <t:{ts}:R>"

            q_label = q["quest_name"]
            if is_main_story_quest(q.get("quest_id")):
                q_label = f"{q_label} · Main story"
            embed.add_field(
                name=f"📜 {q_label}",
                value=value,
                inline=False,
            )

        embed.set_footer(text="Use /interact <npc> to advance talk-to-NPC steps | /quest abandon <name> to drop side quests (main story is locked)")
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
            color=Settings.COLORS["success"],
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

    @interact.autocomplete("npc")
    async def interact_npc_autocomplete(self, interaction: discord.Interaction, current: str):
        """Suggest NPCs the player has actually discovered."""
        try:
            char = await self.char_svc.get_character(interaction.user.id)
            if not char:
                return []
            npcs = await self.quest_svc.get_discovered_npcs(char["id"])
        except Exception:
            return []
        cur = (current or "").lower()
        choices = []
        for n in npcs:
            short = n["name"].split()[0].lower()
            label = f"{n['title']} {n['name']}"
            if cur and cur not in n["name"].lower() and cur not in short:
                continue
            choices.append(app_commands.Choice(name=label[:100], value=short))
            if len(choices) >= 25:
                break
        return choices

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

            # Show faction
            faction_str = ""
            if n.get("faction"):
                faction = FACTIONS.get(n["faction"])
                if faction:
                    faction_str = f" | {faction['emoji']} {faction['name']}"

            embed.add_field(
                name=f"{n['title']} {n['name']}",
                value=(
                    f"{state_emoji} {n['state'].replace('_', ' ').title()} | 📍 {zone_name}{faction_str}\n"
                    f"*Use `/interact {n['name'].split()[0].lower()}` to talk*"
                ),
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

        if is_main_story_quest(target.get("quest_id")):
            return await interaction.followup.send(
                "📜 **Main story** quests cannot be abandoned. Finish the questline or ask an admin if you are stuck.",
                ephemeral=True,
            )

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
                color=Settings.COLORS["success"],
            )
            await msg.edit(embed=keep_embed, view=None)

    # ── /reputation ──────────────────────────────────────────────────────────

    @app_commands.command(name="reputation", description="View your faction standings")
    async def reputation(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        factions = await self.quest_svc.get_all_reputation(char["id"])

        embed = discord.Embed(
            title="🏛️ Faction Reputation",
            description="Your standing with the factions of the world.",
            color=0x9B59B6,
        )

        for f in factions:
            level = f["level"]
            rep = f["reputation"]

            # Calculate progress bar to next level
            current_threshold = level["threshold"]
            next_level = None
            from services.quest.npc_quest_service import REPUTATION_LEVELS
            for thresh, name, emoji, perks in REPUTATION_LEVELS:
                if thresh > rep:
                    next_level = (thresh, name, emoji, perks)
                    break

            if next_level:
                progress = rep - current_threshold
                needed = next_level[0] - current_threshold
                filled = int((progress / needed) * 10) if needed > 0 else 10
                bar = "█" * filled + "░" * (10 - filled)
                progress_text = f"`{bar}` {progress}/{needed} to {next_level[2]} {next_level[1]}"
            else:
                progress_text = "`██████████` MAX RANK!"

            faction_info = FACTIONS.get(f["faction_id"], {})
            embed.add_field(
                name=f"{f['emoji']} {f['name']}",
                value=(
                    f"{level['emoji']} **{level['name']}** ({rep:,} rep)\n"
                    f"{progress_text}\n"
                    f"*{level['perks']}*"
                ),
                inline=False,
            )

        embed.set_footer(text="Complete NPC quests to gain reputation!")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _grant_rewards(self, char_id, rewards: dict, *, quest_id: str = "", char: Optional[dict] = None):
        """Grant XP, gold, and items from quest rewards; return delivery report."""
        granted_items = []
        failed_items = []
        xp_result: dict = {}
        if rewards.get("xp"):
            xp_result = await self.char_svc.award_xp(char_id, rewards["xp"])
        if rewards.get("gold"):
            await self.char_svc.add_gold(char_id, rewards["gold"], "quest_reward", "quest_reward")
        if rewards.get("items"):
            for template_id in rewards["items"]:
                tmpl = await self.bot.db.fetchrow(
                    "SELECT rarity FROM item_templates WHERE id = $1", template_id
                )
                rarity = tmpl["rarity"] if tmpl else "common"
                ok_add, msg_add = await self.inv_svc.add_item(char_id, template_id, rarity=rarity)
                if ok_add:
                    granted_items.append(str(template_id))
                else:
                    failed_items.append({"template_id": str(template_id), "reason": str(msg_add or "could_not_add")})
        if char and quest_id:
            ch = char
            lvl = int((xp_result or {}).get("new_level") or ch.get("level") or 1)
            zk = str(ch.get("current_zone") or "elwynn_forest")
            bg, bf = await self.inv_svc.grant_main_story_quest_gear_bonus_if_needed(
                char_id,
                is_main_story=is_main_story_quest(quest_id),
                template_item_reward_ids=list(rewards.get("items") or []),
                zone_key=zk,
                char_level=lvl,
            )
            granted_items.extend(bg)
            failed_items.extend(bf)
        if rewards.get("deed_flags") and self.lore_gate:
            await self.lore_gate.grant_deed_flags_from_rewards(char_id, rewards)
        return {"granted_items": granted_items, "failed_items": failed_items}

    def _get_progress_dialogue(self, quest_data, step_idx):
        dialogue = quest_data.get("dialogue", {}) if isinstance(quest_data, dict) else {}
        key = f"progress_{step_idx}"
        return dialogue.get(key, "Keep going! You're making good progress.")


async def setup(bot):
    await bot.add_cog(QuestCog(bot))
