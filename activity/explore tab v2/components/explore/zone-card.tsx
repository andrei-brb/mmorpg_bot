"use client"

import { cn } from "@/lib/utils"
import type { Zone } from "@/lib/mmo-data"
import { Users, Skull } from "lucide-react"

interface ZoneCardProps {
  zone: Zone
  selected: boolean
  current: boolean
  onSelect: (zone: Zone) => void
}

const factionColors: Record<string, string> = {
  alliance: "text-xp-blue border-xp-blue/40",
  horde:    "text-enemy-red border-enemy-red/40",
  neutral:  "text-gold-dim border-gold/30",
  hostile:  "text-boss-purple border-boss-purple/40",
}

const factionLabels: Record<string, string> = {
  alliance: "Alliance",
  horde:    "Horde",
  neutral:  "Neutral",
  hostile:  "Contested",
}

export function ZoneCard({ zone, selected, current, onSelect }: ZoneCardProps) {
  return (
    <button
      onClick={() => onSelect(zone)}
      className={cn(
        "relative w-full text-left rounded border transition-all duration-200 p-3 group",
        "hover:border-gold/50 hover:bg-accent/60",
        selected
          ? "border-gold/70 bg-accent shadow-[0_0_12px_oklch(0.74_0.13_80/0.2)]"
          : "border-panel-border bg-panel-bg/60",
      )}
    >
      {/* Boss alive pip */}
      {zone.bossAlive && (
        <span className="absolute top-2 right-2 flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-boss-purple opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-boss-purple" />
        </span>
      )}

      <div className="flex items-start gap-2.5">
        <span className="text-2xl leading-none mt-0.5 animate-float" style={{ animationDelay: `${zone.id.length * 0.1}s` }}>
          {zone.emoji}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={cn("font-serif text-sm font-semibold tracking-wide leading-tight", selected ? "text-gold" : "text-foreground/90")}>
              {zone.name}
            </span>
            {current && (
              <span className="text-[10px] font-sans tracking-widest uppercase text-gold/70 border border-gold/30 rounded-sm px-1 py-0.5 leading-none">
                here
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-xs text-muted-foreground">Lv {zone.levelRange[0]}–{zone.levelRange[1]}</span>
            <span className={cn("text-[10px] uppercase tracking-wider font-semibold", factionColors[zone.faction])}>
              {factionLabels[zone.faction]}
            </span>
            {zone.playersNearby > 0 && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Users className="h-3 w-3" />
                {zone.playersNearby}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground/70 mt-1.5 leading-relaxed line-clamp-2 italic">
            {zone.description}
          </p>
          {zone.bossAlive && (
            <p className="flex items-center gap-1 text-[10px] text-boss-purple mt-1.5 font-semibold">
              <Skull className="h-3 w-3" />
              World Boss Active
            </p>
          )}
        </div>
      </div>
    </button>
  )
}
