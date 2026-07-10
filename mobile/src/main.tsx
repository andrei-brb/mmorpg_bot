import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
// The shared game UI + styles live in ../activity/src (aliased as `@`).
import App from "@/App";
import "@/index.css";
import "@/styles/wom-emergent.css";
import "@/style.css";
import { DiscordOAuthAuth } from "@mobile/platform/DiscordOAuthAuth";

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
    <App authProvider={authProvider} />
  </QueryClientProvider>,
);
