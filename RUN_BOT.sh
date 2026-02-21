#!/bin/bash
# Script to run the MMORPG bot

cd /Users/tara/Downloads/mmorpg_bot
source .venv/bin/activate
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

echo "🚀 Starting World of Discord bot..."
echo ""
python main.py
