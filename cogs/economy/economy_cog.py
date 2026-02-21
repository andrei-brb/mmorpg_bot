"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        cogs/economy/economy_cog.py — /market /leaderboard /gold            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from uuid import UUID
from typing import Optional, List
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import Settings, RARITIES
from services.character.character_service import CharacterService

log = logging.getLogger("cog.economy")


# ── Dropdown Views ──────────────────────────────────────────────────────────────

class _MarketSellView(discord.ui.View):
    """Dropdown to pick an item from inventory to list on the market."""
    def __init__(self, *, owner_id: int, items: List[dict]):
        super().__init__(timeout=90)
        self.owner_id = owner_id
        self.chosen = None
        self.add_item(_MarketSellSelect(items))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True


class _MarketSellSelect(discord.ui.Select):
    def __init__(self, items: List[dict]):
        options: List[discord.SelectOption] = []
        for i in items[:25]:
            rarity = i.get("rarity", "common")
            emoji = getattr(RARITIES.get(rarity), "emoji", "📦")
            slot = i.get("equip_slot") or i.get("item_type", "?")
            label = i.get("name", "Item")
            desc = f"{rarity.title()} • {slot}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=desc[:100],
                    value=str(i["id"]),
                    emoji=emoji,
                )
            )
        super().__init__(
            placeholder="Choose an item to list on the market…",
            min_values=1, max_values=1, options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _MarketSellView):
            return
        view.chosen = self.values[0]
        if not interaction.response.is_done():
            await interaction.response.defer()
        view.stop()


class _MarketBuyView(discord.ui.View):
    """Dropdown to pick a listing to buy from the market."""
    def __init__(self, *, owner_id: int, listings: List[dict]):
        super().__init__(timeout=90)
        self.owner_id = owner_id
        self.chosen = None
        self.add_item(_MarketBuySelect(listings))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True


class _MarketBuySelect(discord.ui.Select):
    def __init__(self, listings: List[dict]):
        options: List[discord.SelectOption] = []
        for r in listings[:25]:
            rc = RARITIES.get(r.get("rarity", "common"))
            emoji = rc.emoji if rc else "📦"
            label = f"{r['name']} — {r['price']:,}🪙"
            desc = f"{r.get('rarity','common').title()} • Seller: {r.get('seller','?')}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=desc[:100],
                    value=str(r["id"]),
                    emoji=emoji,
                )
            )
        super().__init__(
            placeholder="Choose a listing to buy…",
            min_values=1, max_values=1, options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if not isinstance(view, _MarketBuyView):
            return
        view.chosen = self.values[0]
        if not interaction.response.is_done():
            await interaction.response.defer()
        view.stop()


class _PriceSelectView(discord.ui.View):
    """Dropdown to pick a price when listing on the market."""
    def __init__(self, *, owner_id: int, item_name: str, suggested: int):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.chosen = None

        options = []
        # Offer price suggestions based on vendor price
        for mult, label in [(1, "Low"), (2, "Fair"), (5, "High"), (10, "Premium"), (20, "Extreme")]:
            val = max(1, suggested * mult)
            options.append(
                discord.SelectOption(
                    label=f"{val:,}🪙 ({label})",
                    value=str(val),
                    description=f"{mult}x vendor price",
                )
            )
        sel = discord.ui.Select(placeholder=f"Set price for {item_name}…", options=options)
        sel.callback = self._pick
        self.add_item(sel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ This menu isn't for you.", ephemeral=True)
            return False
        return True

    async def _pick(self, interaction: discord.Interaction):
        self.chosen = int(interaction.data["values"][0])
        self.stop()  # Stop FIRST
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass


# ── Cog ────────────────────────────────────────────────────────────────────────

class EconomyCog(commands.Cog, name="Economy"):
    def __init__(self, bot): self.bot = bot; self.svc: CharacterService = None
    async def cog_load(self): self.svc = CharacterService(self.bot.db)

    market = app_commands.Group(name="market", description="Player-driven marketplace")

    @market.command(name="browse", description="Browse items for sale")
    async def browse(self, interaction: discord.Interaction):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "market"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer()
        rows = await self.bot.db.fetch(
            """SELECT ml.id, ml.price, ml.quantity, t.name, t.rarity, t.icon, c.name as seller
               FROM market_listings ml
               JOIN inventory i ON ml.item_id=i.id
               JOIN item_templates t ON i.template_id=t.id
               JOIN characters c ON ml.seller_id=c.id
               WHERE ml.is_active=TRUE AND ml.expires_at>NOW()
               ORDER BY ml.listed_at DESC LIMIT 20"""
        )
        if not rows:
            return await interaction.followup.send(embed=discord.Embed(title="🏪 Marketplace", description="No items listed. Be first to sell!", color=0x2F3136))

        embed = discord.Embed(title=f"🏪 Marketplace — {len(rows)} listings", description=f"Fee: **{Settings.MARKET_FEE_PERCENT}%** of sale price", color=0xFFD700)
        for r in rows:
            rc = RARITIES.get(r["rarity"])
            embed.add_field(
                name=f"{rc.emoji if rc else '📦'} {r['name']} [{r['rarity'].title()}]",
                value=f"💰 **{r['price']:,}**🪙 × {r['quantity']} | By *{r['seller']}*\n`/market buy {r['id']}`",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @market.command(name="sell", description="List an item for sale on the marketplace")
    @app_commands.describe(item_id="Item UUID from /inventory (or use dropdown)", price="Listing price in gold (or use dropdown)")
    async def market_sell(self, interaction: discord.Interaction, item_id: Optional[str] = None, price: Optional[int] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "market"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        from services.character.inventory_service import InventoryService
        inv_svc = InventoryService(self.bot.db)

        # ── Step 1: Pick item ──────────────────────────────────────────────
        if not item_id:
            items = await inv_svc.get_all(char["id"])
            sellable = [
                i for i in items
                if not i.get("is_equipped")
                and not i.get("soulbound")
                and not i.get("locked")
            ]
            if not sellable:
                return await interaction.followup.send("❌ No items available to sell.", ephemeral=True)

            view = _MarketSellView(owner_id=interaction.user.id, items=sellable)
            msg = await interaction.followup.send("**Select an item to list on the marketplace:**", view=view, ephemeral=True, wait=True)
            await view.wait()
            if not view.chosen:
                return await msg.edit(content="❌ Selection timed out.", view=None)
            item_id = view.chosen

        try:
            uid = UUID(item_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid item ID.", ephemeral=True)

        item = await self.bot.db.fetchrow(
            "SELECT i.*, t.name, t.soulbound, t.vendor_sell FROM inventory i JOIN item_templates t ON i.template_id=t.id WHERE i.id=$1 AND i.character_id=$2",
            uid, char["id"]
        )
        if not item:
            return await interaction.followup.send("❌ Item not found.", ephemeral=True)
        if item["soulbound"]:
            return await interaction.followup.send("❌ Soulbound items cannot be sold.", ephemeral=True)
        if item["is_equipped"]:
            return await interaction.followup.send("❌ Unequip first.", ephemeral=True)

        # ── Step 2: Pick price ─────────────────────────────────────────────
        if price is None:
            vendor_price = max(1, int(item.get("vendor_sell") or 10))
            price_view = _PriceSelectView(owner_id=interaction.user.id, item_name=item["name"], suggested=vendor_price)
            price_msg = await interaction.followup.send(
                f"**Set a price for {item['name']}:**",
                view=price_view,
                ephemeral=True,
                wait=True,
            )
            await price_view.wait()
            if not price_view.chosen:
                return await price_msg.edit(content="❌ Price selection timed out.", view=None)
            price = price_view.chosen

        if price <= 0:
            return await interaction.followup.send("❌ Price must be positive.", ephemeral=True)

        fee = max(1, int(price * Settings.MARKET_FEE_PERCENT / 100))
        paid = await self.svc.deduct_gold(char["id"], fee, "market listing fee")
        if not paid:
            return await interaction.followup.send(f"❌ Need **{fee}**🪙 for the listing fee.", ephemeral=True)

        await self.bot.db.execute(
            "INSERT INTO market_listings(seller_id,item_id,price,quantity) VALUES($1,$2,$3,$4)",
            char["id"], uid, price, item["quantity"]
        )
        
        # Check market seller achievement
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        await ach_svc.check_and_award(char["id"], "market_sell", {})
        
        await interaction.followup.send(embed=discord.Embed(
            title="🏪 Listed!",
            description=f"**{item['name']}** listed for **{price:,}**🪙\nFee paid: **{fee}**🪙 | Expires in 7 days.",
            color=0x00FF7F,
        ), ephemeral=True)

    @market_sell.autocomplete("item_id")
    async def market_sell_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return []
        from services.character.inventory_service import InventoryService
        inv_svc = InventoryService(self.bot.db)
        items = await inv_svc.get_all(char["id"])
        sellable = [i for i in items if not i.get("is_equipped") and not i.get("soulbound")]
        current_l = (current or "").lower()
        filtered = [i for i in sellable if current_l in i.get("name", "").lower() or current_l in str(i.get("id", "")).lower()]
        return [
            app_commands.Choice(
                name=f"{i.get('name','Item')} • {i.get('rarity','common').title()}",
                value=str(i["id"])
            )
            for i in filtered[:25]
        ]

    @market.command(name="buy", description="Purchase a market listing")
    @app_commands.describe(listing_id="Listing UUID from /market browse (or use dropdown)")
    async def market_buy(self, interaction: discord.Interaction, listing_id: Optional[str] = None):
        from services.channel_manager import check_channel
        if not await check_channel(interaction, "market"):
            return
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return await interaction.followup.send("❌ No character.", ephemeral=True)

        # ── If no listing_id, show dropdown ────────────────────────────────
        if not listing_id:
            rows = await self.bot.db.fetch(
                """SELECT ml.id, ml.price, ml.quantity, t.name, t.rarity, c.name as seller
                   FROM market_listings ml
                   JOIN inventory i ON ml.item_id=i.id
                   JOIN item_templates t ON i.template_id=t.id
                   JOIN characters c ON ml.seller_id=c.id
                   WHERE ml.is_active=TRUE AND ml.expires_at>NOW() AND ml.seller_id != $1
                   ORDER BY ml.listed_at DESC LIMIT 25""", char["id"]
            )
            if not rows:
                return await interaction.followup.send("❌ No listings available to buy.", ephemeral=True)

            view = _MarketBuyView(owner_id=interaction.user.id, listings=rows)
            msg = await interaction.followup.send("**Select a listing to purchase:**", view=view, ephemeral=True, wait=True)
            await view.wait()
            if not view.chosen:
                return await msg.edit(content="❌ Selection timed out.", view=None)
            listing_id = view.chosen

        try:
            uid = UUID(listing_id)
        except ValueError:
            return await interaction.followup.send("❌ Invalid listing ID.", ephemeral=True)

        listing = await self.bot.db.fetchrow(
            """SELECT ml.*, t.name, i.template_id, i.r_str, i.r_agi, i.r_int, i.r_spi, i.r_sta
               FROM market_listings ml JOIN inventory i ON ml.item_id=i.id
               JOIN item_templates t ON i.template_id=t.id
               WHERE ml.id=$1 AND ml.is_active=TRUE AND ml.expires_at>NOW()""", uid
        )
        if not listing:
            return await interaction.followup.send("❌ Listing not found or expired.", ephemeral=True)
        if listing["seller_id"] == char["id"]:
            return await interaction.followup.send("❌ Can't buy your own listing.", ephemeral=True)

        paid = await self.svc.deduct_gold(char["id"], listing["price"], "market purchase")
        if not paid:
            return await interaction.followup.send(f"❌ You need **{listing['price']:,}**🪙.", ephemeral=True)

        # Transfer gold to seller
        await self.svc.add_gold(listing["seller_id"], listing["price"], "market sale")

        # Transfer item to buyer, mark listing sold, remove seller's old copy
        from services.character.inventory_service import InventoryService
        inv = InventoryService(self.bot.db)
        bonus = {"r_str": listing["r_str"], "r_agi": listing["r_agi"], "r_int": listing["r_int"], "r_spi": listing["r_spi"], "r_sta": listing["r_sta"]}
        await inv.add_item(char["id"], listing["template_id"], from_="market", bonus=bonus)
        # Null out FK first, then mark sold, then clean up inventory
        seller_item_id = listing["item_id"]
        await self.bot.db.execute(
            "UPDATE market_listings SET is_active=FALSE, sold_at=NOW(), buyer_id=$2, item_id=NULL WHERE id=$1",
            uid, char["id"]
        )
        if seller_item_id:
            await self.bot.db.execute("DELETE FROM inventory WHERE id=$1", seller_item_id)
        
        # Check market buyer achievement
        from services.achievement.achievement_service import AchievementService
        ach_svc = AchievementService(self.bot.db)
        await ach_svc.check_and_award(char["id"], "market_buy", {})
        
        await interaction.followup.send(embed=discord.Embed(
            title="✅ Purchased!", description=f"You bought **{listing['name']}** for **{listing['price']:,}**🪙.", color=0x00FF7F,
        ), ephemeral=True)

    @market_buy.autocomplete("listing_id")
    async def market_buy_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        char = await self.svc.get_character(interaction.user.id)
        if not char:
            return []
        rows = await self.bot.db.fetch(
            """SELECT ml.id, ml.price, t.name, t.rarity, c.name as seller
               FROM market_listings ml
               JOIN inventory i ON ml.item_id=i.id
               JOIN item_templates t ON i.template_id=t.id
               JOIN characters c ON ml.seller_id=c.id
               WHERE ml.is_active=TRUE AND ml.expires_at>NOW() AND ml.seller_id != $1
               AND (t.name ILIKE $2 OR c.name ILIKE $2)
               ORDER BY ml.listed_at DESC LIMIT 25""",
            char["id"], f"%{current or ''}%"
        )
        return [
            app_commands.Choice(
                name=f"{r['name']} — {r['price']:,}🪙 (by {r['seller']})",
                value=str(r["id"])
            )
            for r in rows
        ]

    @app_commands.command(name="leaderboard", description="View the server leaderboard")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Level", value="level"),
        app_commands.Choice(name="Gold",  value="gold"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, sort: str = "level"):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if sort == "level":
            rows = await self.bot.db.fetch(
                "SELECT c.name, c.level, c.class, p.username FROM characters c JOIN players p ON c.player_id=p.id WHERE c.is_active ORDER BY c.level DESC, c.xp DESC LIMIT 10"
            )
            title = "🏆 Level Leaderboard"
            lines = [f"**{i+1}.** {r['name']} — Lv **{r['level']}** {r['class'].title()} | *{r['username']}*" for i, r in enumerate(rows)]
        else:
            rows = await self.bot.db.fetch(
                "SELECT c.name, c.gold, p.username FROM characters c JOIN players p ON c.player_id=p.id WHERE c.is_active ORDER BY c.gold DESC LIMIT 10"
            )
            title = "💰 Gold Leaderboard"
            lines = [f"**{i+1}.** {r['name']} — **{r['gold']:,}**🪙 | *{r['username']}*" for i, r in enumerate(rows)]
        embed = discord.Embed(title=title, description="\n".join(lines) or "No entries yet.", color=0xFFD700)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="gold", description="Check your gold balance")
    async def gold(self, interaction: discord.Interaction):
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.response.send_message("❌ No character.", ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"🪙 **{char['name']}** has **{char['gold']:,}** gold.", color=0xFFD700
        ))

async def setup(bot): await bot.add_cog(EconomyCog(bot))
