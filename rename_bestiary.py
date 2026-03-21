#!/usr/bin/env python3
"""
Rename bestiary icons to match game mob and boss names.
Grid structure: 8 rows × 10 columns
- Rows 1-6: Regular enemies (46 mobs)
- Rows 7-8: Bosses (16 bosses)
"""

import os
import re
from pathlib import Path
import shutil

# All 46 regular enemies (from alphabetical list in MOBS_AND_BOSSES_LIST.md)
ALL_MOBS = [
    'Barrens Scorpion', 'Barrens Vulture', 'Basilisk', 'Bloodsail Corsair',
    'Bloodsail Pirate', 'Cave Bat', 'Corrupted Guard', 'Dark Iron Dwarf',
    'Dark Iron Guard', 'Dark Iron Sorcerer', 'Defias Bandit', 'Fire Imp',
    'Firelord Servant', 'Flame Wraith', 'Forest Wolf', 'Frozen Wraith',
    'Frostmane Shaman', 'Frostmane Troll', 'Giant Crocodile', 'Giant Spider',
    'Gnoll Raider', 'Ice Claw Bear', 'Ice Elemental', 'Jungle Stalker',
    'Jungle Troll', 'Kobold', 'Lava Elemental', 'Magma Lord',
    'Molten Giant', 'Murloc Scout', 'Panther', 'Plainstrider',
    'Quillboar', 'Razormane Warrior', 'Shadowforge Sentinel', 'Snow Leopard',
    'Stranglethorn Ape', 'Sunscale Raptor', 'Thunder Lizard', 'Tiger',
    'Trogg', 'Venture Co. Enforcer', 'Wind Sweeper', 'Winter Wolf',
    'Young Boar', 'Zhevra'
]

# First 16 bosses (from alphabetical list, matching what's in the grid)
ALL_BOSSES = [
    'Ancient Frost Giant', 'Barrens Overlord', "Bhag'thera", 'Bloodsail Admiral',
    'Defias Ringleader', 'Emperor Thaurissan', 'Frostmane Headhunter', 'Golem Lord',
    'Hogger', 'Ice Lord', 'Jungle Lord', 'Kolkar Centaur Lord',
    'Kurzen the Mad', 'Lord Incendius', 'Magmadar', 'Murloc Warlord'
]

def sanitize_filename(name: str) -> str:
    """Convert mob/boss name to safe filename."""
    name = name.lower()
    name = name.replace(' ', '_')
    name = name.replace("'", '')
    name = name.replace('.', '')
    name = name.replace(',', '')
    name = re.sub(r'[^a-z0-9_]', '', name)
    return name

def is_empty_image(image_path: Path, threshold: float = 0.95) -> bool:
    """Check if image is mostly empty/transparent."""
    try:
        from PIL import Image
        import numpy as np
        
        img = Image.open(image_path)
        if img.mode == 'RGBA':
            # Check alpha channel
            alpha = np.array(img.split()[3])
            transparent_ratio = np.sum(alpha < 10) / alpha.size
            return transparent_ratio > threshold
        else:
            # Check if mostly white/black
            img_array = np.array(img.convert('L'))
            avg_brightness = np.mean(img_array)
            # If very bright (white) or very dark (black), consider empty
            return avg_brightness > 240 or avg_brightness < 15
    except Exception:
        return False

def rename_bestiary(input_dir: Path, output_mobs_dir: Path, output_bosses_dir: Path):
    """Rename bestiary icons."""
    input_dir = Path(input_dir)
    output_mobs_dir = Path(output_mobs_dir)
    output_bosses_dir = Path(output_bosses_dir)
    
    output_mobs_dir.mkdir(parents=True, exist_ok=True)
    output_bosses_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all bestiary files
    bestiary_files = sorted(input_dir.glob('bestiary_*.png'))
    
    print(f"\n📐 Processing {len(bestiary_files)} bestiary icons...")
    print(f"   Expected: 46 mobs + 16 bosses = 62 icons")
    print(f"   Extracted: {len(bestiary_files)} icons\n")
    
    mob_count = 0
    boss_count = 0
    skipped_count = 0
    
    # Process rows 1-6 (mobs)
    mob_idx = 0
    for row in range(1, 7):  # Rows 1-6
        for col in range(1, 10):  # Cols 1-9 (skip header col)
            filename = f"bestiary_{row}_{col}.png"
            file_path = input_dir / filename
            
            if not file_path.exists():
                continue
            
            # Check if empty
            if is_empty_image(file_path):
                print(f"   ⚠️  Skipping empty: {filename}")
                skipped_count += 1
                continue
            
            if mob_idx < len(ALL_MOBS):
                mob_name = ALL_MOBS[mob_idx]
                new_filename = f"{sanitize_filename(mob_name)}.png"
                new_path = output_mobs_dir / new_filename
                
                shutil.copy2(file_path, new_path)
                mob_count += 1
                print(f"   ✅ Mob {mob_count:2d}: {filename} → {new_filename}")
                mob_idx += 1
            else:
                print(f"   ⚠️  Extra mob icon: {filename}")
                skipped_count += 1
    
    # Process rows 7-8 (bosses)
    boss_idx = 0
    for row in range(7, 9):  # Rows 7-8
        for col in range(1, 10):  # Cols 1-9 (skip header col)
            filename = f"bestiary_{row}_{col}.png"
            file_path = input_dir / filename
            
            if not file_path.exists():
                continue
            
            # Check if empty
            if is_empty_image(file_path):
                print(f"   ⚠️  Skipping empty: {filename}")
                skipped_count += 1
                continue
            
            if boss_idx < len(ALL_BOSSES):
                boss_name = ALL_BOSSES[boss_idx]
                new_filename = f"{sanitize_filename(boss_name)}.png"
                new_path = output_bosses_dir / new_filename
                
                shutil.copy2(file_path, new_path)
                boss_count += 1
                print(f"   ✅ Boss {boss_count:2d}: {filename} → {new_filename}")
                boss_idx += 1
            else:
                print(f"   ⚠️  Extra boss icon: {filename}")
                skipped_count += 1
    
    print(f"\n✨ Summary:")
    print(f"   ✅ Mobs:   {mob_count}/46")
    print(f"   ✅ Bosses: {boss_count}/16")
    print(f"   ⚠️  Skipped: {skipped_count}")
    print(f"   📊 Total: {mob_count + boss_count} icons")
    
    if mob_count == 46 and boss_count == 16:
        print(f"\n🎉 Perfect! All 46 mobs and 16 bosses extracted!")
    else:
        print(f"\n⚠️  Mismatch detected. Please verify the grid structure.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Rename bestiary icons')
    parser.add_argument('--input', type=str, default='bestiary_reprocessed/processed', help='Input directory')
    parser.add_argument('--mobs-output', type=str, default='icons/mobs', help='Output directory for mobs')
    parser.add_argument('--bosses-output', type=str, default='icons/bosses', help='Output directory for bosses')
    
    args = parser.parse_args()
    
    rename_bestiary(
        Path(args.input),
        Path(args.mobs_output),
        Path(args.bosses_output)
    )
