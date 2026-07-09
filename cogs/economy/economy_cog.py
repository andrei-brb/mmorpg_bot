"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        cogs/economy/economy_cog.py — /market /leaderboard /gold            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from uuid import UUID
import discord
from discord import app_commands
from discord.ext import commands
from config.settings import Settings, RARITIES
from services.character.character_service import CharacterService

log = logging.getLogger("cog.economy")


class _MarketAbort(Exception):
    """Raised inside a market transaction to roll it back and show the user a message."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EconomyCog(commands.Cog, name="Economy"):
    def __init__(self, bot): self.bot = bot; self.svc: CharacterService = None
    async def cog_load(self): self.svc = CharacterService(self.bot.db)

    market = app_commands.Group(name="market", description="Player-driven marketplace")

    @market.command(name="browse", description="Browse items for sale")
    async def browse(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await self.bot.db.fetch(
            """SELECT ml.id, ml.price, ml.quantity, ml.expires_at, t.name, t.icon, c.name as seller,
                      COALESCE(i.rarity, t.rarity) as rarity
               FROM market_listings ml
               JOIN inventory i ON ml.item_id=i.id
               JOIN item_templates t ON i.template_id=t.id
               JOIN characters c ON ml.seller_id=c.id
               WHERE ml.is_active=TRUE AND ml.expires_at>NOW()
               AND COALESCE(ml.listing_kind, 'fixed') = 'fixed'
               ORDER BY ml.listed_at DESC LIMIT 20"""
        )
        if not rows:
            return await interaction.followup.send(embed=discord.Embed(title="🏪 Marketplace", description="No items listed. Be first to sell!", color=0x2F3136))

        embed = discord.Embed(title=f"🏪 Marketplace — {len(rows)} listings", description=f"Fee: **{Settings.MARKET_FEE_PERCENT}%** of sale price", color=Settings.COLORS["reward"])
        for r in rows:
            rc = RARITIES.get(r["rarity"])
            expires = f" | expires <t:{int(r['expires_at'].timestamp())}:R>" if r["expires_at"] else ""
            embed.add_field(
                name=f"{rc.emoji if rc else '📦'} {r['name']} [{r['rarity'].title()}]",
                value=f"💰 **{r['price']:,}**🪙 × {r['quantity']} | By *{r['seller']}*{expires}\n`/market buy {r['id']}`",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @market.command(name="sell", description="List an item for sale")
    @app_commands.describe(item_id="Item UUID from /inventory", price="Listing price in gold")
    async def market_sell(self, interaction: discord.Interaction, item_id: str, price: int):
        await interaction.response.defer()
        if price <= 0: return await interaction.followup.send("❌ Price must be positive.")
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        try: uid = UUID(item_id)
        except ValueError: return await interaction.followup.send("❌ Invalid item ID.")

        fee = max(1, int(price * Settings.MARKET_FEE_PERCENT / 100))

        msg = await interaction.followup.send("⏳ Processing…", wait=True)

        # Lock the inventory row FOR UPDATE so re-validation, the duplicate-listing
        # guard, fee, and insert are atomic — prevents listing the same item twice
        # (and paying the fee twice) and prevents losing the fee if the insert fails.
        try:
            async with self.bot.db.transaction() as tx:
                item = await tx.fetchrow(
                    "SELECT i.*, t.name, t.soulbound FROM inventory i JOIN item_templates t ON i.template_id=t.id WHERE i.id=$1 AND i.character_id=$2 FOR UPDATE OF i",
                    uid, char["id"]
                )
                if not item:
                    raise _MarketAbort("❌ Item not found.")
                if item["soulbound"]:
                    raise _MarketAbort("❌ Soulbound items cannot be sold.")
                if item["is_equipped"]:
                    raise _MarketAbort("❌ Unequip first.")

                already = await tx.fetchval(
                    "SELECT 1 FROM market_listings WHERE item_id=$1 AND is_active=TRUE AND sold_at IS NULL",
                    uid,
                )
                if already:
                    raise _MarketAbort("❌ That item is already listed on the market.")

                paid = await CharacterService(tx).deduct_gold(char["id"], fee, "market listing fee")
                if not paid:
                    raise _MarketAbort(f"❌ Need **{fee}**🪙 for the listing fee.")

                await tx.execute(
                    "INSERT INTO market_listings(seller_id,item_id,price,quantity) VALUES($1,$2,$3,$4)",
                    char["id"], uid, price, item["quantity"]
                )
                item_name = item["name"]
        except _MarketAbort as e:
            return await msg.edit(content=e.message)

        await msg.edit(content=None, embed=discord.Embed(
            title="🏪 Listed!",
            description=f"**{item_name}** listed for **{price:,}**🪙\nFee: **{fee}**🪙 ({Settings.MARKET_FEE_PERCENT}% of {price:,}) | Expires in 7 days.",
            color=Settings.COLORS["success"],
        ))

    @market.command(name="buy", description="Purchase a market listing")
    @app_commands.describe(listing_id="Listing UUID from /market browse")
    async def market_buy(self, interaction: discord.Interaction, listing_id: str):
        await interaction.response.defer()
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.followup.send("❌ No character.")
        try: uid = UUID(listing_id)
        except ValueError: return await interaction.followup.send("❌ Invalid listing ID.")

        from services.character.inventory_service import InventoryService

        msg = await interaction.followup.send("⏳ Processing…", wait=True)

        # Whole purchase is atomic: the listing row is locked FOR UPDATE so two buyers
        # can't both pass the is_active check, and any failure rolls back gold + item.
        try:
            async with self.bot.db.transaction() as tx:
                listing = await tx.fetchrow(
                    """SELECT ml.*, t.name, i.template_id,
                              i.rarity, i.r_str, i.r_agi, i.r_int, i.r_spi, i.r_sta,
                              i.r_haste, i.r_lifesteal, i.r_resistance, i.r_hit_rating,
                              COALESCE(i.enhancement_level, 0) as enhancement_level
                       FROM market_listings ml JOIN inventory i ON ml.item_id=i.id
                       JOIN item_templates t ON i.template_id=t.id
                       WHERE ml.id=$1 AND ml.is_active=TRUE AND ml.expires_at>NOW()
                       AND COALESCE(ml.listing_kind, 'fixed') = 'fixed'
                       FOR UPDATE OF ml""", uid
                )
                if not listing:
                    raise _MarketAbort("❌ Listing not found or expired.")
                if listing["seller_id"] == char["id"]:
                    raise _MarketAbort("❌ Can't buy your own listing.")

                char_svc = CharacterService(tx)
                inv = InventoryService(tx)

                paid = await char_svc.deduct_gold(char["id"], listing["price"], "market purchase")
                if not paid:
                    raise _MarketAbort(f"❌ You need **{listing['price']:,}**🪙.")

                # Transfer item to buyer first — preserve rarity and all stats.
                rarity = listing.get("rarity") or "common"
                bonus = {
                    "r_str": listing.get("r_str", 0) or 0,
                    "r_agi": listing.get("r_agi", 0) or 0,
                    "r_int": listing.get("r_int", 0) or 0,
                    "r_spi": listing.get("r_spi", 0) or 0,
                    "r_sta": listing.get("r_sta", 0) or 0,
                    "r_haste": listing.get("r_haste", 0) or 0,
                    "r_lifesteal": listing.get("r_lifesteal", 0) or 0,
                    "r_resistance": listing.get("r_resistance", 0) or 0,
                    "r_hit_rating": listing.get("r_hit_rating", 0) or 0,
                }
                enhancement_level = listing.get("enhancement_level", 0) or 0
                ok, add_msg = await inv.add_item(
                    char["id"], listing["template_id"], rarity=rarity,
                    from_="market", bonus=bonus, enhancement_level=enhancement_level,
                )
                if not ok:
                    # Rolls back the gold deduction too — buyer keeps their gold.
                    raise _MarketAbort(f"❌ Couldn't receive the item: {add_msg}")

                # Pay the seller and finalize only after the item is safely delivered.
                await char_svc.add_gold(listing["seller_id"], listing["price"], "market sale")
                await tx.execute("DELETE FROM inventory WHERE id=$1", listing["item_id"])
                await tx.execute(
                    "UPDATE market_listings SET is_active=FALSE, sold_at=NOW(), buyer_id=$2 WHERE id=$1",
                    uid, char["id"],
                )
                bought_name, bought_price = listing["name"], listing["price"]
        except _MarketAbort as e:
            return await msg.edit(content=e.message)

        await msg.edit(content=None, embed=discord.Embed(
            title="✅ Purchased!", description=f"You bought **{bought_name}** for **{bought_price:,}**🪙.", color=Settings.COLORS["success"],
        ))

    @app_commands.command(name="leaderboard", description="View the server leaderboard")
    @app_commands.choices(sort=[
        app_commands.Choice(name="Level", value="level"),
        app_commands.Choice(name="Gold",  value="gold"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, sort: str = "level"):
        if not interaction.guild_id:
            return await interaction.response.send_message(
                "❌ Use this command in a server to see that server's leaderboard.",
                ephemeral=True,
            )
        await interaction.response.defer()
        guild_id = int(interaction.guild_id)
        if sort == "level":
            rows = await self.bot.db.fetch(
                """SELECT c.name, c.level, c.class, p.username
                   FROM characters c JOIN players p ON c.player_id=p.id
                   WHERE c.is_active AND c.last_discord_guild_id=$1
                   ORDER BY c.level DESC, c.xp DESC LIMIT 10""",
                guild_id,
            )
            title = "🏆 Level Leaderboard"
            lines = [f"**{i+1}.** {r['name']} — Lv **{r['level']}** {r['class'].title()} | *{r['username']}*" for i, r in enumerate(rows)]
        else:
            rows = await self.bot.db.fetch(
                """SELECT c.name, c.gold, p.username
                   FROM characters c JOIN players p ON c.player_id=p.id
                   WHERE c.is_active AND c.last_discord_guild_id=$1
                   ORDER BY c.gold DESC LIMIT 10""",
                guild_id,
            )
            title = "💰 Gold Leaderboard"
            lines = [f"**{i+1}.** {r['name']} — **{r['gold']:,}**🪙 | *{r['username']}*" for i, r in enumerate(rows)]
        embed = discord.Embed(title=title, description="\n".join(lines) or "No entries yet.", color=Settings.COLORS["reward"])
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="gold", description="Check your gold balance")
    async def gold(self, interaction: discord.Interaction):
        char = await self.svc.get_character(interaction.user.id)
        if not char: return await interaction.response.send_message("❌ No character.", ephemeral=True)
        await interaction.response.send_message(embed=discord.Embed(
            description=f"🪙 **{char['name']}** has **{char['gold']:,}** gold.", color=Settings.COLORS["reward"]
        ))

async def setup(bot): await bot.add_cog(EconomyCog(bot))
