"""
Path A (rarity forge): same inventory row, one rarity step up to rare; fail = lose costs only.
Path B (branch forge): template upgrade; input removed at start; fail = no output; success = new item.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

log = logging.getLogger("forge")

# 8A catch-up: branch outputs cannot exceed this template level_req.
FORGE_OUTPUT_MAX_LEVEL_REQ = 35

# Path A cannot push past rare (index in RARITY_ORDER).
PATH_A_MAX_RESULT_INDEX = 2  # rare

RARITY_ORDER = ("common", "uncommon", "rare", "epic", "legendary", "artifact")


def _eff_rarity(row: dict) -> str:
    return str(row.get("rarity") or row.get("trarity") or "common").lower()


def _rarity_index(r: str) -> int:
    r = (r or "common").lower()
    try:
        return RARITY_ORDER.index(r)
    except ValueError:
        return 0


def _normalize_ts(dt: Any) -> Optional[datetime]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return None


class ForgeService:
    """`crafting_service` is the owning CraftingService (for XP); avoid importing it at module load."""

    def __init__(self, db, crafting_service: Any = None):
        self.db = db
        self._craft = crafting_service

    async def add_crafting_xp(self, char_id: UUID, amount: int) -> Dict[str, int]:
        if self._craft is None:
            raise RuntimeError("ForgeService requires crafting_service for XP updates")
        return await self._craft.add_crafting_xp(char_id, amount)

    @staticmethod
    def eligibility_reason(item: dict, template: dict, path: str) -> Tuple[bool, str]:
        """path: 'a' | 'b' — template dict may match item row (joined query)."""
        if item.get("is_equipped"):
            return False, "Unequip the item first."
        if item.get("locked"):
            return False, "Item is locked."
        itype = str(template.get("item_type") or item.get("item_type") or "").lower()
        if itype not in ("weapon", "armor", "accessory"):
            return False, "Only weapons, armor, and accessories can be forged."
        if template.get("set_id") or item.get("set_id"):
            return False, "Set items cannot be forged."
        eff = _eff_rarity({**template, **item})
        if eff in ("legendary", "artifact"):
            return False, "That rarity cannot be forged here."
        if path == "a":
            idx = _rarity_index(eff)
            if idx >= PATH_A_MAX_RESULT_INDEX:
                return False, "Rarity infusion only works up to rare."
            if idx + 1 > PATH_A_MAX_RESULT_INDEX:
                return False, "Already at the maximum rarity for infusion."
        return True, "ok"

    async def list_branch_recipes_filtered(self) -> List[dict]:
        rows = await self.db.fetch(
            f"""SELECT r.id, r.name, r.description, r.input_template_id, r.output_template_id,
                       r.craft_seconds, r.required_crafting_level, r.gold_cost, r.costs, r.crafting_xp_reward,
                       COALESCE(r.success_chance, 1.0)::float AS success_chance,
                       COALESCE(r.destroy_input_on_fail, TRUE) AS destroy_input_on_fail
                FROM craft_recipes r
                JOIN item_templates out_t ON out_t.id = r.output_template_id
                WHERE COALESCE(out_t.level_req, 1) <= {FORGE_OUTPUT_MAX_LEVEL_REQ}
                  AND COALESCE(out_t.rarity::text, 'common') NOT IN ('legendary', 'artifact')
                  AND out_t.set_id IS NULL
                ORDER BY r.required_crafting_level, r.id"""
        )
        return [dict(x) for x in rows]

    async def branch_recipes_for_input_template(self, input_template_id: str) -> List[dict]:
        rows = await self.db.fetch(
            f"""SELECT r.id, r.name, r.description, r.input_template_id, r.output_template_id,
                       r.craft_seconds, r.required_crafting_level, r.gold_cost, r.costs, r.crafting_xp_reward,
                       COALESCE(r.success_chance, 1.0)::float AS success_chance,
                       COALESCE(r.destroy_input_on_fail, TRUE) AS destroy_input_on_fail
                FROM craft_recipes r
                JOIN item_templates out_t ON out_t.id = r.output_template_id
                WHERE r.input_template_id = $1
                  AND COALESCE(out_t.level_req, 1) <= {FORGE_OUTPUT_MAX_LEVEL_REQ}
                  AND COALESCE(out_t.rarity::text, 'common') NOT IN ('legendary', 'artifact')
                  AND out_t.set_id IS NULL
                ORDER BY r.required_crafting_level, r.id""",
            input_template_id,
        )
        return [dict(x) for x in rows]

    async def list_rarity_rules(self) -> List[dict]:
        rows = await self.db.fetch(
            """SELECT id, name, from_rarity::text AS from_rarity, to_rarity::text AS to_rarity,
                      applies_to, required_crafting_level, max_input_template_level,
                      gold_cost, costs, craft_seconds,
                      success_chance::float AS success_chance, crafting_xp_reward
               FROM forge_rarity_rules ORDER BY id"""
        )
        return [dict(x) for x in rows]

    def _next_rarity_for_path_a(self, eff: str) -> Optional[str]:
        idx = _rarity_index(eff)
        if idx >= PATH_A_MAX_RESULT_INDEX:
            return None
        nxt = RARITY_ORDER[idx + 1]
        if _rarity_index(nxt) > PATH_A_MAX_RESULT_INDEX:
            return None
        return nxt

    async def _pick_rarity_rule(
        self, from_r: str, to_r: str, item_type: str
    ) -> Optional[dict]:
        rows = await self.db.fetch(
            """SELECT * FROM forge_rarity_rules
               WHERE from_rarity::text = $1 AND to_rarity::text = $2
                 AND (applies_to = 'all_equipment' OR applies_to = $3)
               ORDER BY CASE WHEN applies_to <> 'all_equipment' THEN 0 ELSE 1 END
               LIMIT 1""",
            from_r,
            to_r,
            item_type,
        )
        return dict(rows[0]) if rows else None

    async def get_inflight_job(self, char_id: UUID) -> Optional[dict]:
        row = await self.db.fetchrow(
            """SELECT j.*, r.name AS recipe_name, r.output_template_id, r.input_template_id,
                      r.craft_seconds, r.gold_cost, r.costs, r.crafting_xp_reward,
                      COALESCE(r.success_chance, 1.0)::float AS recipe_success_chance,
                      fr.name AS rarity_rule_name, fr.from_rarity::text AS rarity_from,
                      fr.to_rarity::text AS rarity_to
               FROM craft_jobs j
               LEFT JOIN craft_recipes r ON j.recipe_id IS NOT NULL AND r.id = j.recipe_id
               LEFT JOIN forge_rarity_rules fr ON j.rarity_rule_id IS NOT NULL AND fr.id = j.rarity_rule_id
               WHERE j.character_id=$1 AND j.status IN ('active','ready')
               ORDER BY j.started_at DESC
               LIMIT 1""",
            char_id,
        )
        if not row:
            return None
        d = dict(row)
        jk = d.get("job_kind") or "template_branch"
        d["job_kind"] = jk
        now = datetime.now(timezone.utc)
        completes = _normalize_ts(d.get("completes_at"))
        if d.get("status") == "active" and completes is not None and completes <= now:
            await self.db.execute(
                "UPDATE craft_jobs SET status='ready' WHERE id=$1 AND status='active'",
                d["id"],
            )
            d["status"] = "ready"
        # Frozen chance for UI
        rawp = d.get("payload")
        if isinstance(rawp, str):
            try:
                pl = json.loads(rawp)
            except json.JSONDecodeError:
                pl = {}
        else:
            pl = dict(rawp or {})
        if jk == "rarity_forge":
            d["success_chance"] = float(pl.get("success_chance", 0.6))
        else:
            d["success_chance"] = float(
                pl.get("success_chance", d.get("recipe_success_chance") or 1.0)
            )
        d["destroy_input_on_fail"] = bool(pl.get("destroy_input_on_fail", jk == "template_branch"))
        return d

    async def forge_options_for_item(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str, Optional[dict]]:
        item = await self.db.fetchrow(
            """SELECT i.*, t.equip_slot, t.item_type, t.name, t.level_req, t.set_id, t.rarity AS trarity
               FROM inventory i JOIN item_templates t ON t.id = i.template_id
               WHERE i.id=$1 AND i.character_id=$2""",
            item_id,
            char_id,
        )
        if not item:
            return False, "Item not found.", None
        t = dict(item)
        ok_a, msg_a = self.eligibility_reason(t, t, "a")
        ok_b, msg_b = self.eligibility_reason(t, t, "b")
        eff = _eff_rarity(t)
        next_r = self._next_rarity_for_path_a(eff) if ok_a else None
        rule = None
        if next_r and ok_a:
            rule = await self._pick_rarity_rule(eff, next_r, str(t.get("item_type") or "").lower())
            if not rule:
                ok_a = False
                msg_a = "No infusion rule for this item."
            elif rule.get("max_input_template_level") is not None:
                if int(t.get("level_req") or 1) > int(rule["max_input_template_level"]):
                    ok_a = False
                    msg_a = "Item level is too high for this infusion."
        recipes = await self.branch_recipes_for_input_template(str(t["template_id"])) if ok_b else []
        if ok_b and not recipes:
            msg_b = "No upgrade paths for this item." if msg_b == "ok" else msg_b

        return True, "ok", {
            "item_id": str(item_id),
            "path_a": {
                "ok": bool(ok_a and rule),
                "message": msg_a if not (ok_a and rule) else None,
                "from_rarity": eff,
                "to_rarity": next_r if rule else None,
                "rule": dict(rule) if rule else None,
            },
            "path_b": {
                "ok": bool(recipes),
                "message": None if recipes else (msg_b if not ok_b else "No upgrade paths for this item."),
                "recipes": recipes,
                "risk_destroy_on_fail": True,
            },
        }

    async def start_forge(
        self,
        char_id: UUID,
        path: str,
        item_id: UUID,
        recipe_id: Optional[str],
        inv_svc,
        char_svc,
    ) -> Tuple[bool, str, Optional[dict]]:
        path = (path or "").lower().strip()
        if path not in ("a", "b"):
            return False, "Invalid path (use 'a' or 'b').", None

        inflight = await self.get_inflight_job(char_id)
        if inflight:
            if inflight.get("status") == "ready":
                return False, "Claim your finished forge job before starting another.", None
            return False, "You already have a forge job in progress.", None

        item = await self.db.fetchrow(
            """SELECT i.*, t.equip_slot, t.item_type, t.name, t.level_req, t.set_id, t.rarity AS trarity
               FROM inventory i JOIN item_templates t ON t.id = i.template_id
               WHERE i.id=$1 AND i.character_id=$2""",
            item_id,
            char_id,
        )
        if not item:
            return False, "Item not found.", None
        row = dict(item)
        ok_e, msg_e = self.eligibility_reason(row, row, path)
        if not ok_e:
            return False, msg_e, None

        char = await self.db.fetchrow(
            "SELECT gold, crafting_level FROM characters WHERE id=$1", char_id
        )
        if not char:
            return False, "Character not found.", None
        clevel = int(char["crafting_level"] or 1)

        if path == "a":
            eff = _eff_rarity(row)
            nxt = self._next_rarity_for_path_a(eff)
            if not nxt:
                return False, "Cannot infuse this rarity further.", None
            rule = await self._pick_rarity_rule(eff, nxt, str(row.get("item_type") or "").lower())
            if not rule:
                return False, "No infusion rule available.", None
            if int(rule["required_crafting_level"] or 1) > clevel:
                return False, f"Requires forging level **{rule['required_crafting_level']}**.", None
            if rule.get("max_input_template_level") is not None:
                if int(row.get("level_req") or 1) > int(rule["max_input_template_level"]):
                    return False, "Item level is too high for this infusion.", None

            gold_cost = int(rule["gold_cost"] or 0)
            if int(char["gold"] or 0) < gold_cost:
                return False, "Not enough gold.", None
            costs = rule["costs"]
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

            ok_g = await char_svc.deduct_gold(char_id, gold_cost, reason="forge_rarity_start")
            if not ok_g:
                return False, "Not enough gold.", None
            for mat_tid, qty in costs.items():
                need = int(qty or 0)
                if need <= 0:
                    continue
                ok_c, msg_c = await inv_svc.consume_template_quantity(char_id, str(mat_tid), need, rarity="common")
                if not ok_c:
                    await char_svc.add_gold(char_id, gold_cost, "forge_rarity_refund")
                    return False, msg_c or "Could not consume materials.", None

            sch = float(rule.get("success_chance") or 0.65)
            sch = max(0.0, min(1.0, sch))
            payload = {
                "inventory_id": str(item_id),
                "from_rarity": eff,
                "to_rarity": nxt,
                "success_chance": sch,
                "destroy_input_on_fail": False,
                "gold_spent": gold_cost,
            }
            await self.db.execute("UPDATE inventory SET locked=TRUE WHERE id=$1", item_id)
            sec = int(rule["craft_seconds"] or 10)
            completes = datetime.now(timezone.utc) + timedelta(seconds=sec)
            await self.db.execute(
                """INSERT INTO craft_jobs (character_id, job_kind, rarity_rule_id, payload, completes_at, status)
                   VALUES ($1,'rarity_forge',$2,$3::jsonb,$4,'active')""",
                char_id,
                rule["id"],
                json.dumps(payload),
                completes,
            )
            job = await self.get_inflight_job(char_id)
            return True, "Infusion started.", job

        # Path B
        rid = (recipe_id or "").strip()
        if not rid:
            return False, "Pick an upgrade recipe.", None
        recipe = await self.db.fetchrow(
            f"""SELECT r.* FROM craft_recipes r
                JOIN item_templates out_t ON out_t.id = r.output_template_id
                WHERE r.id = $1
                  AND COALESCE(out_t.level_req, 1) <= {FORGE_OUTPUT_MAX_LEVEL_REQ}
                  AND COALESCE(out_t.rarity::text, 'common') NOT IN ('legendary', 'artifact')
                  AND out_t.set_id IS NULL""",
            rid,
        )
        if not recipe:
            return False, "Unknown or unavailable recipe.", None
        if str(row["template_id"]) != str(recipe["input_template_id"]):
            return False, "That recipe does not match this item.", None
        if int(recipe["required_crafting_level"] or 1) > clevel:
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

        ok_g = await char_svc.deduct_gold(char_id, gold_cost, reason="forge_branch_start")
        if not ok_g:
            return False, "Not enough gold.", None
        for mat_tid, qty in costs.items():
            need = int(qty or 0)
            if need <= 0:
                continue
            ok_c, msg_c = await inv_svc.consume_template_quantity(char_id, str(mat_tid), need, rarity="common")
            if not ok_c:
                await char_svc.add_gold(char_id, gold_cost, "forge_branch_refund")
                return False, msg_c or "Could not consume materials.", None

        sch = float(recipe.get("success_chance") or 1.0)
        sch = max(0.0, min(1.0, sch))
        payload = {
            "rarity": str(row.get("rarity") or row.get("trarity") or "common"),
            "enhancement_level": 0,
            "r_str": int(row.get("r_str") or 0),
            "r_agi": int(row.get("r_agi") or 0),
            "r_int": int(row.get("r_int") or 0),
            "r_spi": int(row.get("r_spi") or 0),
            "r_sta": int(row.get("r_sta") or 0),
            "r_haste": int(row.get("r_haste") or 0),
            "r_lifesteal": int(row.get("r_lifesteal") or 0),
            "r_resistance": int(row.get("r_resistance") or 0),
            "r_hit_rating": int(row.get("r_hit_rating") or 0),
            "locked": bool(row.get("locked")),
            "success_chance": sch,
            "destroy_input_on_fail": True,
            "gold_spent": gold_cost,
        }
        await self.db.execute("DELETE FROM inventory WHERE id=$1", item_id)
        sec = int(recipe["craft_seconds"] or 10)
        completes = datetime.now(timezone.utc) + timedelta(seconds=sec)
        await self.db.execute(
            """INSERT INTO craft_jobs (character_id, job_kind, recipe_id, payload, completes_at, status)
               VALUES ($1,'template_branch',$2,$3::jsonb,$4,'active')""",
            char_id,
            rid,
            json.dumps(payload),
            completes,
        )
        job = await self.get_inflight_job(char_id)
        return True, "Upgrade started. The item is consumed — claim to see if the forge succeeded.", job

    async def _log_forge(
        self,
        char_id: UUID,
        job_kind: str,
        success: bool,
        roll: float,
        recipe_id: Optional[str],
        rarity_rule_id: Optional[str],
        gold_spent: int,
    ) -> None:
        try:
            await self.db.execute(
                """INSERT INTO forge_log (character_id, job_kind, success, rng_roll, recipe_id, rarity_rule_id, gold_spent)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                char_id,
                job_kind,
                success,
                roll,
                recipe_id,
                rarity_rule_id,
                gold_spent,
            )
        except Exception as e:
            log.warning("forge_log insert skipped: %s", e)

    async def claim_forge(self, char_id: UUID, inv_svc) -> Tuple[bool, str, Optional[dict]]:
        job = await self.get_inflight_job(char_id)
        if not job:
            return False, "Nothing to claim.", None
        now = datetime.now(timezone.utc)
        completes = _normalize_ts(job.get("completes_at"))
        if job.get("status") == "active":
            if not completes or completes > now:
                return False, "Forge is not finished yet.", None
            await self.db.execute(
                "UPDATE craft_jobs SET status='ready' WHERE id=$1 AND status='active'",
                job["id"],
            )
            job["status"] = "ready"
        if job.get("status") != "ready":
            return False, "Nothing to claim.", None

        raw = job.get("payload")
        if isinstance(raw, str):
            snap = json.loads(raw)
        else:
            snap = dict(raw or {})
        gold_spent = int(snap.get("gold_spent") or 0)
        sch = float(snap.get("success_chance") or 1.0)
        sch = max(0.0, min(1.0, sch))
        roll = random.random()
        success = roll < sch
        jk = job.get("job_kind") or "template_branch"

        if jk == "rarity_forge":
            rule = await self.db.fetchrow("SELECT * FROM forge_rarity_rules WHERE id=$1", job["rarity_rule_id"])
            if not rule:
                await self.db.execute(
                    "UPDATE craft_jobs SET status='cancelled' WHERE id=$1",
                    job["id"],
                )
                inv_id = snap.get("inventory_id")
                if inv_id:
                    await self.db.execute(
                        "UPDATE inventory SET locked=FALSE WHERE id=$1::uuid",
                        inv_id,
                    )
                return False, "Infusion rule missing; job cancelled and item unlocked.", None

            inv_uuid = UUID(str(snap["inventory_id"]))
            row = await self.db.fetchrow(
                "SELECT id, character_id, locked FROM inventory WHERE id=$1",
                inv_uuid,
            )
            if not row or str(row["character_id"]) != str(char_id):
                await self.db.execute("UPDATE craft_jobs SET status='claimed' WHERE id=$1", job["id"])
                await self._log_forge(char_id, jk, False, roll, None, str(job["rarity_rule_id"]), gold_spent)
                return False, "Item no longer available.", None

            to_r = str(snap.get("to_rarity") or rule["to_rarity"])
            if success:
                await self.db.execute(
                    """UPDATE inventory SET rarity=$2::item_rarity, locked=FALSE WHERE id=$1""",
                    inv_uuid,
                    to_r,
                )
                xp_reward = int(rule.get("crafting_xp_reward") or 0)
                xp_state = await self.add_crafting_xp(char_id, xp_reward)
                await self.db.execute("UPDATE craft_jobs SET status='claimed' WHERE id=$1", job["id"])
                await self._log_forge(char_id, jk, True, roll, None, str(job["rarity_rule_id"]), gold_spent)
                return True, f"Infusion succeeded — **{to_r}**!", {
                    "path": "a",
                    "success": True,
                    "item_id": str(inv_uuid),
                    "to_rarity": to_r,
                    "crafting_xp_reward": xp_reward,
                    **xp_state,
                }
            await self.db.execute("UPDATE inventory SET locked=FALSE WHERE id=$1", inv_uuid)
            await self.db.execute("UPDATE craft_jobs SET status='claimed' WHERE id=$1", job["id"])
            await self._log_forge(char_id, jk, False, roll, None, str(job["rarity_rule_id"]), gold_spent)
            return True, "Infusion failed. Your item is safe, but the materials and gold are gone.", {
                "path": "a",
                "success": False,
                "item_id": str(inv_uuid),
            }

        # template branch
        recipe = await self.db.fetchrow("SELECT * FROM craft_recipes WHERE id=$1", job["recipe_id"])
        if not recipe:
            await self.db.execute("UPDATE craft_jobs SET status='cancelled' WHERE id=$1", job["id"])
            await self._log_forge(char_id, jk, False, roll, str(job.get("recipe_id")), None, gold_spent)
            return False, "Recipe missing; job cancelled.", None

        if not success:
            await self.db.execute("UPDATE craft_jobs SET status='claimed' WHERE id=$1", job["id"])
            await self._log_forge(char_id, jk, False, roll, str(job["recipe_id"]), None, gold_spent)
            return True, "The forge failed. The sacrificed item and materials are lost.", {
                "path": "b",
                "success": False,
            }

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
        locked = bool(snap.get("locked"))
        out_tid = str(recipe["output_template_id"])
        ok, msg = await inv_svc.add_item(
            char_id,
            out_tid,
            rarity=rarity,
            bonus=bonus,
            from_="forge_upgrade",
            enhancement_level=0,
            locked=locked,
        )
        if not ok:
            log.error("claim_forge add_item failed: %s", msg)
            await self.db.execute("UPDATE craft_jobs SET status='claimed' WHERE id=$1", job["id"])
            await self._log_forge(char_id, jk, False, roll, str(job["recipe_id"]), None, gold_spent)
            return False, msg or "Could not add forged item.", None

        xp_reward = int(recipe.get("crafting_xp_reward") or 0)
        xp_state = await self.add_crafting_xp(char_id, xp_reward)
        await self.db.execute("UPDATE craft_jobs SET status='claimed' WHERE id=$1", job["id"])
        new_row = await self.db.fetchrow(
            """SELECT i.id FROM inventory i
               WHERE i.character_id=$1 AND i.template_id=$2
               ORDER BY i.obtained_at DESC NULLS LAST LIMIT 1""",
            char_id,
            out_tid,
        )
        await self._log_forge(char_id, jk, True, roll, str(job["recipe_id"]), None, gold_spent)
        return True, "Forge succeeded!", {
            "path": "b",
            "success": True,
            "item_id": str(new_row["id"]) if new_row else None,
            "template_id": out_tid,
            "crafting_xp_reward": xp_reward,
            **xp_state,
        }
