"""
Obsidian Silence — extra NPC intros and quest chains merged into NPC_TEMPLATES.

Lore spine: Graying (Vaelkor’s “mercy” as forced stillness) → proofs of motion →
Trisect Key → Architect’s fall. Optional quests deepen mood or gear the shard;
`description` tags **Main arc** vs **Optional** where it helps players (and reviewers).
See also config/lore_gates.py for boss gates.
"""

from __future__ import annotations

from typing import Any, Dict, List


def apply_obsidian_content(templates: Dict[str, Any]) -> None:
    """Merge Obsidian Silence intros and quests into NPC_TEMPLATES (in place)."""
    for npc_id, intro in INTRO_PATCHES.items():
        if npc_id in templates and isinstance(templates[npc_id].get("introduction"), dict):
            templates[npc_id]["introduction"]["text"] = intro

    for npc_id, extra_quests in OBSIDIAN_QUEST_PATCHES.items():
        if npc_id not in templates:
            continue
        q = templates[npc_id].get("quests")
        if not isinstance(q, list):
            templates[npc_id]["quests"] = []
        templates[npc_id]["quests"] = list(templates[npc_id]["quests"]) + list(extra_quests)


# ── Introduction overrides (Obsidian Silence tone) ─────────────────────────────

INTRO_PATCHES: Dict[str, str] = {
    "old_guard_marcus": (
        "The old soldier looks up, eyes like tired steel.\n\n"
        "\"Name's Marcus. I used to guard these roads when they still *moved*—when leaves rustled like an argument, not like a whisper.\n\n"
        "Something's wrong with the forest. Call it bandits if you need sleep. I call it the **Graying**.\n"
        "It spreads where **motion** gives up—like frost, but for time. Nobody's mapped a clean cure; "
        "cut the song at the heart, though, and the margin *stutters*… pulls back a breath.\n"
        "Help me hold the line, and I'll share what coin—and truth—I still have.\""
    ),
    "mage_apprentice": (
        "The apprentice clutches a cracked lens; ash dust glitters on their sleeves.\n\n"
        "\"Don't laugh—I'm measuring **silence**. The Graying isn't 'spooky'—it's *wrong math*.\n\n"
        "They say a **caldera architect** once proved that *frozen* worlds don't scream—"
        "I say that's theology dressed as physics. Bring me samples, blood, and honesty; "
        "I'll give you a tone that cuts glass—because out here, glass is starting to win.\""
    ),
    "guard_thomas": (
        "The young guard salutes too sharp, like fear wearing a uniform.\n\n"
        "\"Thomas. If you want stories, find a bard. I want **edges**—where the green goes ashy.\n\n"
        "Scout the border where the Graying creeps. Map it. Name it. Prove I'm not mad.\""
    ),
    "merchant_crossroads": (
        "The merchant counts coins without looking—eyes on the horizon.\n\n"
        "\"Crossroads hears everything. Freight hums. Wells go quiet wrong.\n\n"
        "The **Barrens** are the hinge—sand carries ash south. Then **Stranglethorn**: "
        "salt, glass, and old bargains. Find **Captain Seafoam**; he still remembers where **glass** is born "
        "and who pays for it.\""
    ),
    "captain_seafoam": (
        "The old pirate taps a glass tooth—grin like a warning.\n\n"
        "\"Seafoam. Retired—like the sea ever retires.\n\n"
        "I'll tell you where the glass comes from… after you prove you can sink a habit older than your kingdom.\""
    ),
    "shaman_tribal": (
        "The shaman's paint is salt-bright; their voice is low tide.\n\n"
        "\"The jungle signed treaties before your maps. The seal is not 'magic'—it's **memory**.\n\n"
        "**Kurzen** didn't just conquer—he *ate* a witness-spirit bound to our bloodline—a sea-memory "
        "that sealed the pact between jungle and salt. The spirit can't testify while it's *digested*; "
        "it stays locked in his gut. **Black-Blood Vance** is half-echo because the knot binds him to "
        "that stolen testimony. Kill Kurzen and the spirit returns—the knot breaks, and Vance becomes "
        "*whole* again. Then we have a true ally—or a true reckoning.\""
    ),
    "eldric_wanderer": (
        "A hooded figure steps from the heat-shimmer like a question. Burn scars lace their wrists—"
        "the kind you get from *arguing* with forges, not from battle.\n\n"
        "\"Eldric. I was an **Architect**—same office **Vaelkor** held before the Breaking. "
        "I kept the **Blackrock seal ledgers** until his edict rewrote them into lullabies. "
        "I walk thresholds: where law pretends to end and physics remembers it doesn't.\n\n"
        "Bring me three proofs of motion—cold steel, stored sun, salt edge—and I'll forge the **key** "
        "the volcano pretends it doesn't need. Keys don't open doors; they make doors *admit they exist*.\""
    ),
    "mage_fire": (
        "The mage writes equations in ash; each line steams.\n\n"
        "\"Fire is grammar. The Forge thinks it wrote the last sentence.\n\n"
        "Help me teach this mountain a new tense—**Flame-Infused**—before stillness becomes law.\""
    ),
    "priest_lightbringer": (
        "The priest presses a thumb to your forehead—blessing like a brand.\n\n"
        "\"Stillness is not peace. Peace is *choice*, repeated.\n\n"
        "Let me bless your blade so it remembers **mercy that moves**.\""
    ),
    "scholar_ancient": (
        "Runes crawl under the scholar's fingernails like living ink.\n\n"
        "\"I don't read stone. I argue with it.\n\n"
        "**Vaelkor** called the Graying *mercy*: freeze the world's hurt so nothing changes, nothing fails, nothing mourns. "
        "I call it **taxidermy**. He wore **sentences** for armor—I'll show you where the grammar breaks… "
        "if you translate the **coastal cipher** first. The jungle tablets are copies; Blackrock is the original draft.\""
    ),
}


# ── Additional quests (appended per NPC) ─────────────────────────────────────

OBSIDIAN_QUEST_PATCHES: Dict[str, List[Dict[str, Any]]] = {
    "mage_apprentice": [
        {
            "id": "obsidian_shatter_tone",
            "name": "The Shatter-Tone",
            "description": "**Main arc — Act 1:** Gather field data on the Graying and receive a tuning fork that can fracture glass-stillness.",
            "level_req": 2,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 4 Defias Bandits (samples for resonance)",
                    "hint": "Bandits prowl Elwynn roads.",
                    "completion_check": {"type": "kill_enemy", "value": "defias_bandit", "count": 4},
                },
                {
                    "step": 2,
                    "objective": "Return to the Mage Apprentice",
                    "hint": "Use /interact with the apprentice.",
                    "completion_check": {"type": "talk_to_npc", "value": "mage_apprentice"},
                },
            ],
            "rewards": {
                "xp": 650,
                "gold": 220,
                "items": ["shatter_tone_tuning_fork"],
                "reputation": {"stormwind_guard": 200},
                "deed_flags": ["has_shatter_tone_fork"],
            },
            "dialogue": {
                "accept": (
                    "\"Good. I need ash-resin and panic in equal measure.\n"
                    "Bring me bandit counts—then I'll give you a **note** that bites glass.\""
                ),
                "decline": "\"Fine. Silence loves patience.\"",
                "progress_1": "\"Keep going—samples first, poetry later.\"",
                "completion": (
                    "\"Here—the **Shatter-Tone Tuning Fork**. One clean strike, one honest fracture.\n"
                    "Don't swing at statues. *Ring* them.\""
                ),
            },
        },
        {
            "id": "obsidian_gorgoth_slayer",
            "name": "The Petrified Bear",
            "description": "**Main arc — Act 1:** Face Gorgoth the Petrified—use the Shatter-Tone or your blows will mean nothing.",
            "level_req": 4,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat Gorgoth the Petrified in Elwynn Forest",
                    "hint": "Use /fight — you need the tuning fork's resonance (complete The Shatter-Tone).",
                    "completion_check": {"type": "kill_enemy", "value": "gorgoth_petrified", "count": 1},
                },
                {
                    "step": 2,
                    "objective": "Return to the Mage Apprentice",
                    "hint": "Use /interact apprentice.",
                    "completion_check": {"type": "talk_to_npc", "value": "mage_apprentice"},
                },
            ],
            "rewards": {
                "xp": 1800,
                "gold": 600,
                "items": ["the_dull_shard"],
                "reputation": {"stormwind_guard": 400},
                "deed_flags": ["gorgoth_defeated", "dull_shard_awarded"],
            },
            "dialogue": {
                "accept": (
                    "\"That bear isn't wildlife—it's a **monument** with teeth.\n"
                    "The fork makes it *honest*. Finish it, and bring me proof that stillness bleeds.\""
                ),
                "decline": "\"Then stay a tourist.\"",
                "progress_1": "\"Don't pity it. Mercy is a clean kill.\"",
                "completion": (
                    "\"You heard it crack—good.\n\n"
                    "Take **The Dull Shard**. It's not pretty. It's a *question* forged in glass.\""
                ),
            },
        },
    ],
    "old_guard_marcus": [
        {
            "id": "obsidian_marcus_recommendation",
            "name": "Marcus's Recommendation",
            "description": "**Main arc — Act 2 bridge:** Marcus hears of your deeds through Grimbeard and officially endorses your mountain approach.",
            "level_req": 8,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 8 enemies in Elwynn Forest (recon work)",
                    "hint": "Marcus needs proof of your reliability.",
                    "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 8},
                },
                {
                    "step": 2,
                    "objective": "Return to Marcus",
                    "hint": "/interact marcus",
                    "completion_check": {"type": "talk_to_npc", "value": "old_guard_marcus"},
                },
            ],
            "rewards": {
                "xp": 1500,
                "gold": 500,
                "items": [],
                "reputation": {"stormwind_guard": 300},
                "deed_flags": ["marcus_recommendation"],
            },
            "dialogue": {
                "accept": "\"Grimbeard says you're *honest*. That's rare. Earn my word.\"",
                "decline": "\"Fine. I'll guard this alone.\"",
                "progress_1": "\"Keep proving yourself.\"",
                "completion": "\"You've got it. Tell Steelhammer the **Old Guard endorses you**—the mountain trusts what you're building.\"",
            },
        },
    ],
    "guard_thomas": [
        {
            "id": "obsidian_scout_gray_border",
            "name": "Scout the Gray Border",
            "description": "**Optional:** Map the Graying's edge in Elwynn—confirms lore; charm is a side trinket, not required for any lore boss gate.",
            "level_req": 3,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 8 enemies in Elwynn Forest (patrol the Graying)",
                    "hint": "Clear threats along the ashen margin.",
                    "completion_check": {"type": "kill_any_zone", "value": "elwynn_forest", "count": 8},
                },
                {
                    "step": 2,
                    "objective": "Return to Guard Thomas",
                    "hint": "/interact thomas",
                    "completion_check": {"type": "talk_to_npc", "value": "guard_thomas"},
                },
            ],
            "rewards": {
                "xp": 900,
                "gold": 320,
                "items": ["gray_border_charm"],
                "reputation": {"stormwind_guard": 280},
                "deed_flags": ["scout_gray_border_done"],
            },
            "dialogue": {
                "accept": (
                    "\"If we don't measure it, Marcus will—by rumor. This pairs with the apprentice's **fork** work—"
                    "same war, different instruments. Go.\""
                ),
                "decline": "\"Then we march blind.\"",
                "progress_1": "\"Keep the perimeter honest.\"",
                "completion": (
                    "\"A line on a map… and a weight off my chest.\n"
                    "Take this charm—**cold glass** still hates warmth.\""
                ),
            },
        },
    ],
    "warrior_grimbeard": [
        {
            "id": "obsidian_khaz_dispatch",
            "name": "Dispatch for Khaz Modan",
            "description": "**Main arc — Act 2 bridge:** Thomas's Gray-border report reaches Grimbeard—proves Elwynn's ash is real so Dun Morogh arms the mountain war.",
            "level_req": 5,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 6 Troggs in Dun Morogh",
                    "hint": "Troggs infest the lower slopes.",
                    "completion_check": {"type": "kill_enemy", "value": "trogg", "count": 6},
                },
                {
                    "step": 2,
                    "objective": "Return to Warrior Grimbeard",
                    "hint": "/interact grimbeard",
                    "completion_check": {"type": "talk_to_npc", "value": "warrior_grimbeard"},
                },
            ],
            "rewards": {
                "xp": 1200,
                "gold": 450,
                "items": ["health_potion"],
                "reputation": {"dwarven_explorers": 350},
                "deed_flags": ["grimbeard_dispatch_ack"],
            },
            "dialogue": {
                "accept": "\"Elwynn sends ash and calls it poetry? Fine—show me work.\"",
                "decline": "\"Then crawl home.\"",
                "progress_1": "\"Break troggs—then we'll talk geology.\"",
                "completion": (
                    "\"Good. The mountain respects sweat. Word travels south—the **Barrens** hinge between our peaks "
                    "and the jungle. Find **Bloodfang**; the desert's already moving.\""
                ),
            },
        },
    ],
    "blacksmith_steelhammer": [
        {
            "id": "obsidian_seismic_trigger",
            "name": "Seismic Trigger",
            "description": "**Main arc — Act 2:** Arm a bedrock spike network to stagger Kaelen-Tor's stabilizers before the depths push.",
            "level_req": 8,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 10 enemies in Dun Morogh (clear dig-site interference)",
                    "hint": "Any foes count toward clearing the approach.",
                    "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 10},
                },
                {
                    "step": 2,
                    "objective": "Return to Blacksmith Steelhammer",
                    "hint": "/interact steelhammer",
                    "completion_check": {"type": "talk_to_npc", "value": "blacksmith_steelhammer"},
                },
            ],
            "rewards": {
                "xp": 2200,
                "gold": 800,
                "items": ["seismic_trigger_kit"],
                "reputation": {"dwarven_explorers": 500},
                "deed_flags": ["seismic_trigger_complete"],
            },
            "dialogue": {
                "accept": (
                    "\"You want Marcus's word on paper? I want **spikes in stone**.\n"
                    "Clear the yard—then I'll arm the trigger.\""
                ),
                "decline": "\"Come back with a spine.\"",
                "progress_1": "\"Still noisy? Good. Noise means motion.\"",
                "completion": (
                    "\"**Seismic Trigger**—one honest punch through rock.\n"
                    "Fire it before you poke the drill—or you're polishing its teeth.\""
                ),
            },
        },
    ],
    "miner_ironforge": [
        {
            "id": "obsidian_deep_rock_rescue",
            "name": "Deep Rock Rescue",
            "description": "**Optional:** Rescue stranded miners before the shaft goes still—tightens Dun Morogh mood; parallel to the seismic line.",
            "level_req": 6,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 12 enemies in Dun Morogh",
                    "hint": "Clear threats around the compromised tunnels.",
                    "completion_check": {"type": "kill_any_zone", "value": "dun_morogh", "count": 12},
                },
                {
                    "step": 2,
                    "objective": "Return to Miner Ironforge",
                    "hint": "/interact ironforge",
                    "completion_check": {"type": "talk_to_npc", "value": "miner_ironforge"},
                },
            ],
            "rewards": {
                "xp": 1600,
                "gold": 620,
                "items": ["glacial_fang", "deep_rock_token"],
                "reputation": {"dwarven_explorers": 420},
                "deed_flags": ["deep_rock_rescue_done"],
            },
            "dialogue": {
                "accept": "\"Headcounts, not hero speeches.\"",
                "decline": "\"Then stay topside.\"",
                "progress_1": "\"Still breathing? Keep going.\"",
                "completion": "\"That's the count I wanted. Don't make me do it again.\"",
            },
        },
    ],
    "wandering_merchant": [
        {
            "id": "obsidian_manifest_destiny",
            "name": "Manifest Destiny",
            "description": "**Main arc — Act 2:** Intercept a Barrens caravan—ash and grit routed south toward Stranglethorn's glass trade.",
            "level_req": 12,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 15 enemies in The Barrens",
                    "hint": "Caravan guards won't yield quietly.",
                    "completion_check": {"type": "kill_any_zone", "value": "barrens", "count": 15},
                },
                {
                    "step": 2,
                    "objective": "Return to Kira",
                    "hint": "/interact kira",
                    "completion_check": {"type": "talk_to_npc", "value": "wandering_merchant"},
                },
            ],
            "rewards": {
                "xp": 2800,
                "gold": 1100,
                "items": ["sun_scorched_scimitar"],
                "reputation": {"trade_coalition": 500},
                "deed_flags": ["manifest_destiny_done"],
            },
            "dialogue": {
                "accept": "\"Destiny's a pretty word for *somebody paid for tomorrow.*\"",
                "decline": "\"Then keep your eyes shut.\"",
                "progress_1": "\"Still alive? Cute.\"",
                "completion": "\"Good. If the sand hums, that's not trade—that's a schedule.\"",
            },
        },
    ],
    "warrior_bloodfang": [
        {
            "id": "obsidian_bloodfang_duel",
            "name": "Bait and Blood",
            "description": "**Main arc — Act 2:** Ritual blood-price so the Barrens *notices* you—opens the Stranglethorn hunt for Vance and the salt-knot.",
            "level_req": 14,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 8 Razormane Warriors in The Barrens",
                    "hint": "Prove strength before the duel.",
                    "completion_check": {"type": "kill_enemy", "value": "razormane_warrior", "count": 8},
                },
                {
                    "step": 2,
                    "objective": "Return to Warrior Bloodfang",
                    "hint": "/interact bloodfang",
                    "completion_check": {"type": "talk_to_npc", "value": "warrior_bloodfang"},
                },
            ],
            "rewards": {
                "xp": 2400,
                "gold": 900,
                "items": ["health_potion"],
                "reputation": {"trade_coalition": 450},
                "deed_flags": ["bait_placed"],
            },
            "dialogue": {
                "accept": "\"You want the oasis-eater? Prove blood means something.\"",
                "decline": "\"Soft.\"",
                "progress_1": "\"More.\"",
                "completion": (
                    "\"Good. The desert wrote your name in salt.\n\n"
                    "**Black-Blood Vance** will smell it in Stranglethorn—he always collects blood-debts. "
                    "Go south; the shaman holds the *legal* side of the hunt, but Vance is the blade that answers. "
                    "The jungle remembers old debts—**Kurzen** guards the witness they need.\""
                ),
            },
        },
    ],
    "captain_seafoam": [
        {
            "id": "obsidian_ghost_ship_sunk",
            "name": "Ghost Ship Sunk",
            "description": "**Optional:** Break a spectral hull—grants a salt compass (stat trinket only, no progression gate). Side content for Stranglethorn depth.",
            "level_req": 28,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 20 enemies in Stranglethorn Vale",
                    "hint": "Jungle and coast breed endless fights—use them as your boarding action.",
                    "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 20},
                },
                {
                    "step": 2,
                    "objective": "Return to Captain Seafoam",
                    "hint": "/interact seafoam",
                    "completion_check": {"type": "talk_to_npc", "value": "captain_seafoam"},
                },
            ],
            "rewards": {
                "xp": 4500,
                "gold": 1800,
                "items": ["salt_true_compass"],
                "reputation": {"pirate_fleet": 600},
                "deed_flags": ["ghost_ship_sunk_done"],
            },
            "dialogue": {
                "accept": "\"That ship ain't a rumor—it's a habit with a hull.\"",
                "decline": "\"Stay in port.\"",
                "progress_1": "\"More salt on your boots.\"",
                "completion": "\"Good. Now we talk glass without lying.\"",
            },
        },
    ],
    "shaman_tribal": [
        {
            "id": "obsidian_curse_lifted",
            "name": "Salt-Knot Severed",
            "description": "**Main arc — Act 2:** Kill Kurzen so the stolen witness-spirit returns; then the shaman can sever the knot that veils **Black-Blood Vance**.",
            "level_req": 30,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat Kurzen the Mad",
                    "hint": "A worthy spirit-offering for the tide.",
                    "completion_check": {"type": "kill_enemy", "value": "kurzen_the_mad", "count": 1},
                },
                {
                    "step": 2,
                    "objective": "Return to Shaman Tribal",
                    "hint": "/interact shaman",
                    "completion_check": {"type": "talk_to_npc", "value": "shaman_tribal"},
                },
            ],
            "rewards": {
                "xp": 5000,
                "gold": 2000,
                "items": ["tribal_seal_charm"],
                "reputation": {"pirate_fleet": 550},
                "deed_flags": ["voodoo_curse_lifted"],
            },
            "dialogue": {
                "accept": (
                    "\"The knot wants blood that remembers the sea—and **Kurzen** is the cork.\n"
                    "While he hoards our witness, Vance stays half-echo. Spill the madman; the tide gets its verdict back.\""
                ),
                "decline": "\"Then stay cursed.\"",
                "progress_1": "\"The tide listens…\"",
                "completion": (
                    "\"Cut. The witness returned—**Vance** can stand in one place now.\n"
                    "Find him where salt and jungle argue; he'll know your blood from Bloodfang's mark. "
                    "Beyond lies **Blackrock**—the caldera holds the grammar even he can't rewrite.\""
                ),
            },
        },
        {
            "id": "silence_blackblood_vance",
            "name": "Black-Blood's Wrath",
            "description": "**Optional boss:** Vance is whole now—answer his blood-debt in Stranglethorn (requires Barrens bait + Salt-Knot).",
            "level_req": 28,
            "requires_deed_flags": ["voodoo_curse_lifted", "bait_placed"],
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat Black-Blood Vance in Stranglethorn Vale",
                    "hint": "Use /fight — lore-gated jungle boss.",
                    "completion_check": {"type": "kill_enemy", "value": "black_blood_vance", "count": 1},
                },
                {
                    "step": 2,
                    "objective": "Return to Shaman Tribal",
                    "hint": "/interact shaman",
                    "completion_check": {"type": "talk_to_npc", "value": "shaman_tribal"},
                },
            ],
            "rewards": {
                "xp": 6000,
                "gold": 2500,
                "items": ["vance_blood_token"],
                "reputation": {"pirate_fleet": 400},
                "deed_flags": ["vance_defeated"],
            },
            "dialogue": {
                "accept": "\"He's *whole* now—dangerous and honest. Pay the debt in blood, or he'll collect it in sleep.\"",
                "decline": "\"Then don't meet him.\"",
                "progress_1": "\"Salt remembers every cut.\"",
                "completion": (
                    "\"Good. The echo became a man—and you reminded him what men cost. "
                    "Keep the token; the sea won't forget either way.\""
                ),
            },
        },
    ],
    "archaeologist_ruins": [
        {
            "id": "obsidian_cipher_translated",
            "name": "Ancient Runes Read",
            "description": "**Main arc — Act 2→3:** Translate Stranglethorn coastal ciphers—duplicates of Blackrock margin-notes the scholar can't safely touch yet.",
            "level_req": 40,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 25 enemies in Stranglethorn Vale",
                    "hint": "Gather rubbings and blood-price in one motion.",
                    "completion_check": {"type": "kill_any_zone", "value": "stranglethorn", "count": 25},
                },
                {
                    "step": 2,
                    "objective": "Return to the Archaeologist",
                    "hint": "/interact archaeologist",
                    "completion_check": {"type": "talk_to_npc", "value": "archaeologist_ruins"},
                },
            ],
            "rewards": {
                "xp": 8000,
                "gold": 3200,
                "items": ["cipher_scroll", "tide_cutter"],
                "reputation": {"pirate_fleet": 700},
                "deed_flags": ["cipher_translated"],
            },
            "dialogue": {
                "accept": (
                    "\"I didn't *guess* Vaelkor's grammar—I **excavated** it.\n\n"
                    "When **the Graying** first crept from Blackrock, the coastal temples *copied* the warnings—"
                    "they carved his sigils into stone thinking it was a *curse* they could study. "
                    "But those sigils? They're his **notes**—his justifications. His arithmetic of mercy. "
                    "By reading the temples, I read him. And now you will too.\n\n"
                    "Wrong steps aren't death—they're *preservation.*\""
                ),
                "decline": "\"Enjoy the museum.\"",
                "progress_1": "\"More samples. Less swagger.\"",
                "completion": (
                    "\"There—**translated**. Same hand as the caldera inscriptions; the scholar will feel it instantly.\n"
                    "The mountain listens for this frequency—walk in tune or walk into teeth.\""
                ),
            },
        },
    ],
    "mage_fire": [
        {
            "id": "obsidian_flame_infused",
            "name": "Flame-Infused",
            "description": "**Main arc — Act 3:** Channel forge-heat into The Dull Shard so the Stasis cannot finish digesting it.",
            "level_req": 52,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat Lord Incendius",
                    "hint": "A worthy furnace trial.",
                    "completion_check": {"type": "kill_enemy", "value": "lord_incendius", "count": 1},
                },
                {
                    "step": 2,
                    "objective": "Return to Mage Fire",
                    "hint": "/interact mage_fire",
                    "completion_check": {"type": "talk_to_npc", "value": "mage_fire"},
                },
            ],
            "rewards": {
                "xp": 12000,
                "gold": 5000,
                "items": ["ember_thread"],
                "reputation": {"arcane_order": 800},
                "deed_flags": ["flame_infused_done"],
            },
            "dialogue": {
                "accept": "\"Fire isn't rage. It's grammar.\"",
                "decline": "\"Then stay cold.\"",
                "progress_1": "\"Heat it until it argues.\"",
                "completion": "\"Good. It remembers heat—**wrong kind of memory**, the right kind for us.\"",
            },
        },
    ],
    "priest_lightbringer": [
        {
            "id": "obsidian_holy_blessing",
            "name": "Holy Blessing",
            "description": "**Optional:** Anchor The Dull Shard with light magic—grants blessed oil (flavor/consumable). No effect on main progression; skip freely.",
            "level_req": 5,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 6 Defias Bandits",
                    "hint": "Blood for the blessing—mercy with teeth.",
                    "completion_check": {"type": "kill_enemy", "value": "defias_bandit", "count": 6},
                },
                {
                    "step": 2,
                    "objective": "Return to Priest Lightbringer",
                    "hint": "/interact priest",
                    "completion_check": {"type": "talk_to_npc", "value": "priest_lightbringer"},
                },
            ],
            "rewards": {
                "xp": 1100,
                "gold": 400,
                "items": ["blessed_oil_vial"],
                "reputation": {"stormwind_guard": 300},
                "deed_flags": ["holy_blessing_done"],
            },
            "dialogue": {
                "accept": "\"A holy blade isn't clean. It's chosen.\"",
                "decline": "\"Then stay dull.\"",
                "progress_1": "\"Purify the road.\"",
                "completion": "\"Go—rough enough to hold truth.\"",
            },
        },
    ],
    "scholar_ancient": [
        {
            "id": "obsidian_ancient_runes_read",
            "name": "Ancient Runes Read (Vaelkor)",
            "description": "**Main arc — Act 3:** Strip Vaelkor's armor-sigils—requires the coastal cipher and throne-fire lessons to read him true.",
            "level_req": 55,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat Emperor Dagran Thaurissan",
                    "hint": "Power near the Throne teaches the old grammar.",
                    "completion_check": {"type": "kill_enemy", "value": "emperor_dagran_thaurissan", "count": 1},
                },
                {
                    "step": 2,
                    "objective": "Return to Scholar Ancient",
                    "hint": "/interact scholar",
                    "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"},
                },
            ],
            "rewards": {
                "xp": 15000,
                "gold": 6000,
                "items": ["rune_rubbing_kit", "obsidian_breaker"],
                "reputation": {"arcane_order": 900},
                "deed_flags": ["ancient_runes_read_done"],
            },
            "dialogue": {
                "accept": "\"He wore sentences. I'll make them stutter.\"",
                "decline": "\"Enjoy being polished.\"",
                "progress_1": "\"More data. Less poetry.\"",
                "completion": "\"There—hit him where grammar fails.\"",
            },
        },
        {
            "id": "obsidian_architects_burden",
            "name": "The Architect's Burden",
            "description": "**Main arc — Act 3 context:** After translating the cipher—read what Vaelkor carved into Blackrock before you face him.",
            "level_req": 52,
            "requires_deed_flags": ["cipher_translated"],
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 10 enemies in Blackrock Depths (gather fragments of memory)",
                    "hint": "The stone remembers what Vaelkor tried to forget.",
                    "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 10},
                },
                {
                    "step": 2,
                    "objective": "Return to Scholar Ancient with the impressions",
                    "hint": "/interact scholar — hear the Architect's own verdict on mercy.",
                    "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"},
                },
            ],
            "rewards": {
                "xp": 8000,
                "gold": 3000,
                "items": [],
                "reputation": {"arcane_order": 700},
                "deed_flags": ["vaelkor_motivation_learned"],
            },
            "dialogue": {
                "accept": "\"He wrote it in stone—his reasons. Listen, and understand what mercy killed.\"",
                "decline": "\"Then fight a myth.\"",
                "progress_1": "\"The depths still echo him—keep listening.\"",
                "completion": (
                    "\"**Vaelkor** was an Architect—one of the old keepers of the threshold. "
                    "He watched the world change, *hurt*, *fail*—so he forged the Graying to make it *still*. "
                    "Not cruelty. *Mercy*. An endless sleep for a world too tired to wake.\n\n"
                    "Now you know why he built it. Now you can choose whether to break it.\""
                ),
            },
        },
        {
            "id": "silence_stillness_codex",
            "name": "The Stillness Codex",
            "description": "**Optional lore:** How the Graying spreads, anchors, and falls quiet—no gate items.",
            "level_req": 35,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 15 enemies in Blackrock Depths",
                    "hint": "The scholar reads the deepest scratches.",
                    "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 15},
                },
                {
                    "step": 2,
                    "objective": "Speak with Scholar Ancient",
                    "hint": "/interact scholar",
                    "completion_check": {"type": "talk_to_npc", "value": "scholar_ancient"},
                },
            ],
            "rewards": {
                "xp": 5000,
                "gold": 2000,
                "items": [],
                "reputation": {"arcane_order": 400},
                "deed_flags": ["graying_codex_learned"],
            },
            "dialogue": {
                "accept": "\"You want to understand the enemy. Smart.\"",
                "decline": "\"Ignorance is quieter.\"",
                "progress_1": "\"More bodies, more data.\"",
                "completion": (
                    "\"The **Graying** is **Vaelkor's will** made physical—a spreading stillness that freezes time and motion. "
                    "It *does* spread: slowly, like frost on glass. But it **requires an anchor**—Vaelkor conducting it. "
                    "Without him, the stillness can't *think*; it can't *spread*. "
                    "It can be *pushed back* by proof of motion—that's your three proofs and the key. "
                    "Destroy the conductor, and the music stops. What remains is **inert** ash and stone—not living malice.\""
                ),
            },
        },
    ],
    "eldric_wanderer": [
        {
            "id": "obsidian_trisect_key",
            "name": "The Trisect Key",
            "description": "**Main arc — climax key:** Prove motion in Blackrock Depths; Eldric forges the Trisect Key from your three proofs (Glacial Fang, Sun-Scorched Scimitar, Tide-Cutter).",
            "level_req": 50,
            "required_items": ["glacial_fang", "sun_scorched_scimitar", "tide_cutter"],
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 15 enemies in Blackrock Depths",
                    "hint": "Clear a path through the forge-clergy.",
                    "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 15},
                },
                {
                    "step": 2,
                    "objective": "Speak with Eldric at the threshold",
                    "hint": "/interact eldric",
                    "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                },
            ],
            "rewards": {
                "xp": 5000,
                "gold": 2000,
                "items": ["trisect_key"],
                "reputation": {"arcane_order": 600},
                "deed_flags": ["trisect_key_forged"],
            },
            "dialogue": {
                "accept": (
                    "\"Three proofs of motion. You understand now?\n\n"
                    "Vaelkor's Graying is pure **stillness**—the opposite of change, heat, flow. "
                    "Your three proofs are its inverse: **ice that endures through time** (Glacial Fang—cold that *remembers*), "
                    "**heat that burns against entropy** (Sun-Scorched Scimitar—fire that refuses ash), "
                    "**salt that flows even when frozen** (Tide-Cutter—water's stubborn motion). "
                    "Together, they forge a key that proves motion is **unkillable**. "
                    "That's what breaks Vaelkor—not violence, but contradiction. Let's make it.\""
                ),
                "decline": "\"Then stay outside the frequency.\"",
                "progress_1": "\"Still breathing? Good. Frequency hates cowards.\"",
                "completion": (
                    "\"**The Trisect Key**—not pretty. **Honest**.\n"
                    "The volcano will hear you coming… and hate it.\""
                ),
            },
        },
        {
            "id": "obsidian_eternal_frequency",
            "name": "The Eternal Frequency",
            "description": "**Main arc — finale:** Slay Vaelkor; the Graying loses its conductor—edges fray, motion returns in waves, not overnight.",
            "level_req": 58,
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat Vaelkor the Architect",
                    "hint": "The final caldera horror—use /fight in Blackrock.",
                    "completion_check": {"type": "kill_enemy", "value": "vaelkor_architect", "count": 1},
                },
                {
                    "step": 2,
                    "objective": "Return to Eldric",
                    "hint": "/interact eldric",
                    "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                },
            ],
            "rewards": {
                "xp": 50000,
                "gold": 20000,
                "items": ["the_eternal_frequency"],
                "reputation": {"arcane_order": 5000},
                "deed_flags": ["architects_defeat", "eternal_frequency_awarded"],
            },
            "dialogue": {
                "accept": "\"If you kill a mercy, do it loudly. The world should hear itself survive.\"",
                "decline": "\"Then kneel to silence.\"",
                "progress_1": "\"Make him *argue*.\"",
                "completion": (
                    "\"**The Eternal Frequency**—not loud. **Unkillable**.\n\n"
                    "The conductor's gone; the stillness is deaf now. Come back when you're ready—I'll show you what that *means* "
                    "for stone and salt. Carry the hum so stillness never gets to call itself peace.\""
                ),
            },
        },
        {
            "id": "obsidian_graying_end",
            "name": "The World Remembers",
            "description": "**Main arc — epilogue:** After Vaelkor—confirm how the Graying unclenches and what returns first.",
            "level_req": 58,
            "requires_deed_flags": ["architects_defeat"],
            "steps": [
                {
                    "step": 1,
                    "objective": "Speak with Eldric at the threshold",
                    "hint": "/interact eldric — witness the world argue again.",
                    "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                },
            ],
            "rewards": {
                "xp": 10000,
                "gold": 5000,
                "items": [],
                "reputation": {"arcane_order": 800},
                "deed_flags": ["graying_defeated_confirmed"],
            },
            "dialogue": {
                "accept": "\"You did it. Now watch.\"",
                "decline": "\"Then don't look.\"",
                "completion": (
                    "\"Feel it? The **Graying unclenches**. Not instant—not magic. "
                    "Vaelkor was its anchor; without him, the stillness *forgets* how to hold. "
                    "Petrified stone will crack in sheets. Ash will wash in tides, not stay painted on forever. "
                    "The world won't *heal*—healing is too gentle. It will *argue* again—loud, messy, *alive*. "
                    "That hum you carry? That's the **Eternal Frequency**—proof stillness was never stronger than motion.\""
                ),
            },
        },
        {
            "id": "silence_eldric_reckoning",
            "name": "The Architect's Reckoning",
            "description": "**Optional lore:** After the key—why Eldric left the order while Vaelkor chose stillness.",
            "level_req": 50,
            "requires_deed_flags": ["trisect_key_forged"],
            "steps": [
                {
                    "step": 1,
                    "objective": "Defeat 20 enemies in Blackrock Depths",
                    "hint": "Walk the threshold Eldric used to keep.",
                    "completion_check": {"type": "kill_any_zone", "value": "blackrock_depths", "count": 20},
                },
                {
                    "step": 2,
                    "objective": "Speak with Eldric",
                    "hint": "/interact eldric",
                    "completion_check": {"type": "talk_to_npc", "value": "eldric_wanderer"},
                },
            ],
            "rewards": {
                "xp": 6000,
                "gold": 2200,
                "items": [],
                "reputation": {"arcane_order": 500},
                "deed_flags": ["eldric_past_revealed"],
            },
            "dialogue": {
                "accept": "\"You want to know why I **left**? Sit.\"",
                "decline": "\"Then don't ask.\"",
                "progress_1": "\"Still walking? Good.\"",
                "completion": (
                    "\"I was an Architect—same as Vaelkor. We *kept* the threshold between what burns and what sleeps. "
                    "When he decided the world's pain could be *cured* with stillness, I refused. We *broke*—"
                    "he chose the Graying; I chose to walk it and forge keys that **disagree** with him.\""
                ),
            },
        },
    ],
}


# Main Obsidian arc order for Activity “story beacon” (skips optional **Optional:** side quests).
OBSIDIAN_STORY_POINTER_ORDER: List[str] = [
    "obsidian_shatter_tone",
    "obsidian_gorgoth_slayer",
    "obsidian_marcus_recommendation",
    "obsidian_khaz_dispatch",
    "obsidian_seismic_trigger",
    "obsidian_manifest_destiny",
    "obsidian_bloodfang_duel",
    "obsidian_curse_lifted",
    "obsidian_cipher_translated",
    "obsidian_architects_burden",
    "obsidian_flame_infused",
    "obsidian_trisect_key",
    "obsidian_ancient_runes_read",
    "obsidian_eternal_frequency",
    "obsidian_graying_end",
]
