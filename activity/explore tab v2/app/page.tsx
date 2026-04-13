"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { ExploreTab } from "@/components/explore/explore-tab"
import {
  Sword,
  Map,
  ScrollText,
  ShoppingBag,
  Trophy,
  BarChart3,
  User,
  Wifi,
} from "lucide-react"

type Tab = "hero" | "explore" | "quests" | "combat" | "market" | "arena" | "progress"

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "hero",     label: "Hero",     icon: User },
  { id: "explore",  label: "Explore",  icon: Map },
  { id: "quests",   label: "Quests",   icon: ScrollText },
  { id: "combat",   label: "Combat",   icon: Sword },
  { id: "market",   label: "Market",   icon: ShoppingBag },
  { id: "arena",    label: "Arena",    icon: Trophy },
  { id: "progress", label: "Progress", icon: BarChart3 },
]

function PlaceholderTab({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-3 text-muted-foreground/40">
      <span className="font-serif text-4xl text-gold/20">{label}</span>
      <p className="text-sm italic">Content for this tab coming soon.</p>
    </div>
  )
}

export default function Page() {
  const [activeTab, setActiveTab] = useState<Tab>("explore")

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-2 sm:p-4">
      {/* Game frame — matches Discord Activity viewport */}
      <div
        className="relative w-full max-w-[860px] rounded-lg overflow-hidden"
        style={{
          background: "oklch(0.118 0.008 260)",
          boxShadow:
            "0 0 0 1px oklch(0.32 0.04 75 / 0.6), 0 0 40px oklch(0 0 0 / 0.6), inset 0 1px 0 oklch(0.74 0.13 80 / 0.12)",
          minHeight: 540,
          maxHeight: "95vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* ── Top ornament bar ── */}
        <div className="h-1 bg-gradient-to-r from-transparent via-gold/40 to-transparent" />

        {/* ── Header ── */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-panel-border/60">
          <div className="flex items-center gap-3">
            {/* Avatar */}
            <div className="relative h-11 w-11 rounded-full border-2 border-gold/50 bg-panel-bg flex items-center justify-center text-xl overflow-hidden">
              🧝
              <div className="absolute bottom-0 right-0 h-3.5 w-3.5 bg-background border border-panel-border rounded-full flex items-center justify-center">
                <span className="text-[8px] font-serif font-bold text-gold leading-none">60</span>
              </div>
            </div>
            <div>
              <h1 className="font-serif text-base font-bold text-gold tracking-wide leading-tight">
                World of Discord
              </h1>
              <p className="text-xs text-muted-foreground">
                Welcome, <span className="text-foreground/80 font-semibold">Bratiska</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-safe-green border border-safe-green/30 bg-safe-green/8 rounded-full px-2.5 py-1">
            <Wifi className="h-3 w-3" />
            Connected
          </div>
        </header>

        {/* ── Tab bar ── */}
        <nav
          className="flex items-center border-b border-panel-border/60 bg-panel-bg/40 overflow-x-auto no-scrollbar"
          aria-label="Game navigation"
        >
          {TABS.map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-2.5 text-[11px] font-serif font-semibold tracking-[0.12em] uppercase whitespace-nowrap border-b-2 transition-all duration-150 flex-shrink-0",
                  active
                    ? "border-gold text-gold bg-gold/8"
                    : "border-transparent text-muted-foreground/60 hover:text-muted-foreground hover:border-white/10",
                )}
                aria-current={active ? "page" : undefined}
              >
                <Icon className="h-3 w-3" />
                {tab.label}
              </button>
            )
          })}
        </nav>

        {/* ── Tab content ── */}
        <main className="flex-1 overflow-hidden flex flex-col min-h-0">
          {activeTab === "explore" && (
            <ExploreTab
              onGoToCombat={() => setActiveTab("combat")}
              onTabChange={(tab) => setActiveTab(tab as Tab)}
            />
          )}
          {activeTab !== "explore" && (
            <PlaceholderTab label={TABS.find((t) => t.id === activeTab)?.label ?? ""} />
          )}
        </main>

        {/* ── Bottom ornament ── */}
        <div className="h-1 bg-gradient-to-r from-transparent via-gold/30 to-transparent" />
      </div>
    </div>
  )
}
