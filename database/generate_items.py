#!/usr/bin/env python3
"""
Generate 10 items per rarity for each equipment slot.
Outputs SQL INSERT statements.
"""

# Slot configurations: (slot_key, item_type, icon, base_stats_template)
# Base values are multiplied by rarity and index
SLOTS = {
    "head": ("armor", "🪖", {"s_armor": 10, "s_sta": 2, "s_agi": 1}),
    "neck": ("accessory", "📿", {"s_str": 2, "s_agi": 2, "s_int": 2}),
    "chest": ("armor", "🥋", {"s_armor": 15, "s_sta": 3, "s_str": 1}),
    "hands": ("armor", "🧤", {"s_armor": 8, "s_agi": 2, "s_str": 1}),
    "legs": ("armor", "👖", {"s_armor": 12, "s_sta": 2, "s_agi": 1}),
    "feet": ("armor", "👢", {"s_armor": 7, "s_agi": 2, "s_sta": 1}),
    "main_hand": ("weapon", "⚔️", {"s_dmg_min": 8, "s_dmg_max": 12, "s_str": 3}),
    "off_hand": ("weapon", "🛡️", {"s_armor": 8, "s_sta": 2, "s_str": 1}),
    "ring": ("accessory", "💍", {"s_str": 2, "s_agi": 2, "s_int": 2, "s_sta": 1}),
    "trinket": ("accessory", "🔮", {"s_int": 3, "s_spi": 3, "s_sta": 1}),
}

# Item names per slot
ITEM_NAMES = {
    "head": [
        "Leather Cap", "Chain Coif", "Iron Helm", "Steel Crown", "Mithril Circlet",
        "Dragon Scale Helm", "Titanium Visor", "Shadow Veil", "Crystal Diadem", "Eternal Crown"
    ],
    "neck": [
        "Copper Pendant", "Silver Amulet", "Gold Chain", "Platinum Necklace", "Diamond Choker",
        "Ruby Talisman", "Sapphire Locket", "Emerald Collar", "Onyx Torc", "Celestial Pendant"
    ],
    "chest": [
        "Leather Vest", "Chain Mail", "Plate Armor", "Scale Cuirass", "Dragon Scale Mail",
        "Titanium Breastplate", "Shadow Forge Plate", "Crystal Robe", "Eternal Guard", "Divine Aegis"
    ],
    "hands": [
        "Leather Gloves", "Chain Gauntlets", "Iron Fists", "Steel Grips", "Mithril Claws",
        "Dragon Scale Gauntlets", "Titanium Gloves", "Shadow Grasp", "Crystal Mitts", "Eternal Hands"
    ],
    "legs": [
        "Leather Pants", "Chain Leggings", "Iron Greaves", "Steel Legguards", "Mithril Trousers",
        "Dragon Scale Legs", "Titanium Legplates", "Shadow Breeches", "Crystal Leggings", "Eternal Legs"
    ],
    "feet": [
        "Leather Boots", "Chain Sabatons", "Iron Treads", "Steel Stompers", "Mithril Slippers",
        "Dragon Scale Boots", "Titanium Greaves", "Shadow Steps", "Crystal Sandals", "Eternal Treads"
    ],
    "main_hand": [
        "Iron Sword", "Steel Blade", "Mithril Longsword", "Dragon Fang", "Titanium Edge",
        "Shadow Reaper", "Crystal Blade", "Eternal Light", "Divine Wrath", "Cosmic Cleaver"
    ],
    "off_hand": [
        "Wooden Shield", "Iron Buckler", "Steel Barrier", "Mithril Aegis", "Dragon Scale Shield",
        "Titanium Bulwark", "Shadow Ward", "Crystal Barrier", "Eternal Guard", "Divine Protector"
    ],
    "ring": [
        "Copper Ring", "Silver Band", "Gold Signet", "Platinum Circle", "Diamond Ring",
        "Ruby Band", "Sapphire Ring", "Emerald Loop", "Onyx Seal", "Celestial Ring"
    ],
    "trinket": [
        "Copper Charm", "Silver Totem", "Gold Idol", "Platinum Relic", "Diamond Gem",
        "Ruby Crystal", "Sapphire Orb", "Emerald Prism", "Onyx Shard", "Celestial Artifact"
    ],
}

# Descriptions per slot
DESCRIPTIONS = {
    "head": "Protects your head from harm.",
    "neck": "A mystical necklace that enhances your power.",
    "chest": "Sturdy armor for your torso.",
    "hands": "Gloves that improve your dexterity.",
    "legs": "Leg armor for protection.",
    "feet": "Boots that help you move swiftly.",
    "main_hand": "A weapon to strike your enemies.",
    "off_hand": "A shield or off-hand weapon for defense.",
    "ring": "A ring that grants magical properties.",
    "trinket": "A mystical trinket with hidden power.",
}

# Rarity multipliers (base stats scale by rarity)
RARITY_MULTIPLIERS = {
    "common": 1.0,
    "uncommon": 1.5,
    "rare": 2.5,
    "epic": 4.0,
    "legendary": 8.0,
}

# Level requirements per rarity
LEVEL_REQS = {
    "common": [1, 3, 5, 8, 10, 12, 15, 18, 20, 22],
    "uncommon": [5, 8, 10, 12, 15, 18, 20, 22, 25, 28],
    "rare": [15, 18, 20, 22, 25, 28, 30, 32, 35, 38],
    "epic": [25, 28, 30, 32, 35, 38, 40, 42, 45, 48],
    "legendary": [40, 42, 45, 48, 50, 52, 55, 58, 60, 60],
}

# Vendor prices (buy/sell ratio ~2.5:1)
VENDOR_BUY = {
    "common": [10, 12, 15, 18, 20, 22, 25, 28, 30, 35],
    "uncommon": [25, 30, 35, 40, 45, 50, 55, 60, 65, 70],
    "rare": [80, 90, 100, 110, 120, 130, 140, 150, 160, 170],
    "epic": [200, 220, 240, 260, 280, 300, 320, 340, 360, 380],
    "legendary": [500, 550, 600, 650, 700, 750, 800, 850, 900, 1000],
}


def generate_item(slot_key, rarity, index):
    """Generate one item."""
    slot_config = SLOTS[slot_key]
    item_type, icon, base_template = slot_config
    
    name = ITEM_NAMES[slot_key][index]
    desc = DESCRIPTIONS[slot_key]
    level_req = LEVEL_REQS[rarity][index]
    multiplier = RARITY_MULTIPLIERS[rarity]
    
    # Generate stats based on template
    s_str = int(base_template.get("s_str", 0) * multiplier * (1 + index * 0.1))
    s_agi = int(base_template.get("s_agi", 0) * multiplier * (1 + index * 0.1))
    s_int = int(base_template.get("s_int", 0) * multiplier * (1 + index * 0.1))
    s_spi = int(base_template.get("s_spi", 0) * multiplier * (1 + index * 0.1))
    s_sta = int(base_template.get("s_sta", 0) * multiplier * (1 + index * 0.1))
    s_armor = int(base_template.get("s_armor", 0) * multiplier * (1 + index * 0.1))
    
    # Damage for weapons
    if "s_dmg_min" in base_template:
        s_dmg_min = int(base_template["s_dmg_min"] * multiplier * (1 + index * 0.15))
        s_dmg_max = int(base_template["s_dmg_max"] * multiplier * (1 + index * 0.15))
    else:
        s_dmg_min = 0
        s_dmg_max = 0
    
    # Item ID
    item_id = f"{slot_key}_{rarity}_{index+1}"
    
    # Vendor prices
    vendor_buy_price = VENDOR_BUY[rarity][index]
    vendor_sell_price = int(vendor_buy_price * 0.4)  # 40% of buy price
    
    # Build SQL values
    return (
        f"('{item_id}','{name}','{desc}','{item_type}','{rarity}','{slot_key}',{level_req},"
        f"{s_str},{s_agi},{s_int},{s_spi},{s_sta},{s_armor},{s_dmg_min},{s_dmg_max},"
        f"NULL,0,0, {vendor_buy_price},{vendor_sell_price},'{icon}')"
    )


def main():
    """Generate all items."""
    rarities = ["common", "uncommon", "rare", "epic", "legendary"]
    
    print("-- Generated items: 10 per rarity per slot")
    print("-- Total: 10 slots × 5 rarities × 10 items = 500 items\n")
    print("INSERT INTO item_templates")
    print("    (id, name, description, item_type, rarity, equip_slot, level_req,")
    print("     s_str, s_agi, s_int, s_spi, s_sta, s_armor, s_dmg_min, s_dmg_max,")
    print("     effect_type, effect_value, effect_duration,")
    print("     vendor_buy, vendor_sell, icon)")
    print("VALUES")
    
    all_items = []
    for slot_key in SLOTS.keys():
        for rarity in rarities:
            for index in range(10):
                item = generate_item(slot_key, rarity, index)
                all_items.append(item)
    
    # Print all items, comma-separated
    for i, item in enumerate(all_items):
        if i < len(all_items) - 1:
            print(f"    {item},")
        else:
            print(f"    {item}")
    
    print("ON CONFLICT (id) DO UPDATE SET")
    print("    name = EXCLUDED.name,")
    print("    description = EXCLUDED.description,")
    print("    item_type = EXCLUDED.item_type,")
    print("    rarity = EXCLUDED.rarity,")
    print("    equip_slot = EXCLUDED.equip_slot,")
    print("    level_req = EXCLUDED.level_req,")
    print("    s_str = EXCLUDED.s_str,")
    print("    s_agi = EXCLUDED.s_agi,")
    print("    s_int = EXCLUDED.s_int,")
    print("    s_spi = EXCLUDED.s_spi,")
    print("    s_sta = EXCLUDED.s_sta,")
    print("    s_armor = EXCLUDED.s_armor,")
    print("    s_dmg_min = EXCLUDED.s_dmg_min,")
    print("    s_dmg_max = EXCLUDED.s_dmg_max,")
    print("    vendor_buy = EXCLUDED.vendor_buy,")
    print("    vendor_sell = EXCLUDED.vendor_sell,")
    print("    icon = EXCLUDED.icon;")
    
    print(f"\n-- Total items generated: {len(all_items)}")


if __name__ == "__main__":
    main()
