"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          services/character/inventory_service.py — Items & Loot            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from config.settings import RARITIES, Settings, zone_tier_for_loot, loot_level_req_bounds, ZONES, DUNGEONS

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

    def roll_bonus_stats(self, template: dict, rarity: str, zone_tier: int = 1) -> Dict[str, int]:
        # Only equippable gear should receive rolled combat stats.
        # Consumables/materials/quest items must never have STR/AGI/etc.
        if not template.get("equip_slot"):
            return {
                "r_str": 0, "r_agi": 0, "r_int": 0, "r_spi": 0, "r_sta": 0,
                "r_haste": 0, "r_lifesteal": 0, "r_resistance": 0, "r_hit_rating": 0,
            }

        mult = RARITIES[rarity].stat_multiplier
        zone_tier = max(1, min(5, int(zone_tier)))
        zone_tier_bonus = 1.0 + (zone_tier - 1) * 0.12
        bonus = {}
        
        # Calculate total stat budget based on template and rarity
        # Sum all primary stats from template
        total_base_stats = sum([
            template.get("s_str", 0),
            template.get("s_agi", 0),
            template.get("s_int", 0),
            template.get("s_spi", 0),
            template.get("s_sta", 0),
        ])
        
        # Calculate stat budget: base stats × multiplier × zone tier × random variation
        # This gives us a pool of stat points to distribute
        stat_budget = int(total_base_stats * mult * zone_tier_bonus * random.uniform(0.90, 1.20))
        
        # For items with no base stats, give a minimum budget based on rarity
        if stat_budget == 0:
            min_budgets = {
                "common": 5, "uncommon": 8, "rare": 15,
                "epic": 25, "legendary": 40, "artifact": 60
            }
            stat_budget = random.randint(
                min_budgets.get(rarity, 5),
                int(min_budgets.get(rarity, 5) * 1.5)
            )
            stat_budget = int(stat_budget * zone_tier_bonus)
        
        # Determine which stats can receive bonuses
        # For rare+ items, all stats can get bonuses even if template has 0
        can_roll_stats = []
        for stat in ("s_str", "s_agi", "s_int", "s_spi", "s_sta"):
            base = template.get(stat, 0)
            if base > 0 or rarity in ("rare", "epic", "legendary", "artifact"):
                can_roll_stats.append(stat)
        
        if not can_roll_stats:
            can_roll_stats = ["s_str", "s_agi", "s_int", "s_spi", "s_sta"]
        
        # Randomly distribute stat budget across available stats
        # This creates variation - one item might get more STR, another more STA
        remaining_budget = stat_budget
        num_stats = len(can_roll_stats)
        
        for i, stat in enumerate(can_roll_stats):
            if i == len(can_roll_stats) - 1:
                # Last stat gets remaining budget
                allocated = remaining_budget
            else:
                # Random allocation (weighted towards higher values for better items)
                if rarity in ("legendary", "artifact"):
                    # Higher rarity gets more consistent distribution
                    min_alloc = int(remaining_budget / (num_stats - i) * 0.6)
                    max_alloc = int(remaining_budget / (num_stats - i) * 1.4)
                else:
                    # Lower rarity gets more random
                    min_alloc = int(remaining_budget / (num_stats - i) * 0.3)
                    max_alloc = int(remaining_budget / (num_stats - i) * 1.7)
                
                allocated = random.randint(
                    max(0, min_alloc),
                    max(1, max_alloc)
                )
                allocated = min(allocated, remaining_budget)
            
            base = template.get(stat, 0)
            # Bonus is the allocated amount minus base (if any)
            bonus[stat.replace("s_", "r_")] = allocated - base
            remaining_budget -= allocated
        
        # Secondary stats (can roll even if base is 0 for rare+ items)
        for stat in ("s_haste", "s_lifesteal", "s_resistance", "s_hit_rating"):
            base = template.get(stat, 0)
            if base > 0 or rarity in ("rare", "epic", "legendary", "artifact"):
                # Higher chance for higher rarity
                chance = 0.3 if rarity == "rare" else (0.5 if rarity == "epic" else 0.7)
                if random.random() < chance:
                    # Roll value based on rarity
                    min_val = 1 if rarity in ("rare", "epic") else 3
                    max_val = int(5 * mult * zone_tier_bonus) if rarity in ("rare", "epic") else int(10 * mult * zone_tier_bonus)
                    rolled = random.randint(min_val, max_val)
                    bonus[stat.replace("s_", "r_")] = rolled - base
                else:
                    bonus[stat.replace("s_", "r_")] = 0
            else:
                bonus[stat.replace("s_", "r_")] = 0
        
        return bonus

    async def generate_loot(
        self, zone_key: str, char_level: int, is_boss: bool = False, luck: float = 0.0
    ) -> Optional[Dict]:
        drop_chance = 1.0 if is_boss else float(getattr(Settings, "LOOT_DROP_CHANCE_NORMAL", 0.5))
        if random.random() > drop_chance:
            return None

        rarity = self.roll_rarity(luck)

        band_lo, band_hi = loot_level_req_bounds(zone_key, char_level)

        # Prefer zone/dungeon loot pools; constrain level_req to zone/player band (not char_level alone).
        pool: Tuple[str, ...] = ()
        try:
            if zone_key in DUNGEONS:
                pool = tuple(DUNGEONS[zone_key].loot_pool or ())
            elif zone_key in ZONES:
                pool = tuple(ZONES[zone_key].loot_pool or ())
        except Exception:
            pool = ()

        tmpl: Optional[dict] = None
        if pool:
            for _ in range(min(12, len(pool) * 2)):
                tid = random.choice(pool)
                row = await self.db.fetchrow(
                    """SELECT * FROM item_templates
                       WHERE id=$1 AND level_req >= $2 AND level_req <= $3
                         AND item_type NOT IN ('quest')""",
                    tid,
                    band_lo,
                    band_hi,
                )
                if row:
                    tmpl = dict(row)
                    break

        if tmpl is None:
            row = await self.db.fetchrow(
                """SELECT * FROM item_templates
                   WHERE level_req >= $1 AND level_req <= $2 AND item_type NOT IN ('quest')
                   ORDER BY RANDOM() LIMIT 1""",
                band_lo,
                band_hi,
            )
            if row is None and band_lo > 1:
                row = await self.db.fetchrow(
                    """SELECT * FROM item_templates
                       WHERE level_req >= $1 AND level_req <= $2 AND item_type NOT IN ('quest')
                       ORDER BY RANDOM() LIMIT 1""",
                    1,
                    band_hi,
                )
            if not row:
                return None
            tmpl = dict(row)

        tier = zone_tier_for_loot(zone_key)
        bonus = self.roll_bonus_stats(tmpl, rarity, zone_tier=tier)
        return {"template": tmpl, "rarity": rarity, "bonus": bonus}

    _MAIN_STORY_GEAR_SQL = (
        "equip_slot IS NOT NULL AND item_type IN ('weapon','armor','accessory')"
    )

    async def roll_main_story_quest_gear_drop(
        self, zone_key: str, char_level: int
    ) -> Optional[Dict]:
        """
        One guaranteed roll for lore-main quest completion when the template has no item rewards.
        Rarity is 50/50 rare vs epic; template is level-banded like zone loot (equippable gear only).
        """
        rarity = random.choice(["rare", "epic"])
        band_lo, band_hi = loot_level_req_bounds(zone_key, char_level)
        gear = self._MAIN_STORY_GEAR_SQL

        pool: Tuple[str, ...] = ()
        try:
            if zone_key in DUNGEONS:
                pool = tuple(DUNGEONS[zone_key].loot_pool or ())
            elif zone_key in ZONES:
                pool = tuple(ZONES[zone_key].loot_pool or ())
        except Exception:
            pool = ()

        tmpl: Optional[dict] = None
        if pool:
            for _ in range(min(16, max(8, len(pool) * 2))):
                tid = random.choice(pool)
                row = await self.db.fetchrow(
                    f"""SELECT * FROM item_templates
                       WHERE id=$1 AND level_req >= $2 AND level_req <= $3
                         AND {gear}""",
                    tid,
                    band_lo,
                    band_hi,
                )
                if row:
                    tmpl = dict(row)
                    break

        if tmpl is None:
            row = await self.db.fetchrow(
                f"""SELECT * FROM item_templates
                   WHERE level_req >= $1 AND level_req <= $2 AND {gear}
                   ORDER BY RANDOM() LIMIT 1""",
                band_lo,
                band_hi,
            )
            if row is None and band_lo > 1:
                row = await self.db.fetchrow(
                    f"""SELECT * FROM item_templates
                       WHERE level_req >= $1 AND level_req <= $2 AND {gear}
                       ORDER BY RANDOM() LIMIT 1""",
                    1,
                    band_hi,
                )
            if not row:
                return None
            tmpl = dict(row)

        tier = zone_tier_for_loot(zone_key)
        bonus = self.roll_bonus_stats(tmpl, rarity, zone_tier=tier)
        return {"template": tmpl, "rarity": rarity, "bonus": bonus}

    async def grant_main_story_quest_gear_bonus_if_needed(
        self,
        char_id: UUID,
        *,
        is_main_story: bool,
        template_item_reward_ids: List[str],
        zone_key: str,
        char_level: int,
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        """
        If this is a main-story quest and the template listed no item rewards, grant one
        rare or epic piece of level-appropriate gear. Returns (granted_ids, failed_rows).
        """
        granted: List[str] = []
        failed: List[Dict[str, str]] = []
        if not is_main_story or template_item_reward_ids:
            return granted, failed

        loot = await self.roll_main_story_quest_gear_drop(zone_key, char_level)
        if not loot:
            return granted, failed

        tid = str(loot["template"]["id"])
        ok, msg = await self.add_item(
            char_id,
            tid,
            rarity=str(loot["rarity"]),
            bonus=loot["bonus"],
            from_="quest_reward",
        )
        if ok:
            granted.append(tid)
        else:
            failed.append({"template_id": tid, "reason": str(msg or "could_not_add")})
        return granted, failed

    async def can_add_reward_items(
        self,
        char_id: UUID,
        template_ids: List[str],
    ) -> Tuple[bool, str]:
        """
        Preflight check for quest reward delivery.
        Returns False if any template is missing or inventory lacks slots/stack room.
        """
        if not template_ids:
            return True, "ok"

        player = await self.db.fetchrow(
            """SELECT p.is_premium FROM players p
               JOIN characters c ON c.player_id=p.id WHERE c.id=$1""",
            char_id,
        )
        max_slots = (
            Settings.PREMIUM_INVENTORY_SLOTS
            if (player and player["is_premium"])
            else Settings.FREE_INVENTORY_SLOTS
        )
        # Inventory slot limits should apply to BAG items (unequipped),
        # not to equipped gear rows.
        current_slots = int(
            await self.db.fetchval(
                "SELECT COUNT(*) FROM inventory WHERE character_id=$1 AND COALESCE(is_equipped,FALSE)=FALSE",
                char_id,
            )
            or 0
        )
        needed_new_slots = 0
        stack_free_cache: Dict[Tuple[str, str], int] = {}

        for tid in template_ids:
            tmpl = await self.db.fetchrow(
                "SELECT id, name, rarity, max_stack FROM item_templates WHERE id=$1",
                tid,
            )
            if not tmpl:
                return False, f"Reward item template missing: {tid}"

            rarity = str(tmpl.get("rarity") or "common")
            max_stack = int(tmpl.get("max_stack") or 1)
            key = (str(tid), rarity)

            if max_stack > 1:
                if key not in stack_free_cache:
                    free = await self.db.fetchval(
                        """
                        SELECT COALESCE(SUM($4 - i.quantity), 0)
                        FROM inventory i
                        WHERE i.character_id=$1
                          AND i.template_id=$2
                          AND COALESCE(i.rarity::text, 'common') = COALESCE($3::text, 'common')
                          AND i.quantity < $4
                          AND COALESCE(i.is_equipped,FALSE)=FALSE
                        """,
                        char_id,
                        tid,
                        rarity,
                        max_stack,
                    )
                    stack_free_cache[key] = int(free or 0)
                if stack_free_cache[key] > 0:
                    stack_free_cache[key] -= 1
                    continue

            needed_new_slots += 1

        if current_slots + needed_new_slots > max_slots:
            missing = current_slots + needed_new_slots - max_slots
            return (
                False,
                f"Bag is full for unequipped items ({current_slots}/{max_slots}). "
                f"Free {missing} bag slot(s) to claim quest rewards (equipped gear does not count).",
            )
        return True, "ok"

    # ── Add / remove items ────────────────────────────────────────────────────

    async def add_item(
        self,
        char_id: UUID,
        template_id: str,
        rarity: str = "common",
        quantity: int = 1,
        bonus: Optional[Dict] = None,
        from_: str = "drop",
        enhancement_level: int = 0,
        locked: bool = False,
    ) -> Tuple[bool, str]:
        tmpl = await self.db.fetchrow("SELECT * FROM item_templates WHERE id=$1", template_id)
        if not tmpl:
            return False, "Item template not found."

        player = await self.db.fetchrow(
            """SELECT p.is_premium FROM players p
               JOIN characters c ON c.player_id=p.id WHERE c.id=$1""", char_id
        )
        max_slots = Settings.PREMIUM_INVENTORY_SLOTS if (player and player["is_premium"]) \
                    else Settings.FREE_INVENTORY_SLOTS

        max_stack = int(tmpl["max_stack"] or 1)

        # Stack consumables/materials (same template + rarity); fill stacks and overflow into new rows.
        if max_stack > 1:
            remaining = int(quantity)
            if remaining <= 0:
                return True, "Nothing added."
            while remaining > 0:
                existing = await self.db.fetchrow(
                    """SELECT id, quantity FROM inventory i
                       WHERE i.character_id=$1 AND i.template_id=$2
                         AND COALESCE(i.rarity::text, 'common') = COALESCE($3::text, 'common')
                         AND i.quantity < $4
                       ORDER BY i.obtained_at NULLS FIRST
                       LIMIT 1""",
                    char_id, template_id, rarity, max_stack,
                )
                if existing:
                    space = max_stack - int(existing["quantity"] or 0)
                    add = min(remaining, space)
                    await self.db.execute(
                        "UPDATE inventory SET quantity = quantity + $2 WHERE id = $1",
                        existing["id"], add,
                    )
                    remaining -= add
                    continue
                count = await self.db.fetchval(
                    "SELECT COUNT(*) FROM inventory WHERE character_id=$1 AND COALESCE(is_equipped,FALSE)=FALSE", char_id
                )
                if count >= max_slots:
                    return False, f"Inventory full ({count}/{max_slots})."
                chunk = min(remaining, max_stack)
                if bonus is None:
                    bonus = self.roll_bonus_stats(dict(tmpl), rarity)
                await self.db.execute(
                    """INSERT INTO inventory
                       (character_id,template_id,quantity,rarity,
                        r_str,r_agi,r_int,r_spi,r_sta,
                        r_haste,r_lifesteal,r_resistance,r_hit_rating,
                        enhancement_level,obtained_from,locked)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)""",
                    char_id, template_id, chunk, rarity,
                    bonus.get("r_str",0), bonus.get("r_agi",0), bonus.get("r_int",0),
                    bonus.get("r_spi",0), bonus.get("r_sta",0),
                    bonus.get("r_haste",0), bonus.get("r_lifesteal",0),
                    bonus.get("r_resistance",0), bonus.get("r_hit_rating",0),
                    enhancement_level, from_, locked,
                )
                remaining -= chunk
                bonus = None
            return True, "Stacked."

        # Non-stackable (gear, etc.): one row per item.
        count = await self.db.fetchval(
            "SELECT COUNT(*) FROM inventory WHERE character_id=$1 AND COALESCE(is_equipped,FALSE)=FALSE", char_id
        )
        if count >= max_slots:
            return False, f"Inventory full ({count}/{max_slots})."

        # Generate bonus stats based on rarity if not provided
        if bonus is None:
            bonus = self.roll_bonus_stats(dict(tmpl), rarity)

        # Insert with rarity and all bonus stats
        await self.db.execute(
            """INSERT INTO inventory
               (character_id,template_id,quantity,rarity,
                r_str,r_agi,r_int,r_spi,r_sta,
                r_haste,r_lifesteal,r_resistance,r_hit_rating,
                enhancement_level,obtained_from,locked)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)""",
            char_id, template_id, quantity, rarity,
            bonus.get("r_str",0), bonus.get("r_agi",0), bonus.get("r_int",0),
            bonus.get("r_spi",0), bonus.get("r_sta",0),
            bonus.get("r_haste",0), bonus.get("r_lifesteal",0),
            bonus.get("r_resistance",0), bonus.get("r_hit_rating",0),
            enhancement_level, from_, locked,
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
                     t.tradeable,
                     t.equip_slot AS template_equip_slot, t.icon, t.vendor_sell, t.soulbound, t.level_req,
                     t.effect_type, t.effect_value, t.effect_duration,
                     t.s_str,t.s_agi,t.s_int,t.s_spi,t.s_sta,t.s_armor,
                     t.s_dmg_min,t.s_dmg_max,
                     t.s_haste,t.s_lifesteal,t.s_resistance,t.s_hit_rating,
                     i.r_str,i.r_agi,i.r_int,i.r_spi,i.r_sta,
                     i.r_haste,i.r_lifesteal,i.r_resistance,i.r_hit_rating,
                     COALESCE(i.rarity, t.rarity) as rarity,
                     COALESCE(i.enhancement_level, 0) as enhancement_level
               FROM inventory i
               JOIN item_templates t ON i.template_id=t.id
               LEFT JOIN market_listings ml ON i.id=ml.item_id AND ml.is_active=TRUE
               WHERE i.character_id=$1 AND ml.id IS NULL
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

    # ── Durability & repair ───────────────────────────────────────────────────

    async def damage_equipped(self, char_id: UUID, points: int) -> None:
        """Reduce durability on all equipped items (floored at 0). Used on combat defeat."""
        await self.db.execute(
            "UPDATE inventory SET durability = GREATEST(0, durability - $2) "
            "WHERE character_id=$1 AND is_equipped=TRUE",
            char_id, points,
        )

    async def get_repair_quote(self, char_id: UUID) -> Tuple[int, List[dict]]:
        """Total gold cost to restore all equipped items to 100 durability, plus per-item lines."""
        from config.settings import Settings

        rows = await self.db.fetch(
            """SELECT i.id, i.durability, t.name, t.icon,
                      COALESCE(i.rarity, t.rarity) AS rarity
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.character_id=$1 AND i.is_equipped=TRUE AND i.durability < 100""",
            char_id,
        )
        total = 0
        items = []
        for r in rows:
            missing = 100 - int(r["durability"])
            mult = Settings.REPAIR_RARITY_MULT.get(str(r["rarity"] or "common").lower(), 1)
            cost = missing * Settings.REPAIR_COST_PER_POINT * mult
            total += cost
            items.append({**dict(r), "missing": missing, "cost": cost})
        return total, items

    async def repair_all(self, char_id: UUID) -> None:
        """Restore all equipped items to full durability (charge gold before calling)."""
        await self.db.execute(
            "UPDATE inventory SET durability = 100 "
            "WHERE character_id=$1 AND is_equipped=TRUE AND durability < 100",
            char_id,
        )

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
        if item["effect_type"] not in (
            "heal_hp",
            "boost_sta",
            "boost_str",
            "boost_agi",
            "boost_int",
            "boost_spi",
            "boost_max_hp",
            "boost_resistance",
        ):
            return False, "This consumable can't be used directly.", None

        if item["effect_type"] == "heal_hp":
            crow = await self.db.fetchrow(
                "SELECT current_hp, max_hp, combat_status FROM characters WHERE id=$1", char_id
            )
            if crow and crow["combat_status"] != "in_combat":
                cur, mx = int(crow["current_hp"] or 0), int(crow["max_hp"] or 0)
                if mx > 0 and cur >= mx:
                    return False, "You are already at full health.", None

        if item["quantity"] > 1:
            await self.db.execute("UPDATE inventory SET quantity=quantity-1 WHERE id=$1", item_id)
        else:
            await self.db.execute("DELETE FROM inventory WHERE id=$1", item_id)

        return True, f"Used **{item['name']}**.", {
            "type": item["effect_type"], "value": item["effect_value"], "duration": item["effect_duration"]
        }

    _SCRAP_BY_SLOT = {
        "main_hand": "weapon_scrap",
        "off_hand": "weapon_scrap",
        "head": "armor_scrap",
        "chest": "armor_scrap",
        "hands": "armor_scrap",
        "legs": "armor_scrap",
        "feet": "armor_scrap",
        "ring": "accessory_scrap",
        "neck": "accessory_scrap",
        "trinket": "accessory_scrap",
    }
    _RARITY_SCRAP_BASE = {
        "common": 2,
        "uncommon": 4,
        "rare": 7,
        "epic": 12,
        "legendary": 20,
        "artifact": 35,
    }

    @classmethod
    def scrap_yield_for_item(cls, equip_slot: Optional[str], rarity: str, level_req: int, enhancement_level: int) -> Tuple[str, int]:
        slot = (equip_slot or "").strip().lower()
        tid = cls._SCRAP_BY_SLOT.get(slot)
        if not tid:
            return "", 0
        r = (rarity or "common").lower()
        base = cls._RARITY_SCRAP_BASE.get(r, 2)
        qty = base + max(0, int(level_req or 0) // 10) + max(0, int(enhancement_level or 0))
        return tid, max(1, qty)

    async def consume_template_quantity(
        self,
        char_id: UUID,
        template_id: str,
        quantity: int,
        *,
        rarity: str = "common",
    ) -> Tuple[bool, str]:
        """Remove `quantity` from stackable rows (materials/consumables)."""
        if quantity <= 0:
            return True, "ok"
        remaining = int(quantity)
        rows = await self.db.fetch(
            """SELECT id, quantity FROM inventory
               WHERE character_id=$1 AND template_id=$2
                 AND COALESCE(rarity::text, 'common') = COALESCE($3::text, 'common')
                 AND COALESCE(is_equipped, FALSE)=FALSE
               ORDER BY obtained_at NULLS FIRST""",
            char_id,
            template_id,
            rarity,
        )
        for row in rows:
            if remaining <= 0:
                break
            q = int(row["quantity"] or 0)
            take = min(remaining, q)
            new_q = q - take
            if new_q <= 0:
                await self.db.execute("DELETE FROM inventory WHERE id=$1", row["id"])
            else:
                await self.db.execute("UPDATE inventory SET quantity=$1 WHERE id=$2", new_q, row["id"])
            remaining -= take
        if remaining > 0:
            return False, f"Not enough {template_id} (short by {remaining})."
        return True, "ok"

    async def count_template_quantity(
        self,
        char_id: UUID,
        template_id: str,
        *,
        rarity: str = "common",
    ) -> int:
        v = await self.db.fetchval(
            """SELECT COALESCE(SUM(quantity),0)::bigint FROM inventory
               WHERE character_id=$1 AND template_id=$2
                 AND COALESCE(rarity::text, 'common') = COALESCE($3::text, 'common')
                 AND COALESCE(is_equipped, FALSE)=FALSE""",
            char_id,
            template_id,
            rarity,
        )
        return int(v or 0)

    async def salvage(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str, Optional[Dict]]:
        """
        Destroy gear for scrap (+ small gold). Soulbound allowed; locked and equipped blocked.
        Returns (ok, message, payload dict with scraps + xp + gold).
        """
        try:
            item = await self.db.fetchrow(
                """SELECT i.*, t.name, t.soulbound, t.item_type, t.equip_slot, t.level_req,
                          t.rarity as template_rarity,
                          COALESCE(i.rarity, t.rarity) as rarity,
                          COALESCE(i.enhancement_level, 0) as enhancement_level
                   FROM inventory i JOIN item_templates t ON i.template_id=t.id
                   WHERE i.id=$1 AND i.character_id=$2""",
                item_id,
                char_id,
            )
            if not item:
                return False, "Item not found.", None
            if item["locked"]:
                return False, "Item is locked. Unlock it first.", None
            if item["is_equipped"]:
                return False, "Unequip the item before salvaging.", None

            itype = (item.get("item_type") or "").lower()
            if itype not in ("weapon", "armor", "accessory"):
                return False, "Only weapons, armor, and accessories can be salvaged.", None
            if not item.get("equip_slot"):
                return False, "This item cannot be salvaged.", None

            scrap_tid, scrap_qty = self.scrap_yield_for_item(
                item.get("equip_slot"),
                str(item.get("rarity") or "common"),
                int(item.get("level_req") or 0),
                int(item.get("enhancement_level") or 0),
            )
            if not scrap_tid or scrap_qty <= 0:
                return False, "Nothing to salvage from this item.", None

            name = item["name"]
            enh = int(item.get("enhancement_level") or 0)
            vendor = int(item.get("vendor_sell") or 0)
            gold = max(0, int(vendor * 0.25) + enh * 2)

            await self.db.execute("DELETE FROM inventory WHERE id=$1", item_id)

            ok, msg = await self.add_item(char_id, scrap_tid, rarity="common", quantity=scrap_qty, from_="salvage")
            if not ok:
                log.error("salvage add_item scrap failed post-delete char=%s: %s", char_id, msg)
                return False, f"Salvage failed while adding scrap: {msg}", None

            xp_gain = 4 + min(20, enh * 2)
            if (str(item.get("rarity") or "").lower()) in ("epic", "legendary", "artifact"):
                xp_gain += 3

            payload = {
                "scrap_template_id": scrap_tid,
                "scrap_quantity": scrap_qty,
                "gold": gold,
                "crafting_xp": xp_gain,
                "name": name,
            }
            return True, f"Salvaged **{name}** into scrap.", payload
        except Exception as e:
            log.error("salvage error %s: %s", item_id, e, exc_info=True)
            return False, f"Salvage error: {str(e)}", None

    # ── Sell ─────────────────────────────────────────────────────────────────

    async def sell(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str, int]:
        try:
            item = await self.db.fetchrow(
                """SELECT i.*, t.vendor_sell, t.name, t.soulbound, t.rarity as template_rarity,
                          COALESCE(i.rarity, t.rarity) as rarity,
                          COALESCE(i.enhancement_level, 0) as enhancement_level
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
            rarity_cfg = RARITIES.get(actual_rarity, RARITIES["common"])
            value_mult = rarity_cfg.value_multiplier  # Use value multiplier, not stat multiplier
            
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
            
            # Base value scaled by rarity value multiplier, plus bonus for extra stats
            # Higher rarity gets more bonus per stat point
            stat_bonus_mult = 2 if actual_rarity in ("common", "uncommon") else (3 if actual_rarity in ("rare", "epic") else 5)
            value = int(base_value * value_mult) + (bonus_stats_total * stat_bonus_mult)
            
            # Add enhancement bonus to value (enhanced items worth more)
            enhancement_level = item.get("enhancement_level", 0) or 0
            if enhancement_level > 0:
                # Enhanced items get 10% more value per enhancement level
                value = int(value * (1 + enhancement_level * 0.10))
            
            gold = value * item["quantity"]
            
            await self.db.execute("DELETE FROM inventory WHERE id=$1", item_id)
            return True, f"Sold **{item['name']}** [{actual_rarity.title()}]" + (f" +{enhancement_level}" if enhancement_level > 0 else "") + f" for **{gold}**🪙.", gold
        except Exception as e:
            log.error(f"Error selling item {item_id}: {e}", exc_info=True)
            return False, f"Error selling item: {str(e)}", 0
