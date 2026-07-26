import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import * as api from "@/lib/gameApi";
import type {
  MilestonesPayload,
  ReputationPayload,
  SocialFriendRow,
  SocialRosterPayload,
} from "@/lib/apiTypes";
import { cn } from "@/lib/utils";
import { TalentsPanel } from "@mobile/ui/parts/TalentsPanel";
import { LinkAccountSheet } from "@mobile/ui/parts/LinkAccountSheet";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";
import type { StoredSession } from "@mobile/platform/sessionStore";

/**
 * Realm, in Ember — all seven classic sub-tabs.
 *
 * Classic stacks these as a segmented row inside an already-tabbed shell. Same
 * grouping here (players know it), but each section is rebuilt for a phone:
 * vertical, one idea per card, and nothing that needs horizontal scrolling.
 */

type Seg = "social" | "world" | "talents" | "records" | "story" | "goals" | "roadmap";

const SEGS: { id: Seg; label: string }[] = [
  { id: "social", label: "Friends" },
  { id: "world", label: "World" },
  { id: "talents", label: "Talents" },
  { id: "records", label: "Records" },
  { id: "story", label: "Story" },
  { id: "goals", label: "Goals" },
  { id: "roadmap", label: "Ahead" },
];

const GOALS_KEY = "emberlone.goals";

/* ── Friends ─────────────────────────────────────────────────────────────── */

function FriendRow({ f }: { f: SocialFriendRow }) {
  const online = f.online || f.presence_status === "online";
  const busy = f.presence_status === "in-combat" || f.presence_status === "in-dungeon";
  return (
    <li className="flex items-center gap-3 rounded-xl p-2.5" style={{ background: "rgba(0,0,0,0.26)" }}>
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ background: busy ? "var(--e-500)" : online ? "var(--vital)" : "var(--n-400)" }}
        aria-label={busy ? "busy" : online ? "online" : "offline"}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px]" style={{ color: "var(--a-100)" }}>
          {f.character_name || f.username}
        </span>
        <span className="block truncate text-[10.5px]" style={{ color: "var(--a-700)" }}>
          {f.level ? `Level ${f.level}` : ""}
          {f.class ? ` ${String(f.class).replace(/_/g, " ")}` : ""}
          {busy ? " · in a fight" : online ? " · online" : ""}
        </span>
      </span>
      {Number(f.unread_count ?? 0) > 0 ? (
        <span className="e-pill e-pill--ember e-num shrink-0">{f.unread_count}</span>
      ) : null}
    </li>
  );
}

function SocialSection() {
  const { accessToken, guildId } = useGameSession();
  const [roster, setRoster] = useState<SocialRosterPayload | null>(null);
  const [requests, setRequests] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    const [r, q] = await Promise.allSettled([
      api.getSocialRoster(accessToken, guildId),
      api.getSocialRequests(accessToken, guildId),
    ]);
    setRoster(r.status === "fulfilled" ? r.value : null);
    setRequests(q.status === "fulfilled" ? (q.value as Record<string, unknown>) : null);
    setLoading(false);
  }, [accessToken, guildId]);

  useEffect(() => {
    void load();
  }, [load]);

  const incoming = (requests?.incoming as Array<Record<string, unknown>> | undefined) ?? [];
  const friends = roster?.friends ?? [];
  const online = friends.filter((f) => f.online || f.presence_status === "online");
  const offline = friends.filter((f) => !(f.online || f.presence_status === "online"));

  async function respond(id: string, accept: boolean) {
    if (!accessToken) return;
    setBusy(id);
    try {
      const fn = accept ? api.postSocialFriendAccept : api.postSocialFriendDecline;
      await fn(accessToken, id, guildId);
      toast.success(accept ? "Friend added." : "Declined.");
      await load();
    } catch (e) {
      toast.error(String(e));
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <p className="py-10 text-center text-[12px]" style={{ color: "var(--a-500)" }}>
        Looking for your people…
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {incoming.length > 0 ? (
        <div className="e-card e-card--ready p-4">
          <div className="e-label mb-2">Friend requests</div>
          <ul className="space-y-2">
            {incoming.map((r, i) => {
              const id = String(r.id ?? r.request_id ?? i);
              return (
                <li key={id} className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-[13px]" style={{ color: "var(--a-100)" }}>
                    {String(r.username ?? r.from_username ?? "Someone")}
                  </span>
                  <button
                    type="button"
                    disabled={busy === id}
                    onClick={() => void respond(id, true)}
                    className="e-pill e-pill--ember shrink-0"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    disabled={busy === id}
                    onClick={() => void respond(id, false)}
                    className="e-pill e-pill--quiet shrink-0"
                  >
                    No
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <div className="e-card p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <span className="e-label">Friends</span>
          <span className="e-num text-[10.5px]" style={{ color: "var(--a-500)" }}>
            {online.length} of {friends.length} online
          </span>
        </div>
        {friends.length === 0 ? (
          <p className="text-[12px] leading-relaxed" style={{ color: "var(--a-500)" }}>
            Nobody yet. Adding friends by username isn’t on mobile yet — you can do it in Discord.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {[...online, ...offline].map((f) => (
              <FriendRow key={f.user_id} f={f} />
            ))}
          </ul>
        )}
      </div>

      <p className="px-1 text-center text-[10.5px] leading-relaxed" style={{ color: "var(--a-700)" }}>
        Whispers, adding friends and the block list aren’t on mobile yet — they’re in Discord.
      </p>
    </div>
  );
}

/* ── World ───────────────────────────────────────────────────────────────── */

function WorldSection() {
  const { accessToken, guildId, map } = useGameSession();
  const [ms, setMs] = useState<MilestonesPayload | null>(null);
  const [rep, setRep] = useState<ReputationPayload | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void Promise.allSettled([
      api.getMilestones(accessToken, guildId),
      api.getReputation(accessToken, guildId),
    ]).then(([m, r]) => {
      if (cancelled) return;
      setMs(m.status === "fulfilled" ? m.value : null);
      setRep(r.status === "fulfilled" ? r.value : null);
    });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId]);

  const zones = map?.zones ?? [];
  const windows = map?.world_boss_windows ?? [];
  const mult = ms?.multipliers ?? null;
  const factions = (rep?.factions ?? []).filter((f) => Number(f.reputation ?? 0) > 0);

  return (
    <div className="space-y-3">
      {mult && (Number(mult.xp_bonus_pct ?? 0) > 0 || Number(mult.gold_bonus_pct ?? 0) > 0) ? (
        <div className="e-card e-card--warm p-4">
          <div className="e-label mb-2">Realm bonuses</div>
          <div className="mb-2 flex gap-2">
            {Number(mult.xp_bonus_pct ?? 0) > 0 ? (
              <span className="e-pill e-pill--ember e-num">+{mult.xp_bonus_pct}% XP</span>
            ) : null}
            {Number(mult.gold_bonus_pct ?? 0) > 0 ? (
              <span className="e-pill e-pill--gold e-num">+{mult.gold_bonus_pct}% gold</span>
            ) : null}
          </div>
          <p className="text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
            Earned by the whole server together — these apply to everyone.
          </p>
        </div>
      ) : null}

      {windows.length > 0 ? (
        <div className="e-card p-4" style={{ borderColor: "rgba(226,73,95,0.4)" }}>
          <div className="e-label mb-2">World bosses up</div>
          <ul className="space-y-1.5">
            {windows.map((w, i) => (
              <li key={`${w.zone_key}-${i}`} className="text-[12.5px]" style={{ color: "var(--a-100)" }}>
                {w.title || w.boss_key}
                <span style={{ color: "var(--a-700)" }}> — {String(w.zone_key).replace(/_/g, " ")}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="e-card p-4">
        <div className="e-label mb-3">Zones</div>
        <ul className="space-y-2">
          {zones.map((z) => (
            <li key={z.key} className="flex items-center gap-2.5">
              <span aria-hidden>{z.emoji || "🗺"}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12.5px]" style={{ color: "var(--a-100)" }}>
                  {z.name}
                  {z.is_current ? <span style={{ color: "var(--e-400)" }}> · you're here</span> : null}
                </span>
                <span className="block text-[10.5px]" style={{ color: "var(--a-700)" }}>
                  level {z.level_min}–{z.level_max}
                  {z.faction ? ` · ${z.faction}` : ""}
                </span>
              </span>
              {z.boss_alive ? (
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: "var(--wound)" }} />
              ) : null}
            </li>
          ))}
        </ul>
      </div>

      {factions.length > 0 ? (
        <div className="e-card p-4">
          <div className="e-label mb-3">Reputation</div>
          <ul className="space-y-2">
            {factions.map((f) => (
              <li key={f.faction_id}>
                <div className="flex items-baseline gap-2.5">
                  <span aria-hidden>{f.emoji || "◆"}</span>
                  <span className="min-w-0 flex-1 truncate text-[12.5px]" style={{ color: "var(--a-100)" }}>
                    {f.name}
                  </span>
                  <span className="shrink-0 text-[11px]" style={{ color: "var(--a-500)" }}>
                    {f.level?.name || ""}
                  </span>
                  <span className="e-num shrink-0 text-[11px]" style={{ color: "var(--a-300)" }}>
                    {Number(f.reputation ?? 0).toLocaleString()}
                  </span>
                </div>
                {/* What the standing actually buys. The perk text has always
                    been in the payload; it was never rendered, so reputation
                    read as a bar that filled up and did nothing. */}
                {f.level?.perks ? (
                  <p className="mt-0.5 pl-6 text-[10.5px] leading-snug" style={{ color: "var(--e-400)" }}>
                    {f.level.perks}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/* ── Records ─────────────────────────────────────────────────────────────── */

function RecordsSection() {
  const { progress } = useGameSession();
  const achievements = progress?.achievements ?? [];
  const history = progress?.history ?? [];
  const stats = progress?.stats ?? null;
  const points = useMemo(
    () => achievements.reduce((a, x) => a + Number(x.points ?? 0), 0),
    [achievements],
  );

  return (
    <div className="space-y-3">
      {stats ? (
        <div className="e-card e-card--warm p-4">
          <div className="e-label mb-3">Combat record</div>
          <div className="grid grid-cols-4 gap-3">
            <div>
              <div className="e-num text-lg font-bold" style={{ color: "var(--vital)" }}>
                {Number(stats.wins ?? 0)}
              </div>
              <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                won
              </div>
            </div>
            <div>
              <div className="e-num text-lg font-bold" style={{ color: "var(--wound)" }}>
                {Number(stats.losses ?? 0)}
              </div>
              <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                lost
              </div>
            </div>
            <div>
              <div className="e-num text-lg font-bold" style={{ color: "var(--a-100)" }}>
                {Number(stats.fled ?? 0)}
              </div>
              <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                fled
              </div>
            </div>
            <div>
              <div className="e-num text-lg font-bold" style={{ color: "var(--a-100)" }}>
                {Math.round(Number(stats.win_rate ?? 0))}%
              </div>
              <div className="text-[10.5px]" style={{ color: "var(--a-500)" }}>
                win rate
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="e-card p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <span className="e-label">Achievements</span>
          <span className="e-num text-[11px]" style={{ color: "var(--g-400)" }}>
            {points.toLocaleString()} points
          </span>
        </div>
        {achievements.length === 0 ? (
          <p className="text-[12px]" style={{ color: "var(--a-500)" }}>
            None yet.
          </p>
        ) : (
          <ul className="space-y-2">
            {achievements.map((a, i) => (
              <li key={a.id ?? i} className="flex items-baseline gap-2.5">
                <span aria-hidden>{a.icon || "◆"}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px]" style={{ color: "var(--a-100)" }}>
                    {a.name}
                  </span>
                  {a.description ? (
                    <span className="block truncate text-[10.5px]" style={{ color: "var(--a-700)" }}>
                      {a.description}
                    </span>
                  ) : null}
                </span>
                {a.points ? (
                  <span className="e-num shrink-0 text-[10.5px]" style={{ color: "var(--g-400)" }}>
                    +{a.points}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {history.length > 0 ? (
        <div className="e-card p-4">
          <div className="e-label mb-3">History</div>
          <ul className="space-y-1.5">
            {history.slice(0, 20).map((h, i) => (
              <li key={i} className="flex items-baseline gap-2 text-[11.5px]">
                <span className="min-w-0 flex-1 truncate" style={{ color: "var(--a-300)" }}>
                  {String(h.type ?? h.outcome ?? "event").replace(/_/g, " ")}
                  {h.zone ? ` · ${String(h.zone).replace(/_/g, " ")}` : ""}
                </span>
                {h.amount ? (
                  <span
                    className="e-num shrink-0"
                    style={{ color: Number(h.amount) > 0 ? "var(--g-400)" : "var(--a-700)" }}
                  >
                    {Number(h.amount) > 0 ? "+" : ""}
                    {Number(h.amount).toLocaleString()}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/* ── Story ───────────────────────────────────────────────────────────────── */

function StorySection() {
  const { deedFlags } = useGameSession();
  return (
    <div className="e-card p-4">
      <div className="e-label mb-2">Deeds</div>
      <p className="mb-3 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
        Marks of what you've done. Some doors in the story won't open without them.
      </p>
      {deedFlags.length === 0 ? (
        <p className="text-[12px]" style={{ color: "var(--a-700)" }}>
          Nothing recorded yet.
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {deedFlags.map((d) => (
            <span key={d} className="e-pill e-pill--quiet">
              {d.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Goals ───────────────────────────────────────────────────────────────── */

type Goal = { id: string; text: string; done: boolean };

function GoalsSection() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem(GOALS_KEY);
      if (raw) setGoals(JSON.parse(raw) as Goal[]);
    } catch {
      /* ignore */
    }
  }, []);

  const save = useCallback((next: Goal[]) => {
    setGoals(next);
    try {
      localStorage.setItem(GOALS_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <div className="space-y-3">
      <div className="e-card p-4">
        <div className="e-label mb-2">Your own list</div>
        {/* Said plainly, because the classic version doesn't make this obvious
            and losing a list you thought was saved is a bad surprise. */}
        <p className="mb-3 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
          Kept on this phone only — not on the server, and not shared with your other devices.
        </p>

        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft.trim()) {
                save([...goals, { id: String(Date.now()), text: draft.trim(), done: false }]);
                setDraft("");
              }
            }}
            placeholder="Something you're working toward"
            className="min-w-0 flex-1 rounded-xl px-3 py-2.5 text-[14px]"
            style={{ background: "rgba(0,0,0,0.4)", border: "1px solid var(--n-500)", color: "var(--a-100)" }}
          />
          <button
            type="button"
            disabled={!draft.trim()}
            onClick={() => {
              save([...goals, { id: String(Date.now()), text: draft.trim(), done: false }]);
              setDraft("");
            }}
            className="e-btn e-btn--primary shrink-0 px-4 py-2"
          >
            Add
          </button>
        </div>
      </div>

      {goals.length > 0 ? (
        <div className="e-card p-4">
          <ul className="space-y-2">
            {goals.map((g) => (
              <li key={g.id} className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => save(goals.map((x) => (x.id === g.id ? { ...x, done: !x.done } : x)))}
                  className="grid h-5 w-5 shrink-0 place-items-center rounded-md"
                  style={{
                    border: `1px solid ${g.done ? "var(--e-500)" : "var(--n-400)"}`,
                    background: g.done ? "rgba(255,122,47,0.18)" : "transparent",
                    color: "var(--e-400)",
                  }}
                  aria-label={g.done ? "Mark as not done" : "Mark as done"}
                >
                  {g.done ? "✓" : ""}
                </button>
                <span
                  className="min-w-0 flex-1 text-[13px]"
                  style={{
                    color: g.done ? "var(--a-700)" : "var(--a-100)",
                    textDecoration: g.done ? "line-through" : "none",
                  }}
                >
                  {g.text}
                </span>
                <button
                  type="button"
                  onClick={() => save(goals.filter((x) => x.id !== g.id))}
                  className="shrink-0 text-[11px]"
                  style={{ color: "var(--a-700)" }}
                  aria-label="Remove"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/* ── Ahead ───────────────────────────────────────────────────────────────── */

const AHEAD = [
  "Territory war between guilds",
  "Looking-for-group finder",
  "Mythic+ style scaling dungeons",
  "Gear loadouts you can swap",
  "Transmog — keep the stats, change the look",
  "Player housing",
  "Mounts and pets",
];

function AheadSection() {
  return (
    <div className="e-card p-4">
      <div className="e-label mb-2">What's ahead</div>
      <p className="mb-3 text-[11.5px] leading-relaxed" style={{ color: "var(--a-500)" }}>
        Not built yet — this is where the game is going, not what it does today.
      </p>
      <ul className="space-y-2">
        {AHEAD.map((x) => (
          <li key={x} className="flex items-baseline gap-2.5 text-[12.5px]" style={{ color: "var(--a-300)" }}>
            <span style={{ color: "var(--a-700)" }}>◦</span>
            <span>{x}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ── Shell ───────────────────────────────────────────────────────────────── */

export function RealmScreen({
  discordAuth,
  onSessionReplaced,
}: {
  discordAuth?: DiscordOAuthAuth;
  onSessionReplaced?: (s: StoredSession) => void;
}) {
  const [seg, setSeg] = useState<Seg>("social");
  const [linkOpen, setLinkOpen] = useState(false);

  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-center gap-2 px-4">
        <span className="e-label flex-1">Realm</span>
        {discordAuth ? (
          <button type="button" onClick={() => setLinkOpen(true)} className="e-pill e-pill--quiet">
            Link Discord
          </button>
        ) : null}
      </div>

      <div className="e-scroll-x mb-3 flex gap-1.5 px-4 pb-0.5">
        {SEGS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSeg(s.id)}
            className={cn("e-pill shrink-0", seg === s.id ? "e-pill--ember" : "e-pill--quiet")}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="px-4">
        {seg === "social" && <SocialSection />}
        {seg === "world" && <WorldSection />}
        {seg === "talents" && <TalentsPanel />}
        {seg === "records" && <RecordsSection />}
        {seg === "story" && <StorySection />}
        {seg === "goals" && <GoalsSection />}
        {seg === "roadmap" && <AheadSection />}
      </div>

      {linkOpen ? (
        <LinkAccountSheet
          discordAuth={discordAuth}
          onClose={() => setLinkOpen(false)}
          onSessionReplaced={(s) => {
            setLinkOpen(false);
            onSessionReplaced?.(s);
          }}
        />
      ) : null}
    </div>
  );
}
