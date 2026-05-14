import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "980px",
      },
    },
    extend: {
      fontFamily: {
        display: ["Cinzel", "serif"],
        blackletter: ["Pirata One", "Cinzel", "serif"],
        body: ["Chivo", "Helvetica Neue", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        cinzel: ["Cinzel", "serif"],
        crimson: ["Crimson Text", "serif"],
        pixel: ["Press Start 2P", "cursive"],
        serif: ["Cinzel", "Times New Roman", "serif"],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        gold: {
          DEFAULT: "hsl(var(--gold))",
          dim: "hsl(var(--gold-dim))",
          50: "#fff8e1",
          200: "#f5dc8a",
          400: "#d4a94e",
          500: "#b89758",
          600: "#8c6b34",
          700: "#5d4720",
        },
        crimson: {
          400: "#d44848",
          500: "#b02020",
          600: "#7d0a0a",
        },
        ember: "#ff6b1a",
        arcane: "#5fa8ff",
        verdant: "#6ee36e",
        "bg-void": "#050505",
        "bg-panel": "#111114",
        "bg-raised": "#17171c",
        panel: {
          bg: "oklch(0.155 0.01 260 / <alpha-value>)",
          border: "oklch(0.32 0.04 75 / <alpha-value>)",
        },
        "enemy-red": "oklch(0.52 0.22 25 / <alpha-value>)",
        "boss-purple": "oklch(0.52 0.18 300 / <alpha-value>)",
        "safe-green": "oklch(0.55 0.14 150 / <alpha-value>)",
        "xp-blue": "oklch(0.58 0.18 240 / <alpha-value>)",
        "npc-teal": "oklch(0.58 0.12 195 / <alpha-value>)",
        connected: "hsl(var(--connected))",
        stone: {
          DEFAULT: "hsl(var(--stone))",
          light: "hsl(var(--stone-light))",
          dark: "hsl(var(--stone-dark))",
        },
        frame: {
          outer: "hsl(var(--frame-outer))",
          mid: "hsl(var(--frame-mid))",
          inner: "hsl(var(--frame-inner))",
          highlight: "hsl(var(--frame-highlight))",
          rim: "hsl(var(--frame-rim))",
        },
        parchment: "hsl(var(--parchment))",
        rarity: {
          common: "hsl(var(--rarity-common))",
          uncommon: "hsl(var(--rarity-uncommon))",
          rare: "hsl(var(--rarity-rare))",
          epic: "hsl(var(--rarity-epic))",
          legendary: "hsl(var(--rarity-legendary))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "var(--radius)",
        sm: "var(--radius)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
