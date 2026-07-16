import { useCallback, useEffect, useState } from "react";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GameSessionProvider } from "@/context/GameSessionContext";
import type { AuthProvider } from "@/context/auth/types";
import { ActivityGate } from "@/components/ActivityGate";
import { BattleRendererProvider } from "@/context/BattleRenderer";
import { MobileGameShell } from "@mobile/shell/MobileGameShell";
import { LoginScreen } from "@mobile/shell/LoginScreen";
import { DrawerBattle } from "@mobile/combat/DrawerBattle";
import { StoredTokenAuth } from "@mobile/platform/StoredTokenAuth";
import {
  clearSession,
  loadSession,
  saveSession,
  type StoredSession,
} from "@mobile/platform/sessionStore";

/**
 * Mobile root.
 *
 * The session is resolved BEFORE the game mounts — read from storage, or
 * obtained through the login screen. Only then is GameSessionProvider given a
 * provider that already holds the token.
 *
 * That ordering is deliberate: GameSessionContext's boot effect calls
 * authenticate() exactly once on mount and has no notion of a login screen
 * (activity/src/components/ActivityGate.tsx is a passive spinner). Rather than
 * teach a shared file about login UI, the shell settles the question first and
 * hands over a resolved token. Nothing in activity/src changes, and the Discord
 * Activity still authenticates silently against its host.
 *
 * The token is persisted (mobile/src/platform/sessionStore.ts). Before this,
 * it lived in a useState and died with the page, so every cold start re-ran the
 * full Discord browser consent bounce.
 */

type Boot = { state: "loading" } | { state: "anon" } | { state: "authed"; session: StoredSession };

const MobileApp = ({ authProvider }: { authProvider?: AuthProvider } = {}) => {
  const [boot, setBoot] = useState<Boot>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const s = await loadSession();
      if (cancelled) return;
      setBoot(s ? { state: "authed", session: s } : { state: "anon" });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onAuthed = useCallback(async (s: StoredSession) => {
    await saveSession(s);
    setBoot({ state: "authed", session: s });
  }, []);

  const onSignOut = useCallback(async () => {
    await clearSession();
    setBoot({ state: "anon" });
  }, []);

  if (boot.state === "loading") {
    return (
      <div className="app-bg flex min-h-[100dvh] items-center justify-center">
        <p className="font-body text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (boot.state === "anon") {
    return (
      <TooltipProvider>
        <Toaster />
        <Sonner position="bottom-center" />
        <LoginScreen discordAuth={authProvider} onAuthed={(s) => void onAuthed(s)} />
      </TooltipProvider>
    );
  }

  return (
    <GameSessionProvider
      // Remount the whole session when the token changes (sign out → sign in as
      // someone else) so no state from the previous player can leak across.
      key={boot.session.token}
      authProvider={new StoredTokenAuth(boot.session.token, boot.session.provider)}
    >
      <TooltipProvider>
        <Toaster />
        <Sonner position="bottom-center" />
        <ActivityGate>
          {/* Combat renders as a phone-native drawer instead of the Activity's
              three-column arena. Layout only — same data, same skill grid. */}
          <BattleRendererProvider renderer={DrawerBattle}>
            <MobileGameShell onSignOut={() => void onSignOut()} />
          </BattleRendererProvider>
        </ActivityGate>
      </TooltipProvider>
    </GameSessionProvider>
  );
};

export default MobileApp;
