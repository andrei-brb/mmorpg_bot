import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";

function exploreRewardHasValues(reward: { xp?: number; gold?: number } | undefined): boolean {
  if (!reward) return false;
  return (Number(reward.xp ?? 0) > 0 || Number(reward.gold ?? 0) > 0);
}

function formatBadgeCount(n: number, max = 99): string {
  if (n <= 0) return "";
  if (n > max) return `${max}+`;
  return String(n);
}

function zoneDangerStars(levelMax?: number): number {
  const lv = Number(levelMax ?? 1);
  if (lv <= 20) return 1;
  if (lv <= 35) return 2;
  if (lv <= 50) return 3;
  if (lv <= 65) return 4;
  return 5;
}

function zoneBadgeLabel(name?: string): string {
  const n = String(name || "").trim();
  if (!n) return "Zone";
  return n.split(/\s+/)[0] || n;
}

export function ExploreTab() {
  const { map, refreshMap, travel, explore, lastExplore, npcInteract, quests, inventory } = useGameSession();
  const [zonePick, setZonePick] = useState("");
  const [busy, setBusy] = useState(false);
  const [npcBusy, setNpcBusy] = useState(false);
  const [showMapResult, setShowMapResult] = useState(true);

  useEffect(() => { void refreshMap(); }, [refreshMap]);
  useEffect(() => { if (map?.current_zone && !zonePick) setZonePick(map.current_zone); }, [map, zonePick]);

  const zones = map?.zones || [];
  const cur = zones.find((z) => z.key === map?.current_zone);
  const outcomeEl = lastExplore?.outcome;
  const activeQuestCount = (quests?.quests || []).filter((q) => String(q.state || "active").toLowerCase() !== "completed").length;
  const materialStacks = (inventory?.items || []).filter((it) => it.item_type === "material").length;
  const latestEncounter = outcomeEl && (outcomeEl.type === "enemy" || outcomeEl.type === "boss");
  const resultType: "enemy" | "boss" | "loot" | "safe" | "npc" | null = lastExplore?.npc
    ? "npc"
    : (outcomeEl?.type ?? null);
  const encounterName =
    outcomeEl && (outcomeEl.type === "enemy" || outcomeEl.type === "boss")
      ? outcomeEl.name
      : "Unknown foe";

  const jumpToTab = (tab: "Hero" | "Combat" | "Quests" | "Market" | "Arena" | "Progress") => {
    window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: tab }));
  };

  useEffect(() => {
    if (lastExplore) setShowMapResult(true);
  }, [lastExplore]);

  const doTravel = async () => {
    if (!zonePick) return;
    setBusy(true);
    try {
      const r = await travel(zonePick);
      if (r.message) toast(r.message); else toast("Traveled.");
    } finally { setBusy(false); }
  };

  const doExplore = async () => {
    setBusy(true);
    try {
      const json = await explore();
      if (json.error === "cooldown" && json.cooldown_s) { toast.error(`Explore cooldown: ${json.cooldown_s}s`); return; }
      if (!json.ok && json.message) { toast.error(json.message); return; }
      if (json.outcome?.type === "enemy" || json.outcome?.type === "boss") {
        toast("Encounter!", { description: `Fight ${json.outcome.name} in the Combat tab.` });
      } else if (json.outcome?.type === "loot" || json.outcome?.type === "safe") {
        toast("Exploration result", { description: json.message || "You continue your journey." });
      }
      if (exploreRewardHasValues(json.reward)) {
        toast.success(`+${json.reward!.xp ?? 0} XP, +${json.reward!.gold ?? 0} gold`);
      }
    } finally { setBusy(false); }
  };

  const interactLastNpc = () => {
    const id = lastExplore?.npc?.npc_id || lastExplore?.npc?.name;
    if (!id) return;
    setNpcBusy(true);
    void npcInteract(id)
      .then((r) => {
        if (r.ok) toast.success(r.message || "NPC interaction");
        else toast.error(r.message || r.error || "Could not interact.");
      })
      .finally(() => setNpcBusy(false));
  };

  return (
    <div className="space-y-4">
      <div className="game-panel">
        <div className="game-panel-header">Explore</div>
        <div className="mb-4 rounded border border-border/60 bg-background/25 px-2 py-2">
          <div className="flex gap-1.5 overflow-x-auto">
            {zones.map((z) => {
              const isCurrent = z.key === map?.current_zone;
              const isSelected = z.key === zonePick;
              return (
                <button
                  key={z.key}
                  type="button"
                  onClick={() => setZonePick(z.key)}
                  className={`relative shrink-0 rounded border px-2 py-1.5 text-center transition ${
                    isSelected || isCurrent
                      ? "border-primary/60 bg-primary/10 text-foreground"
                      : "border-border/60 bg-background/20 text-muted-foreground hover:bg-background/40"
                  }`}
                  title={`${z.name} (${z.level_min ?? "?"}-${z.level_max ?? "?"})`}
                >
                  <div className="text-sm leading-none">{z.emoji}</div>
                  <div className="text-[9px] uppercase tracking-wide mt-0.5">{zoneBadgeLabel(z.name)}</div>
                  {z.boss_alive && (
                    <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-destructive border border-background" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mb-4">
          <h3 className="font-cinzel text-foreground font-semibold text-base">
            {cur?.emoji} {cur?.name ?? "Unknown"}
          </h3>
          <div className="flex gap-3 text-xs text-muted-foreground mt-1.5">
            <span>Levels {cur?.level_min ?? "?"}-{cur?.level_max ?? "?"}</span>
            <span style={{ color: 'hsl(228 14% 28%)' }}>◆</span>
            <span>{cur?.faction ?? "Neutral"}</span>
            {cur?.players != null && (
              <>
                <span style={{ color: 'hsl(228 14% 28%)' }}>◆</span>
                <span>{cur.players} players nearby</span>
              </>
            )}
          </div>
        </div>

        <div className="ornament-divider mb-4" />

        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] uppercase tracking-[0.24em] text-muted-foreground">Zone map</span>
          <div className="h-px flex-1 bg-border/50" />
        </div>

        <div
          className="relative rounded border border-border/70 mb-4 overflow-hidden"
          style={{
            background:
              "radial-gradient(120% 110% at 50% 25%, hsl(145 40% 20% / 0.35) 0%, hsl(220 30% 10% / 0.72) 58%, hsl(228 30% 7% / 0.95) 100%)",
          }}
        >
          <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-black/30 to-black/55" />
          <div className="relative px-4 py-5 text-center min-h-[180px] flex flex-col items-center justify-center">
            <div className="text-4xl mb-1">{cur?.emoji || "🗺️"}</div>
            <div className="font-cinzel text-sm text-foreground font-semibold">{cur?.name ?? "Unknown Zone"}</div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-1">Zone threat</div>
            <div className="mt-1.5 flex items-center justify-center gap-1.5">
              {Array.from({ length: 5 }).map((_, i) => (
                <span key={i} className={`text-xs ${i < zoneDangerStars(cur?.level_max) ? "opacity-100" : "opacity-25"}`}>
                  💀
                </span>
              ))}
            </div>
            {cur?.boss_alive && (
              <div className="mt-2 inline-flex items-center gap-1 rounded border border-destructive/45 bg-destructive/15 px-2 py-0.5 text-[10px] uppercase tracking-wide text-destructive">
                👑 World boss active
              </div>
            )}
          </div>

          {showMapResult && resultType && (
            <div className="absolute inset-0 bg-black/45 backdrop-blur-[1px] flex items-center justify-center px-4">
              <div className="w-full max-w-md rounded border border-border/80 bg-background/85 px-4 py-3 text-center shadow-xl">
                <div className="text-[10px] uppercase tracking-[0.28em] text-muted-foreground mb-1">
                  {resultType === "enemy" && "Encounter"}
                  {resultType === "boss" && "Boss encounter"}
                  {resultType === "loot" && "Discovery"}
                  {resultType === "safe" && "Quiet journey"}
                  {resultType === "npc" && "NPC met"}
                </div>
                {(resultType === "enemy" || resultType === "boss") && (
                  <div className="font-cinzel font-semibold text-foreground text-lg">
                    {encounterName}
                  </div>
                )}
                {resultType === "npc" && (
                  <div className="font-cinzel font-semibold text-accent-foreground text-lg">
                    {lastExplore?.npc?.name || "Wanderer"}
                  </div>
                )}
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  {lastExplore?.message || "You continue your journey."}
                </p>
                {exploreRewardHasValues(lastExplore?.reward) && (
                  <div className="mt-2 text-xs">
                    <span className="text-primary font-semibold mr-3">+{lastExplore?.reward?.xp ?? 0} XP</span>
                    <span className="text-gold font-semibold">+{lastExplore?.reward?.gold ?? 0} 🪙</span>
                  </div>
                )}
                <div className="mt-3 flex items-center justify-center gap-2">
                  {(resultType === "enemy" || resultType === "boss") && (
                    <button
                      type="button"
                      onClick={() => jumpToTab("Combat")}
                      className="game-btn-primary text-xs px-3 py-1.5"
                    >
                      Combat
                    </button>
                  )}
                  {resultType === "npc" && (
                    <button
                      type="button"
                      disabled={npcBusy}
                      onClick={interactLastNpc}
                      className="game-btn-secondary text-xs px-3 py-1.5"
                    >
                      {npcBusy ? "..." : (lastExplore?.npc?.already_met ? "Talk Again" : "Interact")}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setShowMapResult(false)}
                    className="text-xs px-3 py-1.5 rounded border border-border/70 hover:bg-background/60"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {zonePick && zonePick !== map?.current_zone && (
          <div className="mb-4">
            <button onClick={() => void doTravel()} disabled={busy} className="game-btn-primary w-full">
              {busy ? "Traveling..." : "Travel to selected zone"}
            </button>
          </div>
        )}

        <div className="ornament-divider mb-4" />

        <div className="flex items-center gap-3">
          <button onClick={() => void doExplore()} disabled={busy} className="game-btn-secondary">
            Explore
          </button>
          <span className="text-xs text-muted-foreground">Cooldown: ~30s between explorations</span>
        </div>
      </div>

      <div className="rounded border border-gold/20 bg-gold/5 px-3 py-2">
        <p className="text-[11px] text-gold/70 italic">
          Quests often start or advance after meeting NPCs while exploring. Check the <span className="text-gold font-semibold not-italic">Quests</span> tab after NPC encounters.
        </p>
      </div>

      <div className="game-panel">
        <div className="game-panel-header">World Activity</div>
        <p className="text-[11px] text-muted-foreground mb-3">
          Quick access to core MMO systems while keeping zones and travel above.
        </p>
        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
          <button
            type="button"
            onClick={() => jumpToTab("Combat")}
            className="relative rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Encounters and monster fights"
          >
            <div className="text-base">⚔️</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Fights</div>
            {latestEncounter && (
              <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-destructive text-[9px] text-white leading-[15px] font-semibold">
                !
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Quests")}
            className="relative rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Quest log and NPC objectives"
          >
            <div className="text-base">📜</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Quests</div>
            {activeQuestCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-primary text-[9px] text-primary-foreground leading-[15px] font-semibold">
                {formatBadgeCount(activeQuestCount, 9)}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Combat")}
            className="relative rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Dungeon and boss combat systems"
          >
            <div className="text-base">🛡️</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Dungeons</div>
            {cur?.boss_alive && (
              <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-destructive text-[9px] text-white leading-[15px] font-semibold">
                !
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Hero")}
            className="relative rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Recovery and character management"
          >
            <div className="text-base">🛏️</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Rest</div>
            <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-emerald-700 text-[9px] text-white leading-[15px] font-semibold">
              +HP
            </span>
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Hero")}
            className="relative rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Bag materials and crafting goods"
          >
            <div className="text-base">📦</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Materials</div>
            {materialStacks > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-1 rounded-full bg-amber-600 text-[9px] text-black leading-[15px] font-semibold">
                {formatBadgeCount(materialStacks)}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Market")}
            className="rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Shop and player market"
          >
            <div className="text-base">🏪</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Market</div>
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Arena")}
            className="rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Arena PvP"
          >
            <div className="text-base">🏟️</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Arena</div>
          </button>
          <button
            type="button"
            onClick={() => jumpToTab("Progress")}
            className="rounded border border-border/70 bg-background/30 hover:bg-background/50 transition px-2 py-2 text-center"
            title="Stats, achievements, and history"
          >
            <div className="text-base">📈</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Progress</div>
          </button>
          <div className="rounded border border-dashed border-border/70 bg-background/20 px-2 py-2 text-center">
            <div className="text-base">🔨</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Crafting</div>
            <div className="text-[8px] text-muted-foreground/70">Soon</div>
          </div>
          <div className="rounded border border-dashed border-border/70 bg-background/20 px-2 py-2 text-center">
            <div className="text-base">⛏️</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Collecting</div>
            <div className="text-[8px] text-muted-foreground/70">Soon</div>
          </div>
          <div className="rounded border border-dashed border-border/70 bg-background/20 px-2 py-2 text-center">
            <div className="text-base">🌙</div>
            <div className="text-[9px] uppercase tracking-wide text-muted-foreground">Idle</div>
            <div className="text-[8px] text-muted-foreground/70">Soon</div>
          </div>
        </div>
      </div>
    </div>
  );
}
