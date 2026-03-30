import { useState } from "react";
import { toast } from "sonner";

type DungeonConfigUi = {
  key: string;
  name: string;
  emoji: string;
  description: string;
  levelReq: number;
  floors: number;
  xpPerFloor: number;
  goldPerFloorMin: number;
  goldPerFloorMax: number;
};

const DUNGEONS: DungeonConfigUi[] = [
  {
    key: "deadmines",
    name: "The Deadmines",
    emoji: "⛏️",
    description: "A goblin mining operation turned bandit hideout. Watch for traps!",
    levelReq: 10,
    floors: 3,
    xpPerFloor: 150,
    goldPerFloorMin: 50,
    goldPerFloorMax: 150,
  },
  {
    key: "stockades",
    name: "The Stockades",
    emoji: "🔒",
    description: "Stormwind's maximum security prison. The inmates have taken over.",
    levelReq: 20,
    floors: 4,
    xpPerFloor: 250,
    goldPerFloorMin: 100,
    goldPerFloorMax: 250,
  },
  {
    key: "blackrock_depths_dungeon",
    name: "Blackrock Depths",
    emoji: "🌋",
    description: "A labyrinthine dungeon-city inside an active volcano. The ultimate challenge.",
    levelReq: 50,
    floors: 5,
    xpPerFloor: 500,
    goldPerFloorMin: 300,
    goldPerFloorMax: 600,
  },
];

const MOCK_PARTY = [
  { name: "Shadowblade", level: 25, isLeader: true },
  { name: "Lightbringer", level: 23, isLeader: false },
  { name: "Frostweaver", level: 24, isLeader: false },
];

const FLOOR_ENEMIES: Record<string, string[][]> = {
  deadmines: [
    ["Kobold Miner 🐀", "Defias Thug 🦹"],
    ["Goblin Engineer 💣", "Defias Overseer ⚔️"],
    ["⭐ Edwin VanCleef 🏴‍☠️"],
  ],
  stockades: [
    ["Crazed Inmate 😤", "Defias Prisoner 🔒"],
    ["Insurgent 🗡️", "Rioter 💢"],
    ["Kam Deepfury 👹", "Guard Captain ⚔️"],
    ["⭐ Bazil Thredd 👑"],
  ],
  blackrock_depths_dungeon: [
    ["Dark Iron Dwarf ⛏️", "Fire Imp 🔥"],
    ["Shadowforge Sentinel ⚔️", "Lava Elemental 🌋"],
    ["Molten Giant 🔥", "Dark Iron Sorcerer 🔮"],
    ["Magmadar 🐕‍🦺", "Flame Wraith 👻"],
    ["⭐ Emperor Thaurissan 👑"],
  ],
};

type DungeonView = "browser" | "running" | "floor_combat" | "complete" | "failed";

type FloorLog = { floor: number; text: string };

export type DungeonPanelProps = {
  playerLevel?: number;
};

export function DungeonPanel({ playerLevel = 25 }: DungeonPanelProps) {
  const [view, setView] = useState<DungeonView>("browser");
  const [activeDungeon, setActiveDungeon] = useState<DungeonConfigUi | null>(null);
  const [currentFloor, setCurrentFloor] = useState(1);
  const [playerHp, setPlayerHp] = useState(100);
  const [enemyHp, setEnemyHp] = useState(100);
  const [totalXp, setTotalXp] = useState(0);
  const [totalGold, setTotalGold] = useState(0);
  const [logs, setLogs] = useState<FloorLog[]>([]);

  const resetRun = () => {
    setView("browser");
    setActiveDungeon(null);
    setCurrentFloor(1);
    setPlayerHp(100);
    setEnemyHp(100);
    setTotalXp(0);
    setTotalGold(0);
    setLogs([]);
  };

  const onDungeonEnter = (dungeonKey: string) => {
    const d = DUNGEONS.find((x) => x.key === dungeonKey)!;
    setActiveDungeon(d);
    setCurrentFloor(1);
    setPlayerHp(100);
    setEnemyHp(100);
    setTotalXp(0);
    setTotalGold(0);
    setLogs([]);
    setView("running");
    toast(`Entering ${d.name}...`, { description: `${d.floors} floors await!` });
  };

  const onDungeonCreateParty = (dungeonKey: string) => {
    toast("Party flow later", { description: "Invite/start in Discord for now." });
    console.log("onDungeonCreateParty", dungeonKey);
  };

  const startFloorCombat = () => {
    setEnemyHp(100);
    setView("floor_combat");
  };

  const attackEnemy = () => {
    if (!activeDungeon) return;
    const dmg = Math.floor(Math.random() * 25 + 15);
    const enemyDmg = Math.floor(Math.random() * 12 + 3);
    const newEnemyHp = Math.max(0, enemyHp - dmg);
    const newPlayerHp = Math.max(0, playerHp - enemyDmg);
    setEnemyHp(newEnemyHp);
    setPlayerHp(newPlayerHp);

    const enemies = FLOOR_ENEMIES[activeDungeon.key]?.[currentFloor - 1] ?? ["Unknown Enemy"];
    setLogs((prev) => [
      ...prev,
      { floor: currentFloor, text: `⚔️ You deal ${dmg} damage to ${enemies[0]}` },
      { floor: currentFloor, text: `💥 ${enemies[0]} hits you for ${enemyDmg} damage` },
    ]);

    if (newPlayerHp <= 0) {
      setLogs((prev) => [...prev, { floor: currentFloor, text: "💀 You have been defeated..." }]);
      setView("failed");
      return;
    }

    if (newEnemyHp <= 0) {
      const floorXp = activeDungeon.xpPerFloor;
      const floorGold =
        Math.floor(Math.random() * (activeDungeon.goldPerFloorMax - activeDungeon.goldPerFloorMin)) +
        activeDungeon.goldPerFloorMin;
      setTotalXp((prev) => prev + floorXp);
      setTotalGold((prev) => prev + floorGold);
      setLogs((prev) => [
        ...prev,
        { floor: currentFloor, text: `✅ Floor ${currentFloor} cleared! +${floorXp} XP, +${floorGold} 🪙` },
      ]);

      if (currentFloor >= activeDungeon.floors) {
        setView("complete");
      } else {
        setCurrentFloor((f) => f + 1);
        setView("running");
      }
    }
  };

  const usePotion = () => {
    const heal = Math.floor(Math.random() * 15 + 20);
    setPlayerHp((hp) => Math.min(100, hp + heal));
    setLogs((prev) => [...prev, { floor: currentFloor, text: `🧪 Used potion! +${heal} HP` }]);
    toast(`Healed for ${heal} HP`);
  };

  const flee = () => {
    toast("You fled the dungeon!");
    setLogs((prev) => [...prev, { floor: currentFloor, text: "🏃 You fled the dungeon!" }]);
    resetRun();
  };

  if (view === "complete" && activeDungeon) {
    return (
      <div className="space-y-4">
        <div className="game-panel text-center py-8">
          <div className="text-5xl mb-4" style={{ filter: "drop-shadow(0 2px 6px hsl(0 0% 0% / 0.6))" }}>🏆</div>
          <h2
            className="font-cinzel text-xl font-bold text-foreground mb-1"
            style={{ textShadow: "0 0 8px hsl(43 78% 50% / 0.3)" }}
          >
            Dungeon Complete!
          </h2>
          <p className="text-sm text-muted-foreground mb-1">
            {activeDungeon.emoji} {activeDungeon.name}
          </p>
          <div className="ornament-divider my-3 mx-auto max-w-[200px]" />
          <div className="flex justify-center gap-6 mb-4">
            <div className="text-center">
              <p className="text-xs text-muted-foreground font-cinzel uppercase tracking-wider">XP Earned</p>
              <p className="text-lg font-bold text-primary" style={{ textShadow: "0 0 6px hsl(43 78% 50% / 0.3)" }}>
                {totalXp}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground font-cinzel uppercase tracking-wider">Gold Earned</p>
              <p className="text-lg font-bold text-primary" style={{ textShadow: "0 0 6px hsl(43 78% 50% / 0.3)" }}>
                {totalGold} 🪙
              </p>
            </div>
          </div>
          <button type="button" onClick={resetRun} className="game-btn-primary px-6 py-2">
            Return to Dungeons
          </button>
        </div>

        <div className="game-panel max-h-32 overflow-y-auto">
          <div className="game-panel-header">Run Log</div>
          <div className="space-y-1">
            {logs.map((l, i) => (
              <p key={i} className="text-xs text-muted-foreground">
                <span className="text-foreground/40">[F{l.floor}]</span> {l.text}
              </p>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (view === "failed" && activeDungeon) {
    return (
      <div className="space-y-4">
        <div className="game-panel text-center py-8">
          <div className="text-5xl mb-4" style={{ filter: "drop-shadow(0 2px 6px hsl(0 0% 0% / 0.6))" }}>💀</div>
          <h2 className="font-cinzel text-xl font-bold text-foreground mb-1">Dungeon Failed</h2>
          <p className="text-sm text-muted-foreground mb-1">
            Defeated on floor {currentFloor} of {activeDungeon.name}
          </p>
          <div className="ornament-divider my-3 mx-auto max-w-[200px]" />
          <p className="text-xs text-muted-foreground mb-4">
            You kept {Math.floor(totalXp * 0.5)} XP and {Math.floor(totalGold * 0.5)} 🪙 (50% penalty)
          </p>
          <div className="flex gap-3 justify-center">
            <button type="button" onClick={resetRun} className="game-btn-primary px-5 py-2">
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (view === "floor_combat" && activeDungeon) {
    const enemies = FLOOR_ENEMIES[activeDungeon.key]?.[currentFloor - 1] ?? ["Unknown Enemy"];
    const isBoss = currentFloor === activeDungeon.floors;

    return (
      <div className="space-y-4">
        <div className="game-panel py-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground font-cinzel tracking-wider">
            {activeDungeon.emoji} {activeDungeon.name}
          </span>
          <span
            className={`text-xs font-pixel ${isBoss ? "text-destructive" : "text-primary"}`}
            style={{ textShadow: isBoss ? "0 0 4px hsl(0 68% 46% / 0.4)" : "0 0 4px hsl(43 78% 50% / 0.3)" }}
          >
            Floor {currentFloor}/{activeDungeon.floors} {isBoss ? "⭐ BOSS" : ""}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="game-panel text-center">
            <div className="text-3xl mb-2" style={{ filter: "drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))" }}>🧝</div>
            <p className="text-sm font-cinzel font-semibold text-foreground">You</p>
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">HP</span>
                <span className="text-foreground tabular-nums">{playerHp}/100</span>
              </div>
              <div className="hp-bar-track">
                <div
                  className="hp-bar-fill"
                  style={{
                    width: `${playerHp}%`,
                    background:
                      playerHp <= 25
                        ? "linear-gradient(90deg, hsl(0 68% 46%), hsl(0 60% 55%))"
                        : undefined,
                  }}
                />
              </div>
            </div>
          </div>
          <div className="game-panel text-center">
            <div className="text-3xl mb-2" style={{ filter: "drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))" }}>
              {isBoss ? "👹" : "⚔️"}
            </div>
            <p className="text-sm font-cinzel font-semibold text-foreground truncate">{enemies[0]}</p>
            {enemies.length > 1 && <p className="text-[10px] text-muted-foreground">+{enemies.length - 1} more</p>}
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">HP</span>
                <span className="text-foreground tabular-nums">{enemyHp}/100</span>
              </div>
              <div className="hp-bar-track">
                <div className="hp-bar-fill" style={{ width: `${enemyHp}%` }} />
              </div>
            </div>
          </div>
        </div>

        <div className="game-panel">
          <div className="game-panel-header">Actions</div>
          <div className="grid grid-cols-3 gap-2">
            <button type="button" onClick={attackEnemy} className="game-btn-primary text-xs py-2">
              ⚔️ Attack
            </button>
            <button type="button" onClick={usePotion} className="game-btn-secondary text-xs py-2">
              🧪 Potion
            </button>
            <button type="button" onClick={flee} className="game-btn-danger text-xs py-2">
              🏃 Flee
            </button>
          </div>
        </div>

        <div className="game-panel max-h-28 overflow-y-auto">
          <div className="game-panel-header">Combat Log</div>
          <div className="space-y-1">
            {logs
              .filter((l) => l.floor === currentFloor)
              .map((l, i) => (
                <p key={i} className="text-xs text-muted-foreground">{l.text}</p>
              ))}
            {logs.filter((l) => l.floor === currentFloor).length === 0 && (
              <p className="text-xs text-muted-foreground/50 italic">Ready to fight...</p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-center gap-1">
          {Array.from({ length: activeDungeon.floors }).map((_, i) => (
            <div
              key={i}
              className={`w-5 h-5 rounded-sm border text-[10px] flex items-center justify-center font-pixel ${
                i < currentFloor - 1
                  ? "border-primary/60 bg-primary/20 text-primary"
                  : i === currentFloor - 1
                    ? "border-primary bg-primary/30 text-primary ring-1 ring-primary/40"
                    : "border-border bg-muted/30 text-muted-foreground"
              }`}
            >
              {i + 1}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (view === "running" && activeDungeon) {
    const enemies = FLOOR_ENEMIES[activeDungeon.key]?.[currentFloor - 1] ?? ["Unknown Enemy"];
    const isBoss = currentFloor === activeDungeon.floors;

    return (
      <div className="space-y-4">
        <div className="game-panel">
          <div className="game-panel-header">
            {activeDungeon.emoji} {activeDungeon.name} — Floor {currentFloor}/{activeDungeon.floors}
          </div>

          <div className="flex items-center gap-1 mb-4">
            {Array.from({ length: activeDungeon.floors }).map((_, i) => (
              <div
                key={i}
                className={`w-6 h-6 rounded-sm border text-[10px] flex items-center justify-center font-pixel ${
                  i < currentFloor - 1
                    ? "border-primary/60 bg-primary/20 text-primary"
                    : i === currentFloor - 1
                      ? "border-primary bg-primary/30 text-primary ring-1 ring-primary/40"
                      : "border-border bg-muted/30 text-muted-foreground"
                }`}
              >
                {i + 1}
              </div>
            ))}
            <span className="text-[10px] text-muted-foreground ml-2 font-cinzel">
              {isBoss ? "⭐ BOSS FLOOR" : `Floor ${currentFloor}`}
            </span>
          </div>

          <div className="mb-4">
            <p className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-2">
              Party ({MOCK_PARTY.length}/5)
            </p>
            <div className="flex gap-2 flex-wrap">
              {MOCK_PARTY.map((m) => (
                <div
                  key={m.name}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-sm text-xs"
                  style={{
                    background: "hsl(228 18% 14% / 0.6)",
                    border: "1px solid hsl(228 16% 20% / 0.5)",
                  }}
                >
                  {m.isLeader && <span className="text-primary text-[10px]">👑</span>}
                  <span className="text-foreground font-semibold">{m.name}</span>
                  <span className="text-muted-foreground text-[10px]">Lv{m.level}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="ornament-divider my-3" />

          <div className="mb-4">
            <p className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground mb-2">
              {isBoss ? "⭐ Boss Encounter" : "Enemies on this floor"}
            </p>
            <div className="space-y-1">
              {enemies.map((e, i) => (
                <p key={i} className={`text-xs ${isBoss ? "text-destructive font-semibold" : "text-foreground"}`}>
                  {e}
                </p>
              ))}
            </div>
          </div>

          <div className="mb-4">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">Your HP</span>
              <span className="text-foreground tabular-nums">{playerHp}/100</span>
            </div>
            <div className="hp-bar-track">
              <div
                className="hp-bar-fill"
                style={{
                  width: `${playerHp}%`,
                  background:
                    playerHp <= 25
                      ? "linear-gradient(90deg, hsl(0 68% 46%), hsl(0 60% 55%))"
                      : undefined,
                }}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button type="button" onClick={startFloorCombat} className="game-btn-danger text-xs px-4 py-2 flex-1">
              ⚔️ {isBoss ? "Fight Boss!" : `Fight Floor ${currentFloor}`}
            </button>
            <button type="button" onClick={usePotion} className="game-btn-secondary text-xs px-4 py-2">
              🧪 Potion
            </button>
            <button type="button" onClick={flee} className="game-btn-secondary text-xs px-4 py-2">
              🏃 Flee
            </button>
          </div>
        </div>

        {logs.length > 0 && (
          <div className="game-panel max-h-28 overflow-y-auto">
            <div className="game-panel-header">Run Log</div>
            <div className="space-y-1">
              {logs.map((l, i) => (
                <p key={i} className="text-xs text-muted-foreground">
                  <span className="text-foreground/40">[F{l.floor}]</span> {l.text}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">⚔️ Dungeons</div>
        <p className="text-xs text-muted-foreground mb-4">
          Instanced runs with multiple floors. Mock run — connect to server APIs later.
        </p>

        <div className="space-y-3">
          {DUNGEONS.map((d) => {
            const locked = playerLevel < d.levelReq;
            return (
              <div
                key={d.key}
                className={`rounded-sm transition-all ${locked ? "opacity-50" : ""}`}
                style={{
                  background: locked
                    ? "linear-gradient(180deg, hsl(228 18% 10%) 0%, hsl(228 20% 8%) 100%)"
                    : "linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)",
                  border: locked ? "1px solid hsl(228 16% 16%)" : "1px solid hsl(43 50% 35% / 0.4)",
                  boxShadow: locked ? "none" : "0 0 8px hsl(43 78% 50% / 0.05)",
                }}
              >
                <div className="p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-lg" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.5))" }}>
                          {d.emoji}
                        </span>
                        <h3 className="font-cinzel font-semibold text-sm text-foreground truncate">{d.name}</h3>
                        {locked && <span className="text-[10px] text-destructive font-pixel shrink-0">🔒 LOCKED</span>}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{d.description}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px]">
                        <span className="text-muted-foreground">
                          Lv <span className="text-foreground font-semibold">{d.levelReq}+</span>
                        </span>
                        <span className="text-muted-foreground">
                          Floors <span className="text-foreground font-semibold">{d.floors}</span>
                        </span>
                        <span className="text-muted-foreground">
                          XP <span className="text-primary font-semibold">{d.xpPerFloor}/floor</span>
                        </span>
                        <span className="text-muted-foreground">
                          Gold{" "}
                          <span className="text-primary font-semibold">
                            {d.goldPerFloorMin}–{d.goldPerFloorMax} 🪙/floor
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => onDungeonEnter(d.key)}
                      disabled={locked}
                      className={`text-xs px-3 py-1.5 flex-1 ${locked ? "game-btn-secondary opacity-50 cursor-not-allowed" : "game-btn-primary"}`}
                    >
                      ⚔️ Enter Solo
                    </button>
                    <button
                      type="button"
                      onClick={() => onDungeonCreateParty(d.key)}
                      disabled={locked}
                      className={`text-xs px-3 py-1.5 flex-1 ${locked ? "game-btn-secondary opacity-50 cursor-not-allowed" : "game-btn-secondary"}`}
                    >
                      👥 Create Party
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
