# Mob & boss image prompts — copy / paste (by zone)

Source of truth: `config/settings.py` → `ZONES`, `ENEMIES`.

**Where to save files (Vite `public/`):**

| Kind | Path on disk | URL |
|------|----------------|-----|
| Mob | `activity/public/mobs/<key>.png` | `/mobs/<key>.png` |
| Boss | `activity/public/bosses/<key>.png` | `/bosses/<key>.png` |

Matches `activity/src/data/zones.ts` (`icon: \`/mobs/${key}.png\`` / `bosses`).

Optional **pixel-art** prefix for every prompt:

`Pixel art RPG creature sprite or portrait, 128x128 or 256x256 pixels, crisp pixels, limited palette, no soft blur, `

**Mob style** (merge or use as preset): High fantasy MMORPG enemy portrait or full-body sprite, readable at small UI size, clear silhouette, no text, no letters, no watermark, no real-world logos.

**Boss style** (merge or use as preset): High fantasy MMORPG **boss** illustration — larger scale, dramatic lighting, intimidating presence, arena-worthy silhouette, no text, no letters, no watermark.

---

## Elwynn Forest · `elwynn_forest` · levels 1–10 · 🌲

**Setting:** Peaceful woodland near the human capital; gentle starter zone. **Faction:** alliance.

### Mobs → `activity/public/mobs/<key>.png`

**Forest Wolf** · `forest_wolf` · `/mobs/forest_wolf.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: temperate forest paths, dappled sunlight, beginner woodland. Creature: Forest Wolf — lean predator, grey or brown coat, alert stance. Mood: 🐺 — common forest threat.
```

**Kobold** · `kobold` · `/mobs/kobold.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: Elwynn woodland edges, candle-caves mood. Creature: Kobold — small scaly humanoid, candle or mining pick, sneering. Mood: 👺 — nuisance scavenger.
```

**Defias Bandit** · `defias_bandit` · `/mobs/defias_bandit.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: forest roads and ambush trails. Creature: Defias Bandit — masked outlaw, leather armor, dagger or short sword, defiant pose. Mood: 🦹 — human highway threat.
```

**Young Boar** · `young_boar` · `/mobs/young_boar.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: sunny forest underbrush. Creature: Young Boar — small wild pig, bristles, charging stance. Mood: 🐷 — charging nuisance.
```

**Corrupted Guard** · `goldshire_guard` · `/mobs/goldshire_guard.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: human lands gone wrong. Creature: Corrupted Guard — tarnished tabard, shield and spear, hollow or veined eyes suggesting possession. Mood: 🛡️ — fallen protector.
```

**Giant Spider** · `spider` · `/mobs/spider.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: web-choked forest glades. Creature: Giant Spider — hairy legs, dripping fangs, web strands. Mood: 🕷️ — skittering ambusher.
```

**Murloc Scout** · `murloc_scout` · `/mobs/murloc_scout.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: forest streams and shallow pools. Creature: Murloc Scout — fish-amphibian humanoid, spear, goggle eyes, hunched. Mood: 🐸 — coastal creep into woods.
```

**Gnoll Raider** · `gnoll_raider` · `/mobs/gnoll_raider.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: forest-to-hill border packs. Creature: Gnoll Raider — hyena-folk, flail or axe, tribal scraps, snarling. Mood: 🐕 — pack scavenger.
```

### Bosses → `activity/public/bosses/<key>.png`

**Hogger** · `hogger` · `/bosses/hogger.png` · abilities: cleave, enrage

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: Elwynn wilds. Boss: Hogger — massive gnoll chieftain, oversized weapons, frothing rage, alpha posture. Suggest cleaving arcs and enraged aura (visual only). Mood: 🐗 — legendary starter terror.
```

**Defias Ringleader** · `defias_ringleader` · `/bosses/defias_ringleader.png` · abilities: backstab, poison

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: bandit camps and ruined farms. Boss: Defias Ringleader — crowned or marked leader, twin daggers, poison vials, cruel grin. Mood: 👑 — organized crime boss.
```

**Spider Queen** · `spider_queen` · `/bosses/spider_queen.png` · abilities: web, poison

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: deep nest caverns. Boss: Spider Queen — bloated elegant arachnid royalty, egg-sac motif, toxic purple sheen, web throne. Mood: 🕸️ — broodmother.
```

**Murloc Warlord** · `murloc_warlord` · `/bosses/murloc_warlord.png` · abilities: summon, frenzy

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: flooded ruins. Boss: Murloc Warlord — armored murloc tyrant, trident or polearm, crown of shells and bones, rallying smaller silhouettes (abstract). Mood: 👹 — tidecaller tyrant.
```

---

## Dun Morogh · `dun_morogh` · levels 1–10 · ❄️

**Setting:** Frozen dwarven peaks, ice and stone. **Faction:** alliance.

### Mobs

**Ice Claw Bear** · `ice_claw_bear` · `/mobs/ice_claw_bear.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: snowy dwarven mountains, pine and ice. Creature: Ice Claw Bear — shaggy white fur, frozen claws, breath mist. Mood: 🐻 — alpine bruiser.
```

**Trogg** · `trogg` · `/mobs/trogg.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: cave mouths and rocky tunnels. Creature: Trogg — hunched cave brute, rocky skin, crude club. Mood: 👾 — primitive tunnel threat.
```

**Frostmane Troll** · `frostmane_troll` · `/mobs/frostmane_troll.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: icy troll camps. Creature: Frostmane Troll — frost-tipped hair, tribal warpaint, spear or axe. Mood: 🧟 — cold-climate raider.
```

**Snow Leopard** · `snow_leopard` · `/mobs/snow_leopard.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: cliff ledges and snowfields. Creature: Snow Leopard — spotted white coat, piercing eyes, pounce pose. Mood: 🐆 — silent predator.
```

**Frozen Wraith** · `frozen_wraith` · `/mobs/frozen_wraith.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: blizzard-haunted slopes. Creature: Frozen Wraith — translucent ice spirit, tattered cloak of frost, hollow face. Mood: 👻 — cold undeath.
```

**Ice Elemental** · `ice_elemental` · `/mobs/ice_elemental.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: glacial magic nexuses. Creature: Ice Elemental — humanoid shard storm, jagged crystals, blue core glow. Mood: ❄️ — walking winter.
```

**Winter Wolf** · `winter_wolf` · `/mobs/winter_wolf.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: howling mountain passes. Creature: Winter Wolf — thick grey-white pelt, ice in fur, pack hunter eyes. Mood: 🐺 — freezing packmate.
```

**Cave Bat** · `cave_bat` · `/mobs/cave_bat.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: dwarven mine shafts. Creature: Cave Bat — wide leathery wings, bared fangs, hanging upside-down silhouette option. Mood: 🦇 — swarm pest.
```

**Frostmane Shaman** · `frostmane_shaman` · `/mobs/frostmane_shaman.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: ritual snow circles. Creature: Frostmane Shaman — troll caster, frost totems, glowing staff, spirit wisps. Mood: 🔮 — tribal frost magic.
```

### Bosses

**Frostmane Headhunter** · `frostmane_headhunter` · `/bosses/frostmane_headhunter.png`

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: troll highlands. Boss: Frostmane Headhunter — trophy racks, massive axe, trophy skulls (stylized), hunter’s swagger. Mood: 🪓 — elite stalker.
```

**Ice Lord** · `ice_lord` · `/bosses/ice_lord.png` · abilities: frost_nova, freeze

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: frozen throne plateau. Boss: Ice Lord — armored frost monarch, crown of icicles, expanding frost ring at feet (abstract nova), frozen victims as statues (silhouettes). Mood: 🧊 — zone tyrant.
```

**Trogg Overlord** · `trogg_overlord` · `/bosses/trogg_overlord.png` · abilities: stomp, enrage

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: deepest cavern halls. Boss: Trogg Overlord — obese trogg king, stone crown, cracked ground stomp shockwave hint. Mood: 👑 — cave king.
```

**Ancient Frost Giant** · `ancient_frost_giant` · `/bosses/ancient_frost_giant.png` · abilities: ice_slam, blizzard

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: mountain god-tier peak. Boss: Ancient Frost Giant — colossal blue-skinned giant, glacier shoulder pads, blizzard swirl overhead, two-handed ice pillar weapon. Mood: ⛄ — mythic colossus.
```

---

## The Barrens · `barrens` · levels 10–25 · 🌵

**Setting:** Sun-scorched wasteland, Horde heartland tone. **Faction:** horde.

### Mobs

**Razormane Warrior** · `razormane_warrior` · `/mobs/razormane_warrior.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: dry scrub and thornbrush. Creature: Razormane Warrior — quilled boar-folk gladiator, tusks, crude spear and shield. Mood: 🐗 — tribal fighter.
```

**Plainstrider** · `plainstrider` · `/mobs/plainstrider.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: open savanna flats. Creature: Plainstrider — tall flightless bird, orange-brown plumage, powerful legs, kick pose. Mood: 🦢 — plains runner.
```

**Sunscale Raptor** · `sunscale_raptor` · `/mobs/sunscale_raptor.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: sun-baked hunting grounds. Creature: Sunscale Raptor — vivid scaled predator, sickle claws, sprinting lean build. Mood: 🦎 — apex sprint-killer.
```

**Barrens Scorpion** · `barrens_scorpion` · `/mobs/barrens_scorpion.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: cracked earth and dunes. Creature: Barrens Scorpion — oversized arid scorpion, sand-colored shell, raised tail. Mood: 🦂 — venom ambusher.
```

**Zhevra** · `zhevra` · `/mobs/zhevra.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: dusty plains. Creature: Zhevra — zebra-like fantasy equine, bold stripes, dust cloud at hooves. Mood: 🦓 — swift herd beast.
```

**Thunder Lizard** · `thunder_lizard` · `/mobs/thunder_lizard.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: lightning-scarred flats. Creature: Thunder Lizard — heavy reptile, dorsal spines crackling with static, stomping charge. Mood: 🦖 — living thunder.
```

**Quillboar** · `quillboar` · `/mobs/quillboar.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: thorny barrens camps. Creature: Quillboar — bristle-backed humanoid boar, tribal mask, spiked mace. Mood: 🐷 — quill tribe brute.
```

**Wind Sweeper** · `wind_sweeper` · `/mobs/wind_sweeper.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: dust devils and heat shimmer. Creature: Wind Sweeper — elemental or vulture-spirit hybrid, spiral wind, sand in motion. Mood: 🌪️ — harassing gale.
```

**Barrens Vulture** · `barrens_vulture` · `/mobs/barrens_vulture.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: carrion skies. Creature: Barrens Vulture — bald red-eyed scavenger, wide wings, bone piles below. Mood: 🦅 — aerial scavenger.
```

### Bosses

**Kolkar Centaur Lord** · `kolkar_centaur_lord` · `/bosses/kolkar_centaur_lord.png`

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: centaur khan camp. Boss: Kolkar Centaur Lord — four-legged warrior chieftain, ornate lamellar, dual scimitars, tribal banners. Mood: 🏇 — khan of the plains.
```

**Razormane Chieftain** · `razormane_chieftain` · `/bosses/razormane_chieftain.png` · abilities: war_cry, charge

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: razor thorn stronghold. Boss: Razormane Chieftain — massive quilled warlord, roaring maw, dust plume charge lines. Mood: 👑 — tribe warlord.
```

**Thunderhawk Alpha** · `thunderhawk_alpha` · `/bosses/thunderhawk_alpha.png` · abilities: lightning_strike, dive

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: storm-front mesa. Boss: Thunderhawk Alpha — giant raptor, lightning-wreathed wings, diving strike pose. Mood: ⚡ — storm apex predator.
```

**Barrens Overlord** · `barrens_overlord` · `/bosses/barrens_overlord.png` · abilities: earthquake, summon

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: cracked earth throne. Boss: Barrens Overlord — demon or ogre tyrant, fissures at feet, minor silhouettes rising (summons abstract). Mood: 👹 — wasteland despot.
```

---

## Stranglethorn Vale · `stranglethorn` · levels 25–45 · 🌴

**Setting:** Deadly humid jungle, pirates and predators. **Faction:** neutral.

### Mobs

**Bloodsail Pirate** · `bloodsail_pirate` · `/mobs/bloodsail_pirate.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: jungle coves and rope bridges. Creature: Bloodsail Pirate — tricorn, red bandana, cutlass, pistol at hip (no readable insignia). Mood: 🏴‍☠️ — buccaneer raider.
```

**Jungle Stalker** · `jungle_stalker` · `/mobs/jungle_stalker.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: vine-choked shadows. Creature: Jungle Stalker — sleek jungle cat, camouflage spots, stalking crouch. Mood: 🐆 — unseen hunter.
```

**Venture Co. Enforcer** · `venture_co_enforcer` · `/mobs/venture_co_enforcer.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: goblin corporate outposts. Creature: Venture Co. Enforcer — heavy suit, brass goggles, riot shield, industrial menace (no logos). Mood: 🤵 — corporate muscle.
```

**Panther** · `panther` · `/mobs/panther.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: moonlit jungle floor. Creature: Panther — black coat, green eyes, lethal leap. Mood: 🐆 — jungle shadow.
```

**Tiger** · `tiger` · `/mobs/tiger.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: riverside tall grass. Creature: Tiger — orange-black stripes, powerful shoulders, roar. Mood: 🐅 — apex jungle cat.
```

**Basilisk** · `basilisk` · `/mobs/basilisk.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: rocky jungle ruins. Creature: Basilisk — low lizard with petrifying gaze hint (stone cracks on ground, not a beam with text). Mood: 🦎 — petrifying stare.
```

**Jungle Troll** · `jungle_troll` · `/mobs/jungle_troll.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: troll village ziggurats. Creature: Jungle Troll — mossy skin, ritual paint, throwing axes. Mood: 🧟 — voodoo warrior.
```

**Giant Crocodile** · `crocodile` · `/mobs/crocodile.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: mangrove rivers. Creature: Giant Crocodile — armored scales, death roll, water splash. Mood: 🐊 — river nightmare.
```

**Stranglethorn Ape** · `stranglethorn_ape` · `/mobs/stranglethorn_ape.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: canopy and ruins. Creature: Stranglethorn Ape — massive gorilla, vines, bared fangs, chest pound. Mood: 🦍 — jungle bruiser.
```

**Bloodsail Corsair** · `bloodsail_corsair` · `/mobs/bloodsail_corsair.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: beach landings. Creature: Bloodsail Corsair — elite pirate duelist, saber flourish, sea spray. Mood: ⚔️ — swashbuckling elite.
```

### Bosses

**Kurzen the Mad** · `kurzen_the_mad` · `/bosses/kurzen_the_mad.png` · abilities: madness_wave, blood_frenzy

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: mad colonel compound. Boss: Kurzen the Mad — unhinged military jacket, wild eyes, psychic ripple distortion, blood-mist aura (stylized). Mood: 🤯 — fractured mind warlord.
```

**Bhag'thera** · `bhag_thera` · `/bosses/bhag_thera.png`

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: legendary hunt turf. Boss: Bhag'thera — mythic black panther colossus, scars, jungle god presence, moon backlight. Mood: 🐆 — apex legendary beast.
```

**Bloodsail Admiral** · `bloodsail_admiral` · `/bosses/bloodsail_admiral.png` · abilities: cannon_blast, boarding

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: flagship deck or jungle dock. Boss: Bloodsail Admiral — naval coat, hat, saber, cannon smoke and grappling hooks (abstract). Mood: ⚓ — pirate admiral.
```

**Jungle Lord** · `jungle_lord` · `/bosses/jungle_lord.png` · abilities: beast_call, frenzy

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: ancient ziggurat summit. Boss: Jungle Lord — gold and feather regalia, beast spirits swirling, crown of claws, commanding raised arm. Mood: 👑 — primal jungle king.
```

---

## Blackrock Depths · `blackrock_depths` · levels 50–60 · 🌋

**Setting:** Volcanic dungeon-city, endgame. **Faction:** neutral.

### Mobs

**Dark Iron Dwarf** · `dark_iron_dwarf` · `/mobs/dark_iron_dwarf.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: forge tunnels and magma channels. Creature: Dark Iron Dwarf — soot-stained beard, riveted armor, pickaxe or rifle. Mood: ⛏️ — industrial dwarf raider.
```

**Molten Giant** · `molten_giant` · `/mobs/molten_giant.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: lava rivers. Creature: Molten Giant — cracked stone skin with glowing magma veins, dragging molten fist. Mood: 🔥 — walking furnace.
```

**Firelord Servant** · `firelord_servant` · `/mobs/firelord_servant.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: demonic summoning pits. Creature: Firelord Servant — horned infernal, flaming whip, wing stubs. Mood: 😈 — pit fiend lackey.
```

**Lava Elemental** · `lava_elemental` · `/mobs/lava_elemental.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: molten lakes. Creature: Lava Elemental — bubbling humanoid magma, crusted black shell, orange core. Mood: 🌋 — molten animus.
```

**Dark Iron Guard** · `dark_iron_guard` · `/mobs/dark_iron_guard.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: fortress gates. Creature: Dark Iron Guard — full plate, tower shield, halberd, glowing forge eyeslit. Mood: 🛡️ — elite sentry.
```

**Fire Imp** · `fire_imp` · `/mobs/fire_imp.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: brimstone cracks. Creature: Fire Imp — small devil, pitchfork, mischievous flame mouth. Mood: 🔥 — swarm pest.
```

**Shadowforge Sentinel** · `shadowforge_sentinel` · `/mobs/shadowforge_sentinel.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: mechanized halls. Creature: Shadowforge Sentinel — golem or armored construct, dual blades, furnace core chest. Mood: ⚔️ — automated killer.
```

**Magma Lord** · `magma_lord` · `/mobs/magma_lord.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: caldera bridges. Creature: Magma Lord — elite lava humanoid, crown of cooled obsidian, lava arms. Mood: 🌋 — elemental noble.
```

**Dark Iron Sorcerer** · `dark_iron_sorcerer` · `/mobs/dark_iron_sorcerer.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: shadowforge libraries. Creature: Dark Iron Sorcerer — dark iron robes, shadowflame orbs, rune staff (abstract sigils only). Mood: 🔮 — dwarven warlock.
```

**Flame Wraith** · `flame_wraith` · `/mobs/flame_wraith.png`

```
High fantasy MMORPG enemy portrait or sprite, readable at small UI size, no text, no letters, no watermark. Zone: smoke-filled crypts. Creature: Flame Wraith — ash silhouette, burning eyes, ember trail. Mood: 👻 — burning specter.
```

### Bosses

**Emperor Thaurissan** · `emperor_dagran_thaurissan` · `/bosses/emperor_dagran_thaurissan.png` · abilities: imperial_decree, shadowflame, enrage

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: imperial throne of flame. Boss: Emperor Thaurissan — dark iron emperor on magma throne, shadowflame breath motif, crown and decree scepter (no readable text). Mood: 👑 — raid-ending tyrant.
```

**Lord Incendius** · `lord_incendius` · `/bosses/lord_incendius.png` · abilities: flame_nova, inferno

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: forge god altar. Boss: Lord Incendius — towering fire elemental lord, nova ring of fire, inferno pillar. Mood: 🌋 — elemental noble boss.
```

**Magmadar** · `magmadar` · `/bosses/magmadar.png` · abilities: lava_breath, molten_armor

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: core hound lair. Boss: Magmadar — molten core hound, spiked spine dripping lava, breath cone of fire, armored plates. Mood: 🔥 — legendary beast boss.
```

**Golem Lord** · `golem_lord` · `/bosses/golem_lord.png` · abilities: crush, stomp

```
High fantasy MMORPG boss illustration, imposing silhouette, no text, no letters, no watermark. Zone: assembly vault. Boss: Golem Lord — massive stone-and-magma golem, earthquake stomp cracks, crushing fist overhead. Mood: 🤖 — construct overlord.
```

---

## Counts

| Zone key | Levels | Mobs | Bosses |
|----------|--------|------|--------|
| `elwynn_forest` | 1–10 | 8 | 4 |
| `dun_morogh` | 1–10 | 9 | 4 |
| `barrens` | 10–25 | 9 | 4 |
| `stranglethorn` | 25–45 | 10 | 4 |
| `blackrock_depths` | 50–60 | 10 | 4 |
| **Total** | | **46** | **20** |
