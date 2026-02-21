#!/bin/bash
# Start the bot and keep it running

cd /Users/tara/Downloads/mmorpg_bot
source .venv/bin/activate
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

echo "🚀 Starting World of Discord bot..."
echo "Press Ctrl+C to stop"
echo ""

python main.py
