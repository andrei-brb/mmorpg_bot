"""Regression tests for the idle gold rate cap (anti-inflation)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.settings import Settings
from services.activity_idle_rewards import compute_idle_pending


def _char(level: int, hours_ago: float) -> dict:
    return {
        "level": level,
        "idle_last_claim_at": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    }


def test_idle_gold_rate_is_capped_at_high_level():
    """A max-level character offline for the full window earns at most CAP × hours gold."""
    pending = compute_idle_pending(_char(level=60, hours_ago=24))
    max_gold = int(Settings.IDLE_GOLD_PER_HOUR_CAP * Settings.IDLE_REWARDS_MAX_HOURS)
    assert pending.pending_gold <= max_gold


def test_idle_gold_uncapped_below_threshold():
    """Low-level characters below the cap are unaffected by it."""
    level = 5
    rate = Settings.IDLE_GOLD_PER_HOUR_BASE + Settings.IDLE_GOLD_PER_HOUR_PER_LEVEL * level
    assert rate <= Settings.IDLE_GOLD_PER_HOUR_CAP, "test premise: L5 rate under cap"
    pending = compute_idle_pending(_char(level=level, hours_ago=10))
    assert pending.pending_gold == int(10 * rate)


def test_idle_xp_not_affected_by_gold_cap():
    """The cap applies to gold only; XP keeps scaling with level."""
    pending = compute_idle_pending(_char(level=60, hours_ago=24))
    xp_rate = Settings.IDLE_XP_PER_HOUR_BASE + Settings.IDLE_XP_PER_HOUR_PER_LEVEL * 60
    assert pending.pending_xp == int(24 * xp_rate)


def test_idle_accrual_window_capped():
    """Elapsed time beyond IDLE_REWARDS_MAX_HOURS does not increase rewards."""
    a = compute_idle_pending(_char(level=30, hours_ago=Settings.IDLE_REWARDS_MAX_HOURS))
    b = compute_idle_pending(_char(level=30, hours_ago=Settings.IDLE_REWARDS_MAX_HOURS * 3))
    assert b.pending_gold == a.pending_gold
    assert b.pending_xp == a.pending_xp
