"""
Deed flags (per character) + story boss gate evaluation.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from config.lore_gates import LORE_BOSS_GATES, LoreBossGateDict

log = logging.getLogger("lore.gate")


class LoreGateService:
    def __init__(self, db):
        self.db = db

    async def get_flags(self, character_id: UUID) -> List[str]:
        rows = await self.db.fetch(
            "SELECT flag_key FROM character_deed_flags WHERE character_id=$1 ORDER BY flag_key",
            character_id,
        )
        return [r["flag_key"] for r in rows]

    async def has_flag(self, character_id: UUID, flag_key: str) -> bool:
        v = await self.db.fetchval(
            "SELECT 1 FROM character_deed_flags WHERE character_id=$1 AND flag_key=$2",
            character_id,
            flag_key,
        )
        return v is not None

    async def grant_flag(self, character_id: UUID, flag_key: str) -> None:
        await self.db.execute(
            """
            INSERT INTO character_deed_flags (character_id, flag_key)
            VALUES ($1, $2)
            ON CONFLICT (character_id, flag_key) DO NOTHING
            """,
            character_id,
            flag_key,
        )

    async def revoke_flag(self, character_id: UUID, flag_key: str) -> None:
        await self.db.execute(
            "DELETE FROM character_deed_flags WHERE character_id=$1 AND flag_key=$2",
            character_id,
            flag_key,
        )

    async def has_any_item_template(self, character_id: UUID, template_id: str) -> bool:
        v = await self.db.fetchval(
            """
            SELECT 1 FROM inventory i
            WHERE i.character_id=$1 AND i.template_id=$2 AND COALESCE(i.quantity,1) > 0
            LIMIT 1
            """,
            character_id,
            template_id,
        )
        return v is not None

    async def _meets_gate(self, character_id: UUID, cfg: LoreBossGateDict) -> bool:
        flags = set(await self.get_flags(character_id))
        req_f = cfg.get("required_flags") or []
        for f in req_f:
            if f not in flags:
                return False
        req_i = cfg.get("required_items") or []
        for tid in req_i:
            if not await self.has_any_item_template(character_id, tid):
                return False
        return True

    async def evaluate_characters(
        self,
        character_ids: List[UUID],
        enemy_key: str,
        *,
        apply_lore_gates: bool,
    ) -> Tuple[Dict[str, bool], Optional[str]]:
        """
        Returns (lore_gate_by_char, hint).

        If apply_lore_gates is False (Activity / dungeon): everyone may damage (all True).
        If enemy has no LORE_BOSS_GATES entry: everyone may damage (all True).
        Otherwise each character_id maps to True/False.
        """
        if not character_ids:
            return {}, None
        if not apply_lore_gates:
            return {str(cid): True for cid in character_ids}, None

        cfg = LORE_BOSS_GATES.get(enemy_key)
        if not cfg:
            return {str(cid): True for cid in character_ids}, None

        req_f = cfg.get("required_flags") or []
        req_i = cfg.get("required_items") or []
        if not req_f and not req_i:
            return {str(cid): True for cid in character_ids}, None

        hint = cfg.get("hint") or ""
        out: Dict[str, bool] = {}
        for cid in character_ids:
            try:
                out[str(cid)] = await self._meets_gate(cid, cfg)
            except Exception as e:
                log.warning("lore gate eval failed for %s: %s", cid, e)
                out[str(cid)] = False
        return out, hint or None

    async def grant_deed_flags_from_rewards(self, character_id: UUID, rewards: dict) -> List[str]:
        """Grant all deed_flags listed in a quest rewards dict. Returns keys granted."""
        flags = rewards.get("deed_flags") if isinstance(rewards, dict) else None
        if not flags:
            return []
        granted: List[str] = []
        for f in flags:
            fk = (f or "").strip()
            if not fk:
                continue
            await self.grant_flag(character_id, fk)
            granted.append(fk)
        return granted
