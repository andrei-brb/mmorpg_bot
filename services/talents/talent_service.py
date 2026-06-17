"""
Spendable talent points, allocations, respec, and stat aggregation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from config.settings import CLASSES, SPECIALIZATIONS, Settings
from config.talents.loader import (
    all_nodes_for_character,
    get_class_foundation,
    get_node_def,
    get_spec_tree,
    list_class_specs,
    total_talent_points_for_level,
)

log = logging.getLogger("talents")

RESPEC_GOLD_PER_LEVEL = 50
STARTER_NODE_SUFFIX = "_starter"

_STAT_ALIASES = {
    "str": "strength",
    "strength": "strength",
    "agi": "agility",
    "agility": "agility",
    "int": "intellect",
    "intellect": "intellect",
    "spi": "spirit",
    "spirit": "spirit",
    "sta": "stamina",
    "stamina": "stamina",
    "armor": "armor",
    "resistance": "resistance",
    "crit_pct": "crit_pct",
    "haste_pct": "haste_pct",
    "lifesteal_pct": "lifesteal_pct",
}


class TalentService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def points_earned_for_level(level: int) -> int:
        return total_talent_points_for_level(level)

    async def sync_points_for_level(self, char_id: UUID, level: int, class_key: str = "") -> None:
        """Ensure unspent reflects total earned minus spent (free nodes excluded)."""
        earned = self.points_earned_for_level(level)
        spent = await self._total_spent_points(char_id, class_key or None)
        unspent = max(0, earned - spent)
        await self.db.execute(
            """
            INSERT INTO character_talent_meta (character_id, unspent_points)
            VALUES ($1, $2)
            ON CONFLICT (character_id) DO UPDATE SET
                unspent_points = $2,
                updated_at = NOW()
            """,
            char_id,
            unspent,
        )

    async def ensure_starter_granted(self, char_id: UUID, class_key: str) -> None:
        starter_id = f"{class_key}{STARTER_NODE_SUFFIX}"
        if not starter_id.endswith("_starter"):
            starter_id = f"{class_key}_starter"
        starter_id = f"{class_key}_starter"
        row = await self.db.fetchval(
            "SELECT 1 FROM character_talent_allocations WHERE character_id=$1 AND node_id=$2",
            char_id,
            starter_id,
        )
        if not row:
            await self.db.execute(
                """
                INSERT INTO character_talent_allocations (character_id, node_id, ranks)
                VALUES ($1, $2, 1)
                ON CONFLICT DO NOTHING
                """,
                char_id,
                starter_id,
            )

    async def on_spec_chosen(self, char_id: UUID, class_key: str, chosen_spec: str) -> Dict[str, Any]:
        """Lock foundation; refund ranks on non-chosen preview branches."""
        refunded = 0
        foundation = get_class_foundation(class_key)
        for node in foundation.get("nodes") or []:
            if node.get("layer") != "preview":
                continue
            nid = str(node["id"])
            sk = node.get("spec_key")
            if sk == chosen_spec:
                continue
            row = await self.db.fetchrow(
                "SELECT ranks FROM character_talent_allocations WHERE character_id=$1 AND node_id=$2",
                char_id,
                nid,
            )
            if row:
                refunded += int(row["ranks"] or 0)
                await self.db.execute(
                    "DELETE FROM character_talent_allocations WHERE character_id=$1 AND node_id=$2",
                    char_id,
                    nid,
                )
        if refunded > 0:
            await self.db.execute(
                """
                UPDATE character_talent_meta
                SET unspent_points = unspent_points + $2, foundation_locked = TRUE, updated_at = NOW()
                WHERE character_id = $1
                """,
                char_id,
                refunded,
            )
        else:
            await self.db.execute(
                """
                INSERT INTO character_talent_meta (character_id, foundation_locked)
                VALUES ($1, TRUE)
                ON CONFLICT (character_id) DO UPDATE SET foundation_locked = TRUE, updated_at = NOW()
                """,
                char_id,
            )
        return {"refunded_points": refunded, "chosen_spec": chosen_spec}

    async def get_tree_state(self, char: Dict[str, Any]) -> Dict[str, Any]:
        char_id = char["id"]
        class_key = str(char.get("class") or "warrior")
        spec_key = char.get("specialization")
        level = int(char.get("level") or 1)

        await self.ensure_starter_granted(char_id, class_key)
        await self.sync_points_for_level(char_id, level, class_key)

        meta = await self._get_meta(char_id)
        allocs = await self._get_allocations(char_id)
        alloc_map = {a["node_id"]: int(a["ranks"]) for a in allocs}

        foundation = get_class_foundation(class_key)
        spec_keys = list_class_specs(class_key)
        spec_trees = []
        for sk in spec_keys:
            tree = get_spec_tree(sk)
            spec_trees.append(self._enrich_tree(tree, alloc_map, char, active_spec=spec_key))

        foundation_enriched = self._enrich_foundation(foundation, alloc_map, char, spec_key)

        spent = sum(alloc_map.values())
        earned = self.points_earned_for_level(level)

        return {
            "ok": True,
            "class_key": class_key,
            "specialization": spec_key,
            "level": level,
            "points": {
                "earned": earned,
                "spent": spent,
                "unspent": int(meta.get("unspent_points") or 0),
            },
            "foundation_locked": bool(meta.get("foundation_locked")),
            "respec_count": int(meta.get("respec_count") or 0),
            "foundation": foundation_enriched,
            "spec_trees": spec_trees,
            "allocations": alloc_map,
            "respec_gold_cost": self._respec_gold_cost(level, meta),
        }

    def _enrich_foundation(
        self,
        foundation: Dict[str, Any],
        alloc_map: Dict[str, int],
        char: Dict[str, Any],
        spec_key: Optional[str],
    ) -> Dict[str, Any]:
        level = int(char.get("level") or 1)
        class_key = str(char.get("class") or "warrior")
        nodes_out = []
        for node in foundation.get("nodes") or []:
            nodes_out.append(
                self._node_ui_state(node, alloc_map, char, spec_key, is_foundation=True)
            )
        return {**foundation, "nodes": nodes_out}

    def _enrich_tree(
        self,
        tree: Dict[str, Any],
        alloc_map: Dict[str, int],
        char: Dict[str, Any],
        active_spec: Optional[str],
    ) -> Dict[str, Any]:
        sk = tree.get("spec_key")
        nodes_out = []
        for node in tree.get("nodes") or []:
            nodes_out.append(
                self._node_ui_state(node, alloc_map, char, active_spec, is_foundation=False, tree_spec=sk)
            )
        return {**tree, "nodes": nodes_out}

    def _node_ui_state(
        self,
        node: Dict[str, Any],
        alloc_map: Dict[str, int],
        char: Dict[str, Any],
        active_spec: Optional[str],
        is_foundation: bool,
        tree_spec: Optional[str] = None,
    ) -> Dict[str, Any]:
        nid = str(node["id"])
        ranks = int(alloc_map.get(nid, 0))
        max_ranks = int(node.get("max_ranks") or 1)
        level = int(char.get("level") or 1)
        spec_key = char.get("specialization")

        layer = node.get("layer")
        auto_grant = bool(node.get("auto_grant"))

        locked_reason = None
        can_allocate = True

        if auto_grant:
            can_allocate = False
        elif layer == "preview":
            if level < Settings.SPEC_UNLOCK_LEVEL:
                pass  # can allocate in preview before spec
            elif spec_key and node.get("spec_key") != spec_key:
                can_allocate = False
                locked_reason = "other_spec"
        elif not is_foundation:
            if level < Settings.SPEC_UNLOCK_LEVEL:
                can_allocate = False
                locked_reason = "need_spec"
            elif not spec_key:
                can_allocate = False
                locked_reason = "need_spec"
            elif tree_spec and tree_spec != spec_key:
                can_allocate = False
                locked_reason = "other_spec"

        if can_allocate and ranks < max_ranks:
            if not self._prereqs_met(node, alloc_map, char):
                can_allocate = False
                locked_reason = "prereq"

        if can_allocate and is_foundation:
            pts_req = int(node.get("points_required") or 0)
            if pts_req > 0:
                class_key = str(char.get("class") or "warrior")
                spent = self._foundation_points_spent(class_key, alloc_map)
                if spent < pts_req:
                    can_allocate = False
                    locked_reason = "points_required"

        return {
            **node,
            "ranks": ranks,
            "allocated": ranks > 0 or auto_grant,
            "max_ranks": max_ranks,
            "can_allocate": can_allocate and ranks < max_ranks,
            "locked_reason": locked_reason,
            "glow": ranks > 0 or auto_grant,
        }

    def _prereqs_met(self, node: Dict[str, Any], alloc_map: Dict[str, int], char: Dict[str, Any]) -> bool:
        class_key = str(char.get("class") or "warrior")
        for prereq in node.get("prereqs") or []:
            pid = str(prereq)
            pnode = get_node_def(pid, class_key, char.get("specialization"))
            if pnode and pnode.get("auto_grant"):
                if alloc_map.get(pid, 0) < 1 and not pid.endswith("_starter"):
                    if pid != f"{class_key}_starter":
                        return False
                continue
            if alloc_map.get(pid, 0) < 1:
                return False
        return True

    async def allocate(
        self, char: Dict[str, Any], node_id: str, delta: int = 1
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        char_id = char["id"]
        class_key = str(char.get("class") or "warrior")
        spec_key = char.get("specialization")
        level = int(char.get("level") or 1)

        await self.sync_points_for_level(char_id, level, class_key)
        node = get_node_def(node_id, class_key, spec_key)
        if not node:
            return False, "Unknown talent node.", None

        if bool(node.get("auto_grant")):
            return False, "This node is granted automatically.", None

        meta = await self._get_meta(char_id)
        allocs = await self._get_allocations(char_id)
        alloc_map = {a["node_id"]: int(a["ranks"]) for a in allocs}
        current = int(alloc_map.get(node_id, 0))
        max_ranks = int(node.get("max_ranks") or 1)
        delta = int(delta)
        if delta <= 0:
            return False, "Invalid rank change.", None

        layer = str(node.get("layer") or "")
        is_foundation_node = layer in ("starter", "preview", "core")
        ui = self._node_ui_state(node, alloc_map, char, spec_key, is_foundation=is_foundation_node)
        if is_foundation_node and not node.get("auto_grant"):
            spent = self._foundation_points_spent(class_key, alloc_map)
            if spent + delta > 5:
                return False, "Class Foundation allows at most 5 points.", None
        if not ui.get("can_allocate") and current < max_ranks:
            reason = ui.get("locked_reason") or "locked"
            if reason == "need_spec":
                return False, "Choose your specialization at level 10 first.", None
            if reason == "other_spec":
                return False, "This branch belongs to your other specialization.", None
            if reason == "prereq":
                return False, "Prerequisites not met.", None
            return False, "Cannot allocate here.", None

        if current + delta > max_ranks:
            return False, f"Max {max_ranks} rank(s) for this node.", None

        if int(meta.get("unspent_points") or 0) < delta:
            return False, "Not enough talent points.", None

        new_ranks = current + delta
        # Spend points and write the allocation atomically. The conditional decrement
        # (WHERE unspent_points >= delta) is the authoritative guard, so concurrent
        # allocations can never overspend below zero.
        async with self.db.transaction() as tx:
            spent_ok = await tx.fetchval(
                """
                UPDATE character_talent_meta
                SET unspent_points = unspent_points - $2, updated_at = NOW()
                WHERE character_id = $1 AND unspent_points >= $2
                RETURNING unspent_points
                """,
                char_id,
                delta,
            )
            if spent_ok is None:
                return False, "Not enough talent points.", None
            await tx.execute(
                """
                INSERT INTO character_talent_allocations (character_id, node_id, ranks)
                VALUES ($1, $2, $3)
                ON CONFLICT (character_id, node_id) DO UPDATE SET ranks = $3
                """,
                char_id,
                node_id,
                new_ranks,
            )
        state = await self.get_tree_state(char)
        return True, f"Rank {new_ranks}/{max_ranks}.", state

    async def respec(self, char: Dict[str, Any], char_svc) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        char_id = char["id"]
        class_key = str(char.get("class") or "warrior")
        level = int(char.get("level") or 1)
        meta = await self._get_meta(char_id)
        respec_count = int(meta.get("respec_count") or 0)

        cost = self._respec_gold_cost(level, meta) if respec_count > 0 else 0
        starter_id = f"{class_key}_starter"
        earned = self.points_earned_for_level(level)

        # Charge gold and reset allocations atomically — if anything fails the gold
        # charge rolls back, so a player can never be charged without being reset.
        from services.character.character_service import CharacterService
        async with self.db.transaction() as tx:
            if cost > 0:
                ok = await CharacterService(tx).deduct_gold(char_id, cost, reason="talent_respec")
                if not ok:
                    return False, f"Need {cost:,} gold to respec.", None
            await tx.execute(
                "DELETE FROM character_talent_allocations WHERE character_id=$1 AND node_id <> $2",
                char_id,
                starter_id,
            )
            await tx.execute(
                """
                INSERT INTO character_talent_meta (character_id, unspent_points, respec_count, foundation_locked, last_respec_at)
                VALUES ($1, $2, 1, FALSE, NOW())
                ON CONFLICT (character_id) DO UPDATE SET
                    unspent_points = $2,
                    respec_count = character_talent_meta.respec_count + 1,
                    foundation_locked = FALSE,
                    last_respec_at = NOW(),
                    updated_at = NOW()
                """,
                char_id,
                max(0, earned - 1),  # starter rank still allocated
            )
        await self.ensure_starter_granted(char_id, class_key)
        state = await self.get_tree_state(char)
        msg = "Talents reset." if respec_count == 0 else f"Talents reset ({cost:,} gold)."
        return True, msg, state

    def _respec_gold_cost(self, level: int, meta: Dict[str, Any]) -> int:
        if int(meta.get("respec_count") or 0) == 0:
            return 0
        return RESPEC_GOLD_PER_LEVEL * max(1, level)

    async def aggregate_effects(self, char_id: UUID, class_key: str, spec_key: Optional[str]) -> Dict[str, Any]:
        """Sum talent effects for combat stats and passives."""
        allocs = await self._get_allocations(char_id)
        alloc_map = {a["node_id"]: int(a["ranks"]) for a in allocs}
        out: Dict[str, Any] = {
            "stats": {},
            "spec_passive_rank": 0,
            "procs": [],
            "utility": {},
        }
        for node in all_nodes_for_character(class_key, spec_key):
            nid = str(node["id"])
            ranks = int(alloc_map.get(nid, 0))
            if ranks <= 0 and not node.get("auto_grant"):
                continue
            if node.get("auto_grant"):
                ranks = max(1, ranks)
            ntype = node.get("node_type") or "stat"
            for eff in node.get("effects") or []:
                if ntype in ("stat", "starter", "preview", "capstone"):
                    stat = eff.get("stat")
                    if stat:
                        key = _STAT_ALIASES.get(str(stat).lower(), str(stat).lower())
                        flat = float(eff.get("flat") or 0)
                        per = float(eff.get("per_rank") or 0) * ranks
                        out["stats"][key] = out["stats"].get(key, 0) + flat + per
                elif ntype == "spec_passive":
                    pk = eff.get("passive_key") or spec_key
                    if pk == spec_key:
                        out["spec_passive_rank"] = max(
                            out["spec_passive_rank"],
                            ranks,
                        )
                elif ntype == "proc":
                    out["procs"].append(
                        {
                            "proc_id": eff.get("proc_id"),
                            "chance": float(eff.get("chance_per_rank") or 0) * ranks,
                        }
                    )
                elif ntype == "utility":
                    uk = eff.get("utility")
                    if uk:
                        out["utility"][uk] = out["utility"].get(uk, 0) + float(
                            eff.get("pct_per_rank") or 0
                        ) * ranks
        return out

    async def _get_meta(self, char_id: UUID) -> Dict[str, Any]:
        row = await self.db.fetchrow(
            "SELECT * FROM character_talent_meta WHERE character_id=$1", char_id
        )
        if row:
            return dict(row)
        return {"character_id": char_id, "unspent_points": 0, "respec_count": 0, "foundation_locked": False}

    def _foundation_points_spent(self, class_key: str, alloc_map: Dict[str, int]) -> int:
        foundation = get_class_foundation(class_key)
        total = 0
        for n in foundation.get("nodes") or []:
            if n.get("auto_grant"):
                continue
            total += int(alloc_map.get(str(n["id"]), 0))
        return total

    async def _get_allocations(self, char_id: UUID) -> List[Dict[str, Any]]:
        rows = await self.db.fetch(
            "SELECT node_id, ranks FROM character_talent_allocations WHERE character_id=$1",
            char_id,
        )
        return [dict(r) for r in rows]

    async def _total_spent_points(self, char_id: UUID, class_key: Optional[str]) -> int:
        allocs = await self._get_allocations(char_id)
        if not class_key:
            return sum(int(a["ranks"]) for a in allocs)
        total = 0
        for a in allocs:
            node = get_node_def(str(a["node_id"]), class_key, None)
            if node and node.get("auto_grant"):
                continue
            total += int(a["ranks"])
        return total
