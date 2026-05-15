"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        services/daily/daily_login_service.py — Daily Login Rewards         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from uuid import UUID

log = logging.getLogger("daily_login")


class DailyLoginService:
    def __init__(self, db):
        self.db = db

    async def get_streak(self, character_id: UUID) -> Dict:
        """Get current login streak information."""
        streak = await self.db.fetchrow(
            "SELECT * FROM login_streaks WHERE character_id=$1",
            character_id
        )
        if not streak:
            return {
                "character_id": character_id,
                "current_streak": 0,
                "longest_streak": 0,
                "last_login": None,
                "total_logins": 0,
            }
        return dict(streak)

    async def claim_daily_reward(self, character_id: UUID) -> Dict:
        """Claim daily login reward. Returns reward info and whether streak was maintained."""
        streak_data = await self.get_streak(character_id)
        now = datetime.utcnow()
        last_login = streak_data.get("last_login")
        
        # Check if already claimed today
        if last_login:
            last_login_dt = last_login if isinstance(last_login, datetime) else datetime.fromisoformat(str(last_login))
            if last_login_dt.date() == now.date():
                return {
                    "claimed": False,
                    "message": "You've already claimed your daily reward today!",
                    "next_claim": (last_login_dt + timedelta(days=1)).date(),
                }
        
        # Check if streak continues or resets
        current_streak = streak_data.get("current_streak", 0)
        longest_streak = streak_data.get("longest_streak", 0)
        total_logins = streak_data.get("total_logins", 0)
        
        streak_maintained = False
        if last_login:
            last_login_dt = last_login if isinstance(last_login, datetime) else datetime.fromisoformat(str(last_login))
            days_since = (now.date() - last_login_dt.date()).days
            
            if days_since == 1:
                # Streak continues
                current_streak += 1
                streak_maintained = True
            elif days_since > 1:
                # Streak broken, reset to 1
                current_streak = 1
            else:
                # Same day (shouldn't happen, but handle it)
                current_streak = max(1, current_streak)
        else:
            # First login
            current_streak = 1
        
        # Update longest streak
        if current_streak > longest_streak:
            longest_streak = current_streak
        
        # Calculate rewards based on streak
        base_gold = 50
        base_xp = 100
        streak_bonus = min(current_streak * 10, 200)  # Max 200 bonus at 20+ day streak
        
        gold_reward = base_gold + streak_bonus
        xp_reward = base_xp + (streak_bonus // 2)
        
        # Weekly milestone bonus (every 7 days)
        week_bonus = (current_streak // 7) * 50
        gold_reward += week_bonus
        xp_reward += week_bonus
        
        # Monthly milestone bonus (every 30 days)
        month_bonus = (current_streak // 30) * 500
        gold_reward += month_bonus
        xp_reward += month_bonus * 2
        
        # Update streak in database
        await self.db.execute(
            """
            INSERT INTO login_streaks (character_id, current_streak, longest_streak, last_login, total_logins)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (character_id) DO UPDATE SET
                current_streak = $2,
                longest_streak = $3,
                last_login = $4,
                total_logins = $5
            """,
            character_id, current_streak, longest_streak, now, total_logins + 1
        )
        
        return {
            "claimed": True,
            "streak_maintained": streak_maintained,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "gold": gold_reward,
            "xp": xp_reward,
            "next_claim": (now + timedelta(days=1)).date(),
        }

    async def apply_economy_rewards(self, char_svc, character_id: UUID, result: Dict) -> None:
        """Award gold and character XP from a successful claim_daily_reward result."""
        if not result.get("claimed"):
            return
        xp = int(result.get("xp") or 0)
        gold = int(result.get("gold") or 0)
        if xp > 0:
            await char_svc.award_xp(character_id, xp, 1.0)
        if gold > 0:
            await char_svc.add_gold(character_id, gold, "daily_login")
