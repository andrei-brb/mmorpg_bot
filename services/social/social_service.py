"""In-game friends, ignore lists, whispers, and presence."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from config.settings import ZONES

log = logging.getLogger(__name__)

ONLINE_THRESHOLD = timedelta(minutes=3)
WHISPER_MAX_LEN = 500
WHISPER_RATE_LIMIT = 10
WHISPER_RATE_WINDOW = timedelta(minutes=1)
WHISPER_RETENTION = timedelta(days=7)


def _canonical_pair(a: int, b: int) -> tuple[int, int]:
    return (min(a, b), max(a, b))


def _zone_display(zone_key: str | None) -> str | None:
    if not zone_key:
        return None
    z = ZONES.get(zone_key)
    if z:
        return z.name
    return zone_key.replace("_", " ").title()


class SocialService:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def touch_presence(self, player_id: int) -> None:
        await self.db.execute(
            "UPDATE players SET last_seen = NOW() WHERE id = $1",
            int(player_id),
        )

    async def resolve_player_id(self, *, username: str | None = None, user_id: int | None = None) -> int | None:
        if user_id is not None:
            row = await self.db.fetchrow("SELECT id FROM players WHERE id = $1", int(user_id))
            return int(row["id"]) if row else None
        if username:
            un = username.strip()
            if un.startswith("@"):
                un = un[1:].strip()
            if not un:
                return None
            row = await self.db.fetchrow(
                "SELECT id FROM players WHERE LOWER(username) = LOWER($1) LIMIT 1",
                un[:100],
            )
            return int(row["id"]) if row else None
        return None

    async def is_ignored(self, a: int, b: int) -> bool:
        row = await self.db.fetchrow(
            """
            SELECT 1 FROM player_ignores
            WHERE (blocker_id = $1 AND blocked_id = $2)
               OR (blocker_id = $2 AND blocked_id = $1)
            LIMIT 1
            """,
            int(a),
            int(b),
        )
        return row is not None

    async def is_friend(self, a: int, b: int) -> bool:
        pa, pb = _canonical_pair(int(a), int(b))
        row = await self.db.fetchrow(
            "SELECT 1 FROM player_friendships WHERE player_a_id = $1 AND player_b_id = $2",
            pa,
            pb,
        )
        return row is not None

    async def search_players(
        self, viewer_id: int, q: str, *, limit: int = 12, purpose: str = "friend"
    ) -> list[dict]:
        q = (q or "").strip()
        if q.startswith("@"):
            q = q[1:].strip()
        if not q:
            return []
        q = q[:32]
        extra_filters = ""
        if purpose == "friend":
            extra_filters = """
              AND NOT EXISTS (
                  SELECT 1 FROM player_ignores ig
                  WHERE (ig.blocker_id = $1 AND ig.blocked_id = p.id)
                     OR (ig.blocker_id = p.id AND ig.blocked_id = $1)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM player_friendships f
                  WHERE (f.player_a_id = LEAST($1::bigint, p.id) AND f.player_b_id = GREATEST($1::bigint, p.id))
              )
              AND NOT EXISTS (
                  SELECT 1 FROM player_friend_requests fr
                  WHERE fr.status = 'pending'
                    AND (
                      (fr.from_player_id = $1 AND fr.to_player_id = p.id)
                      OR (fr.from_player_id = p.id AND fr.to_player_id = $1)
                    )
              )
            """
        elif purpose == "ignore":
            extra_filters = """
              AND NOT EXISTS (
                  SELECT 1 FROM player_ignores ig
                  WHERE ig.blocker_id = $1 AND ig.blocked_id = p.id
              )
            """
        rows = await self.db.fetch(
            f"""
            SELECT p.id, p.username, c.level, c.class, c.name AS character_name
            FROM players p
            JOIN characters c ON c.player_id = p.id AND c.is_active = TRUE
            WHERE p.id != $1
              AND p.username IS NOT NULL
              AND p.username ILIKE $2
              {extra_filters}
            ORDER BY p.username ASC
            LIMIT $3
            """,
            int(viewer_id),
            q + "%",
            limit,
        )
        return [
            {
                "id": str(r["id"]),
                "username": str(r["username"]),
                "level": int(r["level"] or 1),
                "class": str(r["class"] or ""),
                "character_name": str(r["character_name"] or ""),
            }
            for r in rows
        ]

    def _presence_from_row(self, row: dict) -> dict:
        last_seen = row.get("last_seen")
        now = datetime.now(timezone.utc)
        online = False
        last_seen_iso = None
        if last_seen:
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            last_seen_iso = last_seen.isoformat()
            online = (now - last_seen) <= ONLINE_THRESHOLD

        zone_hint = None
        combat_status = str(row.get("combat_status") or "idle")
        if row.get("in_dungeon"):
            zone_hint = "In dungeon"
        elif combat_status == "in_combat":
            zone_hint = "In combat"
        else:
            zone_hint = _zone_display(row.get("current_zone"))

        return {
            "online": online,
            "last_seen": last_seen_iso,
            "zone_hint": zone_hint,
        }

    async def get_roster(self, viewer_id: int) -> list[dict]:
        rows = await self.db.fetch(
            """
            SELECT
                CASE WHEN f.player_a_id = $1 THEN f.player_b_id ELSE f.player_a_id END AS friend_id,
                p.username,
                p.last_seen,
                c.level,
                c.class,
                c.name AS character_name,
                c.current_zone,
                c.combat_status,
                c.in_dungeon
            FROM player_friendships f
            JOIN players p ON p.id = CASE WHEN f.player_a_id = $1 THEN f.player_b_id ELSE f.player_a_id END
            LEFT JOIN characters c ON c.player_id = p.id AND c.is_active = TRUE
            WHERE f.player_a_id = $1 OR f.player_b_id = $1
            ORDER BY p.username ASC
            """,
            int(viewer_id),
        )
        out = []
        for r in rows:
            pres = self._presence_from_row(dict(r))
            out.append(
                {
                    "user_id": str(r["friend_id"]),
                    "username": str(r["username"] or ""),
                    "character_name": str(r["character_name"] or "") or None,
                    "level": int(r["level"]) if r["level"] is not None else None,
                    "class": str(r["class"]) if r["class"] else None,
                    **pres,
                }
            )
        return out

    async def get_requests(self, viewer_id: int) -> dict:
        incoming_rows = await self.db.fetch(
            """
            SELECT fr.id, fr.from_player_id, fr.created_at, p.username,
                   c.level, c.class, c.name AS character_name
            FROM player_friend_requests fr
            JOIN players p ON p.id = fr.from_player_id
            LEFT JOIN characters c ON c.player_id = p.id AND c.is_active = TRUE
            WHERE fr.to_player_id = $1 AND fr.status = 'pending'
            ORDER BY fr.created_at DESC
            """,
            int(viewer_id),
        )
        outgoing_rows = await self.db.fetch(
            """
            SELECT fr.id, fr.to_player_id, fr.created_at, p.username,
                   c.level, c.class, c.name AS character_name
            FROM player_friend_requests fr
            JOIN players p ON p.id = fr.to_player_id
            LEFT JOIN characters c ON c.player_id = p.id AND c.is_active = TRUE
            WHERE fr.from_player_id = $1 AND fr.status = 'pending'
            ORDER BY fr.created_at DESC
            """,
            int(viewer_id),
        )

        def _req_row(r: Any, *, other_key: str) -> dict:
            return {
                "request_id": str(r["id"]),
                "user_id": str(r[other_key]),
                "username": str(r["username"] or ""),
                "character_name": str(r["character_name"] or "") or None,
                "level": int(r["level"]) if r["level"] is not None else None,
                "class": str(r["class"]) if r["class"] else None,
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            }

        return {
            "incoming": [_req_row(r, other_key="from_player_id") for r in incoming_rows],
            "outgoing": [_req_row(r, other_key="to_player_id") for r in outgoing_rows],
        }

    async def send_friend_request(
        self, from_id: int, *, username: str | None = None, target_user_id: int | None = None
    ) -> tuple[bool, str, dict | None]:
        to_id = target_user_id
        if to_id is None and username:
            to_id = await self.resolve_player_id(username=username)
        if to_id is None:
            return False, "Player not found.", None
        to_id = int(to_id)
        from_id = int(from_id)
        if from_id == to_id:
            return False, "You cannot add yourself.", None

        if await self.is_ignored(from_id, to_id):
            return False, "Unable to send friend request.", None

        if await self.is_friend(from_id, to_id):
            return False, "Already friends.", None

        existing = await self.db.fetchrow(
            """
            SELECT id, status FROM player_friend_requests
            WHERE from_player_id = $1 AND to_player_id = $2 AND status = 'pending'
            """,
            from_id,
            to_id,
        )
        if existing:
            return False, "Friend request already pending.", None

        reverse = await self.db.fetchrow(
            """
            SELECT id FROM player_friend_requests
            WHERE from_player_id = $1 AND to_player_id = $2 AND status = 'pending'
            """,
            to_id,
            from_id,
        )
        if reverse:
            return False, "They already sent you a request — check your inbox.", None

        row = await self.db.fetchrow(
            """
            INSERT INTO player_friend_requests (from_player_id, to_player_id, status)
            VALUES ($1, $2, 'pending')
            RETURNING id, created_at
            """,
            from_id,
            to_id,
        )
        return True, "Friend request sent.", {
            "request_id": str(row["id"]),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }

    async def accept_friend_request(self, viewer_id: int, request_id: str) -> tuple[bool, str]:
        req = await self.db.fetchrow(
            """
            SELECT id, from_player_id, to_player_id, status
            FROM player_friend_requests WHERE id = $1
            """,
            request_id,
        )
        if not req:
            return False, "Request not found."
        if int(req["to_player_id"]) != int(viewer_id):
            return False, "Not your request."
        if req["status"] != "pending":
            return False, "Request is no longer pending."

        from_id = int(req["from_player_id"])
        to_id = int(req["to_player_id"])
        pa, pb = _canonical_pair(from_id, to_id)

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM player_friend_requests WHERE id = $1",
                    request_id,
                )
                await conn.execute(
                    """
                    INSERT INTO player_friendships (player_a_id, player_b_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    pa,
                    pb,
                )
        return True, "Friend added."

    async def decline_friend_request(self, viewer_id: int, request_id: str) -> tuple[bool, str]:
        req = await self.db.fetchrow(
            "SELECT to_player_id, status FROM player_friend_requests WHERE id = $1",
            request_id,
        )
        if not req:
            return False, "Request not found."
        if int(req["to_player_id"]) != int(viewer_id):
            return False, "Not your request."
        if req["status"] != "pending":
            return False, "Request is no longer pending."
        await self.db.execute(
            """
            UPDATE player_friend_requests
            SET status = 'declined', responded_at = NOW()
            WHERE id = $1
            """,
            request_id,
        )
        return True, "Request declined."

    async def unfriend(self, viewer_id: int, friend_user_id: int) -> tuple[bool, str]:
        pa, pb = _canonical_pair(int(viewer_id), int(friend_user_id))
        result = await self.db.execute(
            "DELETE FROM player_friendships WHERE player_a_id = $1 AND player_b_id = $2",
            pa,
            pb,
        )
        if result == "DELETE 0":
            return False, "Not friends."
        return True, "Removed from friends."

    async def list_ignores(self, viewer_id: int) -> list[dict]:
        rows = await self.db.fetch(
            """
            SELECT pi.blocked_id, p.username, pi.created_at
            FROM player_ignores pi
            JOIN players p ON p.id = pi.blocked_id
            WHERE pi.blocker_id = $1
            ORDER BY pi.created_at DESC
            """,
            int(viewer_id),
        )
        return [
            {
                "user_id": str(r["blocked_id"]),
                "username": str(r["username"] or ""),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            }
            for r in rows
        ]

    async def add_ignore(
        self, blocker_id: int, *, username: str | None = None, blocked_user_id: int | None = None
    ) -> tuple[bool, str]:
        bid = blocked_user_id
        if bid is None and username:
            bid = await self.resolve_player_id(username=username)
        if bid is None:
            return False, "Player not found."
        bid = int(bid)
        blocker_id = int(blocker_id)
        if blocker_id == bid:
            return False, "You cannot ignore yourself."
        await self.db.execute(
            """
            INSERT INTO player_ignores (blocker_id, blocked_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            blocker_id,
            bid,
        )
        pa, pb = _canonical_pair(blocker_id, bid)
        await self.db.execute(
            "DELETE FROM player_friendships WHERE player_a_id = $1 AND player_b_id = $2",
            pa,
            pb,
        )
        await self.db.execute(
            """
            UPDATE player_friend_requests
            SET status = 'declined', responded_at = NOW()
            WHERE status = 'pending'
              AND (
                (from_player_id = $1 AND to_player_id = $2)
                OR (from_player_id = $2 AND to_player_id = $1)
              )
            """,
            blocker_id,
            bid,
        )
        return True, "Player ignored."

    async def remove_ignore(self, blocker_id: int, blocked_user_id: int) -> tuple[bool, str]:
        result = await self.db.execute(
            "DELETE FROM player_ignores WHERE blocker_id = $1 AND blocked_id = $2",
            int(blocker_id),
            int(blocked_user_id),
        )
        if result == "DELETE 0":
            return False, "Not on ignore list."
        return True, "Removed from ignore list."

    async def _whisper_rate_ok(self, sender_id: int) -> bool:
        since = datetime.now(timezone.utc) - WHISPER_RATE_WINDOW
        row = await self.db.fetchrow(
            """
            SELECT COUNT(*)::int AS n FROM player_whispers
            WHERE from_player_id = $1 AND created_at >= $2
            """,
            int(sender_id),
            since,
        )
        return int(row["n"] or 0) < WHISPER_RATE_LIMIT

    async def send_whisper(self, from_id: int, to_id: int, body: str) -> tuple[bool, str, dict | None]:
        from_id = int(from_id)
        to_id = int(to_id)
        body = (body or "").strip()
        if not body:
            return False, "Message cannot be empty.", None
        if len(body) > WHISPER_MAX_LEN:
            return False, f"Message too long (max {WHISPER_MAX_LEN} characters).", None
        if not await self.is_friend(from_id, to_id):
            return False, "You can only whisper friends.", None
        if not await self._whisper_rate_ok(from_id):
            return False, "Whisper rate limit reached. Try again shortly.", None

        row = await self.db.fetchrow(
            """
            INSERT INTO player_whispers (from_player_id, to_player_id, body)
            VALUES ($1, $2, $3)
            RETURNING id, created_at
            """,
            from_id,
            to_id,
            body,
        )
        cutoff = datetime.now(timezone.utc) - WHISPER_RETENTION
        await self.db.execute(
            "DELETE FROM player_whispers WHERE created_at < $1",
            cutoff,
        )
        return True, "Sent.", {
            "id": str(row["id"]),
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        }

    async def get_whispers(self, viewer_id: int, with_user_id: int, *, limit: int = 50) -> list[dict]:
        viewer_id = int(viewer_id)
        with_user_id = int(with_user_id)
        if not await self.is_friend(viewer_id, with_user_id):
            return []

        rows = await self.db.fetch(
            """
            SELECT id, from_player_id, to_player_id, body, created_at
            FROM player_whispers
            WHERE (from_player_id = $1 AND to_player_id = $2)
               OR (from_player_id = $2 AND to_player_id = $1)
            ORDER BY created_at ASC
            LIMIT $3
            """,
            viewer_id,
            with_user_id,
            limit,
        )

        await self.db.execute(
            """
            UPDATE player_whispers SET read_at = NOW()
            WHERE to_player_id = $1 AND from_player_id = $2 AND read_at IS NULL
            """,
            viewer_id,
            with_user_id,
        )

        return [
            {
                "id": str(r["id"]),
                "from_user_id": str(r["from_player_id"]),
                "to_user_id": str(r["to_player_id"]),
                "body": str(r["body"]),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                "mine": int(r["from_player_id"]) == viewer_id,
            }
            for r in rows
        ]
