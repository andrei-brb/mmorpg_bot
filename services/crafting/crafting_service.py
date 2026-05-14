"""
Forging / timed crafts: delegates to ForgeService (Path A rarity + Path B branch).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from services.forge.forge_service import ForgeService

log = logging.getLogger("crafting")


def crafting_xp_to_next_level(level: int) -> int:
    """XP required to advance from `level` to `level + 1` (cap at level 99)."""
    lv = max(1, min(98, int(level)))
    return min(8000, 50 + (lv - 1) * 55)


class CraftingService:
    def __init__(self, db):
        self.db = db
        self._forge = ForgeService(db, self)

    async def add_crafting_xp(self, char_id: UUID, amount: int) -> Dict[str, int]:
        """Add crafting XP and level up while thresholds are met."""
        if amount <= 0:
            row = await self.db.fetchrow(
                "SELECT crafting_level, crafting_xp FROM characters WHERE id=$1", char_id
            )
            if not row:
                return {"crafting_level": 1, "crafting_xp": 0}
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
        return await self._forge.list_branch_recipes_filtered()

    async def list_rarity_rules(self) -> List[dict]:
        return await self._forge.list_rarity_rules()

    async def forge_options(self, char_id: UUID, item_id: UUID):
        return await self._forge.forge_options_for_item(char_id, item_id)

    async def start_forge(self, char_id, path, item_id, recipe_id, inv_svc, char_svc):
        return await self._forge.start_forge(char_id, path, item_id, recipe_id, inv_svc, char_svc)

    async def get_inflight_job(self, char_id: UUID) -> Optional[dict]:
        return await self._forge.get_inflight_job(char_id)

    async def start_craft(
        self,
        char_id: UUID,
        recipe_id: str,
        source_inventory_id: UUID,
        inv_svc,
        char_svc,
    ) -> Tuple[bool, str, Optional[dict]]:
        """Path B only (legacy /api/game/craft/start)."""
        return await self._forge.start_forge(
            char_id, "b", source_inventory_id, recipe_id, inv_svc, char_svc
        )

    async def claim_craft(self, char_id: UUID, inv_svc) -> Tuple[bool, str, Optional[dict]]:
        return await self._forge.claim_forge(char_id, inv_svc)
