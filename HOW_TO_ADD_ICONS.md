# How to Add PNG Icons to the Game

## Quick Steps

1. **Get your PNG files from Gemini** (you should have 18 PNG files)
2. **Save them to the correct location**
3. **Name them correctly**
4. **Done!**

## Detailed Instructions

### Step 1: Locate Your PNG Files

After Gemini generates the icons, you should have 18 PNG files. They might be:
- Downloaded to your Downloads folder
- In a folder Gemini created
- Still in Gemini's interface (you'll need to download them)

### Step 2: Prepare the Files (Optional - Only if needed)

**You DON'T need to crop them** if Gemini already created them as 64x64 or 128x128 pixels.

**Only resize/crop if:**
- Files are larger than 256x256 pixels (Discord has size limits)
- Files are not square (should be square for best display)
- You want to optimize file size

**Recommended size:** 64x64 or 128x128 pixels (square)

### Step 3: Save Files to Project

1. Open Finder (Mac) or File Explorer (Windows)
2. Navigate to: `/Users/tara/Downloads/mmorpg_bot/assets/items/`
3. Copy your PNG files into this folder

### Step 4: Rename Files Correctly

Rename each file to match the item ID exactly (case-sensitive, no spaces):

**Consumables (8 files):**
- `health_potion.png`
- `frost_resist_potion.png`
- `stamina_draught.png`
- `elixir_of_fortitude.png`
- `flask_of_the_titans.png`
- `protection_blessing_scroll.png`
- `protection_safety_charm.png`
- `protection_enhancement_fragment.png`

**Special Items (10 files):**
- `iron_sword.png`
- `leather_cap.png`
- `dwarven_axe.png`
- `chain_coif.png`
- `bone_club.png`
- `raptor_hide_vest.png`
- `corsair_blade.png`
- `jungle_leather_chest.png`
- `sulfuron_blade.png`
- `shadowforge_plate.png`

## Quick Rename Script (Optional)

If you have many files, you can use this Python script to rename them:

```python
import os
from pathlib import Path

# Map of display names to file IDs
ITEM_NAMES = {
    "Health Potion": "health_potion",
    "Frost Resist Potion": "frost_resist_potion",
    "Stamina Draught": "stamina_draught",
    "Elixir of Fortitude": "elixir_of_fortitude",
    "Flask of the Titans": "flask_of_the_titans",
    "Blessing Scroll": "protection_blessing_scroll",
    "Safety Charm": "protection_safety_charm",
    "Enhancement Fragment": "protection_enhancement_fragment",
    "Iron Sword": "iron_sword",
    "Leather Cap": "leather_cap",
    "Dwarven Axe": "dwarven_axe",
    "Chain Coif": "chain_coif",
    "Bone Club": "bone_club",
    "Raptor Hide Vest": "raptor_hide_vest",
    "Corsair Blade": "corsair_blade",
    "Jungle Leather Chest": "jungle_leather_chest",
    "Sulfuron Blade": "sulfuron_blade",
    "Shadowforge Plate": "shadowforge_plate",
}

icons_dir = Path("assets/items")
for file in icons_dir.glob("*.png"):
    # Try to match by name
    for display_name, item_id in ITEM_NAMES.items():
        if display_name.lower().replace(" ", "_") in file.name.lower():
            new_name = f"{item_id}.png"
            file.rename(icons_dir / new_name)
            print(f"Renamed: {file.name} -> {new_name}")
            break
```

## Verification

After adding files, verify they're in the right place:

```bash
ls assets/items/
```

You should see all 18 PNG files with the correct names.

## Testing

1. Start your bot
2. Use `/inventory` command
3. Click on an item that has a PNG icon
4. The icon should appear as a thumbnail in the embed!

## Troubleshooting

**Icons don't appear?**
- Check file names are EXACTLY correct (case-sensitive)
- Verify files are in `assets/items/` folder
- Make sure files are PNG format (not JPG, etc.)
- Check file permissions (should be readable)

**Files too large?**
- Discord has a 25MB limit per file
- Recommended: Keep under 100KB each
- Use image editor to resize if needed

**Wrong size/format?**
- Use Preview (Mac) or Paint (Windows) to resize
- Or use online tools like: https://www.iloveimg.com/resize-image
- Set to 64x64 or 128x128 pixels
