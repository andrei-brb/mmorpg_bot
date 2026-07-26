import { useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";

/**
 * What your guild has been doing, on Camp.
 *
 * The guild feed already existed — `guild_feed.fetch_feed`, backed by
 * `guild_feed_messages`, carrying both chat and system events (check-ins,
 * research, raids). It was only visible if you deliberately opened the Guild
 * tab and scrolled, which meant a guild felt empty unless you went looking for
 * proof that it wasn't.
 *
 * Camp is the screen people actually open. Three lines here is the difference
 * between "I am in a guild" and "other people are playing this with me".
 *
 * Deliberately read-only and short. Posting belongs in the guild hall; this is
 * a window, not a second chat client.
 */

type FeedRow = {
  id?: string;
  body?: string;
  message_type?: string;
  author_name?: string | null;
  created_at?: string;
};

const SHOWN = 3;

function ago(iso?: string): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "";
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function GuildActivity({ onOpenGuild }: { onOpenGuild?: () => void }) {
  const { accessToken, guildId, inventory } = useGameSession();
  const [rows, setRows] = useState<FeedRow[] | null>(null);

  const inGuild = Boolean(inventory?.character?.guild_name);

  useEffect(() => {
    if (!accessToken || !inGuild) return;
    let cancelled = false;
    void (async () => {
      try {
        const j = await api.getGuildFeed(accessToken, guildId);
        if (!cancelled) setRows(((j?.messages ?? []) as FeedRow[]).slice(0, SHOWN));
      } catch {
        if (!cancelled) setRows([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, inGuild]);

  // Nothing to say yet, or not in a guild: render nothing rather than an empty
  // card. Camp is the busiest screen in the game and does not need a placeholder.
  if (!inGuild || !rows || rows.length === 0) return null;

  return (
    <section className="e-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="e-label">
          {inventory?.character?.guild_tag ? `[${inventory.character.guild_tag}] ` : ""}
          Hall
        </span>
        {onOpenGuild ? (
          <button
            type="button"
            onClick={onOpenGuild}
            className="text-[11px] font-semibold"
            style={{ color: "var(--e-400)" }}
          >
            Open →
          </button>
        ) : null}
      </div>
      <ul className="space-y-1.5">
        {rows.map((m, i) => (
          <li key={m.id ?? i} className="flex items-baseline gap-2">
            <span
              className="min-w-0 flex-1 truncate text-[12px]"
              style={{ color: m.message_type === "chat" ? "var(--a-100)" : "var(--a-300)" }}
            >
              {m.message_type === "chat" && m.author_name ? (
                <span style={{ color: "var(--e-300)" }}>{m.author_name}: </span>
              ) : null}
              {m.body}
            </span>
            <span className="e-num shrink-0 text-[10px]" style={{ color: "var(--a-700)" }}>
              {ago(m.created_at)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
