"""Zero curves, rolling, discrete dividends and the forward. QuantLib is the curve oracle."""

import datetime as dt
import math
from dataclasses import replace

import pytest
import QuantLib as ql  # noqa: N813
from hypothesis import given
from hypothesis import strategies as st

from engine.errors import MarketDataError
from engine.market.curves import FlatRateCurve, RolledCurve, ZeroCurve
from engine.market.dividends import Dividend
from engine.market.market_data import MarketData
from engine.market.vol import FlatVolSurface
from engine.risk import bumps

VAL = dt.date(2026, 1, 2)
BASE = MarketData(
    valuation_date=VAL,
    spot=100.0,
    discount=FlatRateCurve(0.03),
    vol=FlatVolSurface(0.2),
    dividend_yield=FlatRateCurve(0.01),
    borrow=FlatRateCurve(0.005),
)

pillars = st.lists(st.integers(1, 3650), min_size=1, max_size=8, unique=True).map(sorted)
rates = st.floats(-0.02, 0.10)


@st.composite
def curves(draw):
    days = draw(pillars)
    zs = [draw(rates) for _ in days]
    return ZeroCurve(tuple(d / 365 for d in days), tuple(zs)), days, zs


@given(curves(), st.integers(1, 5000))
def test_zero_curve_matches_quantlib_loglinear(curve_data, day):
    curve, days, zs = curve_data
    today = ql.Date(VAL.day, VAL.month, VAL.year)
    dc = ql.Actual365Fixed()
    dates = [today] + [today + d for d in days]
    dfs = [1.0] + [math.exp(-z * d / 365) for z, d in zip(zs, days, strict=True)]
    ref = ql.DiscountCurve(dates, dfs, dc)  # log-linear discount factors
    ref.enableExtrapolation()
    t = day / 365
    assert curve.df(t) == pytest.approx(ref.discount(t), rel=1e-12)


@given(curves(), st.floats(0.0, 15.0), st.floats(-0.01, 0.01))
def test_parallel_shift_is_exact(curve_data, t, dz):
    curve = curve_data[0]
    shifted = curve.shifted(dz)
    assert shifted.df(t) == pytest.approx(curve.df(t) * math.exp(-dz * t), rel=1e-12)


@given(curves(), st.floats(0.0, 10.0), st.floats(-0.5, 2.0))
def test_roll_realises_forwards(curve_data, t, h):
    curve = curve_data[0]
    rolled = curve.rolled(h)
    assert rolled.df(t) == pytest.approx(curve.df(t + h) / curve.df(h), rel=1e-12)
    back = rolled.rolled(-h)
    assert back.df(t) == pytest.approx(curve.df(t), rel=1e-12)
    assert rolled.shifted(0.01).df(t) == pytest.approx(
        rolled.df(t) * math.exp(-0.01 * t), rel=1e-12
    )


def test_flat_curve_is_roll_invariant():
    c = FlatRateCurve(0.03)
    assert c.rolled(0.5) is c


@given(curves(), st.floats(0.01, 12.0))
def test_instantaneous_forward_is_log_df_slope(curve_data, t):
    curve = curve_data[0]
    h = 1e-7
    slope = -(math.log(curve.df(t + h)) - math.log(curve.df(t - h))) / (2 * h)
    # Piecewise-flat forward: skip points within h of a pillar (the slope jumps there).
    if all(abs(t - p) > 2 * h for p in curve.times):
        assert curve.instantaneous_forward(t) == pytest.approx(slope, rel=1e-6, abs=1e-8)


def test_zero_rate_before_first_pillar_is_flat():
    c = ZeroCurve((1.0, 2.0), (0.02, 0.03))
    assert c.zero_rate(0.25) == pytest.approx(0.02)
    assert c.zero_rate(0.0) == 0.02
    assert isinstance(c.rolled(0.1), RolledCurve)


def test_invalid_curves_rejected():
    with pytest.raises(MarketDataError):
        ZeroCurve((1.0, 0.5), (0.02, 0.03))
    with pytest.raises(MarketDataError):
        ZeroCurve((), ())
    with pytest.raises(MarketDataError):
        Dividend(VAL, cash=-1.0)
    with pytest.raises(MarketDataError):
        Dividend(VAL, proportional=1.0)


# ------------------------------------------------------------------ dividends and the forward


dividend_lists = st.lists(
    st.tuples(st.integers(1, 1000), st.floats(0.0, 3.0), st.floats(0.0, 0.05)), max_size=5
)


def _market(divs):
    return replace(
        BASE,
        discount=ZeroCurve((0.5, 1.0, 3.0), (0.02, 0.025, 0.03)),
        dividends=tuple(Dividend(VAL + dt.timedelta(days=d), c, p) for d, c, p in divs),
    )


def _forward_by_recursion(market, t):
    """Independent forward: carry to each ex-date, then S → S(1 − δ) − D, carry to t."""
    f, last = market.spot, 0.0
    for e in market.dividend_events(t):
        f *= market.growth(e.t) / market.growth(last)
        f = f * (1.0 - e.proportional) - e.cash
        last = e.t
    return f * market.growth(t) / market.growth(last)


@given(dividend_lists, st.integers(1, 1200))
def test_forward_with_dividends(divs, days):
    m = _market(divs)
    t = days / 365
    assert m.forward(t) == pytest.approx(_forward_by_recursion(m, t), rel=1e-12)


@given(dividend_lists, st.integers(30, 1200))
def test_forward_sensitivities_match_finite_differences(divs, days):
    m = _market(divs)
    t, h = days / 365, 1e-6
    fs = m.forward_sensitivities(t)
    d_spot = (replace(m, spot=m.spot + h).forward(t) - replace(m, spot=m.spot - h).forward(t)) / (
        2 * h
    )
    d_rate = (bumps.bump_rate(m, h).forward(t) - bumps.bump_rate(m, -h).forward(t)) / (2 * h)
    d_yield = (
        bumps.bump_dividend_yield(m, h).forward(t) - bumps.bump_dividend_yield(m, -h).forward(t)
    ) / (2 * h)
    assert fs.d_spot == pytest.approx(d_spot, rel=1e-7)
    assert fs.d_rate == pytest.approx(d_rate, rel=1e-6, abs=1e-6)
    assert fs.d_yield == pytest.approx(d_yield, rel=1e-6, abs=1e-6)


@given(dividend_lists, st.integers(30, 1200), st.integers(0, 29))
def test_escrowed_decomposition_reproduces_forward(divs, days, roll):
    """F(t → T) = (S_t − E_t)·Π_t·G(T)/G(t), at t = 0 and after rolling ``roll`` days."""
    m = _market(divs)
    big_t = days / 365
    t = roll / 365
    rolled = bumps.roll_valuation_date(m, roll)
    lhs = rolled.forward(big_t - t)
    rhs = (
        (rolled.spot - m.escrowed_cash(t, big_t))
        * m.proportional_factor(t, big_t)
        * m.growth(big_t)
        / m.growth(t)
    )
    assert lhs == pytest.approx(rhs, rel=1e-11)


def test_dividend_on_valuation_date_is_past_and_on_expiry_counts(market):
    m = replace(market, dividends=(Dividend(VAL, 5.0), Dividend(VAL + dt.timedelta(days=365), 1.0)))
    assert [e.t for e in m.dividend_events(1.0)] == [1.0]
    assert m.forward(1.0) == pytest.approx(market.forward(1.0) - 1.0)
