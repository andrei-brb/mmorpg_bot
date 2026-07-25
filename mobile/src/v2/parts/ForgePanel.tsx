import { useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { ItemIcon } from "@/components/game/ItemIcon";
import { normRarity, ownedTemplateQty, useForge } from "@/hooks/useForge";
import { cn } from "@/lib/utils";

/**
 * The forge, in Ember.
 *
 * Drives the same useForge() hook as the classic Forge tab and the Workbench —
 * one source of truth for starting, claiming, repairing and affordability. This
 * is presentation only.
 *
 * The design position: forging is a gamble, so the odds and the price are the
 * headline and they never leave the screen while you change your mind. The
 * classic tab buries the success % below three stacked panels.
 */

const RARITY_VAR: Record<string, string> = {
  common: "var(--r-common)",
  uncommon: "var(--r-uncommon)",
  rare: "var(--r-rare)",
  epic: "var(--r-epic)",
  legendary: "var(--r-legendary)",
  mythic: "var(--r-mythic)",
};

export function ForgePanel() {
  const f = useForge();
  const { inventory } = useGameSession();
  const [pickerOpen, setPickerOpen] = useState(false);

  const matNames = f.forgeOptions?.material_names ?? {};
  const damaged = f.repairQuote?.items?.length ?? 0;
  const repairCost = Number(f.repairQuote?.total ?? 0);

  // Whichever path is selected decides the two numbers that matter.
  const isRarity = f.forgeMode === "a";
  const active = isRarity
    ? {
        ok: Boolean(f.pathA?.ok && f.rule),
        gold: f.rule?.gold_cost ?? 0,
        costs: f.rule?.costs ?? {},
        chance: f.rule?.success_chance ?? null,
        level: f.rule?.required_crafting_level ?? 1,
        afford: f.canAffordRarityPath,
        meets: f.meetsCraftingLevelRarity,
        message: f.pathA?.message ?? null,
        to: f.pathA?.to_rarity ?? null,
      }
    : {
        ok: Boolean(f.pathB?.ok && f.selectedBranch),
        gold: f.selectedBranch?.gold_cost ?? 0,
        costs: f.selectedBranch?.costs ?? {},
        chance: f.selectedBranch?.success_chance ?? null,
        level: f.selectedBranch?.required_crafting_level ?? 1,
        afford: f.canAffordUpgradePath,
        meets: f.meetsCraftingLevelUpgrade,
        message: f.pathB?.message ?? null,
        to: f.selectedBranch?.name ?? null,
      };

  const pct = active.chance != null ? Math.round(Number(active.chance) * 100) : null;
  const canStrike = !f.job && Boolean(f.selectedId) && active.ok && active.afford && active.meets;
  const rarity = normRarity(f.selectedItem?.rarity);

  return (
    <div className="space-y-3">
      {/* ── Skill ── */}
      <div className="e-card p-4">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="e-label">Forging</span>
          <span className="e-num text-[12px]" style={{ color: "var(--a-300)" }}>
            Level {f.craftLevel}
          </span>
        </div>
        <div className="e-bar e-bar--xp" style={{ height: 4 }}>
          <i style={{ width: `${f.xpPct}%` }} />
        </div>
        <p className="mt-1.5 text-[11px]" style={{ color: "var(--a-700)" }}>
          {f.craftXp.toLocaleString()} / {f.needXp.toLocaleString()} XP
        </p>
      </div>

      {/* ── The piece ── */}
      <button
        type="button"
        onClick={() => setPickerOpen(true)}
        disabled={Boolean(f.job)}
        className={cn("e-card e-card--warm flex w-full items-center gap-3 p-3.5 text-left", f.job && "opacity-60")}
      >
        {f.selectedItem ? (
          <>
            <span
              className="grid h-12 w-12 shrink-0 place-items-center rounded-xl"
              style={{ border: `1px solid ${RARITY_VAR[rarity]}`, background: "var(--n-700)" }}
            >
              <ItemIcon item={f.selectedItem} size={34} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[14px] font-semibold" style={{ color: RARITY_VAR[rarity] }}>
                {f.selectedItem.name}
              </span>
              <span className="block text-[11px] capitalize" style={{ color: "var(--a-500)" }}>
                {rarity}
                {Number(f.selectedItem.enhancement_level ?? 0) > 0 ? ` +${f.selectedItem.enhancement_level}` : ""}
                {active.to ? <span style={{ color: "var(--e-400)" }}> → {active.to}</span> : null}
              </span>
            </span>
          </>
        ) : (
          <>
            <span
              className="grid h-12 w-12 shrink-0 place-items-center rounded-xl text-lg"
              style={{ border: "1px dashed var(--n-400)", color: "var(--a-700)" }}
            >
              ⚒
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-semibold" style={{ color: "var(--a-100)" }}>
                Choose a piece
              </span>
              <span className="block text-[11px]" style={{ color: "var(--a-500)" }}>
                {f.bagGear.length} in your bag · equipped gear can't be forged
              </span>
            </span>
          </>
        )}
        <span className="shrink-0" style={{ color: "var(--e-400)" }}>
          ⇄
        </span>
      </button>

      {/* ── Path ── */}
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
              "e-card flex-1 py-2.5 text-center",
              f.forgeMode === mode && "e-card--warm",
              disabled && "opacity-40",
            )}
            style={f.forgeMode === mode ? { borderColor: "var(--e-500)" } : undefined}
          >
            <div
              className="text-[12px] font-semibold"
              style={{ color: f.forgeMode === mode ? "var(--e-300)" : "var(--a-500)" }}
            >
              {label}
            </div>
            <div
              className="text-[10px]"
              style={{ color: mode === "a" ? "var(--vital)" : "var(--wound)" }}
            >
              {hint}
            </div>
          </button>
        ))}
      </div>

      {/* Upgrade needs a target; rarity has one rule. */}
      {!isRarity && f.branchRecipes.length > 0 ? (
        <div className="e-scroll-x flex gap-1.5 pb-0.5">
          {f.branchRecipes.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => f.setBranchRecipeId(r.id)}
              className={cn("e-pill shrink-0", f.branchRecipeId === r.id ? "e-pill--ember" : "e-pill--quiet")}
            >
              {r.name}
            </button>
          ))}
        </div>
      ) : null}

      {/* ── Odds and price — the decision ── */}
      <div className="e-card p-4">
        {f.job ? (
          <>
            <div className="mb-1 text-[14px] font-semibold" style={{ color: "var(--e-300)" }}>
              {f.jobTitle}
            </div>
            <p className="text-[12px]" style={{ color: "var(--a-500)" }}>
              {f.jobStatusLine}
            </p>
            {f.successPct != null ? (
              <div className="mt-3">
                <div className="mb-1 flex justify-between text-[11px]">
                  <span style={{ color: "var(--a-500)" }}>Success</span>
                  <span className="e-num font-bold" style={{ color: "var(--e-400)" }}>
                    {f.successPct}%
                  </span>
                </div>
                <div className="e-bar" style={{ height: 5 }}>
                  <i
                    style={{
                      width: `${f.successPct}%`,
                      background: "linear-gradient(90deg, var(--e-700), var(--e-400))",
                    }}
                  />
                </div>
              </div>
            ) : null}
          </>
        ) : !f.selectedId ? (
          <p className="py-1 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
            Pick a piece to see its odds and price.
          </p>
        ) : !active.ok ? (
          <p className="py-1 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
            {active.message || "This path isn't available for that piece."}
          </p>
        ) : (
          <>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="e-label">Success</span>
              <span
                className="e-num text-lg font-bold"
                style={{ color: pct != null && pct >= 60 ? "var(--vital)" : "var(--wound)" }}
              >
                {pct != null ? `${pct}%` : "—"}
              </span>
            </div>
            <div className="e-bar mb-3" style={{ height: 5 }}>
              <i
                style={{
                  width: `${pct ?? 0}%`,
                  background:
                    pct != null && pct >= 60
                      ? "linear-gradient(90deg, #2E7A4F, var(--vital))"
                      : "linear-gradient(90deg, #8E2438, var(--wound))",
                }}
              />
            </div>

            <div className="flex items-baseline justify-between text-[12px]">
              <span style={{ color: "var(--a-500)" }}>Gold</span>
              <span
                className="e-num"
                style={{ color: f.playerGold >= active.gold ? "var(--a-100)" : "var(--wound)" }}
              >
                {active.gold.toLocaleString()}
              </span>
            </div>

            {Object.entries(active.costs)
              .filter(([, need]) => Number(need || 0) > 0)
              .map(([key, need]) => {
                const have = ownedTemplateQty(f.items, key);
                return (
                  <div key={key} className="flex items-baseline justify-between text-[12px]">
                    <span className="truncate" style={{ color: "var(--a-500)" }}>
                      {matNames[key] || key.replace(/_/g, " ")} ×{need}
                    </span>
                    <span
                      className="e-num shrink-0"
                      style={{ color: have >= Number(need) ? "var(--vital)" : "var(--wound)" }}
                    >
                      have {have}
                    </span>
                  </div>
                );
              })}

            {!active.meets ? (
              <p className="mt-2 text-[11px]" style={{ color: "var(--wound)" }}>
                Needs forging level {active.level} — you're {f.craftLevel}.
              </p>
            ) : null}
            {!isRarity && f.pathB?.risk_destroy_on_fail ? (
              <p className="mt-2 text-[11px] leading-relaxed" style={{ color: "var(--wound)" }}>
                The piece is consumed when you start, and may be destroyed if the claim fails.
              </p>
            ) : null}
          </>
        )}
      </div>

      {f.outcome ? (
        <p
          className="e-card px-3 py-2 text-center text-[12px]"
          style={{
            color: f.outcome.ok ? "var(--vital)" : "var(--wound)",
            borderColor: f.outcome.ok ? "rgba(79,180,119,0.4)" : "rgba(226,73,95,0.4)",
          }}
        >
          {f.outcome.text}
        </p>
      ) : null}

      {/* ── Act ── */}
      {f.job ? (
        <button
          type="button"
          disabled={!f.canClaim}
          onClick={() => void f.claimForge()}
          className={cn("e-btn w-full", f.canClaim ? "e-btn--primary" : "e-btn--quiet")}
        >
          {f.canClaim ? "Collect" : `Hammering… ${f.secondsLeft ?? 0}s`}
        </button>
      ) : (
        <button
          type="button"
          disabled={!canStrike}
          onClick={() => void f.startForge()}
          className={cn("e-btn w-full", canStrike ? "e-btn--primary" : "e-btn--quiet")}
        >
          Strike the forge
        </button>
      )}

      {/* ── Repair ── */}
      <button
        type="button"
        disabled={f.repairing || damaged === 0}
        onClick={() => void f.repairAll()}
        className={cn("e-card flex w-full items-center gap-3 p-3.5 text-left", damaged === 0 && "opacity-60")}
      >
        <span className="text-lg" aria-hidden>
          🛠
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold" style={{ color: "var(--a-100)" }}>
            {damaged > 0 ? `${damaged} damaged ${damaged === 1 ? "piece" : "pieces"}` : "Everything's intact"}
          </span>
          <span className="block text-[11px]" style={{ color: "var(--a-500)" }}>
            {f.repairLoading
              ? "Checking…"
              : damaged > 0
                ? `Damaged gear fights weaker · ${repairCost.toLocaleString()} gold to fix`
                : "No repairs needed"}
          </span>
        </span>
        {damaged > 0 ? (
          <span className="e-pill e-pill--ember shrink-0">{f.repairing ? "…" : "Repair"}</span>
        ) : null}
      </button>

      {/* ── Picker ── */}
      {pickerOpen ? (
        <>
          <button
            type="button"
            aria-label="Close"
            onClick={() => setPickerOpen(false)}
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
          />
          <div
            className="e-sheet e-scroll fixed inset-x-0 bottom-0 z-50 max-h-[74dvh] px-4"
            role="dialog"
            aria-modal="true"
            aria-label="Choose a piece to forge"
          >
            <div className="e-grabber" />
            <div className="mb-3 flex items-baseline justify-between">
              <h3 className="e-display text-[15px]" style={{ color: "var(--e-300)" }}>
                Choose a piece
              </h3>
              <span className="e-num text-[11px]" style={{ color: "var(--a-500)" }}>
                {f.bagGear.length} in bag
              </span>
            </div>
            {f.bagGear.length === 0 ? (
              <p className="py-6 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
                No forgeable gear. Unequip a piece first — equipped and locked items can't be forged.
              </p>
            ) : (
              <div className="grid grid-cols-4 gap-2 pb-2">
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
                      className="flex flex-col items-center gap-1 rounded-xl p-2"
                      style={{
                        border: `1px solid ${sel ? "var(--e-500)" : `${RARITY_VAR[r]}66`}`,
                        background: sel ? "rgba(255,122,47,0.1)" : "rgba(0,0,0,0.3)",
                      }}
                    >
                      <ItemIcon item={it} size={30} />
                      <span
                        className="line-clamp-2 text-center text-[9.5px] leading-tight"
                        style={{ color: "var(--a-300)" }}
                      >
                        {it.name}
                      </span>
                      <span className="text-[8.5px] capitalize" style={{ color: RARITY_VAR[r] }}>
                        {r}
                        {Number(it.enhancement_level ?? 0) > 0 ? ` +${it.enhancement_level}` : ""}
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
