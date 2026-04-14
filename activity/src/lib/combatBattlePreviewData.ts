import type { BattlePreviewData, CharacterData, CharacterStat, Item } from "@/components/BattlePreview";
import type { CombatAbility, CombatStatePayload, ExploreZone, InventoryPayload } from "@/lib/apiTypes";
import { classIconUrl } from "@/lib/classAndSpecIconUrl";

function displaySpecOrClassTitle(slug: string | null | undefined): string | undefined {
  if (!slug) return undefined;
  return slug
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.slice(0, 1).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

/** Cosmetic element for portrait auras (API does not send element). */
function inferPlayerElement(classKey: string): NonNullable<CharacterData["element"]> {
  const c = classKey.toLowerCase();
  if (c === "mage") return "fire";
  if (c === "priest") return "light";
  if (c === "paladin") return "light";
  if (c === "hunter") return "earth";
  if (c === "rogue") return "dark";
  if (c === "warrior") return "fire";
  return "lightning";
}

function inferEnemyElement(
  enemyKey: string | undefined,
  enemyKind: "enemy" | "boss" | undefined,
): CharacterData["element"] {
  const k = (enemyKey || "").toLowerCase();
  if (k.includes("frost") || k.includes("ice") || k.includes("winter") || k.includes("snow")) return "ice";
  if (k.includes("fire") || k.includes("lava") || k.includes("molten") || k.includes("flame")) return "fire";
  if (k.includes("shadow") || k.includes("dark") || k.includes("void")) return "dark";
  if (k.includes("murloc") || k.includes("jungle")) return "earth";
  if (enemyKind === "boss") return "earth";
  return "dark";
}

function itemsFromInventory(inventory: InventoryPayload | null): Item[] {
  const rows = (inventory?.items || []).filter((r) => !r.is_equipped).slice(0, 6);
  return rows.map((r, i) => ({
    id: r.id || `bag-${i}`,
    name: r.name,
    icon: (r.icon && String(r.icon).trim()) || "📦",
    quantity: Math.max(0, Number(r.quantity ?? 1)),
    description: r.item_type ? String(r.item_type) : "Inventory item",
  }));
}

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

function buildPlayerStats(
  state: CombatStatePayload,
  abilities: CombatAbility[],
  playerLevel?: number,
): CharacterStat[] {
  const rows: CharacterStat[] = [{ label: "HP", value: `${state.player.current_hp} / ${state.player.max_hp}` }];
  if (state.player.max_res > 0) {
    rows.push({
      label: displayResLabel(state.player.res_type || "mana"),
      value: `${state.player.current_res} / ${state.player.max_res}`,
    });
  }
  const lv = playerLevel ?? 1;
  const def = String(Math.max(8, Math.round(lv * 0.92 + 5)));
  const acc = estimateAccuracy(abilities);
  rows.push(
    { label: "Attack Power", value: estimateAttackPower(abilities) },
    { label: "Defense", value: def },
    { label: "Accuracy", value: acc === "—" ? "100%" : acc },
  );
  return rows;
}

/** Enemy offensive stats are not on combat state — derive cosmetic numbers from level/HP so the panel matches the reference. */
function buildEnemyStats(state: CombatStatePayload, enemyLevel?: number): CharacterStat[] {
  const rows: CharacterStat[] = [{ label: "HP", value: `${state.enemy.current_hp} / ${state.enemy.max_hp}` }];
  const maxR = state.enemy.max_res;
  const curR = state.enemy.current_res;
  if (maxR != null && maxR > 0 && curR != null) {
    const rt = state.enemy.res_type === "energy" ? "Energy" : state.enemy.res_type === "rage" ? "Rage" : "Mana";
    rows.push({ label: rt, value: `${curR} / ${maxR}` });
  }
  const lv = enemyLevel ?? 1;
  const atk = String(Math.max(10, Math.round(lv * 1.0 + state.enemy.max_hp / 50)));
  const def = String(Math.max(8, Math.round(lv * 0.92 + 5)));
  rows.push(
    { label: "Attack Power", value: atk },
    { label: "Defense", value: def },
    { label: "Accuracy", value: "100%" },
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

  const bagItems = itemsFromInventory(inventory);
  const specTitle =
    inventory?.character?.specialization_name?.trim() ||
    displaySpecOrClassTitle(state.player.specialization ?? undefined);
  const playerElement = inferPlayerElement(classKey || "mage");
  const enemyElement = inferEnemyElement(enemyKey, enemyKind);
  const classDisplay = displaySpecOrClassTitle(classKey) || undefined;
  const enemyClassDisplay = enemyClassKey ? displaySpecOrClassTitle(enemyClassKey) : undefined;

  return {
    backgroundUrl: "",
    battlefieldZoneKey: battleZone,
    buttonLabel,
    centerActionLabel: "⚔️ Combat History",
    centerStatusLine: buttonLabel,
    gridRows: 3,
    gridCols: 3,
    items: bagItems.length > 0 ? bagItems : undefined,
    showRpgPanel: true,
    player: {
      name: state.player.name,
      portraitUrl: playerPortrait,
      level: playerLevel,
      class: classDisplay,
      title: specTitle,
      element: playerElement,
      stats: buildPlayerStats(state, abilities, playerLevel),
    },
    enemy: {
      name: state.enemy.name,
      portraitUrl: enemyPortrait,
      level: enemyLevel,
      class: enemyClassDisplay || (enemyKind === "boss" ? "Warlord" : undefined),
      isBoss: enemyKind === "boss",
      title: enemyKind === "boss" ? "The Unyielding" : undefined,
      element: enemyElement,
      stats: buildEnemyStats(state, enemyLevel),
    },
  };
}
