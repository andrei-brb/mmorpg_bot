# Profile Card Layout Spec — For v0 / Gemini

Use this spec to place every **dynamic** game value on the character card. Canvas size: **703×1024** px (or keep same aspect ratio). All positions below are for that size; scale proportionally if you change it.

---

## 1. IMAGE / AVATAR

- **What:** Player’s Discord avatar (circular).
- **Source:** URL from the game (we fetch and paste it).
- **Where:** **Top-left**, inside the circular gold ring.
- **Size:** Circle diameter ~**200–220 px** (so the ring can be ~210–230 px).
- **Position:** Center of circle at roughly **(135, 115)** so the full circle fits in the top-left corner without overlapping the name.

---

## 2. HEADER (identity block, right of avatar)

- **Character name**
  - **Value:** One string, e.g. `"Aragorn"`.
  - **Where:** Top-right of the header, **same vertical band as the avatar**, left-aligned to a column that starts after the avatar (e.g. **x ≈ 260**).
  - **Font:** **Largest on the card** — e.g. **44–52 px** height, bold, gold/cream color. This is the main title.

- **Level and class**
  - **Value:** One string, e.g. `"Level 42 Warrior"`.
  - **Where:** **Directly under the character name**, same left alignment (e.g. **y ≈ 175**).
  - **Font:** **Subtitle** — e.g. **26–30 px**, slightly muted gold/green.

- **Specialty (if any)**
  - **Value:** One string, e.g. `"★ Arms Specialist"`.
  - **Where:** **Under the level/class line** (e.g. **y ≈ 210**).
  - **Font:** **Body** — e.g. **20–22 px**, gold/cream.

---

## 3. RESOURCE BARS (below header, full width)

- **HP bar**
  - **Label:** Fixed text **"HP"** on the left.
  - **Values:** Two numbers: **current_hp** and **max_hp** (e.g. `1335 / 1335`). Format: `"{current:,} / {max:,}"`.
  - **Bar:** Horizontal bar; fill width = (current_hp / max_hp) × bar width. Color: **red** (#C83737 or similar).
  - **Where:** First bar; top of bar at **y ≈ 250**, height **~28–32 px**, from **x ≈ 95** to **x ≈ 608**. Text centered in the bar.

- **Second bar (Mana / Energy / Rage)**
  - **Label:** **"Mana"**, **"Energy"**, or **"Rage"** (one of these).
  - **Values:** **current_res** and **max_res** (e.g. `1254 / 1254`). Same format as HP.
  - **Bar:** Same size as HP bar, **directly below** (e.g. top at **y ≈ 328**). Color: **blue** for Mana, **gold/amber** for Energy, **red** for Rage.
  - If the class has no resource (max_res = 0), this bar can be hidden or shown empty.

---

## 4. CORE STATS (left panel)

- **Panel title:** Fixed **"Core Stats"** at top of left box.
- **Where:** Left box from **x ≈ 40** to **x ≈ 340**, **y ≈ 380** to **y ≈ 600** (or so). Five rows of **label + value**.
- **Font:** Labels **18–20 px**, values **22–26 px** (values right-aligned in the box).
- **Rows (in order, top to bottom):**

| Label | Game field      | Example value |
|-------|-----------------|---------------|
| STR   | strength        | 450           |
| AGI   | agility         | 600           |
| INT   | intellect       | 524           |
| SPI   | spirit          | 308           |
| STA   | stamina         | 400           |

- **Colors (for values):** STR warm yellow; AGI green; INT blue; SPI purple; STA dark red/gray (or match your theme).

---

## 5. COMBAT STATS (right panel)

- **Panel title:** Fixed **"Combat Stats"** at top of right box.
- **Where:** Right box from **x ≈ 360** to **x ≈ 663**, same vertical range as Core Stats (**y ≈ 380–600**). Five rows.
- **Font:** Same as Core Stats (labels 18–20 px, values 22–26 px, values right-aligned).
- **Rows (in order):**

| Label  | Game field    | Example value |
|--------|---------------|----------------|
| Attack | attack_power  | 1550           |
| Spell  | spell_power   | 1048           |
| Armor  | armor         | 284            |
| Crit   | crit_chance   | "36.5%"        |
| Dodge  | dodge_chance  | "71.9%"        |

- **Values:** Numbers for Attack, Spell, Armor; **one decimal + "%"** for Crit and Dodge (e.g. `"12.3%"`).

---

## 6. EQUIPMENT (list below stat panels)

- **Section title:** Fixed **"Equipment"** (e.g. **y ≈ 620**).
- **What:** **Up to three item names** (no icons). Each item has a **name** and a **rarity** (for color).
- **Where:** Three lines, left-aligned (e.g. **x ≈ 62**), starting at **y ≈ 674** and **+30 px** per line (e.g. 674, 704, 734).
- **Font:** **20–22 px**.
- **Rarity → color:**  
  common = gray, uncommon = green, rare = blue, epic = purple, legendary = orange, artifact = gold.

- **Slots we show:** **Chest**, **Main hand**, **Feet** (in that order). If a slot is empty, skip that line or show "—" or "Empty".

---

## 7. LOCATION AND GOLD (footer block)

- **Location**
  - **Value:** Zone name, e.g. `"Elwynn Forest"`. We can prepend an emoji (e.g. 🗺️) from the game.
  - **Where:** One line at **y ≈ 800** (or just above the quote), **x ≈ 22**.
  - **Font:** **18–20 px**, gold/cream.

- **Gold**
  - **Value:** One integer, e.g. `30021`. Format: `"🪙 Gold: 30,021"` (with thousands separator).
  - **Where:** **Under the location line** (e.g. **y ≈ 830**).
  - **Font:** Same as location.

---

## 8. FLAVOR QUOTE AND PASSIVE (bottom)

- **Flavor (specialization quote)**
  - **Value:** One string, e.g. `"The best assassin is the one they never knew existed."`
  - **Where:** **y ≈ 858**, **x ≈ 22**. Can wrap to two lines if needed.
  - **Font:** **16–18 px**, italic style, muted white/gray. Show in quotes.

- **Passive (gameplay line)**
  - **Value:** One string, e.g. `"Attacks from stealth ignore 20% of the target's armor."` (we add spec emoji + this text).
  - **Where:** **Under the flavor line** (e.g. **y ≈ 886**).
  - **Font:** **15–17 px**, readable white/gray.

---

## Summary: All dynamic fields (game provides these)

| #  | Field(s)           | Example / format                    |
|----|---------------------|-------------------------------------|
| 1  | avatar (image URL)  | —                                   |
| 2  | name                | "Aragorn"                           |
| 3  | level, class        | "Level 42 Warrior"                  |
| 4  | specialization      | "★ Arms Specialist" or empty        |
| 5  | current_hp, max_hp  | "1,335 / 1,335"                     |
| 6  | res_type            | "Mana" | "Energy" | "Rage"        |
| 7  | current_res, max_res| "1,254 / 1,254"                     |
| 8  | strength, agility, intellect, spirit, stamina | numbers |
| 9  | attack_power, spell_power, armor | numbers |
| 10 | crit_chance, dodge_chance       | "36.5%", "71.9%"   |
| 11 | equipped (chest, main_hand, feet)| name + rarity each |
| 12 | current_zone        | "Elwynn Forest" (+ optional emoji)  |
| 13 | gold                | 30021 → "30,021"                    |
| 14 | spec flavor         | quote string                        |
| 15 | spec passive_desc  | passive description string         |

---

## Layout order (top → bottom)

1. **Avatar** (top-left circle) + **Name / Level+Class / Specialty** (right of avatar).
2. **HP bar** then **Mana/Energy/Rage bar**.
3. **Core Stats** (left) and **Combat Stats** (right) side by side.
4. **Equipment** (title + 3 item lines).
5. **Zone** then **Gold**.
6. **Flavor quote** then **Passive** line.

---

## Font size guidance (so text is not too small)

For a **703×1024** card:

- **Character name:** 44–52 px (largest).
- **Level + class:** 26–30 px.
- **Specialty, bar labels, section titles (Core Stats, Combat Stats, Equipment):** 20–22 px.
- **Stat labels (STR, AGI, … Attack, Spell, …):** 18–20 px.
- **Stat values, item names, zone, gold:** 22–24 px (values can be slightly larger than labels).
- **Bar numbers (HP/MP):** 20–22 px.
- **Flavor + passive:** 15–18 px.

If you export a template image for the Python bot, use **703×1024** and leave these regions as **placeholders** (or empty) so the bot can draw the dynamic text and avatar on top in the right places.
