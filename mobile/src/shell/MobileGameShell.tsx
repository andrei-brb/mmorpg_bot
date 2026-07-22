import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Castle,
  Globe,
  Hammer,
  LayoutGrid,
  Map,
  ScrollText,
  Skull,
  Store,
  Swords,
  Ticket,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import { useGameSession } from "@/context/GameSessionContext";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import type { GameTabId } from "@/components/layout/GameTabs";
import { HeroTab } from "@/components/game/tabs/HeroTab";
// The Forge renders as a phone-native Workbench instead of the Activity's
// three stacked panels. Same useForge() hook — layout only.
import { Workbench } from "@mobile/forge/Workbench";
import { ExploreTab } from "@/components/game/tabs/ExploreTab";
import { QuestsTab } from "@/components/game/tabs/QuestsTab";
import { CombatTab } from "@/components/game/tabs/CombatTab";
import { GuildTab } from "@/components/game/tabs/GuildTab";
import { MarketTab } from "@/components/game/tabs/MarketTab";
import { RealmTab } from "@/components/game/tabs/RealmTab";
import { BattlePassTab } from "@/components/game/tabs/BattlePassTab";
import { PvpPage } from "@/components/pvp/PvpPage";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";
import type { StoredSession } from "@mobile/platform/sessionStore";
import { remindersEnabled, setRemindersEnabled } from "@mobile/platform/notifications";
import { GuildJumpBar } from "./GuildJumpBar";
import { LinkAccountSheet } from "./LinkAccountSheet";
import { ShellModals } from "./ShellModals";

/**
 * Phone-native shell. Replaces GameShell + GameTabs for the mobile app only —
 * the Discord Activity keeps using GameShell, and nothing here is imported by
 * activity/src.
 *
 * What changes versus GameShell:
 *   - Full-bleed. No max-w-[1400px] centering, no game-frame border, no
 *     frame-border.jpg strips, no crest/rune ornaments. A phone has no room to
 *     spend on a frame around the frame.
 *   - Nav is a bottom tab bar instead of a hamburger that opens a COMMAND
 *     overlay (GameTabs.tsx:281). Changing tab was two taps and a full-screen
 *     takeover; here it is one thumb tap.
 *   - The tab panel owns the whole viewport between the two bars and scrolls
 *     on its own, so header and nav never scroll away.
 *
 * What is preserved deliberately:
 *   - The `game:setActiveTab` event contract (GameTabs.tsx:141). QuestsTab,
 *     ExploreTab, GuildTab and SocialPanel navigate by firing it, so the shell
 *     must keep listening or in-game links silently break.
 *   - shellChromeHidden (GameShell.tsx:46): combat/arena focus hides all chrome
 *     and hands the tab the full screen. That behaviour was already right for a
 *     phone.
 */

type TabDef = { id: GameTabId; label: string; icon: LucideIcon; hint: string };

/**
 * Bottom bars hold five targets before they stop being thumb-friendly, and the
 * game has ten tabs. These five are the daily loop — check your character, go
 * out, fight, collect. The rest live one tap away in More.
 */
const PRIMARY: TabDef[] = [
  { id: "Hero", label: "Hero", icon: User, hint: "Gear, stats, talents" },
  { id: "Explore", label: "Explore", icon: Map, hint: "Zones & encounters" },
  { id: "Combat", label: "Combat", icon: Skull, hint: "Fight & dungeons" },
  { id: "Quests", label: "Quests", icon: ScrollText, hint: "Story & objectives" },
];

/** Kept in GameTabs' grouping so the two shells stay conceptually in sync. */
const MORE_GROUPS: { label: string; tabs: TabDef[] }[] = [
  {
    label: "Character",
    tabs: [{ id: "Forge", label: "Forge", icon: Hammer, hint: "Craft & enhance" }],
  },
  {
    label: "Social",
    tabs: [
      { id: "Guild", label: "Guild", icon: Castle, hint: "Hall, raids, tech" },
      { id: "Market", label: "Market", icon: Store, hint: "Buy & sell" },
      { id: "Arena", label: "Arena", icon: Swords, hint: "PvP matches" },
    ],
  },
  {
    label: "Progression",
    tabs: [
      { id: "Pass", label: "Battle Pass", icon: Ticket, hint: "Season rewards" },
      { id: "Realm", label: "Realm", icon: Globe, hint: "Server & milestones" },
    ],
  },
];

const MORE_IDS = new Set<GameTabId>(MORE_GROUPS.flatMap((g) => g.tabs.map((t) => t.id)));

/** Mirrors normalizeTabId in GameTabs so both shells accept the same event payloads. */
function normalizeTabId(raw: string): GameTabId | null {
  const norm =
    raw === "Progress" || raw === "progress" || raw === "realm"
      ? "Realm"
      : raw === "Battle Pass" || raw === "battle-pass"
        ? "Pass"
        : raw;
  const all: string[] = [
    "Hero", "Forge", "Explore", "Quests", "Combat",
    "Guild", "Market", "Arena", "Pass", "Realm",
  ];
  return all.includes(norm) ? (norm as GameTabId) : null;
}

export function MobileGameShell({
  onSignOut,
  discordAuth,
  onSessionReplaced,
}: {
  onSignOut?: () => void;
  discordAuth?: DiscordOAuthAuth;
  onSessionReplaced?: (s: StoredSession) => void;
} = {}) {
  const [tab, setTab] = useState<GameTabId>("Hero");
  const [moreOpen, setMoreOpen] = useState(false);
  const [mailOpen, setMailOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [remindOn, setRemindOn] = useState(false);

  useEffect(() => {
    void remindersEnabled().then(setRemindOn);
  }, []);

  const {
    displayName,
    inventory,
    combatFocusActive,
    arenaFocusActive,
    lostDeliveries,
  } = useGameSession();

  const chromeHidden = combatFocusActive || arenaFocusActive;

  const selectTab = useCallback((id: GameTabId) => {
    setTab(id);
    setMoreOpen(false);
  }, []);

  // Same contract as GameTabs — in-game links depend on it.
  useEffect(() => {
    const onSetTab = (ev: Event) => {
      const next = normalizeTabId(String((ev as CustomEvent).detail ?? ""));
      if (next) selectTab(next);
    };
    window.addEventListener("game:setActiveTab", onSetTab);
    return () => window.removeEventListener("game:setActiveTab", onSetTab);
  }, [selectTab]);

  // A tab taking over the screen should also dismiss the More sheet.
  useEffect(() => {
    if (chromeHidden) setMoreOpen(false);
  }, [chromeHidden]);

  const char = inventory?.character ?? null;
  const gold = Number(char?.gold ?? 0);
  const hpCur = Number(char?.current_hp ?? 0);
  const hpMax = Number(char?.max_hp ?? 0);
  const hpPct = hpMax > 0 ? Math.max(0, Math.min(100, (hpCur / hpMax) * 100)) : 0;

  const mailBadgeActive = lostDeliveries.length > 0;

  const moreActive = MORE_IDS.has(tab);
  const activeMoreTab = useMemo(
    () => MORE_GROUPS.flatMap((g) => g.tabs).find((t) => t.id === tab) ?? null,
    [tab],
  );

  if (!inventory) {
    return (
      <div className="app-bg flex min-h-[100dvh] items-center justify-center">
        <p className="font-body text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  return (
    <div className="app-bg mobile-shell flex h-[100dvh] flex-col overflow-hidden text-foreground">
      <ShellModals mailOpen={mailOpen} onMailOpenChange={setMailOpen} />

      {linkOpen ? (
        <LinkAccountSheet
          discordAuth={discordAuth}
          onClose={() => setLinkOpen(false)}
          onSessionReplaced={(s) => {
            setLinkOpen(false);
            onSessionReplaced?.(s);
          }}
        />
      ) : null}

      {char && !chromeHidden ? (
        <header className="mobile-shell-header flex shrink-0 items-center gap-3 px-4 py-2">
          <div className="relative shrink-0">
            <div className="h-9 w-9 overflow-hidden rounded-full border border-gold/40">
              <Avatar className="h-full w-full">
                {inventory.discord?.avatar_url ? (
                  <AvatarImage src={String(inventory.discord.avatar_url)} alt="" />
                ) : (
                  <AvatarFallback className="text-[10px]">
                    {(displayName || "Adventurer").slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                )}
              </Avatar>
            </div>
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-1.5">
              <span className="truncate font-display text-sm text-gold-bright">
                {char.name || displayName || "Adventurer"}
              </span>
              <span className="shrink-0 text-[11px] text-muted-foreground">Lv {char.level ?? "—"}</span>
            </div>
            {hpMax > 0 ? (
              <div className="mobile-hp-track mt-1 h-1 w-full overflow-hidden rounded-full">
                <div className="mobile-hp-fill h-full rounded-full" style={{ width: `${hpPct}%` }} />
              </div>
            ) : null}
          </div>

          <div className="mobile-gold-pill flex shrink-0 items-center gap-1 px-2.5 py-1">
            <span aria-hidden>🪙</span>
            <span className="font-display text-xs tabular-nums">{gold.toLocaleString()}</span>
          </div>

          <button
            type="button"
            onClick={() => setMailOpen(true)}
            aria-label={mailBadgeActive ? "Mailbox, undelivered rewards" : "Mailbox"}
            className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gold/25"
          >
            <span className="select-none text-base leading-none" aria-hidden>✉️</span>
            {mailBadgeActive ? (
              <span className="absolute right-0.5 top-0.5 h-2 w-2 rounded-full bg-destructive" aria-hidden />
            ) : null}
          </button>
        </header>
      ) : null}

      {/* is-focus: combat/arena take the whole screen, so the shell drops its
          padding and lets the battlefield bleed to the edges. */}
      <main
        className={cn(
          "mobile-shell-main min-h-0 flex-1 overflow-y-auto overflow-x-clip",
          chromeHidden && "is-focus",
        )}
      >
        {tab === "Hero" && <HeroTab />}
        {tab === "Forge" && <Workbench />}
        {tab === "Explore" && <ExploreTab />}
        {tab === "Quests" && <QuestsTab />}
        {tab === "Combat" && <CombatTab focusMode={combatFocusActive} />}
        {tab === "Guild" && (
          <>
            <GuildJumpBar />
            <GuildTab />
          </>
        )}
        {tab === "Market" && <MarketTab />}
        {tab === "Arena" && <PvpPage />}
        {tab === "Pass" && <BattlePassTab />}
        {tab === "Realm" && <RealmTab />}
      </main>

      {moreOpen ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/65 backdrop-blur-sm"
            aria-label="Close menu"
            onClick={() => setMoreOpen(false)}
          />
          <div
            className="mobile-more-sheet fixed inset-x-0 bottom-0 z-50 max-h-[75dvh] overflow-y-auto px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-3"
            role="dialog"
            aria-modal="true"
            aria-label="More tabs"
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-gold/30" aria-hidden />
            <div className="mb-3 flex items-center justify-between">
              <span className="font-display text-sm tracking-wide text-gold-bright">More</span>
              <button
                type="button"
                onClick={() => setMoreOpen(false)}
                aria-label="Close menu"
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-gold/25"
              >
                <X className="h-4 w-4" strokeWidth={1.75} />
              </button>
            </div>

            <div className="space-y-4">
              {onSignOut || discordAuth ? (
                <section>
                  <div className="mb-1.5 font-display text-[10px] uppercase tracking-[0.3em] text-gold-dim">
                    Account
                  </div>
                  <div className="space-y-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        const next = !remindOn;
                        setRemindOn(next);
                        void setRemindersEnabled(next);
                      }}
                      className="flex w-full items-center justify-between rounded-lg border border-border px-3 py-2.5 text-left text-[12px] text-muted-foreground"
                    >
                      <span>Daily reminder</span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                          remindOn ? "bg-gold/20 text-gold-bright" : "bg-black/40 text-muted-foreground",
                        )}
                      >
                        {remindOn ? "ON" : "OFF"}
                      </span>
                    </button>
                    {discordAuth ? (
                      <button
                        type="button"
                        onClick={() => {
                          setMoreOpen(false);
                          setLinkOpen(true);
                        }}
                        className="w-full rounded-lg border border-border px-3 py-2.5 text-left text-[12px] text-muted-foreground"
                      >
                        Link Discord
                      </button>
                    ) : null}
                    {onSignOut ? (
                      <button
                        type="button"
                        onClick={() => {
                          setMoreOpen(false);
                          onSignOut();
                        }}
                        className="w-full rounded-lg border border-border px-3 py-2.5 text-left text-[12px] text-muted-foreground"
                      >
                        Sign out
                      </button>
                    ) : null}
                  </div>
                </section>
              ) : null}

              {MORE_GROUPS.map((group) => (
                <section key={group.label}>
                  <div className="mb-1.5 font-display text-[10px] uppercase tracking-[0.3em] text-gold-dim">
                    {group.label}
                  </div>
                  <ul className="grid grid-cols-3 gap-2" role="list">
                    {group.tabs.map((t) => {
                      const Icon = t.icon;
                      const active = tab === t.id;
                      return (
                        <li key={t.id}>
                          <button
                            type="button"
                            onClick={() => selectTab(t.id)}
                            aria-current={active ? "page" : undefined}
                            className={cn(
                              "mobile-more-tile flex h-full w-full flex-col items-center gap-1.5 px-2 py-3",
                              active && "is-active",
                            )}
                          >
                            <Icon className="h-5 w-5" strokeWidth={1.5} />
                            <span className="font-display text-[11px] leading-tight">{t.label}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </div>
        </>
      ) : null}

      {!chromeHidden ? (
        <nav
          className="mobile-tabbar flex shrink-0 items-stretch pb-[env(safe-area-inset-bottom)]"
          aria-label="Main"
        >
          {PRIMARY.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => selectTab(t.id)}
                aria-current={active ? "page" : undefined}
                className={cn("mobile-tab flex-1", active && "is-active")}
              >
                <Icon className="h-5 w-5" strokeWidth={1.5} aria-hidden />
                <span className="mobile-tab-label">{t.label}</span>
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => setMoreOpen((v) => !v)}
            aria-expanded={moreOpen}
            aria-current={moreActive ? "page" : undefined}
            className={cn("mobile-tab flex-1", (moreOpen || moreActive) && "is-active")}
          >
            <LayoutGrid className="h-5 w-5" strokeWidth={1.5} aria-hidden />
            <span className="mobile-tab-label">{activeMoreTab?.label ?? "More"}</span>
          </button>
        </nav>
      ) : null}
    </div>
  );
}
