"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          services/character/transmog.py — Look like what you want           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Gear progression forces a choice the game never let you refuse: the best item is
the one you wear, so everyone at a given level looks identical, and the piece you
actually liked goes in the bag or the vendor. Character identity is decided
entirely by drop tables.

Transmog separates the two. Stats come from the item; the look comes from
whatever you choose. Two characters in the same best-in-slot gear can look
nothing alike.

── Rules, and why each one exists ────────────────────────────────────────────

**Same slot only.** A helm can look like another helm. Otherwise the paperdoll
stops meaning anything and a boot renders in a weapon frame.

**You must own, or have owned, the appearance.** Enforced by requiring the
source item in your bag at the moment you apply it — the appearance is a trophy,
and buying a look you never earned would make the whole thing decoration.

**It costs gold.** Appearance is the ideal sink: it is purely optional, it is
repeatable forever, and it competes with nothing a player needs. Gold spent here
is gold that leaves the economy for something nobody is disadvantaged by
skipping.

**Never touches stats.** `transmog_template_id` is read by icon and name
resolution only. No stat calculation looks at it — asserted by a test, because
the day it does is the day a cosmetic system becomes a balance exploit.
"""

from typing import Any, Dict, Optional, Tuple
from uuid import UUID

#: Flat cost to change one slot's appearance.
#:
#: Deliberately not scaled by item level or rarity. Transmog is expression, not
#: progression, and a level-60 player paying more to look how they want would be
#: taxing the exact behaviour the feature exists to encourage. Flat also means
#: the price is memorable, which matters for something you do repeatedly.
TRANSMOG_COST = 500

#: Clearing an appearance is free. Charging to undo a cosmetic choice punishes
#: experimenting, which is the entire activity.
TRANSMOG_CLEAR_COST = 0


class TransmogService:
    def __init__(self, db):
        self.db = db

    async def _row(self, char_id: UUID, item_id: UUID) -> Optional[Dict[str, Any]]:
        return await self.db.fetchrow(
            """SELECT i.id, i.is_equipped, i.transmog_template_id,
                      t.id AS template_id, t.name, t.equip_slot, t.item_type, t.icon
               FROM inventory i JOIN item_templates t ON i.template_id = t.id
               WHERE i.id = $1 AND i.character_id = $2""",
            item_id, char_id,
        )

    async def apply(
        self, char_id: UUID, item_id: UUID, source_item_id: UUID
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Make `item_id` look like `source_item_id`.

        Both must be owned, both must be the same slot, and the gold is taken in
        the same transaction as the change — so a failed write can never leave a
        player charged for an appearance they did not get.
        """
        target = await self._row(char_id, item_id)
        if not target:
            return False, "You don't have that item.", None
        source = await self._row(char_id, source_item_id)
        if not source:
            return False, "You don't have the item whose look you want.", None

        if not target["equip_slot"]:
            return False, "That item isn't worn anywhere, so it has no appearance.", None
        if target["equip_slot"] != source["equip_slot"]:
            return False, "You can only borrow the look of another item for the same slot.", None
        if str(target["template_id"]) == str(source["template_id"]):
            return False, "That item already looks like this.", None

        from services.character.character_service import CharacterService

        async with self.db.transaction() as tx:
            paid = await CharacterService(tx).deduct_gold(char_id, TRANSMOG_COST, "transmog")
            if not paid:
                return False, f"You need {TRANSMOG_COST:,} gold to change an appearance.", None
            await tx.execute(
                "UPDATE inventory SET transmog_template_id = $2 WHERE id = $1",
                item_id, source["template_id"],
            )

        return True, f"Now looks like **{source['name']}**.", {
            "item_id": str(item_id),
            "transmog_template_id": source["template_id"],
            "appearance_name": source["name"],
            "appearance_icon": source["icon"],
        }

    async def clear(self, char_id: UUID, item_id: UUID) -> Tuple[bool, str]:
        """Return an item to its own appearance. Free — see TRANSMOG_CLEAR_COST."""
        target = await self._row(char_id, item_id)
        if not target:
            return False, "You don't have that item."
        if not target["transmog_template_id"]:
            return False, "That item already looks like itself."
        await self.db.execute(
            "UPDATE inventory SET transmog_template_id = NULL WHERE id = $1", item_id
        )
        return True, "Appearance restored."

    async def wardrobe(self, char_id: UUID, slot: str) -> list:
        """Appearances available for one slot: everything you currently hold
        that could be worn there.

        Held, not "ever held" — the game keeps no acquisition history, and
        inventing one retroactively would show players a wardrobe they cannot
        explain. Keeping a piece you like is the cost of the look.
        """
        rows = await self.db.fetch(
            """SELECT DISTINCT ON (t.id) i.id AS item_id, t.id AS template_id,
                      t.name, t.icon, t.rarity
               FROM inventory i JOIN item_templates t ON i.template_id = t.id
               WHERE i.character_id = $1 AND t.equip_slot = $2
               ORDER BY t.id, i.id""",
            char_id, slot,
        )
        return [
            {
                "item_id": str(r["item_id"]),
                "template_id": r["template_id"],
                "name": r["name"],
                "icon": r["icon"],
                "rarity": r["rarity"],
            }
            for r in rows
        ]
