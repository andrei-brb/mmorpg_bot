import { useCallback, useEffect, useState } from "react";
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
import { WomPanel } from "@/components/wom/WomUi";

function isOfficer(rank?: string | null) {
  return rank === "officer" || rank === "guildmaster";
}

const RAID_STATUS_BADGE: Record<string, string> = {
  recruiting: "bg-violet-500/20 text-violet-200 border border-violet-500/35",
  active: "bg-amber-500/20 text-amber-200 border border-amber-500/35",
  completed: "bg-emerald-500/15 text-emerald-200/90 border border-emerald-500/30",
  cancelled: "bg-muted/80 text-muted-foreground border border-border/60",
};

function raidStatusClass(status?: string) {
  const k = String(status || "").toLowerCase();
  return RAID_STATUS_BADGE[k] || "bg-muted/50 text-muted-foreground border border-border/50";
}

function GuildHallSkeleton() {
  return (
    <div className="guild-hall flex flex-col gap-4 min-h-0 flex-1 overflow-y-auto pr-1" aria-busy="true" aria-label="Loading guild">
      <WomPanel bracket={false} glow={false} className="relative overflow-hidden">
        <div className="h-5 w-40 rounded-sm bg-muted/50 animate-pulse mb-4" />
        <div className="h-8 w-3/4 max-w-md rounded-sm bg-muted/40 animate-pulse" />
        <div className="h-4 w-full max-w-lg rounded-sm bg-muted/30 animate-pulse mt-3" />
        <div className="flex flex-wrap gap-2 mt-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="guild-hall-stat-chip h-14 w-24 animate-pulse bg-muted/30 border-transparent" />
          ))}
        </div>
      </WomPanel>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <WomPanel bracket={false} glow={false} className="lg:col-span-7 min-h-[180px] animate-pulse bg-muted/20">
          {null}
        </WomPanel>
        <WomPanel bracket={false} glow={false} className="lg:col-span-5 min-h-[180px] animate-pulse bg-muted/20">
          {null}
        </WomPanel>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WomPanel bracket={false} glow={false} className="min-h-[120px] animate-pulse bg-muted/20">
          {null}
        </WomPanel>
        <WomPanel bracket={false} glow={false} className="min-h-[120px] animate-pulse bg-muted/20">
          {null}
        </WomPanel>
      </div>
      <WomPanel bracket={false} glow={false} className="min-h-[200px] animate-pulse bg-muted/20">
        {null}
      </WomPanel>
    </div>
  );
}

type GuildBannerProps = {
  tag?: string;
  name?: string;
  motd?: string | null;
  rank?: string | null;
  guildLevel?: number;
  memberCount?: number;
  maxMembers?: number;
  bankGold?: number;
  guildXp?: number;
  canInvite?: boolean;
  onAddMember?: () => void;
};

function GuildBanner({
  tag,
  name,
  motd,
  rank,
  guildLevel,
  memberCount,
  maxMembers,
  bankGold,
  guildXp,
  canInvite,
  onAddMember,
}: GuildBannerProps) {
  return (
    <WomPanel glow className="guild-hall-banner relative overflow-hidden">
      <div className="game-panel-header">Guild hall</div>
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 relative z-[1]">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-2xl sm:text-3xl leading-none select-none" aria-hidden>
              🏰
            </span>
            <h1 className="font-cinzel text-xl sm:text-2xl text-primary tracking-tight">
              <span className="text-primary/90">[{tag}]</span> {name}
            </h1>
          </div>
          <p className="text-xs text-muted-foreground mt-2 font-cinzel uppercase tracking-wider">
            Your rank: <span className="text-foreground normal-case tracking-normal capitalize">{rank || "member"}</span>
          </p>
          {motd?.trim() ? (
            <p className="text-sm text-foreground/85 mt-3 leading-relaxed border-l-2 border-primary/40 pl-3 italic font-serif">
              {motd}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground/80 mt-2 italic">No motto of the day — officers can set one in Discord.</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end lg:max-w-[min(100%,22rem)]">
          <div className="flex flex-col gap-1.5 min-w-[6.5rem]">
            <div className="guild-hall-stat-chip">
              <span className="guild-hall-stat-chip__label">Guild level</span>
              <span className="guild-hall-stat-chip__value text-primary">{guildLevel ?? 1}</span>
            </div>
            {canInvite && onAddMember ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 text-[11px] font-cinzel shrink-0 border-primary/35 w-full"
                onClick={onAddMember}
              >
                Add member
              </Button>
            ) : null}
          </div>
          <div className="guild-hall-stat-chip">
            <span className="guild-hall-stat-chip__label">Members</span>
            <span className="guild-hall-stat-chip__value tabular-nums">
              {memberCount ?? 0}/{maxMembers ?? 20}
            </span>
          </div>
          <div className="guild-hall-stat-chip guild-hall-stat-chip--gold">
            <span className="guild-hall-stat-chip__label">Treasury</span>
            <span className="guild-hall-stat-chip__value tabular-nums text-amber-200/95">{(bankGold ?? 0).toLocaleString()}</span>
          </div>
          <div className="guild-hall-stat-chip">
            <span className="guild-hall-stat-chip__label">Guild XP</span>
            <span className="guild-hall-stat-chip__value tabular-nums">{(guildXp ?? 0).toLocaleString()}</span>
          </div>
        </div>
      </div>
    </WomPanel>
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

  const loadMe = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const j = await api.getGuildMe(accessToken, guildId);
      setData(j);
      if (j.in_guild && j.ok) {
        const f = await api.getGuildFeed(accessToken, guildId);
        if (f.ok && Array.isArray(f.messages)) {
          setFeed(f.messages as GuildFeedMessage[]);
          setFeedCursor(f.next_cursor ?? null);
        }
      } else {
        setFeed([]);
        setFeedCursor(null);
      }
    } catch (e) {
      toast.error(api.describeFetchError(e, api.apiUrl("/api/game/guild/me")));
      setData({ ok: false });
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
    return <p className="text-muted-foreground text-sm p-4 font-serif">Sign in to manage your guild.</p>;
  }

  if (loading) {
    return <GuildHallSkeleton />;
  }

  if (!data?.in_guild) {
    return (
      <div className="guild-hall max-w-lg mx-auto">
        <WomPanel glow className="text-center">
          <div className="game-panel-header justify-center">No guild yet</div>
          <div className="text-4xl my-3" aria-hidden>
            🏰
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed font-serif px-1">
            Join the war effort with your Discord server:
          </p>
          <ul className="text-left text-xs text-foreground/90 mt-4 space-y-2 mx-auto max-w-sm font-mono border border-border/40 rounded-sm p-3 bg-muted/20">
            <li>
              <span className="text-primary">/guild create</span> — found a guild (guildmaster)
            </li>
            <li>
              <span className="text-primary">/guild join</span> — enlist by guild name
            </li>
            <li>Return here for treasury, boss, tech, raids, and hall chat.</li>
          </ul>
          <Button variant="secondary" size="sm" className="mt-5 font-cinzel" onClick={() => void loadMe()}>
            Refresh
          </Button>
        </WomPanel>
      </div>
    );
  }

  const g = data.guild;
  const rank = g?.my_rank;
  const officer = isOfficer(rank);
  const enc = data.boss?.encounter as {
    id?: string;
    hp_remaining?: number;
    hp_max?: number;
    status?: string;
    closes_at?: string;
  } | undefined;
  const bossActive = enc && enc.status === "active";
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

  return (
    <div className="guild-hall flex flex-col gap-4 min-h-0 flex-1 overflow-y-auto pr-1 pb-2">
      <GuildBanner
        tag={g?.tag}
        name={g?.name}
        motd={g?.motd}
        rank={rank}
        guildLevel={g?.guild_level}
        memberCount={g?.member_count}
        maxMembers={g?.max_members}
        bankGold={g?.bank_gold}
        guildXp={g?.guild_xp}
        canInvite={officer}
        onAddMember={() => setInviteOpen(true)}
      />

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

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <WomPanel glow className="lg:col-span-7 flex flex-col min-h-0">
          <div className="game-panel-header">War council</div>
          {bossActive ? (
            <>
              <div className="flex items-start gap-3">
                <span className="text-4xl shrink-0 opacity-90" title="Boss" aria-hidden>
                  🗿
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-foreground font-cinzel tracking-wide">{tpl.name || "Boss"}</p>
                  <p className="text-[11px] text-muted-foreground mt-1 tabular-nums">
                    {(enc?.hp_remaining ?? 0).toLocaleString()} / {(enc?.hp_max ?? 0).toLocaleString()} HP
                  </p>
                </div>
              </div>
              <div className="guild-hall-boss-hp-track mt-3" role="progressbar" aria-valuenow={Math.round(hpPct)} aria-valuemin={0} aria-valuemax={100}>
                <div className="guild-hall-boss-hp-fill" style={{ width: `${hpPct}%` }} />
              </div>
              {closesLabel ? (
                <p className="text-[10px] text-muted-foreground mt-2 font-cinzel uppercase tracking-wider">
                  Seal breaks · <span className="text-foreground/80 normal-case tracking-normal">{closesLabel}</span>
                </p>
              ) : null}
              <Button size="sm" className="mt-4 w-fit font-cinzel" onClick={() => void onHitBoss()} aria-label="Strike the guild boss">
                Strike
              </Button>
              {lb.length > 0 && (
                <div className="mt-4 pt-3 border-t border-border/40">
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-cinzel mb-2">Top damage</p>
                  <ol className="text-xs space-y-1 list-decimal list-inside text-foreground/90">
                    {lb.slice(0, 8).map((row, i) => (
                      <li key={`${row.name}-${i}`} className="tabular-nums">
                        <span className="font-medium">{row.name}</span> — {Number(row.total_damage).toLocaleString()}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-muted-foreground leading-relaxed">
              No active siege target. Officers can summon a shared boss for the whole guild — everyone contributes damage for
              rewards.
            </p>
          )}
          {officer && (
            <Button size="sm" variant="outline" className="w-fit mt-3 font-cinzel border-primary/35" onClick={() => void onSummonBoss()}>
              Summon Stone Siege Golem
            </Button>
          )}
        </WomPanel>

        <WomPanel glow className="lg:col-span-5 flex flex-col min-h-0">
          <div className="game-panel-header">Treasury</div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Donations fund tech and campaigns. Officers may withdraw (per-guild daily cap on the server).
          </p>
          <div className="flex flex-wrap gap-2 items-end mt-2">
            <div className="flex-1 min-w-[120px]">
              <label className="text-[10px] text-muted-foreground uppercase font-cinzel tracking-wider block mb-1">Donate gold</label>
              <Input value={depositStr} onChange={(e) => setDepositStr(e.target.value)} type="number" min={1} className="h-9" />
            </div>
            <Button size="sm" className="h-9 font-cinzel shrink-0" onClick={() => void onDeposit()}>
              Donate
            </Button>
          </div>
          {officer && (
            <div className="flex flex-wrap gap-2 items-end mt-4 pt-4 border-t border-border/40">
              <div className="flex-1 min-w-[120px]">
                <label className="text-[10px] text-muted-foreground uppercase font-cinzel tracking-wider block mb-1">Withdraw</label>
                <Input value={withdrawStr} onChange={(e) => setWithdrawStr(e.target.value)} type="number" min={1} className="h-9" />
              </div>
              <Button size="sm" variant="secondary" className="h-9 font-cinzel shrink-0" onClick={() => void onWithdraw()}>
                Withdraw
              </Button>
            </div>
          )}
        </WomPanel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WomPanel glow className="min-h-0">
          <div className="game-panel-header">Guild tech</div>
          <p className="text-xs text-muted-foreground mb-3">Passive bonuses for all members (explore, combat, idle).</p>
          <div className="grid sm:grid-cols-1 gap-2 max-h-[min(48vh,420px)] overflow-y-auto pr-1 -mr-1">
            {techDefs.map((node: GuildTechDefinition) => {
              const has = unlocked.has(node.id);
              const missingReq = (node.requires || []).filter((rid) => !unlocked.has(rid));
              const blocked = !has && missingReq.length > 0;
              const canBuy = officer && !has && !blocked;
              return (
                <div
                  key={node.id}
                  className={
                    "guild-hall-tech-card rounded-sm p-3 text-xs flex flex-col gap-1.5 border " +
                    (has
                      ? "guild-hall-tech-card--unlocked border-emerald-600/35 bg-emerald-950/20"
                      : blocked
                        ? "guild-hall-tech-card--locked border-border/50 bg-muted/10 opacity-80"
                        : "border-border/60 bg-muted/5")
                  }
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-foreground font-cinzel text-[13px] tracking-wide">{node.name}</span>
                    {has ? (
                      <span className="text-[10px] uppercase tracking-wider text-emerald-400/95 shrink-0">Unlocked</span>
                    ) : null}
                  </div>
                  <p className="text-muted-foreground leading-snug font-serif">{node.description}</p>
                  <p className="text-[10px] text-muted-foreground/90 tabular-nums">
                    Cost: {node.cost_guild_xp.toLocaleString()} guild XP
                    {node.cost_bank_gold ? ` + ${node.cost_bank_gold.toLocaleString()} bank gold` : ""}
                  </p>
                  {blocked ? (
                    <p className="text-[10px] text-amber-200/80">
                      Requires: {missingReq.join(", ") || "prerequisites"}
                    </p>
                  ) : null}
                  {!has && !blocked && !officer ? (
                    <span className="text-[10px] text-muted-foreground">Officers may unlock this node.</span>
                  ) : null}
                  {canBuy ? (
                    <Button size="sm" className="h-8 mt-1 w-fit font-cinzel" onClick={() => void onUnlockTech(node.id)}>
                      Unlock
                    </Button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </WomPanel>

        <WomPanel glow className="min-h-0 flex flex-col">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div className="game-panel-header flex-1 min-w-0">Raids</div>
            {officer && (
              <Button size="sm" variant="secondary" className="h-8 font-cinzel text-[11px] shrink-0 mb-1" onClick={() => void onCreateRaid()}>
                Schedule sortie
              </Button>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground mb-2">Recent runs — sign up when recruiting is open.</p>
          <ul className="space-y-2 text-xs flex-1 min-h-0 overflow-y-auto max-h-[min(48vh,420px)] pr-1">
            {recentRaids.length === 0 && <li className="text-muted-foreground italic">No raids logged yet.</li>}
            {recentRaids.map((run) => (
              <li
                key={run.id}
                className="rounded-sm p-2.5 border border-border/50 bg-muted/5 flex flex-wrap items-center justify-between gap-2"
              >
                <div className="min-w-0">
                  <div className="font-medium text-foreground truncate">{run.template_key}</div>
                  <div className="text-muted-foreground text-[11px] mt-0.5">
                    Leader <span className="text-foreground/90">{run.leader_name || "?"}</span>
                  </div>
                  <span className={`inline-block mt-1.5 px-2 py-0.5 rounded-sm text-[9px] uppercase tracking-wider font-cinzel ${raidStatusClass(run.status)}`}>
                    {run.status || "?"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 shrink-0">
                  {run.status === "recruiting" && (
                    <Button size="sm" variant="outline" className="h-7 text-[11px] font-cinzel px-2" onClick={() => void onSignupRaid(run.id)}>
                      Sign up
                    </Button>
                  )}
                  {officer && run.status === "recruiting" && (
                    <Button size="sm" className="h-7 text-[11px] font-cinzel px-2" onClick={() => void onStartRaid(run.id)}>
                      Start
                    </Button>
                  )}
                  {officer && run.status === "active" && (
                    <Button size="sm" className="h-7 text-[11px] font-cinzel px-2" onClick={() => void onCompleteRaid(run.id)}>
                      Complete
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </WomPanel>
      </div>

      <WomPanel glow className="flex flex-col min-h-[min(52vh,440px)] max-h-[min(60vh,560px)] flex-1">
        <div className="game-panel-header">Hall chat</div>
        <div className="guild-hall-feed-scroll flex-1 min-h-0 overflow-y-auto space-y-2 pr-1 -mr-1 mb-2">
          {feed.length === 0 && <p className="text-xs text-muted-foreground italic py-2">No messages yet — greet your guild.</p>}
          {feed.map((m) => (
            <div
              key={m.id}
              className={
                "guild-hall-feed-msg rounded-sm p-2.5 leading-relaxed " +
                (m.message_type?.startsWith("system") ? "guild-hall-feed-msg--system" : "")
              }
            >
              <div className="text-[10px] text-muted-foreground mb-1 font-cinzel uppercase tracking-wider">
                {m.author_name || (m.message_type?.startsWith("system") ? "Herald" : "Unknown")}{" "}
                <span className="text-muted-foreground/70 font-normal normal-case tracking-normal">
                  · {m.created_at ? new Date(m.created_at).toLocaleString() : ""}
                </span>
              </div>
              <div className="text-foreground text-sm whitespace-pre-wrap font-serif">{m.body}</div>
            </div>
          ))}
          {feedCursor ? (
            <Button variant="ghost" size="sm" className="text-xs h-8 font-cinzel w-full" onClick={() => void loadMoreFeed()}>
              Older messages
            </Button>
          ) : null}
        </div>
        <div className="guild-hall-chat-composer mt-auto pt-3 border-t border-border/50 flex gap-2 shrink-0">
          <Input
            value={chatDraft}
            onChange={(e) => setChatDraft(e.target.value)}
            placeholder="Message the hall…"
            className="h-9 flex-1"
            maxLength={400}
            onKeyDown={(e) => {
              if (e.key === "Enter") void onSendChat();
            }}
            aria-label="Guild chat message"
          />
          <Button size="sm" className="h-9 shrink-0 font-cinzel" onClick={() => void onSendChat()}>
            Send
          </Button>
        </div>
      </WomPanel>
    </div>
  );
}
