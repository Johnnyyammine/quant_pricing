"""Numerical settings: every bump size, tolerance and grid size lives here.

No numerical constant that affects a reported number may be hard-coded elsewhere in the engine.
The full settings object is echoed in every :class:`~engine.results.PricingResult` and shown in
the UI's Diagnostics tab.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BumpSettings:
    """Finite-difference bump sizes for bump-and-revalue greeks.

    All greeks use central differences, error ``O(h²)``.

    Attributes:
        spot_rel: Relative spot bump ``h_S / S``.
        vol_abs: Absolute bump of the vol surface, in vol units (``0.001`` = 0.1 vol point).
        rate_abs: Absolute parallel bump of zero rates (``1e-4`` = 1 bp).
        time_days: Valuation-date roll in calendar days for theta and charm.

    """

    spot_rel: float = 1e-3
    vol_abs: float = 1e-3
    rate_abs: float = 1e-4
    time_days: int = 1

    def __post_init__(self) -> None:
        if not (self.spot_rel > 0 and self.vol_abs > 0 and self.rate_abs > 0):
            raise ValueError("bump sizes must be strictly positive")
        if self.time_days < 1:
            raise ValueError("time_days must be at least 1")


@dataclass(frozen=True, slots=True)
class PricingSettings:
    """Top-level numerical settings passed to :func:`engine.pricing.price`."""

    bumps: BumpSettings = field(default_factory=BumpSettings)
