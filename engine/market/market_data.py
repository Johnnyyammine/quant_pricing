"""Market data snapshot used by every pricer.

Forward convention (all pricing is forward-based)::

    F(0, T) = S₀ · P_q(0, T) · P_b(0, T) / P_r(0, T) = S₀ · exp((r − q − b)·T)   (flat curves)

where ``P_r`` is the discount curve, ``P_q`` the continuous dividend-yield curve and ``P_b`` the
repo/borrow spread curve. The borrow spread enters the forward drift only; discounting uses
``P_r`` alone. Discrete dividends arrive in Phase 2 through :meth:`MarketData.forward`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from engine.dates import DayCount, year_fraction
from engine.errors import MarketDataError
from engine.market.curves import FlatRateCurve, RateCurve
from engine.market.vol import VolSurface


@dataclass(frozen=True, slots=True)
class MarketData:
    """Immutable market snapshot for a single underlying.

    Attributes:
        valuation_date: Date at which prices are computed (``t = 0``).
        spot: Underlying spot price ``S₀``.
        discount: Discount curve ``P_r(0, t)``.
        vol: Implied volatility surface.
        dividend_yield: Continuous dividend-yield curve ``P_q(0, t)``.
        borrow: Repo/borrow spread curve ``P_b(0, t)``.
        day_count: Day count used to turn dates into year fractions.

    """

    valuation_date: dt.date
    spot: float
    discount: RateCurve
    vol: VolSurface
    dividend_yield: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0))
    borrow: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0))
    day_count: DayCount = DayCount.ACT_365F

    def __post_init__(self) -> None:
        if not self.spot > 0.0:
            raise MarketDataError(f"spot must be positive, got {self.spot}")

    def time_to(self, date: dt.date) -> float:
        """Year fraction from the valuation date to ``date``."""
        return year_fraction(self.valuation_date, date, self.day_count)

    def df(self, t: float) -> float:
        """Discount factor ``P_r(0, t)``."""
        return self.discount.df(t)

    def forward(self, t: float) -> float:
        """Forward price ``F(0, t) = S₀ · P_q(0, t) · P_b(0, t) / P_r(0, t)``."""
        return self.spot * self.dividend_yield.df(t) * self.borrow.df(t) / self.discount.df(t)
