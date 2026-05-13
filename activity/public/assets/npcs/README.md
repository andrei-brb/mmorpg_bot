# NPC portraits (quest dialogue overlay)

The Activity resolves NPC art by **convention** (no portrait URL on `QuestOfferPayload` today):

- **Path:** `activity/public/assets/npcs/{npc_id}.png`
- **URL:** `{BASE_URL}assets/npcs/{npc_id}.png` (see `publicBaseUrl()` in `activity/src/lib/gameApi.ts`)

`npc_id` must match the server’s quest/NPC id — the same string as `QuestOfferPayload.npc_id` and the keys under `NPC_TEMPLATES` in `services/quest/npc_quest_service.py` (after any Obsidian Silence merges).

**Fallback:** If the file is missing or fails to load, the quest-offer modal shows a speech-bubble emoji placeholder instead.

Shipped PNGs here are **simple gradient placeholders** (one per known template id). Swap them for final portrait art without changing code, keeping the same filenames.
