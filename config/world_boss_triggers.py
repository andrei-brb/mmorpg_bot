"""
Declarative world boss window triggers (per Discord guild).

Evaluated periodically by the Events cog; openings are stored in `guild_world_boss_windows`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple, Union


@dataclass(frozen=True)
class MilestoneBossTrigger:
    kind: Literal["milestone"]
    slug: str
    milestone_key: str
    min_tier: int
    zone_key: str
    boss_key: str
    duration_hours: float
    cooldown_hours: float
    title: str


@dataclass(frozen=True)
class PresenceBossTrigger:
    kind: Literal["presence"]
    slug: str
    zone_key: str
    min_players: int
    boss_key: str
    duration_hours: float
    cooldown_hours: float
    title: str


WorldBossTrigger = Union[MilestoneBossTrigger, PresenceBossTrigger]

# MVP examples (see docs/LORE_IMPLEMENTATION.md):
# - Milestone: first boss_kills tier reached → Ghost Admiral window in Stranglethorn.
# - Presence: enough guild-scoped characters in The Barrens → Glass Titan window.
WORLD_BOSS_TRIGGERS: Tuple[WorldBossTrigger, ...] = (
    MilestoneBossTrigger(
        kind="milestone",
        slug="ghost_admiral_milestone",
        milestone_key="boss_kills",
        min_tier=1,
        zone_key="stranglethorn",
        boss_key="ghost_admiral",
        duration_hours=2.0,
        cooldown_hours=48.0,
        title="Ghost Admiral sighted",
    ),
    PresenceBossTrigger(
        kind="presence",
        slug="glass_titan_presence",
        zone_key="barrens",
        min_players=5,
        boss_key="glass_titan",
        duration_hours=1.0,
        cooldown_hours=12.0,
        title="Glass Titan stirs in the Barrens",
    ),
)
