# 🔑 Getting Your Discord Bot Token

## Step-by-Step:

1. **Click "New Application"** (top right button)
2. **Name it**: `World of Discord` → Click **"Create"**
3. **Click "Bot"** in the left sidebar
4. **Click "Add Bot"** → Click **"Yes, do it!"**
5. **Click "Reset Token"** → Click **"Yes, do it!"** → **Copy the token** (save it somewhere safe!)
6. **Scroll down** to **"Privileged Gateway Intents"** and enable:
   - ✅ **Presence Intent**
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
7. **Click "OAuth2"** in the left sidebar → **"URL Generator"**
8. Under **"Scopes"**, check:
   - ✅ **bot**
   - ✅ **applications.commands**
9. Under **"Bot Permissions"**, check **"Administrator"** (or manually select: Send Messages, Embed Links, Use Slash Commands)
10. **Copy the generated URL** at the bottom
11. **Open that URL** in your browser → Select your test server → Click **"Authorize"**

---

## ✅ Once you have the token:

Paste it here and I'll add it to your `.env` file automatically!

Or you can manually edit `/Users/tara/Downloads/mmorpg_bot/.env` and add:
```
DISCORD_TOKEN=your_token_here
```
