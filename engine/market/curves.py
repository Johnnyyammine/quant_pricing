"""Rate curves in continuously compounded zero-rate form.

A curve maps a year fraction ``t`` (from the valuation date, ACT/365F) to a discount factor
``P(0, t) = exp(−z(t)·t)``. The same abstraction carries the discount curve, the repo/borrow
spread curve and the continuous dividend-yield curve; see ``docs/conventions.md``.

Rolling the valuation date by ``h`` years realises the forwards: ``P'(0, t) = P(0, t + h)/P(0, h)``
(the market is unchanged by calendar date). For a flat curve this is the identity.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from engine.errors import MarketDataError


@runtime_checkable
class RateCurve(Protocol):
    """Continuously compounded zero-rate curve."""

    def df(self, t: float) -> float:
        """Discount factor ``exp(−z(t)·t)`` for year fraction ``t``."""
        ...

    def zero_rate(self, t: float) -> float:
        """Continuously compounded zero rate ``z(t)`` (``t = 0``: instantaneous forward)."""
        ...

    def instantaneous_forward(self, t: float) -> float:
        """``f(t) = −∂ ln P(0, t)/∂t``."""
        ...

    def shifted(self, dz: float) -> RateCurve:
        """Curve with every zero rate shifted in parallel by ``dz``."""
        ...

    def rolled(self, h: float) -> RateCurve:
        """Curve seen from ``h`` years later with forwards realised: ``P(0,t+h)/P(0,h)``."""
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

    def instantaneous_forward(self, t: float) -> float:
        """Forward rate, constant ``r``."""
        return self.rate

    def shifted(self, dz: float) -> FlatRateCurve:
        """Flat curve at ``r + dz``."""
        return FlatRateCurve(self.rate + dz)

    def rolled(self, h: float) -> FlatRateCurve:
        """A flat curve is invariant under rolling."""
        return self


@dataclass(frozen=True, slots=True)
class ZeroCurve:
    """Pillar zero rates with log-linear discount-factor interpolation.

    ``ln P(0, t)`` is linear between ``(0, 0)`` and the pillars ``(t_i, −z_i·t_i)``, so
    instantaneous forwards are piecewise flat. Before the first pillar the zero rate is ``z_1``;
    beyond the last pillar the last forward is extended. A parallel shift of every ``z_i`` by
    ``dz`` shifts ``z(t)`` by exactly ``dz`` for every ``t``.

    Attributes:
        times: Pillar year fractions from the valuation date, strictly increasing, positive.
        zero_rates: Continuously compounded zero rates at the pillars.

    """

    times: tuple[float, ...]
    zero_rates: tuple[float, ...]
    _knots_t: tuple[float, ...] = field(init=False, repr=False, compare=False)
    _knots_l: tuple[float, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.times or len(self.times) != len(self.zero_rates):
            raise MarketDataError("zero curve needs matching, non-empty pillar times and rates")
        increasing = all(b > a for a, b in zip(self.times, self.times[1:], strict=False))
        if self.times[0] <= 0.0 or not increasing:
            raise MarketDataError("zero curve pillar times must be positive and increasing")
        # Knots of ln P, computed once: (0, 0) and (t_i, −z_i·t_i).
        object.__setattr__(self, "_knots_t", (0.0, *self.times))
        logs = (-z * t for z, t in zip(self.zero_rates, self.times, strict=True))
        object.__setattr__(self, "_knots_l", (0.0, *logs))

    def _segment(self, t: float) -> tuple[float, float, float]:
        """``(t₀, ln P(0,t₀), f)`` of the right-continuous segment containing ``t``.

        Knots of ``ln P`` are ``(0, 0)`` and ``(t_i, −z_i·t_i)``; the forward ``f`` is flat on
        each segment. Negative ``t`` (backward rolls) uses the first segment; ``t`` beyond the
        last pillar extends the last segment.
        """
        knots_t, knots_l = self._knots_t, self._knots_l
        i = min(max(bisect.bisect_right(knots_t, t), 1), len(knots_t) - 1)
        t0, t1 = knots_t[i - 1], knots_t[i]
        l0, l1 = knots_l[i - 1], knots_l[i]
        return t0, l0, -(l1 - l0) / (t1 - t0)

    def df(self, t: float) -> float:
        """Log-linearly interpolated discount factor."""
        t0, l0, f = self._segment(t)
        return math.exp(l0 - f * (t - t0))

    def zero_rate(self, t: float) -> float:
        """``−ln P(0,t)/t``; at ``t = 0`` the first forward (``z_1``)."""
        if t == 0.0:
            return self.zero_rates[0]
        return -math.log(self.df(t)) / t

    def instantaneous_forward(self, t: float) -> float:
        """Piecewise-flat forward, right-continuous at pillars."""
        return self._segment(t)[2]

    def shifted(self, dz: float) -> ZeroCurve:
        """Every pillar zero rate shifted by ``dz`` (a parallel shift of the whole curve)."""
        return ZeroCurve(self.times, tuple(z + dz for z in self.zero_rates))

    def rolled(self, h: float) -> RateCurve:
        """Forward-realising roll (see module docstring)."""
        return RolledCurve(self, h) if h else self


@dataclass(frozen=True, slots=True)
class RolledCurve:
    """``P'(0, t) = P(0, t + h) / P(0, h)`` for a base curve ``P``."""

    base: RateCurve
    h: float

    def df(self, t: float) -> float:
        """Rolled discount factor."""
        return self.base.df(t + self.h) / self.base.df(self.h)

    def zero_rate(self, t: float) -> float:
        """``−ln P'(0,t)/t``; at ``t = 0`` the instantaneous forward."""
        if t == 0.0:
            return self.instantaneous_forward(0.0)
        return -math.log(self.df(t)) / t

    def instantaneous_forward(self, t: float) -> float:
        """Base forward at ``t + h``."""
        return self.base.instantaneous_forward(t + self.h)

    def shifted(self, dz: float) -> RolledCurve:
        """A parallel shift commutes with rolling."""
        return RolledCurve(self.base.shifted(dz), self.h)

    def rolled(self, h: float) -> RateCurve:
        """Compose rolls."""
        return RolledCurve(self.base, self.h + h) if self.h + h else self.base
