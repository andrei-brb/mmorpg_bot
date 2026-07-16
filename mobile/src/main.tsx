import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
// The shared game UI + styles live in ../activity/src (aliased as `@`). The
// shell itself is mobile-only: MobileApp mounts a phone-native bottom-tab shell
// around the same shared tab components.
import MobileApp from "@mobile/MobileApp";
import "@/index.css";
import "@/styles/wom-emergent.css";
import "@/style.css";
// Mobile-only reskin. Loaded last so it overrides the shared tokens/chrome; the
// Discord Activity never imports it, so its look is unchanged.
import "@mobile/skin-reliquary.css";
import "@mobile/mobile-layout.css";
import { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";

// Two separate signals, deliberately:
//   data-skin     → colour (Reliquary)
//   data-platform → layout (phone)
// Keeping them apart means a skin could later ship to Discord, or a second skin
// to mobile, without one dragging the other along.
//
// data-platform exists because width media queries CANNOT carry this: the
// Discord Activity iframe is also under 640px, so every Tailwind sm:/md: rule is
// inactive in BOTH places (see the comment at HeroTab.tsx:750, where the author
// hardcoded flex-row for exactly this reason). useIsMobile() is width-based too
// and would return true inside the iframe. Only an explicit attribute set by the
// native shell distinguishes "phone" from "narrow desktop panel".
document.documentElement.dataset.skin = "reliquary";
document.documentElement.dataset.platform = "mobile";

const queryClient = new QueryClient();

// Standalone Discord login (works on device and in a plain browser). Phase 2
// adds a login screen that also offers NativeAuth (Apple/Google/email); for now
// the app signs in with Discord and lands on the same cross-play character.
const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID as string | undefined;
// Discord only accepts https redirects, so we register a backend bounce page
// there and it forwards the code into the app via the custom-scheme deep link.
const oauthRedirectUri =
  (import.meta.env.VITE_DISCORD_REDIRECT_URI as string | undefined) ??
  "https://worker-production-1427.up.railway.app/auth/mobile-callback";
const appDeepLink =
  (import.meta.env.VITE_DISCORD_APP_DEEPLINK as string | undefined) ??
  "com.wold.mmo://auth/discord";
const authProvider = clientId
  ? new DiscordOAuthAuth(clientId, oauthRedirectUri, appDeepLink)
  : undefined;

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <MobileApp authProvider={authProvider} />
  </QueryClientProvider>,
);
