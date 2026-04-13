'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import type { ExploreResult } from '@/lib/mmo-data'
import {
  Sword,
  Star,
  MessageCircle,
  Crown,
  Sparkles,
  Coins,
  Zap,
  ChevronRight,
} from 'lucide-react'

const TYPE_CONFIG = {
  enemy: {
    border: 'border-enemy-red/60',
    bg: 'bg-enemy-red/5',
    glow: 'shadow-[0_0_16px_oklch(0.52_0.22_25/0.2)]',
    icon: Sword,
    iconColor: 'text-enemy-red',
    label: 'ENCOUNTER',
    labelColor: 'text-enemy-red',
    cardBg: 'bg-enemy-red/10 border-enemy-red/30',
  },
  boss: {
    border: 'border-boss-purple/70',
    bg: 'bg-boss-purple/5',
    glow: 'shadow-[0_0_20px_oklch(0.52_0.18_300/0.25)]',
    icon: Crown,
    iconColor: 'text-boss-purple',
    label: 'BOSS ENCOUNTER',
    labelColor: 'text-boss-purple',
    cardBg: 'bg-boss-purple/10 border-boss-purple/30',
  },
  loot: {
    border: 'border-gold/50',
    bg: 'bg-gold/5',
    glow: 'shadow-[0_0_14px_oklch(0.74_0.13_80/0.18)]',
    icon: Sparkles,
    iconColor: 'text-gold',
    label: 'DISCOVERY',
    labelColor: 'text-gold',
    cardBg: 'bg-gold/10 border-gold/30',
  },
  safe: {
    border: 'border-safe-green/40',
    bg: 'bg-safe-green/5',
    glow: '',
    icon: Star,
    iconColor: 'text-safe-green',
    label: 'QUIET JOURNEY',
    labelColor: 'text-safe-green',
    cardBg: 'bg-safe-green/10 border-safe-green/30',
  },
  npc: {
    border: 'border-npc-teal/50',
    bg: 'bg-npc-teal/5',
    glow: 'shadow-[0_0_14px_oklch(0.58_0.12_195/0.18)]',
    icon: MessageCircle,
    iconColor: 'text-npc-teal',
    label: 'NPC ENCOUNTERED',
    labelColor: 'text-npc-teal',
    cardBg: 'bg-npc-teal/10 border-npc-teal/30',
  },
}

function RelativeTime({ date }: { date: Date }) {
  const [, forceUpdate] = useState(0)
  useEffect(() => {
    const id = setInterval(() => forceUpdate((n) => n + 1), 10_000)
    return () => clearInterval(id)
  }, [])
  const diff = Math.round((Date.now() - date.getTime()) / 1000)
  if (diff < 60) return <span>{diff}s ago</span>
  if (diff < 3600) return <span>{Math.round(diff / 60)}m ago</span>
  return <span>{Math.round(diff / 3600)}h ago</span>
}

interface ResultPanelProps {
  result: ExploreResult
  onGoToCombat?: () => void
  onInteractNPC?: (npcId: string) => void
  isLatest?: boolean
  isTimeline?: boolean
}

export function ResultPanel({
  result,
  onGoToCombat,
  onInteractNPC,
  isLatest,
  isTimeline,
}: ResultPanelProps) {
  const cfg = TYPE_CONFIG[result.type]
  const Icon = cfg.icon

  return (
    <div
      className={cn(
        'rounded border transition-all duration-300',
        cfg.border,
        cfg.bg,
        isLatest && cfg.glow,
        isLatest && 'animate-result-in',
        isTimeline && 'opacity-80',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <Icon className={cn('h-3.5 w-3.5 flex-shrink-0', cfg.iconColor)} />
          <span className={cn('font-serif text-[10px] tracking-[0.15em] font-bold uppercase', cfg.labelColor)}>
            {cfg.label}
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground/60 tabular-nums">
          <RelativeTime date={result.timestamp} />
        </span>
      </div>

      <div className="px-3 py-3 space-y-2.5">
        {/* Message — always visible immediately */}
        <p className={cn('text-foreground/85 leading-relaxed', isTimeline ? 'text-xs' : 'text-sm')}>
          {result.message}
        </p>

        {/* Enemy / Boss card */}
        {(result.type === 'enemy' || result.type === 'boss') && (
          <div className={cn('rounded px-2.5 py-2 flex items-center justify-between border', cfg.cardBg)}>
            <div>
              <p className={cn('font-serif font-semibold', cfg.labelColor, isTimeline ? 'text-xs' : 'text-sm')}>
                {result.enemyName}
              </p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Level {result.enemyLevel} · {result.isBoss ? 'World Boss' : 'Enemy'}
              </p>
            </div>
            {result.isBoss && <Crown className="h-5 w-5 text-boss-purple animate-float" />}
          </div>
        )}

        {/* NPC card */}
        {result.type === 'npc' && result.npc && (
          <div className="space-y-2">
            <div className={cn('flex items-center gap-3 rounded px-2.5 py-2 border', cfg.cardBg)}>
              <div className={cn(
                'flex-shrink-0 rounded-full border border-npc-teal/40 bg-background flex items-center justify-center text-xl',
                isTimeline ? 'h-8 w-8' : 'h-11 w-11 text-2xl',
              )}>
                {result.npc.silhouette}
              </div>
              <div className="flex-1 min-w-0">
                <p className={cn('font-serif font-semibold text-npc-teal', isTimeline ? 'text-xs' : 'text-sm')}>
                  {result.npc.name}
                </p>
                <p className="text-[10px] text-muted-foreground italic">{result.npc.title}</p>
                {result.npc.alreadyMet && (
                  <p className="text-[10px] text-gold/70 mt-0.5">Already met</p>
                )}
              </div>
            </div>
            {result.npc.discoveryQuote && (
              <blockquote className="border-l-2 border-npc-teal/40 pl-3 italic text-xs text-muted-foreground leading-relaxed">
                {result.npc.discoveryQuote}
              </blockquote>
            )}
          </div>
        )}

        {/* Rewards */}
        {result.reward && (result.reward.xp || result.reward.gold) && (
          <div className="flex items-center gap-3">
            {result.reward.xp && (
              <span className="flex items-center gap-1 text-xs font-semibold text-xp-blue">
                <Zap className="h-3 w-3" />
                +{result.reward.xp} XP
              </span>
            )}
            {result.reward.gold && (
              <span className="flex items-center gap-1 text-xs font-semibold text-gold">
                <Coins className="h-3 w-3" />
                +{result.reward.gold}g
              </span>
            )}
          </div>
        )}

        {/* Hints */}
        {!isTimeline && result.type === 'npc' && (
          <p className="text-[11px] text-gold/55 italic border-t border-white/[0.05] pt-2">
            Quests often start or advance after meeting NPCs while exploring.
          </p>
        )}
        {!isTimeline && (result.type === 'enemy' || result.type === 'boss') && (
          <p className="text-[11px] text-gold/55 italic border-t border-white/[0.05] pt-2">
            Kill objectives on active quests may progress in Combat.
          </p>
        )}

        {/* CTAs */}
        {!isTimeline && (
          <div className="flex items-center gap-2 pt-0.5">
            {(result.type === 'enemy' || result.type === 'boss') && onGoToCombat && (
              <button
                onClick={onGoToCombat}
                className={cn(
                  'flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-serif font-bold tracking-wide uppercase transition-all duration-150',
                  result.isBoss
                    ? 'bg-boss-purple text-foreground hover:bg-boss-purple/80'
                    : 'bg-enemy-red text-foreground hover:bg-enemy-red/80',
                )}
              >
                <Sword className="h-3.5 w-3.5" />
                Go to Combat
                <ChevronRight className="h-3 w-3" />
              </button>
            )}
            {result.type === 'npc' && result.npc && onInteractNPC && (
              <button
                onClick={() => onInteractNPC(result.npc!.id)}
                className="flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-serif font-bold tracking-wide uppercase bg-npc-teal/20 border border-npc-teal/50 text-npc-teal hover:bg-npc-teal/30 transition-all duration-150"
              >
                <MessageCircle className="h-3.5 w-3.5" />
                {result.npc.alreadyMet ? 'Talk Again' : 'Interact'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
