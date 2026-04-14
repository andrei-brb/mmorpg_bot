import { Swords } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { CombatStatePayload, ExploreZone, InventoryPayload, PartyCombatRow } from "@/lib/apiTypes";
import { buildBattlePreviewDataFromCombat } from "@/lib/combatBattlePreviewData";
import { classIconUrl, specIconUrl } from "@/lib/classAndSpecIconUrl";
import BattlePreview from "@/components/BattlePreview";
import { BattleBackground } from "@/components/game/combat/BattleBackground";
import { BattlefieldSkillGrid } from "@/components/game/combat/BattlefieldSkillGrid";
import { CombatSkillButton } from "@/components/game/combat/CombatSkillButton";
import { BattleFighter } from "@/components/game/combat/BattleFighter";
import { DamageNumbers, type DamageEvent } from "@/components/game/combat/DamageNumber";
import { TurnOrder } from "@/components/game/combat/TurnOrder";

function stripMd(s: string): string {
  return s.replace(/\*\*/g, "").trim();
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

function displayClassTitle(slug: string): string {
  if (!slug) return "Adventurer";
  return slug
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.slice(0, 1).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

function ArenaDuelResourceBar({ current, max, kind }: { current: number; max: number; kind: "hp" | "mana" }) {
  const pct = max <= 0 ? 0 : Math.max(0, (current / max) * 100);
  const isLow = kind === "hp" && pct < 30;
  return (
    <div className="hp-bar-track">
      <div
        className={`h-full rounded-sm transition-all duration-500 ${kind === "mana" ? "shadow-[inset_0_1px_0_hsl(210_65%_60%/0.35)]" : "hp-bar-fill"}`}
        style={
          kind === "mana"
            ? {
                width: `${pct}%`,
                background: "linear-gradient(180deg, hsl(210 65% 48%) 0%, hsl(210 55% 32%) 100%)",
                boxShadow: "inset 0 1px 0 hsl(210 65% 60% / 0.35), 0 0 6px hsl(210 65% 40% / 0.25)",
              }
            : isLow
              ? {
                  width: `${pct}%`,
                  background: "linear-gradient(180deg, hsl(0 55% 42%) 0%, hsl(0 50% 28%) 100%)",
                  boxShadow: "inset 0 1px 0 hsl(0 60% 50% / 0.35), 0 0 6px hsl(0 60% 35% / 0.3)",
                }
              : { width: `${pct}%` }
        }
      />
    </div>
  );
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
  /** Optional custom chrome above the encounter (default: none). */
  topBar?: ReactNode | null;
  /** Overrides BattleBackground zone when `zoneLabel` is missing (e.g. `"dungeon"`). */
  battleZoneOverride?: string;
  /** Class key for opponent portrait in 1v1 (e.g. PvP). */
  enemyClassKey?: string | null;
  /** Optional overworld enemy key for mob/boss art: `/mobs/<key>.jpg` / `/bosses/<key>.jpg`. */
  enemyKey?: string;
  enemyKind?: "enemy" | "boss";
  /** Stabilizes damage-float reset across encounters (match id, dungeon floor, …). */
  combatSessionId?: string;
  /** Override level chips when inventory/zone are wrong (PvP). */
  playerLevelOverride?: number;
  enemyLevelOverride?: number;
  showFleeButton?: boolean;
  showPotionButton?: boolean;
  /** Shown after "Your Turn" when it is your turn (e.g. countdown seconds). */
  turnBannerSeconds?: number | null;
  /** Shown when you cannot act (default ally message). */
  opponentTurnLabel?: string;
  /**
   * `arena-duel` — Discord Arena style: twin stat panels, crossed swords, Actions + primary row, inline log.
   * `battle-preview` — Lovable-style 3-column battlefield (portraits + tactical grid + banner); hides party fights.
   */
  presentation?: "battlefield" | "arena-duel" | "battle-preview";
  /** Optional portrait URLs for `battle-preview` (defaults: class icon + mob/boss art). */
  battlePreviewPlayerPortraitUrl?: string;
  battlePreviewEnemyPortraitUrl?: string;
  /** Panel title above abilities (default `Skills`; Arena uses `Actions`). */
  skillsPanelTitle?: string;
  /** Rendered full-width above the skill grid (e.g. PvP `__pvp_attack`). */
  primaryAbilityKey?: string;
  /** Opponent class label on the right card (e.g. API `Mage`). */
  enemyClassDisplayName?: string;
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
  topBar,
  battleZoneOverride,
  enemyClassKey,
  enemyKey,
  enemyKind,
  combatSessionId,
  playerLevelOverride,
  enemyLevelOverride,
  showFleeButton = true,
  showPotionButton = true,
  turnBannerSeconds,
  opponentTurnLabel = "⏳ Ally's Turn",
  presentation = "battlefield",
  skillsPanelTitle = "Skills",
  primaryAbilityKey,
  enemyClassDisplayName,
  battlePreviewPlayerPortraitUrl,
  battlePreviewEnemyPortraitUrl,
}: CombatEncounterViewProps) {
  const [showLogModal, setShowLogModal] = useState(false);
  const classKey = state.player.class || inventory?.character?.class || "";
  const specKey = state.player.specialization || inventory?.character?.specialization || "";
  const partyMode = Boolean(state.party_mode && state.party_players && state.party_players.length > 0);
  const canAct = !state.party_mode || state.your_turn === true;

  const playerLevel = playerLevelOverride ?? inventory?.character?.level ?? 1;
  const enemyLevel = enemyLevelOverride ?? zoneLabel?.level_min ?? zoneLabel?.level_max ?? 1;
  const enemyIcon = enemyClassKey ? classEmoji(enemyClassKey) : firstTokenEmoji(state.enemy.name);
  const enemyIconSrc =
    enemyClassKey
      ? classIconUrl(enemyClassKey)
      : enemyKey
        ? enemyKind === "boss"
          ? `/bosses/${enemyKey}.jpg`
          : `/mobs/${enemyKey}.jpg`
        : null;
  const battleZone = battleZoneOverride ?? zoneLabel?.key ?? "volcano";

  const encounterKey = `${combatSessionId ?? "default"}|${state.enemy.name}|${state.enemy.max_hp}|${state.player.max_hp}`;
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
          icon: enemyIcon,
          iconSrc: enemyIconSrc,
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
        icon: enemyIcon,
        iconSrc: enemyIconSrc,
        isPlayer: false,
        isCurrent: !canAct,
      },
    ];
  }, [partyMode, state.party_players, state.enemy, state.player.name, classKey, canAct, enemyIcon, enemyIconSrc]);

  // Detect if combat is in progress
  const combatInProgress = state.enemy.current_hp > 0;

  const isArenaDuel = presentation === "arena-duel";
  const useBattlePreview =
    presentation === "battle-preview" &&
    !(partyMode && state.party_players && state.party_players.length > 0);
  const battlePreviewData = useMemo(() => {
    if (!useBattlePreview) return null;
    return buildBattlePreviewDataFromCombat({
      state,
      inventory,
      zoneLabel,
      battleZoneOverride,
      enemyKey,
      enemyKind,
      enemyClassKey,
      playerLevelOverride,
      enemyLevelOverride,
      turnBannerSeconds,
      canAct,
      opponentTurnLabel,
      playerPortraitUrl: battlePreviewPlayerPortraitUrl,
      enemyPortraitUrl: battlePreviewEnemyPortraitUrl,
    });
  }, [
    useBattlePreview,
    state,
    inventory,
    zoneLabel,
    battleZoneOverride,
    enemyKey,
    enemyKind,
    enemyClassKey,
    playerLevelOverride,
    enemyLevelOverride,
    turnBannerSeconds,
    canAct,
    opponentTurnLabel,
    battlePreviewPlayerPortraitUrl,
    battlePreviewEnemyPortraitUrl,
  ]);
  const abilitiesList = state.abilities || [];
  const primaryAbility =
    isArenaDuel && primaryAbilityKey ? abilitiesList.find((a) => a.key === primaryAbilityKey) : undefined;
  const gridAbilities =
    isArenaDuel && primaryAbilityKey
      ? abilitiesList.filter((a) => a.key !== primaryAbilityKey)
      : abilitiesList;

  const resLabel =
    state.player.res_type === "mana"
      ? "Mana"
      : state.player.res_type === "energy"
        ? "Energy"
        : state.player.res_type === "rage"
          ? "Rage"
          : displayClassTitle(state.player.res_type || "mana");

  const potionInBattleGrid = useBattlePreview && showPotionButton && state.can_potion;

  return (
    <div className={focusMode ? "flex h-full min-h-0 flex-col gap-2 sm:gap-3" : "space-y-4"}>
      {topBar != null ? topBar : null}

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

      {isArenaDuel ? (
        <div className="relative">
          <DamageNumbers events={damageEvents} />
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
          <div className="game-panel order-1 sm:order-none">
            <div className="p-3 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-sm border border-border bg-muted/40 flex items-center justify-center shrink-0 overflow-hidden">
                  {classKey ? (
                    <img src={classIconUrl(classKey)} alt="" className="w-10 h-10 object-contain" />
                  ) : (
                    <span className="text-xl text-muted-foreground" aria-hidden>
                      🛡️
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="font-cinzel text-xs font-bold text-foreground tracking-wide truncate">{state.player.name}</p>
                  <p className="text-[10px] text-muted-foreground font-crimson">
                    Lv.{playerLevel} {displayClassTitle(classKey)}
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-crimson mb-1">
                    <span className="text-muted-foreground uppercase tracking-wider">Hit Points</span>
                    <span className="text-foreground tabular-nums">
                      {state.player.current_hp} / {state.player.max_hp}
                    </span>
                  </div>
                  <ArenaDuelResourceBar current={state.player.current_hp} max={state.player.max_hp} kind="hp" />
                </div>
                {state.player.max_res > 0 ? (
                  <div>
                    <div className="flex items-center justify-between text-[10px] font-crimson mb-1">
                      <span className="text-muted-foreground uppercase tracking-wider">{resLabel}</span>
                      <span className="text-foreground tabular-nums">
                        {state.player.current_res} / {state.player.max_res}
                      </span>
                    </div>
                    <ArenaDuelResourceBar current={state.player.current_res} max={state.player.max_res} kind="mana" />
                  </div>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-center py-2 sm:py-8 order-2 sm:order-none">
            <Swords className="w-7 h-7 text-primary shrink-0" style={{ filter: "drop-shadow(0 0 8px hsl(43 78% 50% / 0.35))" }} />
          </div>
          <div className="game-panel order-3 sm:order-none">
            <div className="p-3 space-y-3">
              <div className="flex items-center gap-3 flex-row-reverse text-right">
                <div className="w-12 h-12 rounded-sm border border-border bg-muted/40 flex items-center justify-center shrink-0 overflow-hidden">
                  {enemyIconSrc ? (
                    <img src={enemyIconSrc} alt="" className="w-10 h-10 object-contain scale-x-[-1]" />
                  ) : (
                    <span className="text-xl text-muted-foreground" aria-hidden>
                      ⚔️
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="font-cinzel text-xs font-bold text-foreground tracking-wide truncate">{state.enemy.name}</p>
                  <p className="text-[10px] text-muted-foreground font-crimson">
                    Lv.{enemyLevel}{" "}
                    {enemyClassDisplayName?.trim() || displayClassTitle(enemyClassKey || "")}
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-crimson mb-1">
                    <span className="text-muted-foreground uppercase tracking-wider">Hit Points</span>
                    <span className="text-foreground tabular-nums">
                      {state.enemy.current_hp} / {state.enemy.max_hp}
                    </span>
                  </div>
                  <ArenaDuelResourceBar current={state.enemy.current_hp} max={state.enemy.max_hp} kind="hp" />
                </div>
                {state.enemy.max_res != null &&
                state.enemy.max_res > 0 &&
                state.enemy.current_res != null ? (
                  <div>
                    <div className="flex items-center justify-between text-[10px] font-crimson mb-1">
                      <span className="text-muted-foreground uppercase tracking-wider">
                        {state.enemy.res_type === "energy"
                          ? "Energy"
                          : state.enemy.res_type === "rage"
                            ? "Rage"
                            : "Mana"}
                      </span>
                      <span className="text-foreground tabular-nums">
                        {state.enemy.current_res} / {state.enemy.max_res}
                      </span>
                    </div>
                    <ArenaDuelResourceBar current={state.enemy.current_res} max={state.enemy.max_res} kind="mana" />
                  </div>
                ) : null}
              </div>
            </div>
          </div>
          </div>
        </div>
      ) : useBattlePreview && battlePreviewData ? (
        <div className={focusMode ? "flex w-full min-h-0 flex-1 flex-col justify-center" : "mx-auto w-full max-w-6xl"}>
          <BattlePreview
            data={{
              ...battlePreviewData,
              onCommence: () => setShowLogModal(true),
            }}
            combatGrid={
              <BattlefieldSkillGrid
                abilities={gridAbilities}
                loading={loading}
                canAct={canAct}
                onAbility={onAbility}
                showPotionButton={showPotionButton}
                canPotion={state.can_potion}
                onPotion={onPotion}
              />
            }
          />
        </div>
      ) : (
        <BattleBackground zone={battleZone}>
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
                icon={enemyIcon}
                iconSrc={enemyIconSrc}
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
      )}

      {!isArenaDuel && !useBattlePreview && (
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
            {canAct
              ? `⚔️ Your Turn${turnBannerSeconds != null ? ` — ${turnBannerSeconds}s` : ""}`
              : opponentTurnLabel}
          </span>
        </div>
      )}

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

      {!useBattlePreview && (
        <div className="game-panel overflow-visible">
          <div className="game-panel-header">{skillsPanelTitle}</div>
          <div className={isArenaDuel || primaryAbility ? "px-3 pb-3" : ""}>
            {primaryAbility ? (
              <div className="mb-2 overflow-visible">
                {(() => {
                  const pd = primaryAbility;
                  const primaryDisabled = Boolean(pd.disabled) || loading || !canAct;
                  return (
                    <button
                      type="button"
                      aria-disabled={primaryDisabled}
                      tabIndex={primaryDisabled ? -1 : undefined}
                      className="game-btn-primary w-full py-2.5 text-sm font-cinzel font-semibold flex items-center justify-center gap-2"
                      title={pd.description || pd.name}
                      onClick={() => {
                        if (primaryDisabled) return;
                        void onAbility(pd.key);
                      }}
                    >
                      <span aria-hidden>{pd.emoji || "⚔️"}</span>
                      {pd.name}
                    </button>
                  );
                })()}
              </div>
            ) : null}
            <div
              className={`grid gap-2 overflow-visible ${isArenaDuel ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-3 sm:grid-cols-6"}`}
            >
              {gridAbilities.map((a) => (
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
        </div>
      )}

      {isArenaDuel ? (
        <div className="game-panel">
          <div className="game-panel-header">Combat Log</div>
          <div className="h-40 overflow-y-auto p-3 space-y-0.5 font-mono text-[11px]">
            {(state.log || []).map((line, i) => (
              <p key={i} className="text-muted-foreground">
                {stripMd(line)}
              </p>
            ))}
          </div>
        </div>
      ) : combatInProgress ? (
        <button
          type="button"
          onClick={() => setShowLogModal(true)}
          className="game-btn-secondary w-full px-3 py-2 text-xs"
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

      {(showFleeButton || (showPotionButton && state.can_potion && !potionInBattleGrid)) && (
        <div className="flex gap-2">
          {showFleeButton && (
            <button
              type="button"
              onClick={() => void onFlee()}
              disabled={loading || !canAct}
              className="game-btn-secondary px-3 py-1.5 text-xs"
            >
              🏃 Flee
            </button>
          )}
          {showPotionButton && state.can_potion && !potionInBattleGrid && (
            <button
              type="button"
              onClick={() => void onPotion()}
              disabled={loading || !canAct}
              className="game-btn-secondary px-3 py-1.5 text-xs"
            >
              🧪 Potion
            </button>
          )}
        </div>
      )}

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
