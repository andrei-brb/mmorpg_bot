"""
╔══════════════════════════════════════════════════════════════════════════════╗
║             services/combat/combat_engine.py — Turn-Based Engine           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
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
            if ability.target == "all_allies":
                actual_targets = session.alive_players
            elif ability.target == "all_enemies":
                actual_targets = session.alive_enemies
            elif ability.target == "ally":
                # Target first alive ally (excluding self if possible)
                allies = [p for p in session.alive_players if p.id != attacker.id]
                actual_targets = [allies[0]] if allies else [attacker]
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
                # This keeps class identity in combat without requiring a full skill-tree system.
                if attacker.specialization == "retribution":
                    attacker.vengeance_stacks = min(5, attacker.vengeance_stacks + 1)
                    raw = int(raw * (1 + attacker.vengeance_stacks * 0.03))
                if attacker.specialization == "shadow" and ability.key in {"smite", "mind_blast", "vampiric_touch", "void_eruption"}:
                    attacker.shadow_stacks = min(5, attacker.shadow_stacks + 1)
                    raw = int(raw * (1 + attacker.shadow_stacks * 0.05))
                if attacker.specialization == "frost" and ability.key in {"frost_bolt", "ice_lance", "frozen_orb", "frost_nova"}:
                    if target.has(StatusEffect.SLOW) or target.has(StatusEffect.STUN):
                        raw = int(raw * 1.2)
                if attacker.specialization == "marksmanship" and ability.key == "aimed_shot":
                    if random.random() < 0.20:
                        raw = int(raw * 3.0)
                        r.log += " 🎯 Trueshot proc!"
                if attacker.specialization == "subtlety" and attacker.has(StatusEffect.STEALTH):
                    armor_pen_pct = max(armor_pen_pct, 0.30)
                if attacker.specialization == "beast_mastery" and ability.key == "auto_attack":
                    raw = int(raw * 1.4)
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
                        target.add_status(StatusEffect.BLEED, 8, 3, attacker.name)
                        r.effects_added.append("deep_wounds")

                r.damage = max(1, raw)
                target.current_hp = max(0, target.current_hp - r.damage)
                if target.current_hp <= 0:
                    target.is_dead = True

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
                    shield_val = max(6, int(actual_heal * 0.10))
                    heal_target.add_status(StatusEffect.SHIELD, shield_val, 1, "inspiration")
                    r.effects_added.append("inspiration")
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
                # Assassination passive: stronger bleed/poison effects.
                if attacker.specialization == "assassination" and ability.applies in {StatusEffect.BLEED, StatusEffect.POISON}:
                    effect_val = int(effect_val * 1.25)
                target.add_status(ability.applies, effect_val, ability.effect_dur, ability.key)
                r.effects_added.append(ability.applies.value)
                # Fire passive: bonus chance to ignite on fire spells.
                if attacker.specialization == "fire" and ability.key in {"fireball", "pyroblast", "dragon_breath"}:
                    if random.random() < 0.30:
                        target.add_status(StatusEffect.BURN, max(6, int((effect_val or 10) * 0.8)), 3, attacker.name)
                        r.effects_added.append("ignite")

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
            elif combatant.res_type == "rage":
                decay = max(3, int(combatant.max_res * 0.10))
                combatant.current_res = max(0, combatant.current_res - decay)

        return msgs

    # ── Enemy AI ──────────────────────────────────────────────────────────────

    def enemy_turn(
        self,
        enemy: Combatant,
        targets: List[Combatant],
        is_boss: bool = False,
        phase: int = 1,
    ) -> Tuple[str, List[Combatant]]:
        alive = [t for t in targets if not t.is_dead]
        if not alive:
            return "auto_attack", []

        # Highest-threat target (tank priority)
        target = max(alive, key=lambda t: t.threat)

        if not is_boss:
            if random.random() < 0.20:
                return "mortal_strike", [target]
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
        if boss.hp_pct <= 25: return 3
        if boss.hp_pct <= 50: return 2
        return 1

    # ── Rewards ───────────────────────────────────────────────────────────────

    def calculate_rewards(
        self,
        session: "CombatSession",
        xp_mult: float = 1.0,
        gold_mult: float = 1.0,
    ) -> Dict:
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
            "xp":         int(base_xp * xp_mult),
            "gold":       int(gold * gold_mult),
            "loot_rolls": loot_rolls,
        }

    # ── Narrative builder ─────────────────────────────────────────────────────

    def _narrative(self, r: CombatResult, ability: Ability) -> str:
        if r.is_dodge:
            return f"💨 **{r.target}** dodges **{r.attacker}**'s {ability.emoji} **{ability.name}**!"
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
