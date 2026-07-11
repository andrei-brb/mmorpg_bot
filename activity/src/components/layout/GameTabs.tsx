import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Castle,
  Globe,
  Hammer,
  Map,
  Menu,
  ScrollText,
  Skull,
  Store,
  Swords,
  Ticket,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { HeroTab } from "@/components/game/tabs/HeroTab";
import { CraftingTab } from "@/components/game/tabs/CraftingTab";
import { ExploreTab } from "@/components/game/tabs/ExploreTab";
import { QuestsTab } from "@/components/game/tabs/QuestsTab";
import { CombatTab } from "@/components/game/tabs/CombatTab";
import { GuildTab } from "@/components/game/tabs/GuildTab";
import { MarketTab } from "@/components/game/tabs/MarketTab";
import { RealmTab } from "@/components/game/tabs/RealmTab";
import { BattlePassTab } from "@/components/game/tabs/BattlePassTab";
import { PvpPage } from "@/components/pvp/PvpPage";

export type GameTabId =
  | "Hero"
  | "Forge"
  | "Explore"
  | "Quests"
  | "Combat"
  | "Guild"
  | "Market"
  | "Arena"
  | "Pass"
  | "Realm";

const ALL_TAB_IDS: GameTabId[] = [
  "Hero",
  "Forge",
  "Explore",
  "Quests",
  "Combat",
  "Guild",
  "Market",
  "Arena",
  "Pass",
  "Realm",
];

type TabDef = {
  id: GameTabId;
  label: string;
  icon: LucideIcon;
  hint: string;
};

type TabGroup = {
  id: string;
  label: string;
  tabs: TabDef[];
};

const TAB_GROUPS: TabGroup[] = [
  {
    id: "character",
    label: "Character",
    tabs: [
      { id: "Hero", label: "Hero", icon: User, hint: "Gear, stats, talents" },
      { id: "Forge", label: "Forge", icon: Hammer, hint: "Craft & enhance" },
    ],
  },
  {
    id: "world",
    label: "World",
    tabs: [
      { id: "Explore", label: "Explore", icon: Map, hint: "Zones & encounters" },
      { id: "Quests", label: "Quests", icon: ScrollText, hint: "Story & objectives" },
      { id: "Combat", label: "Combat", icon: Skull, hint: "Fight & dungeons" },
    ],
  },
  {
    id: "social",
    label: "Social",
    tabs: [
      { id: "Guild", label: "Guild", icon: Castle, hint: "Hall, raids, tech" },
      { id: "Market", label: "Market", icon: Store, hint: "Buy & sell" },
      { id: "Arena", label: "Arena", icon: Swords, hint: "PvP matches" },
    ],
  },
  {
    id: "progression",
    label: "Progression",
    tabs: [
      { id: "Pass", label: "Battle Pass", icon: Ticket, hint: "Season rewards" },
      { id: "Realm", label: "Realm", icon: Globe, hint: "Server & milestones" },
    ],
  },
];

const TAB_BY_ID = Object.fromEntries(
  TAB_GROUPS.flatMap((g) => g.tabs.map((t) => [t.id, t])),
) as Record<GameTabId, TabDef>;

function normalizeTabId(raw: string): GameTabId | null {
  const norm =
    raw === "Progress" || raw === "progress" || raw === "realm"
      ? "Realm"
      : raw === "Battle Pass" || raw === "battle-pass"
        ? "Pass"
        : raw;
  return (ALL_TAB_IDS as readonly string[]).includes(norm) ? (norm as GameTabId) : null;
}

export type GameTabsProps = {
  shellChromeHidden?: boolean;
  combatFocusActive?: boolean;
  /** Mail, live badge, profile — rendered beside the nav trigger */
  chrome?: ReactNode;
};

export function GameTabs({ shellChromeHidden, combatFocusActive, chrome }: GameTabsProps) {
  const [tab, setTab] = useState<GameTabId>("Hero");
  const [open, setOpen] = useState(false);

  const current = TAB_BY_ID[tab];

  const selectTab = useCallback((id: GameTabId) => {
    setTab(id);
    setOpen(false);
  }, []);

  useEffect(() => {
    const onSetTab = (ev: Event) => {
      const next = normalizeTabId(String((ev as CustomEvent).detail ?? ""));
      if (next) setTab(next);
    };
    window.addEventListener("game:setActiveTab", onSetTab);
    return () => window.removeEventListener("game:setActiveTab", onSetTab);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const CurrentIcon = current?.icon ?? User;

  const panel = useMemo(
    () =>
      open ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            aria-label="Close command menu"
            onClick={() => setOpen(false)}
          />
          <div
            className={cn(
              "fixed z-50",
              // Clear the notch/Dynamic Island: this is a fixed element, so it sits
              // outside the .app-bg safe-area padding and needs its own insets.
              "[top:calc(0.75rem+env(safe-area-inset-top))] sm:[top:calc(1.5rem+env(safe-area-inset-top))]",
              "[left:calc(0.75rem+env(safe-area-inset-left))] sm:[left:calc(1.5rem+env(safe-area-inset-left))]",
              "w-[min(92vw,380px)] max-h-[calc(100dvh-2rem-env(safe-area-inset-top)-env(safe-area-inset-bottom))] overflow-y-auto",
              "tex-forge hero-forge-edge-gold-strong p-[2px]",
              "animate-in fade-in slide-in-from-left-4 duration-200",
            )}
            role="dialog"
            aria-modal="true"
            aria-label="Command menu"
          >
            <span className="corner-ornament corner-tl" aria-hidden />
            <span className="corner-ornament corner-tr" aria-hidden />
            <span className="corner-ornament corner-bl" aria-hidden />
            <span className="corner-ornament corner-br" aria-hidden />

            <div className="relative min-w-0 bg-black/70 border border-gold/30">
              <div className="hero-forge-clip-banner flex items-center justify-center bg-gradient-to-r from-gold-dim via-gold-200 to-gold-dim px-4 py-2.5">
                <span className="font-display text-[11px] font-bold tracking-[0.4em] text-background sm:text-xs">
                  COMMAND
                </span>
              </div>

              <div className="tex-leather p-3 sm:p-4 space-y-4">
                {TAB_GROUPS.map((group) => (
                  <section key={group.id}>
                    <div className="mb-2 flex items-center gap-2">
                      <span className="font-display text-[10px] uppercase tracking-[0.35em] text-gold-dim shrink-0">
                        {group.label}
                      </span>
                      <span
                        className="h-px flex-1"
                        style={{
                          background:
                            "linear-gradient(90deg, oklch(0.78 0.14 78 / 0.45), oklch(0.78 0.14 78 / 0.05))",
                        }}
                        aria-hidden
                      />
                    </div>
                    <ul className="space-y-1.5" role="list">
                      {group.tabs.map((t) => {
                        const Icon = t.icon;
                        const active = tab === t.id;
                        return (
                          <li key={t.id}>
                            <button
                              type="button"
                              onClick={() => selectTab(t.id)}
                              className={cn(
                                "relative flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors",
                                "hero-forge-clip-blade-sm border border-gold/20 bg-black/35",
                                "hover:border-gold/45 hover:bg-black/50",
                                active &&
                                  "border-gold-bright/70 shadow-gold bg-black/55",
                              )}
                              aria-current={active ? "page" : undefined}
                            >
                              {active ? (
                                <span
                                  className="absolute left-1.5 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-gold-200 shadow-[0_0_8px_oklch(0.88_0.16_88/0.9)]"
                                  aria-hidden
                                />
                              ) : null}
                              <span
                                className={cn(
                                  "flex h-9 w-9 shrink-0 items-center justify-center hero-forge-clip-blade-sm tex-forge hero-forge-edge-gold border border-gold/30",
                                  active && "border-gold-bright/60",
                                )}
                              >
                                <Icon
                                  className={cn(
                                    "h-4 w-4",
                                    active ? "text-gold-bright" : "text-gold-dim",
                                  )}
                                  strokeWidth={1.5}
                                />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span
                                  className={cn(
                                    "block font-display text-sm tracking-wide",
                                    active ? "text-gold-bright" : "text-foreground/90",
                                  )}
                                >
                                  {t.label}
                                </span>
                                <span className="block text-[11px] text-gold-dim/90 truncate">
                                  {t.hint}
                                </span>
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : null,
    [open, tab, selectTab],
  );

  return (
    <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col">
      {panel}

      {!shellChromeHidden ? (
        <div className="mb-3 flex min-h-0 items-stretch gap-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className={cn(
              "flex h-11 w-11 shrink-0 items-center justify-center",
              "tex-forge hero-forge-edge-gold-strong hero-forge-clip-blade-sm",
              "border border-gold/40 text-gold-bright transition-colors",
              "hover:border-gold-bright/70 hover:text-gold-200",
              open && "border-gold-bright/70 shadow-gold",
            )}
            aria-label={open ? "Close command menu" : "Open command menu"}
            aria-expanded={open}
          >
            {open ? <X className="h-5 w-5" strokeWidth={1.75} /> : <Menu className="h-5 w-5" strokeWidth={1.75} />}
          </button>

          <div
            className={cn(
              "flex min-w-0 flex-1 items-center gap-2.5 px-3 py-2",
              "tex-leather hero-forge-edge-gold hero-forge-clip-blade-sm border border-gold/30",
            )}
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center hero-forge-clip-blade-sm tex-forge hero-forge-edge-gold border border-gold/30">
              <CurrentIcon className="h-4 w-4 text-gold-bright" strokeWidth={1.5} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-display text-sm tracking-wide text-gold-bright truncate">
                {current?.label ?? tab}
              </span>
              <span className="block text-[11px] text-gold-dim truncate">{current?.hint ?? ""}</span>
            </span>
          </div>

          {chrome ? (
            <div className="flex shrink-0 items-center gap-1.5 self-center border-l border-gold/20 pl-2">
              {chrome}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-x-clip">
        {tab === "Hero" && <HeroTab />}
        {tab === "Forge" && <CraftingTab />}
        {tab === "Explore" && <ExploreTab />}
        {tab === "Quests" && <QuestsTab />}
        {tab === "Combat" && <CombatTab focusMode={combatFocusActive} />}
        {tab === "Guild" && <GuildTab />}
        {tab === "Market" && <MarketTab />}
        {tab === "Arena" && <PvpPage />}
        {tab === "Pass" && <BattlePassTab />}
        {tab === "Realm" && <RealmTab />}
      </div>
    </div>
  );
}
