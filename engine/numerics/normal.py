"""Standard normal distribution helpers with full double-precision relative accuracy in the tails.

* ``Φ(z) = ½·erfc(−z/√2)``: ``erfc`` of a large positive argument is computed without cancellation,
  so the lower tail keeps full relative accuracy (unlike ``1 − Φ(−z)``).
* ``erfcx(z) = exp(z²)·erfc(z)``: scaled complementary error function (Faddeeva package via SciPy).
* ``Φ⁻¹``: SciPy ``ndtri``.
"""

from __future__ import annotations

import math

from scipy import special

ONE_OVER_SQRT_TWO: float = 1.0 / math.sqrt(2.0)
ONE_OVER_SQRT_TWO_PI: float = 1.0 / math.sqrt(2.0 * math.pi)
SQRT_TWO_PI: float = math.sqrt(2.0 * math.pi)


def norm_pdf(z: float) -> float:
    """Standard normal density ``φ(z) = exp(−z²/2)/√(2π)``."""
    return ONE_OVER_SQRT_TWO_PI * math.exp(-0.5 * z * z)


def norm_cdf(z: float) -> float:
    """Standard normal distribution function ``Φ(z)``."""
    return 0.5 * math.erfc(-z * ONE_OVER_SQRT_TWO)


def erfcx(z: float) -> float:
    """Scaled complementary error function ``exp(z²)·erfc(z)``."""
    return float(special.erfcx(z))


def inv_norm_cdf(p: float) -> float:
    """Inverse standard normal distribution function ``Φ⁻¹(p)``."""
    return float(special.ndtri(p))
