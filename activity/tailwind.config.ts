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
        cinzel: ["Cinzel", "serif"],
        crimson: ["Crimson Text", "serif"],
        pixel: ["Press Start 2P", "cursive"],
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
        },
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
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
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
        "pulse-glow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        "float-particle": {
          "0%": { transform: "translateY(0) translateX(0)", opacity: "0.35" },
          "100%": { transform: "translateY(-140px) translateX(16px)", opacity: "0" },
        },
        "fighter-hit": {
          "0%, 100%": { transform: "translateX(0)" },
          "20%": { transform: "translateX(-5px)" },
          "40%": { transform: "translateX(5px)" },
          "60%": { transform: "translateX(-4px)" },
          "80%": { transform: "translateX(4px)" },
        },
        "fighter-attack-right": {
          "0%": { transform: "translateX(0)" },
          "35%": { transform: "translateX(22px) scale(1.02)" },
          "100%": { transform: "translateX(0)" },
        },
        "fighter-attack-left": {
          "0%": { transform: "translateX(0)" },
          "35%": { transform: "translateX(-22px) scale(1.02)" },
          "100%": { transform: "translateX(0)" },
        },
        "hit-flash": {
          "0%, 100%": { opacity: "0" },
          "50%": { opacity: "1" },
        },
        "damage-float": {
          "0%": { transform: "translateY(0) scale(1)", opacity: "1" },
          "100%": { transform: "translateY(-52px) scale(1.08)", opacity: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "float-particle": "float-particle 5s linear infinite",
        "fighter-hit": "fighter-hit 0.45s ease-out",
        "fighter-attack-right": "fighter-attack-right 0.5s ease-out",
        "fighter-attack-left": "fighter-attack-left 0.5s ease-out",
        "hit-flash": "hit-flash 0.38s ease-out",
        "damage-float": "damage-float 1.15s ease-out forwards",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
