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
