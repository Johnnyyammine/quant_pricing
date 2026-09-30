"""Shared check: closed-form (or method) greeks against Richardson-extrapolated bump greeks.

Tolerance policy (CLAUDE.md): the O(h⁴) Richardson residual must be small next to the O(h²)
correction it removed (|g(h) − g(h/2)|), plus a round-off floor ε·(|V| + S)/stencil and a 1e-6
relative floor for points where the h² coefficient vanishes by coincidence. A formula error does
not shrink with h and fails.
"""

import sys
from collections.abc import Collection
from dataclasses import replace

from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.methods.base import PricingMethod
from engine.models.base import Model
from engine.pricing import price
from engine.results import Greek
from engine.settings import BumpSettings, PricingSettings

EPS = sys.float_info.epsilon
SPACE_GREEKS = (
    Greek.DELTA,
    Greek.GAMMA,
    Greek.VEGA,
    Greek.VOLGA,
    Greek.VANNA,
    Greek.RHO,
    Greek.PHI,
)
TIME_GREEKS = (Greek.THETA, Greek.CHARM)


def _bumped(settings: PricingSettings, **bumps) -> PricingSettings:
    return replace(settings, bumps=BumpSettings(**bumps), force_bump_greeks=True)


def assert_greeks_match_bumps(
    instrument: Instrument,
    market: MarketData,
    model: Model,
    method: PricingMethod,
    settings: PricingSettings | None = None,
    greeks: Collection[Greek] = tuple(Greek),
) -> None:
    settings = settings or PricingSettings()
    analytic = price(instrument, market, model, method, settings).greeks
    assert analytic is not None
    s = market.spot
    v = price(instrument, market, model, method, settings, greeks=()).price
    h1 = dict(spot_rel=2e-3, vol_abs=2e-3, rate_abs=2e-4, time_days=1)
    h2 = dict(spot_rel=1e-3, vol_abs=1e-3, rate_abs=1e-4, time_days=1)
    g1 = price(instrument, market, model, method, _bumped(settings, **h1)).greeks
    g2 = price(instrument, market, model, method, _bumped(settings, **h2)).greeks
    assert g1 is not None
    assert g2 is not None
    hs, hv, hr = h2["spot_rel"] * s, h2["vol_abs"], h2["rate_abs"]
    denominator = {
        Greek.DELTA: hs,
        Greek.GAMMA: hs * hs,
        Greek.VEGA: hv,
        Greek.VOLGA: hv * hv,
        Greek.VANNA: hs * hv,
        Greek.RHO: hr,
        Greek.PHI: hr,
    }
    for g in SPACE_GREEKS:
        if g not in greeks:
            continue
        richardson = (4 * g2[g] - g1[g]) / 3
        rounding = 256 * EPS * (abs(v) + s) / denominator[g]
        tol = 1e-6 * abs(analytic[g]) + 0.05 * abs(g1[g] - g2[g]) + rounding
        assert abs(richardson - analytic[g]) <= tol, (g, richardson, analytic[g], tol)

    if not any(g in greeks for g in TIME_GREEKS):
        return
    # Time: Richardson over 1-day and 2-day rolls; a finer spot bump inside charm so its own
    # O(h_S²) error does not dominate.
    fine_spot = 1e-4
    t1, t2 = (
        price(
            instrument, market, model, method, _bumped(settings, spot_rel=fine_spot, time_days=d)
        ).greeks
        for d in (1, 2)
    )
    assert t1 is not None
    assert t2 is not None
    h_t = 1 / 365
    for g, den in ((Greek.THETA, h_t), (Greek.CHARM, h_t * fine_spot * s)):
        if g not in greeks:
            continue
        richardson = (4 * t1[g] - t2[g]) / 3
        rounding = 256 * EPS * (abs(v) + s) / den
        tol = 1e-6 * abs(analytic[g]) + 0.05 * abs(t1[g] - t2[g]) + rounding
        assert abs(richardson - analytic[g]) <= tol, (g, richardson, analytic[g], tol)
