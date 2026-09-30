"""Market data snapshot used by every pricer.

Forward convention (all pricing is forward-based). With growth factor
``G(t) = P_q(0,t)·P_b(0,t)/P_r(0,t)`` and discrete dividends ``(t_i, D_i, δ_i)``, ``0 < t_i ≤ T``::

    F(0, T) = S₀·A(T) − Σ_i D_i·B_i(T)
    A(T)    = G(T)·Π_{t_j ≤ T} (1 − δ_j)
    B_i(T)  = G(T)/G(t_i)·Π_{t_i < t_j ≤ T} (1 − δ_j)

which reduces to ``S₀·exp((r − q − b)·T)`` for flat curves and no dividends. ``P_r`` discounts;
the continuous dividend yield ``P_q`` and the borrow spread ``P_b`` enter the forward only.

Escrowed decomposition (used by the escrowed-dividend model, trees and PDEs): at time ``t`` for an
option expiring at ``T``, ``S_t = Y_t / Π_t + E_t`` where ``Y`` is a continuous lognormal with
``Y_T = S_T``, ``Π_t = Π_{t < t_j ≤ T}(1 − δ_j)`` and
``E_t = Σ_{t < t_i ≤ T} D_i · G(t)/G(t_i) / Π_{t < t_j ≤ t_i}(1 − δ_j)`` is the escrowed cash.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from engine.dates import SAME_INSTANT, DayCount, year_fraction
from engine.errors import MarketDataError
from engine.market.curves import FlatRateCurve, RateCurve
from engine.market.dividends import Dividend, DividendEvent
from engine.market.vol import VolSurface


@dataclass(frozen=True, slots=True)
class ForwardSensitivities:
    """Forward ``F(0,T)`` and its derivatives to spot and to parallel zero-rate shifts.

    ``dF/dq`` also equals the derivative to a parallel shift of the borrow curve.
    """

    forward: float
    d_spot: float
    d_rate: float
    d_yield: float


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
        dividends: Discrete dividends (any order; past ones are ignored).
        day_count: Day count used to turn dates into year fractions.

    """

    valuation_date: dt.date
    spot: float
    discount: RateCurve
    vol: VolSurface
    dividend_yield: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0))
    borrow: RateCurve = field(default_factory=lambda: FlatRateCurve(0.0))
    dividends: tuple[Dividend, ...] = ()
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

    def growth(self, t: float) -> float:
        """Carry growth factor ``G(t) = P_q(0,t)·P_b(0,t)/P_r(0,t)``."""
        return self.dividend_yield.df(t) * self.borrow.df(t) / self.discount.df(t)

    def dividend_events(self, until: float) -> list[DividendEvent]:
        """Future dividends with ``0 < t_i ≤ until``, in ex-date order."""
        events = [
            DividendEvent(self.time_to(d.ex_date), d.cash, d.proportional) for d in self.dividends
        ]
        return sorted(
            (e for e in events if SAME_INSTANT < e.t <= until + SAME_INSTANT), key=lambda e: e.t
        )

    def has_dividends(self, until: float) -> bool:
        """True if a discrete dividend goes ex in ``(0, until]``."""
        return bool(self.dividend_events(until))

    def forward_sensitivities(self, t: float) -> ForwardSensitivities:
        """``F(0,t)`` and ``∂F/∂S``, ``∂F/∂r``, ``∂F/∂q`` in closed form (module docstring).

        A parallel shift ``dz`` of the discount curve scales ``G(u)`` by ``e^{dz·u}``, so
        ``∂F/∂r = T·S·A − Σ D_i (T − t_i) B_i``; yield and borrow shifts give the negative.
        """
        events = self.dividend_events(t)
        g_t = self.growth(t)
        prop_after = 1.0  # Π_{t_i < t_j ≤ T}(1 − δ_j), accumulated backwards
        cash_term = 0.0  # Σ D_i B_i
        cash_rate_term = 0.0  # Σ D_i (T − t_i) B_i
        for e in reversed(events):
            b_i = g_t / self.growth(e.t) * prop_after
            cash_term += e.cash * b_i
            cash_rate_term += e.cash * (t - e.t) * b_i
            prop_after *= 1.0 - e.proportional
        a = g_t * prop_after
        forward = self.spot * a - cash_term
        d_rate = t * self.spot * a - cash_rate_term
        return ForwardSensitivities(forward=forward, d_spot=a, d_rate=d_rate, d_yield=-d_rate)

    def forward(self, t: float) -> float:
        """Forward price ``F(0, t)`` including discrete dividends (module docstring)."""
        if not self.dividends:
            return self.spot * self.growth(t)
        return self.forward_sensitivities(t).forward

    def escrowed_cash(self, t: float, maturity: float) -> float:
        """Escrowed cash ``E_t`` of dividends in ``(t, maturity]`` (module docstring)."""
        total, g_t, prop = 0.0, self.growth(t), 1.0
        for e in self.dividend_events(maturity):
            if e.t <= t + SAME_INSTANT:
                continue
            prop *= 1.0 - e.proportional
            total += e.cash * g_t / self.growth(e.t) / prop
        return total

    def proportional_factor(self, t: float, maturity: float) -> float:
        """``Π_{t < t_j ≤ maturity}(1 − δ_j)``."""
        factor = 1.0
        for e in self.dividend_events(maturity):
            if e.t > t + SAME_INSTANT:
                factor *= 1.0 - e.proportional
        return factor
