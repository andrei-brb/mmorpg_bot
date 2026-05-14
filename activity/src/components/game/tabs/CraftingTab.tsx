import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CraftRecipeRow, CraftJobRow, InvRow } from "@/lib/apiTypes";
import { craftingXpToNextLevel } from "@/lib/craftingXp";
import * as api from "@/lib/gameApi";
import { ItemIcon } from "../ItemIcon";

function recipeCostLines(costs: Record<string, number> | undefined): string[] {
  if (!costs) return [];
  return Object.entries(costs)
    .filter(([, n]) => (n || 0) > 0)
    .map(([k, n]) => `${k.replace(/_/g, " ")} ×${n}`);
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
      toast.error("Select an item in the left slot.");
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

  return (
    <div className="space-y-3 hero-tab-ref">
      <div className="game-panel game-panel-hero min-w-0">
        <div className="game-panel-header game-panel-header-hero">Forge</div>
        <p className="hero-panel-subtitle text-[11px]">
          <strong className="text-amber-200/90">Rarity</strong> — same piece, one step toward rare; failure costs
          gold/scrap only. <strong className="text-amber-200/90">Upgrade</strong> — new item template; the input is
          consumed at start and <strong>destroyed on failure</strong> at claim.
        </p>

        <div className="mt-3 rounded-sm border border-border/60 bg-muted/10 px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-cinzel font-semibold text-foreground">Forging skill</span>
            <span className="text-[10px] tabular-nums text-muted-foreground">
              Lv.{craftLevel} · {craftXp} / {needXp} XP
            </span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-sm bg-black/40">
            <div className="h-full bg-primary/80 transition-all" style={{ width: `${xpPct}%` }} />
          </div>
        </div>

        <div className="mt-3 rounded-sm border border-amber-900/30 bg-black/20 px-3 py-2">
          <div className="text-xs font-cinzel font-semibold text-foreground mb-1">Active job</div>
          {!job ? (
            <p className="text-[11px] text-muted-foreground">No job in progress.</p>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-foreground">{jobTitle}</p>
              <p className="text-[10px] text-muted-foreground">
                {job.status === "ready" || canClaim
                  ? "Ready to claim (rolls success on claim)."
                  : secondsLeft != null
                    ? `Finishes in ${secondsLeft}s`
                    : "In progress…"}
              </p>
              {job.success_chance != null && (
                <p className="text-[10px] text-amber-200/80">
                  Success chance: {Math.round(Number(job.success_chance) * 100)}%
                </p>
              )}
              <button
                type="button"
                className="game-btn-primary text-xs px-3 py-1"
                disabled={!canClaim}
                onClick={() => void claimForge()}
              >
                Claim
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="game-panel game-panel-hero min-w-0">
        <div className="game-panel-header game-panel-header-hero">Anvil</div>
        <div className="mt-2 grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-start">
          <div className="rounded-sm border border-border/50 bg-muted/5 p-2 min-h-[120px]">
            <div className="text-[10px] font-cinzel font-semibold text-muted-foreground mb-1">Source</div>
            <select
              className="w-full text-[11px] bg-background border border-border rounded-sm px-2 py-1 mb-2"
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
            {selectedItem ? (
              <div className="flex justify-center pt-1">
                <ItemIcon item={selectedItem} size={56} />
              </div>
            ) : (
              <p className="text-[10px] text-muted-foreground text-center pt-4">Unequipped gear only.</p>
            )}
          </div>

          <div className="flex flex-col items-center justify-center gap-2 py-2 md:py-8">
            <div className="text-2xl text-muted-foreground hidden md:block">→</div>
            <div className="text-xl text-muted-foreground md:hidden">↓</div>
          </div>

          <div className="rounded-sm border border-border/50 bg-muted/5 p-2 min-h-[120px]">
            <div className="text-[10px] font-cinzel font-semibold text-muted-foreground mb-1">Outcome</div>
            {outcome ? (
              <p className={`text-[11px] ${outcome.ok ? "text-emerald-200" : "text-destructive"}`}>{outcome.text}</p>
            ) : selectedItem && job ? (
              <p className="text-[10px] text-muted-foreground">Claim your active job to resolve.</p>
            ) : (
              <p className="text-[10px] text-muted-foreground text-center pt-4 opacity-70">?</p>
            )}
          </div>
        </div>

        {selectedItem && !job && (
          <div className="mt-3 space-y-3">
            <div className="flex gap-2">
              <button
                type="button"
                className={`text-[10px] px-2 py-1 rounded-sm border ${forgeMode === "a" ? "border-primary bg-primary/15" : "border-border/60"}`}
                disabled={!pathA?.ok}
                onClick={() => setForgeMode("a")}
              >
                Rarity
              </button>
              <button
                type="button"
                className={`text-[10px] px-2 py-1 rounded-sm border ${forgeMode === "b" ? "border-primary bg-primary/15" : "border-border/60"}`}
                disabled={!pathB?.ok}
                onClick={() => setForgeMode("b")}
              >
                Upgrade
              </button>
            </div>

            {forgeMode === "a" && pathA && (
              <div className="rounded-sm border border-border/40 p-2 space-y-1">
                {!pathA.ok || !rule ? (
                  <p className="text-[10px] text-destructive">{pathA.message || "Infusion unavailable."}</p>
                ) : (
                  <>
                    <p className="text-[11px] text-foreground">
                      {pathA.from_rarity} → <strong>{pathA.to_rarity}</strong>
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {rule.craft_seconds}s · {rule.gold_cost}🪙 · Lv.{rule.required_crafting_level}+ · success{" "}
                      {Math.round(Number(rule.success_chance) * 100)}% · +{rule.crafting_xp_reward} forge XP
                    </p>
                    <p className="text-[10px] text-amber-200/90">{recipeCostLines(rule.costs).join(" · ") || "No scrap"}</p>
                    <p className="text-[10px] text-muted-foreground">On failure: item stays; costs are lost.</p>
                  </>
                )}
              </div>
            )}

            {forgeMode === "b" && pathB && (
              <div className="rounded-sm border border-amber-900/40 p-2 space-y-2">
                {!pathB.ok ? (
                  <p className="text-[10px] text-destructive">{pathB.message || "No upgrades."}</p>
                ) : (
                  <>
                    <p className="text-[10px] font-semibold text-destructive">
                      Risk: input is consumed when you start. On failed claim, it is gone — no refund.
                    </p>
                    <select
                      className="w-full text-[11px] bg-background border border-border rounded-sm px-2 py-1"
                      value={branchRecipeId}
                      onChange={(e) => setBranchRecipeId(e.target.value)}
                    >
                      <option value="">Select upgrade…</option>
                      {branchRecipes.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} ({Math.round(Number(r.success_chance ?? 1) * 100)}%)
                        </option>
                      ))}
                    </select>
                    {selectedBranch && (
                      <div className="text-[10px] text-muted-foreground space-y-0.5">
                        <div>{selectedBranch.description}</div>
                        <div>
                          {selectedBranch.craft_seconds}s · {selectedBranch.gold_cost}🪙 · Lv.
                          {selectedBranch.required_crafting_level}+ · success{" "}
                          {Math.round(Number(selectedBranch.success_chance ?? 1) * 100)}%
                        </div>
                        <div>{recipeCostLines(selectedBranch.costs).join(" · ") || "No scrap"}</div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            <button
              type="button"
              className="game-btn-primary text-xs px-3 py-1.5"
              disabled={
                job != null ||
                (forgeMode === "a" && (!pathA?.ok || !rule)) ||
                (forgeMode === "b" && (!pathB?.ok || !branchRecipeId))
              }
              onClick={() => void startForge()}
            >
              Forge
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
