"use client"

import { useState, useCallback, useRef } from "react"
import { cn } from "@/lib/utils"
import { ZONES, SAMPLE_RESULTS, type Zone, type ExploreResult } from "@/lib/mmo-data"
import { ZoneMap } from "./zone-map"
import { CooldownRing } from "./cooldown-ring"
import { ResultPanel } from "./result-panel"
import {
  Compass,
  MapPin,
  ChevronDown,
  ChevronUp,
  Clock,
  Navigation,
  Info,
  Swords,
} from "lucide-react"

// ---- Simulated explore outcomes ----
function generateResult(): ExploreResult {
  const roll = Math.random()
  const id = Math.random().toString(36).slice(2)
  const ts = new Date()

  if (roll < 0.2) {
    return {
      id,
      type: "boss",
      message: "The earth trembles. A colossal silhouette blocks the sun — Gorgothar the Unburied has risen from the depths of the jungle floor.",
      enemyName: "Gorgothar the Unburied",
      enemyLevel: 45,
      isBoss: true,
      timestamp: ts,
    }
  }
  if (roll < 0.45) {
    return {
      id,
      type: "enemy",
      message: "Three Bloodsail Raiders drop from the canopy, weapons drawn — they spotted you first.",
      enemyName: "Bloodsail Raider",
      enemyLevel: 36,
      isBoss: false,
      timestamp: ts,
    }
  }
  if (roll < 0.6) {
    return {
      id,
      type: "npc",
      message: "You nearly trip over a crouched figure in worn leather armour. She doesn't reach for her blade — a good sign.",
      npc: {
        id: "npc_mira",
        name: "Mira Flinthand",
        title: "Tracker & Scout",
        silhouette: "🏹",
        discoveryQuote: "\"There's a cave half a league north — I'd avoid it if I were you. Smells of old magic and something worse.\"",
        alreadyMet: Math.random() > 0.7,
      },
      reward: { xp: 95 },
      timestamp: ts,
    }
  }
  if (roll < 0.75) {
    return {
      id,
      type: "loot",
      message: "Beneath a moss-draped stone you find a leather satchel, long abandoned. Someone was in a great hurry to leave.",
      reward: { xp: 60, gold: 12 },
      timestamp: ts,
    }
  }
  return {
    id,
    type: "safe",
    message: "The path winds along a ridge overlooking the whole vale. For a long moment everything is still — birds, wind, the distant crash of surf. You breathe.",
    reward: { xp: 40 },
    timestamp: ts,
  }
}

export function ExploreTab({ onGoToCombat, onTabChange }: { onGoToCombat?: () => void; onTabChange?: (tab: string) => void }) {
  const [currentZone, setCurrentZone] = useState<Zone>(ZONES[1]) // Stranglethorn
  const [travelTarget, setTravelTarget] = useState<Zone>(ZONES[1])
  const [isTravelling, setIsTravelling] = useState(false)

  const [exploring, setExploring] = useState(false)
  const [cooldownActive, setCooldownActive] = useState(false)
  const [results, setResults] = useState<ExploreResult[]>(SAMPLE_RESULTS)
  const [latestId, setLatestId] = useState<string | null>(null)

  const [timelineOpen, setTimelineOpen] = useState(false)
  const topRef = useRef<HTMLDivElement>(null)

  const handleTravel = useCallback(() => {
    if (travelTarget.id === currentZone.id) return
    setIsTravelling(true)
    setTimeout(() => {
      setCurrentZone(travelTarget)
      setIsTravelling(false)
    }, 1200)
  }, [travelTarget, currentZone])

  const handleExplore = useCallback(() => {
    if (cooldownActive || exploring) return
    setExploring(true)
    setTimeout(() => {
      const r = generateResult()
      setResults((prev) => [r, ...prev].slice(0, 20))
      setLatestId(r.id)
      setExploring(false)
      setCooldownActive(true)
    }, 900)
  }, [cooldownActive, exploring])

  const handleCooldownComplete = useCallback(() => {
    setCooldownActive(false)
  }, [])

  const latestResult = results.find((r) => r.id === latestId)
  const timelineResults = latestResult ? results.filter((r) => r.id !== latestId) : results

  return (
    <div className="flex flex-col gap-0 h-full" ref={topRef}>
      {/* ── Section heading ── */}
      <div className="flex items-center gap-2.5 px-4 pt-4 pb-3 border-b border-panel-border/50">
        <Compass className="h-4 w-4 text-gold" />
        <h2 className="font-serif text-sm tracking-[0.2em] uppercase text-gold font-semibold">
          Explore
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">

        {/* ── Current Zone Banner ── */}
        <div className={cn(
          "rounded border panel-inset transition-all duration-500",
          isTravelling ? "border-gold/60 bg-gold/5 opacity-60" : "border-panel-border bg-panel-bg",
        )}>
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06]">
            <span className="font-serif text-[10px] tracking-[0.2em] uppercase text-gold/60 flex items-center gap-1.5">
              <MapPin className="h-3 w-3" />
              Current Zone
            </span>
            {isTravelling && (
              <span className="text-[10px] text-gold/80 font-sans italic flex items-center gap-1">
                <Navigation className="h-3 w-3 animate-bounce" />
                Travelling…
              </span>
            )}
          </div>
          <div className="px-3 py-2.5 flex items-start gap-3">
            <span className="text-3xl leading-none animate-float">{currentZone.emoji}</span>
            <div className="flex-1 min-w-0">
              <h3 className="font-serif text-base font-bold text-gold tracking-wide leading-tight">
                {currentZone.name}
              </h3>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-muted-foreground">
                <span>Levels {currentZone.levelRange[0]}–{currentZone.levelRange[1]}</span>
                <span className="text-panel-border">◆</span>
                <span className="capitalize">{currentZone.faction}</span>
                <span className="text-panel-border">◆</span>
                <span>{currentZone.playersNearby} player{currentZone.playersNearby !== 1 ? "s" : ""} nearby</span>
              </div>
              {currentZone.regionHint && (
                <div className="flex items-start gap-1.5 mt-2 text-[11px] text-gold/60 italic bg-gold/5 border border-gold/15 rounded px-2 py-1.5 leading-relaxed">
                  <Info className="h-3 w-3 flex-shrink-0 mt-0.5 text-gold/50" />
                  <span>{currentZone.regionHint}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Explore Action ── PRIMARY ACTION */}
        <div className="flex items-center gap-3 bg-panel-bg border border-gold/40 rounded px-4 py-3.5 panel-inset shadow-[0_0_16px_oklch(0.74_0.13_80/0.2)]">
          {cooldownActive ? (
            <CooldownRing totalSeconds={30} onComplete={handleCooldownComplete} />
          ) : (
            <button
              onClick={handleExplore}
              disabled={exploring}
              className={cn(
                "relative flex-shrink-0 rounded border px-6 py-2.5 font-serif text-sm font-bold tracking-[0.15em] uppercase transition-all duration-200",
                exploring
                  ? "border-gold/30 bg-gold/5 text-gold/50 cursor-wait"
                  : "border-gold bg-gold/20 text-gold hover:bg-gold/30 hover:shadow-[0_0_16px_oklch(0.74_0.13_80/0.4)] animate-pulse-gold",
              )}
            >
              {exploring ? (
                <span className="flex items-center gap-2">
                  <span className="inline-block h-3.5 w-3.5 rounded-full border-2 border-gold/40 border-t-gold animate-spin" />
                  Scouting…
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
            {cooldownActive
              ? "Catching your breath before the next foray…"
              : exploring
              ? "Venturing into the unknown…"
              : (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3 text-gold/40" />
                  ~30s cooldown between explorations
                </span>
              )
            }
          </div>
        </div>

        {/* ── Interactive Zone Map ── */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="font-serif text-[10px] tracking-[0.2em] uppercase text-gold/60 flex items-center gap-1.5">
              <MapPin className="h-3 w-3" />
              Zone Map
            </span>
            <div className="flex-1 h-px bg-panel-border/50" />
          </div>
          <ZoneMap
            zones={ZONES}
            currentZone={currentZone}
            onSelectZone={(zone) => setTravelTarget(zone)}
            latestResult={latestResult}
            exploring={exploring}
            onGoToCombat={onGoToCombat}
            onInteractNPC={(_id) => {}}
            cooldownActive={cooldownActive}
            onTabChange={onTabChange}
          />

          {travelTarget.id !== currentZone.id && (
            <button
              onClick={handleTravel}
              disabled={isTravelling}
              className="mt-3 w-full flex items-center justify-center gap-2 rounded border border-gold/50 bg-gold/10 hover:bg-gold/20 text-gold font-serif text-xs font-bold tracking-[0.15em] uppercase py-2.5 transition-all duration-150 disabled:opacity-50"
            >
              <Navigation className="h-3.5 w-3.5" />
              {isTravelling ? "Travelling…" : `Travel to ${travelTarget.name}`}
            </button>
          )}
        </div>

        {/* ── Recent Timeline ── */}
        {timelineResults.length > 0 && (
          <div>
            <button
              className="w-full flex items-center gap-2 mb-2 group"
              onClick={() => setTimelineOpen((o) => !o)}
            >
              <span className="font-serif text-[10px] tracking-[0.2em] uppercase text-gold/60 flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                Recent Explorations ({timelineResults.length})
              </span>
              <div className="flex-1 h-px bg-panel-border/50" />
              {timelineOpen
                ? <ChevronUp className="h-3.5 w-3.5 text-gold/40 group-hover:text-gold/70 transition-colors" />
                : <ChevronDown className="h-3.5 w-3.5 text-gold/40 group-hover:text-gold/70 transition-colors" />
              }
            </button>

            {timelineOpen && (
              <div className="relative space-y-2 pl-4">
                {/* timeline bar */}
                <div className="absolute left-1.5 top-0 bottom-0 w-px bg-panel-border/50" />
                {timelineResults.map((r, i) => (
                  <div key={r.id} className="relative" style={{ animationDelay: `${i * 60}ms` }}>
                    <div className="absolute -left-2.5 top-3 h-2 w-2 rounded-full border border-panel-border bg-background" />
                    <ResultPanel
                      result={r}
                      isTimeline
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Quest Link hint ── */}
        <div className="flex items-start gap-2.5 rounded border border-gold/15 bg-gold/5 px-3 py-2.5">
          <Swords className="h-3.5 w-3.5 flex-shrink-0 text-gold/50 mt-0.5" />
          <p className="text-[11px] text-gold/60 leading-relaxed italic">
            Quests often start or advance after meeting NPCs while exploring. Check the{" "}
            <span className="text-gold/80 not-italic font-semibold">Quests</span> tab after any NPC encounter.
          </p>
        </div>

      </div>
    </div>
  )
}
