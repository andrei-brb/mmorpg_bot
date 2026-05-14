from __future__ import annotations

from typing import Any, Mapping, Optional


def rank_str(rank: Any) -> str:
    if rank is None:
        return ""
    return str(rank).lower()


def can_officer_actions(rank: Optional[str]) -> bool:
    return rank_str(rank) in ("officer", "guildmaster")


def can_guildmaster_only(rank: Optional[str]) -> bool:
    return rank_str(rank) == "guildmaster"


def assert_in_guild(char: Mapping[str, Any]) -> Optional[Any]:
    return char.get("guild_id")
