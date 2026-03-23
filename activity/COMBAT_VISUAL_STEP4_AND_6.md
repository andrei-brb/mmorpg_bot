# Steps 4 & 6 — Mock polish + interaction polish (done)

## Step 4 (richer static presentation)

- **Zone bar:** subtitle `Turn-based · same rules as /fight` under the zone title.
- **Stats row:** Turn, **Total damage** (sum of `**N** … dmg` / `N dmg` patterns in the log — approximate), **Encounter** (enemy name, truncated).
- **Turn banner:** “Your turn — choose an ability below.” (visual cue; combat is always player-choice driven in this flow).
- **Party placeholders:** Slot 2 / Slot 3 with “Locked · Dungeons” / “Unlocks with party mode”; lead row uses “Lead · Adventurer” / “Lead adventurer”.
- **Footer:** `title="Coming soon"` on nav labels.

## Step 6 (polish)

- **Zone bar:** subtle border/shadow transition.
- **Party strip cards:** hover lift + border glow (non-dim cards only).
- **Skill buttons:** `:focus-visible` ring (flee uses danger-tinted ring).
- **Footer nav:** hover background, active scale.
- **Turn banner:** soft pulse animation.
- **`prefers-reduced-motion: reduce`:** disables pulse, float-up damage, hover transform, bar transitions.

**Files:** `activity/src/main.ts`, `activity/src/style.css`

## Party UI visibility (dungeon-only)

The party strip and “Your Party” sidebar render only when the API sends **`in_dungeon: true`** (character has `in_dungeon` set in the DB during a dungeon run). Otherwise the mid band is **solo** (full-width log column). Implemented in `services/combat/activity_combat.py` (`serialize_activity_state`) and `renderCombatState` in `main.ts`.
