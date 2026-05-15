import { useCallback, useEffect, useMemo, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WomPanel, WomSectionHeader } from "@/components/wom/WomUi";
import type { CharacterDerivedStatsPayload, ProgressPayload } from "@/lib/apiTypes";
import * as api from "@/lib/gameApi";
import { cn } from "@/lib/utils";
import { SocialPanel } from "@/components/game/panels/SocialPanel";

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
  { bucket: "Character", title: "Talent trees & full respec meta", blurb: "Point-based builds beyond specializations." },
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

  const c = progress?.character ?? inventory?.character ?? undefined;
  const s = progress?.stats;
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

  const statTiles = useMemo(
    () => [
      { label: "Level", value: c?.level ?? "—", icon: "⭐" },
      { label: "Specialization", value: c?.specialization_name || c?.specialization || "—", icon: "🗡️" },
      { label: "Gold", value: c?.gold != null ? Number(c.gold).toLocaleString() : "—", icon: "🪙" },
      {
        label: "Win rate",
        value: s?.win_rate != null ? `${Math.round(s.win_rate * 10000) / 100}%` : "—",
        icon: "📈",
      },
      { label: "Combats", value: s?.total_combats != null ? s.total_combats : "—", icon: "⚔️" },
      {
        label: "Record",
        value: s?.wins != null || s?.losses != null ? `${s?.wins ?? 0}W / ${s?.losses ?? 0}L` : "—",
        icon: "🏆",
      },
    ],
    [c, s],
  );

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
          <SocialPanel accessToken={accessToken} guildId={guildId} />

          {liveEvents.length > 0 ? (
            <WomPanel glow>
              <WomSectionHeader kicker="Server" title="Live events" />
              <ul className="text-xs space-y-2 text-muted-foreground">
                {liveEvents.map((ev) => (
                  <li key={ev.slug || ev.title || String(ev.ends_at)}>
                    <span className="text-foreground font-medium">{ev.title || ev.slug || "Event"}</span>
                    {ev.description ? <span> — {ev.description}</span> : null}
                  </li>
                ))}
              </ul>
            </WomPanel>
          ) : null}
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
            <WomSectionHeader kicker="Coming later" title="Milestones" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              Server-wide milestone boards (community goals, unlock tiers) will plug in here when the API is ready.
            </p>
          </WomPanel>

          <WomPanel glow>
            <WomSectionHeader kicker="Factions" title="Reputation" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              Faction reputation will surface here when we aggregate it from quests and world events. For now, check
              quest rewards for rep gains.
            </p>
          </WomPanel>
        </TabsContent>

        <TabsContent value="power" className="flex-1 min-h-0 overflow-y-auto mt-3 space-y-3 pr-1 pb-2">
          <WomPanel glow>
            <div className="game-panel-header">Combat snapshot</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {statTiles.map((st) => (
                <div key={st.label} className="stat-card">
                  <div className="text-2xl mb-1.5" style={{ filter: "drop-shadow(0 1px 2px hsl(0 0% 0% / 0.5))" }}>
                    {st.icon}
                  </div>
                  <div
                    className="text-lg font-cinzel font-bold text-foreground tabular-nums"
                    style={{ textShadow: "0 1px 2px hsl(0 0% 0% / 0.4)" }}
                  >
                    {st.value}
                  </div>
                  <div className="text-[10px] text-muted-foreground font-cinzel uppercase tracking-wider mt-0.5">
                    {st.label}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {s ? (
                <>
                  Combats: {s.total_combats ?? 0} · W {s.wins ?? 0} / L {s.losses ?? 0} / Fled {s.fled ?? 0}
                </>
              ) : (
                <>Loading combat stats…</>
              )}
            </p>
          </WomPanel>

          <WomPanel glow>
            <div className="game-panel-header">Derived combat stats</div>
            {!derived ? (
              <p className="text-xs text-muted-foreground">Loading…</p>
            ) : !derived.ok ? (
              <p className="text-xs text-muted-foreground">Could not load derived stats.</p>
            ) : (
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  ["Damage", `${derived.dmg_min}–${derived.dmg_max}`],
                  ["Armor", String(derived.armor)],
                  ["Crit", `${derived.crit_chance.toFixed(1)}%`],
                  ["Dodge", `${derived.dodge_chance.toFixed(1)}%`],
                  ["Haste", `${derived.haste.toFixed(1)}%`],
                  ["Lifesteal", `${derived.lifesteal.toFixed(1)}%`],
                  ["Resistance", String(derived.resistance)],
                  ["Hit", `${derived.hit_rating.toFixed(0)}`],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-2 border border-border/40 rounded-sm px-2 py-1.5 bg-muted/20">
                    <span className="text-muted-foreground font-cinzel">{k}</span>
                    <span className="text-foreground font-mono tabular-nums">{v}</span>
                  </div>
                ))}
              </div>
            )}
            {derived?.class_mastery?.level != null ? (
              <p className="text-xs text-muted-foreground mt-3">
                Class mastery: Lv {derived.class_mastery.level}
                {derived.class_mastery.xp != null ? ` (${derived.class_mastery.xp} XP)` : ""}
              </p>
            ) : null}
            {derived?.top_ability_mastery && derived.top_ability_mastery.length > 0 ? (
              <div className="mt-2 space-y-1">
                <p className="text-[10px] font-cinzel uppercase tracking-wider text-muted-foreground">Top abilities</p>
                <ul className="text-xs text-foreground/90 space-y-0.5">
                  {derived.top_ability_mastery.slice(0, 6).map((ab) => (
                    <li key={ab.ability_key || "?"} className="flex justify-between gap-2 font-mono">
                      <span className="truncate">{ab.ability_key}</span>
                      <span className="shrink-0 text-muted-foreground">
                        Lv {ab.level ?? 1}
                        {ab.xp != null ? ` · ${ab.xp} xp` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </WomPanel>
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
              Full talent grids, path respec costs, and build templates are planned — specializations already gate your
              class fantasy today.
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
