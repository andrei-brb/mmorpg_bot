# 🔧 Environment Variables Setup Guide

## Quick Setup

1. **Create a `.env` file** in the project root (same folder as `main.py`)
2. **Copy the template below** and fill in your values
3. **Save the file** — the bot will automatically load it on startup

---

## Required Variables

### ✅ `DISCORD_TOKEN` (REQUIRED)
Your Discord bot token from https://discord.com/developers/applications

```env
DISCORD_TOKEN=your_bot_token_here
```

**How to get it:**
1. Go to https://discord.com/developers/applications
2. Click your bot application (or create a new one)
3. Go to **Bot** → **Reset Token** → Copy it
4. Paste it in your `.env` file

---

### ✅ `DATABASE_URL` (REQUIRED)
PostgreSQL connection string for your database.

**Local PostgreSQL (what you're using now):**
```env
DATABASE_URL=postgresql://mmorpg_user:yourpassword@localhost:5432/mmorpg
```

**Format breakdown:**
- `mmorpg_user` = your PostgreSQL username
- `yourpassword` = your PostgreSQL password
- `localhost:5432` = database host and port
- `mmorpg` = database name

**If using Docker Compose:**
```env
DATABASE_URL=postgresql://mmorpg_user:changeme@db:5432/mmorpg
```
(Use `db` as hostname, not `localhost`)

**If using a cloud database (Supabase, ElephantSQL, etc.):**
```env
DATABASE_URL=postgresql://user:pass@hostname:5432/dbname
```
(Copy the connection string from your cloud provider)

---

## Optional Variables

### 📊 `LOG_LEVEL` (Optional)
Controls how much logging you see. Default: `INFO`

```env
LOG_LEVEL=INFO
```

**Options:**
- `DEBUG` = Very detailed logs (for troubleshooting)
- `INFO` = Normal logs (recommended)
- `WARNING` = Only warnings and errors
- `ERROR` = Only errors

---

### 🔴 `REDIS_URL` (Optional - Not Used Yet)
For future caching/rate limiting. You can leave this blank for now.

```env
REDIS_URL=redis://localhost:6379/0
```

---

### 💳 Stripe Variables (Optional - Future Monetization)
Only needed if you plan to add premium features later. Leave blank for now.

```env
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_SERVER_PREMIUM_PRICE_ID=
STRIPE_PLAYER_PREMIUM_PRICE_ID=
```

---

## Complete `.env` Template

Copy this into a file named `.env` in your project root:

```env
# ═══════════════════════════════════════════════════════════════════════════
# World of Discord — Environment Configuration
# ═══════════════════════════════════════════════════════════════════════════

# ── REQUIRED ────────────────────────────────────────────────────────────────
DISCORD_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://mmorpg_user:yourpassword@localhost:5432/mmorpg

# ── OPTIONAL ────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
REDIS_URL=redis://localhost:6379/0

# ── STRIPE (Future) ─────────────────────────────────────────────────────────
# STRIPE_SECRET_KEY=
# STRIPE_WEBHOOK_SECRET=
# STRIPE_SERVER_PREMIUM_PRICE_ID=
# STRIPE_PLAYER_PREMIUM_PRICE_ID=
```

---

## ✅ Verification

After creating your `.env` file, test it:

```bash
# Make sure you're in the project directory
cd /Users/tara/Downloads/mmorpg_bot

# Activate virtual environment
source .venv/bin/activate

# Run the bot
python main.py
```

**You should see:**
```
INFO bot: Connecting to database...
INFO database: Database pool ready (min=5, max=20).
INFO database: Schema initialized.
INFO bot: ✓ Database ready
INFO bot: Loading cogs...
INFO bot: ✓ Online as YourBotName#1234 (ID: ...)
```

**If you see errors:**
- `DISCORD_TOKEN is not set` → Check your `.env` file exists and has `DISCORD_TOKEN=...`
- `database "mmorpg" does not exist` → Create the database (see database setup guide)
- `password authentication failed` → Check your `DATABASE_URL` password matches PostgreSQL

---

## 🔒 Security Notes

- **NEVER commit `.env` to git** — it's already in `.gitignore`
- **Keep your `DISCORD_TOKEN` secret** — anyone with it can control your bot
- **Use strong database passwords** in production
- **Rotate tokens** if you suspect they're compromised

---

## 🐳 Docker Compose Users

If using `docker-compose.yml`, you can also set variables in the `docker-compose.yml` file or use a `.env` file (Docker Compose automatically loads it).

**Example `docker-compose.yml` override:**
```yaml
services:
  bot:
    environment:
      DISCORD_TOKEN: ${DISCORD_TOKEN}
      DATABASE_URL: postgresql://mmorpg_user:${DB_PASSWORD}@db:5432/mmorpg
```

Then in your `.env`:
```env
DISCORD_TOKEN=your_token
DB_PASSWORD=your_db_password
```
