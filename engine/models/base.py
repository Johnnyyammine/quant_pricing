"""Model base class: the dynamics of the underlying, with its parameters."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from engine.market.market_data import ForwardSensitivities, MarketData


@dataclass(frozen=True, slots=True)
class Model(ABC):
    """Base for all models. Subclasses are frozen dataclasses holding model parameters."""

    name: ClassVar[str]

    def forward(self, market: MarketData, t: float) -> float:
        """Forward of the modelled underlying for expiry ``t``. Default: the market forward."""
        return market.forward(t)

    def forward_sensitivities(self, market: MarketData, t: float) -> ForwardSensitivities:
        """Forward and its derivatives to spot, rates and yield. Default: the market's."""
        return market.forward_sensitivities(t)
