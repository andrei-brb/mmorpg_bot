"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     config/settings.py — Game Constants                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Single source of truth for all game design values.
Change these to tune balance without touching logic.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
#   CORE SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

class Settings:
    # Bot
    VERSION             = "1.0.0"
    BOT_NAME            = "World of Discord"
    DATABASE_URL        = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mmorpg")
    REDIS_URL           = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Stripe (monetization)
    STRIPE_SECRET_KEY           = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET       = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    SERVER_PREMIUM_PRICE_ID     = os.getenv("STRIPE_SERVER_PREMIUM_PRICE_ID", "")
    PLAYER_PREMIUM_PRICE_ID     = os.getenv("STRIPE_PLAYER_PREMIUM_PRICE_ID", "")

    # Leveling
    MAX_LEVEL               = 60
    SPEC_UNLOCK_LEVEL       = 10
    XP_BASE                 = 100          # XP to reach level 2
    XP_EXPONENT             = 1.15         # How steeply XP scales per level
    XP_RESTED_MULTIPLIER    = 1.5          # Bonus XP while rested

    # Combat
    COMBAT_TIMEOUT_SECONDS  = 120
    MAX_PARTY_SIZE          = 5
    MAX_RAID_SIZE           = 20
    BOSS_HP_SCALE           = 3            # Default boss HP scale (used for endgame / dungeons)
    BOSS_DAMAGE_SCALE       = 0.7          # Boss damage multiplier vs players (global safety valve)
    FLEE_BASE_CHANCE        = 0.55
    
    # Dungeons
    DUNGEON_TIMER_SECONDS   = 1800         # 30 minutes default
    DUNGEON_FLOORS          = 3            # Default floors per dungeon
    DUNGEON_XP_MULTIPLIER   = 2.0          # XP multiplier for dungeon completion
    DUNGEON_GOLD_MULTIPLIER = 1.5          # Gold multiplier for dungeon completion

    # Inventory
    FREE_INVENTORY_SLOTS    = 20
    PREMIUM_INVENTORY_SLOTS = 60

    # Economy
    CURRENCY_SYMBOL         = "🪙"
    MARKET_FEE_PERCENT      = 5
    REPAIR_COST_PER_POINT   = 2

    # Cooldowns (seconds)
    EXPLORE_COOLDOWN        = 30
    REST_COOLDOWN           = 60
    DAILY_RESET_HOUR_UTC    = 0

    # World events
    WORLD_EVENT_INTERVAL    = 21_600       # 6 hours in seconds
    BOSS_RESPAWN_HOURS      = 6

    # Resource tuning (optional)
    # Per-class multipliers applied to ability costs (mana/energy/rage).
    # Lower = cheaper abilities.
    RESOURCE_COST_MULT = {
        "warrior": 1.00,
        "paladin": 0.95,
        "mage":    0.90,
        "rogue":   1.00,
        "priest":  0.90,
        "hunter":  0.95,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#   ITEM RARITY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RarityConfig:
    name:            str
    color:           int     # Discord embed hex color
    emoji:           str
    drop_weight:     float   # Relative probability (higher = more common)
    stat_multiplier: float   # How much better stats are vs common
    value_multiplier: float  # How much more valuable vs common (for vendor prices)

RARITIES: Dict[str, RarityConfig] = {
    "common":    RarityConfig("Common",    0x9D9D9D, "⬜", 50.0, 1.00, 1.00),
    "uncommon":  RarityConfig("Uncommon",  0x1EFF00, "🟩", 28.0, 1.30, 1.50),
    "rare":      RarityConfig("Rare",      0x0070DD, "🟦", 13.0, 1.70, 2.50),
    "epic":      RarityConfig("Epic",      0xA335EE, "🟪",  6.0, 2.20, 4.00),
    "legendary": RarityConfig("Legendary", 0xFF8000, "🟧",  2.5, 3.00, 8.00),
    "artifact":  RarityConfig("Artifact",  0xE6CC80, "🔶",  0.5, 4.50, 15.00),
}


# ═══════════════════════════════════════════════════════════════════════════════
#   CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ClassConfig:
    name:           str
    emoji:          str
    description:    str
    lore:           str
    role:           str    # tank | healer | dps | support
    primary_stat:   str    # strength | agility | intellect | spirit
    resource:       str    # rage | energy | mana
    base_hp:        int
    base_resource:  int
    base_stats:     Dict[str, int]
    specializations: Tuple[str, ...]
    starter_abilities: Tuple[str, ...]

CLASSES: Dict[str, ClassConfig] = {
    "warrior": ClassConfig(
        name="Warrior", emoji="⚔️", role="tank", primary_stat="strength", resource="rage",
        base_hp=240, base_resource=0,
        description="Unstoppable melee fighter clad in heavy armor.",
        lore="Forged in countless battles, Warriors rely on superior strength and "
             "impenetrable plate armor to outlast any foe on the front line.",
        base_stats={"strength": 18, "agility": 10, "intellect": 5, "spirit": 7, "stamina": 16},
        specializations=("arms", "protection"),
        starter_abilities=("strike", "battle_shout", "defensive_stance"),
    ),
    "paladin": ClassConfig(
        name="Paladin", emoji="🛡️", role="tank", primary_stat="strength", resource="mana",
        base_hp=210, base_resource=120,
        description="Holy warrior blending martial power with divine healing.",
        lore="Blessed by the Light, Paladins stand as beacons of hope — equally "
             "capable of smiting evil and healing the fallen.",
        base_stats={"strength": 16, "agility": 8, "intellect": 13, "spirit": 14, "stamina": 14},
        specializations=("retribution", "holy_paladin"),
        starter_abilities=("judgment", "holy_light", "divine_shield"),
    ),
    "mage": ClassConfig(
        name="Mage", emoji="🔮", role="dps", primary_stat="intellect", resource="mana",
        base_hp=120, base_resource=220,
        description="Scholar of arcane arts wielding devastating elemental magic.",
        lore="Years of study have granted Mages mastery over fire, frost, and arcane "
             "energies — power that can level cities or protect kingdoms.",
        base_stats={"strength": 4, "agility": 8, "intellect": 22, "spirit": 14, "stamina": 8},
        specializations=("fire", "frost"),
        starter_abilities=("fireball", "frost_bolt", "blink"),
    ),
    "rogue": ClassConfig(
        name="Rogue", emoji="🗡️", role="dps", primary_stat="agility", resource="energy",
        base_hp=155, base_resource=100,
        description="Deadly assassin who strikes from the shadows with lethal precision.",
        lore="Trained in the arts of deception and precision, Rogues eliminate targets "
             "before they ever see the blade coming.",
        base_stats={"strength": 10, "agility": 20, "intellect": 8, "spirit": 6, "stamina": 11},
        specializations=("assassination", "subtlety"),
        starter_abilities=("sinister_strike", "stealth", "eviscerate"),
    ),
    "priest": ClassConfig(
        name="Priest", emoji="✨", role="healer", primary_stat="intellect", resource="mana",
        base_hp=130, base_resource=240,
        description="Devoted healer channeling divine or shadow power.",
        lore="Priests walk a fine line between devotion and darkness, channeling the "
             "power of the Light to heal allies or shadow to destroy enemies.",
        base_stats={"strength": 4, "agility": 6, "intellect": 18, "spirit": 21, "stamina": 8},
        specializations=("holy_priest", "shadow"),
        starter_abilities=("heal", "smite", "power_word_shield"),
    ),
    "hunter": ClassConfig(
        name="Hunter", emoji="🏹", role="dps", primary_stat="agility", resource="mana",
        base_hp=165, base_resource=110,
        description="Master of ranged combat and beast taming.",
        lore="At home in the wilderness, Hunters combine deadly precision with the "
             "ferocity of their bonded animal companions.",
        base_stats={"strength": 8, "agility": 20, "intellect": 10, "spirit": 10, "stamina": 12},
        specializations=("marksmanship", "beast_mastery"),
        starter_abilities=("aimed_shot", "multi_shot", "hunters_mark"),
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
#   SPECIALIZATIONS  (unlocked at level 10)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SpecConfig:
    name:           str
    parent_class:   str
    emoji:          str
    role:           str
    description:    str
    flavor:         str          # Lore / personality blurb
    stat_bonuses:   Dict[str, float]
    passive_name:   str
    passive_desc:   str
    bonus_abilities: Tuple[str, ...]

SPECIALIZATIONS: Dict[str, SpecConfig] = {
    # ── Warrior ───────────────────────────────────────────────────────────────
    "arms": SpecConfig(
        name="Arms", parent_class="warrior", emoji="⚔️", role="dps",
        description="A master of two-handed weapons who deals devastating, precise strikes.",
        flavor="You are the executioner. Every swing is calculated to maximize carnage.",
        stat_bonuses={"strength": 1.35, "stamina": 1.10},
        passive_name="Deep Wounds",
        passive_desc="Your critical strikes cause the target to bleed for 3 turns.",
        bonus_abilities=("mortal_strike", "whirlwind", "colossus_smash"),
    ),
    "protection": SpecConfig(
        name="Protection", parent_class="warrior", emoji="🛡️", role="tank",
        description="An impenetrable shield wall who redirects enemy attacks to protect allies.",
        flavor="You are the wall between your allies and annihilation.",
        stat_bonuses={"stamina": 1.45, "strength": 1.10},
        passive_name="Shield Block",
        passive_desc="25% chance to block an attack, reducing damage by 40%.",
        bonus_abilities=("shield_slam", "revenge", "last_stand"),
    ),
    # ── Paladin ───────────────────────────────────────────────────────────────
    "retribution": SpecConfig(
        name="Retribution", parent_class="paladin", emoji="🔥", role="dps",
        description="A righteous crusader who channels holy wrath into devastating melee attacks.",
        flavor="Justice is not given. It is taken, with a two-handed hammer.",
        stat_bonuses={"strength": 1.35, "intellect": 1.15},
        passive_name="Vengeance",
        passive_desc="Each consecutive hit increases your damage by 3%, stacking up to 5×.",
        bonus_abilities=("crusader_strike", "divine_storm", "hammer_of_wrath"),
    ),
    "holy_paladin": SpecConfig(
        name="Holy", parent_class="paladin", emoji="💛", role="healer",
        description="A beacon of divine light, healing allies with radiant holy power.",
        flavor="You are the light that refuses to go out, no matter how dark the battle.",
        stat_bonuses={"intellect": 1.40, "spirit": 1.30},
        passive_name="Illumination",
        passive_desc="Critical heals restore 30% of the mana spent.",
        bonus_abilities=("holy_shock", "beacon_of_light", "lay_on_hands"),
    ),
    # ── Mage ──────────────────────────────────────────────────────────────────
    "fire": SpecConfig(
        name="Fire", parent_class="mage", emoji="🔥", role="dps",
        description="An explosive pyromancer who ignites enemies and detonates for massive damage.",
        flavor="Everything burns if you get the temperature right.",
        stat_bonuses={"intellect": 1.40, "spirit": 1.10},
        passive_name="Ignite",
        passive_desc="Your fire spells apply a burn DoT dealing 10% of damage over 3 turns.",
        bonus_abilities=("pyroblast", "combustion", "dragon_breath"),
    ),
    "frost": SpecConfig(
        name="Frost", parent_class="mage", emoji="❄️", role="dps",
        description="A calculating cryomancer who freezes and shatters foes.",
        flavor="Control the battlefield. Let them come to you — frozen.",
        stat_bonuses={"intellect": 1.35, "stamina": 1.15},
        passive_name="Shatter",
        passive_desc="Your spells deal +50% damage against frozen or slowed targets.",
        bonus_abilities=("ice_lance", "frozen_orb", "frost_nova"),
    ),
    # ── Rogue ─────────────────────────────────────────────────────────────────
    "assassination": SpecConfig(
        name="Assassination", parent_class="rogue", emoji="💀", role="dps",
        description="A venomous killer who poisons and bleeds targets to a slow death.",
        flavor="They never feel the blade. Just the slow, creeping darkness.",
        stat_bonuses={"agility": 1.40, "stamina": 1.10},
        passive_name="Master Poisoner",
        passive_desc="Your poison and bleed effects deal 25% more damage.",
        bonus_abilities=("mutilate", "envenom", "vendetta"),
    ),
    "subtlety": SpecConfig(
        name="Subtlety", parent_class="rogue", emoji="🌑", role="dps",
        description="A shadow dancer who ambushes from stealth with devastating efficiency.",
        flavor="The best assassin is the one they never knew existed.",
        stat_bonuses={"agility": 1.35, "intellect": 1.10},
        passive_name="Find Weakness",
        passive_desc="Attacks from stealth ignore 30% of the target's armor.",
        bonus_abilities=("shadowstrike", "shadow_dance", "backstab"),
    ),
    # ── Priest ────────────────────────────────────────────────────────────────
    "holy_priest": SpecConfig(
        name="Holy", parent_class="priest", emoji="🕊️", role="healer",
        description="A devoted healer radiating waves of holy energy to sustain allies.",
        flavor="Your faith is your shield. Your compassion is your weapon.",
        stat_bonuses={"spirit": 1.45, "intellect": 1.30},
        passive_name="Inspiration",
        passive_desc="Your heals also grant the target a 10% damage reduction for 1 turn.",
        bonus_abilities=("circle_of_healing", "prayer_of_mending", "guardian_spirit"),
    ),
    "shadow": SpecConfig(
        name="Shadow", parent_class="priest", emoji="🌑", role="dps",
        description="A void-touched caster who destroys minds and drains life force.",
        flavor="You found something in the dark. And it found you.",
        stat_bonuses={"intellect": 1.42, "spirit": 1.12},
        passive_name="Shadow Weaving",
        passive_desc="Each shadow spell increases shadow damage dealt by 5%, stacking 5×.",
        bonus_abilities=("mind_blast", "vampiric_touch", "void_eruption"),
    ),
    # ── Hunter ────────────────────────────────────────────────────────────────
    "marksmanship": SpecConfig(
        name="Marksmanship", parent_class="hunter", emoji="🎯", role="dps",
        description="A precision sniper who excels at picking off single high-priority targets.",
        flavor="One shot. That's all it takes. The rest is just breathing.",
        stat_bonuses={"agility": 1.40, "intellect": 1.10},
        passive_name="Trueshot",
        passive_desc="Your aimed shots have a 20% chance to deal triple damage.",
        bonus_abilities=("careful_aim", "rapid_fire", "double_tap"),
    ),
    "beast_mastery": SpecConfig(
        name="Beast Mastery", parent_class="hunter", emoji="🐉", role="dps",
        description="A wild tamer who fights alongside a powerful beast companion.",
        flavor="You and your beast are one mind, one fury.",
        stat_bonuses={"agility": 1.30, "stamina": 1.20},
        passive_name="Kindred Spirits",
        passive_desc="Your beast attacks alongside every auto attack, dealing 40% bonus damage.",
        bonus_abilities=("bestial_wrath", "dire_beast", "kill_command"),
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
#   ZONES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ZoneConfig:
    name:             str
    emoji:            str
    description:      str
    level_range:      Tuple[int, int]
    faction:          str            # alliance | horde | neutral
    enemies:          Tuple[str, ...]
    bosses:           Tuple[str, ...]
    loot_pool:        Tuple[str, ...]
    ambients:         Tuple[str, ...]   # Flavor text during exploration

ZONES: Dict[str, ZoneConfig] = {
    "elwynn_forest": ZoneConfig(
        name="Elwynn Forest", emoji="🌲", faction="alliance",
        level_range=(1, 10),
        description="A peaceful woodland surrounding the human capital. Ideal for new adventurers finding their footing.",
        enemies=("forest_wolf", "kobold", "defias_bandit", "young_boar", "goldshire_guard", "spider", "murloc_scout", "gnoll_raider"),
        bosses=("hogger", "defias_ringleader", "spider_queen", "murloc_warlord"),
        loot_pool=("iron_sword", "leather_cap", "health_potion", "linen_cloth"),
        ambients=(
            "Sunlight filters through the ancient canopy above.",
            "You hear wolves howling somewhere in the distance.",
            "A kobold scout scrambles into the underbrush as you approach.",
            "The smell of campfire smoke drifts through the warm air.",
            "A merchant's cart has overturned on the trail ahead.",
        ),
    ),
    "dun_morogh": ZoneConfig(
        name="Dun Morogh", emoji="❄️", faction="alliance",
        level_range=(1, 10),
        description="Frozen dwarven peaks. Bitter cold and hardy enemies await.",
        enemies=("ice_claw_bear", "trogg", "frostmane_troll", "snow_leopard", "frozen_wraith", "ice_elemental", "winter_wolf", "cave_bat", "frostmane_shaman"),
        bosses=("frostmane_headhunter", "ice_lord", "trogg_overlord", "ancient_frost_giant"),
        loot_pool=("dwarven_axe", "chain_coif", "frost_resist_potion", "wool_cloth"),
        ambients=(
            "Biting wind cuts through even the heaviest armor.",
            "Snow crunches under your boots with each step.",
            "Steam rises from a nearby geothermal hot spring.",
            "A trogg snarls from behind a frost-covered boulder.",
            "Icicles hang from the cavern entrance like crystal fangs.",
        ),
    ),
    "barrens": ZoneConfig(
        name="The Barrens", emoji="🌵", faction="horde",
        level_range=(10, 25),
        description="A vast sun-scorched wasteland where only the ruthless survive.",
        enemies=("razormane_warrior", "plainstrider", "sunscale_raptor", "barrens_scorpion", "zhevra", "thunder_lizard", "quillboar", "wind_sweeper", "barrens_vulture"),
        bosses=("kolkar_centaur_lord", "razormane_chieftain", "thunderhawk_alpha", "barrens_overlord"),
        loot_pool=("bone_club", "raptor_hide_vest", "stamina_draught", "silk_cloth"),
        ambients=(
            "Heat shimmers off the cracked, sun-baked earth.",
            "A raptor watches you carefully from behind a thornbush.",
            "The distant cry of a plainstrider echoes across the plains.",
            "Dust devils spiral lazily in the scorching midday wind.",
            "Bleached bones line what was once a watering hole.",
        ),
    ),
    "stranglethorn": ZoneConfig(
        name="Stranglethorn Vale", emoji="🌴", faction="neutral",
        level_range=(25, 45),
        description="A lush but deadly jungle where pirates, predators, and rival factions clash.",
        enemies=("bloodsail_pirate", "jungle_stalker", "venture_co_enforcer", "panther", "tiger", "basilisk", "jungle_troll", "crocodile", "stranglethorn_ape", "bloodsail_corsair"),
        bosses=("kurzen_the_mad", "bhag_thera", "bloodsail_admiral", "jungle_lord"),
        loot_pool=("corsair_blade", "jungle_leather_chest", "elixir_of_fortitude", "mageweave_cloth"),
        ambients=(
            "Parrots screech loudly overhead in the dense canopy.",
            "You spot fresh pirate boot-prints in the mud.",
            "Something enormous rustles in the undergrowth nearby.",
            "A waterfall cascades into a crystal-clear emerald pool.",
            "The humidity is oppressive. Even breathing takes effort.",
        ),
    ),
    "blackrock_depths": ZoneConfig(
        name="Blackrock Depths", emoji="🌋", faction="neutral",
        level_range=(50, 60),
        description="A labyrinthine dungeon-city inside an active volcano. The ultimate endgame challenge.",
        enemies=("dark_iron_dwarf", "molten_giant", "firelord_servant", "lava_elemental", "dark_iron_guard", "fire_imp", "shadowforge_sentinel", "magma_lord", "dark_iron_sorcerer", "flame_wraith"),
        bosses=("emperor_dagran_thaurissan", "lord_incendius", "magmadar", "golem_lord"),
        loot_pool=("sulfuron_blade", "shadowforge_plate", "flask_of_the_titans", "runecloth"),
        ambients=(
            "Waves of heat make the air itself seem to ripple.",
            "The endless clanging of hammers echoes through every corridor.",
            "Rivers of lava cast an orange hellish glow on the walls.",
            "Dark iron sentinels march in perfect formation nearby.",
            "The smell of brimstone is overwhelming.",
        ),
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
#   ENEMIES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EnemyTemplate:
    name:           str
    emoji:          str
    hp_base:        int
    damage_min:     int
    damage_max:     int
    armor:          int
    attack_power:   int
    crit_chance:    float
    xp_reward:      int
    gold_min:       int
    gold_max:       int
    is_boss:        bool = False
    abilities:      Tuple[str, ...] = ()

ENEMIES: Dict[str, EnemyTemplate] = {
    # ── Elwynn Forest (1-10) ────────────────────────────────────────────────────
    "forest_wolf":          EnemyTemplate("Forest Wolf",         "🐺",  70, 6,  12,  5,  20, 7.0,  25,  1, 5),
    "kobold":               EnemyTemplate("Kobold",              "👺",  55, 5,   9,  3,  15, 4.0,  18,  1, 4),
    "defias_bandit":        EnemyTemplate("Defias Bandit",       "🦹",  95, 9,  17, 10,  28, 9.0,  40,  4,12),
    "young_boar":           EnemyTemplate("Young Boar",          "🐷",  60, 5,  10,  4,  18, 5.0,  20,  1, 4),
    "goldshire_guard":      EnemyTemplate("Corrupted Guard",    "🛡️",  85, 8,  15,  9,  25, 8.0,  35,  3, 8),
    "spider":               EnemyTemplate("Giant Spider",        "🕷️",  65, 6,  11,  3,  19, 6.0,  22,  1, 5),
    "murloc_scout":         EnemyTemplate("Murloc Scout",       "🐸",  50, 4,   8,  2,  14, 4.0,  16,  1, 3),
    "gnoll_raider":         EnemyTemplate("Gnoll Raider",       "🐕",  90, 9,  16,  8,  26, 8.0,  38,  3, 9),
    # ── Elwynn Bosses ──────────────────────────────────────────────────────────
    "hogger":               EnemyTemplate("Hogger",              "🐗", 450, 18, 32, 28,  65, 12.0, 280, 45, 90, True, ("cleave", "enrage")),
    "defias_ringleader":    EnemyTemplate("Defias Ringleader",  "👑", 420, 16, 30, 25,  60, 11.0, 260, 40, 85, True, ("backstab", "poison")),
    "spider_queen":         EnemyTemplate("Spider Queen",        "🕸️", 480, 20, 35, 20,  70, 13.0, 300, 50, 95, True, ("web", "poison")),
    "murloc_warlord":       EnemyTemplate("Murloc Warlord",      "👹", 400, 15, 28, 22,  55, 10.0, 240, 35, 75, True, ("summon", "frenzy")),
    
    # ── Dun Morogh (1-10) ──────────────────────────────────────────────────────
    "ice_claw_bear":        EnemyTemplate("Ice Claw Bear",       "🐻", 110, 10, 18, 12,  32, 6.0,  38,  2, 9),
    "trogg":                EnemyTemplate("Trogg",               "👾",  80, 8,  14,  8,  24, 5.0,  30,  2, 7),
    "frostmane_troll":      EnemyTemplate("Frostmane Troll",     "🧟", 100, 9,  16, 10,  28, 7.0,  35,  3, 8),
    "snow_leopard":         EnemyTemplate("Snow Leopard",        "🐆",  75, 7,  13,  6,  22, 6.0,  28,  2, 6),
    "frozen_wraith":        EnemyTemplate("Frozen Wraith",       "👻",  70, 6,  12,  4,  20, 5.0,  24,  1, 5),
    "ice_elemental":        EnemyTemplate("Ice Elemental",       "❄️",  95, 9,  17, 11,  30, 7.0,  42,  3, 9),
    "winter_wolf":          EnemyTemplate("Winter Wolf",         "🐺",  85, 8,  15,  7,  26, 6.0,  32,  2, 7),
    "cave_bat":             EnemyTemplate("Cave Bat",            "🦇",  55, 5,   9,  3,  16, 5.0,  20,  1, 4),
    "frostmane_shaman":     EnemyTemplate("Frostmane Shaman",    "🔮",  88, 7,  14,  5,  24, 6.0,  30,  2, 6),
    # ── Dun Morogh Bosses ──────────────────────────────────────────────────────
    "frostmane_headhunter": EnemyTemplate("Frostmane Headhunter","🪓", 380, 16, 28, 22,  58, 10.0, 240, 40, 80, True),
    "ice_lord":             EnemyTemplate("Ice Lord",            "🧊", 440, 18, 32, 26,  65, 12.0, 270, 45, 90, True, ("frost_nova", "freeze")),
    "trogg_overlord":       EnemyTemplate("Trogg Overlord",      "👑", 410, 17, 30, 24,  62, 11.0, 250, 42, 85, True, ("stomp", "enrage")),
    "ancient_frost_giant":  EnemyTemplate("Ancient Frost Giant", "⛄", 500, 20, 35, 30,  75, 13.0, 320, 55, 100, True, ("ice_slam", "blizzard")),
    # ── Barrens (10-25) ───────────────────────────────────────────────────────
    "razormane_warrior":    EnemyTemplate("Razormane Warrior",   "🐗", 180, 16, 28, 22,  55, 9.0,  90,  8,20),
    "plainstrider":         EnemyTemplate("Plainstrider",        "🦢", 150, 14, 24, 15,  45, 7.0,  75,  6,15),
    "sunscale_raptor":      EnemyTemplate("Sunscale Raptor",     "🦎", 200, 18, 32, 18,  60, 11.0, 105, 10,25),
    "barrens_scorpion":     EnemyTemplate("Barrens Scorpion",    "🦂", 170, 15, 27, 20,  52, 8.0,  85,  7,18),
    "zhevra":               EnemyTemplate("Zhevra",              "🦓", 160, 14, 25, 16,  48, 7.0,  80,  6,16),
    "thunder_lizard":       EnemyTemplate("Thunder Lizard",      "🦖", 190, 17, 30, 19,  58, 10.0,  95,  8,22),
    "quillboar":            EnemyTemplate("Quillboar",           "🐷", 175, 16, 29, 21,  54, 9.0,  88,  7,19),
    "wind_sweeper":         EnemyTemplate("Wind Sweeper",        "🌪️", 165, 15, 26, 17,  50, 8.0,  82,  6,17),
    "barrens_vulture":      EnemyTemplate("Barrens Vulture",     "🦅", 155, 14, 24, 14,  46, 7.0,  78,  6,15),
    # ── Barrens Bosses ────────────────────────────────────────────────────────
    "kolkar_centaur_lord":  EnemyTemplate("Kolkar Centaur Lord", "🏇", 900, 30, 50, 50, 120, 13.0, 550, 80,160, True),
    "razormane_chieftain":  EnemyTemplate("Razormane Chieftain", "👑", 950, 32, 52, 52, 125, 14.0, 580, 85,170, True, ("war_cry", "charge")),
    "thunderhawk_alpha":    EnemyTemplate("Thunderhawk Alpha",  "⚡", 920, 31, 51, 48, 122, 13.0, 560, 82,165, True, ("lightning_strike", "dive")),
    "barrens_overlord":     EnemyTemplate("Barrens Overlord",   "👹", 980, 33, 54, 55, 130, 14.0, 600, 90,180, True, ("earthquake", "summon")),
    # ── Stranglethorn (25-45) ─────────────────────────────────────────────────
    "bloodsail_pirate":     EnemyTemplate("Bloodsail Pirate",    "🏴‍☠️",320, 28, 46, 30,  90, 11.0, 180, 20,50),
    "jungle_stalker":       EnemyTemplate("Jungle Stalker",      "🐆", 280, 25, 40, 25,  80, 13.0, 160, 18,42),
    "venture_co_enforcer":  EnemyTemplate("Venture Co. Enforcer","🤵", 350, 30, 48, 35,  98, 10.0, 195, 22,55),
    "panther":              EnemyTemplate("Panther",              "🐆", 300, 27, 43, 28,  85, 12.0, 170, 19,45),
    "tiger":                EnemyTemplate("Tiger",                "🐅", 310, 28, 45, 29,  88, 12.0, 175, 20,48),
    "basilisk":             EnemyTemplate("Basilisk",             "🦎", 290, 26, 42, 27,  83, 11.0, 165, 18,43),
    "jungle_troll":         EnemyTemplate("Jungle Troll",         "🧟", 330, 29, 47, 32,  92, 11.0, 185, 21,52),
    "crocodile":            EnemyTemplate("Giant Crocodile",     "🐊", 340, 30, 49, 33,  95, 12.0, 190, 22,55),
    "stranglethorn_ape":    EnemyTemplate("Stranglethorn Ape",   "🦍", 315, 28, 44, 31,  90, 11.0, 180, 20,50),
    "bloodsail_corsair":    EnemyTemplate("Bloodsail Corsair",   "⚔️", 325, 29, 46, 31,  91, 11.0, 182, 20,51),
    # ── Stranglethorn Bosses ─────────────────────────────────────────────────
    "kurzen_the_mad":       EnemyTemplate("Kurzen the Mad",      "🤯",1600, 55, 90, 80, 200, 14.0,1200,200,400, True, ("madness_wave", "blood_frenzy")),
    "bhag_thera":           EnemyTemplate("Bhag'thera",          "🐆",1800, 60,100, 85, 220, 16.0,1400,220,450, True),
    "bloodsail_admiral":    EnemyTemplate("Bloodsail Admiral",   "⚓",1700, 58, 95, 82, 210, 15.0,1300,210,430, True, ("cannon_blast", "boarding")),
    "jungle_lord":          EnemyTemplate("Jungle Lord",         "👑",1750, 59, 98, 84, 215, 15.0,1350,215,440, True, ("beast_call", "frenzy")),
    # ── Blackrock Depths (50-60) ──────────────────────────────────────────────
    "dark_iron_dwarf":      EnemyTemplate("Dark Iron Dwarf",     "⛏️", 600, 55, 85, 75, 180, 12.0, 380, 50,100),
    "molten_giant":         EnemyTemplate("Molten Giant",        "🔥", 900, 75,110,100, 250, 10.0, 520, 70,140),
    "firelord_servant":     EnemyTemplate("Firelord Servant",    "😈", 750, 65, 95, 85, 210, 13.0, 450, 60,120),
    "lava_elemental":       EnemyTemplate("Lava Elemental",       "🌋", 700, 60, 90, 80, 195, 12.0, 420, 55,110),
    "dark_iron_guard":      EnemyTemplate("Dark Iron Guard",     "🛡️", 650, 58, 88, 78, 190, 12.0, 400, 52,105),
    "fire_imp":             EnemyTemplate("Fire Imp",             "🔥", 550, 52, 80, 70, 170, 11.0, 360, 48, 95),
    "shadowforge_sentinel": EnemyTemplate("Shadowforge Sentinel","⚔️", 680, 62, 92, 82, 200, 12.0, 430, 56,112),
    "magma_lord":           EnemyTemplate("Magma Lord",          "🌋", 720, 64, 96, 84, 205, 13.0, 440, 58,115),
    "dark_iron_sorcerer":   EnemyTemplate("Dark Iron Sorcerer",  "🔮", 630, 57, 87, 76, 185, 12.0, 390, 51,102),
    "flame_wraith":         EnemyTemplate("Flame Wraith",         "👻", 590, 54, 83, 74, 178, 11.0, 370, 49, 98),
    # ── Blackrock Depths Bosses ───────────────────────────────────────────────
    "emperor_dagran_thaurissan": EnemyTemplate("Emperor Thaurissan", "👑",5000,110,180,180, 450, 15.0, 3500,600,1200, True, ("imperial_decree", "shadowflame", "enrage")),
    "lord_incendius":       EnemyTemplate("Lord Incendius",      "🌋",4000, 95,160,160, 400, 14.0, 3000,500,1000, True, ("flame_nova", "inferno")),
    "magmadar":             EnemyTemplate("Magmadar",             "🔥",4500,105,175,170, 425, 15.0, 3250,550,1100, True, ("lava_breath", "molten_armor")),
    "golem_lord":           EnemyTemplate("Golem Lord",          "🤖",4200,100,170,165, 410, 14.0, 3100,520,1050, True, ("crush", "stomp")),
}


# ═══════════════════════════════════════════════════════════════════════════════
#   DUNGEONS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DungeonConfig:
    key:            str
    name:           str
    emoji:          str
    description:    str
    level_req:      int
    floors:         int
    enemies_per_floor: Tuple[str, ...]  # Enemy keys for each floor
    floor_bosses:   Tuple[str, ...]    # Boss for each floor (last is final boss)
    loot_pool:      Tuple[str, ...]
    xp_reward:      int                 # Base XP per floor
    gold_reward:    Tuple[int, int]    # (min, max) gold per floor

DUNGEONS: Dict[str, DungeonConfig] = {
    "deadmines": DungeonConfig(
        key="deadmines",
        name="The Deadmines",
        emoji="⛏️",
        description="A goblin mining operation turned bandit hideout. Watch for traps!",
        level_req=10,
        floors=3,
        enemies_per_floor=("defias_bandit", "kobold", "defias_bandit", "defias_bandit"),
        floor_bosses=("defias_ringleader", "hogger", "defias_ringleader"),
        loot_pool=("iron_sword", "leather_cap", "health_potion", "dwarven_axe"),
        xp_reward=150,
        gold_reward=(50, 150),
    ),
    "stockades": DungeonConfig(
        key="stockades",
        name="The Stockades",
        emoji="🔒",
        description="Stormwind's maximum security prison. The inmates have taken over.",
        level_req=20,
        floors=4,
        enemies_per_floor=("defias_bandit", "goldshire_guard", "defias_bandit", "defias_bandit"),
        floor_bosses=("defias_ringleader", "hogger", "defias_ringleader", "hogger"),
        loot_pool=("dwarven_axe", "chain_coif", "stamina_draught", "corsair_blade"),
        xp_reward=250,
        gold_reward=(100, 250),
    ),
    "blackrock_depths_dungeon": DungeonConfig(
        key="blackrock_depths_dungeon",
        name="Blackrock Depths",
        emoji="🌋",
        description="A labyrinthine dungeon-city inside an active volcano. The ultimate challenge.",
        level_req=50,
        floors=5,
        enemies_per_floor=("dark_iron_dwarf", "molten_giant", "firelord_servant", "lava_elemental", "dark_iron_guard"),
        floor_bosses=("lord_incendius", "magmadar", "golem_lord", "lord_incendius", "emperor_dagran_thaurissan"),
        loot_pool=("sulfuron_blade", "shadowforge_plate", "flask_of_the_titans", "corsair_blade"),
        xp_reward=500,
        gold_reward=(300, 600),
    ),
}
