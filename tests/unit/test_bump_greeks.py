"""Bump-and-revalue framework checked against a quadratic price function.

Central differences are exact (up to rounding) for polynomials of degree ≤ 2 in each bumped
variable, so every greek of the toy price below is known in closed form.
"""

import datetime as dt
from typing import ClassVar

import pytest

from engine.instruments.base import Instrument
from engine.market.market_data import MarketData
from engine.methods.base import MethodOutput, PricingMethod
from engine.models.base import Model
from engine.models.black_scholes import BlackScholesMerton
from engine.pricing import price
from engine.results import Greek, GreekSource
from engine.settings import BumpSettings, PricingSettings

A, B, C, D, E, F, G = 0.3, 2.0, 50.0, 7.0, -3.0, 4.0, 0.8


class QuadraticToy(PricingMethod):
    """V = A S² + B S σ + C σ² + D r + E q + F τ² + G S τ."""

    name: ClassVar[str] = "toy"
    label: ClassVar[str] = "toy"

    def supports(self, instrument: Instrument, model: Model) -> bool:
        return True

    def evaluate(self, instrument, market: MarketData, model, settings) -> MethodOutput:
        s, sig = market.spot, market.vol.vol(1.0, 1.0)
        r, q = market.discount.zero_rate(1.0), market.dividend_yield.zero_rate(1.0)
        tau = market.time_to(instrument.maturity)
        v = A * s * s + B * s * sig + C * sig * sig + D * r + E * q + F * tau * tau + G * s * tau
        return MethodOutput(value=v)


def _exact(market: MarketData, tau: float) -> dict[Greek, float]:
    s, sig = market.spot, market.vol.vol(1.0, 1.0)
    return {
        Greek.DELTA: 2 * A * s + B * sig + G * tau,
        Greek.GAMMA: 2 * A,
        Greek.VEGA: B * s + 2 * C * sig,
        Greek.VOLGA: 2 * C,
        Greek.VANNA: B,
        Greek.RHO: D,
        Greek.PHI: E,
        Greek.THETA: -(2 * F * tau + G * s),  # ∂V/∂t = −∂V/∂τ
        Greek.CHARM: -G,
    }


def test_bump_greeks_exact_on_quadratic(market, call):
    res = price(call, market, BlackScholesMerton(), QuadraticToy())
    tau = market.time_to(call.expiry)
    assert res.greeks is not None
    for g, expected in _exact(market, tau).items():
        assert res.greeks[g] == pytest.approx(expected, rel=1e-7, abs=1e-7), g
        assert res.greeks.sources[g] is GreekSource.BUMP
    assert res.diagnostics.warnings == ()


def test_revaluations_are_shared(market, call):
    res = price(call, market, BlackScholesMerton(), QuadraticToy())
    # base + S± + σ± + (S±,σ±)×4 + r± + q± + t± + (S±,t±)×4 = 19 distinct points
    assert res.diagnostics.revaluations == 19


def test_time_stencil_is_one_sided_at_maturity(market, call):
    from dataclasses import replace

    near = replace(call, expiry=market.valuation_date)  # expires today
    settings = PricingSettings(bumps=BumpSettings(time_days=1))
    res = price(near, market, BlackScholesMerton(), QuadraticToy(), settings)
    assert res.greeks is not None
    # V(τ) − V(τ + h) over h, with τ = 0: −(F h + G S)
    h = 1 / 365
    assert res.greeks[Greek.THETA] == pytest.approx(-(F * h + G * market.spot), rel=1e-7)
    assert res.diagnostics.warnings


def test_bump_sizes_come_from_settings(market, call):
    small = PricingSettings(bumps=BumpSettings(spot_rel=1e-5, vol_abs=1e-5))
    res = price(call, market, BlackScholesMerton(), QuadraticToy(), small)
    assert res.diagnostics.settings is small


def test_expired_instrument_rejected(market, call):
    from dataclasses import replace

    from engine.errors import PricingError

    with pytest.raises(PricingError):
        price(
            replace(call, expiry=market.valuation_date - dt.timedelta(days=1)),
            market,
            BlackScholesMerton(),
            QuadraticToy(),
        )
