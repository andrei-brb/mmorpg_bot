"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       services/quest/npc_quest_service.py — NPC Quest System               ║
╚══════════════════════════════════════════════════════════════════════════════╝

FLOW:
1. /explore → Public channel shows NPC hint
2. /interact <npc> → Bot DMs player with introduction
3. Player chooses quest path in DM
4. Quest progresses via kills, zone visits, item finds
5. Completion announced publicly
"""

import logging
import random
from typing import Optional, Dict, List, Tuple
from uuid import UUID

log = logging.getLogger("npc_quest")


# ═══════════════════════════════════════════════════════════════════════════════
#  NPC TEMPLATES — Each NPC has their own quest chain
# ═══════════════════════════════════════════════════════════════════════════════

NPC_TEMPLATES: Dict[str, dict] = {
    # ── Elwynn Forest & Dun Morogh (Level 1-10) ──────────────────────────────
    "old_guard_marcus": {
        "name": "Old Guard Marcus",
        "title": "🛡️ Retired Knight",
        "discovery_hint": "An old man in battered armor sits by a campfire, polishing a rusty sword.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.18,
        "introduction": {
            "text": (
                "The old soldier looks up, studying you with weary eyes.\n\n"
                "\"Another young adventurer, eh? I was like you once—full of fire.\n"
                "Name's Marcus. I used to guard the roads before these Defias scum took over.\n\n"
                "I've got a bounty on a bandit captain that's been terrorizing travelers.\n"
                "Help me put him down, and I'll share what wisdom—and coin—I have.\""
            ),
        },
        "quests": [
            {
                "id": "marcus_quest_1",
                "name": "Bandit's End",
                "description": "Hunt down the Defias Bandit plaguing the roads of Elwynn Forest.",
                "level_req": 1,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 3 Defias Bandits in Elwynn Forest",
                        "hint": "Use /fight to engage enemies. Defeat Defias Bandits.",
                        "completion_check": {"type": "kill_enemy", "value": "defias_bandit", "count": 3},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Old Guard Marcus",
                        "hint": "Use /interact marcus to report back.",
                        "completion_check": {"type": "talk_to_npc", "value": "old_guard_marcus"},
                    },
                ],
                "rewards": {
                    "xp": 500,
                    "gold": 200,
                    "items": ["iron_sword"],
                },
                "dialogue": {
                    "accept": "\"Good! Those bandits camp near the river bend. Be careful—they fight dirty.\"",
                    "decline": "\"I understand. Come back when you're ready. They'll still be out there.\"",
                    "progress_1": "\"Keep going! The roads won't be safe until they're dealt with.\"",
                    "completion": (
                        "\"You did it! The roads are safer now, thanks to you.\"\n\n"
                        "Marcus reaches into his pack and pulls out a worn but sturdy blade.\n\n"
                        "\"This served me well for twenty years. May it serve you just as long.\""
                    ),
                },
            },
            {
                "id": "marcus_quest_2",
                "name": "The Captain's Grudge",
                "description": "A stronger bandit leader has emerged. Track and eliminate the threat.",
                "level_req": 5,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat the Goldshire Corrupted Guard",
                        "hint": "A former guard turned bandit. Find and defeat them.",
                        "completion_check": {"type": "kill_enemy", "value": "goldshire_guard", "count": 1},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 5 more enemies in Elwynn Forest",
                        "hint": "Clear out the remaining threats in the area.",
                        "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 5},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Marcus with proof",
                        "hint": "Use /interact marcus to report your victory.",
                        "completion_check": {"type": "talk_to_npc", "value": "old_guard_marcus"},
                    },
                ],
                "rewards": {
                    "xp": 1500,
                    "gold": 500,
                    "items": ["leather_cap"],
                },
                "dialogue": {
                    "accept": "\"This one's dangerous—a former guard who sold us out. Watch your back.\"",
                    "decline": "\"Take your time. This isn't an enemy to face unprepared.\"",
                    "progress_1": "\"Good, you found their hideout. Keep pushing forward!\"",
                    "progress_2": "\"You're doing great! Just a bit more to clear out.\"",
                    "completion": (
                        "\"Outstanding work, soldier! You've earned more than gold today.\"\n\n"
                        "The old knight salutes you with genuine respect.\n\n"
                        "\"Take this cap—enchanted by the mages of old. May it protect you.\""
                    ),
                },
            },
        ],
    },

    "frostbeard_sage": {
        "name": "Frostbeard the Sage",
        "title": "🧙‍♂️ Dwarven Scholar",
        "discovery_hint": "A dwarf with an icy-white beard studies runes carved into a frozen boulder.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.15,
        "introduction": {
            "text": (
                "The dwarf squints at you through thick spectacles.\n\n"
                "\"Bah! Can't a scholar study in peace? ...Wait. You look capable.\n"
                "I'm researching the Trogg migration patterns. Those beasts are getting bolder.\n\n"
                "Thin their numbers for me, and I'll share some ancient dwarven secrets.\""
            ),
        },
        "quests": [
            {
                "id": "frostbeard_quest_1",
                "name": "Trogg Troubles",
                "description": "Help Frostbeard study the Trogg problem—by eliminating some.",
                "level_req": 1,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 3 Troggs in Dun Morogh",
                        "hint": "Use /fight in Dun Morogh to find Troggs.",
                        "completion_check": {"type": "kill_enemy", "value": "trogg", "count": 3},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat an Ice Claw Bear",
                        "hint": "These bears are common in Dun Morogh.",
                        "completion_check": {"type": "kill_enemy", "value": "ice_claw_bear", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Report to Frostbeard",
                        "hint": "Use /interact frostbeard to share your findings.",
                        "completion_check": {"type": "talk_to_npc", "value": "frostbeard_sage"},
                    },
                ],
                "rewards": {
                    "xp": 800,
                    "gold": 300,
                    "items": ["dwarven_axe"],
                },
                "dialogue": {
                    "accept": "\"Aye! Take this journal—note anything unusual about their behavior.\"",
                    "decline": "\"Suit yourself. The troggs won't study themselves, though.\"",
                    "progress_1": "\"Good data! Keep going—I need more samples.\"",
                    "progress_2": "\"A bear too? Excellent—their interaction with troggs is fascinating!\"",
                    "completion": (
                        "Frostbeard's eyes light up as he reviews your notes.\n\n"
                        "\"Brilliant fieldwork! This confirms my theory about the migration.\n"
                        "Here—take this Dwarven Axe. Forged by my ancestor in the Great Forge.\""
                    ),
                },
            },
        ],
    },

    # ── Barrens (Level 10-25) ────────────────────────────────────────────────
    "wandering_merchant": {
        "name": "Kira the Wandering Merchant",
        "title": "👤 Traveling Trader",
        "discovery_hint": "A hooded merchant drags a cart of exotic goods through the dusty wasteland.",
        "zones": ["barrens"],
        "discovery_chance": 0.15,
        "introduction": {
            "text": (
                "The merchant pushes back her hood and grins.\n\n"
                "\"Well met, traveler! Business has been... difficult.\n"
                "The Razormane keep raiding my supply routes. I've lost three shipments!\n\n"
                "If you can deal with those pig-men and retrieve my stolen goods,\n"
                "I'll make it very worth your while. I have connections.\""
            ),
        },
        "quests": [
            {
                "id": "kira_quest_1",
                "name": "Stolen Shipments",
                "description": "Recover Kira's stolen goods by defeating the Razormane raiders.",
                "level_req": 10,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 5 Razormane Warriors",
                        "hint": "Fight in The Barrens to find Razormane Warriors.",
                        "completion_check": {"type": "kill_enemy", "value": "razormane_warrior", "count": 5},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 3 Quillboar",
                        "hint": "Quillboar have been seen near the supply routes.",
                        "completion_check": {"type": "kill_enemy", "value": "quillboar", "count": 3},
                    },
                    {
                        "step": 3,
                        "objective": "Defeat the Razormane Chieftain",
                        "hint": "The boss guards the stolen goods. Use /fight to challenge bosses.",
                        "completion_check": {"type": "kill_enemy", "value": "razormane_chieftain", "count": 1},
                    },
                    {
                        "step": 4,
                        "objective": "Return to Kira",
                        "hint": "Use /interact kira to return the goods.",
                        "completion_check": {"type": "talk_to_npc", "value": "wandering_merchant"},
                    },
                ],
                "rewards": {
                    "xp": 3000,
                    "gold": 1500,
                    "items": ["raptor_hide_vest"],
                },
                "dialogue": {
                    "accept": "\"Wonderful! Here's a map of their raiding camps. Be ruthless.\"",
                    "decline": "\"I understand. If you change your mind, I'll be around.\"",
                    "progress_1": "\"Five down? Keep going! Their chief has my best cargo.\"",
                    "progress_2": "\"You're clearing them out! The chief must be getting nervous.\"",
                    "progress_3": "\"The chieftain is done for! Come back to me with the goods!\"",
                    "completion": (
                        "Kira counts through the recovered crates, grinning ear to ear.\n\n"
                        "\"Everything's here! You're a miracle worker.\"\n\n"
                        "She pulls a beautiful vest from the cargo.\n"
                        "\"Raptor hide—straight from Stranglethorn. It's yours.\""
                    ),
                },
            },
        ],
    },

    # ── Stranglethorn (Level 25-45) ──────────────────────────────────────────
    "captain_seafoam": {
        "name": "Captain Seafoam",
        "title": "🏴‍☠️ Retired Pirate",
        "discovery_hint": "A one-eyed pirate captain sits on a log, drawing a treasure map in the dirt.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.12,
        "introduction": {
            "text": (
                "The pirate looks you up and down with his one good eye.\n\n"
                "\"Arr! Don't just stand there—sit down!\n"
                "Captain Seafoam, formerly of the Bloodsail fleet. Retired, mostly.\n\n"
                "I've buried treasure all over this jungle, but the beasts have taken over\n"
                "my old hiding spots. Clear 'em out, and I'll split the loot with ye!\""
            ),
        },
        "quests": [
            {
                "id": "seafoam_quest_1",
                "name": "Buried Treasure",
                "description": "Help Captain Seafoam reclaim his buried treasure from the jungle.",
                "level_req": 25,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 5 enemies in Stranglethorn Vale",
                        "hint": "Clear the jungle of dangerous creatures.",
                        "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 5},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat a Stranglethorn Boss",
                        "hint": "A powerful beast guards the old treasure site.",
                        "completion_check": {"type": "kill_boss_zone", "value": "stranglethorn", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Captain Seafoam",
                        "hint": "Use /interact seafoam to claim your share.",
                        "completion_check": {"type": "talk_to_npc", "value": "captain_seafoam"},
                    },
                ],
                "rewards": {
                    "xp": 5000,
                    "gold": 3000,
                    "items": ["corsair_blade"],
                },
                "dialogue": {
                    "accept": "\"That's the spirit! Here's the map—X marks the spot, obviously.\"",
                    "decline": "\"Landlubber! The treasure will wait... for now.\"",
                    "progress_1": "\"Keep slashing through that jungle! Almost to the spot.\"",
                    "progress_2": "\"The beast is down? The treasure is practically ours!\"",
                    "completion": (
                        "Captain Seafoam digs up a chest and cracks it open.\n\n"
                        "\"Gold! Beautiful gold! And look at this blade—Corsair steel!\n"
                        "Take it, ye earned it. Finest pirate blade this side of the seas.\"\n\n"
                        "*He winks with his good eye and pockets his share.*"
                    ),
                },
            },
        ],
    },

    # ── Blackrock Depths (Level 50-60) ───────────────────────────────────────
    "eldric_wanderer": {
        "name": "Eldric the Wanderer",
        "title": "🧙‍♂️ Mysterious Sage",
        "discovery_hint": "A hooded figure sits by the roadside, studying an ancient tome.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.10,
        "introduction": {
            "text": (
                "The hooded figure looks up as you approach. His eyes gleam with ancient wisdom.\n\n"
                "\"Ah, another soul drawn to the depths. I am Eldric, keeper of forgotten lore.\n"
                "I've spent decades searching for the secrets of this volcanic fortress.\n\n"
                "The Dark Iron Dwarves guard something incredible within.\n"
                "Help me uncover it, and the power will be... substantial.\""
            ),
        },
        "quests": [
            {
                "id": "eldric_quest_1",
                "name": "Secrets of Blackrock",
                "description": "Uncover the ancient secrets hidden within Blackrock Depths.",
                "level_req": 50,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 10 enemies in Blackrock Depths",
                        "hint": "Fight through the dark iron forces.",
                        "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 10},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 2 Blackrock Bosses",
                        "hint": "The bosses guard the inner chambers.",
                        "completion_check": {"type": "kill_boss_zone", "value": "blackrock_depths", "count": 2},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Eldric with your findings",
                        "hint": "Use /interact eldric to share what you discovered.",
                        "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                    },
                ],
                "rewards": {
                    "xp": 10000,
                    "gold": 5000,
                    "items": ["sulfuron_blade"],
                },
                "dialogue": {
                    "accept": "\"Excellent! The depths are treacherous—but the reward is worth any risk.\"",
                    "decline": "\"I understand. Only the truly brave dare face what lies below.\"",
                    "progress_1": "\"The dark iron are relentless, but you're making progress!\"",
                    "progress_2": "\"Two bosses felled! The inner sanctum must be close now.\"",
                    "completion": (
                        "Eldric's eyes mist over as you describe the inner chambers.\n\n"
                        "\"Incredible... After all these years, the truth is revealed.\"\n\n"
                        "He reaches into his cloak and produces a blade wreathed in flame.\n"
                        "\"The Sulfuron Blade—forged in living fire. It's yours now.\n"
                        "May it burn as bright as your courage.\""
                    ),
                },
            },
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  NPC QUEST SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class NPCQuestService:
    def __init__(self, db):
        self.db = db

    # ── NPC Discovery ────────────────────────────────────────────────────────

    async def roll_npc_encounter(self, char_id: UUID, zone: str) -> Optional[Dict]:
        """Roll for random NPC encounter during exploration."""
        available = [
            (npc_id, npc)
            for npc_id, npc in NPC_TEMPLATES.items()
            if zone in npc["zones"]
        ]
        if not available:
            return None

        discovered = await self.db.fetch(
            "SELECT npc_id FROM npc_discoveries WHERE character_id = $1",
            char_id,
        )
        discovered_ids = {r["npc_id"] for r in discovered}

        for npc_id, npc in available:
            if random.random() < npc["discovery_chance"]:
                return {
                    "npc_id": npc_id,
                    "npc_data": npc,
                    "already_met": npc_id in discovered_ids,
                }
        return None

    async def discover_npc(self, char_id: UUID, npc_id: str, zone: str):
        """Mark an NPC as discovered."""
        await self.db.execute(
            """INSERT INTO npc_discoveries (character_id, npc_id, zone_found, state)
               VALUES ($1, $2, $3, 'discovered')
               ON CONFLICT (character_id, npc_id) DO NOTHING""",
            char_id, npc_id, zone,
        )

    async def get_npc_state(self, char_id: UUID, npc_id: str) -> Optional[str]:
        row = await self.db.fetchrow(
            "SELECT state FROM npc_discoveries WHERE character_id = $1 AND npc_id = $2",
            char_id, npc_id,
        )
        return row["state"] if row else None

    async def update_npc_state(self, char_id: UUID, npc_id: str, state: str):
        await self.db.execute(
            "UPDATE npc_discoveries SET state = $3 WHERE character_id = $1 AND npc_id = $2",
            char_id, npc_id, state,
        )

    async def get_discovered_npcs(self, char_id: UUID) -> List[Dict]:
        """Get all NPCs a character has discovered."""
        rows = await self.db.fetch(
            "SELECT npc_id, state, zone_found, discovered_at FROM npc_discoveries WHERE character_id = $1",
            char_id,
        )
        result = []
        for r in rows:
            npc = NPC_TEMPLATES.get(r["npc_id"])
            if npc:
                result.append({
                    "npc_id": r["npc_id"],
                    "name": npc["name"],
                    "title": npc["title"],
                    "state": r["state"],
                    "zone": r["zone_found"],
                })
        return result

    # ── Quest Management ─────────────────────────────────────────────────────

    async def offer_quest(self, char_id: UUID, npc_id: str, quest_id: str):
        await self.db.execute(
            """INSERT INTO quest_progress (character_id, quest_id, npc_id, current_step, state)
               VALUES ($1, $2, $3, 1, 'offered')
               ON CONFLICT (character_id, quest_id) DO NOTHING""",
            char_id, quest_id, npc_id,
        )

    async def accept_quest(self, char_id: UUID, quest_id: str):
        await self.db.execute(
            """UPDATE quest_progress SET state = 'active', started_at = NOW()
               WHERE character_id = $1 AND quest_id = $2 AND state = 'offered'""",
            char_id, quest_id,
        )

    async def get_quest_progress(self, char_id: UUID, quest_id: str) -> Optional[Dict]:
        row = await self.db.fetchrow(
            "SELECT * FROM quest_progress WHERE character_id = $1 AND quest_id = $2",
            char_id, quest_id,
        )
        return dict(row) if row else None

    async def get_active_quests(self, char_id: UUID) -> List[Dict]:
        """Get all active quests for a character, enriched with template info."""
        rows = await self.db.fetch(
            """SELECT * FROM quest_progress
               WHERE character_id = $1 AND state IN ('active', 'offered')
               ORDER BY started_at""",
            char_id,
        )
        result = []
        for r in rows:
            quest_data = self._find_quest_template(r["quest_id"])
            if quest_data:
                result.append({
                    **dict(r),
                    "quest_name": quest_data["name"],
                    "quest_desc": quest_data["description"],
                    "total_steps": len(quest_data["steps"]),
                    "steps": quest_data["steps"],
                    "rewards": quest_data["rewards"],
                })
        return result

    async def get_completed_quests(self, char_id: UUID) -> List[Dict]:
        rows = await self.db.fetch(
            """SELECT * FROM quest_progress
               WHERE character_id = $1 AND state = 'completed'
               ORDER BY completed_at DESC""",
            char_id,
        )
        result = []
        for r in rows:
            quest_data = self._find_quest_template(r["quest_id"])
            if quest_data:
                result.append({
                    **dict(r),
                    "quest_name": quest_data["name"],
                })
        return result

    async def advance_quest(self, char_id: UUID, quest_id: str) -> bool:
        """Move quest to next step. Returns True if advanced."""
        progress = await self.get_quest_progress(char_id, quest_id)
        if not progress or progress["state"] != "active":
            return False

        quest_data = self._find_quest_template(quest_id)
        if not quest_data:
            return False

        current = progress["current_step"]
        if current >= len(quest_data["steps"]):
            return False  # Already at last step

        await self.db.execute(
            "UPDATE quest_progress SET current_step = current_step + 1 WHERE character_id = $1 AND quest_id = $2",
            char_id, quest_id,
        )
        return True

    async def complete_quest(self, char_id: UUID, quest_id: str) -> Optional[Dict]:
        """
        Mark quest as completed and return rewards to grant.
        Does NOT grant rewards (the cog does that).
        """
        progress = await self.get_quest_progress(char_id, quest_id)
        if not progress or progress["state"] != "active":
            return None

        quest_data = self._find_quest_template(quest_id)
        if not quest_data:
            return None

        await self.db.execute(
            """UPDATE quest_progress SET state = 'completed', completed_at = NOW()
               WHERE character_id = $1 AND quest_id = $2""",
            char_id, quest_id,
        )
        return quest_data["rewards"]

    async def abandon_quest(self, char_id: UUID, quest_id: str) -> bool:
        """Abandon an active quest. Returns True if abandoned."""
        result = await self.db.execute(
            """DELETE FROM quest_progress
               WHERE character_id = $1 AND quest_id = $2 AND state IN ('active', 'offered')""",
            char_id, quest_id,
        )
        return "DELETE 1" in result

    # ── Quest Completion Checks (called from combat / explore hooks) ─────────

    async def check_kill_progress(
        self, char_id: UUID, enemy_key: str, zone_key: str, is_boss: bool
    ) -> List[str]:
        """
        Called after a kill. Check all active quests and advance if criteria met.
        Returns list of notification messages.
        """
        active = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id = $1 AND state = 'active'",
            char_id,
        )
        notifications = []

        for row in active:
            quest_data = self._find_quest_template(row["quest_id"])
            if not quest_data:
                continue

            step_idx = row["current_step"] - 1
            if step_idx >= len(quest_data["steps"]):
                continue

            step = quest_data["steps"][step_idx]
            check = step["completion_check"]
            advanced = False

            # Track kills in metadata
            meta = row.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}

            if check["type"] == "kill_enemy" and check["value"] == enemy_key:
                needed = check.get("count", 1)
                kill_key = f"kills_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills

                if current_kills >= needed:
                    advanced = True
                    notifications.append(
                        f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!"
                    )
                else:
                    notifications.append(
                        f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})"
                    )

            elif check["type"] == "kill_any_zone" and check["value"] == zone_key:
                needed = check.get("count", 1)
                kill_key = f"kills_zone_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills

                if current_kills >= needed:
                    advanced = True
                    notifications.append(
                        f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!"
                    )
                else:
                    notifications.append(
                        f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})"
                    )

            elif check["type"] == "kill_boss_zone" and check["value"] == zone_key and is_boss:
                needed = check.get("count", 1)
                kill_key = f"boss_kills_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills

                if current_kills >= needed:
                    advanced = True
                    notifications.append(
                        f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!"
                    )
                else:
                    notifications.append(
                        f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})"
                    )

            # Save metadata & advance if needed
            await self.db.execute(
                "UPDATE quest_progress SET metadata = $3::jsonb WHERE character_id = $1 AND quest_id = $2",
                char_id, row["quest_id"], str(meta).replace("'", '"'),
            )
            if advanced:
                await self.advance_quest(char_id, row["quest_id"])

        return notifications

    async def check_talk_to_npc(self, char_id: UUID, npc_id: str) -> Optional[Dict]:
        """
        Called when player interacts with NPC. Checks if talking completes a step.
        Returns quest data + rewards if quest is fully complete, else None.
        """
        active = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id = $1 AND state = 'active'",
            char_id,
        )

        for row in active:
            quest_data = self._find_quest_template(row["quest_id"])
            if not quest_data:
                continue

            step_idx = row["current_step"] - 1
            if step_idx >= len(quest_data["steps"]):
                continue

            step = quest_data["steps"][step_idx]
            check = step["completion_check"]

            if check["type"] == "talk_to_npc" and check["value"] == npc_id:
                # This step is complete
                next_step = row["current_step"] + 1
                if next_step > len(quest_data["steps"]):
                    # Quest is fully complete!
                    return {
                        "quest_id": row["quest_id"],
                        "quest_data": quest_data,
                        "complete": True,
                    }
                else:
                    # Advance to next step
                    await self.advance_quest(char_id, row["quest_id"])
                    return {
                        "quest_id": row["quest_id"],
                        "quest_data": quest_data,
                        "complete": False,
                        "next_step": quest_data["steps"][next_step - 1],
                    }

        return None

    def get_next_quest_for_npc(self, npc_id: str, completed_quests: List[str]) -> Optional[Dict]:
        """Get the next available quest from an NPC (supports quest chains)."""
        npc = NPC_TEMPLATES.get(npc_id)
        if not npc:
            return None

        for quest in npc["quests"]:
            if quest["id"] not in completed_quests:
                return quest
        return None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _find_quest_template(self, quest_id: str) -> Optional[Dict]:
        """Find a quest definition by ID across all NPCs."""
        for npc in NPC_TEMPLATES.values():
            for quest in npc["quests"]:
                if quest["id"] == quest_id:
                    return quest
        return None

    def find_npc_by_name(self, search: str) -> Optional[str]:
        """Find NPC ID by partial name match."""
        search_lower = search.lower().strip()
        for npc_id, npc in NPC_TEMPLATES.items():
            if search_lower in npc["name"].lower():
                return npc_id
            if search_lower in npc["title"].lower():
                return npc_id
            # Match by first word of name
            first_word = npc["name"].split()[0].lower()
            if search_lower == first_word:
                return npc_id
            # Match the NPC key
            if search_lower in npc_id:
                return npc_id
        return None
