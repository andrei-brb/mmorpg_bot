#!/usr/bin/env python3
"""
Rename processed icons to match game item and mob names.
"""

import os
from pathlib import Path
import re

# Item names organized by slot (from ITEM_LIST_FOR_ICONS.md)
# Grid is 10 columns (slots) x 10 rows (rarities/tiers)
ITEM_NAMES_BY_SLOT = {
    'head': [
        'Leather Cap', 'Chain Coif', 'Iron Helm', 'Steel Crown', 'Mithril Circlet',
        'Dragon Scale Helm', 'Titanium Visor', 'Shadow Veil', 'Crystal Diadem', 'Eternal Crown'
    ],
    'neck': [
        'Copper Pendant', 'Silver Amulet', 'Gold Chain', 'Platinum Necklace', 'Diamond Choker',
        'Ruby Talisman', 'Sapphire Locket', 'Emerald Collar', 'Onyx Torc', 'Celestial Pendant'
    ],
    'chest': [
        'Leather Vest', 'Chain Mail', 'Plate Armor', 'Scale Cuirass', 'Dragon Scale Mail',
        'Titanium Breastplate', 'Shadow Forge Plate', 'Crystal Robe', 'Eternal Guard', 'Divine Aegis'
    ],
    'hands': [
        'Leather Gloves', 'Chain Gauntlets', 'Iron Fists', 'Steel Grips', 'Mithril Claws',
        'Dragon Scale Gauntlets', 'Titanium Gloves', 'Shadow Grasp', 'Crystal Mitts', 'Eternal Hands'
    ],
    'legs': [
        'Leather Pants', 'Chain Leggings', 'Iron Greaves', 'Steel Legguards', 'Mithril Trousers',
        'Dragon Scale Legs', 'Titanium Legplates', 'Shadow Breeches', 'Crystal Leggings', 'Eternal Legs'
    ],
    'feet': [
        'Leather Boots', 'Chain Sabatons', 'Iron Treads', 'Steel Stompers', 'Mithril Slippers',
        'Dragon Scale Boots', 'Titanium Greaves', 'Shadow Steps', 'Crystal Sandals', 'Eternal Treads'
    ],
    'main_hand': [
        'Iron Sword', 'Steel Blade', 'Mithril Longsword', 'Dragon Fang', 'Titanium Edge',
        'Shadow Reaper', 'Crystal Blade', 'Eternal Light', 'Divine Wrath', 'Cosmic Cleaver'
    ],
    'off_hand': [
        'Wooden Shield', 'Iron Buckler', 'Steel Barrier', 'Mithril Aegis', 'Dragon Scale Shield',
        'Titanium Bulwark', 'Shadow Ward', 'Crystal Barrier', 'Eternal Guard', 'Divine Protector'
    ],
    'ring': [
        'Copper Ring', 'Silver Band', 'Gold Signet', 'Platinum Circle', 'Diamond Ring',
        'Ruby Band', 'Sapphire Ring', 'Emerald Loop', 'Onyx Seal', 'Celestial Ring'
    ],
    'trinket': [
        'Copper Charm', 'Silver Totem', 'Gold Idol', 'Platinum Relic', 'Diamond Gem',
        'Ruby Crystal', 'Sapphire Orb', 'Emerald Prism', 'Onyx Shard', 'Celestial Artifact'
    ]
}

# Unique named items (from seed data)
UNIQUE_ITEMS = {
    'iron_sword': 'Iron Sword',
    'dwarven_axe': 'Dwarven Axe',
    'bone_club': 'Bone Club',
    'corsair_blade': 'Corsair Blade',
    'sulfuron_blade': 'Sulfuron Blade',
    'leather_cap': 'Leather Cap',
    'chain_coif': 'Chain Coif',
    'raptor_hide_vest': 'Raptor Hide Vest',
    'jungle_leather_chest': 'Jungle Leather Chest',
    'shadowforge_plate': 'Shadowforge Plate',
    'health_potion': 'Health Potion',
    'frost_resist_potion': 'Frost Resist Potion',
    'stamina_draught': 'Stamina Draught',
    'elixir_of_fortitude': 'Elixir of Fortitude',
    'flask_of_the_titans': 'Flask of the Titans',
    'protection_blessing_scroll': 'Blessing Scroll',
    'protection_safety_charm': 'Safety Charm',
    'protection_enhancement_fragment': 'Enhancement Fragment',
}

# Mobs organized by zone (from MOBS_AND_BOSSES_LIST.md)
MOBS_BY_ZONE = {
    'elwynn_forest': [
        'Forest Wolf', 'Kobold', 'Defias Bandit', 'Young Boar', 'Corrupted Guard',
        'Giant Spider', 'Murloc Scout', 'Gnoll Raider'
    ],
    'dun_morogh': [
        'Ice Claw Bear', 'Trogg', 'Frostmane Troll', 'Snow Leopard', 'Frozen Wraith',
        'Ice Elemental', 'Winter Wolf', 'Cave Bat', 'Frostmane Shaman'
    ],
    'barrens': [
        'Razormane Warrior', 'Plainstrider', 'Sunscale Raptor', 'Barrens Scorpion', 'Zhevra',
        'Thunder Lizard', 'Quillboar', 'Wind Sweeper', 'Barrens Vulture'
    ],
    'stranglethorn': [
        'Bloodsail Pirate', 'Jungle Stalker', 'Venture Co. Enforcer', 'Panther', 'Tiger',
        'Basilisk', 'Jungle Troll', 'Giant Crocodile', 'Stranglethorn Ape', 'Bloodsail Corsair'
    ],
    'blackrock_depths': [
        'Dark Iron Dwarf', 'Molten Giant', 'Firelord Servant', 'Lava Elemental', 'Dark Iron Guard',
        'Fire Imp', 'Shadowforge Sentinel', 'Magma Lord', 'Dark Iron Sorcerer', 'Flame Wraith'
    ]
}

BOSSES = [
    'Hogger', 'Defias Ringleader', 'Spider Queen', 'Murloc Warlord',
    'Frostmane Headhunter', 'Ice Lord', 'Trogg Overlord', 'Ancient Frost Giant',
    'Kolkar Centaur Lord', 'Razormane Chieftain', 'Thunderhawk Alpha', 'Barrens Overlord',
    'Kurzen the Mad', "Bhag'thera", 'Bloodsail Admiral', 'Jungle Lord',
    'Emperor Thaurissan', 'Lord Incendius', 'Magmadar', 'Golem Lord'
]

def sanitize_filename(name: str) -> str:
    """Convert item/mob name to safe filename."""
    # Replace spaces and special chars
    name = name.lower()
    name = name.replace(' ', '_')
    name = name.replace("'", '')
    name = name.replace('.', '')
    name = name.replace(',', '')
    name = re.sub(r'[^a-z0-9_]', '', name)
    return name

def rename_items(items_dir: Path, output_dir: Path):
    """Rename item icons to match game names."""
    # Grid: 10 columns (slots) x 10 rows (tiers)
    # Column 0 = head, Column 1 = neck, etc.
    slot_order = ['head', 'neck', 'chest', 'hands', 'legs', 'feet', 'main_hand', 'off_hand', 'ring', 'trinket']
    
    # Rarity tiers (rows 1-10, but we skip row 0 which is header)
    rarity_tiers = ['common', 'uncommon', 'rare', 'epic', 'legendary']
    
    items_dir = Path(items_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all item files
    item_files = sorted(items_dir.glob('item_*.png'))
    
    print(f"\n📦 Renaming {len(item_files)} item icons...")
    
    renamed_count = 0
    for item_file in item_files:
        # Parse grid position: item_ROW_COL.png
        match = re.match(r'item_(\d+)_(\d+)\.png', item_file.name)
        if not match:
            continue
        
        row = int(match.group(1))
        col = int(match.group(2))
        
        # Skip header row (row 0) and header column (col 0)
        if row == 0 or col == 0:
            continue
        
        # Adjust for 0-based indexing (row 1-9 = tier 0-8, but we want 0-9)
        # Actually, rows 1-10 are the tiers, columns 1-10 are the slots
        tier_idx = row - 1
        slot_idx = col - 1
        
        if slot_idx >= len(slot_order) or tier_idx >= 10:
            continue
        
        slot = slot_order[slot_idx]
        tier_name = rarity_tiers[min(tier_idx // 2, len(rarity_tiers) - 1)]  # Every 2 rows = new rarity
        
        # Get item name for this slot and tier
        if slot in ITEM_NAMES_BY_SLOT:
            slot_items = ITEM_NAMES_BY_SLOT[slot]
            if tier_idx < len(slot_items):
                item_name = slot_items[tier_idx]
                new_filename = f"{sanitize_filename(item_name)}_{tier_name}.png"
                new_path = output_dir / new_filename
                
                # Copy file
                import shutil
                shutil.copy2(item_file, new_path)
                renamed_count += 1
                print(f"   ✅ {item_file.name} → {new_filename}")
    
    print(f"\n✨ Renamed {renamed_count} item icons!")

def rename_mobs(mobs_dir: Path, output_dir: Path):
    """Rename mob/boss icons to match game names."""
    mobs_dir = Path(mobs_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all mob files
    mob_files = sorted(mobs_dir.glob('mob_*.png'))
    
    print(f"\n🐺 Renaming {len(mob_files)} mob/boss icons...")
    
    # Flatten all mobs into a single list
    all_mobs = []
    for zone_mobs in MOBS_BY_ZONE.values():
        all_mobs.extend(zone_mobs)
    all_mobs.extend(BOSSES)
    
    renamed_count = 0
    for idx, mob_file in enumerate(mob_files):
        # Parse grid position: mob_ROW_COL.png
        match = re.match(r'mob_(\d+)_(\d+)\.png', mob_file.name)
        if not match:
            continue
        
        row = int(match.group(1))
        col = int(match.group(2))
        
        # Skip header row/col
        if row == 0 or col == 0:
            continue
        
        # Calculate index: (row - 1) * 8 + (col - 1) - 1 (accounting for header)
        # Actually simpler: just use sequential index
        mob_idx = (row - 1) * 7 + (col - 1) - 1  # 7 cols per row (excluding header)
        
        if mob_idx < len(all_mobs):
            mob_name = all_mobs[mob_idx]
            new_filename = f"{sanitize_filename(mob_name)}.png"
            new_path = output_dir / new_filename
            
            # Copy file
            import shutil
            shutil.copy2(mob_file, new_path)
            renamed_count += 1
            print(f"   ✅ {mob_file.name} → {new_filename}")
    
    print(f"\n✨ Renamed {renamed_count} mob/boss icons!")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Rename icons to match game names')
    parser.add_argument('--items-dir', type=str, default='items_processed/processed_final', help='Items directory')
    parser.add_argument('--mobs-dir', type=str, default='mobs_processed/processed_final', help='Mobs directory')
    parser.add_argument('--items-output', type=str, default='icons/items', help='Output directory for items')
    parser.add_argument('--mobs-output', type=str, default='icons/mobs', help='Output directory for mobs')
    
    args = parser.parse_args()
    
    # Rename items
    if Path(args.items_dir).exists():
        rename_items(args.items_dir, args.items_output)
    
    # Rename mobs
    if Path(args.mobs_dir).exists():
        rename_mobs(args.mobs_dir, args.mobs_output)
    
    print("\n✅ All icons renamed!")

if __name__ == '__main__':
    main()
