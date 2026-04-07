import { useState } from "react";
import type { CombatStatePayload, ExploreZone, InventoryPayload, PartyCombatRow } from "@/lib/apiTypes";
import { skillIconUrl } from "@/lib/skillIconUrl";
import { classIconUrl, specIconUrl } from "@/lib/classAndSpecIconUrl";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
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
  const php = state.player.max_hp ? (100 * state.player.current_hp) / state.player.max_hp : 0;
  const ehp = state.enemy.max_hp ? (100 * state.enemy.current_hp) / state.enemy.max_hp : 0;
  const classKey = state.player.class || inventory?.character?.class || "";
  const specKey = state.player.specialization || inventory?.character?.specialization || "";
  const partyMode = Boolean(state.party_mode && state.party_players && state.party_players.length > 0);
  const canAct = !state.party_mode || state.your_turn === true;

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

      <div className="grid grid-cols-2 gap-4">
        <div className="game-panel text-center">
          <div className="mb-2 flex items-center justify-center" style={{ filter: "drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))" }}>
            {classKey ? (
              <img
                src={classIconUrl(classKey)}
                alt=""
                width={48}
                height={48}
                className="w-12 h-12 object-contain rounded-sm"
              />
            ) : (
              <span className="text-3xl">🧝</span>
            )}
          </div>
          <p className="text-sm font-cinzel font-semibold text-foreground">{state.player.name}</p>
          {specKey && specIconUrl(specKey) && (
            <div className="mt-1 flex items-center justify-center">
              <img
                src={specIconUrl(specKey)}
                alt=""
                width={18}
                height={18}
                className="w-[18px] h-[18px] object-contain rounded-[2px]"
              />
            </div>
          )}
          <div className="mt-3">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">HP</span>
              <span className="text-foreground tabular-nums">
                {state.player.current_hp}/{state.player.max_hp}
              </span>
            </div>
            <div className="hp-bar-track">
              <div className="hp-bar-fill" style={{ width: `${php}%` }} />
            </div>
            {state.player.max_res > 0 && (
              <p className="text-[10px] text-muted-foreground mt-1">
                {state.player.res_type} {state.player.current_res}/{state.player.max_res}
              </p>
            )}
          </div>
        </div>
        <div className="game-panel text-center">
          <div className="text-3xl mb-2" style={{ filter: "drop-shadow(0 2px 4px hsl(0 0% 0% / 0.5))" }}>
            <EnemyFace name={state.enemy.name} />
          </div>
          <p className="text-sm font-cinzel font-semibold text-foreground">{state.enemy.name}</p>
          <div className="mt-3">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground text-[10px] font-cinzel uppercase tracking-wider">HP</span>
              <span className="text-foreground tabular-nums">
                {state.enemy.current_hp}/{state.enemy.max_hp}
              </span>
            </div>
            <div className="hp-bar-track">
              <div className="hp-bar-fill" style={{ width: `${ehp}%` }} />
            </div>
          </div>
        </div>
      </div>

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

      <div className="game-panel">
        <div className="game-panel-header">Skills</div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {(state.abilities || []).map((a) => (
            <button
              key={a.key}
              type="button"
              disabled={Boolean(a.disabled) || loading || !canAct}
              title={a.disabled || undefined}
              className="skill-btn"
              onClick={() => void onAbility(a.key)}
            >
              <CombatSkillIcon abilityKey={a.key} emoji={a.emoji} />
              <span className="text-foreground font-semibold text-[10px]">{a.name}</span>
              <span className="text-muted-foreground text-[9px]">
                {a.cost} {a.cost_type}
              </span>
            </button>
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

function EnemyFace({ name }: { name: string }) {
  const parts = name.trim().split(/\s+/);
  const emoji = parts[0] && /[^\w\s]/.test(parts[0]) ? parts[0] : "👾";
  return <>{emoji}</>;
}

function CombatSkillIcon({ abilityKey, emoji }: { abilityKey: string; emoji: string }) {
  const [useEmoji, setUseEmoji] = useState(false);
  if (useEmoji) {
    return (
      <span className="text-2xl leading-none" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}>
        {emoji}
      </span>
    );
  }
  return (
    <img
      src={skillIconUrl(abilityKey)}
      alt=""
      width={32}
      height={32}
      className="w-8 h-8 object-contain shrink-0"
      style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}
      onError={() => setUseEmoji(true)}
    />
  );
}
