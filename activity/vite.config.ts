import { defineConfig } from "vite";

// Base path so assets resolve when loaded from Discord's iframe
export default defineConfig({
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
  },
});
