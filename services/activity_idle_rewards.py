"""Server-side idle reward accrual for the Activity app (offline between claims)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from config.settings import Settings


@dataclass(frozen=True)
class IdlePending:
    elapsed_seconds: float
    effective_hours: float
    pending_xp: int
    pending_gold: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_dt(val: Any) -> datetime:
    if val is None:
        return _utc_now()
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    s = str(val).strip()
    if not s:
        return _utc_now()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return _utc_now()


def compute_idle_pending(char: Dict[str, Any]) -> IdlePending:
    level = max(1, int(char.get("level") or 1))
    last = _as_utc_dt(char.get("idle_last_claim_at"))
    now = _utc_now()
    elapsed = max(0.0, (now - last).total_seconds())
    max_s = max(0.0, float(Settings.IDLE_REWARDS_MAX_HOURS)) * 3600.0
    capped_s = min(float(elapsed), max_s) if max_s > 0 else 0.0
    effective_hours = capped_s / 3600.0
    xp_rate = float(Settings.IDLE_XP_PER_HOUR_BASE) + float(Settings.IDLE_XP_PER_HOUR_PER_LEVEL) * float(level)
    gold_rate = float(Settings.IDLE_GOLD_PER_HOUR_BASE) + float(Settings.IDLE_GOLD_PER_HOUR_PER_LEVEL) * float(level)
    pending_xp = int(effective_hours * xp_rate)
    pending_gold = int(effective_hours * gold_rate)
    return IdlePending(
        elapsed_seconds=float(elapsed),
        effective_hours=effective_hours,
        pending_xp=pending_xp,
        pending_gold=pending_gold,
    )


def idle_pending_to_json(p: IdlePending) -> Dict[str, Any]:
    return {
        "elapsed_seconds": round(p.elapsed_seconds, 3),
        "effective_hours": round(p.effective_hours, 4),
        "pending_xp": p.pending_xp,
        "pending_gold": p.pending_gold,
        "max_hours": float(Settings.IDLE_REWARDS_MAX_HOURS),
    }
