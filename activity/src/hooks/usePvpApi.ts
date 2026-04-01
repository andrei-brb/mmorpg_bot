import { useState, useEffect, useCallback, useRef } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { apiUrl, authHeaders } from "@/lib/gameApi";
import type {
  PvpStatus,
  PvpMatchState,
  PvpHistoryResponse,
  PvpMode,
} from "@/lib/pvpTypes";

export type PvpPlayerSearchRow = { id: string; username: string };

const USE_MOCK = import.meta.env.VITE_USE_PVP_MOCK === "true";

const mockStatus: PvpStatus = {
  match_status: "idle",
  stats: {
    rating: 1547,
    rank_tier: "Gold",
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
    username: "",
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
  ],
  skills: [
    {
      key: "whirlwind",
      name: "Whirlwind",
      cooldown: 0,
      max_cooldown: 3,
      description: "Spin attack.",
    },
  ],
};

const mockHistory: PvpHistoryResponse = {
  matches: [
    {
      match_id: "h1",
      date: "2026-03-29",
      opponent_name: "ShadowKnight",
      result: "victory",
      mode: "ranked",
      rating_delta: 15,
    },
  ],
  has_more: false,
  page: 1,
};


export function usePvpApi() {
  const { accessToken, guildId, phase } = useGameSession();
  const [status, setStatus] = useState<PvpStatus | null>(null);
  const [match, setMatch] = useState<PvpMatchState | null>(null);
  const [history, setHistory] = useState<PvpHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const finishedRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    if (USE_MOCK) {
      setStatus(mockStatus);
      setLoading(false);
      return;
    }
    if (!accessToken) {
      setLoading(phase === "boot" || phase === "loading");
      return;
    }
    try {
      const res = await fetch(apiUrl("/api/game/pvp/status"), {
        headers: authHeaders(accessToken, guildId),
      });
      if (!res.ok) throw new Error(`Arena status ${res.status}`);
      const data = (await res.json()) as PvpStatus;
      if (data.error === "no_character") {
        setError("Create a character with /character create in Discord first.");
        setStatus(null);
        return;
      }
      setError(null);
      setStatus(data);
      if (data.match) {
        setMatch(data.match as PvpMatchState);
      } else if (data.match_status !== "active") {
        setMatch((prev) => (prev?.status === "finished" ? prev : null));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId, phase]);

  const fetchHistory = useCallback(
    async (page = 1) => {
      if (USE_MOCK) {
        setHistory(mockHistory);
        return;
      }
      if (!accessToken) return;
      const res = await fetch(apiUrl(`/api/game/pvp/history?page=${page}`), {
        headers: authHeaders(accessToken, guildId),
      });
      if (!res.ok) return;
      setHistory((await res.json()) as PvpHistoryResponse);
    },
    [accessToken, guildId],
  );

  const joinQueue = useCallback(
    async (mode: PvpMode) => {
      if (USE_MOCK) {
        setStatus((s) => (s ? { ...s, match_status: "queued", mode, queue_time: 0 } : s));
        setTimeout(() => {
          setStatus((s) => (s ? { ...s, match_status: "active" } : s));
          setMatch({ ...mockMatch, mode });
        }, 3000);
        return;
      }
      if (!accessToken) return;
      const res = await fetch(apiUrl("/api/game/pvp/queue"), {
        method: "POST",
        headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      await res.json();
      finishedRef.current = false;
      await fetchStatus();
    },
    [accessToken, guildId, fetchStatus],
  );

  const leaveQueue = useCallback(async () => {
    if (USE_MOCK) {
      setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
      return;
    }
    if (!accessToken) return;
    await fetch(apiUrl("/api/game/pvp/queue"), {
      method: "DELETE",
      headers: authHeaders(accessToken, guildId),
    });
    finishedRef.current = false;
    await fetchStatus();
  }, [accessToken, guildId, fetchStatus]);

  const challenge = useCallback(
    async (targetUserId: string) => {
      if (USE_MOCK) {
        setStatus((s) =>
          s ? { ...s, match_status: "challenged", challenge_target: targetUserId, challenge_timer: 60 } : s,
        );
        setTimeout(() => {
          setStatus((s) => (s ? { ...s, match_status: "active" } : s));
          setMatch({ ...mockMatch });
        }, 3000);
        return;
      }
      if (!accessToken) return;
      await fetch(apiUrl("/api/game/pvp/challenge"), {
        method: "POST",
        headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
        body: JSON.stringify({ target_user_id: targetUserId }),
      });
      await fetchStatus();
    },
    [accessToken, guildId, fetchStatus],
  );

  const acceptChallenge = useCallback(async () => {
    if (USE_MOCK) return;
    if (!accessToken) return;
    const res = await fetch(apiUrl("/api/game/pvp/accept"), {
      method: "POST",
      headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      finishedRef.current = false;
      await fetchStatus();
    }
  }, [accessToken, guildId, fetchStatus]);

  const cancelChallenge = useCallback(async () => {
    if (USE_MOCK) {
      setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
      return;
    }
    await leaveQueue();
  }, [leaveQueue]);

  const searchPlayers = useCallback(
    async (q: string): Promise<PvpPlayerSearchRow[]> => {
      if (USE_MOCK) return [];
      if (!accessToken) return [];
      const qs = new URLSearchParams({ q });
      const res = await fetch(apiUrl(`/api/game/pvp/players?${qs.toString()}`), {
        method: "GET",
        headers: authHeaders(accessToken, guildId),
      });
      if (!res.ok) return [];
      const j = await res.json();
      const rows = (j?.players ?? []) as any[];
      return rows
        .map((r) => ({ id: String(r.id ?? ""), username: String(r.username ?? "") }))
        .filter((r) => r.id && r.username);
    },
    [accessToken, guildId],
  );

  const sendAction = useCallback(
    async (action: "attack" | "skill" | "defend" | "pass", skillKey?: string) => {
      if (USE_MOCK) {
        const newLog = {
          id: String(Date.now()),
          timestamp: new Date().toLocaleTimeString(),
          message:
            action === "attack"
              ? "You attack for damage."
              : action === "defend"
                ? "You take a defensive stance."
                : action === "skill" && skillKey
                  ? `You use ${skillKey}!`
                  : "You pass.",
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
              ? {
                  damage_dealt: 1250,
                  damage_taken: 680,
                  crits: 4,
                  duration_seconds: 127,
                  rating_delta: 15,
                }
              : undefined,
          };
        });
        setTimeout(() => {
          setMatch((m) => {
            if (!m || m.status === "finished") return m;
            return {
              ...m,
              is_your_turn: true,
              turn_timer: 60,
              combat_log: [
                ...m.combat_log,
                {
                  id: String(Date.now()),
                  timestamp: new Date().toLocaleTimeString(),
                  message: "Opponent hits you.",
                  type: "damage" as const,
                },
              ].slice(-15),
            };
          });
        }, 1500);
        return;
      }
      if (!accessToken) return;
      const res = await fetch(apiUrl("/api/game/pvp/action"), {
        method: "POST",
        headers: { ...authHeaders(accessToken, guildId), "Content-Type": "application/json" },
        body: JSON.stringify({ action, skill_key: skillKey }),
      });
      const json = (await res.json()) as { match?: PvpMatchState; error?: string; ended?: boolean };
      if (json.match) {
        finishedRef.current = json.match.status === "finished";
        setMatch(json.match);
      }
      if (!res.ok && json.error) {
        // Prefer server-provided human message if available, otherwise use error key
        // Server may include `message`, `required`, and `current` for not_enough_resource
        setError((json as any).message || json.error);
      }
    },
    [accessToken, guildId],
  );

  const backToHub = useCallback(() => {
    finishedRef.current = false;
    setMatch(null);
    setStatus((s) => (s ? { ...s, match_status: "idle" } : s));
    void fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (USE_MOCK) {
      void fetchStatus();
      void fetchHistory();
      return;
    }
    if (phase === "ready" && accessToken) {
      void fetchStatus();
      void fetchHistory(1);
    }
  }, [phase, accessToken, fetchStatus, fetchHistory]);

  useEffect(() => {
    if (USE_MOCK || !accessToken) return;
    const poll = () => {
      const q = status?.match_status === "queued" || status?.match_status === "challenged";
      const act = status?.match_status === "active" || match?.status === "active";
      if (q || act) void fetchStatus();
    };
    const id = window.setInterval(poll, 2000);
    return () => window.clearInterval(id);
  }, [USE_MOCK, accessToken, status?.match_status, match?.status, fetchStatus]);

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
    acceptChallenge,
    searchPlayers,
    sendAction,
    fetchHistory,
    backToHub,
  };
}
