"""Rate curves in continuously compounded zero-rate form.

A curve maps a year fraction ``t`` (from the valuation date, ACT/365F) to a discount factor
``P(0, t) = exp(−z(t)·t)``. The same abstraction carries the discount curve, the repo/borrow
spread curve and the continuous dividend-yield curve; see ``docs/conventions.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class RateCurve(Protocol):
    """Continuously compounded zero-rate curve."""

    def df(self, t: float) -> float:
        """Discount factor ``exp(−z(t)·t)`` for year fraction ``t``."""
        ...

    def zero_rate(self, t: float) -> float:
        """Continuously compounded zero rate ``z(t)``."""
        ...

    def shifted(self, dz: float) -> RateCurve:
        """Curve with every zero rate shifted in parallel by ``dz``."""
        ...


@dataclass(frozen=True, slots=True)
class FlatRateCurve:
    """Flat continuously compounded curve: ``P(0, t) = exp(−r·t)``."""

    rate: float

    def df(self, t: float) -> float:
        """Discount factor ``exp(−r·t)``."""
        return math.exp(-self.rate * t)

    def zero_rate(self, t: float) -> float:
        """Zero rate, constant ``r``."""
        return self.rate

    def shifted(self, dz: float) -> FlatRateCurve:
        """Flat curve at ``r + dz``."""
        return FlatRateCurve(self.rate + dz)
