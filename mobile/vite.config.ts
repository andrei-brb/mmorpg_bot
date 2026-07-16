import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";

// The mobile app is a thin native shell that renders the SAME game UI as the
// Discord Activity. `@` resolves into ../activity/src (the one source of truth);
// `@mobile` is mobile-only glue (native auth, secure storage).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8080";

  return {
    base: "/",
    // Ship the Activity's public assets — mobs, bosses, character portraits,
    // skills, zone maps, textures. Vite defaults publicDir to <root>/public,
    // i.e. mobile/public, which does not exist: the alias above shares the game's
    // CODE but nothing shared its ART, so every URL-referenced image (e.g.
    // /mobs/ice_claw_bear.png, /portraits/characters/warrior_arms.png) 404'd on
    // device and fell back to placeholder.svg — the "?" boxes in combat, and the
    // blank zone map in Explore. Asset-imported images were unaffected because
    // Vite bundles those, which is why the paperdoll rendered but portraits did not.
    publicDir: path.resolve(__dirname, "../activity/public"),
    server: {
      port: 5174,
      strictPort: true,
      proxy: {
        "/api": { target: proxyTarget, changeOrigin: true },
        "/health": { target: proxyTarget, changeOrigin: true },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "../activity/src"),
        "@mobile": path.resolve(__dirname, "./src"),
      },
      // Force a single React copy across the shared activity/src code and the
      // mobile shell — mixed copies would break hooks/context.
      dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime"],
    },
  };
});
