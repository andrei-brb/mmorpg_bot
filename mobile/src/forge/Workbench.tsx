import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { ItemIcon } from "@/components/game/ItemIcon";
import { useForge, ownedTemplateQty, normRarity } from "@/hooks/useForge";

/**
 * Rework 2 — "The Workbench". Mobile only.
 *
 * The Forge is a gambling screen: pick gear, pick a path, pay, roll. Gambling
 * screens work when the odds and the price stay pinned in front of you while
 * you change your mind — so everything lives on one screen and nothing scrolls.
 *
 * Replaces the Activity's Forge on the phone, which stacked three tall panels
 * (Forge / Repair gear / Anvil) and chose the item — the most important decision
 * here — from a native <select> showing names with no icon, rarity or stats.
 *
 * All state and actions come from useForge(), the same hook CraftingTab uses.
 * This is a layout, not a second forge.
 */

const RARITY_HUE: Record<string, string> = {
  common: "hsl(216 12% 65%)",
  uncommon: "hsl(144 40% 51%)",
  rare: "hsl(217 90% 63%)",
  epic: "hsl(271 91% 65%)",
  legendary: "hsl(34 86% 59%)",
  mythic: "hsl(350 80% 62%)",
};

export function Workbench() {
  const f = useForge();
  const [pickerOpen, setPickerOpen] = useState(false);

  const rarityColor = RARITY_HUE[f.sourceRarity] ?? RARITY_HUE.common;

  // Cost + odds for whichever path is selected — the two numbers that decide
  // whether you tap Strike.
  const active = useMemo(() => {
    if (f.forgeMode === "a") {
      const r = f.rule;
      return {
        ok: Boolean(f.pathA?.ok && r),
        gold: r?.gold_cost ?? 0,
        costs: r?.costs ?? {},
        chance: r?.success_chance ?? null,
        level: r?.required_crafting_level ?? 1,
        seconds: r?.craft_seconds ?? null,
        affordable: f.canAffordRarityPath,
        meetsLevel: f.meetsCraftingLevelRarity,
        message: f.pathA?.message ?? null,
        to: f.pathA?.to_rarity ?? null,
      };
    }
    const b = f.selectedBranch;
    return {
      ok: Boolean(f.pathB?.ok && b),
      gold: b?.gold_cost ?? 0,
      costs: b?.costs ?? {},
      chance: b?.success_chance ?? null,
      level: b?.required_crafting_level ?? 1,
      seconds: b?.craft_seconds ?? null,
      affordable: f.canAffordUpgradePath,
      meetsLevel: f.meetsCraftingLevelUpgrade,
      message: f.pathB?.message ?? null,
      to: b?.name ?? null,
    };
  }, [f]);

  const chancePct = active.chance != null ? Math.round(Number(active.chance) * 100) : null;
  const canStrike =
    !f.job && Boolean(f.selectedId) && active.ok && active.affordable && active.meetsLevel;

  const matNames = f.forgeOptions?.material_names ?? {};
  const damagedCount = f.repairQuote?.items?.length ?? 0;

  return (
    <div className="flex h-full flex-col gap-2.5 px-3 pb-2 pt-2 font-body">
      {/* ── source slot: tap to pick ── */}
      <button
        type="button"
        onClick={() => setPickerOpen(true)}
        disabled={Boolean(f.job)}
        className={cn(
          "flex items-center gap-3 rounded-xl border p-2.5 text-left transition-colors",
          "border-gold/35 bg-gradient-to-b from-[hsl(265_26%_16%)] to-[hsl(264_26%_10%)]",
          f.job && "opacity-60",
        )}
      >
        {f.selectedItem ? (
          <>
            <div
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border"
              style={{ borderColor: rarityColor, background: "hsl(264 30% 6%)" }}
            >
              <ItemIcon item={f.selectedItem} className="h-9 w-9" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate font-display text-sm" style={{ color: rarityColor }}>
                {f.selectedItem.name}
              </div>
              <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                {normRarity(f.selectedItem.rarity)}
                {f.selectedItem.enhancement_level ? ` · +${f.selectedItem.enhancement_level}` : ""}
                {active.to ? <span className="text-gold"> → {active.to}</span> : null}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-dashed border-gold/30 text-lg text-gold-dim">
              ⚒
            </div>
            <div className="min-w-0 flex-1">
              <div className="font-display text-sm text-gold-bright">Choose a piece</div>
              <div className="text-[10px] text-muted-foreground">
                {f.bagGear.length} in your bag · equipped gear can't be forged
              </div>
            </div>
          </>
        )}
        <span className="shrink-0 text-gold">⇄</span>
      </button>

      {/* ── path toggle ── */}
      <div className="flex gap-2">
        {(
          [
            ["a", "Rarity", "Safer", f.rarityTabDisabled],
            ["b", "Upgrade", "Riskier", f.upgradeTabDisabled],
          ] as const
        ).map(([mode, label, hint, disabled]) => (
          <button
            key={mode}
            type="button"
            disabled={disabled}
            onClick={() => f.setForgeMode(mode)}
            className={cn(
              "flex-1 rounded-xl border py-2 text-center transition-colors",
              f.forgeMode === mode
                ? "border-gold bg-gold/12"
                : "border-border bg-black/20",
              disabled && "opacity-40",
            )}
          >
            <div
              className={cn(
                "font-display text-[11px] uppercase tracking-[0.18em]",
                f.forgeMode === mode ? "text-gold-bright" : "text-muted-foreground",
              )}
            >
              {label}
            </div>
            <div className={cn("text-[9px]", mode === "a" ? "text-[hsl(146_49%_56%)]" : "text-destructive")}>
              {hint}
            </div>
          </button>
        ))}
      </div>

      {/* Upgrade needs a target recipe; rarity has exactly one rule. */}
      {f.forgeMode === "b" && f.branchRecipes.length > 0 ? (
        <div className="flex gap-1.5 overflow-x-auto pb-0.5" style={{ scrollbarWidth: "none" }}>
          {f.branchRecipes.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => f.setBranchRecipeId(r.id)}
              className={cn(
                "shrink-0 rounded-lg border px-2.5 py-1.5 text-[10px] transition-colors",
                f.branchRecipeId === r.id ? "border-gold text-gold-bright" : "border-border text-muted-foreground",
              )}
            >
              {r.name}
            </button>
          ))}
        </div>
      ) : null}

      {/* ── odds + cost: the two numbers that matter ── */}
      <div className="rounded-xl border border-border bg-black/35 p-3">
        {f.job ? (
          <>
            <div className="mb-1 font-display text-sm text-gold-bright">{f.jobTitle}</div>
            <p className="text-[11px] text-muted-foreground">{f.jobStatusLine}</p>
            {f.successPct != null ? (
              <div className="mt-2">
                <div className="mb-1 flex justify-between text-[10px]">
                  <span className="text-muted-foreground">Success</span>
                  <span className="font-bold tabular-nums text-gold">{f.successPct}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-black/70">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${f.successPct}%`,
                      background: "linear-gradient(90deg, hsl(146 49% 40%), hsl(146 49% 56%))",
                    }}
                  />
                </div>
              </div>
            ) : null}
          </>
        ) : !f.selectedId ? (
          <p className="py-1 text-center text-[11px] text-muted-foreground">
            Pick a piece to see its odds and price.
          </p>
        ) : !active.ok ? (
          <p className="py-1 text-center text-[11px] text-muted-foreground">
            {active.message || "This path isn't available for that piece."}
          </p>
        ) : (
          <>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Success</span>
              <span
                className="font-display text-base font-bold tabular-nums"
                style={{ color: chancePct != null && chancePct >= 60 ? "hsl(146 49% 56%)" : "hsl(350 72% 62%)" }}
              >
                {chancePct != null ? `${chancePct}%` : "—"}
              </span>
            </div>
            <div className="mb-2.5 h-1.5 overflow-hidden rounded-full bg-black/70">
              <div
                className="h-full rounded-full transition-[width] duration-300"
                style={{
                  width: `${chancePct ?? 0}%`,
                  background:
                    chancePct != null && chancePct >= 60
                      ? "linear-gradient(90deg, hsl(146 49% 40%), hsl(146 49% 56%))"
                      : "linear-gradient(90deg, hsl(345 60% 38%), hsl(350 72% 60%))",
                }}
              />
            </div>

            <div className="flex justify-between text-[11px]">
              <span className="text-muted-foreground">Gold</span>
              <span
                className={cn("tabular-nums", f.playerGold >= active.gold ? "text-foreground" : "text-destructive")}
              >
                {active.gold.toLocaleString()}
              </span>
            </div>

            {Object.entries(active.costs)
              .filter(([, need]) => (need || 0) > 0)
              .map(([key, need]) => {
                const have = ownedTemplateQty(f.items, key);
                return (
                  <div key={key} className="flex justify-between text-[11px]">
                    <span className="truncate text-muted-foreground">
                      {matNames[key] || key.replace(/_/g, " ")} ×{need}
                    </span>
                    <span className={cn("shrink-0 tabular-nums", have >= need ? "text-[hsl(146_49%_56%)]" : "text-destructive")}>
                      have {have}
                    </span>
                  </div>
                );
              })}

            {!active.meetsLevel ? (
              <p className="mt-2 text-[10px] text-destructive">
                Needs forging level {active.level} — you're {f.craftLevel}.
              </p>
            ) : null}
            {f.forgeMode === "b" && f.pathB?.risk_destroy_on_fail ? (
              <p className="mt-2 text-[10px] text-destructive">
                The piece is consumed at the start and may be destroyed on a failed claim.
              </p>
            ) : null}
          </>
        )}
      </div>

      {f.outcome ? (
        <p
          className={cn(
            "rounded-lg border px-2.5 py-1.5 text-center text-[11px]",
            f.outcome.ok
              ? "border-[hsl(146_49%_51%/0.4)] text-[hsl(146_49%_66%)]"
              : "border-destructive/40 text-destructive",
          )}
        >
          {f.outcome.text}
        </p>
      ) : null}

      {/* ── the hammer ── */}
      <div className="mt-auto space-y-2">
        {f.job ? (
          <button
            type="button"
            disabled={!f.canClaim}
            onClick={() => void f.claimForge()}
            className={cn(
              "w-full rounded-xl py-3 font-display text-sm tracking-[0.18em] transition-opacity",
              f.canClaim
                ? "bg-gradient-to-b from-[#F2D98A] to-[#C9A24B] text-[#221803] shadow-[0_4px_16px_-4px_rgba(232,197,106,0.6)]"
                : "border border-border text-muted-foreground",
            )}
          >
            {f.canClaim ? "✦ COLLECT" : `HAMMERING… ${f.secondsLeft ?? 0}s`}
          </button>
        ) : (
          <button
            type="button"
            disabled={!canStrike}
            onClick={() => void f.startForge()}
            className={cn(
              "w-full rounded-xl py-3 font-display text-sm tracking-[0.18em] transition-opacity",
              canStrike
                ? "bg-gradient-to-b from-[#F2D98A] to-[#C9A24B] text-[#221803] shadow-[0_4px_16px_-4px_rgba(232,197,106,0.6)]"
                : "border border-border text-muted-foreground",
            )}
          >
            ⚒ STRIKE
          </button>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            disabled={f.repairing || damagedCount === 0}
            onClick={() => void f.repairAll()}
            className={cn(
              "flex-1 rounded-lg border border-border py-2 text-[11px] text-muted-foreground",
              damagedCount === 0 && "opacity-50",
            )}
          >
            {f.repairLoading
              ? "🛠 Repair…"
              : damagedCount > 0
                ? `🛠 Repair ${damagedCount} · ${(f.repairQuote?.total ?? 0).toLocaleString()}🪙`
                : "🛠 All intact"}
          </button>
          <div className="flex-1 rounded-lg border border-border py-2 text-center text-[11px] text-muted-foreground">
            Forge Lv.{f.craftLevel} · {f.xpPct}%
          </div>
        </div>
      </div>

      {/* ── picker sheet: the grid that replaces the dropdown ── */}
      {pickerOpen ? (
        <>
          <button
            type="button"
            aria-label="Close picker"
            onClick={() => setPickerOpen(false)}
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
          />
          <div
            className="fixed inset-x-0 bottom-0 z-50 max-h-[72dvh] overflow-y-auto rounded-t-2xl border-t border-gold/40 px-3 pt-3"
            style={{
              background: "linear-gradient(180deg, hsl(265 26% 15%), hsl(264 27% 9%))",
              paddingBottom: "calc(1rem + env(safe-area-inset-bottom))",
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Choose a piece to forge"
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-gold/30" />
            <div className="mb-2.5 flex items-baseline justify-between">
              <span className="font-display text-sm tracking-[0.1em] text-gold-bright">Choose a piece</span>
              <span className="text-[10px] text-muted-foreground">{f.bagGear.length} in bag</span>
            </div>

            {f.bagGear.length === 0 ? (
              <p className="py-6 text-center text-[11px] text-muted-foreground">
                No forgeable gear. Unequip a piece first — equipped and locked items can't be forged.
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-2 pb-2">
                {f.bagGear.map((it) => {
                  const r = normRarity(it.rarity);
                  const sel = it.id === f.selectedId;
                  return (
                    <button
                      key={it.id}
                      type="button"
                      onClick={() => {
                        f.setSelectedId(String(it.id));
                        setPickerOpen(false);
                      }}
                      className={cn(
                        "flex flex-col items-center gap-1 rounded-xl border p-2 transition-colors",
                        sel ? "bg-gold/10" : "bg-black/30",
                      )}
                      style={{ borderColor: sel ? "hsl(43 73% 66%)" : `${RARITY_HUE[r]}55` }}
                    >
                      <ItemIcon item={it} className="h-8 w-8" />
                      <span className="line-clamp-2 text-center text-[9px] leading-tight text-foreground/90">
                        {it.name}
                      </span>
                      <span className="text-[8px] uppercase tracking-wide" style={{ color: RARITY_HUE[r] }}>
                        {r}
                        {it.enhancement_level ? ` +${it.enhancement_level}` : ""}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

export default Workbench;
