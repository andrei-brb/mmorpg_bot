import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { BattlePassTierRow } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";
import type { CampSnapshot } from "@mobile/v2/useCampData";

/**
 * Battle Pass, in Ember.
 *
 * The classic tab renders two horizontally scroll-synced lanes of tier cards,
 * which on a phone means reading a spreadsheet sideways. Here the pass is a
 * vertical list — the natural axis for a phone — with free and premium side by
 * side per tier, so "what do I get at 12" is one glance instead of two.
 *
 * Claimable tiers glow; that's the only thing that does.
 */

/** Rewards are an open record, so describe whatever's actually in there. */
function describeReward(reward?: Record<string, unknown>): string {
  if (!reward) return "—";
  const bits: string[] = [];
  const gold = Number(reward.gold ?? 0);
  const xp = Number(reward.xp ?? reward.character_xp ?? 0);
  const forge = Number(reward.forge_xp ?? reward.crafting_xp ?? 0);
  if (gold) bits.push(`${gold.toLocaleString()} gold`);
  if (xp) bits.push(`${xp.toLocaleString()} XP`);
  if (forge) bits.push(`${forge.toLocaleString()} forge XP`);
  const items = reward.items;
  if (Array.isArray(items) && items.length) {
    bits.push(items.length === 1 ? "an item" : `${items.length} items`);
  }
  return bits.length ? bits.join(" · ") : "—";
}

function TierCell({
  row,
  onClaim,
  busy,
}: {
  row?: BattlePassTierRow;
  onClaim: (tier: number, track: string) => void;
  busy: boolean;
}) {
  if (!row) {
    return (
      <div
        className="rounded-lg px-2.5 py-2 text-center text-[10.5px]"
        style={{ background: "rgba(0,0,0,0.22)", color: "var(--a-700)" }}
      >
        —
      </div>
    );
  }
  const claimable = Boolean(row.claimable && !row.claimed);
  return (
    <div
      className={cn("rounded-lg px-2.5 py-2")}
      style={{
        background: claimable ? "rgba(255,122,47,0.12)" : "rgba(0,0,0,0.28)",
        border: `1px solid ${claimable ? "rgba(255,154,92,0.5)" : "var(--n-500)"}`,
      }}
    >
      <div className="text-[10.5px] leading-snug" style={{ color: "var(--a-300)" }}>
        {describeReward(row.reward)}
      </div>
      {row.claimed ? (
        <div className="mt-1 text-[10px]" style={{ color: "var(--a-700)" }}>
          Claimed
        </div>
      ) : claimable ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => onClaim(row.tier, row.track)}
          className="e-pill e-pill--ember mt-1.5 w-full"
        >
          {busy ? "…" : "Claim"}
        </button>
      ) : row.locked_premium ? (
        <div className="mt-1 text-[10px]" style={{ color: "var(--g-400)" }}>
          Premium
        </div>
      ) : (
        <div className="mt-1 text-[10px]" style={{ color: "var(--a-700)" }}>
          Locked
        </div>
      )}
    </div>
  );
}

export function PassScreen({ camp }: { camp: CampSnapshot }) {
  const { accessToken, guildId, refreshInventory, refreshProgress } = useGameSession();
  const [busy, setBusy] = useState(false);

  const pass = camp.pass ?? null;
  const season = pass?.season ?? null;
  const prog = pass?.progress ?? null;
  const login = pass?.daily_login ?? null;

  const tier = Number(prog?.tier ?? 0);
  const maxTier = Number(season?.max_tier ?? 0);
  const xpIn = Number(prog?.xp_in_tier ?? 0);
  const xpNeed = Number(prog?.xp_needed_for_next ?? 0);
  const premium = Boolean(prog?.premium_unlocked);

  /** Merge the two lanes into one row per tier — the phone-shaped view. */
  const rows = useMemo(() => {
    const free = pass?.tiers_free ?? pass?.tiers ?? [];
    const prem = pass?.tiers_premium ?? [];
    const byTier = new Map<number, { free?: BattlePassTierRow; premium?: BattlePassTierRow }>();
    for (const r of free) byTier.set(r.tier, { ...(byTier.get(r.tier) ?? {}), free: r });
    for (const r of prem) byTier.set(r.tier, { ...(byTier.get(r.tier) ?? {}), premium: r });
    return [...byTier.entries()].sort((a, b) => a[0] - b[0]);
  }, [pass?.tiers, pass?.tiers_free, pass?.tiers_premium]);

  const claimable = useMemo(
    () =>
      rows.reduce(
        (n, [, v]) =>
          n +
          (v.free?.claimable && !v.free.claimed ? 1 : 0) +
          (v.premium?.claimable && !v.premium.claimed ? 1 : 0),
        0,
      ),
    [rows],
  );

  async function claim(t: number, track: string) {
    if (!accessToken || busy) return;
    setBusy(true);
    try {
      const j = await api.claimBattlePassTier(accessToken, t, guildId, track);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        toast.success(`Tier ${t} claimed.`);
        await Promise.all([refreshInventory(), refreshProgress(), camp.refresh()]);
      } else toast.error((j as { message?: string })?.message || "Could not claim.");
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function claimLogin() {
    setBusy(true);
    const r = await camp.claimDailyLogin();
    setBusy(false);
    if (r.ok) toast.success(r.message || "Daily reward claimed.");
    else toast.error(r.message || "Could not claim.");
  }

  if (!season?.is_live) {
    return (
      <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
        <div className="mb-3 px-4">
          <span className="e-label">Battle Pass</span>
        </div>
        <div className="px-4">
          <div className="e-card p-5 text-center">
            <p className="mb-1 text-[13.5px] font-semibold" style={{ color: "var(--a-100)" }}>
              No season running
            </p>
            <p className="text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
              When one starts, your progress and rewards will show up here.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-baseline justify-between px-4">
        <span className="e-label">Battle Pass</span>
        {claimable > 0 ? (
          <span className="e-pill e-pill--ember">{claimable} ready</span>
        ) : null}
      </div>

      <div className="space-y-3 px-4">
        {/* ── Season ── */}
        <div className="e-card e-card--warm p-4">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="e-display text-[15px]" style={{ color: "var(--e-300)" }}>
              {season.name || "This season"}
            </span>
            {season.weekend_multiplier && Number(season.weekend_multiplier) > 1 ? (
              <span className="e-pill e-pill--gold shrink-0">
                ×{season.weekend_multiplier} weekend
              </span>
            ) : null}
          </div>
          {season.ends_at ? (
            <p className="mb-3 text-[11px]" style={{ color: "var(--a-500)" }}>
              Ends {new Date(season.ends_at).toLocaleDateString()}
            </p>
          ) : null}

          <div className="mb-1 flex items-baseline justify-between">
            <span className="e-num text-2xl font-bold leading-none" style={{ color: "var(--e-400)" }}>
              {tier}
              {maxTier ? <span style={{ color: "var(--a-700)" }}> / {maxTier}</span> : null}
            </span>
            {xpNeed > 0 ? (
              <span className="e-num text-[11px]" style={{ color: "var(--a-500)" }}>
                {(xpNeed - xpIn).toLocaleString()} XP to next tier
              </span>
            ) : null}
          </div>
          <div className="e-bar e-bar--xp mt-2" style={{ height: 5 }}>
            <i style={{ width: `${xpNeed > 0 ? Math.min(100, (xpIn / xpNeed) * 100) : 0}%` }} />
          </div>
        </div>

        {/* ── Daily login ── */}
        {login ? (
          <div className={cn("e-card flex items-center gap-3 p-4", !login.claimed_today && "e-card--ready")}>
            <div className="min-w-0 flex-1">
              <div className="e-label mb-1">Daily login</div>
              <p className="text-[13px]" style={{ color: "var(--a-100)" }}>
                {login.current_streak} day streak
              </p>
              {login.longest_streak ? (
                <p className="mt-0.5 text-[11px]" style={{ color: "var(--a-500)" }}>
                  Best run: {login.longest_streak} days
                </p>
              ) : null}
            </div>
            <button
              type="button"
              disabled={login.claimed_today || busy}
              onClick={() => void claimLogin()}
              className={cn("e-btn shrink-0 px-4", login.claimed_today ? "e-btn--quiet" : "e-btn--primary")}
            >
              {login.claimed_today ? "Claimed" : busy ? "…" : "Claim"}
            </button>
          </div>
        ) : null}

        {/* ── The track ── */}
        <div className="e-card p-4">
          <div className="mb-3 grid grid-cols-[2.2rem_1fr_1fr] items-baseline gap-2">
            <span className="e-label">Tier</span>
            <span className="e-label">Free</span>
            <span className="e-label" style={{ color: premium ? "var(--g-400)" : "var(--a-700)" }}>
              Premium {premium ? "" : "· locked"}
            </span>
          </div>

          <div className="space-y-2">
            {rows.map(([t, v]) => {
              const reached = t <= tier;
              return (
                <div key={t} className="grid grid-cols-[2.2rem_1fr_1fr] items-stretch gap-2">
                  <div
                    className="e-num grid place-items-center rounded-lg text-[12px] font-bold"
                    style={{
                      background: reached ? "rgba(255,122,47,0.14)" : "rgba(0,0,0,0.28)",
                      border: `1px solid ${reached ? "rgba(255,122,47,0.4)" : "var(--n-500)"}`,
                      color: reached ? "var(--e-300)" : "var(--a-700)",
                    }}
                  >
                    {t}
                  </div>
                  <TierCell row={v.free} onClaim={(tt, tr) => void claim(tt, tr)} busy={busy} />
                  <TierCell row={v.premium} onClaim={(tt, tr) => void claim(tt, tr)} busy={busy} />
                </div>
              );
            })}
          </div>

          {rows.length === 0 ? (
            <p className="py-4 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
              No tiers to show yet.
            </p>
          ) : null}
        </div>

        {!premium ? (
          <p className="px-1 text-center text-[11px] leading-relaxed" style={{ color: "var(--a-700)" }}>
            The premium track unlocks with supporter status when it's available this season.
          </p>
        ) : null}
      </div>
    </div>
  );
}
