"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          services/character/inventory_service.py — Items & Loot            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from config.settings import RARITIES, Settings

log = logging.getLogger("inventory")


class InventoryService:
    def __init__(self, db):
        self.db = db

    # ── Loot generation ───────────────────────────────────────────────────────

    def roll_rarity(self, luck: float = 0.0) -> str:
        items = list(RARITIES.items())
        weights = [cfg.drop_weight for _, cfg in items]
        if luck > 0:
            for i in range(len(weights)):
                if i >= 2:  # rare+
                    weights[i] *= 1 + luck * 0.12
        keys = [k for k, _ in items]
        return random.choices(keys, weights=weights)[0]

    def roll_bonus_stats(self, template: dict, rarity: str) -> Dict[str, int]:
        mult = RARITIES[rarity].stat_multiplier
        bonus = {}
        # Primary stats
        for stat in ("s_str", "s_agi", "s_int", "s_spi", "s_sta"):
            base = template.get(stat, 0)
            if base > 0:
                rolled = int(base * random.uniform(0.85, 1.15) * mult)
                bonus[stat.replace("s_", "r_")] = rolled - base
            else:
                bonus[stat.replace("s_", "r_")] = 0
        # Secondary stats (can roll even if base is 0 for rare+ items)
        for stat in ("s_haste", "s_lifesteal", "s_resistance", "s_hit_rating"):
            base = template.get(stat, 0)
            if base > 0 or rarity in ("rare", "epic", "legendary", "artifact"):
                # Secondary stats have lower chance to roll
                if random.random() < 0.4:  # 40% chance
                    rolled = int((base + random.randint(1, 3)) * random.uniform(0.85, 1.15) * mult)
                    bonus[stat.replace("s_", "r_")] = rolled - base
                else:
                    bonus[stat.replace("s_", "r_")] = 0
            else:
                bonus[stat.replace("s_", "r_")] = 0
        return bonus

    async def generate_loot(
        self, zone_key: str, char_level: int, is_boss: bool = False, luck: float = 0.0
    ) -> Optional[Dict]:
        drop_chance = 1.0 if is_boss else 0.42
        if random.random() > drop_chance:
            return None

        rarity = self.roll_rarity(luck)

        rows = await self.db.fetch(
            """SELECT * FROM item_templates
               WHERE level_req <= $1 AND item_type NOT IN ('quest')
               ORDER BY RANDOM() LIMIT 1""",
            char_level,
        )
        if not rows:
            return None

        tmpl = dict(rows[0])
        bonus = self.roll_bonus_stats(tmpl, rarity)
        return {"template": tmpl, "rarity": rarity, "bonus": bonus}

    # ── Add / remove items ────────────────────────────────────────────────────

    async def add_item(
        self,
        char_id: UUID,
        template_id: str,
        rarity: str = "common",
        quantity: int = 1,
        bonus: Optional[Dict] = None,
        from_: str = "drop",
    ) -> Tuple[bool, str]:
        # Check capacity
        count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE character_id=$1", char_id
        )
        player = await self.db.fetchrow(
            """SELECT p.is_premium FROM players p
               JOIN characters c ON c.player_id=p.id WHERE c.id=$1""", char_id
        )
        max_slots = Settings.PREMIUM_INVENTORY_SLOTS if (player and player["is_premium"]) \
                    else Settings.FREE_INVENTORY_SLOTS
        if count >= max_slots:
            return False, f"Inventory full ({count}/{max_slots})."

        tmpl = await self.db.fetchrow("SELECT * FROM item_templates WHERE id=$1", template_id)
        if not tmpl:
            return False, "Item template not found."

        # Stack consumables/materials (only if same rarity)
        if tmpl["max_stack"] > 1:
            existing = await self.db.fetchrow(
                "SELECT id, quantity FROM inventory WHERE character_id=$1 AND template_id=$2 AND rarity=$3 LIMIT 1",
                char_id, template_id, rarity,
            )
            if existing and existing["quantity"] < tmpl["max_stack"]:
                new_qty = min(existing["quantity"] + quantity, tmpl["max_stack"])
                await self.db.execute(
                    "UPDATE inventory SET quantity=$2 WHERE id=$1", existing["id"], new_qty
                )
                return True, "Stacked."

        # Generate bonus stats based on rarity if not provided
        if bonus is None:
            bonus = self.roll_bonus_stats(dict(tmpl), rarity)
        
        # Insert with rarity and all bonus stats
        await self.db.execute(
            """INSERT INTO inventory
               (character_id,template_id,quantity,rarity,
                r_str,r_agi,r_int,r_spi,r_sta,
                r_haste,r_lifesteal,r_resistance,r_hit_rating,
                obtained_from)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
            char_id, template_id, quantity, rarity,
            bonus.get("r_str",0), bonus.get("r_agi",0), bonus.get("r_int",0),
            bonus.get("r_spi",0), bonus.get("r_sta",0),
            bonus.get("r_haste",0), bonus.get("r_lifesteal",0),
            bonus.get("r_resistance",0), bonus.get("r_hit_rating",0),
            from_,
        )
        return True, f"Added {RARITIES.get(rarity, RARITIES['common']).name} item."

    # ── Equip / unequip ───────────────────────────────────────────────────────

    async def equip(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str]:
        item = await self.db.fetchrow(
            """SELECT i.*, t.equip_slot, t.level_req, t.class_req, t.name
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.id=$1 AND i.character_id=$2""",
            item_id, char_id,
        )
        if not item:   return False, "Item not in your inventory."
        if not item["equip_slot"]: return False, "This item cannot be equipped."

        char = await self.db.fetchrow("SELECT level, class FROM characters WHERE id=$1", char_id)
        if char["level"] < item["level_req"]:
            return False, f"Requires level **{item['level_req']}**."
        if item["class_req"] and item["class_req"] != char["class"]:
            return False, f"Only **{item['class_req'].title()}** can equip this."

        # Unequip old item in that slot
        await self.db.execute(
            "UPDATE inventory SET is_equipped=FALSE, equip_slot=NULL "
            "WHERE character_id=$1 AND equip_slot=$2 AND is_equipped=TRUE",
            char_id, item["equip_slot"],
        )
        await self.db.execute(
            "UPDATE inventory SET is_equipped=TRUE, equip_slot=$2 WHERE id=$1",
            item_id, item["equip_slot"],
        )
        return True, f"Equipped **{item['name']}**."

    async def unequip_slot(self, char_id: UUID, slot: str) -> Tuple[bool, str]:
        res = await self.db.execute(
            "UPDATE inventory SET is_equipped=FALSE, equip_slot=NULL "
            "WHERE character_id=$1 AND equip_slot=$2 AND is_equipped=TRUE",
            char_id, slot,
        )
        return ("0" not in res, f"Unequipped **{slot}** slot." if "0" not in res else f"Nothing in {slot}.")

    # ── Get inventory ─────────────────────────────────────────────────────────

    async def get_all(self, char_id: UUID) -> List[dict]:
        rows = await self.db.fetch(
            """SELECT i.*, t.name, t.description, t.item_type,
                     t.equip_slot, t.icon, t.vendor_sell, t.soulbound, t.level_req,
                     t.s_str,t.s_agi,t.s_int,t.s_spi,t.s_sta,t.s_armor,
                     t.s_dmg_min,t.s_dmg_max,
                     t.s_haste,t.s_lifesteal,t.s_resistance,t.s_hit_rating,
                     i.r_str,i.r_agi,i.r_int,i.r_spi,i.r_sta,
                     i.r_haste,i.r_lifesteal,i.r_resistance,i.r_hit_rating,
                     COALESCE(i.rarity, t.rarity) as rarity
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.character_id=$1
               ORDER BY i.is_equipped DESC, COALESCE(i.rarity, t.rarity) DESC, t.name""",
            char_id,
        )
        return [dict(r) for r in rows]

    async def get_equipped(self, char_id: UUID) -> Dict[str, dict]:
        rows = await self.db.fetch(
            """SELECT i.*, t.name, t.rarity, t.icon, t.s_str,t.s_agi,
                      t.s_int,t.s_spi,t.s_sta,t.s_armor,t.s_dmg_min,t.s_dmg_max
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.character_id=$1 AND i.is_equipped=TRUE""",
            char_id,
        )
        return {r["equip_slot"]: dict(r) for r in rows}

    # ── Use consumable ────────────────────────────────────────────────────────

    async def use_consumable(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str, Optional[Dict]]:
        item = await self.db.fetchrow(
            """SELECT i.*, t.item_type, t.effect_type, t.effect_value,
                      t.effect_duration, t.name
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.id=$1 AND i.character_id=$2""",
            item_id, char_id,
        )
        if not item: return False, "Item not found.", None
        if item["item_type"] != "consumable": return False, "Not a consumable.", None

        if item["quantity"] > 1:
            await self.db.execute("UPDATE inventory SET quantity=quantity-1 WHERE id=$1", item_id)
        else:
            await self.db.execute("DELETE FROM inventory WHERE id=$1", item_id)

        return True, f"Used **{item['name']}**.", {
            "type": item["effect_type"], "value": item["effect_value"], "duration": item["effect_duration"]
        }

    # ── Sell ─────────────────────────────────────────────────────────────────

    async def sell(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str, int]:
        item = await self.db.fetchrow(
            """SELECT i.*, t.vendor_sell, t.name, t.soulbound, t.rarity as template_rarity,
                      COALESCE(i.rarity, t.rarity) as rarity
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.id=$1 AND i.character_id=$2""",
            item_id, char_id,
        )
        if not item:         return False, "Item not found.", 0
        if item["locked"]:   return False, "Item is locked. Unlock it first.", 0
        if item["soulbound"]:return False, "Soulbound items cannot be sold.", 0
        if item["is_equipped"]: return False, "Unequip the item before selling.", 0

        # Calculate value based on actual rarity (not template rarity)
        base_value = item["vendor_sell"] or 0
        actual_rarity = item.get("rarity") or "common"
        rarity_mult = RARITIES.get(actual_rarity, RARITIES["common"]).stat_multiplier
        
        # Scale value by rarity multiplier
        # Also add bonus for extra stats (sum of all bonus stats)
        bonus_stats_total = (
            (item.get("r_str", 0) or 0) +
            (item.get("r_agi", 0) or 0) +
            (item.get("r_int", 0) or 0) +
            (item.get("r_spi", 0) or 0) +
            (item.get("r_sta", 0) or 0) +
            (item.get("r_haste", 0) or 0) +
            (item.get("r_lifesteal", 0) or 0) +
            (item.get("r_resistance", 0) or 0) +
            (item.get("r_hit_rating", 0) or 0)
        )
        
        # Base value scaled by rarity, plus small bonus for extra stats
        value = int(base_value * rarity_mult) + (bonus_stats_total * 2)
        gold = value * item["quantity"]
        
        await self.db.execute("DELETE FROM inventory WHERE id=$1", item_id)
        return True, f"Sold **{item['name']}** [{actual_rarity.title()}] for **{gold}**🪙.", gold
