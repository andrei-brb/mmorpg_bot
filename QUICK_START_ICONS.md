# 🚀 Quick Start: Process Your Icons

## Step 1: Save Your Grid Images

Save the grid images you showed me as:
- `items_grid.png` (the 10x10 item grid)
- `bestiary_grid.png` (the mobs/bosses grid)

Place them in the `mmorpg_bot` folder.

## Step 2: Install Dependencies

```bash
cd /Users/tara/Downloads/mmorpg_bot
pip install -r requirements_icon_processor.txt
```

**Note:** `rembg` might take a few minutes to install and download AI models on first run.

## Step 3: Process the Icons

### Option A: Extract from Grids AND Process (Recommended)

```bash
# Process items grid (10x10)
python3 extract_and_process_icons.py both \
    --grid-image items_grid.png \
    --rows 10 \
    --cols 10 \
    --prefix item \
    --output items_processed \
    --size 256

# Process bestiary grid (mobs/bosses)
python3 extract_and_process_icons.py both \
    --grid-image bestiary_grid.png \
    --rows 8 \
    --cols 8 \
    --prefix mob \
    --output mobs_processed \
    --size 256
```

### Option B: Use the Quick Script

```bash
chmod +x process_all_icons.sh
./process_all_icons.sh
```

## Step 4: Check Results

After processing, you'll have:
- `items_processed/processed/` - All item icons (256x256, backgrounds removed)
- `mobs_processed/processed/` - All mob/boss icons (256x256, backgrounds removed)

## What the Script Does

1. ✅ **Extracts** each icon from the grid automatically
2. ✅ **Removes backgrounds** using AI (rembg)
3. ✅ **Auto-crops** to content boundaries
4. ✅ **Resizes** to 256x256 square (maintains aspect ratio)
5. ✅ **Saves** as PNG with transparency

## Troubleshooting

**If rembg fails to install:**
```bash
# Try installing system dependencies first
brew install python3  # macOS
# or
sudo apt-get install python3-dev  # Linux

# Then retry
pip install rembg
```

**If you want to skip background removal (faster):**
```bash
python3 extract_and_process_icons.py both \
    --grid-image items_grid.png \
    --rows 10 \
    --cols 10 \
    --no-bg-remove \
    --output items_processed
```

## Output Structure

```
items_processed/
├── extracted/          # Raw extracted icons from grid
└── processed/          # Final processed icons (ready to use)
    ├── item_1_0.png
    ├── item_1_1.png
    └── ...

mobs_processed/
├── extracted/          # Raw extracted icons from grid
└── processed/          # Final processed icons (ready to use)
    ├── mob_1_0.png
    ├── mob_1_1.png
    └── ...
```

## Next Steps

After processing, you can:
1. Rename icons to match your item/mob names
2. Organize into `items/`, `mobs/`, `bosses/` folders
3. Upload to your game's asset folder
