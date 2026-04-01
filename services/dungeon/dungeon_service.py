"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          services/dungeon/dungeon_service.py — Dungeon Logic                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

log = logging.getLogger("dungeon")


class DungeonService:
    def __init__(self, db):
        self.db = db

    async def create_run(
        self,
        dungeon_key: str,
        leader_id: UUID,
        difficulty: int = 1,
        is_solo: bool = True,
    ) -> Optional[UUID]:
        """Create a new dungeon run."""
        from config.settings import DUNGEONS, Settings
        
        dungeon = DUNGEONS.get(dungeon_key)
        if not dungeon:
            return None
        
        run_id = await self.db.fetchval(
            """
            INSERT INTO dungeon_runs (dungeon_key, difficulty, is_active, total_floors, timer_seconds)
            VALUES ($1, $2, TRUE, $3, $4)
            RETURNING id
            """,
            dungeon_key,
            difficulty,
            dungeon.floors,
            Settings.DUNGEON_TIMER_SECONDS,
        )
        
        # Add leader as participant
        await self.db.execute(
            """
            INSERT INTO dungeon_participants (run_id, character_id, role)
            VALUES ($1, $2, 'leader')
            """,
            run_id,
            leader_id,
        )
        
        # Mark character as in dungeon
        await self.db.execute(
            "UPDATE characters SET in_dungeon=TRUE WHERE id=$1",
            leader_id,
        )
        
        return run_id

    async def add_participant(self, run_id: UUID, char_id: UUID, role: str = "member") -> bool:
        """Add a participant to a dungeon run."""
        from config.settings import Settings
        
        # Check if run exists and is active
        run = await self.db.fetchrow(
            "SELECT * FROM dungeon_runs WHERE id=$1 AND is_active=TRUE",
            run_id,
        )
        if not run:
            return False
        
        # Check party size
        count = await self.db.fetchval(
            "SELECT COUNT(*) FROM dungeon_participants WHERE run_id=$1",
            run_id,
        )
        if count >= Settings.MAX_PARTY_SIZE:
            return False
        
        # Check if already in party
        existing = await self.db.fetchrow(
            "SELECT * FROM dungeon_participants WHERE run_id=$1 AND character_id=$2",
            run_id,
            char_id,
        )
        if existing:
            return False

        # Safety: a character must not belong to two active runs at once.
        # (Invite-accept path also checks this, but service-level guard keeps it invariant.)
        other_active = await self.db.fetchrow(
            """
            SELECT dr.id
            FROM dungeon_runs dr
            JOIN dungeon_participants dp ON dr.id = dp.run_id
            WHERE dp.character_id = $1
              AND dr.is_active = TRUE
              AND dr.id <> $2
            LIMIT 1
            """,
            char_id,
            run_id,
        )
        if other_active:
            return False
        
        await self.db.execute(
            """
            INSERT INTO dungeon_participants (run_id, character_id, role)
            VALUES ($1, $2, $3)
            """,
            run_id,
            char_id,
            role,
        )
        
        # Mark character as in dungeon
        await self.db.execute(
            "UPDATE characters SET in_dungeon=TRUE WHERE id=$1",
            char_id,
        )
        
        return True

    async def get_run(self, run_id: UUID) -> Optional[Dict]:
        """Get dungeon run details."""
        run = await self.db.fetchrow(
            "SELECT * FROM dungeon_runs WHERE id=$1",
            run_id,
        )
        if not run:
            return None
        
        participants = await self.db.fetch(
            """
            SELECT c.id, c.name, c.level, c.class, c.player_id, dp.role
            FROM dungeon_participants dp
            JOIN characters c ON dp.character_id = c.id
            WHERE dp.run_id = $1
            """,
            run_id,
        )
        
        return {
            **dict(run),
            "participants": [dict(p) for p in participants],
        }

    async def get_active_run(self, char_id: UUID) -> Optional[Dict]:
        """Get active dungeon run for a character."""
        run = await self.db.fetchrow(
            """
            SELECT dr.*
            FROM dungeon_runs dr
            JOIN dungeon_participants dp ON dr.id = dp.run_id
            LEFT JOIN (
                SELECT run_id, COUNT(*)::int AS participant_count
                FROM dungeon_participants
                GROUP BY run_id
            ) pc ON pc.run_id = dr.id
            WHERE dp.character_id = $1 AND dr.is_active = TRUE
            ORDER BY COALESCE(pc.participant_count, 0) DESC, dr.started_at DESC
            LIMIT 1
            """,
            char_id,
        )
        if not run:
            return None
        
        return await self.get_run(run["id"])

    async def advance_floor(self, run_id: UUID) -> bool:
        """Advance to next floor."""
        run = await self.db.fetchrow(
            "SELECT * FROM dungeon_runs WHERE id=$1 AND is_active=TRUE",
            run_id,
        )
        if not run:
            return False
        
        new_floor = run["current_floor"] + 1
        if new_floor > run["total_floors"]:
            return False
        
        await self.db.execute(
            "UPDATE dungeon_runs SET current_floor=$1 WHERE id=$2",
            new_floor,
            run_id,
        )
        
        return True

    async def complete_run(self, run_id: UUID, outcome: str = "victory"):
        """Mark dungeon run as completed."""
        await self.db.execute(
            """
            UPDATE dungeon_runs 
            SET is_active=FALSE, outcome=$1, completed_at=NOW()
            WHERE id=$2
            """,
            outcome,
            run_id,
        )
        
        # Mark all participants as not in dungeon (single query instead of loop)
        await self.db.execute(
            """
            UPDATE characters SET in_dungeon=FALSE
            WHERE id IN (SELECT character_id FROM dungeon_participants WHERE run_id=$1)
            """,
            run_id,
        )

    async def leave_run(self, char_id: UUID):
        """Remove character from dungeon run."""
        await self.db.execute(
            """
            DELETE FROM dungeon_participants
            WHERE character_id=$1
            """,
            char_id,
        )
        
        await self.db.execute(
            "UPDATE characters SET in_dungeon=FALSE WHERE id=$1",
            char_id,
        )
        
        # Check if run is empty, mark as abandoned
        runs = await self.db.fetch(
            """
            SELECT dr.id FROM dungeon_runs dr
            LEFT JOIN dungeon_participants dp ON dr.id = dp.run_id
            WHERE dr.is_active=TRUE AND dp.run_id IS NULL
            """
        )
        for run in runs:
            await self.db.execute(
                "UPDATE dungeon_runs SET is_active=FALSE, outcome='abandoned' WHERE id=$1",
                run["id"],
            )
