"""Pricing results: price, greeks and diagnostics.

Greeks are stored in *pure model units* (partial derivatives of the unit price with respect to
the raw model inputs, time measured in years). Conversion to desk units happens in
:mod:`engine.risk.units`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from engine.settings import PricingSettings


class Greek(StrEnum):
    """Supported sensitivities, with their pure-unit definition.

    ``V`` is the unit price, ``S`` spot, ``σ`` the implied vol (parallel surface shift), ``r``
    the discount zero rate, ``q`` the dividend yield, ``t`` calendar time in years (``τ = T − t``).
    """

    DELTA = "delta"  # ∂V/∂S
    GAMMA = "gamma"  # ∂²V/∂S²
    VEGA = "vega"  # ∂V/∂σ
    THETA = "theta"  # ∂V/∂t = −∂V/∂τ, per year, spot/vol/rates held fixed
    RHO = "rho"  # ∂V/∂r
    PHI = "phi"  # ∂V/∂q (dividend / repo rho)
    VANNA = "vanna"  # ∂²V/∂S∂σ
    VOLGA = "volga"  # ∂²V/∂σ²
    CHARM = "charm"  # ∂Δ/∂t = −∂²V/∂S∂τ, per year


class GreekSource(StrEnum):
    """How a greek was computed."""

    ANALYTIC = "analytic"
    BUMP = "bump"


@dataclass(frozen=True, slots=True)
class Greeks:
    """Greeks in pure model units, with the method used for each."""

    values: Mapping[Greek, float]
    sources: Mapping[Greek, GreekSource]

    def __getitem__(self, greek: Greek) -> float:
        return self.values[greek]


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Everything needed to judge and reproduce a price.

    Attributes:
        method: Pricing-method identifier.
        model: Model identifier.
        runtime_ms: CPU time of the pricing thread for price and greeks, milliseconds (not
            inflated by concurrent work in the same process).
        revaluations: Number of full revaluations performed (1 + bump revaluations).
        settings: Numerical settings used.
        details: Method-specific diagnostics (MC std error, grid size, iterations, ...).
        warnings: Human-readable caveats about this result.

    """

    method: str
    model: str
    runtime_ms: float
    revaluations: int
    settings: PricingSettings
    details: Mapping[str, float | int | str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PricingResult:
    """Unit price (per one unit of underlying, in the instrument currency), greeks, diagnostics."""

    price: float
    greeks: Greeks | None
    diagnostics: Diagnostics
