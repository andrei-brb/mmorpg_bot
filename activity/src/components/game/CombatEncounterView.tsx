import { useEffect, useMemo, useRef, useState } from "react";
import type { CombatStatePayload, ExploreZone, InventoryPayload, PartyCombatRow } from "@/lib/apiTypes";
import { classIconUrl, specIconUrl } from "@/lib/classAndSpecIconUrl";
import { BattleBackground } from "@/components/game/combat/BattleBackground";
import { CombatSkillButton } from "@/components/game/combat/CombatSkillButton";
import { BattleFighter } from "@/components/game/combat/BattleFighter";
import { DamageNumbers, type DamageEvent } from "@/components/game/combat/DamageNumber";
import { TurnOrder } from "@/components/game/combat/TurnOrder";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
}

function battleBackgroundZone(zoneKey?: string): string {
  if (!zoneKey) return "volcano";
  const k = zoneKey.toLowerCase();
  if (k.includes("forest") || k.includes("wood")) return "forest";
  if (k.includes("grave") || k.includes("crypt")) return "graveyard";
  if (k.includes("dungeon") || k.includes("depth") || k.includes("shadow")) return "dungeon";
  return "volcano";
}

function classEmoji(classKey: string): string {
  const m: Record<string, string> = {
    warrior: "🛡️",
    paladin: "⚔️",
    mage: "🧙",
    rogue: "🗡️",
    priest: "✨",
    hunter: "🏹",
    shared: "🧝",
  };
  return m[classKey] || "🧝";
}

function firstTokenEmoji(name: string): string {
  const parts = name.trim().split(/\s+/);
  const t = parts[0] || "";
  return t && /[^\w\s]/.test(t) ? t : "👾";
}

export type CombatEncounterViewProps = {
  focusMode?: boolean;
  zoneLabel?: ExploreZone;
  state: CombatStatePayload;
  inventory: InventoryPayload | null;
  loading: boolean;
  onAbility: (key: string) => void;
  onFlee: () => void;
  onPotion: () => void;
  /** Discord /dungeon DB run — show party placeholders */
  showDiscordDungeonBanner?: boolean;
  /** Activity Dungeon tab — custom header (zone bar replaced) */
  dungeonHeader?: { emoji: string; name: string; floor: number; totalFloors: number };
};

export function CombatEncounterView({
  focusMode,
  zoneLabel,
  state,
  inventory,
  loading,
  onAbility,
  onFlee,
  onPotion,
  showDiscordDungeonBanner,
  dungeonHeader,
}: CombatEncounterViewProps) {
  const [showLogModal, setShowLogModal] = useState(false);
  const classKey = state.player.class || inventory?.character?.class || "";
  const specKey = state.player.specialization || inventory?.character?.specialization || "";
  const partyMode = Boolean(state.party_mode && state.party_players && state.party_players.length > 0);
  const canAct = !state.party_mode || state.your_turn === true;

  const encounterKey = `${state.enemy.name}-${state.enemy.max_hp}-${state.player.max_hp}`;
  const prevKeyRef = useRef<string | null>(null);
  const prevHpRef = useRef({ p: state.player.current_hp, e: state.enemy.current_hp });
  const damageIdRef = useRef(0);
  const [damageEvents, setDamageEvents] = useState<DamageEvent[]>([]);
  const [playerHit, setPlayerHit] = useState(false);
  const [enemyHit, setEnemyHit] = useState(false);
  const [playerAttacking, setPlayerAttacking] = useState(false);
  const [enemyAttacking, setEnemyAttacking] = useState(false);

  useEffect(() => {
    if (prevKeyRef.current !== encounterKey) {
      prevKeyRef.current = encounterKey;
      prevHpRef.current = { p: state.player.current_hp, e: state.enemy.current_hp };
      setDamageEvents([]);
      return;
    }
    const prev = prevHpRef.current;
    const p = state.player.current_hp;
    const e = state.enemy.current_hp;
    const logs = (state.log || []).filter(Boolean);
    const lastLog = logs[logs.length - 1] || "";
    const isCrit = /\bcrit/i.test(lastLog);

    const next: DamageEvent[] = [];
    if (e < prev.e) {
      next.push({
        id: ++damageIdRef.current,
        value: prev.e - e,
        isCrit,
        isHeal: false,
        side: "enemy",
      });
    } else if (e > prev.e) {
      next.push({
        id: ++damageIdRef.current,
        value: e - prev.e,
        isCrit: false,
        isHeal: true,
        side: "enemy",
      });
    }
    if (p < prev.p) {
      next.push({
        id: ++damageIdRef.current,
        value: prev.p - p,
        isCrit,
        isHeal: false,
        side: "player",
      });
    } else if (p > prev.p) {
      next.push({
        id: ++damageIdRef.current,
        value: p - prev.p,
        isCrit: false,
        isHeal: true,
        side: "player",
      });
    }

    prevHpRef.current = { p, e };
    if (next.length === 0) return;

    setDamageEvents((ev) => [...ev, ...next].slice(-14));

    const timers: number[] = [];
    if (e < prev.e) {
      setPlayerAttacking(true);
      setEnemyHit(true);
      timers.push(window.setTimeout(() => setPlayerAttacking(false), 480));
      timers.push(window.setTimeout(() => setEnemyHit(false), 420));
    }
    if (p < prev.p) {
      setEnemyAttacking(true);
      setPlayerHit(true);
      timers.push(window.setTimeout(() => setEnemyAttacking(false), 480));
      timers.push(window.setTimeout(() => setPlayerHit(false), 420));
    }
    return () => timers.forEach(clearTimeout);
  }, [encounterKey, state.player.current_hp, state.enemy.current_hp, state.log]);

  const turnFighters = useMemo(() => {
    if (partyMode && state.party_players?.length) {
      const rows = state.party_players as PartyCombatRow[];
      const enemyTurn = rows.every((r) => !r.your_turn) && state.enemy.current_hp > 0;
      return [
        ...rows.map((row) => ({
          name: row.name,
          icon: classEmoji(row.class || ""),
          iconSrc: row.class ? classIconUrl(row.class) : null,
          isPlayer: true,
          isCurrent: Boolean(row.your_turn),
        })),
        {
          name: state.enemy.name,
          icon: firstTokenEmoji(state.enemy.name),
          iconSrc: null,
          isPlayer: false,
          isCurrent: enemyTurn,
        },
      ];
    }
    return [
      {
        name: state.player.name,
        icon: classEmoji(classKey),
        iconSrc: classKey ? classIconUrl(classKey) : null,
        isPlayer: true,
        isCurrent: canAct,
      },
      {
        name: state.enemy.name,
        icon: firstTokenEmoji(state.enemy.name),
        iconSrc: null,
        isPlayer: false,
        isCurrent: !canAct,
      },
    ];
  }, [partyMode, state.party_players, state.enemy, state.player.name, classKey, canAct]);

  const playerLevel = inventory?.character?.level ?? 1;
  const enemyLevel = zoneLabel?.level_min ?? zoneLabel?.level_max ?? 1;

  // Detect if combat is in progress
  const combatInProgress = state.enemy.current_hp > 0;

  return (
    <div className={focusMode ? "flex flex-col gap-2 sm:gap-3 h-full min-h-0" : "space-y-4"}>
      {dungeonHeader ? (
        <div className="game-panel py-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground font-cinzel tracking-wider">
            {dungeonHeader.emoji} {dungeonHeader.name}
          </span>
          <span className="text-xs text-primary font-pixel" style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.3)" }}>
            Floor {dungeonHeader.floor}/{dungeonHeader.totalFloors} · Turn {state.turn}
          </span>
        </div>
      ) : (
        <div className="game-panel py-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground font-cinzel tracking-wider">
            {zoneLabel?.emoji} {zoneLabel?.name ?? "Zone"}
          </span>
          <span className="text-xs text-primary font-pixel" style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.3)" }}>
            Turn {state.turn}
          </span>
        </div>
      )}

      {showDiscordDungeonBanner && (
        <div
          className="rounded-sm px-3 py-2 text-xs"
          style={{
            border: "1px solid hsl(43 45% 35% / 0.45)",
            background: "linear-gradient(180deg, hsl(228 22% 12%) 0%, hsl(228 20% 8%) 100%)",
          }}
        >
          <div className="font-cinzel font-semibold text-primary flex items-center gap-2">
            <span className="text-base" aria-hidden>
              🏰
            </span>
            Dungeon run
          </div>
          <p className="text-muted-foreground mt-1 leading-relaxed">
            You’re on the battlefield below — allies column shows reserved slots for party dungeons (same rules as{" "}
            <code className="text-[10px]">/fight</code>).
          </p>
        </div>
      )}

      <BattleBackground zone={battleBackgroundZone(zoneLabel?.key)}>
        <div className="p-2 space-y-2">
          <div className="flex justify-center">
            <TurnOrder fighters={turnFighters} />
          </div>
          <div className="relative flex items-end justify-between gap-2 px-2 sm:px-4 pb-2 pt-1 min-h-[200px]">
            <DamageNumbers events={damageEvents} />
            <BattleFighter
              name={state.player.name}
              icon={classEmoji(classKey)}
              iconSrc={classKey ? classIconUrl(classKey) : null}
              hp={state.player.current_hp}
              maxHp={state.player.max_hp}
              mp={state.player.max_res > 0 ? state.player.current_res : undefined}
              maxMp={state.player.max_res > 0 ? state.player.max_res : undefined}
              resourceLabel={state.player.res_type || "MP"}
              level={playerLevel}
              isPlayer
              isHit={playerHit}
              isAttacking={playerAttacking}
            />
            <BattleFighter
              name={state.enemy.name}
              icon={firstTokenEmoji(state.enemy.name)}
              hp={state.enemy.current_hp}
              maxHp={state.enemy.max_hp}
              level={enemyLevel}
              isPlayer={false}
              isHit={enemyHit}
              isAttacking={enemyAttacking}
            />
          </div>
          {specKey && specIconUrl(specKey) && (
            <div className="flex justify-center -mt-1 pb-1">
              <img
                src={specIconUrl(specKey)}
                alt=""
                width={18}
                height={18}
                className="w-[18px] h-[18px] object-contain rounded-[2px] opacity-90"
              />
            </div>
          )}
        </div>
      </BattleBackground>

      <div className="text-center">
        <span
          className="inline-block px-5 py-1.5 font-cinzel font-semibold text-sm text-primary rounded-sm"
          style={{
            background: "linear-gradient(180deg, hsl(228 18% 14%) 0%, hsl(228 20% 10%) 100%)",
            border: "1px solid hsl(43 50% 35% / 0.5)",
            boxShadow: "0 0 12px hsl(43 78% 50% / 0.1), inset 0 1px 0 hsl(228 14% 22% / 0.4)",
            textShadow: "0 0 6px hsl(43 78% 50% / 0.3)",
          }}
        >
          {canAct ? "⚔️ Your Turn" : "⏳ Ally's Turn"}
        </span>
      </div>

      {partyMode ? (
        <div className="game-panel py-2">
          <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mb-2">Party</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-lg mx-auto">
            {(state.party_players as PartyCombatRow[]).map((row, i) => {
              const pk = row.class || "";
              const pct = row.max_hp ? (100 * row.current_hp) / row.max_hp : 0;
              return (
                <div
                  key={`${row.name}-${i}`}
                  className={`rounded-sm p-2 text-center ${row.your_turn ? "ring-1 ring-primary/60" : "opacity-90"}`}
                  style={{ border: "1px solid hsl(228 16% 22%)", background: "hsl(228 20% 10%)" }}
                >
                  <div className="flex justify-center mb-0.5">
                    {pk ? (
                      <img src={classIconUrl(pk)} alt="" width={28} height={28} className="w-7 h-7 object-contain rounded-sm" />
                    ) : (
                      <span className="text-lg">🧝</span>
                    )}
                  </div>
                  <div className="text-[10px] font-cinzel text-foreground truncate">{row.name}</div>
                  <div className="hp-bar-track mt-1">
                    <div className="hp-bar-fill" style={{ width: `${pct}%` }} />
                  </div>
                  <div className="text-[9px] text-muted-foreground tabular-nums mt-0.5">
                    {row.current_hp}/{row.max_hp}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : showDiscordDungeonBanner ? (
        <div className="game-panel py-2">
          <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mb-2">Allies</div>
          <div className="grid grid-cols-2 gap-2 max-w-sm mx-auto">
            <div
              className="rounded-sm p-2 text-center opacity-60"
              style={{ border: "1px solid hsl(228 16% 22%)", background: "hsl(228 20% 10%)" }}
            >
              <div className="text-lg mb-0.5" aria-hidden>
                🛡️
              </div>
              <div className="text-[10px] font-cinzel text-foreground">Slot 2</div>
              <div className="text-[9px] text-muted-foreground">Solo / invite friends</div>
            </div>
            <div
              className="rounded-sm p-2 text-center opacity-60"
              style={{ border: "1px solid hsl(228 16% 22%)", background: "hsl(228 20% 10%)" }}
            >
              <div className="text-lg mb-0.5" aria-hidden>
                🏹
              </div>
              <div className="text-[10px] font-cinzel text-foreground">Slot 3</div>
              <div className="text-[9px] text-muted-foreground">Solo / invite friends</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="game-panel overflow-visible">
        <div className="game-panel-header">Skills</div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 overflow-visible">
          {(state.abilities || []).map((a) => (
            <CombatSkillButton
              key={a.key}
              ability={a}
              loading={loading}
              canAct={canAct}
              onUse={(key) => void onAbility(key)}
            />
          ))}
        </div>
      </div>

      {combatInProgress ? (
        <button
          type="button"
          onClick={() => setShowLogModal(true)}
          className="game-btn-secondary text-xs px-3 py-2 w-full"
        >
          📋 Combat Log
        </button>
      ) : (
        <div className={focusMode ? "game-panel flex-1 min-h-0 overflow-y-auto" : "game-panel max-h-36 overflow-y-auto"}>
          <div className="game-panel-header">Combat Log</div>
          <div className="space-y-1.5">
            {(state.log || []).slice(-12).map((line, i) => (
              <p key={i} className="text-xs text-muted-foreground">
                {stripMd(line)}
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void onFlee()}
          disabled={loading || !canAct}
          className="game-btn-secondary text-xs px-3 py-1.5"
        >
          🏃 Flee
        </button>
        {state.can_potion && (
          <button
            type="button"
            onClick={() => void onPotion()}
            disabled={loading || !canAct}
            className="game-btn-secondary text-xs px-3 py-1.5"
          >
            🧪 Potion
          </button>
        )}
      </div>

      {showLogModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setShowLogModal(false)}
        >
          <div
            className="game-panel w-full max-w-md max-h-[70vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="game-panel-header flex items-center justify-between pb-2 border-b border-primary/20">
              <span>📋 Combat Log</span>
              <button
                type="button"
                onClick={() => setShowLogModal(false)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1.5 p-3">
              {(state.log || []).map((line, i) => (
                <p key={i} className="text-xs text-muted-foreground">
                  {stripMd(line)}
                </p>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setShowLogModal(false)}
              className="game-btn-secondary text-xs px-3 py-1.5 mt-2"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
