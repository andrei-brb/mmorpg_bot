import { useCallback, useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { BattlePassStatePayload, IdleRewardsPayload } from "@/lib/apiTypes";

/**
 * The data the Camp screen needs that the session context does not carry.
 *
 * GameSessionContext covers character/inventory/explore/combat/quests. Idle
 * rewards, the daily quest, repair state and prestige each live behind their own
 * gameApi call, so this pulls them together into one "what is waiting for you"
 * snapshot — the same pattern useForge uses.
 *
 * Everything is best-effort: a single failing endpoint must not blank the home
 * screen, so each lands in its own piece of state and failures leave that piece
 * null rather than throwing.
 */

export type CampSnapshot = {
  idle: IdleRewardsPayload | null;
  daily: api.DailyQuestPayload["quest"] | null;
  repair: api.RepairQuotePayload | null;
  prestige: api.PrestigePayload | null;
  pass: BattlePassStatePayload | null;
  loading: boolean;
  refresh: () => Promise<void>;
  claimIdle: () => Promise<{ ok: boolean; gold?: number; message?: string }>;
  claimDailyLogin: () => Promise<{ ok: boolean; message?: string }>;
  upgradeIdleCap: () => Promise<{ ok: boolean; message?: string }>;
};

export function useCampData(): CampSnapshot {
  const { accessToken, guildId, phase, refreshInventory, refreshProgress } = useGameSession();
  const [idle, setIdle] = useState<IdleRewardsPayload | null>(null);
  const [daily, setDaily] = useState<api.DailyQuestPayload["quest"] | null>(null);
  const [repair, setRepair] = useState<api.RepairQuotePayload | null>(null);
  const [prestige, setPrestige] = useState<api.PrestigePayload | null>(null);
  const [pass, setPass] = useState<BattlePassStatePayload | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    // Parallel + independently settled: one dead endpoint shouldn't cost the
    // others. allSettled rather than all, deliberately.
    const [i, d, r, p, bp] = await Promise.allSettled([
      api.getIdleRewards(accessToken, guildId),
      api.getDailyQuest(accessToken, guildId),
      api.getRepairQuote(accessToken, guildId),
      api.getPrestige(accessToken, guildId),
      api.getBattlePass(accessToken, guildId),
    ]);
    setIdle(i.status === "fulfilled" ? i.value : null);
    setDaily(d.status === "fulfilled" ? (d.value?.quest ?? null) : null);
    setRepair(r.status === "fulfilled" && r.value?.ok !== false ? r.value : null);
    setPrestige(p.status === "fulfilled" ? p.value : null);
    setPass(bp.status === "fulfilled" ? bp.value : null);
    setLoading(false);
  }, [accessToken, guildId]);

  useEffect(() => {
    if (phase === "ready") void refresh();
  }, [phase, refresh]);

  const claimIdle = useCallback(async () => {
    if (!accessToken) return { ok: false, message: "Not signed in." };
    try {
      const j = await api.postIdleClaim(accessToken, guildId);
      if (j?.ok === false) return { ok: false, message: j.message || "Nothing to collect yet." };
      await Promise.all([refreshInventory(), refreshProgress()]);
      await refresh();
      return { ok: true, gold: Number(j?.gold_gained ?? 0) };
    } catch (e) {
      return { ok: false, message: String(e) };
    }
  }, [accessToken, guildId, refresh, refreshInventory, refreshProgress]);

  const upgradeIdleCap = useCallback(async () => {
    if (!accessToken) return { ok: false, message: "Not signed in." };
    try {
      const j = await api.postIdleCapUpgrade(accessToken, guildId);
      const ok = j?.ok !== false;
      if (ok) {
        await Promise.all([refreshInventory(), refreshProgress()]);
        await refresh();
      }
      return { ok, message: j?.message };
    } catch (e) {
      return { ok: false, message: String(e) };
    }
  }, [accessToken, guildId, refresh, refreshInventory, refreshProgress]);

  const claimDailyLogin = useCallback(async () => {
    if (!accessToken) return { ok: false, message: "Not signed in." };
    try {
      const j = await api.claimDailyLogin(accessToken, guildId);
      const ok = (j as { ok?: boolean })?.ok !== false;
      if (ok) {
        await Promise.all([refreshInventory(), refreshProgress()]);
        await refresh();
      }
      return { ok, message: (j as { message?: string })?.message };
    } catch (e) {
      return { ok: false, message: String(e) };
    }
  }, [accessToken, guildId, refresh, refreshInventory, refreshProgress]);

  return { idle, daily, repair, prestige, pass, loading, refresh, claimIdle, claimDailyLogin, upgradeIdleCap };
}
