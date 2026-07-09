"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      cogs/trade/trade_cog.py — /trade offer /list /accept /cancel          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from typing import Optional
from uuid import UUID

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import RARITIES, Settings
from services.character.character_service import CharacterService
from services.character.inventory_service import InventoryService
from services.trade.trade_service import TradeService

log = logging.getLogger("cog.trade")


class TradeOfferView(discord.ui.View):
    """Accept/Decline buttons on a trade offer. Only the TARGET user may click."""

    def __init__(self, *, cog: "TradeCog", trade_id, target_user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.trade_id = trade_id
        self.target_user_id = target_user_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message(
                "❌ This trade offer isn't for you.", ephemeral=True
            )
            return False
        return True

    def _disable_all(self):
        for child in self.children:
            child.disabled = True

    async def on_timeout(self):
        self._disable_all()
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Accept", emoji="🤝", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        ok, msg = await self.cog.do_accept(interaction.user.id, self.trade_id)
        if ok:
            self._disable_all()
            self.stop()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{'🤝' if ok else '❌'} {msg}",
                color=Settings.COLORS["success"] if ok else Settings.COLORS["error"],
            ),
            ephemeral=not ok,
        )

    @discord.ui.button(label="Decline", emoji="🚫", style=discord.ButtonStyle.secondary)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        char = await self.cog.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        ok, msg = await self.cog.svc.decline(self.trade_id, char["id"])
        if ok:
            self._disable_all()
            self.stop()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass
        await interaction.followup.send(f"{'🚫' if ok else '❌'} {msg}", ephemeral=True)


class TradeCog(commands.Cog, name="Trade"):
    def __init__(self, bot):
        self.bot = bot
        self.svc: TradeService = None
        self.char_svc: CharacterService = None
        self.inv_svc: InventoryService = None

    async def cog_load(self):
        self.svc = TradeService(self.bot.db)
        self.char_svc = CharacterService(self.bot.db)
        self.inv_svc = InventoryService(self.bot.db)

    trade = app_commands.Group(name="trade", description="Trade items directly with other players")

    # ── Shared accept path (button + /trade accept) ───────────────────────────

    async def do_accept(self, user_id: int, trade_id) -> tuple[bool, str]:
        await self.svc.expire_stale()
        char = await self.char_svc.get_character(user_id)
        if not char:
            return False, "No character. Use `/character create` first."
        ok, msg, _payload = await self.svc.accept(trade_id, char["id"])
        return ok, msg

    # ── /trade offer ──────────────────────────────────────────────────────────

    @trade.command(name="offer", description="Offer an item to another player (0 gold = gift)")
    @app_commands.describe(
        member="Player to trade with",
        item_id="Item from your bag (start typing to search)",
        gold_ask="Gold they must pay you (0 = gift)",
    )
    async def trade_offer(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        item_id: str,
        gold_ask: app_commands.Range[int, 0, 10_000_000] = 0,
    ):
        await interaction.response.defer(ephemeral=True)
        if member.bot:
            return await interaction.followup.send("❌ You can't trade with a bot.", ephemeral=True)
        if member.id == interaction.user.id:
            return await interaction.followup.send("❌ You can't trade with yourself.", ephemeral=True)

        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        target = await self.char_svc.get_character(member.id)
        if not target:
            return await interaction.followup.send(
                f"❌ **{member.display_name}** doesn't have a character yet.", ephemeral=True
            )
        try:
            uid = UUID(item_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid item ID.", ephemeral=True)

        await self.svc.expire_stale()
        ok, msg, offer = await self.svc.create_offer(char["id"], target["id"], uid, gold_ask)
        if not ok:
            return await interaction.followup.send(f"❌ {msg}", ephemeral=True)

        rc = RARITIES.get(offer.get("rarity") or "common")
        gold_line = f"💰 **{gold_ask:,}**🪙" if gold_ask > 0 else "🎁 **Free** (gift)"
        embed = discord.Embed(
            title="🤝 Trade Offer",
            description=(
                f"**{char['name']}** offers {rc.emoji if rc else '📦'} "
                f"{offer.get('item_icon') or '📦'} **{offer['item_name']}** "
                f"to {member.mention} for {gold_line}\n\n"
                f"Expires <t:{int(offer['expires_at'].timestamp())}:R>\n"
                f"Use the buttons below or `/trade accept {offer['id']}`."
            ),
            color=Settings.COLORS["info"],
        )
        embed.set_footer(text=f"Trade ID: {offer['id']}")

        view = TradeOfferView(cog=self, trade_id=offer["id"], target_user_id=member.id)
        try:
            sent = await interaction.channel.send(content=member.mention, embed=embed, view=view)
            view.message = sent
            await interaction.followup.send(f"✅ {msg} They have been pinged.", ephemeral=True)
        except Exception:
            # Can't post in the channel — still confirm; target can /trade list.
            await interaction.followup.send(
                f"✅ {msg} (couldn't ping them here — they can see it with `/trade list`)",
                ephemeral=True,
            )

    @trade_offer.autocomplete("item_id")
    async def trade_offer_autocomplete(self, interaction: discord.Interaction, current: str):
        """Suggest unequipped, tradeable items by name (up to 25)."""
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return []
        items = await self.inv_svc.get_all(char["id"])
        offerable = [
            i for i in items
            if not i.get("is_equipped")
            and not i.get("locked")
            and not i.get("soulbound")
            and i.get("tradeable", True) is not False
        ]
        current_l = (current or "").lower()
        filtered = [
            i for i in offerable
            if current_l in (i.get("name", "").lower()) or current_l in str(i.get("id", "")).lower()
        ]
        choices = []
        for i in filtered[:25]:
            rarity = (i.get("rarity") or "common").title()
            qty = i.get("quantity", 1)
            name = f"{i.get('name', 'Item')} • {rarity}" + (f" • x{qty}" if qty > 1 else "")
            choices.append(app_commands.Choice(name=name, value=str(i["id"])))
        return choices

    # ── /trade list ───────────────────────────────────────────────────────────

    @trade.command(name="list", description="View your open incoming and outgoing trade offers")
    async def trade_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        await self.svc.expire_stale()
        rows = await self.svc.list_for(char["id"])
        incoming = [r for r in rows if r["to_character"] == char["id"]]
        outgoing = [r for r in rows if r["from_character"] == char["id"]]

        embed = discord.Embed(title="🤝 Your Trade Offers", color=Settings.COLORS["info"])
        if not rows:
            embed.description = "No open trade offers. Start one with `/trade offer`!"

        def _line(r, incoming_side: bool) -> str:
            gold = f"**{r['gold_ask']:,}**🪙" if int(r["gold_ask"] or 0) > 0 else "🎁 gift"
            who = f"from **{r['from_name']}**" if incoming_side else f"to **{r['to_name']}**"
            action = "accept" if incoming_side else "cancel"
            return (
                f"{r.get('item_icon') or '📦'} **{r['item_name']}** for {gold} {who} "
                f"• expires <t:{int(r['expires_at'].timestamp())}:R>\n"
                f"`/trade {action} {r['id']}`"
            )

        if incoming:
            embed.add_field(
                name=f"📥 Incoming ({len(incoming)})",
                value="\n".join(_line(r, True) for r in incoming[:5]),
                inline=False,
            )
        if outgoing:
            embed.add_field(
                name=f"📤 Outgoing ({len(outgoing)})",
                value="\n".join(_line(r, False) for r in outgoing[:5]),
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /trade accept ─────────────────────────────────────────────────────────

    @trade.command(name="accept", description="Accept a trade offer sent to you")
    @app_commands.describe(trade_id="Trade ID from /trade list")
    async def trade_accept(self, interaction: discord.Interaction, trade_id: str):
        await interaction.response.defer()
        try:
            uid = UUID(trade_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid trade ID.", ephemeral=True)
        ok, msg = await self.do_accept(interaction.user.id, uid)
        await interaction.followup.send(
            embed=discord.Embed(
                description=f"{'🤝' if ok else '❌'} {msg}",
                color=Settings.COLORS["success"] if ok else Settings.COLORS["error"],
            ),
            ephemeral=not ok,
        )

    # ── /trade cancel ─────────────────────────────────────────────────────────

    @trade.command(name="cancel", description="Cancel one of your outgoing trade offers")
    @app_commands.describe(trade_id="Trade ID from /trade list")
    async def trade_cancel(self, interaction: discord.Interaction, trade_id: str):
        await interaction.response.defer(ephemeral=True)
        char = await self.char_svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)
        try:
            uid = UUID(trade_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid trade ID.", ephemeral=True)

        await self.svc.expire_stale()
        ok, msg = await self.svc.cancel(uid, char["id"])
        await interaction.followup.send(f"{'✅' if ok else '❌'} {msg}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
