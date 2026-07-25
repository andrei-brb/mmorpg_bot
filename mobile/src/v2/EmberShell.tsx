import { useCallback, useEffect, useMemo, useState } from "react";
import { useGameSession } from "@/context/GameSessionContext";
import { cn } from "@/lib/utils";
import { EMBER_TABS, type EmberTab } from "@mobile/v2/tabs";
import { useCampData } from "@mobile/v2/useCampData";
import { CampScreen } from "@mobile/v2/screens/CampScreen";
import { VentureScreen } from "@mobile/v2/screens/VentureScreen";
import { HeroScreen } from "@mobile/v2/screens/HeroScreen";
import { RealmScreen } from "@mobile/v2/screens/RealmScreen";
import { LegendScreen } from "@mobile/v2/screens/LegendScreen";
import { SettingsSheet } from "@mobile/v2/screens/SettingsSheet";
import type { StoredSession } from "@mobile/platform/sessionStore";
import type { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";

/**
 * The Ember shell: 5 intent-shaped tabs instead of 10 system-shaped ones.
 *
 * Deliberately NOT a fork of MobileGameShell — this is a different structure,
 * not a restyle of the same one. It consumes the same session context and the
 * same API, so both UIs drive one character on live data.
 */

/** Classic tabs still fire `game:setActiveTab` (GameTabs.tsx:136-143) from
 *  Explore, Quests, Guild and Social. Those components are reused inside this
 *  shell, so their navigation has to land somewhere sensible. */
const CLASSIC_TO_EMBER: Record<string, EmberTab> = {
  Hero: "hero",
  Forge: "hero",
  Explore: "venture",
  Quests: "venture",
  Combat: "venture",
  Guild: "realm",
  Market: "realm",
  Arena: "realm",
  Pass: "legend",
  Realm: "legend",
};

export function EmberShell({
  onSignOut,
  onExitEmber,
  discordAuth,
  onSessionReplaced,
}: {
  onSignOut?: () => void;
  /** Switch back to the classic UI. */
  onExitEmber?: () => void;
  discordAuth?: DiscordOAuthAuth;
  onSessionReplaced?: (s: StoredSession) => void;
}) {
  const { inventory, combatFocusActive, arenaFocusActive } = useGameSession();
  const [tab, setTab] = useState<EmberTab>("camp");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const camp = useCampData();

  const chromeHidden = combatFocusActive || arenaFocusActive;

  useEffect(() => {
    const onSet = (ev: Event) => {
      const raw = String((ev as CustomEvent).detail ?? "");
      const next = CLASSIC_TO_EMBER[raw];
      if (next) setTab(next);
    };
    window.addEventListener("game:setActiveTab", onSet);
    return () => window.removeEventListener("game:setActiveTab", onSet);
  }, []);

  const go = useCallback((t: EmberTab) => setTab(t), []);

  /** How many things on Camp actually want the player. Drives the tab badge —
   *  the classic UI makes you visit every tab to discover this. */
  const campCount = useMemo(() => {
    let n = 0;
    if (Number(camp.idle?.pending_gold ?? 0) > 0 || Number(camp.idle?.pending_xp ?? 0) > 0) n++;
    if (camp.daily?.is_complete) n++;
    const job = inventory?.craft_job;
    if (job && (job.status === "ready" || (job.completes_at && Date.parse(String(job.completes_at)) <= Date.now())))
      n++;
    return n;
  }, [camp.idle, camp.daily, inventory?.craft_job]);

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
      <main className={cn("e-scroll min-h-0 flex-1", chromeHidden && "pb-0")}>
        {tab === "camp" && <CampScreen camp={camp} onGo={go} onOpenSettings={() => setSettingsOpen(true)} />}
        {tab === "venture" && <VentureScreen />}
        {tab === "hero" && <HeroScreen />}
        {tab === "realm" && <RealmScreen discordAuth={discordAuth} onSessionReplaced={onSessionReplaced} />}
        {tab === "legend" && <LegendScreen camp={camp} />}
      </main>

      {settingsOpen ? (
        <SettingsSheet
          onClose={() => setSettingsOpen(false)}
          onSignOut={onSignOut}
          onExitEmber={onExitEmber}
        />
      ) : null}

      {!chromeHidden ? (
        <nav className="e-tabbar flex shrink-0 items-stretch" aria-label="Main">
          {EMBER_TABS.map((t) => {
            const active = tab === t.id;
            const badge = t.id === "camp" ? campCount : 0;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                aria-current={active ? "page" : undefined}
                aria-label={`${t.label} — ${t.question}`}
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
        </nav>
      ) : null}
    </div>
  );
}
