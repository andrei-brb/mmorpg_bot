"""In-game friends, ignore lists, whispers, and presence."""

from __future__ import annotations

import json
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


def _ignore_filter_sql(viewer_param: str = "$1") -> str:
    """Exclude players blocked in either direction from viewer."""
    return f"""
      AND NOT EXISTS (
          SELECT 1 FROM player_ignores ig
          WHERE (ig.blocker_id = {viewer_param} AND ig.blocked_id = p.id)
             OR (ig.blocker_id = p.id AND ig.blocked_id = {viewer_param})
      )
    """


class SocialService:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def _player_settings(self, player_id: int) -> dict:
        row = await self.db.fetchrow("SELECT settings FROM players WHERE id = $1", int(player_id))
        raw = row["settings"] if row else {}
        if raw is None:
            return {}
        if isinstance(raw, str):
            try:
                return json.loads(raw) or {}
            except json.JSONDecodeError:
                return {}
        if isinstance(raw, dict):
            return raw
        return {}

    async def appears_offline(self, player_id: int) -> bool:
        settings = await self._player_settings(player_id)
        return bool(settings.get("social_appear_offline"))

    async def allows_whispers_from_strangers(self, player_id: int) -> bool:
        settings = await self._player_settings(player_id)
        return bool(settings.get("social_allow_whispers_from_strangers"))

    async def allows_party_invites_from_strangers(self, player_id: int) -> bool:
        settings = await self._player_settings(player_id)
        return bool(settings.get("social_allow_party_invites_from_strangers"))

    async def get_settings(self, player_id: int) -> dict:
        return {
            "appear_offline": await self.appears_offline(player_id),
            "allow_whispers_from_strangers": await self.allows_whispers_from_strangers(player_id),
            "allow_party_invites_from_strangers": await self.allows_party_invites_from_strangers(player_id),
        }

    async def set_settings(
        self,
        player_id: int,
        *,
        appear_offline: bool | None = None,
        allow_whispers_from_strangers: bool | None = None,
        allow_party_invites_from_strangers: bool | None = None,
    ) -> dict:
        settings = await self._player_settings(player_id)
        if appear_offline is not None:
            settings["social_appear_offline"] = bool(appear_offline)
        if allow_whispers_from_strangers is not None:
            settings["social_allow_whispers_from_strangers"] = bool(allow_whispers_from_strangers)
        if allow_party_invites_from_strangers is not None:
            settings["social_allow_party_invites_from_strangers"] = bool(allow_party_invites_from_strangers)
        await self.db.execute(
            "UPDATE players SET settings = $2::jsonb WHERE id = $1",
            int(player_id),
            json.dumps(settings),
        )
        return await self.get_settings(player_id)

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

    def _presence_from_row(self, row: dict, *, mask_offline: bool = False) -> dict:
        if mask_offline:
            return {
                "online": False,
                "last_seen": None,
                "zone_hint": None,
                "presence_status": "offline",
            }
        last_seen = row.get("last_seen")
        now = datetime.now(timezone.utc)
        online = False
        last_seen_iso = None
        if last_seen:
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            last_seen_iso = last_seen.isoformat()
            online = (now - last_seen) <= ONLINE_THRESHOLD

        if not online:
            return {
                "online": False,
                "last_seen": last_seen_iso,
                "zone_hint": None,
                "presence_status": "offline",
            }

        zone_hint = None
        presence_status = "online"
        combat_status = str(row.get("combat_status") or "idle")
        if row.get("in_dungeon"):
            zone_hint = "In dungeon"
            presence_status = "in-dungeon"
        elif combat_status == "in_combat":
            zone_hint = "In combat"
            presence_status = "in-combat"
        else:
            zone_hint = _zone_display(row.get("current_zone"))

        return {
            "online": True,
            "last_seen": last_seen_iso,
            "zone_hint": zone_hint,
            "presence_status": presence_status,
        }

    async def get_unread_counts(self, viewer_id: int) -> dict[str, int]:
        rows = await self.db.fetch(
            """
            SELECT from_player_id, COUNT(*)::int AS n
            FROM player_whispers
            WHERE to_player_id = $1 AND read_at IS NULL
            GROUP BY from_player_id
            """,
            int(viewer_id),
        )
        return {str(r["from_player_id"]): int(r["n"]) for r in rows}

    async def get_total_unread(self, viewer_id: int) -> int:
        try:
            row = await self.db.fetchrow(
                """
                SELECT COUNT(*)::int AS n FROM player_whispers
                WHERE to_player_id = $1 AND read_at IS NULL
                """,
                int(viewer_id),
            )
            return int(row["n"] or 0) if row else 0
        except Exception as e:
            log.warning("get_total_unread failed: %s", e)
            return 0

    async def get_roster(self, viewer_id: int) -> list[dict]:
        try:
            unread = await self.get_unread_counts(viewer_id)
        except Exception as e:
            log.warning("get_unread_counts failed: %s", e)
            unread = {}
        try:
            rows = await self.db.fetch(
                """
                SELECT
                    CASE WHEN f.player_a_id = $1 THEN f.player_b_id ELSE f.player_a_id END AS friend_id,
                    p.username,
                    p.last_seen,
                    p.settings AS friend_settings,
                    c.id AS character_id,
                    c.level,
                    c.class,
                    c.name AS character_name,
                    c.current_zone,
                    c.combat_status,
                    c.in_dungeon,
                    (
                        SELECT w.body FROM player_whispers w
                        WHERE (w.from_player_id = $1 AND w.to_player_id = p.id)
                           OR (w.from_player_id = p.id AND w.to_player_id = $1)
                        ORDER BY w.created_at DESC
                        LIMIT 1
                    ) AS last_whisper_body
                FROM player_friendships f
                JOIN players p ON p.id = CASE WHEN f.player_a_id = $1 THEN f.player_b_id ELSE f.player_a_id END
                LEFT JOIN characters c ON c.player_id = p.id AND c.is_active = TRUE
                WHERE f.player_a_id = $1 OR f.player_b_id = $1
                ORDER BY p.username ASC
                """,
                int(viewer_id),
            )
        except Exception as e:
            log.warning("get_roster query failed: %s", e)
            return []
        out = []
        for r in rows:
            fid = int(r["friend_id"])
            settings = r.get("friend_settings") or {}
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings) or {}
                except json.JSONDecodeError:
                    settings = {}
            mask = bool(settings.get("social_appear_offline"))
            pres = self._presence_from_row(dict(r), mask_offline=mask)
            out.append(
                {
                    "user_id": str(fid),
                    "username": str(r["username"] or ""),
                    "character_id": str(r["character_id"]) if r.get("character_id") else None,
                    "character_name": str(r["character_name"] or "") or None,
                    "level": int(r["level"]) if r["level"] is not None else None,
                    "class": str(r["class"]) if r["class"] else None,
                    "unread_count": unread.get(str(fid), 0),
                    "last_whisper_preview": str(r["last_whisper_body"])[:120] if r.get("last_whisper_body") else None,
                    **pres,
                }
            )
        return out

    async def get_whisper_inbox(self, viewer_id: int) -> list[dict]:
        """Friends with unread messages (offline inbox summary)."""
        roster = await self.get_roster(viewer_id)
        return [f for f in roster if int(f.get("unread_count") or 0) > 0]

    async def get_requests(self, viewer_id: int) -> dict:
        try:
            return await self._get_requests_impl(viewer_id)
        except Exception as e:
            log.warning("get_requests failed: %s", e)
            return {"incoming": [], "outgoing": []}

    async def _get_requests_impl(self, viewer_id: int) -> dict:
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

    async def cancel_friend_request(self, viewer_id: int, request_id: str) -> tuple[bool, str]:
        req = await self.db.fetchrow(
            "SELECT from_player_id, status FROM player_friend_requests WHERE id = $1",
            request_id,
        )
        if not req:
            return False, "Request not found."
        if int(req["from_player_id"]) != int(viewer_id):
            return False, "Not your request."
        if req["status"] != "pending":
            return False, "Request is no longer pending."
        await self.db.execute("DELETE FROM player_friend_requests WHERE id = $1", request_id)
        return True, "Request cancelled."

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
        try:
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
        except Exception as e:
            log.warning("list_ignores failed: %s", e)
            return []

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
            if not await self.allows_whispers_from_strangers(to_id):
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

    async def _viewer_character_id(self, viewer_id: int) -> Any:
        row = await self.db.fetchrow(
            "SELECT id FROM characters WHERE player_id = $1 AND is_active = TRUE LIMIT 1",
            int(viewer_id),
        )
        return row["id"] if row else None

    async def get_suggestions(self, viewer_id: int, *, limit: int = 12) -> list[dict]:
        try:
            return await self._get_suggestions_impl(viewer_id, limit=limit)
        except Exception as e:
            log.warning("get_suggestions failed: %s", e)
            return []

    async def _get_suggestions_impl(self, viewer_id: int, *, limit: int = 12) -> list[dict]:
        char_id = await self._viewer_character_id(viewer_id)
        if not char_id:
            return []

        exclude_sql = """
          AND p.id != $1
          AND NOT EXISTS (
              SELECT 1 FROM player_friendships fr
              WHERE fr.player_a_id = LEAST($1::bigint, p.id) AND fr.player_b_id = GREATEST($1::bigint, p.id)
          )
          AND NOT EXISTS (
              SELECT 1 FROM player_ignores ig
              WHERE (ig.blocker_id = $1 AND ig.blocked_id = p.id)
                 OR (ig.blocker_id = p.id AND ig.blocked_id = $1)
          )
          AND NOT EXISTS (
              SELECT 1 FROM player_friend_requests r
              WHERE r.status = 'pending'
                AND ((r.from_player_id = $1 AND r.to_player_id = p.id)
                  OR (r.from_player_id = p.id AND r.to_player_id = $1))
          )
        """
        out: list[dict] = []
        seen: set[int] = set()

        def _add(rows: list, reason: str) -> None:
            for r in rows:
                pid = int(r["id"])
                if pid in seen or pid == int(viewer_id):
                    continue
                seen.add(pid)
                out.append(
                    {
                        "user_id": str(pid),
                        "username": str(r["username"] or ""),
                        "character_id": str(r["character_id"]) if r.get("character_id") else None,
                        "character_name": str(r.get("character_name") or "") or None,
                        "level": int(r["level"]) if r.get("level") is not None else None,
                        "class": str(r["class"]) if r.get("class") else None,
                        "reason": reason,
                    }
                )
                if len(out) >= limit:
                    return

        guild_rows = await self.db.fetch(
            f"""
            SELECT DISTINCT p.id, p.username, c.id AS character_id, c.name AS character_name, c.level, c.class
            FROM characters me
            JOIN characters c ON c.guild_id = me.guild_id AND c.player_id != me.player_id AND c.is_active = TRUE
            JOIN players p ON p.id = c.player_id
            WHERE me.id = $2 AND me.guild_id IS NOT NULL
            {exclude_sql}
            ORDER BY p.username ASC
            LIMIT 6
            """,
            int(viewer_id),
            char_id,
        )
        _add(guild_rows, "Guild mate")

        if len(out) < limit:
            try:
                dungeon_rows = await self.db.fetch(
                    f"""
                    SELECT DISTINCT ON (p.id) p.id, p.username, c.id AS character_id,
                           c.name AS character_name, c.level, c.class
                    FROM dungeon_participants me
                    JOIN dungeon_participants other ON other.run_id = me.run_id
                        AND other.character_id != me.character_id
                    JOIN characters c ON c.id = other.character_id AND c.is_active = TRUE
                    JOIN players p ON p.id = c.player_id
                    JOIN dungeon_runs dr ON dr.id = me.run_id
                    WHERE me.character_id = $2
                      AND dr.started_at >= NOW() - INTERVAL '7 days'
                    {exclude_sql}
                    ORDER BY p.id, dr.started_at DESC
                    LIMIT 6
                    """,
                    int(viewer_id),
                    char_id,
                )
                _add(dungeon_rows, "Recent dungeon")
            except Exception as e:
                log.debug("dungeon suggestions skipped: %s", e)

        if len(out) < limit:
            try:
                pvp_rows = await self.db.fetch(
                    f"""
                    SELECT DISTINCT ON (p.id) p.id, p.username, c.id AS character_id,
                           c.name AS character_name, c.level, c.class
                    FROM pvp_match_history h
                    JOIN characters c ON c.id = h.opponent_character_id AND c.is_active = TRUE
                    JOIN players p ON p.id = c.player_id
                    WHERE h.character_id = $2
                      AND h.created_at >= NOW() - INTERVAL '7 days'
                      AND h.opponent_character_id IS NOT NULL
                    {exclude_sql}
                    ORDER BY p.id, h.created_at DESC
                    LIMIT 6
                    """,
                    int(viewer_id),
                    char_id,
                )
                _add(pvp_rows, "Recent PvP")
            except Exception as e:
                log.debug("pvp suggestions skipped: %s", e)

        return out[:limit]
