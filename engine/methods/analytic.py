"""Closed-form pricing of European options under BSM and Black-76.

Maps ``(EuropeanOption, MarketData, model)`` to :class:`BlackInputs` using zero rates to expiry:
``r = z_r(T)``; for BSM ``μ = r − z_q(T) − z_b(T)``, for Black-76 ``X = F`` (``market.spot``)
and ``μ = 0``. The implied vol is read at the option's strike and expiry.

All nine greeks are closed form. Θ and charm assume time-homogeneous market data (flat curves and
a flat vol surface); otherwise they are omitted here and the bump layer computes them by rolling
the valuation date.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import ClassVar

from engine.instruments.base import Instrument
from engine.instruments.vanilla import EuropeanOption
from engine.market.curves import FlatRateCurve
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.base import MethodOutput, PricingMethod
from engine.methods.black_formulas import BlackInputs, CarryModel, black_greeks, black_price
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton
from engine.results import Greek
from engine.settings import PricingSettings


def black_inputs(option: EuropeanOption, market: MarketData, model: Model) -> BlackInputs:
    """Generalised Black inputs for ``option`` under ``model`` (BSM or Black-76)."""
    t = max(market.time_to(option.expiry), 0.0)
    r = market.discount.zero_rate(t)
    sigma = market.vol.vol(option.strike, t)
    if isinstance(model, Black76):
        carry, carry_model = 0.0, CarryModel.FORWARD
    else:
        carry = r - market.dividend_yield.zero_rate(t) - market.borrow.zero_rate(t)
        carry_model = CarryModel.SPOT
    return BlackInputs(
        underlying=market.spot,
        strike=option.strike,
        t=t,
        sigma=sigma,
        rate=r,
        carry=carry,
        omega=option.option_type.omega,
        carry_model=carry_model,
    )


def _time_homogeneous(market: MarketData) -> bool:
    curves = (market.discount, market.dividend_yield, market.borrow)
    return all(isinstance(c, FlatRateCurve) for c in curves) and isinstance(
        market.vol, FlatVolSurface
    )


class AnalyticBlack(PricingMethod):
    """Closed-form Black–Scholes–Merton / Black-76 for European options."""

    name: ClassVar[str] = "analytic"
    label: ClassVar[str] = "Analytic (closed form)"

    def supports(self, instrument: Instrument, model: Model) -> bool:
        """European options under BSM or Black-76."""
        return isinstance(instrument, EuropeanOption) and isinstance(
            model, BlackScholesMerton | Black76
        )

    def evaluate(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> MethodOutput:
        """Unit price and Black diagnostics (σ, F, D, d₁, d₂)."""
        assert isinstance(instrument, EuropeanOption)
        p = black_inputs(instrument, market, model)
        details: dict[str, float | int | str] = {
            "sigma": p.sigma,
            "forward": p.forward,
            "discount_factor": p.discount,
            "time_to_expiry_years": p.t,
        }
        if p.t > 0.0:
            s = p.stdev
            d1 = math.log(p.forward / p.strike) / s + 0.5 * s
            details |= {"stdev": s, "d1": d1, "d2": d1 - s}
        return MethodOutput(value=black_price(p), details=details)

    def analytic_greeks(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> Mapping[Greek, float]:
        """All nine greeks; Θ and charm only for time-homogeneous market data."""
        assert isinstance(instrument, EuropeanOption)
        p = black_inputs(instrument, market, model)
        greeks = black_greeks(p, black_price(p))
        if not _time_homogeneous(market):
            del greeks[Greek.THETA], greeks[Greek.CHARM]
        return greeks
