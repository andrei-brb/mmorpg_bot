# Step 2 — CSS foundation (done)

**Goal:** Shared design tokens, typography (system font), spacing, radii, shadows, and reusable **combat layout primitives** for Step 3 markup.

**Source of truth:** `activity/src/style.css`

---

## 1. Tokens (`:root`)

| Group | Examples |
|-------|-----------|
| Surfaces | `--combat-bg-deep`, `--combat-surface`, `--combat-surface-raised`, `--combat-scene-base` |
| Borders | `--combat-border`, `--combat-border-strong`, `--combat-border-accent` |
| Text | `--combat-text`, `--combat-text-muted`, `--combat-text-highlight` |
| Accents | `--combat-accent`, `--combat-success`, `--combat-danger-*`, `--combat-warning` |
| HP | `--combat-hp-track`, `--combat-hp-player`, `--combat-hp-enemy` |
| Radii | `--combat-radius-sm` … `--combat-radius-xl` |
| Shadows | `--combat-shadow-soft`, `--combat-shadow-inset-tab`, `--combat-shadow-drop` |
| Spacing | `--combat-space-1` … `--combat-space-6` |
| Layout | `--combat-shell-max-width`, `--combat-touch-min` (44px) |
| Typography | `--font-sans`, `--combat-text-xs` … `--combat-text-xl` |

**Legacy aliases** (`--bg`, `--panel`, `--text`, …) still map to the same palette so Hero/Progress screens stay consistent.

---

## 2. Battlefield placeholder

`.bg-layer` uses a **CSS-only gradient** (no image). When you add `activity/public/assets/bg/zone-default.jpg`, you can layer it in CSS (see `COMBAT_VISUAL_SPEC_STEP1.md`).

---

## 3. Layout primitives (for Step 3)

| Class | Role |
|-------|------|
| `.combat-panel` | Generic glassy panel |
| `.combat-zone-bar` + `__title` / `__meta` | Zone B; **`__meta` hidden ≤767px** (IDs on desktop only) |
| `.combat-mid-band` + `__log` / `__party` | Zone E; **mobile order: log → party** |
| `.combat-footer-nav` + `__item` | Zone G; 2×2 grid on mobile |

Existing combat UI still uses `.scene`, `.log-box`, `.skills`, `.footer` — now token-backed.

---

## 4. Breakpoint

- **≤767px:** Spec mobile layout; zone meta hidden; combat mid-band column order; footer nav grid; scene tweaks.

**Done:** Step 3 — see `COMBAT_VISUAL_STEP3.md`.
