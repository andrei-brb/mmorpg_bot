# Where to copy your PNGs

Copy files into **`mmorpg_bot/activity/public/`** (this folder’s parent is `public/`).  
Vite serves them at **`/assets/...`** in the built Activity.

Rename your art to the **exact filenames** below so `style.css` picks them up.

## Global — `public/assets/ui/global/`

| Save as | Your art (from prompts) |
|---------|-------------------------|
| `app-background.jpeg` | App background (full page) |
| `panel-texture.png` | Panel frame / texture overlay on panels |
| `tab-strip-bg.jpeg` | Tab bar strip (optional chrome behind tabs) |
| `btn-primary.png` | Primary button (stretches with button size) |
| `btn-secondary.png` | Secondary button |
| `mini-btn-bg.png` | Mini button (Use / Equip / Sell rows) |
| `tooltip-frame.png` | Item hover tooltip panel (optional; sits in `global/` for shared use) |

## Hero — `public/assets/ui/hero/`

| Save as | Your art |
|---------|----------|
| `equipment-slot-empty.png` | Universal empty equipment slot |
| `inventory-slot-empty.png` | Empty inventory grid cell |
| `coin-icon.png` | Gold coin (Hero + Progress gold line) |

## Explore — `public/assets/ui/explore/`

| Save as | Your art |
|---------|----------|
| `zone-panel-accent.jpeg` | Zone / explore header panel decoration |

## Quests — `public/assets/ui/quests/`

| Save as | Your art |
|---------|----------|
| `quest-card-bg.png` | Quest card parchment / frame |

## Combat — `public/assets/ui/combat/` and `public/assets/bg/`

| Save as | Your art |
|---------|----------|
| `../bg/combat-battlefield.jpg` | Battlefield background (under fighters) |
| `player-sprite.jpeg` | Player battle sprite |
| `enemy-sprite.png` | Enemy battle sprite |
| `zone-bar-bg.jpeg` | Combat zone title bar |
| `skill-slot.jpeg` | Skill bar button tile |
| `turn-banner-bg.jpeg` | “Your turn” ribbon |
| `combat-log-bg.png` | Combat log panel |
| `ally-portrait-frame.jpeg` | Dungeon allies sidebar portrait frame |
| `outcome-panel-bg.jpeg` | Victory outcome panel (wired in UI) |

Path note: **`combat-battlefield.jpg`** lives in **`public/assets/bg/`**. Extra combat art (dungeon bg, defeat plaque, orbs, etc.) stays under `ui/combat/` with kebab-case names for your own use.

## Progress — `public/assets/ui/progress/`

| Save as | Your art |
|---------|----------|
| `stat-card-bg.png` | Progress stat plaques |

## Modals — `public/assets/ui/modals/`

| Save as | Your art |
|---------|----------|
| `modal-backdrop.jpeg` | Dim overlay texture (optional) |
| `modal-card-bg.jpeg` | Enhance / modal card |
| `spec-option-bg.jpeg` | Specialization option row |

---

Until a file exists, the browser may log a 404 for that URL; the UI still uses the old CSS colors underneath.
