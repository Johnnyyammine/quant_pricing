"""Day count and calendar conventions.

Default day count is ACT/365 Fixed: ``τ(d1, d2) = (d2 − d1).days / 365``.
The default calendar is a weekday calendar (Mon–Fri) with a pluggable set of holidays.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum

DAYS_PER_YEAR_ACT365F: float = 365.0


class DayCount(StrEnum):
    """Supported day-count conventions."""

    ACT_365F = "ACT/365F"


def year_fraction(start: dt.date, end: dt.date, day_count: DayCount = DayCount.ACT_365F) -> float:
    """Year fraction between two dates under ``day_count``.

    Negative when ``end`` precedes ``start``, so the function is additive:
    ``τ(a, c) = τ(a, b) + τ(b, c)``.
    """
    match day_count:
        case DayCount.ACT_365F:
            return (end - start).days / DAYS_PER_YEAR_ACT365F


@dataclass(frozen=True, slots=True)
class WeekdayCalendar:
    """Business days are Monday–Friday excluding ``holidays``."""

    holidays: frozenset[dt.date] = field(default_factory=frozenset)

    def is_business_day(self, d: dt.date) -> bool:
        """True if ``d`` is a weekday and not a holiday."""
        return d.weekday() < 5 and d not in self.holidays

    def adjust_following(self, d: dt.date) -> dt.date:
        """Roll ``d`` forward to the next business day (Following convention)."""
        while not self.is_business_day(d):
            d += dt.timedelta(days=1)
        return d

    def add_business_days(self, d: dt.date, n: int) -> dt.date:
        """Move ``n`` business days from ``d`` (``n`` may be negative).

        For ``n == 0`` returns ``d`` adjusted to the following business day.
        """
        if n == 0:
            return self.adjust_following(d)
        step = dt.timedelta(days=1 if n > 0 else -1)
        remaining = abs(n)
        while remaining:
            d += step
            if self.is_business_day(d):
                remaining -= 1
        return d
