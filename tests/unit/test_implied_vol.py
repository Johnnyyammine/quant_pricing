"""Accurate normalised Black and Let's Be Rational implied vol.

References: 50-digit mpmath evaluation of the Black formula; py_lets_be_rational (independent port
of Jäckel's code) as a second oracle.
"""

import math
import sys

import mpmath
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from py_lets_be_rational import lets_be_rational as plbr

from engine.calibration.implied_vol import implied_black_vol, normalised_implied_vol
from engine.errors import AboveMaximumError, BelowIntrinsicError
from engine.numerics.black import black_undiscounted, normalised_black_call, normalised_vega

EPS = sys.float_info.epsilon
mpmath.mp.dps = 50


def mp_black(forward: float, strike: float, stdev: float, omega: int) -> float:
    f, k, s = mpmath.mpf(forward), mpmath.mpf(strike), mpmath.mpf(stdev)
    d1 = mpmath.log(f / k) / s + s / 2
    d2 = d1 - s
    return float(omega * (f * mpmath.ncdf(omega * d1) - k * mpmath.ncdf(omega * d2)))


# One point in each of Jäckel's four regions, plus in-the-money mirrors.
REGION_CASES = [
    (-20.0, 1.0),  # region 1: h = −20, asymptotic expansion
    (-1.0, 0.1),  # region 2: t = 0.05 < 0.21, small-t expansion
    (-0.05, 2.0),  # region 3: h + t > 0.85
    (-3.0, 1.0),  # region 4: erfcx form
    (-12.0, 0.8),  # region 1, deep OTM
    (0.7, 0.3),  # in the money
]


@pytest.mark.parametrize(("x", "s"), REGION_CASES)
def test_normalised_black_matches_50_digit_reference(x, s):
    b = normalised_black_call(x, s)
    ref = mp_black(math.exp(x / 2), math.exp(-x / 2), s, 1)
    assert b == pytest.approx(ref, rel=16 * EPS)


@given(
    st.floats(0.01, 100.0),
    st.floats(0.05, 20.0),
    st.floats(1e-3, 3.0),
    st.sampled_from([1, -1]),
)
def test_black_undiscounted_relative_accuracy(forward, strike_ratio, stdev, omega):
    strike = forward * strike_ratio
    ref = mp_black(forward, strike, stdev, omega)
    assume(ref > 1e-300)
    assert black_undiscounted(forward, strike, stdev, omega) == pytest.approx(ref, rel=1e-13)


def _condition(x: float, s: float, omega: int) -> float:
    """Relative-error amplification of the normalised inversion at (x, s, ω).

    For in-the-money inputs the solver recovers the out-of-the-money price as β − intrinsic, which
    amplifies round-off by β/β_otm; the inversion itself amplifies by β_otm/(s·∂b/∂s).
    """
    xx = -x if omega < 0 else x
    beta = normalised_black_call(xx, s)
    otm = normalised_black_call(-abs(xx), s)
    return (beta / otm) * (1.0 + otm / (s * normalised_vega(xx, s)))


@given(st.floats(-8.0, 8.0), st.floats(1e-3, 6.0), st.sampled_from([1, -1]))
def test_implied_vol_round_trip(x, s, omega):
    xx = -x if omega < 0 else x
    beta = normalised_black_call(xx, s)
    otm = normalised_black_call(-abs(xx), s)
    # Normal (not subnormal) floats only: below ~1e-290 intermediate terms lose mantissa bits.
    assume(otm > 1e-290 and normalised_vega(xx, s) > 0.0)
    assume(otm > 1e3 * EPS * beta)  # otherwise the price carries no information about s
    s_hat = normalised_implied_vol(beta, x, omega)
    assert abs(s_hat - s) <= 64 * EPS * s * _condition(x, s, omega)


@given(
    st.floats(1.0, 500.0),
    st.floats(0.3, 3.0),
    st.floats(1 / 365, 10.0),
    st.floats(0.02, 2.0),
    st.sampled_from([1, -1]),
)
def test_implied_black_vol_recovers_sigma(forward, strike_ratio, t, sigma, omega):
    strike = forward * strike_ratio
    price = black_undiscounted(forward, strike, sigma * math.sqrt(t), omega)
    otm = black_undiscounted(forward, strike, sigma * math.sqrt(t), -1 if strike < forward else 1)
    # Well-conditioned domain: the OTM part is resolvable next to intrinsic and not in the far tail.
    assume(otm > 1e-3 * price and otm > 1e-12 * forward)
    assert implied_black_vol(price, forward, strike, t, omega) == pytest.approx(sigma, rel=1e-11)


@given(st.floats(-5.0, 5.0), st.floats(0.01, 4.0), st.sampled_from([1, -1]))
def test_agrees_with_independent_port(x, s, omega):
    beta = normalised_black_call(-x if omega < 0 else x, s)
    b_max = math.exp(0.5 * (-x if omega < 0 else x))
    assume(1e-200 < beta < b_max * (1 - 1e-10))
    assume(normalised_black_call(-abs(x), s) > 1e-6 * beta)  # OTM part resolvable for ITM inputs
    ours = normalised_implied_vol(beta, x, omega)
    theirs = plbr.normalised_implied_volatility_from_a_transformed_rational_guess(beta, x, omega)
    assert ours == pytest.approx(theirs, rel=1e-12)


def test_no_arbitrage_bounds_raise():
    with pytest.raises(BelowIntrinsicError):
        implied_black_vol(4.9, 105.0, 100.0, 1.0, 1)  # call intrinsic 5
    with pytest.raises(AboveMaximumError):
        implied_black_vol(105.0, 105.0, 100.0, 1.0, 1)  # call worth at most F
    with pytest.raises(AboveMaximumError):
        implied_black_vol(100.0, 105.0, 100.0, 1.0, -1)  # put worth at most K
    with pytest.raises(ValueError, match="positive"):
        implied_black_vol(1.0, 100.0, 100.0, 0.0, 1)


def test_intrinsic_price_gives_zero_vol():
    assert implied_black_vol(5.0, 105.0, 100.0, 1.0, 1) == 0.0
