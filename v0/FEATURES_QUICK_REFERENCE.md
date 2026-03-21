# 📋 Features Quick Reference

Quick checklist of all planned features.

## ✅ High Priority (Do First)

- [ ] **1. Crafting & Professions** - Blacksmithing, Alchemy, etc.
- [ ] **2. PvP Arena** - 1v1, 2v2, 3v3 with rankings
- [ ] **3. Quest System** - Story quests and chains
- [ ] **4. Prestige System** - Reset at 60 for bonuses
- [ ] **5. Trading System** - Direct player-to-player trades

## ✅ Medium Priority

- [ ] **6. Item Enchanting** - Upgrade items and add stats
- [ ] **7. Bank System** - Personal and guild banks
- [ ] **8. Mount/Pet System** - Cosmetics and bonuses
- [ ] **9. Title System** - Earn and display titles
- [ ] **10. Statistics Tracking** - Detailed combat/lifetime stats

## ✅ Quality of Life

- [ ] **11. Profile Card Images** - Visual profile cards (see explanation below)
- [ ] **12. Daily Login Rewards** - Streak bonuses
- [ ] **13. Guild Wars** - GvG battles and raids
- [ ] **14. Auction House** - Bidding system
- [ ] **15. Reputation System** - Faction standing

## ✅ Advanced Features

- [ ] **16. Mythic+ Dungeons** - Scaling difficulty
- [ ] **17. Raid System** - 10-20 player raids
- [ ] **18. Seasonal Events** - Holiday events
- [ ] **19. Voice Integration** - Auto-join voice channels
- [ ] **20. Tournament System** - Weekly/monthly tournaments

---

## 🖼️ Feature #11: Profile Card Image Generation - DETAILED EXPLANATION

### What It Does:
Instead of showing text-only profile in Discord, generate a **beautiful image card** that looks like a game character profile.

### Visual Example:
```
╔═══════════════════════════════════════════╗
║  ⚔️  JOHN "THE DESTROYER"  Level 45       ║
║  ───────────────────────────────────────  ║
║  Warrior • Protection Spec                ║
║  [Guild Icon] [UP] Warriors               ║
║  ───────────────────────────────────────  ║
║  ❤️ HP:  ████████░░  800/1000            ║
║  💙 Mana: ██████████  500/500            ║
║  ───────────────────────────────────────  ║
║  ⚔️ Attack: 250  🛡️ Armor: 180          ║
║  🎯 Crit: 15%  💨 Dodge: 8%              ║
║  ───────────────────────────────────────  ║
║  🏆 Achievements: 15 (250 pts)            ║
║  [Badge Icons: 🏆 ⭐ 💎 👑]              ║
║  ───────────────────────────────────────  ║
║  Equipped Items:                           ║
║  [Sword Icon] [Helmet] [Armor] [Boots]   ║
║  ───────────────────────────────────────  ║
║  Prestige Level: 3                         ║
╚═══════════════════════════════════════════╝
```

### How It Works:

1. **Python Library:** Uses `Pillow` (PIL) to create images programmatically
2. **Template System:** 
   - Base template image (background, borders, layout)
   - Different themes per class (Warrior = red/orange, Mage = blue/purple)
   - Prestige level affects border color (gold for high prestige)
3. **Data Collection:** Pulls from database:
   - Character stats, level, class
   - Equipped items
   - Achievements and badges
   - Guild info
4. **Image Generation:**
   - Draw text (name, stats, numbers)
   - Draw progress bars (HP, mana bars)
   - Draw icons (class icon, item icons, badge icons)
   - Apply colors and styling
5. **Output:** Saves as PNG file, sends as Discord attachment

### Technical Details:

**Dependencies:**
```python
# Add to requirements.txt
Pillow>=10.0.0
```

**File Structure:**
```
services/profile/
  ├── profile_card_generator.py  # Main generator
  ├── templates/                 # Image templates
  │   ├── warrior_bg.png
  │   ├── mage_bg.png
  │   └── default_bg.png
  └── icons/                     # Item/class icons
      ├── warrior.png
      ├── sword.png
      └── ...
```

**Example Code Structure:**
```python
from PIL import Image, ImageDraw, ImageFont

class ProfileCardGenerator:
    def generate(self, character_data):
        # 1. Load template based on class
        template = Image.open(f"templates/{character_data['class']}_bg.png")
        
        # 2. Create drawing context
        draw = ImageDraw.Draw(template)
        
        # 3. Draw character name
        draw.text((50, 50), character_data['name'], font=title_font)
        
        # 4. Draw HP bar
        hp_percent = character_data['current_hp'] / character_data['max_hp']
        bar_width = 300
        bar_filled = int(bar_width * hp_percent)
        draw.rectangle([50, 100, 50+bar_filled, 120], fill='red')
        draw.rectangle([50, 100, 50+bar_width, 120], outline='black')
        
        # 5. Draw stats
        draw.text((50, 150), f"Attack: {stats['attack_power']}", font=stats_font)
        
        # 6. Draw equipped items as icons
        for i, item in enumerate(equipped_items):
            icon = Image.open(f"icons/{item['icon']}.png")
            template.paste(icon, (50 + i*40, 200))
        
        # 7. Draw achievements
        for i, badge in enumerate(badges[:5]):
            # Draw badge icon
            ...
        
        # 8. Save and return
        template.save("temp_profile.png")
        return "temp_profile.png"
```

### Benefits:

1. **Visual Appeal:** Much more engaging than text embeds
2. **Shareability:** Players can save and share their cards
3. **Prestige:** High-level players have impressive visual cards
4. **Customization:** Different themes, borders, layouts
5. **Social:** Players compare cards, creates competition

### Commands:
- `/profile card` - Generate your profile card
- `/profile card @player` - View another player's card
- `/profile card theme <theme_name>` - Change card theme/style

### Future Enhancements:
- Animated profile cards (GIF)
- Custom backgrounds from achievements
- Profile card gallery (view all players' cards)
- Profile card sharing to other channels
- Seasonal themes (Halloween, Christmas cards)

---

**See `FEATURE_ROADMAP.md` for full details on all features.**
