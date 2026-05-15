"""Discord slash commands for talent trees."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import CLASSES, SPECIALIZATIONS
from services.character.character_service import CharacterService
from services.talents.talent_service import TalentService

log = logging.getLogger("cog.talents")


def _top_allocated_nodes(state: Dict[str, Any], limit: int = 6) -> List[str]:
    alloc = state.get("allocations") or {}
    if not isinstance(alloc, dict):
        return []
    rows: List[tuple[str, int, str]] = []
    for tree_key, tree in (
        ("foundation", state.get("foundation")),
        *[(f"spec:{t.get('spec_key')}", t) for t in (state.get("spec_trees") or [])],
    ):
        if not tree:
            continue
        for node in tree.get("nodes") or []:
            nid = str(node.get("id") or "")
            ranks = int(alloc.get(nid) or node.get("ranks") or 0)
            if ranks <= 0 or node.get("auto_grant"):
                continue
            rows.append((nid, ranks, str(node.get("name") or nid)))
    rows.sort(key=lambda x: (-x[1], x[2]))
    return [f"**{name}** ({ranks}/{_max_for_node(state, nid)})" for nid, ranks, name in rows[:limit]]


def _max_for_node(state: Dict[str, Any], node_id: str) -> int:
    for tree in [state.get("foundation"), *(state.get("spec_trees") or [])]:
        if not tree:
            continue
        for node in tree.get("nodes") or []:
            if str(node.get("id")) == node_id:
                return int(node.get("max_ranks") or 1)
    return 1


class TalentsCog(commands.Cog, name="Talents"):
    def __init__(self, bot):
        self.bot = bot
        self.char_svc: Optional[CharacterService] = None

    async def cog_load(self):
        self.char_svc = CharacterService(self.bot.db)

    talents = app_commands.Group(name="talents", description="Talent tree points and builds")

    @talents.command(name="summary", description="View talent points and current build")
    async def talents_summary(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel

        if not await check_channel(interaction, "talents"):
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send(
                "❌ No character — use `/character create`.",
                ephemeral=True,
            )

        state = await TalentService(self.bot.db).get_tree_state(dict(char))
        pts = state.get("points") or {}
        spec_key = state.get("specialization")
        spec_name = SPECIALIZATIONS[spec_key].name if spec_key and spec_key in SPECIALIZATIONS else "Not chosen"
        cls = CLASSES.get(str(char.get("class") or ""))
        class_label = cls.name if cls else str(char.get("class") or "?")

        embed = discord.Embed(
            title=f"🌳 Talents — {char['name']}",
            description=(
                f"**{class_label}** · **{spec_name}** · Lv **{state.get('level', char.get('level', 1))}**\n"
                f"Unspent **{pts.get('unspent', 0)}** · Spent **{pts.get('spent', 0)}** · "
                f"Earned **{pts.get('earned', 0)}**"
            ),
            color=0xC9A227,
        )

        respec_count = int(state.get("respec_count") or 0)
        gold_cost = int(state.get("respec_gold_cost") or 0)
        if respec_count == 0:
            respec_line = "Next respec: **free**"
        else:
            respec_line = f"Next respec: **{gold_cost:,}** gold"
        embed.add_field(name="Respec", value=respec_line, inline=True)

        if spec_key:
            embed.add_field(
                name="Profession tree",
                value="Unlocked — spend points in your active spec tree.",
                inline=False,
            )
        else:
            embed.add_field(
                name="Before Lv 10",
                value="Preview both spec branches (2 ranks each). Choose a spec at level 10.",
                inline=False,
            )

        top = _top_allocated_nodes(state)
        embed.add_field(
            name="Top nodes",
            value="\n".join(top) if top else "_No points spent yet._",
            inline=False,
        )

        embed.set_footer(
            text="Full tree: open the Activity → Realm → Power · or use /open_game"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @talents.command(name="points", description="Quick view of unspent talent points")
    async def talents_points(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel

        if not await check_channel(interaction, "talents"):
            return

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.response.send_message(
                "❌ No character — use `/character create`.",
                ephemeral=True,
            )

        state = await TalentService(self.bot.db).get_tree_state(dict(char))
        pts = state.get("points") or {}
        await interaction.response.send_message(
            f"🌳 **{pts.get('unspent', 0)}** unspent talent points "
            f"({pts.get('spent', 0)} spent / {pts.get('earned', 0)} earned). "
            f"Open **Realm → Power** in the Activity for the full tree.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(TalentsCog(bot))
