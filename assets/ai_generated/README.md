# AI-generated portrait pack (enemies + classes)

This folder holds **game art prompts** and optional **PNG exports** aligned with `config/settings.py`:

- **80** `ENEMIES` rows (24 bosses, 56 regular mobs)
- **6** playable `CLASSES` (warrior, paladin, mage, rogue, priest, hunter)

## Files

- `image_prompts.json` — machine-readable `{ key, kind, display_name, filename, prompt }` for each asset (regenerate with `python3 scripts/export_ai_image_prompts.py` from repo root).

PNG files use stable names:

- `enemies/enemy_boss_<key>.png` / `enemies/enemy_mob_<key>.png`
- `classes/class_<key>.png`

## Wiring into the game

The Discord bot / Activity UI do **not** load these paths automatically yet; they are reference assets. Hook them up where you render enemies (combat, bestiary) and class selection once you settle on dimensions and cropping.

## Regenerating / completing the set

Cursor image generation saves under the IDE project assets directory first; copy completed PNGs into `enemies/` or `classes/` here. For a full batch outside the IDE, feed `image_prompts.json` prompts into your preferred image API or pipeline.
