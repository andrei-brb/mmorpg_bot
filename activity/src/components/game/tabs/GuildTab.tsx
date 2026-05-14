import { useCallback, useEffect, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import * as api from "@/lib/gameApi";
import type { GuildFeedMessage, GuildMePayload } from "@/lib/apiTypes";
import { toast } from "sonner";

function isOfficer(rank?: string | null) {
  return rank === "officer" || rank === "guildmaster";
}

function panelClass() {
  return "rounded-sm p-3 sm:p-4 flex flex-col gap-2 min-h-0";
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
    return <p className="text-muted-foreground text-sm p-4">Sign in to manage your guild.</p>;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground text-sm font-cinzel">
        Loading guild…
      </div>
    );
  }

  if (!data?.in_guild) {
    return (
      <div className={`${panelClass()} max-w-lg mx-auto text-center gap-4`} style={{ border: "1px solid hsl(43 40% 28% / 0.35)" }}>
        <div className="text-4xl" aria-hidden>
          🏰
        </div>
        <h2 className="font-cinzel text-lg text-primary">No guild yet</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Found a guild or join one from Discord: <span className="text-foreground font-mono">/guild create</span> or{" "}
          <span className="text-foreground font-mono">/guild join</span>. Then open this tab again — your hall, boss,
          tech, and raids live here.
        </p>
      </div>
    );
  }

  const g = data.guild;
  const rank = g?.my_rank;
  const officer = isOfficer(rank);
  const enc = data.boss?.encounter as { id?: string; hp_remaining?: number; hp_max?: number; status?: string; closes_at?: string } | undefined;
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

  return (
    <div className="flex flex-col gap-4 min-h-0 flex-1 overflow-y-auto pr-1">
      <header
        className="rounded-sm p-4 flex flex-wrap items-end justify-between gap-3"
        style={{
          background: "linear-gradient(135deg, hsl(43 35% 14% / 0.5) 0%, hsl(228 22% 10% / 0.85) 100%)",
          border: "1px solid hsl(43 45% 32% / 0.4)",
        }}
      >
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-cinzel mb-1">Guild hall</div>
          <h1 className="font-cinzel text-xl sm:text-2xl text-primary">
            [{g?.tag}] {g?.name}
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Level {g?.guild_level ?? 1} · {g?.member_count ?? 0}/{g?.max_members ?? 20} members · You:{" "}
            <span className="text-foreground capitalize">{rank || "member"}</span>
          </p>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase text-muted-foreground font-cinzel">Treasury</div>
          <div className="text-xl font-semibold text-amber-200 tabular-nums">{(g?.bank_gold ?? 0).toLocaleString()} gold</div>
          <div className="text-[11px] text-muted-foreground">Guild XP {(g?.guild_xp ?? 0).toLocaleString()}</div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className={panelClass()} style={{ border: "1px solid hsl(228 16% 22%)" }}>
          <h2 className="font-cinzel text-sm text-primary flex items-center gap-2">Bank</h2>
          <p className="text-xs text-muted-foreground">Donations fund tech and boss prep. Officers may withdraw (daily guild cap applies).</p>
          <div className="flex flex-wrap gap-2 items-end">
            <div className="flex-1 min-w-[120px]">
              <label className="text-[10px] text-muted-foreground uppercase">Donate</label>
              <Input value={depositStr} onChange={(e) => setDepositStr(e.target.value)} type="number" min={1} className="h-9" />
            </div>
            <Button size="sm" className="h-9" onClick={() => void onDeposit()}>
              Donate
            </Button>
          </div>
          {officer && (
            <div className="flex flex-wrap gap-2 items-end pt-2 border-t border-border/40">
              <div className="flex-1 min-w-[120px]">
                <label className="text-[10px] text-muted-foreground uppercase">Withdraw</label>
                <Input value={withdrawStr} onChange={(e) => setWithdrawStr(e.target.value)} type="number" min={1} className="h-9" />
              </div>
              <Button size="sm" variant="secondary" className="h-9" onClick={() => void onWithdraw()}>
                Withdraw
              </Button>
            </div>
          )}
        </section>

        <section className={panelClass()} style={{ border: "1px solid hsl(228 16% 22%)" }}>
          <h2 className="font-cinzel text-sm text-primary flex items-center gap-2">Guild boss</h2>
          {bossActive ? (
            <>
              <div className="text-sm font-medium">{tpl.name || "Boss"}</div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-700 to-amber-400 transition-all"
                  style={{
                    width: `${Math.max(3, (100 * Number(enc?.hp_remaining ?? 0)) / Math.max(1, Number(enc?.hp_max ?? 1)))}%`,
                  }}
                />
              </div>
              <p className="text-xs text-muted-foreground tabular-nums">
                {(enc?.hp_remaining ?? 0).toLocaleString()} / {(enc?.hp_max ?? 0).toLocaleString()} HP
                {enc?.closes_at ? ` · ends ${new Date(enc.closes_at).toLocaleString()}` : ""}
              </p>
              <Button size="sm" className="w-fit" onClick={() => void onHitBoss()}>
                Strike
              </Button>
              {lb.length > 0 && (
                <div className="text-xs mt-2 space-y-1">
                  <div className="text-muted-foreground uppercase tracking-wide text-[10px]">Top damage</div>
                  <ol className="list-decimal list-inside space-y-0.5">
                    {lb.slice(0, 8).map((row, i) => (
                      <li key={`${row.name}-${i}`}>
                        {row.name} — {Number(row.total_damage).toLocaleString()}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-muted-foreground">No active boss. Officers summon a shared target for the whole guild.</p>
          )}
          {officer && (
            <Button size="sm" variant="outline" className="w-fit mt-1" onClick={() => void onSummonBoss()}>
              Summon Stone Siege Golem
            </Button>
          )}
        </section>
      </div>

      <section className={panelClass()} style={{ border: "1px solid hsl(228 16% 22%)" }}>
        <h2 className="font-cinzel text-sm text-primary">Guild tech</h2>
        <p className="text-xs text-muted-foreground mb-2">Bonuses apply to all members (explore, combat, idle).</p>
        <div className="grid sm:grid-cols-2 gap-2">
          {techDefs.map((node) => {
            const has = unlocked.has(node.id);
            const canBuy = officer && !has;
            return (
              <div
                key={node.id}
                className="rounded-sm p-3 text-xs flex flex-col gap-1"
                style={{
                  border: "1px solid hsl(228 14% 24%)",
                  background: has ? "hsl(140 20% 8% / 0.35)" : "hsl(228 18% 10% / 0.5)",
                }}
              >
                <div className="font-semibold text-foreground">{node.name}</div>
                <div className="text-muted-foreground leading-snug">{node.description}</div>
                <div className="text-[10px] text-muted-foreground">
                  Cost: {node.cost_guild_xp} guild XP
                  {node.cost_bank_gold ? ` + ${node.cost_bank_gold} bank gold` : ""}
                </div>
                {has ? (
                  <span className="text-emerald-400 text-[11px] font-medium">Unlocked</span>
                ) : canBuy ? (
                  <Button size="sm" className="h-8 mt-1 w-fit" onClick={() => void onUnlockTech(node.id)}>
                    Unlock
                  </Button>
                ) : (
                  <span className="text-muted-foreground text-[11px]">Officers unlock · requires prerequisites</span>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section className={panelClass()} style={{ border: "1px solid hsl(228 16% 22%)" }}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-cinzel text-sm text-primary">Raids</h2>
          {officer && (
            <Button size="sm" variant="secondary" className="h-8" onClick={() => void onCreateRaid()}>
              Schedule Gnoll Warren
            </Button>
          )}
        </div>
        <ul className="space-y-2 text-xs">
          {recentRaids.length === 0 && <li className="text-muted-foreground">No recent raids.</li>}
          {recentRaids.map((run) => (
            <li
              key={run.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-sm p-2"
              style={{ border: "1px solid hsl(228 14% 22%)" }}
            >
              <div>
                <div className="font-medium">{run.template_key}</div>
                <div className="text-muted-foreground">
                  {run.status} · leader {run.leader_name || "?"}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {run.status === "recruiting" && (
                  <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => void onSignupRaid(run.id)}>
                    Sign up
                  </Button>
                )}
                {officer && run.status === "recruiting" && (
                  <Button size="sm" className="h-7 text-[11px]" onClick={() => void onStartRaid(run.id)}>
                    Start
                  </Button>
                )}
                {officer && run.status === "active" && (
                  <Button size="sm" className="h-7 text-[11px]" onClick={() => void onCompleteRaid(run.id)}>
                    Complete
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className={`${panelClass()} flex-1 min-h-[220px]`} style={{ border: "1px solid hsl(228 16% 22%)" }}>
        <h2 className="font-cinzel text-sm text-primary">Hall chat</h2>
        <div className="flex gap-2 flex-1 min-h-0">
          <Input
            value={chatDraft}
            onChange={(e) => setChatDraft(e.target.value)}
            placeholder="Message your guild…"
            className="h-9 flex-1"
            maxLength={400}
            onKeyDown={(e) => {
              if (e.key === "Enter") void onSendChat();
            }}
          />
          <Button size="sm" className="h-9 shrink-0" onClick={() => void onSendChat()}>
            Send
          </Button>
        </div>
        <div className="mt-3 space-y-2 max-h-[280px] overflow-y-auto text-xs pr-1">
          {feed.map((m) => (
            <div
              key={m.id}
              className="rounded-sm p-2 leading-relaxed"
              style={{
                background: m.message_type?.startsWith("system") ? "hsl(43 25% 10% / 0.35)" : "hsl(228 16% 12% / 0.5)",
                border: "1px solid hsl(228 14% 20%)",
              }}
            >
              <div className="text-[10px] text-muted-foreground mb-0.5">
                {m.author_name || (m.message_type?.startsWith("system") ? "System" : "Unknown")} ·{" "}
                {m.created_at ? new Date(m.created_at).toLocaleString() : ""}
              </div>
              <div className="text-foreground whitespace-pre-wrap">{m.body}</div>
            </div>
          ))}
        </div>
        {feedCursor && (
          <Button variant="ghost" size="sm" className="text-xs h-8" onClick={() => void loadMoreFeed()}>
            Older messages
          </Button>
        )}
      </section>
    </div>
  );
}
