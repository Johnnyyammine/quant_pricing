"""Black implied volatility: P. Jäckel, "Let's Be Rational", Wilmott (2015), 75, pp. 40–53.

The normalised price ``β = B/√(FK)`` is inverted for ``s = σ√T`` at fixed ``x = ln(F/K)``:

1. In-the-money inputs are mapped to out-of-the-money by subtracting the normalised intrinsic,
   and puts to calls via ``b_put(x) = b_call(−x)``.
2. The domain ``β ∈ (0, e^{x/2})`` is split at ``b_l < b_c < b_h`` into four segments. Each gets a
   rational cubic initial guess: in transformed coordinates ``f`` (lower and upper maps) at the
   ends, in ``s`` directly in the middle.
3. ``max_iterations`` (default 2) Householder(3) steps are taken on a segment-specific objective:
   ``1/ln b − 1/ln β`` in the lowest segment, ``ln((b_max − β)/(b_max − b))`` in the upper
   segment (for ``β > b_max/2``), and ``b − β`` otherwise. A bracket is maintained and bisection
   takes over if an iterate leaves it or oscillates.

The result is accurate to machine precision in ``s`` wherever the price carries information
about ``σ``. This is a port of Jäckel's reference implementation with his notice preserved; it
follows the C++ control flow (``py_lets_be_rational`` 1.1.2, used as a test oracle, resets its
step inside the upper-segment loop and range-checks only one bound of ``f''``).

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

from engine.errors import AboveMaximumError, BelowIntrinsicError
from engine.instruments.vanilla import EuropeanOption
from engine.market.market_data import MarketData
from engine.models.base import Model
from engine.numerics.black import normalised_black_call, normalised_intrinsic, normalised_vega
from engine.numerics.normal import inv_norm_cdf, norm_cdf, norm_pdf
from engine.numerics.rational_cubic import (
    convex_control_to_fit_second_derivative_left,
    convex_control_to_fit_second_derivative_right,
    rational_cubic_interpolation,
)
from engine.settings import ImpliedVolSettings

DBL_EPSILON: float = sys.float_info.epsilon
DBL_MIN: float = sys.float_info.min
DBL_MAX: float = sys.float_info.max
SQRT_DBL_MAX: float = math.sqrt(DBL_MAX)
SQRT_THREE: float = math.sqrt(3.0)
SQRT_ONE_OVER_THREE: float = math.sqrt(1.0 / 3.0)
TWO_PI: float = 2.0 * math.pi
TWO_PI_OVER_SQRT_27: float = 2.0 * math.pi / math.sqrt(27.0)
PI_OVER_SIX: float = math.pi / 6.0
SQRT_PI_OVER_TWO: float = math.sqrt(math.pi / 2.0)


def _householder_factor(newton: float, halley: float, hh3: float) -> float:
    """Householder(3) step multiplier: ``s ← s + newton·(1 + ½·halley·newton)/(1 + newton·(halley + hh3·newton/6))``."""  # noqa: E501
    return (1.0 + 0.5 * halley * newton) / (1.0 + newton * (halley + hh3 * newton / 6.0))


def _lower_map(x: float, s: float) -> tuple[float, float, float]:
    """``f(s) = 2π/√27·|x|·Φ(−z)³`` with ``z = |x|/(s√3)``, and ``df/dβ``, ``d²f/dβ²``."""
    ax = abs(x)
    z = SQRT_ONE_OVER_THREE * ax / s
    y = z * z
    s2 = s * s
    big_phi = norm_cdf(-z)
    small_phi = norm_pdf(z)
    fpp = (
        PI_OVER_SIX
        * y
        / (s2 * s)
        * big_phi
        * (8.0 * SQRT_THREE * s * ax + (3.0 * s2 * (s2 - 8.0) - 8.0 * x * x) * big_phi / small_phi)
        * math.exp(2.0 * y + 0.25 * s2)
    )
    phi2 = big_phi * big_phi
    fp = TWO_PI * y * phi2 * math.exp(y + 0.125 * s2)
    f = TWO_PI_OVER_SQRT_27 * ax * (phi2 * big_phi)
    return f, fp, fpp


def _inverse_lower_map(x: float, f: float) -> float:
    return abs(x / (SQRT_THREE * inv_norm_cdf((f / (TWO_PI_OVER_SQRT_27 * abs(x))) ** (1.0 / 3.0))))


def _upper_map(x: float, s: float) -> tuple[float, float, float]:
    """``f(s) = Φ(−s/2)``, and ``df/dβ``, ``d²f/dβ²``."""
    f = norm_cdf(-0.5 * s)
    w = (x / s) ** 2
    fp = -0.5 * math.exp(0.5 * w)
    fpp = SQRT_PI_OVER_TWO * math.exp(w + 0.125 * s * s) * w / s
    return f, fp, fpp


def _inverse_upper_map(f: float) -> float:
    return -2.0 * inv_norm_cdf(f)


def _normalised_iv_otm_call(beta: float, x: float, n_max: int) -> float:
    """``s`` such that ``b(x, s) = β`` for an out-of-the-money call (``x ≤ 0``, ``0 < β < e^{x/2}``)."""  # noqa: E501
    b_max = math.exp(0.5 * x)
    iterations = 0
    direction_reversals = 0
    ds = -DBL_MAX
    ds_previous = 0.0
    s_left = DBL_MIN
    s_right = DBL_MAX

    s_c = math.sqrt(abs(2.0 * x))
    b_c = normalised_black_call(x, s_c)
    v_c = normalised_vega(x, s_c)

    if beta < b_c:
        s_l = s_c - b_c / v_c
        b_l = normalised_black_call(x, s_l)
        if beta < b_l:
            # Lowest segment: guess in the lower-map coordinate, iterate on 1/ln b − 1/ln β.
            f_l, fp_l, fpp_l = _lower_map(x, s_l)
            r_ll = convex_control_to_fit_second_derivative_right(
                0.0, b_l, 0.0, f_l, 1.0, fp_l, fpp_l, True
            )
            f = rational_cubic_interpolation(beta, 0.0, b_l, 0.0, f_l, 1.0, fp_l, r_ll)
            if not f > 0.0:  # round-off for extreme |x|: quadratic through f(0)=0, f'(0)=1, f(b_l)
                t = beta / b_l
                f = (f_l * t + b_l * (1.0 - t)) * t
            s = _inverse_lower_map(x, f)
            s_right = s_l
            while iterations < n_max and abs(ds) > DBL_EPSILON * s:
                if ds * ds_previous < 0.0:
                    direction_reversals += 1
                if iterations > 0 and (direction_reversals == 3 or not s_left < s < s_right):
                    s = 0.5 * (s_left + s_right)
                    if s_right - s_left <= DBL_EPSILON * s:
                        break
                    direction_reversals = 0
                    ds = 0.0
                ds_previous = ds
                b = normalised_black_call(x, s)
                bp = normalised_vega(x, s)
                if b > beta and s < s_right:
                    s_right = s
                elif b < beta and s > s_left:
                    s_left = s
                if b <= 0.0 or bp <= 0.0:
                    ds = 0.5 * (s_left + s_right) - s
                else:
                    ln_b = math.log(b)
                    ln_beta = math.log(beta)
                    bpob = bp / b
                    h = x / s
                    b_halley = h * h / s - s / 4.0
                    newton = (ln_beta - ln_b) * ln_b / ln_beta / bpob
                    halley = b_halley - bpob * (1.0 + 2.0 / ln_b)
                    b_hh3 = b_halley * b_halley - 3.0 * (h / s) ** 2 - 0.25
                    hh3 = (
                        b_hh3
                        + 2.0 * bpob * bpob * (1.0 + 3.0 / ln_b * (1.0 + 1.0 / ln_b))
                        - 3.0 * b_halley * bpob * (1.0 + 2.0 / ln_b)
                    )
                    ds = newton * _householder_factor(newton, halley, hh3)
                ds = max(-0.5 * s, ds)
                s += ds
                iterations += 1
            return s
        # Lower-middle segment: guess directly in s.
        v_l = normalised_vega(x, s_l)
        r_lm = convex_control_to_fit_second_derivative_right(
            b_l, b_c, s_l, s_c, 1.0 / v_l, 1.0 / v_c, 0.0, False
        )
        s = rational_cubic_interpolation(beta, b_l, b_c, s_l, s_c, 1.0 / v_l, 1.0 / v_c, r_lm)
        s_left, s_right = s_l, s_c
    else:
        s_h = s_c + (b_max - b_c) / v_c if v_c > DBL_MIN else s_c
        b_h = normalised_black_call(x, s_h)
        if beta <= b_h:
            # Upper-middle segment: guess directly in s.
            v_h = normalised_vega(x, s_h)
            r_hm = convex_control_to_fit_second_derivative_left(
                b_c, b_h, s_c, s_h, 1.0 / v_c, 1.0 / v_h, 0.0, False
            )
            s = rational_cubic_interpolation(beta, b_c, b_h, s_c, s_h, 1.0 / v_c, 1.0 / v_h, r_hm)
            s_left, s_right = s_c, s_h
        else:
            # Upper segment: guess in the upper-map coordinate.
            f_h, fp_h, fpp_h = _upper_map(x, s_h)
            f = -DBL_MAX
            if -SQRT_DBL_MAX < fpp_h < SQRT_DBL_MAX:
                r_hh = convex_control_to_fit_second_derivative_left(
                    b_h, b_max, f_h, 0.0, fp_h, -0.5, fpp_h, True
                )
                f = rational_cubic_interpolation(beta, b_h, b_max, f_h, 0.0, fp_h, -0.5, r_hh)
            if f <= 0.0:  # quadratic through f(b_h), f(b_max)=0, f'(b_max)=−1/2
                h = b_max - b_h
                t = (beta - b_h) / h
                f = (f_h * (1.0 - t) + 0.5 * h * t) * (1.0 - t)
            s = _inverse_upper_map(f)
            s_left = s_h
            if beta > 0.5 * b_max:
                # Iterate on g(s) = ln((b_max − β)/(b_max − b(s))).
                while iterations < n_max and abs(ds) > DBL_EPSILON * s:
                    if ds * ds_previous < 0.0:
                        direction_reversals += 1
                    if iterations > 0 and (direction_reversals == 3 or not s_left < s < s_right):
                        s = 0.5 * (s_left + s_right)
                        if s_right - s_left <= DBL_EPSILON * s:
                            break
                        direction_reversals = 0
                        ds = 0.0
                    ds_previous = ds
                    b = normalised_black_call(x, s)
                    bp = normalised_vega(x, s)
                    if b > beta and s < s_right:
                        s_right = s
                    elif b < beta and s > s_left:
                        s_left = s
                    if b >= b_max or bp <= DBL_MIN:
                        ds = 0.5 * (s_left + s_right) - s
                    else:
                        b_max_minus_b = b_max - b
                        g = math.log((b_max - beta) / b_max_minus_b)
                        gp = bp / b_max_minus_b
                        b_halley = (x / s) ** 2 / s - s / 4.0
                        b_hh3 = b_halley * b_halley - 3.0 * (x / (s * s)) ** 2 - 0.25
                        newton = -g / gp
                        halley = b_halley + gp
                        hh3 = b_hh3 + gp * (2.0 * gp + 3.0 * b_halley)
                        ds = newton * _householder_factor(newton, halley, hh3)
                    ds = max(-0.5 * s, ds)
                    s += ds
                    iterations += 1
                return s

    # Middle segments (and the upper segment when β ≤ b_max/2): iterate on g(s) = b(s) − β.
    while iterations < n_max and abs(ds) > DBL_EPSILON * s:
        if ds * ds_previous < 0.0:
            direction_reversals += 1
        if iterations > 0 and (direction_reversals == 3 or not s_left < s < s_right):
            s = 0.5 * (s_left + s_right)
            if s_right - s_left <= DBL_EPSILON * s:
                break
            direction_reversals = 0
            ds = 0.0
        ds_previous = ds
        b = normalised_black_call(x, s)
        bp = normalised_vega(x, s)
        if b > beta and s < s_right:
            s_right = s
        elif b < beta and s > s_left:
            s_left = s
        newton = (beta - b) / bp
        halley = (x / s) ** 2 / s - s / 4.0
        hh3 = halley * halley - 3.0 * (x / (s * s)) ** 2 - 0.25
        ds = max(-0.5 * s, newton * _householder_factor(newton, halley, hh3))
        s += ds
        iterations += 1
    return s


def normalised_implied_vol(beta: float, x: float, omega: int, max_iterations: int = 2) -> float:
    """Normalised implied volatility ``s = σ√T`` from ``β = B/√(FK)`` and ``x = ln(F/K)``.

    Raises:
        BelowIntrinsicError: ``β`` below the normalised intrinsic value.
        AboveMaximumError: ``β ≥ e^{ωx/2}`` (call: forward; put: strike, normalised).

    """
    if omega * x > 0.0:
        beta -= normalised_intrinsic(x, omega)
        if beta < 0.0:
            raise BelowIntrinsicError("price below intrinsic value")
        omega = -omega
    if beta < 0.0:
        raise BelowIntrinsicError("price below intrinsic value")
    if omega < 0:  # put → call with reciprocal moneyness
        x = -x
    if beta <= 0.0:
        return 0.0
    if beta >= math.exp(0.5 * x):
        raise AboveMaximumError("price at or above the maximum attainable price")
    return _normalised_iv_otm_call(beta, x, max_iterations)


def implied_black_vol(
    undiscounted_price: float,
    forward: float,
    strike: float,
    t: float,
    omega: int,
    settings: ImpliedVolSettings | None = None,
) -> float:
    """Black implied volatility ``σ`` from an undiscounted (forward) option price.

    Args:
        undiscounted_price: ``price / P(0, T)``.
        forward: Forward ``F(0, T)``.
        strike: Strike ``K``.
        t: Time to expiry in years (ACT/365F).
        omega: +1 call, −1 put.
        settings: Solver settings.

    Raises:
        BelowIntrinsicError, AboveMaximumError: No volatility reproduces the price.
        ValueError: Non-positive forward, strike or time.

    """
    if not (forward > 0.0 and strike > 0.0 and t > 0.0):
        raise ValueError("forward, strike and time to expiry must be positive")
    settings = settings or ImpliedVolSettings()
    intrinsic = max(omega * (forward - strike), 0.0)
    if undiscounted_price < intrinsic:
        raise BelowIntrinsicError(
            f"price {undiscounted_price:.10g} below intrinsic {intrinsic:.10g} (undiscounted)"
        )
    maximum = forward if omega > 0 else strike
    if undiscounted_price >= maximum:
        raise AboveMaximumError(
            f"price {undiscounted_price:.10g} at or above maximum {maximum:.10g} (undiscounted)"
        )
    x = math.log(forward / strike)
    otm_omega = omega
    beta = undiscounted_price
    if omega * x > 0.0:  # in the money: subtract intrinsic, switch to the OTM counterpart
        beta = max(beta - intrinsic, 0.0)
        otm_omega = -omega
    s = normalised_implied_vol(
        beta / (math.sqrt(forward) * math.sqrt(strike)), x, otm_omega, settings.max_iterations
    )
    return s / math.sqrt(t)


def option_implied_vol(
    option: EuropeanOption,
    market: MarketData,
    model: Model,
    target_price: float,
    settings: ImpliedVolSettings | None = None,
) -> float:
    """Flat implied vol at which ``option`` (unit price) is worth ``target_price``.

    Uses the model forward (spot-based for BSM, quoted forward for Black-76) and the discount
    factor to expiry: ``σ = LBR(target / P(0,T), F, K, T, ω)``.
    """
    t = market.time_to(option.expiry)
    if t <= 0.0:
        raise ValueError("option has expired: no implied volatility")
    return implied_black_vol(
        target_price / market.df(t),
        model.forward(market, t),
        option.strike,
        t,
        option.option_type.omega,
        settings,
    )
