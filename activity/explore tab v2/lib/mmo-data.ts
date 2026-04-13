export type Faction = "alliance" | "horde" | "neutral" | "hostile"
export type OutcomeType = "enemy" | "boss" | "loot" | "safe" | "npc"

export interface Zone {
  id: string
  name: string
  emoji: string
  levelRange: [number, number]
  faction: Faction
  playersNearby: number
  bossAlive: boolean
  description: string
  regionHint?: string
}

export interface NPC {
  id: string
  name: string
  title: string
  silhouette: string // emoji stand-in for portrait
  discoveryQuote?: string
  alreadyMet: boolean
}

export interface ExploreReward {
  xp?: number
  gold?: number
}

export interface ExploreResult {
  id: string
  type: OutcomeType
  message: string
  reward?: ExploreReward
  npc?: NPC
  enemyName?: string
  enemyLevel?: number
  isBoss?: boolean
  timestamp: Date
}

export const ZONES: Zone[] = [
  {
    id: "elwynn",
    name: "Elwynn Forest",
    emoji: "🌲",
    levelRange: [1, 10],
    faction: "alliance",
    playersNearby: 4,
    bossAlive: false,
    description: "Rolling hills of ancient oak shelter both wanderers and wolves.",
    regionHint: "Rumours speak of a missing patrol — locals blame something darker than wolves.",
  },
  {
    id: "stranglethorn",
    name: "Stranglethorn Vale",
    emoji: "🌴",
    levelRange: [25, 45],
    faction: "neutral",
    playersNearby: 1,
    bossAlive: true,
    description: "Thick jungle canopy hides ruins older than memory — and the gangs that claim them.",
    regionHint: "The Bloodsail Buccaneers grow bolder near Booty Bay.",
  },
  {
    id: "plaguelands",
    name: "Eastern Plaguelands",
    emoji: "💀",
    levelRange: [50, 60],
    faction: "hostile",
    playersNearby: 0,
    bossAlive: true,
    description: "The Scourge's blight bleeds from every cracked stone of this cursed land.",
    regionHint: "Stratholme's gates remain sealed — the main story quest demands entry.",
  },
  {
    id: "barrens",
    name: "The Barrens",
    emoji: "🏜️",
    levelRange: [10, 25],
    faction: "horde",
    playersNearby: 7,
    bossAlive: false,
    description: "Vast sunburned plains where centaur outriders test the courage of every traveller.",
  },
  {
    id: "winterspring",
    name: "Winterspring",
    emoji: "❄️",
    levelRange: [55, 60],
    faction: "neutral",
    playersNearby: 2,
    bossAlive: false,
    description: "Frost-choked valleys whisper of lost Kaldorei knowledge — and the Furbolg who guard it.",
  },
  {
    id: "silithus",
    name: "Silithus",
    emoji: "🐛",
    levelRange: [55, 60],
    faction: "hostile",
    playersNearby: 0,
    bossAlive: true,
    description: "The Old God's dream festers beneath these sands. Nothing here is truly dead.",
    regionHint: "C'Thun stirs — the final chapter of the main story begins here.",
  },
]

export const SAMPLE_RESULTS: ExploreResult[] = [
  {
    id: "r1",
    type: "enemy",
    message: "A Bloodsail Corsair springs from the undergrowth, cutlass drawn!",
    enemyName: "Bloodsail Corsair",
    enemyLevel: 38,
    isBoss: false,
    timestamp: new Date(Date.now() - 90_000),
  },
  {
    id: "r2",
    type: "safe",
    message: "You follow an overgrown path to a crumbling stone vista. The jungle stretches endlessly below. A pleasant silence settles over you.",
    reward: { xp: 120 },
    timestamp: new Date(Date.now() - 210_000),
  },
  {
    id: "r3",
    type: "npc",
    message: "A weathered figure crouches by a fire, studying a frayed map.",
    npc: {
      id: "npc_grol",
      name: "Grol the Wanderer",
      title: "Disgraced Scout",
      silhouette: "🧙",
      discoveryQuote: "\"These routes have not been safe for months. Something moves through the trees at night.\"",
      alreadyMet: false,
    },
    reward: { xp: 80 },
    timestamp: new Date(Date.now() - 360_000),
  },
]
