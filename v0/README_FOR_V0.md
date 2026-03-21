# MMORPG Bot - Complete Feature Documentation for v0.app

This folder contains all the essential files needed to understand the complete MMORPG Discord bot system.

## 📋 Quick Summary

This is a **Discord MMORPG bot** with:

### CORE SYSTEMS:
- **6 Classes** (Warrior, Paladin, Mage, Rogue, Priest, Hunter) with **12 specializations**
- **Turn-based combat** with 60+ abilities, status effects, crits, dodges
- **Boss fights** with phase-based AI (changes behavior at 50% and 25% HP)
- **5 Zones** (level-gated, each with unique enemies and world bosses)
- **Item system** with 6 rarity tiers (common → artifact) with random stat rolls
- **Enhancement system** (upgrade items with gold/materials)
- **Quest system** (NPC discovery, quest chains, story quests)
- **Guild system** (create/manage guilds, ranks, guild banks)
- **Marketplace** (player-to-player economy with listing fees)
- **World events** (server-wide bonuses every 6 hours)
- **Daily login rewards** and streaks
- **Achievement system**
- **Dungeon system** (multi-floor, party-based)

### GAME MECHANICS:
- **XP/Leveling**: Exponential XP curve, max level 60, specialization at level 10
- **Combat**: Turn-based, abilities have costs (mana/rage/energy), cooldowns, status effects
- **Loot**: Instanced random drops with stat variance based on rarity
- **Economy**: Gold from combat/quests/exploration, marketplace trading
- **Cooldowns**: Persistent across bot restarts (stored in PostgreSQL)

---

## 📁 File Structure & What Each File Contains

### 📖 Documentation
- `README.md` - Main project overview and features
- `FEATURES_QUICK_REFERENCE.md` - Complete feature checklist
- `QUICK_START.md` - Gameplay guide for new players

### ⚙️ Core Configuration
- `config/settings.py` - **ALL game constants**:
  - Classes and specializations (6 classes, 12 specs)
  - Zones (5 zones with level ranges, enemies, bosses)
  - Enemies and bosses (stats, abilities, scaling formulas)
  - Item rarities (6 tiers with colors and multipliers)
  - Abilities (60+ abilities with costs, cooldowns, effects)
  - Game balance (XP curves, combat multipliers, etc.)

### 🗄️ Database
- `database/db.py` - **Complete database schema**:
  - All tables (characters, inventory, items, quests, guilds, etc.)
  - Item templates with all stats
  - Seed data for initial items
  - Foreign key relationships and constraints

### 🎮 Core Game Logic (Services)
- `services/character/character_service.py` - Character management:
  - XP/leveling system
  - Stats calculation (base + equipment + bonuses)
  - Gold management
  - Cooldowns (persistent in DB)
  
- `services/character/inventory_service.py` - Inventory system:
  - Item management (add, remove, equip)
  - Loot generation (random stats based on rarity)
  - Equipment system (8 slots: weapon, armor pieces, accessories)
  - Item selling
  
- `services/combat/combat_engine.py` - **Combat system**:
  - All 60+ abilities (damage, healing, buffs, debuffs)
  - Turn-based combat logic
  - Status effects (DoTs, buffs, debuffs)
  - Crit/dodge calculations
  - Boss AI (phase-based behavior at HP thresholds)
  
- `services/quest/npc_quest_service.py` - Quest system:
  - NPC discovery (random encounters during exploration)
  - Quest chains (prerequisite quests)
  - Quest progress tracking
  - Quest rewards (XP, gold, items)
  
- `services/blacksmith/blacksmith_service.py` - Enhancement system:
  - Item enhancement logic (upgrade items +1, +2, +3, etc.)
  - Enhancement costs (gold + materials)
  - Stat scaling formulas
  - Success/failure rates
  
- `services/dungeon/dungeon_service.py` - Dungeon system:
  - Multi-floor dungeons
  - Dungeon rewards
  - Party mechanics (5-player groups)
  
- `services/achievement/achievement_service.py` - Achievement system
- `services/daily/daily_login_service.py` - Daily login rewards

### 🎯 Feature Implementations (Cogs - Discord Commands)
- `cogs/character/character_cog.py` - Character commands (/character create, profile, specialize, delete)
- `cogs/combat/combat_cog.py` - Combat commands (/fight, /rest)
- `cogs/exploration/exploration_cog.py` - Exploration system (/explore, /travel, /map)
- `cogs/inventory/inventory_cog.py` - Inventory/equipment commands (/inventory, /equip, /sell, /use)
- `cogs/quest/quest_cog.py` - Quest commands (/quest list, accept, complete, abandon)
- `cogs/guild/guild_cog.py` - Guild system (/guild create, info, join, leave, disband)
- `cogs/economy/economy_cog.py` - Marketplace/economy (/market list, buy, /leaderboard)
- `cogs/events/events_cog.py` - World events (/events, /daily)
- `cogs/blacksmith/blacksmith_cog.py` - Enhancement commands (/enhance)
- `cogs/dungeon/dungeon_cog.py` - Dungeon commands (/dungeon start, enter)
- `cogs/achievements/achievements_cog.py` - Achievement commands (/achievements)

### 🚀 Entry Point
- `main.py` - Bot initialization and structure

---

## 🎨 Design Requirements for Web App

Create a **modern, game-like web interface** that:

1. **Visual Design**:
   - Dark fantasy theme (similar to World of Warcraft)
   - Beautiful UI with gradients, shadows, animations
   - Responsive layout (desktop-first, mobile-friendly)
   - Game-like fonts (fantasy/medieval style)

2. **Core Features to Implement**:
   - Character creation and profile display
   - Combat arena with ability buttons and combat log
   - Inventory grid with item tooltips (show rarity, stats)
   - Quest journal with progress tracking
   - Guild management interface
   - Marketplace with buy/sell functionality
   - Enhancement/blacksmith interface
   - Dungeon lobby and party system
   - Achievement showcase
   - World map with zone navigation

3. **Interactive Elements**:
   - Real-time combat updates
   - Drag-and-drop inventory
   - Animated stat bars (HP, mana, XP)
   - Notification system for game events
   - Modal dialogs for item details, quest info, etc.

4. **Data Display**:
   - Character stats with visual bars
   - Equipment slots with item icons
   - Ability cooldown timers
   - Quest progress indicators
   - Gold/XP gain animations

---

## 📝 Reading Order (Recommended)

1. Start with `README.md` for overview
2. Read `config/settings.py` to understand all game constants
3. Read `database/db.py` to understand data structure
4. Read service files to understand game logic:
   - `services/character/character_service.py`
   - `services/character/inventory_service.py`
   - `services/combat/combat_engine.py`
   - `services/quest/npc_quest_service.py`
5. Read cog files to see how features are exposed to users
6. Reference `FEATURES_QUICK_REFERENCE.md` for complete feature list

---

**Goal**: Create a beautiful, modern web application that brings all these MMORPG features to life with an engaging, game-like user experience!
