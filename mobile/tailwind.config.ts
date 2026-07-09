import type { Config } from "tailwindcss";
// Reuse the Discord Activity's exact theme (fonts, colors, keyframes) so the
// mobile app looks identical. Only the content globs change: scan the shared
// activity/src (the one UI source of truth) plus any mobile-only files.
import activityConfig from "../activity/tailwind.config.ts";

export default {
  ...activityConfig,
  content: [
    "../activity/src/**/*.{ts,tsx}",
    "../activity/components/**/*.{ts,tsx}",
    "../activity/pages/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
    "./index.html",
  ],
} satisfies Config;
