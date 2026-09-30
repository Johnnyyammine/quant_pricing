"""Implied volatility surfaces.

A surface returns the Black implied volatility ``σ(K, T)`` for absolute strike ``K`` and year
fraction ``T``. Vol bumps are absolute (``0.01`` = 1 vol point).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from engine.errors import MarketDataError


@runtime_checkable
class VolSurface(Protocol):
    """Black implied volatility surface."""

    def vol(self, strike: float, t: float) -> float:
        """Implied volatility for strike ``strike`` and expiry year fraction ``t``."""
        ...

    def shifted(self, dvol: float) -> VolSurface:
        """Surface with every implied vol shifted in parallel by ``dvol``."""
        ...


@dataclass(frozen=True, slots=True)
class FlatVolSurface:
    """Constant implied volatility ``σ`` across strikes and expiries."""

    sigma: float

    def __post_init__(self) -> None:
        if not self.sigma > 0.0:
            raise MarketDataError(f"volatility must be positive, got {self.sigma}")

    def vol(self, strike: float, t: float) -> float:
        """Implied volatility, constant ``σ``."""
        return self.sigma

    def shifted(self, dvol: float) -> FlatVolSurface:
        """Flat surface at ``σ + dvol``."""
        return FlatVolSurface(self.sigma + dvol)
