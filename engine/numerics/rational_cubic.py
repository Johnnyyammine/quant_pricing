"""Shape-preserving rational cubic interpolation (Delbourgo & Gregory, 1985).

Port of the routines used in P. Jäckel, "Let's Be Rational" (2013–2014), www.jaeckel.org.

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

DBL_EPSILON: float = sys.float_info.epsilon
DBL_MIN: float = sys.float_info.min
DBL_MAX: float = sys.float_info.max
MIN_CONTROL: float = -(1.0 - math.sqrt(DBL_EPSILON))
MAX_CONTROL: float = 2.0 / (DBL_EPSILON * DBL_EPSILON)


def _is_zero(x: float) -> bool:
    return abs(x) < DBL_MIN


def rational_cubic_interpolation(
    x: float, x_l: float, x_r: float, y_l: float, y_r: float, d_l: float, d_r: float, r: float
) -> float:
    """Rational cubic through (x_l, y_l), (x_r, y_r) with end slopes d_l, d_r and control ``r``.

    Delbourgo–Gregory (2.4)/(2.5). ``r → ∞`` is linear; ``r = 3`` is the cubic Hermite.
    """
    h = x_r - x_l
    if abs(h) <= 0.0:
        return 0.5 * (y_l + y_r)
    t = (x - x_l) / h
    if not r >= MAX_CONTROL:
        omt = 1.0 - t
        t2 = t * t
        omt2 = omt * omt
        return (
            y_r * t2 * t
            + (r * y_r - h * d_r) * t2 * omt
            + (r * y_l + h * d_l) * t * omt2
            + y_l * omt2 * omt
        ) / (1.0 + (r - 3.0) * t * omt)
    return y_r * t + y_l * (1.0 - t)


def _control_to_fit_second_derivative_left(
    x_l: float, x_r: float, y_l: float, y_r: float, d_l: float, d_r: float, d2_l: float
) -> float:
    h = x_r - x_l
    numerator = 0.5 * h * d2_l + (d_r - d_l)
    if _is_zero(numerator):
        return 0.0
    denominator = (y_r - y_l) / h - d_l
    if _is_zero(denominator):
        return MAX_CONTROL if numerator > 0 else MIN_CONTROL
    return numerator / denominator


def _control_to_fit_second_derivative_right(
    x_l: float, x_r: float, y_l: float, y_r: float, d_l: float, d_r: float, d2_r: float
) -> float:
    h = x_r - x_l
    numerator = 0.5 * h * d2_r + (d_r - d_l)
    if _is_zero(numerator):
        return 0.0
    denominator = d_r - (y_r - y_l) / h
    if _is_zero(denominator):
        return MAX_CONTROL if numerator > 0 else MIN_CONTROL
    return numerator / denominator


def _minimum_control(d_l: float, d_r: float, s: float, prefer_shape: bool) -> float:
    """Smallest control parameter preserving monotonicity/convexity (D&G (3.8), (3.18))."""
    monotonic = d_l * s >= 0 and d_r * s >= 0
    convex = d_l <= s <= d_r
    concave = d_l >= s >= d_r
    if not (monotonic or convex or concave):
        return MIN_CONTROL
    d_r_m_d_l = d_r - d_l
    d_r_m_s = d_r - s
    s_m_d_l = s - d_l
    r1 = -DBL_MAX
    r2 = r1
    if monotonic:
        if not _is_zero(s):
            r1 = (d_r + d_l) / s
        elif prefer_shape:
            r1 = MAX_CONTROL
    if convex or concave:
        if not (_is_zero(s_m_d_l) or _is_zero(d_r_m_s)):
            r2 = max(abs(d_r_m_d_l / d_r_m_s), abs(d_r_m_d_l / s_m_d_l))
        elif prefer_shape:
            r2 = MAX_CONTROL
    elif monotonic and prefer_shape:
        r2 = MAX_CONTROL
    return max(MIN_CONTROL, r1, r2)


def convex_control_to_fit_second_derivative_left(
    x_l: float,
    x_r: float,
    y_l: float,
    y_r: float,
    d_l: float,
    d_r: float,
    d2_l: float,
    prefer_shape: bool,
) -> float:
    """Control parameter matching ``y''(x_l) = d2_l``, floored to preserve shape."""
    r = _control_to_fit_second_derivative_left(x_l, x_r, y_l, y_r, d_l, d_r, d2_l)
    return max(r, _minimum_control(d_l, d_r, (y_r - y_l) / (x_r - x_l), prefer_shape))


def convex_control_to_fit_second_derivative_right(
    x_l: float,
    x_r: float,
    y_l: float,
    y_r: float,
    d_l: float,
    d_r: float,
    d2_r: float,
    prefer_shape: bool,
) -> float:
    """Control parameter matching ``y''(x_r) = d2_r``, floored to preserve shape."""
    r = _control_to_fit_second_derivative_right(x_l, x_r, y_l, y_r, d_l, d_r, d2_r)
    return max(r, _minimum_control(d_l, d_r, (y_r - y_l) / (x_r - x_l), prefer_shape))
