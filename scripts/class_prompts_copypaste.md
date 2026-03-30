# Class & specialization prompts — copy / paste (image generators)

Use these prompts to generate **class portraits**, **selection icons**, or **emblem-style class art** for *World of Discord* / your MMORPG UI.

Optional: prepend this to **every** prompt if you want pixel art:

`Pixel art RPG character portrait or class emblem, 128x128 or 256x256 pixels, crisp pixels, limited palette, no soft blur, `

**Suggested exports**

- Base class: `class_<key>.png` (e.g. `class_warrior.png`)
- Specialization: `spec_<key>.png` (e.g. `spec_arms.png`)

**Global style** (merge into each prompt or paste once if your tool supports a style preset):

High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark, no real-world logos, cohesive lighting, dramatic but not gory, single clear focal subject.

---

## Base classes (6)

Keys and filenames match `config/settings.py` → `CLASSES`.

### Warrior · key: `warrior` · `class_warrior.png`

**Role:** tank · **Resource:** rage · **Primary stat:** strength · **Emoji mood:** ⚔️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Subject: Warrior — unstoppable melee fighter in heavy plate armor, shield and two-handed weapon or sword, battle-worn and imposing, front-line tank silhouette. Mood: forged in countless battles, unbreakable front line. Palette: steel, deep red accents, muted gold trim. Class vibe: warrior.
```

### Paladin · key: `paladin` · `class_paladin.png`

**Role:** tank · **Resource:** mana · **Primary stat:** strength · **Emoji mood:** 🛡️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Subject: Paladin — holy warrior in polished plate, tabard or sunburst motif, blend of martial might and gentle divine light (glow, not readable symbols). Mood: beacon of hope, smites evil and heals allies. Palette: gold, white, soft azure. Class vibe: paladin.
```

### Mage · key: `mage` · `class_mage.png`

**Role:** dps · **Resource:** mana · **Primary stat:** intellect · **Emoji mood:** 🔮

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Subject: Mage — robed arcane scholar, hands wreathed in mixed fire frost and arcane energy, floating rune disks or spell focus (abstract, not letters). Mood: devastating elemental control. Palette: deep violet robe, cyan and ember highlights. Class vibe: mage.
```

### Rogue · key: `rogue` · `class_rogue.png`

**Role:** dps · **Resource:** energy · **Primary stat:** agility · **Emoji mood:** 🗡️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Subject: Rogue — lean assassin in leather hood and twin blades or dagger, subtle shadow wisps, poised to strike from darkness. Mood: deception and lethal precision. Palette: charcoal, blood red accents, silver steel. Class vibe: rogue.
```

### Priest · key: `priest` · `class_priest.png`

**Role:** healer · **Resource:** mana · **Primary stat:** intellect · **Emoji mood:** ✨

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Subject: Priest — devout caster in flowing vestments, one hand raised with soft holy radiance, subtle shadow curl on the opposite side suggesting dual path (light vs shadow) without horror. Mood: devotion and inner conflict. Palette: white gold and soft purple shadow. Class vibe: priest.
```

### Hunter · key: `hunter` · `class_hunter.png`

**Role:** dps · **Resource:** mana · **Primary stat:** agility · **Emoji mood:** 🏹

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Subject: Hunter — wilderness ranger with bow or crossbow, quiver, leather and fur trim, optional loyal beast companion at side (wolf or bird of prey silhouette). Mood: precision and bond with the wild. Palette: forest green, tan leather, sky blue accents. Class vibe: hunter.
```

---

## Specializations (12)

Unlocked at level 10 (`SPEC_UNLOCK_LEVEL`). Keys match `config/settings.py` → `SPECIALIZATIONS`.

### Warrior — Arms · key: `arms` · `spec_arms.png`

**Parent:** warrior · **Role:** dps · **Emoji:** ⚔️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Arms Warrior — two-handed weapon master, executioner stance, cleaving arc and blood-spatter motif (stylized, not graphic). Flavor: every swing maximizes carnage. Passive theme: deep wounds / bleeding strikes. Palette: iron, crimson, bronze.
```

### Warrior — Protection · key: `protection` · `spec_protection.png`

**Parent:** warrior · **Role:** tank · **Emoji:** 🛡️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Protection Warrior — tower shield wall, defensive bulwark, enemies breaking against steel. Flavor: the wall between allies and annihilation. Passive theme: shield block. Palette: steel blue, silver, battle-scarred metal.
```

### Paladin — Retribution · key: `retribution` · `spec_retribution.png`

**Parent:** paladin · **Role:** dps · **Emoji:** 🔥

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Retribution Paladin — two-handed hammer wreathed in righteous fire, aggressive forward stride. Flavor: justice taken by force. Passive theme: stacking vengeance. Palette: gold flame, white-hot core, dark iron.
```

### Paladin — Holy · key: `holy_paladin` · `spec_holy_paladin.png`

**Parent:** paladin · **Role:** healer · **Emoji:** 💛

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Holy Paladin healer — radiant hands, soft halo, mending light spirals toward allies. Flavor: the light that refuses to go out. Passive theme: illumination / efficient healing. Palette: warm gold, soft amber, clean white.
```

### Mage — Fire · key: `fire` · `spec_fire.png`

**Parent:** mage · **Role:** dps · **Emoji:** 🔥

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Fire Mage — pyromancer surrounded by explosive flames and ember motes, confident smirk optional. Flavor: everything burns. Passive theme: ignite / burn DoT. Palette: orange, crimson, black smoke wisps.
```

### Mage — Frost · key: `frost` · `spec_frost.png`

**Parent:** mage · **Role:** dps · **Emoji:** ❄️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Frost Mage — cryomancer with ice crystals, frost breath, frozen shards orbiting. Flavor: control the battlefield. Passive theme: shatter / frozen targets. Palette: ice blue, white, pale cyan.
```

### Rogue — Assassination · key: `assassination` · `spec_assassination.png`

**Parent:** rogue · **Role:** dps · **Emoji:** 💀

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Assassination Rogue — poison vials, green-purple vapor, twin daggers with dripping venom (stylized). Flavor: they never feel the blade. Passive theme: master poisoner. Palette: toxic green, deep purple, black leather.
```

### Rogue — Subtlety · key: `subtlety` · `spec_subtlety.png`

**Parent:** rogue · **Role:** dps · **Emoji:** 🌑

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Subtlety Rogue — shadow dancer half-faded into darkness, ambush pose, moonlit silhouette. Flavor: the assassin never seen. Passive theme: find weakness / armor ignore from stealth. Palette: midnight blue, silver edge light, void black.
```

### Priest — Holy · key: `holy_priest` · `spec_holy_priest.png`

**Parent:** priest · **Role:** healer · **Emoji:** 🕊️

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Holy Priest — pure radiance, dove or soft halo abstract shapes, waves of healing light. Flavor: faith as shield, compassion as weapon. Passive theme: inspiration / damage reduction after heal. Palette: white, soft gold, sky blue.
```

### Priest — Shadow · key: `shadow` · `spec_shadow.png`

**Parent:** priest · **Role:** dps · **Emoji:** 🌑

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Shadow Priest — void tendrils, dark halo, eyes of starry emptiness, mind-bending distortion (cosmic horror lite, not gore). Flavor: something in the dark found you. Passive theme: shadow weaving stacks. Palette: deep violet, black, sickly green accent.
```

### Hunter — Marksmanship · key: `marksmanship` · `spec_marksmanship.png`

**Parent:** hunter · **Role:** dps · **Emoji:** 🎯

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Marksmanship Hunter — sniper stance, longbow or rifle silhouette, single perfect shot line and bullseye ripple (abstract). Flavor: one shot is enough. Passive theme: trueshot / crit emphasis. Palette: forest camo, steel, crimson fletching accent.
```

### Hunter — Beast Mastery · key: `beast_mastery` · `spec_beast_mastery.png`

**Parent:** hunter · **Role:** dps · **Emoji:** 🐉

```
High fantasy MMORPG game asset, readable at small UI size, no text, no letters, no watermark. Specialization emblem or bust portrait: Beast Mastery Hunter — hunter beside a fierce beast companion (wolf, raptor, or spirit beast), shared battle fury. Flavor: one mind, one fury. Passive theme: pet strikes with you. Palette: primal brown, beast amber eyes, tribal leather accents.
```

---

## Quick checklist

| Type | Count | Key pattern |
|------|-------|-------------|
| Base classes | 6 | `warrior`, `paladin`, `mage`, `rogue`, `priest`, `hunter` |
| Specializations | 12 | `arms`, `protection`, `retribution`, `holy_paladin`, `fire`, `frost`, `assassination`, `subtlety`, `holy_priest`, `shadow`, `marksmanship`, `beast_mastery` |

Source of truth: `config/settings.py` (`CLASSES`, `SPECIALIZATIONS`).
