# Icon Integration Guide

This guide explains how to integrate PNG icons into the MMORPG bot.

## 📁 File Structure

Place your PNG icon files in:
```
assets/items/
```

Name them using the item template ID (e.g., `health_potion.png`, `iron_sword.png`)

## ✅ What's Been Done

1. ✅ Created `assets/items/` directory
2. ✅ Created `utils/icon_helper.py` utility functions
3. ✅ Updated `cogs/inventory/inventory_cog.py` to use PNG icons in embeds

## 📝 How It Works

1. **Icon Helper** (`utils/icon_helper.py`):
   - `get_icon_path(item_id)` - Returns file path if PNG exists
   - `get_icon_file(item_id)` - Returns Discord File object if PNG exists
   - `has_png_icon(item_id)` - Checks if PNG exists

2. **Inventory Display**:
   - When displaying an item, the code checks for a PNG file
   - If PNG exists: Uses it as embed thumbnail
   - If PNG doesn't exist: Falls back to emoji (current behavior)

## 🎯 Next Steps

1. **Add Your PNG Files**:
   - Place all 18 PNG icons in `assets/items/` directory
   - Name them exactly as the item IDs:
     - `health_potion.png`
     - `frost_resist_potion.png`
     - `stamina_draught.png`
     - `elixir_of_fortitude.png`
     - `flask_of_the_titans.png`
     - `protection_blessing_scroll.png`
     - `protection_safety_charm.png`
     - `protection_enhancement_fragment.png`
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

2. **Test the Integration**:
   - Run the bot
   - Use `/inventory` command
   - View an item that has a PNG icon
   - The icon should appear as a thumbnail in the embed

## 🔧 Technical Details

- Icons are attached as Discord File objects to embeds
- The embed thumbnail URL uses `attachment://filename.png` format
- Files are automatically attached when sending/editing messages
- If no PNG exists, the system falls back to emoji icons (backward compatible)

## 📌 Notes

- **Button Icons**: Discord buttons still use emojis (they can't use file attachments)
- **Database**: The `icon` column in `item_templates` still stores emojis (for buttons/fallback)
- **File Size**: Keep PNG files reasonably sized (64x64 or 128x128 recommended)
- **Format**: Must be PNG format

## 🐛 Troubleshooting

If icons don't appear:
1. Check file names match item IDs exactly (case-sensitive)
2. Verify files are in `assets/items/` directory
3. Check file permissions
4. Look for errors in bot logs
5. Ensure files are PNG format
