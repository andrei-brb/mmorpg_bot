"""Mirror `streak_from_dates` from `services.guild.guild_checkin` (pure; no DB imports)."""

from datetime import date, timedelta
from typing import Set


def streak_from_dates(dates: Set[date], today: date, checked_today: bool) -> int:
    anchor = today if checked_today else today - timedelta(days=1)
    if anchor not in dates:
        return 0
    s = 0
    d = anchor
    while d in dates:
        s += 1
        d -= timedelta(days=1)
    return s


def test_streak_includes_today_when_checked():
    today = date(2026, 5, 14)
    days = {today - timedelta(days=2), today - timedelta(days=1), today}
    assert streak_from_dates(days, today, checked_today=True) == 3


def test_streak_ends_yesterday_when_not_checked_today():
    today = date(2026, 5, 14)
    days = {today - timedelta(days=2), today - timedelta(days=1)}
    assert streak_from_dates(days, today, checked_today=False) == 2


def test_streak_zero_when_gap():
    today = date(2026, 5, 14)
    days = {today - timedelta(days=5), today - timedelta(days=3)}
    assert streak_from_dates(days, today, checked_today=False) == 0


if __name__ == "__main__":
    test_streak_includes_today_when_checked()
    test_streak_ends_yesterday_when_not_checked_today()
    test_streak_zero_when_gap()
    print("guild checkin streak tests ok")
