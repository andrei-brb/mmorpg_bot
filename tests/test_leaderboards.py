"""Weekly scoreboards.

The game had no way to compare yourself to anyone. The only leaderboards that
existed were per-encounter — damage inside one guild boss fight, strikes inside
one raid run, top enhancement levels — none of which answer "how am I doing
relative to other people playing this game". Without that, a shared world is
just a market with strangers in it.
"""
import inspect
import unittest
from datetime import datetime, timedelta, timezone

from services import leaderboards
from services.leaderboards import (
    BOARD_SIZE,
    DEFAULT_METRIC,
    DEFAULT_SCOPE,
    METRICS,
    SCOPES,
    next_reset,
    normalize_metric,
    normalize_scope,
    week_start,
)


class TestWeekBoundary(unittest.TestCase):
    """Defined once, here, rather than as date_trunc('week') in each query —
    which would spread the definition across call sites and depend on the
    database's locale for what a week is."""

    def test_the_week_starts_on_monday_utc(self):
        # 2026-07-26 is a Sunday; its week began Monday the 20th.
        sunday = datetime(2026, 7, 26, 23, 59, tzinfo=timezone.utc)
        self.assertEqual(week_start(sunday).isoformat(), "2026-07-20")

    def test_every_day_of_one_week_maps_to_the_same_start(self):
        monday = datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc)
        starts = {week_start(monday + timedelta(days=d, hours=5)) for d in range(7)}
        self.assertEqual(len(starts), 1)

    def test_the_next_day_rolls_over(self):
        sunday_late = datetime(2026, 7, 26, 23, 59, tzinfo=timezone.utc)
        monday_early = datetime(2026, 7, 27, 0, 1, tzinfo=timezone.utc)
        self.assertNotEqual(week_start(sunday_late), week_start(monday_early))

    def test_naive_datetimes_are_treated_as_utc_not_rejected(self):
        naive = datetime(2026, 7, 22, 12, 0)
        self.assertEqual(week_start(naive).isoformat(), "2026-07-20")

    def test_reset_is_exactly_one_week_after_the_start(self):
        when = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        start = week_start(when)
        reset = next_reset(when)
        self.assertEqual(reset.date() - start, timedelta(days=7))
        self.assertEqual(reset.tzinfo, timezone.utc)
        self.assertGreater(reset, when)


class TestMetrics(unittest.TestCase):
    def test_unknown_metrics_fall_back_rather_than_erroring(self):
        """The metric reaches a SQL column name, so anything unrecognised must
        become a known key before it gets near a query."""
        for junk in (None, "", "nonsense", "kills; DROP TABLE", 42, []):
            self.assertIn(normalize_metric(junk), METRICS)
        self.assertEqual(normalize_metric("nonsense"), DEFAULT_METRIC)

    def test_known_metrics_survive_normalisation(self):
        for key in METRICS:
            self.assertEqual(normalize_metric(key), key)
            self.assertEqual(normalize_metric(key.upper()), key)

    def test_every_metric_has_a_column_and_a_label(self):
        for key, cfg in METRICS.items():
            self.assertTrue(cfg["column"], key)
            self.assertTrue(cfg["label"], key)

    def test_metric_columns_are_plain_identifiers(self):
        """They are interpolated into SQL (a column name cannot be a bind
        parameter), so the table itself is the allowlist and every value in it
        must be inert."""
        for key, cfg in METRICS.items():
            self.assertRegex(cfg["column"], r"^[a-z_]+$", key)

    def test_the_board_fits_on_a_phone(self):
        self.assertGreaterEqual(BOARD_SIZE, 10)
        self.assertLessEqual(BOARD_SIZE, 50)


class TestScopes(unittest.TestCase):
    """`friends` is the scope that motivates: you will never be rank 1 of the
    world and you know it, but you might beat the person who got you playing."""

    def test_unknown_scopes_fall_back(self):
        for junk in (None, "", "nonsense", "; DROP TABLE", 7, []):
            self.assertIn(normalize_scope(junk), SCOPES)
        self.assertEqual(normalize_scope("nonsense"), DEFAULT_SCOPE)

    def test_known_scopes_survive(self):
        for s in SCOPES:
            self.assertEqual(normalize_scope(s), s)
            self.assertEqual(normalize_scope(s.upper()), s)

    def test_scope_never_reaches_sql_as_text(self):
        """The clause is chosen from a closed set; the scope string itself is
        never interpolated."""
        src = inspect.getsource(leaderboards.board)
        self.assertNotIn("{scope}", src)

    def test_every_scope_has_a_clause_or_is_the_default(self):
        src = inspect.getsource(leaderboards.board)
        for s in SCOPES:
            if s == DEFAULT_SCOPE:
                continue
            self.assertIn(f'"{s}"', src, f"{s} has no branch")


class TestDesignInvariants(unittest.TestCase):
    def test_recording_a_score_can_never_cost_a_player_their_rewards(self):
        """It runs on the victory path. A scoreboard is a nice-to-have sitting
        behind something that is not."""
        src = inspect.getsource(leaderboards.record)
        self.assertIn("try:", src)
        self.assertIn("except Exception:", src)

    def test_recording_is_a_single_upsert(self):
        """Read-then-write would race two kills landing at once."""
        src = inspect.getsource(leaderboards.record)
        self.assertIn("ON CONFLICT (character_id, week_start) DO UPDATE", src)
        self.assertNotIn("SELECT", src.upper().replace("INSERT", ""))

    def test_negative_amounts_cannot_be_recorded(self):
        src = inspect.getsource(leaderboards.record)
        self.assertIn("max(0,", src)

    def test_the_viewer_gets_their_rank_even_when_off_the_board(self):
        """A board that only shows the top 25 tells 99% of players nothing about
        themselves, which is the opposite of the point."""
        src = inspect.getsource(leaderboards.board)
        self.assertIn("off_board", src)

    def test_scores_are_recorded_from_the_victory_path(self):
        from services.combat import activity_combat

        src = inspect.getsource(activity_combat._finish_victory)
        self.assertIn("leaderboards.record", src)
        # After the gold is banked, not before.
        self.assertLess(src.index('add_gold'), src.index("leaderboards.record"))

    def test_the_endpoint_is_registered(self):
        import pathlib

        http = pathlib.Path("services/activity_http.py").read_text()
        self.assertIn('"/api/game/leaderboard"', http)

    def test_the_table_and_its_indexes_exist(self):
        import pathlib

        schema = pathlib.Path("database/db.py").read_text()
        self.assertIn("CREATE TABLE IF NOT EXISTS weekly_scores", schema)
        self.assertIn("ON DELETE CASCADE", schema[schema.index("weekly_scores"):][:800])
        for m in METRICS.values():
            self.assertIn(m["column"], schema)


if __name__ == "__main__":
    unittest.main()
