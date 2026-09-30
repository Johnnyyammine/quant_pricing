"""Phase 0 stub: discounted forward intrinsic value.

``V = P_r(0, T) · max(ω·(F(0, T) − K), 0)``, the ``σ → 0`` limit of Black–Scholes. It exists only
to wire the UI end to end before the analytic Black–Scholes pricer lands in Phase 1, and will be
removed then.
"""

from __future__ import annotations

from typing import ClassVar

from engine.instruments.base import Instrument
from engine.instruments.vanilla import EuropeanOption
from engine.market.market_data import MarketData
from engine.methods.base import MethodOutput, PricingMethod
from engine.models.base import Model
from engine.models.black_scholes import BlackScholesMerton
from engine.settings import PricingSettings


class ForwardIntrinsic(PricingMethod):
    """Discounted forward intrinsic value (stub)."""

    name: ClassVar[str] = "forward_intrinsic"
    label: ClassVar[str] = "Forward intrinsic (stub)"

    def supports(self, instrument: Instrument, model: Model) -> bool:
        """European options under BSM."""
        return isinstance(instrument, EuropeanOption) and isinstance(model, BlackScholesMerton)

    def evaluate(
        self,
        instrument: Instrument,
        market: MarketData,
        model: Model,
        settings: PricingSettings,
    ) -> MethodOutput:
        """``P_r(0, T) · max(ω·(F − K), 0)``."""
        assert isinstance(instrument, EuropeanOption)
        t = market.time_to(instrument.expiry)
        omega = instrument.option_type.omega
        value = market.df(t) * max(omega * (market.forward(t) - instrument.strike), 0.0)
        return MethodOutput(value=value, details={"time_to_expiry_years": t})
