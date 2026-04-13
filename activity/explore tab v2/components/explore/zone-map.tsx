'use client';

import React, { useEffect, useState } from 'react';
import { Zone, ExploreResult } from '@/lib/mmo-data';
import {
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
} from 'lucide-react';
import { cn } from '@/lib/utils';

/* ─────────────────────────── types ─────────────────────────── */

interface ZoneMapProps {
  zones: Zone[];
  currentZone: Zone;
  onSelectZone: (zone: Zone) => void;
  latestResult?: ExploreResult | null;
  exploring?: boolean;
  onGoToCombat?: () => void;
  onInteractNPC?: (id: string) => void;
  cooldownActive?: boolean;
  className?: string;
  onTabChange?: (tab: string) => void;
}

/* ─────────────────────────── zone themes ─────────────────────────── */

const ZONE_THEMES: Record<string, {
  bg: string;
  glow: string;
  accent: string;
  dangerLabel: string;
  dangerColor: string;
  biomeLabel: string;
  stars: number; // 1–5 danger stars
}> = {
  'Elwynn Forest': {
    bg: 'linear-gradient(160deg, oklch(0.20 0.07 145) 0%, oklch(0.14 0.05 155) 55%, oklch(0.10 0.03 165) 100%)',
    glow: 'oklch(0.50 0.14 148)',
    accent: 'oklch(0.55 0.14 150)',
    dangerLabel: 'Beginner',
    dangerColor: 'oklch(0.62 0.16 145)',
    biomeLabel: 'Temperate Forest',
    stars: 1,
  },
  'The Barrens': {
    bg: 'linear-gradient(160deg, oklch(0.28 0.09 50) 0%, oklch(0.20 0.07 45) 55%, oklch(0.14 0.04 40) 100%)',
    glow: 'oklch(0.62 0.14 55)',
    accent: 'oklch(0.68 0.14 60)',
    dangerLabel: 'Moderate',
    dangerColor: 'oklch(0.72 0.16 75)',
    biomeLabel: 'Arid Plains',
    stars: 2,
  },
  'Stranglethorn Vale': {
    bg: 'linear-gradient(160deg, oklch(0.18 0.07 148) 0%, oklch(0.13 0.05 158) 55%, oklch(0.10 0.03 168) 100%)',
    glow: 'oklch(0.48 0.14 152)',
    accent: 'oklch(0.52 0.14 148)',
    dangerLabel: 'Dangerous',
    dangerColor: 'oklch(0.68 0.18 50)',
    biomeLabel: 'Tropical Jungle',
    stars: 3,
  },
  'Eastern Plaguelands': {
    bg: 'linear-gradient(160deg, oklch(0.16 0.06 280) 0%, oklch(0.12 0.05 290) 55%, oklch(0.09 0.03 300) 100%)',
    glow: 'oklch(0.45 0.15 290)',
    accent: 'oklch(0.52 0.18 300)',
    dangerLabel: 'Very Dangerous',
    dangerColor: 'oklch(0.60 0.22 25)',
    biomeLabel: 'Cursed Wasteland',
    stars: 4,
  },
  'Winterspring': {
    bg: 'linear-gradient(160deg, oklch(0.20 0.04 225) 0%, oklch(0.15 0.03 230) 55%, oklch(0.10 0.02 240) 100%)',
    glow: 'oklch(0.55 0.08 225)',
    accent: 'oklch(0.60 0.10 220)',
    dangerLabel: 'Deadly',
    dangerColor: 'oklch(0.62 0.14 220)',
    biomeLabel: 'Frozen Tundra',
    stars: 4,
  },
  'Silithus': {
    bg: 'linear-gradient(160deg, oklch(0.22 0.08 75) 0%, oklch(0.16 0.07 65) 55%, oklch(0.11 0.04 60) 100%)',
    glow: 'oklch(0.58 0.14 70)',
    accent: 'oklch(0.62 0.15 72)',
    dangerLabel: 'Lethal',
    dangerColor: 'oklch(0.55 0.22 25)',
    biomeLabel: 'Ancient Desert',
    stars: 5,
  },
};

const FALLBACK_THEME = ZONE_THEMES['Stranglethorn Vale'];

/* ─────────────────────────── result overlays ─────────────────────────── */

const RESULT_CFG = {
  enemy: { icon: Sword,         color: 'oklch(0.52 0.22 25)',  label: 'ENCOUNTER',    textClass: 'text-red-400',    borderClass: 'border-red-500/50',    bgClass: 'bg-red-950/80' },
  boss:  { icon: Crown,         color: 'oklch(0.52 0.18 300)', label: 'BOSS',         textClass: 'text-purple-400', borderClass: 'border-purple-500/50', bgClass: 'bg-purple-950/80' },
  loot:  { icon: Sparkles,      color: 'oklch(0.74 0.13 80)',  label: 'DISCOVERY',    textClass: 'text-yellow-400', borderClass: 'border-yellow-500/50', bgClass: 'bg-yellow-950/80' },
  safe:  { icon: Star,          color: 'oklch(0.55 0.14 150)', label: 'SAFE JOURNEY', textClass: 'text-green-400',  borderClass: 'border-green-500/50',  bgClass: 'bg-green-950/80' },
  npc:   { icon: MessageCircle, color: 'oklch(0.58 0.12 195)', label: 'NPC MET',      textClass: 'text-teal-400',   borderClass: 'border-teal-500/50',   bgClass: 'bg-teal-950/80' },
};

/* ─────────────────────────── activity tiles ─────────────────────────── */

interface ActivityTile {
  id: string;
  icon: React.ElementType;
  label: string;
  tab?: string;
  badgeType?: 'cooldown' | 'boss' | 'quests' | 'static';
  staticBadge?: string;
}

const ACTIVITY_TILES: ActivityTile[] = [
  { id: 'encounters', icon: Sword,        label: 'Encounters',   tab: 'combat',    badgeType: 'cooldown' },
  { id: 'quests',     icon: ScrollText,   label: 'Quests & NPCs',tab: 'quests',    badgeType: 'quests' },
  { id: 'dungeons',   icon: Shield,       label: 'Dungeons',     tab: 'combat',    badgeType: 'boss' },
  { id: 'rest',       icon: Bed,          label: 'Rest',         tab: 'hero',      badgeType: 'static', staticBadge: '+HP' },
  { id: 'materials',  icon: Package,      label: 'Materials',    tab: 'market',    badgeType: 'static', staticBadge: '3' },
  { id: 'market',     icon: ShoppingBag,  label: 'Market',       tab: 'market' },
  { id: 'arena',      icon: Trophy,       label: 'Arena',        tab: 'arena',     badgeType: 'static', staticBadge: 'PvP' },
];

/* ─────────────────────────── component ─────────────────────────── */

export function ZoneMap({
  zones,
  currentZone,
  onSelectZone,
  latestResult,
  exploring,
  onGoToCombat,
  onInteractNPC,
  cooldownActive,
  className = '',
  onTabChange,
}: ZoneMapProps) {
  const [showResult, setShowResult] = useState(false);
  const [displayedResultId, setDisplayedResultId] = useState<string | null>(null);

  useEffect(() => {
    if (latestResult && latestResult.id !== displayedResultId) {
      setShowResult(true);
      setDisplayedResultId(latestResult.id);
    }
  }, [latestResult, displayedResultId]);

  const theme = ZONE_THEMES[currentZone?.name] || FALLBACK_THEME;
  const resCfg = latestResult ? RESULT_CFG[latestResult.type] : null;
  const ResIcon = resCfg?.icon;

  function getBadge(tile: ActivityTile): string | null {
    if (tile.badgeType === 'cooldown') return cooldownActive ? 'CD' : null;
    if (tile.badgeType === 'boss') return currentZone.bossAlive ? '!' : null;
    if (tile.badgeType === 'quests') return '2'; // static for now
    if (tile.badgeType === 'static') return tile.staticBadge ?? null;
    return null;
  }

  return (
    <div className={cn('flex flex-col rounded-lg overflow-hidden border border-white/10', className)}>

      {/* ── Zone pin selector row ── */}
      <div className="flex items-center gap-1.5 px-3 py-2 overflow-x-auto no-scrollbar border-b border-white/10 bg-black/30">
        {zones && Array.isArray(zones) && zones.map((zone) => {
          const isCurrent = zone.id === currentZone.id;
          return (
            <button
              key={zone.id}
              onClick={() => onSelectZone(zone)}
              title={`${zone.name} (Lv ${zone.levelRange[0]}–${zone.levelRange[1]})`}
              className={cn(
                'relative flex-shrink-0 flex flex-col items-center gap-0.5 rounded px-2 py-1.5 transition-all duration-200 text-[10px] font-serif',
                isCurrent
                  ? 'bg-gold/15 border border-gold/50 text-gold'
                  : 'border border-transparent text-muted-foreground hover:bg-white/5 hover:text-foreground'
              )}
            >
              <span className="text-base leading-none">{zone.emoji}</span>
              <span className="leading-none whitespace-nowrap max-w-[60px] truncate">{zone.name.split(' ')[0]}</span>
              {zone.bossAlive && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500 border border-black animate-pulse" />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Biome center panel ── */}
      <div
        className="relative flex-1"
        style={{ background: theme.bg, minHeight: '220px' }}
      >
        {/* Atmospheric glow */}
        <div
          className="absolute inset-0 opacity-20 animate-parallax pointer-events-none"
          style={{
            background: `radial-gradient(ellipse 60% 50% at 50% 40%, ${theme.glow}, transparent)`,
          }}
        />
        <div className="absolute top-0 left-0 right-0 h-12 bg-gradient-to-b from-black/50 to-transparent pointer-events-none" />
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-black/70 to-transparent pointer-events-none" />

        {/* Normal state — biome info */}
        {!exploring && !showResult && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center">
            <div className="text-5xl animate-float leading-none">{currentZone.emoji}</div>
            <div>
              <div className="font-serif text-sm font-bold text-foreground tracking-wide">{currentZone.name}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5 tracking-widest uppercase">{theme.biomeLabel}</div>
            </div>

            {/* Danger stars */}
            <div className="flex items-center gap-1 mt-1">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skull
                  key={i}
                  className={cn('h-3 w-3 transition-colors', i < theme.stars ? 'opacity-100' : 'opacity-15')}
                  style={{ color: i < theme.stars ? theme.dangerColor : undefined }}
                />
              ))}
              <span className="ml-1.5 text-[10px] font-serif uppercase tracking-wider" style={{ color: theme.dangerColor }}>
                {theme.dangerLabel}
              </span>
            </div>

            {/* Boss alive badge */}
            {currentZone.bossAlive && (
              <div className="flex items-center gap-1.5 mt-1 rounded px-2 py-0.5 bg-red-950/70 border border-red-500/40">
                <Crown className="h-3 w-3 text-red-400 animate-pulse" />
                <span className="text-[10px] font-serif text-red-300 uppercase tracking-wide">World Boss Active</span>
              </div>
            )}

            {/* Region hint */}
            {currentZone.regionHint && (
              <p className="text-[10px] text-muted-foreground/70 italic max-w-[220px] leading-relaxed mt-1">
                {currentZone.regionHint}
              </p>
            )}
          </div>
        )}

        {/* Scouting overlay */}
        {exploring && !showResult && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/50">
            <div
              className="w-10 h-10 rounded-full border-2 animate-spin"
              style={{ borderColor: `${theme.accent}40`, borderTopColor: theme.accent }}
            />
            <div className="font-serif text-sm tracking-[0.2em] uppercase" style={{ color: theme.accent }}>
              Scouting…
            </div>
            <div className="text-[11px] text-muted-foreground">Venturing into the unknown</div>
          </div>
        )}

        {/* Result overlay */}
        {showResult && latestResult && resCfg && ResIcon && (
          <div className="absolute inset-0 animate-backdrop">
            <div
              className="absolute inset-0 opacity-25 pointer-events-none"
              style={{ background: `radial-gradient(ellipse at center, ${resCfg.color}, transparent 70%)` }}
            />
            <div className="relative h-full flex flex-col items-center justify-center px-4 gap-2.5 text-center">
              {/* Icon */}
              <div
                className="w-14 h-14 rounded-full flex items-center justify-center border-2 animate-silhouette"
                style={{
                  borderColor: resCfg.color,
                  background: `${resCfg.color}20`,
                  boxShadow: `0 0 24px ${resCfg.color}50`,
                }}
              >
                <ResIcon className="w-6 h-6" style={{ color: resCfg.color }} />
              </div>

              {/* Type label */}
              <div className="font-serif text-[10px] tracking-[0.3em] uppercase font-bold animate-text-reveal" style={{ color: resCfg.color }}>
                {resCfg.label}
              </div>

              {/* Enemy name */}
              {(latestResult.type === 'enemy' || latestResult.type === 'boss') && latestResult.enemyName && (
                <div className="animate-text-reveal">
                  <div className="font-serif text-base font-bold text-foreground">{latestResult.enemyName}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">
                    Level {latestResult.enemyLevel}{latestResult.type === 'boss' ? ' — World Boss' : ''}
                  </div>
                </div>
              )}

              {/* NPC name */}
              {latestResult.type === 'npc' && latestResult.npc && (
                <div className="animate-text-reveal">
                  <div className="font-serif text-base font-bold text-foreground">{latestResult.npc.name}</div>
                  <div className="text-[10px] text-muted-foreground italic">{latestResult.npc.title}</div>
                </div>
              )}

              {/* Message */}
              <p className="text-[11px] text-foreground/75 max-w-[240px] leading-relaxed animate-text-reveal">
                {latestResult.message}
              </p>

              {/* Rewards */}
              {latestResult.reward && (latestResult.reward.xp || latestResult.reward.gold) && (
                <div className="flex items-center gap-3 animate-text-reveal">
                  {latestResult.reward.xp && (
                    <span className="flex items-center gap-1 text-xs font-bold text-blue-400">
                      <Zap className="w-3 h-3" />+{latestResult.reward.xp} XP
                    </span>
                  )}
                  {latestResult.reward.gold && (
                    <span className="flex items-center gap-1 text-xs font-bold text-yellow-400">
                      <Coins className="w-3 h-3" />+{latestResult.reward.gold}g
                    </span>
                  )}
                </div>
              )}

              {/* CTA buttons */}
              <div className="flex items-center gap-2 animate-text-reveal">
                {(latestResult.type === 'enemy' || latestResult.type === 'boss') && onGoToCombat && (
                  <button
                    onClick={onGoToCombat}
                    className="flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-serif font-bold tracking-wide uppercase text-white transition-all"
                    style={{ background: resCfg.color, boxShadow: `0 0 10px ${resCfg.color}70` }}
                  >
                    <Sword className="w-3 h-3" />
                    Combat
                    <ChevronRight className="w-3 h-3" />
                  </button>
                )}
                {latestResult.type === 'npc' && latestResult.npc && onInteractNPC && (
                  <button
                    onClick={() => onInteractNPC(latestResult.npc!.id)}
                    className="flex items-center gap-1.5 rounded px-3.5 py-1.5 text-xs font-serif font-bold tracking-wide uppercase text-teal-300 border border-teal-500/50 bg-teal-950/60"
                  >
                    <MessageCircle className="w-3 h-3" />
                    {latestResult.npc.alreadyMet ? 'Talk Again' : 'Interact'}
                  </button>
                )}
                <button
                  onClick={() => setShowResult(false)}
                  className="rounded px-3 py-1.5 text-xs text-muted-foreground border border-white/10 bg-black/50 hover:bg-black/70 transition-all"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── World Activity grid ── */}
      <div className="bg-black/40 border-t border-white/10 px-3 py-2.5">
        <div className="font-serif text-[9px] tracking-[0.25em] uppercase text-muted-foreground/60 mb-2">
          World Activity
        </div>
        <div className="grid grid-cols-7 gap-1">
          {ACTIVITY_TILES.map((tile) => {
            const Icon = tile.icon;
            const badge = getBadge(tile);
            return (
              <button
                key={tile.id}
                onClick={() => tile.tab && onTabChange?.(tile.tab)}
                title={tile.label}
                className="relative flex flex-col items-center gap-1 rounded py-2 px-1 bg-white/[0.04] border border-white/[0.07] hover:bg-white/[0.08] hover:border-gold/30 transition-all duration-150 group"
              >
                <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover:text-gold transition-colors" />
                <span className="text-[8px] text-muted-foreground/70 group-hover:text-gold/80 transition-colors leading-none text-center">
                  {tile.label.split(' ')[0]}
                </span>
                {badge && (
                  <span className="absolute -top-1 -right-1 min-w-[14px] h-3.5 px-0.5 rounded-full bg-gold text-[8px] font-bold text-black flex items-center justify-center leading-none">
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
