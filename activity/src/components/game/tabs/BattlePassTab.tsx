import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { RewardRevealDialog } from "@/components/game/RewardRevealDialog";
import * as api from "@/lib/gameApi";
import type { BattlePassStatePayload, BattlePassTierRow, RewardDelivery } from "@/lib/apiTypes";
import { WomOrnateDivider, WomPanel, WomSectionHeader, WomStatBar } from "@/components/wom/WomUi";
import "./battle-pass.css";

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

function tierCardClass(t: BattlePassTierRow, currentTier: number): string {
  const parts = ["bp-tier-card"];
  if (t.tier === currentTier && t.unlocked) parts.push("is-current");
  if (t.claimable) parts.push("is-claimable");
  if (t.locked_premium) parts.push("is-locked-premium");
  return parts.join(" ");
}

function TierLane({
  label,
  tiers,
  currentTier,
  premiumLocked,
  claimingKey,
  onClaim,
  scrollRef,
  onScroll,
}: {
  label: string;
  tiers: BattlePassTierRow[];
  currentTier: number;
  premiumLocked?: boolean;
  claimingKey: string | null;
  onClaim: (tier: number, track: string) => void;
  scrollRef: RefObject<HTMLDivElement | null>;
  onScroll: () => void;
}) {
  return (
    <div className={`bp-premium-overlay${premiumLocked ? " is-locked" : ""}`}>
      <div className="bp-lane-label">{label}</div>
      <div className="bp-lane-scroll" ref={scrollRef} onScroll={onScroll}>
        <div className="bp-lane-row">
          {tiers.map((t) => {
            const key = `${t.track}-${t.tier}`;
            return (
              <div key={key} className={tierCardClass(t, currentTier)}>
                <div className="bp-tier-num">T{t.tier}</div>
                <div className="bp-tier-reward">{rewardSummary(t.reward)}</div>
                {t.claimed ? (
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-[var(--verdant)]">Claimed</span>
                ) : t.claimable ? (
                  <button
                    type="button"
                    className="btn-gold !px-2 !py-1 !text-[9px] w-full"
                    disabled={claimingKey === key}
                    onClick={() => onClaim(t.tier, t.track)}
                  >
                    {claimingKey === key ? "…" : "Claim"}
                  </button>
                ) : (
                  <span className="text-[9px] text-[var(--text-disabled)] uppercase tracking-wider">
                    {t.locked_premium ? "Premium" : t.unlocked ? "—" : "Locked"}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function BattlePassTab() {
  const { accessToken, guildId, refreshInventory } = useGameSession();
  const [state, setState] = useState<BattlePassStatePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [claimingLogin, setClaimingLogin] = useState(false);
  const [claimingKey, setClaimingKey] = useState<string | null>(null);
  const [rewardOpen, setRewardOpen] = useState(false);
  const [rewardDelivery, setRewardDelivery] = useState<RewardDelivery | null>(null);
  const [rewardTitle, setRewardTitle] = useState("Battle pass reward");
  const playtimeSent = useRef(0);
  const freeScrollRef = useRef<HTMLDivElement>(null);
  const premScrollRef = useRef<HTMLDivElement>(null);
  const syncingScroll = useRef(false);

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
  const premiumOk = Boolean(prog?.premium_unlocked);
  const tiersFree = state?.tiers_free ?? (state?.tiers || []).filter((t) => t.track === "free");
  const tiersPremium = state?.tiers_premium ?? (state?.tiers || []).filter((t) => t.track === "premium");
  const currentTier = prog?.tier ?? 0;

  const progressPct = useMemo(() => {
    if (!prog || !season) return 0;
    const per = season.xp_per_tier || 100;
    const inTier = prog.xp_in_tier ?? 0;
    return Math.min(100, Math.round((inTier / Math.max(1, per)) * 100));
  }, [prog, season]);

  const claimableCount = useMemo(
    () => [...tiersFree, ...tiersPremium].filter((t) => t.claimable).length,
    [tiersFree, tiersPremium],
  );

  const syncFromFree = () => {
    if (syncingScroll.current) return;
    const a = freeScrollRef.current;
    const b = premScrollRef.current;
    if (!a || !b) return;
    syncingScroll.current = true;
    b.scrollLeft = a.scrollLeft;
    syncingScroll.current = false;
  };

  const syncFromPrem = () => {
    if (syncingScroll.current) return;
    const a = freeScrollRef.current;
    const b = premScrollRef.current;
    if (!a || !b) return;
    syncingScroll.current = true;
    a.scrollLeft = b.scrollLeft;
    syncingScroll.current = false;
  };

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

  const claimTier = async (tier: number, track: string) => {
    if (!accessToken) return;
    const key = `${track}-${tier}`;
    setClaimingKey(key);
    try {
      const j = await api.claimBattlePassTier(accessToken, tier, guildId, track);
      if (j.ok === false) {
        toast.error(j.message || "Could not claim.");
      } else {
        setRewardTitle(`Tier ${tier} — ${track === "premium" ? "Premium" : "Free"}`);
        setRewardDelivery((j.delivery as RewardDelivery) ?? null);
        setRewardOpen(true);
        await refreshInventory();
        await load();
      }
    } catch (e) {
      toast.error(String(e));
    } finally {
      setClaimingKey(null);
    }
  };

  const unlockPremium = async () => {
    if (!accessToken) return;
    try {
      const res = await fetch(api.apiUrl("/api/game/battle-pass/unlock-premium"), {
        method: "POST",
        headers: { ...api.authHeaders(accessToken, guildId), "Content-Type": "application/json" },
        body: "{}",
      });
      const j = (await res.json()) as { ok?: boolean; message?: string; battle_pass?: BattlePassStatePayload };
      if (!j.ok) toast.error(j.message || "Could not unlock premium.");
      else {
        toast.success(j.message || "Premium unlocked.");
        if (j.battle_pass) setState(j.battle_pass);
        else await load();
      }
    } catch (e) {
      toast.error(String(e));
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

  return (
    <div className="space-y-4 pb-2">
      <RewardRevealDialog
        open={rewardOpen}
        onOpenChange={setRewardOpen}
        title={rewardTitle}
        description="Season reward added to your character."
        delivery={rewardDelivery}
      />

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
      </WomPanel>

      <WomPanel className="p-5 sm:p-6" glow>
        <WomSectionHeader
          kicker="Dual track"
          title="Season lanes"
          right={
            claimableCount > 0 ? (
              <span className="text-xs font-semibold text-[var(--verdant)]">{claimableCount} ready</span>
            ) : undefined
          }
        />
        <div className="bp-lanes-wrap">
          <TierLane
            label="Free track"
            tiers={tiersFree}
            currentTier={currentTier}
            claimingKey={claimingKey}
            onClaim={claimTier}
            scrollRef={freeScrollRef}
            onScroll={syncFromFree}
          />
          <TierLane
            label="Premium track"
            tiers={tiersPremium}
            currentTier={currentTier}
            premiumLocked={!premiumOk}
            claimingKey={claimingKey}
            onClaim={claimTier}
            scrollRef={premScrollRef}
            onScroll={syncFromPrem}
          />
        </div>
        {!premiumOk ? (
          <div className="mt-4 flex flex-col items-center gap-2 sm:flex-row sm:justify-center">
            <p className="text-xs text-[var(--text-muted)] text-center sm:text-left">
              Premium lane unlocks with supporter status or a season unlock.
            </p>
            <button type="button" className="btn-ghost !text-[11px]" onClick={() => void unlockPremium()}>
              Unlock premium (test)
            </button>
          </div>
        ) : null}
      </WomPanel>
    </div>
  );
}
