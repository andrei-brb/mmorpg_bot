import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { BattlePassStatePayload } from "@/lib/apiTypes";
import { WomOrnateDivider, WomPanel, WomSectionHeader, WomStatBar } from "@/components/wom/WomUi";

function rewardSummary(reward: Record<string, unknown> | undefined): string {
  if (!reward) return "Reward";
  const parts: string[] = [];
  if (reward.gold) parts.push(`${reward.gold} gold`);
  if (reward.character_xp) parts.push(`${reward.character_xp} XP`);
  if (reward.crafting_xp) parts.push(`${reward.crafting_xp} forge XP`);
  const items = (reward.items as { template_id?: string; quantity?: number }[]) || [];
  for (const it of items) {
    if (it?.template_id) parts.push(`${it.quantity ?? 1}× ${it.template_id.replace(/_/g, " ")}`);
  }
  return parts.length ? parts.join(", ") : "Bundle";
}

function formatEndsAt(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function BattlePassTab() {
  const { accessToken, guildId, refreshInventory } = useGameSession();
  const [state, setState] = useState<BattlePassStatePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [claimingLogin, setClaimingLogin] = useState(false);
  const [claimingTier, setClaimingTier] = useState<number | null>(null);
  const playtimeSent = useRef(0);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const j = await api.getBattlePass(accessToken, guildId);
      setState(j);
    } catch (e) {
      toast.error(String(e));
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!accessToken) return;
    const tick = () => {
      const now = Date.now();
      if (now - playtimeSent.current < 5 * 60 * 1000) return;
      playtimeSent.current = now;
      void api.postBattlePassPlaytime(accessToken, 5, guildId).then(() => void load());
    };
    tick();
    const id = window.setInterval(tick, 5 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [accessToken, guildId, load]);

  const season = state?.season;
  const prog = state?.progress;
  const daily = state?.daily_login;

  const progressPct = useMemo(() => {
    if (!prog || !season) return 0;
    const per = season.xp_per_tier || 100;
    const inTier = prog.xp_in_tier ?? 0;
    return Math.min(100, Math.round((inTier / Math.max(1, per)) * 100));
  }, [prog, season]);

  const claimDaily = async () => {
    if (!accessToken || daily?.claimed_today) return;
    setClaimingLogin(true);
    try {
      const j = await api.claimDailyLogin(accessToken, guildId);
      if (j.ok === false) {
        toast.error(j.message || "Already claimed today.");
      } else {
        toast.success(`Daily login — +${j.login?.gold ?? 0} gold, streak ${j.login?.current_streak ?? 0}`);
        setState(j.battle_pass ?? state);
        await refreshInventory();
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setClaimingLogin(false);
    }
  };

  const claimTier = async (tier: number) => {
    if (!accessToken) return;
    setClaimingTier(tier);
    try {
      const j = await api.claimBattlePassTier(accessToken, tier, guildId);
      if (j.ok === false) toast.error(j.message || "Could not claim.");
      else {
        toast.success(j.message || "Claimed!");
        await refreshInventory();
        await load();
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setClaimingTier(null);
    }
  };

  if (loading && !state) {
    return <p className="px-2 text-sm text-[var(--text-muted)]">Loading battle pass…</p>;
  }

  if (!season) {
    return (
      <WomPanel className="p-5">
        <p className="text-sm text-[var(--text-secondary)]">No battle pass season is active right now. Check back soon.</p>
      </WomPanel>
    );
  }

  const claimableCount = (state?.tiers || []).filter((t) => t.claimable).length;

  return (
    <div className="space-y-4 pb-2">
      <WomPanel className="p-5 sm:p-6" glow>
        <WomSectionHeader kicker="Seasonal rewards" title={season.name || "Battle Pass"} />
        <p className="mb-4 text-sm text-[var(--text-secondary)]">
          {season.is_live ? (
            <>
              Ends <span className="text-[var(--gold-200)]">{formatEndsAt(season.ends_at)}</span>
              {daily?.weekend_double ? (
                <span className="ml-2 text-[var(--verdant)]">· Weekend double pass XP (UTC)</span>
              ) : null}
            </>
          ) : (
            <span className="text-amber-400">Season not live yet — progress unlocks when it starts.</span>
          )}
        </p>

        <div className="mb-4 space-y-2">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <span className="text-label">Tier {prog?.tier ?? 0} / {season.max_tier}</span>
            <span className="wom-font-mono text-xs tabular-nums text-[var(--text-muted)]">
              {prog?.xp?.toLocaleString() ?? 0} pass XP
            </span>
          </div>
          <WomStatBar value={prog?.xp_in_tier ?? 0} max={season.xp_per_tier || 100} variant="gold" />
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{progressPct}% to next tier</p>
        </div>

        <WomOrnateDivider label="Daily login" />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-[var(--text-secondary)]">
            Streak <span className="font-semibold text-[var(--gold-200)]">{daily?.current_streak ?? 0}</span> day(s)
            {daily?.longest_streak ? (
              <span className="text-[var(--text-muted)]"> · best {daily.longest_streak}</span>
            ) : null}
          </div>
          <button
            type="button"
            className="btn-gold shrink-0 !px-5 !py-2.5"
            disabled={daily?.claimed_today || claimingLogin || !season.is_live}
            onClick={() => void claimDaily()}
          >
            {daily?.claimed_today ? "Claimed today" : claimingLogin ? "Claiming…" : "Claim daily reward"}
          </button>
        </div>
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Daily login grants gold, character XP, and battle pass XP. Every 7-day streak grants a ladder milestone bonus.
        </p>
      </WomPanel>

      <WomPanel className="p-5 sm:p-6" glow>
        <WomSectionHeader
          kicker="Free track"
          title="Tier rewards"
          right={
            claimableCount > 0 ? (
              <span className="text-xs font-semibold text-[var(--verdant)]">{claimableCount} ready</span>
            ) : undefined
          }
        />
        <ul className="mt-3 max-h-[min(28rem,50vh)] space-y-2 overflow-y-auto pr-1">
          {(state?.tiers || []).map((t) => (
            <li
              key={t.tier}
              className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-[var(--border-default)] bg-[var(--bg-void)]/60 px-3 py-2.5"
            >
              <div className="min-w-0 flex-1">
                <div className="text-xs font-cinzel font-semibold uppercase tracking-wider text-[var(--gold-500)]">
                  Tier {t.tier}
                </div>
                <div className="text-sm text-[var(--text-secondary)]">{rewardSummary(t.reward)}</div>
              </div>
              {t.claimed ? (
                <span className="text-xs font-semibold text-[var(--verdant)]">Claimed</span>
              ) : t.claimable ? (
                <button
                  type="button"
                  className="btn-gold !px-4 !py-2 !text-[10px]"
                  disabled={claimingTier === t.tier}
                  onClick={() => void claimTier(t.tier)}
                >
                  {claimingTier === t.tier ? "…" : "Claim"}
                </button>
              ) : (
                <span className="text-xs text-[var(--text-disabled)]">{t.unlocked ? "—" : "Locked"}</span>
              )}
            </li>
          ))}
        </ul>
      </WomPanel>
    </div>
  );
}