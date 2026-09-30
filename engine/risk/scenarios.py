"""Market shocks and full-revaluation grids (profiles, spot × vol heatmaps).

A :class:`MarketShock` composes the same transformations the bump layer uses, so scenario PnL and
greeks are consistent by construction. All revaluations go through :func:`engine.pricing.price`,
so every instrument and method is supported without special-casing.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from engine.errors import MarketDataError
from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.methods.base import PricingMethod
from engine.models.base import Model
from engine.pricing import price
from engine.results import Greek, PricingResult
from engine.risk import bumps
from engine.settings import PricingSettings


@dataclass(frozen=True, slots=True)
class MarketShock:
    """A joint market move, applied in the order: time roll, spot, vol, rates.

    Attributes:
        spot_rel: Relative spot move (``0.1`` = +10%).
        vol_abs: Parallel implied-vol shift in vol units (``0.01`` = +1 vol point).
        rate_abs: Parallel discount zero-rate shift (``1e-4`` = +1 bp).
        days: Valuation-date roll in calendar days (spot, vols, rates otherwise fixed).

    """

    spot_rel: float = 0.0
    vol_abs: float = 0.0
    rate_abs: float = 0.0
    days: int = 0

    def apply(self, market: MarketData) -> MarketData:
        """Shocked market. Raises :class:`MarketDataError` if the shock leaves the domain."""
        m = market
        if self.days:
            m = bumps.roll_valuation_date(m, self.days)
        if self.spot_rel:
            m = bumps.bump_spot_rel(m, self.spot_rel)
        if self.vol_abs:
            m = bumps.bump_vol(m, self.vol_abs)
        if self.rate_abs:
            m = bumps.bump_rate(m, self.rate_abs)
        return m


def revalue(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
    shock: MarketShock,
    greeks: Collection[Greek] = (),
) -> PricingResult:
    """Full revaluation of ``instrument`` under ``shock``."""
    return price(instrument, shock.apply(market), model, method, settings, greeks=greeks)


def spot_value_grid(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
    spot_shifts: Sequence[float],
    vol_shifts: Sequence[float],
    days: int = 0,
) -> list[list[float]]:
    """Unit values on a ``vol_shifts × spot_shifts`` grid (rows: vol), after rolling ``days``.

    Cells whose shock leaves the market domain (e.g. a negative vol) are ``nan``.
    """
    rows: list[list[float]] = []
    for dv in vol_shifts:
        row: list[float] = []
        for ds in spot_shifts:
            shock = MarketShock(spot_rel=ds, vol_abs=dv, days=days)
            try:
                row.append(revalue(instrument, market, model, method, settings, shock).price)
            except MarketDataError:
                row.append(math.nan)
        rows.append(row)
    return rows


def spot_profile(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
    spot_shifts: Sequence[float],
    days: int = 0,
    greeks: Collection[Greek] = tuple(Greek),
) -> list[tuple[MarketData, PricingResult]]:
    """Price and greeks across relative spot shifts, after rolling ``days``."""
    out = []
    for ds in spot_shifts:
        shocked = MarketShock(spot_rel=ds, days=days).apply(market)
        out.append((shocked, price(instrument, shocked, model, method, settings, greeks=greeks)))
    return out


def time_profile(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings,
    roll_days: Sequence[int],
    spot_shift: float = 0.0,
    greeks: Collection[Greek] = tuple(Greek),
) -> list[tuple[MarketData, PricingResult]]:
    """Price and greeks as the valuation date rolls forward, at a fixed relative spot shift."""
    out = []
    for d in roll_days:
        shocked = MarketShock(spot_rel=spot_shift, days=d).apply(market)
        out.append((shocked, price(instrument, shocked, model, method, settings, greeks=greeks)))
    return out
