"""Closed-form pricing of European vanillas and cash-or-nothing digitals under BSM and Black-76.

Inputs come from the model's forward and its sensitivities (``Model.forward_sensitivities``), the
discount factor and the implied vol at the option's strike and expiry; see
:mod:`engine.methods.black_formulas`. Discrete dividends enter through the forward, which is exact
under the escrowed treatment. Under the ``SPOT`` treatment with cash dividends before expiry there
is no closed form and the method raises :class:`UnsupportedCombinationError` (use the PDE).

Θ and charm are closed form only for time-homogeneous market data (flat curves, flat vol surface,
no discrete dividends before expiry); otherwise they are left to the bump layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from engine.errors import UnsupportedCombinationError
from engine.instruments.base import Instrument
from engine.instruments.vanilla import DigitalOption, EuropeanOption
from engine.market.curves import FlatRateCurve
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.methods.base import MethodOutput, PricingMethod
from engine.methods.black_formulas import (
    BlackInputs,
    digital_greeks,
    digital_price,
    vanilla_greeks,
    vanilla_price,
)
from engine.models.base import Model
from engine.models.black76 import Black76
from engine.models.black_scholes import BlackScholesMerton, DividendTreatment
from engine.results import Greek
from engine.settings import PricingSettings

Priceable = EuropeanOption | DigitalOption


def _time_homogeneous(market: MarketData, t: float, model: Model) -> bool:
    curves = (market.discount, market.dividend_yield, market.borrow)
    flat = all(isinstance(c, FlatRateCurve) for c in curves) and isinstance(
        market.vol, FlatVolSurface
    )
    return flat and (isinstance(model, Black76) or not market.has_dividends(t))


def black_inputs(option: Priceable, market: MarketData, model: Model) -> BlackInputs:
    """Forward-based Black inputs for ``option`` under ``model``."""
    t = max(market.time_to(option.expiry), 0.0)
    if (
        isinstance(model, BlackScholesMerton)
        and model.dividend_treatment is DividendTreatment.SPOT
        and any(e.cash > 0.0 for e in market.dividend_events(t))
    ):
        raise UnsupportedCombinationError(
            "no closed form under the spot-jump dividend treatment with cash dividends before "
            "expiry: use the PDE method, or the escrowed treatment"
        )
    fs = model.forward_sensitivities(market, t)
    r = market.discount.zero_rate(t)
    carry: float | None = None
    if _time_homogeneous(market, t, model):
        carry = (
            0.0
            if isinstance(model, Black76)
            else r - market.dividend_yield.zero_rate(t) - market.borrow.zero_rate(t)
        )
    return BlackInputs(
        forward=fs.forward,
        strike=option.strike,
        t=t,
        sigma=market.vol.vol(option.strike, t),
        discount=market.df(t),
        omega=option.option_type.omega,
        d_spot=fs.d_spot,
        d_rate=fs.d_rate,
        d_yield=fs.d_yield,
        rate=r,
        carry=carry,
    )


class AnalyticBlack(PricingMethod):
    """Closed-form Black–Scholes–Merton / Black-76 for European vanillas and digitals."""

    name: ClassVar[str] = "analytic"
    label: ClassVar[str] = "Analytic (closed form)"

    def supports(self, instrument: Instrument, model: Model) -> bool:
        """European vanillas and cash-or-nothing digitals under BSM or Black-76."""
        return isinstance(instrument, EuropeanOption | DigitalOption) and isinstance(
            model, BlackScholesMerton | Black76
        )

    def evaluate(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> MethodOutput:
        """Unit price and Black diagnostics (σ, F, D, τ, σ√T, d₁, d₂)."""
        assert isinstance(instrument, EuropeanOption | DigitalOption)
        p = black_inputs(instrument, market, model)
        details: dict[str, float | int | str] = {
            "sigma": p.sigma,
            "forward": p.forward,
            "discount_factor": p.discount,
            "time_to_expiry_years": p.t,
        }
        if p.t > 0.0:
            d1, d2 = p.d1_d2()
            details |= {"stdev": p.stdev, "d1": d1, "d2": d2}
        if isinstance(instrument, DigitalOption):
            return MethodOutput(value=digital_price(p, instrument.payout), details=details)
        return MethodOutput(value=vanilla_price(p), details=details)

    def analytic_greeks(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> Mapping[Greek, float]:
        """All nine greeks; Θ and charm only for time-homogeneous market data."""
        assert isinstance(instrument, EuropeanOption | DigitalOption)
        p = black_inputs(instrument, market, model)
        if isinstance(instrument, DigitalOption):
            return digital_greeks(p, digital_price(p, instrument.payout), instrument.payout)
        return vanilla_greeks(p, vanilla_price(p))
