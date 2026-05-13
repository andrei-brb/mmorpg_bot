# NPC portraits (quest dialogue overlay)

The Activity resolves NPC art by **convention** (no portrait URL on `QuestOfferPayload` today):

- **Path:** `activity/public/assets/npcs/{npc_id}.png`
- **URL:** `{BASE_URL}assets/npcs/{npc_id}.png` (see `publicBaseUrl()` in `activity/src/lib/gameApi.ts`)

`npc_id` must match the server’s quest/NPC id — the same string as `QuestOfferPayload.npc_id` and the keys under `NPC_TEMPLATES` in `services/quest/npc_quest_service.py` (after any Obsidian Silence merges).

**Fallback:** If the file is missing or fails to load, the quest-offer modal shows a speech-bubble emoji placeholder instead.

**Regenerate in-repo cards** (soft silhouette + name + discovery hint, distinct per `npc_id`):

```bash
PYTHONPATH=. python3 scripts/render_npc_quest_portraits.py
```

**Illustrated art pass (v0 / external gen):** copy-paste prompts for every NPC are in [`scripts/v0_prompts_npcs_quest_vn.md`](../../../../scripts/v0_prompts_npcs_quest_vn.md). Export PNGs with the same `{npc_id}.png` filenames into this folder.
