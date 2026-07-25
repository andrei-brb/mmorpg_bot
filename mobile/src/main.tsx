import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
// The shared game UI + styles live in ../activity/src (aliased as `@`). The
// shell is mobile-only: MobileApp mounts the Ember shell around the same shared
// data layer and, for Explore and Forge, the same shared tab components.
import MobileApp from "@mobile/MobileApp";
import "@/index.css";
import "@/styles/wom-emergent.css";
import "@/style.css";
import "@mobile/mobile-layout.css";
import { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";

// Two signals, set synchronously so no frame paints unstyled:
//   data-ui       → the Ember design (colour + the skin over classic tabs)
//   data-platform → phone layout
//
// data-platform exists because width media queries CANNOT carry this: the
// Discord Activity iframe is also under 640px, so every Tailwind sm:/md: rule is
// inactive in BOTH places (see the comment at HeroTab.tsx:750, where the author
// hardcoded flex-row for exactly this reason). useIsMobile() is width-based too
// and would return true inside the iframe. Only an explicit attribute set by the
// native shell distinguishes "phone" from "narrow desktop panel".
//
// They stay separate rather than becoming one flag: layout and colour are
// genuinely different concerns, and merging them would make either impossible to
// change alone.
document.documentElement.dataset.ui = "ember";
document.documentElement.dataset.platform = "mobile";

const queryClient = new QueryClient();

// Discord OAuth, offered alongside game accounts on the login screen. Signing in
// this way lands on the same cross-play character as the Discord Activity.
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
