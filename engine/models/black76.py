"""Black (1976) model for options on forwards and futures.

The market's ``spot`` field holds the forward (futures) price ``F`` for the option expiry, which
follows a driftless lognormal ``dF/F = σ dW`` under the pricing measure. Dividend-yield and borrow
curves and discrete dividends do not enter (they are in the quoted forward); the discount curve
discounts the payoff. Hence ``ρ = −T·V`` (the forward is
held fixed when rates move) and ``φ = 0``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from engine.market.market_data import ForwardSensitivities, MarketData
from engine.models.base import Model


@dataclass(frozen=True, slots=True)
class Black76(Model):
    """Lognormal forward with volatility read from the market vol surface."""

    name: ClassVar[str] = "black76"

    def forward(self, market: MarketData, t: float) -> float:
        """The quoted forward: ``market.spot``."""
        return market.spot

    def forward_sensitivities(self, market: MarketData, t: float) -> ForwardSensitivities:
        """``∂F/∂F = 1``; the quoted forward does not move with rates or yields."""
        return ForwardSensitivities(forward=market.spot, d_spot=1.0, d_rate=0.0, d_yield=0.0)
