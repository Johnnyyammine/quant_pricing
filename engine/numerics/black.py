"""Accurate (normalised) Black function.

With ``x = ln(F/K)``, ``s = σ√T``, ``h = x/s`` and ``t = s/2``, the normalised Black call is

    b(x, s) = B_call / √(FK) = Φ(h + t)·e^{x/2} − Φ(h − t)·e^{−x/2}.

Direct evaluation loses relative accuracy for out-of-the-money options (difference of two nearly
equal products). Following P. Jäckel, "Let's Be Rational" (2013–2014), four regions are used:

1. ``h < −10`` and ``t`` small relative to ``|h|``: 17th-order asymptotic expansion (A&S 26.2.12).
2. ``t < 2·ε^{1/16} ≈ 0.21``: 12th-order small-``t`` expansion of ``Y(h+t) − Y(h−t)``.
3. ``h + t > 0.85`` (price dominated by the first term): direct formula.
4. Otherwise: ``b = ½·exp(−½(h² + t²))·[erfcx(−(h+t)/√2) − erfcx(−(h−t)/√2)]``.

In-the-money prices are computed as intrinsic + out-of-the-money counterpart (``x > 0`` maps to
``−x``), so every price keeps full relative accuracy. This is the pricing kernel used everywhere
in the engine and by the implied-volatility solver.

======================================================================================
Copyright © 2013-2014 Peter Jäckel.

Permission to use, copy, modify, and distribute this software is freely granted,
provided that this notice is preserved.

WARRANTY DISCLAIMER
The Software is provided "as is" without warranty of any kind, either express or implied,
including without limitation any implied warranties of condition, uninterrupted use,
merchantability, fitness for a particular purpose, or non-infringement.
======================================================================================
"""

from __future__ import annotations

import math
import sys

from engine.numerics.normal import (
    ONE_OVER_SQRT_TWO,
    ONE_OVER_SQRT_TWO_PI,
    SQRT_TWO_PI,
    erfcx,
    norm_cdf,
)

DBL_EPSILON: float = sys.float_info.epsilon
DBL_MIN: float = sys.float_info.min
SQRT_DBL_MIN: float = math.sqrt(DBL_MIN)
FOURTH_ROOT_DBL_EPSILON: float = DBL_EPSILON**0.25
SIXTEENTH_ROOT_DBL_EPSILON: float = DBL_EPSILON**0.0625

ASYMPTOTIC_EXPANSION_THRESHOLD: float = -10.0  # η
SMALL_T_EXPANSION_THRESHOLD: float = 2.0 * SIXTEENTH_ROOT_DBL_EPSILON  # τ
REGION3_THRESHOLD: float = 0.85


def normalised_intrinsic(x: float, omega: int) -> float:
    """Normalised intrinsic value ``max(ω·(e^{x/2} − e^{−x/2}), 0)``, accurate for small ``x``."""
    if omega * x <= 0.0:
        return 0.0
    x2 = x * x
    if x2 < 98.0 * FOURTH_ROOT_DBL_EPSILON:  # Taylor series of 2·sinh(x/2); 98 ≈ 92897280^{1/4}
        return abs(
            omega
            * x
            * (
                1.0
                + x2 * (1.0 / 24.0 + x2 * (1.0 / 1920.0 + x2 * (1.0 / 322560.0 + x2 / 92897280.0)))
            )
        )
    b_max = math.exp(0.5 * x)
    return abs(omega * (b_max - 1.0 / b_max))


def _asymptotic_expansion(h: float, t: float) -> float:
    """Region 1: asymptotic expansion of ``b`` for large negative ``h`` (Jäckel (2.4)ff)."""
    e = (t / h) * (t / h)
    r = (h + t) * (h - t)
    q = (h / r) * (h / r)
    # fmt: off
    s = (2.0+q*(-6.0E0-2.0*e+3.0*q*(1.0E1+e*(2.0E1+2.0*e)+5.0*q*(-1.4E1+e*(-7.0E1+e*(-4.2E1-2.0*e))+7.0*q*(1.8E1+e*(1.68E2+e*(2.52E2+e*(7.2E1+2.0*e)))+9.0*q*(-2.2E1+e*(-3.3E2+e*(-9.24E2+e*(-6.6E2+e*(-1.1E2-2.0*e))))+1.1E1*q*(2.6E1+e*(5.72E2+e*(2.574E3+e*(3.432E3+e*(1.43E3+e*(1.56E2+2.0*e)))))+1.3E1*q*(-3.0E1+e*(-9.1E2+e*(-6.006E3+e*(-1.287E4+e*(-1.001E4+e*(-2.73E3+e*(-2.1E2-2.0*e))))))+1.5E1*q*(3.4E1+e*(1.36E3+e*(1.2376E4+e*(3.8896E4+e*(4.862E4+e*(2.4752E4+e*(4.76E3+e*(2.72E2+2.0*e)))))))+1.7E1*q*(-3.8E1+e*(-1.938E3+e*(-2.3256E4+e*(-1.00776E5+e*(-1.84756E5+e*(-1.51164E5+e*(-5.4264E4+e*(-7.752E3+e*(-3.42E2-2.0*e))))))))+1.9E1*q*(4.2E1+e*(2.66E3+e*(4.0698E4+e*(2.3256E5+e*(5.8786E5+e*(7.05432E5+e*(4.0698E5+e*(1.08528E5+e*(1.197E4+e*(4.2E2+2.0*e)))))))))+2.1E1*q*(-4.6E1+e*(-3.542E3+e*(-6.7298E4+e*(-4.90314E5+e*(-1.63438E6+e*(-2.704156E6+e*(-2.288132E6+e*(-9.80628E5+e*(-2.01894E5+e*(-1.771E4+e*(-5.06E2-2.0*e))))))))))+2.3E1*q*(5.0E1+e*(4.6E3+e*(1.0626E5+e*(9.614E5+e*(4.08595E6+e*(8.9148E6+e*(1.04006E7+e*(6.53752E6+e*(2.16315E6+e*(3.542E5+e*(2.53E4+e*(6.0E2+2.0*e)))))))))))+2.5E1*q*(-5.4E1+e*(-5.85E3+e*(-1.6146E5+e*(-1.77606E6+e*(-9.37365E6+e*(-2.607579E7+e*(-4.01166E7+e*(-3.476772E7+e*(-1.687257E7+e*(-4.44015E6+e*(-5.9202E5+e*(-3.51E4+e*(-7.02E2-2.0*e))))))))))))+2.7E1*q*(5.8E1+e*(7.308E3+e*(2.3751E5+e*(3.12156E6+e*(2.003001E7+e*(6.919458E7+e*(1.3572783E8+e*(1.5511752E8+e*(1.0379187E8+e*(4.006002E7+e*(8.58429E6+e*(9.5004E5+e*(4.7502E4+e*(8.12E2+2.0*e)))))))))))))+2.9E1*q*(-6.2E1+e*(-8.99E3+e*(-3.39822E5+e*(-5.25915E6+e*(-4.032015E7+e*(-1.6934463E8+e*(-4.1250615E8+e*(-6.0108039E8+e*(-5.3036505E8+e*(-2.8224105E8+e*(-8.870433E7+e*(-1.577745E7+e*(-1.472562E6+e*(-6.293E4+e*(-9.3E2-2.0*e))))))))))))))+3.1E1*q*(6.6E1+e*(1.0912E4+e*(4.74672E5+e*(8.544096E6+e*(7.71342E7+e*(3.8707344E8+e*(1.14633288E9+e*(2.07431664E9+e*(2.33360622E9+e*(1.6376184E9+e*(7.0963464E8+e*(1.8512208E8+e*(2.7768312E7+e*(2.215136E6+e*(8.184E4+e*(1.056E3+2.0*e)))))))))))))))+3.3E1*(-7.0E1+e*(-1.309E4+e*(-6.49264E5+e*(-1.344904E7+e*(-1.4121492E8+e*(-8.344518E8+e*(-2.9526756E9+e*(-6.49588632E9+e*(-9.0751353E9+e*(-8.1198579E9+e*(-4.6399188E9+e*(-1.6689036E9+e*(-3.67158792E8+e*(-4.707164E7+e*(-3.24632E6+e*(-1.0472E5+e*(-1.19E3-2.0*e)))))))))))))))))*q)))))))))))))))))  # noqa: E501
    # fmt: on
    b = ONE_OVER_SQRT_TWO_PI * math.exp(-0.5 * (h * h + t * t)) * (t / r) * s
    return abs(max(b, 0.0))


def _small_t_expansion(h: float, t: float) -> float:
    """Region 2: 12th-order expansion of ``Y(h+t) − Y(h−t)`` in ``t``, ``Y := Φ/φ``."""
    a = 1.0 + h * (0.5 * SQRT_TWO_PI) * erfcx(-ONE_OVER_SQRT_TWO * h)
    w = t * t
    h2 = h * h
    # fmt: off
    expansion = 2*t*(a+w*((-1+3*a+a*h2)/6+w*((-7+15*a+h2*(-1+10*a+a*h2))/120+w*((-57+105*a+h2*(-18+105*a+h2*(-1+21*a+a*h2)))/5040+w*((-561+945*a+h2*(-285+1260*a+h2*(-33+378*a+h2*(-1+36*a+a*h2))))/362880+w*((-6555+10395*a+h2*(-4680+17325*a+h2*(-840+6930*a+h2*(-52+990*a+h2*(-1+55*a+a*h2)))))/39916800+((-89055+135135*a+h2*(-82845+270270*a+h2*(-20370+135135*a+h2*(-1926+25740*a+h2*(-75+2145*a+h2*(-1+78*a+a*h2))))))*w)/6227020800.0))))))  # noqa: E501
    # fmt: on
    b = ONE_OVER_SQRT_TWO_PI * math.exp(-0.5 * (h * h + t * t)) * expansion
    return abs(max(b, 0.0))


def _direct(x: float, s: float) -> float:
    """Region 3: ``Φ(h+t)·e^{x/2} − Φ(h−t)·e^{−x/2}``."""
    h = x / s
    t = 0.5 * s
    b_max = math.exp(0.5 * x)
    b = norm_cdf(h + t) * b_max - norm_cdf(h - t) / b_max
    return abs(max(b, 0.0))


def _erfcx_form(h: float, t: float) -> float:
    """Region 4: ``½·exp(−½(h²+t²))·[erfcx(−(h+t)/√2) − erfcx(−(h−t)/√2)]``."""
    b = (
        0.5
        * math.exp(-0.5 * (h * h + t * t))
        * (erfcx(-ONE_OVER_SQRT_TWO * (h + t)) - erfcx(-ONE_OVER_SQRT_TWO * (h - t)))
    )
    return abs(max(b, 0.0))


def normalised_black_call(x: float, s: float) -> float:
    """Normalised Black call ``b(x, s)`` with full relative accuracy (see module docstring)."""
    if x > 0.0:
        return normalised_intrinsic(x, 1) + normalised_black_call(-x, s)
    if s <= 0.0:
        return normalised_intrinsic(x, 1)
    # Region tests written without divisions by s: h < η and t < τ + |h| − |η|.
    if x < s * ASYMPTOTIC_EXPANSION_THRESHOLD and 0.5 * s * s + x < s * (
        SMALL_T_EXPANSION_THRESHOLD + ASYMPTOTIC_EXPANSION_THRESHOLD
    ):
        return _asymptotic_expansion(x / s, 0.5 * s)
    if 0.5 * s < SMALL_T_EXPANSION_THRESHOLD:
        return _small_t_expansion(x / s, 0.5 * s)
    if x + 0.5 * s * s > s * REGION3_THRESHOLD:
        return _direct(x, s)
    return _erfcx_form(x / s, 0.5 * s)


def normalised_black(x: float, s: float, omega: int) -> float:
    """Normalised Black price for ``ω = ±1``, using ``b_put(x) = b_call(−x)``."""
    return normalised_black_call(-x if omega < 0 else x, s)


def normalised_vega(x: float, s: float) -> float:
    """``∂b/∂s = φ(x/s)·φ(s/2)·√(2π) = exp(−½((x/s)² + (s/2)²))/√(2π)``."""
    ax = abs(x)
    if ax <= 0.0:
        return ONE_OVER_SQRT_TWO_PI * math.exp(-0.125 * s * s)
    if s <= 0.0 or s <= ax * SQRT_DBL_MIN:
        return 0.0
    return ONE_OVER_SQRT_TWO_PI * math.exp(-0.5 * ((x / s) ** 2 + (0.5 * s) ** 2))


def black_undiscounted(forward: float, strike: float, stdev: float, omega: int) -> float:
    """Undiscounted Black price ``ω·(F·Φ(ωd₁) − K·Φ(ωd₂))`` with ``stdev = σ√T``.

    Evaluated as intrinsic + √(FK)·b(out-of-the-money) for full relative accuracy.
    """
    intrinsic = max(omega * (forward - strike), 0.0)
    otm_omega = -omega if omega * (forward - strike) > 0 else omega
    x = math.log(forward / strike)
    return intrinsic + max(
        0.0, math.sqrt(forward) * math.sqrt(strike) * normalised_black(x, stdev, otm_omega)
    )
