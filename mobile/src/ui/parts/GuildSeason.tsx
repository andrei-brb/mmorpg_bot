import { useCallback, useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type { GuildSeasonPayload } from "@/lib/apiTypes";

/**
 * Guild versus guild, this month.
 *
 * Guilds had no opponent — you could fund research and claim quests, but nothing
 * a guild did was ever measured against another guild.
 *
 * The number is derived from what members actually did, so `contributors` is
 * shown next to it: a guild's rank is a claim about its people, and a big roster
 * with three active members should not read the same as a small one where
 * everybody fights.
 */

function endsIn(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (!Number.isFinite(ms) || ms <= 0) return "ending";
  const days = Math.floor(ms / 86_400_000);
  if (days >= 1) return `${days}d left`;
  return `${Math.max(1, Math.floor(ms / 3_600_000))}h left`;
}

export function GuildSeason() {
  const { accessToken, guildId } = useGameSession();
  const [metric, setMetric] = useState("kills");
  const [data, setData] = useState<GuildSeasonPayload | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      setData(await api.getGuildSeason(accessToken, metric, guildId));
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId, metric]);

  useEffect(() => {
    void load();
  }, [load]);

  const yours = data?.yours ?? null;
  const listed = data?.entries?.some((e) => e.is_yours) ?? false;

  return (
    <section className="e-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="e-label">Season {data?.season ?? ""}</span>
        {data?.ends_at ? (
          <span className="e-num text-[10.5px]" style={{ color: "var(--a-500)" }}>
            {endsIn(data.ends_at)}
          </span>
        ) : null}
      </div>

      {data?.last_champion?.name ? (
        <p className="mb-2 text-[11.5px]" style={{ color: "var(--g-400)" }}>
          🏆 {data.last_champion.season} — {data.last_champion.tag ? `[${data.last_champion.tag}] ` : ""}
          {data.last_champion.name}
        </p>
      ) : null}

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
          No guild has scored yet this season.
        </p>
      ) : (
        <ol className="space-y-1">
          {data.entries.map((e) => (
            <li
              key={e.guild_id ?? e.rank}
              className="flex items-baseline gap-2 rounded-lg px-2 py-1.5"
              style={{
                background: e.is_yours ? "rgba(255,122,47,0.12)" : "rgba(0,0,0,0.24)",
                border: `1px solid ${e.is_yours ? "rgba(255,122,47,0.4)" : "transparent"}`,
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
                style={{ color: e.is_yours ? "var(--e-300)" : "var(--a-100)" }}
              >
                {e.tag ? <span style={{ color: "var(--a-700)" }}>[{e.tag}] </span> : null}
                {e.name}
              </span>
              <span className="e-num shrink-0 text-[10px]" style={{ color: "var(--a-700)" }}>
                {e.contributors}👤
              </span>
              <span className="e-num shrink-0 text-[11.5px]" style={{ color: "var(--a-300)" }}>
                {Number(e.score ?? 0).toLocaleString()}
              </span>
            </li>
          ))}
        </ol>
      )}

      {!loading && data && yours && !listed ? (
        <div
          className="mt-2 flex items-baseline gap-2 rounded-lg px-2 py-1.5"
          style={{ background: "rgba(255,122,47,0.1)", border: "1px solid rgba(255,122,47,0.35)" }}
        >
          <span className="e-num w-6 shrink-0 text-[11px] font-bold" style={{ color: "var(--a-700)" }}>
            {yours.rank ?? "—"}
          </span>
          <span className="min-w-0 flex-1 text-[12.5px]" style={{ color: "var(--e-300)" }}>
            Your guild
          </span>
          <span className="e-num shrink-0 text-[11.5px]" style={{ color: "var(--a-300)" }}>
            {yours.score > 0 ? Number(yours.score).toLocaleString() : "nothing yet"}
          </span>
        </div>
      ) : null}
    </section>
  );
}
