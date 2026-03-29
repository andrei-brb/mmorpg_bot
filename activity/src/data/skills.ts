export type SkillClass = 'shared' | 'warrior' | 'paladin' | 'mage' | 'rogue' | 'priest' | 'hunter';

export interface Skill {
  key: string;
  name: string;
  description: string;
  icon: string; // path to /skills/skill_<key>.png
  class: SkillClass;
  cost: string;
}

const skill = (key: string, name: string, description: string, cls: SkillClass, cost: string): Skill => ({
  key, name, description, icon: `/skills/skill_${key}.png`, class: cls, cost,
});

export const SKILLS: Skill[] = [
  // Shared
  skill('auto_attack', 'Auto Attack', 'A basic melee or ranged swing.', 'shared', '0 MP'),

  // Warrior
  skill('strike', 'Strike', 'A powerful melee strike.', 'warrior', '0 MP'),
  skill('battle_shout', 'Battle Shout', 'Boost attack power for 3 turns.', 'warrior', '10 MP'),
  skill('defensive_stance', 'Defensive Stance', 'Increases dodge for 3 turns.', 'warrior', '10 MP'),
  skill('mortal_strike', 'Mortal Strike', 'Devastating blow that causes bleeding.', 'warrior', '20 MP'),
  skill('whirlwind', 'Whirlwind', 'Spin and strike all enemies.', 'warrior', '25 MP'),
  skill('colossus_smash', 'Colossus Smash', 'Sunder armor, making target vulnerable.', 'warrior', '30 MP'),
  skill('shield_slam', 'Shield Slam', 'Ram your shield into the enemy, stunning them.', 'warrior', '15 MP'),
  skill('revenge', 'Revenge', 'Counter-attack after being hit.', 'warrior', '10 MP'),
  skill('last_stand', 'Last Stand', 'Temporarily bolster your HP.', 'warrior', '35 MP'),

  // Paladin
  skill('judgment', 'Judgment', 'Strike with holy power, ignoring armor.', 'paladin', '15 MP'),
  skill('holy_light', 'Holy Light', 'A powerful heal.', 'paladin', '20 MP'),
  skill('divine_shield', 'Divine Shield', 'Block the next enemy hit (persists until then).', 'paladin', '30 MP'),
  skill('crusader_strike', 'Crusader Strike', 'A righteous melee blow.', 'paladin', '0 MP'),
  skill('divine_storm', 'Divine Storm', 'Holy AoE that also heals you.', 'paladin', '25 MP'),
  skill('hammer_of_wrath', 'Hammer of Wrath', 'Execute — only usable below 20% enemy HP.', 'paladin', '20 MP'),
  skill('holy_shock', 'Holy Shock', 'Instant holy damage or heal.', 'paladin', '15 MP'),
  skill('beacon_of_light', 'Beacon of Light', 'Mark yourself with a healing regen.', 'paladin', '25 MP'),
  skill('lay_on_hands', 'Lay on Hands', 'Instantly restore a massive amount of HP.', 'paladin', '50 MP'),

  // Mage
  skill('fireball', 'Fireball', 'Hurl a ball of fire.', 'mage', '15 MP'),
  skill('frost_bolt', 'Frost Bolt', 'Frost bolt that slows the target.', 'mage', '15 MP'),
  skill('blink', 'Blink', 'Teleport, increasing dodge for 1 turn.', 'mage', '10 MP'),
  skill('pyroblast', 'Pyroblast', 'Massive fireball with a burn DoT.', 'mage', '35 MP'),
  skill('combustion', 'Combustion', 'Empower all fire spells for 3 turns.', 'mage', '30 MP'),
  skill('dragon_breath', "Dragon's Breath", 'Cone of fire that stuns.', 'mage', '25 MP'),
  skill('ice_lance', 'Ice Lance', 'Fast piercing frost shard.', 'mage', '10 MP'),
  skill('frozen_orb', 'Frozen Orb', 'AoE frost that slows all enemies.', 'mage', '30 MP'),
  skill('frost_nova', 'Frost Nova', 'Freeze all enemies in place.', 'mage', '20 MP'),

  // Rogue
  skill('sinister_strike', 'Sinister Strike', 'Quick precise stab.', 'rogue', '0 MP'),
  skill('stealth', 'Stealth', 'Vanish into shadows, entering stealth for a few turns.', 'rogue', '10 MP'),
  skill('eviscerate', 'Eviscerate', 'Rip through the target, causing bleed.', 'rogue', '20 MP'),
  skill('mutilate', 'Mutilate', 'Dual stab causing deep wounds.', 'rogue', '15 MP'),
  skill('envenom', 'Envenom', 'Inject lethal poison.', 'rogue', '25 MP'),
  skill('vendetta', 'Vendetta', 'Mark a target for bonus damage.', 'rogue', '20 MP'),
  skill('shadowstrike', 'Shadowstrike', 'A devastating attack from the shadows.', 'rogue', '25 MP'),
  skill('shadow_dance', 'Shadow Dance', 'Enter a state of rapid shadow strikes.', 'rogue', '35 MP'),
  skill('backstab', 'Backstab', 'Brutal stab ignoring armor.', 'rogue', '15 MP'),

  // Priest
  skill('heal', 'Heal', 'Restore HP to yourself.', 'priest', '15 MP'),
  skill('smite', 'Smite', 'Strike with holy energy.', 'priest', '10 MP'),
  skill('power_word_shield', 'Power Word: Shield', 'Create a damage-absorbing shield.', 'priest', '20 MP'),
  skill('mind_blast', 'Mind Blast', 'Shadow psychic assault.', 'priest', '20 MP'),
  skill('vampiric_touch', 'Vampiric Touch', 'Shadow DoT that drains life.', 'priest', '25 MP'),
  skill('void_eruption', 'Void Eruption', 'Unleash shadow energy on all foes.', 'priest', '40 MP'),
  skill('circle_of_healing', 'Circle of Healing', 'AoE heal for all allies.', 'priest', '30 MP'),
  skill('prayer_of_mending', 'Prayer of Mending', 'Place a HoT on yourself.', 'priest', '20 MP'),
  skill('guardian_spirit', 'Guardian Spirit', 'Prevent death once in the next 3 turns.', 'priest', '45 MP'),

  // Hunter
  skill('aimed_shot', 'Aimed Shot', 'Carefully aimed, high-damage shot.', 'hunter', '15 MP'),
  skill('multi_shot', 'Multi-Shot', 'Volley of arrows hits all enemies.', 'hunter', '20 MP'),
  skill('hunters_mark', "Hunter's Mark", 'Mark a target, making them vulnerable.', 'hunter', '10 MP'),
  skill('careful_aim', 'Careful Aim', 'Next shot deals massive damage.', 'hunter', '20 MP'),
  skill('rapid_fire', 'Rapid Fire', 'Quickly fire 3 shots in one turn.', 'hunter', '25 MP'),
  skill('double_tap', 'Double Tap', 'Fire twice at the same target.', 'hunter', '15 MP'),
  skill('bestial_wrath', 'Bestial Wrath', 'Your beast enters a frenzy, massive power boost.', 'hunter', '30 MP'),
  skill('dire_beast', 'Dire Beast', 'Summon a dire beast to attack.', 'hunter', '25 MP'),
  skill('kill_command', 'Kill Command', 'Command your beast to kill.', 'hunter', '20 MP'),
];

export const getSkillsByClass = (cls: SkillClass): Skill[] =>
  SKILLS.filter(s => s.class === cls || s.class === 'shared');

export const CLASS_LIST: { key: SkillClass; name: string; color: string }[] = [
  { key: 'warrior', name: 'Warrior', color: 'hsl(30 80% 55%)' },
  { key: 'paladin', name: 'Paladin', color: 'hsl(43 90% 55%)' },
  { key: 'mage', name: 'Mage', color: 'hsl(210 80% 60%)' },
  { key: 'rogue', name: 'Rogue', color: 'hsl(270 60% 55%)' },
  { key: 'priest', name: 'Priest', color: 'hsl(0 0% 85%)' },
  { key: 'hunter', name: 'Hunter', color: 'hsl(120 50% 50%)' },
];
