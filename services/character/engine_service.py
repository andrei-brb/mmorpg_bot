"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           services/character/engine_service.py — Game Engine Logic            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from typing import Dict, Tuple
from uuid import UUID

from config.settings import CLASSES

log = logging.getLogger("engine")


class GameEngine:
    """AAA Standard: Game engine for stat calculation and synchronization."""
    
    @staticmethod
    def calculate_power_score(stats: Dict) -> int:
        """Calculate a simple but effective power score to rank players."""
        return int(
            (stats.get('str', 0) * 2) +
            (stats.get('agi', 0) * 2) +
            (stats.get('int', 0) * 2) +
            (stats.get('sta', 0) * 3)
        )

    async def sync_character_stats(self, char_id: UUID, db) -> Tuple[bool, Dict]:
        """
        Sync character stats to database based on level and equipped items.
        Maintains HP percentage so equipping gear doesn't "hurt" the player.
        """
        try:
            # 1. Fetch character and all EQUIPPED items
            char = await db.fetchrow(
                """SELECT level, class, current_hp, max_hp, str, agi, int_, spi, sta
                   FROM characters WHERE id=$1""",
                char_id
            )
            if not char:
                return False, {"error": "Character not found"}

            # Get equipped items with their stats (template + random rolls + enhancement)
            equipped_items = await db.fetch(
                """SELECT 
                       t.s_str, t.s_agi, t.s_int, t.s_spi, t.s_sta, t.s_armor,
                       t.s_dmg_min, t.s_dmg_max,
                       i.r_str, i.r_agi, i.r_int, i.r_spi, i.r_sta,
                       i.durability, i.enhancement_level
                   FROM inventory i
                   JOIN item_templates t ON i.template_id = t.id
                   WHERE i.character_id = $1 AND i.is_equipped = TRUE""",
                char_id
            )

            # 2. Start with Base Stats for their level
            class_key = char['class']
            cls = CLASSES.get(class_key)
            if not cls:
                log.warning(f"Unknown class: {class_key}, using warrior defaults")
                cls = CLASSES.get("warrior")

            # Base stats scale with level (1.5x per level)
            level_mult = char['level'] * 1.5
            base_stats = cls.base_stats
            
            totals = {
                "str": int(base_stats.get("strength", 0) * level_mult),
                "agi": int(base_stats.get("agility", 0) * level_mult),
                "int": int(base_stats.get("intellect", 0) * level_mult),
                "spi": int(base_stats.get("spirit", 0) * level_mult),
                "sta": int(base_stats.get("stamina", 0) * level_mult),
                "armor": 0,
                "dmg_min": 0,
                "dmg_max": 0,
            }

            # 3. Add Item Bonuses (with enhancement and durability)
            try:
                from services.blacksmith.blacksmith_service import ENHANCEMENT_CONFIG
            except ImportError:
                ENHANCEMENT_CONFIG = {}
                log.warning("ENHANCEMENT_CONFIG not found, using defaults")
            
            for item in equipped_items:
                durability_factor = item['durability'] / 100.0 if item['durability'] else 1.0
                enhancement_level = item.get('enhancement_level', 0) or 0
                
                # Calculate enhancement multiplier
                if enhancement_level > 0 and ENHANCEMENT_CONFIG:
                    enh_config = ENHANCEMENT_CONFIG.get(enhancement_level, {"stat_boost": 0})
                    enh_mult = 1 + enh_config.get("stat_boost", 0)
                else:
                    enh_mult = 1.0

                # Base stats from template + random rolls
                base_str = (item['s_str'] or 0) + (item.get('r_str', 0) or 0)
                base_agi = (item['s_agi'] or 0) + (item.get('r_agi', 0) or 0)
                base_int = (item['s_int'] or 0) + (item.get('r_int', 0) or 0)
                base_spi = (item['s_spi'] or 0) + (item.get('r_spi', 0) or 0)
                base_sta = (item['s_sta'] or 0) + (item.get('r_sta', 0) or 0)

                # Apply enhancement, then durability
                totals["str"] += int(base_str * enh_mult * durability_factor)
                totals["agi"] += int(base_agi * enh_mult * durability_factor)
                totals["int"] += int(base_int * enh_mult * durability_factor)
                totals["spi"] += int(base_spi * enh_mult * durability_factor)
                totals["sta"] += int(base_sta * enh_mult * durability_factor)
                
                # Armor and damage (damage not affected by durability)
                totals["armor"] += int((item['s_armor'] or 0) * enh_mult * durability_factor)
                totals["dmg_min"] += int((item['s_dmg_min'] or 0) * enh_mult)
                totals["dmg_max"] += int((item['s_dmg_max'] or 0) * enh_mult)

            # 4. Calculate Derived Combat Stats
            new_max_hp = cls.base_hp + totals['sta'] * 10
            
            # Attack power based on primary stat
            if class_key in ("warrior", "paladin"):
                attack_power = totals['str'] * 2
            elif class_key in ("rogue", "hunter"):
                attack_power = totals['agi'] * 2
            else:
                attack_power = totals['int'] * 2  # Mage, Priest
            
            power_score = self.calculate_power_score(totals)

            # AAA Touch: Maintain HP percentage so equipping gear doesn't "hurt" you
            old_max_hp = char['max_hp'] or 1
            hp_percent = char['current_hp'] / old_max_hp if old_max_hp > 0 else 1.0
            new_current_hp = int(new_max_hp * hp_percent)
            # Ensure HP doesn't exceed max
            if new_current_hp > new_max_hp:
                new_current_hp = new_max_hp

            # 5. SAVE TO DATABASE
            await db.execute("""
                UPDATE characters 
                SET str=$1, agi=$2, int_=$3, spi=$4, sta=$5, 
                    max_hp=$6, current_hp=$7
                WHERE id=$8
            """, totals['str'], totals['agi'], totals['int'], totals['spi'], totals['sta'],
                 new_max_hp, new_current_hp, char_id)

            # Update armor, attack_power, power_score if columns exist
            try:
                await db.execute("""
                    UPDATE characters 
                    SET armor=$1, attack_power=$2, power_score=$3
                    WHERE id=$4
                """, totals['armor'], attack_power, power_score, char_id)
            except Exception as e:
                # Columns might not exist yet, that's okay
                log.debug(f"Could not update armor/attack_power/power_score (columns may not exist): {e}")
            
            totals['max_hp'] = new_max_hp
            totals['current_hp'] = new_current_hp
            totals['attack_power'] = attack_power
            totals['power_score'] = power_score
            
            log.info(f"✅ Synced stats for character {char_id}: str={totals['str']}, agi={totals['agi']}, sta={totals['sta']}, max_hp={new_max_hp}")
            return True, totals

        except Exception as e:
            log.error(f"❌ Error syncing stats for {char_id}: {e}", exc_info=True)
            return False, {"error": str(e)}
