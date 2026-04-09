"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        services/blacksmith/blacksmith_service.py — Enhancement System       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from typing import Dict, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta

log = logging.getLogger("blacksmith")


# ═══════════════════════════════════════════════════════════════════════════════
#  ENHANCEMENT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

ENHANCEMENT_CONFIG = {
    1:  {"stat_boost": 0.10, "success_rate": 1.00, "cost": 100,     "can_break": False},  # +10% (was 5%)
    2:  {"stat_boost": 0.20, "success_rate": 0.95, "cost": 250,     "can_break": False},  # +20% (was 10%)
    3:  {"stat_boost": 0.30, "success_rate": 0.90, "cost": 500,     "can_break": False},  # +30% (was 15%)
    4:  {"stat_boost": 0.40, "success_rate": 0.75, "cost": 1000,    "can_break": True},   # +40% (was 20%)
    5:  {"stat_boost": 0.50, "success_rate": 0.65, "cost": 2500,    "can_break": True},   # +50% (was 25%)
    6:  {"stat_boost": 0.60, "success_rate": 0.55, "cost": 5000,    "can_break": True},   # +60% (was 30%)
    7:  {"stat_boost": 0.70, "success_rate": 0.45, "cost": 10000,   "can_break": True},   # +70% (was 35%)
    8:  {"stat_boost": 0.80, "success_rate": 0.35, "cost": 25000,   "can_break": True},   # +80% (was 40%)
    9:  {"stat_boost": 0.90, "success_rate": 0.25, "cost": 50000,   "can_break": True},   # +90% (was 45%)
    10: {"stat_boost": 1.00, "success_rate": 0.15, "cost": 100000,  "can_break": True},   # +100% (was 50%)
}

# Protection items
PROTECTION_ITEMS = {
    "blessing_scroll": {
        "name": "Blessing Scroll",
        "emoji": "🛡️",
        "description": "Prevents item destruction. On fail, item loses 1 enhancement level instead.",
        "cost": 10000,
        "effect": "downgrade",  # Item goes down 1 level instead of breaking
        "can_use_above": 10,    # Can use on any level
    },
    "safety_charm": {
        "name": "Safety Charm",
        "emoji": "✨",
        "description": "Guarantees success for enhancements +1 through +5.",
        "cost": 5000,
        "effect": "guarantee",  # 100% success
        "can_use_above": 5,     # Only works up to +5
    },
    "enhancement_fragment": {
        "name": "Enhancement Fragment",
        "emoji": "💎",
        "description": "Increases success chance by 10%. Can stack up to 3 times (+30%).",
        "cost": 2000,
        "effect": "boost",      # +10% success per fragment
        "max_stack": 3,
    },
}


class BlacksmithService:
    def __init__(self, db):
        self.db = db

    # ── Enhancement Attempt ───────────────────────────────────────────────────

    async def enhance_item(
        self,
        char_id: UUID,
        item_id: UUID,
        protection_type: Optional[str] = None,
        fragment_count: int = 0,
    ) -> Dict:
        """
        Attempt to enhance an item.
        
        Returns:
            {
                "success": bool,
                "broke": bool,
                "downgraded": bool,
                "new_level": int,
                "old_level": int,
                "stat_boost": float,
                "cost": int,
                "message": str,
            }
        """
        # Get item
        item = await self.db.fetchrow(
            """SELECT i.*, t.name, t.s_str, t.s_agi, t.s_int, t.s_spi, t.s_sta,
                      t.s_armor, t.s_dmg_min, t.s_dmg_max, t.item_type, t.rarity
               FROM inventory i
               JOIN item_templates t ON i.template_id = t.id
               WHERE i.id = $1 AND i.character_id = $2""",
            item_id, char_id
        )
        
        if not item:
            return {"success": False, "message": "Item not found."}

        item_type = (item.get("item_type") or "").lower()
        if item_type in ("quest", "material", "cosmetic"):
            return {"success": False, "message": "This item cannot be enhanced."}
        
        # Allow enhancing equipped items - no need to unequip first
        current_level = item.get("enhancement_level", 0)
        
        if current_level >= 10:
            return {"success": False, "message": "Item is already at maximum enhancement (+10)."}
        
        target_level = current_level + 1
        config = ENHANCEMENT_CONFIG[target_level]
        
        # Check if character has enough gold
        char = await self.db.fetchrow("SELECT gold FROM characters WHERE id = $1", char_id)
        if char["gold"] < config["cost"]:
            return {
                "success": False,
                "message": f"Not enough gold. Need {config['cost']:,}🪙, you have {char['gold']:,}🪙."
            }
        
        # Apply protection effects
        success_rate = config["success_rate"]
        protection_used = None
        to_consume: list[tuple[str, int]] = []
        
        if protection_type == "safety_charm":
            if target_level <= PROTECTION_ITEMS["safety_charm"]["can_use_above"]:
                success_rate = 1.0  # Guaranteed success
                protection_used = "safety_charm"
                to_consume.append(("protection_safety_charm", 1))
            else:
                return {"success": False, "message": "Safety Charm only works up to +5!"}
        
        elif protection_type == "blessing_scroll":
            protection_used = "blessing_scroll"
            to_consume.append(("protection_blessing_scroll", 1))
        
        # Apply enhancement fragments
        if fragment_count > 0:
            max_fragments = PROTECTION_ITEMS["enhancement_fragment"]["max_stack"]
            fragment_count = min(fragment_count, max_fragments)
            success_rate = min(1.0, success_rate + (0.10 * fragment_count))
            to_consume.append(("protection_enhancement_fragment", int(fragment_count)))

        # Verify and consume protection items/fragments (attempt cost)
        for template_id, qty in to_consume:
            have = await self.db.fetchval(
                "SELECT COALESCE(SUM(quantity),0) FROM inventory WHERE character_id=$1 AND template_id=$2",
                char_id,
                template_id,
            ) or 0
            if have < qty:
                return {"success": False, "message": f"Missing required protection item: {template_id} (need {qty})."}
        for template_id, qty in to_consume:
            # Prefer decrementing a single stack row (these items are stackable/consumable).
            row = await self.db.fetchrow(
                "SELECT id, quantity FROM inventory WHERE character_id=$1 AND template_id=$2 ORDER BY quantity DESC LIMIT 1",
                char_id,
                template_id,
            )
            if not row:
                continue
            if int(row["quantity"] or 0) > qty:
                await self.db.execute("UPDATE inventory SET quantity=quantity-$2 WHERE id=$1", row["id"], qty)
            else:
                await self.db.execute("DELETE FROM inventory WHERE id=$1", row["id"])
        
        # Deduct gold cost
        await self.db.execute(
            "UPDATE characters SET gold = gold - $2 WHERE id = $1",
            char_id, config["cost"]
        )
        
        # Roll for success
        roll = random.random()
        success = roll <= success_rate
        
        result = {
            "old_level": current_level,
            "target_level": target_level,
            "success_rate": success_rate * 100,
            "cost": config["cost"],
            "stat_boost": config["stat_boost"],
            "broke": False,
            "downgraded": False,
            "protection_used": protection_used,
        }
        
        if success:
            # SUCCESS!
            await self.db.execute(
                "UPDATE inventory SET enhancement_level = $2 WHERE id = $1",
                item_id, target_level
            )
            result["success"] = True
            result["new_level"] = target_level
            result["message"] = f"✨ SUCCESS! {item['name']} is now +{target_level}!"
            
            # Log success
            await self._log_enhancement(
                char_id, item_id, item["name"], current_level, target_level,
                True, config["cost"], protection_used
            )
            
            # Check for server announcement (legendary +10)
            if target_level == 10 and item["rarity"] in ("legendary", "artifact"):
                result["announce"] = True
        
        else:
            # FAILURE!
            result["success"] = False
            
            if config["can_break"]:
                # Item can break
                if protection_used == "blessing_scroll":
                    # Protected: downgrade instead of break
                    new_level = max(0, current_level - 1)
                    await self.db.execute(
                        "UPDATE inventory SET enhancement_level = $2 WHERE id = $1",
                        item_id, new_level
                    )
                    result["downgraded"] = True
                    result["new_level"] = new_level
                    result["message"] = (
                        f"🛡️ Blessing activated! Item protected.\n"
                        f"💔 {item['name']} +{current_level} → +{new_level}"
                    )
                else:
                    # ITEM DESTROYED
                    await self.db.execute("DELETE FROM inventory WHERE id = $1", item_id)
                    result["broke"] = True
                    result["new_level"] = 0
                    result["message"] = (
                        f"💥 ENHANCEMENT FAILED!\n"
                        f"💀 Your {item['name']} +{current_level} shattered into pieces..."
                    )
            else:
                # Safe zone - just fails, no penalty
                result["new_level"] = current_level
                result["message"] = f"❌ Enhancement failed, but item is safe (+{current_level})."
            
            # Log failure
            await self._log_enhancement(
                char_id, item_id, item["name"], current_level, target_level,
                False, config["cost"], protection_used
            )
        
        return result

    # ── Protection Items ──────────────────────────────────────────────────────

    async def get_protection_inventory(self, char_id: UUID) -> Dict[str, int]:
        """Get count of protection items owned by character."""
        # Check if character has protection items in inventory
        # For now, we'll store these as special consumables
        counts = {}
        for key in PROTECTION_ITEMS.keys():
            count = await self.db.fetchval(
                """SELECT COALESCE(SUM(quantity), 0)
                   FROM inventory i
                   JOIN item_templates t ON i.template_id = t.id
                   WHERE i.character_id = $1 AND t.id = $2""",
                char_id, f"protection_{key}"
            )
            counts[key] = count or 0
        
        return counts

    async def buy_protection(self, char_id: UUID, protection_key: str) -> Tuple[bool, str]:
        """Purchase a protection item from the blacksmith shop."""
        if protection_key not in PROTECTION_ITEMS:
            return False, "Invalid protection item."
        
        item = PROTECTION_ITEMS[protection_key]
        
        # Check gold
        char = await self.db.fetchrow("SELECT gold FROM characters WHERE id = $1", char_id)
        if char["gold"] < item["cost"]:
            return False, f"Not enough gold. Need {item['cost']:,}🪙, you have {char['gold']:,}🪙."
        
        # Deduct gold
        await self.db.execute(
            "UPDATE characters SET gold = gold - $2 WHERE id = $1",
            char_id, item["cost"]
        )
        
        # Add to inventory using InventoryService
        from services.character.inventory_service import InventoryService
        inv_svc = InventoryService(self.db)
        
        template_id = f"protection_{protection_key}"
        ok, msg = await inv_svc.add_item(char_id, template_id, rarity="rare", from_="blacksmith_shop")
        
        if ok:
            return True, f"✅ Purchased {item['emoji']} **{item['name']}** for **{item['cost']:,}**🪙!"
        else:
            # Refund gold if adding to inventory failed
            await self.db.execute(
                "UPDATE characters SET gold = gold + $2 WHERE id = $1",
                char_id, item["cost"]
            )
            return False, f"Failed to add item to inventory: {msg}"

    async def buy_protection_bulk(self, char_id: UUID, protection_key: str, quantity: int) -> Tuple[bool, str]:
        """Purchase multiple protection items in one transaction (Activity UI convenience)."""
        if protection_key not in PROTECTION_ITEMS:
            return False, "Invalid protection item."
        q = int(quantity or 0)
        if q <= 0:
            return False, "Quantity must be at least 1."
        item = PROTECTION_ITEMS[protection_key]
        total_cost = int(item["cost"]) * q

        char = await self.db.fetchrow("SELECT gold FROM characters WHERE id = $1", char_id)
        if not char or int(char["gold"] or 0) < total_cost:
            have = int(char["gold"] or 0) if char else 0
            return False, f"Not enough gold. Need {total_cost:,}🪙, you have {have:,}🪙."

        # Deduct once.
        await self.db.execute(
            "UPDATE characters SET gold = gold - $2 WHERE id = $1",
            char_id, total_cost
        )

        from services.character.inventory_service import InventoryService
        inv_svc = InventoryService(self.db)
        template_id = f"protection_{protection_key}"
        ok, msg = await inv_svc.add_item(char_id, template_id, rarity="rare", quantity=q, from_="blacksmith_shop")
        if ok:
            return True, f"✅ Purchased {item['emoji']} **{item['name']}** x{q} for **{total_cost:,}**🪙!"

        # Refund if failed to add.
        await self.db.execute(
            "UPDATE characters SET gold = gold + $2 WHERE id = $1",
            char_id, total_cost
        )
        return False, f"Failed to add item to inventory: {msg}"

    # ── Item Stats Calculation ────────────────────────────────────────────────

    def calculate_enhanced_stats(self, base_stats: Dict, enhancement_level: int) -> Dict:
        """Calculate item stats with enhancement bonus."""
        if enhancement_level == 0:
            return base_stats
        
        config = ENHANCEMENT_CONFIG.get(enhancement_level, {"stat_boost": 0})
        multiplier = 1 + config["stat_boost"]
        
        enhanced = {}
        for stat, value in base_stats.items():
            if value > 0:  # Only boost non-zero stats
                enhanced[stat] = int(value * multiplier)
            else:
                enhanced[stat] = value
        
        return enhanced

    # ── Enhancement Info ──────────────────────────────────────────────────────

    async def get_enhancement_info(self, item_id: UUID, char_id: UUID) -> Optional[Dict]:
        """Get detailed enhancement information for an item."""
        item = await self.db.fetchrow(
            """SELECT i.*, t.name, t.s_str, t.s_agi, t.s_int, t.s_spi, t.s_sta,
                      t.s_armor, t.s_dmg_min, t.s_dmg_max, t.rarity
               FROM inventory i
               JOIN item_templates t ON i.template_id = t.id
               WHERE i.id = $1 AND i.character_id = $2""",
            item_id, char_id
        )
        
        if not item:
            return None
        
        current_level = item.get("enhancement_level", 0)
        
        if current_level >= 10:
            next_config = None
        else:
            next_config = ENHANCEMENT_CONFIG[current_level + 1]
        
        # Calculate current and next stats
        base_stats = {
            "str": item["s_str"], "agi": item["s_agi"], "int": item["s_int"],
            "spi": item["s_spi"], "sta": item["s_sta"], "armor": item["s_armor"],
            "dmg_min": item["s_dmg_min"], "dmg_max": item["s_dmg_max"]
        }
        
        current_stats = self.calculate_enhanced_stats(base_stats, current_level)
        next_stats = self.calculate_enhanced_stats(base_stats, current_level + 1) if next_config else None
        
        return {
            "item": dict(item),
            "current_level": current_level,
            "current_stats": current_stats,
            "next_level": current_level + 1 if next_config else None,
            "next_stats": next_stats,
            "next_config": next_config,
        }

    # ── Leaderboard ───────────────────────────────────────────────────────────

    async def get_leaderboard(self, limit: int = 10) -> list:
        """Get top enhanced items on the server."""
        rows = await self.db.fetch(
            """SELECT c.name as char_name, t.name as item_name, t.rarity,
                      i.enhancement_level, t.icon
               FROM inventory i
               JOIN characters c ON i.character_id = c.id
               JOIN item_templates t ON i.template_id = t.id
               WHERE i.enhancement_level > 0
               ORDER BY i.enhancement_level DESC, t.rarity DESC
               LIMIT $1""",
            limit
        )
        return [dict(r) for r in rows]

    # ── Statistics ────────────────────────────────────────────────────────────

    async def get_player_stats(self, char_id: UUID) -> Dict:
        """Get enhancement statistics for a player."""
        stats = await self.db.fetchrow(
            """SELECT 
                COUNT(*) FILTER (WHERE success = TRUE) as successes,
                COUNT(*) FILTER (WHERE success = FALSE AND to_level = from_level) as failures,
                COUNT(*) FILTER (WHERE success = FALSE AND to_level < from_level) as downgrades,
                COALESCE(SUM(gold_spent), 0) as total_gold_spent,
                MAX(to_level) as highest_enhancement
               FROM enhancement_log
               WHERE character_id = $1""",
            char_id
        )
        return dict(stats) if stats else {}

    # ── Helper: Log Enhancement ───────────────────────────────────────────────

    async def _log_enhancement(
        self,
        char_id: UUID,
        item_id: UUID,
        item_name: str,
        from_level: int,
        to_level: int,
        success: bool,
        gold_spent: int,
        protection_used: Optional[str]
    ):
        """Log enhancement attempt for history/statistics."""
        await self.db.execute(
            """INSERT INTO enhancement_log
               (character_id, item_id, item_name, from_level, to_level, 
                success, gold_spent, protection_used)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            char_id, item_id, item_name, from_level, to_level,
            success, gold_spent, protection_used
        )

    # ── Helper: Daily Free Blessing ───────────────────────────────────────────

    async def claim_daily_blessing(self, char_id: UUID) -> Tuple[bool, str]:
        """Claim 1 free Blessing Scroll per day."""
        # Check last claim
        last_claim = await self.db.fetchval(
            "SELECT last_blessing_claim FROM characters WHERE id = $1",
            char_id
        )
        
        now = datetime.utcnow()
        if last_claim and (now - last_claim).total_seconds() < 86400:  # 24 hours
            time_left = 86400 - (now - last_claim).total_seconds()
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            return False, f"⏰ Next free blessing in {hours}h {minutes}m"
        
        # Grant blessing (add to inventory as special item)
        await self.db.execute(
            "UPDATE characters SET last_blessing_claim = $2 WHERE id = $1",
            char_id, now
        )
        
        return True, "🎁 Claimed daily Blessing Scroll!"
