"""Market-data transformations used by bump-and-revalue risk and scenarios.

Every greek is defined as the derivative of the price along one of these transformations, so the
bump layer works for any instrument without special-casing.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace

from engine.dates import DAYS_PER_YEAR_ACT365F
from engine.market.market_data import MarketData


def bump_spot_rel(market: MarketData, rel: float) -> MarketData:
    """Spot multiplied by ``1 + rel``. Curves and vol surface are unchanged (sticky strike)."""
    return replace(market, spot=market.spot * (1.0 + rel))


def bump_vol(market: MarketData, dvol: float) -> MarketData:
    """Parallel shift of the implied-vol surface by ``dvol`` (absolute, vol units)."""
    return replace(market, vol=market.vol.shifted(dvol))


def bump_rate(market: MarketData, dz: float) -> MarketData:
    """Parallel shift of discount zero rates by ``dz``. Forwards move with ``r``."""
    return replace(market, discount=market.discount.shifted(dz))


def bump_dividend_yield(market: MarketData, dz: float) -> MarketData:
    """Parallel shift of the continuous dividend-yield curve by ``dz``."""
    return replace(market, dividend_yield=market.dividend_yield.shifted(dz))


def roll_valuation_date(market: MarketData, days: int) -> MarketData:
    """Move the valuation date by ``days`` calendar days with the market unchanged by date.

    Spot and implied vols are held fixed; curves realise their forwards
    (``P'(0,t) = P(0,t+h)/P(0,h)``, identity for flat curves); discrete dividends keep their
    ex-dates, so their year fractions shrink by ``h``.
    """
    h = days / DAYS_PER_YEAR_ACT365F
    return replace(
        market,
        valuation_date=market.valuation_date + dt.timedelta(days=days),
        discount=market.discount.rolled(h),
        dividend_yield=market.dividend_yield.rolled(h),
        borrow=market.borrow.rolled(h),
    )
