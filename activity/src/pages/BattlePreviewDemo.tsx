import BattlePreview, {
  type BattlePreviewData,
  type BuffDebuff,
  type Item,
  type Skill,
} from "@/components/BattlePreview";

const base = import.meta.env.BASE_URL || "/";

const playerSkills: Skill[] = [
  {
    id: "ps1",
    name: "Lightning Strike",
    icon: "⚡",
    element: "lightning",
    damage: 45,
    manaCost: 12,
    cooldown: 3,
    level: 5,
    description: "Calls down a bolt of lightning on a single target, dealing heavy lightning damage.",
    keybind: "1",
  },
  {
    id: "ps2",
    name: "Shadow Step",
    icon: "🌑",
    element: "dark",
    damage: 20,
    manaCost: 8,
    cooldown: 5,
    level: 3,
    description: "Vanish into shadows and reappear behind the enemy, striking from behind.",
    keybind: "2",
  },
  {
    id: "ps3",
    name: "Rain of Arrows",
    icon: "🏹",
    damage: 35,
    manaCost: 18,
    cooldown: 6,
    level: 4,
    description: "Unleash a barrage of arrows covering a wide area. Hits all enemies.",
    keybind: "3",
  },
  {
    id: "ps4",
    name: "Thunder Trap",
    icon: "⚡",
    element: "lightning",
    damage: 30,
    manaCost: 15,
    cooldown: 8,
    level: 3,
    description: "Place an electrified trap that stuns and damages enemies who trigger it.",
    keybind: "4",
    isReady: false,
  },
  {
    id: "ps5",
    name: "Evasion",
    icon: "💨",
    manaCost: 5,
    cooldown: 10,
    level: 2,
    description: "Greatly increases dodge rate for 3 turns. Cannot be targeted by physical attacks.",
    keybind: "5",
  },
  {
    id: "ps6",
    name: "Hunter's Mark",
    icon: "🎯",
    manaCost: 6,
    cooldown: 4,
    level: 4,
    description: "Mark a target, increasing all damage dealt to them by 25% for 4 turns.",
    keybind: "6",
  },
];

const enemySkills: Skill[] = [
  {
    id: "es1",
    name: "Earthen Slam",
    icon: "🌍",
    element: "earth",
    damage: 55,
    manaCost: 14,
    cooldown: 4,
    level: 6,
    description: "Slam the ground with immense force, sending shockwaves through the earth.",
    keybind: "1",
  },
];

const items: Item[] = [
  { id: "i1", name: "Health Potion", icon: "🧪", quantity: 5, description: "Restores 30 HP instantly." },
  { id: "i2", name: "Mana Elixir", icon: "💧", quantity: 3, description: "Restores 20 MP instantly." },
  { id: "i3", name: "Antidote", icon: "🌿", quantity: 2, description: "Cures poison status." },
  { id: "i4", name: "Smoke Bomb", icon: "💨", quantity: 1, description: "Escape from battle." },
  { id: "i5", name: "Fire Bomb", icon: "🔥", quantity: 4, description: "Deals 25 fire damage to all enemies." },
  { id: "i6", name: "Shield Scroll", icon: "📜", quantity: 2, description: "Grants +10 DEF for 3 turns." },
];

const buffs: BuffDebuff[] = [
  { id: "b1", name: "Swift Feet", icon: "💨", type: "buff", duration: "3 turns" },
  { id: "b2", name: "Lightning Aura", icon: "⚡", type: "buff", duration: "5 turns" },
  { id: "b3", name: "Minor Bleed", icon: "🩸", type: "debuff", duration: "2 turns" },
];

const mockBattle: BattlePreviewData = {
  backgroundUrl: "",
  battlefieldZoneKey: "dun_morogh",
  centerActionLabel: "⚔️ Combat History",
  gridRows: 3,
  gridCols: 3,
  units: [
    { id: "u1", label: "🗡️", row: 1, col: 0 },
    { id: "u2", label: "🛡️", row: 2, col: 1 },
    { id: "u3", label: "🏹", row: 0, col: 2 },
  ],
  playerSkills,
  enemySkills,
  items,
  buffs,
  showRpgPanel: true,
  player: {
    name: "Captain Vel Dina",
    title: "The Swift Blade",
    level: 28,
    class: "Ranger",
    element: "lightning",
    portraitUrl: `${base}placeholder.svg`,
    stats: [
      { label: "HP", value: "66 / 66" },
      { label: "Attack Power", value: 26 },
      { label: "Defense", value: 25 },
      { label: "Accuracy", value: "100%" },
    ],
    statuses: [
      { effect: "bleed", value: 12, duration: 2 },
      { effect: "shield", value: 240, duration: 1 },
    ],
  },
  enemy: {
    name: "Greg Ironheart",
    title: "The Unyielding",
    level: 35,
    class: "Warlord",
    element: "earth",
    isBoss: true,
    portraitUrl: `${base}placeholder.svg`,
    weakness: "WEAK",
    indicators: ["???", "???", "???"],
    intent: {
      name: "Lava Breath",
      emoji: "🌋",
      tell: "its throat glows red",
      kind: "sweep",
      severity: 3,
      isAoe: true,
      elemental: true,
    },
    statuses: [{ effect: "power_up", value: 30, duration: 2 }],
    stats: [
      { label: "HP", value: "150 / 150" },
      { label: "Attack Power", value: 35 },
      { label: "Defense", value: 32 },
      { label: "Accuracy", value: "100%" },
    ],
  },
  onCommence: () => alert("Combat history (demo)"),
};

/**
 * Standalone battle preview demo — open at `/battle-preview-demo`.
 * Production combat still uses `<GameShell />` at `/`.
 */
export default function BattlePreviewDemo() {
  return (
    <div className="min-h-screen bg-background p-4 flex items-center justify-center">
      <div className="w-full max-w-6xl">
        <BattlePreview data={mockBattle} />
      </div>
    </div>
  );
}
