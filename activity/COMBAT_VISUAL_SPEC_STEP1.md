# Step 1 — Combat visual spec (desktop + mobile)

**Scope:** Purely visual shell for the Combat tab. No party/dungeon mechanics yet — we only *display* multi-slot UI with mock or repeated data where needed.

**Product:** Discord Embedded Activity (in-app browser). Treat **mobile** as a first-class layout (stacked columns, full width, thumb-friendly targets).

### Confirmed decisions

| Decision | Value |
|----------|--------|
| Mobile mid band (zone **E**) stack order | **Log first**, then “Your Party” list |
| Breakpoints | **768px** — desktop `≥ 768px`, mobile `≤ 767px` |
| Zone bar — guild/channel IDs | **Show on desktop**, **hide on mobile** (zone name only on small screens) |
| Assets | **Placeholders** (CSS / gradients / no custom image files for now) |
| Font | **System** stack (no custom WOFF2) |
| Footer nav (zone **G**) | **Back** · **Map** · **Quest Log** · **Profile** — you confirmed **Back**; the other three follow the spec defaults (change anytime before build). |

**Step 1 product inputs: complete.**

**Step 2:** CSS tokens + primitives — `COMBAT_VISUAL_STEP2.md`.  
**Step 3:** Combat HTML structure — `COMBAT_VISUAL_STEP3.md`. **Next: Step 4+** (mock polish / wiring).

---

## 1. Target layout zones (reference)

These map to the cinematic mock you shared. Names are for code/CSS later.

| Zone | Role |
|------|------|
| **A — App chrome** | Title row + main tabs (Hero / Combat / Progress) — already exists on shell |
| **B — Location bar** | Zone name (e.g. “Elwynn Forest”) + optional meta (IDs hidden on small screens) |
| **C — Battlefield** | Full-width **16:9-ish** hero image: background + optional vignette; enemy title overlay (e.g. elite tag) |
| **D — Party strip** | Horizontal row of **3 compact cards** (avatar, name, class/role, HP bar) — visual only for now |
| **E — Mid band (two columns)** | **Left:** “Your Party” vertical list (name, MP or secondary bar, small portrait). **Right:** combat log + “your turn” highlight + optional turn/damage stats |
| **F — Skill bar** | Icon or wide buttons: abilities + cost + **Flee**; wraps on narrow width |
| **G — Footer nav** | Back, Map, Quest Log, Profile (or your final labels) — single row; avoid duplicate buttons |

### Desktop (≥ 768px)

- **B** full width above **C**.
- **C** max width inside shell (can be `100%` of `.shell`).
- **D** full width under **C**.
- **E** as **CSS grid: `1fr 1.2fr`** or `minmax(220px, 0.4fr) minmax(0, 1fr)` — party column left, log right.
- **F** + **G** full width.

### Mobile (≤ 767px)

- **Stack vertically:** B → C → D → **E** becomes **single column**:
  - Order (**locked**): **Log → Party list** (combat context before roster).
- **D** (party strip): allow **horizontal scroll** (`overflow-x: auto`, snap optional) if 3 cards don’t fit.
- **F**: skills in **2 columns** or wrapped rows; minimum **44×44px** touch targets.
- **G**: footer can be **2×2 grid** or scrollable row if needed.
- **B**: truncate long IDs; show zone name only on small screens.

---

## 2. Viewport assumptions (Discord)

| Context | Typical width | Notes |
|---------|----------------|-------|
| Desktop Activity | ~900–1200px usable | Sidebars vary; keep content max-width but fluid |
| Mobile Discord | 320–430px | Safe area; avoid hover-only affordances |
| Min height | Short | Battlefield min-height scales down; log may scroll internally |

**We commit to these breakpoints:**

- `≤ 767px` — **mobile** layout (stacked).
- `≥ 768px` — **desktop** layout (two-column mid band).

(Optional fine-tuning: `≤ 480px` for extra-tight padding only.)

---

## 3. Asset manifest (what we need from you)

Place files under **`activity/public/`** so Vite serves them at `/assets/...`.  
Until you provide assets, we use **CSS gradients + placeholders** (no broken images).

### Required for “cinematic” look (priority)

| Asset ID | Path (suggested) | Purpose | Suggested spec |
|----------|------------------|---------|----------------|
| `bg_zone_default` | `/assets/bg/zone-default.jpg` | Battlefield background | **1920×1080** (or 1600×900), JPG/WebP, &lt; ~500KB if possible |
| `frame_party_card` | `/assets/ui/party-card-frame.png` | Optional frame behind party cards | PNG with transparency, **~280×120** |
| `icon_skill_slot` | `/assets/ui/skill-slot.png` | Empty skill slot chrome | PNG **64×64** tileable or 9-slice later |

### Per class / role (optional for v1 mock)

| Asset ID | Path pattern | Purpose | Suggested spec |
|----------|----------------|---------|----------------|
| `portrait_mage` | `/assets/portraits/mage.png` | Party strip + sidebar | **128×128** PNG, circular crop in CSS OK |
| `portrait_ranger` | `/assets/portraits/ranger.png` | … | same |
| `portrait_warrior` | `/assets/portraits/warrior.png` | … | same |

### Enemy / boss art (optional until you have combat variety)

| Asset ID | Path pattern | Purpose | Suggested spec |
|----------|----------------|---------|----------------|
| `enemy_bear` | `/assets/enemies/bear.png` | Sprite in scene (or full-bleed if you use one image for C) | **~256×256** or larger transparent PNG |

### Skill icons (optional)

| Asset ID | Path pattern | Purpose | Suggested spec |
|----------|----------------|---------|----------------|
| `skill_fireball` | `/assets/skills/fireball.png` | Skill bar | **64×64** PNG |

### Icons / misc

| Asset ID | Path (suggested) | Purpose |
|----------|------------------|---------|
| `logo_small` | `/assets/ui/logo.png` | Optional header badge |

### Fonts (optional)

- If you want a specific fantasy look: provide **WOFF2** files + license, or we stay on **system UI** + `font-weight` tuning for speed.

---

## 4. Step 1 checklist — **done**

| Item | Status |
|------|--------|
| Breakpoints (768) | ✅ |
| Mobile log-first | ✅ |
| Zone bar (desktop IDs yes, mobile hide IDs) | ✅ |
| Assets | ✅ placeholders |
| Font | ✅ system |
| Footer | ✅ Back + Map + Quest Log + Profile (defaults; Back explicitly confirmed) |

---

## 5. Out of scope (Step 1)

- Real party turns, targeting, or dungeon flow.
- Backend changes for multiple heroes.
- Animations beyond basic layout (Step 6).

---

## 6. Next step after you answer

**Step 2** — CSS tokens + base panels (colors, radii, shadows, spacing) aligned to this spec and your assets.
