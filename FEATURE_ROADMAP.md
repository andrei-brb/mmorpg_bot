# 🗺️ Feature Roadmap - Complete MMORPG Expansion

This document tracks all planned features for the Discord MMORPG bot.

---

## 🎯 High-Impact Features (Priority 1)

### ✅ 1. Crafting & Professions System
**Status:** Not Started  
**Description:**
- Multiple professions: Blacksmithing, Alchemy, Enchanting, Tailoring, Engineering
- Gather materials from zones/enemies (ores, herbs, cloth, etc.)
- Craft consumables, gear, and upgrades
- Profession levels (1-100) with recipes unlocked at milestones
- Crafted items can be sold on marketplace

**Commands:**
- `/craft` - Open crafting menu
- `/profession` - View your professions and levels
- `/gather` - Gather materials in current zone

**Database:**
- `professions` table (character_id, profession_name, level, xp)
- `recipes` table (recipe_id, profession, level_req, materials JSONB, result_item)
- `materials` table (material_id, name, rarity, source)

---

### ✅ 2. PvP Arena System
**Status:** Not Started  
**Description:**
- 1v1, 2v2, 3v3 arena matches
- Seasonal rankings with Elo/MMR system
- Arena-specific rewards (titles, cosmetics, gear)
- Queue system for matchmaking
- Arena seasons reset every month

**Commands:**
- `/arena queue [1v1|2v2|3v3]` - Join arena queue
- `/arena stats` - View your arena statistics
- `/arena leaderboard [season]` - View rankings

**Database:**
- `arena_matches` table (match_id, season, participants, winner, elo_changes)
- `arena_stats` table (character_id, season, wins, losses, elo, rank)

---

### ✅ 3. Quest System Expansion
**Status:** Partially Implemented (daily quests exist, need story quests)  
**Description:**
- Story quests with narrative and chain quests
- Zone-specific quests that unlock content
- Quest rewards: XP, gold, items, reputation
- Quest tracking and progress display

**Commands:**
- `/quest` - View active quests
- `/quest accept <quest_id>` - Accept a quest
- `/quest complete` - Complete current quest objectives

**Database:**
- Already has `quest_templates` and `character_quests` tables
- Need to populate with actual quests

---

### ✅ 4. Prestige System
**Status:** Not Started (database has `prestige` column)  
**Description:**
- At level 60, players can "prestige" (reset to level 1)
- Gain permanent bonuses: +1% XP, +1% gold, +1% stats per prestige level
- Unlock exclusive cosmetics, titles, and items
- Prestige levels shown in profile

**Commands:**
- `/prestige` - View prestige options
- `/prestige reset` - Prestige your character (confirmation required)

**Database:**
- Already has `prestige` column in characters table
- Need `prestige_rewards` table for unlocks

---

### ✅ 5. Trading System
**Status:** Not Started  
**Description:**
- Direct player-to-player trades (not just marketplace)
- Trade window with item/gold confirmation
- Both players must confirm before trade completes
- Trade history logging

**Commands:**
- `/trade @player` - Initiate trade with another player
- Trade window UI with confirm buttons

**Database:**
- `trades` table (trade_id, initiator_id, target_id, items, gold, status, completed_at)

---

## 🎨 Medium-Impact Features (Priority 2)

### ✅ 6. Item Enchanting/Upgrading System
**Status:** Not Started  
**Description:**
- Upgrade item rarity (common → uncommon → rare → epic → legendary)
- Enchant items with stat bonuses (requires materials)
- Item level upgrades
- Enchanting can fail (with material loss)

**Commands:**
- `/enchant <item_id>` - Enchant an item
- `/upgrade <item_id>` - Upgrade item rarity

**Database:**
- `item_enchantments` table (item_id, enchant_type, enchant_level, stats)
- `enchantment_templates` table (enchant_id, name, materials, success_rate)

---

### ✅ 7. Bank System
**Status:** Not Started (database has `bank_gold` column)  
**Description:**
- Personal bank: Extra storage for items (expandable)
- Guild bank: Shared storage for guild members
- Bank access from any zone
- Deposit/withdraw items and gold

**Commands:**
- `/bank` - Open your personal bank
- `/guild bank` - Open guild bank (if officer+)

**Database:**
- `bank_items` table (character_id, item_id, slot)
- `guild_bank_items` table (guild_id, item_id, slot, deposited_by)

---

### ✅ 8. Mount/Pet System
**Status:** Not Started  
**Description:**
- **Mounts:** Reduce travel cooldown, cosmetic display
- **Pets:** Cosmetic companions, some provide small stat bonuses
- Mounts/pets obtained from achievements, quests, or marketplace
- Display in profile

**Commands:**
- `/mount` - View/equip mounts
- `/pet` - View/equip pets

**Database:**
- `mounts` table (mount_id, name, speed_bonus, icon, source)
- `character_mounts` table (character_id, mount_id, obtained_at)
- `pets` table (pet_id, name, stat_bonus, icon, source)
- `character_pets` table (character_id, pet_id, obtained_at)

---

### ✅ 9. Title System
**Status:** Not Started  
**Description:**
- Earn titles from achievements, quests, PvP, etc.
- Display in profile: "John 'The Destroyer'"
- Titles can provide small stat bonuses
- Prestige titles for high prestige levels

**Commands:**
- `/title` - View available titles
- `/title equip <title_id>` - Equip a title

**Database:**
- `titles` table (title_id, name, description, source, stat_bonus)
- `character_titles` table (character_id, title_id, earned_at)
- Add `active_title` column to characters table

---

### ✅ 10. Statistics Tracking System
**Status:** Not Started  
**Description:**
- Detailed combat stats: DPS, healing done, damage taken, crits
- Lifetime stats: Total gold earned, items collected, enemies killed
- Per-zone statistics
- Leaderboards by various stats

**Commands:**
- `/stats` - View your detailed statistics
- `/stats leaderboard [stat_type]` - View stat leaderboards

**Database:**
- `character_stats` table (character_id, stat_type, value, updated_at)
- `combat_stats` table (character_id, total_damage, total_healing, crits, dodges)

---

## 🖼️ Feature #11: Profile Card Image Generation (Detailed Explanation)

### What It Is:
Instead of just showing text in `/character profile`, generate a **visual image card** that displays:
- Character portrait/avatar (class icon or custom)
- Character name and level
- Stats displayed visually (bars, numbers)
- Equipped items shown as icons
- Achievements/badges displayed
- Guild tag and rank
- Background based on zone/class
- Border color based on prestige level

### How It Works:
1. **Library:** Use Python's `Pillow` (PIL) library to generate images
2. **Template:** Create image templates for different classes/levels
3. **Data:** Pull character data from database
4. **Generation:** Combine template + data → PNG image
5. **Display:** Send image as Discord embed attachment

### Example Output:
```
┌─────────────────────────────────┐
│  [Class Icon]  John "The Hero"  │
│  Level 45 Warrior               │
│  ─────────────────────────────  │
│  ❤️ HP: ████████░░ 800/1000    │
│  ⚔️ ATK: 250  🛡️ ARM: 180      │
│  ─────────────────────────────  │
│  🏆 Achievements: 15            │
│  🏰 Guild: [UP] Warriors        │
│  ─────────────────────────────  │
│  [Item Icons: Sword, Armor...]  │
└─────────────────────────────────┘
```

### Implementation:
- Create `services/profile/profile_card_generator.py`
- Use Pillow to draw text, shapes, icons
- Cache generated images (don't regenerate every time)
- Support different themes/styles
- Optional: Use Discord avatar as character portrait

### Commands:
- `/profile card` - Generate and display profile card image
- `/profile card [member]` - View another player's card

### Benefits:
- **Visual Appeal:** Much more engaging than text
- **Shareability:** Players can share their cards
- **Prestige:** High-level players have impressive cards
- **Customization:** Different styles/themes

---

## 🔧 Quality-of-Life Features (Priority 3)

### ✅ 12. Daily Login Rewards
**Status:** Not Started  
**Description:**
- Daily login streak bonuses
- Weekly/monthly milestone rewards
- Streak resets if you miss a day
- Rewards scale with streak length

**Commands:**
- `/daily login` - Claim daily reward
- `/daily streak` - View your login streak

**Database:**
- `login_streaks` table (character_id, current_streak, last_login, longest_streak)

---

### ✅ 13. Guild Wars/Events
**Status:** Not Started  
**Description:**
- Guild vs Guild battles (scheduled events)
- Guild raids (10-20 players)
- Guild rankings and leaderboards
- Guild-specific achievements

**Commands:**
- `/guild war challenge @guild` - Challenge another guild
- `/guild raid start` - Start a guild raid

**Database:**
- `guild_wars` table (war_id, guild1_id, guild2_id, status, winner)
- `guild_raids` table (raid_id, guild_id, participants, boss, status)

---

### ✅ 14. Auction House (Enhanced Marketplace)
**Status:** Not Started (marketplace exists, needs bidding)  
**Description:**
- Bid system (not just "buy now")
- Auction timer (24-48 hours)
- Auto-bid system
- Better search/filtering

**Commands:**
- `/auction list` - Browse auctions
- `/auction bid <auction_id> <amount>` - Place a bid
- `/auction create <item_id> <starting_price> <duration>` - Create auction

**Database:**
- Enhance `market_listings` table with `auction_type`, `current_bid`, `bidder_id`, `ends_at`

---

### ✅ 15. Reputation System
**Status:** Not Started  
**Description:**
- Zone/faction reputation (Honored, Revered, Exalted)
- Unlock vendors, quests, items at reputation tiers
- Reputation gained from quests, kills, donations
- Reputation decay over time (optional)

**Commands:**
- `/reputation` - View your reputation standings
- `/reputation vendor <faction>` - View faction vendor

**Database:**
- `reputation` table (character_id, faction, standing, points, rank)

---

## 🚀 Advanced Features (Priority 4)

### ✅ 16. Mythic+ Dungeons
**Status:** Not Started  
**Description:**
- Scaling difficulty with affixes (enrage, time limit, etc.)
- Timed runs with better rewards for faster completion
- Keystone system (higher keys = harder = better loot)
- Weekly leaderboards

**Commands:**
- `/mythic+ enter <dungeon> <key_level>` - Enter mythic+ dungeon
- `/mythic+ leaderboard` - View weekly leaderboard

**Database:**
- `mythic_runs` table (run_id, dungeon_key, key_level, affixes, time, completed)

---

### ✅ 17. Raid System
**Status:** Not Started  
**Description:**
- 10-20 player raids
- Complex boss mechanics (phases, adds, mechanics)
- Raid lockouts (once per week)
- Raid-specific loot

**Commands:**
- `/raid create <raid_name>` - Create raid group
- `/raid invite @player` - Invite to raid
- `/raid start` - Begin raid

**Database:**
- `raids` table (raid_id, raid_name, difficulty, participants, status)
- `raid_bosses` table (boss_id, raid_id, name, mechanics JSONB)

---

### ✅ 18. Seasonal Events
**Status:** Not Started  
**Description:**
- Holiday events (Halloween, Christmas, etc.)
- Limited-time rewards, items, quests
- Event-specific achievements
- Seasonal cosmetics

**Commands:**
- `/events seasonal` - View active seasonal events
- `/events participate <event_id>` - Join event

**Database:**
- `seasonal_events` table (event_id, name, start_date, end_date, rewards)
- `event_participants` table (character_id, event_id, progress)

---

### ✅ 19. Voice Channel Integration
**Status:** Not Started  
**Description:**
- Auto-join voice channel for party dungeons
- Voice-based commands (optional)
- Better coordination for raids

**Implementation:**
- Requires `discord.py[voice]` and `PyNaCl`
- Voice channel creation for parties
- Optional voice commands

---

### ✅ 20. Tournament System
**Status:** Not Started  
**Description:**
- Weekly/monthly tournaments
- Bracket system (single/double elimination)
- Prizes for winners
- Tournament-specific titles

**Commands:**
- `/tournament register` - Register for tournament
- `/tournament bracket` - View tournament bracket
- `/tournament results` - View past tournament results

**Database:**
- `tournaments` table (tournament_id, type, start_date, participants, bracket, winner)

---

## 📊 Implementation Priority

### Phase 1 (Core Systems)
1. ✅ Crafting & Professions
2. ✅ PvP Arena System
3. ✅ Quest System Expansion
4. ✅ Trading System

### Phase 2 (Progression)
5. ✅ Prestige System
6. ✅ Item Enchanting/Upgrading
7. ✅ Bank System
8. ✅ Title System

### Phase 3 (Engagement)
9. ✅ Profile Card Image Generation (#11)
10. ✅ Statistics Tracking
11. ✅ Mount/Pet System
12. ✅ Daily Login Rewards

### Phase 4 (Advanced)
13. ✅ Guild Wars/Events
14. ✅ Auction House Enhancement
15. ✅ Reputation System
16. ✅ Mythic+ Dungeons

### Phase 5 (Endgame)
17. ✅ Raid System
18. ✅ Seasonal Events
19. ✅ Voice Channel Integration
20. ✅ Tournament System

---

## 📝 Notes

- Features marked with ✅ are planned but not yet implemented
- Database schemas are suggestions - may need adjustment during implementation
- Some features may require additional dependencies (e.g., Pillow for #11)
- Priority order can be adjusted based on player feedback

---

**Last Updated:** 2026-02-18  
**Total Features:** 20  
**Status:** Planning Phase
