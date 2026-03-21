"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        services/achievement/achievement_service.py — Achievement Logic      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

log = logging.getLogger("achievement")


def _parse_criteria(raw) -> dict:
    """Safely parse criteria from DB — may be dict (JSONB), str, or None."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


class AchievementService:
    def __init__(self, db):
        self.db = db

    async def get_achievement(self, achievement_id: str) -> Optional[Dict]:
        """Get achievement template by ID."""
        return await self.db.fetchrow(
            "SELECT * FROM achievement_templates WHERE id=$1", achievement_id
        )

    async def get_all_achievements(self, category: Optional[str] = None) -> List[Dict]:
        """Get all achievement templates, optionally filtered by category."""
        if category:
            return await self.db.fetch(
                "SELECT * FROM achievement_templates WHERE category=$1 ORDER BY points DESC, name",
                category
            )
        return await self.db.fetch(
            "SELECT * FROM achievement_templates ORDER BY category, points DESC, name"
        )

    async def get_character_achievements(self, character_id: UUID) -> List[Dict]:
        """Get all achievements earned by a character."""
        return await self.db.fetch(
            """
            SELECT at.*, ca.earned_at
            FROM character_achievements ca
            JOIN achievement_templates at ON ca.achievement_id = at.id
            WHERE ca.character_id = $1
            ORDER BY ca.earned_at DESC
            """,
            character_id
        )

    async def has_achievement(self, character_id: UUID, achievement_id: str) -> bool:
        """Check if character has earned an achievement."""
        count = await self.db.fetchval(
            "SELECT COUNT(*) FROM character_achievements WHERE character_id=$1 AND achievement_id=$2",
            character_id, achievement_id
        )
        return count > 0

    async def award_achievement(self, character_id: UUID, achievement_id: str) -> bool:
        """Award an achievement to a character. Returns True if newly earned, False if already had it."""
        if await self.has_achievement(character_id, achievement_id):
            return False
        
        try:
            await self.db.execute(
                """
                INSERT INTO character_achievements (character_id, achievement_id, earned_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT DO NOTHING
                """,
                character_id, achievement_id
            )
            return True
        except Exception as e:
            log.error(f"Failed to award achievement {achievement_id} to {character_id}: {e}")
            return False

    async def get_achievement_progress(self, character_id: UUID, achievement_id: str) -> Optional[Dict]:
        """Get progress towards an achievement. Returns None if achievement doesn't exist or is already earned."""
        if await self.has_achievement(character_id, achievement_id):
            return None
        
        achievement = await self.get_achievement(achievement_id)
        if not achievement:
            return None
        
        criteria = _parse_criteria(achievement["criteria"])
        progress = {}
        
        # Calculate progress based on criteria type
        crit_type = criteria.get("type")
        
        if crit_type == "kill_count":
            target = criteria.get("target", 0)
            current = await self.db.fetchval(
                """
                SELECT COUNT(*) FROM combat_sessions cs
                JOIN combat_participants cp ON cs.id = cp.session_id
                WHERE cp.character_id = $1 AND cs.outcome = 'victory' AND cp.is_player = TRUE
                """,
                character_id
            ) or 0
            progress = {"current": current, "target": target, "percent": int((current / target * 100) if target > 0 else 0)}
        
        elif crit_type == "boss_kill_count":
            target = criteria.get("target", 0)
            current = await self.db.fetchval(
                """
                SELECT COUNT(*) FROM combat_sessions cs
                JOIN combat_participants cp ON cs.id = cp.session_id
                WHERE cp.character_id = $1 AND cs.outcome = 'victory' AND cs.is_boss = TRUE AND cp.is_player = TRUE
                """,
                character_id
            ) or 0
            progress = {"current": current, "target": target, "percent": int((current / target * 100) if target > 0 else 0)}
        
        elif crit_type == "level":
            target = criteria.get("target", 0)
            char = await self.db.fetchrow("SELECT level FROM characters WHERE id=$1", character_id)
            current = char["level"] if char else 0
            progress = {"current": current, "target": target, "percent": int((current / target * 100) if target > 0 else 0)}
        
        elif crit_type == "gold_earned":
            target = criteria.get("target", 0)
            total = await self.db.fetchval(
                "SELECT COALESCE(SUM(amount), 0) FROM gold_log WHERE character_id=$1 AND amount > 0",
                character_id
            ) or 0
            progress = {"current": total, "target": target, "percent": int((total / target * 100) if target > 0 else 0)}
        
        elif crit_type == "explore_count":
            target = criteria.get("target", 0)
            current = await self.db.fetchval(
                "SELECT COUNT(*) FROM characters WHERE id=$1 AND last_explore IS NOT NULL",
                character_id
            ) or 0
            # This is approximate - we'd need a better tracking system
            progress = {"current": min(current, target), "target": target, "percent": int((min(current, target) / target * 100) if target > 0 else 0)}
        
        elif crit_type == "dungeon_complete":
            target = criteria.get("target", 0)
            current = await self.db.fetchval(
                """
                SELECT COUNT(*) FROM dungeon_runs dr
                JOIN dungeon_participants dp ON dr.id = dp.run_id
                WHERE dp.character_id = $1 AND dr.outcome = 'victory'
                """,
                character_id
            ) or 0
            progress = {"current": current, "target": target, "percent": int((current / target * 100) if target > 0 else 0)}
        
        elif crit_type == "item_collect":
            target = criteria.get("target", 0)
            current = await self.db.fetchval(
                "SELECT COUNT(DISTINCT template_id) FROM inventory WHERE character_id=$1",
                character_id
            ) or 0
            progress = {"current": current, "target": target, "percent": int((current / target * 100) if target > 0 else 0)}
        
        elif crit_type == "zone_visit":
            zones = criteria.get("zones", [])
            visited = await self.db.fetch(
                "SELECT DISTINCT current_zone FROM characters WHERE id=$1",
                character_id
            )
            visited_zones = [r["current_zone"] for r in visited] if visited else []
            current = len([z for z in zones if z in visited_zones])
            progress = {"current": current, "target": len(zones), "percent": int((current / len(zones) * 100) if zones else 0)}
        
        return progress

    async def check_and_award(self, character_id: UUID, event_type: str, event_data: Dict) -> List[str]:
        """Check achievements based on an event and award any that are completed.
        
        Returns list of newly earned achievement IDs.
        """
        # Get all achievements that might be triggered by this event
        achievements = await self.get_all_achievements()
        newly_earned = []
        
        for ach in achievements:
            if await self.has_achievement(character_id, ach["id"]):
                continue
            
            criteria = _parse_criteria(ach["criteria"])
            if criteria.get("trigger") != event_type:
                continue
            
            # Check if achievement is completed
            should_award = False
            
            if event_type == "level_up":
                target_level = criteria.get("target", 0)
                if event_data.get("level", 0) >= target_level:
                    should_award = True
            
            elif event_type == "kill":
                if criteria.get("type") == "kill_count":
                    # Check total kills
                    kills = await self.db.fetchval(
                        """
                        SELECT COUNT(*) FROM combat_sessions cs
                        JOIN combat_participants cp ON cs.id = cp.session_id
                        WHERE cp.character_id = $1 AND cs.outcome = 'victory' AND cp.is_player = TRUE
                        """,
                        character_id
                    ) or 0
                    if kills >= criteria.get("target", 0):
                        should_award = True
                elif criteria.get("type") == "boss_kill_count" and event_data.get("is_boss"):
                    kills = await self.db.fetchval(
                        """
                        SELECT COUNT(*) FROM combat_sessions cs
                        JOIN combat_participants cp ON cs.id = cp.session_id
                        WHERE cp.character_id = $1 AND cs.outcome = 'victory' AND cs.is_boss = TRUE AND cp.is_player = TRUE
                        """,
                        character_id
                    ) or 0
                    if kills >= criteria.get("target", 0):
                        should_award = True
            
            elif event_type == "gold_earned":
                total = await self.db.fetchval(
                    "SELECT COALESCE(SUM(amount), 0) FROM gold_log WHERE character_id=$1 AND amount > 0",
                    character_id
                ) or 0
                if total >= criteria.get("target", 0):
                    should_award = True
            
            elif event_type == "dungeon_complete":
                if criteria.get("type") == "dungeon_complete":
                    count = await self.db.fetchval(
                        """
                        SELECT COUNT(*) FROM dungeon_runs dr
                        JOIN dungeon_participants dp ON dr.id = dp.run_id
                        WHERE dp.character_id = $1 AND dr.outcome = 'victory'
                        """,
                        character_id
                    ) or 0
                    if count >= criteria.get("target", 0):
                        should_award = True
            
            elif event_type == "zone_visit":
                zones = criteria.get("zones", [])
                visited = await self.db.fetch(
                    "SELECT DISTINCT current_zone FROM characters WHERE id=$1",
                    character_id
                )
                visited_zones = [r["current_zone"] for r in visited] if visited else []
                if all(z in visited_zones for z in zones):
                    should_award = True
            
            elif event_type == "item_collect":
                count = await self.db.fetchval(
                    "SELECT COUNT(DISTINCT template_id) FROM inventory WHERE character_id=$1",
                    character_id
                ) or 0
                if count >= criteria.get("target", 0):
                    should_award = True
            
            if should_award:
                if await self.award_achievement(character_id, ach["id"]):
                    newly_earned.append(ach["id"])
                    log.info(f"Achievement earned: {ach['name']} by character {character_id}")
        
        return newly_earned

    async def get_total_points(self, character_id: UUID) -> int:
        """Get total achievement points for a character."""
        return await self.db.fetchval(
            """
            SELECT COALESCE(SUM(at.points), 0)
            FROM character_achievements ca
            JOIN achievement_templates at ON ca.achievement_id = at.id
            WHERE ca.character_id = $1
            """,
            character_id
        ) or 0
