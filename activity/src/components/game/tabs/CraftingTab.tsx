import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CraftRecipeRow, CraftJobRow, InvRow } from "@/lib/apiTypes";
import { craftingXpToNextLevel } from "@/lib/craftingXp";
import * as api from "@/lib/gameApi";
import { ErrorState } from "@/components/ui/error-state";
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

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function lookupForgeMaterialName(
  templateId: string,
  catalog: Record<string, string> | undefined,
): string | undefined {
  if (!catalog) return undefined;
  const tid = String(templateId || "").trim();
  const direct = catalog[tid]?.trim();
  if (direct) return direct;
  const low = tid.toLowerCase();
  for (const [k, v] of Object.entries(catalog)) {
    if (k.toLowerCase() === low && v.trim()) return v.trim();
  }
  return undefined;
}

function materialLabel(
  templateId: string,
  sample: InvRow | undefined,
  catalog?: Record<string, string>,
): string {
  const fromApi = lookupForgeMaterialName(templateId, catalog);
  if (fromApi) return fromApi;
  const n = sample?.name?.trim();
  if (n) return n;
  const tid = String(templateId || "").trim();
  if (UUID_RE.test(tid)) return `Reagent (${tid.slice(0, 8)}…)`;
  return prettyMaterialKey(tid);
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
  materialNames,
}: {
  costs: Record<string, number> | undefined;
  goldNeed: number;
  goldHave: number;
  items: InvRow[];
  materialNames?: Record<string, string>;
}) {
  const scrapRows = Object.entries(costs || {}).filter(([, n]) => (n || 0) > 0);
  const goldOk = goldHave >= goldNeed;

  return (
    <div className="space-y-3">
      <WomOrnateDivider label="Materials" />
      <div className="rounded-sm border border-[var(--border-default)] bg-[var(--bg-void)]/80 px-3 py-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        <p className="mb-2 flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
          <span className="inline-flex items-center gap-1.5 font-semibold text-foreground">
            <WomGoldCoin size={16} />
            Gold
          </span>
          <span className="text-[var(--text-muted)]">—</span>
          <span className="wom-font-mono tabular-nums">
            need <span className="font-semibold text-[var(--gold-200)]">{goldNeed.toLocaleString()}</span>
            <span className="text-[var(--text-muted)]">, you have </span>
            <span className={goldOk ? "font-semibold text-[var(--verdant)]" : "font-semibold text-[var(--crimson-400)]"}>
              {goldHave.toLocaleString()}
            </span>
          </span>
        </p>
        {scrapRows.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No extra scrap or reagents — gold covers this forge.</p>
        ) : (
          <ul className="mt-2 space-y-2 border-t border-[var(--border-default)]/60 pt-2">
            {scrapRows.map(([templateId, need]) => {
              const have = ownedTemplateQty(items, templateId);
              const ok = have >= need;
              const sample = items.find(
                (it) => String(it.template_id || "").trim().toLowerCase() === templateId.toLowerCase(),
              );
              return (
                <li key={templateId} className="text-xs sm:text-sm">
                  <span className="font-semibold text-foreground">{materialLabel(templateId, sample, materialNames)}</span>
                  <span className="text-[var(--text-muted)]"> — </span>
                  <span className="wom-font-mono tabular-nums text-[var(--text-muted)]">
                    need <span className="font-semibold text-foreground">{need}</span>
                    <span>, you have </span>
                    <span className={ok ? "font-semibold text-[var(--verdant)]" : "font-semibold text-amber-400"}>{have}</span>
                  </span>
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
  item_id?: string;
  /** Server-resolved `item_templates.name` for each `costs` key (works when the player owns 0). */
  material_names?: Record<string, string>;
  path_a?: ForgePathAOption;
  path_b?: ForgePathBOption;
};

function isGearRow(it: InvRow): boolean {
  const t = (it.item_type || "").toLowerCase();
  return t === "weapon" || t === "armor" || t === "accessory";
}

export function CraftingTab() {
  const { inventory, refreshInventory, refreshProgress, itemPost, accessToken, guildId } = useGameSession();
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
        toast.success(
          `Repaired ${n} item${n === 1 ? "" : "s"} for ${(j.total ?? 0).toLocaleString()} 🪙.`,
        );
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
        <WomSectionHeader kicker="Guild services" title="Repair gear" />
        {(() => {
          if (repairError) {
            return <ErrorState message="Could not load the repair quote." onRetry={() => void loadRepairQuote()} />;
          }
          if (repairLoading && !repairQuote) {
            return <p className="text-sm text-[var(--text-muted)]">Checking your gear for damage…</p>;
          }
          const quoteItems = repairQuote?.items || [];
          const repairTotal = Math.max(0, Math.floor(Number(repairQuote?.total ?? 0)));
          const repairGold = Math.max(0, Math.floor(Number(repairQuote?.gold ?? char?.gold ?? 0)));
          const cantAfford = repairTotal > 0 && repairGold < repairTotal;
          return (
            <div className="space-y-4">
              {quoteItems.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)]">All gear is in fighting shape — nothing to repair.</p>
              ) : (
                <ul className="space-y-2">
                  {quoteItems.map((it) => (
                    <li
                      key={it.id}
                      className="flex items-center gap-3 rounded-sm border border-[var(--border-default)] bg-[var(--bg-void)]/80 px-3 py-2"
                    >
                      <span className="shrink-0">
                        <ItemIcon
                          item={{ id: it.id, name: it.name, icon: it.icon, rarity: it.rarity } as InvRow}
                          size={32}
                        />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-foreground">{it.name}</span>
                        <span className="block text-[10px] uppercase tracking-widest text-[var(--text-muted)]">
                          −{it.missing ?? 0} durability
                        </span>
                      </span>
                      <span className="wom-font-mono shrink-0 text-sm tabular-nums text-[var(--gold-200)]">
                        {(it.cost ?? 0).toLocaleString()} 🪙
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-default)]/60 pt-3">
                <span className="wom-font-mono text-sm tabular-nums text-[var(--text-secondary)]">
                  Total <span className="font-semibold text-[var(--gold-200)]">{repairTotal.toLocaleString()}</span>
                  <span className="text-[var(--text-muted)]"> 🪙 · you have </span>
                  <span className={cantAfford ? "font-semibold text-[var(--crimson-400)]" : "font-semibold text-[var(--verdant)]"}>
                    {repairGold.toLocaleString()}
                  </span>
                </span>
                <button
                  type="button"
                  className="btn-gold shrink-0 !px-6 !py-3 !text-[11px]"
                  disabled={repairing || repairLoading || repairTotal === 0 || cantAfford}
                  title={cantAfford ? "Not enough gold to cover the full repair bill." : undefined}
                  onClick={() => void repairAll()}
                >
                  {repairing ? "Repairing…" : "Repair all"}
                </button>
              </div>
              {cantAfford ? (
                <p className="text-xs text-amber-400/95">
                  You need {(repairTotal - repairGold).toLocaleString()} more gold to repair everything.
                </p>
              ) : null}
            </div>
          );
        })()}
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
                <ForgeMaterialAudit
                  costs={rule.costs}
                  goldNeed={rule.gold_cost || 0}
                  goldHave={playerGold}
                  items={items}
                  materialNames={forgeOptions?.material_names}
                />
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
                      materialNames={forgeOptions?.material_names}
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
