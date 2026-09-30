import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.dates import WeekdayCalendar, year_fraction

dates = st.dates(min_value=dt.date(2000, 1, 1), max_value=dt.date(2100, 12, 31))


def test_act365f_leap_year():
    # 2028 is a leap year: 366 days → 366/365
    assert year_fraction(dt.date(2028, 1, 1), dt.date(2029, 1, 1)) == 366 / 365


@given(dates, dates, dates)
def test_year_fraction_additive_and_antisymmetric(a, b, c):
    total = year_fraction(a, b) + year_fraction(b, c)
    assert year_fraction(a, c) == pytest.approx(total, abs=1e-12)
    assert year_fraction(a, b) == -year_fraction(b, a)


def test_weekday_calendar_skips_weekends_and_holidays():
    xmas = dt.date(2026, 12, 25)  # Friday
    cal = WeekdayCalendar(holidays=frozenset({xmas}))
    assert not cal.is_business_day(xmas)
    assert cal.adjust_following(xmas) == dt.date(2026, 12, 28)  # Monday
    assert cal.add_business_days(dt.date(2026, 12, 24), 1) == dt.date(2026, 12, 28)
    assert cal.add_business_days(dt.date(2026, 12, 28), -1) == dt.date(2026, 12, 24)


@given(dates, st.integers(-300, 300))
def test_add_business_days_lands_on_business_day(d, n):
    cal = WeekdayCalendar()
    out = cal.add_business_days(d, n)
    assert cal.is_business_day(out)
    if n > 0:
        assert out > d
    elif n < 0:
        assert out < d
