"""
Timed upgrade crafting + crafting XP / levels.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

log = logging.getLogger("crafting")


def crafting_xp_to_next_level(level: int) -> int:
    """XP required to advance from `level` to `level + 1` (cap at level 99)."""
    lv = max(1, min(98, int(level)))
    return min(8000, 50 + (lv - 1) * 55)


class CraftingService:
    def __init__(self, db):
        self.db = db

    async def add_crafting_xp(self, char_id: UUID, amount: int) -> Dict[str, int]:
        """Add crafting XP and level up while thresholds are met."""
        if amount <= 0:
            row = await self.db.fetchrow(
                "SELECT crafting_level, crafting_xp FROM characters WHERE id=$1", char_id
            )
            return {
                "crafting_level": int(row["crafting_level"] or 1),
                "crafting_xp": int(row["crafting_xp"] or 0),
            }

        row = await self.db.fetchrow(
            "SELECT crafting_level, crafting_xp FROM characters WHERE id=$1",
            char_id,
        )
        if not row:
            return {"crafting_level": 1, "crafting_xp": 0}
        level = int(row["crafting_level"] or 1)
        xp = int(row["crafting_xp"] or 0) + int(amount)
        while level < 99:
            need = crafting_xp_to_next_level(level)
            if xp < need:
                break
            xp -= need
            level += 1
        await self.db.execute(
            "UPDATE characters SET crafting_level=$2, crafting_xp=$3 WHERE id=$1",
            char_id,
            level,
            xp,
        )
        return {"crafting_level": level, "crafting_xp": xp}

    async def list_recipes(self) -> List[dict]:
        rows = await self.db.fetch(
            """SELECT id, name, description, input_template_id, output_template_id,
                      craft_seconds, required_crafting_level, gold_cost, costs, crafting_xp_reward
               FROM craft_recipes ORDER BY required_crafting_level, id"""
        )
        return [dict(r) for r in rows]

    async def get_inflight_job(self, char_id: UUID) -> Optional[dict]:
        row = await self.db.fetchrow(
            """SELECT j.*, r.name AS recipe_name, r.output_template_id, r.input_template_id,
                      r.craft_seconds, r.gold_cost, r.costs, r.crafting_xp_reward
               FROM craft_jobs j
               JOIN craft_recipes r ON r.id = j.recipe_id
               WHERE j.character_id=$1 AND j.status IN ('active','ready')
               ORDER BY j.started_at DESC
               LIMIT 1""",
            char_id,
        )
        if not row:
            return None
        d = dict(row)
        now = datetime.now(timezone.utc)
        completes = d.get("completes_at")
        if d.get("status") == "active" and completes is not None:
            cdt = completes
            if getattr(cdt, "tzinfo", None) is None:
                cdt = cdt.replace(tzinfo=timezone.utc)
            if cdt <= now:
                await self.db.execute(
                    "UPDATE craft_jobs SET status='ready' WHERE id=$1 AND status='active'",
                    d["id"],
                )
                d["status"] = "ready"
        return d

    async def start_craft(
        self,
        char_id: UUID,
        recipe_id: str,
        source_inventory_id: UUID,
        inv_svc,
        char_svc,
    ) -> Tuple[bool, str, Optional[dict]]:
        inflight = await self.get_inflight_job(char_id)
        if inflight:
            if inflight.get("status") == "ready":
                return False, "Claim your finished craft before starting another.", None
            return False, "You already have a craft in progress.", None

        recipe = await self.db.fetchrow("SELECT * FROM craft_recipes WHERE id=$1", recipe_id)
        if not recipe:
            return False, "Unknown recipe.", None

        item = await self.db.fetchrow(
            """SELECT i.*, t.equip_slot, t.item_type, t.name, t.level_req
               FROM inventory i JOIN item_templates t ON t.id = i.template_id
               WHERE i.id=$1 AND i.character_id=$2""",
            source_inventory_id,
            char_id,
        )
        if not item:
            return False, "Item not found.", None
        if item["locked"]:
            return False, "Item is locked.", None
        if item["is_equipped"]:
            return False, "Unequip the item before crafting.", None
        if str(item["template_id"]) != str(recipe["input_template_id"]):
            return False, "That item does not match this recipe.", None

        char = await self.db.fetchrow(
            "SELECT gold, crafting_level FROM characters WHERE id=$1", char_id
        )
        if not char:
            return False, "Character not found.", None
        if int(char["crafting_level"] or 1) < int(recipe["required_crafting_level"] or 1):
            return False, f"Requires forging level **{recipe['required_crafting_level']}**.", None

        gold_cost = int(recipe["gold_cost"] or 0)
        if int(char["gold"] or 0) < gold_cost:
            return False, "Not enough gold.", None

        costs = recipe["costs"]
        if isinstance(costs, str):
            costs = json.loads(costs)
        if not isinstance(costs, dict):
            costs = {}

        for mat_tid, qty in costs.items():
            need = int(qty or 0)
            if need <= 0:
                continue
            have = await inv_svc.count_template_quantity(char_id, str(mat_tid), rarity="common")
            if have < need:
                return False, f"Not enough **{mat_tid}** ({have}/{need}).", None

        ok_g = await char_svc.deduct_gold(char_id, gold_cost, reason="forge_start")
        if not ok_g:
            return False, "Not enough gold.", None

        for mat_tid, qty in costs.items():
            need = int(qty or 0)
            if need <= 0:
                continue
            ok_c, msg_c = await inv_svc.consume_template_quantity(char_id, str(mat_tid), need, rarity="common")
            if not ok_c:
                await char_svc.add_gold(char_id, gold_cost, "forge_refund")
                return False, msg_c or "Could not consume materials.", None

        payload = {
            "rarity": (item.get("rarity") or "common"),
            "enhancement_level": int(item.get("enhancement_level") or 0),
            "r_str": int(item.get("r_str") or 0),
            "r_agi": int(item.get("r_agi") or 0),
            "r_int": int(item.get("r_int") or 0),
            "r_spi": int(item.get("r_spi") or 0),
            "r_sta": int(item.get("r_sta") or 0),
            "r_haste": int(item.get("r_haste") or 0),
            "r_lifesteal": int(item.get("r_lifesteal") or 0),
            "r_resistance": int(item.get("r_resistance") or 0),
            "r_hit_rating": int(item.get("r_hit_rating") or 0),
            "locked": bool(item.get("locked")),
        }

        await self.db.execute("DELETE FROM inventory WHERE id=$1", source_inventory_id)

        sec = int(recipe["craft_seconds"] or 10)
        completes = datetime.now(timezone.utc) + timedelta(seconds=sec)

        await self.db.execute(
            """INSERT INTO craft_jobs (character_id, recipe_id, payload, completes_at, status)
               VALUES ($1,$2,$3::jsonb,$4,'active')""",
            char_id,
            recipe_id,
            json.dumps(payload),
            completes,
        )
        job = await self.get_inflight_job(char_id)
        return True, "Crafting started.", job

    async def claim_craft(self, char_id: UUID, inv_svc) -> Tuple[bool, str, Optional[dict]]:
        job = await self.get_inflight_job(char_id)
        if not job:
            return False, "No craft to claim.", None
        now = datetime.now(timezone.utc)
        completes = job.get("completes_at")
        if job.get("status") == "active":
            if not completes or completes > now:
                return False, "Craft is not finished yet.", None
            await self.db.execute(
                "UPDATE craft_jobs SET status='ready' WHERE id=$1 AND status='active'",
                job["id"],
            )
            job["status"] = "ready"

        if job.get("status") != "ready":
            return False, "Nothing to claim.", None

        recipe = await self.db.fetchrow("SELECT * FROM craft_recipes WHERE id=$1", job["recipe_id"])
        if not recipe:
            await self.db.execute("UPDATE craft_jobs SET status='cancelled' WHERE id=$1", job["id"])
            return False, "Recipe missing; job cancelled.", None

        raw = job.get("payload")
        if isinstance(raw, str):
            snap = json.loads(raw)
        else:
            snap = dict(raw or {})

        bonus = {
            "r_str": int(snap.get("r_str", 0)),
            "r_agi": int(snap.get("r_agi", 0)),
            "r_int": int(snap.get("r_int", 0)),
            "r_spi": int(snap.get("r_spi", 0)),
            "r_sta": int(snap.get("r_sta", 0)),
            "r_haste": int(snap.get("r_haste", 0)),
            "r_lifesteal": int(snap.get("r_lifesteal", 0)),
            "r_resistance": int(snap.get("r_resistance", 0)),
            "r_hit_rating": int(snap.get("r_hit_rating", 0)),
        }
        rarity = str(snap.get("rarity") or "common")
        enh = int(snap.get("enhancement_level", 0))
        locked = bool(snap.get("locked"))

        out_tid = str(recipe["output_template_id"])
        ok, msg = await inv_svc.add_item(
            char_id,
            out_tid,
            rarity=rarity,
            bonus=bonus,
            from_="forge_upgrade",
            enhancement_level=enh,
            locked=locked,
        )
        if not ok:
            log.error("claim_craft add_item failed: %s", msg)
            return False, msg or "Could not add crafted item.", None

        xp_reward = int(recipe.get("crafting_xp_reward") or 0)
        xp_state = await self.add_crafting_xp(char_id, xp_reward)

        await self.db.execute(
            "UPDATE craft_jobs SET status='claimed' WHERE id=$1",
            job["id"],
        )

        new_row = await self.db.fetchrow(
            """SELECT i.id FROM inventory i
               WHERE i.character_id=$1 AND i.template_id=$2
               ORDER BY i.obtained_at DESC NULLS LAST LIMIT 1""",
            char_id,
            out_tid,
        )
        return True, "Craft complete.", {
            "item_id": str(new_row["id"]) if new_row else None,
            "template_id": out_tid,
            "crafting_xp_reward": xp_reward,
            **xp_state,
        }
