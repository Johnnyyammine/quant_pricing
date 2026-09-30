"""Discrete dividends.

A dividend goes ex at the open of its ex-date: on that date ``S → S·(1 − δ) − D`` (proportional part
first, then cash). A dividend is *future* when ``0 < t_i`` (ex-date after the valuation date) and it
affects an option expiring at ``T`` when ``t_i ≤ T``. Payment is assumed on the ex-date (no payment
lag).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from engine.errors import MarketDataError


@dataclass(frozen=True, slots=True)
class Dividend:
    """A discrete dividend.

    Attributes:
        ex_date: Ex-dividend date.
        cash: Cash amount ``D`` per share, in the underlying's currency.
        proportional: Proportional part ``δ`` (fraction of spot, ``0 ≤ δ < 1``).

    """

    ex_date: dt.date
    cash: float = 0.0
    proportional: float = 0.0

    def __post_init__(self) -> None:
        if self.cash < 0.0 or not 0.0 <= self.proportional < 1.0:
            raise MarketDataError(
                f"dividend on {self.ex_date}: cash must be ≥ 0 and 0 ≤ proportional < 1"
            )


@dataclass(frozen=True, slots=True)
class DividendEvent:
    """A dividend expressed in year fractions from the valuation date."""

    t: float
    cash: float
    proportional: float
