"""Rotating daily quests: assignment, progress, idempotent completion rewards.

Templates live in quest_templates (quest_type='daily') with objectives like
[{"id": "kills", "kind": "kill", "description": "...", "count": 3}].
Progress is a {objective_id: current} dict on character_quests.

Event kinds recorded today: "kill" (any fight win), "boss" (boss fight win,
recorded in addition to "kill"), "explore".
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

log = logging.getLogger("quest.daily")


def _as_list(val: Any) -> List[dict]:
    if isinstance(val, list):
        return val
    try:
        return json.loads(val or "[]")
    except (TypeError, ValueError):
        return []


def _as_dict(val: Any) -> Dict[str, Any]:
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val or "{}")
    except (TypeError, ValueError):
        return {}


class DailyQuestService:
    def __init__(self, db):
        self.db = db

    async def get_or_assign_today(self, char_id: UUID) -> Optional[dict]:
        """Return today's daily quest row (joined with its template), assigning one if needed."""
        row = await self._today_row(char_id)
        if row:
            return row

        # The (character_id, quest_id) PK blocks re-assigning a template the
        # character has had before, so clear stale daily rows first.
        await self.db.execute(
            """
            DELETE FROM character_quests cq
            USING quest_templates qt
            WHERE cq.quest_id = qt.id
              AND cq.character_id = $1
              AND qt.quest_type = 'daily'
              AND cq.started_at::date < CURRENT_DATE
            """,
            char_id,
        )
        tmpl_id = await self.db.fetchval(
            "SELECT id FROM quest_templates WHERE quest_type='daily' ORDER BY RANDOM() LIMIT 1"
        )
        if not tmpl_id:
            return None
        await self.db.execute(
            """
            INSERT INTO character_quests (character_id, quest_id, progress)
            VALUES ($1, $2, '{}'::jsonb)
            ON CONFLICT (character_id, quest_id) DO NOTHING
            """,
            char_id, tmpl_id,
        )
        return await self._today_row(char_id)

    _TODAY_SQL = """
        SELECT cq.character_id, cq.quest_id, cq.progress, cq.is_complete,
               qt.name, qt.description, qt.objectives, qt.rewards
        FROM character_quests cq
        JOIN quest_templates qt ON cq.quest_id = qt.id
        WHERE cq.character_id = $1
          AND qt.quest_type = 'daily'
          AND cq.started_at::date = CURRENT_DATE
        LIMIT 1
    """

    @staticmethod
    def _coerce(row) -> Optional[dict]:
        """asyncpg returns jsonb as str (no json codec configured) — coerce once here."""
        if not row:
            return None
        out = dict(row)
        out["objectives"] = _as_list(out.get("objectives"))
        out["progress"] = _as_dict(out.get("progress"))
        out["rewards"] = _as_dict(out.get("rewards"))
        return out

    async def _today_row(self, char_id: UUID) -> Optional[dict]:
        return self._coerce(await self.db.fetchrow(self._TODAY_SQL, char_id))

    async def record_event(self, char_svc, char_id: UUID, kind: str, n: int = 1) -> Optional[str]:
        """Bump today's daily progress for `kind`. On completion, grant rewards
        exactly once and return a display line for the caller's embed.

        Never raises: daily bookkeeping must not break combat/explore flows.
        """
        try:
            return await self._record_event_inner(char_svc, char_id, kind, n)
        except Exception:
            log.warning("daily record_event failed char=%s kind=%s", char_id, kind, exc_info=True)
            return None

    @staticmethod
    def _obj_key(obj: dict) -> str:
        # Single source of truth for the progress-dict key so increments and
        # the completion check can never disagree on templates without an "id".
        return str(obj.get("id") or obj.get("kind") or "")

    async def _record_event_inner(self, char_svc, char_id: UUID, kind: str, n: int) -> Optional[str]:
        # Fast path: skip the transaction when there's no active daily to bump.
        peek = await self._today_row(char_id)
        if not peek or peek["is_complete"]:
            return None

        # Lock the row for the read-modify-write so concurrent events from
        # Discord and the Activity can't lose increments. The conditional
        # is_complete flip below keeps the reward grant exactly-once.
        async with self.db.transaction() as tx:
            row = self._coerce(await tx.fetchrow(self._TODAY_SQL + " FOR UPDATE OF cq", char_id))
            if not row or row["is_complete"]:
                return None

            objectives = row["objectives"]
            progress = row["progress"]
            changed = False
            for obj in objectives:
                if obj.get("kind") != kind:
                    continue
                oid = self._obj_key(obj)
                need = int(obj.get("count") or 1)
                cur = int(progress.get(oid) or 0)
                if cur < need:
                    progress[oid] = min(need, cur + n)
                    changed = True
            if not changed:
                return None

            complete = all(
                int(progress.get(self._obj_key(o), 0)) >= int(o.get("count") or 1)
                for o in objectives
            )
            if not complete:
                await tx.execute(
                    """
                    UPDATE character_quests SET progress = $3::jsonb
                    WHERE character_id = $1 AND quest_id = $2 AND is_complete = FALSE
                    """,
                    char_id, row["quest_id"], json.dumps(progress),
                )
                return None

            # Idempotent completion: only the update that flips is_complete grants rewards.
            res = await tx.execute(
                """
                UPDATE character_quests
                SET progress = $3::jsonb, is_complete = TRUE, completed_at = NOW()
                WHERE character_id = $1 AND quest_id = $2 AND is_complete = FALSE
                """,
                char_id, row["quest_id"], json.dumps(progress),
            )
            if not str(res).endswith("1"):
                return None

        # Grant after the flip commits — only the caller that won the
        # conditional UPDATE reaches this point.
        rewards = row["rewards"]
        xp = int(rewards.get("xp") or 0)
        gold = int(rewards.get("gold") or 0)
        if xp > 0:
            await char_svc.award_xp(char_id, xp)
        if gold > 0:
            await char_svc.add_gold(char_id, gold, "quest_reward")
        return f"📋 **Daily complete: {row['name']}** — +{xp} XP, +{gold}🪙"
