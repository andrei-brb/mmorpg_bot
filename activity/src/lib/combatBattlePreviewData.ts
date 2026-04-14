import type { BattlePreviewData, CharacterStat } from "@/components/BattlePreview";
import type { CombatAbility, CombatStatePayload, ExploreZone, InventoryPayload } from "@/lib/apiTypes";
import { classIconUrl } from "@/lib/classAndSpecIconUrl";

function displayResLabel(resType: string): string {
  if (resType === "mana") return "Mana";
  if (resType === "energy") return "Energy";
  if (resType === "rage") return "Rage";
  return resType;
}

function estimateAttackPower(abilities: CombatAbility[]): string {
  let best: number | null = null;
  for (const a of abilities) {
    if (a.dmg_min != null && a.dmg_max != null) {
      const mid = (a.dmg_min + a.dmg_max) / 2;
      if (best === null || mid > best) best = mid;
    }
  }
  return best != null ? String(Math.round(best)) : "—";
}

function estimateAccuracy(abilities: CombatAbility[]): string {
  let best: number | null = null;
  for (const a of abilities) {
    if (a.crit_pct != null) {
      if (best === null || a.crit_pct > best) best = a.crit_pct;
    }
  }
  return best != null ? `${Math.round(best)}%` : "—";
}

function buildPlayerStats(state: CombatStatePayload, abilities: CombatAbility[]): CharacterStat[] {
  const rows: CharacterStat[] = [{ label: "HP", value: `${state.player.current_hp} / ${state.player.max_hp}` }];
  if (state.player.max_res > 0) {
    rows.push({
      label: displayResLabel(state.player.res_type || "mana"),
      value: `${state.player.current_res} / ${state.player.max_res}`,
    });
  }
  rows.push(
    { label: "Attack Power", value: estimateAttackPower(abilities) },
    { label: "Defense", value: "—" },
    { label: "Accuracy", value: estimateAccuracy(abilities) },
  );
  return rows;
}

/** Enemy offensive stats are not exposed on combat state — keep placeholders so the layout matches. */
function buildEnemyStats(state: CombatStatePayload): CharacterStat[] {
  const rows: CharacterStat[] = [{ label: "HP", value: `${state.enemy.current_hp} / ${state.enemy.max_hp}` }];
  const maxR = state.enemy.max_res;
  const curR = state.enemy.current_res;
  if (maxR != null && maxR > 0 && curR != null) {
    const rt = state.enemy.res_type === "energy" ? "Energy" : state.enemy.res_type === "rage" ? "Rage" : "Mana";
    rows.push({ label: rt, value: `${curR} / ${maxR}` });
  }
  rows.push(
    { label: "Attack Power", value: "—" },
    { label: "Defense", value: "—" },
    { label: "Accuracy", value: "—" },
  );
  return rows;
}

export function buildBattlePreviewDataFromCombat(args: {
  state: CombatStatePayload;
  inventory: InventoryPayload | null;
  zoneLabel?: ExploreZone;
  battleZoneOverride?: string;
  enemyKey?: string;
  enemyKind?: "enemy" | "boss";
  enemyClassKey?: string | null;
  playerLevelOverride?: number;
  enemyLevelOverride?: number;
  turnBannerSeconds?: number | null;
  canAct: boolean;
  opponentTurnLabel: string;
  playerPortraitUrl?: string;
  enemyPortraitUrl?: string;
}): BattlePreviewData {
  const {
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
    playerPortraitUrl: playerOverride,
    enemyPortraitUrl: enemyOverride,
  } = args;

  const battleZone = battleZoneOverride ?? zoneLabel?.key ?? "volcano";
  const classKey = state.player.class || inventory?.character?.class || "";
  const playerLevel = playerLevelOverride ?? inventory?.character?.level;
  const enemyLevel = enemyLevelOverride ?? zoneLabel?.level_max ?? zoneLabel?.level_min;
  const base = import.meta.env.BASE_URL || "/";

  const playerPortrait =
    playerOverride ?? (classKey ? classIconUrl(classKey) : `${base}placeholder.svg`);

  const enemyPortrait =
    enemyOverride ??
    (enemyKey
      ? `${base}${enemyKind === "boss" ? "bosses" : "mobs"}/${enemyKey}.jpg`
      : enemyClassKey
        ? classIconUrl(enemyClassKey)
        : `${base}placeholder.svg`);

  const abilities = state.abilities || [];

  const buttonLabel = canAct
    ? `Your Turn${turnBannerSeconds != null ? ` — ${turnBannerSeconds}s` : ""}`
    : opponentTurnLabel.replace(/^\s*⏳\s*/u, "").trim() || "Waiting…";

  return {
    backgroundUrl: "",
    battlefieldZoneKey: battleZone,
    buttonLabel,
    gridRows: 3,
    gridCols: 3,
    player: {
      name: state.player.name,
      portraitUrl: playerPortrait,
      level: playerLevel,
      class: classKey || undefined,
      stats: buildPlayerStats(state, abilities),
    },
    enemy: {
      name: state.enemy.name,
      portraitUrl: enemyPortrait,
      level: enemyLevel,
      class: enemyClassKey || undefined,
      isBoss: enemyKind === "boss",
      title: enemyKind === "boss" ? "Boss" : undefined,
      stats: buildEnemyStats(state),
    },
  };
}
