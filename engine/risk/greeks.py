"""Generic bump-and-revalue greeks by central finite differences, evaluated on spot ladders.

Given a *ladder* ``L(market, [m₁, …, m_n]) = [V(S·m₁), …, V(S·m_n)]`` (one call may share a PDE
solve or a vectorised tree across all spots), the greeks at spot ``S·m_k`` are, with
``h_S = spot_rel·S·m_k``, ``h_σ``, ``h_r`` and ``h_t = days/365``:

* Δ = [V(S+h_S) − V(S−h_S)] / 2h_S
* Γ = [V(S+h_S) − 2V + V(S−h_S)] / h_S²
* ν = [V(σ+h_σ) − V(σ−h_σ)] / 2h_σ
* volga = [V(σ+h_σ) − 2V + V(σ−h_σ)] / h_σ²
* vanna = [V(++) − V(+−) − V(−+) + V(−−)] / 4h_S h_σ
* ρ, φ = central differences in the discount / dividend-yield zero rate
* Θ = ∂V/∂t = [V(t+h_t) − V(t−h_t)] / 2h_t (valuation-date roll, market unchanged by date)
* charm = ∂Δ/∂t, central in both spot and time

All are ``O(h²)``. When the instrument matures within ``h_t``, Θ and charm fall back to a
one-sided difference that does not step past maturity, and a warning is returned. Stencil points
are grouped by their non-spot bumps, so each group is one ladder call: all nine greeks need nine
market revaluations regardless of how many spots are requested.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass

from engine.dates import DAYS_PER_YEAR_ACT365F
from engine.market.market_data import MarketData
from engine.results import Greek
from engine.risk import bumps
from engine.settings import BumpSettings

Ladder = Callable[[MarketData, Sequence[float]], Sequence[float]]
"""``(market, spot multipliers) → unit values at spot·m``."""

# (spot, vol, rate, dividend yield, time) step multipliers, each in {-1, 0, +1}
_Point = tuple[int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class BumpGreeks:
    """Pure-unit greeks at one spot, number of stencil points, warnings."""

    values: dict[Greek, float]
    revaluations: int
    warnings: tuple[str, ...]


def _stencil(greek: Greek, t_up: int, t_dn: int) -> list[_Point]:
    match greek:
        case Greek.DELTA:
            return [(1, 0, 0, 0, 0), (-1, 0, 0, 0, 0)]
        case Greek.GAMMA:
            return [(1, 0, 0, 0, 0), (0, 0, 0, 0, 0), (-1, 0, 0, 0, 0)]
        case Greek.VEGA:
            return [(0, 1, 0, 0, 0), (0, -1, 0, 0, 0)]
        case Greek.VOLGA:
            return [(0, 1, 0, 0, 0), (0, 0, 0, 0, 0), (0, -1, 0, 0, 0)]
        case Greek.VANNA:
            return [(1, 1, 0, 0, 0), (1, -1, 0, 0, 0), (-1, 1, 0, 0, 0), (-1, -1, 0, 0, 0)]
        case Greek.RHO:
            return [(0, 0, 1, 0, 0), (0, 0, -1, 0, 0)]
        case Greek.PHI:
            return [(0, 0, 0, 1, 0), (0, 0, 0, -1, 0)]
        case Greek.THETA:
            return [(0, 0, 0, 0, t_up), (0, 0, 0, 0, t_dn)]
        case Greek.CHARM:
            return [
                (1, 0, 0, 0, t_up),
                (-1, 0, 0, 0, t_up),
                (1, 0, 0, 0, t_dn),
                (-1, 0, 0, 0, t_dn),
            ]


def _market_for(market: MarketData, v: int, r: int, q: int, t: int, b: BumpSettings) -> MarketData:
    m = market
    if v:
        m = bumps.bump_vol(m, v * b.vol_abs)
    if r:
        m = bumps.bump_rate(m, r * b.rate_abs)
    if q:
        m = bumps.bump_dividend_yield(m, q * b.rate_abs)
    if t:
        m = bumps.roll_valuation_date(m, t * b.time_days)
    return m


def ladder_bump_greeks(
    market: MarketData,
    maturity: dt.date,
    ladder: Ladder,
    greeks: Collection[Greek],
    settings: BumpSettings,
    multipliers: Sequence[float],
) -> list[BumpGreeks]:
    """Central-difference ``greeks`` at each spot ``market.spot·m`` (see module docstring)."""
    h_v, h_r = settings.vol_abs, settings.rate_abs
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

    points = sorted({p for g in greeks for p in _stencil(g, t_up, t_dn)} | {(0, 0, 0, 0, 0)})
    groups: dict[tuple[int, int, int, int], list[int]] = {}
    for s, v, r, q, t in points:
        groups.setdefault((v, r, q, t), []).append(s)

    # One ladder call per non-spot group, covering every requested spot and spot sign.
    values: dict[tuple[int, _Point], float] = {}
    for (v, r, q, t), signs in groups.items():
        spot_mults = [m * (1.0 + s * settings.spot_rel) for m in multipliers for s in signs]
        out = ladder(_market_for(market, v, r, q, t, settings), spot_mults)
        it = iter(out)
        for k in range(len(multipliers)):
            for s in signs:
                values[(k, (s, v, r, q, t))] = next(it)

    results: list[BumpGreeks] = []
    for k, m in enumerate(multipliers):
        h_s = settings.spot_rel * market.spot * m

        def val(p: _Point, k: int = k) -> float:
            return values[(k, p)]

        def delta_at(t: int, h_s: float = h_s, val: Callable[[_Point], float] = val) -> float:
            return (val((1, 0, 0, 0, t)) - val((-1, 0, 0, 0, t))) / (2.0 * h_s)

        base = val((0, 0, 0, 0, 0))
        out_k: dict[Greek, float] = {}
        for g in greeks:
            match g:
                case Greek.DELTA:
                    out_k[g] = delta_at(0)
                case Greek.GAMMA:
                    out_k[g] = (val((1, 0, 0, 0, 0)) - 2.0 * base + val((-1, 0, 0, 0, 0))) / h_s**2
                case Greek.VEGA:
                    out_k[g] = (val((0, 1, 0, 0, 0)) - val((0, -1, 0, 0, 0))) / (2.0 * h_v)
                case Greek.VOLGA:
                    out_k[g] = (val((0, 1, 0, 0, 0)) - 2.0 * base + val((0, -1, 0, 0, 0))) / h_v**2
                case Greek.VANNA:
                    out_k[g] = (
                        val((1, 1, 0, 0, 0))
                        - val((1, -1, 0, 0, 0))
                        - val((-1, 1, 0, 0, 0))
                        + val((-1, -1, 0, 0, 0))
                    ) / (4.0 * h_s * h_v)
                case Greek.RHO:
                    out_k[g] = (val((0, 0, 1, 0, 0)) - val((0, 0, -1, 0, 0))) / (2.0 * h_r)
                case Greek.PHI:
                    out_k[g] = (val((0, 0, 0, 1, 0)) - val((0, 0, 0, -1, 0))) / (2.0 * h_r)
                case Greek.THETA:
                    out_k[g] = (val((0, 0, 0, 0, t_up)) - val((0, 0, 0, 0, t_dn))) / t_width
                case Greek.CHARM:
                    out_k[g] = (delta_at(t_up) - delta_at(t_dn)) / t_width
        results.append(BumpGreeks(values=out_k, revaluations=len(points), warnings=tuple(warnings)))
    return results


def bump_greeks(
    market: MarketData,
    maturity: dt.date,
    ladder: Ladder,
    greeks: Collection[Greek],
    settings: BumpSettings,
) -> BumpGreeks:
    """Central-difference ``greeks`` at the market's own spot."""
    return ladder_bump_greeks(market, maturity, ladder, greeks, settings, [1.0])[0]
