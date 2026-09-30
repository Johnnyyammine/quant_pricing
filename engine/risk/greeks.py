"""Generic bump-and-revalue greeks by central finite differences.

Given a revaluation function ``V(market)``, the greeks below are computed with bump sizes from
:class:`~engine.settings.BumpSettings` (``h_S = spot_rel·S``, ``h_σ``, ``h_r``, ``h_t = days/365``):

* Δ = [V(S+h_S) − V(S−h_S)] / 2h_S
* Γ = [V(S+h_S) − 2V + V(S−h_S)] / h_S²
* ν = [V(σ+h_σ) − V(σ−h_σ)] / 2h_σ
* volga = [V(σ+h_σ) − 2V + V(σ−h_σ)] / h_σ²
* vanna = [V(++) − V(+−) − V(−+) + V(−−)] / 4h_S h_σ
* ρ, φ = central differences in the discount / dividend-yield zero rate
* Θ = ∂V/∂t = [V(t+h_t) − V(t−h_t)] / 2h_t (time rolled by moving the valuation date)
* charm = ∂Δ/∂t, central in both spot and time

All are ``O(h²)`` accurate. When the instrument matures within ``h_t``, theta and charm fall back to
a one-sided difference (``O(h)``) that does not step past maturity, and a warning is returned.
Revaluations are cached so shared points (e.g. S±h for Δ and Γ) are priced once.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Collection
from dataclasses import dataclass, field

from engine.dates import DAYS_PER_YEAR_ACT365F
from engine.market.market_data import MarketData
from engine.results import Greek
from engine.risk import bumps
from engine.settings import BumpSettings

# (spot, vol, rate, dividend yield, time) step multipliers, each in {-1, 0, +1}
_Point = tuple[int, int, int, int, int]
_BASE: _Point = (0, 0, 0, 0, 0)


@dataclass(slots=True)
class _Revaluer:
    market: MarketData
    revalue: Callable[[MarketData], float]
    bumps: BumpSettings
    cache: dict[_Point, float] = field(default_factory=dict)

    def __call__(self, point: _Point) -> float:
        if point not in self.cache:
            s, v, r, q, t = point
            m = self.market
            if s:
                m = bumps.bump_spot_rel(m, s * self.bumps.spot_rel)
            if v:
                m = bumps.bump_vol(m, v * self.bumps.vol_abs)
            if r:
                m = bumps.bump_rate(m, r * self.bumps.rate_abs)
            if q:
                m = bumps.bump_dividend_yield(m, q * self.bumps.rate_abs)
            if t:
                m = bumps.roll_valuation_date(m, t * self.bumps.time_days)
            self.cache[point] = self.revalue(m)
        return self.cache[point]


@dataclass(frozen=True, slots=True)
class BumpGreeks:
    """Result of :func:`bump_greeks`: pure-unit greeks, revaluation count, warnings."""

    values: dict[Greek, float]
    revaluations: int
    warnings: tuple[str, ...]


def bump_greeks(
    market: MarketData,
    maturity: dt.date,
    revalue: Callable[[MarketData], float],
    greeks: Collection[Greek],
    settings: BumpSettings,
    base_value: float,
) -> BumpGreeks:
    """Compute ``greeks`` by central differences of ``revalue`` around ``market``.

    Args:
        market: Base market.
        maturity: Instrument maturity, used to keep time rolls from stepping past it.
        revalue: Unit price as a function of the market.
        greeks: Which greeks to compute.
        settings: Bump sizes.
        base_value: ``revalue(market)``, already computed by the caller.

    """
    rv = _Revaluer(market, revalue, settings, {_BASE: base_value})
    h_s = settings.spot_rel * market.spot
    h_v = settings.vol_abs
    h_r = settings.rate_abs
    h_t = settings.time_days / DAYS_PER_YEAR_ACT365F
    warnings: list[str] = []

    # Time stencil: central if both rolls stay on or before maturity, else backward only.
    days_left = (maturity - market.valuation_date).days
    if days_left >= settings.time_days:
        t_up, t_dn, t_width = 1, -1, 2.0 * h_t
    else:
        t_up, t_dn, t_width = 0, -1, h_t
        if Greek.THETA in greeks or Greek.CHARM in greeks:
            warnings.append("theta/charm: maturity within the time bump; one-sided difference used")

    def delta_at(t: int) -> float:
        return (rv((1, 0, 0, 0, t)) - rv((-1, 0, 0, 0, t))) / (2.0 * h_s)

    out: dict[Greek, float] = {}
    for g in greeks:
        match g:
            case Greek.DELTA:
                out[g] = delta_at(0)
            case Greek.GAMMA:
                out[g] = (rv((1, 0, 0, 0, 0)) - 2.0 * base_value + rv((-1, 0, 0, 0, 0))) / h_s**2
            case Greek.VEGA:
                out[g] = (rv((0, 1, 0, 0, 0)) - rv((0, -1, 0, 0, 0))) / (2.0 * h_v)
            case Greek.VOLGA:
                out[g] = (rv((0, 1, 0, 0, 0)) - 2.0 * base_value + rv((0, -1, 0, 0, 0))) / h_v**2
            case Greek.VANNA:
                out[g] = (
                    rv((1, 1, 0, 0, 0))
                    - rv((1, -1, 0, 0, 0))
                    - rv((-1, 1, 0, 0, 0))
                    + rv((-1, -1, 0, 0, 0))
                ) / (4.0 * h_s * h_v)
            case Greek.RHO:
                out[g] = (rv((0, 0, 1, 0, 0)) - rv((0, 0, -1, 0, 0))) / (2.0 * h_r)
            case Greek.PHI:
                out[g] = (rv((0, 0, 0, 1, 0)) - rv((0, 0, 0, -1, 0))) / (2.0 * h_r)
            case Greek.THETA:
                out[g] = (rv((0, 0, 0, 0, t_up)) - rv((0, 0, 0, 0, t_dn))) / t_width
            case Greek.CHARM:
                out[g] = (delta_at(t_up) - delta_at(t_dn)) / t_width

    return BumpGreeks(values=out, revaluations=len(rv.cache), warnings=tuple(warnings))
