import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CraftJobRow, CraftRecipeRow, InvRow } from "@/lib/apiTypes";
import { craftingXpToNextLevel } from "@/lib/craftingXp";
import * as api from "@/lib/gameApi";

/**
 * All Forge state and actions, lifted out of CraftingTab so more than one view
 * can drive the same forge.
 *
 * CraftingTab (the Discord Activity's Forge) now calls this and renders exactly
 * what it rendered before — the extraction is behaviour-preserving. The mobile
 * Workbench calls the same hook with a phone-native layout. Nothing here is
 * duplicated per shell: one source of truth for starting, claiming, repairing
 * and affordability.
 */

export type ForgePathAOption = {
  ok?: boolean;
  message?: string | null;
  from_rarity?: string;
  to_rarity?: string | null;
  rule?: {
    id: string;
    gold_cost: number;
    costs: Record<string, number>;
    craft_seconds: number;
    success_chance: number;
    required_crafting_level: number;
    crafting_xp_reward: number;
  } | null;
};

export type ForgePathBOption = {
  ok?: boolean;
  message?: string | null;
  recipes?: CraftRecipeRow[];
  risk_destroy_on_fail?: boolean;
};

export type ForgeOptionsPayload = {
  item_id?: string;
  /** Server-resolved `item_templates.name` per `costs` key (works when the player owns 0). */
  material_names?: Record<string, string>;
  path_a?: ForgePathAOption;
  path_b?: ForgePathBOption;
};

export type Rarity = "common" | "uncommon" | "rare" | "epic" | "legendary" | "mythic";

export function ownedTemplateQty(items: InvRow[], templateKey: string): number {
  const k = templateKey.trim().toLowerCase();
  let sum = 0;
  for (const it of items) {
    if (String(it.template_id || "").trim().toLowerCase() !== k) continue;
    sum += Math.max(0, Math.floor(Number(it.quantity ?? 1)));
  }
  return sum;
}

export function normRarity(r?: string | null): Rarity {
  const s = String(r || "common").toLowerCase();
  if (s === "uncommon" || s === "rare" || s === "epic" || s === "legendary" || s === "mythic") return s;
  return "common";
}

export function isGearRow(it: InvRow): boolean {
  const t = (it.item_type || "").toLowerCase();
  return t === "weapon" || t === "armor" || t === "accessory";
}

export function useForge() {
  const { inventory, refreshInventory, refreshProgress, itemPost, accessToken, guildId } =
    useGameSession();
  const char = inventory?.character;
  const items = useMemo(() => inventory?.items || [], [inventory?.items]);
  const job = (inventory?.craft_job || null) as CraftJobRow | null;

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const craftLevel = Number(char?.crafting_level ?? 1) || 1;
  const craftXp = Number(char?.crafting_xp ?? 0) || 0;
  const needXp = craftingXpToNextLevel(craftLevel);
  const xpPct = Math.min(100, Math.round((craftXp / Math.max(1, needXp)) * 100));

  const completesMs = useMemo(() => {
    if (!job?.completes_at) return null;
    const t = Date.parse(String(job.completes_at));
    return Number.isFinite(t) ? t : null;
  }, [job?.completes_at]);

  const secondsLeft = completesMs != null ? Math.max(0, Math.ceil((completesMs - now) / 1000)) : null;
  const canClaim = job?.status === "ready" || (job?.status === "active" && secondsLeft === 0);

  const bagGear = useMemo(
    () =>
      items.filter(
        (it) => !it.is_equipped && !it.locked && isGearRow(it) && it.id && (it.quantity ?? 1) >= 1,
      ),
    [items],
  );

  // ── repair ──
  const [repairQuote, setRepairQuote] = useState<api.RepairQuotePayload | null>(null);
  const [repairLoading, setRepairLoading] = useState(false);
  const [repairError, setRepairError] = useState(false);
  const [repairing, setRepairing] = useState(false);

  const loadRepairQuote = useCallback(async () => {
    if (!accessToken) return;
    setRepairLoading(true);
    setRepairError(false);
    try {
      const j = await api.getRepairQuote(accessToken, guildId);
      if (j.ok === false) throw new Error("repair quote unavailable");
      setRepairQuote(j);
    } catch (e) {
      console.warn("repair quote", e);
      setRepairError(true);
    } finally {
      setRepairLoading(false);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void loadRepairQuote();
  }, [loadRepairQuote]);

  const repairAll = useCallback(async () => {
    if (!accessToken || repairing) return;
    setRepairing(true);
    try {
      const j = await api.postRepairAll(accessToken, guildId);
      if (j.ok) {
        const n = j.repaired ?? 0;
        toast.success(`Repaired ${n} item${n === 1 ? "" : "s"} for ${(j.total ?? 0).toLocaleString()} 🪙.`);
        await refreshInventory();
        await refreshProgress();
      } else if (j.error === "insufficient_gold") {
        toast.error(`Not enough gold — repairs cost ${(j.total ?? 0).toLocaleString()} 🪙.`);
      } else {
        toast.error(j.message || j.error || "Could not repair gear.");
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setRepairing(false);
    }
    await loadRepairQuote();
  }, [accessToken, guildId, repairing, refreshInventory, refreshProgress, loadRepairQuote]);

  // ── forge ──
  const [selectedId, setSelectedId] = useState<string>("");
  const [forgeMode, setForgeMode] = useState<"a" | "b">("a");
  const [branchRecipeId, setBranchRecipeId] = useState<string>("");
  const [forgeOptions, setForgeOptions] = useState<ForgeOptionsPayload | null>(null);
  const [outcome, setOutcome] = useState<{ text: string; ok: boolean } | null>(null);

  const selectedItem = useMemo(() => bagGear.find((x) => x.id === selectedId) || null, [bagGear, selectedId]);

  useEffect(() => {
    if (!accessToken || !selectedId) {
      setForgeOptions(null);
      setBranchRecipeId("");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const j = await api.getForgeOptions(accessToken, selectedId, guildId);
        if (cancelled) return;
        if (j.ok === false) {
          setForgeOptions(null);
          toast.error(j.message || "Could not load forge options.");
          return;
        }
        setForgeOptions((j.options || null) as ForgeOptionsPayload | null);
        setBranchRecipeId("");
        setOutcome(null);
      } catch (e) {
        if (!cancelled) toast.error(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, selectedId]);

  const startForge = useCallback(async () => {
    if (!selectedId) {
      toast.error("Select an item in the source slot.");
      return;
    }
    try {
      const body: Record<string, unknown> = { path: forgeMode, item_id: selectedId };
      if (forgeMode === "b") {
        if (!branchRecipeId) {
          toast.error("Pick an upgrade target.");
          return;
        }
        body.recipe_id = branchRecipeId;
      }
      const res = await itemPost("/api/game/forge/start", body);
      const j = (await res.json()) as { ok?: boolean; message?: string };
      if (res.ok && j.ok !== false) toast.success(j.message || "Forge started.");
      else toast.error(j.message || "Could not start forge.");
      setOutcome(null);
      await refreshInventory();
    } catch (e) {
      toast.error(String(e));
    }
  }, [branchRecipeId, forgeMode, itemPost, refreshInventory, selectedId]);

  const claimForge = useCallback(async () => {
    try {
      const res = await itemPost("/api/game/forge/claim", {});
      const j = (await res.json()) as {
        ok?: boolean;
        message?: string;
        result?: { success?: boolean; path?: string; to_rarity?: string; template_id?: string };
      };
      const okHttp = res.ok && j.ok !== false;
      const succ = j.result?.success;
      if (okHttp && succ === false) {
        toast.error(j.message || "Forge failed.");
        setOutcome({ text: j.message || "Failed", ok: false });
      } else if (okHttp) {
        toast.success(j.message || "Done.");
        setOutcome({ text: j.message || "Success", ok: true });
      } else {
        toast.error(j.message || "Could not claim.");
      }
      await refreshInventory();
    } catch (e) {
      toast.error(String(e));
    }
  }, [itemPost, refreshInventory]);

  const pathA = forgeOptions?.path_a;
  const pathB = forgeOptions?.path_b;
  const rule = pathA?.rule;
  const branchRecipes = useMemo(() => pathB?.recipes || [], [pathB?.recipes]);
  const selectedBranch = branchRecipes.find((r) => r.id === branchRecipeId);

  const jobTitle = useMemo(() => {
    if (!job) return "";
    if ((job.job_kind || "template_branch") === "rarity_forge") {
      return job.rarity_rule_name || "Rarity infusion";
    }
    return job.recipe_name || job.recipe_id || "Upgrade";
  }, [job]);

  const jobStatusLine = !job
    ? "No work order in the queue."
    : job.status === "ready" || canClaim
      ? "Ready to claim — success rolls when you collect."
      : secondsLeft != null
        ? `Hammering… ${secondsLeft}s remaining`
        : "In progress…";

  const successPct = job?.success_chance != null ? Math.round(Number(job.success_chance) * 100) : null;

  const sourceRarity = normRarity(selectedItem?.rarity);

  const pathTabsLocked = Boolean(job);
  const rarityTabDisabled =
    pathTabsLocked || Boolean(forgeOptions != null && pathA != null && pathA.ok === false);
  const upgradeTabDisabled =
    pathTabsLocked || Boolean(forgeOptions != null && pathB != null && pathB.ok === false);

  const playerGold = useMemo(() => Math.max(0, Math.floor(Number(char?.gold ?? 0))), [char?.gold]);

  const canAffordRarityPath = useMemo(() => {
    if (!rule || !pathA?.ok) return false;
    if (playerGold < (rule.gold_cost || 0)) return false;
    for (const [key, need] of Object.entries(rule.costs || {})) {
      if ((need || 0) <= 0) continue;
      if (ownedTemplateQty(items, key) < need) return false;
    }
    return true;
  }, [rule, pathA?.ok, playerGold, items]);

  const canAffordUpgradePath = useMemo(() => {
    if (!selectedBranch || !pathB?.ok) return false;
    if (playerGold < (selectedBranch.gold_cost || 0)) return false;
    for (const [key, need] of Object.entries(selectedBranch.costs || {})) {
      if ((need || 0) <= 0) continue;
      if (ownedTemplateQty(items, key) < need) return false;
    }
    return true;
  }, [selectedBranch, pathB?.ok, playerGold, items]);

  const meetsCraftingLevelRarity = !rule || craftLevel >= (rule.required_crafting_level || 1);
  const meetsCraftingLevelUpgrade =
    !selectedBranch || craftLevel >= (selectedBranch.required_crafting_level || 1);

  return {
    // session
    char,
    items,
    inventory,
    // skill
    craftLevel,
    craftXp,
    needXp,
    xpPct,
    // job
    job,
    jobTitle,
    jobStatusLine,
    secondsLeft,
    canClaim,
    successPct,
    outcome,
    // selection
    bagGear,
    selectedId,
    setSelectedId,
    selectedItem,
    sourceRarity,
    forgeMode,
    setForgeMode,
    branchRecipeId,
    setBranchRecipeId,
    // options
    forgeOptions,
    pathA,
    pathB,
    rule,
    branchRecipes,
    selectedBranch,
    rarityTabDisabled,
    upgradeTabDisabled,
    pathTabsLocked,
    // money
    playerGold,
    canAffordRarityPath,
    canAffordUpgradePath,
    meetsCraftingLevelRarity,
    meetsCraftingLevelUpgrade,
    // actions
    startForge,
    claimForge,
    // repair
    repairQuote,
    repairLoading,
    repairError,
    repairing,
    repairAll,
    loadRepairQuote,
  };
}
