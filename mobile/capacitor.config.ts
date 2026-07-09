import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.wold.mmo",
  appName: "Wold of MMO",
  // Vite build output; `cap sync` copies this into the native projects.
  webDir: "dist",
  server: {
    androidScheme: "https",
  },
};

export default config;
