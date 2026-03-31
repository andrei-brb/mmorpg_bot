import { useState, useEffect, useCallback, useRef } from "react";
import type {
  PvpStatus,
  PvpMatchState,
  PvpHistoryResponse,
  PvpMode,
} from "@/lib/pvpTypes";

const USE_MOCK = import.meta.env.VITE_USE_PVP_MOCK !== "false";

// ── Mock Data ──────────────────────────────────────────────────────────────

const mockStatus: PvpStatus = {
  match_status: "idle",
  stats: {
    rating: 1547,
    rank_tier: "Gold II",
    wins: 42,
    losses: 28,
    draws: 3,
    win_rate: 57.5,
    streak: 3,
  },
  player: {
    user_id: "me",
    username: "Player",
    character_name: "Arathorn",
    level: 34,
    class: "Warrior",
    spec: "Berserker",
    hp: 850,
    max_hp: 850,
    resource: 100,
    max_resource: 100,
  },
  rules: {
    bracket: "Level 21–40",
    level_range: "21-40",
    gear_normalized: false,
  },
};

const mockMatch: PvpMatchState = {
  match_id: "match-001",
  status: "active",
  mode: "casual",
  is_your_turn: true,
  turn_timer: 45,
  player: { ...mockStatus.player! },
  opponent: {
    user_id: "opp-1",
    username: "DarkMage99",
    character_name: "Malachar",
    level: 36,
    class: "Mage",
    spec: "Shadow",
    hp: 520,
    max_hp: 680,
    resource: 180,
    max_resource: 250,
  },
  combat_log: [
    { id: "1", timestamp: "12:00:01", message: "Battle begins!", type: "system" },
    { id: "2", timestamp: "12:00:05", message: "Arathorn attacks Malachar for 128 damage.", type: "damage" },
    { id: "3", timestamp: "12:00:08", message: "Malachar casts Shadow Bolt for 95 damage.", type: "damage" },
    { id: "4", timestamp: "12:00:12", message: "Arathorn uses Whirlwind for 160 damage. Critical hit!", type: "damage" },
    { id: "5", timestamp: "12:00:15", message: "Malachar applies Curse of Weakness.", type: "debuff" },
  ],
  skills: [
    { key: "whirlwind", name: "Whirlwind", cooldown: 0, max_cooldown: 3, description: "Deal 160% damage to opponent." },
    { key: "execute", name: "Execute", cooldown: 2, max_cooldown: 5, description: "Massive damage when opponent below 30% HP." },
    { key: "shield_wall", name: "Shield Wall", cooldown: 0, max_cooldown: 4, description: "Reduce incoming damage by 50% for 1 turn." },
    { key: "battle_cry", name: "Battle Cry", cooldown: 1, max_cooldown: 3, description: "Increase crit chance by 25% for 2 turns." },
  ],
};

const mockHistory: PvpHistoryResponse = {
  matches: [
    { match_id: "h1", date: "2025-03-29", opponent_name: "ShadowKnight", result: "victory", mode: "ranked", rating_delta: 15 },
    { match_id: "h2", date: "2025-03-28", opponent_name: "IceMage42", result: "defeat", mode: "ranked", rating_delta: -12 },
    { match_id: "h3", date: "2025-03-28", opponent_name: "BladeDancer", result: "victory", mode: "casual" },
    { match_id: "h4", date: "2025-03-27", opponent_name: "DarkMage99", result: "victory", mode: "ranked", rating_delta: 18 },
    { match_id: "h5", date: "2025-03-26", opponent_name: "HolyPaladin", result: "draw", mode: "casual" },
    { match_id: "h6", date: "2025-03-25", opponent_name: "StormArcher", result: "victory", mode: "ranked", rating_delta: 14 },
  ],
  has_more: true,
  page: 1,
};

// ── Hook ───────────────────────────────────────────────────────────────────

export function usePvpApi() {
  const [status, setStatus] = useState<PvpStatus | null>(null);
  const [match, setMatch] = useState<PvpMatchState | null>(null);
  const [history, setHistory] = useState<PvpHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async () => {
    if (USE_MOCK) {
      setStatus(mockStatus);
      setLoading(false);
      return;
    }
    try {
      const res = await fetch("/api/game/pvp/status");
      if (!res.ok) throw new Error("Could not connect to Arena service");
      setStatus(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  const joinQueue = useCallback(async (mode: PvpMode) => {
    if (USE_MOCK) {
      setStatus((s) => (s ? { ...s, match_status: "queued", mode, queue_time: 0 } : s));
      setTimeout(() => {
        setStatus((s) => (s ? { ...s, match_status: "active" } : s));
        setMatch({ ...mockMatch, mode });
      }, 3000);
      return;
    }
    await fetch("/api/game/pvp/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    setStatus((s) => (s ? { ...s, match_status: "queued", mode } : s));
  }, []);

  const leaveQueue = useCallback(async () => {
    if (USE_MOCK) {
      setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
      return;
    }
    await fetch("/api/game/pvp/queue", { method: "DELETE" });
    setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
  }, []);

  const challenge = useCallback(async (targetUserId: string) => {
    if (USE_MOCK) {
      setStatus((s) =>
        s ? { ...s, match_status: "challenged", challenge_target: targetUserId, challenge_timer: 60 } : s
      );
      setTimeout(() => {
        setStatus((s) => (s ? { ...s, match_status: "active" } : s));
        setMatch({ ...mockMatch });
      }, 3000);
      return;
    }
    await fetch("/api/game/pvp/challenge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_user_id: targetUserId }),
    });
  }, []);

  const cancelChallenge = useCallback(async () => {
    if (USE_MOCK) {
      setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
      return;
    }
    await fetch("/api/game/pvp/queue", { method: "DELETE" });
    setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
  }, []);

  const sendAction = useCallback(async (action: "attack" | "skill" | "defend" | "pass", skillKey?: string) => {
    if (USE_MOCK) {
      const newLog = {
        id: String(Date.now()),
        timestamp: new Date().toLocaleTimeString(),
        message:
          action === "attack"
            ? "Arathorn attacks Malachar for 115 damage."
            : action === "defend"
              ? "Arathorn takes a defensive stance."
              : action === "skill" && skillKey
                ? `Arathorn uses ${skillKey}!`
                : "Arathorn passes.",
        type: "damage" as const,
      };
      setMatch((m) => {
        if (!m) return m;
        const oHp = Math.max(0, m.opponent.hp - (action === "attack" ? 115 : action === "skill" ? 160 : 0));
        const finished = oHp <= 0;
        return {
          ...m,
          status: finished ? "finished" : "active",
          result: finished ? "victory" : undefined,
          is_your_turn: false,
          opponent: { ...m.opponent, hp: oHp },
          combat_log: [...m.combat_log, newLog].slice(-15),
          result_stats: finished
            ? { damage_dealt: 1250, damage_taken: 680, crits: 4, duration_seconds: 127, rating_delta: 15 }
            : undefined,
        };
      });
      setTimeout(() => {
        setMatch((m) => {
          if (!m || m.status === "finished") return m;
          const pHp = Math.max(0, m.player.hp - 85);
          return {
            ...m,
            is_your_turn: true,
            turn_timer: 60,
            player: { ...m.player, hp: pHp },
            combat_log: [
              ...m.combat_log,
              {
                id: String(Date.now()),
                timestamp: new Date().toLocaleTimeString(),
                message: "Malachar casts Shadow Bolt for 85 damage.",
                type: "damage" as const,
              },
            ].slice(-15),
          };
        });
      }, 1500);
      return;
    }
    await fetch("/api/game/pvp/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, skill_key: skillKey }),
    });
  }, []);

  const fetchHistory = useCallback(async (page = 1) => {
    if (USE_MOCK) {
      setHistory(mockHistory);
      return;
    }
    const res = await fetch(`/api/game/pvp/history?page=${page}`);
    setHistory(await res.json());
  }, []);

  const backToHub = useCallback(() => {
    setMatch(null);
    setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
  }, []);

  useEffect(() => {
    void fetchStatus();
    void fetchHistory();
  }, [fetchStatus, fetchHistory]);

  return {
    status,
    match,
    history,
    loading,
    error,
    joinQueue,
    leaveQueue,
    challenge,
    cancelChallenge,
    sendAction,
    fetchHistory,
    backToHub,
  };
}
