import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import type { CraftRecipeRow, CraftJobRow, InvRow } from "@/lib/apiTypes";
import { craftingXpToNextLevel } from "@/lib/craftingXp";
import { ItemIcon } from "../ItemIcon";

function recipeCostLines(costs: Record<string, number> | undefined): string[] {
  if (!costs) return [];
  return Object.entries(costs)
    .filter(([, n]) => (n || 0) > 0)
    .map(([k, n]) => `${k.replace(/_/g, " ")} ×${n}`);
}

export function CraftingTab() {
  const { inventory, refreshInventory, itemPost } = useGameSession();
  const char = inventory?.character;
  const items = inventory?.items || [];
  const recipes = (inventory?.craft_recipes || []) as CraftRecipeRow[];
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

  const bagByTemplate = useMemo(() => {
    const m = new Map<string, InvRow[]>();
    for (const it of items) {
      if (it.is_equipped) continue;
      const tid = it.template_id || "";
      if (!tid) continue;
      const arr = m.get(tid) || [];
      arr.push(it);
      m.set(tid, arr);
    }
    return m;
  }, [items]);

  const startCraft = useCallback(
    async (recipe: CraftRecipeRow, sourceItemId: string) => {
      try {
        const res = await itemPost("/api/game/craft/start", {
          recipe_id: recipe.id,
          source_item_id: sourceItemId,
        });
        const j = (await res.json()) as { ok?: boolean; message?: string };
        if (res.ok && j.ok !== false) toast.success(j.message || "Crafting started.");
        else toast.error(j.message || "Could not start craft.");
        await refreshInventory();
      } catch (e) {
        toast.error(String(e));
      }
    },
    [itemPost, refreshInventory],
  );

  const claimCraft = useCallback(async () => {
    try {
      const res = await itemPost("/api/game/craft/claim", {});
      const j = (await res.json()) as { ok?: boolean; message?: string };
      if (res.ok && j.ok !== false) toast.success(j.message || "Claimed.");
      else toast.error(j.message || "Could not claim.");
      await refreshInventory();
    } catch (e) {
      toast.error(String(e));
    }
  }, [itemPost, refreshInventory]);

  return (
    <div className="space-y-3 hero-tab-ref">
      <div className="game-panel game-panel-hero min-w-0">
        <div className="game-panel-header game-panel-header-hero">Forge</div>
        <p className="hero-panel-subtitle">
          Salvage gear in Hero inventory for scrap, then spend scrap + gold to upgrade items here. Timed crafts finish
          automatically — claim when ready.
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
          <div className="text-xs font-cinzel font-semibold text-foreground mb-1">Active craft</div>
          {!job ? (
            <p className="text-[11px] text-muted-foreground">No job in progress.</p>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-foreground">{job.recipe_name || job.recipe_id}</p>
              <p className="text-[10px] text-muted-foreground">
                {job.status === "ready" || canClaim
                  ? "Ready to claim."
                  : secondsLeft != null
                    ? `Finishes in ${secondsLeft}s`
                    : "In progress…"}
              </p>
              <button
                type="button"
                className="game-btn-primary text-xs px-3 py-1"
                disabled={!canClaim}
                onClick={() => void claimCraft()}
              >
                Claim item
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="game-panel game-panel-hero min-w-0">
        <div className="game-panel-header game-panel-header-hero">Upgrade recipes</div>
        <p className="hero-panel-subtitle text-[11px]">
          Start consumes your input item, materials, and gold. Claim the upgraded item when the timer completes.
        </p>
        <ul className="mt-2 space-y-2 max-h-[min(60vh,520px)] overflow-y-auto pr-1">
          {recipes.map((r) => {
            const inputs = bagByTemplate.get(r.input_template_id) || [];
            const first = inputs[0];
            const hasInput = Boolean(first);
            const costs = (r.costs || {}) as Record<string, number>;
            let matsOk = true;
            for (const [tid, need] of Object.entries(costs)) {
              const have = items
                .filter((it) => !it.is_equipped && it.template_id === tid)
                .reduce((s, it) => s + Number(it.quantity ?? 1), 0);
              if (have < Number(need || 0)) matsOk = false;
            }
            const levelOk = craftLevel >= Number(r.required_crafting_level || 1);
            const goldOk = Number(char?.gold ?? 0) >= Number(r.gold_cost || 0);
            const canStart = hasInput && matsOk && levelOk && goldOk && !job;
            return (
              <li
                key={r.id}
                className="rounded-sm border border-border/50 bg-muted/5 p-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-cinzel text-xs font-semibold text-foreground">{r.name}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{r.description}</div>
                  <div className="text-[10px] text-muted-foreground mt-1 space-x-2">
                    <span>{r.craft_seconds}s</span>
                    <span>·</span>
                    <span>{r.gold_cost}🪙</span>
                    <span>·</span>
                    <span>Lv.{r.required_crafting_level}+</span>
                    <span>·</span>
                    <span>+{r.crafting_xp_reward} forge XP</span>
                  </div>
                  <div className="text-[10px] text-amber-200/80 mt-1">{recipeCostLines(costs).join(" · ") || "No extra scrap"}</div>
                  {!levelOk && (
                    <div className="text-[10px] text-destructive mt-1">Requires forging level {r.required_crafting_level}.</div>
                  )}
                  {!hasInput && <div className="text-[10px] text-destructive mt-1">Need {r.input_template_id} in bag.</div>}
                  {hasInput && !matsOk && <div className="text-[10px] text-destructive mt-1">Not enough scrap in bag.</div>}
                  {hasInput && !goldOk && <div className="text-[10px] text-destructive mt-1">Not enough gold.</div>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {first ? <ItemIcon item={first} size={40} /> : <span className="text-2xl opacity-40">📦</span>}
                  <button
                    type="button"
                    className="game-btn-primary text-[10px] px-2 py-1 whitespace-nowrap"
                    disabled={!canStart}
                    onClick={() => first && void startCraft(r, first.id)}
                  >
                    Start
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
