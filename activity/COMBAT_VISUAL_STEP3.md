# Step 3 — Combat HTML structure (done)

**Implementation:** `renderCombatState()` in `activity/src/main.ts`  
**Styles:** `activity/src/style.css` (`.party-strip`, `.party-sidebar`, `.scene-sprite`, zone bar `__right` / `__turn`)

---

## Zones (B–G)

| Zone | Markup | Notes |
|------|--------|--------|
| **B** | `.combat-zone-bar` | Title (`zoneLabel` or default “🌲 Current battle”), **Turn** always visible, **Guild · Channel** in `.combat-zone-bar__meta` (hidden ≤767px per Step 1) |
| **C** | `.scene-wrap` → `.scene` | `.bg-layer` gradient placeholder; `.scene-sprite` emoji placeholders (no image 404s) |
| **D** | `.party-strip` | 3 cards: real hero + 2 “Reserve / Party (soon)” (visual only) |
| **E** | `.combat-mid-band` | **Desktop:** party sidebar (left) · log (right). **Mobile:** log first (`order`), then party |
| **F** | `.skills` | Unchanged wiring (`data-abi`, flee, potion) |
| **G** | `nav.combat-footer-nav` | Back · Map · Quest Log · Profile (non-interactive labels for now) |

---

## Context passed from Discord

`mountApp` passes `combatUiMeta()` → `{ guildId, channelId }` into `renderCombatState` for the zone bar. Optional `zoneLabel` can be added later when a travel/zone API exists.

---

**Next:** Steps 4 & 6 — see `COMBAT_VISUAL_STEP4_AND_6.md`.
