import { useCallback, useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { LeaderboardPayload } from "@/lib/apiTypes";

/**
 * This week's scoreboard.
 *
 * The game had no way to compare yourself to anyone — the only leaderboards
 * were per-encounter (damage inside one guild boss fight, strikes inside one
 * raid run), none of which answer "how am I doing relative to other people
 * playing this game".
 *
 * Weekly, not all-time: an all-time board is decided within a month and then
 * never changes, so everyone who did not start first is looking at a wall.
 */

function fmt(n: number, unit?: string): string {
  const v = Math.max(0, Math.round(n));
  if (unit === "g") return `${v.toLocaleString()}g`;
  if (unit === "xp") return `${v.toLocaleString()} xp`;
  return v.toLocaleString();
}

function untilReset(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (!Number.isFinite(ms) || ms <= 0) return "resetting";
  const days = Math.floor(ms / 86_400_000);
  if (days >= 1) return `${days}d left`;
  const hours = Math.floor(ms / 3_600_000);
  return hours >= 1 ? `${hours}h left` : "under an hour";
}

export function Leaderboard() {
  const { accessToken, guildId } = useGameSession();
  const [metric, setMetric] = useState("kills");
  const [data, setData] = useState<LeaderboardPayload | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      setData(await api.getLeaderboard(accessToken, metric, guildId));
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId, metric]);

  useEffect(() => {
    void load();
  }, [load]);

  const you = data?.you ?? null;
  const onBoard = data?.entries?.some((e) => e.is_you) ?? false;

  return (
    <section className="e-card p-4">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <span className="e-label">This week</span>
        {data?.resets_at ? (
          <span className="e-num text-[10.5px]" style={{ color: "var(--a-500)" }}>
            {untilReset(data.resets_at)}
          </span>
        ) : null}
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {(data?.metrics ?? [{ key: "kills", label: "Kills" }]).map((m) => {
          const on = m.key === metric;
          return (
            <button
              key={m.key}
              type="button"
              onClick={() => setMetric(m.key)}
              aria-pressed={on}
              className="rounded-lg px-2 py-1 text-[11px] font-semibold"
              style={{
                border: `1px solid ${on ? "var(--e-500)" : "var(--n-500)"}`,
                background: on ? "rgba(255,122,47,0.12)" : "rgba(0,0,0,0.28)",
                color: on ? "var(--e-400)" : "var(--a-500)",
              }}
            >
              {m.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <p className="py-6 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
          Counting…
        </p>
      ) : !data || !data.entries.length ? (
        <p className="py-6 text-center text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          Nobody's on the board yet this week. Win a fight and you'll be first.
        </p>
      ) : (
        <ol className="space-y-1">
          {data.entries.map((e) => (
            <li
              key={e.character_id ?? e.rank}
              className="flex items-baseline gap-2 rounded-lg px-2 py-1.5"
              style={{
                background: e.is_you ? "rgba(255,122,47,0.12)" : "rgba(0,0,0,0.24)",
                border: `1px solid ${e.is_you ? "rgba(255,122,47,0.4)" : "transparent"}`,
              }}
            >
              <span
                className="e-num w-6 shrink-0 text-[11px] font-bold"
                style={{ color: e.rank <= 3 ? "var(--g-400)" : "var(--a-700)" }}
              >
                {e.rank}
              </span>
              <span
                className="min-w-0 flex-1 truncate text-[12.5px]"
                style={{ color: e.is_you ? "var(--e-300)" : "var(--a-100)" }}
              >
                {e.guild_tag ? (
                  <span style={{ color: "var(--a-700)" }}>[{e.guild_tag}] </span>
                ) : null}
                {e.name}
                {e.prestige ? <span style={{ color: "var(--g-400)" }}> ★{e.prestige}</span> : null}
              </span>
              <span className="e-num shrink-0 text-[11.5px]" style={{ color: "var(--a-300)" }}>
                {fmt(e.score, data.unit)}
              </span>
            </li>
          ))}
        </ol>
      )}

      {/* Your own standing, when you're below the cut. A board that only shows
          the top 25 tells almost everyone nothing about themselves. */}
      {!loading && data && you && !onBoard ? (
        <div
          className="mt-2 flex items-baseline gap-2 rounded-lg px-2 py-1.5"
          style={{ background: "rgba(255,122,47,0.1)", border: "1px solid rgba(255,122,47,0.35)" }}
        >
          <span className="e-num w-6 shrink-0 text-[11px] font-bold" style={{ color: "var(--a-700)" }}>
            {you.rank ?? "—"}
          </span>
          <span className="min-w-0 flex-1 text-[12.5px]" style={{ color: "var(--e-300)" }}>
            You
          </span>
          <span className="e-num shrink-0 text-[11.5px]" style={{ color: "var(--a-300)" }}>
            {you.score > 0 ? fmt(you.score, data.unit) : "nothing yet"}
          </span>
        </div>
      ) : null}
    </section>
  );
}
