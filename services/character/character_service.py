"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           services/character/character_service.py — Character Logic        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import math
from typing import Dict, Optional, Tuple
from uuid import UUID

import asyncpg

from config.settings import Settings, CLASSES, SPECIALIZATIONS

log = logging.getLogger("char_service")


class CharacterService:
    def __init__(self, db):
        self.db = db

    # ── Player ────────────────────────────────────────────────────────────────

    async def ensure_player(self, uid: int, username: str) -> asyncpg.Record:
        row = await self.db.fetchrow("SELECT * FROM players WHERE id=$1", uid)
        if not row:
            row = await self.db.fetchrow(
                "INSERT INTO players(id,username) VALUES($1,$2) RETURNING *", uid, username
            )
        else:
            await self.db.execute(
                "UPDATE players SET username=$2, last_seen=NOW() WHERE id=$1", uid, username
            )
        return row

    # ── Create / Get ──────────────────────────────────────────────────────────

    async def create_character(
        self, player_id: int, name: str, class_key: str
    ) -> Tuple[bool, str, Optional[asyncpg.Record]]:
        if class_key not in CLASSES:
            return False, f"Unknown class `{class_key}`.", None

        taken = await self.db.fetchrow("SELECT id FROM characters WHERE name ILIKE $1", name)
        if taken:
            return False, f"The name **{name}** is already taken.", None

        active = await self.db.fetchrow(
            "SELECT id FROM characters WHERE player_id=$1 AND is_active=TRUE", player_id
        )
        if active:
            return False, "Delete your existing character first with `/character delete`.", None

        cls = CLASSES[class_key]
        max_hp  = cls.base_hp + cls.base_stats["stamina"] * 10
        # Resource rules:
        # - Mana/Energy: start full
        # - Rage: starts at 0 with a fixed cap (generated via combat)
        max_res = 100 if cls.resource == "rage" else cls.base_resource
        start_res = 0 if cls.resource == "rage" else max_res

        char = await self.db.fetchrow(
            """
            INSERT INTO characters
                (player_id,name,class,str,agi,int_,spi,sta,
                 current_hp,max_hp,current_res,max_res,is_active)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$9,$10,$10,TRUE)
            RETURNING *
            """,
            player_id, name, class_key,
            cls.base_stats["strength"], cls.base_stats["agility"],
            cls.base_stats["intellect"], cls.base_stats["spirit"],
            cls.base_stats["stamina"],
            max_hp, start_res,
        )
        return True, f"Character **{name}** created!", char

    async def get_character(self, player_id: int) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow(
            "SELECT * FROM characters WHERE player_id=$1 AND is_active=TRUE", player_id
        )

    async def get_by_id(self, char_id: UUID) -> Optional[asyncpg.Record]:
        return await self.db.fetchrow("SELECT * FROM characters WHERE id=$1", char_id)

    # ── XP & Leveling ─────────────────────────────────────────────────────────

    @staticmethod
    def xp_for_next_level(level: int) -> int:
        """XP needed to go from `level` to `level+1`."""
        return int(Settings.XP_BASE * (Settings.XP_EXPONENT ** (level - 1)))

    @staticmethod
    def total_xp_to_reach(level: int) -> int:
        return sum(
            int(Settings.XP_BASE * (Settings.XP_EXPONENT ** (i - 1)))
            for i in range(1, level)
        )

    @staticmethod
    def level_from_total_xp(total_xp: int) -> int:
        lvl = 1
        while lvl < Settings.MAX_LEVEL:
            if total_xp < CharacterService.total_xp_to_reach(lvl + 1):
                break
            lvl += 1
        return lvl

    async def award_xp(self, char_id: UUID, amount: int, xp_mult: float = 1.0) -> Dict:
        char = await self.get_by_id(char_id)

        # Rested bonus
        rested_used = min(char["xp_rested"], amount)
        effective   = int((amount + rested_used) * xp_mult)
        new_rested  = char["xp_rested"] - rested_used

        old_level   = char["level"]
        new_total   = char["xp"] + effective
        new_level   = min(self.level_from_total_xp(new_total), Settings.MAX_LEVEL)
        gained      = new_level - old_level

        if gained > 0:
            stats = self._leveled_stats(char, new_level)
            cls = CLASSES[char["class"]]
            # On level-up:
            # - Mana/Energy: refill to new max
            # - Rage: keep current rage (capped)
            new_cur_res = (
                min(int(char["current_res"] or 0), stats["max_res"])
                if cls.resource == "rage"
                else stats["max_res"]
            )
            await self.db.execute(
                """UPDATE characters SET
                   xp=$2, xp_rested=$3, level=$4,
                   max_hp=$5, current_hp=$5,
                   max_res=$6, current_res=$7
                   WHERE id=$1""",
                char_id, new_total, new_rested, new_level,
                stats["max_hp"], stats["max_res"], new_cur_res,
            )
        else:
            await self.db.execute(
                "UPDATE characters SET xp=$2, xp_rested=$3 WHERE id=$1",
                char_id, new_total, new_rested,
            )

        return {
            "xp_gained":    effective,
            "rested_bonus": rested_used,
            "old_level":    old_level,
            "new_level":    new_level,
            "leveled_up":   gained > 0,
            "levels_gained":gained,
        }

    def _leveled_stats(self, char: asyncpg.Record, new_level: int) -> Dict:
        cls = CLASSES[char["class"]]
        bonus = (new_level - 1) * 5
        sta  = char["sta"] + bonus // 5
        int_ = char["int_"] + bonus // 5
        max_hp  = cls.base_hp + sta * 10 + new_level * 8
        if cls.resource == "rage":
            max_res = 100
        else:
            max_res = (cls.base_resource + int_ * 12 + new_level * 5) if cls.base_resource else 0
        return {"max_hp": max_hp, "max_res": max_res}

    # ── Stats (with gear) ─────────────────────────────────────────────────────

    def _apply_stat_caps(self, stat_name: str, value: float) -> float:
        """Apply soft caps with diminishing returns."""
        # Hard caps (absolute maximum)
        hard_caps = {
            "crit_chance": 75.0,
            "dodge_chance": 50.0,
            "haste": 50.0,
            "lifesteal": 30.0,
            "hit_rating": 100.0,
        }
        
        # Soft caps (diminishing returns start here)
        soft_caps = {
            "crit_chance": 40.0,
            "dodge_chance": 30.0,
            "haste": 25.0,
            "lifesteal": 15.0,
            "hit_rating": 50.0,
        }
        
        if stat_name not in hard_caps:
            return value
        
        hard_cap = hard_caps[stat_name]
        soft_cap = soft_caps.get(stat_name, hard_cap * 0.6)
        
        # Hard cap
        if value >= hard_cap:
            return hard_cap
        
        # Soft cap with diminishing returns
        if value > soft_cap:
            excess = value - soft_cap
            # Diminishing returns: 50% effectiveness after soft cap
            effective = soft_cap + excess * 0.5
            return min(effective, hard_cap)
        
        return value

    async def total_stats(self, char_id: UUID) -> Dict:
        char = await self.get_by_id(char_id)
        stats = {
            "strength":  char["str"],
            "agility":   char["agi"],
            "intellect": char["int_"],
            "spirit":    char["spi"],
            "stamina":   char["sta"],
            "armor": 0, "dmg_min": 0, "dmg_max": 0,
            "haste": 0, "lifesteal": 0, "resistance": 0, "hit_rating": 0,
        }

        equipped = await self.db.fetch(
            """
            SELECT i.*, t.s_str,t.s_agi,t.s_int,t.s_spi,t.s_sta,
                   t.s_armor,t.s_dmg_min,t.s_dmg_max,
                   t.s_haste,t.s_lifesteal,t.s_resistance,t.s_hit_rating,
                   t.set_id,
                   i.r_str,i.r_agi,i.r_int,i.r_spi,i.r_sta,
                   i.r_haste,i.r_lifesteal,i.r_resistance,i.r_hit_rating,
                   COALESCE(i.enhancement_level, 0) as enhancement_level
            FROM inventory i JOIN item_templates t ON i.template_id=t.id
            WHERE i.character_id=$1 AND i.is_equipped=TRUE
            """, char_id,
        )
        
        # Track sets for set bonuses
        set_counts: Dict[str, int] = {}
        
        # Import enhancement config
        from services.blacksmith.blacksmith_service import ENHANCEMENT_CONFIG
        
        for it in equipped:
            df = it["durability"] / 100
            enhancement_level = it.get("enhancement_level", 0) or 0
            
            # Calculate enhancement multiplier
            if enhancement_level > 0:
                enh_config = ENHANCEMENT_CONFIG.get(enhancement_level, {"stat_boost": 0})
                enh_mult = 1 + enh_config["stat_boost"]
            else:
                enh_mult = 1.0
            
            # FIX: Apply enhancement to (base + random rolls), then durability
            # Primary stats: (base + roll) * enhancement * durability
            base_str = it["s_str"] + (it.get("r_str", 0) or 0)
            base_agi = it["s_agi"] + (it.get("r_agi", 0) or 0)
            base_int = it["s_int"] + (it.get("r_int", 0) or 0)
            base_spi = it["s_spi"] + (it.get("r_spi", 0) or 0)
            base_sta = it["s_sta"] + (it.get("r_sta", 0) or 0)
            
            stats["strength"]  += int(base_str * enh_mult * df)
            stats["agility"]   += int(base_agi * enh_mult * df)
            stats["intellect"] += int(base_int * enh_mult * df)
            stats["spirit"]    += int(base_spi * enh_mult * df)
            stats["stamina"]   += int(base_sta * enh_mult * df)
            
            # Armor and damage: (base) * enhancement * durability (damage not affected by durability)
            stats["armor"]     += int((it["s_armor"] * enh_mult) * df)
            stats["dmg_min"]   += int(it["s_dmg_min"] * enh_mult)
            stats["dmg_max"]   += int(it["s_dmg_max"] * enh_mult)
            
            # Secondary stats: (base + roll) * enhancement * durability
            base_haste = (it.get("s_haste", 0) or 0) + (it.get("r_haste", 0) or 0)
            base_lifesteal = (it.get("s_lifesteal", 0) or 0) + (it.get("r_lifesteal", 0) or 0)
            base_resistance = (it.get("s_resistance", 0) or 0) + (it.get("r_resistance", 0) or 0)
            base_hit_rating = (it.get("s_hit_rating", 0) or 0) + (it.get("r_hit_rating", 0) or 0)
            
            stats["haste"]      += int(base_haste * enh_mult * df)
            stats["lifesteal"]  += int(base_lifesteal * enh_mult * df)
            stats["resistance"] += int(base_resistance * enh_mult * df)
            stats["hit_rating"] += int(base_hit_rating * enh_mult * df)
            
            # Track set pieces
            if it.get("set_id"):
                set_counts[it["set_id"]] = set_counts.get(it["set_id"], 0) + 1
        
        # Apply set bonuses
        for set_id, count in set_counts.items():
            if count >= 6:
                stats["strength"] += 15
                stats["agility"] += 15
                stats["intellect"] += 15
                stats["armor"] += 30
            elif count >= 4:
                stats["strength"] += 10
                stats["agility"] += 10
                stats["intellect"] += 10
            elif count >= 2:
                stats["armor"] += 15

        # Spec multipliers
        if char["specialization"]:
            spec = SPECIALIZATIONS.get(char["specialization"])
            if spec:
                for stat, mult in spec.stat_bonuses.items():
                    key = "intellect" if stat == "intellect" else stat
                    if key in stats:
                        stats[key] = int(stats[key] * mult)

        cls = CLASSES[char["class"]]
        primary = stats[cls.primary_stat]
        stats["attack_power"] = stats["strength"] * 2 + primary
        stats["spell_power"]  = stats["intellect"] * 2
        
        # Apply stat caps
        stats["crit_chance"]  = self._apply_stat_caps("crit_chance", 5.0 + stats["agility"] * 0.05)
        stats["dodge_chance"] = self._apply_stat_caps("dodge_chance", 3.0 + stats["agility"] * 0.03)
        stats["haste"]        = self._apply_stat_caps("haste", stats["haste"])
        stats["lifesteal"]    = self._apply_stat_caps("lifesteal", stats["lifesteal"])
        stats["hit_rating"]   = self._apply_stat_caps("hit_rating", stats["hit_rating"])
        
        stats["max_hp"]       = char["max_hp"]
        stats["max_res"]      = char["max_res"]
        return stats

    # ── Specialization ────────────────────────────────────────────────────────

    async def choose_spec(self, char_id: UUID, spec_key: str) -> Tuple[bool, str]:
        char = await self.get_by_id(char_id)
        if not char:
            return False, "Character not found."
        if char["level"] < Settings.SPEC_UNLOCK_LEVEL:
            return False, f"Specializations unlock at level **{Settings.SPEC_UNLOCK_LEVEL}**."
        if char["specialization"]:
            return False, "You have already chosen a specialization. It is permanent."
        spec = SPECIALIZATIONS.get(spec_key)
        if not spec or spec.parent_class != char["class"]:
            return False, "Invalid specialization for your class."
        await self.db.execute(
            "UPDATE characters SET specialization=$2 WHERE id=$1", char_id, spec_key
        )
        return True, f"You have become a **{spec.name}**!"

    # ── HP / Resources ────────────────────────────────────────────────────────

    async def heal(self, char_id: UUID, amount: int) -> int:
        char = await self.get_by_id(char_id)
        actual = min(amount, char["max_hp"] - char["current_hp"])
        if actual > 0:
            await self.db.execute(
                "UPDATE characters SET current_hp=current_hp+$2 WHERE id=$1", char_id, actual
            )
        return actual

    async def boost_stat(self, char_id: UUID, stat: str, amount: int, duration_minutes: int = 0) -> Tuple[bool, str]:
        """Boost a character stat temporarily or permanently.
        
        Args:
            char_id: Character UUID
            stat: One of 'str', 'agi', 'int_', 'spi', 'sta', 'max_hp'
            amount: Amount to boost
            duration_minutes: 0 = permanent, >0 = temporary (stored in cooldowns table)
        
        Returns:
            (success, message)
        """
        if stat not in ("str", "agi", "int_", "spi", "sta", "max_hp"):
            return False, f"Invalid stat: {stat}"
        
        char = await self.get_by_id(char_id)
        if not char:
            return False, "Character not found."
        
        if duration_minutes == 0:
            # Permanent boost (for stat potions that permanently increase base stats)
            if stat == "max_hp":
                new_max = char["max_hp"] + amount
                await self.db.execute(
                    "UPDATE characters SET max_hp=$2, current_hp=LEAST(current_hp+$3, $2) WHERE id=$1",
                    char_id, new_max, amount
                )
                return True, f"Max HP increased by {amount} (now {new_max})"
            else:
                await self.db.execute(
                    f"UPDATE characters SET {stat}={stat}+$2 WHERE id=$1", char_id, amount
                )
                # Recalculate max_hp if stamina changed
                if stat == "sta":
                    char = await self.get_by_id(char_id)
                    cls = CLASSES[char["class"]]
                    new_max_hp = cls.base_hp + char["sta"] * 10
                    await self.db.execute(
                        "UPDATE characters SET max_hp=$2 WHERE id=$1", char_id, new_max_hp
                    )
                return True, f"{stat.upper()} increased by {amount}"
        else:
            # Temporary boost - store in cooldowns table with expiration
            from datetime import datetime, timedelta
            expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)
            effect_key = f"potion_{stat}_{amount}"
            
            # Check if already has this effect
            existing = await self.db.fetchrow(
                "SELECT expires_at FROM cooldowns WHERE character_id=$1 AND action_key=$2",
                char_id, effect_key
            )
            if existing and existing["expires_at"] > datetime.utcnow():
                return False, f"You already have this effect active."
            
            # Store the effect
            await self.db.execute(
                """INSERT INTO cooldowns (character_id, action_key, expires_at)
                   VALUES($1, $2, $3)
                   ON CONFLICT (character_id, action_key) 
                   DO UPDATE SET expires_at=$3""",
                char_id, effect_key, expires_at
            )
            
            # Apply the boost
            if stat == "max_hp":
                new_max = char["max_hp"] + amount
                await self.db.execute(
                    "UPDATE characters SET max_hp=$2 WHERE id=$1", char_id, new_max
                )
                return True, f"Max HP increased by {amount} for {duration_minutes} minutes (now {new_max})"
            else:
                await self.db.execute(
                    f"UPDATE characters SET {stat}={stat}+$2 WHERE id=$1", char_id, amount
                )
                # Recalculate max_hp if stamina changed
                if stat == "sta":
                    char = await self.get_by_id(char_id)
                    cls = CLASSES[char["class"]]
                    new_max_hp = cls.base_hp + char["sta"] * 10
                    await self.db.execute(
                        "UPDATE characters SET max_hp=$2 WHERE id=$1", char_id, new_max_hp
                    )
                return True, f"{stat.upper()} increased by {amount} for {duration_minutes} minutes"

    async def full_restore(self, char_id: UUID):
        char = await self.get_by_id(char_id)
        if not char:
            return
        cls = CLASSES[char["class"]]
        # Rest refills HP. For resources:
        # - Mana/Energy: refill
        # - Rage: reset to 0
        await self.db.execute(
            "UPDATE characters SET current_hp=max_hp, current_res=$2 WHERE id=$1",
            char_id,
            0 if cls.resource == "rage" else char["max_res"],
        )

    async def sync_combat_hp(self, char_id: UUID, hp: int, res: int):
        """Write combat HP/res back to DB after a fight."""
        await self.db.execute(
            "UPDATE characters SET current_hp=$2, current_res=$3, combat_status='idle' WHERE id=$1",
            char_id, max(0, hp), max(0, res),
        )

    # ── Gold ─────────────────────────────────────────────────────────────────

    async def add_gold(self, char_id: UUID, amount: int, reason: str = "", source: str = "drop"):
        char = await self.get_by_id(char_id)
        new_bal = char["gold"] + amount
        await self.db.execute("UPDATE characters SET gold=$2 WHERE id=$1", char_id, new_bal)
        await self.db.execute(
            "INSERT INTO gold_log(character_id,amount,balance_after,reason) VALUES($1,$2,$3,$4)",
            char_id, amount, new_bal, reason,
        )

    async def deduct_gold(self, char_id: UUID, amount: int, reason: str = "") -> bool:
        char = await self.get_by_id(char_id)
        if char["gold"] < amount:
            return False
        new_bal = char["gold"] - amount
        await self.db.execute("UPDATE characters SET gold=$2 WHERE id=$1", char_id, new_bal)
        await self.db.execute(
            "INSERT INTO gold_log(character_id,amount,balance_after,reason) VALUES($1,$2,$3,$4)",
            char_id, -amount, new_bal, reason,
        )
        return True

    # ── Cooldowns ─────────────────────────────────────────────────────────────

    async def on_cooldown(self, char_id: UUID, action: str) -> Optional[float]:
        row = await self.db.fetchrow(
            """SELECT EXTRACT(EPOCH FROM (expires_at - NOW())) AS rem
               FROM cooldowns WHERE character_id=$1 AND action_key=$2 AND expires_at>NOW()""",
            char_id, action,
        )
        return float(row["rem"]) if row else None

    async def set_cooldown(self, char_id: UUID, action: str, seconds: int):
        await self.db.execute(
            """INSERT INTO cooldowns(character_id,action_key,expires_at)
               VALUES($1,$2, NOW()+($3||' seconds')::INTERVAL)
               ON CONFLICT(character_id,action_key)
               DO UPDATE SET expires_at=NOW()+($3||' seconds')::INTERVAL""",
            char_id, action, str(seconds),
        )

    # ── Profile ───────────────────────────────────────────────────────────────

    async def full_profile(self, player_id: int) -> Optional[Dict]:
        char = await self.get_character(player_id)
        if not char:
            return None

        stats   = await self.total_stats(char["id"])
        current = char["xp"] - self.total_xp_to_reach(char["level"])
        needed  = self.xp_for_next_level(char["level"]) if char["level"] < Settings.MAX_LEVEL else 1
        pct     = int(current / needed * 100) if needed else 100

        equipped = await self.db.fetch(
            """SELECT i.equip_slot, t.name, t.rarity, t.icon
               FROM inventory i JOIN item_templates t ON i.template_id=t.id
               WHERE i.character_id=$1 AND i.is_equipped=TRUE""",
            char["id"],
        )
        ach_count = await self.db.fetchval(
            "SELECT COUNT(*) FROM character_achievements WHERE character_id=$1", char["id"]
        )

        return {
            "char":         char,
            "stats":        stats,
            "xp_current":   current,
            "xp_needed":    needed,
            "xp_pct":       pct,
            "equipped":     {r["equip_slot"]: dict(r) for r in equipped},
            "ach_count":    ach_count,
        }
