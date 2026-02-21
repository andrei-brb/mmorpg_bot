# 🚀 Step-by-Step Setup Guide

## ✅ Step 1: Database Setup

### Option A: Cloud Database (Easiest - Recommended)

1. Go to https://supabase.com
2. Sign up / Sign in
3. Click "New Project"
4. Fill in:
   - Name: `mmorpg-bot`
   - Database Password: (save this!)
   - Region: Choose closest
5. Wait ~2 minutes for setup
6. Go to **Settings → Database**
7. Find **"Connection string"** → Select **"URI"**
8. Copy the connection string (looks like: `postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres`)

### Option B: Local PostgreSQL

```bash
# Install PostgreSQL
brew install postgresql@16

# Start PostgreSQL service
brew services start postgresql@16

# Create database and user
psql postgres
```

Then in psql, run:
```sql
CREATE DATABASE mmorpg;
CREATE USER mmorpg_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE mmorpg TO mmorpg_user;
\q
```

Your connection string will be:
```
postgresql://mmorpg_user:yourpassword@localhost:5432/mmorpg
```

---

## ✅ Step 2: Get Discord Bot Token

1. Go to https://discord.com/developers/applications
2. Click **"New Application"**
3. Name it: `World of Discord` (or any name)
4. Click **"Bot"** in the left sidebar
5. Click **"Add Bot"** → Confirm
6. Click **"Reset Token"** → Copy the token (save it securely!)
7. Scroll down to **"Privileged Gateway Intents"** and enable:
   - ✅ **Presence Intent**
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
8. Click **"OAuth2"** → **"URL Generator"**
9. Select:
   - ✅ **bot**
   - ✅ **applications.commands**
10. Under **"Bot Permissions"**, select **"Administrator"** (or manually select: Send Messages, Embed Links, Use Slash Commands)
11. Copy the generated URL and open it in your browser
12. Select your test server and click **"Authorize"**

---

## ✅ Step 3: Configure .env File

Edit `/Users/tara/Downloads/mmorpg_bot/.env`:

```env
# Required
DISCORD_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://postgres:yourpassword@db.xxx.supabase.co:5432/postgres

# Optional (can leave blank)
LOG_LEVEL=INFO
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=
```

**For local PostgreSQL:**
```env
DATABASE_URL=postgresql://mmorpg_user:yourpassword@localhost:5432/mmorpg
```

---

## ✅ Step 4: Run the Bot

```bash
cd /Users/tara/Downloads/mmorpg_bot
source .venv/bin/activate
python main.py
```

You should see:
```
INFO bot: Connecting to database...
INFO database: Database pool ready (min=5, max=20).
INFO database: Schema initialized.
INFO bot: ✓ Database ready
INFO bot: Loading cogs...
INFO bot: ✓ Commands synced
INFO bot: ✓ Online as YourBotName#1234
```

---

## ✅ Step 5: Test in Discord

In your Discord server, try:
- `/help` - See all commands
- `/character create` - Create your first character
- `/explore` - Start adventuring
- `/fight` - Enter combat!

---

## 🔧 Troubleshooting

**"DISCORD_TOKEN is not set"**
→ Edit `.env` and add your token

**"database does not exist"**
→ Make sure you created the database (Step 1)

**"Commands don't work"**
→ Wait 1-2 minutes for Discord to sync, or re-invite the bot

**"Connection refused" (local PostgreSQL)**
→ Run: `brew services start postgresql@16`
