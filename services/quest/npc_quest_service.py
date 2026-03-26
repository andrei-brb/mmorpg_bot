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
            {
                "id": "marcus_quest_3",
                "name": "Forest Patrol",
                "description": "Help Marcus secure the forest by defeating multiple enemy types.",
                "level_req": 7,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 4 Forest Wolves",
                        "hint": "Wolves roam the forest paths.",
                        "completion_check": {"type": "kill_enemy", "value": "forest_wolf", "count": 4},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 3 Kobolds",
                        "hint": "Kobolds hide in the mines and caves.",
                        "completion_check": {"type": "kill_enemy", "value": "kobold", "count": 3},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Marcus",
                        "hint": "Use /interact marcus to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "old_guard_marcus"},
                    },
                ],
                "rewards": {
                    "xp": 2000,
                    "gold": 600,
                    "items": ["health_potion"],
                    "reputation": {"stormwind_guard": 600},
                },
                "dialogue": {
                    "accept": "\"The forest needs constant patrolling. Clear out the threats.\"",
                    "decline": "\"I understand. The forest will wait.\"",
                    "progress_1": "\"Good work! Keep clearing them out.\"",
                    "progress_2": "\"Excellent! The forest is getting safer.\"",
                    "completion": "\"The forest thanks you, adventurer. Here's your reward.\"",
                },
            },
            {
                "id": "marcus_quest_4",
                "name": "The Final Threat",
                "description": "Face the ultimate challenge: defeat a boss in Elwynn Forest.",
                "level_req": 9,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 8 enemies in Elwynn Forest",
                        "hint": "Prepare by clearing regular enemies first.",
                        "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 8},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat Hogger",
                        "hint": "Hogger is a dangerous boss. Use /fight to challenge him.",
                        "completion_check": {"type": "kill_enemy", "value": "hogger", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Marcus",
                        "hint": "Use /interact marcus to claim your reward.",
                        "completion_check": {"type": "talk_to_npc", "value": "old_guard_marcus"},
                    },
                ],
                "rewards": {
                    "xp": 3000,
                    "gold": 1000,
                    "items": ["iron_sword", "leather_cap"],
                    "reputation": {"stormwind_guard": 1000},
                },
                "dialogue": {
                    "accept": "\"Hogger is the most dangerous threat. Defeat him and the forest will be safe.\"",
                    "decline": "\"I understand. Bosses are not to be taken lightly.\"",
                    "progress_1": "\"Good preparation! Now face Hogger.\"",
                    "progress_2": "\"Hogger is defeated! Return for your reward.\"",
                    "completion": "\"Legendary! You've saved the forest. Here's a worthy reward.\"",
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
            {
                "id": "frostbeard_quest_2",
                "name": "Frozen Threats",
                "description": "Clear out more dangerous creatures in Dun Morogh.",
                "level_req": 3,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 4 Frostmane Trolls",
                        "hint": "Trolls are aggressive in the frozen peaks.",
                        "completion_check": {"type": "kill_enemy", "value": "frostmane_troll", "count": 4},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 2 Snow Leopards",
                        "hint": "Snow leopards hunt in the mountains.",
                        "completion_check": {"type": "kill_enemy", "value": "snow_leopard", "count": 2},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Frostbeard",
                        "hint": "Use /interact frostbeard to report your findings.",
                        "completion_check": {"type": "talk_to_npc", "value": "frostbeard_sage"},
                    },
                ],
                "rewards": {
                    "xp": 1200,
                    "gold": 450,
                    "items": ["chain_coif"],
                    "reputation": {"dwarven_explorers": 450},
                },
                "dialogue": {
                    "accept": "\"More data needed! Clear out these threats.\"",
                    "decline": "\"Suit yourself. The threats remain.\"",
                    "progress_1": "\"Good data collection! Keep going.\"",
                    "progress_2": "\"Excellent! The patterns are becoming clear.\"",
                    "completion": "\"Brilliant! Your data is invaluable. Here's your reward.\"",
                },
            },
            {
                "id": "frostbeard_quest_3",
                "name": "Zone Survey",
                "description": "Conduct a comprehensive survey of Dun Morogh's dangers.",
                "level_req": 6,
                "time_limit_hours": 48,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 10 enemies in Dun Morogh",
                        "hint": "Fight any enemies throughout the zone.",
                        "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 10},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Frostbeard",
                        "hint": "Use /interact frostbeard to share your survey results.",
                        "completion_check": {"type": "talk_to_npc", "value": "frostbeard_sage"},
                    },
                ],
                "rewards": {
                    "xp": 2000,
                    "gold": 700,
                    "items": ["frost_resist_potion"],
                    "reputation": {"dwarven_explorers": 700},
                },
                "dialogue": {
                    "accept": "\"A comprehensive survey! Complete it within 48 hours.\"",
                    "decline": "\"I understand. This is extensive work.\"",
                    "progress_1": "\"Keep fighting! The survey needs completion.\"",
                    "completion": "\"Incredible data! The zone is well documented now.\"",
                },
            },
            {
                "id": "frostbeard_quest_4",
                "name": "Ancient Frost Giant",
                "description": "Face the legendary Frost Giant that guards the ancient peaks.",
                "level_req": 9,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 8 enemies in Dun Morogh",
                        "hint": "Prepare by clearing regular enemies first.",
                        "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 8},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat the Ancient Frost Giant",
                        "hint": "The giant is a powerful boss. Use /fight to challenge it.",
                        "completion_check": {"type": "kill_enemy", "value": "ancient_frost_giant", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Frostbeard",
                        "hint": "Use /interact frostbeard to claim your reward.",
                        "completion_check": {"type": "talk_to_npc", "value": "frostbeard_sage"},
                    },
                ],
                "rewards": {
                    "xp": 3000,
                    "gold": 1000,
                    "items": ["dwarven_axe", "chain_coif"],
                    "reputation": {"dwarven_explorers": 1000},
                },
                "dialogue": {
                    "accept": "\"The Ancient Frost Giant is the ultimate challenge. Defeat it!\"",
                    "decline": "\"I understand. Giants are not to be taken lightly.\"",
                    "progress_1": "\"Good preparation! Now face the giant.\"",
                    "progress_2": "\"The giant is defeated! Return for your reward.\"",
                    "completion": "\"Legendary! You've defeated the ancient giant. Here's a worthy reward.\"",
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
            {
                "id": "kira_quest_2",
                "name": "Desert Raiders",
                "description": "Deal with multiple raiding parties in The Barrens.",
                "level_req": 13,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 6 Razormane Warriors",
                        "hint": "Razormane warriors are aggressive raiders.",
                        "completion_check": {"type": "kill_enemy", "value": "razormane_warrior", "count": 6},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 4 Quillboar",
                        "hint": "Quillboar are dangerous desert creatures.",
                        "completion_check": {"type": "kill_enemy", "value": "quillboar", "count": 4},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Kira",
                        "hint": "Use /interact kira to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "wandering_merchant"},
                    },
                ],
                "rewards": {
                    "xp": 4000,
                    "gold": 2000,
                    "items": ["stamina_draught"],
                    "reputation": {"trade_coalition": 700},
                },
                "dialogue": {
                    "accept": "\"More raiders! Clear them out for me.\"",
                    "decline": "\"I understand. The raiders are dangerous.\"",
                    "progress_1": "\"Good work! Keep clearing them out.\"",
                    "progress_2": "\"Excellent! The routes are getting safer.\"",
                    "completion": "\"Wonderful! My routes are safer now. Here's your reward.\"",
                },
            },
            {
                "id": "kira_quest_3",
                "name": "Trade Route Security",
                "description": "Secure the trade routes by clearing The Barrens.",
                "level_req": 18,
                "time_limit_hours": 48,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 12 enemies in The Barrens",
                        "hint": "Fight any enemies throughout the zone.",
                        "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 12},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Kira",
                        "hint": "Use /interact kira to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "wandering_merchant"},
                    },
                ],
                "rewards": {
                    "xp": 5000,
                    "gold": 2500,
                    "items": ["bone_club"],
                    "reputation": {"trade_coalition": 900},
                },
                "dialogue": {
                    "accept": "\"Secure the routes! Complete this within 48 hours.\"",
                    "decline": "\"I understand. This is extensive work.\"",
                    "progress_1": "\"Keep fighting! The routes need securing.\"",
                    "completion": "\"Incredible! The trade routes are much safer now.\"",
                },
            },
            {
                "id": "kira_quest_4",
                "name": "The Chieftain's End",
                "description": "Eliminate the Razormane Chieftain to secure the trade routes permanently.",
                "level_req": 22,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 10 enemies in The Barrens",
                        "hint": "Prepare by clearing regular enemies first.",
                        "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 10},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat the Razormane Chieftain",
                        "hint": "The chieftain is a powerful boss. Use /fight to challenge him.",
                        "completion_check": {"type": "kill_enemy", "value": "razormane_chieftain", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Kira",
                        "hint": "Use /interact kira to claim your reward.",
                        "completion_check": {"type": "talk_to_npc", "value": "wandering_merchant"},
                    },
                ],
                "rewards": {
                    "xp": 7000,
                    "gold": 3500,
                    "items": ["raptor_hide_vest", "stamina_draught"],
                    "reputation": {"trade_coalition": 1200},
                },
                "dialogue": {
                    "accept": "\"The chieftain is the ultimate threat. Defeat him and the routes will be safe!\"",
                    "decline": "\"I understand. Chieftains are not to be taken lightly.\"",
                    "progress_1": "\"Good preparation! Now face the chieftain.\"",
                    "progress_2": "\"The chieftain is defeated! Return for your reward.\"",
                    "completion": "\"Legendary! You've secured the trade routes permanently. Here's a worthy reward.\"",
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
            {
                "id": "seafoam_quest_2",
                "name": "Jungle Predators",
                "description": "Clear out dangerous predators in Stranglethorn.",
                "level_req": 30,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 6 Panthers",
                        "hint": "Panthers are stealthy jungle predators.",
                        "completion_check": {"type": "kill_enemy", "value": "panther", "count": 6},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 4 Tigers",
                        "hint": "Tigers are powerful jungle hunters.",
                        "completion_check": {"type": "kill_enemy", "value": "tiger", "count": 4},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Captain Seafoam",
                        "hint": "Use /interact seafoam to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "captain_seafoam"},
                    },
                ],
                "rewards": {
                    "xp": 7000,
                    "gold": 4000,
                    "items": ["elixir_of_fortitude"],
                    "reputation": {"pirate_fleet": 1000},
                },
                "dialogue": {
                    "accept": "\"Arr! Clear out those predators! They're scaring away the treasure.\"",
                    "decline": "\"Landlubber! The predators will wait.\"",
                    "progress_1": "\"Good work! Keep clearing them out.\"",
                    "progress_2": "\"Excellent! The jungle is getting safer.\"",
                    "completion": "\"Wonderful! The predators are gone. Here's yer reward.\"",
                },
            },
            {
                "id": "seafoam_quest_3",
                "name": "Jungle Clearing",
                "description": "Clear the jungle of all threats to access hidden treasure sites.",
                "level_req": 35,
                "time_limit_hours": 72,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 15 enemies in Stranglethorn Vale",
                        "hint": "Fight any enemies throughout the jungle.",
                        "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 15},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Captain Seafoam",
                        "hint": "Use /interact seafoam to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "captain_seafoam"},
                    },
                ],
                "rewards": {
                    "xp": 9000,
                    "gold": 5000,
                    "items": ["jungle_leather_chest"],
                    "reputation": {"pirate_fleet": 1200},
                },
                "dialogue": {
                    "accept": "\"Clear the jungle! Complete this within 72 hours.\"",
                    "decline": "\"Landlubber! The jungle will wait.\"",
                    "progress_1": "\"Keep fighting! The jungle needs clearing.\"",
                    "completion": "\"Incredible! The jungle is much safer now.\"",
                },
            },
            {
                "id": "seafoam_quest_4",
                "name": "The Jungle Lord",
                "description": "Face the legendary Jungle Lord that guards the greatest treasure.",
                "level_req": 42,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 12 enemies in Stranglethorn Vale",
                        "hint": "Prepare by clearing regular enemies first.",
                        "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 12},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat the Jungle Lord",
                        "hint": "The Jungle Lord is a powerful boss. Use /fight to challenge him.",
                        "completion_check": {"type": "kill_enemy", "value": "jungle_lord", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Captain Seafoam",
                        "hint": "Use /interact seafoam to claim your share of the treasure.",
                        "completion_check": {"type": "talk_to_npc", "value": "captain_seafoam"},
                    },
                ],
                "rewards": {
                    "xp": 12000,
                    "gold": 7000,
                    "items": ["corsair_blade", "jungle_leather_chest"],
                    "reputation": {"pirate_fleet": 1500},
                },
                "dialogue": {
                    "accept": "\"The Jungle Lord guards the greatest treasure! Defeat him!\"",
                    "decline": "\"Landlubber! The treasure will wait.\"",
                    "progress_1": "\"Good preparation! Now face the Jungle Lord.\"",
                    "progress_2": "\"The Jungle Lord is defeated! Return for yer share.\"",
                    "completion": "\"Legendary! Ye've earned the greatest treasure. Here's yer share.\"",
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
            {
                "id": "eldric_quest_2",
                "name": "Dark Iron Forces",
                "description": "Thin the ranks of the Dark Iron Dwarves in Blackrock Depths.",
                "level_req": 53,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 8 Dark Iron Dwarves",
                        "hint": "Dark Iron Dwarves guard the depths.",
                        "completion_check": {"type": "kill_enemy", "value": "dark_iron_dwarf", "count": 8},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat 5 Dark Iron Guards",
                        "hint": "Guards are elite Dark Iron warriors.",
                        "completion_check": {"type": "kill_enemy", "value": "dark_iron_guard", "count": 5},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Eldric",
                        "hint": "Use /interact eldric to report your findings.",
                        "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                    },
                ],
                "rewards": {
                    "xp": 15000,
                    "gold": 7000,
                    "items": ["flask_of_the_titans"],
                    "reputation": {"arcane_order": 1500},
                },
                "dialogue": {
                    "accept": "\"The Dark Iron forces are strong. Thin their ranks.\"",
                    "decline": "\"I understand. The depths are dangerous.\"",
                    "progress_1": "\"Good work! Keep pushing forward.\"",
                    "progress_2": "\"Excellent! The forces are weakening.\"",
                    "completion": "\"Incredible! The Dark Iron forces are diminished. Here's your reward.\"",
                },
            },
            {
                "id": "eldric_quest_3",
                "name": "Depths Exploration",
                "description": "Explore the depths and defeat all threats to uncover ancient secrets.",
                "level_req": 56,
                "time_limit_hours": 96,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 20 enemies in Blackrock Depths",
                        "hint": "Fight any enemies throughout the depths.",
                        "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 20},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Eldric",
                        "hint": "Use /interact eldric to share your discoveries.",
                        "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                    },
                ],
                "rewards": {
                    "xp": 20000,
                    "gold": 10000,
                    "items": ["shadowforge_plate"],
                    "reputation": {"arcane_order": 2000},
                },
                "dialogue": {
                    "accept": "\"Explore the depths thoroughly! Complete this within 96 hours.\"",
                    "decline": "\"I understand. The depths are treacherous.\"",
                    "progress_1": "\"Keep fighting! The depths need exploration.\"",
                    "completion": "\"Incredible discoveries! The depths are well documented now.\"",
                },
            },
            {
                "id": "eldric_quest_4",
                "name": "The Emperor's Fall",
                "description": "Face the ultimate challenge: defeat Emperor Dagran Thaurissan.",
                "level_req": 58,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 15 enemies in Blackrock Depths",
                        "hint": "Prepare by clearing regular enemies first.",
                        "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 15},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat Emperor Dagran Thaurissan",
                        "hint": "The Emperor is the ultimate boss. Use /fight to challenge him.",
                        "completion_check": {"type": "kill_enemy", "value": "emperor_dagran_thaurissan", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Eldric",
                        "hint": "Use /interact eldric to claim your ultimate reward.",
                        "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                    },
                ],
                "rewards": {
                    "xp": 30000,
                    "gold": 15000,
                    "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"],
                    "reputation": {"arcane_order": 3000},
                },
                "dialogue": {
                    "accept": "\"The Emperor is the ultimate challenge. Defeat him and uncover the greatest secret!\"",
                    "decline": "\"I understand. Emperors are not to be taken lightly.\"",
                    "progress_1": "\"Good preparation! Now face the Emperor.\"",
                    "progress_2": "\"The Emperor is defeated! Return for your ultimate reward.\"",
                    "completion": "\"Legendary! You've uncovered the greatest secret. Here's your ultimate reward.\"",
                },
            },
        ],
    },
    
    # ── New NPCs for Elwynn Forest (6 additional) ────────────────────────────
    "farmer_saldean": {
        "name": "Farmer Saldean",
        "title": "🌾 Local Farmer",
        "discovery_hint": "A worried farmer stands by his damaged crops, shaking his head.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.16,
        "faction": "stormwind_guard",
        "introduction": {
            "text": (
                "The farmer looks up from his damaged crops with desperation.\n\n"
                "\"Please, adventurer! The wolves and boars are destroying my farm!\n"
                "I can't feed my family if this continues.\n\n"
                "Help me protect my crops, and I'll reward you with what little I have.\""
            ),
        },
        "quests": [
            {
                "id": "saldean_quest_1",
                "name": "Protect the Crops",
                "description": "Defeat the creatures threatening Farmer Saldean's crops.",
                "level_req": 2,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 4 Young Boars",
                        "hint": "Boars are destroying the crops.",
                        "completion_check": {"type": "kill_enemy", "value": "young_boar", "count": 4},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Farmer Saldean",
                        "hint": "Use /interact saldean to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "farmer_saldean"},
                    },
                ],
                "rewards": {
                    "xp": 600,
                    "gold": 250,
                    "items": ["health_potion"],
                    "reputation": {"stormwind_guard": 300},
                },
                "dialogue": {
                    "accept": "\"Thank you! Please clear out those boars quickly!\"",
                    "decline": "\"I understand. The farm will wait.\"",
                    "progress_1": "\"Keep going! The crops need protection.\"",
                    "completion": "\"Thank you so much! My crops are safe now. Here's your reward.\"",
                },
            },
            {
                "id": "saldean_quest_2",
                "name": "Wolf Pack Threat",
                "description": "Eliminate the wolf pack that's been hunting near the farm.",
                "level_req": 4,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 5 Forest Wolves",
                        "hint": "Wolves are hunting near the farm.",
                        "completion_check": {"type": "kill_enemy", "value": "forest_wolf", "count": 5},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Farmer Saldean",
                        "hint": "Use /interact saldean to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "farmer_saldean"},
                    },
                ],
                "rewards": {
                    "xp": 1000,
                    "gold": 400,
                    "items": ["leather_cap"],
                    "reputation": {"stormwind_guard": 400},
                },
                "dialogue": {
                    "accept": "\"The wolves are getting bolder! Please help!\"",
                    "decline": "\"I understand. The wolves are dangerous.\"",
                    "progress_1": "\"Keep fighting! The wolves must be stopped.\"",
                    "completion": "\"Wonderful! The wolves are gone. Here's your reward.\"",
                },
            },
            {
                "id": "saldean_quest_3",
                "name": "Farm Security",
                "description": "Secure the entire farm area by clearing all threats.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 10 enemies in Elwynn Forest",
                        "hint": "Clear all threats to the farm area.",
                        "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 10},
                    },
                    {
                        "step": 2,
                        "objective": "Return to Farmer Saldean",
                        "hint": "Use /interact saldean to report your success.",
                        "completion_check": {"type": "talk_to_npc", "value": "farmer_saldean"},
                    },
                ],
                "rewards": {
                    "xp": 1800,
                    "gold": 700,
                    "items": ["iron_sword"],
                    "reputation": {"stormwind_guard": 600},
                },
                "dialogue": {
                    "accept": "\"Secure the entire area! Complete this within 48 hours!\"",
                    "decline": "\"I understand. This is extensive work.\"",
                    "progress_1": "\"Keep fighting! The farm needs complete security.\"",
                    "completion": "\"Incredible! The farm is completely secure now.\"",
                },
            },
            {
                "id": "saldean_quest_4",
                "name": "The Spider Queen",
                "description": "Defeat the Spider Queen that's been terrorizing the farm.",
                "level_req": 9,
                "steps": [
                    {
                        "step": 1,
                        "objective": "Defeat 8 enemies in Elwynn Forest",
                        "hint": "Prepare by clearing regular enemies first.",
                        "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 8},
                    },
                    {
                        "step": 2,
                        "objective": "Defeat the Spider Queen",
                        "hint": "The Spider Queen is a powerful boss. Use /fight to challenge her.",
                        "completion_check": {"type": "kill_enemy", "value": "spider_queen", "count": 1},
                    },
                    {
                        "step": 3,
                        "objective": "Return to Farmer Saldean",
                        "hint": "Use /interact saldean to claim your reward.",
                        "completion_check": {"type": "talk_to_npc", "value": "farmer_saldean"},
                    },
                ],
                "rewards": {
                    "xp": 2800,
                    "gold": 1100,
                    "items": ["iron_sword", "leather_cap"],
                    "reputation": {"stormwind_guard": 900},
                },
                "dialogue": {
                    "accept": "\"The Spider Queen is the ultimate threat! Defeat her!\"",
                    "decline": "\"I understand. The Spider Queen is dangerous.\"",
                    "progress_1": "\"Good preparation! Now face the Spider Queen.\"",
                    "progress_2": "\"The Spider Queen is defeated! Return for your reward.\"",
                    "completion": "\"Legendary! You've saved my farm. Here's a worthy reward.\"",
                },
            },
        ],
    },
    
    "guard_thomas": {
        "name": "Guard Thomas",
        "title": "⚔️ Stormwind Guard",
        "discovery_hint": "A young guard patrols the road, looking alert and ready.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.17,
        "faction": "stormwind_guard",
        "introduction": {
            "text": (
                "The guard stands at attention as you approach.\n\n"
                "\"Hail, adventurer! I'm Guard Thomas, assigned to patrol these roads.\n"
                "The Defias have been causing trouble, and we need help.\n\n"
                "If you're willing to assist, I have several tasks that need completion.\""
            ),
        },
        "quests": [
            {
                "id": "thomas_quest_1",
                "name": "Road Patrol",
                "description": "Help Guard Thomas patrol the roads by defeating threats.",
                "level_req": 2,
                "steps": [
                    {"step": 1, "objective": "Defeat 4 Defias Bandits", "hint": "Bandits threaten the roads.", "completion_check": {"type": "kill_enemy", "value": "defias_bandit", "count": 4}},
                    {"step": 2, "objective": "Return to Guard Thomas", "hint": "Use /interact thomas to report back.", "completion_check": {"type": "talk_to_npc", "value": "guard_thomas"}},
                ],
                "rewards": {"xp": 700, "gold": 280, "items": ["health_potion"], "reputation": {"stormwind_guard": 350}},
                "dialogue": {"accept": "\"Good! Help me secure these roads.\"", "decline": "\"I understand. The roads will wait.\"", "progress_1": "\"Keep going! The roads need securing.\"", "completion": "\"Excellent! The roads are safer. Here's your reward.\""},
            },
            {
                "id": "thomas_quest_2",
                "name": "Kobold Menace",
                "description": "Clear out the kobolds that have been raiding travelers.",
                "level_req": 4,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Kobolds", "hint": "Kobolds hide in caves and mines.", "completion_check": {"type": "kill_enemy", "value": "kobold", "count": 5}},
                    {"step": 2, "objective": "Return to Guard Thomas", "hint": "Use /interact thomas to report back.", "completion_check": {"type": "talk_to_npc", "value": "guard_thomas"}},
                ],
                "rewards": {"xp": 1100, "gold": 450, "items": ["leather_cap"], "reputation": {"stormwind_guard": 450}},
                "dialogue": {"accept": "\"The kobolds are getting bolder! Clear them out.\"", "decline": "\"I understand. Kobolds are tricky.\"", "progress_1": "\"Keep fighting! The kobolds must be stopped.\"", "completion": "\"Wonderful! The kobolds are gone. Here's your reward.\""},
            },
            {
                "id": "thomas_quest_3",
                "name": "Complete Security",
                "description": "Secure all roads by clearing threats throughout Elwynn Forest.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 10 enemies in Elwynn Forest", "hint": "Clear all threats to the roads.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 10}},
                    {"step": 2, "objective": "Return to Guard Thomas", "hint": "Use /interact thomas to report back.", "completion_check": {"type": "talk_to_npc", "value": "guard_thomas"}},
                ],
                "rewards": {"xp": 2000, "gold": 800, "items": ["iron_sword"], "reputation": {"stormwind_guard": 700}},
                "dialogue": {"accept": "\"Secure all roads! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The roads need complete security.\"", "completion": "\"Incredible! All roads are secure now.\""},
            },
            {
                "id": "thomas_quest_4",
                "name": "The Defias Ringleader",
                "description": "Defeat the Defias Ringleader to end the bandit threat permanently.",
                "level_req": 9,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 enemies in Elwynn Forest", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 8}},
                    {"step": 2, "objective": "Defeat the Defias Ringleader", "hint": "The Ringleader is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "defias_ringleader", "count": 1}},
                    {"step": 3, "objective": "Return to Guard Thomas", "hint": "Use /interact thomas to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "guard_thomas"}},
                ],
                "rewards": {"xp": 3000, "gold": 1200, "items": ["iron_sword", "leather_cap"], "reputation": {"stormwind_guard": 1000}},
                "dialogue": {"accept": "\"The Ringleader is the ultimate threat! Defeat him!\"", "decline": "\"I understand. The Ringleader is dangerous.\"", "progress_1": "\"Good preparation! Now face the Ringleader.\"", "progress_2": "\"The Ringleader is defeated! Return for your reward.\"", "completion": "\"Legendary! You've ended the bandit threat. Here's a worthy reward.\""},
            },
        ],
    },
    
    "merchant_westfall": {
        "name": "Merchant Westfall",
        "title": "📦 Traveling Merchant",
        "discovery_hint": "A merchant with a broken cart sits by the roadside, counting coins.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.15,
        "faction": "stormwind_guard",
        "introduction": {
            "text": (
                "The merchant looks up from his broken cart with a worried expression.\n\n"
                "\"Oh, thank goodness! A capable adventurer!\n"
                "My cart was attacked by bandits, and I lost most of my goods.\n\n"
                "Help me recover what I can, and I'll reward you handsomely.\""
            ),
        },
        "quests": [
            {
                "id": "westfall_quest_1",
                "name": "Recover Lost Goods",
                "description": "Help the merchant recover goods stolen by bandits.",
                "level_req": 3,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Defias Bandits", "hint": "Bandits stole the merchant's goods.", "completion_check": {"type": "kill_enemy", "value": "defias_bandit", "count": 5}},
                    {"step": 2, "objective": "Return to Merchant Westfall", "hint": "Use /interact westfall to return the goods.", "completion_check": {"type": "talk_to_npc", "value": "merchant_westfall"}},
                ],
                "rewards": {"xp": 900, "gold": 350, "items": ["health_potion"], "reputation": {"stormwind_guard": 400}},
                "dialogue": {"accept": "\"Thank you! Please recover my goods quickly!\"", "decline": "\"I understand. The goods will wait.\"", "progress_1": "\"Keep going! My goods are out there.\"", "completion": "\"Thank you so much! Here's your reward.\""},
            },
            {
                "id": "westfall_quest_2",
                "name": "Gnoll Raiders",
                "description": "Deal with the gnoll raiders that have been attacking merchants.",
                "level_req": 5,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Gnoll Raiders", "hint": "Gnolls are aggressive raiders.", "completion_check": {"type": "kill_enemy", "value": "gnoll_raider", "count": 6}},
                    {"step": 2, "objective": "Return to Merchant Westfall", "hint": "Use /interact westfall to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_westfall"}},
                ],
                "rewards": {"xp": 1300, "gold": 500, "items": ["leather_cap"], "reputation": {"stormwind_guard": 500}},
                "dialogue": {"accept": "\"The gnolls are getting bolder! Clear them out.\"", "decline": "\"I understand. Gnolls are dangerous.\"", "progress_1": "\"Keep fighting! The gnolls must be stopped.\"", "completion": "\"Wonderful! The gnolls are gone. Here's your reward.\""},
            },
            {
                "id": "westfall_quest_3",
                "name": "Trade Route Safety",
                "description": "Secure the trade routes by clearing all threats.",
                "level_req": 8,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in Elwynn Forest", "hint": "Clear all threats to the trade routes.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 12}},
                    {"step": 2, "objective": "Return to Merchant Westfall", "hint": "Use /interact westfall to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_westfall"}},
                ],
                "rewards": {"xp": 2500, "gold": 900, "items": ["iron_sword"], "reputation": {"stormwind_guard": 800}},
                "dialogue": {"accept": "\"Secure the routes! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The routes need securing.\"", "completion": "\"Incredible! The trade routes are secure now.\""},
            },
            {
                "id": "westfall_quest_4",
                "name": "The Murloc Warlord",
                "description": "Defeat the Murloc Warlord that's been terrorizing the trade routes.",
                "level_req": 10,
                "steps": [
                    {"step": 1, "objective": "Defeat 10 enemies in Elwynn Forest", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 10}},
                    {"step": 2, "objective": "Defeat the Murloc Warlord", "hint": "The Warlord is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "murloc_warlord", "count": 1}},
                    {"step": 3, "objective": "Return to Merchant Westfall", "hint": "Use /interact westfall to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "merchant_westfall"}},
                ],
                "rewards": {"xp": 3500, "gold": 1300, "items": ["iron_sword", "leather_cap"], "reputation": {"stormwind_guard": 1100}},
                "dialogue": {"accept": "\"The Warlord is the ultimate threat! Defeat him!\"", "decline": "\"I understand. The Warlord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Warlord.\"", "progress_2": "\"The Warlord is defeated! Return for your reward.\"", "completion": "\"Legendary! You've secured the trade routes. Here's a worthy reward.\""},
            },
        ],
    },
    
    "priest_lightbringer": {
        "name": "Priest Lightbringer",
        "title": "✨ Light's Servant",
        "discovery_hint": "A priest in white robes tends to wounded travelers at a small shrine.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.14,
        "faction": "stormwind_guard",
        "introduction": {
            "text": (
                "The priest looks up from tending a wounded traveler.\n\n"
                "\"Blessings of the Light upon you, adventurer.\n"
                "I am Priest Lightbringer, and I tend to those harmed by the darkness.\n\n"
                "The Light calls for action against the evil that plagues this forest.\n"
                "Will you answer the call?\""
            ),
        },
        "quests": [
            {
                "id": "lightbringer_quest_1",
                "name": "Cleanse the Darkness",
                "description": "Help the priest cleanse the darkness from Elwynn Forest.",
                "level_req": 3,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Spiders", "hint": "Spiders represent the darkness.", "completion_check": {"type": "kill_enemy", "value": "spider", "count": 5}},
                    {"step": 2, "objective": "Return to Priest Lightbringer", "hint": "Use /interact lightbringer to report back.", "completion_check": {"type": "talk_to_npc", "value": "priest_lightbringer"}},
                ],
                "rewards": {"xp": 850, "gold": 320, "items": ["health_potion"], "reputation": {"stormwind_guard": 380}},
                "dialogue": {"accept": "\"The Light guides you. Go forth and cleanse the darkness.\"", "decline": "\"I understand. The Light will wait.\"", "progress_1": "\"Keep fighting! The darkness must be cleansed.\"", "completion": "\"Blessings upon you! The Light is stronger. Here's your reward.\""},
            },
            {
                "id": "lightbringer_quest_2",
                "name": "Murloc Scourge",
                "description": "Eliminate the murloc threat that's been attacking travelers.",
                "level_req": 5,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Murloc Scouts", "hint": "Murlocs are a dangerous threat.", "completion_check": {"type": "kill_enemy", "value": "murloc_scout", "count": 6}},
                    {"step": 2, "objective": "Return to Priest Lightbringer", "hint": "Use /interact lightbringer to report back.", "completion_check": {"type": "talk_to_npc", "value": "priest_lightbringer"}},
                ],
                "rewards": {"xp": 1200, "gold": 480, "items": ["leather_cap"], "reputation": {"stormwind_guard": 480}},
                "dialogue": {"accept": "\"The murlocs must be stopped! The Light demands it.\"", "decline": "\"I understand. Murlocs are dangerous.\"", "progress_1": "\"Keep fighting! The murlocs must be eliminated.\"", "completion": "\"Wonderful! The murloc threat is diminished. Here's your reward.\""},
            },
            {
                "id": "lightbringer_quest_3",
                "name": "Forest Purification",
                "description": "Purify the entire forest by clearing all dark threats.",
                "level_req": 8,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in Elwynn Forest", "hint": "Clear all dark threats from the forest.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 12}},
                    {"step": 2, "objective": "Return to Priest Lightbringer", "hint": "Use /interact lightbringer to report back.", "completion_check": {"type": "talk_to_npc", "value": "priest_lightbringer"}},
                ],
                "rewards": {"xp": 2400, "gold": 950, "items": ["iron_sword"], "reputation": {"stormwind_guard": 850}},
                "dialogue": {"accept": "\"Purify the forest! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The forest needs purification.\"", "completion": "\"Incredible! The forest is purified. The Light shines brighter.\""},
            },
            {
                "id": "lightbringer_quest_4",
                "name": "The Ultimate Darkness",
                "description": "Face the ultimate darkness: defeat Hogger, the embodiment of evil.",
                "level_req": 10,
                "steps": [
                    {"step": 1, "objective": "Defeat 10 enemies in Elwynn Forest", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 10}},
                    {"step": 2, "objective": "Defeat Hogger", "hint": "Hogger is the ultimate boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "hogger", "count": 1}},
                    {"step": 3, "objective": "Return to Priest Lightbringer", "hint": "Use /interact lightbringer to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "priest_lightbringer"}},
                ],
                "rewards": {"xp": 3600, "gold": 1400, "items": ["iron_sword", "leather_cap"], "reputation": {"stormwind_guard": 1200}},
                "dialogue": {"accept": "\"Hogger is the ultimate darkness! Defeat him in the Light's name!\"", "decline": "\"I understand. The ultimate darkness is dangerous.\"", "progress_1": "\"Good preparation! Now face Hogger.\"", "progress_2": "\"Hogger is defeated! The Light triumphs! Return for your reward.\"", "completion": "\"Legendary! You've banished the ultimate darkness. The Light rewards you.\""},
            },
        ],
    },
    
    "hunter_redpath": {
        "name": "Hunter Redpath",
        "title": "🏹 Master Tracker",
        "discovery_hint": "A skilled hunter examines tracks near a forest path.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.16,
        "faction": "stormwind_guard",
        "introduction": {
            "text": (
                "The hunter looks up from examining tracks with a knowing smile.\n\n"
                "\"Ah, another tracker! I'm Hunter Redpath, and I know these woods better than anyone.\n"
                "I've been tracking some dangerous prey, and I could use help.\n\n"
                "If you're skilled with a weapon, I have several hunts that need completion.\""
            ),
        },
        "quests": [
            {
                "id": "redpath_quest_1",
                "name": "First Hunt",
                "description": "Join Hunter Redpath on your first hunt in Elwynn Forest.",
                "level_req": 2,
                "steps": [
                    {"step": 1, "objective": "Defeat 4 Forest Wolves", "hint": "Wolves are common prey in the forest.", "completion_check": {"type": "kill_enemy", "value": "forest_wolf", "count": 4}},
                    {"step": 2, "objective": "Return to Hunter Redpath", "hint": "Use /interact redpath to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_redpath"}},
                ],
                "rewards": {"xp": 750, "gold": 300, "items": ["health_potion"], "reputation": {"stormwind_guard": 360}},
                "dialogue": {"accept": "\"Good! Let's see what you can track.\"", "decline": "\"I understand. Hunting takes skill.\"", "progress_1": "\"Keep tracking! You're doing well.\"", "completion": "\"Excellent tracking! Here's your reward.\""},
            },
            {
                "id": "redpath_quest_2",
                "name": "Dual Prey",
                "description": "Hunt multiple types of dangerous creatures.",
                "level_req": 4,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Forest Wolves", "hint": "Track and defeat wolves.", "completion_check": {"type": "kill_enemy", "value": "forest_wolf", "count": 5}},
                    {"step": 2, "objective": "Defeat 3 Young Boars", "hint": "Now track and defeat boars.", "completion_check": {"type": "kill_enemy", "value": "young_boar", "count": 3}},
                    {"step": 3, "objective": "Return to Hunter Redpath", "hint": "Use /interact redpath to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_redpath"}},
                ],
                "rewards": {"xp": 1150, "gold": 460, "items": ["leather_cap"], "reputation": {"stormwind_guard": 470}},
                "dialogue": {"accept": "\"This is more challenging. Track both prey types.\"", "decline": "\"I understand. Multiple prey is difficult.\"", "progress_1": "\"Good tracking! Keep going.\"", "progress_2": "\"Excellent! You're a skilled tracker.\"", "completion": "\"Outstanding tracking! Here's your reward.\""},
            },
            {
                "id": "redpath_quest_3",
                "name": "Forest Sweep",
                "description": "Conduct a comprehensive hunt throughout Elwynn Forest.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 11 enemies in Elwynn Forest", "hint": "Hunt any creatures throughout the forest.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 11}},
                    {"step": 2, "objective": "Return to Hunter Redpath", "hint": "Use /interact redpath to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_redpath"}},
                ],
                "rewards": {"xp": 2200, "gold": 880, "items": ["iron_sword"], "reputation": {"stormwind_guard": 780}},
                "dialogue": {"accept": "\"A comprehensive hunt! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive hunting.\"", "progress_1": "\"Keep hunting! The forest needs clearing.\"", "completion": "\"Incredible hunting! The forest is well tracked now.\""},
            },
            {
                "id": "redpath_quest_4",
                "name": "The Ultimate Prey",
                "description": "Face the ultimate challenge: hunt down Hogger, the legendary beast.",
                "level_req": 9,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 enemies in Elwynn Forest", "hint": "Prepare by hunting regular creatures first.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 9}},
                    {"step": 2, "objective": "Defeat Hogger", "hint": "Hogger is the ultimate prey. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "hogger", "count": 1}},
                    {"step": 3, "objective": "Return to Hunter Redpath", "hint": "Use /interact redpath to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "hunter_redpath"}},
                ],
                "rewards": {"xp": 3200, "gold": 1280, "items": ["iron_sword", "leather_cap"], "reputation": {"stormwind_guard": 1050}},
                "dialogue": {"accept": "\"Hogger is the ultimate prey! Hunt him down!\"", "decline": "\"I understand. The ultimate prey is dangerous.\"", "progress_1": "\"Good preparation! Now hunt Hogger.\"", "progress_2": "\"Hogger is defeated! Return for your reward.\"", "completion": "\"Legendary hunting! You've taken down the ultimate prey. Here's a worthy reward.\""},
            },
        ],
    },
    
    "mage_apprentice": {
        "name": "Mage Apprentice",
        "title": "🔮 Young Scholar",
        "discovery_hint": "A young mage practices spells near a glowing crystal.",
        "zones": ["elwynn_forest"],
        "discovery_chance": 0.15,
        "faction": "stormwind_guard",
        "introduction": {
            "text": (
                "The young mage looks up from practicing spells with excitement.\n\n"
                "\"Oh! Another adventurer! I'm a mage apprentice studying the arcane.\n"
                "I've been researching the magical disturbances in this forest.\n\n"
                "If you can help me gather data by defeating certain creatures,\n"
                "I'll share what I've learned and reward you.\""
            ),
        },
        "quests": [
            {
                "id": "apprentice_quest_1",
                "name": "Arcane Research",
                "description": "Help the mage apprentice with arcane research by defeating magical creatures.",
                "level_req": 3,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Spiders", "hint": "Spiders have magical properties.", "completion_check": {"type": "kill_enemy", "value": "spider", "count": 5}},
                    {"step": 2, "objective": "Return to Mage Apprentice", "hint": "Use /interact apprentice to report back.", "completion_check": {"type": "talk_to_npc", "value": "mage_apprentice"}},
                ],
                "rewards": {"xp": 880, "gold": 340, "items": ["health_potion"], "reputation": {"stormwind_guard": 390}},
                "dialogue": {"accept": "\"Excellent! Help me gather arcane data.\"", "decline": "\"I understand. Research takes time.\"", "progress_1": "\"Keep going! The data is valuable.\"", "completion": "\"Wonderful data! Here's your reward.\""},
            },
            {
                "id": "apprentice_quest_2",
                "name": "Magical Threats",
                "description": "Study the magical threats in Elwynn Forest.",
                "level_req": 5,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Kobolds", "hint": "Kobolds have arcane connections.", "completion_check": {"type": "kill_enemy", "value": "kobold", "count": 6}},
                    {"step": 2, "objective": "Defeat 4 Spiders", "hint": "Spiders are magical creatures.", "completion_check": {"type": "kill_enemy", "value": "spider", "count": 4}},
                    {"step": 3, "objective": "Return to Mage Apprentice", "hint": "Use /interact apprentice to report back.", "completion_check": {"type": "talk_to_npc", "value": "mage_apprentice"}},
                ],
                "rewards": {"xp": 1250, "gold": 490, "items": ["leather_cap"], "reputation": {"stormwind_guard": 490}},
                "dialogue": {"accept": "\"More research needed! Study these magical threats.\"", "decline": "\"I understand. Research is complex.\"", "progress_1": "\"Good data! Keep going.\"", "progress_2": "\"Excellent! The patterns are clear.\"", "completion": "\"Brilliant research! Here's your reward.\""},
            },
            {
                "id": "apprentice_quest_3",
                "name": "Comprehensive Study",
                "description": "Conduct a comprehensive study of all magical threats in Elwynn Forest.",
                "level_req": 8,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 13 enemies in Elwynn Forest", "hint": "Study all magical threats in the forest.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 13}},
                    {"step": 2, "objective": "Return to Mage Apprentice", "hint": "Use /interact apprentice to report back.", "completion_check": {"type": "talk_to_npc", "value": "mage_apprentice"}},
                ],
                "rewards": {"xp": 2600, "gold": 1000, "items": ["iron_sword"], "reputation": {"stormwind_guard": 900}},
                "dialogue": {"accept": "\"A comprehensive study! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive research.\"", "progress_1": "\"Keep studying! The data is valuable.\"", "completion": "\"Incredible research! The forest is well documented now.\""},
            },
            {
                "id": "apprentice_quest_4",
                "name": "The Arcane Boss",
                "description": "Face the ultimate magical threat: defeat the Spider Queen.",
                "level_req": 10,
                "steps": [
                    {"step": 1, "objective": "Defeat 11 enemies in Elwynn Forest", "hint": "Prepare by studying regular creatures first.", "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 11}},
                    {"step": 2, "objective": "Defeat the Spider Queen", "hint": "The Spider Queen is the ultimate magical boss. Use /fight to challenge her.", "completion_check": {"type": "kill_enemy", "value": "spider_queen", "count": 1}},
                    {"step": 3, "objective": "Return to Mage Apprentice", "hint": "Use /interact apprentice to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "mage_apprentice"}},
                ],
                "rewards": {"xp": 3800, "gold": 1500, "items": ["iron_sword", "leather_cap"], "reputation": {"stormwind_guard": 1300}},
                "dialogue": {"accept": "\"The Spider Queen is the ultimate magical threat! Defeat her!\"", "decline": "\"I understand. The Spider Queen is dangerous.\"", "progress_1": "\"Good preparation! Now face the Spider Queen.\"", "progress_2": "\"The Spider Queen is defeated! Return for your reward.\"", "completion": "\"Legendary research! You've defeated the ultimate magical threat. Here's a worthy reward.\""},
            },
        ],
    },
    
    # ── New NPCs for Dun Morogh (6 additional) ───────────────────────────────
    "miner_ironforge": {
        "name": "Miner Ironforge",
        "title": "⛏️ Prospector",
        "discovery_hint": "A grizzled dwarf miner examines ore samples near a cave entrance.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.14,
        "faction": "dwarven_explorers",
        "introduction": {
            "text": (
                "The miner looks up from his ore samples with a gruff expression.\n\n"
                "\"Aye, another adventurer! I'm Miner Ironforge, and I know these mountains.\n"
                "The troggs and other beasts are making mining dangerous.\n\n"
                "Help me clear out the threats, and I'll share some of my findings.\""
            ),
        },
        "quests": [
            {
                "id": "ironforge_quest_1",
                "name": "Mining Safety",
                "description": "Help secure the mining areas by defeating threats.",
                "level_req": 2,
                "steps": [
                    {"step": 1, "objective": "Defeat 4 Troggs", "hint": "Troggs threaten the mines.", "completion_check": {"type": "kill_enemy", "value": "trogg", "count": 4}},
                    {"step": 2, "objective": "Return to Miner Ironforge", "hint": "Use /interact ironforge to report back.", "completion_check": {"type": "talk_to_npc", "value": "miner_ironforge"}},
                ],
                "rewards": {"xp": 900, "gold": 350, "items": ["frost_resist_potion"], "reputation": {"dwarven_explorers": 350}},
                "dialogue": {"accept": "\"Good! Help me secure the mines.\"", "decline": "\"I understand. Mining is dangerous.\"", "progress_1": "\"Keep going! The mines need securing.\"", "completion": "\"Excellent! The mines are safer. Here's your reward.\""},
            },
            {
                "id": "ironforge_quest_2",
                "name": "Cave Threats",
                "description": "Clear out the threats in the mining caves.",
                "level_req": 4,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Cave Bats", "hint": "Bats infest the caves.", "completion_check": {"type": "kill_enemy", "value": "cave_bat", "count": 5}},
                    {"step": 2, "objective": "Defeat 3 Troggs", "hint": "Troggs guard the deeper caves.", "completion_check": {"type": "kill_enemy", "value": "trogg", "count": 3}},
                    {"step": 3, "objective": "Return to Miner Ironforge", "hint": "Use /interact ironforge to report back.", "completion_check": {"type": "talk_to_npc", "value": "miner_ironforge"}},
                ],
                "rewards": {"xp": 1300, "gold": 500, "items": ["chain_coif"], "reputation": {"dwarven_explorers": 500}},
                "dialogue": {"accept": "\"The caves are dangerous! Clear them out.\"", "decline": "\"I understand. Caves are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The caves are getting safer.\"", "completion": "\"Wonderful! The caves are secure. Here's your reward.\""},
            },
            {
                "id": "ironforge_quest_3",
                "name": "Mountain Security",
                "description": "Secure all mining operations by clearing threats throughout Dun Morogh.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 11 enemies in Dun Morogh", "hint": "Clear all threats to mining operations.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 11}},
                    {"step": 2, "objective": "Return to Miner Ironforge", "hint": "Use /interact ironforge to report back.", "completion_check": {"type": "talk_to_npc", "value": "miner_ironforge"}},
                ],
                "rewards": {"xp": 2200, "gold": 850, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 800}},
                "dialogue": {"accept": "\"Secure all mines! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The mines need complete security.\"", "completion": "\"Incredible! All mines are secure now.\""},
            },
            {
                "id": "ironforge_quest_4",
                "name": "The Trogg Overlord",
                "description": "Defeat the Trogg Overlord that controls the deepest mines.",
                "level_req": 9,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 enemies in Dun Morogh", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 9}},
                    {"step": 2, "objective": "Defeat the Trogg Overlord", "hint": "The Overlord is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "trogg_overlord", "count": 1}},
                    {"step": 3, "objective": "Return to Miner Ironforge", "hint": "Use /interact ironforge to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "miner_ironforge"}},
                ],
                "rewards": {"xp": 3200, "gold": 1200, "items": ["dwarven_axe", "chain_coif"], "reputation": {"dwarven_explorers": 1100}},
                "dialogue": {"accept": "\"The Overlord is the ultimate threat! Defeat him!\"", "decline": "\"I understand. The Overlord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Overlord.\"", "progress_2": "\"The Overlord is defeated! Return for your reward.\"", "completion": "\"Legendary! You've secured the mines permanently. Here's a worthy reward.\""},
            },
        ],
    },
    
    "warrior_grimbeard": {
        "name": "Warrior Grimbeard",
        "title": "🪓 Clan Warrior",
        "discovery_hint": "A battle-scarred dwarf warrior sharpens his axe by a fire.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.16,
        "faction": "dwarven_explorers",
        "introduction": {
            "text": (
                "The warrior looks up from sharpening his axe with a fierce grin.\n\n"
                "\"Aye, another fighter! I'm Warrior Grimbeard, and I've seen many battles.\n"
                "The frostmane trolls and other threats need dealing with.\n\n"
                "If you're ready for a real fight, I have several challenges for you.\""
            ),
        },
        "quests": [
            {
                "id": "grimbeard_quest_1",
                "name": "First Battle",
                "description": "Prove yourself in your first battle with Warrior Grimbeard.",
                "level_req": 2,
                "steps": [
                    {"step": 1, "objective": "Defeat 4 Frostmane Trolls", "hint": "Trolls are aggressive fighters.", "completion_check": {"type": "kill_enemy", "value": "frostmane_troll", "count": 4}},
                    {"step": 2, "objective": "Return to Warrior Grimbeard", "hint": "Use /interact grimbeard to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_grimbeard"}},
                ],
                "rewards": {"xp": 950, "gold": 370, "items": ["frost_resist_potion"], "reputation": {"dwarven_explorers": 370}},
                "dialogue": {"accept": "\"Good! Let's see what you can do in battle.\"", "decline": "\"I understand. Battle takes courage.\"", "progress_1": "\"Keep fighting! You're doing well.\"", "completion": "\"Excellent battle! Here's your reward.\""},
            },
            {
                "id": "grimbeard_quest_2",
                "name": "Dual Threats",
                "description": "Face multiple types of dangerous enemies.",
                "level_req": 4,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Frostmane Trolls", "hint": "Fight the trolls.", "completion_check": {"type": "kill_enemy", "value": "frostmane_troll", "count": 5}},
                    {"step": 2, "objective": "Defeat 3 Frostmane Shamans", "hint": "Now fight the shamans.", "completion_check": {"type": "kill_enemy", "value": "frostmane_shaman", "count": 3}},
                    {"step": 3, "objective": "Return to Warrior Grimbeard", "hint": "Use /interact grimbeard to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_grimbeard"}},
                ],
                "rewards": {"xp": 1400, "gold": 540, "items": ["chain_coif"], "reputation": {"dwarven_explorers": 540}},
                "dialogue": {"accept": "\"This is more challenging. Face both threats.\"", "decline": "\"I understand. Multiple enemies are difficult.\"", "progress_1": "\"Good fighting! Keep going.\"", "progress_2": "\"Excellent! You're a skilled warrior.\"", "completion": "\"Outstanding battle! Here's your reward.\""},
            },
            {
                "id": "grimbeard_quest_3",
                "name": "Mountain Conquest",
                "description": "Conquer all threats throughout Dun Morogh.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in Dun Morogh", "hint": "Fight all threats in the mountains.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 12}},
                    {"step": 2, "objective": "Return to Warrior Grimbeard", "hint": "Use /interact grimbeard to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_grimbeard"}},
                ],
                "rewards": {"xp": 2400, "gold": 920, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 880}},
                "dialogue": {"accept": "\"Conquer the mountains! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive fighting.\"", "progress_1": "\"Keep fighting! The mountains need conquering.\"", "completion": "\"Incredible conquest! The mountains are yours.\""},
            },
            {
                "id": "grimbeard_quest_4",
                "name": "The Frostmane Headhunter",
                "description": "Face the ultimate challenge: defeat the Frostmane Headhunter.",
                "level_req": 9,
                "steps": [
                    {"step": 1, "objective": "Defeat 10 enemies in Dun Morogh", "hint": "Prepare by fighting regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 10}},
                    {"step": 2, "objective": "Defeat the Frostmane Headhunter", "hint": "The Headhunter is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "frostmane_headhunter", "count": 1}},
                    {"step": 3, "objective": "Return to Warrior Grimbeard", "hint": "Use /interact grimbeard to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "warrior_grimbeard"}},
                ],
                "rewards": {"xp": 3400, "gold": 1300, "items": ["dwarven_axe", "chain_coif"], "reputation": {"dwarven_explorers": 1200}},
                "dialogue": {"accept": "\"The Headhunter is the ultimate challenge! Defeat him!\"", "decline": "\"I understand. The Headhunter is dangerous.\"", "progress_1": "\"Good preparation! Now face the Headhunter.\"", "progress_2": "\"The Headhunter is defeated! Return for your reward.\"", "completion": "\"Legendary battle! You've proven yourself a true warrior. Here's a worthy reward.\""},
            },
        ],
    },
    
    "shaman_iceheart": {
        "name": "Shaman Iceheart",
        "title": "❄️ Frost Shaman",
        "discovery_hint": "A shaman chants ancient words while standing near ice formations.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.15,
        "faction": "dwarven_explorers",
        "introduction": {
            "text": (
                "The shaman finishes a chant and turns to you with wise eyes.\n\n"
                "\"The spirits speak, adventurer. I am Shaman Iceheart, keeper of the old ways.\n"
                "The balance of the mountains is disturbed by dark forces.\n\n"
                "Help me restore the balance, and the spirits will reward you.\""
            ),
        },
        "quests": [
            {
                "id": "iceheart_quest_1",
                "name": "Spirit Balance",
                "description": "Help the shaman restore balance by defeating dark forces.",
                "level_req": 3,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Frozen Wraiths", "hint": "Wraiths disturb the spirit balance.", "completion_check": {"type": "kill_enemy", "value": "frozen_wraith", "count": 5}},
                    {"step": 2, "objective": "Return to Shaman Iceheart", "hint": "Use /interact iceheart to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_iceheart"}},
                ],
                "rewards": {"xp": 1000, "gold": 390, "items": ["frost_resist_potion"], "reputation": {"dwarven_explorers": 400}},
                "dialogue": {"accept": "\"The spirits guide you. Restore the balance.\"", "decline": "\"I understand. Balance takes time.\"", "progress_1": "\"Keep fighting! The balance is being restored.\"", "completion": "\"Blessings! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "iceheart_quest_2",
                "name": "Elemental Threats",
                "description": "Deal with the elemental threats disturbing the balance.",
                "level_req": 5,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Ice Elementals", "hint": "Elementals disrupt the natural balance.", "completion_check": {"type": "kill_enemy", "value": "ice_elemental", "count": 6}},
                    {"step": 2, "objective": "Defeat 4 Frozen Wraiths", "hint": "Wraiths are dark spirits.", "completion_check": {"type": "kill_enemy", "value": "frozen_wraith", "count": 4}},
                    {"step": 3, "objective": "Return to Shaman Iceheart", "hint": "Use /interact iceheart to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_iceheart"}},
                ],
                "rewards": {"xp": 1500, "gold": 580, "items": ["chain_coif"], "reputation": {"dwarven_explorers": 580}},
                "dialogue": {"accept": "\"More threats! Restore the balance.\"", "decline": "\"I understand. Balance is complex.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The balance is being restored.\"", "completion": "\"Wonderful! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "iceheart_quest_3",
                "name": "Mountain Purification",
                "description": "Purify the entire mountain by clearing all dark forces.",
                "level_req": 8,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 13 enemies in Dun Morogh", "hint": "Clear all dark forces from the mountains.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 13}},
                    {"step": 2, "objective": "Return to Shaman Iceheart", "hint": "Use /interact iceheart to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_iceheart"}},
                ],
                "rewards": {"xp": 2600, "gold": 1000, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 950}},
                "dialogue": {"accept": "\"Purify the mountains! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The mountains need purification.\"", "completion": "\"Incredible! The mountains are purified. The spirits are pleased.\""},
            },
            {
                "id": "iceheart_quest_4",
                "name": "The Ice Lord",
                "description": "Face the ultimate dark force: defeat the Ice Lord.",
                "level_req": 10,
                "steps": [
                    {"step": 1, "objective": "Defeat 11 enemies in Dun Morogh", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 11}},
                    {"step": 2, "objective": "Defeat the Ice Lord", "hint": "The Ice Lord is the ultimate boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "ice_lord", "count": 1}},
                    {"step": 3, "objective": "Return to Shaman Iceheart", "hint": "Use /interact iceheart to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "shaman_iceheart"}},
                ],
                "rewards": {"xp": 3600, "gold": 1400, "items": ["dwarven_axe", "chain_coif"], "reputation": {"dwarven_explorers": 1300}},
                "dialogue": {"accept": "\"The Ice Lord is the ultimate dark force! Defeat him!\"", "decline": "\"I understand. The Ice Lord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Ice Lord.\"", "progress_2": "\"The Ice Lord is defeated! The balance is restored! Return for your reward.\"", "completion": "\"Legendary! You've restored the ultimate balance. The spirits reward you.\""},
            },
        ],
    },
    
    "explorer_brawnbelly": {
        "name": "Explorer Brawnbelly",
        "title": "🗺️ Cartographer",
        "discovery_hint": "A dwarf with maps spread out studies the frozen landscape.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.14,
        "faction": "dwarven_explorers",
        "introduction": {
            "text": (
                "The cartographer looks up from his maps with excitement.\n\n"
                "\"Ah! Another explorer! I'm Explorer Brawnbelly, and I map these mountains.\n"
                "I've been documenting all the threats and landmarks.\n\n"
                "If you can help me clear out the dangers while I map,\n"
                "I'll share my findings and reward you.\""
            ),
        },
        "quests": [
            {
                "id": "brawnbelly_quest_1",
                "name": "Mapping Safety",
                "description": "Help the cartographer map safely by clearing threats.",
                "level_req": 2,
                "steps": [
                    {"step": 1, "objective": "Defeat 4 Snow Leopards", "hint": "Leopards threaten the mapping routes.", "completion_check": {"type": "kill_enemy", "value": "snow_leopard", "count": 4}},
                    {"step": 2, "objective": "Return to Explorer Brawnbelly", "hint": "Use /interact brawnbelly to report back.", "completion_check": {"type": "talk_to_npc", "value": "explorer_brawnbelly"}},
                ],
                "rewards": {"xp": 920, "gold": 360, "items": ["frost_resist_potion"], "reputation": {"dwarven_explorers": 360}},
                "dialogue": {"accept": "\"Good! Help me map safely.\"", "decline": "\"I understand. Mapping takes time.\"", "progress_1": "\"Keep going! The maps are coming along.\"", "completion": "\"Excellent! The maps are safer. Here's your reward.\""},
            },
            {
                "id": "brawnbelly_quest_2",
                "name": "Terrain Threats",
                "description": "Clear out threats in different terrain types.",
                "level_req": 4,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Winter Wolves", "hint": "Wolves roam the frozen terrain.", "completion_check": {"type": "kill_enemy", "value": "winter_wolf", "count": 5}},
                    {"step": 2, "objective": "Defeat 3 Ice Claw Bears", "hint": "Bears guard the mountain passes.", "completion_check": {"type": "kill_enemy", "value": "ice_claw_bear", "count": 3}},
                    {"step": 3, "objective": "Return to Explorer Brawnbelly", "hint": "Use /interact brawnbelly to report back.", "completion_check": {"type": "talk_to_npc", "value": "explorer_brawnbelly"}},
                ],
                "rewards": {"xp": 1350, "gold": 520, "items": ["chain_coif"], "reputation": {"dwarven_explorers": 520}},
                "dialogue": {"accept": "\"The terrain is dangerous! Clear it out.\"", "decline": "\"I understand. Terrain is treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The terrain is getting safer.\"", "completion": "\"Wonderful! The terrain is mapped and secure. Here's your reward.\""},
            },
            {
                "id": "brawnbelly_quest_3",
                "name": "Complete Mapping",
                "description": "Complete the mapping by clearing all threats throughout Dun Morogh.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in Dun Morogh", "hint": "Clear all threats to complete the mapping.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 12}},
                    {"step": 2, "objective": "Return to Explorer Brawnbelly", "hint": "Use /interact brawnbelly to report back.", "completion_check": {"type": "talk_to_npc", "value": "explorer_brawnbelly"}},
                ],
                "rewards": {"xp": 2300, "gold": 880, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 860}},
                "dialogue": {"accept": "\"Complete the mapping! Finish this within 48 hours!\"", "decline": "\"I understand. This is extensive mapping.\"", "progress_1": "\"Keep fighting! The mapping is progressing.\"", "completion": "\"Incredible! The mapping is complete. All threats are documented.\""},
            },
            {
                "id": "brawnbelly_quest_4",
                "name": "The Ancient Frost Giant",
                "description": "Face the ultimate challenge: map the area guarded by the Ancient Frost Giant.",
                "level_req": 9,
                "steps": [
                    {"step": 1, "objective": "Defeat 10 enemies in Dun Morogh", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 10}},
                    {"step": 2, "objective": "Defeat the Ancient Frost Giant", "hint": "The Giant guards the final mapping area. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "ancient_frost_giant", "count": 1}},
                    {"step": 3, "objective": "Return to Explorer Brawnbelly", "hint": "Use /interact brawnbelly to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "explorer_brawnbelly"}},
                ],
                "rewards": {"xp": 3300, "gold": 1250, "items": ["dwarven_axe", "chain_coif"], "reputation": {"dwarven_explorers": 1150}},
                "dialogue": {"accept": "\"The Ancient Frost Giant guards the final area! Defeat him!\"", "decline": "\"I understand. The Giant is dangerous.\"", "progress_1": "\"Good preparation! Now face the Giant.\"", "progress_2": "\"The Giant is defeated! The mapping is complete! Return for your reward.\"", "completion": "\"Legendary! The complete map is finished. Here's a worthy reward.\""},
            },
        ],
    },
    
    "blacksmith_steelhammer": {
        "name": "Blacksmith Steelhammer",
        "title": "🔨 Master Smith",
        "discovery_hint": "A blacksmith works at a portable forge, hammering glowing metal.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.15,
        "faction": "dwarven_explorers",
        "introduction": {
            "text": (
                "The blacksmith looks up from his forge with a friendly smile.\n\n"
                "\"Aye, another customer! I'm Blacksmith Steelhammer, master of the forge.\n"
                "I need rare materials from dangerous creatures to craft better weapons.\n\n"
                "Help me gather materials, and I'll craft something special for you.\""
            ),
        },
        "quests": [
            {
                "id": "steelhammer_quest_1",
                "name": "Material Gathering",
                "description": "Help the blacksmith gather materials from defeated enemies.",
                "level_req": 3,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Ice Claw Bears", "hint": "Bears provide valuable materials.", "completion_check": {"type": "kill_enemy", "value": "ice_claw_bear", "count": 5}},
                    {"step": 2, "objective": "Return to Blacksmith Steelhammer", "hint": "Use /interact steelhammer to deliver materials.", "completion_check": {"type": "talk_to_npc", "value": "blacksmith_steelhammer"}},
                ],
                "rewards": {"xp": 1050, "gold": 410, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 410}},
                "dialogue": {"accept": "\"Good! Help me gather materials.\"", "decline": "\"I understand. Materials are valuable.\"", "progress_1": "\"Keep gathering! The materials are useful.\"", "completion": "\"Excellent materials! Here's a crafted reward.\""},
            },
            {
                "id": "steelhammer_quest_2",
                "name": "Rare Components",
                "description": "Gather rare components from multiple enemy types.",
                "level_req": 5,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Troggs", "hint": "Troggs have rare components.", "completion_check": {"type": "kill_enemy", "value": "trogg", "count": 6}},
                    {"step": 2, "objective": "Defeat 4 Frostmane Trolls", "hint": "Trolls provide unique materials.", "completion_check": {"type": "kill_enemy", "value": "frostmane_troll", "count": 4}},
                    {"step": 3, "objective": "Return to Blacksmith Steelhammer", "hint": "Use /interact steelhammer to deliver materials.", "completion_check": {"type": "talk_to_npc", "value": "blacksmith_steelhammer"}},
                ],
                "rewards": {"xp": 1550, "gold": 600, "items": ["chain_coif"], "reputation": {"dwarven_explorers": 600}},
                "dialogue": {"accept": "\"Rare components needed! Gather them for me.\"", "decline": "\"I understand. Rare components are hard to find.\"", "progress_1": "\"Good gathering! Keep going.\"", "progress_2": "\"Excellent! The components are perfect.\"", "completion": "\"Wonderful components! Here's a crafted reward.\""},
            },
            {
                "id": "steelhammer_quest_3",
                "name": "Master Materials",
                "description": "Gather master-level materials from throughout Dun Morogh.",
                "level_req": 8,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 13 enemies in Dun Morogh", "hint": "Gather materials from all enemies.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 13}},
                    {"step": 2, "objective": "Return to Blacksmith Steelhammer", "hint": "Use /interact steelhammer to deliver materials.", "completion_check": {"type": "talk_to_npc", "value": "blacksmith_steelhammer"}},
                ],
                "rewards": {"xp": 2700, "gold": 1050, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 1000}},
                "dialogue": {"accept": "\"Master materials needed! Gather them within 48 hours!\"", "decline": "\"I understand. Master materials are rare.\"", "progress_1": "\"Keep gathering! The materials are valuable.\"", "completion": "\"Incredible materials! I can craft something legendary now.\""},
            },
            {
                "id": "steelhammer_quest_4",
                "name": "Legendary Components",
                "description": "Gather the ultimate materials from the Ancient Frost Giant.",
                "level_req": 10,
                "steps": [
                    {"step": 1, "objective": "Defeat 11 enemies in Dun Morogh", "hint": "Prepare by gathering regular materials first.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 11}},
                    {"step": 2, "objective": "Defeat the Ancient Frost Giant", "hint": "The Giant has legendary components. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "ancient_frost_giant", "count": 1}},
                    {"step": 3, "objective": "Return to Blacksmith Steelhammer", "hint": "Use /interact steelhammer to claim your legendary crafted reward.", "completion_check": {"type": "talk_to_npc", "value": "blacksmith_steelhammer"}},
                ],
                "rewards": {"xp": 3700, "gold": 1450, "items": ["dwarven_axe", "chain_coif"], "reputation": {"dwarven_explorers": 1400}},
                "dialogue": {"accept": "\"Legendary components! Gather them from the Giant!\"", "decline": "\"I understand. The Giant is dangerous.\"", "progress_1": "\"Good preparation! Now gather from the Giant.\"", "progress_2": "\"The Giant is defeated! Legendary components gathered! Return for your reward.\"", "completion": "\"Legendary! I've crafted the ultimate weapon. Here's your reward.\""},
            },
        ],
    },
    
    "ranger_frostwind": {
        "name": "Ranger Frostwind",
        "title": "🏹 Mountain Guide",
        "discovery_hint": "A ranger with a bow watches the mountain passes carefully.",
        "zones": ["dun_morogh"],
        "discovery_chance": 0.16,
        "faction": "dwarven_explorers",
        "introduction": {
            "text": (
                "The ranger lowers his bow and greets you with a nod.\n\n"
                "\"Well met, traveler! I'm Ranger Frostwind, guide of these mountains.\n"
                "I know every pass and every threat in these frozen peaks.\n\n"
                "If you're willing to help clear the paths, I'll guide you to great rewards.\""
            ),
        },
        "quests": [
            {
                "id": "frostwind_quest_1",
                "name": "Path Clearing",
                "description": "Help the ranger clear the mountain paths of threats.",
                "level_req": 2,
                "steps": [
                    {"step": 1, "objective": "Defeat 4 Winter Wolves", "hint": "Wolves block the mountain paths.", "completion_check": {"type": "kill_enemy", "value": "winter_wolf", "count": 4}},
                    {"step": 2, "objective": "Return to Ranger Frostwind", "hint": "Use /interact frostwind to report back.", "completion_check": {"type": "talk_to_npc", "value": "ranger_frostwind"}},
                ],
                "rewards": {"xp": 940, "gold": 370, "items": ["frost_resist_potion"], "reputation": {"dwarven_explorers": 370}},
                "dialogue": {"accept": "\"Good! Help me clear the paths.\"", "decline": "\"I understand. Paths are dangerous.\"", "progress_1": "\"Keep going! The paths need clearing.\"", "completion": "\"Excellent! The paths are clear. Here's your reward.\""},
            },
            {
                "id": "frostwind_quest_2",
                "name": "Mountain Passes",
                "description": "Secure multiple mountain passes by clearing threats.",
                "level_req": 4,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Snow Leopards", "hint": "Leopards guard the passes.", "completion_check": {"type": "kill_enemy", "value": "snow_leopard", "count": 5}},
                    {"step": 2, "objective": "Defeat 3 Winter Wolves", "hint": "Wolves patrol the passes.", "completion_check": {"type": "kill_enemy", "value": "winter_wolf", "count": 3}},
                    {"step": 3, "objective": "Return to Ranger Frostwind", "hint": "Use /interact frostwind to report back.", "completion_check": {"type": "talk_to_npc", "value": "ranger_frostwind"}},
                ],
                "rewards": {"xp": 1380, "gold": 530, "items": ["chain_coif"], "reputation": {"dwarven_explorers": 530}},
                "dialogue": {"accept": "\"The passes are dangerous! Secure them.\"", "decline": "\"I understand. Passes are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The passes are getting safer.\"", "completion": "\"Wonderful! All passes are secure. Here's your reward.\""},
            },
            {
                "id": "frostwind_quest_3",
                "name": "Complete Guide",
                "description": "Complete the guide by clearing all threats throughout Dun Morogh.",
                "level_req": 7,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in Dun Morogh", "hint": "Clear all threats to complete the guide.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 12}},
                    {"step": 2, "objective": "Return to Ranger Frostwind", "hint": "Use /interact frostwind to report back.", "completion_check": {"type": "talk_to_npc", "value": "ranger_frostwind"}},
                ],
                "rewards": {"xp": 2400, "gold": 920, "items": ["dwarven_axe"], "reputation": {"dwarven_explorers": 880}},
                "dialogue": {"accept": "\"Complete the guide! Finish this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The guide is progressing.\"", "completion": "\"Incredible! The complete guide is finished. All paths are documented.\""},
            },
            {
                "id": "frostwind_quest_4",
                "name": "The Ultimate Pass",
                "description": "Face the ultimate challenge: clear the pass guarded by the Ice Lord.",
                "level_req": 9,
                "steps": [
                    {"step": 1, "objective": "Defeat 10 enemies in Dun Morogh", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 10}},
                    {"step": 2, "objective": "Defeat the Ice Lord", "hint": "The Ice Lord guards the ultimate pass. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "ice_lord", "count": 1}},
                    {"step": 3, "objective": "Return to Ranger Frostwind", "hint": "Use /interact frostwind to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "ranger_frostwind"}},
                ],
                "rewards": {"xp": 3400, "gold": 1300, "items": ["dwarven_axe", "chain_coif"], "reputation": {"dwarven_explorers": 1200}},
                "dialogue": {"accept": "\"The Ice Lord guards the ultimate pass! Defeat him!\"", "decline": "\"I understand. The Ice Lord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Ice Lord.\"", "progress_2": "\"The Ice Lord is defeated! The ultimate pass is clear! Return for your reward.\"", "completion": "\"Legendary! You've cleared the ultimate pass. Here's a worthy reward.\""},
            },
        ],
    },
    
    # ── New NPCs for The Barrens (6 additional) ──────────────────────────────
    "hunter_razorwind": {
        "name": "Hunter Razorwind",
        "title": "🏹 Desert Tracker",
        "discovery_hint": "A skilled hunter tracks prey across the scorched earth.",
        "zones": ["barrens"],
        "discovery_chance": 0.14,
        "faction": "trade_coalition",
        "introduction": {
            "text": (
                "The hunter looks up from tracking with a confident smile.\n\n"
                "\"Well met, traveler! I'm Hunter Razorwind, master tracker of the desert.\n"
                "I know every creature and every threat in this wasteland.\n\n"
                "If you're ready for some real hunting, I have several targets for you.\""
            ),
        },
        "quests": [
            {
                "id": "razorwind_quest_1",
                "name": "Desert Hunt",
                "description": "Join Hunter Razorwind on a desert hunt.",
                "level_req": 11,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Plainstriders", "hint": "Plainstriders are common desert prey.", "completion_check": {"type": "kill_enemy", "value": "plainstrider", "count": 5}},
                    {"step": 2, "objective": "Return to Hunter Razorwind", "hint": "Use /interact razorwind to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_razorwind"}},
                ],
                "rewards": {"xp": 3500, "gold": 1700, "items": ["stamina_draught"], "reputation": {"trade_coalition": 600}},
                "dialogue": {"accept": "\"Good! Let's see what you can track in the desert.\"", "decline": "\"I understand. Desert hunting takes skill.\"", "progress_1": "\"Keep tracking! You're doing well.\"", "completion": "\"Excellent tracking! Here's your reward.\""},
            },
            {
                "id": "razorwind_quest_2",
                "name": "Multiple Prey",
                "description": "Hunt multiple types of desert creatures.",
                "level_req": 14,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Sunscale Raptors", "hint": "Track and defeat raptors.", "completion_check": {"type": "kill_enemy", "value": "sunscale_raptor", "count": 6}},
                    {"step": 2, "objective": "Defeat 4 Barrens Scorpions", "hint": "Now track and defeat scorpions.", "completion_check": {"type": "kill_enemy", "value": "barrens_scorpion", "count": 4}},
                    {"step": 3, "objective": "Return to Hunter Razorwind", "hint": "Use /interact razorwind to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_razorwind"}},
                ],
                "rewards": {"xp": 4500, "gold": 2200, "items": ["bone_club"], "reputation": {"trade_coalition": 800}},
                "dialogue": {"accept": "\"This is more challenging. Track both prey types.\"", "decline": "\"I understand. Multiple prey is difficult.\"", "progress_1": "\"Good tracking! Keep going.\"", "progress_2": "\"Excellent! You're a skilled tracker.\"", "completion": "\"Outstanding tracking! Here's your reward.\""},
            },
            {
                "id": "razorwind_quest_3",
                "name": "Desert Sweep",
                "description": "Conduct a comprehensive hunt throughout The Barrens.",
                "level_req": 19,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in The Barrens", "hint": "Hunt any creatures throughout the desert.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 15}},
                    {"step": 2, "objective": "Return to Hunter Razorwind", "hint": "Use /interact razorwind to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_razorwind"}},
                ],
                "rewards": {"xp": 6000, "gold": 3000, "items": ["raptor_hide_vest"], "reputation": {"trade_coalition": 1100}},
                "dialogue": {"accept": "\"A comprehensive hunt! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive hunting.\"", "progress_1": "\"Keep hunting! The desert needs clearing.\"", "completion": "\"Incredible hunting! The desert is well tracked now.\""},
            },
            {
                "id": "razorwind_quest_4",
                "name": "The Thunderhawk Alpha",
                "description": "Face the ultimate challenge: hunt down the Thunderhawk Alpha.",
                "level_req": 23,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in The Barrens", "hint": "Prepare by hunting regular creatures first.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 12}},
                    {"step": 2, "objective": "Defeat the Thunderhawk Alpha", "hint": "The Alpha is the ultimate prey. Use /fight to challenge it.", "completion_check": {"type": "kill_enemy", "value": "thunderhawk_alpha", "count": 1}},
                    {"step": 3, "objective": "Return to Hunter Razorwind", "hint": "Use /interact razorwind to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "hunter_razorwind"}},
                ],
                "rewards": {"xp": 8000, "gold": 4000, "items": ["raptor_hide_vest", "stamina_draught"], "reputation": {"trade_coalition": 1500}},
                "dialogue": {"accept": "\"The Thunderhawk Alpha is the ultimate prey! Hunt it down!\"", "decline": "\"I understand. The Alpha is dangerous.\"", "progress_1": "\"Good preparation! Now hunt the Alpha.\"", "progress_2": "\"The Alpha is defeated! Return for your reward.\"", "completion": "\"Legendary hunting! You've taken down the ultimate prey. Here's a worthy reward.\""},
            },
        ],
    },
    
    "shaman_thunderhoof": {
        "name": "Shaman Thunderhoof",
        "title": "⚡ Tribal Shaman",
        "discovery_hint": "A shaman performs rituals near ancient totems.",
        "zones": ["barrens"],
        "discovery_chance": 0.15,
        "faction": "trade_coalition",
        "introduction": {
            "text": (
                "The shaman finishes a ritual and turns to you with wise eyes.\n\n"
                "\"The spirits speak, traveler. I am Shaman Thunderhoof, keeper of the old ways.\n"
                "The balance of the desert is disturbed by dark forces.\n\n"
                "Help me restore the balance, and the spirits will reward you.\""
            ),
        },
        "quests": [
            {
                "id": "thunderhoof_quest_1",
                "name": "Spirit Balance",
                "description": "Help the shaman restore balance by defeating dark forces.",
                "level_req": 12,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Zhevras", "hint": "Zhevras disturb the spirit balance.", "completion_check": {"type": "kill_enemy", "value": "zhevra", "count": 6}},
                    {"step": 2, "objective": "Return to Shaman Thunderhoof", "hint": "Use /interact thunderhoof to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_thunderhoof"}},
                ],
                "rewards": {"xp": 3800, "gold": 1900, "items": ["stamina_draught"], "reputation": {"trade_coalition": 650}},
                "dialogue": {"accept": "\"The spirits guide you. Restore the balance.\"", "decline": "\"I understand. Balance takes time.\"", "progress_1": "\"Keep fighting! The balance is being restored.\"", "completion": "\"Blessings! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "thunderhoof_quest_2",
                "name": "Desert Threats",
                "description": "Deal with the threats disturbing the desert balance.",
                "level_req": 15,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Thunder Lizards", "hint": "Lizards disrupt the natural balance.", "completion_check": {"type": "kill_enemy", "value": "thunder_lizard", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Wind Sweepers", "hint": "Wind sweepers are elemental threats.", "completion_check": {"type": "kill_enemy", "value": "wind_sweeper", "count": 5}},
                    {"step": 3, "objective": "Return to Shaman Thunderhoof", "hint": "Use /interact thunderhoof to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_thunderhoof"}},
                ],
                "rewards": {"xp": 5000, "gold": 2500, "items": ["bone_club"], "reputation": {"trade_coalition": 900}},
                "dialogue": {"accept": "\"More threats! Restore the balance.\"", "decline": "\"I understand. Balance is complex.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The balance is being restored.\"", "completion": "\"Wonderful! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "thunderhoof_quest_3",
                "name": "Desert Purification",
                "description": "Purify the entire desert by clearing all dark forces.",
                "level_req": 20,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 16 enemies in The Barrens", "hint": "Clear all dark forces from the desert.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 16}},
                    {"step": 2, "objective": "Return to Shaman Thunderhoof", "hint": "Use /interact thunderhoof to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_thunderhoof"}},
                ],
                "rewards": {"xp": 6500, "gold": 3200, "items": ["raptor_hide_vest"], "reputation": {"trade_coalition": 1200}},
                "dialogue": {"accept": "\"Purify the desert! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The desert needs purification.\"", "completion": "\"Incredible! The desert is purified. The spirits are pleased.\""},
            },
            {
                "id": "thunderhoof_quest_4",
                "name": "The Barrens Overlord",
                "description": "Face the ultimate dark force: defeat the Barrens Overlord.",
                "level_req": 24,
                "steps": [
                    {"step": 1, "objective": "Defeat 13 enemies in The Barrens", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 13}},
                    {"step": 2, "objective": "Defeat the Barrens Overlord", "hint": "The Overlord is the ultimate boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "barrens_overlord", "count": 1}},
                    {"step": 3, "objective": "Return to Shaman Thunderhoof", "hint": "Use /interact thunderhoof to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "shaman_thunderhoof"}},
                ],
                "rewards": {"xp": 8500, "gold": 4200, "items": ["raptor_hide_vest", "stamina_draught"], "reputation": {"trade_coalition": 1600}},
                "dialogue": {"accept": "\"The Overlord is the ultimate dark force! Defeat him!\"", "decline": "\"I understand. The Overlord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Overlord.\"", "progress_2": "\"The Overlord is defeated! The balance is restored! Return for your reward.\"", "completion": "\"Legendary! You've restored the ultimate balance. The spirits reward you.\""},
            },
        ],
    },
    
    "warrior_bloodfang": {
        "name": "Warrior Bloodfang",
        "title": "⚔️ Tribal Warrior",
        "discovery_hint": "A fierce warrior trains with weapons in the hot sun.",
        "zones": ["barrens"],
        "discovery_chance": 0.16,
        "faction": "trade_coalition",
        "introduction": {
            "text": (
                "The warrior stops training and greets you with a fierce grin.\n\n"
                "\"Well met, fighter! I'm Warrior Bloodfang, and I've seen many battles.\n"
                "The Razormane and other threats need dealing with.\n\n"
                "If you're ready for a real fight, I have several challenges for you.\""
            ),
        },
        "quests": [
            {
                "id": "bloodfang_quest_1",
                "name": "First Battle",
                "description": "Prove yourself in your first battle with Warrior Bloodfang.",
                "level_req": 11,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Razormane Warriors", "hint": "Razormane are aggressive fighters.", "completion_check": {"type": "kill_enemy", "value": "razormane_warrior", "count": 5}},
                    {"step": 2, "objective": "Return to Warrior Bloodfang", "hint": "Use /interact bloodfang to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_bloodfang"}},
                ],
                "rewards": {"xp": 3600, "gold": 1800, "items": ["stamina_draught"], "reputation": {"trade_coalition": 640}},
                "dialogue": {"accept": "\"Good! Let's see what you can do in battle.\"", "decline": "\"I understand. Battle takes courage.\"", "progress_1": "\"Keep fighting! You're doing well.\"", "completion": "\"Excellent battle! Here's your reward.\""},
            },
            {
                "id": "bloodfang_quest_2",
                "name": "Dual Threats",
                "description": "Face multiple types of dangerous enemies.",
                "level_req": 14,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Razormane Warriors", "hint": "Fight the Razormane.", "completion_check": {"type": "kill_enemy", "value": "razormane_warrior", "count": 6}},
                    {"step": 2, "objective": "Defeat 4 Quillboar", "hint": "Now fight the Quillboar.", "completion_check": {"type": "kill_enemy", "value": "quillboar", "count": 4}},
                    {"step": 3, "objective": "Return to Warrior Bloodfang", "hint": "Use /interact bloodfang to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_bloodfang"}},
                ],
                "rewards": {"xp": 4600, "gold": 2300, "items": ["bone_club"], "reputation": {"trade_coalition": 840}},
                "dialogue": {"accept": "\"This is more challenging. Face both threats.\"", "decline": "\"I understand. Multiple enemies are difficult.\"", "progress_1": "\"Good fighting! Keep going.\"", "progress_2": "\"Excellent! You're a skilled warrior.\"", "completion": "\"Outstanding battle! Here's your reward.\""},
            },
            {
                "id": "bloodfang_quest_3",
                "name": "Desert Conquest",
                "description": "Conquer all threats throughout The Barrens.",
                "level_req": 19,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in The Barrens", "hint": "Fight all threats in the desert.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 15}},
                    {"step": 2, "objective": "Return to Warrior Bloodfang", "hint": "Use /interact bloodfang to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_bloodfang"}},
                ],
                "rewards": {"xp": 6100, "gold": 3050, "items": ["raptor_hide_vest"], "reputation": {"trade_coalition": 1120}},
                "dialogue": {"accept": "\"Conquer the desert! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive fighting.\"", "progress_1": "\"Keep fighting! The desert needs conquering.\"", "completion": "\"Incredible conquest! The desert is yours.\""},
            },
            {
                "id": "bloodfang_quest_4",
                "name": "The Razormane Chieftain",
                "description": "Face the ultimate challenge: defeat the Razormane Chieftain.",
                "level_req": 23,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in The Barrens", "hint": "Prepare by fighting regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 12}},
                    {"step": 2, "objective": "Defeat the Razormane Chieftain", "hint": "The Chieftain is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "razormane_chieftain", "count": 1}},
                    {"step": 3, "objective": "Return to Warrior Bloodfang", "hint": "Use /interact bloodfang to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "warrior_bloodfang"}},
                ],
                "rewards": {"xp": 8100, "gold": 4050, "items": ["raptor_hide_vest", "stamina_draught"], "reputation": {"trade_coalition": 1520}},
                "dialogue": {"accept": "\"The Chieftain is the ultimate challenge! Defeat him!\"", "decline": "\"I understand. The Chieftain is dangerous.\"", "progress_1": "\"Good preparation! Now face the Chieftain.\"", "progress_2": "\"The Chieftain is defeated! Return for your reward.\"", "completion": "\"Legendary battle! You've proven yourself a true warrior. Here's a worthy reward.\""},
            },
        ],
    },
    
    "merchant_crossroads": {
        "name": "Merchant Crossroads",
        "title": "💰 Trade Master",
        "discovery_hint": "A merchant sets up a stall at a busy crossroads.",
        "zones": ["barrens"],
        "discovery_chance": 0.14,
        "faction": "trade_coalition",
        "introduction": {
            "text": (
                "The merchant greets you with a business-like smile.\n\n"
                "\"Welcome, traveler! I'm Merchant Crossroads, master of trade.\n"
                "Business has been difficult with all these threats around.\n\n"
                "Help me secure the trade routes, and I'll make it worth your while.\""
            ),
        },
        "quests": [
            {
                "id": "crossroads_quest_1",
                "name": "Trade Route Security",
                "description": "Help secure the trade routes by defeating threats.",
                "level_req": 12,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Barrens Vultures", "hint": "Vultures threaten the trade routes.", "completion_check": {"type": "kill_enemy", "value": "barrens_vulture", "count": 6}},
                    {"step": 2, "objective": "Return to Merchant Crossroads", "hint": "Use /interact crossroads to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_crossroads"}},
                ],
                "rewards": {"xp": 3900, "gold": 1950, "items": ["stamina_draught"], "reputation": {"trade_coalition": 680}},
                "dialogue": {"accept": "\"Good! Help me secure the routes.\"", "decline": "\"I understand. Trade routes are dangerous.\"", "progress_1": "\"Keep going! The routes need securing.\"", "completion": "\"Excellent! The routes are safer. Here's your reward.\""},
            },
            {
                "id": "crossroads_quest_2",
                "name": "Multiple Threats",
                "description": "Deal with multiple threats to the trade routes.",
                "level_req": 15,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Plainstriders", "hint": "Plainstriders block the routes.", "completion_check": {"type": "kill_enemy", "value": "plainstrider", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Barrens Scorpions", "hint": "Scorpions guard the routes.", "completion_check": {"type": "kill_enemy", "value": "barrens_scorpion", "count": 5}},
                    {"step": 3, "objective": "Return to Merchant Crossroads", "hint": "Use /interact crossroads to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_crossroads"}},
                ],
                "rewards": {"xp": 5100, "gold": 2550, "items": ["bone_club"], "reputation": {"trade_coalition": 920}},
                "dialogue": {"accept": "\"The routes are dangerous! Clear them out.\"", "decline": "\"I understand. Routes are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The routes are getting safer.\"", "completion": "\"Wonderful! All routes are secure. Here's your reward.\""},
            },
            {
                "id": "crossroads_quest_3",
                "name": "Complete Security",
                "description": "Secure all trade routes by clearing threats throughout The Barrens.",
                "level_req": 20,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 16 enemies in The Barrens", "hint": "Clear all threats to the trade routes.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 16}},
                    {"step": 2, "objective": "Return to Merchant Crossroads", "hint": "Use /interact crossroads to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_crossroads"}},
                ],
                "rewards": {"xp": 6600, "gold": 3300, "items": ["raptor_hide_vest"], "reputation": {"trade_coalition": 1220}},
                "dialogue": {"accept": "\"Secure all routes! Complete this within 48 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The routes need complete security.\"", "completion": "\"Incredible! All routes are secure now.\""},
            },
            {
                "id": "crossroads_quest_4",
                "name": "The Kolkar Centaur Lord",
                "description": "Defeat the Kolkar Centaur Lord to secure the trade routes permanently.",
                "level_req": 24,
                "steps": [
                    {"step": 1, "objective": "Defeat 13 enemies in The Barrens", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 13}},
                    {"step": 2, "objective": "Defeat the Kolkar Centaur Lord", "hint": "The Centaur Lord is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "kolkar_centaur_lord", "count": 1}},
                    {"step": 3, "objective": "Return to Merchant Crossroads", "hint": "Use /interact crossroads to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "merchant_crossroads"}},
                ],
                "rewards": {"xp": 8600, "gold": 4300, "items": ["raptor_hide_vest", "stamina_draught"], "reputation": {"trade_coalition": 1620}},
                "dialogue": {"accept": "\"The Centaur Lord is the ultimate threat! Defeat him!\"", "decline": "\"I understand. The Centaur Lord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Centaur Lord.\"", "progress_2": "\"The Centaur Lord is defeated! Return for your reward.\"", "completion": "\"Legendary! You've secured the routes permanently. Here's a worthy reward.\""},
            },
        ],
    },
    
    "scout_eagleeye": {
        "name": "Scout Eagleeye",
        "title": "👁️ Watch Scout",
        "discovery_hint": "A scout scans the horizon from a high vantage point.",
        "zones": ["barrens"],
        "discovery_chance": 0.15,
        "faction": "trade_coalition",
        "introduction": {
            "text": (
                "The scout lowers his spyglass and greets you.\n\n"
                "\"Well met! I'm Scout Eagleeye, watcher of the wasteland.\n"
                "I've spotted many threats that need dealing with.\n\n"
                "If you're willing to help clear them out, I'll share valuable intel and rewards.\""
            ),
        },
        "quests": [
            {
                "id": "eagleeye_quest_1",
                "name": "Threat Elimination",
                "description": "Help the scout eliminate spotted threats.",
                "level_req": 11,
                "steps": [
                    {"step": 1, "objective": "Defeat 5 Sunscale Raptors", "hint": "Raptors have been spotted nearby.", "completion_check": {"type": "kill_enemy", "value": "sunscale_raptor", "count": 5}},
                    {"step": 2, "objective": "Return to Scout Eagleeye", "hint": "Use /interact eagleeye to report back.", "completion_check": {"type": "talk_to_npc", "value": "scout_eagleeye"}},
                ],
                "rewards": {"xp": 3700, "gold": 1850, "items": ["stamina_draught"], "reputation": {"trade_coalition": 660}},
                "dialogue": {"accept": "\"Good! Help me eliminate these threats.\"", "decline": "\"I understand. Threats are dangerous.\"", "progress_1": "\"Keep going! The threats need elimination.\"", "completion": "\"Excellent! The threats are gone. Here's your reward.\""},
            },
            {
                "id": "eagleeye_quest_2",
                "name": "Multiple Targets",
                "description": "Eliminate multiple types of spotted threats.",
                "level_req": 14,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Thunder Lizards", "hint": "Thunder lizards have been spotted.", "completion_check": {"type": "kill_enemy", "value": "thunder_lizard", "count": 6}},
                    {"step": 2, "objective": "Defeat 4 Zhevras", "hint": "Zhevras are also a threat.", "completion_check": {"type": "kill_enemy", "value": "zhevra", "count": 4}},
                    {"step": 3, "objective": "Return to Scout Eagleeye", "hint": "Use /interact eagleeye to report back.", "completion_check": {"type": "talk_to_npc", "value": "scout_eagleeye"}},
                ],
                "rewards": {"xp": 4700, "gold": 2350, "items": ["bone_club"], "reputation": {"trade_coalition": 860}},
                "dialogue": {"accept": "\"Multiple targets! Eliminate them all.\"", "decline": "\"I understand. Multiple targets are difficult.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The targets are being eliminated.\"", "completion": "\"Wonderful! All targets eliminated. Here's your reward.\""},
            },
            {
                "id": "eagleeye_quest_3",
                "name": "Complete Reconnaissance",
                "description": "Complete reconnaissance by clearing all threats throughout The Barrens.",
                "level_req": 19,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in The Barrens", "hint": "Clear all spotted threats.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 15}},
                    {"step": 2, "objective": "Return to Scout Eagleeye", "hint": "Use /interact eagleeye to report back.", "completion_check": {"type": "talk_to_npc", "value": "scout_eagleeye"}},
                ],
                "rewards": {"xp": 6200, "gold": 3100, "items": ["raptor_hide_vest"], "reputation": {"trade_coalition": 1140}},
                "dialogue": {"accept": "\"Complete reconnaissance! Finish this within 48 hours!\"", "decline": "\"I understand. This is extensive reconnaissance.\"", "progress_1": "\"Keep fighting! The reconnaissance is progressing.\"", "completion": "\"Incredible! The complete reconnaissance is finished. All threats are documented.\""},
            },
            {
                "id": "eagleeye_quest_4",
                "name": "The Ultimate Threat",
                "description": "Face the ultimate spotted threat: defeat the Barrens Overlord.",
                "level_req": 23,
                "steps": [
                    {"step": 1, "objective": "Defeat 12 enemies in The Barrens", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 12}},
                    {"step": 2, "objective": "Defeat the Barrens Overlord", "hint": "The Overlord is the ultimate threat. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "barrens_overlord", "count": 1}},
                    {"step": 3, "objective": "Return to Scout Eagleeye", "hint": "Use /interact eagleeye to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "scout_eagleeye"}},
                ],
                "rewards": {"xp": 8200, "gold": 4100, "items": ["raptor_hide_vest", "stamina_draught"], "reputation": {"trade_coalition": 1540}},
                "dialogue": {"accept": "\"The Overlord is the ultimate threat! Defeat him!\"", "decline": "\"I understand. The Overlord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Overlord.\"", "progress_2": "\"The Overlord is defeated! Return for your reward.\"", "completion": "\"Legendary! You've eliminated the ultimate threat. Here's a worthy reward.\""},
            },
        ],
    },
    
    "herbalist_desert": {
        "name": "Herbalist Desert",
        "title": "🌿 Desert Healer",
        "discovery_hint": "An herbalist collects rare plants in the harsh terrain.",
        "zones": ["barrens"],
        "discovery_chance": 0.15,
        "faction": "trade_coalition",
        "introduction": {
            "text": (
                "The herbalist looks up from collecting plants with a warm smile.\n\n"
                "\"Greetings, traveler! I'm Herbalist Desert, healer of the wasteland.\n"
                "I need to collect rare plants, but the threats make it dangerous.\n\n"
                "Help me clear the area, and I'll share my healing knowledge and rewards.\""
            ),
        },
        "quests": [
            {
                "id": "desert_quest_1",
                "name": "Collection Safety",
                "description": "Help the herbalist collect safely by clearing threats.",
                "level_req": 12,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Barrens Vultures", "hint": "Vultures threaten the collection areas.", "completion_check": {"type": "kill_enemy", "value": "barrens_vulture", "count": 6}},
                    {"step": 2, "objective": "Return to Herbalist Desert", "hint": "Use /interact desert to report back.", "completion_check": {"type": "talk_to_npc", "value": "herbalist_desert"}},
                ],
                "rewards": {"xp": 3800, "gold": 1900, "items": ["stamina_draught"], "reputation": {"trade_coalition": 670}},
                "dialogue": {"accept": "\"Good! Help me collect safely.\"", "decline": "\"I understand. Collection takes time.\"", "progress_1": "\"Keep going! The collection areas are getting safer.\"", "completion": "\"Excellent! The areas are safe. Here's your reward.\""},
            },
            {
                "id": "desert_quest_2",
                "name": "Rare Plant Areas",
                "description": "Clear threats from multiple rare plant collection areas.",
                "level_req": 15,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Wind Sweepers", "hint": "Wind sweepers guard rare plant areas.", "completion_check": {"type": "kill_enemy", "value": "wind_sweeper", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Barrens Scorpions", "hint": "Scorpions also guard the areas.", "completion_check": {"type": "kill_enemy", "value": "barrens_scorpion", "count": 5}},
                    {"step": 3, "objective": "Return to Herbalist Desert", "hint": "Use /interact desert to report back.", "completion_check": {"type": "talk_to_npc", "value": "herbalist_desert"}},
                ],
                "rewards": {"xp": 5000, "gold": 2500, "items": ["bone_club"], "reputation": {"trade_coalition": 910}},
                "dialogue": {"accept": "\"The areas are dangerous! Clear them out.\"", "decline": "\"I understand. Areas are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The areas are getting safer.\"", "completion": "\"Wonderful! All areas are secure. Here's your reward.\""},
            },
            {
                "id": "desert_quest_3",
                "name": "Complete Collection",
                "description": "Complete the collection by clearing all threats throughout The Barrens.",
                "level_req": 20,
                "time_limit_hours": 48,
                "steps": [
                    {"step": 1, "objective": "Defeat 16 enemies in The Barrens", "hint": "Clear all threats to complete the collection.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 16}},
                    {"step": 2, "objective": "Return to Herbalist Desert", "hint": "Use /interact desert to report back.", "completion_check": {"type": "talk_to_npc", "value": "herbalist_desert"}},
                ],
                "rewards": {"xp": 6500, "gold": 3250, "items": ["raptor_hide_vest"], "reputation": {"trade_coalition": 1230}},
                "dialogue": {"accept": "\"Complete the collection! Finish this within 48 hours!\"", "decline": "\"I understand. This is extensive collection.\"", "progress_1": "\"Keep fighting! The collection is progressing.\"", "completion": "\"Incredible! The complete collection is finished. All areas are safe.\""},
            },
            {
                "id": "desert_quest_4",
                "name": "The Ultimate Garden",
                "description": "Face the ultimate challenge: clear the garden guarded by the Thunderhawk Alpha.",
                "level_req": 24,
                "steps": [
                    {"step": 1, "objective": "Defeat 13 enemies in The Barrens", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 13}},
                    {"step": 2, "objective": "Defeat the Thunderhawk Alpha", "hint": "The Alpha guards the ultimate garden. Use /fight to challenge it.", "completion_check": {"type": "kill_enemy", "value": "thunderhawk_alpha", "count": 1}},
                    {"step": 3, "objective": "Return to Herbalist Desert", "hint": "Use /interact desert to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "herbalist_desert"}},
                ],
                "rewards": {"xp": 8500, "gold": 4250, "items": ["raptor_hide_vest", "stamina_draught"], "reputation": {"trade_coalition": 1630}},
                "dialogue": {"accept": "\"The Thunderhawk Alpha guards the ultimate garden! Defeat it!\"", "decline": "\"I understand. The Alpha is dangerous.\"", "progress_1": "\"Good preparation! Now face the Alpha.\"", "progress_2": "\"The Alpha is defeated! The ultimate garden is clear! Return for your reward.\"", "completion": "\"Legendary! You've cleared the ultimate garden. Here's a worthy reward.\""},
            },
        ],
    },
    
    # ── New NPCs for Stranglethorn (6 additional) ────────────────────────────
    "explorer_jungle": {
        "name": "Explorer Jungle",
        "title": "🗺️ Jungle Explorer",
        "discovery_hint": "An explorer with a machete cuts through dense vegetation.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.11,
        "faction": "pirate_fleet",
        "introduction": {
            "text": (
                "The explorer looks up from cutting vegetation with excitement.\n\n"
                "\"Ah! Another explorer! I'm Explorer Jungle, and I map these jungles.\n"
                "I've been documenting all the threats and landmarks.\n\n"
                "If you can help me clear out the dangers while I map,\n"
                "I'll share my findings and reward you.\""
            ),
        },
        "quests": [
            {
                "id": "jungle_quest_1",
                "name": "Jungle Mapping",
                "description": "Help the explorer map safely by clearing threats.",
                "level_req": 26,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Panthers", "hint": "Panthers threaten the mapping routes.", "completion_check": {"type": "kill_enemy", "value": "panther", "count": 6}},
                    {"step": 2, "objective": "Return to Explorer Jungle", "hint": "Use /interact jungle to report back.", "completion_check": {"type": "talk_to_npc", "value": "explorer_jungle"}},
                ],
                "rewards": {"xp": 5500, "gold": 3300, "items": ["elixir_of_fortitude"], "reputation": {"pirate_fleet": 850}},
                "dialogue": {"accept": "\"Good! Help me map safely.\"", "decline": "\"I understand. Mapping takes time.\"", "progress_1": "\"Keep going! The maps are coming along.\"", "completion": "\"Excellent! The maps are safer. Here's your reward.\""},
            },
            {
                "id": "jungle_quest_2",
                "name": "Terrain Threats",
                "description": "Clear out threats in different jungle terrain types.",
                "level_req": 30,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Tigers", "hint": "Tigers roam the jungle terrain.", "completion_check": {"type": "kill_enemy", "value": "tiger", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Basilisks", "hint": "Basilisks guard the jungle passes.", "completion_check": {"type": "kill_enemy", "value": "basilisk", "count": 5}},
                    {"step": 3, "objective": "Return to Explorer Jungle", "hint": "Use /interact jungle to report back.", "completion_check": {"type": "talk_to_npc", "value": "explorer_jungle"}},
                ],
                "rewards": {"xp": 7000, "gold": 4200, "items": ["jungle_leather_chest"], "reputation": {"pirate_fleet": 1100}},
                "dialogue": {"accept": "\"The terrain is dangerous! Clear it out.\"", "decline": "\"I understand. Terrain is treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The terrain is getting safer.\"", "completion": "\"Wonderful! The terrain is mapped and secure. Here's your reward.\""},
            },
            {
                "id": "jungle_quest_3",
                "name": "Complete Mapping",
                "description": "Complete the mapping by clearing all threats throughout Stranglethorn.",
                "level_req": 37,
                "time_limit_hours": 72,
                "steps": [
                    {"step": 1, "objective": "Defeat 18 enemies in Stranglethorn Vale", "hint": "Clear all threats to complete the mapping.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 18}},
                    {"step": 2, "objective": "Return to Explorer Jungle", "hint": "Use /interact jungle to report back.", "completion_check": {"type": "talk_to_npc", "value": "explorer_jungle"}},
                ],
                "rewards": {"xp": 10000, "gold": 6000, "items": ["corsair_blade"], "reputation": {"pirate_fleet": 1400}},
                "dialogue": {"accept": "\"Complete the mapping! Finish this within 72 hours!\"", "decline": "\"I understand. This is extensive mapping.\"", "progress_1": "\"Keep fighting! The mapping is progressing.\"", "completion": "\"Incredible! The mapping is complete. All threats are documented.\""},
            },
            {
                "id": "jungle_quest_4",
                "name": "The Bhag Thera",
                "description": "Face the ultimate challenge: map the area guarded by Bhag Thera.",
                "level_req": 42,
                "steps": [
                    {"step": 1, "objective": "Defeat 14 enemies in Stranglethorn Vale", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 14}},
                    {"step": 2, "objective": "Defeat Bhag Thera", "hint": "Bhag Thera guards the final mapping area. Use /fight to challenge it.", "completion_check": {"type": "kill_enemy", "value": "bhag_thera", "count": 1}},
                    {"step": 3, "objective": "Return to Explorer Jungle", "hint": "Use /interact jungle to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "explorer_jungle"}},
                ],
                "rewards": {"xp": 13000, "gold": 7800, "items": ["corsair_blade", "jungle_leather_chest"], "reputation": {"pirate_fleet": 1800}},
                "dialogue": {"accept": "\"Bhag Thera guards the final area! Defeat it!\"", "decline": "\"I understand. Bhag Thera is dangerous.\"", "progress_1": "\"Good preparation! Now face Bhag Thera.\"", "progress_2": "\"Bhag Thera is defeated! The mapping is complete! Return for your reward.\"", "completion": "\"Legendary! The complete map is finished. Here's a worthy reward.\""},
            },
        ],
    },
    
    "hunter_tiger": {
        "name": "Hunter Tiger",
        "title": "🐅 Beast Hunter",
        "discovery_hint": "A hunter examines large cat tracks in the mud.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.12,
        "faction": "pirate_fleet",
        "introduction": {
            "text": (
                "The hunter looks up from examining tracks with a knowing smile.\n\n"
                "\"Ah, another tracker! I'm Hunter Tiger, and I know these jungles.\n"
                "I've been tracking some dangerous prey, and I could use help.\n\n"
                "If you're skilled with a weapon, I have several hunts for you.\""
            ),
        },
        "quests": [
            {
                "id": "tiger_quest_1",
                "name": "Jungle Hunt",
                "description": "Join Hunter Tiger on a jungle hunt.",
                "level_req": 26,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Panthers", "hint": "Panthers are common jungle prey.", "completion_check": {"type": "kill_enemy", "value": "panther", "count": 6}},
                    {"step": 2, "objective": "Return to Hunter Tiger", "hint": "Use /interact tiger to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_tiger"}},
                ],
                "rewards": {"xp": 5600, "gold": 3360, "items": ["elixir_of_fortitude"], "reputation": {"pirate_fleet": 860}},
                "dialogue": {"accept": "\"Good! Let's see what you can track in the jungle.\"", "decline": "\"I understand. Jungle hunting takes skill.\"", "progress_1": "\"Keep tracking! You're doing well.\"", "completion": "\"Excellent tracking! Here's your reward.\""},
            },
            {
                "id": "tiger_quest_2",
                "name": "Multiple Prey",
                "description": "Hunt multiple types of jungle creatures.",
                "level_req": 30,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Tigers", "hint": "Track and defeat tigers.", "completion_check": {"type": "kill_enemy", "value": "tiger", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Crocodiles", "hint": "Now track and defeat crocodiles.", "completion_check": {"type": "kill_enemy", "value": "crocodile", "count": 5}},
                    {"step": 3, "objective": "Return to Hunter Tiger", "hint": "Use /interact tiger to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_tiger"}},
                ],
                "rewards": {"xp": 7100, "gold": 4260, "items": ["jungle_leather_chest"], "reputation": {"pirate_fleet": 1120}},
                "dialogue": {"accept": "\"This is more challenging. Track both prey types.\"", "decline": "\"I understand. Multiple prey is difficult.\"", "progress_1": "\"Good tracking! Keep going.\"", "progress_2": "\"Excellent! You're a skilled tracker.\"", "completion": "\"Outstanding tracking! Here's your reward.\""},
            },
            {
                "id": "tiger_quest_3",
                "name": "Jungle Sweep",
                "description": "Conduct a comprehensive hunt throughout Stranglethorn.",
                "level_req": 37,
                "time_limit_hours": 72,
                "steps": [
                    {"step": 1, "objective": "Defeat 18 enemies in Stranglethorn Vale", "hint": "Hunt any creatures throughout the jungle.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 18}},
                    {"step": 2, "objective": "Return to Hunter Tiger", "hint": "Use /interact tiger to report back.", "completion_check": {"type": "talk_to_npc", "value": "hunter_tiger"}},
                ],
                "rewards": {"xp": 10100, "gold": 6060, "items": ["corsair_blade"], "reputation": {"pirate_fleet": 1420}},
                "dialogue": {"accept": "\"A comprehensive hunt! Complete this within 72 hours!\"", "decline": "\"I understand. This is extensive hunting.\"", "progress_1": "\"Keep hunting! The jungle needs clearing.\"", "completion": "\"Incredible hunting! The jungle is well tracked now.\""},
            },
            {
                "id": "tiger_quest_4",
                "name": "The Jungle Lord",
                "description": "Face the ultimate challenge: hunt down the Jungle Lord.",
                "level_req": 43,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in Stranglethorn Vale", "hint": "Prepare by hunting regular creatures first.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 15}},
                    {"step": 2, "objective": "Defeat the Jungle Lord", "hint": "The Jungle Lord is the ultimate prey. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "jungle_lord", "count": 1}},
                    {"step": 3, "objective": "Return to Hunter Tiger", "hint": "Use /interact tiger to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "hunter_tiger"}},
                ],
                "rewards": {"xp": 13100, "gold": 7860, "items": ["corsair_blade", "jungle_leather_chest"], "reputation": {"pirate_fleet": 1820}},
                "dialogue": {"accept": "\"The Jungle Lord is the ultimate prey! Hunt it down!\"", "decline": "\"I understand. The Jungle Lord is dangerous.\"", "progress_1": "\"Good preparation! Now hunt the Jungle Lord.\"", "progress_2": "\"The Jungle Lord is defeated! Return for your reward.\"", "completion": "\"Legendary hunting! You've taken down the ultimate prey. Here's a worthy reward.\""},
            },
        ],
    },
    
    "merchant_pirate": {
        "name": "Merchant Pirate",
        "title": "💰 Smuggler",
        "discovery_hint": "A shady merchant sells exotic goods from a hidden cove.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.11,
        "faction": "pirate_fleet",
        "introduction": {
            "text": (
                "The merchant looks around nervously before speaking.\n\n"
                "\"Shh! Keep it quiet, mate. I'm Merchant Pirate, and I deal in... special goods.\n"
                "Business has been difficult with all these threats around.\n\n"
                "Help me secure my operations, and I'll share some of my... inventory.\""
            ),
        },
        "quests": [
            {
                "id": "pirate_quest_1",
                "name": "Smuggler Security",
                "description": "Help secure the smuggler's operations by defeating threats.",
                "level_req": 27,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Bloodsail Pirates", "hint": "Pirates threaten the operations.", "completion_check": {"type": "kill_enemy", "value": "bloodsail_pirate", "count": 6}},
                    {"step": 2, "objective": "Return to Merchant Pirate", "hint": "Use /interact pirate to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_pirate"}},
                ],
                "rewards": {"xp": 5700, "gold": 3420, "items": ["elixir_of_fortitude"], "reputation": {"pirate_fleet": 870}},
                "dialogue": {"accept": "\"Good! Help me secure my operations.\"", "decline": "\"I understand. Operations are dangerous.\"", "progress_1": "\"Keep going! The operations need securing.\"", "completion": "\"Excellent! The operations are safer. Here's your reward.\""},
            },
            {
                "id": "pirate_quest_2",
                "name": "Multiple Threats",
                "description": "Deal with multiple threats to the smuggler's operations.",
                "level_req": 31,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Bloodsail Corsairs", "hint": "Corsairs are elite pirates.", "completion_check": {"type": "kill_enemy", "value": "bloodsail_corsair", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Venture Co Enforcers", "hint": "Enforcers also threaten operations.", "completion_check": {"type": "kill_enemy", "value": "venture_co_enforcer", "count": 5}},
                    {"step": 3, "objective": "Return to Merchant Pirate", "hint": "Use /interact pirate to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_pirate"}},
                ],
                "rewards": {"xp": 7200, "gold": 4320, "items": ["jungle_leather_chest"], "reputation": {"pirate_fleet": 1130}},
                "dialogue": {"accept": "\"The operations are dangerous! Clear them out.\"", "decline": "\"I understand. Operations are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The operations are getting safer.\"", "completion": "\"Wonderful! All operations are secure. Here's your reward.\""},
            },
            {
                "id": "pirate_quest_3",
                "name": "Complete Security",
                "description": "Secure all operations by clearing threats throughout Stranglethorn.",
                "level_req": 38,
                "time_limit_hours": 72,
                "steps": [
                    {"step": 1, "objective": "Defeat 19 enemies in Stranglethorn Vale", "hint": "Clear all threats to the operations.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 19}},
                    {"step": 2, "objective": "Return to Merchant Pirate", "hint": "Use /interact pirate to report back.", "completion_check": {"type": "talk_to_npc", "value": "merchant_pirate"}},
                ],
                "rewards": {"xp": 10200, "gold": 6120, "items": ["corsair_blade"], "reputation": {"pirate_fleet": 1430}},
                "dialogue": {"accept": "\"Secure all operations! Complete this within 72 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The operations need complete security.\"", "completion": "\"Incredible! All operations are secure now.\""},
            },
            {
                "id": "pirate_quest_4",
                "name": "The Bloodsail Admiral",
                "description": "Defeat the Bloodsail Admiral to secure the operations permanently.",
                "level_req": 43,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in Stranglethorn Vale", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 15}},
                    {"step": 2, "objective": "Defeat the Bloodsail Admiral", "hint": "The Admiral is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "bloodsail_admiral", "count": 1}},
                    {"step": 3, "objective": "Return to Merchant Pirate", "hint": "Use /interact pirate to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "merchant_pirate"}},
                ],
                "rewards": {"xp": 13200, "gold": 7920, "items": ["corsair_blade", "jungle_leather_chest"], "reputation": {"pirate_fleet": 1830}},
                "dialogue": {"accept": "\"The Admiral is the ultimate threat! Defeat him!\"", "decline": "\"I understand. The Admiral is dangerous.\"", "progress_1": "\"Good preparation! Now face the Admiral.\"", "progress_2": "\"The Admiral is defeated! Return for your reward.\"", "completion": "\"Legendary! You've secured the operations permanently. Here's a worthy reward.\""},
            },
        ],
    },
    
    "shaman_tribal": {
        "name": "Shaman Tribal",
        "title": "🔮 Jungle Shaman",
        "discovery_hint": "A tribal shaman performs rituals near ancient ruins.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.12,
        "faction": "pirate_fleet",
        "introduction": {
            "text": (
                "The shaman finishes a ritual and turns to you with wise eyes.\n\n"
                "\"The spirits speak, traveler. I am Shaman Tribal, keeper of the jungle ways.\n"
                "The balance of the jungle is disturbed by dark forces.\n\n"
                "Help me restore the balance, and the spirits will reward you.\""
            ),
        },
        "quests": [
            {
                "id": "tribal_quest_1",
                "name": "Spirit Balance",
                "description": "Help the shaman restore balance by defeating dark forces.",
                "level_req": 27,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Jungle Trolls", "hint": "Trolls disturb the spirit balance.", "completion_check": {"type": "kill_enemy", "value": "jungle_troll", "count": 6}},
                    {"step": 2, "objective": "Return to Shaman Tribal", "hint": "Use /interact tribal to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_tribal"}},
                ],
                "rewards": {"xp": 5800, "gold": 3480, "items": ["elixir_of_fortitude"], "reputation": {"pirate_fleet": 880}},
                "dialogue": {"accept": "\"The spirits guide you. Restore the balance.\"", "decline": "\"I understand. Balance takes time.\"", "progress_1": "\"Keep fighting! The balance is being restored.\"", "completion": "\"Blessings! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "tribal_quest_2",
                "name": "Jungle Threats",
                "description": "Deal with the threats disturbing the jungle balance.",
                "level_req": 31,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Stranglethorn Apes", "hint": "Apes disrupt the natural balance.", "completion_check": {"type": "kill_enemy", "value": "stranglethorn_ape", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Basilisks", "hint": "Basilisks are elemental threats.", "completion_check": {"type": "kill_enemy", "value": "basilisk", "count": 5}},
                    {"step": 3, "objective": "Return to Shaman Tribal", "hint": "Use /interact tribal to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_tribal"}},
                ],
                "rewards": {"xp": 7300, "gold": 4380, "items": ["jungle_leather_chest"], "reputation": {"pirate_fleet": 1140}},
                "dialogue": {"accept": "\"More threats! Restore the balance.\"", "decline": "\"I understand. Balance is complex.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The balance is being restored.\"", "completion": "\"Wonderful! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "tribal_quest_3",
                "name": "Jungle Purification",
                "description": "Purify the entire jungle by clearing all dark forces.",
                "level_req": 38,
                "time_limit_hours": 72,
                "steps": [
                    {"step": 1, "objective": "Defeat 19 enemies in Stranglethorn Vale", "hint": "Clear all dark forces from the jungle.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 19}},
                    {"step": 2, "objective": "Return to Shaman Tribal", "hint": "Use /interact tribal to report back.", "completion_check": {"type": "talk_to_npc", "value": "shaman_tribal"}},
                ],
                "rewards": {"xp": 10300, "gold": 6180, "items": ["corsair_blade"], "reputation": {"pirate_fleet": 1440}},
                "dialogue": {"accept": "\"Purify the jungle! Complete this within 72 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The jungle needs purification.\"", "completion": "\"Incredible! The jungle is purified. The spirits are pleased.\""},
            },
            {
                "id": "tribal_quest_4",
                "name": "Kurzen the Mad",
                "description": "Face the ultimate dark force: defeat Kurzen the Mad.",
                "level_req": 43,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in Stranglethorn Vale", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 15}},
                    {"step": 2, "objective": "Defeat Kurzen the Mad", "hint": "Kurzen is the ultimate boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "kurzen_the_mad", "count": 1}},
                    {"step": 3, "objective": "Return to Shaman Tribal", "hint": "Use /interact tribal to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "shaman_tribal"}},
                ],
                "rewards": {"xp": 13300, "gold": 7980, "items": ["corsair_blade", "jungle_leather_chest"], "reputation": {"pirate_fleet": 1840}},
                "dialogue": {"accept": "\"Kurzen is the ultimate dark force! Defeat him!\"", "decline": "\"I understand. Kurzen is dangerous.\"", "progress_1": "\"Good preparation! Now face Kurzen.\"", "progress_2": "\"Kurzen is defeated! The balance is restored! Return for your reward.\"", "completion": "\"Legendary! You've restored the ultimate balance. The spirits reward you.\""},
            },
        ],
    },
    
    "warrior_troll": {
        "name": "Warrior Troll",
        "title": "⚔️ Troll Warrior",
        "discovery_hint": "A troll warrior sharpens his blade near a campfire.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.11,
        "faction": "pirate_fleet",
        "introduction": {
            "text": (
                "The warrior stops sharpening and greets you with a fierce grin.\n\n"
                "\"Well met, fighter! I'm Warrior Troll, and I've seen many battles.\n"
                "The jungle threats need dealing with.\n\n"
                "If you're ready for a real fight, I have several challenges for you.\""
            ),
        },
        "quests": [
            {
                "id": "troll_quest_1",
                "name": "First Battle",
                "description": "Prove yourself in your first battle with Warrior Troll.",
                "level_req": 26,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Jungle Stalkers", "hint": "Stalkers are aggressive fighters.", "completion_check": {"type": "kill_enemy", "value": "jungle_stalker", "count": 6}},
                    {"step": 2, "objective": "Return to Warrior Troll", "hint": "Use /interact troll to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_troll"}},
                ],
                "rewards": {"xp": 5900, "gold": 3540, "items": ["elixir_of_fortitude"], "reputation": {"pirate_fleet": 890}},
                "dialogue": {"accept": "\"Good! Let's see what you can do in battle.\"", "decline": "\"I understand. Battle takes courage.\"", "progress_1": "\"Keep fighting! You're doing well.\"", "completion": "\"Excellent battle! Here's your reward.\""},
            },
            {
                "id": "troll_quest_2",
                "name": "Dual Threats",
                "description": "Face multiple types of dangerous enemies.",
                "level_req": 30,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Crocodiles", "hint": "Fight the crocodiles.", "completion_check": {"type": "kill_enemy", "value": "crocodile", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Jungle Trolls", "hint": "Now fight the trolls.", "completion_check": {"type": "kill_enemy", "value": "jungle_troll", "count": 5}},
                    {"step": 3, "objective": "Return to Warrior Troll", "hint": "Use /interact troll to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_troll"}},
                ],
                "rewards": {"xp": 7400, "gold": 4440, "items": ["jungle_leather_chest"], "reputation": {"pirate_fleet": 1150}},
                "dialogue": {"accept": "\"This is more challenging. Face both threats.\"", "decline": "\"I understand. Multiple enemies are difficult.\"", "progress_1": "\"Good fighting! Keep going.\"", "progress_2": "\"Excellent! You're a skilled warrior.\"", "completion": "\"Outstanding battle! Here's your reward.\""},
            },
            {
                "id": "troll_quest_3",
                "name": "Jungle Conquest",
                "description": "Conquer all threats throughout Stranglethorn.",
                "level_req": 37,
                "time_limit_hours": 72,
                "steps": [
                    {"step": 1, "objective": "Defeat 18 enemies in Stranglethorn Vale", "hint": "Fight all threats in the jungle.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 18}},
                    {"step": 2, "objective": "Return to Warrior Troll", "hint": "Use /interact troll to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_troll"}},
                ],
                "rewards": {"xp": 10400, "gold": 6240, "items": ["corsair_blade"], "reputation": {"pirate_fleet": 1450}},
                "dialogue": {"accept": "\"Conquer the jungle! Complete this within 72 hours!\"", "decline": "\"I understand. This is extensive fighting.\"", "progress_1": "\"Keep fighting! The jungle needs conquering.\"", "completion": "\"Incredible conquest! The jungle is yours.\""},
            },
            {
                "id": "troll_quest_4",
                "name": "The Jungle Lord",
                "description": "Face the ultimate challenge: defeat the Jungle Lord.",
                "level_req": 42,
                "steps": [
                    {"step": 1, "objective": "Defeat 14 enemies in Stranglethorn Vale", "hint": "Prepare by fighting regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 14}},
                    {"step": 2, "objective": "Defeat the Jungle Lord", "hint": "The Jungle Lord is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "jungle_lord", "count": 1}},
                    {"step": 3, "objective": "Return to Warrior Troll", "hint": "Use /interact troll to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "warrior_troll"}},
                ],
                "rewards": {"xp": 13400, "gold": 8040, "items": ["corsair_blade", "jungle_leather_chest"], "reputation": {"pirate_fleet": 1850}},
                "dialogue": {"accept": "\"The Jungle Lord is the ultimate challenge! Defeat him!\"", "decline": "\"I understand. The Jungle Lord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Jungle Lord.\"", "progress_2": "\"The Jungle Lord is defeated! Return for your reward.\"", "completion": "\"Legendary battle! You've proven yourself a true warrior. Here's a worthy reward.\""},
            },
        ],
    },
    
    "archaeologist_ruins": {
        "name": "Archaeologist Ruins",
        "title": "📜 Ruin Scholar",
        "discovery_hint": "An archaeologist studies ancient carvings on stone tablets.",
        "zones": ["stranglethorn"],
        "discovery_chance": 0.12,
        "faction": "pirate_fleet",
        "introduction": {
            "text": (
                "The archaeologist looks up from studying tablets with excitement.\n\n"
                "\"Ah! Another explorer! I'm Archaeologist Ruins, and I study these ancient sites.\n"
                "I've been documenting all the threats and artifacts.\n\n"
                "If you can help me clear out the dangers while I study,\n"
                "I'll share my findings and reward you.\""
            ),
        },
        "quests": [
            {
                "id": "ruins_quest_1",
                "name": "Ruin Safety",
                "description": "Help the archaeologist study safely by clearing threats.",
                "level_req": 27,
                "steps": [
                    {"step": 1, "objective": "Defeat 6 Basilisks", "hint": "Basilisks threaten the ruin sites.", "completion_check": {"type": "kill_enemy", "value": "basilisk", "count": 6}},
                    {"step": 2, "objective": "Return to Archaeologist Ruins", "hint": "Use /interact ruins to report back.", "completion_check": {"type": "talk_to_npc", "value": "archaeologist_ruins"}},
                ],
                "rewards": {"xp": 6000, "gold": 3600, "items": ["elixir_of_fortitude"], "reputation": {"pirate_fleet": 900}},
                "dialogue": {"accept": "\"Good! Help me study safely.\"", "decline": "\"I understand. Study takes time.\"", "progress_1": "\"Keep going! The ruins are getting safer.\"", "completion": "\"Excellent! The ruins are safe. Here's your reward.\""},
            },
            {
                "id": "ruins_quest_2",
                "name": "Ancient Sites",
                "description": "Clear threats from multiple ancient ruin sites.",
                "level_req": 31,
                "steps": [
                    {"step": 1, "objective": "Defeat 7 Stranglethorn Apes", "hint": "Apes guard ancient sites.", "completion_check": {"type": "kill_enemy", "value": "stranglethorn_ape", "count": 7}},
                    {"step": 2, "objective": "Defeat 5 Crocodiles", "hint": "Crocodiles also guard the sites.", "completion_check": {"type": "kill_enemy", "value": "crocodile", "count": 5}},
                    {"step": 3, "objective": "Return to Archaeologist Ruins", "hint": "Use /interact ruins to report back.", "completion_check": {"type": "talk_to_npc", "value": "archaeologist_ruins"}},
                ],
                "rewards": {"xp": 7500, "gold": 4500, "items": ["jungle_leather_chest"], "reputation": {"pirate_fleet": 1160}},
                "dialogue": {"accept": "\"The sites are dangerous! Clear them out.\"", "decline": "\"I understand. Sites are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The sites are getting safer.\"", "completion": "\"Wonderful! All sites are secure. Here's your reward.\""},
            },
            {
                "id": "ruins_quest_3",
                "name": "Complete Study",
                "description": "Complete the study by clearing all threats throughout Stranglethorn.",
                "level_req": 38,
                "time_limit_hours": 72,
                "steps": [
                    {"step": 1, "objective": "Defeat 19 enemies in Stranglethorn Vale", "hint": "Clear all threats to complete the study.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 19}},
                    {"step": 2, "objective": "Return to Archaeologist Ruins", "hint": "Use /interact ruins to report back.", "completion_check": {"type": "talk_to_npc", "value": "archaeologist_ruins"}},
                ],
                "rewards": {"xp": 10500, "gold": 6300, "items": ["corsair_blade"], "reputation": {"pirate_fleet": 1460}},
                "dialogue": {"accept": "\"Complete the study! Finish this within 72 hours!\"", "decline": "\"I understand. This is extensive study.\"", "progress_1": "\"Keep fighting! The study is progressing.\"", "completion": "\"Incredible! The complete study is finished. All ruins are documented.\""},
            },
            {
                "id": "ruins_quest_4",
                "name": "The Ultimate Ruin",
                "description": "Face the ultimate challenge: study the ruin guarded by Kurzen the Mad.",
                "level_req": 43,
                "steps": [
                    {"step": 1, "objective": "Defeat 15 enemies in Stranglethorn Vale", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 15}},
                    {"step": 2, "objective": "Defeat Kurzen the Mad", "hint": "Kurzen guards the ultimate ruin. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "kurzen_the_mad", "count": 1}},
                    {"step": 3, "objective": "Return to Archaeologist Ruins", "hint": "Use /interact ruins to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "archaeologist_ruins"}},
                ],
                "rewards": {"xp": 13500, "gold": 8100, "items": ["corsair_blade", "jungle_leather_chest"], "reputation": {"pirate_fleet": 1860}},
                "dialogue": {"accept": "\"Kurzen guards the ultimate ruin! Defeat him!\"", "decline": "\"I understand. Kurzen is dangerous.\"", "progress_1": "\"Good preparation! Now face Kurzen.\"", "progress_2": "\"Kurzen is defeated! The ultimate ruin is accessible! Return for your reward.\"", "completion": "\"Legendary! The ultimate ruin is studied. Here's a worthy reward.\""},
            },
        ],
    },
    
    # ── New NPCs for Blackrock Depths (6 additional) ─────────────────────────
    "mage_fire": {
        "name": "Mage Fire",
        "title": "🔥 Fire Mage",
        "discovery_hint": "A mage surrounded by flames studies arcane texts.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.09,
        "faction": "arcane_order",
        "introduction": {
            "text": (
                "The mage looks up from studying texts with intense eyes.\n\n"
                "\"Ah! Another seeker of power! I'm Mage Fire, master of flame.\n"
                "I've been researching the fire magic in these depths.\n\n"
                "Help me clear out the threats, and I'll share my arcane knowledge.\""
            ),
        },
        "quests": [
            {
                "id": "fire_quest_1",
                "name": "Fire Research",
                "description": "Help the mage research by defeating fire creatures.",
                "level_req": 51,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 Fire Imps", "hint": "Fire imps are common in the depths.", "completion_check": {"type": "kill_enemy", "value": "fire_imp", "count": 8}},
                    {"step": 2, "objective": "Return to Mage Fire", "hint": "Use /interact fire to report back.", "completion_check": {"type": "talk_to_npc", "value": "mage_fire"}},
                ],
                "rewards": {"xp": 12000, "gold": 6000, "items": ["flask_of_the_titans"], "reputation": {"arcane_order": 1200}},
                "dialogue": {"accept": "\"Good! Help me with my research.\"", "decline": "\"I understand. Research takes time.\"", "progress_1": "\"Keep going! The research is progressing.\"", "completion": "\"Excellent! The research is valuable. Here's your reward.\""},
            },
            {
                "id": "fire_quest_2",
                "name": "Elemental Threats",
                "description": "Study multiple types of fire elemental threats.",
                "level_req": 53,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 Lava Elementals", "hint": "Lava elementals are powerful.", "completion_check": {"type": "kill_enemy", "value": "lava_elemental", "count": 9}},
                    {"step": 2, "objective": "Defeat 6 Flame Wraiths", "hint": "Flame wraiths are dangerous.", "completion_check": {"type": "kill_enemy", "value": "flame_wraith", "count": 6}},
                    {"step": 3, "objective": "Return to Mage Fire", "hint": "Use /interact fire to report back.", "completion_check": {"type": "talk_to_npc", "value": "mage_fire"}},
                ],
                "rewards": {"xp": 16000, "gold": 8000, "items": ["shadowforge_plate"], "reputation": {"arcane_order": 1600}},
                "dialogue": {"accept": "\"More research needed! Study these threats.\"", "decline": "\"I understand. Research is complex.\"", "progress_1": "\"Good data! Keep going.\"", "progress_2": "\"Excellent! The patterns are clear.\"", "completion": "\"Brilliant research! Here's your reward.\""},
            },
            {
                "id": "fire_quest_3",
                "name": "Comprehensive Study",
                "description": "Conduct a comprehensive study of all fire threats in Blackrock Depths.",
                "level_req": 56,
                "time_limit_hours": 96,
                "steps": [
                    {"step": 1, "objective": "Defeat 22 enemies in Blackrock Depths", "hint": "Study all fire threats in the depths.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 22}},
                    {"step": 2, "objective": "Return to Mage Fire", "hint": "Use /interact fire to report back.", "completion_check": {"type": "talk_to_npc", "value": "mage_fire"}},
                ],
                "rewards": {"xp": 22000, "gold": 11000, "items": ["sulfuron_blade"], "reputation": {"arcane_order": 2200}},
                "dialogue": {"accept": "\"A comprehensive study! Complete this within 96 hours!\"", "decline": "\"I understand. This is extensive research.\"", "progress_1": "\"Keep studying! The data is valuable.\"", "completion": "\"Incredible research! The depths are well documented now.\""},
            },
            {
                "id": "fire_quest_4",
                "name": "The Magmadar",
                "description": "Face the ultimate fire threat: defeat Magmadar.",
                "level_req": 59,
                "steps": [
                    {"step": 1, "objective": "Defeat 17 enemies in Blackrock Depths", "hint": "Prepare by studying regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 17}},
                    {"step": 2, "objective": "Defeat Magmadar", "hint": "Magmadar is the ultimate fire boss. Use /fight to challenge it.", "completion_check": {"type": "kill_enemy", "value": "magmadar", "count": 1}},
                    {"step": 3, "objective": "Return to Mage Fire", "hint": "Use /interact fire to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "mage_fire"}},
                ],
                "rewards": {"xp": 32000, "gold": 16000, "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"], "reputation": {"arcane_order": 3200}},
                "dialogue": {"accept": "\"Magmadar is the ultimate fire threat! Defeat it!\"", "decline": "\"I understand. Magmadar is dangerous.\"", "progress_1": "\"Good preparation! Now face Magmadar.\"", "progress_2": "\"Magmadar is defeated! Return for your reward.\"", "completion": "\"Legendary research! You've defeated the ultimate fire threat. Here's a worthy reward.\""},
            },
        ],
    },
    
    "warrior_dark": {
        "name": "Warrior Dark",
        "title": "⚔️ Dark Warrior",
        "discovery_hint": "A warrior in dark armor stands guard near a lava flow.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.10,
        "faction": "arcane_order",
        "introduction": {
            "text": (
                "The warrior turns to face you with a grim expression.\n\n"
                "\"Well met, fighter! I'm Warrior Dark, and I've seen many battles.\n"
                "The Dark Iron forces need dealing with.\n\n"
                "If you're ready for a real fight, I have several challenges for you.\""
            ),
        },
        "quests": [
            {
                "id": "dark_quest_1",
                "name": "First Battle",
                "description": "Prove yourself in your first battle with Warrior Dark.",
                "level_req": 51,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 Dark Iron Dwarves", "hint": "Dark Iron are aggressive fighters.", "completion_check": {"type": "kill_enemy", "value": "dark_iron_dwarf", "count": 8}},
                    {"step": 2, "objective": "Return to Warrior Dark", "hint": "Use /interact dark to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_dark"}},
                ],
                "rewards": {"xp": 12500, "gold": 6250, "items": ["flask_of_the_titans"], "reputation": {"arcane_order": 1250}},
                "dialogue": {"accept": "\"Good! Let's see what you can do in battle.\"", "decline": "\"I understand. Battle takes courage.\"", "progress_1": "\"Keep fighting! You're doing well.\"", "completion": "\"Excellent battle! Here's your reward.\""},
            },
            {
                "id": "dark_quest_2",
                "name": "Dual Threats",
                "description": "Face multiple types of dangerous enemies.",
                "level_req": 53,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 Dark Iron Guards", "hint": "Fight the guards.", "completion_check": {"type": "kill_enemy", "value": "dark_iron_guard", "count": 9}},
                    {"step": 2, "objective": "Defeat 6 Shadowforge Sentinels", "hint": "Now fight the sentinels.", "completion_check": {"type": "kill_enemy", "value": "shadowforge_sentinel", "count": 6}},
                    {"step": 3, "objective": "Return to Warrior Dark", "hint": "Use /interact dark to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_dark"}},
                ],
                "rewards": {"xp": 16500, "gold": 8250, "items": ["shadowforge_plate"], "reputation": {"arcane_order": 1650}},
                "dialogue": {"accept": "\"This is more challenging. Face both threats.\"", "decline": "\"I understand. Multiple enemies are difficult.\"", "progress_1": "\"Good fighting! Keep going.\"", "progress_2": "\"Excellent! You're a skilled warrior.\"", "completion": "\"Outstanding battle! Here's your reward.\""},
            },
            {
                "id": "dark_quest_3",
                "name": "Depths Conquest",
                "description": "Conquer all threats throughout Blackrock Depths.",
                "level_req": 56,
                "time_limit_hours": 96,
                "steps": [
                    {"step": 1, "objective": "Defeat 22 enemies in Blackrock Depths", "hint": "Fight all threats in the depths.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 22}},
                    {"step": 2, "objective": "Return to Warrior Dark", "hint": "Use /interact dark to report back.", "completion_check": {"type": "talk_to_npc", "value": "warrior_dark"}},
                ],
                "rewards": {"xp": 23000, "gold": 11500, "items": ["sulfuron_blade"], "reputation": {"arcane_order": 2300}},
                "dialogue": {"accept": "\"Conquer the depths! Complete this within 96 hours!\"", "decline": "\"I understand. This is extensive fighting.\"", "progress_1": "\"Keep fighting! The depths need conquering.\"", "completion": "\"Incredible conquest! The depths are yours.\""},
            },
            {
                "id": "dark_quest_4",
                "name": "Lord Incendius",
                "description": "Face the ultimate challenge: defeat Lord Incendius.",
                "level_req": 59,
                "steps": [
                    {"step": 1, "objective": "Defeat 17 enemies in Blackrock Depths", "hint": "Prepare by fighting regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 17}},
                    {"step": 2, "objective": "Defeat Lord Incendius", "hint": "Lord Incendius is a powerful boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "lord_incendius", "count": 1}},
                    {"step": 3, "objective": "Return to Warrior Dark", "hint": "Use /interact dark to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "warrior_dark"}},
                ],
                "rewards": {"xp": 33000, "gold": 16500, "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"], "reputation": {"arcane_order": 3300}},
                "dialogue": {"accept": "\"Lord Incendius is the ultimate challenge! Defeat him!\"", "decline": "\"I understand. Lord Incendius is dangerous.\"", "progress_1": "\"Good preparation! Now face Lord Incendius.\"", "progress_2": "\"Lord Incendius is defeated! Return for your reward.\"", "completion": "\"Legendary battle! You've proven yourself a true warrior. Here's a worthy reward.\""},
            },
        ],
    },
    
    "priest_shadow": {
        "name": "Priest Shadow",
        "title": "🌑 Shadow Priest",
        "discovery_hint": "A priest in dark robes chants near shadowy crystals.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.09,
        "faction": "arcane_order",
        "introduction": {
            "text": (
                "The priest finishes a chant and turns to you with shadowy eyes.\n\n"
                "\"The shadows speak, traveler. I am Priest Shadow, keeper of dark knowledge.\n"
                "The balance of the depths is disturbed by light forces.\n\n"
                "Help me restore the balance, and the shadows will reward you.\""
            ),
        },
        "quests": [
            {
                "id": "shadow_quest_1",
                "name": "Shadow Balance",
                "description": "Help the priest restore balance by defeating light forces.",
                "level_req": 52,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 Firelord Servants", "hint": "Servants disturb the shadow balance.", "completion_check": {"type": "kill_enemy", "value": "firelord_servant", "count": 8}},
                    {"step": 2, "objective": "Return to Priest Shadow", "hint": "Use /interact shadow to report back.", "completion_check": {"type": "talk_to_npc", "value": "priest_shadow"}},
                ],
                "rewards": {"xp": 13000, "gold": 6500, "items": ["flask_of_the_titans"], "reputation": {"arcane_order": 1300}},
                "dialogue": {"accept": "\"The shadows guide you. Restore the balance.\"", "decline": "\"I understand. Balance takes time.\"", "progress_1": "\"Keep fighting! The balance is being restored.\"", "completion": "\"Blessings! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "shadow_quest_2",
                "name": "Depths Threats",
                "description": "Deal with the threats disturbing the depths balance.",
                "level_req": 54,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 Molten Giants", "hint": "Giants disrupt the natural balance.", "completion_check": {"type": "kill_enemy", "value": "molten_giant", "count": 9}},
                    {"step": 2, "objective": "Defeat 6 Dark Iron Sorcerers", "hint": "Sorcerers are magical threats.", "completion_check": {"type": "kill_enemy", "value": "dark_iron_sorcerer", "count": 6}},
                    {"step": 3, "objective": "Return to Priest Shadow", "hint": "Use /interact shadow to report back.", "completion_check": {"type": "talk_to_npc", "value": "priest_shadow"}},
                ],
                "rewards": {"xp": 17000, "gold": 8500, "items": ["shadowforge_plate"], "reputation": {"arcane_order": 1700}},
                "dialogue": {"accept": "\"More threats! Restore the balance.\"", "decline": "\"I understand. Balance is complex.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The balance is being restored.\"", "completion": "\"Wonderful! The balance is stronger. Here's your reward.\""},
            },
            {
                "id": "shadow_quest_3",
                "name": "Depths Purification",
                "description": "Purify the entire depths by clearing all light forces.",
                "level_req": 57,
                "time_limit_hours": 96,
                "steps": [
                    {"step": 1, "objective": "Defeat 23 enemies in Blackrock Depths", "hint": "Clear all light forces from the depths.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 23}},
                    {"step": 2, "objective": "Return to Priest Shadow", "hint": "Use /interact shadow to report back.", "completion_check": {"type": "talk_to_npc", "value": "priest_shadow"}},
                ],
                "rewards": {"xp": 24000, "gold": 12000, "items": ["sulfuron_blade"], "reputation": {"arcane_order": 2400}},
                "dialogue": {"accept": "\"Purify the depths! Complete this within 96 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The depths need purification.\"", "completion": "\"Incredible! The depths are purified. The shadows are pleased.\""},
            },
            {
                "id": "shadow_quest_4",
                "name": "The Golem Lord",
                "description": "Face the ultimate light force: defeat the Golem Lord.",
                "level_req": 59,
                "steps": [
                    {"step": 1, "objective": "Defeat 18 enemies in Blackrock Depths", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 18}},
                    {"step": 2, "objective": "Defeat the Golem Lord", "hint": "The Golem Lord is the ultimate boss. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "golem_lord", "count": 1}},
                    {"step": 3, "objective": "Return to Priest Shadow", "hint": "Use /interact shadow to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "priest_shadow"}},
                ],
                "rewards": {"xp": 34000, "gold": 17000, "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"], "reputation": {"arcane_order": 3400}},
                "dialogue": {"accept": "\"The Golem Lord is the ultimate light force! Defeat him!\"", "decline": "\"I understand. The Golem Lord is dangerous.\"", "progress_1": "\"Good preparation! Now face the Golem Lord.\"", "progress_2": "\"The Golem Lord is defeated! The balance is restored! Return for your reward.\"", "completion": "\"Legendary! You've restored the ultimate balance. The shadows reward you.\""},
            },
        ],
    },
    
    "rogue_assassin": {
        "name": "Rogue Assassin",
        "title": "🗡️ Shadow Assassin",
        "discovery_hint": "A figure in shadows moves silently through the depths.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.10,
        "faction": "arcane_order",
        "introduction": {
            "text": (
                "The assassin steps from the shadows with a knowing smile.\n\n"
                "\"Ah, another shadow walker! I'm Rogue Assassin, master of stealth.\n"
                "I've been tracking targets in these depths.\n\n"
                "If you're skilled in the shadows, I have several contracts for you.\""
            ),
        },
        "quests": [
            {
                "id": "assassin_quest_1",
                "name": "First Contract",
                "description": "Complete your first contract with Rogue Assassin.",
                "level_req": 51,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 Dark Iron Dwarves", "hint": "Dwarves are the first targets.", "completion_check": {"type": "kill_enemy", "value": "dark_iron_dwarf", "count": 8}},
                    {"step": 2, "objective": "Return to Rogue Assassin", "hint": "Use /interact assassin to report back.", "completion_check": {"type": "talk_to_npc", "value": "rogue_assassin"}},
                ],
                "rewards": {"xp": 12800, "gold": 6400, "items": ["flask_of_the_titans"], "reputation": {"arcane_order": 1280}},
                "dialogue": {"accept": "\"Good! Let's see what you can do in the shadows.\"", "decline": "\"I understand. Contracts take skill.\"", "progress_1": "\"Keep going! The contract is progressing.\"", "completion": "\"Excellent work! Here's your reward.\""},
            },
            {
                "id": "assassin_quest_2",
                "name": "Multiple Targets",
                "description": "Eliminate multiple types of targets.",
                "level_req": 53,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 Dark Iron Guards", "hint": "Guards are elite targets.", "completion_check": {"type": "kill_enemy", "value": "dark_iron_guard", "count": 9}},
                    {"step": 2, "objective": "Defeat 6 Magma Lords", "hint": "Magma lords are powerful targets.", "completion_check": {"type": "kill_enemy", "value": "magma_lord", "count": 6}},
                    {"step": 3, "objective": "Return to Rogue Assassin", "hint": "Use /interact assassin to report back.", "completion_check": {"type": "talk_to_npc", "value": "rogue_assassin"}},
                ],
                "rewards": {"xp": 16800, "gold": 8400, "items": ["shadowforge_plate"], "reputation": {"arcane_order": 1680}},
                "dialogue": {"accept": "\"Multiple targets! Eliminate them all.\"", "decline": "\"I understand. Multiple targets are difficult.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The targets are being eliminated.\"", "completion": "\"Wonderful! All targets eliminated. Here's your reward.\""},
            },
            {
                "id": "assassin_quest_3",
                "name": "Complete Contract",
                "description": "Complete the contract by clearing all targets throughout Blackrock Depths.",
                "level_req": 56,
                "time_limit_hours": 96,
                "steps": [
                    {"step": 1, "objective": "Defeat 22 enemies in Blackrock Depths", "hint": "Eliminate all contract targets.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 22}},
                    {"step": 2, "objective": "Return to Rogue Assassin", "hint": "Use /interact assassin to report back.", "completion_check": {"type": "talk_to_npc", "value": "rogue_assassin"}},
                ],
                "rewards": {"xp": 22500, "gold": 11250, "items": ["sulfuron_blade"], "reputation": {"arcane_order": 2250}},
                "dialogue": {"accept": "\"Complete the contract! Finish this within 96 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The contract is progressing.\"", "completion": "\"Incredible! The contract is complete. All targets eliminated.\""},
            },
            {
                "id": "assassin_quest_4",
                "name": "The Ultimate Target",
                "description": "Face the ultimate contract: eliminate the Emperor.",
                "level_req": 59,
                "steps": [
                    {"step": 1, "objective": "Defeat 17 enemies in Blackrock Depths", "hint": "Prepare by eliminating regular targets first.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 17}},
                    {"step": 2, "objective": "Defeat Emperor Dagran Thaurissan", "hint": "The Emperor is the ultimate target. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "emperor_dagran_thaurissan", "count": 1}},
                    {"step": 3, "objective": "Return to Rogue Assassin", "hint": "Use /interact assassin to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "rogue_assassin"}},
                ],
                "rewards": {"xp": 33500, "gold": 16750, "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"], "reputation": {"arcane_order": 3350}},
                "dialogue": {"accept": "\"The Emperor is the ultimate target! Eliminate him!\"", "decline": "\"I understand. The Emperor is dangerous.\"", "progress_1": "\"Good preparation! Now eliminate the Emperor.\"", "progress_2": "\"The Emperor is eliminated! Return for your reward.\"", "completion": "\"Legendary! You've completed the ultimate contract. Here's a worthy reward.\""},
            },
        ],
    },
    
    "scholar_ancient": {
        "name": "Scholar Ancient",
        "title": "📚 Ancient Scholar",
        "discovery_hint": "A scholar deciphers ancient runes on a stone wall.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.09,
        "faction": "arcane_order",
        "introduction": {
            "text": (
                "The scholar looks up from deciphering runes with excitement.\n\n"
                "\"Ah! Another seeker of knowledge! I'm Scholar Ancient, keeper of old texts.\n"
                "I've been studying the ancient secrets in these depths.\n\n"
                "Help me clear out the threats, and I'll share my discoveries.\""
            ),
        },
        "quests": [
            {
                "id": "ancient_quest_1",
                "name": "Rune Study",
                "description": "Help the scholar study safely by clearing threats.",
                "level_req": 52,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 Dark Iron Sorcerers", "hint": "Sorcerers threaten the study sites.", "completion_check": {"type": "kill_enemy", "value": "dark_iron_sorcerer", "count": 8}},
                    {"step": 2, "objective": "Return to Scholar Ancient", "hint": "Use /interact ancient to report back.", "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"}},
                ],
                "rewards": {"xp": 13200, "gold": 6600, "items": ["flask_of_the_titans"], "reputation": {"arcane_order": 1320}},
                "dialogue": {"accept": "\"Good! Help me study safely.\"", "decline": "\"I understand. Study takes time.\"", "progress_1": "\"Keep going! The study sites are getting safer.\"", "completion": "\"Excellent! The sites are safe. Here's your reward.\""},
            },
            {
                "id": "ancient_quest_2",
                "name": "Ancient Sites",
                "description": "Clear threats from multiple ancient study sites.",
                "level_req": 54,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 Firelord Servants", "hint": "Servants guard ancient sites.", "completion_check": {"type": "kill_enemy", "value": "firelord_servant", "count": 9}},
                    {"step": 2, "objective": "Defeat 6 Magma Lords", "hint": "Magma lords also guard the sites.", "completion_check": {"type": "kill_enemy", "value": "magma_lord", "count": 6}},
                    {"step": 3, "objective": "Return to Scholar Ancient", "hint": "Use /interact ancient to report back.", "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"}},
                ],
                "rewards": {"xp": 17200, "gold": 8600, "items": ["shadowforge_plate"], "reputation": {"arcane_order": 1720}},
                "dialogue": {"accept": "\"The sites are dangerous! Clear them out.\"", "decline": "\"I understand. Sites are treacherous.\"", "progress_1": "\"Good work! Keep going.\"", "progress_2": "\"Excellent! The sites are getting safer.\"", "completion": "\"Wonderful! All sites are secure. Here's your reward.\""},
            },
            {
                "id": "ancient_quest_3",
                "name": "Complete Study",
                "description": "Complete the study by clearing all threats throughout Blackrock Depths.",
                "level_req": 57,
                "time_limit_hours": 96,
                "steps": [
                    {"step": 1, "objective": "Defeat 23 enemies in Blackrock Depths", "hint": "Clear all threats to complete the study.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 23}},
                    {"step": 2, "objective": "Return to Scholar Ancient", "hint": "Use /interact ancient to report back.", "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"}},
                ],
                "rewards": {"xp": 24500, "gold": 12250, "items": ["sulfuron_blade"], "reputation": {"arcane_order": 2450}},
                "dialogue": {"accept": "\"Complete the study! Finish this within 96 hours!\"", "decline": "\"I understand. This is extensive study.\"", "progress_1": "\"Keep fighting! The study is progressing.\"", "completion": "\"Incredible! The complete study is finished. All secrets are documented.\""},
            },
            {
                "id": "ancient_quest_4",
                "name": "The Ultimate Secret",
                "description": "Face the ultimate challenge: study the secret guarded by the Emperor.",
                "level_req": 59,
                "steps": [
                    {"step": 1, "objective": "Defeat 18 enemies in Blackrock Depths", "hint": "Prepare by clearing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 18}},
                    {"step": 2, "objective": "Defeat Emperor Dagran Thaurissan", "hint": "The Emperor guards the ultimate secret. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "emperor_dagran_thaurissan", "count": 1}},
                    {"step": 3, "objective": "Return to Scholar Ancient", "hint": "Use /interact ancient to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"}},
                ],
                "rewards": {"xp": 34500, "gold": 17250, "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"], "reputation": {"arcane_order": 3450}},
                "dialogue": {"accept": "\"The Emperor guards the ultimate secret! Defeat him!\"", "decline": "\"I understand. The Emperor is dangerous.\"", "progress_1": "\"Good preparation! Now face the Emperor.\"", "progress_2": "\"The Emperor is defeated! The ultimate secret is revealed! Return for your reward.\"", "completion": "\"Legendary! The ultimate secret is studied. Here's a worthy reward.\""},
            },
        ],
    },
    
    "paladin_light": {
        "name": "Paladin Light",
        "title": "✨ Lightbringer",
        "discovery_hint": "A paladin in glowing armor stands against the darkness.",
        "zones": ["blackrock_depths"],
        "discovery_chance": 0.10,
        "faction": "arcane_order",
        "introduction": {
            "text": (
                "The paladin turns to face you with a determined expression.\n\n"
                "\"The Light calls, adventurer! I am Paladin Light, servant of justice.\n"
                "The darkness in these depths must be cleansed.\n\n"
                "If you serve the Light, I have several missions for you.\""
            ),
        },
        "quests": [
            {
                "id": "light_quest_1",
                "name": "Light's Mission",
                "description": "Help the paladin cleanse the darkness.",
                "level_req": 51,
                "steps": [
                    {"step": 1, "objective": "Defeat 8 Flame Wraiths", "hint": "Wraiths represent the darkness.", "completion_check": {"type": "kill_enemy", "value": "flame_wraith", "count": 8}},
                    {"step": 2, "objective": "Return to Paladin Light", "hint": "Use /interact light to report back.", "completion_check": {"type": "talk_to_npc", "value": "paladin_light"}},
                ],
                "rewards": {"xp": 12600, "gold": 6300, "items": ["flask_of_the_titans"], "reputation": {"arcane_order": 1260}},
                "dialogue": {"accept": "\"The Light guides you. Go forth and cleanse the darkness.\"", "decline": "\"I understand. The Light will wait.\"", "progress_1": "\"Keep fighting! The darkness must be cleansed.\"", "completion": "\"Blessings upon you! The Light is stronger. Here's your reward.\""},
            },
            {
                "id": "light_quest_2",
                "name": "Dark Forces",
                "description": "Eliminate multiple types of dark forces.",
                "level_req": 53,
                "steps": [
                    {"step": 1, "objective": "Defeat 9 Fire Imps", "hint": "Imps are dark creatures.", "completion_check": {"type": "kill_enemy", "value": "fire_imp", "count": 9}},
                    {"step": 2, "objective": "Defeat 6 Lava Elementals", "hint": "Elementals are dark forces.", "completion_check": {"type": "kill_enemy", "value": "lava_elemental", "count": 6}},
                    {"step": 3, "objective": "Return to Paladin Light", "hint": "Use /interact light to report back.", "completion_check": {"type": "talk_to_npc", "value": "paladin_light"}},
                ],
                "rewards": {"xp": 16600, "gold": 8300, "items": ["shadowforge_plate"], "reputation": {"arcane_order": 1660}},
                "dialogue": {"accept": "\"The dark forces must be stopped! The Light demands it.\"", "decline": "\"I understand. Dark forces are dangerous.\"", "progress_1": "\"Keep fighting! The dark forces must be eliminated.\"", "completion": "\"Wonderful! The dark forces are diminished. Here's your reward.\""},
            },
            {
                "id": "light_quest_3",
                "name": "Depths Cleansing",
                "description": "Cleanse the entire depths by clearing all dark forces.",
                "level_req": 56,
                "time_limit_hours": 96,
                "steps": [
                    {"step": 1, "objective": "Defeat 22 enemies in Blackrock Depths", "hint": "Cleanse all dark forces from the depths.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 22}},
                    {"step": 2, "objective": "Return to Paladin Light", "hint": "Use /interact light to report back.", "completion_check": {"type": "talk_to_npc", "value": "paladin_light"}},
                ],
                "rewards": {"xp": 23500, "gold": 11750, "items": ["sulfuron_blade"], "reputation": {"arcane_order": 2350}},
                "dialogue": {"accept": "\"Cleanse the depths! Complete this within 96 hours!\"", "decline": "\"I understand. This is extensive work.\"", "progress_1": "\"Keep fighting! The depths need cleansing.\"", "completion": "\"Incredible! The depths are cleansed. The Light shines brighter.\""},
            },
            {
                "id": "light_quest_4",
                "name": "The Ultimate Darkness",
                "description": "Face the ultimate darkness: defeat the Emperor.",
                "level_req": 59,
                "steps": [
                    {"step": 1, "objective": "Defeat 17 enemies in Blackrock Depths", "hint": "Prepare by cleansing regular enemies first.", "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 17}},
                    {"step": 2, "objective": "Defeat Emperor Dagran Thaurissan", "hint": "The Emperor is the ultimate darkness. Use /fight to challenge him.", "completion_check": {"type": "kill_enemy", "value": "emperor_dagran_thaurissan", "count": 1}},
                    {"step": 3, "objective": "Return to Paladin Light", "hint": "Use /interact light to claim your reward.", "completion_check": {"type": "talk_to_npc", "value": "paladin_light"}},
                ],
                "rewards": {"xp": 35000, "gold": 17500, "items": ["sulfuron_blade", "shadowforge_plate", "flask_of_the_titans"], "reputation": {"arcane_order": 3500}},
                "dialogue": {"accept": "\"The Emperor is the ultimate darkness! Defeat him in the Light's name!\"", "decline": "\"I understand. The ultimate darkness is dangerous.\"", "progress_1": "\"Good preparation! Now face the Emperor.\"", "progress_2": "\"The Emperor is defeated! The Light triumphs! Return for your reward.\"", "completion": "\"Legendary! You've banished the ultimate darkness. The Light rewards you.\""},
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
        # FIX: Include both 'active' and 'offered' quests (offered quests should still track progress)
        active = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id = $1 AND state IN ('active', 'offered')",
            char_id,
        )
        notifications = []

        for row in active:
            # Auto-activate offered quests when progress starts
            if row["state"] == "offered":
                await self.db.execute(
                    "UPDATE quest_progress SET state = 'active', started_at = NOW() WHERE character_id = $1 AND quest_id = $2",
                    char_id, row["quest_id"],
                )
                row = dict(row)
                row["state"] = "active"

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
                log.warning(f"Quest template not found for quest_id: {row['quest_id']}")
                continue

            step_idx = row["current_step"] - 1
            if step_idx >= len(quest_data["steps"]):
                continue

            step = quest_data["steps"][step_idx]
            check = step["completion_check"]
            advanced = False

            # FIX: Properly parse JSONB metadata (handles dict, string, None cases)
            import json
            meta = row.get("metadata")
            if meta is None:
                meta = {}
            elif isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            elif not isinstance(meta, dict):
                meta = {}

            # Track if we need to update metadata
            metadata_updated = False

            # DEBUG: Log what we're checking
            log.debug(f"Quest {row['quest_id']}: checking kill_enemy={check['type']=='kill_enemy'}, enemy_key={enemy_key}, check_value={check.get('value')}, zone={zone_key}")

            if check["type"] == "kill_enemy" and check["value"] == enemy_key:
                needed = check.get("count", 1)
                kill_key = f"kills_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills
                metadata_updated = True
                log.info(f"Quest {row['quest_id']}: Kill tracked! {current_kills}/{needed} for {enemy_key}")
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
                metadata_updated = True
                log.info(f"Quest {row['quest_id']}: Zone kill tracked! {current_kills}/{needed} in {zone_key}")
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
                metadata_updated = True
                log.info(f"Quest {row['quest_id']}: Boss kill tracked! {current_kills}/{needed} in {zone_key}")
                if current_kills >= needed:
                    advanced = True
                    notifications.append(f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!")
                else:
                    notifications.append(f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})")

            # FIX: Re-fetch metadata right before updating to avoid race conditions
            # This ensures we have the latest kill counts even if multiple kills happen quickly
            if metadata_updated:
                fresh_row = await self.db.fetchrow(
                    "SELECT metadata FROM quest_progress WHERE character_id = $1 AND quest_id = $2",
                    char_id, row["quest_id"]
                )
                if fresh_row and fresh_row.get("metadata"):
                    fresh_meta = fresh_row["metadata"]
                    if isinstance(fresh_meta, str):
                        try:
                            fresh_meta = json.loads(fresh_meta)
                        except (json.JSONDecodeError, TypeError):
                            fresh_meta = {}
                    elif not isinstance(fresh_meta, dict):
                        fresh_meta = {}
                    # Merge with our updates (preserve any concurrent updates)
                    for key, value in meta.items():
                        # For kill counters, take the maximum to avoid losing progress
                        if key.startswith("kills_") or key.startswith("boss_kills_"):
                            fresh_meta[key] = max(fresh_meta.get(key, 0), value)
                        else:
                            fresh_meta[key] = value
                    meta = fresh_meta

            # Save metadata (only save if we updated it)
            if metadata_updated:
                await self.db.execute(
                    "UPDATE quest_progress SET metadata = $3::jsonb WHERE character_id = $1 AND quest_id = $2",
                    char_id, row["quest_id"], json.dumps(meta),
                )
            if advanced:
                await self.advance_quest(char_id, row["quest_id"])

        return notifications

    async def check_kill_progress_events(
        self, char_id: UUID, enemy_key: str, zone_key: str, is_boss: bool
    ) -> Dict:
        """
        Like check_kill_progress(), but also returns structured events so callers
        (Discord cogs, Activity, etc.) can react (DMs, reward granting).

        Returns:
          {
            "notifications": list[str],
            "step_updates": list[{"quest_id": str, "quest_data": dict, "next_step": dict}],
            "completed": list[{"quest_id": str, "quest_data": dict, "npc_id": str, "rewards": dict}],
          }
        """
        # Include both 'active' and 'offered' so offered quests can progress.
        active = await self.db.fetch(
            "SELECT * FROM quest_progress WHERE character_id = $1 AND state IN ('active', 'offered')",
            char_id,
        )

        notifications: List[str] = []
        step_updates: List[Dict] = []
        completed: List[Dict] = []

        import json

        for row in active:
            # Auto-activate offered quests when progress starts
            if row["state"] == "offered":
                await self.db.execute(
                    "UPDATE quest_progress SET state = 'active', started_at = NOW() WHERE character_id = $1 AND quest_id = $2",
                    char_id, row["quest_id"],
                )
                row = dict(row)
                row["state"] = "active"

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
                log.warning(f"Quest template not found for quest_id: {row['quest_id']}")
                continue

            total_steps = len(quest_data.get("steps") or [])
            if total_steps <= 0:
                continue

            step_idx = row["current_step"] - 1
            if step_idx < 0 or step_idx >= total_steps:
                continue

            step = quest_data["steps"][step_idx]
            check = step["completion_check"]
            advanced = False

            # Parse JSONB metadata (dict, string, None cases)
            meta = row.get("metadata")
            if meta is None:
                meta = {}
            elif isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            elif not isinstance(meta, dict):
                meta = {}

            metadata_updated = False

            if check["type"] == "kill_enemy" and check["value"] == enemy_key:
                needed = check.get("count", 1)
                kill_key = f"kills_{check['value']}"
                current_kills = meta.get(kill_key, 0) + 1
                meta[kill_key] = current_kills
                metadata_updated = True
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
                metadata_updated = True
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
                metadata_updated = True
                if current_kills >= needed:
                    advanced = True
                    notifications.append(f"✅ Quest **{quest_data['name']}**: \"{step['objective']}\" — Complete!")
                else:
                    notifications.append(f"📋 Quest **{quest_data['name']}**: {step['objective']} ({current_kills}/{needed})")

            # Re-fetch metadata before updating to reduce race-condition loss
            if metadata_updated:
                fresh_row = await self.db.fetchrow(
                    "SELECT metadata FROM quest_progress WHERE character_id = $1 AND quest_id = $2",
                    char_id, row["quest_id"],
                )
                if fresh_row and fresh_row.get("metadata"):
                    fresh_meta = fresh_row["metadata"]
                    if isinstance(fresh_meta, str):
                        try:
                            fresh_meta = json.loads(fresh_meta)
                        except (json.JSONDecodeError, TypeError):
                            fresh_meta = {}
                    elif not isinstance(fresh_meta, dict):
                        fresh_meta = {}
                    for key, value in meta.items():
                        if key.startswith("kills_") or key.startswith("boss_kills_"):
                            fresh_meta[key] = max(fresh_meta.get(key, 0), value)
                        else:
                            fresh_meta[key] = value
                    meta = fresh_meta

                await self.db.execute(
                    "UPDATE quest_progress SET metadata = $3::jsonb WHERE character_id = $1 AND quest_id = $2",
                    char_id, row["quest_id"], json.dumps(meta),
                )

            if not advanced:
                continue

            # If this was the final step, auto-complete the quest right now.
            # This prevents "stuck" quests where the last step is a kill objective.
            if row["current_step"] >= total_steps:
                rewards = await self.complete_quest(char_id, row["quest_id"])
                if rewards:
                    completed.append(
                        {
                            "quest_id": row["quest_id"],
                            "quest_data": quest_data,
                            "npc_id": row["npc_id"],
                            "rewards": rewards,
                        }
                    )
                continue

            # Otherwise, advance to next step and report the new objective.
            ok = await self.advance_quest(char_id, row["quest_id"])
            if ok:
                next_idx = step_idx + 1
                if 0 <= next_idx < total_steps:
                    step_updates.append(
                        {
                            "quest_id": row["quest_id"],
                            "quest_data": quest_data,
                            "next_step": quest_data["steps"][next_idx],
                        }
                    )

        return {
            "notifications": notifications,
            "step_updates": step_updates,
            "completed": completed,
        }

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
