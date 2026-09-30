"""Black–Scholes–Merton model.

Under the pricing measure ``dS_t / S_t = (r − q − b) dt + σ dW_t`` with the volatility taken from
the market's implied-vol surface at the instrument's strike and expiry. The model carries no
parameters of its own: all inputs are market data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from engine.models.base import Model


@dataclass(frozen=True, slots=True)
class BlackScholesMerton(Model):
    """Lognormal dynamics with volatility read from the market vol surface."""

    name: ClassVar[str] = "bsm"
