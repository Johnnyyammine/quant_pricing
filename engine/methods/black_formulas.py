"""Closed-form generalised Black–Scholes price and greeks (cost-of-carry form).

Underlying ``X`` with cost of carry ``μ`` and discount rate ``r`` (continuously compounded zero
rates to expiry ``T``)::

    F = X·e^{μT},  D = e^{−rT},  c = e^{(μ−r)T} = D·F/X,  s = σ√T,
    d₁ = ln(F/K)/s + s/2,  d₂ = d₁ − s,  n₁ = φ(d₁)

    V      = D·ω·[F·Φ(ωd₁) − K·Φ(ωd₂)]         (evaluated with Jäckel's accurate kernel)
    Δ      = ω·c·Φ(ωd₁)
    Γ      = c·n₁ / (X·s)
    ν      = X·c·n₁·√T
    vanna  = −c·n₁·d₂/σ
    volga  = ν·d₁·d₂/σ
    Θ      = ∂V/∂t = −X·c·n₁·σ/(2√T) − ω(μ − r)·X·c·Φ(ωd₁) − ω·r·K·D·Φ(ωd₂)
    charm  = ∂Δ/∂t = −ω(μ − r)·c·Φ(ωd₁) − c·n₁·(2μT − d₂·s)/(2T·s)

* BSM: ``X = S``, ``μ = r − q − b``; ``ρ = ∂V/∂r = ω·K·T·D·Φ(ωd₂)`` (forward moves with ``r``),
  ``φ = ∂V/∂q = −ω·T·X·c·Φ(ωd₁)``.
* Black-76: ``X = F``, ``μ = 0``; ``ρ = −T·V``, ``φ = 0``.

References: E. G. Haug, *The Complete Guide to Option Pricing Formulas*, 2nd ed., ch. 1–2;
J. C. Hull, *Options, Futures, and Other Derivatives*, ch. 15, 19.

Θ and charm hold ``r``, ``μ`` and ``σ`` fixed as ``T`` shrinks, which is exact for flat curves and
a flat surface. At ``T = 0`` the price is intrinsic, Δ is the (discounted) step function (½ at the
money) and every other greek is reported as 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from engine.numerics.black import black_undiscounted
from engine.numerics.normal import norm_cdf, norm_pdf
from engine.results import Greek


class CarryModel(Enum):
    """How the carry ``μ`` depends on the discount rate (determines ρ and φ)."""

    SPOT = "spot"  # μ = r − q − b: BSM on spot
    FORWARD = "forward"  # μ = 0: Black-76 on a forward


@dataclass(frozen=True, slots=True)
class BlackInputs:
    """Inputs of the generalised Black formula (zero rates to expiry)."""

    underlying: float  # X
    strike: float  # K
    t: float  # T, years
    sigma: float  # σ
    rate: float  # r
    carry: float  # μ
    omega: int  # +1 call, −1 put
    carry_model: CarryModel

    @property
    def forward(self) -> float:
        """``F = X·e^{μT}``."""
        return self.underlying * math.exp(self.carry * self.t)

    @property
    def discount(self) -> float:
        """``D = e^{−rT}``."""
        return math.exp(-self.rate * self.t)

    @property
    def stdev(self) -> float:
        """``s = σ√T``."""
        return self.sigma * math.sqrt(self.t)


def black_price(p: BlackInputs) -> float:
    """``V = D·B(F, K, σ√T, ω)`` with the accurate undiscounted Black kernel."""
    if p.t <= 0.0:
        return max(p.omega * (p.underlying - p.strike), 0.0)
    return p.discount * black_undiscounted(p.forward, p.strike, p.stdev, p.omega)


def black_greeks(p: BlackInputs, price: float) -> dict[Greek, float]:
    """All greeks in pure model units (see module docstring). ``price`` is :func:`black_price`."""
    x, k, w, mu, r = p.underlying, p.strike, p.omega, p.carry, p.rate
    if p.t <= 0.0:
        itm = w * (x - k)
        delta = w * (1.0 if itm > 0.0 else 0.5 if itm == 0.0 else 0.0)
        out = dict.fromkeys(Greek, 0.0)
        out[Greek.DELTA] = delta
        return out

    t, sigma, s = p.t, p.sigma, p.stdev
    sqrt_t = math.sqrt(t)
    d = p.discount
    c = math.exp((mu - r) * t)
    d1 = math.log(p.forward / k) / s + 0.5 * s
    d2 = d1 - s
    n1 = norm_pdf(d1)
    cdf1 = norm_cdf(w * d1)
    cdf2 = norm_cdf(w * d2)

    vega = x * c * n1 * sqrt_t
    greeks = {
        Greek.DELTA: w * c * cdf1,
        Greek.GAMMA: c * n1 / (x * s),
        Greek.VEGA: vega,
        Greek.VANNA: -c * n1 * d2 / sigma,
        Greek.VOLGA: vega * d1 * d2 / sigma,
        Greek.THETA: (
            -x * c * n1 * sigma / (2.0 * sqrt_t)
            - w * (mu - r) * x * c * cdf1
            - w * r * k * d * cdf2
        ),
        Greek.CHARM: -w * (mu - r) * c * cdf1 - c * n1 * (2.0 * mu * t - d2 * s) / (2.0 * t * s),
    }
    match p.carry_model:
        case CarryModel.SPOT:
            greeks[Greek.RHO] = w * k * t * d * cdf2
            greeks[Greek.PHI] = -w * t * x * c * cdf1
        case CarryModel.FORWARD:
            greeks[Greek.RHO] = -t * price
            greeks[Greek.PHI] = 0.0
    return greeks
