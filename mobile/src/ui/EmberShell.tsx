import { useCallback, useEffect, useMemo, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { cn } from "@/lib/utils";
import { ExploreTab } from "@/components/game/tabs/ExploreTab";
import { CraftingTab } from "@/components/game/tabs/CraftingTab";
import { CombatTab } from "@/components/game/tabs/CombatTab";
import {
  MORE_GROUPS,
  PRIMARY_TABS,
  normalizeClassicTab,
  tabById,
  type EmberTab,
  type TabDef,
} from "@mobile/ui/tabs";
import { useCampData } from "@mobile/ui/useCampData";
import { CampScreen } from "@mobile/ui/screens/CampScreen";
import { HeroScreen } from "@mobile/ui/screens/HeroScreen";
import { QuestsScreen } from "@mobile/ui/screens/QuestsScreen";
import { PassScreen } from "@mobile/ui/screens/PassScreen";
import { RealmScreen } from "@mobile/ui/screens/RealmScreen";
import { SettingsSheet } from "@mobile/ui/screens/SettingsSheet";
import { GuildPanel } from "@mobile/ui/parts/GuildPanel";
import { MarketPanel } from "@mobile/ui/parts/MarketPanel";
import { ArenaPanel } from "@mobile/ui/parts/ArenaPanel";
import { SessionModals } from "@mobile/ui/parts/SessionModals";
import type { StoredSession } from "@mobile/platform/sessionStore";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";

/**
 * The mobile game shell.
 *
 * Classic tab list plus Camp. Four tabs in the bar, the rest in a More sheet.
 * Explore, Forge and Combat render the CLASSIC components on purpose — they're
 * skinned, not rebuilt, so they pick up the Ember palette from ember-skin.css
 * without forking their layout, and inherit future changes for free. Combat's
 * selector in particular is already good; only the fight it launches is
 * replaced, by DrawerBattle.
 */

/** Ember-framed wrapper so rebuilt panels share one header treatment. */
function Screen({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-full pb-6" style={{ paddingTop: "calc(env(safe-area-inset-top) + 10px)" }}>
      <div className="mb-3 flex items-center gap-2 px-4">
        <span className="e-label flex-1">{title}</span>
        {right}
      </div>
      <div className="px-4">{children}</div>
    </div>
  );
}

export function EmberShell({
  onSignOut,
  discordAuth,
  onSessionReplaced,
}: {
  onSignOut?: () => void;
  discordAuth?: DiscordOAuthAuth;
  onSessionReplaced?: (s: StoredSession) => void;
}) {
  const { inventory, combatFocusActive, arenaFocusActive, lostDeliveries, refreshMap } =
    useGameSession();
  // Defaults high, not low: if the level has not loaded yet, briefly showing a
  // tab that is really locked is a far smaller error than briefly locking a tab
  // a level-60 player uses every day.
  const charLevel = inventory?.character?.level ?? 999;
  const [tab, setTab] = useState<EmberTab>("camp");
  const [moreOpen, setMoreOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mailOpen, setMailOpen] = useState(false);
  const camp = useCampData();

  const chromeHidden = combatFocusActive || arenaFocusActive;

  const go = useCallback((t: EmberTab) => {
    setTab(t);
    setMoreOpen(false);
  }, []);

  // Classic components navigate by firing this (GameTabs.tsx:136-143). Explore
  // and Quests both do, and Explore is rendered here as-is, so honouring it is
  // required, not optional.
  useEffect(() => {
    const onSet = (ev: Event) => {
      const next = normalizeClassicTab(String((ev as CustomEvent).detail ?? ""));
      if (next) go(next);
    };
    window.addEventListener("game:setActiveTab", onSet);
    return () => window.removeEventListener("game:setActiveTab", onSet);
  }, [go]);

  useEffect(() => {
    if (chromeHidden) setMoreOpen(false);
  }, [chromeHidden]);

  // Re-fetch the world when you open Explore. The map is now loaded at boot
  // (GameSessionContext), but it still goes stale while you're on other tabs —
  // world bosses spawn and despawn on their own schedule, and zone state moves
  // when other players act. Opening the tab is the natural moment to re-check.
  useEffect(() => {
    if (tab === "explore") void refreshMap();
  }, [tab, refreshMap]);

  /** Things on Camp that actually want the player. */
  const campCount = useMemo(() => {
    let n = 0;
    if (Number(camp.idle?.pending_gold ?? 0) > 0 || Number(camp.idle?.pending_xp ?? 0) > 0) n++;
    if (camp.daily?.is_complete) n++;
    const job = inventory?.craft_job;
    if (
      job &&
      (job.status === "ready" ||
        (job.completes_at && Date.parse(String(job.completes_at)) <= Date.now()))
    )
      n++;
    const login = camp.pass?.daily_login;
    if (camp.pass?.season?.is_live && login && !login.claimed_today) n++;
    return n;
  }, [camp.idle, camp.daily, camp.pass, inventory?.craft_job]);

  const activeMore = MORE_GROUPS.flatMap((g) => g.tabs).find((t) => t.id === tab) ?? null;

  if (!inventory) {
    return (
      <div className="ember-root grid min-h-[100dvh] place-items-center">
        <p className="text-sm" style={{ color: "var(--a-500)" }}>
          Lighting the fire…
        </p>
      </div>
    );
  }

  return (
    <div className="ember-root flex h-[100dvh] flex-col overflow-hidden">
      {/* Session modals live above the tabs because they're driven by session
          state, not by which screen you're on. Without these, a new player
          cannot create a character and nobody can accept a quest. */}
      <SessionModals mailOpen={mailOpen} onMailOpenChange={setMailOpen} />

      <main className="e-scroll min-h-0 flex-1">
        {tab === "camp" && (
          <CampScreen
            camp={camp}
            onGo={go}
            onOpenSettings={() => setSettingsOpen(true)}
            onOpenMail={() => setMailOpen(true)}
            mailCount={lostDeliveries.length}
          />
        )}

        {/* Skinned, not rebuilt — classic layout wearing the Ember palette.
            `classic-skin` scopes the mobile touch-target floor to markup that
            wasn't written for a phone; Ember's own controls size themselves. */}
        {tab === "explore" && (
          <Screen title="Explore">
            <div className="classic-skin">
              <ExploreTab />
            </div>
          </Screen>
        )}
        {tab === "forge" && (
          <Screen title="Forge">
            <div className="classic-skin">
              <CraftingTab />
            </div>
          </Screen>
        )}
        {/* Combat keeps the classic selector — zone picker, foe roster with risk
            tiers, preview. It's good, and rebuilding it gained nothing. The
            fight it launches still renders through DrawerBattle. */}
        {tab === "combat" && (
          <Screen title="Combat">
            <div className="classic-skin">
              <CombatTab />
            </div>
          </Screen>
        )}

        {tab === "quests" && <QuestsScreen />}
        {tab === "hero" && <HeroScreen />}
        {tab === "pass" && <PassScreen camp={camp} />}
        {tab === "realm" && (
          <RealmScreen discordAuth={discordAuth} onSessionReplaced={onSessionReplaced} />
        )}

        {tab === "guild" && (
          <Screen title="Guild">
            <GuildPanel />
          </Screen>
        )}
        {tab === "market" && (
          <Screen title="Market">
            <MarketPanel />
          </Screen>
        )}
        {tab === "arena" && (
          <Screen title="Arena">
            <ArenaPanel />
          </Screen>
        )}
      </main>

      {/* ── More ── */}
      {moreOpen ? (
        <>
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setMoreOpen(false)}
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm"
          />
          <div
            className="e-sheet e-scroll fixed inset-x-0 bottom-0 z-50 max-h-[76dvh] px-4"
            role="dialog"
            aria-modal="true"
            aria-label="More"
          >
            <div className="e-grabber" />
            <div className="mb-3 flex items-center">
              <span className="e-display flex-1 text-[15px]" style={{ color: "var(--e-300)" }}>
                More
              </span>
              <button
                type="button"
                onClick={() => {
                  setMoreOpen(false);
                  setSettingsOpen(true);
                }}
                className="e-pill e-pill--quiet"
              >
                Settings
              </button>
            </div>

            <div className="space-y-4 pb-2">
              {MORE_GROUPS.map((group) => (
                <section key={group.label}>
                  <div className="e-label mb-2">{group.label}</div>
                  <div className="grid grid-cols-3 gap-2">
                    {group.tabs.map((t) => {
                      const active = tab === t.id;
                      // Locked tabs stay visible rather than disappearing: the
                      // point is to show what is coming, not to hide the game.
                      const locked = Boolean(t.unlockLevel && charLevel < t.unlockLevel);
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => (locked ? undefined : go(t.id))}
                          aria-current={active ? "page" : undefined}
                          aria-disabled={locked}
                          title={locked ? `${t.lockedHint ?? ""} Unlocks at level ${t.unlockLevel}.`.trim() : t.hint}
                          className="relative flex flex-col items-center gap-1.5 rounded-xl px-2 py-3"
                          style={{
                            border: `1px solid ${active ? "var(--e-500)" : "var(--n-500)"}`,
                            background: active ? "rgba(255,122,47,0.1)" : "rgba(0,0,0,0.28)",
                            color: active ? "var(--e-400)" : "var(--a-300)",
                            opacity: locked ? 0.42 : 1,
                            cursor: locked ? "not-allowed" : undefined,
                          }}
                        >
                          {locked ? (
                            <span
                              className="e-num absolute right-1 top-1 rounded px-1 text-[9px] font-bold"
                              style={{ background: "rgba(0,0,0,0.6)", color: "var(--a-500)" }}
                            >
                              Lv{t.unlockLevel}
                            </span>
                          ) : null}
                          <svg
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden
                          >
                            <path d={t.icon} />
                          </svg>
                          <span className="text-[11px] font-semibold leading-tight">{t.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </>
      ) : null}

      {settingsOpen ? (
        <SettingsSheet onClose={() => setSettingsOpen(false)} onSignOut={onSignOut} />
      ) : null}

      {/* ── Bar ── */}
      {!chromeHidden ? (
        <nav className="e-tabbar flex shrink-0 items-stretch" aria-label="Main">
          {PRIMARY_TABS.map((t: TabDef) => {
            const active = tab === t.id;
            const badge = t.id === "camp" ? campCount : 0;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => go(t.id)}
                aria-current={active ? "page" : undefined}
                aria-label={`${t.label} — ${t.hint}`}
                className={cn("e-tab", active && "is-active")}
              >
                <svg
                  width="21"
                  height="21"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={active ? 2 : 1.6}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d={t.icon} />
                </svg>
                <span className="e-tab-label">{t.label}</span>
                {badge > 0 ? <span className="e-tab-dot e-num">{badge}</span> : null}
              </button>
            );
          })}

          <button
            type="button"
            onClick={() => setMoreOpen((v) => !v)}
            aria-expanded={moreOpen}
            aria-current={activeMore ? "page" : undefined}
            className={cn("e-tab", (moreOpen || activeMore) && "is-active")}
          >
            <svg
              width="21"
              height="21"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={moreOpen || activeMore ? 2 : 1.6}
              strokeLinecap="round"
              aria-hidden
            >
              <circle cx="5" cy="12" r="1.6" />
              <circle cx="12" cy="12" r="1.6" />
              <circle cx="19" cy="12" r="1.6" />
            </svg>
            {/* Shows which tab you're on when it lives in the sheet, so More
                never reads as "nowhere". */}
            <span className="e-tab-label">{activeMore ? activeMore.label : "More"}</span>
          </button>
        </nav>
      ) : null}
    </div>
  );
}
