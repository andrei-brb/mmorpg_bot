"""Guild versus guild seasons.

Guilds had no opponent. You could join one, fund its research, check in and claim
its quests, but nothing a guild did was ever measured against another guild — it
was a co-op buff with a chat channel, competing silently with its own last week.
"""
import inspect
import pathlib
import unittest
from datetime import datetime, timezone

from services import guild_seasons
from services.guild_seasons import (
    STANDINGS_SIZE,
    previous_season_key,
    season_bounds,
    season_key,
)


class TestSeasonWindow(unittest.TestCase):
    def test_a_season_is_a_calendar_month(self):
        b = season_bounds(datetime(2026, 7, 26, tzinfo=timezone.utc))
        self.assertEqual(b["key"], "2026-07")
        self.assertEqual(b["start"].isoformat(), "2026-07-01")
        self.assertEqual(b["end"].isoformat(), "2026-08-01")

    def test_the_end_is_exclusive(self):
        """`>= start AND < end`, so no day is double-counted or dropped."""
        b = season_bounds(datetime(2026, 7, 15, tzinfo=timezone.utc))
        nxt = season_bounds(datetime(2026, 8, 1, tzinfo=timezone.utc))
        self.assertEqual(b["end"], nxt["start"])

    def test_december_rolls_into_the_next_year(self):
        b = season_bounds(datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(b["key"], "2026-12")
        self.assertEqual(b["end"].isoformat(), "2027-01-01")

    def test_january_looks_back_to_december(self):
        self.assertEqual(previous_season_key(datetime(2026, 1, 1, tzinfo=timezone.utc)), "2025-12")

    def test_every_day_of_a_month_is_the_same_season(self):
        keys = {season_key(datetime(2026, 3, d, tzinfo=timezone.utc)) for d in (1, 15, 31)}
        self.assertEqual(keys, {"2026-03"})

    def test_naive_datetimes_are_treated_as_utc(self):
        self.assertEqual(season_key(datetime(2026, 5, 4)), "2026-05")

    def test_standings_fit_on_a_screen(self):
        self.assertGreaterEqual(STANDINGS_SIZE, 5)
        self.assertLessEqual(STANDINGS_SIZE, 50)


class TestDerivedNotRecorded(unittest.TestCase):
    """A guild's score is the sum of what its members did, so it is COMPUTED
    from weekly_scores. A parallel table would need its own write on every kill,
    its own backfill when someone changes guild, and its own reconciliation when
    the two disagree — and they would, because membership changes and history
    does not."""

    def test_standings_aggregate_the_member_scores(self):
        src = inspect.getsource(guild_seasons.standings)
        self.assertIn("FROM weekly_scores w", src)
        self.assertIn("JOIN characters c ON c.id = w.character_id", src)
        self.assertIn("GROUP BY g.id", src)

    def test_there_is_no_guild_score_write_path(self):
        src = pathlib.Path("services/guild_seasons.py").read_text()
        self.assertNotIn("INSERT INTO guild_season_scores", src)
        self.assertNotIn("UPDATE guilds SET season", src)

    def test_only_the_finished_result_is_persisted(self):
        """A past season must not change when someone leaves a guild."""
        schema = pathlib.Path("database/db.py").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS guild_season_champions", schema)
        block = schema[schema.index("guild_season_champions"):][:600]
        self.assertIn("season_key      VARCHAR(7) PRIMARY KEY", block)
        # A disbanded guild must not erase the record that it won.
        self.assertIn("ON DELETE SET NULL", block)

    def test_contributors_are_reported(self):
        """A guild's rank is a claim about its people. Showing how many actually
        fought is what stops a big roster reading as a strong one."""
        src = inspect.getsource(guild_seasons.standings)
        self.assertIn("COUNT(DISTINCT w.character_id)", src)

    def test_your_guild_gets_a_rank_even_when_off_the_board(self):
        src = inspect.getsource(guild_seasons.standings)
        self.assertIn("off_board", src)


class TestSealing(unittest.TestCase):
    def test_sealing_is_idempotent(self):
        """There is no scheduler here, so this runs on every standings request;
        it must be safe to call constantly."""
        src = inspect.getsource(guild_seasons.seal_finished_season)
        self.assertIn("ON CONFLICT (season_key) DO NOTHING", src)
        self.assertIn("SELECT 1 FROM guild_season_champions WHERE season_key", src)

    def test_sealing_never_blocks_the_standings_request(self):
        http = pathlib.Path("services/activity_http.py").read_text()
        block = http[http.index("async def handle_guild_season"):][:1400]
        self.assertIn("seal_finished_season", block)
        self.assertIn("except Exception", block)

    def test_the_metric_is_normalised_before_it_is_stored(self):
        src = inspect.getsource(guild_seasons.seal_finished_season)
        self.assertIn("normalize_metric(metric)", src)


class TestNoInventedRewards(unittest.TestCase):
    def test_seasons_do_not_pay_out_gold_or_items(self):
        """Any number picked here would inject currency into an economy whose
        measured problem is having too much of it. Choosing it is the owner's
        call, not something to slip into a feature commit."""
        src = pathlib.Path("services/guild_seasons.py").read_text()
        for forbidden in ("add_gold", "deduct_gold", "add_item", "generate_loot", "award_xp"):
            self.assertNotIn(forbidden, src, f"season code touches {forbidden}")

    def test_the_endpoint_is_registered(self):
        http = pathlib.Path("services/activity_http.py").read_text()
        self.assertIn('"/api/game/guild/season"', http)


if __name__ == "__main__":
    unittest.main()
