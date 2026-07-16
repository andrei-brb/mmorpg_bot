import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GameSessionProvider } from "@/context/GameSessionContext";
import type { AuthProvider } from "@/context/auth/types";
import { ActivityGate } from "@/components/ActivityGate";
import { BattleRendererProvider } from "@/context/BattleRenderer";
import { MobileGameShell } from "@mobile/shell/MobileGameShell";
import { DrawerBattle } from "@mobile/combat/DrawerBattle";

/**
 * Mobile root. Mirrors activity/src/App.tsx's provider stack exactly, but mounts
 * MobileGameShell instead of routing to GameShell.
 *
 * The router is dropped on purpose: App.tsx only routes "/" (the game),
 * "/battle-preview-demo" (a dev page) and a 404. A native app has no address
 * bar, so BrowserRouter would add a history stack nothing navigates. In-game
 * navigation goes through the `game:setActiveTab` event, which the shell
 * handles directly.
 *
 * Toaster position differs: Sonner sits top-right in the Activity, which on a
 * phone collides with the notch and the header. Toasts come from the bottom,
 * above the tab bar.
 */
const MobileApp = ({ authProvider }: { authProvider?: AuthProvider } = {}) => (
  <GameSessionProvider authProvider={authProvider}>
    <TooltipProvider>
      <Toaster />
      <Sonner position="bottom-center" />
      <ActivityGate>
        {/* Combat renders as a phone-native drawer instead of the Activity's
            three-column arena. Layout only — same data, same skill grid. */}
        <BattleRendererProvider renderer={DrawerBattle}>
          <MobileGameShell />
        </BattleRendererProvider>
      </ActivityGate>
    </TooltipProvider>
  </GameSessionProvider>
);

export default MobileApp;
