# Obsidian Silence — implementation checklist

Use this with the in-repo **Todo** list and `/admin lore` commands.

## Done (this PR)

- [x] **`character_deed_flags` table** — per-character deed flags (`database/db.py` migration).
- [x] **`LoreGateService`** — `get_flags`, `grant_flag`, `revoke_flag`, inventory check, `evaluate_characters`.
- [x] **`config/lore_gates.py`** — `LORE_BOSS_GATES` dict (empty by default = no immunities).
- [x] **Story boss immunity** — only when `CombatSession.apply_lore_gates` is True and boss has a gate; damage blocked in `combat_engine.use_ability`.
- [x] **Discord `/fight` + explore** — `apply_lore_gates=True`, evaluates gates at combat start.
- [x] **Activity combat tab** — `apply_lore_gates=False` (gear/leveling unchanged by lore gates).
- [x] **Dungeon combat** — `apply_lore_gates=False`, `enemy_key` / `zone_key` set on session.
- [x] **`Settings.COMBAT_AWARD_XP_ON_VICTORY`** — default `True`; set `False` for “no XP from mob kills” (quest XP still applies in `combat_cog` quest completion block).
- [x] **Admin** — `/admin lore flags`, `grant_flag`, `revoke_flag`, `gates`.

## You should still add (content + wiring)

- [ ] **Fill `LORE_BOSS_GATES`** in `config/lore_gates.py` with real `enemy_key` values and `required_flags` / `required_items`.
- [ ] **Create item templates** for key items (e.g. Shatter-Tone Tuning Fork) if gating by item.
- [ ] **Grant flags on quest completion** — extend `NPCQuestService` (or quest rewards) to call `LoreGateService.grant_flag` when a deed completes.
- [ ] **World boss triggers** (5–10 players, Glass Titan, Ghost Admiral) — server milestone tables + jobs (not built yet).
- [ ] **Activity UI** — optional: show “story locked” when same boss exists in both places (only if you surface story bosses in Activity).

## Quick reference

| Mechanism | Purpose |
|-----------|---------|
| `LORE_BOSS_GATES[enemy_key]` | Requires flags + optional item templates before damage applies (Discord only). |
| `character_deed_flags` | Stores `flag_key` per character. |
| `COMBAT_AWARD_XP_ON_VICTORY` | Gate XP from combat victory; quests can still award XP via `award_xp` in quest completion. |

## Admin commands

```
/admin lore flags @player
/admin lore grant_flag @player marcus_recommendation
/admin lore revoke_flag @player marcus_recommendation
/admin lore gates
```
