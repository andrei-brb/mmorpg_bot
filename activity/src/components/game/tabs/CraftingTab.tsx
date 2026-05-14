import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CraftRecipeRow, CraftJobRow, InvRow } from "@/lib/apiTypes";
import { craftingXpToNextLevel } from "@/lib/craftingXp";
import * as api from "@/lib/gameApi";
import { ItemIcon } from "../ItemIcon";
import {
  WomGoldCoin,
  WomOrnateDivider,
  WomPanel,
  WomPill,
  WomSectionHeader,
  WomStatBar,
} from "@/components/wom/WomUi";

function prettyMaterialKey(key: string): string {
  return String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Sum bag quantities for rows whose `template_id` matches (e.g. `weapon_scrap`). */
function ownedTemplateQty(items: InvRow[], templateKey: string): number {
  const k = templateKey.trim().toLowerCase();
  let sum = 0;
  for (const it of items) {
    if (String(it.template_id || "").trim().toLowerCase() !== k) continue;
    sum += Math.max(0, Math.floor(Number(it.quantity ?? 1)));
  }
  return sum;
}

function ForgeMaterialAudit({
  costs,
  goldNeed,
  goldHave,
  items,
}: {
  costs: Record<string, number> | undefined;
  goldNeed: number;
  goldHave: number;
  items: InvRow[];
}) {
  const scrapRows = Object.entries(costs || {}).filter(([, n]) => (n || 0) > 0);
  const goldOk = goldHave >= goldNeed;

  return (
    <div className="space-y-3">
      <WomOrnateDivider label="Costs" />
      <div className="rounded-sm border border-[var(--border-default)] bg-[var(--bg-void)]/80">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-default)]/80 px-3 py-2.5">
          <div className="flex items-center gap-2">
            <WomGoldCoin size={18} />
            <span className="text-xs font-semibold text-[var(--text-secondary)]">Gold</span>
          </div>
          <div className="wom-font-mono text-right text-xs tabular-nums">
            <span className="text-[var(--text-muted)]">Need </span>
            <span className="font-bold text-[var(--gold-200)]">{goldNeed.toLocaleString()}</span>
            <span className="text-[var(--text-muted)]"> · You </span>
            <span className={goldOk ? "text-[var(--verdant)]" : "text-[var(--crimson-400)]"}>{goldHave.toLocaleString()}</span>
          </div>
        </div>
        {scrapRows.length === 0 ? (
          <p className="px-3 py-3 text-xs text-[var(--text-muted)]">No scrap or extra materials for this forge — gold only.</p>
        ) : (
          <ul className="divide-y divide-[var(--border-default)]/60">
            {scrapRows.map(([templateId, need]) => {
              const have = ownedTemplateQty(items, templateId);
              const ok = have >= need;
              const sample = items.find((it) => String(it.template_id || "").trim().toLowerCase() === templateId.toLowerCase());
              return (
                <li key={templateId} className="flex items-center gap-3 px-3 py-2.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border border-[var(--border-default)] bg-[var(--bg-panel-raised)]">
                    {sample ? (
                      <ItemIcon item={sample} size={28} />
                    ) : (
                      <span className="text-[10px] uppercase tracking-wider text-[var(--text-disabled)]">?</span>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-foreground">{prettyMaterialKey(templateId)}</div>
                    <div className="wom-font-mono text-[11px] tabular-nums text-[var(--text-muted)]">
                      Need <span className="font-bold text-foreground">{need}</span>
                      <span> · You </span>
                      <span className={ok ? "text-[var(--verdant)]" : "text-amber-400"}>{have}</span>
                    </div>
                  </div>
                  {ok ? (
                    <WomPill tone="success">OK</WomPill>
                  ) : (
                    <WomPill tone="crimson">Short</WomPill>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function normRarity(r?: string | null): "common" | "uncommon" | "rare" | "epic" | "legendary" | "mythic" {
  const s = String(r || "common").toLowerCase();
  if (s === "uncommon" || s === "rare" || s === "epic" || s === "legendary" || s === "mythic") return s;
  return "common";
}

type ForgePathAOption = {
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

type ForgePathBOption = {
  ok?: boolean;
  message?: string | null;
  recipes?: CraftRecipeRow[];
  risk_destroy_on_fail?: boolean;
};

type ForgeOptionsPayload = {
  path_a?: ForgePathAOption;
  path_b?: ForgePathBOption;
};

function isGearRow(it: InvRow): boolean {
  const t = (it.item_type || "").toLowerCase();
  return t === "weapon" || t === "armor" || t === "accessory";
}

export function CraftingTab() {
  const { inventory, refreshInventory, itemPost, accessToken, guildId } = useGameSession();
  const char = inventory?.character;
  const items = inventory?.items || [];
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

  const [selectedId, setSelectedId] = useState<string>("");
  const [forgeMode, setForgeMode] = useState<"a" | "b">("a");
  const [branchRecipeId, setBranchRecipeId] = useState<string>("");
  const [forgeOptions, setForgeOptions] = useState<ForgeOptionsPayload | null>(null);
  const [outcome, setOutcome] = useState<{ text: string; ok: boolean } | null>(null);

  const selectedItem = useMemo(
    () => bagGear.find((x) => x.id === selectedId) || null,
    [bagGear, selectedId],
  );

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

  useEffect(() => {
    const pa = forgeOptions?.path_a;
    const pb = forgeOptions?.path_b;
    if (forgeMode === "a" && pa && !pa.ok && pb?.ok) setForgeMode("b");
    if (forgeMode === "b" && pb && !pb.ok && pa?.ok) setForgeMode("a");
  }, [forgeOptions, forgeMode]);

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
  const branchRecipes = pathB?.recipes || [];
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

  const successPct =
    job?.success_chance != null ? Math.round(Number(job.success_chance) * 100) : null;

  const sourceRarity = normRarity(selectedItem?.rarity);

  const pathTabsLocked = Boolean(job);
  const rarityTabDisabled =
    pathTabsLocked || Boolean(forgeOptions != null && pathA != null && pathA.ok === false);
  const upgradeTabDisabled =
    pathTabsLocked || Boolean(forgeOptions != null && pathB != null && pathB.ok === false);

  const pathTabClass = (active: boolean) =>
    `btn-ghost flex-1 min-h-[4.25rem] flex-col justify-center gap-0.5 py-3 sm:min-h-[4.5rem] ${
      active ? "!border-[var(--gold-600)] !bg-[rgba(184,151,88,0.12)] !text-[var(--gold-200)]" : ""
    }`;

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

  return (
    <div className="forge-tab-root wom-anim-fade-up space-y-4 px-0.5 pb-2 font-body">
      <WomPanel className="p-5 sm:p-6" glow>
        <WomSectionHeader kicker="Guild services" title="Forge" />

        <div className="mb-4 grid grid-cols-2 gap-2 sm:gap-3">
          <button
            type="button"
            className={pathTabClass(forgeMode === "a")}
            disabled={rarityTabDisabled}
            onClick={() => setForgeMode("a")}
          >
            <span className="text-[10px] font-cinzel font-semibold uppercase tracking-[0.22em] text-[var(--gold-500)]">
              Rarity path
            </span>
            <span className="text-[11px] text-[var(--text-muted)]">Safer</span>
          </button>
          <button
            type="button"
            className={pathTabClass(forgeMode === "b")}
            disabled={upgradeTabDisabled}
            onClick={() => setForgeMode("b")}
          >
            <span className="text-[10px] font-cinzel font-semibold uppercase tracking-[0.22em] text-[var(--gold-500)]">
              Upgrade
            </span>
            <span className="text-[11px] text-[var(--text-muted)]">Riskier</span>
          </button>
        </div>

        <p className="mb-5 max-w-prose text-sm leading-relaxed text-[var(--text-secondary)]">
          <span className="text-gold font-semibold">Rarity</span> nudges the same piece toward a higher tier; failure spends
          costs only. <span className="text-gold font-semibold">Upgrade</span> re-shapes the item — the input is consumed at
          start and may be <span className="text-crimson font-semibold">destroyed on a failed claim</span>.
        </p>

        <WomOrnateDivider label="Skill" />

        <div className="mb-1 flex flex-wrap items-end justify-between gap-2">
          <span className="text-label">Forging experience</span>
          <span className="wom-font-mono text-[11px] tabular-nums text-[var(--text-muted)]">
            Lv.{craftLevel} · {craftXp.toLocaleString()} / {needXp.toLocaleString()} XP
          </span>
        </div>
        <WomStatBar value={craftXp} max={needXp} variant="gold" />
        <p className="mt-1.5 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{xpPct}% toward next level</p>

        <WomOrnateDivider label="Work order" />

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1 space-y-2">
            {!job ? (
              <p className="text-sm text-[var(--text-secondary)]">{jobStatusLine}</p>
            ) : (
              <>
                <div className="font-blackletter text-2xl leading-none tracking-wide text-[var(--gold-200)] drop-shadow-[0_2px_8px_rgba(0,0,0,0.85)] sm:text-3xl">
                  {jobTitle}
                </div>
                <p className="text-sm text-[var(--text-secondary)]">{jobStatusLine}</p>
                {successPct != null ? (
                  <WomPill tone="gold">
                    Success <span className="wom-font-mono">{successPct}%</span>
                  </WomPill>
                ) : null}
              </>
            )}
          </div>
          <button type="button" className="btn-gold shrink-0 !px-6 !py-3 !text-[11px]" disabled={!job || !canClaim} onClick={() => void claimForge()}>
            Claim
          </button>
        </div>
      </WomPanel>

      <WomPanel className="p-5 sm:p-6" glow>
        <WomSectionHeader kicker="Equipment" title="Anvil" />
        <p className="mb-5 text-sm text-[var(--text-secondary)]">Bag gear only — select a piece, choose path, then strike the forge.</p>

        <div className="grid grid-cols-1 items-stretch gap-4 md:grid-cols-[1fr_auto_1fr]">
          <div className="flex min-h-[200px] flex-col gap-2">
            <div className="text-label">Source</div>
            <select
              className="wom-select"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              <option value="">Choose bag item…</option>
              {bagGear.map((it) => (
                <option key={it.id} value={it.id}>
                  {it.name} ({it.rarity || "common"})
                </option>
              ))}
            </select>
            <div
              className="wom-slot mx-auto flex w-full max-w-[8.5rem] flex-1 items-center justify-center"
              data-rarity={sourceRarity}
              data-empty={selectedItem ? "false" : "true"}
            >
              {selectedItem ? (
                <>
                  <ItemIcon item={selectedItem} size={64} />
                  {Number(selectedItem.enhancement_level ?? 0) > 0 ? (
                    <span className="wom-slot-badge">+{selectedItem.enhancement_level}</span>
                  ) : null}
                </>
              ) : (
                <span className="text-label !tracking-[0.2em] text-[var(--text-disabled)]">Empty</span>
              )}
            </div>
          </div>

          <div className="flex flex-col items-center justify-center gap-2 py-2 text-[var(--text-muted)] md:py-0">
            <span className="font-display hidden text-2xl md:inline" aria-hidden>
              →
            </span>
            <span className="font-display text-2xl md:hidden" aria-hidden>
              ↓
            </span>
          </div>

          <div className="flex min-h-[200px] flex-col gap-2">
            <div className="text-label">Outcome</div>
            <div
              className="wom-slot mx-auto flex w-full max-w-[8.5rem] flex-1 items-center justify-center px-2"
              data-empty={outcome || (selectedItem && job) ? "false" : "true"}
            >
              {outcome ? (
                <p
                  className={`text-center font-body text-xs leading-snug ${
                    outcome.ok ? "text-[var(--verdant)]" : "text-[var(--crimson-400)]"
                  }`}
                >
                  {outcome.text}
                </p>
              ) : selectedItem && job ? (
                <p className="text-center text-xs text-[var(--text-muted)]">Claim your work order to resolve the hammer&apos;s verdict.</p>
              ) : (
                <span className="font-display text-3xl text-[var(--text-disabled)]" aria-hidden>
                  ?
                </span>
              )}
            </div>
          </div>
        </div>

        <p className="mt-4 text-center text-xs text-[var(--text-muted)]">
          Use the tabs above to switch workshops. After you pick gear here, the{" "}
          <span className="text-[var(--gold-500)]">Rarity path</span> or <span className="text-[var(--gold-500)]">Upgrade</span>{" "}
          panel opens below.
        </p>
      </WomPanel>

      {selectedItem && !job ? (
        <WomPanel key={forgeMode} className="min-h-[280px] p-5 sm:p-6" glow>
          <WomSectionHeader
            kicker={forgeMode === "a" ? "Safer infusion" : "Riskier re-shaping"}
            title={forgeMode === "a" ? "Rarity path" : "Upgrade"}
          />

          {!forgeOptions ? (
            <p className="text-sm text-[var(--text-muted)]">Loading forge options…</p>
          ) : forgeMode === "a" && pathA ? (
            !pathA.ok || !rule ? (
              <p className="text-sm text-[var(--crimson-400)]">{pathA.message || "Infusion unavailable."}</p>
            ) : (
              <div className="space-y-5">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="font-display text-lg uppercase tracking-wider text-[var(--gold-200)]">{pathA.from_rarity}</span>
                  <span className="text-[var(--text-muted)]">→</span>
                  <span
                    className={`font-display text-lg uppercase tracking-wider rar-${normRarity(pathA.to_rarity || undefined)}`}
                  >
                    {pathA.to_rarity}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
                  {(
                    [
                      ["Time", `${rule.craft_seconds}s`],
                      ["Gold", rule.gold_cost],
                      ["Req.Lv", rule.required_crafting_level],
                      ["Success", `${Math.round(Number(rule.success_chance) * 100)}%`],
                      ["Forge XP", `+${rule.crafting_xp_reward}`],
                    ] as const
                  ).map(([label, val]) => (
                    <div key={label} className="border border-[var(--border-default)] bg-[var(--bg-void)] px-2 py-2 text-center">
                      <div className="text-label !text-[9px] !tracking-[0.2em] text-[var(--gold-600)]">{label}</div>
                      <div className="wom-font-mono text-sm font-bold text-[var(--text-primary)]">{val}</div>
                    </div>
                  ))}
                </div>
                {!meetsCraftingLevelRarity ? (
                  <p className="text-xs text-amber-400/95">
                    Your forging skill is Lv.{craftLevel}; this infusion requires Lv.{rule.required_crafting_level}.
                  </p>
                ) : null}
                <ForgeMaterialAudit costs={rule.costs} goldNeed={rule.gold_cost || 0} goldHave={playerGold} items={items} />
                <p className="text-xs text-[var(--text-muted)]">On failure the piece remains; spent gold and scrap are lost.</p>
                <button
                  type="button"
                  className="btn-gold w-full !py-3.5 !tracking-[0.22em]"
                  disabled={
                    !pathA.ok ||
                    !rule ||
                    !meetsCraftingLevelRarity ||
                    !canAffordRarityPath
                  }
                  title={
                    !canAffordRarityPath || !meetsCraftingLevelRarity
                      ? "Need higher forging level, more gold, or more materials in your bag."
                      : undefined
                  }
                  onClick={() => void startForge()}
                >
                  Strike forge
                </button>
              </div>
            )
          ) : forgeMode === "b" && pathB ? (
            !pathB.ok ? (
              <p className="text-sm text-[var(--crimson-400)]">{pathB.message || "No upgrades."}</p>
            ) : (
              <div className="space-y-5">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--crimson-400)]">
                  Risk: input consumed at start — failed claim destroys it. No refund.
                </p>
                <div>
                  <div className="text-label mb-1.5">Upgrade target</div>
                  <select className="wom-select" value={branchRecipeId} onChange={(e) => setBranchRecipeId(e.target.value)}>
                    <option value="">Select upgrade…</option>
                    {branchRecipes.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} ({Math.round(Number(r.success_chance ?? 1) * 100)}%)
                      </option>
                    ))}
                  </select>
                </div>
                {selectedBranch ? (
                  <>
                    <p className="text-sm text-[var(--text-secondary)]">{selectedBranch.description}</p>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {(
                        [
                          ["Time", `${selectedBranch.craft_seconds}s`],
                          ["Gold", selectedBranch.gold_cost],
                          ["Req.Lv", selectedBranch.required_crafting_level],
                          ["Success", `${Math.round(Number(selectedBranch.success_chance ?? 1) * 100)}%`],
                        ] as const
                      ).map(([label, val]) => (
                        <div key={label} className="border border-[var(--border-default)] bg-[var(--bg-void)] px-2 py-2 text-center">
                          <div className="text-label !text-[9px] !tracking-[0.2em] text-[var(--gold-600)]">{label}</div>
                          <div className="wom-font-mono text-sm font-bold text-[var(--text-primary)]">{val}</div>
                        </div>
                      ))}
                    </div>
                    {!meetsCraftingLevelUpgrade ? (
                      <p className="text-xs text-amber-400/95">
                        Your forging skill is Lv.{craftLevel}; this upgrade requires Lv.{selectedBranch.required_crafting_level}.
                      </p>
                    ) : null}
                    <ForgeMaterialAudit
                      costs={selectedBranch.costs}
                      goldNeed={selectedBranch.gold_cost || 0}
                      goldHave={playerGold}
                      items={items}
                    />
                  </>
                ) : (
                  <p className="text-xs text-[var(--text-muted)]">Pick an upgrade recipe to see timers, odds, and material checks.</p>
                )}
                <button
                  type="button"
                  className="btn-gold w-full !py-3.5 !tracking-[0.22em]"
                  disabled={
                    !pathB.ok ||
                    !branchRecipeId ||
                    !selectedBranch ||
                    !meetsCraftingLevelUpgrade ||
                    !canAffordUpgradePath
                  }
                  title={
                    !branchRecipeId
                      ? "Choose an upgrade recipe first."
                      : !canAffordUpgradePath || !meetsCraftingLevelUpgrade
                        ? "Need higher forging level, more gold, or more materials in your bag."
                        : undefined
                  }
                  onClick={() => void startForge()}
                >
                  Strike forge
                </button>
              </div>
            )
          ) : (
            <p className="text-sm text-[var(--text-muted)]">No data for this path.</p>
          )}
        </WomPanel>
      ) : (
        <WomPanel className="p-4 sm:p-5" glow={false}>
          <p className="text-center text-xs text-[var(--text-muted)]">
            {job
              ? "Clear or claim your active work order before starting another forge."
              : "Choose unequipped bag gear in the Anvil to open the Rarity path or Upgrade workshop."}
          </p>
        </WomPanel>
      )}
    </div>
  );
}
