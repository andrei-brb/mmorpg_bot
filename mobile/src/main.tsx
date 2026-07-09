import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
// The shared game UI + styles live in ../activity/src (aliased as `@`).
import App from "@/App";
import "@/index.css";
import "@/styles/wom-emergent.css";
import "@/style.css";

const queryClient = new QueryClient();

// Phase 0: mounts the shared App with the default (Discord Activity) provider,
// which proves the code-sharing build. Phase 1 injects `authProvider={new
// DiscordOAuthAuth(...)}` here so the app authenticates standalone on device;
// Phase 2 adds a login screen that also offers NativeAuth (Apple/Google/email).
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
);
