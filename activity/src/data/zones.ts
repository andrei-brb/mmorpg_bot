export interface Mob {
  key: string;
  name: string;
  icon: string; // path to /mobs/<key>.<ext>
  level: number;
}

export interface Boss {
  key: string;
  name: string;
  icon: string; // path to /bosses/<key>.<ext>
  level: number;
  abilities: string[];
}

export interface Zone {
  key: string;
  name: string;
  levelRange: [number, number];
  faction: 'Alliance' | 'Horde' | 'Neutral';
  mobs: Mob[];
  bosses: Boss[];
}

const mob = (key: string, name: string, level: number): Mob => ({
  key, name, icon: `/mobs/${key}.png`, level,
});

const boss = (key: string, name: string, level: number, abilities: string[] = []): Boss => ({
  key, name, icon: `/bosses/${key}.png`, level, abilities,
});

export const ZONES: Zone[] = [
  // ── Elwynn Forest ──
  {
    key: 'elwynn_forest',
    name: 'Elwynn Forest',
    levelRange: [1, 10],
    faction: 'Alliance',
    mobs: [
      mob('forest_wolf', 'Forest Wolf', 3),
      mob('kobold', 'Kobold', 4),
      mob('defias_bandit', 'Defias Bandit', 6),
      mob('young_boar', 'Young Boar', 2),
      mob('goldshire_guard', 'Corrupted Guard', 7),
      mob('spider', 'Giant Spider', 5),
      mob('murloc_scout', 'Murloc Scout', 6),
      mob('gnoll_raider', 'Gnoll Raider', 8),
    ],
    bosses: [
      boss('hogger', 'Hogger', 10, ['cleave', 'enrage']),
      boss('defias_ringleader', 'Defias Ringleader', 9, ['backstab', 'poison']),
      boss('spider_queen', 'Spider Queen', 10, ['web', 'poison']),
      boss('murloc_warlord', 'Murloc Warlord', 10, ['summon', 'frenzy']),
    ],
  },

  // ── Dun Morogh ──
  {
    key: 'dun_morogh',
    name: 'Dun Morogh',
    levelRange: [1, 10],
    faction: 'Alliance',
    mobs: [
      mob('ice_claw_bear', 'Ice Claw Bear', 4),
      mob('trogg', 'Trogg', 3),
      mob('frostmane_troll', 'Frostmane Troll', 6),
      mob('snow_leopard', 'Snow Leopard', 5),
      mob('frozen_wraith', 'Frozen Wraith', 7),
      mob('ice_elemental', 'Ice Elemental', 8),
      mob('winter_wolf', 'Winter Wolf', 4),
      mob('cave_bat', 'Cave Bat', 3),
      mob('frostmane_shaman', 'Frostmane Shaman', 7),
    ],
    bosses: [
      boss('frostmane_headhunter', 'Frostmane Headhunter', 9),
      boss('ice_lord', 'Ice Lord', 10, ['frost_nova', 'freeze']),
      boss('trogg_overlord', 'Trogg Overlord', 10, ['stomp', 'enrage']),
      boss('ancient_frost_giant', 'Ancient Frost Giant', 10, ['ice_slam', 'blizzard']),
    ],
  },

  // ── The Barrens ──
  {
    key: 'barrens',
    name: 'The Barrens',
    levelRange: [10, 25],
    faction: 'Horde',
    mobs: [
      mob('razormane_warrior', 'Razormane Warrior', 12),
      mob('plainstrider', 'Plainstrider', 11),
      mob('sunscale_raptor', 'Sunscale Raptor', 14),
      mob('barrens_scorpion', 'Barrens Scorpion', 13),
      mob('zhevra', 'Zhevra', 12),
      mob('thunder_lizard', 'Thunder Lizard', 18),
      mob('quillboar', 'Quillboar', 15),
      mob('wind_sweeper', 'Wind Sweeper', 16),
      mob('barrens_vulture', 'Barrens Vulture', 14),
    ],
    bosses: [
      boss('kolkar_centaur_lord', 'Kolkar Centaur Lord', 20),
      boss('razormane_chieftain', 'Razormane Chieftain', 22, ['war_cry', 'charge']),
      boss('thunderhawk_alpha', 'Thunderhawk Alpha', 23, ['lightning_strike', 'dive']),
      boss('barrens_overlord', 'Barrens Overlord', 25, ['earthquake', 'summon']),
    ],
  },

  // ── Stranglethorn Vale ──
  {
    key: 'stranglethorn',
    name: 'Stranglethorn Vale',
    levelRange: [25, 45],
    faction: 'Neutral',
    mobs: [
      mob('bloodsail_pirate', 'Bloodsail Pirate', 28),
      mob('jungle_stalker', 'Jungle Stalker', 30),
      mob('venture_co_enforcer', 'Venture Co. Enforcer', 32),
      mob('panther', 'Panther', 27),
      mob('tiger', 'Tiger', 29),
      mob('basilisk', 'Basilisk', 33),
      mob('jungle_troll', 'Jungle Troll', 31),
      mob('crocodile', 'Giant Crocodile', 34),
      mob('stranglethorn_ape', 'Stranglethorn Ape', 35),
      mob('bloodsail_corsair', 'Bloodsail Corsair', 36),
    ],
    bosses: [
      boss('kurzen_the_mad', 'Kurzen the Mad', 40, ['madness_wave', 'blood_frenzy']),
      boss('bhag_thera', "Bhag'thera", 42),
      boss('bloodsail_admiral', 'Bloodsail Admiral', 43, ['cannon_blast', 'boarding']),
      boss('jungle_lord', 'Jungle Lord', 45, ['beast_call', 'frenzy']),
    ],
  },

  // ── Blackrock Depths ──
  {
    key: 'blackrock_depths',
    name: 'Blackrock Depths',
    levelRange: [50, 60],
    faction: 'Neutral',
    mobs: [
      mob('dark_iron_dwarf', 'Dark Iron Dwarf', 52),
      mob('molten_giant', 'Molten Giant', 55),
      mob('firelord_servant', 'Firelord Servant', 54),
      mob('lava_elemental', 'Lava Elemental', 53),
      mob('dark_iron_guard', 'Dark Iron Guard', 54),
      mob('fire_imp', 'Fire Imp', 51),
      mob('shadowforge_sentinel', 'Shadowforge Sentinel', 56),
      mob('magma_lord', 'Magma Lord', 57),
      mob('dark_iron_sorcerer', 'Dark Iron Sorcerer', 55),
      mob('flame_wraith', 'Flame Wraith', 53),
    ],
    bosses: [
      boss('emperor_dagran_thaurissan', 'Emperor Thaurissan', 60, ['imperial_decree', 'shadowflame', 'enrage']),
      boss('lord_incendius', 'Lord Incendius', 58, ['flame_nova', 'inferno']),
      boss('magmadar', 'Magmadar', 59, ['lava_breath', 'molten_armor']),
      boss('golem_lord', 'Golem Lord', 57, ['crush', 'stomp']),
    ],
  },
];

export const getZoneByKey = (key: string): Zone | undefined =>
  ZONES.find(z => z.key === key);
