"""
╔══════════════════════════════════════════════════════════════════════════════╗
║             services/combat/combat_engine.py — Turn-Based Engine           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

log = logging.getLogger("combat")


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS EFFECTS
# ═══════════════════════════════════════════════════════════════════════════════

class StatusEffect(Enum):
    BURN          = "burn"
    BLEED         = "bleed"
    POISON        = "poison"
    STUN          = "stun"
    SLOW          = "slow"
    SHIELD        = "shield"
    REGEN         = "regen"
    POWER_UP      = "power_up"
    VULNERABILITY = "vulnerability"
    DODGE_UP      = "dodge_up"
    SILENCED      = "silenced"
    STEALTH       = "stealth"   # Rogue stealth state


@dataclass
class StatusInstance:
    effect:   StatusEffect
    value:    int          # damage/heal per tick or % modifier
    duration: int          # turns remaining
    source:   str


# ═══════════════════════════════════════════════════════════════════════════════
#  COMBATANT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Combatant:
    id:           str
    name:         str
    is_player:    bool
    char_id:      Optional[UUID]

    current_hp:   int
    max_hp:       int
    current_res:  int   # mana / energy / rage
    max_res:      int
    res_type:     str = "none"  # mana | energy | rage | none

    # Combat stats
    attack_power: int = 50
    spell_power:  int = 0
    armor:        int = 0
    dmg_min:      int = 8
    dmg_max:      int = 16
    crit_chance:  float = 5.0
    dodge_chance: float = 3.0
    speed:        float = 2.0
    
    # Secondary stats
    haste:        float = 0.0      # Attack speed bonus (%)
    lifesteal:    float = 0.0      # Lifesteal (%)
    resistance:   int = 0           # Elemental resistance
    hit_rating:   float = 0.0       # Accuracy bonus

    # State
    status_effects:     List[StatusInstance] = field(default_factory=list)
    ability_cooldowns:  Dict[str, int]       = field(default_factory=dict)
    is_stunned:         bool = False
    is_dead:            bool = False
    is_stealthed:       bool = False
    specialization:     Optional[str] = None  # e.g. "arms", "subtlety", etc.
    class_key:          Optional[str] = None  # warrior, paladin, mage, rogue, priest, hunter
    threat:             int  = 0             # aggro for group content
    combo_points:       int  = 0             # rogue mechanic
    vengeance_stacks:   int  = 0             # retribution paladin passive
    shadow_stacks:      int  = 0             # shadow priest passive
    talent_spec_passive_rank: int = 0        # max spec_passive talent ranks invested
    talent_procs:       Dict[str, float] = field(default_factory=dict)  # proc_id -> chance
    intent:             Optional[str] = None  # telegraphed next ability (see plan_enemy_turn)

    @property
    def hp_pct(self) -> float:
        return (self.current_hp / self.max_hp * 100) if self.max_hp else 0

    def has(self, effect: StatusEffect) -> bool:
        return any(s.effect == effect for s in self.status_effects)

    def get_status(self, effect: StatusEffect) -> Optional[StatusInstance]:
        return next((s for s in self.status_effects if s.effect == effect), None)

    def add_status(self, effect: StatusEffect, value: int, duration: int, source: str):
        existing = self.get_status(effect)
        if existing:
            existing.value = value
            existing.duration = duration
        else:
            self.status_effects.append(StatusInstance(effect, value, duration, source))

    def remove_status(self, effect: StatusEffect):
        self.status_effects = [s for s in self.status_effects if s.effect != effect]


# ═══════════════════════════════════════════════════════════════════════════════
#  ABILITIES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Ability:
    key:             str
    name:            str
    emoji:           str
    description:     str
    cost_type:       str   # mana | energy | rage | none
    cost:            int
    cooldown:        int   # turns
    target:          str   # enemy | self | ally | all_enemies | all_allies

    dmg_mult:        float = 0.0
    heal_mult:       float = 0.0
    applies:         Optional[StatusEffect] = None
    effect_val:      int = 0
    effect_dur:      int = 0
    is_aoe:          bool = False
    ignores_armor:   bool = False
    from_stealth:    bool = False   # Must be in stealth
    execute_threshold: Optional[float] = None  # Only usable when target HP% <= this (e.g. 0.20)


def ability_tooltip_payload(attacker: Combatant, ab: Ability) -> Dict[str, Any]:
    """Rough pre-mitigation numbers for Activity / PvP tooltips (matches core damage/heal formulas)."""
    out: Dict[str, Any] = {
        "crit_pct": round(float(attacker.crit_chance), 1),
        "dmg_min": None,
        "dmg_max": None,
        "heal_estimate": None,
        "is_aoe": bool(ab.is_aoe),
    }
    if ab.dmg_mult > 0:
        power = attacker.spell_power if ab.ignores_armor else attacker.attack_power
        raw_min = int((attacker.dmg_min + power * 0.12) * ab.dmg_mult)
        raw_max = int((attacker.dmg_max + power * 0.12) * ab.dmg_mult)
        out["dmg_min"] = max(1, raw_min)
        out["dmg_max"] = max(1, raw_max)
    if ab.heal_mult > 0:
        out["heal_estimate"] = max(1, int(attacker.spell_power * ab.heal_mult + 25))
    return out


ABILITIES: Dict[str, Ability] = {
    # ── Shared / Auto ─────────────────────────────────────────────────────────
    "auto_attack": Ability(
        "auto_attack","Auto Attack","👊","A basic melee or ranged swing.",
        "none",0,0,"enemy", dmg_mult=0.75),

    # ── Warrior ───────────────────────────────────────────────────────────────
    "strike": Ability(
        "strike","Strike","⚔️","A powerful melee strike.",
        "rage",10,0,"enemy", dmg_mult=1.0),
    "battle_shout": Ability(
        "battle_shout","Battle Shout","📣","Boost attack power for 3 turns.",
        "rage",5,5,"self",
        applies=StatusEffect.POWER_UP, effect_val=25, effect_dur=3),
    "defensive_stance": Ability(
        "defensive_stance","Defensive Stance","🛡️","Increases dodge for 3 turns.",
        "none",0,4,"self",
        applies=StatusEffect.DODGE_UP, effect_val=18, effect_dur=3),
    "mortal_strike": Ability(
        "mortal_strike","Mortal Strike","💀","Devastating blow that causes bleeding.",
        "rage",25,3,"enemy", dmg_mult=1.9,
        applies=StatusEffect.BLEED, effect_val=9, effect_dur=3),
    "whirlwind": Ability(
        "whirlwind","Whirlwind","🌪️","Spin and strike all enemies.",
        "rage",30,4,"all_enemies", dmg_mult=0.85, is_aoe=True),
    "colossus_smash": Ability(
        "colossus_smash","Colossus Smash","🪨","Sunder armor, making target vulnerable.",
        "rage",20,6,"enemy", dmg_mult=1.2,
        applies=StatusEffect.VULNERABILITY, effect_val=30, effect_dur=3),
    "shield_slam": Ability(
        "shield_slam","Shield Slam","🛡️","Ram your shield into the enemy, stunning them.",
        "rage",20,5,"enemy", dmg_mult=1.3,
        applies=StatusEffect.STUN, effect_val=0, effect_dur=1),
    "revenge": Ability(
        "revenge","Revenge","🔄","Counter-attack after being hit.",
        "rage",15,2,"enemy", dmg_mult=1.5),
    "last_stand": Ability(
        "last_stand","Last Stand","💪","Temporarily bolster your HP.",
        "none",0,10,"self", heal_mult=0.35),

    # ── Paladin ───────────────────────────────────────────────────────────────
    "judgment": Ability(
        "judgment","Judgment","⚡","Strike with holy power, ignoring armor.",
        "mana",30,1,"enemy", dmg_mult=1.0, ignores_armor=True),
    "holy_light": Ability(
        "holy_light","Holy Light","💛","A powerful heal.",
        "mana",50,0,"self", heal_mult=1.9),
    "divine_shield": Ability(
        "divine_shield","Divine Shield","🛡️","Block the next enemy hit (persists until then).",
        "mana",60,10,"self",
        # Duration is not ticked down in tick_turn; removed on first blocked hit.
        applies=StatusEffect.SHIELD, effect_val=9999, effect_dur=99),
    "crusader_strike": Ability(
        "crusader_strike","Crusader Strike","⚔️","A righteous melee blow.",
        "mana",20,1,"enemy", dmg_mult=1.3),
    "divine_storm": Ability(
        "divine_storm","Divine Storm","🌩️","Holy AoE that also heals you.",
        "mana",55,5,"all_enemies", dmg_mult=0.9, is_aoe=True, heal_mult=0.4),
    "hammer_of_wrath": Ability(
        "hammer_of_wrath","Hammer of Wrath","🔨","Execute — only usable below 20% enemy HP.",
        "mana",35,1,"enemy", dmg_mult=2.5, ignores_armor=True, execute_threshold=0.20),
    "holy_shock": Ability(
        "holy_shock","Holy Shock","💥","Instant holy damage or heal.",
        "mana",40,2,"enemy", dmg_mult=1.1, ignores_armor=True),
    "beacon_of_light": Ability(
        "beacon_of_light","Beacon of Light","🕯️","Mark yourself with a healing regen.",
        "mana",45,8,"self",
        applies=StatusEffect.REGEN, effect_val=20, effect_dur=4),
    "lay_on_hands": Ability(
        "lay_on_hands","Lay on Hands","🙌","Instantly restore a massive amount of HP.",
        "none",0,15,"self", heal_mult=5.0),

    # ── Mage ──────────────────────────────────────────────────────────────────
    "fireball": Ability(
        "fireball","Fireball","🔥","Hurl a ball of fire.",
        "mana",28,0,"enemy", dmg_mult=1.2, ignores_armor=True),
    "frost_bolt": Ability(
        "frost_bolt","Frost Bolt","❄️","Frost bolt that slows the target.",
        "mana",22,0,"enemy", dmg_mult=0.95, ignores_armor=True,
        applies=StatusEffect.SLOW, effect_val=35, effect_dur=2),
    "blink": Ability(
        "blink","Blink","💨","Teleport, increasing dodge for 1 turn.",
        "mana",20,5,"self",
        applies=StatusEffect.DODGE_UP, effect_val=50, effect_dur=1),
    "pyroblast": Ability(
        "pyroblast","Pyroblast","💥","Massive fireball with a burn DoT.",
        "mana",65,5,"enemy", dmg_mult=2.3, ignores_armor=True,
        applies=StatusEffect.BURN, effect_val=14, effect_dur=3),
    "combustion": Ability(
        "combustion","Combustion","🔥","Empower all fire spells for 3 turns.",
        "mana",50,8,"self",
        applies=StatusEffect.POWER_UP, effect_val=40, effect_dur=3),
    "dragon_breath": Ability(
        "dragon_breath","Dragon's Breath","🐉","Cone of fire that stuns.",
        "mana",55,6,"all_enemies", dmg_mult=0.9, is_aoe=True, ignores_armor=True,
        applies=StatusEffect.STUN, effect_val=0, effect_dur=1),
    "ice_lance": Ability(
        "ice_lance","Ice Lance","🔱","Fast piercing frost shard.",
        "mana",18,0,"enemy", dmg_mult=0.8, ignores_armor=True),
    "frozen_orb": Ability(
        "frozen_orb","Frozen Orb","🌐","AoE frost that slows all enemies.",
        "mana",60,6,"all_enemies", dmg_mult=0.75, is_aoe=True, ignores_armor=True,
        applies=StatusEffect.SLOW, effect_val=40, effect_dur=2),
    "frost_nova": Ability(
        "frost_nova","Frost Nova","❄️","Freeze all enemies in place.",
        "mana",50,7,"all_enemies", dmg_mult=0.2, is_aoe=True,
        applies=StatusEffect.STUN, effect_val=0, effect_dur=1),

    # ── Rogue ─────────────────────────────────────────────────────────────────
    "sinister_strike": Ability(
        "sinister_strike","Sinister Strike","🗡️","Quick precise stab.",
        "energy",40,0,"enemy", dmg_mult=1.1),
    "stealth": Ability(
        "stealth","Stealth","🌑","Vanish into shadows, entering stealth for a few turns.",
        "energy",20,8,"self",
        applies=StatusEffect.STEALTH, effect_val=0, effect_dur=3),
    "eviscerate": Ability(
        "eviscerate","Eviscerate","💉","Rip through the target, causing bleed.",
        "energy",35,2,"enemy", dmg_mult=1.7,
        applies=StatusEffect.BLEED, effect_val=11, effect_dur=4),
    "mutilate": Ability(
        "mutilate","Mutilate","⚔️","Dual stab causing deep wounds.",
        "energy",55,1,"enemy", dmg_mult=1.4,
        applies=StatusEffect.BLEED, effect_val=8, effect_dur=3),
    "envenom": Ability(
        "envenom","Envenom","☠️","Inject lethal poison.",
        "energy",45,2,"enemy", dmg_mult=1.2, ignores_armor=True,
        applies=StatusEffect.POISON, effect_val=12, effect_dur=4),
    "vendetta": Ability(
        "vendetta","Vendetta","🩸","Mark a target for bonus damage.",
        "energy",30,10,"enemy",
        applies=StatusEffect.VULNERABILITY, effect_val=30, effect_dur=5),
    "shadowstrike": Ability(
        "shadowstrike","Shadowstrike","🌑","A devastating attack from the shadows.",
        "energy",50,1,"enemy", dmg_mult=2.0, from_stealth=True),
    "shadow_dance": Ability(
        "shadow_dance","Shadow Dance","💃","Enter a state of rapid shadow strikes.",
        "energy",40,8,"self",
        applies=StatusEffect.POWER_UP, effect_val=35, effect_dur=2),
    "backstab": Ability(
        "backstab","Backstab","🔪","Brutal stab ignoring armor.",
        "energy",45,1,"enemy", dmg_mult=1.8, ignores_armor=True),

    # ── Priest ────────────────────────────────────────────────────────────────
    "heal": Ability(
        "heal","Heal","💚","Restore HP to yourself.",
        "mana",35,0,"self", heal_mult=1.3),
    "smite": Ability(
        "smite","Smite","✨","Strike with holy energy.",
        "mana",25,0,"enemy", dmg_mult=0.9, ignores_armor=True),
    "power_word_shield": Ability(
        "power_word_shield","Power Word: Shield","🔵","Create a damage-absorbing shield.",
        "mana",40,4,"self",
        applies=StatusEffect.SHIELD, effect_val=50, effect_dur=3),
    "mind_blast": Ability(
        "mind_blast","Mind Blast","🧠","Shadow psychic assault.",
        "mana",45,2,"enemy", dmg_mult=1.5, ignores_armor=True),
    "vampiric_touch": Ability(
        "vampiric_touch","Vampiric Touch","🩸","Shadow DoT that drains life.",
        "mana",40,3,"enemy",
        applies=StatusEffect.BLEED, effect_val=13, effect_dur=4),
    "void_eruption": Ability(
        "void_eruption","Void Eruption","🕳️","Unleash shadow energy on all foes.",
        "mana",80,8,"all_enemies", dmg_mult=1.3, is_aoe=True, ignores_armor=True),
    "circle_of_healing": Ability(
        "circle_of_healing","Circle of Healing","💫","AoE heal for all allies.",
        "mana",70,5,"all_allies", heal_mult=0.8, is_aoe=True),
    "prayer_of_mending": Ability(
        "prayer_of_mending","Prayer of Mending","🙏","Place a HoT on yourself.",
        "mana",50,4,"self",
        applies=StatusEffect.REGEN, effect_val=18, effect_dur=4),
    "guardian_spirit": Ability(
        "guardian_spirit","Guardian Spirit","👼","Prevent death once in the next 3 turns.",
        "mana",90,15,"self",
        applies=StatusEffect.SHIELD, effect_val=200, effect_dur=3),

    # ── Hunter ────────────────────────────────────────────────────────────────
    "aimed_shot": Ability(
        "aimed_shot","Aimed Shot","🎯","Carefully aimed, high-damage shot.",
        "mana",30,2,"enemy", dmg_mult=1.7),
    "multi_shot": Ability(
        "multi_shot","Multi-Shot","🏹","Volley of arrows hits all enemies.",
        "mana",40,3,"all_enemies", dmg_mult=0.75, is_aoe=True),
    "hunters_mark": Ability(
        "hunters_mark","Hunter's Mark","🎯","Mark a target, making them vulnerable.",
        "mana",20,6,"enemy",
        applies=StatusEffect.VULNERABILITY, effect_val=20, effect_dur=4),
    "careful_aim": Ability(
        "careful_aim","Careful Aim","🔭","Next shot deals massive damage.",
        "mana",35,4,"self",
        applies=StatusEffect.POWER_UP, effect_val=50, effect_dur=1),
    "rapid_fire": Ability(
        "rapid_fire","Rapid Fire","💨","Quickly fire 3 shots in one turn.",
        "mana",50,5,"enemy", dmg_mult=2.0),
    "double_tap": Ability(
        "double_tap","Double Tap","🔫","Fire twice at the same target.",
        "mana",45,3,"enemy", dmg_mult=1.6),
    "bestial_wrath": Ability(
        "bestial_wrath","Bestial Wrath","😤","Your beast enters a frenzy, massive power boost.",
        "mana",60,8,"self",
        applies=StatusEffect.POWER_UP, effect_val=60, effect_dur=3),
    "dire_beast": Ability(
        "dire_beast","Dire Beast","🦁","Summon a dire beast to attack.",
        "mana",50,6,"enemy", dmg_mult=1.4),
    "kill_command": Ability(
        "kill_command","Kill Command","💀","Command your beast to kill.",
        "mana",35,1,"enemy", dmg_mult=1.5),

    # ── Shared / Defensive ────────────────────────────────────────────────────
    # Brace is the answer to a telegraphed hit. Every class has it, it costs
    # nothing, and it is only ever the right move when you can see what is
    # coming — which is the whole point of enemy intent. The absorb is a share
    # of your own max HP (applied in use_ability) so it stays meaningful at
    # every level rather than being a flat number that ages out.
    "brace": Ability(
        "brace","Brace","🛡️","Absorb a share of the next hit and catch your breath.",
        "none",0,2,"self",
        applies=StatusEffect.SHIELD, effect_val=0, effect_dur=1),
}

# Boss signature moves. Every boss template in config/settings.py declares a kit;
# until this merge, 37 of the 39 keys had no entry here and silently resolved to
# auto_attack via the `.get(key, ABILITIES["auto_attack"])` default below.
# See services/combat/enemy_abilities.py for the design rules.
def _build_enemy_abilities() -> Dict[str, Ability]:
    from services.combat.enemy_abilities import ENEMY_ABILITY_SPECS

    # `applies` lands on whoever the ability targets, so a buff must target the
    # caster and a hit must target the players — an ability may never be both.
    self_buffs = {"shield", "power_up", "regen"}

    built: Dict[str, Ability] = {}
    for key, s in ENEMY_ABILITY_SPECS.items():
        if s["applies"] in self_buffs:
            target = "self"
        elif s["aoe"]:
            target = "all_enemies"
        else:
            target = "enemy"
        built[key] = Ability(
            key, s["name"], s["emoji"], s["desc"],
            "none", 0, int(s["cooldown"]), target,
            dmg_mult=float(s["dmg"]),
            applies=StatusEffect(s["applies"]) if s["applies"] else None,
            effect_val=int(s["val"]),
            effect_dur=int(s["dur"]),
            is_aoe=bool(s["aoe"]),
            # NOT ignores_armor — see design rule 3 in enemy_abilities.py. These
            # cut through armour via armor_pen_pct instead, because no item in
            # the game grants resistance, so the armour-ignoring branch would
            # apply no mitigation whatsoever.
            ignores_armor=False,
        )
    return built


ABILITIES.update(_build_enemy_abilities())

#: Health percentage at or below which a boss enters each phase.
PHASE_THRESHOLDS = {2: 50.0, 3: 25.0}

#: How often a boss reaches for its own signature kit, by phase. Rising with
#: the phase is what makes a phase change *felt* rather than merely computed:
#: the same boss that opened with a swing every other turn starts leading with
#: Lava Breath once it is cornered.
SIGNATURE_RATE_BY_PHASE = {1: 0.35, 2: 0.50, 3: 0.65}

#: What the player is told when a boss crosses a threshold. Phase 1 has no line
#: because there is no transition into it.
PHASE_ANNOUNCE = {
    2: "⚠️ **{name}** is wounded and fighting harder.",
    3: "🔥 **{name}** is cornered — it has stopped holding back.",
}

PHASE_LABEL = {1: "Opening", 2: "Wounded", 3: "Cornered"}


#: Brace absorbs this share of the bracing combatant's maximum health.
BRACE_ABSORB_PCT = 0.25

#: Brace also returns this share of maximum resource — so spending a turn
#: defending is never a completely wasted turn for a caster.
BRACE_RESOURCE_PCT = 0.15


def intent_payload(enemy: "Combatant") -> Optional[Dict[str, Any]]:
    """What the player is told about the enemy's telegraphed move.

    Deliberately no damage number: the real figure depends on a damage roll,
    crit, armour or resistance, and any vulnerability, so a printed number would
    be wrong more often than right. The player gets the move's name, what it
    does, and how bad it is on a three-point scale — enough to decide whether to
    brace, heal, or race it down, which is all the decision needs.
    """
    key = getattr(enemy, "intent", None)
    if not key:
        return None
    ab = ABILITIES.get(key)
    if not ab:
        return None

    from services.combat.enemy_abilities import ELEMENTAL_KEYS, TELLS, classify_intent

    shape = classify_intent(ab)
    return {
        "key": key,
        "name": ab.name,
        "emoji": ab.emoji,
        "description": ab.description,
        "tell": TELLS.get(key, "readies its next move"),
        "kind": shape["kind"],
        "severity": shape["severity"],
        "is_aoe": bool(ab.is_aoe),
        # Read from ELEMENTAL_KEYS, not `ignores_armor`: elemental moves cut
        # through armour via armor_pen_pct, so the flag on the Ability is false
        # by design and would report every move as physical.
        "elemental": key in ELEMENTAL_KEYS or bool(ab.ignores_armor),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  COMBAT SESSION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CombatResult:
    attacker:       str
    target:         str
    ability_name:   str
    damage:         int = 0
    healing:        int = 0
    # Who actually received HP (may differ from `target` for enemy-target AoE that self-heals).
    heal_recipient: Optional[str] = None
    is_crit:        bool = False
    is_dodge:       bool = False
    effects_added:  List[str] = field(default_factory=list)
    narrative:      str = ""
    log:            str = ""   # extra detail for spec passives, lifesteal, etc.


@dataclass
class CombatSession:
    session_id:   UUID
    players:      List[Combatant]
    enemies:      List[Combatant]
    turn:         int = 0
    log:          List[CombatResult] = field(default_factory=list)
    is_boss:      bool = False
    boss_phase:   int = 1
    zone_key:     str = ""
    enemy_key:    str = ""   # key from ENEMIES used for display / rewards
    # Story lore gates: Discord /fight, explore, Activity overworld story bosses. Dungeons stay off.
    apply_lore_gates: bool = True
    lore_gate_by_char: Dict[str, bool] = field(default_factory=dict)
    lore_gate_hint: Optional[str] = None

    @property
    def alive_players(self): return [p for p in self.players if not p.is_dead]
    @property
    def alive_enemies(self): return [e for e in self.enemies if not e.is_dead]
    @property
    def over(self): return not self.alive_players or not self.alive_enemies
    @property
    def players_won(self): return bool(self.alive_players) and not self.alive_enemies


# ═══════════════════════════════════════════════════════════════════════════════
#  ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class CombatEngine:

    # ── Execute one ability ───────────────────────────────────────────────────

    def use_ability(
        self,
        key: str,
        attacker: Combatant,
        targets: List[Combatant],
        session: Optional['CombatSession'] = None,
    ) -> List[CombatResult]:
        ability = ABILITIES.get(key, ABILITIES["auto_attack"])

        # Determine actual targets based on ability.target type
        if session:
            # In PvP, either side can be the attacker; "all_enemies"/"all_allies" must be relative.
            attacker_is_player_side = any(p.id == attacker.id for p in session.players)
            allies = session.alive_players if attacker_is_player_side else session.alive_enemies
            enemies = session.alive_enemies if attacker_is_player_side else session.alive_players
            if ability.target == "all_allies":
                actual_targets = allies
            elif ability.target == "all_enemies":
                actual_targets = enemies
            elif ability.target == "ally":
                # Target first alive ally (excluding self if possible)
                other_allies = [a for a in allies if a.id != attacker.id]
                actual_targets = [other_allies[0]] if other_allies else [attacker]
            elif ability.target == "self":
                actual_targets = [attacker]
            elif ability.target == "enemy":
                # Use provided targets (enemies)
                actual_targets = targets if ability.is_aoe else [targets[0]] if targets else []
            else:
                # Default: use provided targets
                actual_targets = targets if ability.is_aoe else [targets[0]] if targets else []
        else:
            # Fallback for backwards compatibility
            actual_targets = targets if ability.is_aoe else [targets[0]] if targets else []

        # ── Ability requirements (execute, stealth) ─────────────────────────────
        if ability.execute_threshold is not None and actual_targets:
            primary = actual_targets[0]
            if primary.hp_pct > ability.execute_threshold * 100:
                return [CombatResult(
                    attacker=attacker.name,
                    target=primary.name,
                    ability_name=ability.name,
                    narrative=(
                        f"❌ **{ability.name}** can only be used when target is below "
                        f"{int(ability.execute_threshold * 100)}% HP! "
                        f"(Target: {primary.hp_pct:.1f}%)"
                    ),
                )]

        if ability.from_stealth:
            if not attacker.has(StatusEffect.STEALTH):
                target_name = actual_targets[0].name if actual_targets else "None"
                return [CombatResult(
                    attacker=attacker.name,
                    target=target_name,
                    ability_name=ability.name,
                    narrative=f"❌ **{ability.name}** requires you to be in stealth! Use Stealth first.",
                )]

        results = []

        from services.talents.talent_combat import (
            apply_talent_damage_procs,
            apply_talent_damage_taken_procs,
            apply_talent_heal_procs,
            spec_passive_mult_for,
            try_talent_on_hit_slow,
        )

        spm = spec_passive_mult_for(attacker)

        for target in actual_targets:
            r = CombatResult(attacker=attacker.name, target=target.name, ability_name=ability.name)

            # Stun check
            if attacker.is_stunned:
                r.narrative = f"⚡ **{attacker.name}** is stunned and cannot act!"
                results.append(r)
                continue

            # Dodge check (only physical / targeted abilities)
            if ability.dmg_mult > 0 and not ability.ignores_armor:
                dodge = target.dodge_chance
                buff = target.get_status(StatusEffect.DODGE_UP)
                if buff:
                    dodge += buff.value
                if random.random() * 100 < dodge:
                    r.is_dodge = True
                    r.narrative = f"💨 **{target.name}** dodges **{attacker.name}**'s {ability.emoji} {ability.name}!"
                    results.append(r)
                    continue

            # ── Damage ────────────────────────────────────────────────────────
            if ability.dmg_mult > 0:
                base = random.randint(attacker.dmg_min, attacker.dmg_max)
                power = attacker.spell_power if ability.ignores_armor else attacker.attack_power
                raw = int((base + power * 0.12) * ability.dmg_mult)
                armor_pen_pct = 0.0

                # Spec/class passive and proc damage hooks.
                if attacker.specialization == "retribution":
                    attacker.vengeance_stacks = min(5, attacker.vengeance_stacks + 1)
                    raw = int(raw * (1 + attacker.vengeance_stacks * 0.03 * spm))
                if attacker.specialization == "shadow" and ability.key in {"smite", "mind_blast", "vampiric_touch", "void_eruption"}:
                    attacker.shadow_stacks = min(5, attacker.shadow_stacks + 1)
                    raw = int(raw * (1 + attacker.shadow_stacks * 0.05 * spm))
                if attacker.specialization == "frost" and ability.key in {"frost_bolt", "ice_lance", "frozen_orb", "frost_nova"}:
                    if target.has(StatusEffect.SLOW) or target.has(StatusEffect.STUN):
                        raw = int(raw * (1 + 0.2 * spm))
                if attacker.specialization == "marksmanship" and ability.key == "aimed_shot":
                    if random.random() < min(0.45, 0.20 * spm):
                        raw = int(raw * (1 + 2.0 * spm))
                        r.log += " 🎯 Trueshot proc!"
                if attacker.specialization == "subtlety" and attacker.has(StatusEffect.STEALTH):
                    armor_pen_pct = max(armor_pen_pct, min(0.45, 0.30 * spm))
                if attacker.specialization == "beast_mastery" and ability.key == "auto_attack":
                    raw = int(raw * (1 + 0.4 * spm))
                    r.log += " 🐉 Beast strikes with you!"
                if ability.key == "shadowstrike" and attacker.has(StatusEffect.STEALTH):
                    armor_pen_pct = max(armor_pen_pct, 0.30)
                if ability.key == "backstab" and attacker.has(StatusEffect.STEALTH):
                    armor_pen_pct = max(armor_pen_pct, 0.30)
                if ability.key == "strike" and random.random() < 0.25:
                    target.add_status(StatusEffect.VULNERABILITY, 10, 2, attacker.name)
                    r.effects_added.append("sunder")
                if ability.key == "judgment" and random.random() < 0.20:
                    target.add_status(StatusEffect.VULNERABILITY, 15, 2, attacker.name)
                    r.effects_added.append("exposed")
                if ability.key == "sinister_strike" and random.random() < 0.20:
                    target.add_status(StatusEffect.VULNERABILITY, 12, 1, attacker.name)
                    r.effects_added.append("find_weakness")
                if ability.key == "aimed_shot" and random.random() < 0.25:
                    armor_pen_pct = max(armor_pen_pct, 0.30)
                    r.log += " 🏹 Piercing hit!"
                # Elemental boss moves cut through plate rather than ignore it.
                from services.combat.enemy_abilities import ELEMENTAL_KEYS
                if ability.key in ELEMENTAL_KEYS:
                    armor_pen_pct = max(armor_pen_pct, ELEMENTAL_KEYS[ability.key])

                # Elemental matchup — the player's offence only, so the choice
                # of which ability to press matters without also making every
                # boss hit harder. See services/combat/elements.py.
                if attacker.is_player and session is not None:
                    from services.combat.elements import ability_element, enemy_element, matchup

                    mm = matchup(ability_element(ability.key), enemy_element(getattr(session, "enemy_key", None)))
                    if mm != 1.0:
                        raw = int(raw * mm)
                        r.log += " 🔺 Super effective!" if mm > 1.0 else " 🔻 Resisted."

                # Power-up buff
                pu = attacker.get_status(StatusEffect.POWER_UP)
                if pu:
                    raw = int(raw * (1 + pu.value / 100))

                # Armor reduction (physical only)
                if not ability.ignores_armor:
                    reduction = target.armor / (target.armor + 500)
                    if armor_pen_pct > 0:
                        reduction = max(0.0, reduction * (1 - armor_pen_pct))
                    raw = int(raw * (1 - reduction))
                else:
                    # Spell/elemental-style mitigation via resistance.
                    # This makes resistance potions and gear meaningful against magic-like hits.
                    res = max(0, int(getattr(target, "resistance", 0) or 0))
                    if res > 0:
                        magic_reduction = min(0.60, res / (res + 500))
                        raw = int(raw * (1 - magic_reduction))

                # Vulnerability
                vu = target.get_status(StatusEffect.VULNERABILITY)
                if vu:
                    raw = int(raw * (1 + vu.value / 100))

                # Hit rating check (accuracy) — before shield consumption so misses don't waste shields
                hit_chance = 95.0 + getattr(attacker, 'hit_rating', 0) * 0.1
                if random.random() * 100 > hit_chance:
                    r.damage = 0
                    r.log = f"{attacker.name} **missed**!"
                    results.append(r)
                    continue

                # Divine Shield: full immunity to the next successful hit (persists through your own turns)
                sh = target.get_status(StatusEffect.SHIELD)
                if sh and sh.source == "divine_shield":
                    target.remove_status(StatusEffect.SHIELD)
                    r.damage = 0
                    r.narrative = (
                        f"🛡️ **Divine Shield** absorbs **{attacker.name}**'s attack — **{target.name}** takes no damage!"
                    )
                    results.append(r)
                    continue

                # Normal shield absorption (Power Word: Shield, Inspiration, etc.)
                sh = target.get_status(StatusEffect.SHIELD)
                if sh:
                    absorbed = min(sh.value, raw)
                    raw -= absorbed
                    sh.value -= absorbed
                    if sh.value <= 0:
                        target.remove_status(StatusEffect.SHIELD)

                # Crit
                crit_roll = random.random() * 100
                if crit_roll < attacker.crit_chance:
                    raw = int(raw * 1.5)
                    r.is_crit = True
                    if attacker.specialization == "arms" and ability.key in {"strike", "mortal_strike", "whirlwind", "colossus_smash"}:
                        bleed_val = int(8 * spm)
                        bleed_dur = 3 if spm <= 1.12 else 4
                        target.add_status(StatusEffect.BLEED, bleed_val, bleed_dur, attacker.name)
                        r.effects_added.append("deep_wounds")

                raw = apply_talent_damage_procs(attacker, target, raw, is_crit=r.is_crit)
                if target.is_player:
                    raw = apply_talent_damage_taken_procs(target, raw, r)

                # Lore boss gate: story bosses immune until deed flags / key items (Discord path only)
                if (
                    session
                    and session.is_boss
                    and getattr(session, "apply_lore_gates", True)
                    and ability.dmg_mult > 0
                    and attacker.is_player
                    and not target.is_player
                ):
                    cid = str(attacker.char_id) if attacker.char_id else ""
                    ok = session.lore_gate_by_char.get(cid, True)
                    if ok is False:
                        r.damage = 0
                        hint = getattr(session, "lore_gate_hint", None) or ""
                        r.narrative = (
                            f"🪞 **{target.name}** is **immune** — your strikes won't bite until the story allows it.\n"
                            + (f"_{hint}_" if hint else "_Talk to the relevant NPC and complete the deed or obtain the key item._")
                        )
                        results.append(r)
                        continue

                r.damage = max(1, raw)
                target.current_hp = max(0, target.current_hp - r.damage)
                if target.current_hp <= 0:
                    target.is_dead = True
                if r.damage > 0:
                    try_talent_on_hit_slow(attacker, target, r)

                # Rage from taking damage (player warrior hit by enemy)
                if target.is_player and target.res_type == "rage" and r.damage > 0:
                    rg = max(1, r.damage // 5)
                    target.current_res = min(target.max_res or 100, target.current_res + rg)

                # Break stealth when the stealthed unit ATTACKS (but not when merely taking damage)
                if attacker.has(StatusEffect.STEALTH) and ability.key != "stealth":
                    attacker.remove_status(StatusEffect.STEALTH)

                # Lifesteal
                lifesteal_pct = getattr(attacker, 'lifesteal', 0)
                if lifesteal_pct > 0:
                    heal_amount = int(r.damage * lifesteal_pct / 100)
                    attacker.current_hp = min(attacker.max_hp, attacker.current_hp + heal_amount)
                    if heal_amount > 0:
                        r.log += f" (💚 +{heal_amount} HP from lifesteal)"

                # Rage generation
                if attacker.res_type == "rage":
                    attacker.current_res = min(attacker.max_res or 100, attacker.current_res + r.damage // 4)

                # Threat for tanking
                attacker.threat += r.damage

            # ── Healing ───────────────────────────────────────────────────────
            if ability.heal_mult > 0:
                # For offensive abilities that include self-heal (e.g. Divine Storm),
                # healing should go to the attacker, not the enemy target.
                heal_target = attacker if ability.target in {"enemy", "all_enemies"} else target
                base_heal = int(attacker.spell_power * ability.heal_mult + 25)
                actual_heal = min(base_heal, heal_target.max_hp - heal_target.current_hp)
                heal_target.current_hp = min(heal_target.max_hp, heal_target.current_hp + actual_heal)
                r.healing = actual_heal
                r.heal_recipient = heal_target.name
                # Holy priest passive: heals grant small absorb.
                if attacker.specialization == "holy_priest" and actual_heal > 0:
                    shield_val = max(6, int(actual_heal * 0.10 * spm))
                    heal_target.add_status(StatusEffect.SHIELD, shield_val, 1, "inspiration")
                    r.effects_added.append("inspiration")
                apply_talent_heal_procs(attacker, heal_target, actual_heal, r)
                # Holy paladin passive: critical heals refund mana.
                if attacker.specialization == "holy_paladin":
                    heal_crit_roll = random.random() * 100
                    if heal_crit_roll < attacker.crit_chance:
                        refund = int(ability.cost * 0.30)
                        if refund > 0 and attacker.max_res > 0:
                            attacker.current_res = min(attacker.max_res, attacker.current_res + refund)
                            r.log += f" ✨ Illumination +{refund} mana"

            # ── Apply status ──────────────────────────────────────────────────
            if ability.applies:
                effect_val = ability.effect_val
                # Enemy signature effects scale off the combatant instead of a
                # flat number, so a level-60 boss's poison is not the same tick
                # as a level-5 one's. See services/combat/enemy_abilities.py.
                from services.combat.enemy_abilities import DOT_SCALE_BY_KEY, SHIELD_SCALE

                dot_scale = DOT_SCALE_BY_KEY.get(ability.key)
                if dot_scale:
                    effect_val = max(1, int(attacker.attack_power * dot_scale))
                shield_scale = SHIELD_SCALE.get(ability.key)
                if shield_scale:
                    effect_val = max(1, int(attacker.max_hp * shield_scale))
                # Brace absorbs a share of the bracing combatant's own health,
                # so it is worth the same turn at level 5 and at level 60.
                if ability.key == "brace":
                    effect_val = max(1, int(target.max_hp * BRACE_ABSORB_PCT))
                # Assassination passive: stronger bleed/poison effects.
                if attacker.specialization == "assassination" and ability.applies in {StatusEffect.BLEED, StatusEffect.POISON}:
                    effect_val = int(effect_val * (1 + 0.25 * spm))
                target.add_status(ability.applies, effect_val, ability.effect_dur, ability.key)
                r.effects_added.append(ability.applies.value)
                # Fire passive: bonus chance to ignite on fire spells.
                if attacker.specialization == "fire" and ability.key in {"fireball", "pyroblast", "dragon_breath"}:
                    if random.random() < min(0.55, 0.30 * spm):
                        target.add_status(StatusEffect.BURN, max(6, int((effect_val or 10) * 0.8 * spm)), 3, attacker.name)
                        r.effects_added.append("ignite")

            # Brace also returns a little resource. A defensive turn should cost
            # you tempo, not leave a caster with nothing to spend next turn.
            if ability.key == "brace":
                sh = attacker.get_status(StatusEffect.SHIELD)
                bits = [f"Absorbing up to **{sh.value}** damage"] if sh else []
                if attacker.max_res > 0:
                    gain = max(1, int(attacker.max_res * BRACE_RESOURCE_PCT))
                    attacker.current_res = min(attacker.max_res, attacker.current_res + gain)
                    bits.append(f"+{gain} {attacker.res_type}")
                r.log = (" · ".join(bits) + ".") if bits else r.log

            r.narrative = self._narrative(r, ability)
            results.append(r)

        # Cooldown
        if ability.cooldown > 0:
            attacker.ability_cooldowns[key] = ability.cooldown

        return results

    # ── Process start-of-turn effects ─────────────────────────────────────────

    def tick_turn(self, combatant: Combatant) -> List[str]:
        """Apply DoTs/HoTs, tick cooldowns, regen resources. Returns messages."""
        msgs = []
        combatant.is_stunned = False
        expired = []

        for s in combatant.status_effects:
            if s.effect == StatusEffect.BURN:
                combatant.current_hp = max(0, combatant.current_hp - s.value)
                if combatant.current_hp == 0: combatant.is_dead = True
                msgs.append(f"🔥 **{combatant.name}** burns for **{s.value}** dmg")
            elif s.effect in (StatusEffect.BLEED, StatusEffect.POISON):
                combatant.current_hp = max(0, combatant.current_hp - s.value)
                if combatant.current_hp == 0: combatant.is_dead = True
                emoji = "🩸" if s.effect == StatusEffect.BLEED else "☠️"
                msgs.append(f"{emoji} **{combatant.name}** takes **{s.value}** {s.effect.value} dmg")
            elif s.effect == StatusEffect.REGEN:
                healed = min(s.value, combatant.max_hp - combatant.current_hp)
                combatant.current_hp += healed
                msgs.append(f"💚 **{combatant.name}** regens **{healed}** HP")
            elif s.effect == StatusEffect.STUN:
                combatant.is_stunned = True
                msgs.append(f"⚡ **{combatant.name}** is stunned!")
            elif s.effect == StatusEffect.STEALTH:
                # Stealth just ticks down; no per-turn effect here
                pass

            # Divine Shield is removed on first blocked hit, not by turn ticks
            if s.effect == StatusEffect.SHIELD and s.source == "divine_shield":
                pass
            else:
                s.duration -= 1
            if s.duration <= 0:
                expired.append(s)

        for s in expired:
            combatant.status_effects.remove(s)

        # Tick cooldowns
        for k in list(combatant.ability_cooldowns):
            combatant.ability_cooldowns[k] -= 1
            if combatant.ability_cooldowns[k] <= 0:
                del combatant.ability_cooldowns[k]

        # Resource regen / decay
        if combatant.max_res > 0:
            if combatant.res_type == "mana":
                regen = max(1, int(combatant.max_res * 0.06))
                combatant.current_res = min(combatant.max_res, combatant.current_res + regen)
            elif combatant.res_type == "energy":
                regen = max(5, int(combatant.max_res * 0.20))
                combatant.current_res = min(combatant.max_res, combatant.current_res + regen)
            # Rage: do not decay each turn — small gains (dmg//4) were wiped by decay (10/rnd).
            # Rage resets to 0 on rest (full_restore). In combat it only changes via hits.

        return msgs

    # ── Enemy AI ──────────────────────────────────────────────────────────────

    def enemy_turn(
        self,
        enemy: Combatant,
        targets: List[Combatant],
        is_boss: bool = False,
        phase: int = 1,
        enemy_key: Optional[str] = None,
    ) -> Tuple[str, List[Combatant]]:
        """Resolve the enemy's action for this turn.

        If a move was telegraphed with `plan_enemy_turn`, that is the move that
        executes — the whole value of showing intent is that it cannot be a
        bluff. Otherwise the action is rolled here, which is the original
        behaviour and what the Discord cogs still do.
        """
        alive = [t for t in targets if not t.is_dead]
        if not alive:
            enemy.intent = None
            return "auto_attack", []

        planned = enemy.intent
        if planned:
            enemy.intent = None
            if planned in ABILITIES and planned not in enemy.ability_cooldowns:
                ab = ABILITIES[planned]
                if ab.target == "self":
                    return planned, [enemy]
                if ab.is_aoe:
                    return planned, alive
                # Re-resolve the target: the one we telegraphed may have died,
                # or threat may have moved during the party's turn.
                return planned, [max(alive, key=lambda t: t.threat)]
            # Telegraphed something we can no longer do (cooldown changed under
            # us). Fall through and roll fresh rather than fake it.

        return self._roll_enemy_action(enemy, alive, is_boss, phase, enemy_key)

    def plan_enemy_turn(
        self,
        enemy: Combatant,
        targets: List[Combatant],
        is_boss: bool = False,
        phase: int = 1,
        enemy_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Decide the enemy's *next* move now, so the player can see it coming.

        This is what turns a turn into a decision. Combat used to be: press your
        biggest button, read what happened. Now the enemy commits first and the
        player answers — brace the heavy hit, burn the boss down while it is
        buffing itself, stun it mid-wind-up to cancel the move outright (a stun
        makes `use_ability` bail at the top, so the telegraphed turn is simply
        lost).

        Returns the intent payload for the UI, or None if there is nothing to
        telegraph.
        """
        alive = [t for t in targets if not t.is_dead]
        if not alive or enemy.is_dead:
            enemy.intent = None
            return None

        key, _ = self._roll_enemy_action(enemy, alive, is_boss, phase, enemy_key)
        enemy.intent = key
        return intent_payload(enemy)

    def _roll_enemy_action(
        self,
        enemy: Combatant,
        alive: List[Combatant],
        is_boss: bool,
        phase: int,
        enemy_key: Optional[str],
    ) -> Tuple[str, List[Combatant]]:

        # Highest-threat target (tank priority)
        target = max(alive, key=lambda t: t.threat)

        # Prefer enemy template ability list when provided (prevents normal mobs using player-only kits).
        if enemy_key:
            try:
                from config.settings import ENEMIES

                tmpl = ENEMIES.get(enemy_key)
                if tmpl and tmpl.abilities:
                    usable = [k for k in tmpl.abilities if k not in enemy.ability_cooldowns]
                    # A cornered boss reaches for its signature moves more often.
                    # This rate used to be a flat 0.35 regardless of phase, so a
                    # boss at 5% health fought exactly like one at 100% — the
                    # phase machinery below only ever governed the fallback kit,
                    # never the boss's own.
                    if usable and random.random() < SIGNATURE_RATE_BY_PHASE.get(phase, 0.35):
                        return random.choice(usable), [target]
            except Exception:
                pass

        if not is_boss:
            return "auto_attack", [target]

        # Boss AI — phase-aware
        if phase == 1:
            r = random.random()
            if r < 0.25: return "mortal_strike", [target]
            return "auto_attack", [target]
        elif phase == 2:
            r = random.random()
            if r < 0.35: return "whirlwind", alive
            if r < 0.55: return "mortal_strike", [target]
            return "auto_attack", [target]
        else:  # phase 3 — enraged
            r = random.random()
            if r < 0.45: return "whirlwind", alive
            if r < 0.65: return "mortal_strike", [target]
            return "auto_attack", alive

    def boss_phase(self, boss: Combatant) -> int:
        if boss.hp_pct <= PHASE_THRESHOLDS[3]: return 3
        if boss.hp_pct <= PHASE_THRESHOLDS[2]: return 2
        return 1

    # ── Rewards ───────────────────────────────────────────────────────────────

    def calculate_rewards(self, session: "CombatSession") -> Dict:
        """Base XP/gold before guild/event multipliers (apply once in victory handlers)."""
        from config.settings import ENEMIES
        base_xp = gold = 0
        loot_rolls = 0

        for enemy in session.enemies:
            # Try to match name back to a template for rewards
            for key, tmpl in ENEMIES.items():
                if tmpl.name in enemy.name:
                    base_xp  += tmpl.xp_reward
                    gold     += random.randint(tmpl.gold_min, tmpl.gold_max)
                    loot_rolls += 1
                    break
            else:
                base_xp  += int(enemy.max_hp * 0.15)
                gold     += int(enemy.max_hp * 0.04)
                loot_rolls += 1

        if session.is_boss:
            base_xp   *= 5
            gold      *= 6
            loot_rolls += 3

        return {
            "xp":         int(base_xp),
            "gold":       int(gold),
            "loot_rolls": loot_rolls,
        }

    # ── Narrative builder ─────────────────────────────────────────────────────

    def _narrative(self, r: CombatResult, ability: Ability) -> str:
        if r.is_dodge:
            return f"💨 **{r.target}** dodges **{r.attacker}**'s {ability.emoji} **{ability.name}**!"
        if ability.key == "brace":
            # The most-pressed defensive button in the game deserves better than
            # "applying *shield*".
            return f"🛡️ **{r.attacker}** braces for impact. {r.log}".strip()
        parts = [f"{ability.emoji} **{r.attacker}** uses **{ability.name}**"]
        if r.damage:
            crit = " *(CRIT!)*" if r.is_crit else ""
            parts.append(f"dealing **{r.damage}** dmg to **{r.target}**{crit}")
        if r.healing:
            who = getattr(r, "heal_recipient", None) or r.target
            parts.append(f"restoring **{r.healing}** HP to **{who}**")
        if r.effects_added:
            parts.append(f"applying *{', '.join(r.effects_added)}*")
        msg = " — ".join(parts) + "."
        if r.log:
            msg += f" {r.log}"
        return msg
