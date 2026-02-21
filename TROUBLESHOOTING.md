# 🔧 Troubleshooting: Bot Not Responding to Commands

## Current Issue:
Bot starts but stops after "Syncing application commands..." and doesn't respond to `/help`.

## Solution:

The bot needs to be run in a way that keeps it alive. Try this:

### Option 1: Run in Terminal (Recommended)
Open a terminal and run:
```bash
cd /Users/tara/Downloads/mmorpg_bot
source .venv/bin/activate
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
python main.py
```

Keep this terminal open! The bot needs to stay running.

### Option 2: Use screen or tmux
```bash
# Install screen if needed: brew install screen
screen -S mmorpg_bot
cd /Users/tara/Downloads/mmorpg_bot
source .venv/bin/activate
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
python main.py
# Press Ctrl+A then D to detach
# Reattach with: screen -r mmorpg_bot
```

### Option 3: Check if bot is actually running
```bash
ps aux | grep "python main.py"
```

If it's not running, start it again using Option 1.

---

## Why "Application did not respond"?
This error means:
1. Bot received the command but crashed before responding
2. Bot isn't running when you use the command
3. Bot is running but there's an error in the command handler

Make sure the bot is running and check the logs!
