"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       services/quest/npc_quest_service.py — NPC Quest System               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
  • NPC Discovery during /explore
  • Multi-step quest chains with kill/zone/boss tracking
  • Timed quests (expire after X hours)
  • Dynamic dialogue (class/level-based NPC speech)
  • Reputation system (factions, levels, rewards)
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from uuid import UUID

log = logging.getLogger("npc_quest")


# ═══════════════════════════════════════════════════════════════════════════════
#  FACTION / REPUTATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

REPUTATION_LEVELS = [
    # (min_rep, name, emoji, perks_description)
    (-3000, "Hated",      "🔴", "NPCs refuse to help you"),
    (-1000, "Hostile",    "🟠", "NPCs distrust you"),
    (0,     "Neutral",    "⚪", "Default standing"),
    (500,   "Friendly",   "🟢", "5% shop discount"),
    (1500,  "Honored",    "🔵", "10% shop discount, new quests"),
    (3000,  "Revered",    "🟣", "15% shop discount, special items"),
    (6000,  "Exalted",    "🟡", "20% shop discount, unique rewards"),
]

FACTIONS = {
    "stormwind_guard": {
        "name": "Stormwind Guard",
        "emoji": "🛡️",
        "description": "The protectors of Elwynn Forest and its people.",
        "zones": ["elwynn_forest"],
    },
    "dwarven_explorers": {
        "name": "Dwarven Explorers' League",
        "emoji": "⛏️",
        "description": "Scholars and adventurers mapping the frozen north.",
        "zones": ["dun_morogh"],
    },
    "trade_coalition": {
        "name": "Merchant Trade Coalition",
        "emoji": "💰",
        "description": "A network of traders keeping commerce alive in dangerous lands.",
        "zones": ["barrens"],
    },
    "pirate_fleet": {
        "name": "Bloodsail Buccaneers",
        "emoji": "🏴‍☠️",
        "description": "Seafarers and treasure hunters of Stranglethorn.",
        "zones": ["stranglethorn"],
    },
    "arcane_order": {
        "name": "Order of the Arcane",
        "emoji": "🔮",
        "description": "Ancient scholars seeking forbidden knowledge in the depths.",
        "zones": ["blackrock_depths"],
    },
}


def get_rep_level(rep: int) -> dict:
    """Get the reputation level info for a given rep amount."""
    result = REPUTATION_LEVELS[0]
    for threshold, name, emoji, perks in REPUTATION_LEVELS:
        if rep >= threshold:
            result = (threshold, name, emoji, perks)
    return {"threshold": result[0], "name": result[1], "emoji": result[2], "perks": result[3]}


def get_rep_discount(rep: int) -> float:
    """Get shop discount multiplier based on reputation."""
    level = get_rep_level(rep)
    discounts = {"Friendly": 0.05, "Honored": 0.10, "Revered": 0.15, "Exalted": 0.20}
    return discounts.get(level["name"], 0.0)


# ═══════════════════════════════════════════════════════════════════════════════
#  DYNAMIC DIALOGUE — Class & level-specific NPC speech
# ═══════════════════════════════════════════════════════════════════════════════

# Intro overrides keyed by NPC → class
DYNAMIC_INTRODUCTIONS = {
    "old_guard_marcus": {
        "warrior": (
            "The old soldier's eyes light up as he sees your armor.\n\n"
            "\"A fellow warrior! I can see it in how you carry yourself.\n"
            "Name's Marcus. I fought in the Second War—same as your fighting instructors, I'd bet.\n\n"
            "Those Defias scum have taken over the roads. A warrior like you could handle them easily.\""
        ),
        "paladin": (
            "The old soldier drops to one knee, then catches himself.\n\n"
            "\"Forgive me—old habits. I served alongside Paladins during the war.\n"
            "Name's Marcus. The Light brought you here for a reason.\n\n"
            "The Defias are terrorizing travelers. Will the Light guide your blade against them?\""
        ),
        "mage": (
            "The old soldier eyes your robes with a mix of awe and suspicion.\n\n"
            "\"A mage, eh? Don't see many spellcasters out here on the roads.\n"
            "Name's Marcus. Could use someone with your talents.\n\n"
            "The Defias bandits are a problem steel alone can't solve. Perhaps magic can.\""
        ),
        "rogue": (
            "The old soldier notices you before you notice him. Impressive.\n\n"
            "\"I see you moving in the shadows—takes one to know one.\n"
            "Name's Marcus. I did some... reconnaissance work in my younger days.\n\n"
            "The Defias think they own these roads. Let's remind them who's really watching.\""
        ),
        "priest": (
            "The old soldier winces, clutching an old wound.\n\n"
            "\"A healer! Thank the Light. This shoulder's been bothering me for years.\n"
            "Name's Marcus. The roads aren't safe anymore.\n\n"
            "The Defias are hurting travelers. A priest's presence could help—both in healing and smiting.\""
        ),
        "hunter": (
            "The old soldier watches you and your steady stance with interest.\n\n"
            "\"A hunter! Your kind can track anything through these woods.\n"
            "Name's Marcus. I need someone who can find the Defias camps.\n\n"
            "Those bandits keep moving, but a skilled tracker could pin them down.\""
        ),
    },
    "frostbeard_sage": {
        "warrior": "The dwarf looks at your heavy armor and sighs.\n\n\"A warrior? Bah, I needed a scholar, not a brute. ...Well, you CAN smash troggs. That's useful enough. I'm Frostbeard.\"",
        "mage": "The dwarf's eyes widen with delight.\n\n\"A fellow practitioner of the arcane! Excellent! I'm Frostbeard, and I've been DYING for intelligent company.\n\nHelp me study these trogg migration patterns. Your magical insight would be invaluable!\"",
        "rogue": "The dwarf jumps, nearly dropping his spectacles.\n\n\"GAH! Don't sneak up on a scholar! ...Wait, your stealth skills could be useful.\n\nI'm Frostbeard. I need someone who can observe troggs WITHOUT being seen.\"",
    },
    "captain_seafoam": {
        "rogue": "The pirate grins widely.\n\n\"A rogue! Now THAT'S what I like to see. A kindred spirit!\n\nCaptain Seafoam, at yer service. I've got treasure to dig up, and your... particular skills... would be perfect for the job.\"",
        "warrior": "The pirate eyes your weapons appreciatively.\n\n\"A proper fighter! Arr, the jungle beasts won't know what hit 'em.\n\nCaptain Seafoam. I need muscle to clear my old treasure sites. You look like just the muscle.\"",
    },
    "eldric_wanderer": {
        "mage": "Eldric's eyes gleam with recognition.\n\n\"A mage! I sense the arcane flowing through you. We are kindred seekers of knowledge.\n\nThe secrets below require both magical skill and raw power. You have both.\"",
        "priest": "Eldric bows respectfully.\n\n\"A servant of the Light in these dark depths? How fitting.\n\nThe corruption here runs deep. Your spiritual sight may reveal what my eyes cannot.\"",
    },
}

# High-level greetings (level 30+, 50+)
LEVEL_GREETINGS = {
    "old_guard_marcus": {
        30: "\n\n*Marcus studies you with new respect.* \"You've grown powerful since we first met. The realm owes you a debt.\"",
        50: "\n\n*Marcus stands at attention.* \"Commander. I don't use that title lightly. You've earned it a hundred times over.\"",
    },
    "frostbeard_sage": {
        30: "\n\n*Frostbeard adjusts his spectacles.* \"My, you've come a long way from that green adventurer I first met!\"",
        50: "\n\n*Frostbeard whispers reverently.* \"Your power rivals the ancient heroes of old. Truly remarkable.\"",
    },
    "captain_seafoam": {
        30: "\n\n*Seafoam raises his flask.* \"To a proper adventurer! You've got salt water in yer veins now.\"",
        50: "\n\n*Seafoam removes his hat.* \"I've sailed every sea, and I've never met anyone as fearsome as you. Legend.\"",
    },
}


def get_dynamic_intro(npc_id: str, npc_data: dict, char_class: str, char_level: int) -> str:
    """Get class/level-appropriate introduction text."""
    # Try class-specific intro
    class_intros = DYNAMIC_INTRODUCTIONS.get(npc_id, {})
    base_text = class_intros.get(char_class, npc_data["introduction"]["text"])

    # Append level greeting if applicable
    level_greets = LEVEL_GREETINGS.get(npc_id, {})
    for level_threshold in sorted(level_greets.keys(), reverse=True):
        if char_level >= level_threshold:
            base_text += level_greets[level_threshold]
            break

    return base_text


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
        "faction": "stormwind_guard",
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
                    "reputation": {"stormwind_guard": 250},
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
                "time_limit_hours": 48,
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
                    "reputation": {"stormwind_guard": 500},
                },
                "dialogue": {
                    "accept": "\"This one's dangerous—a former guard who sold us out. Watch your back.\n⏰ You have **48 hours** to complete this mission!\"",
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
        "faction": "dwarven_explorers",
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
                    "reputation": {"dwarven_explorers": 300},
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
        "faction": "trade_coalition",
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
                "time_limit_hours": 24,
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
                    "reputation": {"trade_coalition": 500},
                },
                "dialogue": {
                    "accept": "\"Wonderful! Here's a map of their raiding camps. Be ruthless.\n⏰ Hurry though—I need those goods within **24 hours** before they spoil!\"",
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
        "faction": "pirate_fleet",
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
                    "reputation": {"pirate_fleet": 750},
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
        "faction": "arcane_order",
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
                "time_limit_hours": 72,
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
                    "reputation": {"arcane_order": 1000},
                },
                "dialogue": {
                    "accept": "\"Excellent! The depths are treacherous—but the reward is worth any risk.\n⏰ I'll wait **72 hours** for your return. After that, I must move on.\"",
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
                    "faction": npc.get("faction"),
                })
        return result

    # ── Quest Management ─────────────────────────────────────────────────────

    async def offer_quest(self, char_id: UUID, npc_id: str, quest_id: str):
        # Calculate expiration from time_limit_hours if set
        quest_data = self._find_quest_template(quest_id)
        expires_at = None
        if quest_data and quest_data.get("time_limit_hours"):
            expires_at = datetime.now(timezone.utc) + timedelta(hours=quest_data["time_limit_hours"])

        await self.db.execute(
            """INSERT INTO quest_progress (character_id, quest_id, npc_id, current_step, state, expires_at)
               VALUES ($1, $2, $3, 1, 'offered', $4)
               ON CONFLICT (character_id, quest_id) DO NOTHING""",
            char_id, quest_id, npc_id, expires_at,
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
        """Get all active quests, auto-failing expired timed quests."""
        rows = await self.db.fetch(
            """SELECT * FROM quest_progress
               WHERE character_id = $1 AND state IN ('active', 'offered')
               ORDER BY started_at""",
            char_id,
        )
        result = []
        now = datetime.now(timezone.utc)

        for r in rows:
            # Check for expiration
            expires_at = r.get("expires_at")
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and now > expires_at:
                # Quest expired — auto-fail
                await self.db.execute(
                    "UPDATE quest_progress SET state = 'expired' WHERE character_id = $1 AND quest_id = $2",
                    char_id, r["quest_id"],
                )
                continue

            quest_data = self._find_quest_template(r["quest_id"])
            if quest_data:
                entry = {
                    **dict(r),
                    "quest_name": quest_data["name"],
                    "quest_desc": quest_data["description"],
                    "total_steps": len(quest_data["steps"]),
                    "steps": quest_data["steps"],
                    "rewards": quest_data["rewards"],
                    "time_limit_hours": quest_data.get("time_limit_hours"),
                    "dialogue": quest_data.get("dialogue", {}),
                }
                result.append(entry)
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
                result.append({**dict(r), "quest_name": quest_data["name"]})
        return result

    async def advance_quest(self, char_id: UUID, quest_id: str) -> bool:
        progress = await self.get_quest_progress(char_id, quest_id)
        if not progress or progress["state"] != "active":
            return False
        quest_data = self._find_quest_template(quest_id)
        if not quest_data:
            return False
        if progress["current_step"] >= len(quest_data["steps"]):
            return False
        await self.db.execute(
            "UPDATE quest_progress SET current_step = current_step + 1 WHERE character_id = $1 AND quest_id = $2",
            char_id, quest_id,
        )
        return True

    async def complete_quest(self, char_id: UUID, quest_id: str) -> Optional[Dict]:
        """Mark quest completed and return rewards dict."""
        progress = await self.get_quest_progress(char_id, quest_id)
        if not progress or progress["state"] != "active":
            return None
        quest_data = self._find_quest_template(quest_id)
        if not quest_data:
            return None

        # Check if timed quest expired
        expires_at = progress.get("expires_at")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                await self.db.execute(
                    "UPDATE quest_progress SET state = 'expired' WHERE character_id = $1 AND quest_id = $2",
                    char_id, quest_id,
                )
                return None

        await self.db.execute(
            "UPDATE quest_progress SET state = 'completed', completed_at = NOW() WHERE character_id = $1 AND quest_id = $2",
            char_id, quest_id,
        )
        return quest_data["rewards"]

    async def abandon_quest(self, char_id: UUID, quest_id: str) -> bool:
        result = await self.db.execute(
            "DELETE FROM quest_progress WHERE character_id = $1 AND quest_id = $2 AND state IN ('active', 'offered')",
            char_id, quest_id,
        )
        return "DELETE 1" in result

    # ── Kill Progress Check ──────────────────────────────────────────────────

    async def check_kill_progress(
        self, char_id: UUID, enemy_key: str, zone_key: str, is_boss: bool
    ) -> List[str]:
        active = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id = $1 AND state = 'active'",
            char_id,
        )
        notifications = []

        for row in active:
            # Skip expired quests
            expires_at = row.get("expires_at")
            if expires_at:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    await self.db.execute(
                        "UPDATE quest_progress SET state = 'expired' WHERE character_id = $1 AND quest_id = $2",
                        char_id, row["quest_id"],
                    )
                    notifications.append(f"⏰ Quest **{row['quest_id']}** has expired!")
                    continue

            quest_data = self._find_quest_template(row["quest_id"])
            if not quest_data:
                continue

            step_idx = row["current_step"] - 1
            if step_idx >= len(quest_data["steps"]):
                continue

            step = quest_data["steps"][step_idx]
            check = step["completion_check"]
            advanced = False

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
                    notifications.append(f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!")
                else:
                    notifications.append(f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})")

            elif check["type"] == "kill_any_zone" and check["value"] == zone_key:
                needed = check.get("count", 1)
                kill_key = f"kills_zone_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills
                if current_kills >= needed:
                    advanced = True
                    notifications.append(f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!")
                else:
                    notifications.append(f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})")

            elif check["type"] == "kill_boss_zone" and check["value"] == zone_key and is_boss:
                needed = check.get("count", 1)
                kill_key = f"boss_kills_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills
                if current_kills >= needed:
                    advanced = True
                    notifications.append(f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!")
                else:
                    notifications.append(f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})")

            # Save metadata
            import json
            await self.db.execute(
                "UPDATE quest_progress SET metadata = $3::jsonb WHERE character_id = $1 AND quest_id = $2",
                char_id, row["quest_id"], json.dumps(meta),
            )
            if advanced:
                await self.advance_quest(char_id, row["quest_id"])

        return notifications

    async def check_talk_to_npc(self, char_id: UUID, npc_id: str) -> Optional[Dict]:
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
                next_step = row["current_step"] + 1
                if next_step > len(quest_data["steps"]):
                    return {"quest_id": row["quest_id"], "quest_data": quest_data, "complete": True}
                else:
                    await self.advance_quest(char_id, row["quest_id"])
                    return {
                        "quest_id": row["quest_id"],
                        "quest_data": quest_data,
                        "complete": False,
                        "next_step": quest_data["steps"][next_step - 1],
                    }
        return None

    def get_next_quest_for_npc(self, npc_id: str, completed_quests: List[str]) -> Optional[Dict]:
        npc = NPC_TEMPLATES.get(npc_id)
        if not npc:
            return None
        for quest in npc["quests"]:
            if quest["id"] not in completed_quests:
                return quest
        return None

    # ── Reputation ───────────────────────────────────────────────────────────

    async def add_reputation(self, char_id: UUID, faction_id: str, amount: int) -> Dict:
        """Add reputation and return new level info."""
        row = await self.db.fetchrow(
            "SELECT reputation FROM faction_reputation WHERE character_id = $1 AND faction_id = $2",
            char_id, faction_id,
        )
        old_rep = row["reputation"] if row else 0
        new_rep = old_rep + amount

        await self.db.execute(
            """INSERT INTO faction_reputation (character_id, faction_id, reputation)
               VALUES ($1, $2, $3)
               ON CONFLICT (character_id, faction_id)
               DO UPDATE SET reputation = $3, updated_at = NOW()""",
            char_id, faction_id, new_rep,
        )

        old_level = get_rep_level(old_rep)
        new_level = get_rep_level(new_rep)
        leveled_up = old_level["name"] != new_level["name"]

        return {
            "faction_id": faction_id,
            "old_rep": old_rep,
            "new_rep": new_rep,
            "level": new_level,
            "leveled_up": leveled_up,
        }

    async def get_reputation(self, char_id: UUID, faction_id: str) -> int:
        row = await self.db.fetchrow(
            "SELECT reputation FROM faction_reputation WHERE character_id = $1 AND faction_id = $2",
            char_id, faction_id,
        )
        return row["reputation"] if row else 0

    async def get_all_reputation(self, char_id: UUID) -> List[Dict]:
        """Get all faction standings for a character."""
        rows = await self.db.fetch(
            "SELECT faction_id, reputation, updated_at FROM faction_reputation WHERE character_id = $1 ORDER BY reputation DESC",
            char_id,
        )
        result = []
        for r in rows:
            faction = FACTIONS.get(r["faction_id"])
            if faction:
                level = get_rep_level(r["reputation"])
                result.append({
                    "faction_id": r["faction_id"],
                    "name": faction["name"],
                    "emoji": faction["emoji"],
                    "reputation": r["reputation"],
                    "level": level,
                })
        # Add undiscovered factions at 0
        known_ids = {r["faction_id"] for r in result}
        for fid, faction in FACTIONS.items():
            if fid not in known_ids:
                result.append({
                    "faction_id": fid,
                    "name": faction["name"],
                    "emoji": faction["emoji"],
                    "reputation": 0,
                    "level": get_rep_level(0),
                })
        return result

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _find_quest_template(self, quest_id: str) -> Optional[Dict]:
        for npc in NPC_TEMPLATES.values():
            for quest in npc["quests"]:
                if quest["id"] == quest_id:
                    return quest
        return None

    def find_npc_by_name(self, search: str) -> Optional[str]:
        search_lower = search.lower().strip()
        for npc_id, npc in NPC_TEMPLATES.items():
            if search_lower in npc["name"].lower():
                return npc_id
            if search_lower in npc["title"].lower():
                return npc_id
            first_word = npc["name"].split()[0].lower()
            if search_lower == first_word:
                return npc_id
            if search_lower in npc_id:
                return npc_id
        return None
