"""
Seasonal battle pass: XP from gameplay, tier claims (free track v1).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from services.crafting.crafting_service import CraftingService

log = logging.getLogger("battle_pass")

# Pass XP grants (base; weekend multiplier applied in try_grant_xp)
XP_DAILY_LOGIN = 40
XP_LADDER_MILESTONE = 30
XP_GUILD_CHECKIN = 20
XP_QUEST_COMPLETE = 25
XP_PVP_WIN = 35
XP_PLAYTIME_BLOCK = 15  # per 5 minutes, capped per day
XP_COMBAT_WIN = 10
XP_COMBAT_BOSS_BONUS = 10
XP_DUNGEON_FLOOR = 20
XP_GUILD_RAID_CLEAR = 25
XP_GUILD_BOSS_DEFEAT = 30
XP_GUILD_BOSS_HIT = 10
XP_EXPLORE = 12
XP_BANK_DONATE_BLOCK = 5  # per 500 gold donated, capped daily
PLAYTIME_BLOCK_MINUTES = 5
PLAYTIME_DAILY_CAP_MINUTES = 30
COMBAT_BP_DAILY_CAP = 25
EXPLORE_BP_DAILY_CAP = 6
BANK_BP_DAILY_CAP = 50  # max blocks per day

DEFAULT_SEASON_KEY = "season_1"
DEFAULT_SEASON_NAME = "Season I — Path of the Wanderer"
DEFAULT_MAX_TIER = 30
DEFAULT_XP_PER_TIER = 100


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_weekend_utc(dt: Optional[datetime] = None) -> bool:
    d = (dt or utc_now()).weekday()
    return d >= 5  # Saturday=5, Sunday=6


def tier_from_xp(xp: int, xp_per_tier: int, max_tier: int) -> int:
    if xp_per_tier <= 0:
        return 0
    return min(max_tier, max(0, xp // xp_per_tier))


def xp_into_current_tier(xp: int, xp_per_tier: int) -> int:
    if xp_per_tier <= 0:
        return 0
    return xp % xp_per_tier


class BattlePassService:
    def __init__(self, db):
        self.db = db

    # ── Season bootstrap ─────────────────────────────────────────────────────

    async def ensure_active_season(self) -> Optional[dict]:
        now = utc_now()
        row = await self.db.fetchrow(
            """
            SELECT * FROM battle_pass_seasons
            WHERE is_active = TRUE AND starts_at <= $1 AND ends_at > $1
            ORDER BY starts_at DESC
            LIMIT 1
            """,
            now,
        )
        if row:
            await self._seed_tier_rewards_if_empty(int(row["id"]))
            return dict(row)

        upcoming = await self.db.fetchrow(
            """
            SELECT * FROM battle_pass_seasons
            WHERE is_active = TRUE AND ends_at > $1
            ORDER BY starts_at ASC
            LIMIT 1
            """,
            now,
        )
        if upcoming:
            await self._seed_tier_rewards_if_empty(int(upcoming["id"]))
            return dict(upcoming)

        any_season = await self.db.fetchval("SELECT 1 FROM battle_pass_seasons LIMIT 1")
        gap_days = 0 if not any_season else 3
        starts = now + timedelta(days=gap_days)
        ends = starts + timedelta(days=28)
        sid = await self.db.fetchval(
            """
            INSERT INTO battle_pass_seasons
                (key, name, starts_at, ends_at, max_tier, xp_per_tier, weekend_multiplier, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
            RETURNING id
            """,
            DEFAULT_SEASON_KEY,
            DEFAULT_SEASON_NAME,
            starts,
            ends,
            DEFAULT_MAX_TIER,
            DEFAULT_XP_PER_TIER,
            2.0,
        )
        if sid:
            await self._seed_tier_rewards_if_empty(int(sid))
            row = await self.db.fetchrow("SELECT * FROM battle_pass_seasons WHERE id=$1", sid)
            return dict(row) if row else None
        return None

    async def _seed_tier_rewards_if_empty(self, season_id: int) -> None:
        n_free = await self.db.fetchval(
            "SELECT COUNT(*)::int FROM battle_pass_tier_rewards WHERE season_id=$1 AND track='free'",
            season_id,
        )
        if int(n_free or 0) == 0:
            for tier, reward in self._default_free_tier_rewards().items():
                await self.db.execute(
                    """
                    INSERT INTO battle_pass_tier_rewards (season_id, tier, track, reward)
                    VALUES ($1, $2, 'free', $3::jsonb)
                    ON CONFLICT (season_id, tier, track) DO NOTHING
                    """,
                    season_id,
                    int(tier),
                    json.dumps(reward),
                )
        n_prem = await self.db.fetchval(
            "SELECT COUNT(*)::int FROM battle_pass_tier_rewards WHERE season_id=$1 AND track='premium'",
            season_id,
        )
        if int(n_prem or 0) == 0:
            for tier, reward in self._default_premium_tier_rewards().items():
                await self.db.execute(
                    """
                    INSERT INTO battle_pass_tier_rewards (season_id, tier, track, reward)
                    VALUES ($1, $2, 'premium', $3::jsonb)
                    ON CONFLICT (season_id, tier, track) DO NOTHING
                    """,
                    season_id,
                    int(tier),
                    json.dumps(reward),
                )
        log.info("Seeded battle pass tier rewards for season %s", season_id)

    @staticmethod
    def _default_free_tier_rewards() -> Dict[int, dict]:
        """Non-power rewards: gold, XP, mats, consumables."""
        out: Dict[int, dict] = {}
        for t in range(1, DEFAULT_MAX_TIER + 1):
            if t % 10 == 0:
                out[t] = {"gold": 500, "character_xp": 200, "crafting_xp": 100}
            elif t % 5 == 0:
                out[t] = {
                    "gold": 250,
                    "items": [
                        {"template_id": "weapon_scrap", "quantity": 5, "rarity": "common"},
                        {"template_id": "armor_scrap", "quantity": 5, "rarity": "common"},
                    ],
                }
            elif t % 3 == 0:
                out[t] = {
                    "gold": 100,
                    "items": [{"template_id": "health_potion", "quantity": 3, "rarity": "common"}],
                }
            elif t % 2 == 0:
                out[t] = {"gold": 75, "character_xp": 50}
            else:
                out[t] = {"gold": 50, "crafting_xp": 25}
        return out

    @staticmethod
    def _default_premium_tier_rewards() -> Dict[int, dict]:
        """Premium track — richer than free."""
        out: Dict[int, dict] = {}
        for t in range(1, DEFAULT_MAX_TIER + 1):
            if t % 10 == 0:
                out[t] = {
                    "gold": 900,
                    "character_xp": 400,
                    "crafting_xp": 200,
                    "items": [{"template_id": "health_potion", "quantity": 5, "rarity": "common"}],
                }
            elif t % 5 == 0:
                out[t] = {
                    "gold": 450,
                    "items": [
                        {"template_id": "weapon_scrap", "quantity": 8, "rarity": "common"},
                        {"template_id": "armor_scrap", "quantity": 8, "rarity": "common"},
                    ],
                }
            elif t % 3 == 0:
                out[t] = {"gold": 200, "character_xp": 120}
            elif t % 2 == 0:
                out[t] = {"gold": 150, "character_xp": 80, "crafting_xp": 50}
            else:
                out[t] = {"gold": 100, "crafting_xp": 40}
        return out

    async def _get_or_create_progress(self, character_id: UUID, season_id: int) -> dict:
        row = await self.db.fetchrow(
            "SELECT * FROM character_battle_pass WHERE character_id=$1 AND season_id=$2",
            character_id,
            season_id,
        )
        if row:
            return dict(row)
        await self.db.execute(
            """
            INSERT INTO character_battle_pass (character_id, season_id, xp)
            VALUES ($1, $2, 0)
            ON CONFLICT (character_id, season_id) DO NOTHING
            """,
            character_id,
            season_id,
        )
        row = await self.db.fetchrow(
            "SELECT * FROM character_battle_pass WHERE character_id=$1 AND season_id=$2",
            character_id,
            season_id,
        )
        return dict(row) if row else {"character_id": character_id, "season_id": season_id, "xp": 0}

    # ── XP grants ────────────────────────────────────────────────────────────

    async def try_grant_xp(
        self,
        character_id: UUID,
        event_key: str,
        base_amount: int,
        source: str,
    ) -> Dict[str, Any]:
        """Idempotent pass XP grant; applies weekend multiplier from active season."""
        if base_amount <= 0:
            return {"granted": False, "xp": 0}
        season = await self.ensure_active_season()
        if not season:
            return {"granted": False, "xp": 0, "reason": "no_season"}
        now = utc_now()
        if season["starts_at"] > now or season["ends_at"] <= now:
            return {"granted": False, "xp": 0, "reason": "season_inactive"}

        season_id = int(season["id"])
        mult = float(season.get("weekend_multiplier") or 1.0)
        if is_weekend_utc(now):
            amount = int(round(base_amount * mult))
        else:
            amount = int(base_amount)

        inserted = await self.db.fetchrow(
            """
            INSERT INTO battle_pass_xp_grants (character_id, season_id, event_key, xp_amount, source)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (character_id, season_id, event_key) DO NOTHING
            RETURNING xp_amount
            """,
            character_id,
            season_id,
            event_key[:128],
            amount,
            source[:64],
        )
        if not inserted:
            return {"granted": False, "xp": 0, "reason": "duplicate"}

        await self.db.execute(
            """
            INSERT INTO character_battle_pass (character_id, season_id, xp, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (character_id, season_id) DO UPDATE SET
                xp = character_battle_pass.xp + EXCLUDED.xp,
                updated_at = NOW()
            """,
            character_id,
            season_id,
            amount,
        )
        prog = await self._get_or_create_progress(character_id, season_id)
        return {
            "granted": True,
            "xp": amount,
            "total_xp": int(prog.get("xp") or 0),
            "season_id": season_id,
            "weekend_bonus": is_weekend_utc(now) and mult > 1.0,
        }

    async def on_daily_login_claimed(self, character_id: UUID, current_streak: int) -> List[Dict[str, Any]]:
        results = []
        r = await self.try_grant_xp(character_id, f"daily_login_{utc_now().date().isoformat()}", XP_DAILY_LOGIN, "daily_login")
        results.append(r)
        if current_streak > 0 and current_streak % 7 == 0:
            milestone = current_streak // 7
            r2 = await self.try_grant_xp(
                character_id,
                f"ladder_milestone_{milestone}",
                XP_LADDER_MILESTONE,
                "login_ladder",
            )
            results.append(r2)
        return results

    async def grant_playtime_xp(self, character_id: UUID, minutes: int) -> Dict[str, Any]:
        """Grant pass XP for Activity playtime; capped per UTC day."""
        if minutes <= 0:
            return {"granted": False, "xp": 0}
        season = await self.ensure_active_season()
        if not season:
            return {"granted": False, "xp": 0}
        season_id = int(season["id"])
        today = utc_now().date()
        prog = await self._get_or_create_progress(character_id, season_id)
        stored_day = prog.get("playtime_day")
        if isinstance(stored_day, str):
            stored_day = date.fromisoformat(stored_day[:10])
        minutes_today = int(prog.get("playtime_minutes_today") or 0)
        if stored_day != today:
            minutes_today = 0
        cap = PLAYTIME_DAILY_CAP_MINUTES
        room = max(0, cap - minutes_today)
        apply_min = min(minutes, room)
        if apply_min <= 0:
            return {"granted": False, "xp": 0, "reason": "playtime_cap"}

        blocks = apply_min // PLAYTIME_BLOCK_MINUTES
        if blocks <= 0 and apply_min >= 1:
            blocks = 1
        total_xp = 0
        last_result: Dict[str, Any] = {"granted": False}
        for i in range(blocks):
            key = f"playtime_{today.isoformat()}_{minutes_today + (i + 1) * PLAYTIME_BLOCK_MINUTES}"
            last_result = await self.try_grant_xp(character_id, key, XP_PLAYTIME_BLOCK, "playtime")
            if last_result.get("granted"):
                total_xp += int(last_result.get("xp") or 0)

        new_minutes = minutes_today + apply_min
        await self.db.execute(
            """
            UPDATE character_battle_pass
            SET playtime_minutes_today=$3, playtime_day=$4, updated_at=NOW()
            WHERE character_id=$1 AND season_id=$2
            """,
            character_id,
            season_id,
            new_minutes,
            today,
        )
        return {"granted": total_xp > 0, "xp": total_xp, "minutes_applied": apply_min}

    async def _player_is_premium(self, character_id: UUID) -> bool:
        row = await self.db.fetchrow(
            """
            SELECT p.is_premium FROM players p
            JOIN characters c ON c.player_id = p.id
            WHERE c.id = $1
            """,
            character_id,
        )
        return bool(row and row.get("is_premium"))

    async def _premium_unlocked(self, character_id: UUID, season_id: int, prog: dict) -> bool:
        if prog.get("premium_unlocked_at"):
            return True
        if await self._player_is_premium(character_id):
            await self.db.execute(
                """
                UPDATE character_battle_pass
                SET premium_unlocked_at = COALESCE(premium_unlocked_at, NOW())
                WHERE character_id = $1 AND season_id = $2
                """,
                character_id,
                season_id,
            )
            return True
        return False

    def _build_tier_rows(
        self,
        tier_rows,
        track: str,
        current_tier: int,
        claimed_set: set,
        premium_ok: bool,
    ) -> List[dict]:
        out = []
        for tr in tier_rows:
            t = int(tr["tier"])
            reward = tr["reward"]
            if isinstance(reward, str):
                try:
                    reward = json.loads(reward)
                except json.JSONDecodeError:
                    reward = {}
            unlocked = t <= current_tier
            claimed = (t, track) in claimed_set
            locked_premium = track == "premium" and not premium_ok
            claimable = unlocked and not claimed and t > 0 and not locked_premium
            out.append(
                {
                    "tier": t,
                    "track": track,
                    "reward": reward,
                    "unlocked": unlocked,
                    "claimed": claimed,
                    "claimable": claimable,
                    "locked_premium": locked_premium,
                }
            )
        return out

    # ── State + claims ───────────────────────────────────────────────────────

    async def get_state(self, character_id: UUID) -> Dict[str, Any]:
        season = await self.ensure_active_season()
        if not season:
            return {"ok": True, "season": None, "progress": None, "tiers": [], "tiers_free": [], "tiers_premium": []}

        season_id = int(season["id"])
        prog = await self._get_or_create_progress(character_id, season_id)
        xp = int(prog.get("xp") or 0)
        xp_per = int(season.get("xp_per_tier") or DEFAULT_XP_PER_TIER)
        max_tier = int(season.get("max_tier") or DEFAULT_MAX_TIER)
        current_tier = tier_from_xp(xp, xp_per, max_tier)
        tier_xp = xp_into_current_tier(xp, xp_per)
        premium_ok = await self._premium_unlocked(character_id, season_id, prog)

        tier_rows = await self.db.fetch(
            """
            SELECT tier, track, reward FROM battle_pass_tier_rewards
            WHERE season_id=$1 AND track IN ('free', 'premium')
            ORDER BY track, tier
            """,
            season_id,
        )
        claims = await self.db.fetch(
            "SELECT tier, track FROM battle_pass_claims WHERE character_id=$1 AND season_id=$2",
            character_id,
            season_id,
        )
        claimed_set = {(int(c["tier"]), str(c["track"])) for c in claims}

        free_rows = [r for r in tier_rows if r["track"] == "free"]
        prem_rows = [r for r in tier_rows if r["track"] == "premium"]
        tiers_free = self._build_tier_rows(free_rows, "free", current_tier, claimed_set, premium_ok)
        tiers_premium = self._build_tier_rows(prem_rows, "premium", current_tier, claimed_set, premium_ok)
        tiers_out = tiers_free + tiers_premium

        streak = await self.db.fetchrow(
            "SELECT current_streak, longest_streak, last_login FROM login_streaks WHERE character_id=$1",
            character_id,
        )
        streak_dict = dict(streak) if streak else {}
        last_login = streak_dict.get("last_login")
        claimed_today = False
        if last_login:
            ll = last_login if isinstance(last_login, datetime) else datetime.fromisoformat(str(last_login))
            if ll.tzinfo is None:
                ll = ll.replace(tzinfo=timezone.utc)
            claimed_today = ll.date() >= utc_now().date()

        now = utc_now()
        return {
            "ok": True,
            "season": {
                "id": season_id,
                "key": season.get("key"),
                "name": season.get("name"),
                "starts_at": season.get("starts_at"),
                "ends_at": season.get("ends_at"),
                "max_tier": max_tier,
                "xp_per_tier": xp_per,
                "weekend_multiplier": float(season.get("weekend_multiplier") or 1.0),
                "is_live": season["starts_at"] <= now < season["ends_at"],
            },
            "progress": {
                "xp": xp,
                "tier": current_tier,
                "xp_in_tier": tier_xp,
                "xp_needed_for_next": xp_per - tier_xp if current_tier < max_tier else 0,
                "premium_unlocked": premium_ok,
            },
            "tiers": tiers_out,
            "tiers_free": tiers_free,
            "tiers_premium": tiers_premium,
            "daily_login": {
                "current_streak": int(streak_dict.get("current_streak") or 0),
                "longest_streak": int(streak_dict.get("longest_streak") or 0),
                "claimed_today": claimed_today,
                "weekend_double": is_weekend_utc(now),
            },
        }

    async def unlock_premium(self, character_id: UUID) -> Tuple[bool, str]:
        season = await self.ensure_active_season()
        if not season:
            return False, "No active season."
        season_id = int(season["id"])
        await self._get_or_create_progress(character_id, season_id)
        await self.db.execute(
            """
            UPDATE character_battle_pass
            SET premium_unlocked_at = COALESCE(premium_unlocked_at, NOW())
            WHERE character_id = $1 AND season_id = $2
            """,
            character_id,
            season_id,
        )
        return True, "Premium track unlocked."

    async def claim_tier(
        self, character_id: UUID, tier: int, track: str = "free"
    ) -> Tuple[bool, str, Optional[dict]]:
        track = (track or "free").lower().strip()
        if track not in ("free", "premium"):
            return False, "Invalid track.", None
        if tier < 1:
            return False, "Invalid tier.", None

        season = await self.ensure_active_season()
        if not season:
            return False, "No active season.", None
        now = utc_now()
        if not (season["starts_at"] <= now < season["ends_at"]):
            return False, "Season is not live yet or has ended.", None

        season_id = int(season["id"])
        prog = await self._get_or_create_progress(character_id, season_id)
        if track == "premium" and not await self._premium_unlocked(character_id, season_id, prog):
            return False, "Premium track is locked.", None
        xp = int(prog.get("xp") or 0)
        xp_per = int(season.get("xp_per_tier") or DEFAULT_XP_PER_TIER)
        max_tier = int(season.get("max_tier") or DEFAULT_MAX_TIER)
        if tier > tier_from_xp(xp, xp_per, max_tier):
            return False, "Tier not unlocked yet.", None

        existing = await self.db.fetchval(
            """
            SELECT 1 FROM battle_pass_claims
            WHERE character_id=$1 AND season_id=$2 AND tier=$3 AND track=$4
            """,
            character_id,
            season_id,
            tier,
            track,
        )
        if existing:
            return False, "Already claimed.", None

        row = await self.db.fetchrow(
            """
            SELECT reward FROM battle_pass_tier_rewards
            WHERE season_id=$1 AND tier=$2 AND track=$3
            """,
            season_id,
            tier,
            track,
        )
        if not row:
            return False, "No reward configured for this tier.", None
        reward = row["reward"]
        if isinstance(reward, str):
            reward = json.loads(reward)

        from services.character.character_service import CharacterService
        from services.character.inventory_service import InventoryService

        char_svc = CharacterService(self.db)
        inv_svc = InventoryService(self.db)
        craft_svc = CraftingService(self.db)
        delivery = await self.apply_reward_json(character_id, reward, char_svc, inv_svc, craft_svc)

        await self.db.execute(
            """
            INSERT INTO battle_pass_claims (character_id, season_id, tier, track)
            VALUES ($1, $2, $3, $4)
            """,
            character_id,
            season_id,
            tier,
            track,
        )
        return True, "Reward claimed.", delivery

    async def apply_reward_json(
        self,
        character_id: UUID,
        reward: dict,
        char_svc,
        inv_svc,
        craft_svc,
    ) -> dict:
        out: Dict[str, Any] = {"gold": 0, "character_xp": 0, "crafting_xp": 0, "items": [], "failures": []}
        if not isinstance(reward, dict):
            return out
        if reward.get("gold"):
            g = int(reward["gold"])
            await char_svc.add_gold(character_id, g, "battle_pass")
            out["gold"] = g
        if reward.get("character_xp"):
            x = int(reward["character_xp"])
            await char_svc.award_xp(character_id, x, 1.0)
            out["character_xp"] = x
        if reward.get("crafting_xp"):
            c = int(reward["crafting_xp"])
            await craft_svc.add_crafting_xp(character_id, c)
            out["crafting_xp"] = c
        items = reward.get("items") or []
        if isinstance(reward.get("item"), dict):
            items = [reward["item"]] + list(items)
        for it in items:
            if not isinstance(it, dict):
                continue
            tid = str(it.get("template_id") or "")
            qty = int(it.get("quantity") or 1)
            rarity = str(it.get("rarity") or "common")
            if not tid:
                continue
            ok, msg = await inv_svc.add_item(character_id, tid, rarity=rarity, quantity=qty, from_="battle_pass")
            if ok:
                out["items"].append({"template_id": tid, "quantity": qty})
            else:
                out["failures"].append({"template_id": tid, "reason": msg})
        return out

    # ── Admin ────────────────────────────────────────────────────────────────

    @staticmethod
    def is_admin_discord_id(discord_id: int) -> bool:
        raw = (os.getenv("BATTLE_PASS_ADMIN_DISCORD_IDS") or "").strip()
        if not raw:
            return False
        try:
            allowed = {int(x.strip()) for x in raw.split(",") if x.strip()}
        except ValueError:
            return False
        return int(discord_id) in allowed

    async def admin_reset_season(self, restart_now: bool = True) -> Tuple[bool, str]:
        """
        Wipe all player progress/claims/XP grants for seasons; optionally restart Season I from now.
        For pre-launch testing only.
        """
        await self.db.execute("DELETE FROM battle_pass_xp_grants")
        await self.db.execute("DELETE FROM battle_pass_claims")
        await self.db.execute("DELETE FROM character_battle_pass")
        await self.db.execute("DELETE FROM battle_pass_tier_rewards")
        await self.db.execute("DELETE FROM battle_pass_seasons")

        if restart_now:
            now = utc_now()
            ends = now + timedelta(days=28)
            sid = await self.db.fetchval(
                """
                INSERT INTO battle_pass_seasons
                    (key, name, starts_at, ends_at, max_tier, xp_per_tier, weekend_multiplier, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                RETURNING id
                """,
                DEFAULT_SEASON_KEY,
                DEFAULT_SEASON_NAME,
                now,
                ends,
                DEFAULT_MAX_TIER,
                DEFAULT_XP_PER_TIER,
                2.0,
            )
            if sid:
                await self._seed_tier_rewards_if_empty(int(sid))
            return True, f"Battle pass reset. Season restarted (ends {ends.date().isoformat()} UTC)."
        return True, "Battle pass data wiped. Next ensure_active_season will create a new season."


async def grant_combat_victory_xp(db, character_id: UUID, enemy_key: str, is_boss: bool = False) -> None:
    try:
        svc = BattlePassService(db)
        today = utc_now().date().isoformat()
        ek = (enemy_key or "foe")[:48].replace(" ", "_")
        amount = XP_COMBAT_WIN + (XP_COMBAT_BOSS_BONUS if is_boss else 0)
        granted_today = await db.fetchval(
            """
            SELECT COALESCE(SUM(xp_amount), 0)::int FROM battle_pass_xp_grants
            WHERE character_id = $1 AND source = 'combat_victory'
              AND event_key LIKE $2
            """,
            character_id,
            f"%_{today}",
        )
        if int(granted_today or 0) >= COMBAT_BP_DAILY_CAP:
            return
        room = COMBAT_BP_DAILY_CAP - int(granted_today or 0)
        await svc.try_grant_xp(
            character_id,
            f"combat_{ek}_{today}",
            min(amount, room),
            "combat_victory",
        )
    except Exception:
        log.debug("battle pass combat xp grant skipped", exc_info=True)


async def grant_dungeon_floor_xp(db, character_id: UUID, run_id: UUID, floor: int) -> None:
    try:
        svc = BattlePassService(db)
        await svc.try_grant_xp(
            character_id,
            f"dungeon_{run_id}_{floor}",
            XP_DUNGEON_FLOOR,
            "dungeon_floor",
        )
    except Exception:
        log.debug("battle pass dungeon xp grant skipped", exc_info=True)


async def grant_raid_clear_xp(db, character_id: UUID, run_id: UUID) -> None:
    try:
        svc = BattlePassService(db)
        await svc.try_grant_xp(character_id, f"raid_clear_{run_id}", XP_GUILD_RAID_CLEAR, "guild_raid_clear")
    except Exception:
        log.debug("battle pass raid clear xp grant skipped", exc_info=True)


async def grant_guild_boss_hit_xp(db, character_id: UUID, encounter_id: UUID) -> None:
    try:
        svc = BattlePassService(db)
        await svc.try_grant_xp(
            character_id,
            f"guild_boss_hit_{encounter_id}",
            XP_GUILD_BOSS_HIT,
            "guild_boss_hit",
        )
    except Exception:
        log.debug("battle pass guild boss hit xp grant skipped", exc_info=True)


async def grant_guild_boss_defeat_xp(db, character_id: UUID, encounter_id: UUID) -> None:
    try:
        svc = BattlePassService(db)
        await svc.try_grant_xp(
            character_id,
            f"guild_boss_defeat_{encounter_id}",
            XP_GUILD_BOSS_DEFEAT,
            "guild_boss_defeat",
        )
    except Exception:
        log.debug("battle pass guild boss defeat xp grant skipped", exc_info=True)


async def grant_explore_xp(db, character_id: UUID) -> None:
    try:
        svc = BattlePassService(db)
        today = utc_now().date().isoformat()
        n = await db.fetchval(
            """
            SELECT COUNT(*)::int FROM battle_pass_xp_grants
            WHERE character_id = $1 AND source = 'explore' AND event_key LIKE $2
            """,
            character_id,
            f"explore_{today}_%",
        )
        if int(n or 0) >= EXPLORE_BP_DAILY_CAP:
            return
        await svc.try_grant_xp(
            character_id,
            f"explore_{today}_{int(n or 0) + 1}",
            XP_EXPLORE,
            "explore",
        )
    except Exception:
        log.debug("battle pass explore xp grant skipped", exc_info=True)


async def grant_bank_donate_xp(db, character_id: UUID, amount: int) -> None:
    try:
        blocks = max(0, int(amount) // 500)
        if blocks <= 0:
            return
        svc = BattlePassService(db)
        today = utc_now().date().isoformat()
        existing = await db.fetchval(
            """
            SELECT COUNT(*)::int FROM battle_pass_xp_grants
            WHERE character_id = $1 AND source = 'bank_donate' AND event_key LIKE $2
            """,
            character_id,
            f"bank_donate_{today}_%",
        )
        used = int(existing or 0)
        for i in range(min(blocks, BANK_BP_DAILY_CAP - used)):
            await svc.try_grant_xp(
                character_id,
                f"bank_donate_{today}_{used + i + 1}",
                XP_BANK_DONATE_BLOCK,
                "bank_donate",
            )
    except Exception:
        log.debug("battle pass bank donate xp grant skipped", exc_info=True)
