"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      services/character/presets_service.py — Saved gear and builds          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Swapping gear means unequipping and re-equipping ten slots by hand, and changing
a talent build means a respec that costs gold and wipes everything. So in
practice nobody does either: you pick one set of gear and one build and you keep
them, and the depth the game already has — two damage profiles, a defensive
option, a whole talent tree — collapses to whatever you chose first.

Presets make the swap cheap enough to actually use. Gear costs nothing (the
items are already yours). Talents still cost a respec, because the respec price
is a real balance lever and this is a convenience feature, not a way around it.

── Gear stores inventory row ids, not template ids ───────────────────────────

Two copies of the same sword are different rows with different enhancement
levels and different rolled stats. A preset that restored "a steel sword"
instead of "*this* steel sword" would quietly hand you the worse one, and the
player would have no way to tell why their damage dropped.

The cost of that choice is that a preset breaks if you sell the item — which is
the honest outcome, and `apply_gear` reports exactly which pieces went missing
rather than silently equipping a partial set.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

#: Per character, per kind. Enough for the builds people actually keep
#: (single-target / AoE / defensive) without becoming a filing system.
MAX_PRESETS = 6

MAX_NAME_LEN = 32

KIND_GEAR = "gear"
KIND_TALENTS = "talents"
KINDS = (KIND_GEAR, KIND_TALENTS)


def clean_name(raw: Any) -> str:
    name = str(raw or "").strip()
    return name[:MAX_NAME_LEN]


class PresetsService:
    def __init__(self, db):
        self.db = db

    # ── Read ──────────────────────────────────────────────────────────────────

    async def list_presets(self, char_id: UUID, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        if kind:
            rows = await self.db.fetch(
                "SELECT * FROM character_presets WHERE character_id=$1 AND kind=$2 ORDER BY name",
                char_id, kind,
            )
        else:
            rows = await self.db.fetch(
                "SELECT * FROM character_presets WHERE character_id=$1 ORDER BY kind, name", char_id
            )
        out: List[Dict[str, Any]] = []
        for r in rows:
            payload = r["payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except ValueError:
                    payload = {}
            out.append(
                {
                    "id": str(r["id"]),
                    "kind": r["kind"],
                    "name": r["name"],
                    "payload": payload or {},
                    "updated_at": r["updated_at"],
                }
            )
        return out

    # ── Capture ───────────────────────────────────────────────────────────────

    async def capture_gear(self, char_id: UUID) -> Dict[str, Any]:
        """Snapshot what is worn right now, slot -> inventory row id."""
        rows = await self.db.fetch(
            "SELECT id, equip_slot FROM inventory WHERE character_id=$1 AND is_equipped=TRUE",
            char_id,
        )
        return {str(r["equip_slot"]): str(r["id"]) for r in rows if r["equip_slot"]}

    async def capture_talents(self, char_id: UUID) -> Dict[str, Any]:
        rows = await self.db.fetch(
            "SELECT node_id, ranks FROM character_talent_allocations WHERE character_id=$1", char_id
        )
        return {str(r["node_id"]): int(r["ranks"]) for r in rows}

    async def save(self, char_id: UUID, kind: str, name: str) -> Tuple[bool, str, Optional[Dict]]:
        if kind not in KINDS:
            return False, "Unknown preset type.", None
        name = clean_name(name)
        if not name:
            return False, "Give the preset a name.", None

        payload = (
            await self.capture_gear(char_id) if kind == KIND_GEAR else await self.capture_talents(char_id)
        )
        if not payload:
            what = "equipped gear" if kind == KIND_GEAR else "allocated talents"
            return False, f"You have no {what} to save.", None

        async with self.db.transaction() as tx:
            # Counted inside the transaction so two saves racing cannot both see
            # room for one more and push a character over the limit.
            existing = await tx.fetchval(
                "SELECT COUNT(*) FROM character_presets WHERE character_id=$1 AND kind=$2",
                char_id, kind,
            )
            replacing = await tx.fetchval(
                "SELECT 1 FROM character_presets WHERE character_id=$1 AND kind=$2 AND name=$3",
                char_id, kind, name,
            )
            if not replacing and int(existing or 0) >= MAX_PRESETS:
                return False, f"You can keep {MAX_PRESETS} {kind} presets. Overwrite or delete one.", None

            row = await tx.fetchrow(
                """
                INSERT INTO character_presets (character_id, kind, name, payload)
                VALUES ($1, $2, $3, $4::jsonb)
                ON CONFLICT (character_id, kind, name)
                DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                RETURNING id, kind, name
                """,
                char_id, kind, name, json.dumps(payload),
            )

        return True, f"Saved **{name}**.", {
            "id": str(row["id"]), "kind": row["kind"], "name": row["name"], "payload": payload
        }

    async def delete(self, char_id: UUID, preset_id: UUID) -> Tuple[bool, str]:
        res = await self.db.execute(
            "DELETE FROM character_presets WHERE id=$1 AND character_id=$2", preset_id, char_id
        )
        ok = "0" not in str(res)
        return ok, "Preset deleted." if ok else "Preset not found."

    # ── Apply ─────────────────────────────────────────────────────────────────

    async def apply_gear(self, char_id: UUID, preset_id: UUID) -> Tuple[bool, str, Dict[str, Any]]:
        """Equip a saved set.

        Only touches slots the preset names. A slot the preset does not mention
        is left alone rather than emptied — a saved weapon set should not strip
        your rings.
        """
        row = await self.db.fetchrow(
            "SELECT name, payload FROM character_presets WHERE id=$1 AND character_id=$2 AND kind=$3",
            preset_id, char_id, KIND_GEAR,
        )
        if not row:
            return False, "Preset not found.", {}

        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        wanted: Dict[str, str] = {str(k): str(v) for k, v in (payload or {}).items()}
        if not wanted:
            return False, "That preset is empty.", {}

        # One query for every wanted row, so a preset of ten pieces is one round
        # trip rather than ten.
        ids: List[UUID] = []
        for raw in wanted.values():
            try:
                ids.append(UUID(raw))
            except (ValueError, AttributeError):
                continue

        owned = await self.db.fetch(
            """SELECT i.id, i.equip_slot AS worn_slot, t.equip_slot AS slot, t.name, t.level_req, t.class_req
               FROM inventory i JOIN item_templates t ON i.template_id = t.id
               WHERE i.character_id = $1 AND i.id = ANY($2::uuid[])""",
            char_id, ids,
        )
        by_id = {str(r["id"]): r for r in owned}

        char = await self.db.fetchrow("SELECT level, class FROM characters WHERE id=$1", char_id)
        level = int((char or {}).get("level") or 1)
        class_key = (char or {}).get("class")

        equipped: List[str] = []
        missing: List[str] = []
        blocked: List[str] = []

        async with self.db.transaction() as tx:
            for slot, item_id in wanted.items():
                item = by_id.get(item_id)
                if not item:
                    # Sold, salvaged or traded away since the preset was saved.
                    missing.append(slot)
                    continue
                if level < int(item["level_req"] or 1):
                    blocked.append(item["name"])
                    continue
                if item["class_req"] and item["class_req"] != class_key:
                    blocked.append(item["name"])
                    continue

                target_slot = item["slot"] or slot
                await tx.execute(
                    "UPDATE inventory SET is_equipped=FALSE, equip_slot=NULL "
                    "WHERE character_id=$1 AND equip_slot=$2 AND is_equipped=TRUE",
                    char_id, target_slot,
                )
                await tx.execute(
                    "UPDATE inventory SET is_equipped=TRUE, equip_slot=$2 WHERE id=$1",
                    UUID(item_id), target_slot,
                )
                equipped.append(item["name"])

        parts = [f"**{row['name']}** — equipped {len(equipped)} piece{'' if len(equipped) == 1 else 's'}"]
        if missing:
            parts.append(f"{len(missing)} no longer in your bag")
        if blocked:
            parts.append(f"{len(blocked)} you cannot use")
        return True, ", ".join(parts) + ".", {
            "equipped": equipped, "missing_slots": missing, "blocked": blocked
        }

    async def apply_talents(
        self, char: Dict[str, Any], preset_id: UUID, talent_svc, char_svc
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Respec and re-spend into a saved build.

        The respec is charged normally. This is a convenience feature, not a way
        around the respec price — that price is a real balance lever, and making
        presets free would quietly delete it.

        Allocation is done by looping until no further rank can be spent, rather
        than by sorting the tree: `allocate` already enforces prerequisites and
        point costs, so letting it reject an out-of-order node and retrying next
        pass means this code never has to model the tree's shape. If the tree
        changes, this keeps working.
        """
        char_id = char["id"]
        row = await self.db.fetchrow(
            "SELECT name, payload FROM character_presets WHERE id=$1 AND character_id=$2 AND kind=$3",
            preset_id, char_id, KIND_TALENTS,
        )
        if not row:
            return False, "Preset not found.", {}

        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        wanted: Dict[str, int] = {str(k): int(v) for k, v in (payload or {}).items() if int(v or 0) > 0}
        if not wanted:
            return False, "That preset is empty.", {}

        ok, msg, _state = await talent_svc.respec(char, char_svc, charge_gold=True)
        if not ok:
            # Almost always "not enough gold" — pass it through untouched so the
            # player sees the real reason rather than a generic failure.
            return False, msg, {}

        applied: Dict[str, int] = {}
        progressed = True
        # Bounded: each pass must place at least one rank or we stop, so the
        # worst case is one pass per rank in the preset.
        while progressed:
            progressed = False
            for node_id, ranks in wanted.items():
                while applied.get(node_id, 0) < ranks:
                    placed, _m, _s = await talent_svc.allocate(char, node_id, 1)
                    if not placed:
                        break
                    applied[node_id] = applied.get(node_id, 0) + 1
                    progressed = True

        total_wanted = sum(wanted.values())
        total_applied = sum(applied.values())
        short = total_wanted - total_applied
        text = f"**{row['name']}** — {total_applied} of {total_wanted} points placed."
        if short > 0:
            # Usually means the character has since lost levels (prestige) or the
            # tree changed under the preset.
            text += f" {short} could not be spent."
        return True, text, {"applied": applied, "wanted": wanted, "short": short}
