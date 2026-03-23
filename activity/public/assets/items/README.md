# Item icons (optional)

**Step-by-step helpers (export manifest, rename batch):** see **`scripts/README_ITEM_ICONS.md`** in the repo root.

---

The Activity **Hero** tab loads item art from this folder when present.

## File naming

For each row in **`item_templates`** (same DB as the bot), add one PNG:

```text
public/assets/items/{template_id}.png
```

`template_id` is the **template UUID** (same as `inventory.template_id` / `item_templates.id`), including hyphens, e.g.  
`a1b2c3d4-e5f6-7890-abcd-ef1234567890.png`

The inventory API already sends `template_id` on each item; the UI requests:

`/assets/items/<template_id>.png`

If the file is missing, the UI falls back to the emoji in the database (`icon` column).

## Copying from mmorpg-web

1. In **mmorpg-web**, note how files map to items (e.g. by slug or template id).
2. Export or copy PNGs into this folder.
3. **Rename** each file to `{template_id}.png` where `template_id` matches PostgreSQL `item_templates.id`.

Quick list of IDs (run against your DB):

```sql
SELECT id, name FROM item_templates ORDER BY name;
```

4. Rebuild and redeploy the Activity (`npm run build` in `activity/`).

## Size / format

- **PNG** (or convert WebP → PNG for consistency).
- Icons are displayed at **~26–32px**; larger sources are scaled down with `object-fit: contain`.
