import { useCallback, useEffect, useMemo, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { WomPanel, WomSectionHeader } from "@/components/wom/WomUi";
import type {
  CharacterDerivedStatsPayload,
  FactionReputationRow,
  MilestoneProgressRow,
  MilestoneBuffRow,
  MilestonesPayload,
  ProgressPayload,
} from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";
import { cn } from "@/lib/utils";
import { SocialPanel } from "@/components/game/panels/SocialPanel";
import { TalentForgeView } from "@/components/game/talents/TalentForgeView";

const GOALS_STORAGE_KEY = "realm_player_goals_v1";

type GoalRow = { id: string; text: string; done: boolean };

const TYPE_ICONS: Record<string, string> = {
  victory: "🏆",
  defeat: "💀",
  gold: "✨",
  combat_session: "⚔️",
  combat_gold: "🪙",
};

const ROADMAP: { bucket: string; title: string; blurb: string }[] = [
  { bucket: "Social", title: "Friend suggestions & Discord invites", blurb: "Smarter recommendations and optional DM alerts for friend requests." },
  { bucket: "World", title: "Territory & faction campaigns", blurb: "Server-wide objectives, war phases, and map control." },
  { bucket: "Economy", title: "Direct player trade", blurb: "Secure trade window alongside the market." },
  { bucket: "Economy", title: "Auction dynamics", blurb: "Bids, buy orders, and listing depth." },
  { bucket: "PvE", title: "Dungeon finder & large raids", blurb: "Automated LFG and multi-phase raid tiers." },
  { bucket: "PvE", title: "Mythic+ style scaling", blurb: "Affixes, keystones, and seasonal dungeon ladders." },
  { bucket: "Character", title: "Build templates & loadouts", blurb: "Save and share talent layouts across characters." },
  { bucket: "Character", title: "Cosmetics & transmog", blurb: "Wardrobe, dyes, and fashion endgame." },
  { bucket: "World", title: "Housing & guild hall spaces", blurb: "Instanced spaces with decoration progression." },
  { bucket: "Life sim", title: "Mounts, pets, minigames", blurb: "Collections that feed into combat or social hooks." },
];

function formatHistoryAt(at: string | undefined): string {
  if (!at) return "";
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleString();
}

function historyLine(h: NonNullable<ProgressPayload["history"]>[number]): string {
  if (h.type === "combat_session") {
    const o = h.outcome || "unknown";
    const z = h.zone ? ` · ${h.zone}` : "";
    return `${o}${z}`;
  }
  if (h.type === "combat_gold" || h.amount != null) {
    const amt = h.amount ?? 0;
    const r = h.reason || "reward";
    return `+${amt} ${r}`;
  }
  return h.reason || h.type || "—";
}

function formatDeedLabel(flag: string): string {
  return flag
    .split(/[_/]+/g)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function loadGoals(): GoalRow[] {
  try {
    const raw = localStorage.getItem(GOALS_STORAGE_KEY);
    if (!raw) return [];
    const j = JSON.parse(raw) as unknown;
    if (!Array.isArray(j)) return [];
    return j
      .filter((x) => x && typeof (x as GoalRow).id === "string" && typeof (x as GoalRow).text === "string")
      .map((x) => ({
        id: String((x as GoalRow).id),
        text: String((x as GoalRow).text),
        done: Boolean((x as GoalRow).done),
      }));
  } catch {
    return [];
  }
}

function saveGoals(rows: GoalRow[]) {
  try {
    localStorage.setItem(GOALS_STORAGE_KEY, JSON.stringify(rows));
  } catch {
    /* ignore */
  }
}

export function RealmTab() {
  const {
    accessToken,
    guildId,
    inventory,
    map,
    progress,
    refreshProgress,
    refreshMap,
    deedFlags,
    liveEvents,
  } = useGameSession();

  const [derived, setDerived] = useState<CharacterDerivedStatsPayload | null>(null);
  const [goals, setGoals] = useState<GoalRow[]>([]);
  const [goalDraft, setGoalDraft] = useState("");
  const [milestones, setMilestones] = useState<MilestoneProgressRow[]>([]);
  const [milestoneBuffs, setMilestoneBuffs] = useState<MilestoneBuffRow[]>([]);
  const [factions, setFactions] = useState<FactionReputationRow[]>([]);
  const [worldMetaLoading, setWorldMetaLoading] = useState(false);

  useEffect(() => {
    setGoals(loadGoals());
  }, []);

  useEffect(() => {
    saveGoals(goals);
  }, [goals]);

  useEffect(() => {
    void refreshProgress();
    void refreshMap();
  }, [refreshProgress, refreshMap]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    setWorldMetaLoading(true);
    void (async () => {
      try {
        const [ms, rep] = await Promise.all([
          guildId ? api.getMilestones(accessToken, guildId) : Promise.resolve<MilestonesPayload>({ ok: false }),
          api.getReputation(accessToken, guildId),
        ]);
        if (cancelled) return;
        setMilestones(ms.ok ? ms.progress || [] : []);
        setMilestoneBuffs(ms.ok ? ms.buffs || [] : []);
        setFactions(rep.ok ? rep.factions || [] : []);
      } catch {
        if (!cancelled) {
          setMilestones([]);
          setMilestoneBuffs([]);
          setFactions([]);
        }
      } finally {
        if (!cancelled) setWorldMetaLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId]);

  const derivedStatsKey = useMemo(() => {
    const items = inventory?.items || [];
    const eq = items
      .filter((it) => Boolean(it.is_equipped && it.equip_slot))
      .map((it) => `${it.equip_slot}:${it.template_id || it.id}:${Number(it.enhancement_level ?? 0)}`)
      .sort()
      .join("|");
    const lvl = inventory?.character?.level ?? 0;
    return `${lvl}|${eq}`;
  }, [inventory?.items, inventory?.character?.level]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void api
      .getCharacterDerivedStats(accessToken, guildId)
      .then((j) => {
        if (!cancelled) setDerived(j.ok ? j : null);
      })
      .catch(() => {
        if (!cancelled) setDerived(null);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, guildId, derivedStatsKey]);

  const refreshDerivedStats = useCallback(() => {
    if (!accessToken) return;
    void api.getCharacterDerivedStats(accessToken, guildId).then((stats) => {
      if (stats.ok) setDerived(stats);
    });
  }, [accessToken, guildId]);

  const c = progress?.character ?? inventory?.character ?? undefined;
  const ach = progress?.achievements || [];
  const hist = progress?.history || [];

  const zones = map?.zones || [];
  const wb = map?.world_boss_windows || [];

  const addGoal = () => {
    const t = goalDraft.trim();
    if (!t) return;
    setGoals((g) => [...g, { id: crypto.randomUUID(), text: t, done: false }]);
    setGoalDraft("");
  };

  return (
    <div className="flex flex-col gap-3 min-h-0 flex-1 overflow-hidden pr-0.5">
      <Tabs defaultValue="social" className="flex flex-col flex-1 min-h-0">
        <TabsList
          className={cn(
            "h-auto w-full shrink-0 flex flex-wrap justify-start gap-1 p-1.5",
            "bg-muted/50 border border-border/50 rounded-sm overflow-x-auto",
          )}
        >
          {(
            [
              ["social", "Social"],
              ["world", "World"],
              ["power", "Power"],
              ["records", "Records"],
              ["story", "Story"],
              ["goals", "Goals"],
              ["roadmap", "Roadmap"],
            ] as const
          ).map(([v, label]) => (
            <TabsTrigger
              key={v}
              value={v}
              className="text-[10px] sm:text-xs px-2.5 py-2 data-[state=active]:bg-background/90 font-cinzel uppercase tracking-wide"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="social" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <SocialPanel accessToken={accessToken} guildId={guildId} liveEvents={liveEvents} />
        </TabsContent>

        <TabsContent value="world" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <WomPanel glow>
            <WomSectionHeader kicker="Atlas" title="Known zones" />
            {zones.length === 0 ? (
              <p className="text-xs text-muted-foreground">No zone data — try Explore to refresh the map.</p>
            ) : (
              <ul className="space-y-2 text-xs">
                {zones.map((z) => (
                  <li
                    key={z.key}
                    className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/30 pb-2 last:border-0 last:pb-0"
                  >
                    <span>
                      <span className="mr-1">{z.emoji || "🗺️"}</span>
                      <span className="font-semibold text-foreground">{z.name}</span>
                      {z.is_current ? <span className="ml-2 text-primary text-[10px] uppercase">Current</span> : null}
                    </span>
                    <span className="text-muted-foreground tabular-nums">
                      Lv {z.level_min ?? "?"}–{z.level_max ?? "?"}
                      {z.faction ? ` · ${z.faction}` : ""}
                      {z.boss_alive ? " · boss up" : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </WomPanel>

          <WomPanel glow>
            <WomSectionHeader kicker="World bosses" title="Windows" />
            {wb.length === 0 ? (
              <p className="text-xs text-muted-foreground">No active world boss windows.</p>
            ) : (
              <ul className="text-xs space-y-2 text-muted-foreground">
                {wb.map((w, i) => (
                  <li key={`${w.zone_key}-${w.boss_key}-${i}`}>
                    <span className="text-foreground">{w.title || w.boss_key}</span>
                    {w.ends_at ? <span className="tabular-nums"> · ends {new Date(w.ends_at).toLocaleString()}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </WomPanel>

          <WomPanel glow>
            <WomSectionHeader kicker="Server" title="Milestones" />
            {!guildId ? (
              <p className="text-xs text-muted-foreground">Open the game in a Discord server to see shared milestones.</p>
            ) : worldMetaLoading ? (
              <ul className="space-y-3" aria-busy="true" aria-label="Loading milestones">
                {[1, 2, 3].map((i) => (
                  <li key={i}>
                    <div className="flex justify-between gap-2">
                      <Skeleton className="h-3 w-2/5" />
                      <Skeleton className="h-3 w-14" />
                    </div>
                    <Skeleton className="mt-2 h-1.5 w-full rounded-sm" />
                    <Skeleton className="mt-2 h-3 w-1/3" />
                  </li>
                ))}
              </ul>
            ) : milestones.length === 0 ? (
              <p className="text-xs text-muted-foreground">No milestone data yet — play in this server to contribute.</p>
            ) : (
              <ul className="space-y-3 text-xs">
                {milestones.map((m) => {
                  const pct =
                    m.next_target && m.next_target > 0
                      ? Math.min(100, Math.round((m.value / m.next_target) * 100))
                      : 100;
                  return (
                    <li key={m.key}>
                      <div className="flex justify-between gap-2 text-foreground font-medium">
                        <span>{m.title}</span>
                        <span className="tabular-nums text-muted-foreground">
                          Tier {m.tier}/{m.max_tier}
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-sm overflow-hidden bg-muted/40">
                        <div className="h-full bg-primary/80" style={{ width: `${pct}%` }} />
                      </div>
                      <p className="mt-1 text-muted-foreground tabular-nums">
                        {m.value.toLocaleString()}
                        {m.next_target != null ? ` / ${m.next_target.toLocaleString()} ${m.unit}` : ` ${m.unit} (max)`}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
            {milestoneBuffs.length > 0 ? (
              <div className="mt-3 pt-3 border-t border-border/40">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Active buffs</p>
                <ul className="space-y-1 text-xs text-emerald-200/90">
                  {milestoneBuffs.map((b, i) => (
                    <li key={i}>
                      {b.buff_type === "xp_multiplier" ? "XP" : "Gold"}{" "}
                      +{Math.round(Number(b.buff_value || 0) * 100)}%
                      {b.expires_at ? ` · until ${new Date(b.expires_at).toLocaleString()}` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </WomPanel>

          <WomPanel glow>
            <WomSectionHeader kicker="Factions" title="Reputation" />
            {worldMetaLoading ? (
              <p className="text-xs text-muted-foreground">Loading reputation…</p>
            ) : factions.length === 0 ? (
              <p className="text-xs text-muted-foreground">Complete quests to earn faction reputation.</p>
            ) : (
              <ul className="space-y-2 text-xs">
                {factions
                  .filter((f) => f.reputation > 0)
                  .slice(0, 8)
                  .map((f) => (
                    <li
                      key={f.faction_id}
                      className="flex items-center justify-between gap-2 border-b border-border/30 pb-2 last:border-0"
                    >
                      <span>
                        {f.emoji} <span className="font-semibold text-foreground">{f.name}</span>
                      </span>
                      <span className="text-muted-foreground tabular-nums shrink-0">
                        {f.reputation.toLocaleString()}
                        {f.level?.name ? ` · ${f.level.name}` : ""}
                      </span>
                    </li>
                  ))}
                {factions.every((f) => f.reputation <= 0) ? (
                  <li className="text-muted-foreground">No standing yet — talk to NPCs on the Quests tab.</li>
                ) : null}
              </ul>
            )}
          </WomPanel>
        </TabsContent>

        <TabsContent value="power" className="flex-1 min-h-0 overflow-y-auto mt-0 pr-0 pb-0">
          <TalentForgeView
            characterLevel={c?.level}
            characterClass={c?.class}
            onStatsRefresh={refreshDerivedStats}
          />
        </TabsContent>

        <TabsContent value="records" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <WomPanel glow>
            <div className="game-panel-header">Achievements</div>
            <div className="space-y-1">
              {ach.length === 0 && <p className="text-xs text-muted-foreground">None earned yet.</p>}
              {ach.map((a, i) => (
                <div key={`${a.id ?? a.name ?? i}`}>
                  <div className="flex items-center gap-3 p-2.5">
                    <span className="text-xl" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.4))" }}>
                      {a.icon || "🏅"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-foreground font-cinzel">{a.name}</div>
                      <div className="text-xs text-muted-foreground">{a.description}</div>
                    </div>
                    <span className="text-xs text-primary font-semibold shrink-0" style={{ textShadow: "0 0 4px hsl(43 78% 50% / 0.2)" }}>
                      +{a.points ?? 0} pts
                    </span>
                  </div>
                  {i < ach.length - 1 && <div className="ornament-divider" />}
                </div>
              ))}
            </div>
          </WomPanel>

          <WomPanel glow>
            <div className="game-panel-header">History</div>
            <div className="space-y-0">
              {hist.length === 0 && <p className="text-xs text-muted-foreground">No history.</p>}
              {hist.map((h, i) => (
                <div key={i}>
                  <div className="flex items-center gap-2 text-xs py-2">
                    <span>{TYPE_ICONS[h.type || ""] || "✨"}</span>
                    <span className="text-foreground flex-1">{historyLine(h)}</span>
                    {h.type !== "combat_session" && h.zone ? (
                      <span className="text-muted-foreground hidden sm:inline">{h.zone}</span>
                    ) : null}
                    <span className="text-muted-foreground shrink-0 tabular-nums">{formatHistoryAt(h.at)}</span>
                  </div>
                  {i < hist.length - 1 && <div className="ornament-divider" />}
                </div>
              ))}
            </div>
          </WomPanel>
        </TabsContent>

        <TabsContent value="story" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <WomPanel glow>
            <WomSectionHeader kicker="Lore" title="Story deeds" />
            {deedFlags.length === 0 ? (
              <p className="text-xs text-muted-foreground">No deeds recorded yet — progress the main story in Quests.</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {deedFlags.map((f) => (
                  <li
                    key={f}
                    className="text-xs px-2 py-1 rounded-sm border border-primary/35 bg-primary/10 text-foreground font-mono"
                  >
                    {formatDeedLabel(f)}
                  </li>
                ))}
              </ul>
            )}
          </WomPanel>
        </TabsContent>

        <TabsContent value="goals" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <WomPanel glow>
            <WomSectionHeader kicker="This device only" title="Personal goals" />
            <p className="text-xs text-muted-foreground mb-3">
              Simple checklist stored in your browser (not synced to the server yet).
            </p>
            <div className="flex gap-2 mb-3">
              <Input
                value={goalDraft}
                onChange={(e) => setGoalDraft(e.target.value)}
                placeholder="Add a goal…"
                className="h-9 text-sm"
                maxLength={120}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addGoal();
                }}
              />
              <Button type="button" size="sm" className="shrink-0 font-cinzel" onClick={addGoal}>
                Add
              </Button>
            </div>
            <ul className="space-y-2">
              {goals.length === 0 ? <p className="text-xs text-muted-foreground">No goals yet.</p> : null}
              {goals.map((row) => (
                <li key={row.id} className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={row.done}
                    onChange={() => setGoals((g) => g.map((x) => (x.id === row.id ? { ...x, done: !x.done } : x)))}
                    aria-label={`Done: ${row.text}`}
                  />
                  <span className={cn(row.done ? "line-through text-muted-foreground" : "text-foreground")}>{row.text}</span>
                  <button
                    type="button"
                    className="ml-auto text-[10px] text-muted-foreground hover:text-destructive uppercase tracking-wide"
                    onClick={() => setGoals((g) => g.filter((x) => x.id !== row.id))}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </WomPanel>

          <WomPanel glow>
            <WomSectionHeader kicker="Builds" title="Talent trees" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              Spend points in Realm → Power. First respec is free; later respecs cost gold based on your level.
            </p>
          </WomPanel>
        </TabsContent>

        <TabsContent value="roadmap" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <WomPanel glow>
            <WomSectionHeader kicker="Later" title="Realm roadmap" />
            <p className="text-xs text-muted-foreground mb-3">
              Bigger MMORPG pillars we are not building yet — kept here so we can pick them up intentionally.
            </p>
            <ul className="space-y-3">
              {ROADMAP.map((row) => (
                <li key={row.title} className="text-xs border-b border-border/30 pb-3 last:border-0 last:pb-0">
                  <span className="text-[10px] font-cinzel uppercase tracking-wider text-primary/80">{row.bucket}</span>
                  <div className="text-sm font-semibold text-foreground mt-0.5">{row.title}</div>
                  <p className="text-muted-foreground mt-1 leading-relaxed">{row.blurb}</p>
                </li>
              ))}
            </ul>
          </WomPanel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
