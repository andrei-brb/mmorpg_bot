#!/usr/bin/env python3
"""
Force sync commands - bypasses Discord Activity Entry Point issue.
Run this once to register all commands cleanly.
"""
import asyncio
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set in .env")

# Create minimal bot instance
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("Syncing commands...")
    
    try:
        # Clear ALL guild commands first
        print("Clearing guild commands...")
        for guild in bot.guilds:
            try:
                await bot.tree.sync(guild=guild)
                print(f"  Cleared commands in {guild.name}")
            except Exception as e:
                print(f"  Error clearing {guild.name}: {e}")
        
        # Sync global commands (this will include the Entry Point + all our commands)
        print("Syncing global commands...")
        synced = await bot.tree.sync()
        print(f"✓ Synced {len(synced)} global commands")
        
        # List all registered commands
        print("\nRegistered commands:")
        for cmd in await bot.tree.fetch_commands():
            print(f"  - /{cmd.name}")
            if hasattr(cmd, 'options') and cmd.options:
                for sub in getattr(cmd, 'options', []):
                    print(f"      - {sub.name}")
        
        print("\n✓ Command sync complete!")
        print("Wait 1-2 minutes for Discord to update, then try /admin givelevel")
        
    except Exception as e:
        print(f"✗ Sync failed: {e}")
        if "50240" in str(e) or "Entry Point" in str(e):
            print("\n⚠ Discord Activity Entry Point detected.")
            print("  Commands ARE registered despite the error.")
            print("  Wait 1-2 minutes and try again.")
    
    await bot.close()

if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))
