import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  Shield,
  ScrollText,
  Bed,
  Package,
  ShoppingBag,
  Trophy,
} from "lucide-react";

type Faction = "alliance" | "horde" | "neutral" | "hostile";
type OutcomeType = "enemy" | "boss" | "loot" | "safe" | "npc";
type AppTab = "Hero" | "Explore" | "Quests" | "Combat" | "Market" | "Arena" | "Progress";

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
  enemyLevel?: number;
  isBoss?: boolean;
  timestamp: Date;
};

const ZONES: Zone[] = [
  { id: "elwynn", name: "Elwynn Forest", emoji: "🌲", levelRange: [1, 10], faction: "alliance", playersNearby: 4, bossAlive: false, description: "Rolling hills of ancient oak shelter both wanderers and wolves." },
  { id: "stranglethorn", name: "Stranglethorn Vale", emoji: "🌴", levelRange: [25, 45], faction: "neutral", playersNearby: 1, bossAlive: true, description: "Thick jungle canopy hides ruins older than memory — and the gangs that claim them.", regionHint: "The Bloodsail Buccaneers grow bolder near Booty Bay." },
  { id: "plaguelands", name: "Eastern Plaguelands", emoji: "💀", levelRange: [50, 60], faction: "hostile", playersNearby: 0, bossAlive: true, description: "The Scourge's blight bleeds from every cracked stone of this cursed land." },
  { id: "barrens", name: "The Barrens", emoji: "🏜️", levelRange: [10, 25], faction: "horde", playersNearby: 7, bossAlive: false, description: "Vast sunburned plains where centaur outriders test the courage of every traveller." },
  { id: "winterspring", name: "Winterspring", emoji: "❄️", levelRange: [55, 60], faction: "neutral", playersNearby: 2, bossAlive: false, description: "Frost-choked valleys whisper of lost knowledge." },
  { id: "silithus", name: "Silithus", emoji: "🐛", levelRange: [55, 60], faction: "hostile", playersNearby: 0, bossAlive: true, description: "The Old God's dream festers beneath these sands." },
];

const SAMPLE_RESULTS: ExploreResult[] = [
  { id: "r1", type: "enemy", message: "A Bloodsail Corsair springs from the undergrowth, cutlass drawn!", enemyName: "Bloodsail Corsair", enemyLevel: 38, isBoss: false, timestamp: new Date(Date.now() - 90_000) },
  { id: "r2", type: "safe", message: "You follow an overgrown path to a crumbling stone vista. A pleasant silence settles over you.", reward: { xp: 120 }, timestamp: new Date(Date.now() - 210_000) },
  {
    id: "r3",
    type: "npc",
    message: "A weathered figure crouches by a fire, studying a frayed map.",
    npc: { id: "npc_grol", name: "Grol the Wanderer", title: "Disgraced Scout", silhouette: "🧙", discoveryQuote: "\"These routes have not been safe for months.\"", alreadyMet: false },
    reward: { xp: 80 },
    timestamp: new Date(Date.now() - 360_000),
  },
];

const ZONE_THEMES: Record<string, { bg: string; glow: string; accent: string; dangerLabel: string; dangerColor: string; biomeLabel: string; stars: number }> = {
  "Elwynn Forest": { bg: "linear-gradient(160deg, oklch(0.20 0.07 145) 0%, oklch(0.14 0.05 155) 55%, oklch(0.10 0.03 165) 100%)", glow: "oklch(0.50 0.14 148)", accent: "oklch(0.55 0.14 150)", dangerLabel: "Beginner", dangerColor: "oklch(0.62 0.16 145)", biomeLabel: "Temperate Forest", stars: 1 },
  "The Barrens": { bg: "linear-gradient(160deg, oklch(0.28 0.09 50) 0%, oklch(0.20 0.07 45) 55%, oklch(0.14 0.04 40) 100%)", glow: "oklch(0.62 0.14 55)", accent: "oklch(0.68 0.14 60)", dangerLabel: "Moderate", dangerColor: "oklch(0.72 0.16 75)", biomeLabel: "Arid Plains", stars: 2 },
  "Stranglethorn Vale": { bg: "linear-gradient(160deg, oklch(0.18 0.07 148) 0%, oklch(0.13 0.05 158) 55%, oklch(0.10 0.03 168) 100%)", glow: "oklch(0.48 0.14 152)", accent: "oklch(0.52 0.14 148)", dangerLabel: "Dangerous", dangerColor: "oklch(0.68 0.18 50)", biomeLabel: "Tropical Jungle", stars: 3 },
  "Eastern Plaguelands": { bg: "linear-gradient(160deg, oklch(0.16 0.06 280) 0%, oklch(0.12 0.05 290) 55%, oklch(0.09 0.03 300) 100%)", glow: "oklch(0.45 0.15 290)", accent: "oklch(0.52 0.18 300)", dangerLabel: "Very Dangerous", dangerColor: "oklch(0.60 0.22 25)", biomeLabel: "Cursed Wasteland", stars: 4 },
  Winterspring: { bg: "linear-gradient(160deg, oklch(0.20 0.04 225) 0%, oklch(0.15 0.03 230) 55%, oklch(0.10 0.02 240) 100%)", glow: "oklch(0.55 0.08 225)", accent: "oklch(0.60 0.10 220)", dangerLabel: "Deadly", dangerColor: "oklch(0.62 0.14 220)", biomeLabel: "Frozen Tundra", stars: 4 },
  Silithus: { bg: "linear-gradient(160deg, oklch(0.22 0.08 75) 0%, oklch(0.16 0.07 65) 55%, oklch(0.11 0.04 60) 100%)", glow: "oklch(0.58 0.14 70)", accent: "oklch(0.62 0.15 72)", dangerLabel: "Lethal", dangerColor: "oklch(0.55 0.22 25)", biomeLabel: "Ancient Desert", stars: 5 },
};
const FALLBACK_THEME = ZONE_THEMES["Stranglethorn Vale"];

function generateResult(): ExploreResult {
  const roll = Math.random();
  const id = Math.random().toString(36).slice(2);
  const ts = new Date();
  if (roll < 0.2) return { id, type: "boss", message: "The earth trembles. A colossal silhouette blocks the sun.", enemyName: "Gorgothar the Unburied", enemyLevel: 45, isBoss: true, timestamp: ts };
  if (roll < 0.45) return { id, type: "enemy", message: "Three Bloodsail Raiders drop from the canopy, weapons drawn.", enemyName: "Bloodsail Raider", enemyLevel: 36, isBoss: false, timestamp: ts };
  if (roll < 0.6) return { id, type: "npc", message: "You nearly trip over a crouched figure in worn leather armour.", npc: { id: "npc_mira", name: "Mira Flinthand", title: "Tracker & Scout", silhouette: "🏹", discoveryQuote: "\"There's a cave half a league north.\"", alreadyMet: Math.random() > 0.7 }, reward: { xp: 95 }, timestamp: ts };
  if (roll < 0.75) return { id, type: "loot", message: "Beneath a moss-draped stone you find a leather satchel.", reward: { xp: 60, gold: 12 }, timestamp: ts };
  return { id, type: "safe", message: "The path winds along a ridge overlooking the whole vale.", reward: { xp: 40 }, timestamp: ts };
}

function resolveTab(tab: string): AppTab | null {
  const t = String(tab || "").trim().toLowerCase();
  if (t === "hero") return "Hero";
  if (t === "explore") return "Explore";
  if (t === "quests") return "Quests";
  if (t === "combat") return "Combat";
  if (t === "market") return "Market";
  if (t === "arena") return "Arena";
  if (t === "progress") return "Progress";
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
            onComplete();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [totalSeconds, onComplete]);

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
      {(result.type === "enemy" || result.type === "boss") && (
        <div className="rounded px-2.5 py-2 mt-2 border border-white/15">
          <p className="font-serif font-semibold text-sm text-foreground">{result.enemyName}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">Level {result.enemyLevel} · {result.isBoss ? "World Boss" : "Enemy"}</p>
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

const ACTIVITY_TILES = [
  { id: "encounters", icon: Sword, label: "Encounters", tab: "combat", badgeType: "cooldown" as const },
  { id: "quests", icon: ScrollText, label: "Quests & NPCs", tab: "quests", badgeType: "quests" as const },
  { id: "dungeons", icon: Shield, label: "Dungeons", tab: "combat", badgeType: "boss" as const },
  { id: "rest", icon: Bed, label: "Rest", tab: "hero", badgeType: "static" as const, staticBadge: "+HP" },
  { id: "materials", icon: Package, label: "Materials", tab: "market", badgeType: "static" as const, staticBadge: "3" },
  { id: "market", icon: ShoppingBag, label: "Market", tab: "market" },
  { id: "arena", icon: Trophy, label: "Arena", tab: "arena", badgeType: "static" as const, staticBadge: "PvP" },
];

function ZoneMap({
  zones,
  currentZone,
  onSelectZone,
  latestResult,
  exploring,
  onGoToCombat,
  onInteractNPC,
  cooldownActive,
  onTabChange,
}: {
  zones: Zone[];
  currentZone: Zone;
  onSelectZone: (zone: Zone) => void;
  latestResult?: ExploreResult | null;
  exploring?: boolean;
  onGoToCombat: () => void;
  onInteractNPC: (id: string) => void;
  cooldownActive?: boolean;
  onTabChange: (tab: string) => void;
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

  function getBadge(tile: typeof ACTIVITY_TILES[number]): string | null {
    if (tile.badgeType === "cooldown") return cooldownActive ? "CD" : null;
    if (tile.badgeType === "boss") return currentZone.bossAlive ? "!" : null;
    if (tile.badgeType === "quests") return "2";
    if (tile.badgeType === "static") return tile.staticBadge ?? null;
    return null;
  }

  return (
    <div className="flex flex-col rounded-lg overflow-hidden border border-white/10">
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

      <div className="relative flex-1" style={{ background: theme.bg, minHeight: "220px" }}>
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
                  <div className="text-[10px] text-muted-foreground mt-0.5">Level {latestResult.enemyLevel}{latestResult.type === "boss" ? " - World Boss" : ""}</div>
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
                  <button onClick={onGoToCombat} className="flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-serif font-bold tracking-wide uppercase text-white transition-all" style={{ background: currentCfg.color, boxShadow: `0 0 10px ${currentCfg.color}70` }}>
                    <Sword className="w-3 h-3" />Combat<ChevronRight className="w-3 h-3" />
                  </button>
                )}
                {latestResult.type === "npc" && latestResult.npc && (
                  <button onClick={() => onInteractNPC(latestResult.npc!.id)} className="flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-serif font-bold tracking-wide uppercase text-teal-300 border border-teal-500/50 bg-teal-950/60">
                    <MessageCircle className="w-3 h-3" />{latestResult.npc.alreadyMet ? "Talk Again" : "Interact"}
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

      <div className="bg-black/40 border-t border-white/10 px-3 py-2.5">
        <div className="font-serif text-[9px] tracking-[0.25em] uppercase text-muted-foreground/60 mb-2">World Activity</div>
        <div className="grid grid-cols-7 gap-1">
          {ACTIVITY_TILES.map((tile) => {
            const Icon = tile.icon;
            const badge = getBadge(tile);
            return (
              <button
                key={tile.id}
                onClick={() => tile.tab && onTabChange(tile.tab)}
                title={tile.label}
                className="relative flex flex-col items-center gap-1 rounded py-2 px-1 bg-white/[0.04] border border-white/[0.07] hover:bg-white/[0.08] hover:border-gold/30 transition-all duration-150 group"
              >
                <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover:text-gold transition-colors" />
                <span className="text-[8px] text-muted-foreground/70 group-hover:text-gold/80 transition-colors leading-none text-center">{tile.label.split(" ")[0]}</span>
                {badge ? <span className="absolute -top-1 -right-1 min-w-[14px] h-3.5 px-0.5 rounded-full bg-gold text-[8px] font-bold text-black flex items-center justify-center leading-none">{badge}</span> : null}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function ExploreTab() {
  const [currentZone, setCurrentZone] = useState<Zone>(ZONES[1]);
  const [travelTarget, setTravelTarget] = useState<Zone>(ZONES[1]);
  const [isTravelling, setIsTravelling] = useState(false);
  const [exploring, setExploring] = useState(false);
  const [cooldownActive, setCooldownActive] = useState(false);
  const [results, setResults] = useState<ExploreResult[]>(SAMPLE_RESULTS);
  const [latestId, setLatestId] = useState<string | null>(null);
  const [timelineOpen, setTimelineOpen] = useState(false);
  const topRef = useRef<HTMLDivElement>(null);

  const setTab = (tab: string) => {
    const resolved = resolveTab(tab);
    if (!resolved) return;
    window.dispatchEvent(new CustomEvent("game:setActiveTab", { detail: resolved }));
  };

  const handleTravel = useCallback(() => {
    if (travelTarget.id === currentZone.id) return;
    setIsTravelling(true);
    setTimeout(() => {
      setCurrentZone(travelTarget);
      setIsTravelling(false);
    }, 1200);
  }, [travelTarget, currentZone]);

  const handleExplore = useCallback(() => {
    if (cooldownActive || exploring) return;
    setExploring(true);
    setTimeout(() => {
      const r = generateResult();
      setResults((prev) => [r, ...prev].slice(0, 20));
      setLatestId(r.id);
      setExploring(false);
      setCooldownActive(true);
    }, 900);
  }, [cooldownActive, exploring]);

  const latestResult = results.find((r) => r.id === latestId) || null;
  const timelineResults = latestResult ? results.filter((r) => r.id !== latestResult.id) : results;

  return (
    <div className="flex flex-col gap-0 h-full" ref={topRef}>
      <div className="flex items-center gap-2.5 px-4 pt-4 pb-3 border-b border-panel-border/50">
        <Compass className="h-4 w-4 text-gold" />
        <h2 className="font-serif text-sm tracking-[0.2em] uppercase text-gold font-semibold">Explore</h2>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">

        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="font-serif text-[10px] tracking-[0.2em] uppercase text-gold/60 flex items-center gap-1.5"><MapPin className="h-3 w-3" />Zone Map</span>
            <div className="flex-1 h-px bg-panel-border/50" />
          </div>
          <ZoneMap
            zones={ZONES}
            currentZone={currentZone}
            onSelectZone={setTravelTarget}
            latestResult={latestResult}
            exploring={exploring}
            onGoToCombat={() => setTab("combat")}
            onInteractNPC={() => setTab("quests")}
            cooldownActive={cooldownActive}
            onTabChange={setTab}
          />
          {travelTarget.id !== currentZone.id ? (
            <button
              onClick={handleTravel}
              disabled={isTravelling}
              className="mt-3 w-full flex items-center justify-center gap-2 rounded border border-gold/50 bg-gold/10 hover:bg-gold/20 text-gold font-serif text-xs font-bold tracking-[0.15em] uppercase py-2.5 transition-all duration-150 disabled:opacity-50"
            >
              <Navigation className="h-3.5 w-3.5" />
              {isTravelling ? "Travelling..." : `Travel to ${travelTarget.name}`}
            </button>
          ) : null}
        </div>

        <div className="flex items-center gap-3 bg-panel-bg border border-gold/40 rounded px-4 py-3.5 panel-inset shadow-[0_0_16px_oklch(0.74_0.13_80/0.2)]">
          {cooldownActive ? (
            <CooldownRing totalSeconds={30} onComplete={() => setCooldownActive(false)} />
          ) : (
            <button
              onClick={handleExplore}
              disabled={exploring}
              className={cn(
                "relative flex-shrink-0 rounded border px-6 py-2.5 font-serif text-sm font-bold tracking-[0.15em] uppercase transition-all duration-200",
                exploring ? "border-gold/30 bg-gold/5 text-gold/50 cursor-wait" : "border-gold bg-gold/20 text-gold hover:bg-gold/30 hover:shadow-[0_0_16px_oklch(0.74_0.13_80/0.4)] animate-pulse-gold",
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
            {cooldownActive ? "Catching your breath before the next foray..." : exploring ? "Venturing into the unknown..." : <span className="flex items-center gap-1"><Clock className="h-3 w-3 text-gold/40" />~30s cooldown between explorations</span>}
          </div>
        </div>

        {timelineResults.length > 0 ? (
          <div>
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
                    <ResultPanel result={r} onGoToCombat={() => setTab("combat")} onInteractNPC={() => setTab("quests")} isTimeline />
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="flex items-start gap-2.5 rounded border border-gold/15 bg-gold/5 px-3 py-2.5">
          <Swords className="h-3.5 w-3.5 flex-shrink-0 text-gold/50 mt-0.5" />
          <p className="text-[11px] text-gold/60 leading-relaxed italic">
            Quests often start or advance after meeting NPCs while exploring. Check the <span className="text-gold/80 not-italic font-semibold">Quests</span> tab after any NPC encounter.
          </p>
        </div>
      </div>
    </div>
  );
}
