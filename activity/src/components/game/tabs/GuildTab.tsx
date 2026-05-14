import { useCallback, useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { CalendarCheck, CalendarDays, Castle, Cpu, Crown, Flag, ShieldHalf, Sword } from "lucide-react";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import * as api from "@/lib/gameApi";
import type { GuildFeedMessage, GuildInviteCandidate, GuildMePayload, GuildTechDefinition } from "@/lib/apiTypes";
import { toast } from "sonner";
import "./guild.css";

function isOfficer(rank?: string | null) {
  return rank === "officer" || rank === "guildmaster";
}

function raidPillClass(status?: string) {
  const k = String(status || "").toLowerCase();
  if (k === "recruiting") return "pill violet";
  if (k === "active") return "pill amber";
  if (k === "completed") return "pill success";
  if (k === "cancelled") return "pill crimson";
  return "pill";
}

function Panel({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <div className={`gpanel ${className}`.trim()} style={style}>
      <span className="corner tl" />
      <span className="corner tr" />
      <span className="corner bl" />
      <span className="corner br" />
      {children}
    </div>
  );
}

function SectionHeader({ kicker, title, right }: { kicker?: string; title: string; right?: ReactNode }) {
  return (
    <div className="section-h">
      <div>
        {kicker ? <div className="kicker">{kicker}</div> : null}
        <h2>{title}</h2>
        <div className="accent-line" />
      </div>
      {right}
    </div>
  );
}

function GoldCoin({ size = 14 }: { size?: number }) {
  const uid = useId().replace(/:/g, "");
  const gid = `coin-grad-${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: "inline-block" }} aria-hidden>
      <defs>
        <radialGradient id={gid} cx="35%" cy="35%">
          <stop offset="0%" stopColor="#fff8e1" />
          <stop offset="50%" stopColor="#d4a94e" />
          <stop offset="100%" stopColor="#5d4720" />
        </radialGradient>
      </defs>
      <circle cx="12" cy="12" r="10" fill={`url(#${gid})`} />
      <circle cx="12" cy="12" r="7" fill="none" stroke="#5d4720" strokeWidth="0.8" />
      <path
        d="M12 7 L13.4 10.2 L17 10.6 L14.3 13.1 L15 16.6 L12 14.9 L9 16.6 L9.7 13.1 L7 10.6 L10.6 10.2 Z"
        fill="#5d4720"
        opacity="0.6"
      />
    </svg>
  );
}

function GuildHallSkeleton() {
  return (
    <div className="guild-root" aria-busy="true" aria-label="Loading guild">
      <div className="guild-container">
        <Panel className="guild-banner">
          <div className="banner-bg" />
          <div className="banner-fade" />
          <div className="guild-banner-row">
            <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
              <div className="guild-skel-block guild-crest" style={{ border: "none" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="guild-skel-block h-3 w-24 mb-2" />
                <div className="guild-skel-block h-8 w-48 max-w-full mb-2" />
                <div className="guild-skel-block h-3 w-40" />
              </div>
            </div>
            <div className="guild-stat-grid" style={{ flex: "1 1 200px", maxWidth: 420 }}>
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="guild-skel-block stat-tile" style={{ minHeight: 72 }} />
              ))}
            </div>
          </div>
        </Panel>
        <div className="grid">
          <Panel className="col-8">
            <div className="guild-skel-block h-6 w-40 mb-4" />
            <div className="guild-skel-block h-24 w-full" />
          </Panel>
          <Panel className="col-4">
            <div className="guild-skel-block h-6 w-32 mb-4" />
            <div className="guild-skel-block h-20 w-full" />
          </Panel>
        </div>
      </div>
    </div>
  );
}

export function GuildTab() {
  const { accessToken, guildId, refreshInventory } = useGameSession();
  const [data, setData] = useState<GuildMePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [depositStr, setDepositStr] = useState("100");
  const [withdrawStr, setWithdrawStr] = useState("100");
  const [chatDraft, setChatDraft] = useState("");
  const [feed, setFeed] = useState<GuildFeedMessage[]>([]);
  const [feedCursor, setFeedCursor] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteQuery, setInviteQuery] = useState("");
  const [inviteResults, setInviteResults] = useState<GuildInviteCandidate[]>([]);
  const [inviteSearchLoading, setInviteSearchLoading] = useState(false);
  const [inviteSendingId, setInviteSendingId] = useState<string | null>(null);
  const [createName, setCreateName] = useState("");
  const [createTag, setCreateTag] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [checkinBusy, setCheckinBusy] = useState(false);
  /** Avoid full skeleton on every refetch after boss/bank actions (only first paint / not-in-guild). */
  const hasLoadedGuildHubRef = useRef(false);

  useEffect(() => {
    hasLoadedGuildHubRef.current = false;
  }, [guildId]);

  const loadMe = useCallback(async () => {
    if (!accessToken) return;
    const showFullSpinner = !hasLoadedGuildHubRef.current;
    if (showFullSpinner) setLoading(true);
    try {
      const j = await api.getGuildMe(accessToken, guildId);
      if (j.in_guild && j.ok) {
        hasLoadedGuildHubRef.current = true;
      } else {
        hasLoadedGuildHubRef.current = false;
      }
      setData(j);
      if (j.in_guild && j.ok) {
        try {
          const f = await api.getGuildFeed(accessToken, guildId);
          if (f.ok && Array.isArray(f.messages)) {
            setFeed(f.messages as GuildFeedMessage[]);
            setFeedCursor(f.next_cursor ?? null);
          } else {
            setFeed([]);
            setFeedCursor(null);
          }
        } catch (feedErr) {
          console.warn("guild feed load failed", feedErr);
          setFeed([]);
          setFeedCursor(null);
          toast.message("Hall chat could not load — the rest of the guild hub is still available.", { duration: 4500 });
        }
      } else {
        setFeed([]);
        setFeedCursor(null);
      }
    } catch (e) {
      toast.error(api.describeFetchError(e, api.apiUrl("/api/game/guild/me")));
      setData((prev) => prev);
    } finally {
      setLoading(false);
    }
  }, [accessToken, guildId]);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  useEffect(() => {
    if (!inviteOpen || !accessToken) return;
    const q = inviteQuery.trim();
    if (!q) {
      setInviteResults([]);
      setInviteSearchLoading(false);
      return;
    }
    setInviteSearchLoading(true);
    const ac = new AbortController();
    const t = window.setTimeout(() => {
      void api
        .getGuildInviteCandidates(accessToken, q, guildId, ac.signal)
        .then((r) => {
          if (ac.signal.aborted) return;
          if (r.error === "forbidden") {
            setInviteResults([]);
            toast.error("Only officers can search for recruits.");
          } else {
            setInviteResults(r.players ?? []);
          }
        })
        .catch((e) => {
          if (ac.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
          toast.error(api.describeFetchError(e, api.apiUrl("/api/game/guild/invite/candidates")));
          setInviteResults([]);
        })
        .finally(() => {
          if (!ac.signal.aborted) setInviteSearchLoading(false);
        });
    }, 280);
    return () => {
      ac.abort();
      window.clearTimeout(t);
    };
  }, [inviteOpen, inviteQuery, accessToken, guildId]);

  const sendGuildInvite = async (characterId: string) => {
    if (!accessToken) return;
    setInviteSendingId(characterId);
    try {
      const r = await api.postGuildInviteSend(accessToken, characterId, guildId);
      if (!r.ok) {
        toast.error(r.message || "Invite failed");
        return;
      }
      toast.success(r.message || "Invite sent");
      setInviteOpen(false);
      setInviteQuery("");
      setInviteResults([]);
    } catch (e) {
      toast.error(api.describeFetchError(e, api.apiUrl("/api/game/guild/invite/send")));
    } finally {
      setInviteSendingId(null);
    }
  };

  const loadMoreFeed = async () => {
    if (!accessToken || !feedCursor) return;
    const f = await api.getGuildFeed(accessToken, guildId, feedCursor);
    if (f.ok && Array.isArray(f.messages) && f.messages.length) {
      setFeed((prev) => [...prev, ...(f.messages as GuildFeedMessage[])]);
      setFeedCursor(f.next_cursor ?? null);
    }
  };

  const onDeposit = async () => {
    if (!accessToken) return;
    const amount = Math.max(0, Math.floor(Number(depositStr) || 0));
    const r = await api.postGuildBankDeposit(accessToken, amount, guildId);
    if (!r.ok) {
      toast.error(r.message || "Deposit failed");
      return;
    }
    toast.success(`Donated ${amount.toLocaleString()} gold`);
    await refreshInventory();
    await loadMe();
  };

  const onWithdraw = async () => {
    if (!accessToken) return;
    const amount = Math.max(0, Math.floor(Number(withdrawStr) || 0));
    const r = await api.postGuildBankWithdraw(accessToken, amount, guildId);
    if (!r.ok) {
      toast.error(r.message || "Withdraw failed");
      return;
    }
    toast.success(`Withdrew ${amount.toLocaleString()} gold`);
    await refreshInventory();
    await loadMe();
  };

  const onSendChat = async () => {
    if (!accessToken || !chatDraft.trim()) return;
    const r = await api.postGuildFeed(accessToken, chatDraft.trim(), guildId);
    if (!r.ok) {
      toast.error(r.message || "Could not send");
      return;
    }
    setChatDraft("");
    const f = await api.getGuildFeed(accessToken, guildId);
    if (f.ok && Array.isArray(f.messages)) setFeed(f.messages as GuildFeedMessage[]);
  };

  const onSummonBoss = async () => {
    if (!accessToken) return;
    const r = await api.postGuildBossStart(accessToken, "stone_siege_golem", guildId);
    if (!r.ok) {
      toast.error(r.message || "Could not start boss");
      return;
    }
    toast.success("Guild boss summoned");
    await loadMe();
  };

  const onHitBoss = async () => {
    if (!accessToken) return;
    const encId =
      data?.boss?.encounter && typeof data.boss.encounter === "object" && "id" in data.boss.encounter
        ? String((data.boss.encounter as { id?: string }).id)
        : undefined;
    const r = await api.postGuildBossHit(accessToken, encId, guildId);
    if (!r.ok) {
      toast.error(r.message || "Hit failed");
      return;
    }
    toast.message(r.message || "Strike!");
    await loadMe();
  };

  const onUnlockTech = async (nodeId: string) => {
    if (!accessToken) return;
    const r = await api.postGuildTechUnlock(accessToken, nodeId, guildId);
    if (!r.ok) {
      toast.error(r.message || "Unlock failed");
      return;
    }
    toast.success("Tech unlocked");
    await loadMe();
  };

  const onCreateRaid = async () => {
    if (!accessToken) return;
    const r = await api.postGuildRaidCreate(accessToken, "gnoll_warren_raid", guildId);
    if (!r.ok) {
      toast.error(r.message || "Could not create raid");
      return;
    }
    toast.success("Raid scheduled — members can sign up");
    await loadMe();
  };

  const onSignupRaid = async (runId: string) => {
    if (!accessToken) return;
    const r = await api.postGuildRaidSignup(accessToken, runId, guildId);
    if (!r.ok) toast.error(r.message || "Signup failed");
    else {
      toast.success("Signed up");
      await loadMe();
    }
  };

  const onStartRaid = async (runId: string) => {
    if (!accessToken) return;
    const r = await api.postGuildRaidStart(accessToken, runId, guildId);
    if (!r.ok) toast.error(r.message || "Start failed");
    else {
      toast.success("Raid underway");
      await loadMe();
    }
  };

  const onCompleteRaid = async (runId: string) => {
    if (!accessToken) return;
    const r = await api.postGuildRaidComplete(accessToken, runId, guildId);
    if (!r.ok) toast.error(r.message || "Complete failed");
    else {
      toast.success("Raid completed — rewards sent");
      await refreshInventory();
      await loadMe();
    }
  };

  if (!accessToken) {
    return (
      <div className="guild-root">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Sign in to manage your guild.
        </p>
      </div>
    );
  }

  if (loading) {
    return <GuildHallSkeleton />;
  }

  if (!data?.in_guild) {
    const canSubmit =
      Boolean(guildId) &&
      createName.trim().length >= 3 &&
      createName.trim().length <= 64 &&
      createTag.length >= 2 &&
      createTag.length <= 8 &&
      !createBusy;

    const onFoundHall = async () => {
      if (!accessToken || !guildId || !canSubmit) return;
      setCreateBusy(true);
      try {
        const r = await api.postGuildCreate(accessToken, { name: createName.trim(), tag: createTag }, guildId);
        if (!r.ok) {
          toast.error(r.message || r.error || "Could not create guild.");
          return;
        }
        toast.success(r.message || "Guild founded!");
        setCreateName("");
        setCreateTag("");
        await loadMe();
      } catch (e) {
        toast.error(api.describeFetchError(e, api.apiUrl("/api/game/guild/create")));
      } finally {
        setCreateBusy(false);
      }
    };

    return (
      <div className="guild-root">
        <div className="guild-container">
          <div className="grid">
            {!guildId ? (
              <Panel className="col-12">
                <div className="kicker" style={{ color: "var(--crimson-400)" }}>
                  Realm link
                </div>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "8px 0 0", lineHeight: 1.55 }}>
                  Discord did not send a server id for this session. Open the Activity from a channel inside your server,
                  then return here to found a hall.
                </p>
              </Panel>
            ) : null}

            <Panel className="col-7">
              <SectionHeader
                kicker="For guildmasters"
                title="Found a hall"
                right={<Flag size={18} color="var(--gold-400)" strokeWidth={1.5} aria-hidden />}
              />
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 0, marginBottom: 20, lineHeight: 1.55 }}>
                Register a new guild for <span style={{ color: "var(--gold-200)" }}>this Discord server</span>. You become
                guildmaster; the name and tag must be unique across the realm.
              </p>

              <div className="divider" style={{ marginTop: 0 }} />

              <div style={{ marginBottom: 16 }}>
                <div className="text-label" style={{ marginBottom: 8 }}>
                  Guild name
                </div>
                <input
                  type="text"
                  className="gold-input"
                  value={createName}
                  maxLength={64}
                  placeholder="e.g. Obsidian Vanguard"
                  autoComplete="off"
                  disabled={createBusy || !guildId}
                  onChange={(e) => setCreateName(e.target.value)}
                  aria-label="Guild name"
                />
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>3–64 characters.</p>
              </div>

              <div style={{ marginBottom: 20 }}>
                <div className="text-label" style={{ marginBottom: 8 }}>
                  Guild tag
                </div>
                <input
                  type="text"
                  className="gold-input font-mono"
                  style={{ letterSpacing: "0.12em" }}
                  value={createTag}
                  maxLength={8}
                  placeholder="e.g. OV"
                  disabled={createBusy || !guildId}
                  onChange={(e) => setCreateTag(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8))}
                  aria-label="Guild tag"
                />
                <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>2–8 letters or numbers (stored uppercase).</p>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                <button type="button" className="btn-gold" disabled={!canSubmit} onClick={() => void onFoundHall()}>
                  <Castle size={15} strokeWidth={2} /> Raise banner
                </button>
                <button type="button" className="btn-ghost" disabled={createBusy} onClick={() => void loadMe()}>
                  Refresh
                </button>
              </div>
            </Panel>

            <Panel className="col-5">
              <SectionHeader kicker="Recruitment desk" title="Discord commands" />
              <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55, marginTop: 0 }}>
                Prefer typing in chat? Same rules apply:
              </p>
              <ul
                style={{
                  textAlign: "left",
                  fontSize: 12,
                  marginTop: 14,
                  padding: 12,
                  border: "1px solid var(--border-default)",
                  background: "var(--bg-panel-raised)",
                  listStyle: "disc",
                  paddingLeft: 26,
                  color: "var(--text-primary)",
                  lineHeight: 1.6,
                }}
              >
                <li style={{ marginBottom: 8 }}>
                  <span style={{ color: "var(--gold-400)" }}>/guild create</span> — same as this form
                </li>
                <li style={{ marginBottom: 8 }}>
                  <span style={{ color: "var(--gold-400)" }}>/guild join</span> — enlist by guild name
                </li>
                <li>Recruit members with invites once your hall stands.</li>
              </ul>
            </Panel>
          </div>
        </div>
      </div>
    );
  }

  const g = data.guild;
  const rank = g?.my_rank;
  const officer = isOfficer(rank);
  const enc = data.boss?.encounter as
    | {
        id?: string;
        hp_remaining?: number;
        hp_max?: number;
        status?: string;
        closes_at?: string;
      }
    | undefined;
  const bossActive = Boolean(enc && enc.status === "active");
  const tpl = (data.boss?.template as { name?: string; hp_max?: number }) || {};
  const lb = (data.boss?.leaderboard as { name: string; total_damage: number }[]) || [];
  const techDefs = data.tech?.definitions || [];
  const unlocked = new Set(data.tech?.unlocked || []);
  const recentRaids = (data.raids?.recent || []) as Array<{
    id: string;
    template_key?: string;
    status?: string;
    leader_name?: string;
  }>;

  const hpPct = Math.max(3, (100 * Number(enc?.hp_remaining ?? 0)) / Math.max(1, Number(enc?.hp_max ?? 1)));
  let closesLabel = "";
  if (enc?.closes_at) {
    try {
      closesLabel = new Date(enc.closes_at).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      closesLabel = String(enc.closes_at);
    }
  }

  const motd = g?.motd?.trim();
  const mottoText = motd || "No motto of the day — officers can set one in Discord.";
  const ci = data.checkin;

  const onCheckin = async () => {
    if (!accessToken || checkinBusy) return;
    setCheckinBusy(true);
    try {
      const r = await api.postGuildCheckin(accessToken, guildId);
      if (r.ok) toast.success(r.message || "Checked in!");
      else toast.message(r.message || "Check-in", { duration: 5000 });
      await refreshInventory();
      await loadMe();
    } catch (e) {
      toast.error(api.describeFetchError(e, api.apiUrl("/api/game/guild/checkin")));
    } finally {
      setCheckinBusy(false);
    }
  };

  return (
    <div className="guild-root">
      <div className="guild-container">
        <Dialog
          open={inviteOpen}
          onOpenChange={(open) => {
            setInviteOpen(open);
            if (!open) {
              setInviteQuery("");
              setInviteResults([]);
              setInviteSearchLoading(false);
            }
          }}
        >
          <DialogContent className="max-w-[min(calc(100vw-2rem),22rem)] sm:max-w-sm gap-3 p-4">
            <DialogHeader className="space-y-1">
              <DialogTitle className="text-base font-cinzel tracking-wide">Invite to guild</DialogTitle>
              <DialogDescription className="text-xs leading-relaxed">
                Type the start of a character name. Pick a player to send them a Discord DM with Accept / Decline.
              </DialogDescription>
            </DialogHeader>
            <Input
              value={inviteQuery}
              onChange={(e) => setInviteQuery(e.target.value)}
              placeholder="Character name…"
              className="h-9 font-serif"
              autoComplete="off"
              autoFocus
            />
            <div
              className="max-h-52 overflow-y-auto rounded-sm border border-border/50 bg-muted/15"
              role="listbox"
              aria-label="Matching characters"
            >
              {inviteSearchLoading ? (
                <p className="text-xs text-muted-foreground p-3 font-serif">Searching…</p>
              ) : inviteQuery.trim().length === 0 ? (
                <p className="text-xs text-muted-foreground p-3 font-serif">Type a letter to search.</p>
              ) : inviteResults.length === 0 ? (
                <p className="text-xs text-muted-foreground p-3 font-serif">No guildless characters match.</p>
              ) : (
                <ul className="divide-y divide-border/40">
                  {inviteResults.map((row) => (
                    <li key={row.character_id} className="p-2">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">{row.name}</p>
                          <p className="text-[11px] text-muted-foreground tabular-nums">
                            Lv {row.level} {row.class}
                            {row.username ? <span className="ml-1 opacity-80">· @{row.username}</span> : null}
                          </p>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          className="h-8 shrink-0 text-[11px] font-cinzel"
                          disabled={inviteSendingId !== null}
                          onClick={() => void sendGuildInvite(row.character_id)}
                        >
                          {inviteSendingId === row.character_id ? "…" : "Invite"}
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </DialogContent>
        </Dialog>

        <Panel className="guild-banner">
          <div className="banner-bg" />
          <div className="banner-fade" />
          <div className="guild-banner-row">
            <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
              <div className="guild-crest">
                <Castle size={36} color="var(--gold-200)" strokeWidth={1.25} />
                <span className="badge">
                  <Crown size={10} color="var(--gold-200)" strokeWidth={2} />
                </span>
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="text-label">Guild Hall</div>
                <h1 className="guild-name">
                  <span style={{ color: "var(--gold-400)" }}>[{g?.tag || "—"}]</span> {g?.name || "Guild"}
                </h1>
                <div
                  style={{
                    fontSize: 11,
                    letterSpacing: "0.28em",
                    textTransform: "uppercase",
                    color: "var(--text-muted)",
                    marginTop: 8,
                  }}
                >
                  Your rank:{" "}
                  <span style={{ color: "var(--gold-200)", fontFamily: "Cinzel, serif", textTransform: "capitalize" }}>
                    {rank || "member"}
                  </span>
                </div>
                <p className="guild-motto" style={motd ? { color: "var(--text-secondary)", fontStyle: "normal" } : undefined}>
                  {mottoText}
                </p>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "stretch" }}>
              <div className="guild-stat-grid">
                <div className="stat-tile">
                  <div className="lbl">Guild Lv</div>
                  <div className="val">{g?.guild_level ?? 1}</div>
                </div>
                <div className="stat-tile">
                  <div className="lbl">Members</div>
                  <div className="val">
                    {g?.member_count ?? 0}/{g?.max_members ?? 20}
                  </div>
                </div>
                <div className="stat-tile">
                  <div className="lbl">Treasury</div>
                  <div className="val">
                    {(g?.bank_gold ?? 0).toLocaleString()}
                    <GoldCoin size={14} />
                  </div>
                </div>
                <div className="stat-tile">
                  <div className="lbl">Guild XP</div>
                  <div className="val">{(g?.guild_xp ?? 0).toLocaleString()}</div>
                </div>
              </div>
              {officer ? (
                <button type="button" className="btn-ghost" style={{ width: "100%" }} onClick={() => setInviteOpen(true)}>
                  Add member
                </button>
              ) : null}
            </div>
          </div>
        </Panel>

        {ci ? (
          <Panel>
            <SectionHeader
              kicker="Daily attendance (UTC)"
              title="Hall check-in"
              right={
                ci.checked_today ? (
                  <span className="pill success">Signed today</span>
                ) : (
                  <CalendarCheck size={18} color="var(--gold-400)" strokeWidth={1.5} aria-hidden />
                )
              }
            />
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 16,
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0, lineHeight: 1.55 }}>
                  Streak <span className="font-mono" style={{ color: "var(--gold-200)" }}>{ci.streak}</span> day(s)
                  {" · "}
                  <span style={{ color: "var(--text-secondary)" }}>
                    {ci.checked_in_guild_today}/{g?.max_members ?? 20} members today
                  </span>
                </p>
                <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8, marginBottom: 0 }}>
                  Rewards: <span className="font-mono">{ci.rewards.gold}</span> gold,{" "}
                  <span className="font-mono">{ci.rewards.xp}</span> XP,{" "}
                  <span className="font-mono">{ci.rewards.guild_xp}</span> guild XP — UTC day{" "}
                  <span className="font-mono">{ci.utc_day}</span>.
                </p>
              </div>
              <button
                type="button"
                className="btn-gold"
                disabled={Boolean(ci.checked_today) || checkinBusy}
                onClick={() => void onCheckin()}
                style={{ flexShrink: 0 }}
              >
                {ci.checked_today ? "Done for today" : checkinBusy ? "…" : "Check in"}
              </button>
            </div>
          </Panel>
        ) : null}

        <div className="grid">
          <Panel className="col-8">
            <SectionHeader
              kicker="World boss assault"
              title="War Council"
              right={bossActive ? <span className="pill crimson">Active</span> : null}
            />

            {bossActive ? (
              <>
                <div className="boss-row">
                  <div className="boss-icon">
                    <ShieldHalf size={26} color="var(--crimson-400)" strokeWidth={1.5} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="font-display" style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }}>
                      {tpl.name || "Boss"}
                    </div>
                    <div className="font-mono" style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                      {(enc?.hp_remaining ?? 0).toLocaleString()} / {(enc?.hp_max ?? 0).toLocaleString()} HP
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: 12 }}>
                  <div className="bar-track" role="progressbar" aria-valuenow={Math.round(hpPct)} aria-valuemin={0} aria-valuemax={100}>
                    <div className="bar-fill" style={{ width: `${hpPct}%` }} />
                  </div>
                </div>

                {closesLabel ? (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      marginTop: 12,
                      fontSize: 11,
                      letterSpacing: "0.24em",
                      textTransform: "uppercase",
                      color: "var(--text-muted)",
                    }}
                  >
                    <CalendarDays size={11} strokeWidth={2} />
                    Seal breaks: <span style={{ color: "var(--gold-200)", letterSpacing: "0.06em" }}>{closesLabel}</span>
                  </div>
                ) : null}

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    alignItems: "start",
                    gap: 16,
                    marginTop: 20,
                  }}
                >
                  <div>
                    <div className="text-label" style={{ marginBottom: 6 }}>
                      Top Damage
                    </div>
                    {lb.length === 0 ? (
                      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>No strikes logged yet.</p>
                    ) : (
                      lb.slice(0, 8).map((row, i) => (
                        <div key={`${row.name}-${i}`} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 4 }}>
                          <span style={{ fontFamily: "Cinzel, serif", color: "var(--gold-400)" }}>{i + 1}.</span>
                          <span style={{ color: "var(--text-primary)" }}>{row.name}</span>
                          <span style={{ color: "var(--text-muted)" }}>—</span>
                          <span className="font-mono" style={{ color: "var(--gold-200)" }}>
                            {Number(row.total_damage).toLocaleString()}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                  <button type="button" className="btn-crimson self-center" onClick={() => void onHitBoss()}>
                    <Sword size={13} strokeWidth={2.5} /> Strike
                  </button>
                </div>

                <div className="divider" />
                {officer ? (
                  <button type="button" className="btn-ghost" disabled={bossActive} onClick={() => void onSummonBoss()}>
                    Summon Stone Siege Golem
                  </button>
                ) : null}
              </>
            ) : (
              <>
                <p style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.55, margin: 0 }}>
                  No active siege target. Officers can summon a shared boss for the whole guild — everyone contributes damage for rewards.
                </p>
                {officer ? (
                  <button type="button" className="btn-ghost" style={{ marginTop: 16 }} onClick={() => void onSummonBoss()}>
                    Summon Stone Siege Golem
                  </button>
                ) : null}
              </>
            )}
          </Panel>

          <Panel className="col-4">
            <SectionHeader kicker="Guild bank" title="Treasury" />
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 0, marginBottom: 16, lineHeight: 1.5 }}>
              Donations fund tech and campaigns. Officers may withdraw (per-guild daily cap on the server).
            </p>

            <div style={{ marginBottom: 16 }}>
              <div className="text-label" style={{ marginBottom: 6 }}>
                Donate Gold
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <input
                  type="number"
                  className="gold-input"
                  style={{ flex: "1 1 120px" }}
                  value={depositStr}
                  min={1}
                  onChange={(e) => setDepositStr(e.target.value)}
                  aria-label="Donate gold amount"
                />
                <button type="button" className="btn-gold shrink-0" onClick={() => void onDeposit()}>
                  Donate
                </button>
              </div>
            </div>

            {officer ? (
              <div>
                <div className="text-label" style={{ marginBottom: 6 }}>
                  Withdraw
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <input
                    type="number"
                    className="gold-input"
                    style={{ flex: "1 1 120px" }}
                    value={withdrawStr}
                    min={1}
                    onChange={(e) => setWithdrawStr(e.target.value)}
                    aria-label="Withdraw gold amount"
                  />
                  <button type="button" className="btn-ghost shrink-0" onClick={() => void onWithdraw()}>
                    Withdraw
                  </button>
                </div>
              </div>
            ) : null}
          </Panel>

          <Panel className="col-7">
            <SectionHeader
              kicker="Passive bonuses for all members (explore, combat, idle)"
              title="Guild Tech"
              right={<Cpu size={16} color="var(--gold-400)" strokeWidth={1.5} aria-hidden />}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: "min(48vh, 420px)", overflowY: "auto", paddingRight: 4 }}>
              {techDefs.map((node: GuildTechDefinition) => {
                const has = unlocked.has(node.id);
                const missingReq = (node.requires || []).filter((rid) => !unlocked.has(rid));
                const blocked = !has && missingReq.length > 0;
                const canBuy = officer && !has && !blocked;
                return (
                  <div
                    key={node.id}
                    className={`tech-card${has ? " tech-card--unlocked" : ""}${blocked ? " tech-card--locked" : ""}`}
                  >
                    <div className="tech-icon">
                      <Cpu size={16} color="var(--gold-400)" strokeWidth={1.5} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="font-display" style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                        {node.name}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2, lineHeight: 1.4 }}>{node.description}</div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }} className="font-mono">
                        Cost: {node.cost_guild_xp.toLocaleString()} guild XP
                        {node.cost_bank_gold ? ` + ${node.cost_bank_gold.toLocaleString()} bank gold` : ""}
                      </div>
                      {blocked ? (
                        <p style={{ fontSize: 10, color: "var(--gold-200)", marginTop: 6, marginBottom: 0 }}>
                          Requires: {missingReq.join(", ") || "prerequisites"}
                        </p>
                      ) : null}
                      {!has && !blocked && !officer ? (
                        <p style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6, marginBottom: 0 }}>Officers may unlock this node.</p>
                      ) : null}
                      {canBuy ? (
                        <button type="button" className="btn-ghost" style={{ marginTop: 8 }} onClick={() => void onUnlockTech(node.id)}>
                          Research
                        </button>
                      ) : null}
                    </div>
                    {has ? <span className="pill success shrink-0">Unlocked</span> : null}
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel className="col-5">
            <SectionHeader
              kicker="Recent runs — sign up when recruiting is open"
              title="Raids"
              right={
                officer ? (
                  <button type="button" className="btn-ghost" onClick={() => void onCreateRaid()}>
                    Schedule sortie
                  </button>
                ) : null
              }
            />
            {recentRaids.length === 0 ? (
              <div className="empty-card">
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>No raids logged yet.</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", fontStyle: "italic", marginTop: 8 }}>
                  Cull a world boss together to add the first entry.
                </div>
              </div>
            ) : (
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                {recentRaids.map((run) => (
                  <li
                    key={run.id}
                    style={{
                      padding: 10,
                      border: "1px solid var(--border-default)",
                      background: "var(--bg-panel-raised)",
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: 13 }}>{run.template_key}</div>
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                        Leader <span style={{ color: "var(--text-primary)" }}>{run.leader_name || "?"}</span>
                      </div>
                      <span className={`${raidPillClass(run.status)}`} style={{ marginTop: 8, display: "inline-block" }}>
                        {run.status || "?"}
                      </span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, flexShrink: 0 }}>
                      {run.status === "recruiting" ? (
                        <button type="button" className="btn-ghost" style={{ padding: "6px 12px", fontSize: 10 }} onClick={() => void onSignupRaid(run.id)}>
                          Sign up
                        </button>
                      ) : null}
                      {officer && run.status === "recruiting" ? (
                        <button type="button" className="btn-gold" style={{ padding: "6px 14px", fontSize: 10 }} onClick={() => void onStartRaid(run.id)}>
                          Start
                        </button>
                      ) : null}
                      {officer && run.status === "active" ? (
                        <button type="button" className="btn-gold" style={{ padding: "6px 14px", fontSize: 10 }} onClick={() => void onCompleteRaid(run.id)}>
                          Complete
                        </button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel className="col-12" style={{ display: "flex", flexDirection: "column", minHeight: "min(52vh, 440px)", maxHeight: "min(60vh, 560px)" }}>
            <SectionHeader kicker="Guild channel" title="Hall Chat" />
            <div className="guild-feed-scroll">
              {feed.length === 0 ? (
                <p style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", margin: 0 }}>No messages yet — greet your guild.</p>
              ) : null}
              {feed.map((m) => (
                <div
                  key={m.id}
                  className={`guild-feed-msg${m.message_type?.startsWith("system") ? " guild-feed-msg--system" : ""}`}
                >
                  <div className="text-label" style={{ marginBottom: 4, letterSpacing: "0.12em" }}>
                    {m.author_name || (m.message_type?.startsWith("system") ? "Herald" : "Unknown")}{" "}
                    <span style={{ color: "var(--text-muted)", fontWeight: 400, textTransform: "none", letterSpacing: "0.02em" }}>
                      · {m.created_at ? new Date(m.created_at).toLocaleString() : ""}
                    </span>
                  </div>
                  <div style={{ fontSize: 14, color: "var(--text-primary)", whiteSpace: "pre-wrap", lineHeight: 1.45 }}>{m.body}</div>
                </div>
              ))}
              {feedCursor ? (
                <button type="button" className="btn-ghost" style={{ width: "100%" }} onClick={() => void loadMoreFeed()}>
                  Older messages
                </button>
              ) : null}
            </div>
            <div className="guild-chat-composer">
              <input
                value={chatDraft}
                onChange={(e) => setChatDraft(e.target.value)}
                placeholder="Message the hall…"
                className="gold-input"
                style={{ flex: 1 }}
                maxLength={400}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void onSendChat();
                }}
                aria-label="Guild chat message"
              />
              <button type="button" className="btn-gold" style={{ padding: "10px 16px" }} onClick={() => void onSendChat()}>
                Send
              </button>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
