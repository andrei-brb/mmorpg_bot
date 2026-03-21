"""
Icon helper utility for loading PNG icons or falling back to emojis.
"""
import os
from pathlib import Path
from typing import Optional, Tuple, Any

# Base path for item icons
ICONS_DIR = Path(__file__).parent.parent / "assets" / "items"


def get_icon_path(item_id: str) -> Optional[Path]:
    """
    Get the file path for an item's PNG icon if it exists.
    
    Args:
        item_id: The item template ID (e.g., 'health_potion', 'iron_sword')
    
    Returns:
        Path to PNG file if exists, None otherwise
    """
    icon_path = ICONS_DIR / f"{item_id}.png"
    if icon_path.exists():
        return icon_path
    return None


def get_icon_file(item_id: str):
    """
    Get a Discord File object for an item's PNG icon if it exists.
    
    Args:
        item_id: The item template ID
    
    Returns:
        discord.File if PNG exists, None otherwise
    """
    try:
        import discord
    except ImportError:
        return None
    
    icon_path = get_icon_path(item_id)
    if icon_path:
        return discord.File(icon_path, filename=f"{item_id}.png")
    return None


def get_icon_emoji_or_file(item_id: str, fallback_emoji: str = "📦"):
    """
    Get both emoji (for buttons) and file (for embeds) for an item.
    
    Args:
        item_id: The item template ID
        fallback_emoji: Emoji to use if PNG doesn't exist
    
    Returns:
        Tuple of (emoji_string, discord_file)
        - emoji_string: Emoji to use in buttons/text (or None if using PNG)
        - discord_file: File object for embed thumbnail (or None if using emoji)
    """
    try:
        import discord
    except ImportError:
        return fallback_emoji, None
    
    icon_path = get_icon_path(item_id)
    if icon_path:
        file = discord.File(icon_path, filename=f"{item_id}.png")
        return None, file  # Use file, no emoji needed
    else:
        return fallback_emoji, None  # Use emoji fallback


def has_png_icon(item_id: str) -> bool:
    """Check if a PNG icon exists for an item."""
    return get_icon_path(item_id) is not None
