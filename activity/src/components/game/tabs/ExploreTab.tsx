import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { useGameSession } from "@/context/GameSessionContext";
import { ZONES as DATA_ZONES } from "@/data/zones";
import { zoneMapImageUrl } from "@/data/zoneMapArt";
import type { ExploreResultPayload } from "@/lib/apiTypes";
import { cn } from "@/lib/utils";
import {
  Compass,
  MapPin,
  ChevronDown,
  ChevronUp,
  Clock,
  Navigation,
  Swords,
  Sword,
  Crown,
  Sparkles,
  Star,
  MessageCircle,
  Zap,
  Coins,
  ChevronRight,
  Skull,
} from "lucide-react";

type Faction = "alliance" | "horde" | "neutral" | "hostile";
type OutcomeType = "enemy" | "boss" | "loot" | "safe" | "npc";
type AppTab = "Hero" | "Explore" | "Quests" | "Combat" | "Market" | "Arena" | "Realm";

type Zone = {
  id: string;
  name: string;
  emoji: string;
  levelRange: [number, number];
  faction: Faction;
  playersNearby: number;
  bossAlive: boolean;
  description: string;
  regionHint?: string;
  /** Hand-painted zone map from `public/assets/items/generated/maps/`, when available. */
  mapImageUrl?: string;
};

type Npc = {
  id: string;
  name: string;
  title: string;
  silhouette: string;
  discoveryQuote?: string;
  alreadyMet: boolean;
};

type ExploreResult = {
  id: string;
  type: OutcomeType;
  message: string;
  reward?: { xp?: number; gold?: number };
  npc?: Npc;
  enemyName?: string;
  /** Server enemy template key — required to jump straight into combat. */
  enemyKey?: string;
  enemyLevel?: number;
  isBoss?: boolean;
  timestamp: Date;
};

const ZONE_EMOJI: Record<string, string> = {
  elwynn_forest: "🌲",
  dun_morogh: "❄️",
  barrens: "🌵",
  stranglethorn: "🌴",
  blackrock_depths: "🌋",
};

const ZONE_COPY: Record<string, { description: string; regionHint?: string }> = {
  elwynn_forest: {
    description: "A peaceful woodland surrounding the human capital. Ideal for new adventurers finding their footing.",
  },
  dun_morogh: { description: "Frozen dwarven peaks. Bitter cold and hardy enemies await." },
  barrens: { description: "A vast sun-scorched wasteland where only the ruthless survive." },
  stranglethorn: {
    description: "A lush but deadly jungle where pirates, predators, and rival factions clash.",
    regionHint: "The Bloodsail Buccaneers grow bolder near Booty Bay.",
  },
  blackrock_depths: {
    description: "A labyrinthine dungeon-city inside an active volcano. The ultimate endgame challenge.",
  },
};

function dataFactionToUi(f: "Alliance" | "Horde" | "Neutral"): Faction {
  if (f === "Alliance") return "alliance";
  if (f === "Horde") return "horde";
  return "neutral";
}

const EXPLORE_ZONES: Zone[] = DATA_ZONES.map((z) => {
  const copy = ZONE_COPY[z.key] ?? { description: "" };
  return {
    id: z.key,
    name: z.name,
    emoji: ZONE_EMOJI[z.key] ?? "🗺️",
    levelRange: z.levelRange,
    faction: dataFactionToUi(z.faction),
    playersNearby: 0,
    bossAlive: false,
    description: copy.description,
    regionHint: copy.regionHint,
    mapImageUrl: zoneMapImageUrl(z.key),
  };
});

const ZONE_THEMES: Record<string, { bg: string; glow: string; accent: string; dangerLabel: string; dangerColor: string; biomeLabel: string; stars: number }> = {
  "Elwynn Forest": { bg: "linear-gradient(160deg, oklch(0.20 0.07 145) 0%, oklch(0.14 0.05 155) 55%, oklch(0.10 0.03 165) 100%)", glow: "oklch(0.50 0.14 148)", accent: "oklch(0.55 0.14 150)", dangerLabel: "Beginner", dangerColor: "oklch(0.62 0.16 145)", biomeLabel: "Temperate Forest", stars: 1 },
  "Dun Morogh": { bg: "linear-gradient(160deg, oklch(0.22 0.06 230) 0%, oklch(0.16 0.05 235) 55%, oklch(0.11 0.03 240) 100%)", glow: "oklch(0.55 0.10 230)", accent: "oklch(0.62 0.12 225)", dangerLabel: "Beginner", dangerColor: "oklch(0.58 0.12 230)", biomeLabel: "Frozen Peaks", stars: 1 },
  "The Barrens": { bg: "linear-gradient(160deg, oklch(0.28 0.09 50) 0%, oklch(0.20 0.07 45) 55%, oklch(0.14 0.04 40) 100%)", glow: "oklch(0.62 0.14 55)", accent: "oklch(0.68 0.14 60)", dangerLabel: "Moderate", dangerColor: "oklch(0.72 0.16 75)", biomeLabel: "Arid Plains", stars: 2 },
  "Stranglethorn Vale": { bg: "linear-gradient(160deg, oklch(0.18 0.07 148) 0%, oklch(0.13 0.05 158) 55%, oklch(0.10 0.03 168) 100%)", glow: "oklch(0.48 0.14 152)", accent: "oklch(0.52 0.14 148)", dangerLabel: "Dangerous", dangerColor: "oklch(0.68 0.18 50)", biomeLabel: "Tropical Jungle", stars: 3 },
  "Blackrock Depths": { bg: "linear-gradient(160deg, oklch(0.22 0.12 35) 0%, oklch(0.14 0.10 30) 55%, oklch(0.09 0.06 25) 100%)", glow: "oklch(0.62 0.18 40)", accent: "oklch(0.70 0.20 45)", dangerLabel: "Lethal", dangerColor: "oklch(0.72 0.22 35)", biomeLabel: "Molten Depths", stars: 5 },
};
const FALLBACK_THEME = ZONE_THEMES["Stranglethorn Vale"];

function explorePayloadToExploreResult(json: ExploreResultPayload): ExploreResult | null {
  if (!json.ok || !json.outcome) return null;
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const ts = new Date();
  const out = json.outcome;
  const reward =
    json.reward && (json.reward.xp != null || json.reward.gold != null)
      ? { xp: json.reward.xp, gold: json.reward.gold }
      : undefined;

  if (out.type === "enemy" || out.type === "boss") {
    const em = out.emoji ? `${out.emoji} ` : "";
    return {
      id,
      type: out.type,
      message:
        (json.message && json.message.trim()) ||
        (out.type === "boss" ? `A terrible foe reveals itself: ${out.name}!` : `${em}${out.name} bars your path!`.trim()),
      enemyName: out.name,
      enemyKey: out.key,
      isBoss: out.type === "boss",
      timestamp: ts,
      reward,
    };
  }

  if (json.npc?.npc_id) {
    const n = json.npc;
    return {
      id,
      type: "npc",
      message: (json.message && json.message.trim()) || "You cross paths with someone on the road.",
      npc: {
        id: String(n.npc_id),
        name: n.name || "Traveler",
        title: n.title || "",
        silhouette: "💬",
        discoveryQuote: n.discovery_hint,
        alreadyMet: Boolean(n.already_met),
      },
      reward,
      timestamp: ts,
    };
  }

  if (out.type === "loot") {
    return {
      id,
      type: "loot",
      message: (json.message && json.message.trim()) || "You uncover something worth taking with you.",
      reward,
      timestamp: ts,
    };
  }

  if (out.type === "safe") {
    return {
      id,
      type: "safe",
      message: (json.message && json.message.trim()) || "The surroundings settle; you move on without incident.",
      reward,
      timestamp: ts,
    };
  }

  return null;
}

function resolveTab(tab: string): AppTab | null {
  const t = String(tab || "").trim().toLowerCase();
  if (t === "hero") return "Hero";
  if (t === "explore") return "Explore";
  if (t === "quests") return "Quests";
  if (t === "combat") return "Combat";
  if (t === "market") return "Market";
  if (t === "arena") return "Arena";
  if (t === "progress" || t === "realm") return "Realm";
  return null;
}

function RelativeTime({ date }: { date: Date }) {
  const [, forceUpdate] = useState(0);
  useEffect(() => {
    const id = setInterval(() => forceUpdate((n) => n + 1), 10_000);
    return () => clearInterval(id);
  }, []);
  const diff = Math.round((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return <span>{diff}s ago</span>;
  if (diff < 3600) return <span>{Math.round(diff / 60)}m ago</span>;
  return <span>{Math.round(diff / 3600)}h ago</span>;
}

function CooldownRing({ totalSeconds, onComplete, size = 52 }: { totalSeconds: number; onComplete: () => void; size?: number }) {
  const [remaining, setRemaining] = useState(totalSeconds);
  const calledRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = remaining / totalSeconds;
  const dashOffset = circumference * (1 - progress);

  useEffect(() => {
    calledRef.current = false;
    setRemaining(totalSeconds);
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (!calledRef.current) {
            calledRef.current = true;
            onCompleteRef.current();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [totalSeconds]);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="oklch(0.28 0.025 75 / 0.4)" strokeWidth={4} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="oklch(0.74 0.13 80)"
          strokeWidth={4}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{ transition: "stroke-dashoffset 0.9s linear" }}
        />
      </svg>
      <span className="absolute font-serif text-sm font-bold text-gold tabular-nums">{remaining}</span>
    </div>
  );
}

function ResultPanel({
  result,
  onGoToCombat,
  onInteractNPC,
  isTimeline,
}: {
  result: ExploreResult;
  onGoToCombat: () => void;
  onInteractNPC: (npcId: string) => void;
  isTimeline?: boolean;
}) {
  const enemyArtSrc =
    (result.type === "enemy" || result.type === "boss") && result.enemyKey
      ? result.type === "boss" || result.isBoss
        ? `/bosses/${result.enemyKey}.png`
        : `/mobs/${result.enemyKey}.png`
      : null;
  const typeStyle = {
    enemy: "border-enemy-red/60 bg-enemy-red/5",
    boss: "border-boss-purple/70 bg-boss-purple/5",
    loot: "border-gold/50 bg-gold/5",
    safe: "border-safe-green/40 bg-safe-green/5",
    npc: "border-npc-teal/50 bg-npc-teal/5",
  }[result.type];
  return (
    <div className={cn("rounded border transition-all duration-300 px-3 py-3", typeStyle, isTimeline && "opacity-80")}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-serif text-[10px] tracking-[0.15em] font-bold uppercase text-gold">
          {result.type === "enemy" ? "ENCOUNTER" : result.type === "boss" ? "BOSS ENCOUNTER" : result.type === "npc" ? "NPC ENCOUNTERED" : result.type === "loot" ? "DISCOVERY" : "QUIET JOURNEY"}
        </span>
        <span className="text-[10px] text-muted-foreground/60 tabular-nums"><RelativeTime date={result.timestamp} /></span>
      </div>
      <p className={cn("text-foreground/85 leading-relaxed", isTimeline ? "text-xs" : "text-sm")}>{result.message}</p>
      {(result.type === "enemy" || result.type === "boss") && result.enemyName && (
        <div className="rounded px-2.5 py-2 mt-2 border border-white/15 flex items-center gap-2.5">
          {enemyArtSrc ? (
            <img
              src={enemyArtSrc}
              alt=""
              className="h-10 w-10 rounded bg-black/20 object-contain border border-white/10"
              onError={(e) => {
                // Hide broken image so we fall back to text-only.
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          ) : null}
          <div className="min-w-0">
            <p className="font-serif font-semibold text-sm text-foreground">{result.enemyName}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {result.enemyLevel != null ? <>Level {result.enemyLevel} · </> : null}
              {result.isBoss ? "World Boss" : "Enemy"}
            </p>
          </div>
        </div>
      )}
      {result.type === "npc" && result.npc && (
        <div className="space-y-2 mt-2">
          <div className="flex items-center gap-3 rounded px-2.5 py-2 border border-white/15">
            <div className="flex-shrink-0 rounded-full border border-npc-teal/40 bg-background flex items-center justify-center h-11 w-11 text-2xl">{result.npc.silhouette}</div>
            <div className="flex-1 min-w-0">
              <p className="font-serif font-semibold text-npc-teal text-sm">{result.npc.name}</p>
              <p className="text-[10px] text-muted-foreground italic">{result.npc.title}</p>
            </div>
          </div>
          {result.npc.discoveryQuote && <blockquote className="border-l-2 border-npc-teal/40 pl-3 italic text-xs text-muted-foreground leading-relaxed">{result.npc.discoveryQuote}</blockquote>}
        </div>
      )}
      {result.reward && (result.reward.xp || result.reward.gold) && (
        <div className="flex items-center gap-3 mt-2">
          {result.reward.xp ? <span className="flex items-center gap-1 text-xs font-semibold text-xp-blue"><Zap className="h-3 w-3" />+{result.reward.xp} XP</span> : null}
          {result.reward.gold ? <span className="flex items-center gap-1 text-xs font-semibold text-gold"><Coins className="h-3 w-3" />+{result.reward.gold}g</span> : null}
        </div>
      )}
      {!isTimeline && (
        <div className="flex items-center gap-2 pt-2">
          {(result.type === "enemy" || result.type === "boss") && (
            <button onClick={onGoToCombat} className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-serif font-bold tracking-wide uppercase bg-enemy-red text-foreground hover:bg-enemy-red/80 transition-all duration-150">
              <Sword className="h-3.5 w-3.5" />Go to Combat<ChevronRight className="h-3 w-3" />
            </button>
          )}
          {result.type === "npc" && result.npc && (
            <button onClick={() => onInteractNPC(result.npc!.id)} className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-serif font-bold tracking-wide uppercase bg-npc-teal/20 border border-npc-teal/50 text-npc-teal hover:bg-npc-teal/30 transition-all duration-150">
              <MessageCircle className="h-3.5 w-3.5" />{result.npc.alreadyMet ? "Talk Again" : "Interact"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ZoneMap({
  zones,
  currentZone,
  loreWindowTitle,
  onSelectZone,
  latestResult,
  exploring,
  combatStarting,
  npcInteracting,
  onGoToCombat,
  onInteractNPC,
}: {
  zones: Zone[];
  currentZone: Zone;
  loreWindowTitle?: string | null;
  onSelectZone: (zone: Zone) => void;
  latestResult?: ExploreResult | null;
  exploring?: boolean;
  combatStarting?: boolean;
  npcInteracting?: boolean;
  onGoToCombat: () => void;
  onInteractNPC: (id: string) => void;
}) {
  const [showResult, setShowResult] = useState(false);
  const [displayedResultId, setDisplayedResultId] = useState<string | null>(null);

  useEffect(() => {
    if (latestResult && latestResult.id !== displayedResultId) {
      setShowResult(true);
      setDisplayedResultId(latestResult.id);
    }
  }, [latestResult, displayedResultId]);

  const theme = ZONE_THEMES[currentZone?.name] || FALLBACK_THEME;
  const resCfg = useMemo(() => ({
    enemy: { icon: Sword, color: "oklch(0.52 0.22 25)", label: "ENCOUNTER", textClass: "text-red-400" },
    boss: { icon: Crown, color: "oklch(0.52 0.18 300)", label: "BOSS", textClass: "text-purple-400" },
    loot: { icon: Sparkles, color: "oklch(0.74 0.13 80)", label: "DISCOVERY", textClass: "text-yellow-400" },
    safe: { icon: Star, color: "oklch(0.55 0.14 150)", label: "SAFE JOURNEY", textClass: "text-green-400" },
    npc: { icon: MessageCircle, color: "oklch(0.58 0.12 195)", label: "NPC MET", textClass: "text-teal-400" },
  }), []);
  const currentCfg = latestResult ? resCfg[latestResult.type] : null;
  const ResIcon = currentCfg?.icon;

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-lg overflow-hidden border border-white/10">
      <div className="flex items-center gap-1.5 px-3 py-2 overflow-x-auto no-scrollbar border-b border-white/10 bg-black/30">
        {zones.map((zone) => {
          const isCurrent = zone.id === currentZone.id;
          return (
            <button
              key={zone.id}
              onClick={() => onSelectZone(zone)}
              title={`${zone.name} (Lv ${zone.levelRange[0]}-${zone.levelRange[1]})`}
              className={cn(
                "relative flex-shrink-0 flex flex-col items-center gap-0.5 rounded px-2 py-1.5 transition-all duration-200 text-[10px] font-serif",
                isCurrent ? "bg-gold/15 border border-gold/50 text-gold" : "border border-transparent text-muted-foreground hover:bg-white/5 hover:text-foreground",
              )}
            >
              <span className="text-base leading-none">{zone.emoji}</span>
              <span className="leading-none whitespace-nowrap max-w-[60px] truncate">{zone.name.split(" ")[0]}</span>
              {zone.bossAlive && <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500 border border-black animate-pulse" />}
            </button>
          );
        })}
      </div>

      <div className="relative min-h-0 flex-1" style={{ background: theme.bg, minHeight: "min(44vh, 580px)" }}>
        {currentZone.mapImageUrl ? (
          <img
            src={currentZone.mapImageUrl}
            alt=""
            className="absolute inset-0 h-full w-full object-cover opacity-[0.42] pointer-events-none"
            loading="lazy"
            decoding="async"
          />
        ) : null}
        <div className="absolute inset-0 opacity-20 animate-parallax pointer-events-none" style={{ background: `radial-gradient(ellipse 60% 50% at 50% 40%, ${theme.glow}, transparent)` }} />
        <div className="absolute top-0 left-0 right-0 h-12 bg-gradient-to-b from-black/50 to-transparent pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-black/70 to-transparent pointer-events-none" />

        {!exploring && !showResult && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center">
            <div className="text-5xl animate-float leading-none">{currentZone.emoji}</div>
            <div>
              <div className="font-serif text-sm font-bold text-foreground tracking-wide">{currentZone.name}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5 tracking-widest uppercase">{theme.biomeLabel}</div>
            </div>
            <div className="flex items-center gap-1 mt-1">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skull key={i} className={cn("h-3 w-3 transition-colors", i < theme.stars ? "opacity-100" : "opacity-15")} style={{ color: i < theme.stars ? theme.dangerColor : undefined }} />
              ))}
              <span className="ml-1.5 text-[10px] font-serif uppercase tracking-wider" style={{ color: theme.dangerColor }}>{theme.dangerLabel}</span>
            </div>
            {currentZone.bossAlive && (
              <div className="flex items-center gap-1.5 mt-1 rounded px-2 py-0.5 bg-red-950/70 border border-red-500/40">
                <Crown className="h-3 w-3 text-red-400 animate-pulse" />
                <span className="text-[10px] font-serif text-red-300 uppercase tracking-wide">World Boss Active</span>
              </div>
            )}
            {loreWindowTitle ? (
              <div className="flex items-center gap-1.5 mt-1 rounded px-2 py-0.5 bg-purple-950/70 border border-purple-400/40">
                <Crown className="h-3 w-3 text-purple-300 animate-pulse" />
                <span className="text-[10px] font-serif text-purple-200 uppercase tracking-wide">{loreWindowTitle}</span>
              </div>
            ) : null}
            {currentZone.regionHint && <p className="text-[10px] text-muted-foreground/70 italic max-w-[220px] leading-relaxed mt-1">{currentZone.regionHint}</p>}
          </div>
        )}

        {exploring && !showResult && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/50">
            <div className="w-10 h-10 rounded-full border-2 animate-spin" style={{ borderColor: `${theme.accent}40`, borderTopColor: theme.accent }} />
            <div className="font-serif text-sm tracking-[0.2em] uppercase" style={{ color: theme.accent }}>Scouting...</div>
            <div className="text-[11px] text-muted-foreground">Venturing into the unknown</div>
          </div>
        )}

        {showResult && latestResult && currentCfg && ResIcon && (
          <div className="absolute inset-0 animate-backdrop">
            <div className="absolute inset-0 opacity-25 pointer-events-none" style={{ background: `radial-gradient(ellipse at center, ${currentCfg.color}, transparent 70%)` }} />
            <div className="relative h-full flex flex-col items-center justify-center px-4 gap-2.5 text-center">
              <div className="w-14 h-14 rounded-full flex items-center justify-center border-2 animate-silhouette" style={{ borderColor: currentCfg.color, background: `${currentCfg.color}20`, boxShadow: `0 0 24px ${currentCfg.color}50` }}>
                <ResIcon className="w-6 h-6" style={{ color: currentCfg.color }} />
              </div>
              <div className="font-serif text-[10px] tracking-[0.3em] uppercase font-bold animate-text-reveal" style={{ color: currentCfg.color }}>{currentCfg.label}</div>
              {(latestResult.type === "enemy" || latestResult.type === "boss") && latestResult.enemyName && (
                <div className="animate-text-reveal">
                  <div className="font-serif text-base font-bold text-foreground">{latestResult.enemyName}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">
                    {latestResult.enemyLevel != null ? `Level ${latestResult.enemyLevel} · ` : null}
                    {latestResult.type === "boss" ? "World Boss" : "Enemy"}
                  </div>
                </div>
              )}
              {latestResult.type === "npc" && latestResult.npc && (
                <div className="animate-text-reveal">
                  <div className="font-serif text-base font-bold text-foreground">{latestResult.npc.name}</div>
                  <div className="text-[10px] text-muted-foreground italic">{latestResult.npc.title}</div>
                </div>
              )}
              <p className="text-[11px] text-foreground/75 max-w-[240px] leading-relaxed animate-text-reveal">{latestResult.message}</p>
              {latestResult.reward && (latestResult.reward.xp || latestResult.reward.gold) && (
                <div className="flex items-center gap-3 animate-text-reveal">
                  {latestResult.reward.xp ? <span className="flex items-center gap-1 text-xs font-bold text-blue-400"><Zap className="w-3 h-3" />+{latestResult.reward.xp} XP</span> : null}
                  {latestResult.reward.gold ? <span className="flex items-center gap-1 text-xs font-bold text-yellow-400"><Coins className="w-3 h-3" />+{latestResult.reward.gold}g</span> : null}
                </div>
              )}
              <div className="flex items-center gap-2 animate-text-reveal">
                {(latestResult.type === "enemy" || latestResult.type === "boss") && (
                  <button
                    type="button"
                    disabled={combatStarting}
                    onClick={onGoToCombat}
                    className="flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-serif font-bold tracking-wide uppercase text-white transition-all disabled:opacity-50 disabled:cursor-wait"
                    style={{ background: currentCfg.color, boxShadow: `0 0 10px ${currentCfg.color}70` }}
                  >
                    {combatStarting ? (
                      <span className="inline-block h-3 w-3 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                    ) : (
                      <Sword className="w-3 h-3" />
                    )}
                    {combatStarting ? "Starting…" : "Combat"}
                    {!combatStarting ? <ChevronRight className="w-3 h-3" /> : null}
                  </button>
                )}
                {latestResult.type === "npc" && latestResult.npc && (
                  <button
                    type="button"
                    disabled={npcInteracting}
                    onClick={() => onInteractNPC(latestResult.npc!.id)}
                    className="flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-serif font-bold tracking-wide uppercase text-teal-300 border border-teal-500/50 bg-teal-950/60 disabled:opacity-50 disabled:cursor-wait"
                  >
                    {npcInteracting ? (
                      <span className="inline-block h-3 w-3 rounded-full border-2 border-teal-400/40 border-t-teal-200 animate-spin" />
                    ) : (
                      <MessageCircle className="w-3 h-3" />
                    )}
                    {npcInteracting ? "…" : latestResult.npc.alreadyMet ? "Talk Again" : "Interact"}
                  </button>
                )}
                <button onClick={() => setShowResult(false)} className="rounded px-3 py-1.5 text-xs text-muted-foreground border border-white/10 bg-black/50 hover:bg-black/70 transition-all">
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ExploreTab() {
  const { map, explore, travel, npcInteract, accessToken, startCombat, setQuickFightIntent, lastExplore } = useGameSession();
  const [currentZoneId, setCurrentZoneId] = useState(EXPLORE_ZONES[0].id);
  const [travelTargetId, setTravelTargetId] = useState(EXPLORE_ZONES[0].id);
  const [isTravelling, setIsTravelling] = useState(false);
  const [exploring, setExploring] = useState(false);
  const [cooldownActive, setCooldownActive] = useState(false);
  const [cooldownSeconds, setCooldownSeconds] = useState(30);
  const [cooldownKey, setCooldownKey] = useState(0);
  const [results, setResults] = useState<ExploreResult[]>([]);
  const [latestId, setLatestId] = useState<string | null>(null);
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [combatStarting, setCombatStarting] = useState(false);
  const [npcInteracting, setNpcInteracting] = useState(false);
  const topRef = useRef<HTMLDivElement>(null);

  const latestResult = results.find((r) => r.id === latestId) || null;
  const timelineResults = latestResult ? results.filter((r) => r.id !== latestResult.id) : results;

  const zones = useMemo(() => {
    const apiZones = map?.zones;
    if (!apiZones?.length) return EXPLORE_ZONES;
    const byKey = new Map(apiZones.map((z) => [z.key, z]));
    return EXPLORE_ZONES.map((z) => {
      const s = byKey.get(z.id);
      if (!s) return z;
      return {
        ...z,
        playersNearby: typeof s.players === "number" ? s.players : z.playersNearby,
        bossAlive: typeof s.boss_alive === "boolean" ? s.boss_alive : z.bossAlive,
        description: (typeof s.description === "string" && s.description.trim()) || z.description,
      };
    });
  }, [map?.zones]);

  const currentZone = useMemo(
    () => zones.find((z) => z.id === currentZoneId) ?? EXPLORE_ZONES[0],
    [zones, currentZoneId],
  );
  const travelTarget = useMemo(
    () => zones.find((z) => z.id === travelTargetId) ?? EXPLORE_ZONES[0],
    [zones, travelTargetId],
  );

  const activeLoreWindow = useMemo(() => {
    const wins = map?.world_boss_windows;
    if (!wins?.length) return null;
    return wins.find((w) => w.zone_key === currentZoneId) ?? null;
  }, [map?.world_boss_windows, currentZoneId]);

  useEffect(() => {
    const key = map?.current_zone?.trim();
    if (!key || !EXPLORE_ZONES.some((z) => z.id === key)) return;
    setCurrentZoneId(key);
    setTravelTargetId(key);
  }, [map?.current_zone]);

  const setTab = useCallback((tab: string) => {
    const resolved = resolveTab(tab);
    if (!resolved) return;
    window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: resolved }));
  }, []);

  const handleTravel = useCallback(async () => {
    if (travelTargetId === currentZoneId) return;
    if (!accessToken) {
      toast.error("Connect with Discord to travel.");
      return;
    }
    setIsTravelling(true);
    try {
      const r = await travel(travelTargetId);
      if (!r.ok) toast.error(r.message || "Travel failed");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setIsTravelling(false);
    }
  }, [travelTargetId, currentZoneId, accessToken, travel]);

  const handleNpcInteract = useCallback(
    async (npcId: string) => {
      setNpcInteracting(true);
      try {
        const r = await npcInteract(npcId);
        if (!r.ok) {
          toast.error(r.error || r.message || "Could not interact");
          return;
        }
        if (r.openedQuestOffer || r.openedCompletion) {
          if (r.message) toast.success(r.message);
          return;
        }
        toast.info(r.message || "Nothing new from this NPC right now.", {
          description:
            "Often you already finished their line, need a higher level, or must advance elsewhere. Check the Quests tab for your log.",
        });
      } finally {
        setNpcInteracting(false);
      }
    },
    [npcInteract],
  );

  const handleGoToCombat = useCallback(async () => {
    let enemyKey: string | undefined =
      latestResult && (latestResult.type === "enemy" || latestResult.type === "boss")
        ? latestResult.enemyKey
        : undefined;
    const le = lastExplore?.outcome;
    if (!enemyKey && le && (le.type === "enemy" || le.type === "boss") && "key" in le && typeof le.key === "string") {
      enemyKey = le.key;
    }
    if (!enemyKey?.trim()) {
      toast.error("No encounter to fight. Explore again to roll a foe.");
      setTab("Combat");
      return;
    }
    if (!accessToken) {
      toast.error("Not connected.");
      return;
    }
    setCombatStarting(true);
    try {
      setQuickFightIntent({ kind: "enemy", enemyKey: enemyKey.trim() });
      const r = await startCombat({ kind: "zone", enemyKey: enemyKey.trim() });
      if (r.ok && r.state) {
        setTab("Combat");
        toast.success("Combat started.", { description: "Switched to Combat tab." });
        return;
      }
      toast.error(r.message || "Could not start combat.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setCombatStarting(false);
    }
  }, [latestResult, lastExplore, accessToken, setQuickFightIntent, startCombat, setTab]);

  const handleExplore = useCallback(async () => {
    if (cooldownActive || exploring) return;
    if (!accessToken) {
      toast.error("Connect with Discord to explore.");
      return;
    }
    setExploring(true);
    try {
      const json = await explore();
      if (!json.ok) {
        if (json.error === "cooldown" && json.cooldown_s != null) {
          setCooldownSeconds(Math.max(1, Math.ceil(json.cooldown_s)));
          setCooldownKey((k) => k + 1);
          setCooldownActive(true);
        } else {
          toast.error(json.message || json.error || "Explore failed");
        }
        return;
      }
      const r = explorePayloadToExploreResult(json);
      if (r) {
        setResults((prev) => [r, ...prev].slice(0, 20));
        setLatestId(r.id);
      }
      const cd = json.cooldown_s != null ? Math.max(1, Math.ceil(json.cooldown_s)) : 30;
      setCooldownSeconds(cd);
      setCooldownKey((k) => k + 1);
      setCooldownActive(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setExploring(false);
    }
  }, [accessToken, cooldownActive, exploring, explore]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-0" ref={topRef}>
      <div className="flex shrink-0 items-center gap-2.5 border-b border-panel-border/50 px-4 py-2.5">
        <Compass className="h-4 w-4 text-gold" />
        <h2 className="font-serif text-sm font-semibold uppercase tracking-[0.2em] text-gold">Explore</h2>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-3">
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="flex shrink-0 items-center gap-2">
            <span className="flex items-center gap-1.5 font-serif text-[10px] uppercase tracking-[0.2em] text-gold/60">
              <MapPin className="h-3 w-3" />
              Zone Map
            </span>
            <div className="h-px flex-1 bg-panel-border/50" />
          </div>
          <ZoneMap
            zones={zones}
            currentZone={currentZone}
            loreWindowTitle={activeLoreWindow?.title ?? null}
            onSelectZone={(z) => setTravelTargetId(z.id)}
            latestResult={latestResult}
            exploring={exploring}
            combatStarting={combatStarting}
            npcInteracting={npcInteracting}
            onGoToCombat={() => void handleGoToCombat()}
            onInteractNPC={(id) => void handleNpcInteract(id)}
          />
          {travelTarget.id !== currentZone.id ? (
            <button
              onClick={() => void handleTravel()}
              disabled={isTravelling || !accessToken}
              className="mt-3 w-full flex items-center justify-center gap-2 rounded border border-gold/50 bg-gold/10 hover:bg-gold/20 text-gold font-serif text-xs font-bold tracking-[0.15em] uppercase py-2.5 transition-all duration-150 disabled:opacity-50"
            >
              <Navigation className="h-3.5 w-3.5" />
              {isTravelling ? "Travelling..." : `Travel to ${travelTarget.name}`}
            </button>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-3 bg-panel-bg border border-gold/40 rounded px-4 py-3.5 panel-inset shadow-[0_0_16px_oklch(0.74_0.13_80/0.2)]">
          {cooldownActive ? (
            <CooldownRing key={cooldownKey} totalSeconds={cooldownSeconds} onComplete={() => setCooldownActive(false)} />
          ) : (
            <button
              type="button"
              onClick={() => void handleExplore()}
              disabled={exploring || !accessToken}
              title={!accessToken ? "Open this Activity from Discord while logged in." : undefined}
              className={cn(
                "relative flex-shrink-0 rounded border px-6 py-2.5 font-serif text-sm font-bold tracking-[0.15em] uppercase transition-all duration-200",
                exploring || !accessToken
                  ? "border-gold/30 bg-gold/5 text-gold/50 cursor-not-allowed"
                  : "border-gold bg-gold/20 text-gold hover:bg-gold/30 hover:shadow-[0_0_16px_oklch(0.74_0.13_80/0.4)] animate-pulse-gold",
              )}
            >
              {exploring ? (
                <span className="flex items-center gap-2">
                  <span className="inline-block h-3.5 w-3.5 rounded-full border-2 border-gold/40 border-t-gold animate-spin" />
                  Scouting...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Compass className="h-5 w-5" />
                  Explore
                </span>
              )}
            </button>
          )}

          <div className="text-xs text-muted-foreground/70 leading-relaxed">
            {cooldownActive ? (
              "Catching your breath before the next foray…"
            ) : exploring ? (
              "Calling the server…"
            ) : !accessToken ? (
              "Sign in through Discord to explore and travel."
            ) : (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-gold/40" />
                Cooldown is set by the server (longer after enemies or bosses).
              </span>
            )}
          </div>
        </div>

        {timelineResults.length > 0 ? (
          <div className="shrink-0">
            <button className="w-full flex items-center gap-2 mb-2 group" onClick={() => setTimelineOpen((o) => !o)}>
              <span className="font-serif text-[10px] tracking-[0.2em] uppercase text-gold/60 flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                Recent Explorations ({timelineResults.length})
              </span>
              <div className="flex-1 h-px bg-panel-border/50" />
              {timelineOpen ? <ChevronUp className="h-3.5 w-3.5 text-gold/40 group-hover:text-gold/70 transition-colors" /> : <ChevronDown className="h-3.5 w-3.5 text-gold/40 group-hover:text-gold/70 transition-colors" />}
            </button>
            {timelineOpen ? (
              <div className="relative space-y-2 pl-4">
                <div className="absolute left-1.5 top-0 bottom-0 w-px bg-panel-border/50" />
                {timelineResults.map((r, i) => (
                  <div key={r.id} className="relative" style={{ animationDelay: `${i * 60}ms` }}>
                    <div className="absolute -left-2.5 top-3 h-2 w-2 rounded-full border border-panel-border bg-background" />
                    <ResultPanel
                      result={r}
                      onGoToCombat={() => void handleGoToCombat()}
                      onInteractNPC={(id) => void handleNpcInteract(id)}
                      isTimeline
                    />
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="flex shrink-0 items-start gap-2.5 rounded border border-gold/15 bg-gold/5 px-3 py-2.5">
          <Swords className="h-3.5 w-3.5 flex-shrink-0 text-gold/50 mt-0.5" />
          <p className="text-[11px] text-gold/60 leading-relaxed italic">
            Quests often start or advance after meeting NPCs while exploring. Check the <span className="text-gold/80 not-italic font-semibold">Quests</span> tab after any NPC encounter.
          </p>
        </div>
      </div>
    </div>
  );
}
