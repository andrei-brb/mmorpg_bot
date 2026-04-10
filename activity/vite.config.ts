import path from "path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8080";
  const testMode = env.VITE_TEST_MODE === "true";

  return {
    // Root-relative `/assets/...` URLs — avoids broken relative `./assets` resolution in some iframe paths.
    base: "/",
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": { target: proxyTarget, changeOrigin: true },
        "/health": { target: proxyTarget, changeOrigin: true },
      },
    },
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
        // In test mode, replace Discord SDK with mock to avoid real auth
        ...(testMode && { "@discord/embedded-app-sdk": path.resolve(__dirname, "./src/lib/mockDiscordSDK.ts") }),
      },
      dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime"],
    },
  };
});
