# 🗡️ World of Discord — WoW-inspired Discord MMORPG Bot

A fully-featured, production-ready Discord MMORPG inspired by World of Warcraft.  
Built with Python, discord.py, and PostgreSQL.

---

## ✨ Features

| System | Details |
|--------|---------|
| **6 Classes** | Warrior, Paladin, Mage, Rogue, Priest, Hunter |
| **12 Specializations** | 2 per class, unlocked at level 10, permanent choice |
| **Combat Engine** | Turn-based with abilities, DoTs, crits, dodges, status effects |
| **Boss Fights** | Phase-based AI that changes behavior at 50% and 25% HP |
| **5 Zones** | Level-gated zones with lore, enemies, and world bosses |
| **Loot System** | 6 rarity tiers with instanced random stat rolls |
| **Guild System** | Create, manage, and rank members in player guilds |
| **Marketplace** | Full player-to-player economy with listing fees |
| **World Events** | Server-wide events every 6 hours with XP/gold bonuses |
| **Daily Quests** | Rotating daily objectives |
| **Admin Tools** | GM commands for gold, XP, items, events, server config |
| **Persistent Cooldowns** | Survive bot restarts via PostgreSQL |
| **Monetization Hooks** | Stripe-ready premium tiers for servers and players |

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))

### 2. Clone & Install

```bash
git clone <your-repo>
cd mmorpg_bot

# (Recommended) Create a local virtualenv
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
nano .env
```

Required `.env` values:
```
DISCORD_TOKEN=your_bot_token
DATABASE_URL=postgresql://user:password@localhost:5432/mmorpg
```

### 4. Create the Database

```sql
-- In psql:
CREATE DATABASE mmorpg;
CREATE USER mmorpg_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE mmorpg TO mmorpg_user;
```

The schema initializes automatically on first run.

### 5. Run

```bash
python main.py
```

---

## 📁 Project Structure

```
mmorpg_bot/
├── main.py                         # Bot entry point
├── requirements.txt
├── .env.example
│
├── config/
│   └── settings.py                 # ALL game constants (classes, zones, enemies, rarities)
│
├── database/
│   └── db.py                       # asyncpg pool + complete PostgreSQL schema
│
├── services/
│   ├── character/
│   │   ├── character_service.py    # XP, leveling, stats, gold, cooldowns
│   │   └── inventory_service.py    # Items, loot gen, equip, sell
│   └── combat/
│       └── combat_engine.py        # All 60+ abilities, status effects, AI
│
└── cogs/
    ├── character/character_cog.py  # /character create|profile|specialize|delete|classes
    ├── combat/combat_cog.py        # /fight /rest
    ├── exploration/exploration_cog.py  # /explore /travel /map
    ├── inventory/inventory_cog.py  # /inventory /equip /sell /use
    ├── guild/guild_cog.py          # /guild create|info|leave|disband
    ├── economy/economy_cog.py      # /market /leaderboard /gold
    ├── events/events_cog.py        # /events /daily + background loops
    ├── admin/admin_cog.py          # /admin givegold|givexp|giveitem|setup|stats
    └── help_cog.py                 # /help
```

---

## ⚔️ Classes & Specs

| Class | Role | Resource | Specs |
|-------|------|----------|-------|
| Warrior | Tank | Rage | Arms (DPS) / Protection (Tank) |
| Paladin | Tank | Mana | Retribution (DPS) / Holy (Healer) |
| Mage | DPS | Mana | Fire (DPS) / Frost (DPS) |
| Rogue | DPS | Energy | Assassination (DPS) / Subtlety (DPS) |
| Priest | Healer | Mana | Holy (Healer) / Shadow (DPS) |
| Hunter | DPS | Mana | Marksmanship (DPS) / Beast Mastery (DPS) |

---

## 🗺️ Zones

| Zone | Levels | Faction |
|------|--------|---------|
| Elwynn Forest | 1–10 | Alliance |
| Dun Morogh | 1–10 | Alliance |
| The Barrens | 10–25 | Horde |
| Stranglethorn Vale | 25–45 | Neutral |
| Blackrock Depths | 50–60 | Neutral |

---

## 💰 Monetization

The bot is Stripe-ready. Two revenue streams:

**Server Premium** (`$9–15/month`):  
- Custom XP/gold multipliers  
- Expanded guild slots  
- Custom item drops  
- Priority support

**Player Premium** (`$3–5/month`):  
- 60 inventory slots (vs 20 free)  
- Rested XP bonus  
- Exclusive cosmetic titles  

To activate: set `STRIPE_SECRET_KEY` and `STRIPE_SERVER_PREMIUM_PRICE_ID` in `.env`.

---

## 🔧 Extending the Game

### Add a new zone
In `config/settings.py`, add a `ZoneConfig` to the `ZONES` dict and insert to `zone_state` in the schema seed.

### Add a new ability
In `services/combat/combat_engine.py`, add an `Ability` dataclass to `ABILITIES`. Assign it to a class in `config/settings.py`.

### Add a new item
Insert a row into `item_templates` in the DB seed section of `database/db.py`.

### Add a new class
Add a `ClassConfig` to `CLASSES` in `config/settings.py` and add 2 `SpecConfig` entries to `SPECIALIZATIONS`.

---

## 🏗️ Roadmap (Phase 2+)

- [ ] Party / group dungeon system (5-player threads)
- [ ] Raid system (20-player events)
- [ ] PvP arena with seasonal ladders
- [ ] Crafting / profession system
- [ ] Prestige system (reset at level 60 for permanent bonuses)
- [ ] Profile card image generation (Pillow)
- [ ] Stripe webhook integration (auto premium activation)
- [ ] Mythic+ dungeon affixes
- [ ] Achievement system completion
- [ ] Mount / cosmetic system

---

## 📜 License

MIT License — build freely, monetize freely.
