# Item icons — easy workflow (Activity + mmorpg-web)

The Activity loads PNGs from `activity/public/assets/items/{template_id}.png`. Your **mmorpg-web** repo likely uses other names (slug, key, etc.). These scripts help you **list UUIDs** and **batch-copy** with a mapping.

## 1) Export what the DB expects

Same `DATABASE_URL` as the bot:

```bash
cd /path/to/mmorpg_bot
export DATABASE_URL="postgresql://..."
python3 scripts/export_item_icon_manifest.py
```

Creates **`item_template_manifest.csv`** in the current directory with:

- `template_id` — use this in the PNG filename  
- `filename` — exact target name (e.g. `a1b2...-....png`)  
- `name` — in-game name (for matching to mmorpg-web)

Open this CSV in Excel/Sheets next to your mmorpg-web file list.

## 2) Build a mapping CSV

Create **`mapping.csv`** with a header:

```csv
source,template_id
iron_sword.png,a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

- **source** — file name inside your mmorpg-web icons folder (`.png` optional).  
- **template_id** — UUID from the manifest (column `template_id`).

See `scripts/mapping.example.csv`.

## 3) Apply (copy into the Activity)

```bash
python3 scripts/apply_item_icon_mapping.py \
  --source /path/to/mmorpg-web/public/items \
  --mapping mapping.csv \
  --dest activity/public/assets/items
```

Then:

```bash
cd activity && npm run build
```

Deploy `activity/dist` (or your usual pipeline).

## Tips

- **All items:** start from the manifest, fill `template_id` for each row, and add `source` as you match files (can be gradual).  
- **No Python DB access:** run the SQL in `export_item_template_manifest.sql` in psql/pgAdmin and save as CSV manually.  
- **Wrong size:** PNGs are shown ~26–32px; large images are scaled down automatically.
